"""OD-R3: a workbook after row insert/delete opens in the real LibreOffice engine and its formulas calculate to the
right totals (not only "the XML looks right"). Skipped when the pinned engine is not installed."""
import csv
import io
import os
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "office"))
from test_xlsx_struct import budget_bytes, parts_of  # noqa: E402

from uri_office import xlsx_struct as S  # noqa: E402

SOFFICE = Path(os.environ.get("URI_ENGINES_ROOT", Path(os.environ.get("LOCALAPPDATA", "")) / "URI" / "engines")) \
    / "libreoffice-26.8.1" / "program" / "soffice.com"
pytestmark = pytest.mark.skipif(not SOFFICE.exists(), reason="pinned LibreOffice engine not installed")


def calc_csv(tmp_path: Path, parts: dict, sheet_index: int = 1) -> list:
    src = tmp_path / "book.xlsx"
    with zipfile.ZipFile(src, "w") as z:
        for n, d in parts.items():
            z.writestr(n, d)
    prof = tmp_path / "lo-profile"
    out = tmp_path / "out"
    r = subprocess.run([str(SOFFICE), f"-env:UserInstallation={prof.as_uri()}", "--headless", "--norestore",
                        "--convert-to", f"csv:Text - txt - csv (StarCalc):44,34,76,1,,0,false,true,false,false,false,"
                                         f"{sheet_index}", "--outdir", str(out), str(src)],
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    files = sorted(out.glob("*.csv"))
    assert files, r.stdout + r.stderr
    return list(csv.reader(io.StringIO(files[0].read_text(encoding="utf-8"))))


def test_inserted_row_is_counted_by_the_total_after_recalculation(tmp_path):
    parts = parts_of(budget_bytes())
    S.apply_row_op(parts, {"op": "insert_rows", "sheet": "Budget", "at": 4, "count": 1})
    # fill the new row the way the service does after the structural change
    from uri_office.xlsx_patch import _get_cell, _set_cell, _ser, _xml, M
    root = _xml(parts["xl/worksheets/sheet1.xml"])
    sd = root.find(M + "sheetData")
    _set_cell(_get_cell(sd, "A4"), {"value": "Travel 2"})
    _set_cell(_get_cell(sd, "B4"), {"value": 25000})
    parts["xl/worksheets/sheet1.xml"] = _ser(root)
    rows = calc_csv(tmp_path, parts)
    total = next(r for r in rows if r and r[0] == "Total")
    assert float(total[1]) == 1250000 + 480000 + 25000 + 35000 + 60000 + 90000


def test_deleted_row_leaves_the_total_and_a_ref_error_where_it_was_used(tmp_path):
    parts = parts_of(budget_bytes())
    S.apply_row_op(parts, {"op": "delete_rows", "sheet": "Budget", "at": 5, "count": 1})
    rows = calc_csv(tmp_path, parts)
    total = next(r for r in rows if r and r[0] == "Total")
    assert float(total[1]) == 1250000 + 480000 + 35000 + 90000
    (tmp_path / "n").mkdir()
    notes = calc_csv(tmp_path / "n", parts, sheet_index=2)
    assert notes[1][0] == "#REF!"
