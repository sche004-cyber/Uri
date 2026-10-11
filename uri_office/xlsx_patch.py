"""Write approved cell changes into an .xlsx package and leave every other part byte-identical (AC4).

Library: lxml (already shipped with URI; python-docx and python-pptx require it). The standard library's ElementTree
renames namespace prefixes and drops declarations that `mc:Ignorable` depends on, which makes Excel report a repair.

Rules
  * Edits are cell values or formulas only (`{"sheet", "cell", "value"}` or `{"sheet", "cell", "formula"}`).
  * Strings are written as inline strings, so `xl/sharedStrings.xml` is never touched. The cell keeps its style (`s`).
  * Any edit sets `calcPr fullCalcOnLoad="1"` so dependent formulas are recalculated when the file is opened.
  * When a formula cell is created or replaced, `xl/calcChain.xml` is removed together with its content-type override
    and workbook relationship (Excel rebuilds it).
  * Refused: cells inside a merged range other than its anchor, shared/array formula cells, Excel table header
    and totals rows, unknown sheets, bad refs.
  * The result is written to a temp file next to the destination and moved into place (atomic on the same volume).
"""
from __future__ import annotations

import os
import posixpath
import zipfile
from pathlib import Path

from lxml import etree

from . import refs
from .errors import OfficeError

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
M = "{%s}" % NS_MAIN
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
_PARSER = etree.XMLParser(remove_blank_text=False, resolve_entities=False, no_network=True, huge_tree=False)


def _xml(data: bytes):
    return etree.fromstring(data, _PARSER)


def _ser(root) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def sheet_parts(parts: dict) -> dict:
    """Sheet name -> package part name, from workbook.xml and its relationships."""
    wb = _xml(parts["xl/workbook.xml"])
    rels = _xml(parts["xl/_rels/workbook.xml.rels"])
    targets = {r.get("Id"): r.get("Target") for r in rels}
    out = {}
    for s in wb.iter(M + "sheet"):
        t = targets.get(s.get("{%s}id" % NS_REL))
        if not t:
            continue
        out[s.get("name")] = t.lstrip("/") if t.startswith("/") else posixpath.normpath(posixpath.join("xl", t))
    return out


def _in_merged_non_anchor(root, col, row) -> bool:
    for mc in root.iter(M + "mergeCell"):
        c1, r1, c2, r2 = refs.parse_range(mc.get("ref"))
        if c1 <= col <= c2 and r1 <= row <= r2 and (col, row) != (c1, r1):
            return True
    return False


def _get_cell(sheet_data, ref):
    col, row = refs.parse_cell(ref)
    row_el = None
    for r in sheet_data.iterfind(M + "row"):
        rn = int(r.get("r"))
        if rn == row:
            row_el = r
            break
        if rn > row:
            row_el = etree.Element(M + "row", r=str(row))
            r.addprevious(row_el)
            break
    if row_el is None:
        row_el = etree.SubElement(sheet_data, M + "row", r=str(row))
    for c in row_el.iterfind(M + "c"):
        cc = refs.parse_cell(c.get("r"))[0]
        if cc == col:
            return c
        if cc > col:
            new = etree.Element(M + "c", r=ref)
            c.addprevious(new)
            return new
    return etree.SubElement(row_el, M + "c", r=ref)


def _set_cell(c, edit) -> bool:
    """Rewrite one cell, keeping its style. True if a formula was created or removed."""
    old_f = c.find(M + "f")
    if old_f is not None and old_f.get("t") in ("shared", "array"):
        raise OfficeError("CELL_NOT_EDITABLE", f"{c.get('r')}: shared or array formula")
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
        f = edit["formula"]
        if not isinstance(f, str) or not f.startswith("=") or len(f) < 2:
            raise OfficeError("BAD_FORMULA", c.get("r"))
        etree.SubElement(c, M + "f").text = f[1:]
        return True
    v = edit.get("value")
    if v is None or v == "":
        return had_formula
    if isinstance(v, bool):
        c.set("t", "b")
        etree.SubElement(c, M + "v").text = "1" if v else "0"
    elif isinstance(v, (int, float)):
        if v != v or v in (float("inf"), float("-inf")):
            raise OfficeError("BAD_VALUE", c.get("r"))
        etree.SubElement(c, M + "v").text = repr(v) if isinstance(v, float) else str(v)
    elif isinstance(v, str):
        c.set("t", "inlineStr")
        t = etree.SubElement(etree.SubElement(c, M + "is"), M + "t")
        t.text = v
        if v != v.strip() or "\n" in v:
            t.set(XML_SPACE, "preserve")
    else:
        raise OfficeError("BAD_VALUE", c.get("r"))
    return had_formula


def _extend_dimension(root, cells):
    dim = root.find(M + "dimension")
    if dim is None or not cells:
        return
    c1, r1, c2, r2 = refs.parse_range(dim.get("ref"))
    pts = [refs.parse_cell(x) for x in cells]
    new = "%s:%s" % (refs.cell_ref(min([c1] + [p[0] for p in pts]), min([r1] + [p[1] for p in pts])),
                     refs.cell_ref(max([c2] + [p[0] for p in pts]), max([r2] + [p[1] for p in pts])))
    if new != dim.get("ref"):
        dim.set("ref", new)


def _table_locks(parts: dict, sheet_part: str) -> set:
    """Header and totals rows of Excel tables on this sheet: their text must keep matching the table's column
    definitions in xl/tables/tableN.xml, which this patcher never edits, so Excel would otherwise repair the file."""
    folder, name = posixpath.split(sheet_part)
    rels_name = posixpath.join(folder, "_rels", name + ".rels")
    if rels_name not in parts:
        return set()
    locked = set()
    for r in _xml(parts[rels_name]):
        if not r.get("Type", "").endswith("/table"):
            continue
        target = r.get("Target", "")
        tpart = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join(folder, target))
        if tpart not in parts:
            continue
        t = _xml(parts[tpart])
        c1, r1, c2, r2 = refs.parse_range(t.get("ref"))
        head, tot = int(t.get("headerRowCount", "1")), int(t.get("totalsRowCount", "0"))
        rows = list(range(r1, r1 + head)) + list(range(r2 - tot + 1, r2 + 1) if tot else [])
        locked |= {refs.cell_ref(c, row) for row in rows for c in range(c1, c2 + 1)}
    return locked


def _locks(parts: dict, sheet_part: str, root) -> set:
    locked = set()
    for c in root.iter(M + "c"):
        f = c.find(M + "f")
        if f is not None and f.get("t") in ("shared", "array"):
            locked.add(c.get("r"))
    for mc in root.iter(M + "mergeCell"):
        c1, r1, c2, r2 = refs.parse_range(mc.get("ref"))
        if (c2 - c1 + 1) * (r2 - r1 + 1) > 10_000:
            continue
        locked |= {refs.cell_ref(c, r) for c in range(c1, c2 + 1) for r in range(r1, r2 + 1)} - {refs.cell_ref(c1, r1)}
    return locked | _table_locks(parts, sheet_part)


def locked_cells(path: Path) -> dict:
    """Sheet name -> sorted refs this patcher refuses to edit (shared/array formula cells, merged non-anchors, table
    header and totals rows), so the panel can show them read-only instead of failing at save time."""
    with zipfile.ZipFile(path) as z:
        parts = {n: z.read(n) for n in z.namelist() if n.endswith(".xml") or n.endswith(".rels")}
    out = {}
    for name, part in sheet_parts(parts).items():
        if part in parts:
            out[name] = sorted(_locks(parts, part, _xml(parts[part])))
    return out


def patch(src: Path, dst: Path, edits: list) -> dict:
    """Apply `edits` to the package at `src` and write the result to `dst` (may equal `src`)."""
    if not edits:
        raise OfficeError("NOTHING_TO_SAVE")
    try:
        zin = zipfile.ZipFile(src)
    except zipfile.BadZipFile:
        raise OfficeError("NOT_AN_XLSX", "the file is not a valid .xlsx package") from None
    with zin:
        order = zin.infolist()
        parts = {i.filename: zin.read(i.filename) for i in order}
    by_sheet = sheet_parts(parts)
    grouped: dict[str, list] = {}
    for e in edits:
        if e.get("sheet") not in by_sheet:
            raise OfficeError("UNKNOWN_SHEET", str(e.get("sheet"))[:64])
        grouped.setdefault(by_sheet[e["sheet"]], []).append(e)
    formulas = False
    changed = set()
    for part, es in grouped.items():
        root = _xml(parts[part])
        sd = root.find(M + "sheetData")
        tables = _table_locks(parts, part)
        for e in es:
            col, row = refs.parse_cell(e["cell"])
            if _in_merged_non_anchor(root, col, row):
                raise OfficeError("CELL_NOT_EDITABLE", f"{e['cell']}: inside a merged range")
            if e["cell"] in tables:
                raise OfficeError("CELL_NOT_EDITABLE", f"{e['cell']}: table header or totals row")
            formulas |= _set_cell(_get_cell(sd, e["cell"]), e)
        _extend_dimension(root, [e["cell"] for e in es])
        parts[part] = _ser(root)
        changed.add(part)
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
            if r.get("Target", "").rsplit("/", 1)[-1] == "calcChain.xml":
                rels.remove(r)
        parts["xl/_rels/workbook.xml.rels"] = _ser(rels)
        changed |= {"xl/calcChain.xml", "[Content_Types].xml", "xl/_rels/workbook.xml.rels"}
    tmp = dst.with_name(dst.name + ".uri-office.tmp")
    try:
        with zipfile.ZipFile(tmp, "w") as z:
            for info in order:
                if info.filename in parts:
                    z.writestr(info, parts[info.filename], compress_type=info.compress_type)
        os.replace(tmp, dst)
    finally:
        if tmp.exists():
            tmp.unlink()
    return {"changed_parts": sorted(changed)}
