# URI Phase 2 closure report

Date 2026-10-08. Author: Claude (lead implementer and self-auditor; NOT an independent review). Worktree
`C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`, detached at `e8e3b65`, everything uncommitted. Nothing was
committed, pushed, merged, released, frozen, cut over or activated. No login was performed; no credential file was read.
Evidence root `E:` = `C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\`.

## Verdict

**PHASE 2 TECHNICALLY READY — PHYSICAL/OWNER GATES PENDING** — subject to the regression and review results recorded
in sections H and J (this line is re-confirmed or corrected there; see the correction record at the end).

Not claimed: PHASE 2 ACCEPTED AND QUALIFIED. Human acceptance on the real app, client-profile logins, native
execution inside the worker process (BLOCKED by EXE-1, an owner decision), the physical power-loss campaign, C6 owner
decisions and the C7 cutover remain open (`PHASE2CLOSE_CLOSURE_CHECKLIST.md` section B).

## A. Starting point (verified, not assumed)

* Round-7 accepted candidate `E:phase2ops-candidate-20261008-r6.zip` re-hashed: `9a0be52c...affb50a` (matches).
* Live tree vs its manifest before any closure change: 117 tree files, 116 byte-identical; the one difference is
  `docs/plans/PHASE2OPS_REPORT.md` (the acceptance record appended after the candidate was cut).
* Frozen Phase 1 checkpoint `31a34dcb...efeb98cf7`: hash and byte-identity re-verified by `tests/phase2a/test_frozen_core.py`
  inside every Phase 2 run and by `scripts/phase2close_acceptance.py preflight` (`E:phase2close\acceptance_preflight.json`).
* Recoverable checkpoint before high-risk changes: the round-7 zip itself (immutable, outside the tree).

## B. Acceptance criteria (set before implementation)

1. Each change traces requirement -> implementation -> test (failing on the incoming code where a defect is claimed)
   -> evidence -> review -> status.
2. No frozen Phase 1 file changes; no accepted Phase 2 property weakens; any changed accepted test is disclosed.
3. Every gate rerun on the final tree, sequentially, by one chain that fails loudly (`scripts/phase2close_chain.py`).
4. Physical and owner gates are prepared, never marked passed.
5. Uncertainty that cannot be removed is stated.

## C. Technical closure: findings and repairs

| ID | Finding | Evidence of the defect | Repair | Tests | Status |
|---|---|---|---|---|---|
| LOG-3 (Codex r7, Low) | refusal logger joined every error-body chunk before truncating | negative control on the r6 file: tracemalloc peak 4,209,676 B for a 4 MiB body | bounded `bytearray`, at most `BODY_CAP` = 4096 bytes kept (`refusal_log.py`) | `test_log3_error_body_retention_is_bounded_whatever_the_chunking` (peak < 1 MiB, pass-through intact, split code found, non-bytes body safe) | IMPLEMENTED, TESTED |
| VAL-1 (open since r3) | historical single HTTP 403 on the approval POST, turn left `approval_required` v0 | **Mechanism established.** `paired_coordinator.py:303` stamps `issued_at = int(clock())`; after the `_authority` callback, `client_execution_control.py:77` refuses unless `issued_at == int(clock())`; a second boundary in between -> `TICKET_CLOCK_OR_GENERATION`, re-raised as `ClientControlError(..., 403)` (`paired_coordinator.py:314-316`) before `ClientService.act` bumps the version (`client_service.py:256-261`). Reproduced deterministically with clock injection (no frozen file changed): 403 `{"detail": "TICKET_CLOCK_OR_GENERATION"}`, server turn `approval_required` at the same version = the VAL-1 signature. Control: same injection without the crossing completes. Window measured in-process: 0.000547 s (~0.05 % per approval; larger under load). Other 403 sources reviewed (`TURN_SCOPE`, `SESSION_SCOPE`, `REQUEST_BINDING`, `CLIENT_BINDING`, `SERVER_BINDING`, `PRINCIPAL_BINDING`): their inputs are constant for the worker's requests. **Residual uncertainty:** the 2026-10-07 instance itself cannot be attributed (no refusal code was logged then). *Corrected after review round 1:* the clock check is NOT the only 403 path whose inputs can vary: `prepare` also calls the coordinator's `_authorize` (`paired_coordinator.py:425-440`), which re-reads current grants and qualification and can refuse as `EXECUTION_AUTHORITY_UNAVAILABLE` (also re-raised as 403). Nothing changed grants or qualification during the 2026-10-07 run as far as its evidence shows, but that cannot be proven either. The resend is safe for that case too: the server gates run again and a second refusal ends `failed`. | `ExecutionController._decide`: ONE resend of the same approval, only if the error is `SERVER_REFUSED:HTTP_403` or `...TICKET_CLOCK_OR_GENERATION`, no cancel requested, the record shows no ticket/task, and the server's own status shows `approval_required` at the approved version and session. A second refusal -> `failed` / `APPROVAL_REFUSED_NOT_APPLIED:<code>` (was `uncertain`), released (CAP-1). UI explains it (`sx-approval-not-applied`). | `tests/phase2ops/test_val1_clock_boundary.py` (6): reproduction, control, window, one-crossing absorbed -> `completed`, precondition refusals (version moved, state moved, other session, progress, server down), seam rules (never a third call, never for a denial, other codes, cancel) | IMPLEMENTED, TESTED |
| CAP-1 (new) | a worker-abandoned `approval_required` turn held server capacity: frozen limits are one active turn per (client, session) and four per server (`client_service.py:169-174`), 15 min idle expiry | probe on the incoming code: after a proposal-digest mismatch the same session got `SERVER_REFUSED:TURN_CAPACITY`, and after four abandoned cards a FRESH session was refused too (whole server blocked) | `SupervisedWorkerService.release_turn/release_pending` post the frozen server's own cancel route (version-checked; the server never relabels a dispatched turn) on: digest mismatch (`execution_begin`, `turn_decide`), malformed decide, VAL-1 final refusal, `close`, stdin EOF | `tests/phase2ops/test_capacity_release.py` (7, incl. stale entry refused `TURN_TERMINAL`/`VERSION_CONFLICT` and server-down reported not raised), `test_worker_process.py::test_cap1_close_and_stdin_eof_release_pending_cards_over_real_frames` (REAL processes) | IMPLEMENTED, TESTED |
| ISO-1 (new, security) | the worker's sanitized client profile did not isolate Codex: Codex 0.158.0 resolves the Windows profile itself | live, read-only: `codex login status` with only USERPROFILE/HOME/APPDATA/LOCALAPPDATA pointed at a client profile -> "Logged in using ChatGPT" (the owner's global login); with `CODEX_HOME` = client profile -> "Not logged in". Found because the closure's own `qualify` step first wrote a NATIVE_QUALIFIED record under the owner's login; that record was VOIDED (moved to `VOIDED_qualification\`, correction in the campaign file), not deleted. | `qualification.client_cli_homes(root)` -> `CODEX_HOME=<client_root>/home/.codex`; the supervised worker sets it at start; `worker-instance.json` records `cli_homes_pinned`; `qualify` uses the same pins | `tests/phase2close/test_iso1_cli_home.py` (3, incl. LIVE leak-and-pin observation and a REAL worker process) | IMPLEMENTED, TESTED |
| EXE-1 (new) | native execution inside the worker process cannot start Codex: the sanitized PATH (venv, System32, git) makes `codex.CMD` fail with `"node" is not recognized`; real worker `harness_discover` -> `NOT_INSTALLED` | observed 2026-10-08 (`claude.CMD --version` works under the same PATH) | NOT repaired: every fix widens what the worker may launch. Options A-D in `PHASE2CLOSE_C7_READINESS.md` section 4 (recommended A: pin `node.exe` in the record) | — | BLOCKED (owner decision) |

Execution / cancellation / recovery / qualification edge cases reviewed beyond these: restart reconciliation of
`queued` records (kept conservative `uncertain`; not changed, no evidence of harm), cancel during the VAL-1 resend
window (resend refused when cancel requested; tested), release of a turn that moved (refused by the server; tested).

## D. Chat and supervised execution (C6 decision 2)

Recommendation, options and the no-decision part: `PHASE2CLOSE_C6_CHAT_INTEGRATION.md`. Recommended option B (Chat
hands an UNSENT draft of the user's own message to the supervised screen); target D; C not before the paired runtime
serves Chat's attachments and model selector. Implemented and tested without the decision: `TaskHandoff`,
`SupervisedExecutionScreen(draft:)`, `SupervisedExecutionEntry.open(context, draft:)` (3 widget tests + 1 VAL-1 display
test). Chat itself is unchanged. Status: AWAITING OWNER DECISION.

## E. Physical acceptance readiness

`PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md` (gates PA-1..PA-12) and `scripts/phase2close_acceptance.py`
(preflight / provision / qualify / record / collect). Verified here: preflight `ready_for_session: true`; provision
created `work\c1\acceptance-20261008-045345` (port 18300 range, opt-in file, harness grant); `qualify` fails closed
without a client-profile login (`persisted: false`). Power loss: `scripts/phase2close_powerloss_harness.py`
(guest/host/verify/simulate) implements `PHASE2A_POWER_LOSS_TEST_PLAN.md`; SIMULATED plumbing 3/3 and the test suite
pass; this PC has no Hyper-V cmdlets, so the campaign needs an owner-provided VM. All PA gates: PENDING (PA-10 BLOCKED).

## F. C7 readiness

`PHASE2CLOSE_C7_READINESS.md`: NOT READY. Gates 1-2 MET (Phase 1), 3 and 9 PARTIAL, 4/5/8 NOT MET, 6/10 not
authorized/requested, 7 procedure only; Phase 2 additions P2-1..P2-8 (incl. EXE-1 and the reconciliation of the
`_V1` development line, which is 62 commits past `e8e3b65`).

## G. UI readiness

`docs/architecture/PHASE2CLOSE_UI_READINESS.md`: what exists on each development line, readiness of each target
experience, a presentation-state contract for the Orb derived only from authoritative state, the interfaces the next
phase can rely on, reusable patterns to extract, dependency order. No screen was redesigned.

## H. Regression (final tree, sequential chain `scripts/phase2close_chain.py`)

Filled from `E:phase2close\run4\chain_summary.json` (see the record appended below). Runs 1-3 were aborted by the
orchestrator (tree edited while running) and are kept with `ABORTED.txt`; they are not evidence.

## I. Development ledger

`docs/plans/URI_DEVELOPMENT_TODO.md` (new; supersedes the per-slice ledgers) and `PHASE2CLOSE_CLOSURE_CHECKLIST.md`.

## J. Independent review

Mandate `E:phase2close_review\MANDATE_round1.md`; result appended below.

## K. Files changed (vs the round-7 candidate) and frozen boundary

Changed: `uri_supervisor_bridge/{refusal_log,execution,worker_service,qualification}.py`,
`scripts/run_uri_supervised_worker.py`, `scripts/phase2d_regression.py` (adds `tests/phase2close`),
`tests/phase2a/test_frozen_core.py` (ALLOWED_NEW closure globs), `tests/phase2ops/{test_refusal_log,test_worker_process}.py`,
`tests/phase2d/{test_worker_service,test_worker_process}.py` (**accepted assertions changed for CAP-1**: the dropped
turn is now `cancelled` instead of `approval_required`, and the same session continues instead of `TURN_CAPACITY`;
both say so inline), `uri_ui/lib/screens/tasks/supervised_execution_screen.dart`,
`uri_ui/test/supervised_execution_screen_test.dart`, `docs/architecture/PHASE2OPS_UI_OPERATIONS.md` (superseding
notes appended), `docs/plans/PHASE2OPS_REPORT.md` (round-7 acceptance record, pre-existing).
New: `uri_ui/lib/services/task_handoff.dart`; `tests/phase2close/{__init__,test_iso1_cli_home,test_powerloss_harness}.py`;
`tests/phase2ops/{test_val1_clock_boundary,test_capacity_release}.py`;
`scripts/phase2close_{chain,acceptance,powerloss_harness,checkpoint}.py`; `docs/plans/PHASE2CLOSE_{REPORT,C6_CHAT_INTEGRATION,C7_READINESS,PHYSICAL_ACCEPTANCE_RUNBOOK,CLOSURE_CHECKLIST}.md`;
`docs/architecture/PHASE2CLOSE_UI_READINESS.md`; `docs/plans/URI_DEVELOPMENT_TODO.md`.
Frozen Phase 1 checkpoint files changed: none. Tracked (Phase 1) files: same modified set as before the closure.
Candidate archive and hashes: appended below.

## Record H: regression results on the final tree (2026-10-08)

Chain `scripts/phase2close_chain.py`, sequential, `E:phase2close\run4\` (+ native rerun `run4b\`). ORCHESTRATOR-PRODUCED.

| Gate | Result | Baseline (round 7) |
|---|---|---|
| Phase 2 (`tests/phase2a..2d, phase2ops, phase2close`) | **439 passed, 2 skipped, 0 failed** (379 s) | 415 / 2 |
| Phase 1 authority | **134 passed** | 134 |
| Phase 1 full (Phase 2 excluded) | **2675 passed, 12 skipped, 11 failed**, failure IDs identical to the round-7 log (`SAME_FAILURE_SET: true`) | 2675 / 12 / 11 |
| Residue | none planted | — |
| Flutter (whole `uri_ui/test`) | **195 passed, 2 skipped** ("All tests passed!") | 191 / 2 |
| Live Dart -> real worker -> real server | **10/10**; server logs present, 0 `CLIENT_REFUSAL` lines | 10/10 |
| Native Codex (in-process composition, owner shell login, NOT the worker process) | lifecycle `completed/SETTLED_VERIFIED`; mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, executor `DEAD` (run4 and run4b) | same |

Correction inside the chain: run4 ended `CHAIN_FAILED` only because the native gate's parser read the report JSON
instead of the native script's summary line (the run's own output, `run4\native_codex_stdout.txt`, shows the passing
outcomes). The parser was repaired and the native gate rerun alone (`run4b`, `ALL_PASS`); `run4\CORRECTION.txt` records
it. The parser change touches only `scripts/phase2close_chain.py`, which no test imports. Runs 1-3: aborted, not evidence.

Candidate cut before this record was appended: `E:phase2close-candidate-20261008.zip` (`8982c9f8...ad7777`), superseded
before review by the `-a` candidate below (same tree plus this record).

## Correction record 1 (after independent review round 1; earlier text kept as history)

Codex CLI 0.158.0 (gpt-6-sol, medium), fresh session `01a118d3-786c-76f0-b934-71d4e8aef50b`, on
`E:phase2close-candidate-20261008-a.zip` (`8fc1d5e8...9e2470`): **PHASE 2 CLOSURE REJECTED**
(`E:phase2close_review\round1\CODEX_REVIEW_round1.md`). A first launch was refused by the CLI before any review
("Not inside a trusted directory"; kept in `round1\launch_attempt1_refused\`). The reviewer confirmed LOG-3, the VAL-1
mechanism and resend safety, CAP-1, ISO-1 placement and the honesty of the changed accepted tests, and found:

| ID | Severity | Finding (reviewer) | Disposition |
|---|---|---|---|
| D1 | High | `qualify` kept inherited provider token variables (`CODEX_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`), so a shell token could satisfy the probe and the login-status check and persist NATIVE_QUALIFIED without a client-profile login | ACCEPTED, REPAIRED: `probe_environment` removes every built-in `auth_env` variable except the CODEX_HOME pin, the never-forward set and any `*_API_KEY/*_TOKEN/*_SECRET/*_PASSWORD`, then pins the client profile; the caller's environment is restored; removed NAMES are recorded. Tests `tests/phase2close/test_acceptance_tooling.py` (2) |
| D2 | High | the power-loss `host` labelled any run `PHYSICAL_VM`, ignored power-command exit codes, could pass iterations with no acknowledged work and did not enforce the NORMAL control | ACCEPTED, REPAIRED: host writes `VM_SERIES` + `SERIES_ALL_PASS/SERIES_FAIL` and the recorded power method; a failed power command stops and fails the series; `NO_ACKED_WORK` fails an iteration; new `assess` requires FULL >= 200 all-pass with guest `synchronous` FULL AND a NORMAL control with >= 1 lost acknowledged step, and its best result is `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION` with `qualified: false`. Tests (assess matrix, failing power command on a REAL local guest, iteration rules, no "qualified"/"PHYSICAL_VM" strings) |
| D3 | Medium | no single green full chain on the final candidate (run4 failed on the parser; only native rerun) | ACCEPTED: full chain rerun on the final tree (record H2 below) |
| K1 | Low, known | SUP-1 suspended orphan window | ACCEPTED as RECORDED, not repaired (Phase 2A containment change needs its own review); a second occurrence was seen in the D2 tests and killed. Widened explanation: the kill can land DURING `CreateProcess(CREATE_SUSPENDED)` (milliseconds for Python), not only between it and `AssignProcessToJobObject` |
| (text) | — | section C's claim that the clock check is the only varying 403 path was overstated (`_authorize` -> `EXECUTION_AUTHORITY_UNAVAILABLE`) | ACCEPTED; section C corrected in place with an "after review round 1" note |

Verdict line at the top: unchanged wording, still subject to the round-2 review.

## Record H2: one green full chain on the final tree (after review round 1; closes D3)

`E:phase2close\run5\chain_summary.json`: **ALL_PASS: true**, every gate in one sequential run, after the D1/D2 repairs
and with no tree edit while it ran.

| Gate | Result |
|---|---|
| Phase 2 | **445 passed, 2 skipped, 0 failed** (439 + D1 2 + D2 4) |
| Phase 1 authority | **134 passed** |
| Phase 1 full | **2675 / 12 / 11**, `SAME_FAILURE_SET: true` vs the round-7 log |
| Residue | none |
| Flutter | **195 passed, 2 skipped** |
| Live Dart bridge | **10/10**, 0 refusal lines |
| Native Codex (in-process, owner shell login) | lifecycle `completed/SETTLED_VERIFIED`; mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, executor `DEAD` |

## Correction record 2 (after independent review round 2; earlier text kept as history)

Codex CLI 0.158.0 (gpt-6-sol, medium), fresh session, on `E:phase2close-candidate-20261008-b.zip` (`3ab0a859...fc121b`):
**PHASE 2 CLOSURE REJECTED** (`E:phase2close_review\round2\CODEX_REVIEW_round2.md`). Dispositions: D1 REPAIRED, D2
REPAIRED as to the physical label, D3 CLOSED by run5, K1 RECORDED/OPEN (Low), VAL-1 text CORRECTED; LOG-3, VAL-1 resend,
CAP-1, ISO-1 and the changed accepted tests CONFIRMED. New:

| ID | Severity | Finding (reviewer, reproduced by probe) | Disposition |
|---|---|---|---|
| D4 | Medium, blocking | `assess` trusted `summary.json` fields one by one: a FULL "SERIES_ALL_PASS" over 200 failed iterations and a zero-iteration NORMAL control claiming one lost step were called "evidence sufficient" | ACCEPTED, REPAIRED: `assess` now takes the two series DIRECTORIES and recomputes everything from the raw host record `acks.jsonl` (`replay_series`: per boot, acknowledged steps vs the next boot's report, `iteration_verdict`, guest and ledger `synchronous`); `iterations.json` and `summary.json` must agree with the replay (boots, verdicts, acked counts, lost counts, passed, requested vs run) or the series is refused; FULL needs >= 200 replayed iterations all PASS; the control needs a replayed loss >= 1. Tests: the reviewer's exact contradictory pair, eleven tampered/weak cases, and a REAL local campaign whose replay matches its own rows. |
| D5 | Low | checklist B4 still named the removed `ALL_ITERATIONS_PASS` | ACCEPTED, REPAIRED: B4 restated in the `assess` terms; runbook steps 4-5 now pass series directories |

## Record H3: green full chain after the round-2 repairs

`E:phase2close\run6\chain_summary.json`: **ALL_PASS: true**, sequential, no code/test edit while it ran.
Phase 2 **448 passed, 2 skipped, 0 failed** (445 + D4 net +3); Phase 1 authority **134**; Phase 1 full **2675 / 12 / 11**
(`SAME_FAILURE_SET: true`); no residue; Flutter **195 / 2**; live Dart bridge **10/10**, 0 refusal lines; native Codex
(in-process, owner shell login) lifecycle `completed/SETTLED_VERIFIED`, mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`,
executor `DEAD`.

## Correction record 3 (after independent review round 3; earlier text kept as history)

Codex CLI 0.158.0 (gpt-6-sol, medium), fresh session, on `E:phase2close-candidate-20261008-c.zip` (`0cfc3175...a8432c`):
**PHASE 2 CLOSURE REJECTED** (`E:phase2close_review\round3\CODEX_REVIEW_round3.md`). D1, D2 (label), D3, D5 closed; K1
recorded; LOG-3, VAL-1 resend, CAP-1, ISO-1 and the changed accepted tests confirmed. Open:

| ID | Severity | Finding (reviewer, reproduced by probe) | Disposition |
|---|---|---|---|
| D4 residual | Medium, blocking | `assess` still ignored `summary.failed/verdict/synchronous`, compared only the LENGTH of each row's `lost`, accepted a raw record missing the final `ready` line or with a wrong `previous_boot`, and accepted `{"simulated": ...}` as a power method | ACCEPTED, REPAIRED: one row builder (`build_row`) and one summary builder (`build_summary`) are now shared by `campaign` and `replay_series`, and `assess_series` requires the recorded `iterations.json` and `summary.json` to EQUAL the rebuild from `acks.jsonl` (only `delay_s`, which only the host knew, and the `finished` stamp come from the record and must be well-formed); `load_raw` enforces raw-record structure (contiguous boots from 1, one report and one ready per boot, report B names `previous_boot` B-1, ready after its report, acks only for a ready boot, a final ready after the last report); a power method must be exactly a `power_off`/`power_on` command pair with no "simulat" text. Tests: every round-3 probe, the round-2 pair, twelve other tampered/weak cases, and a REAL local campaign whose raw record rebuilds its own files exactly. |

## Record H4: green full chain after the round-3 repair

`E:phase2close\run7\chain_summary.json`: **ALL_PASS: true**, sequential. Phase 2 **449 passed, 2 skipped, 0 failed**;
Phase 1 authority **134**; Phase 1 full **2675 / 12 / 11** (`SAME_FAILURE_SET: true`); no residue; Flutter **195 / 2**;
live Dart bridge **10/10**, 0 refusal lines; native Codex (in-process, owner shell login) lifecycle
`completed/SETTLED_VERIFIED`, mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, executor `DEAD`.

## Correction record 4 (after independent review round 4; earlier text kept as history)

Codex CLI 0.158.0 (gpt-6-sol, medium), fresh session, on `E:phase2close-candidate-20261008-d.zip` (`38ca7f81...66043`):
**PHASE 2 CLOSURE REJECTED** (`E:phase2close_review\round4\CODEX_REVIEW_round4.md`). All earlier dispositions held (D1,
D2 label, D3, D5 closed; the round-3 probes repaired; K1 recorded). Open:

| ID | Severity | Finding (reviewer) | Disposition |
|---|---|---|---|
| D4 residual | Medium, blocking | `iteration_verdict` trusted the guest report's own `invariants_ok` flag; a raw report (and matching row) recording corrupt integrity, an orphan attempt, a task still in flight or a relaunch, but claiming `invariants_ok: true`, still passed | ACCEPTED, REPAIRED: `report_invariants_hold` checks every invariant from the report's facts (integrity "ok", `orphan_attempts == []`, `still_in_flight == []`, `relaunched_by_recovery == []`, plus the flag); missing facts fail. Tests: the four reviewer cases plus a missing-fact case, each fails the iteration and the series. |
| D6 | Low | checklist A6-A11 cited run4/"see run5" instead of the final chain | ACCEPTED, REPAIRED: A6-A11 name one final chain (`run8`, record H5) |

## Record H5: final green full chain (after the round-4 repair)

`E:phase2close\run8\chain_summary.json`: **ALL_PASS: true**, sequential. Phase 2 **450 passed, 2 skipped, 0 failed**;
Phase 1 authority **134**; Phase 1 full **2675 / 12 / 11** (`SAME_FAILURE_SET: true`); no residue; Flutter **195 / 2**;
live Dart bridge **10/10**, 0 refusal lines; native Codex (in-process, owner shell login) lifecycle
`completed/SETTLED_VERIFIED`, mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, executor `DEAD`. Checklist A6-A14 now
cite this chain.

## Correction record 5 (after independent review round 5; earlier text kept as history)

Codex CLI 0.158.0 (gpt-6-sol, medium), fresh session, on `E:phase2close-candidate-20261008-e.zip` (`14362501...e32b`):
**PHASE 2 CLOSURE REJECTED** (`E:phase2close_review\round5\CODEX_REVIEW_round5.md`). Every round-1..4 finding closed or
recorded (K1). Open:

| ID | Severity | Finding (reviewer) | Disposition |
|---|---|---|---|
| D7 | Medium, blocking | a FULL series whose summary says `iterations_requested: 0` or `201` (so its own verdict is `SERIES_FAIL`) still assessed sufficient: the rebuild reused the summary's requested count, so the files were self-consistent | ACCEPTED, REPAIRED: a usable series must be COMPLETE (`iterations_requested` == replayed rows == recorded rows) and the FULL series' recorded verdict must be `SERIES_ALL_PASS`. Tests: both reviewer values, plus an incomplete control. |
| method limitation | Low | `echo hello` / `echo world` passed the power-method check | ACCEPTED, NARROWED: the power-off command must match a recognised hypervisor HARD power-off form (Hyper-V `Stop-VM ... -TurnOff`, VirtualBox `controlvm ... poweroff`, VMware `vmrun ... stop ... hard`, libvirt `virsh destroy`); a graceful `Stop-VM` without `-TurnOff` is refused. This cannot prove the command cut THIS VM, so `assess` now also returns `power_method_attestation_required: true` and owner attestation (PA-11) remains the only way to PASS. Tests: arbitrary commands and graceful stop refused; each recognised form accepted. |

Also checked after an escape slip during this repair: all 41 closure-touched files scanned for control characters; none.

## Record H6: final green full chain (after the round-5 repair)

`E:phase2close\run9\chain_summary.json`: **ALL_PASS: true**, sequential. Phase 2 **452 passed, 2 skipped, 0 failed**;
Phase 1 authority **134**; Phase 1 full **2675 / 12 / 11** (`SAME_FAILURE_SET: true`); no residue; Flutter **195 / 2**;
live Dart bridge **10/10**, 0 refusal lines; native Codex (in-process, owner shell login) lifecycle
`completed/SETTLED_VERIFIED`, mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, executor `DEAD`. Checklist A6-A14 cite
this chain.
