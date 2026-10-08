# Independent Phase 2 operational qualification review — round 1

Date: 2026-10-08. Subject: `evidence/phase2oq-candidate-20261008.zip`, SHA-256 `47f8fc817f9bfbc355db2340b7a72845ef08a49108cc61ecaaee9cc521261deb`. This is an independent review of the archived candidate and the matching live tree, not an acceptance of the implementer's report. I read source and evidence, recomputed hashes, compared archives, and ran the narrow probes identified below. I did not use credentials, change account settings, or run a physical acceptance campaign.

## A. Integrity and exact change set

The candidate hash matches `ROUND1_SUBJECT.txt`. Its `MANIFEST.json` has 219 entries (153 tree files and 66 evidence files); every payload hash matches and every payload byte matches its corresponding live file (`uri-agent/` for source, outer `evidence/` for evidence). HEAD is `e8e3b65`. The accepted `-f` zip hashes to `fcd0d72e0cd91412c361edec9114e2edaebbf70ede052046b808f3c4fc571298`; the round-7 zip hashes to `9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a`; the Phase 1 frozen zip hashes to `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7`. I did not modify those archives. The Phase 1 frozen test is itself edited to extend the allowed-new-file list; that is a test-boundary change, not a change to the frozen archive. The archive's baseline source outside the enumerated Phase 2 changes remains the accepted `-f` payload.

Exact archive delta versus `-f`: **82 added, 25 changed, 31 removed**. Changed paths are `docs/plans/PHASE2CLOSE_C6_CHAT_INTEGRATION.md`, `PHASE2CLOSE_C7_READINESS.md`, `PHASE2CLOSE_CLOSURE_CHECKLIST.md`, `PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md`, `PHASE2CLOSE_REPORT.md`, `URI_DEVELOPMENT_TODO.md`; `scripts/phase2c_native_qualification.py`, `phase2close_acceptance.py`, `phase2close_chain.py`, `phase2close_powerloss_harness.py`, `phase2d_regression.py`, `run_uri_supervised_worker.py`; `tests/phase2a/test_frozen_core.py`, `tests/phase2close/test_acceptance_tooling.py`, `test_powerloss_harness.py`, `tests/phase2ops/test_lifecycle.py`; `uri_supervisor/supervisor.py`, `winproc.py`; `uri_supervisor_bridge/composition.py`, `execution.py`, `qualification.py`; `uri_ui/lib/screens/tasks/supervised_execution_screen.dart`, `lib/services/supervised_runtime.dart`, `task_handoff.dart`, `test/supervised_execution_screen_test.dart`.

Added source/docs paths are `docs/architecture/PHASE2OQ_UI_VOICE_ACCEPTANCE_PLAN.md`, `docs/plans/PHASE2OQ_REPORT.md`, `PHASE2OQ_SHIPPING_LINE_RECOMMENDATION.md`; `scripts/phase2oq_checkpoint.py`, `phase2oq_native_worker.py`, `phase2oq_powerloss_bundle.py`, `phase2oq_scripted_endpoint.py`; `tests/phase2oq/__init__.py`, `conftest.py`, `test_acceptance_oq.py`, `test_exe1_native.py`, `test_powerloss_bundle.py`, `test_sup1_self_containment.py`; `uri_ui/lib/screens/ask/ask_uri_screen.dart`, `lib/widgets/supervised_handoff_action.dart`, `test/chat_supervised_handoff_test.dart`. The other 66 additions are exactly the entries under `evidence/phase2oq/` in the candidate manifest: `chain1` (2 files), `chain1_stdout.txt`, `chain2` (38 files: summary, gate logs, refusals, two native groups, ten bridge JSON and ten bridge stdout files), `chain2_stdout.txt`, `chain2b_phase1_ollama_unreachable` (2 files), `chain2b_stdout.txt`, `native_try1` (5 files), `native_try2` (6 files), `powerloss_guest_bundle.zip`, `precheck_phase2.log`, `sandbox_probes` (7 files), and `sup1_orphan_observed_20261008.json`. The 31 removals are exactly the old `evidence/run9/` chain summary, phase1/phase2/Flutter/native logs and ten bridge JSON/stdout pairs; `-f` itself is retained separately. This inventory is from the two zip manifests, not the implementation report.

## B. EXE-1 native identity and attack probes

The normal npm-vendored path is direct `codex.exe`; `codex_native_launch_chain` pins the layout descriptor and `.exe`/`.dll` files with no resolve pins, and `revalidate` checks hashes, record signature, evidence, version, and expiry on composition and through `still_valid`. A replaced pinned file or changed descriptor hash invalidates an existing record. The worker environment does not add Node to PATH. The chain's `.cmd` negative control records `LAUNCH_CHAIN_RESOLUTION_CHANGED`.

**Defect OQ-R1-1:** unknown layout can still be *newly* qualified. In `uri_supervisor_bridge/qualification.py`, `codex_native_launch_chain` returns `None` if `codex-package.json` is absent, and `launch_chain_for` then returns `({}, {})` for the `.exe`. My local probe created `work/c1/oq-review-probe/vendor/bin/codex.exe`: missing descriptor returned `(None, ({}, {}))`; a descriptor with `layoutVersion:99` correctly raised `LAUNCH_CHAIN_LAYOUT_UNKNOWN`. Thus the required unknown-layout fail-closed rule is asymmetric. A record built from a successful direct probe can pin only the executable hash without the vendor dependency set. The current archive's actual record has 33 pins; I did not replace the installed vendor binary. A standalone binary is an explicitly supported separate case, but the code does not distinguish it from a damaged vendored layout. Direct probing limits immediate exploitation, yet this does not meet the stated native-chain invariant.

## C. CODEX_HOME / ISO-1

The production worker sets `CODEX_HOME` to `<client_root>/home/.codex` before composition and passes that directory as `codex_home`. `revalidate` calls `check_codex_client_home`, and `still_valid` calls `revalidate` before every bound execution. Because `environ=None` reads the current `os.environ`, a missing or changed `CODEX_HOME` after composition invalidates execution. It also checks the currently selected Windows sandbox mode. The in-process tools omit `codex_home` intentionally; those runs are not client-profile worker qualification and cannot be counted as PA-10. I found no ISO-1 bypass in the production worker path. The hash-to-spawn interval remains a conventional race, not an observed bypass here.

## D. EXE-1b sandbox backend

The provided sandbox logs support the narrow observation that `unelevated` permitted a workspace write, denied a parent write, and permitted localhost and `example.com` network requests. I read those logs; I did not rerun a sandboxed network probe. `elevated` was not tested. An absent/invalid `[windows] sandbox` yields `CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED` for a native Codex record. `provision` defaults `--codex-sandbox` to `None` and only writes config on an explicit option, so the backend choice remains with the owner. The network observation cannot establish a universal Windows security boundary, but it is enough to reject any claim that `unelevated` restricts network.

## E. OQ-1 approval gate

`ExecutionController.begin` checks live harness usability before starting its approval thread, removes the pending turn, and calls the CAP-1 cancel route on refusal. The revised `tests/phase2ops/test_lifecycle.py` assertion honestly describes this `execution_begin` path. The chain's W case reports `HARNESS_NOT_USABLE` and a cancelled server turn.

**Defect OQ-R1-2:** `SupervisedWorkerService.handle('turn_decide', {'approve': True, ...})` remains admitted in the same production worker protocol and calls `super().handle` without `harness_state`/`selectable` first. That older runner sends approval to the server and reaches dispatch before the bridge refuses an unusable harness. The optional `approval_digest` protects the echo, not usability. Thus the statement that *no approval for an unusable executor reaches the server* is false; the new test covers only `execution_begin`. I verified the call path in `worker_service.py:94-118`, `execution.py:502-519`, and `turn_runner.py:121`; I did not run a live worker frame for this bypass. UI preference for `execution_begin` does not remove the authorized legacy command.

## F. SUP-1 containment

`Supervisor.__init__` calls `contain_current_process` before it can spawn. The Windows job has `KILL_ON_JOB_CLOSE`, no breakaway flag, and the process-level handle lives until host exit. The real-process test and `sup1_orphan_observed_20261008.json` support the suspended-orphan mechanism; I read them, and did not kill a process myself. Recovery and ledger code are otherwise unchanged.

**Defect OQ-R1-3:** `contain_current_process` explicitly returns `UNAVAILABLE:*` rather than raising if job creation/assignment fails, and `Supervisor.__init__` continues. The original suspended-orphan window therefore remains for any host where nesting or assignment is unavailable. The test accepts `UNAVAILABLE` on non-Windows, while the Windows assertion only shows this particular test host accepted containment. The process-wide job also means other descendants of a host process (including pytest or a guest) are killed on host exit, beyond the supervisor's own executor. That side effect is inherent in the selected mechanism and should be scoped or documented for hosts that do other work. No new execution authority was found.

## G. D8 power loss witness

`unclean_shutdown_witnessed` requires a guest-reported event after `ready.guest_wall` and a later boot time; `assess_series` demands it for every VM iteration. A clean shutdown with no unclean event cannot satisfy this test. The data is guest-supplied and cannot tie a particular event to the hypervisor's asserted cut; a different unclean restart after `ready` could satisfy it. `assess` always returns `qualified: false` and `power_method_attestation_required: true`. This is an evidence screen pending owner attestation, not physical qualification. The prior D8 command-form limitation remains; the new witness narrows but does not remove it.

## H. C6 Option B Chat handoff

The Chat widget is mounted only on nonempty user turns outside its in-flight stages and only with supervised opt-in. Tapping creates an in-memory `TaskHandoff` and navigates; it supplies no executor, approval, ticket, or send call. Overlong messages disable the action rather than truncate. The supervised screen's draft/busy, stale, Back, and restart cases are covered by widget tests in the chain; I did not run a device UI session. A settled conversation turn can still be handed off after a prior conversation action, but the widget does not put the same pending request into two simultaneous approval paths. Physical PA-13 remains open.

## I. Acceptance tooling

`login-guide` prints commands and does not invoke a login or read credential files. `status` has distinct installed, client-profile authenticated, record-qualified, and PA-10 operational fields. `provision --codex-sandbox` has no default. The guest bundle has 17 declared files, all hashes match, and no unlisted payload. The installer refuses without `-IAmInsideTheThrowawayVM`, but that switch is a manual assertion and is not VM detection; it must only be run in the owner's VM campaign. None of these tools establishes PA-8 through PA-13 by itself.

## J. Chain and prior dispositions

`chain2/chain_summary.json` records phase2 470 passed/2 skipped, authority 134 passed, Flutter 205 passed/2 skipped, ten bridge runs, and passing native and native-worker gates. It also records phase1-full **17 failed**, 2676 passed, 5 skipped, `SAME_FAILURE_SET:false`, and `ALL_PASS:false`. This is not a single green full chain. The subsequent `chain2b` environmental control gives 11 failures matching the prior accepted failure set and 11 skips; it is a separate run and also has `ALL_PASS:false`. The six extra live Ollama failures have a plausible environmental cause from the logs, but a control cannot turn `chain2` green. The other 11 baseline failures remain unresolved as previously accepted limitations. LOG-3, VAL-1 resend, CAP-1, ISO-1 and closure round 1–6 regression suites are included in the passing phase2/authority gates; I did not independently replay each historical exploit. CAP-1 works on the `execution_begin` refusal but does not cure OQ-R1-2. The accepted closure round-6 D8 limitation remains pending physical attestation.

## K. Shipping line and UI/voice plan

The Core-line recommendation is reasoned from accepted checkpoint provenance and the separation of `_V1` and `eb73693` donor features; it is a recommendation, not a shipping authorization. I did not independently inspect the separate git-sync worktree or its remote, so its claimed push/current branch state remains unverified here. The UI/voice plan labels Chat handoff as widget-tested, voice as absent from this tree, and real-device checks as PA gates. It does not mislabel a scripted model or widget result as device evidence. Its statement that OQ-1 is ready must be read subject to OQ-R1-2.

## L. New defects

The defects are OQ-R1-1 through OQ-R1-3 below. OQ-R1-2 is a direct approval-boundary regression; OQ-R1-1 breaks the promised unknown-layout native-chain rule; OQ-R1-3 leaves SUP-1 open when host self-containment cannot be established. The failed full chain independently blocks the claimed one-green-chain acceptance condition.

## M. Decision

The archived candidate is internally consistent and contains meaningful worker and UI evidence. It does not meet the operational qualification mandate because of the approval bypass and native-layout fallback, and its own final full chain failed. PA gates and the sandbox backend decision remain with the owner. Repair the three defects, add adversarial regression coverage for both approval commands and missing native descriptors, and rerun an attributable final chain before another review.

## DEFECTS

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| OQ-R1-1 | High | Missing vendor layout descriptor is accepted as a generic `.exe` with empty launch-chain pins; unknown layout can be newly qualified. | `uri_supervisor_bridge/qualification.py:194-232`; local missing-descriptor probe returned `({}, {})`. |
| OQ-R1-2 | High | Legacy `turn_decide approve=True` bypasses OQ-1's pre-approval usability check; approval can reach the server before bridge refusal. | `uri_supervisor_bridge/worker_service.py:94-118`; `execution.py:502-519`; `uri_core/client_runtime/turn_runner.py:121`. |
| OQ-R1-3 | Medium | Supervisor continues after `contain_current_process` reports `UNAVAILABLE`, retaining the suspended-orphan window; process-wide job affects unrelated host descendants. | `uri_supervisor/winproc.py:242-288`; `supervisor.py:58-65`; `tests/phase2oq/test_sup1_self_containment.py`. |
| OQ-R1-4 | Gate | Candidate's final `chain2` is `CHAIN_FAILED`, with 17 phase1-full failures and `ALL_PASS:false`; control is separate and also failed. | `evidence/phase2oq/chain2/chain_summary.json`; `chain2b_phase1_ollama_unreachable/chain_summary.json`. |

## NOT VERIFIED

No client-profile login, credential read, real model in the worker, elevated sandbox, owner UI/device session, physical VM power cut, hypervisor attestation, or remote shipping-line inspection. I read orchestrator native and chain outputs but did not reproduce those end-to-end runs. My focused pytest invocation (`test_unqualified_provider_fails_closed_before_any_task` plus `test_exe1_native.py`) ended with Windows `PermissionError [WinError 5]` on its `work/c1/oq-review-pytest` temporary directory and is not counted as passing; no test result is claimed from it. I did reproduce archive hashes/byte matching, the missing-descriptor launch-chain probe, and guest-bundle hash verification.

## FINAL VERDICT

**PHASE 2 OPERATIONAL CANDIDATE REJECTED**
