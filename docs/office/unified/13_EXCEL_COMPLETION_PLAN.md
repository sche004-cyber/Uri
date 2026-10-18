# URI Office: Excel completion (OD-R3, OD-R2): what was built and acceptance criteria

Owner decisions (2026-10-16): **OD-R3** genuine Excel row insert/delete and formatting persistence; fix XB-2 (no local
insert-rows) and XF-1 (formatting shown then silently lost); no simulated insertion; explicitly identify what is not
supported; keep the no-op filtering, pending-proposal, exact-equality, overlap and order semantics; regression coverage
for NOOP-1 and the readiness rounds R8-R11. **OD-R2** keep proposals with warnings: show original and proposed, explain
a conflict, ask for approval, clarify when ambiguous, never silently overwrite.

Branch `milestone/office-excel-completion-20261016` from the integration plan commit `d3b51d9e`; commits `bfed2b8e`
(row engine), `fcea4a1c` (service, draft, Brain, page), `e308eb68` (formatting). To be merged onto the integrated
baseline before qualification (OD-A4).

## 1. Row insert and delete (XB-2)

- Engine `uri_office/xlsx_struct.py` (XML level, all or nothing): moves cells, dimension, merges, conditional formats
  (ranges and formulas), validations, hyperlinks, auto-filter, row breaks, selections, every formula in the workbook
  that refers to the sheet (case-insensitive and quoted sheet names), array ranges and defined names. Shared formulas
  that refer to the sheet are unshared first. Deleted targets become `Sheet!#REF!`; ranges that lose rows shrink;
  `calcChain` is dropped so Excel rebuilds it.
- Refused before anything changes, by name: tables, drawings, comments, pivots, slicers on the sheet; charts, pivot
  caches, tables or slicers elsewhere that read the sheet; data tables; `extLst`; sheet protection; 3-D references;
  deletions through merges or arrays; formulas that do not round-trip.
- Draft: a row change is a proposed structural change in plain words ("Insert 1 row above row 4 on 'Budget': Travel 2 |
  25000"); a delete records and shows what the rows hold now (OD-R2). An insert may carry the new rows' values,
  checked like any cell value or formula.
- Save: cell edits as shown, then row changes in order; the saved file is re-read, the layout version moves, and
  proposals on moved rows are dropped (same rule as Google workbooks).
- Brain: the local prompt explains real row operations; a row change together with cell changes on the same sheet in
  one answer is refused (`ROW_AND_CELL_CHANGES`) so totals are never adjusted twice.

## 2. Formatting persistence (XF-1)

- `uri_office/xlsx_styles.py` writes bold, italic, underline, text colour, solid fill, number format, horizontal
  alignment and wrap into `styles.xml`. Only properties that changed are written; new font, fill and xf records are
  copies of the cell's current ones (theme colours, size, family, borders, protection kept); identical records are
  reused; schema order kept.
- The page applies only this saved subset for local workbooks and reports a cell's whole saved-subset style; other
  formatting (borders, merges, resizes, fonts outside the subset) is still removed with a notice. Google and new
  workbooks keep the XF-1 refusal. The save card lists formatting in plain words.

## 3. Acceptance criteria

| ID | Criterion | Evidence |
|---|---|---|
| XC-1 | Insert and delete rows move every dependent structure listed in section 1; LibreOffice recalculates totals over an inserted row and shows `#REF!` where a deleted row was used | `tests/office/test_xlsx_struct.py`, `tests/office_u2/test_xlsx_struct_engine.py` (real engine) |
| XC-2 | Every unsupported structure is refused by name with the file unchanged (all or nothing) | unit + service tests |
| XC-3 | Row changes are proposals with plain words and the rows' current content on deletes; nothing is written before approval; moved-row proposals drop after save | `tests/office/test_local_rows_service.py` |
| XC-4 | A Brain answer mixing row and cell changes on a sheet is refused; values in inserts are validated | service tests |
| XC-5 | Formatting subset saved exactly (delta only, records reused, schema order); round trip in LibreOffice | `tests/office/test_xlsx_styles.py` + engine test |
| XC-6 | Page: saved subset applied, other formatting refused with a notice; Google/new workbooks unchanged | page JS tests (real Univer engine), Flutter office tests |
| XC-7 | No regression of NOOP-1 and R8-R11 semantics (no-op filtering, pending proposals, exact equality, overlap, order) | existing office suites pass unchanged |
| XC-8 | Live: insert and delete rows through URI on a local workbook, format cells and save, reopen in the app and in LibreOffice | Stage 8 live journeys (formatting through the real WebView2 page) |
| XC-9 | Independent review ACCEPT (or AwF) on the exact commit; gates pass | driver receipt |

Not in scope: column insert/delete, sorting, charts, Google Sheets formatting.
