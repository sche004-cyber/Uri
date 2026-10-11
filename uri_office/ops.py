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
MAX_CELLS_PER_OP = 5000
MAX_TEXT = 32767
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
            "required": ["op", "sheet", "range", "values", "cell", "formula", "at", "count", "name"],
            "properties": {
                "op": {"type": "string", "enum": list(CELL_OPS + STRUCT_OPS)},
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
        return v
    raise OfficeError("BAD_VALUE", type(v).__name__)


def _sheet(op, sheets):
    s = op.get("sheet")
    if s not in sheets:
        raise OfficeError("UNKNOWN_SHEET", str(s)[:64])
    return s


def to_cell_edits(op, *, engine, sheets, locked=None) -> list:
    """Validate one op. Cell ops -> [{"sheet", "cell", "value"|"formula"}]; Google structural ops -> [op] unchanged
    after validation. `locked` maps sheet -> set of refs that must not be edited (local only)."""
    if not isinstance(op, dict) or op.get("op") not in CELL_OPS + STRUCT_OPS:
        raise OfficeError("UNKNOWN_OP", str(op.get("op") if isinstance(op, dict) else op)[:32])
    kind = op["op"]
    if kind in STRUCT_OPS and engine != "google":
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
