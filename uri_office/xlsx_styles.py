"""Save the owner's cell formatting into an .xlsx package at the XML level (owner decision OD-R3, finding XF-1).

Supported properties, the same subset URI reads and shows (`xlsx_model._style`): bold `b`, italic `i`, underline `u`,
font colour `fc`, solid fill `bg` (#RRGGBB), number format `nf`, horizontal alignment `ha` (left/center/right) and
wrap `wrap`. A change names the cell's style as URI showed it (`before`) and as the owner left it (`after`); only the
properties that differ are written. Everything else in the cell's existing style (theme colours, font size and
family, borders, protection, other alignment) is kept exactly, because the new font, fill and cell format are copies
of the cell's current ones with only those properties changed. Identical new records are reused, and nothing else in
styles.xml is touched.
"""
from __future__ import annotations

import copy
import re

from lxml import etree
from openpyxl.styles.numbers import BUILTIN_FORMATS

from . import refs
from .errors import OfficeError
from .xlsx_patch import M, _get_cell, _ser, _xml, sheet_parts

KEYS = ("b", "i", "u", "fc", "bg", "nf", "ha", "wrap")
_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff￾￿]")
_BUILTIN_IDS = {v: k for k, v in BUILTIN_FORMATS.items()}


def check_style(st) -> dict:
    """A style dict from the page or the Brain: only known keys, valid values; False/None/"" mean "not set"."""
    if not isinstance(st, dict) or set(st) - set(KEYS):
        raise OfficeError("BAD_STYLE", "unknown formatting")
    out = {}
    for k, v in st.items():
        if v in (None, False, ""):
            continue
        if k in ("b", "i", "u", "wrap"):
            if v is not True:
                raise OfficeError("BAD_STYLE", k)
            out[k] = True
        elif k in ("fc", "bg"):
            if not isinstance(v, str) or not _HEX.match(v):
                raise OfficeError("BAD_STYLE", k)
            out[k] = "#" + v[1:].upper()
        elif k == "nf":
            if not isinstance(v, str) or len(v) > 255 or _XML_INVALID.search(v):
                raise OfficeError("BAD_STYLE", k)
            if v != "General":
                out[k] = v
        elif k == "ha":
            if v not in ("left", "center", "right"):
                raise OfficeError("BAD_STYLE", k)
            out[k] = v
    return out


def _child(parent, tag):
    return parent.find(M + tag)


def _list(styles, tag, child):
    el = _child(styles, tag)
    if el is None:
        el = etree.SubElement(styles, M + tag, count="0")
    return el


def _add_unique(container, el) -> int:
    """Index of an element equal to `el` in `container`, appending it when there is none."""
    want = etree.tostring(el)
    for i, e in enumerate(container):
        if etree.tostring(e) == want:
            return i
    container.append(el)
    container.set("count", str(len(container)))
    return len(container) - 1


def _set_font(font, changed: dict):
    for key, tag in (("b", "b"), ("i", "i"), ("u", "u")):
        if key in changed:
            for e in font.findall(M + tag):
                font.remove(e)
            if changed[key]:
                font.insert(_font_pos(font, tag), etree.Element(M + tag))
    if "fc" in changed:
        for e in font.findall(M + "color"):
            font.remove(e)
        if changed["fc"]:
            font.insert(_font_pos(font, "color"), etree.Element(M + "color", rgb="FF" + changed["fc"][1:]))


# CT_Font child order (ECMA-376): b i strike condense extend outline shadow u vertAlign sz color name family charset
# scheme. Inserting in schema order keeps Excel from repairing the file.
_FONT_ORDER = ("b", "i", "strike", "condense", "extend", "outline", "shadow", "u", "vertAlign", "sz", "color", "name",
               "family", "charset", "scheme")


def _font_pos(font, tag) -> int:
    rank = _FONT_ORDER.index(tag)
    for i, e in enumerate(font):
        local = etree.QName(e).localname
        if local in _FONT_ORDER and _FONT_ORDER.index(local) > rank:
            return i
    return len(font)


def _fill(bg):
    fill = etree.Element(M + "fill")
    if bg:
        pf = etree.SubElement(fill, M + "patternFill", patternType="solid")
        etree.SubElement(pf, M + "fgColor", rgb="FF" + bg[1:])
        etree.SubElement(pf, M + "bgColor", indexed="64")
    else:
        etree.SubElement(fill, M + "patternFill", patternType="none")
    return fill


def _numfmt_id(styles, code) -> int:
    if code is None:
        return 0
    if code in _BUILTIN_IDS:
        return _BUILTIN_IDS[code]
    nfs = _child(styles, "numFmts")
    if nfs is None:
        nfs = etree.Element(M + "numFmts", count="0")
        styles.insert(0, nfs)
    used = [int(n.get("numFmtId")) for n in nfs]
    for n in nfs:
        if n.get("formatCode") == code:
            return int(n.get("numFmtId"))
    nid = max([163] + used) + 1
    etree.SubElement(nfs, M + "numFmt", numFmtId=str(nid), formatCode=code)
    nfs.set("count", str(len(nfs)))
    return nid


def _new_xf(styles, base_xf, changed: dict) -> int:
    fonts, fills = _list(styles, "fonts", "font"), _list(styles, "fills", "fill")
    xfs = _list(styles, "cellXfs", "xf")
    xf = copy.deepcopy(base_xf)
    if set(changed) & {"b", "i", "u", "fc"}:
        fid = int(xf.get("fontId", "0"))
        font = copy.deepcopy(fonts[fid]) if fid < len(fonts) else etree.Element(M + "font")
        _set_font(font, changed)
        xf.set("fontId", str(_add_unique(fonts, font)))
        xf.set("applyFont", "1")
    if "bg" in changed:
        xf.set("fillId", str(_add_unique(fills, _fill(changed["bg"]))))
        xf.set("applyFill", "1")
    if "nf" in changed:
        xf.set("numFmtId", str(_numfmt_id(styles, changed["nf"])))
        xf.set("applyNumberFormat", "1")
    if set(changed) & {"ha", "wrap"}:
        al = _child(xf, "alignment")
        if al is None:
            al = etree.Element(M + "alignment")
            xf.insert(0, al)
        if "ha" in changed:
            al.attrib.pop("horizontal", None)
            if changed["ha"]:
                al.set("horizontal", changed["ha"])
        if "wrap" in changed:
            al.attrib.pop("wrapText", None)
            if changed["wrap"]:
                al.set("wrapText", "1")
        if not al.attrib:
            xf.remove(al)
        xf.set("applyAlignment", "1")
    return _add_unique(xfs, xf)


def apply_formats(parts: dict, formats: list) -> set:
    """Apply [{"sheet", "cell", "before": style, "after": style}] in place. Returns the changed part names."""
    if not formats:
        return set()
    if "xl/styles.xml" not in parts:
        raise OfficeError("STYLE_NOT_SUPPORTED", "the workbook has no style part")
    styles = _xml(parts["xl/styles.xml"])
    xfs = _list(styles, "cellXfs", "xf")
    if len(xfs) == 0:
        etree.SubElement(xfs, M + "xf", numFmtId="0", fontId="0", fillId="0", borderId="0", xfId="0")
        xfs.set("count", "1")
    by_sheet = sheet_parts(parts)
    roots, changed_parts = {}, {"xl/styles.xml"}
    for f in formats:
        if f["sheet"] not in by_sheet:
            raise OfficeError("UNKNOWN_SHEET", str(f["sheet"])[:64])
        before, after = check_style(f.get("before") or {}), check_style(f.get("after") or {})
        delta = {k: after.get(k) for k in KEYS if before.get(k) != after.get(k)}
        if not delta:
            continue
        part = by_sheet[f["sheet"]]
        root = roots.setdefault(part, _xml(parts[part]))
        c = _get_cell(root.find(M + "sheetData"), refs.canonical_cell(f["cell"]))
        base = xfs[int(c.get("s", "0"))] if int(c.get("s", "0")) < len(xfs) else xfs[0]
        c.set("s", str(_new_xf(styles, base, delta)))
        changed_parts.add(part)
    for part, root in roots.items():
        parts[part] = _ser(root)
    parts["xl/styles.xml"] = _ser(styles)
    return changed_parts
