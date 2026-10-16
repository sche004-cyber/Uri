"""Insert and delete whole rows in an .xlsx package at the XML level (owner decision OD-R3, findings XB-2 / XF-1).

What moves with the rows, on the target sheet and wherever the target sheet is referred to:
  * cells and row elements (`<row r>`, `<c r>`), the sheet dimension, merged ranges, conditional formatting ranges and
    their rule formulas, data-validation ranges and formulas, hyperlinks, the auto-filter range, manual row breaks;
  * every formula in the workbook that refers to the target sheet (unqualified on the target sheet itself, qualified
    `Sheet!A1` / `'My Sheet'!A1` anywhere), array formula ranges, and defined names in workbook.xml;
  * shared formulas whose master refers to the target sheet are first written out as ordinary formulas
    (openpyxl's Translator), because a shared group that straddles the moved rows would otherwise change meaning.
Deleted cells that formulas pointed at become `#REF!` (as Excel does); ranges that lose some rows shrink.

What is refused, explicitly and before anything is written (`STRUCTURE_NOT_SUPPORTED` with the reason), because this
module does not rewrite those parts and moving rows under them would corrupt the file: Excel tables on the sheet or
tables whose formulas name the sheet, drawings (charts, images, shapes) and comments anchored on the sheet, charts or
pivot caches anywhere that read from the sheet, slicers, data-table (what-if) formulas, sheet extensions it does not
parse (`extLst`: data bars, sparklines, x14 validations), sheet protection, 3-D references (`Sheet1:Sheet3!A1`),
array formulas or merged ranges cut by a deletion, and formulas it cannot tokenize.

`calcChain.xml` is removed (Excel rebuilds it) and `fullCalcOnLoad` is set. Untouched parts stay byte-identical.
"""
from __future__ import annotations

import posixpath
import re

from lxml import etree
from openpyxl.formula.tokenizer import Tokenizer, TokenizerError
from openpyxl.formula.translate import Translator

from . import refs
from .errors import OfficeError
from .xlsx_patch import M, NS_MAIN, NS_REL, _ser, _xml, sheet_parts

MAX_ROWS_PER_OP = 1000
_REF = re.compile(r"^(\$?)([A-Z]{1,3})?(\$?)([0-9]{1,7})?$")
DRAWING_TYPES = ("/drawing", "/comments", "/vmlDrawing", "/table", "/pivotTable", "/threadedComment", "/slicer",
                 "/timeline")


def _refuse(why: str):
    raise OfficeError("STRUCTURE_NOT_SUPPORTED", why)


# ---- one reference -----------------------------------------------------------------------------------------------
class _Shift:
    """Row mapping for one structural change: insert `count` rows above row `at`, or delete rows at..at+count-1."""

    def __init__(self, op: str, at: int, count: int):
        self.op, self.at, self.count = op, at, count
        self.last = at + count - 1

    def row(self, r: int):
        """New row number of a single cell row, or None when the row is deleted."""
        if self.op == "insert_rows":
            n = r + self.count if r >= self.at else r
            if n > refs.MAX_ROW:
                _refuse("rows would be pushed past the last row of the sheet")
            return n
        if self.at <= r <= self.last:
            return None
        return r - self.count if r > self.last else r

    def span(self, r1: int, r2: int):
        """New (r1, r2) of a row span, or None when every row of it is deleted."""
        if self.op == "insert_rows":
            n1, n2 = r1 + self.count if r1 >= self.at else r1, r2 + self.count if r2 >= self.at else r2
            if n1 > refs.MAX_ROW or n2 > refs.MAX_ROW:
                _refuse("rows would be pushed past the last row of the sheet")
            return n1, n2
        if self.at <= r1 and r2 <= self.last:
            return None
        n1 = r1 if r1 < self.at else (self.at if r1 <= self.last else r1 - self.count)
        n2 = r2 if r2 < self.at else (self.at - 1 if r2 <= self.last else r2 - self.count)
        return n1, n2


def _split_sheet(token: str):
    """('Sheet', 'A1:B2') for "Sheet!A1:B2" or "'My Sheet'!A1"; (None, token) when unqualified."""
    if "!" not in token:
        return None, token
    sheet, ref = token.rsplit("!", 1)
    if sheet.startswith("'") and sheet.endswith("'"):
        sheet = sheet[1:-1].replace("''", "'")
    if ":" in sheet:
        _refuse("3-D references across several sheets are not supported")
    return sheet, ref


def _shift_area(ref: str, sh: _Shift):
    """Shift one A1 area ("A1", "$A$1:B$7", "3:5", "A:C"). Returns the new text, "#REF!", or None when the text is
    not a cell area (a defined name, an error literal...)."""
    parts = ref.split(":")
    if len(parts) > 2:
        return None
    ms = [_REF.match(p) for p in parts]
    if not all(ms) or any(not (m.group(2) or m.group(4)) for m in ms):
        return None
    rows = [int(m.group(4)) if m.group(4) else None for m in ms]
    if any(r is None for r in rows):          # whole columns: rows do not move
        return ref
    if len(rows) == 1:
        n = sh.row(rows[0])
        if n is None:
            return "#REF!"
        new = [n]
    else:
        span = sh.span(min(rows), max(rows))
        if span is None:
            return "#REF!"
        new = list(span) if rows[0] <= rows[1] else [span[1], span[0]]
    out = []
    for m, r in zip(ms, new):
        if r > refs.MAX_ROW:
            _refuse("rows would be pushed past the last row of the sheet")
        out.append(f"{m.group(1)}{m.group(2) or ''}{m.group(3)}{r}")
    return ":".join(out)


def shift_formula(formula: str, sh: _Shift, target: str, here: str) -> str:
    """Rewrite references to sheet `target` in `formula` (text without or with a leading '='), written on sheet
    `here`. Refuses what it cannot parse."""
    eq = formula.startswith("=")
    text = formula if eq else "=" + formula
    try:
        items = Tokenizer(text).items
    except (TokenizerError, Exception):  # noqa: BLE001 - any tokenizer failure is a refusal, never a guess
        _refuse("a formula could not be read: " + text[:80])
    if "=" + "".join(t.value for t in items) != text:
        _refuse("a formula could not be rewritten exactly: " + text[:80])
    out = []
    for t in items:
        v = t.value
        if t.type == "OPERAND" and t.subtype == "RANGE" and not v.startswith("["):
            if v.count("!") == 2 and ":" in v:
                left, right = v.split(":", 1)
                left_sheet, left_ref = _split_sheet(left)
                right_sheet, right_ref = _split_sheet(right)
                if left_sheet is not None and right_sheet is not None:
                    if left_sheet.casefold() != right_sheet.casefold():
                        _refuse("3-D references across several sheets are not supported")
                    if left_sheet.casefold() == target.casefold():
                        shifted = _shift_area(left_ref + ":" + right_ref, sh)
                        if shifted is not None:
                            if shifted == "#REF!":
                                v = left[: len(left) - len(left_ref)] + shifted
                            else:
                                a, b = shifted.split(":", 1)
                                v = left[: len(left) - len(left_ref)] + a + ":" + right[: len(right) - len(right_ref)] + b
                    out.append(v)
                    continue
            sheet, ref = _split_sheet(v)
            if (sheet if sheet is not None else here).casefold() == target.casefold() and "[" not in ref:
                new = _shift_area(ref, sh)
                if new is not None:
                    # A deleted target keeps its sheet prefix (Budget!#REF!), as Excel writes it; LibreOffice reads a
                    # bare #REF! inside an expression as an unknown name.
                    v = v[: len(v) - len(ref)] + new
        out.append(v)
    res = "".join(out)
    return ("=" + res) if eq else res


def _shift_sqref(sqref: str, sh: _Shift):
    """Space-separated areas; areas that vanish are dropped. None when nothing is left."""
    kept = []
    for a in sqref.split():
        n = _shift_area(a, sh)
        if n is None:
            _refuse("an unreadable range: " + a[:40])
        if n != "#REF!":
            kept.append(n)
    return " ".join(kept) or None


# ---- the package -----------------------------------------------------------------------------------------------
def _rels(parts: dict, part: str):
    folder, name = posixpath.split(part)
    rp = posixpath.join(folder, "_rels", name + ".rels")
    if rp not in parts:
        return []
    out = []
    for r in _xml(parts[rp]):
        t = r.get("Target", "")
        tp = t.lstrip("/") if t.startswith("/") else posixpath.normpath(posixpath.join(folder, t))
        out.append((r.get("Type", ""), tp))
    return out


def _quoted_names(name: str):
    return {name + "!", "'" + name.replace("'", "''") + "'!"}


def _mentions(root, target: str) -> bool:
    """True when any text or attribute of the parsed part names the sheet (as a reference prefix or a sheet= value);
    case-insensitive, after XML unescaping."""
    names = {n.casefold() for n in _quoted_names(target)}
    for el in root.iter():
        for v in [el.text or ""] + list(el.attrib.values()):
            low = v.casefold()
            if any(n in low for n in names) or low == target.casefold():
                return True
    return False


def _check_supported(parts: dict, by_sheet: dict, target: str, root):
    part = by_sheet[target]
    for typ, _ in _rels(parts, part):
        if any(typ.endswith(d) for d in DRAWING_TYPES):
            _refuse("the sheet has tables, charts, pictures, shapes, comments, pivot tables or slicers")
    if root.find(M + "sheetProtection") is not None:
        _refuse("the sheet is protected")
    if root.find(M + "extLst") is not None:
        _refuse("the sheet uses Excel extensions (for example data bars, sparklines or extended validations)")
    for p, data in parts.items():
        if not p.endswith(".xml"):
            continue
        if p.startswith(("xl/charts/", "xl/pivotCache/", "xl/tables/", "xl/slicerCaches/", "xl/timelineCaches/")):
            if _mentions(_xml(data), target):
                _refuse(f"a chart, pivot table, table or slicer reads from '{target}'")
    for c in root.iter(M + "c"):
        f = c.find(M + "f")
        if f is not None and f.get("t") == "dataTable":
            _refuse("the sheet has a data table (what-if analysis)")


def _unshare(parts: dict, by_sheet: dict, target: str):
    """Write shared formulas whose master refers to the target sheet as ordinary formulas."""
    names = _quoted_names(target)
    for sname, part in by_sheet.items():
        if part not in parts:
            continue
        root = _xml(parts[part])
        masters = {}
        for c in root.iter(M + "c"):
            f = c.find(M + "f")
            if f is not None and f.get("t") == "shared" and f.text:
                masters[f.get("si")] = (c.get("r"), f.text)
        low = {n.casefold() for n in names}
        hit = {si for si, (_, txt) in masters.items()
               if sname.casefold() == target.casefold() or any(n in txt.casefold() for n in low)}
        if not hit:
            continue
        for c in root.iter(M + "c"):
            f = c.find(M + "f")
            if f is None or f.get("t") != "shared" or f.get("si") not in hit:
                continue
            origin, text = masters[f.get("si")]
            if c.get("r") != origin:
                try:
                    f.text = Translator("=" + text, origin=origin).translate_formula(c.get("r"))[1:]
                except Exception:  # noqa: BLE001
                    _refuse("a shared formula could not be written out: " + text[:60])
            for a in ("t", "si", "ref"):
                f.attrib.pop(a, None)
        parts[part] = _ser(root)


def _shift_formulas_everywhere(parts: dict, by_sheet: dict, target: str, sh: _Shift):
    for sname, part in by_sheet.items():
        if part not in parts:
            continue
        root = _xml(parts[part])
        changed = False
        for c in root.iter(M + "c"):
            f = c.find(M + "f")
            if f is None or not f.text:
                continue
            new = shift_formula(f.text, sh, target, sname)
            if new != f.text:
                f.text = new
                changed = True
                v = c.find(M + "v")
                if v is not None:            # cached value of a changed formula is stale; Excel recalculates
                    c.remove(v)
        if changed:
            parts[part] = _ser(root)


def _shift_sheet(root, sh: _Shift, target: str):
    sd = root.find(M + "sheetData")
    if sh.op == "delete_rows":
        for f in sd.iter(M + "f"):
            if f.get("ref"):
                _, r1, _, r2 = refs.parse_range(f.get("ref"))
                if r1 <= sh.last and r2 >= sh.at and not (sh.at <= r1 and r2 <= sh.last):
                    _refuse("a deletion cuts through an array formula")
    for row in list(sd.iterfind(M + "row")):
        n = sh.row(int(row.get("r")))
        if n is None:
            sd.remove(row)
            continue
        row.set("r", str(n))
        for c in row.iterfind(M + "c"):
            col, _ = refs.parse_cell(c.get("r"))
            c.set("r", refs.cell_ref(col, n))
            f = c.find(M + "f")
            if f is not None and f.get("ref"):              # array formulas (shared ones were written out above)
                f.set("ref", _shift_area(f.get("ref"), sh))
    if sh.op == "insert_rows":
        rows = sorted(sd.iterfind(M + "row"), key=lambda r: int(r.get("r")))
        for r in rows:
            sd.remove(r)
            sd.append(r)
    dim = root.find(M + "dimension")
    if dim is not None and ":" in dim.get("ref", ""):
        new = _shift_area(dim.get("ref"), sh)
        if new not in (None, "#REF!"):
            dim.set("ref", new)
    mcs = root.find(M + "mergeCells")
    if mcs is not None:
        for mc in list(mcs):
            c1, r1, c2, r2 = refs.parse_range(mc.get("ref"))
            if sh.op == "delete_rows" and r1 <= sh.last and r2 >= sh.at and not (sh.at <= r1 and r2 <= sh.last):
                _refuse("a deletion cuts through merged cells")
            span = sh.span(r1, r2)
            if span is None or (span[0] == span[1] and c1 == c2):
                mcs.remove(mc)
                continue
            mc.set("ref", f"{refs.cell_ref(c1, span[0])}:{refs.cell_ref(c2, span[1])}")
        if len(mcs) == 0:
            root.remove(mcs)
        else:
            mcs.set("count", str(len(mcs)))
    for cf in list(root.iterfind(M + "conditionalFormatting")):
        new = _shift_sqref(cf.get("sqref", ""), sh)
        if new is None:
            root.remove(cf)
            continue
        cf.set("sqref", new)
        for fe in cf.iter(M + "formula"):
            if fe.text:
                fe.text = shift_formula(fe.text, sh, target, target)
    dvs = root.find(M + "dataValidations")
    if dvs is not None:
        for dv in list(dvs):
            new = _shift_sqref(dv.get("sqref", ""), sh)
            if new is None:
                dvs.remove(dv)
                continue
            dv.set("sqref", new)
            for tag in ("formula1", "formula2"):
                fe = dv.find(M + tag)
                if fe is not None and fe.text:
                    fe.text = shift_formula(fe.text, sh, target, target)
        if len(dvs) == 0:
            root.remove(dvs)
        else:
            dvs.set("count", str(len(dvs)))
    hls = root.find(M + "hyperlinks")
    if hls is not None:
        for h in list(hls):
            new = _shift_area(h.get("ref", ""), sh)
            if new in (None, "#REF!"):
                hls.remove(h)
            else:
                h.set("ref", new)
        if len(hls) == 0:
            root.remove(hls)
    af = root.find(M + "autoFilter")
    if af is not None:
        new = _shift_area(af.get("ref", ""), sh)
        if new in (None, "#REF!"):
            _refuse("the change would remove the filtered range")
        af.set("ref", new)
        ss = af.find(M + "sortState")
        if ss is not None:
            _refuse("the filter has a saved sort")
    rb = root.find(M + "rowBreaks")
    if rb is not None:
        for b in list(rb):
            n = sh.row(int(b.get("id", "0")) + 1)
            if n is None:
                rb.remove(b)
            else:
                b.set("id", str(n - 1))
        rb.set("count", str(len(rb)))
        rb.set("manualBreakCount", str(len(rb)))
    for sv in root.iter(M + "selection"):          # keep the view valid; Excel does the same
        for a in ("activeCell", "sqref"):
            if sv.get(a):
                sv.attrib.pop(a, None)


def _shift_defined_names(parts: dict, target: str, sh: _Shift):
    wb = _xml(parts["xl/workbook.xml"])
    dns = wb.find(M + "definedNames")
    changed = False
    if dns is not None:
        sheet_names = [s.get("name") for s in wb.find(M + "sheets").iterfind(M + "sheet")]
        target_local_id = str(sheet_names.index(target))
        for dn in dns:
            local_on_target = dn.get("localSheetId") == target_local_id
            if dn.text and (local_on_target or any(n.casefold() in dn.text.casefold() for n in _quoted_names(target))):
                new = shift_formula(dn.text, sh, target, target if local_on_target else "\0no-sheet")
                if new != dn.text:
                    dn.text = new
                    changed = True
    calc = wb.find(M + "calcPr")
    if calc is None:
        calc = etree.SubElement(wb, M + "calcPr")
    if calc.get("fullCalcOnLoad") != "1":
        calc.set("fullCalcOnLoad", "1")
        changed = True
    if changed:
        parts["xl/workbook.xml"] = _ser(wb)


def _drop_calc_chain(parts: dict):
    if "xl/calcChain.xml" not in parts:
        return
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


def apply_row_op(parts: dict, op: dict) -> None:
    """Apply one {"op": "insert_rows"|"delete_rows", "sheet", "at", "count"} to the package parts in place.
    Everything is checked before any part is changed; on a refusal `parts` is left exactly as it was."""
    kind, sheet, at, count = op.get("op"), op.get("sheet"), op.get("at"), op.get("count")
    if kind not in ("insert_rows", "delete_rows"):
        raise OfficeError("UNKNOWN_OP", str(kind)[:32])
    if not isinstance(at, int) or isinstance(at, bool) or not 1 <= at <= refs.MAX_ROW:
        raise OfficeError("BAD_ROW", str(at)[:16])
    if not isinstance(count, int) or isinstance(count, bool) or not 1 <= count <= MAX_ROWS_PER_OP:
        raise OfficeError("BAD_COUNT", str(count)[:16])
    by_sheet = sheet_parts(parts)
    if sheet not in by_sheet or by_sheet[sheet] not in parts:
        raise OfficeError("UNKNOWN_SHEET", str(sheet)[:64])
    work = dict(parts)                              # all-or-nothing
    root = _xml(work[by_sheet[sheet]])
    _check_supported(work, by_sheet, sheet, root)
    sh = _Shift(kind, at, count)
    _unshare(work, by_sheet, sheet)
    _shift_formulas_everywhere(work, by_sheet, sheet, sh)
    root = _xml(work[by_sheet[sheet]])
    _shift_sheet(root, sh, sheet)
    work[by_sheet[sheet]] = _ser(root)
    _shift_defined_names(work, sheet, sh)
    _drop_calc_chain(work)
    parts.clear()
    parts.update(work)
