"""A1 references. Columns A..XFD, rows 1..1048576 (Excel limits)."""
import re

from .errors import OfficeError

MAX_COL = 16384
MAX_ROW = 1048576
_CELL = re.compile(r"^([A-Z]{1,3})([1-9][0-9]{0,6})$")


def col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n


def col_letters(n: int) -> str:
    s = ""
    while n:
        n, rem = divmod(n - 1, 26)
        s = chr(65 + rem) + s
    return s


def parse_cell(ref) -> tuple:
    """'B3' -> (col=2, row=3). Refuses anything outside Excel's grid."""
    m = _CELL.match(ref) if isinstance(ref, str) else None
    if not m:
        raise OfficeError("BAD_CELL_REF", str(ref)[:32])
    col, row = col_index(m.group(1)), int(m.group(2))
    if col > MAX_COL or row > MAX_ROW:
        raise OfficeError("BAD_CELL_REF", ref)
    return col, row


def cell_ref(col: int, row: int) -> str:
    return f"{col_letters(col)}{row}"


def parse_range(ref) -> tuple:
    """'A1:C3' or 'B2' -> (c1, r1, c2, r2), normalised so c1<=c2 and r1<=r2."""
    if not isinstance(ref, str):
        raise OfficeError("BAD_RANGE", "")
    a, sep, b = ref.partition(":")
    c1, r1 = parse_cell(a)
    c2, r2 = parse_cell(b) if sep else (c1, r1)
    return min(c1, c2), min(r1, r2), max(c1, c2), max(r1, r2)
