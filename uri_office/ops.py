"""The closed op schema (AC13). The Brain and the panel may only propose these; anything else is refused, never guessed.

  set_values   {"op", "sheet", "range": "A1:C3", "values": [[...], ...]}   local + Google
  set_formula  {"op", "sheet", "cell": "D4", "formula": "=SUM(A1:A3)"}      local + Google
  insert_rows  {"op", "sheet", "at": 5, "count": 2}                          Google only
  delete_rows  {"op", "sheet", "at": 5, "count": 2}                          Google only
  add_sheet    {"op", "name": "Summary"}                                     Google only
  rename_sheet {"op", "sheet": "Old", "name": "New"}                         Google only

Formulas that reach the network or other programs (IMPORTXML, WEBSERVICE, HYPERLINK, IMAGE, STOCKHISTORY, CUBE*, ...,
even when only named; DDE `|`; external workbook links `[..]`) are refused: a sheet must never become a way to send its
contents somewhere.
"""
from __future__ import annotations

import re

from . import refs
from .errors import OfficeError

CELL_OPS = ("set_values", "set_formula")
STRUCT_OPS = ("insert_rows", "delete_rows", "add_sheet", "rename_sheet")
SHEET_OPS = ("add_sheet", "rename_sheet")
SOURCE_OPS = ("copy_range",)          # M2: a new workbook built from source files
MAX_CELLS_PER_OP = 5000
MAX_TEXT = 32767
# Characters XML 1.0 cannot carry (C0 controls other than tab/LF/CR, U+FFFE/U+FFFF, lone surrogates). A cell holding one
# cannot be written to an .xlsx, so it is refused when proposed rather than failing the approved save later.
_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]")
# Functions that reach the network, other programs, external data or cloud services. They are refused as bare tokens,
# not only when followed by "(": a function can be passed by name (=MAP(A1,WEBSERVICE), =LET(f,IMAGE,f(x))).
# Only formula code is scanned: _code() drops double-quoted string literals (text cannot be called as a function in
# Excel or Google Sheets) and single-quoted sheet names, tokenising left to right so a quote of one kind inside the
# other (='q"'!A1) cannot hide a call.
_NETWORK_FN = re.compile(
    r"(?<![A-Za-z0-9_])(IMPORT[A-Z]*|WEBSERVICE|FILTERXML|ENCODEURL|HYPERLINK|IMAGE|RTD|CALL|REGISTER(?:\.ID)?|EXEC|"
    r"STOCKHISTORY|STOCKSERIES|TRANSLATE|DETECTLANGUAGE|COPILOT|CUBE[A-Z]*|SQL\.REQUEST|GOOGLEFINANCE|"
    r"GOOGLETRANSLATE)(?![A-Za-z0-9_])", re.IGNORECASE)
# Short names that are also column letters (AI, PY) are refused only as calls, so =SUM(AI:AI) stays valid.
_NETWORK_CALL = re.compile(r"(?<![A-Za-z0-9_])(AI|PY)\s*\(", re.IGNORECASE)
_SHEET_NAME = re.compile(r"^[^\[\]:*?/\\]{1,31}$")

# Strict JSON schema for one Brain answer (every property required; unused ones are null).
_SCALAR = {"type": ["string", "number", "boolean", "null"]}
BRAIN_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["message", "ops"],
    "properties": {
        "message": {"type": "string"},
        "ops": {"type": "array", "maxItems": 20, "items": {
            "type": "object", "additionalProperties": False,
            "required": ["op", "sheet", "range", "values", "cell", "formula", "at", "count", "name", "source",
                         "from_sheet", "from_range"],
            "properties": {
                "op": {"type": "string", "enum": list(CELL_OPS + STRUCT_OPS + SOURCE_OPS)},
                "source": {"type": ["string", "null"]}, "from_sheet": {"type": ["string", "null"]},
                "from_range": {"type": ["string", "null"]},
                "sheet": {"type": ["string", "null"]}, "range": {"type": ["string", "null"]},
                "values": {"type": ["array", "null"], "items": {"type": "array", "items": _SCALAR}},
                "cell": {"type": ["string", "null"]}, "formula": {"type": ["string", "null"]},
                "at": {"type": ["integer", "null"]}, "count": {"type": ["integer", "null"]},
                "name": {"type": ["string", "null"]}}}}}}


def _code(f: str) -> str:
    """The formula with every "string" and 'sheet name' replaced by an empty pair of its quotes. Inside either, a
    doubled quote of the same kind is an escape. An unterminated quote is refused."""
    out, i, n = [], 0, len(f)
    while i < n:
        q = f[i]
        if q not in "\"'":
            out.append(q)
            i += 1
            continue
        i += 1
        while True:
            if i >= n:
                raise OfficeError("BAD_FORMULA", "unterminated quote")
            if f[i] == q:
                if i + 1 < n and f[i + 1] == q:
                    i += 2
                    continue
                i += 1
                break
            i += 1
        out.append(q + q)
    return "".join(out)


def check_formula(f) -> str:
    if not isinstance(f, str) or not f.startswith("=") or len(f) < 2 or len(f) > 8192:
        raise OfficeError("BAD_FORMULA", "a formula must start with '='")
    if _XML_INVALID.search(f):
        raise OfficeError("BAD_FORMULA", "the formula contains a control character a workbook cannot store")
    code = _code(f)
    if _NETWORK_FN.search(code) or _NETWORK_CALL.search(code) or "|" in f or "[" in f:
        raise OfficeError("FORMULA_REFUSED", "formulas that reach the network, other programs or other files are not allowed")
    return f


def check_value(v):
    if v is None or isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        if v != v or v in (float("inf"), float("-inf")):
            raise OfficeError("BAD_VALUE", "not a finite number")
        return v
    if isinstance(v, str):
        if len(v) > MAX_TEXT:
            raise OfficeError("BAD_VALUE", "text longer than a cell can hold")
        if v.startswith("="):
            raise OfficeError("BAD_VALUE", "use set_formula for formulas")
        if _XML_INVALID.search(v):
            raise OfficeError("BAD_VALUE", "the text contains a control character a workbook cannot store")
        return v
    raise OfficeError("BAD_VALUE", type(v).__name__)


def _sheet(op, sheets):
    s = op.get("sheet")
    if s not in sheets:
        raise OfficeError("UNKNOWN_SHEET", str(s)[:64])
    return s


def to_cell_edits(op, *, engine, sheets, locked=None) -> list:
    """Validate one op. Cell ops -> [{"sheet", "cell", "value"|"formula"}]; Google structural ops -> [op] unchanged
    after validation. `locked` maps sheet -> set of refs that must not be edited (local only). A new workbook (engine
    "new", M2) also takes add_sheet and rename_sheet; copy_range is expanded by `copy_edits`, not here."""
    if not isinstance(op, dict) or op.get("op") not in CELL_OPS + STRUCT_OPS:
        raise OfficeError("UNKNOWN_OP", str(op.get("op") if isinstance(op, dict) else op)[:32])
    kind = op["op"]
    if kind in STRUCT_OPS and engine != "google" and not (engine == "new" and kind in SHEET_OPS):
        raise OfficeError("OP_NOT_SUPPORTED_LOCALLY", f"{kind} is available for Google Sheets only in this version")
    locked = locked or {}
    out = []
    if kind == "set_values":
        sheet = _sheet(op, sheets)
        c1, r1, c2, r2 = refs.parse_range(op.get("range"))
        vals = op.get("values")
        if not isinstance(vals, list) or len(vals) != r2 - r1 + 1 or \
                any(not isinstance(r, list) or len(r) != c2 - c1 + 1 for r in vals):
            raise OfficeError("VALUES_SHAPE", "values do not match the range")
        if (r2 - r1 + 1) * (c2 - c1 + 1) > MAX_CELLS_PER_OP:
            raise OfficeError("OP_TOO_LARGE", f"more than {MAX_CELLS_PER_OP} cells")
        for dr, row in enumerate(vals):
            for dc, v in enumerate(row):
                out.append({"sheet": sheet, "cell": refs.cell_ref(c1 + dc, r1 + dr), "value": check_value(v)})
    elif kind == "set_formula":
        sheet = _sheet(op, sheets)
        out.append({"sheet": sheet, "cell": refs.canonical_cell(op.get("cell")),
                    "formula": check_formula(op.get("formula"))})
    elif kind in ("insert_rows", "delete_rows"):
        _sheet(op, sheets)
        at, count = op.get("at"), op.get("count")
        if not (isinstance(at, int) and isinstance(count, int) and 1 <= at <= refs.MAX_ROW and 1 <= count <= 1000):
            raise OfficeError("BAD_ROWS", "row position or count out of range")
        out.append({k: op[k] for k in ("op", "sheet", "at", "count")})
    elif kind == "add_sheet":
        name = op.get("name")
        if not isinstance(name, str) or not _SHEET_NAME.match(name) or name in sheets:
            raise OfficeError("BAD_SHEET_NAME", str(name)[:40])
        out.append({"op": kind, "name": name})
    elif kind == "rename_sheet":
        _sheet(op, sheets)
        name = op.get("name")
        if not isinstance(name, str) or not _SHEET_NAME.match(name) or name in sheets:
            raise OfficeError("BAD_SHEET_NAME", str(name)[:40])
        out.append({"op": kind, "sheet": op["sheet"], "name": name})
    for e in out:
        if "cell" in e and e["cell"] in set(locked.get(e["sheet"], ())):
            raise OfficeError("CELL_NOT_EDITABLE", f"{e['sheet']}!{e['cell']} is part of a shared formula or merged range")
    return out


_OPEN_RANGE = re.compile(r"^([A-Z]{1,3})([1-9][0-9]{0,6})?:([A-Z]{1,3})$")


def _source_range(ref, sheet: dict) -> tuple:
    """A source range: 'A1:C3' as usual, or open-ended to the sheet's last used row: 'A2:C' (from row 2) and 'A:C'
    (from row 1). Open ranges let URI copy a whole table without counting its rows."""
    m = _OPEN_RANGE.match(ref) if isinstance(ref, str) else None
    if m is None:
        return refs.parse_range(ref)
    last = max(1, int(sheet.get("max_row") or 1))
    first = int(m.group(2) or 1)
    if first > last:
        raise OfficeError("BAD_RANGE", "the range starts below the sheet's last used row")
    return refs.parse_range(f"{m.group(1)}{first}:{m.group(3)}{last}")


def copy_edits(op, *, sources: dict, sheets, next_free_row=None, locked=None) -> tuple:
    """M2 `copy_range`: copy a range's **values** from a source workbook into the new workbook (M2-D3). `sources`
    maps source id -> workbook model (`xlsx_model.read`). `cell` may be a bare column ("A"): the copy then starts at
    `next_free_row(sheet, first_col, last_col)`. Formula cells copy their cached result; one without a cached
    result is copied as empty and counted, and so is a value a workbook cannot store as a value. Returns
    (edits, uncalculated_count, skipped_count)."""
    src = sources.get(op.get("source")) if isinstance(op.get("source"), str) else None
    if src is None:
        raise OfficeError("UNKNOWN_SOURCE", str(op.get("source"))[:16])
    sheet = next((sh for sh in src["sheets"] if sh["name"] == op.get("from_sheet")), None)
    if sheet is None:
        raise OfficeError("UNKNOWN_SOURCE_SHEET", str(op.get("from_sheet"))[:64])
    if sheet.get("truncated"):
        # The reader stopped at its cell cap: cells it did not read would be copied as empty (Codex R2-01).
        raise OfficeError("SOURCE_SHEET_TOO_LARGE", f"{sheet['name']} has more cells than URI Office reads "
                                                    "(50,000 per sheet); split the file or copy from a smaller sheet")
    c1, r1, c2, r2 = _source_range(op.get("from_range"), sheet)
    if (r2 - r1 + 1) * (c2 - c1 + 1) > MAX_CELLS_PER_OP:
        raise OfficeError("OP_TOO_LARGE", f"more than {MAX_CELLS_PER_OP} cells")
    to = _sheet(op, sheets)
    target = op.get("cell")
    if isinstance(target, str) and re.fullmatch(r"[A-Z]{1,3}", target) and next_free_row is not None:
        # A bare column: append below what the target columns already hold (accepted cells and earlier ops of the
        # same answer), so tables can be stacked without counting rows.
        tc = refs.col_index(target)
        tr = next_free_row(to, tc, tc + (c2 - c1))
    else:
        tc, tr = refs.parse_cell(refs.canonical_cell(target))
    if tc + (c2 - c1) > refs.MAX_COL or tr + (r2 - r1) > refs.MAX_ROW:
        raise OfficeError("BAD_RANGE", "the copy does not fit in the sheet")
    out, uncalculated, skipped = [], 0, 0
    for dr in range(r2 - r1 + 1):
        for dc in range(c2 - c1 + 1):
            cell = sheet["cells"].get(refs.cell_ref(c1 + dc, r1 + dr), {})
            v = cell.get("v")
            if v is None and cell.get("f"):
                uncalculated += 1
            try:
                v = check_value(v)
            except OfficeError:
                v = None                          # e.g. text starting with "=": copied as empty, never as a formula
                skipped += 1
            out.append({"sheet": to, "cell": refs.cell_ref(tc + dc, tr + dr), "value": v})
    lk = (locked or {}).get(to, ())
    hit = next((e for e in out if e["cell"] in lk), None)
    if hit is not None:
        raise OfficeError("CELL_NOT_EDITABLE", f"{to}!{hit['cell']} is part of a shared formula or merged range")
    return out, uncalculated, skipped
