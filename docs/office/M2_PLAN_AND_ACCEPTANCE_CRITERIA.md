# URI Office M2: build a new workbook from one or more Excel files

Branch `phase/uri-office-m2`, from `phase/uri-office` at `6348b1b1` (M1 with the M1-c2 repairs). M1 stays a separate milestone and is reviewed on its own. M2 is not merged, deployed or cut over without the owner's authorisation.

## 1. Owner request (2026-10-12)

> "Also ensure user can add one or more excel files and uri can extract information to work on a fresh file and generate a new file"

The owner placed this in a new milestone M2 ("New milestone M2 (Recommended)").

Later the same day the owner added: "The one this is to be made clear from the user, the intent of adding the sheet, eg. is it for reference or user wants something checked or edited", and "So somthing like active working sheet or reference sheet may be arranged". Owner answers: a checked file gets "Findings + suggested fixes"; files are edited "One at a time".

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
| M2-D1 (**owner approved 2026-10-12**: "Ok reccommendation") | The approval card for *creating a new file* shows a summary (destination; each sheet with its cell and formula counts; the sources used), not every cell. The hash still binds the full content, and a different draft version is refused as before. M1's rule that a card lists every change stays for saving *into an existing file* and for Google. | A new file from sources can hold tens of thousands of cells, which no card can show; M1 would refuse it. Creating a new file changes no existing data; the owner reviewed the content in the grid and accepted it change by change or with *Accept all*. |
| M2-D2 | *Accept all* / *Reject all* decide every change that was **proposed** when the pane last showed the draft. The request carries the draft version and the SHA-256 over the sorted `(change id, change hash)` pairs; the service recomputes both and refuses with `STALE_CHANGE` if anything differs. All or nothing. | Per-change decisions stay hash-bound; the batch is bound the same way without a 2 MB request. |
| M2-D3 | `copy_range` copies **values** (the cached results for formula cells), never formulas, from a source into the new workbook. A source formula cell without a cached result (a file Excel never calculated) is copied as empty and reported. | Formulas from a source would point at sheets that are not in the new workbook. External references stay refused (M1 rule). |
| M2-D4 | In a new workbook, `add_sheet` and `rename_sheet` take effect in the draft at once (there is no file yet); they are listed in the conversation. A sheet left with no cells is not written. Saving with no cells at all is refused (`NOTHING_TO_SAVE`). | Structure is free until the file exists; it keeps the draft model unchanged. |
| M2-D5 | New files are written with `openpyxl` (already in `requirements.txt`): values and formulas only, no styles; `calcPr fullCalcOnLoad` so Excel calculates on open. | Plain, reproducible output; styling is out of scope for M2. |
| M2-D7 (from the PC live check) | `copy_range` source ranges may be open-ended (`A2:B` = to the last used row, `A:B` = whole columns) and the target `cell` may be a bare column (`A` = first empty row below what those columns hold, including earlier ops of the same answer). | The local Brain miscounted table rows on the PC (dropped rows, stacked a total onto data); these forms move whole tables without counting. |
| M2-D8 (from the PC live check) | Within one Brain answer, an op that would overwrite a non-empty cell an earlier op of the same answer wrote is refused as `OVERLAPS_EARLIER_OP` (reported, never merged or moved). An empty placeholder may be filled. | A slip such as a total written over a copied row must not silently destroy copied data. |
| M2-D9 (from the PC live check) | For a new workbook the strict output schema limits `source` and `from_sheet` to the ids and sheet names that exist, and the Brain sees every sheet of the new workbook (within the cell cap), not only the first. | On the PC the Brain put the source id into `from_sheet` (2 of 3 answers), and on a second request it saw only the empty first sheet. |
| M2-D10 (owner, 2026-10-12) | Every added file needs a role the owner chooses: **Reference** (URI only reads it), **Check** or **Edit**. URI does not work with the files until each has a role: a request is refused (`ROLES_NEEDED`, and the pane does not send it) and the pane asks "What is each file for?". The role is never inferred. | The owner's intent must be explicit (consequence-aware binding: editing a file is consequential). |
| M2-D11 (owner, 2026-10-12) | At most one file is the **working file** (Check or Edit), shown in the sheet view and saved in place through the M1 path (copy-in, conflict check, backup, hash-bound card). Choosing another working file makes the previous one a reference; it is refused while the current one has unsaved accepted or typed changes (`SAVE_OR_DISCARD_FIRST`) and when the file changed on disk since it was added (`TARGET_CHANGED`). With no working file URI builds a new workbook. **Check** means: URI compares the working file with the references, lists findings (sheet, cell, issue) in the pane, and offers clear fixes as ordinary change cards; nothing is applied without the owner. | Owner answers "Findings + suggested fixes" and "One at a time". |
| M2-D6 | The correction history stays per workbook and off by default; a new workbook has no history until it is saved and reopened as a local file. | M1 OFF-O3 ruling. |

## 4. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| M2-AC1 | `POST /open/new {"paths": [...]}` opens a new workbook (engine `new`, one empty sheet `Sheet1`) with 1-10 sources. Every path goes through the M1 path rule (`grants.grant_open`: owner-picked, allowed roots, regular file, 50 MB cap) and is copied in; a source whose file changes during copy-in is refused. Duplicate names get distinct labels. More than 10 sources, or a non-xlsx, is refused with nothing opened. | pytest |
| M2-AC2 | `POST /workbook/<id>/sources {"paths": [...]}` adds files to a workbook opened with "New from files" under the same rules (total stays at most 10), also while one of its files is the working file (a later file is often another reference). A file added later has no role until the owner gives it one, so requests wait again (M2-D10). A workbook opened with "Open file" or a Google link takes no added files. (Corrected 2026-10-12 after Codex C-04: the first text said "only engine `new`", which contradicted M2-D11.) | pytest |
| M2-AC3 | The view lists sources (id `S1..`, label, sheet names and sizes) and never a source path. | pytest, widget test |
| M2-AC4 | The Brain request for a new workbook contains the owner's instruction as the only instruction; each source's bounded excerpt (sheet sizes, the first rows of each sheet, a total cell cap) and the new workbook's excerpt are inside untrusted-data blocks. A source cell saying "ignore previous instructions" does not change the ops returned by the fake Brain. | pytest |
| M2-AC5 | New-workbook ops: `set_values`, `set_formula`, `add_sheet`, `rename_sheet`, `copy_range{source, from_sheet, from_range, sheet, cell}`. Each is validated; an invalid op is reported, never guessed. `copy_range` is capped at 5,000 cells per op, copies values only (D3), and refuses an unknown source, sheet or range. Network and external-reference formulas stay refused. Row ops stay Google-only. | pytest |
| M2-AC6 | `add_sheet`/`rename_sheet` in a new workbook change its sheets at once (D4); the panel reloads the grid from the returned workbook. | pytest, widget test |
| M2-AC7 | `POST /workbook/<id>/decide_all {"decision", "draft_version", "set_sha256"}` decides every proposed change atomically when version and set hash match, else refuses with `STALE_CHANGE` and changes nothing. Works for every engine. | pytest, widget test |
| M2-AC8 | The pane shows sources, *Add file*, *Accept all N* / *Reject all N* when more than one change is proposed, at most 50 change cards plus "and N more, marked in the sheet", and "Save as new file..." (no "Save to file") for a new workbook. | widget tests |
| M2-AC9 | `propose_save` for a new workbook requires `save_as_path`; the destination must not exist (checked at propose and again at create); the card follows D1; the create action writes the file through a temporary file in the destination folder and a no-overwrite link, so a file that appeared meanwhile is never replaced. | pytest |
| M2-AC10 | The created file opens with openpyxl and holds exactly the draft's cells (values and formulas) on non-empty sheets in order; no source file changed (hash before and after). After creating, the session is a local M1 session on the new file (copy-in), so later saves use the M1 cell patch. | pytest |
| M2-AC11 | M1 behaviour and gates are unchanged: `tests/office`, `tests/a2ui`, `flutter test`, `flutter analyze`, `ws_frozen_check`. The guarded worker never imports `uri_office`. | gates |
| M2-AC13 | Roles (D10/D11): `POST /workbook/<id>/roles` validates roles and the one-working-file rule; requests wait for every role; the Edit file becomes the working file and saves in place with a backup while references stay unchanged; switching with unsaved changes or after an outside change is refused; Check returns validated findings and fixes as proposed changes; copies into the working file respect its locked cells. The pane shows each file with Reference / Check / Edit, marks the working file, and does not send requests until every file has a role. | pytest, widget tests |
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

### 2026-10-12, M2-AC12 scripted live check on the PC (owner allowed the GPU override; NOT the owner's own check)

Brain READY 158 tok/s with `--override-contention` (owner: "Yes, override start" for this check); `gpu_lease advise --window` GO before every window. Two sources (`north_sales.xlsx` 3 regions, `south_sales.xlsx` 2 regions), app `OfficeRegion` inside `LivingScope`, Office focus.

| Run | What happened | Finding / repair |
|---|---|---|
| 1 | Flow completed; 2 of URI's ops refused, only the total row written | refusal reasons were not shown: the notice now names each code and detail |
| 2 | `UNKNOWN_SOURCE: None`: the Brain put the source id into `from_sheet` (direct probes: 2 of 3 answers) | M2-D9 schema enums; example op in the prompt; probes then 5 of 5 correct ids |
| 2b (probes) | The Brain placed "Total" on a copied row (4 of 5 answers) | M2-D8 `OVERLAPS_EARLIER_OP`; the copied rows are never overwritten |
| 3 | Second request ("add Total under the regions") answered "sheet is empty": the Brain saw only `Sheet1` | M2-D9 excerpt of every sheet for new workbooks |
| 3 | First request copied too few S1 rows (row miscount) | M2-D7 open ranges and bare-column targets; probes then 3 of 3 correct (12 cells) |
| 4 | **COMPLETED_WITH_RESULT.** Request 1: 12 cells (S1 table with header, then S2 rows stacked under it); Accept all; request 2: `Total` and `=SUM(B2:B6)` in row 7; Accept all; summary card; Create file. The new file holds exactly `Region/Amount, North 120, North-East 95, Hills 143, South 88, Coast 61, Total =SUM(B2:B6)` on one sheet `Summary` (empty `Sheet1` not written), `fullCalcOnLoad` on; both sources unchanged (SHA-256 before = after); the session became a local workbook on the new file. Brain and service stopped; GPU lease FREE. | Evidence `evidence/m2_live_check_20261012/` |

Seen in run 4's screenshots: the grid stayed on the empty `Sheet1` while URI's data was on `Summary`. Repair: the grid now lists sheets with changes first (file order unchanged). Tested (`test_grid_opens_on_the_sheet_uri_built_not_the_empty_start_sheet`); **not re-verified on the PC** (the Brain had been stopped; another override would be needed).

Gates after these repairs: Python `tests/office tests/a2ui tests/ws tests/oi` 872 passed, 27 skipped; `flutter test` 541 passed, 5 skipped; `flutter analyze` 2 pre-existing infos; `ws_frozen_check` ok.

Model quality note: the local Brain still makes planning slips; every op is validated, refused ops are explained in the pane, and nothing is written until the owner accepts and approves.

### 2026-10-12, roles added (M2-D10/D11, owner request)

| Check | Result |
|---|---|
| `tests/office/test_m2_new_workbook.py` | 37 passed (7 new role tests) |
| `uri_ui/test/office` | 28 passed (2 new role/findings tests) |

The PC live check (M2-AC12, run 4) predates the roles: it is evidence for building a new workbook, not for the role flow. The harness now sets both files as references first; a PC run of the role flow needs the Brain (owner's GPU permission) and is NOT VERIFIED until then.

### 2026-10-12, PC live check of the role flow (owner allowed the GPU override; NOT the owner's own check)

Brain READY 159 tok/s with `--override-contention`; `advise --window` GO before each window. Evidence `evidence/m2_roles_live_check_20261012/`.

| Mode | Result |
|---|---|
| Check (`budget.xlsx` = Check, `rates.xlsx` = Reference) | COMPLETED_WITH_RESULT. A request before the roles was not sent ("First say what each file is for..."). After the roles, `budget.xlsx` was the working file (shown in the sheet view, "Working file: budget.xlsx"). URI (3.1 s) found "Food amount is 300 but should be 350 according to the rates file" and proposed `Budget!B3 = 350`; Accept all; the M1 save card; saved in place with a backup. `rates.xlsx` unchanged. **Missed:** the wrong total (`Total` 1500, rows add up to 1470 after the fix); the local Brain did not report it. |
| Build (both files = Reference) | COMPLETED_WITH_RESULT. The new file holds exactly `Region/Amount, North 120, North-East 95, Hills 143, South 88, Coast 61, Total =SUM(B2:B6)`; the sheet view listed `Summary` first; both references unchanged. |

The check run used a build made before the opening notice was reworded ("Added ... Say what each file is for"); the build run used the reworded one. Brain and service stopped; GPU lease FREE.

Limitation (model, not mechanism): the local Brain's checks are not exhaustive (it missed an arithmetic error). Findings are suggestions; the owner remains the reviewer.

### 2026-10-12, Codex review of 99bd8116 (owner: "Send the review to codex")

`codex exec`, model `gpt-6-sol`, effort high, read-only, 227 s, status COMPLETED_WITH_RESULT. **Verdict: REJECT**, 4 findings. Each was verified here before repair (Codex output is a claim):

| Finding | Verified | Repair | Test (fails on 99bd8116, passes after) |
|---|---|---|---|
| C-01 HIGH: the snapshot kept only the last 500 changes, so with more than 500 proposals the pane's *Accept all* hash could not match | reproduced: 501 proposed, 500 in the snapshot | the snapshot carries every proposed change plus the latest 500 others, `proposed_count` and `proposed_set_sha256` | `test_c01_...` |
| C-02 HIGH: after saving the working file in place, its source record kept the copy-in hash and data: switching back gave a false `TARGET_CHANGED`, and as a reference its data was stale | confirmed by reading `_apply`/`_switch_target` | an in-place save of a working file updates its source record; a real outside change is still refused | `test_c02_...` |
| C-03 HIGH: `Draft.propose` changed the draft before a refusal (cap, unknown sheet, locked cell), leaving partial proposals | reproduced: cap 2, 2 changes left after `DRAFT_TOO_LARGE` | propose is all or nothing (capacity checked first; any refusal restores the draft) | `test_c03_...` |
| C-04 MEDIUM: `/sources` accepted files while a working file was set, contrary to the AC2 text | confirmed | kept the behaviour (a later file is usually another reference, and it waits for a role); corrected AC2, which contradicted M2-D11 | `test_c04_...` (passes before and after: a documentation correction) |

Codex could not run pytest in its read-only sandbox (no temporary folder) and did not run Flutter; the PC gates below are this session's.

PC gates after the Codex repairs: Python `tests/office tests/a2ui tests/ws tests/oi` 883 passed, 27 skipped; `flutter test` 543 passed, 5 skipped; `flutter analyze` 2 pre-existing infos; `ws_frozen_check` ok.

### 2026-10-12, Codex re-review of 317a64e2 (round 2)

`gpt-6-sol`, high, read-only, 268 s, COMPLETED_WITH_RESULT. **Verdict: REJECT.** C-01, C-03, C-04 REPAIRED; C-02 PARTIAL (see R2-02). Verified here before repair:

| Finding | Verified | Repair | Test (fails on 317a64e2, passes after) |
|---|---|---|---|
| R2-01 HIGH: `copy_range` copied cells beyond the reader's 50,000-cell cap as empty, silently | reproduced | copying from a sheet that was read only in part is refused (`SOURCE_SHEET_TOO_LARGE`) | `test_r2_01_...` |
| R2-02 HIGH: the same file could be added twice; after a save through one record the other went stale | confirmed by reading | one record per physical file: a second selection is refused (`DUPLICATE_FILE`) | `test_r2_02_...` |
| R2-03 MEDIUM: undo removed an `add_sheet` change but not the sheet; the grid was not resynced | reproduced | undo/redo restore a new workbook's sheets as well (an opened file's base is not copied, to keep edits fast) and return the workbook for the grid | `test_r2_03_...` (2 tests) |
| R2-04 MEDIUM: workbook (600) and reference (400) excerpts allowed 1,000 cells, against the 600 total in the plan | confirmed by reading | one budget: references get what the workbook excerpt leaves | `test_r2_04_...` |

M2 limit added: a sheet larger than 50,000 cells can be shown and checked in part only; it cannot be a copy source.
PC gates after round 2: Python 888 passed / 27 skipped; flutter test 543 passed / 5 skipped; ws_frozen_check ok.

### 2026-10-12, Codex re-review of a4838589 (round 3)

`gpt-6-sol`, high, read-only, 199 s, COMPLETED_WITH_RESULT. **Verdict: REJECT.** C-02, R2-01, R2-02, R2-04 REPAIRED; R2-03 PARTIAL (R3-01).

| Finding | Repair | Test (fails on a4838589, passes after) |
|---|---|---|
| R3-01 MEDIUM: `rename_sheet` cleared undo and redo | no longer cleared: every saved version holds its own sheets and changes | `test_r3_01_...` |
| R3-02 HIGH: within one answer, a rename hid earlier writes from the overlap rule, so a later op could silently replace an earlier op's value | the cells written earlier follow the rename | `test_r3_02_...` |
| R3-03 MEDIUM (non-blocking): a malformed `findings` field (not a list) crashed the check | ignored unless it is a list | `test_r3_03_...` (dict and number cases failed before) |

Known edge (not a finding): a bare-column target on a sheet renamed earlier in the same answer counts only cells written in that answer, not cells accepted before under the old name; the copy is then proposed over those cells as ordinary change cards showing before and after, never applied without the owner.
PC gates after round 3: Python 894 passed / 27 skipped; flutter test 543 passed / 5 skipped; ws_frozen_check ok.
