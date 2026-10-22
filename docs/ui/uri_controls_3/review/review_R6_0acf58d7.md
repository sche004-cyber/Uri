# URI-CONTROLS-3 - Independent review R6 on 0acf58d7 (integration readiness)

Reviewer: fresh read-only subagent (Lifecycle V3). Did not write this work. No tracked file modified, nothing committed, no build or suite run by me (gates read from the parallel run).

## Verdict: ACCEPT WITH FINDINGS - ready for controlled integration

No blocking finding. One LOW documentation inconsistency (R6-01) and INFO items.

## Acceptance criteria (defined first)

- AC1 Candidate HEAD is exactly 0acf58d7; code outside docs/ identical to R5-reviewed 1741e97e; every docs change listed.
- AC2 9488c0fd is an ancestor of 0acf58d7 and is still the remote canonical tip (push = fast-forward).
- AC3 Stage 8 live evidence (c3-1, c3-1b, c3-main, c3-returning, c3-perf) supports report section 6b: row counts and PASS/FAIL recounted, source_head c49256e2 (code = 1741e97e), source_status_before limited to the live driver, driver hashes correct; c3-1 failure explanation credible and not masking a product defect.
- AC4 Ember follow-up evidence (e-main 68, e-returning 12, e-perf 3) supports receipt 05 (source_head 9488c0fd, clean).
- AC5 No FAILED/NO_OUTPUT run counted as success; earlier failed attempts disclosed.
- AC6 Gates at 0acf58d7 on a clean tree: pytest, flutter test, analyze, build, frozen check.
- AC7 No secrets or personal data in committed evidence.

## Results

### AC1 - MET
- `git rev-parse HEAD` = 0acf58d7b66fbdb4953a904131cf83763caf9f62; `git status --porcelain` empty.
- `git diff 1741e97e 0acf58d7 -- . ':!docs'` empty.
- Commits 1741e97e..0acf58d7: c49256e2 (record), 4ed41910 (live evidence + record), 0acf58d7 (merge, parents 4ed41910 + 9488c0fd).
- Changed docs paths (all additions except two M):
  - A docs/integration/qc_ember_20261018/04_EMBER_V21_CANONICAL_INTEGRATION_RECEIPT.md (from canonical 9488c0fd; identical to 9488c0fd)
  - A docs/integration/qc_ember_20261018/05_EMBER_V21_FOLLOWUP_LIVE_20261022.md
  - A docs/integration/qc_ember_20261018/evidence_followup_20261022/{e-main,e-perf,e-returning}/* (brain-ready, native-execution, observations-*, samples, session, ui-finished; e-main also stop-brain.done.json) - 20 files
  - M docs/ui/uri_controls_3/URI_CONTROLS_3_REPORT.md
  - A docs/ui/uri_controls_3/evidence/live/c3-1/* (7 JSON), c3-1b/* (10 PNG + 7 JSON), c3-main/* (7), c3-perf/* (6), c3-returning/* (6)
  - M docs/ui/uri_controls_3/live_harness/controls3_driver.dart (+3 lines, see AC3)
  - A docs/ui/uri_controls_3/review/review_R5_1741e97e.md (byte-identical to D:/uri-dev/lifecycle/URI-CONTROLS-3/review_R5_1741e97e.md; verdict ACCEPT WITH FINDINGS)

### AC2 - MET
- `git merge-base --is-ancestor 9488c0fd 0acf58d7` -> true.
- `git ls-remote uri-repo refs/heads/integration/git-sync-20261008` -> 9488c0fd50bc5937bb2008dd33c85b14304daeeb. Pushing 0acf58d7 is a fast-forward (as of this check; re-check immediately before push).

### AC3 - MET
- `git diff 1741e97e c49256e2 -- . ':!docs'` empty, so the UI built from c49256e2 is the reviewed code.
- Recount (own script over observations*.json, rows with label "check"):

| Run | Check rows | PASS | FAIL | source_head | status_before | exit | driver_sha256 |
|---|---|---|---|---|---|---|---|
| c3-1 | 30 | 29 | 1 (C3-vision-enter-opens-confirm) | c49256e2 | '' (clean) | 1 | cea44038... = controls3_driver.dart at c49256e2 |
| c3-1b | 30 | 30 | 0 | c49256e2 | `M docs/ui/uri_controls_3/live_harness/controls3_driver.dart` only | 0 | fc42ddbd...a2efeec = sha256 of the driver at 0acf58d7 (verified with `git show 0acf58d7:... \| sha256sum`) |
| c3-main | 68 | 68 | 0 | c49256e2 | driver only | 0 | 884902e2... |
| c3-returning | 12 | 12 | 0 | c49256e2 | driver only | 0 | 884902e2... |
| c3-perf | 3 | 3 | 0 | c49256e2 | driver only | 0 | 884902e2... |

  884902e2... equals sha256 of docs/operational_intelligence/profiles_live/evidence/harness/uiv2_driver.dart at c49256e2, 9488c0fd and 0acf58d7 (UI V2 driver unchanged). ui-finished.json failures lists agree ([] everywhere except c3-1 listing the one failure). c3-perf decode 93.66-97.17 tok/s matches the "93.7-97.2" claim. Spot-checked c3-1b claims against rows: injected start failure -> fallback READY to Standard with honest notice; Long continuity answer 4817 twice; Vision On refused with fit explanation (needs 15.3 GB, 13.5 GB free), Long kept; Assist adapters ADAPTER_UNAVAILABLE, toggle off; restart consistent; 0 Flutter errors. Screenshot 09-assist-on is absent; the driver takes it only inside the grant branch (line 379), consistent with no grant possible.
- c3-1 failure explanation: in c3-1 the keyboard row for qc-vision is `focused: true, focus_ring: false`, and the FAIL row's `texts` show the confirmation dialog did open - only the ring condition failed (`kb && dialog`). The earlier Space row on qc-thinking (before any tap) had ring true. The driver fix adds a single `sendKeyEvent(shiftLeft)` before `requestFocus()`; the check still requires both focus and ring, so it was not weakened. qc_toggle.dart draws the ring from `FocusableActionDetector.onShowFocusHighlight`, which is true only when focused and FocusManager highlight mode is traditional; flutter_test taps are touch-kind pointer events that switch the mode to touch, and a real Tab/arrow key event switches it back before traversal. So a real keyboard user gets the ring; the explanation is credible and does not hide a product defect. Residual (already disclosed): no physical keyboard/mouse/Narrator qualification.

### AC4 - MET
- e-main 68/68, e-returning 12/12, e-perf 3/3 recounted; source_head 9488c0fd, source_status_before and _after empty (clean), exit 0, driver 884902e2. e-perf tps 95.68-98.13, ttft 0.255-0.925 s, brain-ready host.calibration.decode_tps 106.6, idle build_ms_p95 0.363-0.841 ms - all match receipt 05.

### AC5 - MET
- c3-1 is reported as 29/30 with the FAIL named, not as a pass; the PASS claim rests on c3-1b. Report section 6 keeps the 2026-10-21 NO_OUTPUT attempt as "nothing is counted as evidence". 6b states earlier attempts are kept outside git; I confirmed D:/uri-dev/uri-controls-live/live/ holds *-attempt1-gpu-contended and *-attempt2 for all c3-* and e-* labels. Receipt 05 discloses the expired-session (401) attempt as not evidence; the GPU-contended Ember attempt is disclosed in receipt 04 section 3.

### AC6 - MET
gates_0acf58d7 (DONE present): head.txt `HEAD=0acf58d7... dirty=0`; pytest tests/oi tests/ws 807 passed, 23 skipped, rc 0; flutter test 882 passed, 5 skipped, "All tests passed!", rc 0; analyze 5 issues all info, no warning/error, identical set to gates_1741e97e (rc=1 is the info exit code, same baseline as before); release build rc 0 (uri_ui.exe built); ws_frozen_check ok true, unapproved_drift [], unapproved_protected_changes [], rc 0. Matches 1741e97e gate numbers.

### AC7 - MET
grep -i token|password|api_key|bearer|principal_token|pairing_token over all committed evidence JSON: only `context_tokens` and calibration `tokens` count fields. Long strings found are commit/tree/file hashes and UUIDs (session/run ids). PNG names are UI-state names only. Paths include the local Windows user name (R6-03).

## Findings

- **R6-01 LOW (docs consistency).** URI_CONTROLS_3_REPORT.md section 7 "Status (2026-10-21)" still says "ACCEPTED - NOT INTEGRATED. Blocker: ... Stage 8 ... has no result on this code" with next step "run chain_c3.sh", and the section 6 evidence row "Live runs: NOT RUN (BLOCKED)" is undated as current, both contradicting section 6b (PASS, 2026-10-22). Fix: keep both as history but add a dated 2026-10-22 status (Stage 8 PASS on c3-1b/main/returning/perf, R6 verdict, ready for controlled integration) and label the 2026-10-21 row/section as superseded. Not a blocker; can land with or right after integration.
- **R6-02 INFO.** c3-main and e-main contain 68 check rows but 67 unique ids (`J2-ctrl-dashboard` twice). This is the unchanged accepted UI V2 driver (same sha as earlier UI V2 runs), so "68/68" means 68 check rows, all PASS. Worth one note in the report.
- **R6-03 INFO.** Evidence JSONs contain local paths with the Windows user name (`C:\Users\cheta\...`). Not a secret; consistent with existing repo evidence. Relevant only for any public distribution.
- **R6-04 INFO.** c3-1b ran with the driver fix uncommitted in the worktree (disclosed in source_status_before); its hash equals the committed driver at 0acf58d7, so the provenance is intact. Inputs were synthesized (no physical keyboard/mouse/Narrator), disclosed in every run.
- Open from earlier rounds (unchanged code): LOW R3-03, R3-04, R5-01, R5-02; INFO R3-05, R5-03.

## What I ran vs read

Ran (read-only): git rev-parse/status/diff/log/merge-base/ls-remote/show in D:/uri-dev/uri-controls-3; sha256sum of both drivers at the relevant commits; a Python recount of check rows, PASS/FAIL, duplicate ids, native-execution fields and perf/calibration values; grep for secret patterns and user paths; listing of live attempt directories; comparison of analyze info sets vs gates_1741e97e.
Read: report sections 5-7, receipt 05, receipt 04 lines on the open item, the driver keyOn helper and check sites, qc_toggle.dart focus logic, gate logs, frozen_check.json, R5 review verdict.
Not verified: the live runs themselves (I inspected records, not re-ran them); the PNG contents (names only, as instructed); the remote tip can move after this check.
