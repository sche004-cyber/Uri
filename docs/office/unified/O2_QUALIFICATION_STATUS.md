# O2 and O2P qualification status (visible receipt, not a freeze)

Date: 2026-10-15. Branch `phase/uri-office-u-2-a` (local only; nothing pushed, merged or deployed).
**O2 is NOT frozen and NOT accepted for integration. O2P is NOT qualified (PARTIAL at best without a physical
printer).** The freeze rule (plan §12) needs every applicable row PASS at one exact commit, the Brain rows in an
owner-approved GPU window, the owner check, and independent acceptance of the phase.

Only results with `COMPLETED_WITH_RESULT` evidence are counted as PASS.

## Independent review

| Round | Scope | Commit | Verdict |
|---|---|---|---|
| 1 | WS-A backend | `6d2d6816` | REVISE (2 major), repaired |
| 2 | WS-A backend | `c974a655` | ACCEPT WITH FINDINGS (contract o2.1 frozen for O2P) |
| 3 | Flutter B1 workspace, O2P printing, live-run repairs | `63e0e73f` | REVISE (narrow), repaired; round 4 pending |

## Automated suites (author's runs after the round-3 repairs, Windows 11)

| Suite | Result |
|---|---|
| `tests/office_u2` + `tests/devices`, not engine (includes one real job to Microsoft Print to PDF, OD-U13) | 182 passed |
| `tests/office_u2/test_render_engine.py` (real LibreOffice: canaries, chart, profile in effect, crash/idle/kill) | 15 passed |
| `tests/office_u2/test_service_o2.py -m engine` (end to end through the service) | 4 passed |
| `tests/office` + `tests/a2ui` (M1/M2 + A2UI, Univer bundle staged) | 483 passed, 5 skipped (2 need `npm ci`, 3 POSIX-only) |
| `uri_ui` `flutter test` | 587 passed, 5 skipped |

## Live matrix (plan §12, A1 §A8)

Evidence: `evidence/o2_live_20261015/README.md` (service run 7, UI run 2).

| Row | Status | Notes |
|---|---|---|
| C1 intent, deterministic subset | PASS (automated corpus 24/24, 0 Brain calls; UI: navigation and clarification shown) | |
| C1 intent, Brain subset | **BLOCKED** | no GPU window |
| A1 open and preview correctness | PASS | |
| B1 (a) engine regression, (b) structure | PASS (live renders inspected; chart regression fixed) | (c) fidelity against Microsoft Word: **NOT VERIFIED** (no Office licence) |
| K1 rendering | PASS | screenshots and page images in the evidence |
| D1 save, reopen, no overwrite | PASS | |
| I1 Word/PowerPoint/Excel to PDF | PASS | |
| D2 batch | N/A (O7) | |
| O1 one-hint rule | PASS (automated U8; live shows one hint) | |
| E1–E7 scripted first use, widths, keyboard | PASS for the scripted parts (UI run 2; widths set on the region, not the window) | owner think-aloud: **BLOCKED** (owner away) |
| F1 canaries | PASS (HTTP, SMB) | WebDAV canary: not run |
| F2 crash/timeout | PASS (engine tests) | |
| F3 kill mid-run, resume | PASS | |
| F4 corrupt/encrypted/zip bomb/XXE | PASS (automated) | |
| F5 disk full | PASS by fault injection only | real disk-full: **NOT VERIFIED** |
| F6 file changed while open | PASS (automated `INPUT_CHANGED`) | |
| G1 originals and temp | PASS | |
| H1 latencies | PASS | |
| H2 CPU, RAM, GPU census | **Measured; AC-O2-16 not met as written**: raster worker 30–41 MB dedicated GPU memory while alive (0 % engine), 0 after its idle stop; print worker 53 MB (300 dpi) to 146 MB (600 dpi) while printing (engine ≤ 2 %) | owner decision |
| H3 Brain speed with Office open | **BLOCKED** | no GPU window |
| L1 Excel live journey with the Brain | **BLOCKED** | no GPU window |
| L2 repeats | PASS | |
| L3 Excel suites | PASS (483 + Flutter) | |
| J1 realistic synthetic documents | PASS | |
| K2 visual inspection | Reviewer part: done by Claude (montages inspected) | owner part: **BLOCKED** |
| R1 follow-up chips | PASS (automated U17; live "Show my PDFs") | |
| P-1, P-2, P-4, P-5, P-6 | PASS | P-3 is O4 |
| PR-1 to PR-5, PR-10 (scripted), PR-11 (deterministic), PR-12 | PASS (virtual printers only) | |
| PR-6 to PR-9 physical print, progress/cancel, offline, printer error | **NOT VERIFIED** | no physical printer; needs one and owner authorization |

## Open items before any freeze

1. Owner decision on the GPU finding (AC-O2-16).
2. GPU window for C1 (Brain), H3 and L1.
3. Owner check (E, K2).
4. A physical printer and authorization for PR-6 to PR-9 (O2P only).
5. Authenticode signer check (plan F11) not implemented; SHA-256 pin is the control in force.
6. Round 3 findings (if any) resolved and re-reviewed at the final commit.
