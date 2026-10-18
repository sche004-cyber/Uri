# BRAIN-QC-20261018 - Brain Quick Controls: candidate report

Branch `milestone/brain-quick-controls-20261018` (base `f3d5eb29`). Code: `aa7a1cf6` (UI); the Python runtime code
has not changed since `0d599b6a`, and every session verified that byte for byte. Plan and acceptance criteria:
`BRAIN_QC_PLAN.md`. Record: `BRAIN_QC_QUALIFICATION.json`. Status: the candidate passes; independent review is
pending. Nothing is integrated, frozen, pushed or deployed. The default Brain stays the frozen Runtime v1.

## What the user gets
Three chips under the chat box in the Workspace / dashboard composer: **Thinking** (Auto / Off / On, per message; it
also shows what the last answer actually did), **Vision** (On / Off) and **Context** (32K / 64K). A Vision or Context
choice loads a qualified profile, Standard (frozen) or Long context (64K, no vision), after a confirmation. 64K with
vision is listed but disabled, with the reason it is not qualified (CRASH-1, DEMOTE-P1). The chips show "(starting)"
or "(not running)" until the worker has verified the running Brain, and "Switching to ..." during a reload.

## Live results (real Windows app via production main(), real worker, Core and Brain; automation input)
| Run | Checks | Switch to Long / back to Standard (s) | Decode tok/s Standard / Long / Standard after switch |
|---|---|---|---|
| qc-1 (Brain first) | 20/20 | 29.9 / 35.1 | short answers only |
| qc-2 (UI first) | 20/20 | 31.5 / 34.7 | 122.5 / 98.7 / 149.4 |
| qc-3 (UI first, `aa7a1cf6`) | 20/20 | 31.4 / 36.6 | 125.6 / 99.3 / 147.6 |

- **Thinking:** Off gave tier FAST and On gave NORMAL on the same server. Nothing reloaded.
- **Continuity:** the number 4817, told before the first switch, was recalled after each switch. The worker processes
  stayed the same and the session stayed the same.
- **Turn safety:** a message sent during a switch was refused with BRAIN_RESTARTING.
- **Old server stop:** about 3.5 s.
- **VRAM:** Long context uses 13.9 GB dedicated (fit FITS, +1.64 GB). Standard next to the open app window is
  AT_RISK (-0.29 to -0.34 GB) with 1.7 GB non-local, which is the known frozen-config behaviour. Decode after the
  switch was still healthy.
- **qc-1, Brain-first harness order:** the UI window opened after the Brain loaded. About 0.77 GB moved to system
  memory, and one 257-token Thinking answer decoded at 40 tok/s. This is P-GOV-1, which the launcher order (UI first)
  avoids. qc-2 and qc-3 use the launcher order.
- **Regression:** canonical UI V2 journeys 68/68 (`uiv2-main`, `uiv2-main-2` on the final code).
- **No-Brain run (`dry-1`):** nothing is shown as active, switching is disabled, and the chips say "(not running)".

## Gates (exact commit)
pytest tests/oi + tests/ws 759 passed / 23 skipped (baseline 731 / 23, plus 28 new); flutter test 776 passed;
flutter analyze 4 pre-existing infos; Windows release build OK; ws_frozen_check ok; frozen UI V2 files only additive.

## Open findings / limitations
- QC-F1: the profile choice is not persisted. A new Brain host starts on Standard, and the UI shows what actually runs.
- QC-F2: the context-shrink confirmation is verified by unit and widget tests only.
- QC-F3: the host's 60 s residency alert missed the qc-1 demotion because of timing. This is pre-existing host
  behaviour and is unchanged.
- QC-F4: `test_frozen_core` stray list (pre-existing at base) now also names the two new BRAIN-QC files.
- The new `reconfigure` action changes `ws_brain_host.py`, which the runtime-profiles IC-1 counts as byte-identical
  to 7c7a7776. Integrating BRAIN-QC therefore supersedes that file and needs its own review.

---

## Review R1 (2026-10-18): corrections and repairs

The independent review is in `review/R1_report.md` (verdict: REVISE, narrow). The text above this line is kept as it
was written at `177a5319`. The corrections below replace any statement above that they contradict.

**Code:** repaired code `aba3a5b6`. The runtime for the live runs was materialized from `578f7c40`, whose code is
identical; `runtime3` was verified byte for byte by the session. Gates run at `25701f51`, which is code-identical,
with `.head` files in `evidence/gates/`.

### Corrections to the earlier claims
- **C-1 (R1-01):** commit `aa7a1cf6` ("no stale ready while switching") claimed something its own qc-3 evidence
  disproves. In qc-3 the header and the right panel showed "ready" for about 10-17 s while the old server was
  stopping, and again during calibration. The qc-3 PASS for QC-4 covered only the chips and the RECOVERING card, not
  the header.
- **C-2 (R1-02):** the shrink dialog promised "the Brain will not see all of it at once", but nothing trims the
  history. QC-8 "MET_UNIT_ONLY" checked only the confirmation gate.
- **C-3 (R1-04):** the earlier "Gates (exact commit) ... release build OK" was not pinned to the reviewed code. The
  release build log predated `aa7a1cf6`, and the frozen-files patch and the diff stat were stale.
- **C-4 (R1-05):** QC-9 said "only additive". The added lines are additive, but `refreshHealth` (a frozen UI V2
  method) now also reads `brain_status` on every screen when the health state changes, and on every poll while the
  Brain is recovering. UI V2 journeys 68/68 were re-run on the repaired UI (`uiv2-main-3`, `29db21f9`).

### Repairs
| Finding | Change | Verified by |
|---|---|---|
| R1-01 MEDIUM | `refreshHealth` re-reads `brain_status` on a health change and on every poll while health is RECOVERING or a switch is pending. During a pending switch, a READY status is shown as "starting" (`runtime_state` keeps the raw READY), so the Brain is not reported ready until the switch is finished. | Widget test: READY at the edge, then STOPPED, LOADING, READY-before-calibration, then READY. Live qc-4 and qc-5: `QC-header-truthful-*` PASS, 0 rows show "ready" while the switch is pending. Screenshot `qc-4/06-switching.png` header reads "starting". |
| R1-02 MEDIUM | No "switch anyway" path, and `confirm_shrink` is removed from the schema. The worker refuses a target context that the largest session's last answer context plus a 4,096-token answer reserve would not fit (`CONTEXT_SMALLER_THAN_CONVERSATION`, with the numbers). The UI says so and advises keeping the larger context. Context size is now tracked per session. | Unit tests (30,000 + 4,096 > 32K refused; 20,000 allowed; the old confirm is a schema error) and a widget test. **Live evidence with a conversation over 32K tokens is still absent.** |
| R1-03 LOW | The fit pre-check uses `cfg_required_mib(derive_config(...))`, the same 15,626 MiB the start budgets for the frozen profile. | Unit test. Live qc-4/qc-5: `fit_before.required_mib` 15626 for Standard. |
| R1-04 LOW | Gates, release build, frozen check, frozen-files patch and diff stat regenerated at `25701f51`, each with a `.head` file. | `evidence/gates/` |
| R1-05 LOW | Disclosed (C-4). | |
| R1-06 LOW | The dialog now says "If URI sees before the switch that it does not fit, it keeps the current Brain. If the new setting then fails to start or waits for memory, choose the previous setting again." Listed as QC-F5. | Widget test. |
| R1-07 LOW | QC-F4 completed (below). | |
| R1-08.1 | A refusal notice clears after 20 s. | Widget test. |
| R1-08.2 | Outcome lines for a waiting, stopped or other non-ready end of a switch. | Widget test. |
| R1-08.3 | Behaviour kept and documented: choosing a setting while the Brain is stopped starts it. The dialog says so, and the host records `started_stopped_brain`. | Unit and widget tests. |
| R1-08.4 | Below 640 x 420 the chip row stays hidden, and one compact "Brain settings" button in the composer row opens the same controls in a dialog (reachable at 800x600). | Widget test at 800x600; UI V2 no-overflow tests pass. |
| Coordinator note | P3 (32K + vision, no MTP) is recognized but never a switch target (`switchable: false`, `PROFILE_NOT_OFFERED`). Only Standard and Long context are offered. | Unit and widget tests. |

Note on the coordinator message: it lists `(32768, gpu, False)` (which is P3) as allowed by the runtime-profiles
SELECTABLE, and in the same message says P3 is not in SELECTABLE. The two statements conflict. Quick Controls
follows the instruction itself (never offer P3), and that holds under either reading.

### Live re-verification (real app, production main(), real Brain, UI-first, no override)
| Run | Code | Checks | Switch to Long / back (s) | Stop (s) | Decode tok/s Standard / Long / Standard after switch |
|---|---|---|---|---|---|
| qc-4 | `78db55f6` (R1 repairs) | 22/22 | 30.9 / 37.3 | 3.5 | 121.5 / 97.4 / 151.3 |
| qc-5 | `578f7c40` (final code) | 22/22 | 30.8 / 38.2 | 3.6 | 121.2 / 98.2 / 148.3 |

- In both runs, "4817" was recalled after each switch, the worker processes stayed the same, a message sent during
  the switch was refused, and the lease was FREE afterwards.
- `uiv2-main-3` (`29db21f9`): 68/68.
- The P3 change after it only touched catalog resolution and one refusal text; UI V2 was not re-run for it, and
  qc-5 covers it live.

### Gates at `25701f51` (code = `aba3a5b6`)
- pytest `tests/oi` + `tests/ws`: 762 passed, 23 skipped.
- flutter test: 778 passed.
- flutter analyze: 4 info messages, all in files this milestone did not touch.
- Windows release build OK.
- `ws_frozen_check` ok.
- Frozen UI V2 files against `7893aaed`: +96/0 and +37/0 lines (behaviour note C-4).

### Open findings (updated)
- **QC-F1:** the choice is not persisted; a new host starts on Standard.
- **QC-F2:** no live evidence with a conversation over 32K tokens. The refusal path is covered by unit and widget
  tests only.
- **QC-F3:** the pre-existing host residency alert can miss a demotion because of timing.
- **QC-F4:** two guards would flag the new files and were not edited, because they are governance files:
  `tests/phase2a/test_frozen_core.py` ALLOWED_NEW and `scripts/phase2close_chain.py` WS_EXACT. Both lack
  `uri_operational_intelligence/brain_quick_controls.py`, and the base `f3d5eb29` already lacks the runtime-profiles
  files in both.
- **QC-F5:** there is no automatic fallback. If the pre-check passes but the new start then fails or waits, URI has
  no ready Brain until the user chooses another setting. The UI tells the user to do so.
- **QC-F6:** the existing health chip can show the previous instance's tok/s for a moment during a switch. This is
  pre-existing WS hardening behaviour and was not changed.
- `ws_brain_host.py` supersedes the runtime-profiles IC-1 byte-identity for that file. Integration needs its own
  review.

---

## Review R2 (2026-10-18): ACCEPT WITH FINDINGS (3 LOW, 2 INFO); repairs

The review report is in `review/R2_report.md`. The sections above are kept as written; this section adds to them.
The code repairs are in `ce5c2fe0`. The gates were run again on the commit named in `evidence/gates/*.head`.

| Finding | Change | Verified by |
|---|---|---|
| R2-01 LOW | `refreshHealth` also re-reads the status while the stored status is a masked one (`switching: true`). A failed read on the poll where the switch ends can therefore no longer leave "starting" behind. | Unit test (OiConversation, in the widget test file): the status read throws at the final edge, the next READY poll re-reads, and the result is READY and `brainReady`. |
| R2-02 LOW | (a) The context sizes are now a real LRU: a key is popped before it is re-inserted. (b) The notice is worded for the whole worker: "a conversation URI has held since it started uses about N tokens ... Keep the larger context until URI is restarted." (c) The code comment says the 4,096-token reserve is a heuristic: the next user message is not counted. Scope listed as QC-F7. | Unit test (LRU eviction keeps a recently used long session); widget test (the notice text). |
| R2-03 LOW | The IC-1 note is corrected (below). | |
| R2-04 INFO | `BRAIN_QC_QUALIFICATION.json` corrected: the AT_RISK range now includes qc-4's -336.6 MiB, QC-6 cites qc-4 and qc-5, and `not_qualified` now names the refusal path. | |
| R2-05 INFO | Noted as QC-F8. | |

### Corrected IC-1 / integration note (replaces the last bullet of "Open findings (updated)")

BRAIN-QC changes three files that the runtime-profiles plan counts in IC-1, including amendment A1 (fa0a70e6,
4d782ef1):

| File | Change vs `f3d5eb29` |
|---|---|
| `scripts/ws_brain_host.py` | the reconfigure action |
| `uri_operational_intelligence/brain_health.py` | `RESTART_ACTIONS` / `ACTIONS`, and the profile in a request |
| `scripts/run_uri_integrated_worker.py` | the `host_request` lambda passes the profile |

The runtime-profiles branch has moved on to `c3fc8bbc`: its SELECTABLE allows only the frozen config, P2 and
`(32768, gpu, False)`. BRAIN-QC was gated on `f3d5eb29`, not on that tip. Before integration, BRAIN-QC must be
rebased or merged onto the current runtime-profiles tip, or onto the integrated canonical commit, and its gates and
one live switch round trip re-run. That is the main session's decision.

### Open findings added
- **QC-F7** (R3-03 wording): the shrink refusal covers every conversation the worker has answered since it started; the sizes are
  never cleared except by LRU eviction beyond 64 sessions. Original text:
  never cleared, and neither is the history the worker keeps. One long conversation therefore blocks a switch to a
  smaller context until URI restarts, which is conservative. The 4,096-token answer reserve is a heuristic and does
  not count the next user message.
- **QC-F8:** when a harness or CLI started the host on P3 (32K + vision, no MTP), the menus offer only Long context,
  because P3 is never a target. Getting back to Standard takes two switches.

### Live evidence after R2
No new live run was made. The R2 changes are a status re-read condition at the end of a switch, a notice text, and the
order of an internal dict, and the widget and unit tests cover them. The live switch evidence (qc-4, qc-5) was taken
on `78db55f6` and `578f7c40`, which do not include `ce5c2fe0`.

### Gates for the R2 repairs: `9ea83b24` (code = `ce5c2fe0`)
- pytest `tests/oi` + `tests/ws`: 763 passed, 23 skipped.
- flutter test: 779 passed.
- flutter analyze: 4 info messages, all in files this milestone did not touch.
- Windows release build OK.
- `ws_frozen_check` ok.
- Frozen UI V2 files against `7893aaed`: +98/0 and +37/0 lines.

The `25701f51` gate section above is kept as history.

---

## Review R3 (2026-10-18): ACCEPT WITH FINDINGS (2 LOW, 2 INFO); repairs

The review report is in `review/R3_report.md`. The code and test repairs are in `e39a9a13`.

| Finding | Change |
|---|---|
| R3-01 | `BRAIN_QC_QUALIFICATION.json` QC-9 and QC-10 now point to the current gates, and the R2 section above has its gate line. |
| R3-02 | The R1-02 widget test now also asserts the notice wording ("a conversation URI has held since it started", "until URI is restarted"). |
| R3-03 | The QC-F7 text and the `worker_bridge.py` comment now say: the sizes are never cleared except by LRU eviction beyond 64 sessions. |
| R3-04 | The notice now reads "has held since it started" (it said "holds"); the test asserts the new wording. |
| Nit | The R2-01 test is now described as a unit test of `OiConversation`. It lives in the widget test file. |

### Gates at `e39a9a13` (final code)
- pytest `tests/oi` + `tests/ws`: 763 passed, 23 skipped.
- flutter test: 779 passed.
- flutter analyze: 4 info messages, all in files this milestone did not touch.
- `ws_frozen_check` ok.
- Frozen UI V2 files against `7893aaed`: +98/0 and +37/0 lines.

The release build was not re-run. Its last build is `9ea83b24`, recorded in `uibuild-release.head`. R3 changed only
one string in the UI code. No live run was made for R3, as the coordinator directed: the changes are wording, a
comment and a test assertion.

---

## Refresh onto the integrated canonical `cd4a7963` (2026-10-18)

- **Merge:** `0226e7ee` merges canonical `integration/git-sync-20261008` = `cd4a7963` (runtime profiles integrated;
  it contains `f3d5eb29` and `c3fc8bbc`). It is a merge commit with no conflicts; nothing was rebased or rewritten.
  This is still a candidate: nothing is integrated or pushed.
- **Catalog vs `runtime_profile_selection.SELECTABLE`** (frozen, P2 `(65536, off, False)`, P3 `(32768, gpu, False)`):
  - the qualified entries in the catalog are exactly SELECTABLE;
  - Quick Controls offer only Standard and Long context;
  - P3 is recognized but never offered;
  - P1 is refused by both the catalog and SELECTABLE.

  A unit test pins all of this: `test_catalog_agrees_with_the_integrated_selectable_set`.
- **R9-01** (runtime-profiles audit note), fixed in `4c61a0b3`: the host writes the selection file only for a
  SELECTABLE profile. A host started on a research profile (for example P1 via `--profile`) removes any selection,
  writes none, and records `selection_error: PROFILE_NOT_SELECTABLE`. The worker then verifies against the frozen
  config and fails closed. Unit test: `test_host_never_writes_a_selection_for_a_research_profile`.
- **`backend.profile.qualified`:** the accepted `runtime_profiles.describe` still says `qualified: false` for P2 and
  P3. The Quick Controls UI never shows that field and never calls a running profile "qualified". It names profiles
  (Standard, Long context) and shows "Not qualified yet" only for P1, whose catalog entry is the authority, with
  evidence paths.
- **IC-1 / integration note** (replaces the earlier note; corrected by R4-02, see below): against canonical
  `cd4a7963`, BRAIN-QC changes three IC-1 files: `scripts/ws_brain_host.py`,
  `uri_operational_intelligence/brain_health.py` and `scripts/run_uri_integrated_worker.py`. It adds the catalog,
  the UI file and the tests (diff stat: `evidence/gates/diff_stat_vs_canonical_cd4a7963.txt`). Integrating needs its
  own review on this merged candidate.

### Live round trip on the merged candidate: qc-6
Source and runtime `b653c154`; the runtime was verified byte for byte. The real app ran through production `main()`,
the Brain was started by the production host under a FREE lease, no override was used, and input was automated.

- **Checks:** 22/22 PASS.
- **Switches:**
  - Standard -> Long context: 30.1 s (FITS +1,648 MiB).
  - Long context -> Standard: 37.2 s (AT_RISK -325.5 MiB).
  - The old server stopped in 3.5 to 3.6 s.
- **Continuity:** "4817" was recalled after both switches, and the worker processes stayed the same.
- **After the run:** lease FREE, Brain config unchanged.
- **Decode speed (tok/s):**

| Point in the run | Decode tok/s |
|---|---|
| Standard at start | 40.6 |
| Long context | 99.8 |
| Standard after switch | 149.2 |

  The slow start is the known effect of opening the UI window after the Brain has loaded (P-GOV-1), not a switch
  defect. The runner is "UI first", but the Flutter integration build took longer than the Brain load: the app window
  appeared at 07:57:46, after READY. The Brain then moved 0.77 GB to system memory, as in qc-1. The switch round trip
  brought Standard back to 149 tok/s.

### Gates at `76088dad` (merged candidate)
- pytest `tests/oi` + `tests/ws`: 778 passed, 23 skipped. This includes the canonical tests that came in with the
  merge.
- flutter test: 779 passed.
- flutter analyze: 4 info messages, all in files this milestone did not touch.
- Windows release build OK.
- `ws_frozen_check` ok.
- Frozen UI V2 files against `7893aaed`: +98/0 and +37/0 lines.

All of these have `.head` files.

---

## Review R4 (2026-10-18): ACCEPT WITH FINDINGS (2 LOW, 3 INFO); repairs

The review report is in `review/R4_report.md`. The code repair and the gates are both at `5bcf1f24`.

| Finding | Change |
|---|---|
| R4-01 LOW | `_brain_reconfigure` now checks the host's reported profile. When the host runs a profile the worker does not follow (a research `--profile` launch such as P1, where the worker stays on the frozen config), choosing Standard sends a reconfigure; it no longer answers `already_active`. If the host reports Standard, the answer is `already_active`. Unit test: `test_the_host_report_decides_whether_a_target_already_runs`. There is no live run for this: it only affects a research launch with `--profile`. |
| R4-02 LOW | The IC-1 wording is corrected (below). |
| R4-03 INFO | The main session's R3 logs (`HEAD=d65b122c`) moved to `evidence/gates/history_r3_d65b122c/`. The new gate logs start with a `HEAD=` line. Where a log and its `.head` sidecar disagree, the `.head` file is authoritative. |
| R4-04 INFO | Recorded as QC-F9. |
| R4-05 INFO | Recorded as QC-F10. |

### Existing files changed vs canonical `cd4a7963` (R4-02)
The three IC-1 files: `scripts/ws_brain_host.py`, `uri_operational_intelligence/brain_health.py` and
`scripts/run_uri_integrated_worker.py`. All six existing files changed:

| File | IC-1 file |
|---|---|
| `scripts/ws_brain_host.py` | yes |
| `uri_operational_intelligence/brain_health.py` | yes |
| `scripts/run_uri_integrated_worker.py` | yes |
| `uri_operational_intelligence/worker_bridge.py` | no |
| `uri_ui/lib/living/integration/oi_conversation.dart` | no |
| `uri_ui/lib/living/widgets/living_composer.dart` | no |

The new files are `uri_operational_intelligence/brain_quick_controls.py`,
`uri_ui/lib/living/integration/brain_quick_controls.dart` and the two test files.

### Open findings added
- **QC-F9:** the host's `selection_error: PROFILE_NOT_SELECTABLE` (R9-01) appears only in the host report. Neither
  the worker's `controls` nor the UI shows it, so the user sees only the generic not-ready / foreign state.
- **QC-F10:** a host-side refusal of a reconfigure target (`REFUSED_PROFILE_*`) is recorded in `last_request`, not
  in `profile_switch`, and has no plain-words mapping, so the UI would show no notice. Today this cannot happen: the
  worker applies the same `QC.switch_target` first. It matters only if the worker and the host ever diverge.

### Gates at `5bcf1f24` (final code; `.head` files plus an in-log `HEAD=` line)
- pytest `tests/oi` + `tests/ws`: 779 passed, 23 skipped.
- Quick Controls flutter test file: 18 passed.
- Full flutter test: 779 passed.
- flutter analyze: 4 info messages, all in files this milestone did not touch.
- `ws_frozen_check` ok.

The R4 changes are Python only. The Dart code is the same as at `76088dad`, and the release build from that commit
stands (`uibuild-release.head`).
