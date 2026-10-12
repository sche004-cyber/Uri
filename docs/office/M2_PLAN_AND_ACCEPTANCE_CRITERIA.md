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
| M2-D4 (amended by M2-D12) | In a new workbook, `add_sheet` takes effect in the draft at once (there is no file yet) and is listed in the conversation. A sheet left with no cells is not written. Saving with no cells at all is refused (`NOTHING_TO_SAVE`). | Structure is free until the file exists; it keeps the draft model unchanged. |
| M2-D5 | New files are written with `openpyxl` (already in `requirements.txt`): values and formulas only, no styles; `calcPr fullCalcOnLoad` so Excel calculates on open. | Plain, reproducible output; styling is out of scope for M2. |
| M2-D7 (from the PC live check) | `copy_range` source ranges may be open-ended (`A2:B` = to the last used row, `A:B` = whole columns) and the target `cell` may be a bare column (`A` = first empty row below what those columns hold, including earlier ops of the same answer). | The local Brain miscounted table rows on the PC (dropped rows, stacked a total onto data); these forms move whole tables without counting. |
| M2-D8 (from the PC live check) | Within one Brain answer, an op that would overwrite a non-empty cell an earlier op of the same answer wrote is refused as `OVERLAPS_EARLIER_OP` (reported, never merged or moved). An empty placeholder may be filled. | A slip such as a total written over a copied row must not silently destroy copied data. |
| M2-D9 (from the PC live check) | For a new workbook the strict output schema limits `source` and `from_sheet` to the ids and sheet names that exist, and the Brain sees every sheet of the new workbook (within the cell cap), not only the first. | On the PC the Brain put the source id into `from_sheet` (2 of 3 answers), and on a second request it saw only the empty first sheet. |
| M2-D10 (owner, 2026-10-12) | Every added file needs a role the owner chooses: **Reference** (URI only reads it), **Check** or **Edit**. URI does not work with the files until each has a role: a request is refused (`ROLES_NEEDED`, and the pane does not send it) and the pane asks "What is each file for?". The role is never inferred. | The owner's intent must be explicit (consequence-aware binding: editing a file is consequential). |
| M2-D11 (owner, 2026-10-12) | At most one file is the **working file** (Check or Edit), shown in the sheet view and saved in place through the M1 path (copy-in, conflict check, backup, hash-bound card). Choosing another working file makes the previous one a reference; it is refused while the current one has unsaved accepted or typed changes (`SAVE_OR_DISCARD_FIRST`) and when the file changed on disk since it was added (`TARGET_CHANGED`). With no working file URI builds a new workbook. **Check** means: URI compares the working file with the references, lists findings (sheet, cell, issue) in the pane, and offers clear fixes as ordinary change cards; nothing is applied without the owner. | Owner answers "Findings + suggested fixes" and "One at a time". |
| M2-D12 (coordinator decision, owner instruction, 2026-10-12) | `rename_sheet` is unavailable for new workbooks. URI names a sheet when it adds it; the empty starting sheet is never written. `add_sheet` names must be unique ignoring case. Google `rename_sheet` remains available under M1. This amends M2-D4, M2-AC5 and M2-AC6. | New-workbook rename was a developer convenience, not an owner requirement. Removing it resolves R6-02, R7-01 and R7-02 by construction; case-insensitive uniqueness and a writer title check resolve R7-03. |
| M2-D6 | The correction history stays per workbook and off by default; a new workbook has no history until it is saved and reopened as a local file. | M1 OFF-O3 ruling. |

## 4. Acceptance criteria

| AC | Criterion | Evidence |
|---|---|---|
| M2-AC1 | `POST /open/new {"paths": [...]}` opens a new workbook (engine `new`, one empty sheet `Sheet1`) with 1-10 sources. Every path goes through the M1 path rule (`grants.grant_open`: owner-picked, allowed roots, regular file, 50 MB cap) and is copied in; a source whose file changes during copy-in is refused. Duplicate names get distinct labels. More than 10 sources, or a non-xlsx, is refused with nothing opened. | pytest |
| M2-AC2 | `POST /workbook/<id>/sources {"paths": [...]}` adds files to a workbook opened with "New from files" under the same rules (total stays at most 10), also while one of its files is the working file (a later file is often another reference). A file added later has no role until the owner gives it one, so requests wait again (M2-D10). A workbook opened with "Open file" or a Google link takes no added files. (Corrected 2026-10-12 after Codex C-04: the first text said "only engine `new`", which contradicted M2-D11.) | pytest |
| M2-AC3 | The view lists sources (id `S1..`, label, sheet names and sizes) and never a source path. | pytest, widget test |
| M2-AC4 | The Brain request for a new workbook contains the owner's instruction as the only instruction; each source's bounded excerpt (sheet sizes, the first rows of each sheet, a total cell cap) and the new workbook's excerpt are inside untrusted-data blocks. A source cell saying "ignore previous instructions" does not change the ops returned by the fake Brain. | pytest |
| M2-AC5 | New-workbook ops: `set_values`, `set_formula`, `add_sheet`, `copy_range{source, from_sheet, from_range, sheet, cell}`. `rename_sheet` and row ops are refused for new workbooks; Google retains its M1 operations. Each op is validated; an invalid op is reported, never guessed. `add_sheet` names are unique ignoring case. `copy_range` is capped at 5,000 cells per op, copies values only (D3), and refuses an unknown source, sheet or range. Network and external-reference formulas stay refused. | pytest |
| M2-AC6 | `add_sheet` in a new workbook changes its sheets at once (D4/D12); the panel reloads the grid from the returned workbook. | pytest, widget test |
| M2-AC7 | `POST /workbook/<id>/decide_all {"decision", "draft_version", "set_sha256"}` decides every proposed change atomically when version and set hash match, else refuses with `STALE_CHANGE` and changes nothing. Works for every engine. | pytest, widget test |
| M2-AC8 | The pane shows sources, *Add file*, *Accept all N* / *Reject all N* when more than one change is proposed, at most 50 change cards plus "and N more, marked in the sheet", and "Save as new file..." (no "Save to file") for a new workbook. | widget tests |
| M2-AC9 | `propose_save` for a new workbook requires `save_as_path`; the destination must not exist (checked at propose and again at create); the card follows D1; the create action writes the file through a temporary file in the destination folder and a no-overwrite link, so a file that appeared meanwhile is never replaced. | pytest |
| M2-AC10 | The created file opens with openpyxl and holds exactly the draft's cells (values and formulas) on non-empty sheets in order; no source file changed (hash before and after). After creating, the session is a local M1 session on the new file (copy-in), so later saves use the M1 cell patch. | pytest |
| M2-AC11 | M1 behaviour and gates are unchanged: `tests/office`, `tests/a2ui`, `flutter test`, `flutter analyze`, `ws_frozen_check`. The guarded worker never imports `uri_office`. | gates |
| M2-AC13 | Roles (D10/D11): `POST /workbook/<id>/roles` validates roles and the one-working-file rule; requests wait for every role; the Edit file becomes the working file and saves in place with a backup while references stay unchanged; switching with unsaved changes or after an outside change is refused; Check returns validated findings and fixes as proposed changes; copies into the working file respect its locked cells. The pane shows each file with Reference / Check / Edit, marks the working file, and does not send requests until every file has a role. | pytest, widget tests |
| M2-AC12 | PC scripted live check (owner choice 2b pattern, NOT the owner's own check): two source files -> URI builds a summary sheet -> accept all -> create file -> the new file holds the expected cells; sources unchanged. Needs the Brain (GPU lease; an override needs the owner's permission each time). | evidence |

## 5. Limits (M2)

- At most 10 sources per new workbook; each at most 50 MB; each sheet read up to 50,000 cells (M1 reader cap, reported as truncated).
- A generated new file larger than 50 MB is refused before it is written.
- The Brain sees bounded excerpts only (up to 600 cells in total across the new workbook and sources). `copy_range` lets URI move data it has not seen cell by cell, within 5,000 cells per op and the draft's 20,000-change cap.
- No styles, charts or pivot tables in new files; no Google targets for new files (use "Share via Google" after creating it).
- New workbooks do not offer `rename_sheet`; URI names each sheet when it adds it, and the empty starting sheet is not written.

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

### 2026-10-12, Codex re-review of 77cd9bfe (round 4)

Repair performed by Codex on the owner's instruction "Use codex for audit and repair".

| Finding | Repair | Tests |
|---|---|---|
| R4-01 MEDIUM (blocking): an outside change to the current working file could be demoted into a stale reference | Check the current working file's on-disk SHA-256 against the session hash before changing roles, target, draft, or approvals; retain the new-target check | `test_r4_01_changed_working_file_cannot_be_demoted` (both another working file and all references), `test_r4_01_switch_after_in_place_save_uses_current_hash`; the existing C-02 test now expects refusal on demotion after an outside change |

Verified by Claude before commit: the repair is limited to `_switch_target` (both checks run before any change; approvals are closed only after them); the two demotion tests fail on 77cd9bfe and pass after; the in-place-save test passes on both (it guards against a false refusal). Codex's 3 HTTP-test errors came from its sandbox (Windows ACLs cannot be set there); on the PC the file passes 55/55. PC gates: Python 897 passed / 27 skipped; `flutter test` 543 passed / 5 skipped; `ws_frozen_check` ok.

### 2026-10-12, Codex re-review of 4acacb91 (round 5)

Repair performed by Codex on the owner's instruction "Use codex for audit and repair".

| Finding | Repair | Tests |
|---|---|---|
| R5-01 MEDIUM (blocking): a generated file over 50 MB was published before the input cap refused it | Check the temporary workbook against the shared 50 MB cap before publication; refuse with `NEW_FILE_TOO_LARGE`, remove the temporary file, and close the approval | `test_r5_01_oversized_new_file_is_refused_before_publication_and_can_be_retried` |
| R5-02 LOW: a missing or unreadable working or new target raised an unhandled `OSError` during role switching | Return `TARGET_CHANGED` (409) before changing session state | `test_r5_02_deleted_working_file_refuses_role_switch_without_state_change`, `test_r5_02_deleted_new_target_refuses_role_switch_without_state_change` |

Verified by Claude before commit: the changes are limited to the size check before linking (`xlsx_new.write`), closing the approval on that refusal, and OSError translated to `TARGET_CHANGED` in `_switch_target`; no sandbox workaround is in the tests (the only monkeypatch lowers the size cap). The 3 new tests fail on 4acacb91 and pass after. Codex's leftover sandbox temp folders were deleted. PC gates are recorded in the line below.
PC gates after round 5: Python 900 passed / 27 skipped; flutter test 543 passed / 5 skipped; ws_frozen_check ok.

### 2026-10-12, Codex re-review of f9ea1f3c (round 6)

Repair performed by Codex on the owner's instruction. R6-01 also affected M1 opened files with more than 500 accepted or typed changes; this repair fixes it on the M2 branch only.

| Finding | Repair | Tests |
|---|---|---|
| R6-01 HIGH (blocking): accepted and user changes beyond the snapshot's 500-other-change window disappeared from panel marks | Keep every live change in draft order; bound only rejected and edited-by-user history to the latest 500 | `test_r6_01_snapshot_keeps_all_accepted_and_user_marks_with_bounded_history` |
| R6-02 MEDIUM (blocking): renaming a sheet left live formulas referring to the old name | Refuse only the rename op when the current view or an earlier op's formula names the old sheet, with Draft retaining its safeguard. | `test_r6_02_live_formula_refuses_rename_without_changing_draft`, `test_r6_02_rename_with_no_reference_still_works`, `test_r6_02_brain_answer_refuses_formula_then_rename`, `test_r6_02_prior_formula_refuses_rename_in_later_brain_answer` |

Codex's local rerun: 62 passed, 4 HTTP-fixture setup errors (`ACL_FAILED` in the Windows sandbox); independent review and full gate verification remain pending.

Verified by Claude before commit: changes limited to `Draft.snapshot` (all live changes; history bounded), `formula_references_sheet` with the draft backstop, and the per-op refusal in `OfficeBrain.plan` (before the op's edits are added); no sandbox workaround in the tests. 7 of the 8 round-6 tests fail on f9ea1f3c and pass after (the rename-without-reference test guards against over-refusal). Codex's sandbox temp folders were deleted. PC gates: Python 908 passed / 27 skipped; `flutter test` 543 passed / 5 skipped; `ws_frozen_check` ok.

### 2026-10-12, Codex re-review of 74f3970c (round 7)

Repair by Codex on the owner's instruction, under coordinator decision M2-D12. The round-6 account above is historical; its new-workbook rename behavior is superseded here. This repair is uncommitted and awaits independent re-review.

| Finding | Repair | Tests |
|---|---|---|
| R7-01: the formula/sheet-name matcher misread quoted names | Removed new-workbook `rename_sheet` and the matcher (M2-D12); removed rename from the new-workbook prompt and schema. Google rename remains in its M1 path. | Retired R6-02 rename expectations; new refusal tests cover direct Draft and Brain proposals; `test_r7_01_new_workbook_prompt_and_schema_do_not_offer_rename`. |
| R7-02: the rename backstop counted superseded formulas and failed the Brain answer | Removed the draft and per-op formula backstops with the unavailable new-workbook rename. A refused rename is reported per op; later ops still proceed. | `test_r6_02_brain_answer_refuses_rename_but_keeps_other_ops`, `test_r6_02_prior_formula_survives_refused_rename_in_later_brain_answer`, `test_r3_02_overlap_rule_survives_a_refused_rename_in_the_same_answer`; add-sheet undo/redo retains R3-01's state intent. |
| R7-03: case-only duplicate sheet names passed validation and openpyxl silently changed the written title | Reject `add_sheet` names equal ignoring case in ops and Draft; verify each openpyxl title exactly matches its requested name before publication. | `test_r7_03_ops_reject_case_only_duplicate_add_sheet`, `test_r7_03_draft_rejects_case_only_duplicate_add_sheet`, `test_r7_03_writer_refuses_title_that_openpyxl_changes_before_publication`. |

Codex ran the requested `python -m pytest -c scripts/phase2d_pytest.ini --rootdir=. -q tests/office`: **132 passed, 5 skipped, 183 setup errors, 2 failed**. This sandbox denies access to pytest's default Windows temporary directories (`WinError 5`), so that run does not qualify as a clean gate. A separate diagnostic run with temp-directory creation made accessible, without changing the tests, yielded **292 passed, 5 skipped, 20 errors, 5 failed**; the M2 file alone yielded **68 passed, 4 errors**. The four M2 errors are the HTTP fixture's `ACL_FAILED` while restricting the state directory; the broader run's remaining failures are page/security-environment checks. Two existing Google rename tests passed in isolation. Independent review and a clean full gate remain pending.

Verified by Claude before commit: new-workbook rename removed at every layer (ops, draft, Brain prompt and schema enum); Google rename unchanged; case-insensitive add_sheet check in ops and draft; the writer checks exact titles before publication. 10 of the round-7 tests fail on 74f3970c and pass after (the others pass on both: undo of add_sheet, prompt text, writer guard). Codex's test-run failures were its sandbox (temp folder and Windows ACLs); on the PC `tests/office` passes 317 / 5 skipped. Codex's temp folders were deleted. PC gates: Python 914 passed / 27 skipped; `flutter test` 543 passed / 5 skipped; `ws_frozen_check` ok.

### 2026-10-12, Codex review of 581cde5d (round 8)

**Verdict: ACCEPT WITH FINDINGS.** The coordinator classified both non-blocking findings as plan violations, so Codex repaired them on the owner's instruction under the owner's limitation-vs-repair rule.

| Finding | Classification | Repair | Tests |
|---|---|---|---|
| R8-01 MEDIUM: `add_sheet` accepted XML-invalid control characters, leaving an approved new workbook unwritable | Violates M2-AC5: invalid ops must be reported | Reject such names with `BAD_SHEET_NAME` during op validation and in `Draft._sheet_op`; the writer's exact-title guard remains | `test_r8_01_xml_invalid_add_sheet_name_is_refused_at_ops_and_draft` and `test_r8_01_brain_refuses_invalid_sheet_name_and_keeps_later_op` cover NUL and BEL, with later Brain ops proceeding |
| R8-02 LOW: a refused `copy_range` could still report source cells as copied empty | Violates M2-D3 reporting | Add `uncalculated` and `not_copied` counts only after the op's edits enter the Brain answer | `test_r8_02_refused_copy_does_not_report_uncalculated_cells` covers zero notes on overlap refusal and both counts on an accepted copy |

Codex's focused round-8 tests: **5 passed**. The requested full-file pytest command ran with `TMP`/`TEMP` in `.codex_tmp`: **23 passed, 54 setup errors**. The setup errors are `PermissionError: [WinError 5]` when pytest scans its temporary directory in this Windows sandbox; this is not a clean gate. The repair is uncommitted and awaits independent review and a clean PC gate.

Verified by Claude before commit: changes limited to the sheet-name check (ops and draft backstop) and moving the copy counts after the op is accepted; the 5 round-8 tests fail on 581cde5d and pass after; Codex's sandbox temp folders deleted. PC gates are in the next line.
PC gates after round 8: Python 919 passed / 27 skipped; flutter test 543 passed / 5 skipped; ws_frozen_check ok.

### 2026-10-12, Codex review of e656f68e (round 9)

**Verdict: REJECT.** R8-01 and R8-02 were confirmed repaired. Repair by Codex on the owner's instruction; this repair is uncommitted and awaits independent re-review.

| Finding | Repair | Test |
|---|---|---|
| R9-01 MEDIUM (blocking): `Office.instruct` returned `copy_range` notes only for a new workbook, so an Edit working file did not tell the owner when an uncalculated source formula was copied as empty, contrary to M2-D3 | Return `notes` for every session with added files; retain the new-workbook-only `workbook` response | `test_r9_01_edit_copy_reports_uncalculated_source_cell`: an Edit working file copies an uncalculated formula from a reference; the response reports `{"uncalculated": 1, "not_copied": 0}` |

Codex attempted the new pytest test before and after repair with `TMP`/`TEMP` and `--basetemp` under `.codex_tmp`: **0 passed, 1 setup error** each time. Pytest could not scan its temporary directory (`PermissionError: [WinError 5]`), so the regression test did not execute in this sandbox. The existing R8-02 Brain-count test passed (**1 passed**). A direct service-response probe after repair passed 3 assertions (notes, proposed change, and no `workbook` field in Edit mode). Independent review and a clean pytest run remain pending.

Verified by Claude before commit: the change only moves `notes` out of the new-workbook branch (returned for any session with added files); the round-9 test fails on e656f68e and passes after (Codex could not run it in its sandbox). PC gates are in the next line.
PC gates after round 9: Python 920 passed / 27 skipped; flutter test 543 passed / 5 skipped; ws_frozen_check ok.

### 2026-10-12, Codex review of 3dee8bb9 (round 10)

**Verdict: ACCEPT WITH FINDINGS.** R9-01 was confirmed repaired. Both round-10 findings are LOW, non-blocking, cheap to repair, and are not limitations already stated in this plan. Codex repaired them on the owner's instruction under the owner's repair-versus-document rule; the repairs remain uncommitted for independent re-review.

| Finding | Classification | Repair | Test |
|---|---|---|---|
| R10-01: changing the working file closes the service approval, but leaves its A2UI card in the Flutter pane until a click fails with `UNKNOWN_SURFACE` | Undocumented stale approval; repair | `OfficeController.setRole` deletes the hub's open surfaces when the working file changes, using the same `deleteSurface` mechanism as `_forgetWorkbook` | `switching the working file removes its open approval surface` also checks that an unchanged working file retains the card |
| R10-02: the no-hard-link fallback can leave a partial `.xlsx` when its exclusive-create copy fails | Undocumented partial file; repair | After `O_EXCL` creates the destination, a copy failure removes that destination and re-raises; an existing destination is still refused without replacement | `test_r10_02_fallback_write_failure_removes_only_its_destination` simulates unavailable hard links and a partial write, checks destination and `.~uri-*` cleanup, then checks existing-file preservation |

Codex's focused pytest invocation did not run the test: pytest raised `PermissionError: [WinError 5]` while scanning `.codex_tmp/pytest-r10` during temporary-directory setup. The R10-02 test body passed when invoked directly with `.codex_tmp` supplied as its temporary directory; a separate direct fallback probe also passed (partial destination removed, temporary file removed, existing destination preserved). Flutter test verification could not run in this sandbox: the Flutter tool cannot open `C:\Users\cheta\flutter\bin\cache\lockfile` outside the writable worktree. Direct `dart analyze` was also denied when it tried to start `dartaotruntime.exe`.

Verified by Claude before commit: `_clearSurfaces` runs only when the working file changed (and from `_forgetWorkbook`, unchanged behaviour); the writer fallback removes only the file its own O_EXCL created. Both new tests (Python and Dart) fail on 3dee8bb9 and pass after (Codex could run neither fully in its sandbox). PC gates: Python 921 passed / 27 skipped; `flutter test` 544 passed / 5 skipped; `flutter analyze` 2 pre-existing infos; `ws_frozen_check` ok.
