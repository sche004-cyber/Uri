# Independent review: Phase 2 closure, round 1

Reviewed 2026-10-08. Subject: `phase2close-candidate-20261008-a.zip`. This report is based on my own archive comparisons, source tracing and limited probes. Implementer reports and orchestrator logs are treated as claims. I changed no repository source, test, configuration or documentation file.

## A. Integrity

The subject SHA-256 is `8fc1d5e818dc99bb15511d7e29bb3786678cab85c69f6f8f17249329099e2470`, matching `ROUND1_SUBJECT.txt` and the sidecar. The round-7 zip independently hashes to `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`. The new zip's 175 manifest entries exactly cover its 136 tree files and 39 evidence files; every manifest digest matches. All 136 tree files exist and are byte-identical in the live tree. HEAD is `e8e3b65259c45fc823addc3ef8969425a265bd1b`.

Relative to round 7, the archive has 19 added files, 15 changed files and no removed files. The changed files are `PHASE2OPS_UI_OPERATIONS.md`, `PHASE2OPS_REPORT.md`, `phase2d_regression.py`, `run_uri_supervised_worker.py`, `test_frozen_core.py`, two `tests/phase2d` files, two existing `tests/phase2ops` files, four bridge modules, and two Flutter files. The 19 additions comprise the closure docs, four closure scripts, two `phase2close` test modules and package marker, two `phase2ops` test modules, and `task_handoff.dart`; the archive comparison script in this review folder prints the exact lists. The added C6/C7 docs predate the closure effort in concept but are new relative to the round-7 archive. No hidden archive change was found.

The Phase 1 checkpoint zip hashes to `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`. Its 121 source files are present and byte-identical in the live tree. Three archive metadata files have no tree counterpart, as expected. The checkpoint and round-7 candidate are unchanged.

## B. Changes 1-4, adversarial review

**LOG-3.** `refusal_log.py:84-95` keeps a `bytearray` of at most 4096 bytes, copies at most the remaining room from each bytes/bytearray chunk, and passes the original ASGI message on. A missing, `None`, or non-bytes body contributes zero bytes. This closes the unbounded chunk accumulation in round 7. The logger parses only the prefix, so a valid code after byte 4096 becomes `NON_JSON_BODY`, an acceptable logging tradeoff. No unbounded retained body shape was found for valid ASGI messages.

**VAL-1.** The stated clock mechanism is real: `paired_coordinator.py:303` takes a whole-second stamp; `client_execution_control.py:76-78` checks it after the authority callback; `paired_coordinator.py:314-316` converts a failure to HTTP 403; `client_service.py:256-261` has not yet committed the turn or bumped its version. The historical 2026-10-07 refusal has no recorded code, so this is a reproduced *mechanism*, not historical attribution. It is also not the only varying 403 cause: `_authorize` at `paired_coordinator.py:425-440` rechecks current grants and qualification and can produce `EXECUTION_AUTHORITY_UNAVAILABLE` through `prepare`; pairing and scope gates can also refuse. The claim that the clock is the only variable cause is overstated.

`execution.py:581-599` allows one resend only for the two specified refusal forms, while the record is approving with no operation/task/start, no cancel requested, and the server reports `approval_required` at the original version. The second call uses the same worker-held text, session, reasoning and turn; `TurnRunner.decide` reconstructs the same approval digest and decision but a fresh idempotency key. An applied approval changes the server state/version before the status check; a concurrent move between the check and resend is rejected by the server's version gate. I found no path through this resend that approves a different proposal, launches twice or labels an applied approval `failed` under the server's normal atomic state rules. I ran the pure seam test directly; it passed. Full process tests were not reproducible in this sandbox (see NOT VERIFIED).

**CAP-1.** `worker_service.py:61-84` sends the abandoned turn's original version and binding to the frozen cancel route; `client_service.py:266-295` rejects a moved version and terminal turn, and changes a dispatched turn to `execution_uncertain` rather than `cancelled`. The changed call sites drop only pending entries or, after VAL-1, an approving record that the server still shows unchanged. I found no route by which the release can conceal a dispatched effect. The release is best effort: when the server is down, the worker discards its pending entry and records a failure locally; capacity remains held until the frozen 15-minute expiry. This limitation is disclosed and not a new safety regression.

**ISO-1.** The supervised worker sets `CODEX_HOME` to `<client_root>/home/.codex` before composition (`run_uri_supervised_worker.py:102-110`). Its auth probe passes that variable via `qualification.py:66,320-328`; version probes inherit the worker environment through `harness_env`, and supervisor executor launch passes it via `executors.py:114-116,196` and `supervisor.py:235-249`. The frozen child environment strips inherited API keys. The pin is correctly placed for the actual supervised worker. It does not by itself prove `qualify` used a client-owned login: defect D1 below.

## C. Accepted test edits

The two changed Phase 2D test files contain three material assertion changes. `test_worker_service.py` now asserts the dropped turn is `cancelled`, and `test_worker_process.py` removes the expected same-session refusal and asserts same-session continuation. Inline comments identify CAP-1 and explain the previous behavior. The tests still assert the dropped turn did not execute, that a duplicate decision cannot revive it, and that a new turn can proceed. This is an honest disclosed behavior change, not a weakened gate.

## D. Power loss and acceptance tooling

The `simulate` role always writes `SIMULATED_ONLY_NOT_A_QUALIFICATION`; its output is not physical evidence. The `host` role, however, sets `PHYSICAL_VM` solely from which CLI subcommand was selected (`phase2close_powerloss_harness.py:304-310`). `power_off` and `power_on` shell return codes are ignored. `campaign` can write `ALL_ITERATIONS_PASS` after 200 passing comparisons even if no acknowledged step was observed, and never checks that the required `synchronous=NORMAL` negative control lost an acknowledged step (`:251-300`). A process-kill rig launched through `host` can therefore produce a seemingly physical pass. The runbook's manual requirements help a careful owner but the machine-produced verdict is insufficient as qualification. See D2.

`qualify` correctly fails with exit 2 and `persisted:false` when its probe or auth check fails (`phase2close_acceptance.py:183-200`), but its process environment is only augmented with profile home variables (`:143-175`). It retains inherited provider token variables. The direct probe and auth probe both allow `CODEX_API_KEY` or `CLAUDE_CODE_OAUTH_TOKEN` (`phase2c_native_qualification.py:62`, `qualification.py:66,326`, `executors.py:114-116,190,196`). A synthetic environment probe independently showed those keys are forwarded. Therefore a successful direct probe and auth status can reflect a shared shell token rather than a login stored under the client profile. The later real worker strips those tokens, so the record would not give that worker a usable login, but `qualify` could persist a misleading `NATIVE_QUALIFIED` record and claim the profile login gate passed. See D1. I did not read any credential file or invoke a login.

The `record` command accepts a caller-supplied PASS and labels the observer `owner` without authenticating an owner (`phase2close_acceptance.py:209-218`). This is a manual ledger, and its entries should be corroborated with the named physical evidence; I do not treat its label alone as proof. Preflight's `ready_for_session:true` checks baseline materials and tools, not physical completion, and is correctly named readiness.

## E. New defects and earlier dispositions

| ID | Severity | Location | Finding and evidence | Reproduced? |
|---|---|---|---|---|
| D1 | High | `scripts/phase2close_acceptance.py:169-190`; `uri_supervisor/executors.py:114-116,190,196` | `qualify` inherits shell provider tokens. Direct probe and auth can succeed on a shared token and persist `NATIVE_QUALIFIED` without a client-profile login. A synthetic environment probe confirmed both provider token names are forwarded. | Token forwarding reproduced; false qualification follows from control flow, live login not attempted. |
| D2 | High | `scripts/phase2close_powerloss_harness.py:251-310` | `host` labels arbitrary power commands `PHYSICAL_VM`, ignores their exit codes, allows an all-pass result without acknowledged work, and does not enforce the NORMAL negative control required by the plan. Its `ALL_ITERATIONS_PASS` can be mistaken for physical qualification. | Source-traced; no VM or physical campaign available. |
| D3 | Medium | `scripts/phase2close_chain.py:141-160`; `evidence/phase2close/run4/chain_summary.json`, `run4b/chain_summary.json` | The only full sequential chain reports `ALL_PASS:false` because its native parser failed. After the parser change, only the native gate was rerun. Thus the final candidate has no single successful full-chain record, contrary to closure criterion B3. This is an evidence gap, not proof the tests regressed. | Log/summary comparison reproduced; full chain not executable here. |
| K1 | Low, known | `uri_supervisor/winproc.py:256` | The disclosed suspended-process orphan window before job assignment remains. It was found after the cut and is unrepaired. | Read only; no process-kill probe. |

EXE-1 remains explicitly BLOCKED, with no native Codex execution *inside* the worker. The inert `TaskHandoff` seam carries a draft to the supervised screen; Chat is not wired, and the C6 owner decision remains open. The round-7 UI/operations acceptance remains valid for its stated slice; no evidence here converts it to full Phase 2 acceptance. The 11 Phase 1 full-suite failures have the same IDs as round 7 and remain unresolved/unaccepted for cutover.

## F. Regression evidence and readiness claims

I checked the run4 logs independently of `chain_summary.json`: Phase 2 reports 439 passed/2 skipped; Phase 1 authority 134 passed; Phase 1 full 2675 passed/12 skipped/11 failed; Flutter 195 passed/2 skipped. The 11 failure IDs match the round-7 log. Ten live bridge JSONs and the summary report 10/10; `refusals.txt` is empty. The native stdout in run4 and run4b reports lifecycle `completed/SETTLED_VERIFIED` and mid-run cancel `uncertain/CANCELLED_AFTER_DISPATCH`, PID dead; it used an in-process composition under the shell login. I read these orchestrator-produced outputs, not personally reran them. Run4's full-chain verdict is false; run4b's true verdict covers only native. Aborted run1-run3 were excluded.

My pytest attempt for the focused VAL-1, CAP-1 and harness modules reached collection but 17 tests errored during setup because this sandbox received Windows `Access is denied` enumerating its pytest temp directory under `work/c1`. I then directly invoked the pure VAL-1 resend seam test and the pure power-loss comparison test in the venv; both passed. Archive hashes, file comparisons and the synthetic token forwarding probe were also independently reproduced. The orchestrator's passing suites are credible log evidence but not my own execution.

`PHASE2CLOSE_C7_READINESS.md` correctly says **NOT READY FOR CUTOVER** and leaves native worker execution, Chat/UI pinning, rollback overlay, owner decisions, physical power loss, development-line reconciliation and the 11 failures open. The development ledger generally keeps these items open. Its ISO-1/acceptance-tooling language and the closure report's “technically ready” verdict are too strong in light of D1-D3. Checklist A14 cannot be PASS as a client-profile-login fail-closed gate until D1 is repaired, A13 is only plumbing readiness and cannot yield a physical verdict as written, and criterion B3 lacks a successful final full chain.

## G. Decision

Closure acceptance requires correcting D1 and D2, then obtaining a successful final full-chain record or an explicitly approved equivalent gate record on the final artifact. EXE-1 and physical/owner gates remain pending even after those fixes. No physical qualification is established.

## NOT VERIFIED

No client-profile login, real worker native Codex execution, human UI click session, physical VM power cut, NORMAL negative-control loss, final full sequential chain, or live reproduction of the historical VAL-1 event was performed by this reviewer. The sandbox denied pytest fixture temp-directory enumeration. Orchestrator logs were inspected but are not independently reproduced execution. The suspended orphan window was not experimentally tested.

## FINAL VERDICT

**PHASE 2 CLOSURE REJECTED**
