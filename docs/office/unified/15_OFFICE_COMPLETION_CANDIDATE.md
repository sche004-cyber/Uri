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
