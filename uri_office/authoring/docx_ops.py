"""Word ops on a python-docx Document (milestone C; plan 12_AUTHORING_C_WORD_PLAN.md section 3).

Body blocks (paragraphs and tables, in document order) are addressed by index, and every op that names a block also
carries `expect`: a short SHA-256 address bound to the edit revision, body version, block index and block XML as viewed.
A mismatch is refused (STALE_BLOCK), so an op never lands on a block that moved. Ops touch only the XML they are about; other parts
of the package (comments, footnotes, media, numbering, theme) are left as python-docx loaded them. An op that would
need content it does not handle is refused with AUTHORING_NOT_SUPPORTED and a named reason, before anything changes.
"""
from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from docx.table import Table
from docx.text.paragraph import Paragraph

from ..errors import OfficeError

MAX_TEXT = 20_000
MAX_TABLE = 20
MAX_BLOCKS_SHOWN = 2000
_ALIGN = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT,
          "justify": WD_ALIGN_PARAGRAPH.JUSTIFY}
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
# Paragraph content URI does not rewrite: changing such a paragraph's text would drop or break it.
_FOREIGN = {"ins": "a tracked change", "del": "a tracked change", "moveFrom": "a tracked change",
            "moveTo": "a tracked change", "commentRangeStart": "a comment", "commentRangeEnd": "a comment",
            "sdt": "a content control", "fldSimple": "a field", "smartTag": "a smart tag",
            "customXml": "custom content", "oMath": "an equation", "oMathPara": "an equation"}
_FOREIGN_RUN = {"footnoteReference": "a footnote", "endnoteReference": "an endnote", "fldChar": "a field",
                "object": "an embedded object", "commentReference": "a comment", "drawing": "a picture or shape",
                "pict": "a picture or shape", "sym": "a symbol",
                # Independent review C1-08: tracked formatting and table changes are tracked changes too
                "rPrChange": "a tracked change", "pPrChange": "a tracked change", "sectPrChange": "a tracked change",
                "tblPrChange": "a tracked change", "trPrChange": "a tracked change", "tcPrChange": "a tracked change",
                "numberingChange": "a tracked change", "cellIns": "a tracked change", "cellDel": "a tracked change",
                "cellMerge": "a tracked change"}
_M = "{http://schemas.openxmlformats.org/officeDocument/2006/math}"
# Run children that a text replacement keeps; a run with anything else is not rewritten (C1-08: w:sym was dropped).
_PLAIN_RUN = {_W + "rPr", _W + "t", _W + "tab", _W + "br", _W + "cr", _W + "noBreakHyphen", _W + "softHyphen",
              _W + "lastRenderedPageBreak"}


def _refuse(why: str):
    raise OfficeError("AUTHORING_NOT_SUPPORTED", why)


def _text(v, name="text") -> str:
    if not isinstance(v, str) or len(v) > MAX_TEXT:
        raise OfficeError("BAD_TEXT", name)
    return v


def block_text(el) -> str:
    return "".join(t.text or "" for t in el.iter(_W + "t"))


def block_sha(el, version: bytes, index: int) -> str:
    return hashlib.sha256(version + str(index).encode("ascii") + el.xml.encode("utf-8")).hexdigest()[:12]


def _body(doc):
    return doc.element.body


def _body_version(doc) -> bytes:
    revision = getattr(doc, "_uri_edit_revision", 0)
    return hashlib.sha256(str(revision).encode("ascii") + b"\0" + _body(doc).xml.encode("utf-8")).digest()


def _advance_revision(doc):
    doc._uri_edit_revision = getattr(doc, "_uri_edit_revision", 0) + 1


def blocks(doc) -> list:
    """Body paragraphs and tables in order (the section properties element is not a block)."""
    return [el for el in _body(doc) if el.tag in (_W + "p", _W + "tbl")]


def block(doc, index, expect):
    bl = blocks(doc)
    if not isinstance(index, int) or not 0 <= index < len(bl):
        raise OfficeError("UNKNOWN_BLOCK", str(index)[:16])
    el = bl[index]
    if expect != block_sha(el, _body_version(doc), index):
        raise OfficeError("STALE_BLOCK", "the document changed since this was shown; look again", 409)
    return el


def _para(doc, el) -> Paragraph:
    if el.tag != _W + "p":
        _refuse("that block is a table, not a paragraph")
    return Paragraph(el, doc._body)


def _table(doc, el) -> Table:
    if el.tag != _W + "tbl":
        _refuse("that block is not a table")
    return Table(el, doc._body)


def _section_break(el) -> bool:
    ppr = el.find(_W + "pPr")
    return ppr is not None and ppr.find(_W + "sectPr") is not None


# Independent review C2-03: what a paragraph URI rewrites may contain. Anything else is kept and refused by name
# (an allow-list: unknown content is never dropped silently).
_PLAIN_PARA = {_W + "pPr", _W + "r", _W + "bookmarkStart", _W + "bookmarkEnd", _W + "proofErr", _W + "permStart",
               _W + "permEnd"}


def _local(tag) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else "?"


def _not_plain(el) -> str | None:
    paras = [el] if el.tag == _W + "p" else list(el.iter(_W + "p"))
    for p in paras:
        for child in p:
            if not isinstance(child.tag, str):
                continue
            if child.tag not in _PLAIN_PARA:
                return f"content URI does not edit ({_local(child.tag)})"
            if child.tag == _W + "r":
                for rc in child:
                    if isinstance(rc.tag, str) and rc.tag not in _PLAIN_RUN:
                        return f"content URI does not edit ({_local(rc.tag)})"
    return None


def _foreign(el) -> str | None:
    """The first unsupported content in an XML element and its descendants, named, or None."""
    for child in el.iter():
        if child is el or not isinstance(child.tag, str):
            continue
        # C1-08: compare by namespace and local name (equations are in the math namespace, not the Word one)
        if child.tag.startswith(_M):
            return "an equation"
        name = child.tag[len(_W):] if child.tag.startswith(_W) else ""
        if not name:
            continue
        if name in _FOREIGN:
            return _FOREIGN[name]
        if name in _FOREIGN_RUN:
            return _FOREIGN_RUN[name]
        if name in ("hyperlink",):
            return "a link"
    return _not_plain(el)


def _insert_at(doc, after, new_el, after_expect=None):
    """Insert a block after block `after` (an index; None = at the start). With `after_expect` the block is checked
    against its address like any other op (independent review C1-11; the op map requires it)."""
    if after is not None and after_expect is not None:
        block(doc, after, after_expect)
    body = _body(doc)
    bl = blocks(doc)
    if after is None:
        if bl:
            bl[0].addprevious(new_el)
        else:
            sect = body.find(_W + "sectPr")
            if sect is not None:
                sect.addprevious(new_el)
            else:
                body.append(new_el)
    else:
        if not isinstance(after, int) or not 0 <= after < len(bl):
            raise OfficeError("BAD_POSITION", "after")
        bl[after].addnext(new_el)
    return blocks(doc).index(new_el)


def _style(doc, name, kind="paragraph"):
    from docx.enum.style import WD_STYLE_TYPE
    want = WD_STYLE_TYPE.PARAGRAPH if kind == "paragraph" else WD_STYLE_TYPE.TABLE
    for st in doc.styles:
        if st.type == want and st.name == name:
            return st
    raise OfficeError("UNKNOWN_STYLE", str(name)[:60])


def paragraph_styles(doc) -> list:
    from docx.enum.style import WD_STYLE_TYPE
    names = [st.name for st in doc.styles if st.type == WD_STYLE_TYPE.PARAGRAPH and not getattr(st, "hidden", False)]
    first = [n for n in ("Normal", "Title", "Subtitle", "Heading 1", "Heading 2", "Heading 3", "List Bullet",
                         "List Number", "Quote") if n in names]
    return first + sorted(n for n in names if n not in first)


def _set_runs(p: Paragraph, text: str):
    """Replace the paragraph's text, keeping its first run's formatting."""
    runs = p._p.findall(_W + "r")
    rpr = None
    if runs and runs[0].find(_W + "rPr") is not None:
        rpr = copy.deepcopy(runs[0].find(_W + "rPr"))
    for r in runs:
        p._p.remove(r)
    if text:
        r = p.add_run(text)
        if rpr is not None:
            r._r.insert(0, rpr)


# ---- paragraphs ----------------------------------------------------------------------------------------------------
def insert_paragraph(doc, after, text: str, style=None) -> int:
    el = OxmlElement("w:p")
    i = _insert_at(doc, after, el)
    p = Paragraph(el, doc._body)
    if style is not None:
        p.style = _style(doc, style)
    if _text(text):
        p.add_run(text)
    _advance_revision(doc)
    return i


def set_paragraph_text(doc, index, expect, text: str):
    el = block(doc, index, expect)
    p = _para(doc, el)
    why = _foreign(el)
    if why:
        _refuse(f"this paragraph has {why}, which URI does not rewrite")
    _set_runs(p, _text(text))


def delete_block(doc, index, expect):
    el = block(doc, index, expect)
    if el.tag == _W + "p" and _section_break(el):
        _refuse("this paragraph ends a section (page layout); it is kept")
    why = _foreign(el)
    if why:
        kind = "paragraph" if el.tag == _W + "p" else "table"
        _refuse(f"this {kind} has {why}, which URI does not remove")
    if len(blocks(doc)) == 1:
        _refuse("a document keeps at least one paragraph")
    el.getparent().remove(el)
    _advance_revision(doc)


def move_block(doc, index, expect, to: int):
    el = block(doc, index, expect)
    bl = blocks(doc)
    if not isinstance(to, int) or not 0 <= to < len(bl):
        raise OfficeError("BAD_POSITION", "to")
    if el.tag == _W + "p" and _section_break(el) or any(_section_break(b) for b in bl if b.tag == _W + "p"
                                                        and min(index, to) <= bl.index(b) <= max(index, to)
                                                        and b is not el):
        _refuse("moving across a section break would change the page layout")
    if to == index:
        return
    el.getparent().remove(el)
    rest = blocks(doc)
    if to >= len(rest):
        rest[-1].addnext(el)
    else:
        rest[to].addprevious(el)
    _advance_revision(doc)


def set_style(doc, index, expect, style: str):
    p = _para(doc, block(doc, index, expect))
    p.style = _style(doc, style)


def format_text(doc, index, expect, fmt: dict):
    p = _para(doc, block(doc, index, expect))
    if not isinstance(fmt, dict) or not fmt or set(fmt) - {"b", "i", "u", "size", "color", "align"}:
        raise OfficeError("BAD_FORMAT", "unknown formatting")
    for k in ("b", "i", "u"):
        if k in fmt and not isinstance(fmt[k], bool):
            raise OfficeError("BAD_FORMAT", k)
    if "size" in fmt and (not isinstance(fmt["size"], (int, float)) or not 6 <= fmt["size"] <= 200):
        raise OfficeError("BAD_FORMAT", "size")
    if "color" in fmt and not (isinstance(fmt["color"], str) and len(fmt["color"]) == 7 and fmt["color"][0] == "#"):
        raise OfficeError("BAD_FORMAT", "color")
    if "align" in fmt and fmt["align"] not in _ALIGN:
        raise OfficeError("BAD_FORMAT", "align")
    if "align" in fmt:
        p.alignment = _ALIGN[fmt["align"]]
    for r in p.runs:
        for k, attr in (("b", "bold"), ("i", "italic"), ("u", "underline")):
            if k in fmt:
                setattr(r.font, attr, fmt[k])
        if "size" in fmt:
            r.font.size = Pt(fmt["size"])
        if "color" in fmt:
            r.font.color.rgb = RGBColor.from_string(fmt["color"][1:].upper())


def insert_page_break(doc, after) -> int:
    el = OxmlElement("w:p")
    i = _insert_at(doc, after, el)
    Paragraph(el, doc._body).add_run().add_break(WD_BREAK.PAGE)
    _advance_revision(doc)
    return i


def replace_text(doc, find: str, replace: str, match_case: bool = True) -> dict:
    """Replaces matches that lie inside one run (formatting kept). Matches split across runs are counted, not changed.
    Paragraphs with content URI does not rewrite (tracked changes, fields, ...) are skipped and counted."""
    if not isinstance(find, str) or not find or len(find) > 500:
        raise OfficeError("BAD_TEXT", "find")
    _text(replace, "replace")
    if not isinstance(match_case, bool):
        raise OfficeError("BAD_OP", "match_case")
    import re
    pat = re.compile(re.escape(find), 0 if match_case else re.IGNORECASE)
    changed = split = skipped = 0
    paras = list(doc.paragraphs)
    seen = set()
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                # R8-01: a merged cell is returned once per grid position; replace in each underlying cell once
                if id(c._tc) in seen:
                    continue
                seen.add(id(c._tc))
                paras.extend(c.paragraphs)
    for p in paras:
        if not pat.search(block_text(p._p)):          # all text, including tracked insertions
            continue
        if _foreign(p._p) is not None:
            skipped += 1
            continue
        total = len(pat.findall(p.text))
        inside = 0
        for r in p.runs:
            n = len(pat.findall(r.text))
            if not n:
                continue
            if any(c.tag not in _PLAIN_RUN for c in r._r):
                skipped += 1                          # C1-08: never rewrite a run that holds more than text;
                total -= n                            # C2-05: and never count it as replaced
                continue
            r.text = pat.sub(lambda m: replace, r.text)
            inside += n
        changed += inside
        split += max(0, total - inside)
    if changed == 0 and split == 0 and skipped == 0:
        raise OfficeError("NOT_FOUND", "no matches")
    return {"replaced": changed, "split_across_formatting": split, "skipped": skipped}


# ---- tables --------------------------------------------------------------------------------------------------------
def _cells(cells):
    if not isinstance(cells, list) or not 1 <= len(cells) <= MAX_TABLE or not all(
            isinstance(r, list) and 1 <= len(r) <= MAX_TABLE for r in cells):
        raise OfficeError("BAD_TABLE", "1 to 20 rows and columns")
    cols = max(len(r) for r in cells)
    return [[_text(r[c]) if c < len(r) else "" for c in range(cols)] for r in cells]


def insert_table(doc, after, cells) -> int:
    cells = _cells(cells)
    t = doc.add_table(rows=len(cells), cols=len(cells[0]))
    try:
        t.style = _style(doc, "Table Grid", "table")
    except OfficeError:
        pass
    for r, row in enumerate(cells):
        for c, v in enumerate(row):
            t.cell(r, c).text = v
    el = t._tbl
    el.getparent().remove(el)
    i = _insert_at(doc, after, el)
    _advance_revision(doc)
    return i


def _cell(doc, index, expect, row, col):
    t = _table(doc, block(doc, index, expect))
    if not isinstance(row, int) or not isinstance(col, int) or not 0 <= row < len(t.rows) or \
            not 0 <= col < len(t.columns):
        raise OfficeError("BAD_POSITION", "row or column")
    return t, t.cell(row, col)


def set_table_cell(doc, index, expect, row, col, text: str):
    _, c = _cell(doc, index, expect, row, col)
    text = _text(text)
    for child in c._tc:
        if child.tag not in (_W + "tcPr", _W + "p"):
            _refuse("this cell has other content, which URI does not rewrite")
    ps = c.paragraphs
    for p in ps:
        why = _foreign(p._p)
        if why:
            _refuse(f"this cell has {why}, which URI does not rewrite")
    for extra in ps[1:]:
        extra._p.getparent().remove(extra._p)
    _set_runs(ps[0], text)


def add_table_row(doc, index, expect, after_row: int):
    t = _table(doc, block(doc, index, expect))
    if not isinstance(after_row, int) or not 0 <= after_row < len(t.rows):
        raise OfficeError("BAD_POSITION", "row")
    src = t.rows[after_row]._tr
    if src.find(".//" + _W + "vMerge") is not None or src.find(".//" + _W + "gridSpan") is not None:
        _refuse("this row has merged cells")
    if any(child.tag not in (_W + "trPr", _W + "tc") for child in src):
        _refuse("this row has other content, which URI does not clone")
    for tc in src.iter(_W + "tc"):
        if any(child.tag not in (_W + "tcPr", _W + "p") for child in tc):
            _refuse("this row has other cell content, which URI does not clone")
        for p in tc.findall(_W + "p"):
            why = _foreign(p)
            if why:
                _refuse(f"this row has {why}, which URI does not clone")
            if any(child.tag not in (_W + "pPr", _W + "r") for child in p):
                _refuse("this row has other paragraph content, which URI does not clone")
    new = copy.deepcopy(src)
    for tc in new.iter(_W + "tc"):
        for p in tc.findall(_W + "p")[1:]:
            tc.remove(p)
        for r in tc.findall(_W + "p")[0].findall(_W + "r"):
            r.getparent().remove(r)
    src.addnext(new)
    _advance_revision(doc)


def delete_table_row(doc, index, expect, row: int):
    t = _table(doc, block(doc, index, expect))
    if not isinstance(row, int) or not 0 <= row < len(t.rows):
        raise OfficeError("BAD_POSITION", "row")
    if len(t.rows) == 1:
        _refuse("a table keeps at least one row; delete the table instead")
    tr = t.rows[row]._tr
    if tr.find(".//" + _W + "vMerge") is not None:
        _refuse("this row has merged cells")
    why = _foreign(tr)
    if why:
        _refuse(f"this row has {why}, which URI does not remove")
    tr.getparent().remove(tr)
    _advance_revision(doc)


# ---- pictures ------------------------------------------------------------------------------------------------------
def insert_image(doc, after, image_path: Path, width: float = 0.5) -> int:
    if not isinstance(width, (int, float)) or not 0.05 <= width <= 1:
        raise OfficeError("BAD_BOX", "width as a fraction of the text width")
    sec = doc.sections[0]
    text_w = sec.page_width - sec.left_margin - sec.right_margin
    el = OxmlElement("w:p")
    i = _insert_at(doc, after, el)
    try:
        Paragraph(el, doc._body).add_run().add_picture(str(image_path), width=int(text_w * width))
    except Exception as e:  # noqa: BLE001 - an image python-docx cannot read is one refusal
        el.getparent().remove(el)
        raise OfficeError("BAD_IMAGE", type(e).__name__) from None
    _advance_revision(doc)
    return i


# ---- page ----------------------------------------------------------------------------------------------------------
def _hf(doc, which):
    sec = doc.sections[0]
    hf = sec.header if which == "header" else sec.footer
    if hf.is_linked_to_previous:
        hf.is_linked_to_previous = False
    return hf


def _set_hf_text(doc, which, text):
    hf = _hf(doc, which)
    for p in hf.paragraphs:
        why = _foreign(p._p)
        if why and why != "a field":
            _refuse(f"the {which} has {why}, which URI does not rewrite")
    ps = hf.paragraphs
    for extra in ps[1:]:
        if extra._p.find(".//" + _W + "fldSimple") is None and extra._p.find(".//" + _W + "fldChar") is None:
            extra._p.getparent().remove(extra._p)
    first = ps[0]
    if first._p.find(".//" + _W + "fldSimple") is not None or first._p.find(".//" + _W + "fldChar") is not None:
        p = OxmlElement("w:p")
        first._p.addprevious(p)
        first = Paragraph(p, hf)
    _set_runs(first, _text(text))


def set_header_text(doc, text: str):
    _set_hf_text(doc, "header", text)


def set_footer_text(doc, text: str):
    _set_hf_text(doc, "footer", text)


def insert_page_number(doc, where: str = "footer", align: str = "center"):
    if where not in ("header", "footer") or align not in _ALIGN:
        raise OfficeError("BAD_POSITION", "where or align")
    hf = _hf(doc, where)
    if any(p._p.find(".//" + _W + "fldSimple") is not None for p in hf.paragraphs):
        _refuse(f"the {where} already has a field")
    p = hf.add_paragraph()
    p.alignment = _ALIGN[align]
    fld = OxmlElement("w:fldSimple")
    fld.set(qn("w:instr"), "PAGE")
    r = OxmlElement("w:r")
    t = OxmlElement("w:t")
    t.text = "1"
    r.append(t)
    fld.append(r)
    p._p.append(fld)


def set_page_setup(doc, orientation=None, margins_cm=None):
    if orientation is not None and orientation not in ("portrait", "landscape"):
        raise OfficeError("BAD_FORMAT", "orientation")
    if margins_cm is not None:
        if not isinstance(margins_cm, dict) or set(margins_cm) - {"top", "bottom", "left", "right"} or not all(
                isinstance(v, (int, float)) and 0 <= v <= 10 for v in margins_cm.values()):
            raise OfficeError("BAD_FORMAT", "margins in cm, 0 to 10")
    if orientation is None and not margins_cm:
        raise OfficeError("BAD_OP", "nothing to change")
    for sec in doc.sections:
        if orientation is not None:
            want = WD_ORIENT.LANDSCAPE if orientation == "landscape" else WD_ORIENT.PORTRAIT
            if sec.orientation != want:
                w, h = sec.page_width, sec.page_height
                sec.orientation = want
                sec.page_width, sec.page_height = (max(w, h), min(w, h)) if orientation == "landscape" else \
                    (min(w, h), max(w, h))
        for k, v in (margins_cm or {}).items():
            setattr(sec, f"{k}_margin", Cm(v))


# ---- view ----------------------------------------------------------------------------------------------------------
def describe(doc) -> dict:
    """What the edit panes show: blocks in order (text, style, kind, address hash), styles, page setup, header and
    footer text. No file paths and no binary data."""
    out = []
    for i, el in enumerate(blocks(doc)[:MAX_BLOCKS_SHOWN]):
        it = {"index": i}
        if el.tag == _W + "p":
            p = Paragraph(el, doc._body)
            style = p.style.name if p.style is not None else "Normal"
            level = None
            if style.startswith("Heading ") and style[8:].isdigit():
                level = int(style[8:])
            elif style == "Title":
                level = 0
            runs = [r for r in p.runs if r.text.strip()]
            it.update(kind="paragraph", style=style, level=level, text=p.text[:4000],
                      bold=bool(runs) and all(r.bold is True for r in runs),
                      italic=bool(runs) and all(r.italic is True for r in runs),
                      picture=el.find(".//" + _W + "drawing") is not None,
                      page_break=any(b.get(qn("w:type")) == "page" for b in el.iter(_W + "br")),
                      section_break=_section_break(el), locked=_foreign(el))
        else:
            t = Table(el, doc._body)
            it.update(kind="table", rows=len(t.rows), cols=len(t.columns),
                      cells=[[c.text[:500] for c in r.cells][:MAX_TABLE] for r in t.rows][:MAX_TABLE])
        out.append(it)
    sec = doc.sections[0]
    hf = {}
    for which in ("header", "footer"):
        h = getattr(sec, which)
        hf[which] = "" if h.is_linked_to_previous and len(doc.sections) == 1 and not h.paragraphs else \
            "\n".join(p.text for p in h.paragraphs).strip()
    result = {"blocks": out, "truncated": len(blocks(doc)) > MAX_BLOCKS_SHOWN, "styles": paragraph_styles(doc),
            "page": {"orientation": "landscape" if sec.orientation == WD_ORIENT.LANDSCAPE else "portrait",
                     "margins_cm": {k: round(getattr(sec, f"{k}_margin").cm, 2) if getattr(sec, f"{k}_margin")
                                    is not None else None for k in ("top", "bottom", "left", "right")},
                     "width_cm": round(sec.page_width.cm, 2) if sec.page_width else None,
                     "height_cm": round(sec.page_height.cm, 2) if sec.page_height else None,
                     "sections": len(doc.sections)},
            "header": hf["header"], "footer": hf["footer"]}
    version = _body_version(doc)
    for i, (it, el) in enumerate(zip(out, blocks(doc))):
        it["expect"] = block_sha(el, version, i)
    return result


def check_after(doc, op) -> int | None:
    """An insert names the block it goes after with that block's address, like every other op that names a block
    (plan 12 section 2; independent review C1-11). None means at the start of the document."""
    after = op.get("after")
    if after is not None:
        block(doc, after, op["after_expect"])
    return after


OPS = {
    "insert_paragraph": lambda d, op: insert_paragraph(d, check_after(d, op), op["text"], op.get("style")),
    "set_paragraph_text": lambda d, op: set_paragraph_text(d, op["block"], op["expect"], op["text"]),
    "delete_block": lambda d, op: delete_block(d, op["block"], op["expect"]),
    "move_block": lambda d, op: move_block(d, op["block"], op["expect"], op["to"]),
    "set_style": lambda d, op: set_style(d, op["block"], op["expect"], op["style"]),
    "format_text": lambda d, op: format_text(d, op["block"], op["expect"], op["format"]),
    "insert_page_break": lambda d, op: insert_page_break(d, check_after(d, op)),
    "replace_text": lambda d, op: replace_text(d, op["find"], op["replace"], op.get("match_case", True)),
    "insert_table": lambda d, op: insert_table(d, check_after(d, op), op["cells"]),
    "set_table_cell": lambda d, op: set_table_cell(d, op["block"], op["expect"], op["row"], op["col"], op["text"]),
    "add_table_row": lambda d, op: add_table_row(d, op["block"], op["expect"], op["after_row"]),
    "delete_table_row": lambda d, op: delete_table_row(d, op["block"], op["expect"], op["row"]),
    "set_header_text": lambda d, op: set_header_text(d, op["text"]),
    "set_footer_text": lambda d, op: set_footer_text(d, op["text"]),
    "insert_page_number": lambda d, op: insert_page_number(d, op.get("where", "footer"), op.get("align", "center")),
    "set_page_setup": lambda d, op: set_page_setup(d, op.get("orientation"), op.get("margins_cm")),
    # insert_image needs a granted file path; the session resolves the grant and calls insert_image itself.
}
