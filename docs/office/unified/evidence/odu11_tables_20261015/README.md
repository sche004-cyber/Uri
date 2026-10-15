# OD-U11 investigation: PDF tables to Excel with what is already installed, 2026-10-15

Owner decision OD-U11: keep "PDF tables → Excel" as a deferred capability; install nothing; first investigate whether
existing engines or lightweight deterministic methods extract tables reliably; it must not block O2. Nothing was
installed. All documents are synthetic.

## Method tried

`table_spike.py`: pypdf (BSD, already installed) text positions from `extract_text(visitor_text=...)`, then a
deterministic layout step: runs grouped into rows by baseline (2 pt tolerance), columns found by clustering the left x
of runs across rows (6 pt tolerance), each run placed in the nearest column. Scored against the table the generator
wrote (exact row match).

## Results

| PDF (made by LibreOffice from a synthetic file) | Rows exact | Columns | Time |
|---|---|---|---|
| Office order, 41 rows × 4 columns, short left-aligned cells | **41 / 41** | 4 of 4 | 38 ms |
| Budget sheet, 6 rows × 3 columns, right-aligned numbers of similar width | **6 / 6** (header text not matched exactly) | 3 of 3 | 6 ms |
| Expenditure statement, 15 rows × 3 columns, wrapped multi-line descriptions, right-aligned amounts of 3 to 7 digits, paragraphs above and below | **0 / 15** | 7 found, 3 expected | 26 ms |

Why the third case fails: right-aligned numbers of different widths start at different x positions, so they form
separate "columns"; a wrapped cell's second line becomes its own row; paragraphs outside the table join the grid.

## Assessment against the owner's criteria

| Criterion | pypdf positions + clustering (no install) |
|---|---|
| Accuracy | Good for simple, single-line, left-aligned tables. Unreliable for ordinary administrative tables (wrapped text, right-aligned amounts, text around the table). Not fit for release as is. |
| Layout preservation | Cell text only; no merged cells, no number formats. |
| Licensing | BSD (pypdf), no new dependency. |
| Performance | Tens of milliseconds per page. |
| Complexity | Small for the naive method; a reliable version needs cell boundaries. |

## Options for a reliable version (owner decision later; none taken)

1. **No install:** read the table's ruling lines from the PDF drawing operators (pypdf content stream: `re`, `m`/`l`
   paths) to get cell boxes, then place text runs by box, using right edges for right-aligned text. LibreOffice and
   Word draw grid lines for bordered tables, so this covers the common case; borderless tables would still fail.
   Moderate custom work; needs its own test corpus.
2. **Install pdfplumber (MIT)**, which does lines, words and table detection; needs an owner install decision.
3. **Scanned tables** need OCR first (Tesseract) and are harder in every option.

Recommendation: keep the capability deferred; if the owner wants it, try option 1 first with a corpus of real-shaped
synthetic tables (bordered and borderless) and an accuracy bar set before the run. This does not block O2.
