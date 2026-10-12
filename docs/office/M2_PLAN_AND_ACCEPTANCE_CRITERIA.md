# URI Office M2: build a new workbook from one or more Excel files

Branch `phase/uri-office-m2`, from `phase/uri-office` at `6348b1b1` (M1 with the M1-c2 repairs). M1 stays a separate milestone and is reviewed on its own. M2 is not merged, deployed or cut over without the owner's authorisation.

## 1. Owner request (2026-10-12)

> "Also ensure user can add one or more excel files and uri can extract information to work on a fresh file and generate a new file"

The owner placed this in a new milestone M2 ("New milestone M2 (Recommended)").

## 2. What M2 adds

1. **New from files.** The owner picks one or more `.xlsx` files (the system file picker, multi-select). They become read-only *sources*. URI Office opens a fresh, empty workbook next to them.
2. **More sources later.** The owner can add more files to the same new workbook while working.
3. **URI works from the sources.** The owner asks in the companion pane (typed or push-to-talk, as in M1). URI reads the sources (bounded excerpts, as untrusted data) and proposes changes to the new workbook: values, formulas, new sheets, and copying ranges from a source.
4. **Review as in M1.** Every URI change is proposed and marked; the owner accepts or rejects it. Because one request can copy thousands of cells, the pane also offers *Accept all* / *Reject all* for the changes it shows, bound to a hash of exactly that set.
5. **Generate the new file.** "Save as new file..." asks for a destination, then shows the hash-bound approval card. Only after "Create file" is the new `.xlsx` written. An existing file is never overwritten. After it is created, the session continues as an ordinary M1 local workbook on the new file.

The sources are never written. Nothing leaves the PC.

## 3. Decisions

| Id | Decision | Why |
|---|---|---|
| M2-D1 (**owner may overrule**) | The approval card for *creating a new file* shows a summary (destination; each sheet with its cell and formula counts; the sources used), not every cell. The hash still binds the full content, and a different draft version is refused as before. M1's rule that a card lists every change stays for saving *into an existing file* and for Google. | A new file from sources can hold tens of thousands of cells, which no card can show; M1 would refuse it. Creating a new file changes no existing data; the owner reviewed the content in the grid and accepted it change by change or with *Accept all*. |
| M2-D2 | *Accept all* / *Reject all* decide every change that was **proposed** when the pane last showed the draft. The request carries the draft version and the SHA-256 over the sorted `(change id, change hash)` pairs; the service recomputes both and refuses with `STALE_CHANGE` if anything differs. All or nothing. | Per-change decisions stay hash-bound; the batch is bound the same way without a 2 MB request. |
| M2-D3 | `copy_range` copies **values** (the cached results for formula cells), never formulas, from a source into the new workbook. A source formula cell without a cached result (a file Excel never calculated) is copied as empty and reported. | Formulas from a source would point at sheets that are not in the new workbook. External references stay refused (M1 rule). |
| M2-D4 | In a new workbook, `add_sheet` and `rename_sheet` take effect in the draft at once (there is no file yet); they are listed in the conversation. A sheet left with no cells is not written. Saving with no cells at all is refused (`NOTHING_TO_SAVE`). | Structure is free until the file exists; it keeps the draft model unchanged. |
| M2-D5 | New files are written with `openpyxl` (already in `requirements.txt`): values and formulas only, no styles; `calcPr fullCalcOnLoad` so Excel calculates on open. | Plain, reproducible output; styling is out of scope for M2. |
| M2-D6 | The correction history stays per workbook and off by default; a new workbook has no history until it is saved and reopened as a local file. | M1 OFF-O3 ruling. |

## 4. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| M2-AC1 | `POST /open/new {"paths": [...]}` opens a new workbook (engine `new`, one empty sheet `Sheet1`) with 1-10 sources. Every path goes through the M1 path rule (`grants.grant_open`: owner-picked, allowed roots, regular file, 50 MB cap) and is copied in; a source whose file changes during copy-in is refused. Duplicate names get distinct labels. More than 10 sources, or a non-xlsx, is refused with nothing opened. | pytest |
| M2-AC2 | `POST /workbook/<id>/sources {"paths": [...]}` adds sources to an open new workbook under the same rules (total stays at most 10). Only engine `new` accepts sources. | pytest |
| M2-AC3 | The view lists sources (id `S1..`, label, sheet names and sizes) and never a source path. | pytest, widget test |
| M2-AC4 | The Brain request for a new workbook contains the owner's instruction as the only instruction; each source's bounded excerpt (sheet sizes, the first rows of each sheet, a total cell cap) and the new workbook's excerpt are inside untrusted-data blocks. A source cell saying "ignore previous instructions" does not change the ops returned by the fake Brain. | pytest |
| M2-AC5 | New-workbook ops: `set_values`, `set_formula`, `add_sheet`, `rename_sheet`, `copy_range{source, from_sheet, from_range, sheet, cell}`. Each is validated; an invalid op is reported, never guessed. `copy_range` is capped at 5,000 cells per op, copies values only (D3), and refuses an unknown source, sheet or range. Network and external-reference formulas stay refused. Row ops stay Google-only. | pytest |
| M2-AC6 | `add_sheet`/`rename_sheet` in a new workbook change its sheets at once (D4); the panel reloads the grid from the returned workbook. | pytest, widget test |
| M2-AC7 | `POST /workbook/<id>/decide_all {"decision", "draft_version", "set_sha256"}` decides every proposed change atomically when version and set hash match, else refuses with `STALE_CHANGE` and changes nothing. Works for every engine. | pytest, widget test |
| M2-AC8 | The pane shows sources, *Add file*, *Accept all N* / *Reject all N* when more than one change is proposed, at most 50 change cards plus "and N more, marked in the sheet", and "Save as new file..." (no "Save to file") for a new workbook. | widget tests |
| M2-AC9 | `propose_save` for a new workbook requires `save_as_path`; the destination must not exist (checked at propose and again at create); the card follows D1; the create action writes the file through a temporary file in the destination folder and a no-overwrite link, so a file that appeared meanwhile is never replaced. | pytest |
| M2-AC10 | The created file opens with openpyxl and holds exactly the draft's cells (values and formulas) on non-empty sheets in order; no source file changed (hash before and after). After creating, the session is a local M1 session on the new file (copy-in), so later saves use the M1 cell patch. | pytest |
| M2-AC11 | M1 behaviour and gates are unchanged: `tests/office`, `tests/a2ui`, `flutter test`, `flutter analyze`, `ws_frozen_check`. The guarded worker never imports `uri_office`. | gates |
| M2-AC12 | PC scripted live check (owner choice 2b pattern, NOT the owner's own check): two source files -> URI builds a summary sheet -> accept all -> create file -> the new file holds the expected cells; sources unchanged. Needs the Brain (GPU lease; an override needs the owner's permission each time). | evidence |

## 5. Limits (M2)

- At most 10 sources per new workbook; each at most 50 MB; each sheet read up to 50,000 cells (M1 reader cap, reported as truncated).
- The Brain sees bounded excerpts only (up to 600 cells in total across the new workbook and sources). `copy_range` lets URI move data it has not seen cell by cell, within 5,000 cells per op and the draft's 20,000-change cap.
- No styles, charts or pivot tables in new files; no Google targets for new files (use "Share via Google" after creating it).

## 6. Out of scope

Docs; editing sources; merging into existing files from sources (open the existing file in M1 instead); formulas that reference sources; scheduled or automatic regeneration.

## 7. Process

Owner-gated steps stay NOT VERIFIED until the owner does them. Independent review by the uri-development-lifecycle skill in a Linux cloud session with a fresh `claude_cli` reviewer; PC results are gate evidence, not the review. GPU lease: `advise --window` before opening windows; never override without the owner's permission.

## 8. Status ledger

### 2026-10-12, first build (PC, Windows)

| Check | Result |
|---|---|
| `tests/office tests/a2ui tests/ws tests/oi` | 865 passed, 27 skipped (incl. 23 new M2 tests in `tests/office/test_m2_new_workbook.py`) |
| `flutter test` | 540 passed, 5 skipped (incl. 4 new in `uri_ui/test/office/office_m2_test.dart`) |
| `flutter analyze` | 2 pre-existing infos |
| `ws_frozen_check` | ok |
| Dart and Python set hash | equal on a reference value (`office_m2_test.dart`) |

The page bundle is unchanged from M1 (`b379fff2…`): new sheets reach the grid through the existing `load` message.

Not verified yet: M2-AC12 (PC scripted live check with the real Brain and WebView2; needs a GPU override from the owner), the independent review, the owner's own check.
