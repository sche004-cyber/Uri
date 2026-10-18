# REVIEW QCC-R2: BRAIN-QC-CLOSURE-20261018 (final round)

Nonce: **QCC-R2-d61f93**

- Reviewer: an independent read-only subagent. I did not write this work and did not take part in QCC-R1. Verification class: subagent review of code, gates and recorded live evidence. I ran no live checks myself.
- Target: detached worktree `D:\uri-dev\qcc-r2-review`. `git rev-parse HEAD` = `0988176d4cbf84def6bee4d1ed014d247aca3b53` (verified).
- Code under test: `fcc1f183` (merge of `18831515` with `feaabe3f`). `git diff --name-only fcc1f183 0988176d` touches only `docs/` (verified): `0988176d` adds evidence, report and R1 review only.
- `git ls-remote uri-repo integration/git-sync-20261008` returned `feaabe3f683b192817a16ac10ae826d7cb8d03f0`, so canonical is unchanged. `feaabe3f` is an ancestor of `fcc1f183` (verified with `merge-base --is-ancestor`).
- Scope reviewed: the whole `git diff feaabe3f 0988176d`, which is 121 files. Code: `brain_quick_controls.py`, `worker_bridge.py`, `run_uri_integrated_worker.py`, `brain_quick_controls.dart`, `oi_conversation.dart`. Also the tests, the harness, all evidence and the report. `ws_brain_host.py`, `runtime_profiles.py`, `runtime_profile_selection.py` and `runtime_v1.py` are not in the diff (`git diff --stat`: empty).

## Worktree state

- Before: `git status --porcelain --ignored` was empty.
- After pytest: still empty.
- After `flutter test`: no tracked change and HEAD unchanged. New **ignored** entries only:
  - `uri_ui/.dart_tool/`
  - `uri_ui/.flutter-plugins-dependencies`
  - `uri_ui/android/app/src/main/java/`
  - `uri_ui/android/local.properties`
  - `uri_ui/build/`
  - `uri_ui/windows/flutter/ephemeral/`
- Nothing was modified, added, committed, stashed or checked out in any worktree, and nothing was pushed. I started no GPU process, Brain host, worker, server, app or harness. I did not touch any lease, `D:\uri-dev\uri-integ-rt-e` or port 18300. The only file written is this review.

## Tests I ran (read-only, COMPLETED_WITH_RESULT)

- `runtime-e\.venv python -B -m pytest -c scripts/phase2d_pytest.ini --rootdir=. -q -p no:cacheprovider tests/oi/test_brain_quick_controls.py tests/oi/test_runtime_profile_selection.py tests/oi/test_brain_qc_integration.py` gave **84 passed** in 17.47 s, rc 0.
- `flutter test test/living/brain_quick_controls_test.dart` gave **+27 All tests passed**. That is 2 more than QCC-R1's 25: the new R1-06 lockVision case and the R1-05 selection-error case are both present.

## Acceptance criteria (defined before review)

These are the owner closure criteria, each checked against primary evidence.

| # | Criterion | Result | Evidence I inspected |
|---|---|---|---|
| A1 | Frozen fallback functional; default unchanged | **MET** | qcc-1 `session.json`: `brain_config_sha256_before == after` (`112c0595…`), `host_final.profile` = `frozen`, lease_after FREE. `host_state_sequence` starts and ends `READY frozen`. The runtime/host/selection files are not in the diff. `CATALOG[0]` = frozen. |
| A2 | P2 and P3 operate through the Windows UI | **MET** (automation input; L-1 disclosed) | qcc-1 `native-execution.json`: production `main()`, flutter integration_test on Windows, `source_head` fcc1f183, `source_status_before/after` "", `closure_steps: true`, exit 0. Switches from `summary.json`: frozen→P2 READY 33.0 s, P2→frozen 38.4 s, frozen→P3 READY 35.2 s, P3→frozen 39.2 s. Checks `QC-chips-long`, `QC-chips-p3`, `QC-continuity-long/p3` PASS. |
| A3 | P1 not selectable through normal controls | **MET** | Catalog `long-vision` `qualified: False`. `switch_target` raises `PROFILE_NOT_QUALIFIED`. `SELECTABLE` = frozen/P2/P3 only. Live `QC-unqualified-listed-disabled`, `QC-unqualified-not-requested`, `QC-unqualified-listed-at-64k` PASS. No P1 id appears in the switch list. |
| A4 | UI qualification and active-profile information accurate; host, worker and selection never disagree silently | **MET** (one LOW, QCC-R2-04) | `mismatch()` covers four cases: agree, host≠worker, PROFILE_NOT_SELECTABLE, HOST_SELECTION_ERROR (agreeing profiles plus a write error) and unreadable; it is suppressed only while a switch is pending. Unit and widget tests pass. Live `QC-no-mismatch-p3` PASS, and final controls show `mismatch: null` with host == configured == frozen. The UI reads `qualified` from the QC catalog only (grep: no `host_profile` use in `uri_ui/lib`). |
| A5 | Conversation continuity and worker stability | **MET** | "4817" was recalled on P2, Standard, P3 and Standard-after-P3: 4 switches, 4 recalls, all `route: answer`. `QC-same-worker-and-session`: the same session `e4bbdcb4…` and `runtime_identical: true`. `worker_processes` = the same 2 PIDs (4932, 7560) throughout. |
| A6 | Vision available throughout active Assist sessions | **MET at implemented + unit/widget-tested level; not live through the worker** (disclosed as L-2; wording finding QCC-R2-01) | `assist_state_of`: `state != "OFF"` (ACTIVE or PAUSED). `_brain_reconfigure` refuses `ASSIST_NEEDS_VISION` and `ASSIST_ASK_IN_PROGRESS`. `lockVision` disables vision-off choices. A real `AssistCommands` test covers grant, pause and revoke. Live `QC-assist-vision-on-p3` shows that the production Assist classes get a correct vision answer from the P3 Brain: `host_profile.id` = `c32k-visgpu-mtpoff`, method vision, COMPLETE, 1.54 s, the 401 error and both toggles named. It used a separate session-process instance with a FakeAdapter and `vision_qualified=True`. |
| A7 | Truthful loading, switching, readiness and failure states | **MET** | `QC-header-truthful-long/standard/p3`: `rows_ready_while_pending: 0`. `QC-truthful-switch-*`: no early active. `QC-turn-refused-during-switch` gives `BRAIN_RESTARTING` with the user-facing "Not sent…" text. The confirm dialog text is accurate. |
| A8 | No material regression (performance, memory, safety, functionality) | **MET** | pytest tests/oi + tests/ws: 793 passed, 23 skipped, rc 0. Full flutter test: +788 ~5, rc 0. Release build rc 0. `frozen_check.json`: ok, `unapproved_drift: []`. UI V2 frozen files vs `7893aaed`: +137/-0, re-computed by me (`git diff --stat 7893aaed fcc1f183`, no `-` lines). qcc-uiv2 passed 68/68. Decode per profile matches its class (below). Standard code is unchanged. |
| A9 | Canonical unchanged until approved | **MET** | ls-remote = feaabe3f. |
| A10 | No claim of Windows live verification, qualification or deployment without evidence | **MET** (LOW wording, QCC-R2-04) | Every live claim in sections 4-5 traces to the qcc-1/qcc-uiv2 files. Report line 7: nothing pushed, integrated, frozen or deployed. |
| A11 | Distinguish implemented / tested / independently accepted / integrated / frozen-deployed | **MET** (LOW, QCC-R2-03/04) | Sections 2/3/4/7 separate code, gates, live and review. C9 is left to this round. Section 9 is unfilled (expected). |
| A12 | Every QCC-R1 repair verified in 18831515 | **MET** (R1-03b partial, LOW) | See the R1 repair table. |
| A13 | Report sections 4-6 numbers recomputed from raw files | **MET** except one presentation issue (QCC-R2-02) | See the recompute section below. |

## Verdict

**ACCEPT WITH FINDINGS**: no HIGH or MEDIUM findings; 4 LOW. All owner closure criteria are met at the verification level the report claims. The report's section 1 table is true, with the wording caveats in QCC-R2-01 and QCC-R2-04.

## QCC-R1 repair verification (commit 18831515)

| R1 finding | Repair verified | Status |
|---|---|---|
| R1-01 MEDIUM: vacuous closure steps | `go.sh:16` `[ "$K" = closure ] && export URI_QC_CLOSURE=1` runs before `run_qc_ui.py`. The export comes after `qc_session.py` forks, which does not matter because only the driver reads the variable (grep: only `qc_driver.dart:334`). `run_qc_ui.py:65` records `closure_steps`. `summarize.py:79-83` requires all 10 IDs when `closure_steps` is true, and a missing ID counts as a failure. qcc-1: `closure_steps: true`, `missing_closure_checks: []`, all 10 IDs PASS in `observations.json`. Residual: the requirement depends on the recorded flag, so a reader must check `closure_steps: true`. It is true for qcc-1. | RESOLVED |
| R1-02 LOW: PAUSED grant | `worker_bridge.assist_state_of` uses `state != "OFF"`. A test with a real `AssistCommands` covers grant, pause and revoke. | RESOLVED |
| R1-03 LOW: lock text | Product strings are reworded in `brain_quick_controls.dart:179` and `oi_conversation.dart:52`, and the new text is true whether or not Assist vision is qualified. **03b (harness/report "application path") is not repaired**: see QCC-R2-01. | PARTIAL |
| R1-04 LOW: no reverse guard | `run_uri_integrated_worker.py:284-286` raises `TurnError("BRAIN_RESTARTING")` for `assist_ask`/`assist_grant` while `oi.switch_pending()`. The error is caught by the loop's `except (... TurnError)` at `:356`. `switch_pending` is limited to profile switches; a plain restart is not covered, and the test asserts that by design. | RESOLVED (scope: profile switch only) |
| R1-05 LOW: mismatch wording | `HOST_SELECTION_ERROR` branch and the label-based unreadable branch (`brain_quick_controls.py:147-157`). The Dart notice has a matching sentence. Python and Dart tests exist. | RESOLVED |
| R1-06 LOW: test gaps | A real `AssistCommands` test, `switch_pending` tests, Dart lockVision (active null / vision off) and selection-error tests. The dispatch-guard test is still a source-text check (`test_worker_wires_assist_state_after_assist_is_created`): see QCC-R2-03. | RESOLVED (residual noted) |
| R1-07 LOW: weak Assist check, dev imports | `qc_session.py` imports only from `RT` (runtime6, verified 361 files byte for byte against fcc1f183). The toggle check now rejects answers that name an off toggle unless the answer also contains " off". The heuristic is still loose ("Dark theme on, Gmail off" would pass). The live answer named only Voice input and Gmail drafts, so its pass did not depend on that loophole. | RESOLVED |

## Recompute of report sections 4-6 (from raw files)

**Section 4, qcc-1** (`observations.json`, `summary.json`, `session.json`, `native-execution.json`, `assist-result.json`):
- 32 checks, all PASS; `failed_checks: []`; classification COMPLETED_WITH_RESULT. Runtime: `runtime_verified.ok` true (361 files, 0 mismatched); `receipt.candidate_head` fcc1f183; `native.source_head` fcc1f183. Matches.
- Switch UI seconds: 34.948, 54.212, 36.817; the 4th has no UI timer, host 39.2 s. Matches 34.9 / 54.2 / 36.8 / (host 39.2).
- Decode on the perf turns: standard-start 110.69, long 96.24, standard-after-switch 148.89, p3 99.77. Matches.
- Thinking: Off gave FAST and On gave NORMAL, with no host state change between them. `QC-turn-refused-during-switch` gives BRAIN_RESTARTING. Lease FREE; digest unchanged. Matches.
- Assist: `host_profile.id` c32k-visgpu-mtpoff, 1.54 s, the 401 error, Voice input and Gmail drafts. Matches.

**Section 4, qcc-uiv2:**
- `observations-main.json`: 68 checks, all PASS; final record `failures: []`, `flutter_errors: 0`.
- `native-execution.json`: exit_code 0, source_head fcc1f183, `source_status_after` "".
- `session.json`: result COMPLETED, runtime_verified ok (361), lease FREE, digest unchanged, host on frozen.
- The report's explanation of `summary.json` "INCOMPLETE" is **correct**. `ui-finished.json` is `{"failures":[],"mode":"main"}`, with no `by` key. `summarize.py:84` requires `finished.get("by") == "driver"`. The runner writes `by: runner` only when the file is missing (`run_qc_ui.py:81-82`), so the UI V2 driver itself wrote this file. "verdict FAIL" therefore follows only from `complete == False`; `failed_checks` is empty. `chain-live.log` shows the same values.

**Section 5** (`summary.json` profiles/switches, `samples.json` host_mem):

| Profile | Request MiB | Fit margin before the switch | Dedicated max | Non-local max | Calibration tok/s |
|---|---|---|---|---|---|
| Standard | 15626 | -320.8 (P2→Std), -327.6 (P3→Std); report says -321 / -328 | 15008.2 | 1731.1 | 146.7 / 150.0 / 150.5 |
| P2 | 13658 | +1664.9 | 13895.5 | 561.8 | 94.6 |
| P3 | 14360 | +943.2 | 14589.1 | 499.7 | 98.4 |

- Host commit: limit 52148 (constant); free min 17803, max 39659. Matches.
- llama-server private bytes max 20430.4 MiB, in the same sample as working set 3650.5 (11:26:05, READY frozen). Matches. The report correctly labels the commit-charge hypothesis as unverified.

**Section 6:**
- The comparison is evidence-based and draws on the same files. **No default change**: the catalog order, `SELECTABLE`, the frozen config and the host are untouched, and the recommendation is explicitly left to the owner.
- Decode "149-150" for Standard omits the measured 110.7 on the first list task. See QCC-R2-02.

## Findings

### QCC-R2-01: LOW: "application path" wording kept for the live Assist check (R1-03b not repaired)
- Files:
  - `docs/operational_intelligence/brain_quick_controls/BRAIN_QC_CLOSURE_REPORT.md:18` (C6 "Live: only the application path")
  - `BRAIN_QC_CLOSURE_REPORT.md:147` (L-2 "used the application path with stand-ins")
  - `evidence/harness/qc_session.py:78` (docstring "(application path)")
  - `evidence/harness/qc_driver.dart:367` (comment)
- Evidence: the live Assist step builds its own `AssistCommands` in the session process, with a FakeAdapter and `vision_qualified=True`. It does not go through the worker, the worker's Assist guard, `vision_locked`, or the UI lock. Report section 4 (lines 93-97) and the second half of L-2 describe this correctly, but C6 and the first half of L-2 still say "application path", which QCC-R1-03b asked to change.
- Effect: wording only. The C6 result is already qualified as "MET in code and tests", so the verdict is unaffected.
- Repair: replace "application path" with "production Assist classes in the session process (not the worker path)" in all four places.

### QCC-R2-02: LOW: section 6 Standard decode "149-150" omits a measured 110.7 tok/s list task
- File: `BRAIN_QC_CLOSURE_REPORT.md:122`.
- Evidence: qcc-1 has two Standard list-task perf turns, `perf-standard-start` at 110.69 and `perf-standard-after-switch` at 148.89. Calibration was 146.7-150.5. The section 4 table shows 110.7, but the comparison table that the default recommendation rests on shows only the high range.
- Effect: the recommendation does not change, because Standard is still the fastest.
- Repair: write "149 (110.7 on the first, cold turn; calibration 147-151)", or give the range of measured turns.

### QCC-R2-03: LOW: two gate or test claims lack primary evidence
- Files: `BRAIN_QC_CLOSURE_REPORT.md:62` and `:71`.
- Evidence:
  - (a) "flutter analyze: 4 info messages, all pre-existing" has an empty evidence column, and `evidence/gates/closure_fcc1f183/` contains no analyze log (grep: none).
  - (b) Section 3 lists "the dispatch guard" among the tests added. The only test for the `assist_ask`/`assist_grant` BRAIN_RESTARTING guard is a source-text check (`tests/oi/test_brain_quick_controls.py`, `test_worker_wires_assist_state_after_assist_is_created`); nothing executes the dispatch path.
  - (c) `frozen_check.json` records `tree` but not the HEAD. It is bound to fcc1f183 only through `head.txt` and the timing of the gate session. The "same as the QC baseline" comparison has no baseline file in this folder.
- Effect: none on the verdict; the other gates are fully evidenced.
- Repair: add `flutter_analyze.log` (with HEAD) or mark the row "not recorded". Call (b) "a source check of the dispatch guard". Add HEAD to the frozen-check record, or cite the baseline file.

### QCC-R2-04: LOW: qualification class of P2/P3 is stated loosely, and the host's own report says `qualified: false` for them
- Files: `BRAIN_QC_CLOSURE_REPORT.md:125` ("live-qualified + this closure"); `uri_operational_intelligence/runtime_profiles.py:114,129` (derived profiles carry `"qualified": False`).
- Evidence:
  - The QC catalog docstring (`brain_quick_controls.py:16-17`) says the P2/P3 qualification sources are "subagent-reviewed, not driver-accepted".
  - Meanwhile the host report's `profile` block reports `qualified: false` for P2 and P3: qcc-1 `samples.json` (e.g. the 11:26:28 sample) and `assist-result.json` `host_profile`. The source is the R1 research flag in `runtime_profiles.describe`, which predates this work.
  - The UI never reads the host's flag (grep), so nothing is shown wrongly to the user. Still, a reader of the evidence sees "qualified: false" next to a report that says "live-qualified".
- Effect: no code defect from this closure. It is a documentation and traceability gap.
- Repair: in section 6, state the qualification class ("live UI V2 runs, subagent-reviewed, not driver-accepted"). Add one line explaining that the host report's `qualified` field is the R1 research flag, not the Quick Controls catalog qualification (or record it as a follow-up to align the two).

## Points checked with no finding

- `fcc1f183..0988176d` touches only `docs/`. The diff of the frozen UI V2 file `oi_conversation.dart` against feaabe3f is +2/-0, the two switch arms.
- `switch_target` and host: P3 has no `switchable: False` any more, so the host accepts it. P1 is still refused with `PROFILE_NOT_QUALIFIED`.
- `draftChoices` returns empty unless two switchable profiles at the active ctx/vision differ in MTP, so it never offers P1. Vision and Context choices still resolve to Standard first (catalog order).
- `mismatch` is suppressed only when `switch.pending`, and the UI suppresses it too (`pending ? null`).
- `_assist()` swallows exceptions, so a status read never breaks. The lock reads are sequential, not nested (as in R1).
- The worker's `TurnError` raised in the Assist dispatch is handled by the loop's error writer (`:356`).
- qcc-1 and qcc-uiv2 have the same `ui_binary_sha256` (`6cf7d4f9…`), both Debug, both from source fcc1f183 with a clean status.
- `materialize6.json`: candidate_head fcc1f183, tree `6b5e2ad3…`, which equals `native.source_tree`.
- C10 and line 7: no push or integration is claimed, and ls-remote confirms it.

## Self-review and re-check

- **Criteria first:** A1-A13 were defined before I read the evidence. Each MET has a file reference above.
- **QCC-R2-01 severity:** a first draft rated it MEDIUM because it was a repeat of an R1 finding. I re-checked: section 4 lines 93-97 disclose the stand-ins and the separate instance, and C6 claims MET only "in code and tests". No positive claim depends on the wrong wording, so LOW.
- **"INCOMPLETE" explanation:** re-checked against `summarize.py:84` and `run_qc_ui.py:81-82`. The driver, not the runner, wrote `ui-finished.json`. The report's explanation is accurate, and the report correctly does not claim `summary.json` as a PASS.
- **Fit margins -321 / -328:** re-checked. They are the two `fit_before` values of the switches back to Standard (-320.8, -327.6). They are not the samples' `fit_margin_mib` values (-324.8 / -108.7). The report states "before the switch", so they are correct.
- **QCC-R2-02 recompute:** I recomputed 110.7 from the `perf` record (`decode_tps` 110.6865) to confirm it is a real Standard list-task measurement.
- **A6 vision lock:** I checked whether any live evidence exercised it. None did; it is unit- and widget-only, as L-2 states. This is disclosed, so it does not block.

## Unverified items

- **Physical input and full live paths:** physical keyboard and mouse input are not qualified (L-1). The live UI lock, the worker Assist guard and the live `qc-mismatch` line were not exercised (L-2, L-3). These limit the verification class, not this verdict.
- **Gates:** I did not re-run the full gates (793 pytest / 788 flutter / release build). I verified their logs: HEAD line, totals, rc 0. I ran only the focused allowed tests (84 + 27 PASS).
- **flutter analyze:** I could not verify "4 info messages, pre-existing" because there is no log (QCC-R2-03).
- **Screenshots:** I did not open the PNG screenshots in qcc-1/qcc-uiv2; I judged the checks from the JSON observations.
- **Earlier evidence:** the runtime-profiles evidence that qualifies P2/P3 (`RUNTIME_PROFILES_LIVE_RESULTS.md`) and earlier QC/IC-1 reviews were not re-audited. P2/P3 qualification is taken as recorded at canonical feaabe3f.
- **`frozen_check.json`:** "same as the QC baseline" cannot be verified without the baseline file.
