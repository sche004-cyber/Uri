# FINAL QC - pre-push acceptance gate, Brain Quick Controls canonical integration stage 1

Reviewer: independent read-only subagent (not owner approval). Date 2026-10-18.
Target: push `5f77acb8` as `integration/git-sync-20261008` on `uri-repo` (fast-forward from `cd4a7963`).

## Verdict: ACCEPT WITH FINDINGS (0 HIGH, 0 MEDIUM, 4 LOW, 4 INFO)

None of the findings blocks the push. All LOW findings are about how precisely the receipt describes the evidence. The code is correct.

## Acceptance criteria (set before review)

| # | Criterion | Result |
|---|---|---|
| AC1 | HEAD = 5f77acb8, clean tree; remote = cd4a7963 | MET (ran) |
| AC2 | R2-01 / R2-02 correct; no stale `stop_requested` path; tests discriminating | MET (read + ran) |
| AC3 | 6427b681..5f77acb8 docs only; no secrets, Ember assets, reference art or docs/companions | MET (ran); INFO F-5 on personal paths |
| AC4 | Receipt numbers and claims match the evidence | PARTLY: F-1..F-4 |
| AC5 | FF-safe: cd4a7963 is an ancestor; no Ember commits; no history rewrite | MET (ran) |
| AC6 | Requested pytest passes | MET (ran): 40 passed in 9.55 s |

## Ran
- `rev-parse HEAD` = 5f77acb81d58...; `status --porcelain` empty (also empty after all checks).
- `ls-remote uri-repo refs/heads/integration/git-sync-20261008` = cd4a7963c316...
- `merge-base --is-ancestor cd4a7963 5f77acb8`: true. d6a83131 and 8a1438ec are NOT ancestors of 5f77acb8 and are not in `cd4a7963..5f77acb8`. The only merge in the range is 0226e7ee, which merges canonical cd4a7963 INTO the candidate, so it is forward-only and rewrites nothing.
- `diff --name-only 6427b681 5f77acb8`: 46 files, all under `docs/integration/qc_ember_20261018/`. Nothing under docs/companions in the full range. The only non-doc files in the full range are QC code and tests (11 files). No image assets outside evidence screenshots.
- Secret regex scan (sk-, ghp_, xox, AKIA, private key, api_key=, bearer, password=, AIza) over all non-PNG additions in `cd4a7963..5f77acb8`: no matches. Every "secret"/"token" hit is the "secret number 4817" test prompt or a `context_tokens` field.
- pytest (requested command, in the worktree): **40 passed**.
- Discrimination check, in scratch and then deleted: `git archive 01e06d70` (minus docs and uri_ui) plus the 6427b681 test file. Both new tests FAIL on the pre-fix sources. The lease test fails with `'WAITING_FOR_LEASE' == 'STOPPED'`, and the retry test with `5 == 4` sleeps. Both pass at HEAD.
- JSON parsing of evidence: integ-qc-2, integ-qc-3, integ-qc-4, integ-uiv2-2 and integ-vision-1, plus qc-1..qc-6 in the milestone worktree. Also the raw run directory `D:/uri-dev/uri-integ-live/qc/live/integ-qc-3/` (samples.json, observations.json, 09-confirm-standard.png, logs).
- The driver of integ-qc-3 differs from the driver of integ-qc-4 (diff run).

## Read
- `scripts/ws_brain_host.py` at HEAD: take_request, wait_for_gpu, wait_or_request, acquire_lease, start_brain/_finish_switch, _start_brain load loop, reconfigure, run loop. Also the run-loop restart branch at cd4a7963.
- `uri_operational_intelligence/worker_bridge.py`: `_restart_pending`, `_brain_reconfigure`, and the 01e06d70 diff.
- Receipt, the IC1 and IC1-R2 reports, gate logs, and BRAIN_QC_REPORT QC-F4.

## Check 1 - R2-01 / R2-02

- **R2-01 is correct.** The bug: `reconfigure` on a stopped Brain calls `acquire_lease()`. A stop consumed in its `wait_or_request` returns False without setting `stop_during_wait`. `_finish_switch` then saw state WAITING_FOR_LEASE and kept that as the result. With `self.stop_requested` added, the result becomes STOPPED.
- **No path leaves a stale `stop_requested` that mislabels a later switch.**
  - `stop_requested` is set only in `take_request`, when a `stop` is ACCEPTED.
  - It is cleared in the same run-loop iteration in which it was consumed (`if action == "stop" or self.stop_requested`).
  - Inside that iteration, no new switch can start after the stop is consumed:
    - `wait_for_gpu` returns False at once.
    - `acquire_lease` returns False at once.
    - The load loop returns STOPPED_DURING_LOAD.
    - `reconfigure` and `start_brain` end after that.
  - A stop consumed during the initial pre-loop `start_brain` is cleared on the first loop iteration, before any `take_request`.
  - The rewrite also only applies to WAITING_FOR_GPU, WAITING_FOR_LEASE and RELEASE_WAIT. A READY or FAILED result is never turned into STOPPED.
- **R2-02 is correct.** `attempt == 4` returns before the sleep, so the worst case is 2.0 s of sleep in total (0.2+0.4+0.6+0.8).
- **Tests are meaningful.** Both fail on 01e06d70 and pass at HEAD (ran).

## Check 4 - fast-forward
cd4a7963 is an ancestor of 5f77acb8, and neither Ember commit is in the range (see Ran).

## Findings

**F-1 LOW - Receipt section 4 baseline table: the qc-5 "Switch to Long / back (UI s)" values are host seconds, not UI seconds.**
- The receipt gives `30.8 / 38.2`. In qc-5 `summary.json` those are `switches[].seconds`, which is the host measure.
- The qc-5 `switch_ui_timelines` values are 31.4 / 40.1.
- The integ-qc-4 column is correct: UI 32.1 / 38.8, host 31.0 / 36.9.
- With like-for-like numbers, the integrated UI time back to Standard is faster (38.8 vs 40.1), so the no-regression conclusion still holds.
- Fix: change the qc-5 cell to `31.4 / 40.1 (host 30.8 / 38.2)`.

**F-2 LOW - Receipt section 4: the qc-5 "Fit before" cell is a range taken from other runs.**
- `AT_RISK (-294.5..-336.6 MiB)` is the range across qc-1..qc-4 (-294.5 in qc-1, -336.6 in qc-4).
- qc-5 itself is FITS +1,678.5 / AT_RISK -299.3. qc-6 is -325.5.
- The table header names "(qc-5, qc-6)" but there is only a qc-5 column.
- Fix: give the qc-5 values (`FITS +1,678.5 / AT_RISK -299.3`). Either label the range "qc-1..qc-6: -294.5..-336.6" or drop qc-6 from the header.

**F-3 LOW - INTEG-F1 is understated as "not reproduced" without disclosing that the harness changed. Part of its description is unevidenced.**
- (a) integ-qc-2 and integ-qc-3 ran driver sha `c2f23a11` (= the milestone `qc_driver.dart`). integ-qc-4 ran `ebeb62dd` (= `evidence/qc_driver_integration.dart`). After the Standard Switch tap, the new driver adds a `go_found` probe and 10 x `settle(500)` (about 5 s of frame pumping) before `waitActive`. So "not reproduced in integ-qc-4" was observed on a different harness. The extra pumping could plausibly hide a tap or frame race.
- (b) Verified from raw files that are not committed: the Standard confirm dialog was shown (`D:/uri-dev/uri-integ-live/qc/live/integ-qc-3/09-confirm-standard.png`). The host never received a second request: every one of the 105 samples shows only `profile_switch` 9f97223e (the Long switch), and `host_state_sequence` has no second switch. The worker's final controls show `switch.last` = the Long switch and no pending switch.
- (c) Not evidenced: "no notice appeared". The old driver never recorded `profileNotice` for the Standard switch, and no screenshot after the tap exists. Also not evidenced: "a user can tap again".
- The observed rate is 1 failure in 9 live QC runs (qc-1..qc-6, integ-qc-2/3/4). The cause is UNKNOWN.
- Dart is unchanged between integ-qc-2 (PASS) and integ-qc-3 (FAIL). 01e06d70 changed worker_bridge (IC1-01) and the host. The host shows no request, so a host-side cause is unlikely. A worker-side BridgeRefused, or the UI never sending, cannot be told apart from the committed evidence.
- Fix:
  - State in the receipt that integ-qc-4 used the instrumented driver (sha ebeb62dd, +5 s settle) and that the cause is UNKNOWN.
  - Commit or cite the integ-qc-3 `09-confirm-standard.png` and `samples.json`.
  - Change "no notice appeared" to "not recorded".
  - Mark "a user can tap again" as unverified.
  - Keep INTEG-F1 OPEN, not merely "recorded", for a follow-up live run with the original driver.

**F-4 LOW - Two gate claims in the receipt have no committed evidence.**
- (a) "test_frozen_core: identical set fails on canonical cd4a7963". The committed log covers only HEAD=4e827178 (3 failed, 5 passed). BRAIN_QC_REPORT QC-F4 says the base already lacks the runtime-profiles files, which supports the claim but does not prove it. I did not run the test on cd4a7963. This is UNVERIFIED, and it does not change the verdict, because the guard is a governance gap recorded as QC-F4.
- (b) "Secret scan no matches" has no committed log. I re-ran an independent scan over the whole `cd4a7963..5f77acb8` range and found no matches, so this claim is now independently confirmed.
- Fix: commit the cd4a7963 frozen-core log, or reword the claim to "reported by ...".

**F-5 INFO - Personal local paths in the added evidence.**
- Examples: `C:\Users\cheta\flutter\bin\flutter.bat` and `C:\Users\cheta\AppData\Local\Temp\claude\brain_qc...`.
- These are not secrets, and the same practice already exists in 996 canonical doc files.

**F-6 INFO - The receipt's section 4 header ("real app, production main()") omits the input method.**
- native-execution.json states the runs are integration_test Debug builds with synthesized taps and TestTextInput, and that the physical keyboard and mouse are not qualified.
- The release build was built but not exercised live.
- Suggest adding one line to the header.

**F-7 INFO (pre-existing, out of scope) - A stop during the restart branch's lease wait makes the host exit.**
- In the run loop, `if self.lease is None and not self.acquire_lease(): break`, so the host exits instead of stopping. The run loop has this identical branch at cd4a7963.

**F-8 INFO - The R2-01 test checks only the switch record.**
- It does not check that the run loop then ends in STOPPED / STOP_REQUESTED and releases the lease. Acceptable.

## Checked and correct (receipt)
- Decode tok/s: qc-5 121.2 / 98.2 / 148.3 and integ-qc-4 122.8 / 98.8 / 150.0.
- Integ fit: FITS +1,669.9 / AT_RISK -316.4.
- Dedicated / non-local MiB: 15,008 / 1,731 and 13,896 / 562 (both runs).
- Continuity "4817", same workers and session, lease FREE, config digest unchanged.
- integ-qc-2 PASS 22/22 at 4e827178; integ-qc-4 PASS 22/22 at 6427b681.
- integ-qc-3 FAIL on 1 check at 01e06d70, about 7 min 4 s from 10:44:22 to 10:51:26.
- integ-uiv2-2: 68 PASS, 0 failures, 0 flutter errors, at 4e827178.
- integ-vision-1: Standard "Red" in 2.14 s; Long HTTP 500 "image input is not supported"; config sha unchanged; lease FREE.
- pytest: 784 passed / 23 skipped at 6427b681 (also 779 at 4e827178 and 782 at 01e06d70).
- ws_frozen_check `unapproved_protected_changes: []` x3.
- Flutter: analyze 4 info and 0 errors; 779 passed; release rc 0.
- Dart diff 4e827178..6427b681 is empty.
- IC1 verdict AwF (1 MEDIUM, 5 LOW, 2 INFO) with 744 canonical tests; IC1-R2 AwF (1 LOW, 3 INFO).
- Rollback statement consistent: cd4a7963 is on the remote and is an ancestor.

## Unverified
- test_frozen_core on cd4a7963 (F-4a). Does not affect the verdict.
- Worker-side root cause of INTEG-F1 (F-3). Does not block: it is a UI-level intermittent issue in a qualified milestone, it is truthfully not hidden, and the host is unaffected. It should be kept open.
