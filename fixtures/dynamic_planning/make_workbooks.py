"""Write the dynamic planning slice-1 fixture workbooks deterministically.

Minimal .xlsx files built with `zipfile` and a fixed entry time, so the bytes
(and the SHA-256 pinned in qualification_cases.json) never change between
runs or machines. Cells are inline strings or numbers; there is no shared
string table. Usage: python fixtures/dynamic_planning/make_workbooks.py [OUT_DIR]
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import sys
import zipfile

FIXED_TIME = (2020, 1, 1, 0, 0, 0)
HERE = Path(__file__).resolve().parent
OUT = HERE / "workbooks"

WORKBOOKS = {
    "wb_a.xlsx": {"Orders": [["Id", "Date", "Amount"], [1, "2024-01-01", 10], [2, "2024-01-02", 20]],
                  "Vendors": [["VendorId", "Name"], [7, "Acme"]]},
    "wb_b.xlsx": {"Orders": [["Id", "Date", "Amount", "Region"], [1, "2024-02-01", 5, "North"]],
                  "Returns": [["Id", "Reason"], [1, "Damaged"]]},
    "wb_same_as_a.xlsx": None,  # content-identical to wb_a.xlsx, different name
    "wb_formula_err.xlsx": {"Orders": [["Id", "Date", "Amount"], [1, "2024-03-01", "#REF!"]]},
    "wb_big_header.xlsx": {"Wide": [["H%d" % i for i in range(1, 521)], [1]]},
}
ERROR_CELLS = {("wb_formula_err.xlsx", "Orders", 2, 3)}


def _col(n: int) -> str:
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def _esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _sheet_xml(name, rows, wb_name) -> bytes:
    out = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
           '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>']
    for r, row in enumerate(rows, start=1):
        cells = []
        for c, value in enumerate(row, start=1):
            ref = f"{_col(c)}{r}"
            if (wb_name, name, r, c) in ERROR_CELLS:
                cells.append(f'<c r="{ref}" t="e"><v>{_esc(value)}</v></c>')
            elif isinstance(value, (int, float)):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{ref}" t="inlineStr"><is><t>{_esc(value)}</t></is></c>')
        out.append(f'<row r="{r}">' + "".join(cells) + "</row>")
    out.append("</sheetData></worksheet>")
    return "".join(out).encode("utf-8")


def _entry(zf, name, data):
    info = zipfile.ZipInfo(name, date_time=FIXED_TIME)
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o644 << 16
    zf.writestr(info, data)


def write_workbook(path: Path, sheets: dict, wb_name: str) -> None:
    names = list(sheets)
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
          + "".join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                    for i in range(1, len(names) + 1)) + "</Types>")
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>")
    workbook = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
                'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
                + "".join(f'<sheet name="{_esc(n)}" sheetId="{i}" r:id="rId{i}"/>' for i, n in enumerate(names, start=1))
                + "</sheets></workbook>")
    wb_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
               '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
               + "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
                         for i in range(1, len(names) + 1)) + "</Relationships>")
    with zipfile.ZipFile(path, "w") as zf:
        _entry(zf, "[Content_Types].xml", ct.encode("utf-8"))
        _entry(zf, "_rels/.rels", rels.encode("utf-8"))
        _entry(zf, "xl/workbook.xml", workbook.encode("utf-8"))
        _entry(zf, "xl/_rels/workbook.xml.rels", wb_rels.encode("utf-8"))
        for i, n in enumerate(names, start=1):
            _entry(zf, f"xl/worksheets/sheet{i}.xml", _sheet_xml(n, sheets[n], wb_name))


def build(out: Path = OUT) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    for name, sheets in WORKBOOKS.items():
        write_workbook(out / name, sheets or WORKBOOKS["wb_a.xlsx"], name if sheets else "wb_a.xlsx")
    (out / "wb_malformed.xlsx").write_bytes(b"this is not a zip container\n")
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob("*.xlsx"))}


if __name__ == "__main__":
    for name, sha in build(Path(sys.argv[1]) if len(sys.argv) > 1 else OUT).items():
        print(sha, name)
