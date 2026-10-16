"""Spike P1: patch only edited cells inside an .xlsx package.

Edits: [{"sheet": "Sales", "cell": "B3", "value": 25}, {"sheet": "Sales", "cell": "B6", "formula": "=B5*2"}]
Strings are written as inline strings so sharedStrings.xml is never touched.
Any edit sets calcPr fullCalcOnLoad="1"; calcChain.xml is dropped when a formula cell is created or replaced.
"""
import posixpath
import re
import zipfile
from pathlib import Path

from lxml import etree

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
NS_CT = "http://schemas.openxmlformats.org/package/2006/content-types"
M = "{%s}" % NS_MAIN
CELL_RE = re.compile(r"^([A-Z]{1,3})([1-9][0-9]{0,6})$")


class PatchError(ValueError):
    pass


def col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def split_ref(ref: str):
    m = CELL_RE.match(ref)
    if not m:
        raise PatchError(f"bad cell reference {ref!r}")
    return m.group(1), int(m.group(2))


def _xml(data: bytes):
    return etree.fromstring(data, etree.XMLParser(remove_blank_text=False, resolve_entities=False))


def _ser(root) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def sheet_parts(parts: dict) -> dict:
    wb = _xml(parts["xl/workbook.xml"])
    rels = _xml(parts["xl/_rels/workbook.xml.rels"])
    targets = {r.get("Id"): r.get("Target") for r in rels}
    out = {}
    for s in wb.iter(M + "sheet"):
        t = targets[s.get("{%s}id" % NS_REL)]
        out[s.get("name")] = t.lstrip("/") if t.startswith("/") else posixpath.normpath(posixpath.join("xl", t))
    return out


def _merged_non_anchor(root, col: int, row: int) -> bool:
    for mc in root.iter(M + "mergeCell"):
        a, _, b = mc.get("ref").partition(":")
        (ac, ar), (bc, br) = split_ref(a), split_ref(b or a)
        ac, bc = col_index(ac), col_index(bc)
        if ac <= col <= bc and ar <= row <= br and (col, row) != (ac, ar):
            return True
    return False


def _get_cell(sheet_data, ref: str, create: bool):
    letters, row = split_ref(ref)
    col = col_index(letters)
    row_el = None
    for r in sheet_data.iterfind(M + "row"):
        rn = int(r.get("r"))
        if rn == row:
            row_el = r
            break
        if rn > row:
            if not create:
                return None
            row_el = etree.Element(M + "row", r=str(row))
            r.addprevious(row_el)
            break
    if row_el is None:
        if not create:
            return None
        row_el = etree.SubElement(sheet_data, M + "row", r=str(row))
    for c in row_el.iterfind(M + "c"):
        cc = col_index(split_ref(c.get("r"))[0])
        if cc == col:
            return c
        if cc > col:
            if not create:
                return None
            new = etree.Element(M + "c", r=ref)
            c.addprevious(new)
            return new
    if not create:
        return None
    return etree.SubElement(row_el, M + "c", r=ref)


def _set_cell(c, edit) -> bool:
    """Rewrite one cell; keep its style. Returns True if formulas are involved."""
    old_f = c.find(M + "f")
    if old_f is not None and (old_f.get("t") in ("shared", "array")):
        raise PatchError(f"{c.get('r')}: shared/array formula cells are not editable in M1")
    had_formula = old_f is not None
    style = c.get("s")
    for child in list(c):
        c.remove(child)
    for attr in list(c.attrib):
        if attr not in ("r", "s"):
            del c.attrib[attr]
    if style is not None:
        c.set("s", style)
    if "formula" in edit:
        f = str(edit["formula"])
        if not f.startswith("="):
            raise PatchError(f"{c.get('r')}: formula must start with '='")
        etree.SubElement(c, M + "f").text = f[1:]
        return True
    v = edit.get("value")
    if v is None or v == "":
        return had_formula
    if isinstance(v, bool):
        c.set("t", "b")
        etree.SubElement(c, M + "v").text = "1" if v else "0"
    elif isinstance(v, (int, float)):
        etree.SubElement(c, M + "v").text = repr(v) if isinstance(v, float) else str(v)
    else:
        c.set("t", "inlineStr")
        t = etree.SubElement(etree.SubElement(c, M + "is"), M + "t")
        t.text = str(v)
        if t.text != t.text.strip():
            t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    return had_formula


def _extend_dimension(root, refs):
    dim = root.find(M + "dimension")
    if dim is None or not refs:
        return
    a, _, b = dim.get("ref").partition(":")
    (ac, ar), (bc, br) = split_ref(a), split_ref(b or a)
    cols = [col_index(ac), col_index(bc)] + [col_index(split_ref(r)[0]) for r in refs]
    rows = [ar, br] + [split_ref(r)[1] for r in refs]

    def letters(n):
        s = ""
        while n:
            n, rem = divmod(n - 1, 26)
            s = chr(65 + rem) + s
        return s

    new = f"{letters(min(cols))}{min(rows)}:{letters(max(cols))}{max(rows)}"
    if new != dim.get("ref"):
        dim.set("ref", new)


def patch(src: Path, dst: Path, edits: list) -> dict:
    zin = zipfile.ZipFile(src)
    order = zin.infolist()
    parts = {i.filename: zin.read(i.filename) for i in order}
    zin.close()
    by_sheet = sheet_parts(parts)
    grouped = {}
    for e in edits:
        if e.get("sheet") not in by_sheet:
            raise PatchError(f"unknown sheet {e.get('sheet')!r}")
        grouped.setdefault(by_sheet[e["sheet"]], []).append(e)
    formulas = False
    changed = set()
    for part, es in grouped.items():
        root = _xml(parts[part])
        sd = root.find(M + "sheetData")
        for e in es:
            letters, row = split_ref(e["cell"])
            if _merged_non_anchor(root, col_index(letters), row):
                raise PatchError(f"{e['cell']}: inside a merged range (not its anchor)")
            formulas |= _set_cell(_get_cell(sd, e["cell"], create=True), e)
        _extend_dimension(root, [e["cell"] for e in es])
        parts[part] = _ser(root)
        changed.add(part)
    # Recalculate on open so cached values of dependent formulas are refreshed.
    wb = _xml(parts["xl/workbook.xml"])
    calc = wb.find(M + "calcPr")
    if calc is None:
        calc = etree.SubElement(wb, M + "calcPr")
    if calc.get("fullCalcOnLoad") != "1":
        calc.set("fullCalcOnLoad", "1")
        parts["xl/workbook.xml"] = _ser(wb)
        changed.add("xl/workbook.xml")
    if formulas and "xl/calcChain.xml" in parts:
        del parts["xl/calcChain.xml"]
        ct = _xml(parts["[Content_Types].xml"])
        for o in list(ct):
            if o.get("PartName") == "/xl/calcChain.xml":
                ct.remove(o)
        parts["[Content_Types].xml"] = _ser(ct)
        rels = _xml(parts["xl/_rels/workbook.xml.rels"])
        for r in list(rels):
            if r.get("Target", "").endswith("calcChain.xml"):
                rels.remove(r)
        parts["xl/_rels/workbook.xml.rels"] = _ser(rels)
        changed |= {"xl/calcChain.xml", "[Content_Types].xml", "xl/_rels/workbook.xml.rels"}
    tmp = dst.with_suffix(dst.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w") as z:
        for info in order:
            if info.filename in parts:
                z.writestr(info, parts[info.filename], compress_type=info.compress_type)
    tmp.replace(dst)
    return {"changed_parts": sorted(changed)}
