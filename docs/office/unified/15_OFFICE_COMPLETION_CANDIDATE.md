# URI Office completion candidate (2026-10-16): Excel completion, folder access, Word and PowerPoint authoring

Branch `candidate/office-completion-20261016`, built on the integrated O2 baseline `eaeb10c1` (OD-A4) by merging the
three milestone branches, each already merged with the integration tip:

| Milestone | Branch | Record and acceptance criteria |
|---|---|---|
| Excel completion (OD-R3, OD-R2) | `milestone/office-excel-completion-20261016` | `13_EXCEL_COMPLETION_PLAN.md` (XC-1..XC-9) |
| Folder access (OD-R1) | `milestone/office-folder-access-20261016` | `14_FOLDER_ACCESS_PLAN.md` (FA-1..FA-8) |
| Authoring A/B (OD-A1, OD-A3, OD-A5) | `milestone/office-authoring-ab-20261016` (contained in C) | `11_AUTHORING_A_B_PLAN.md` (AB-1..AB-11) |
| Authoring C, Word | `milestone/office-authoring-c-word-20261016` | `12_AUTHORING_C_WORD_PLAN.md` (C-1..C-9) |

Merge conflicts were additive (new pickers in `office_bridge.dart` and `platform_office_environment.dart`, new
routes in `service.py`, new client methods): both sides kept; the INT-L2 wrapper of the integration kept.

## Acceptance criteria for this candidate

| ID | Criterion | Evidence |
|---|---|---|
| OC-1 | The candidate descends from the canonical tip and contains each milestone branch tip | `git merge-base --is-ancestor` |
| OC-2 | Each milestone's unit, service and real-engine criteria hold on the combined code (XC-1..7, FA-1..6, AB-1..7, C-1..7) | gates (office, office_u2, a2ui, Flutter, page JS) with no new failure against canonical |
| OC-3 | Independent review ACCEPT (or AwF) on the exact commit, covering all four records | driver receipt |
| OC-4 | Live (Stage 8, production main, real service and engines, real Windows dialogs): PowerPoint edit/new/template/leave/refused save (A01-A05), Word edit/new/template (C01-C03), a folder on D: (F01), Excel row insert through URI in Brain mode (X01), plus the O2 journeys for regression | live record |
| OC-5 | Frozen boundary intact; no unapproved protected change | `ws_frozen_check` |

Not verified by these runs: physical keyboard and mouse (WidgetTester input), owner's own files, Excel formatting set
through the WebView2 page by a person (the page's saved-style path is covered by the page JS tests on the real Univer
engine).

## Live qualification record (2026-10-16)

Production `main()` through `integration_test`, real Core, real Office service and engines, Runtime v1 Brain under the
GPU lease (no override), real Windows file and folder dialogs filled by the harness (Win32 messages); pointer and keys
through Flutter WidgetTester, so physical input is NOT qualified. Window 1264x681 with the UI V2 rail. Evidence:
`evidence/office_completion_20261016/` (records of every run, failure screenshots, the drivers as run).

| Run | Commit | Result | Product findings repaired (commit) | Harness corrections |
|---|---|---|---|---|
| a1 | `6163510f` | 7/12 | editor preview squeezed to ~170 px beside the URI pane (`8dd5b566`: URI pane is a side sheet while editing); stale "not allowed yet" message after adding a folder (`54b3ce6b`) | lazily built slide strip not scrolled; a picture change waited on "not busy" instead of the change |
| a2 | `6163510f` | 10/12 | refused save showed `Refused: TARGET_CHANGED (...)` and the editor kept "Waiting for your approval" (`75e90a38`) | F01 stray open; X01 order |
| a3 | `54b3ce6b` | 10/12 | - | F01 path lost its backslash; X01 per-card Accept |
| a4 | `75e90a38` | 11/12 | - | X01 card button is "Save to file" |
| a5 | `75e90a38` | 11/12 | two save cards shown after a second proposal (`27b1a381`: newer card replaces the older) | the harness tapped the sheet's own "Save to file" again |
| a6 | `27b1a381` | 11/12 | - | slide strip scroll (flake) |
| a7 | `27b1a381` | 12/12, run failed at teardown | `ValueNotifier used after being disposed` when the app closed with Office open (`a80f83aa`) | - |
| **a8** | **`a80f83aa`** | **12/12 PASS, exit 0** | - | - |
| o1 | `a80f83aa` | 33/34 | - | B5-excel-brain: the O2 rule counted a structural row proposal (no before/after value) as a no-op; the Brain had proposed a genuine row insert (XB-2 fixed) |
| **o2** | **`a80f83aa`** | **34/34 PASS, exit 0** (O2 regression set, Brain mode) | - | - |

What a8 shows on `a80f83aa`: PowerPoint edit (title, add slide, duplicate the chart slide, move, table and cell,
notes, picture through the dialog, undo/redo), save through the card with backup, reopened 13 slides, PDF export;
new blank presentation saved as a new file; new from the owner's .potx (11 layouts); leave with unsaved (keep, then
discard); a file changed on disk is not replaced and the refusal is said in words. Word edit (text, style, bold,
table and cell, picture, header, page numbers, landscape, replace all), save and reopen; new letter from a layout
saved as a new file; new from the owner's .dotx (letterhead header kept). Folder on D: refused, added through the
folder dialog, file opened from it. Excel: "Insert a new row above row 6 with Contingency and 5000" -> one
structural proposal in plain words -> Accept -> card -> saved; the file on disk has Contingency at row 6 and the
totals moved to row 9 as `=SUM(B2:B7)`.

OC-4 met on `a80f83aa`. The candidate after this record is `a80f83aa` plus this documentation commit only.
