# URI Phase 2B: Core <-> Supervisor integration boundary, slice report

Date 2026-10-07. Author: Claude (implementer and self-auditor; NOT an independent audit). Worktree
`C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`, detached at `e8e3b65`, everything uncommitted. Nothing was
committed, pushed, merged, cut over or activated; no account was logged into; the frozen Phase 1 checkpoint was not touched.

Labels used: RESEARCHED / PLANNED, IMPLEMENTED, TESTED (automated test ran and passed, `COMPLETED_WITH_RESULT`), QUALIFIED,
FROZEN. Evidence marked SYNTHETIC uses the fake harness executor; evidence marked REAL used an installed CLI.

## A. Starting checkpoint

* Phase 2A candidate `C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2a-candidate-20261007.zip`,
  SHA-256 recomputed with `certutil`: `c0b82fa040a52c3e829e4951c1e89d7bffa1c0576bf362ffdfbef51e8314751c` (matches the brief).
  Sidecar: 41 files, base `e8e3b65`, head `e8e3b65259c45fc823addc3ef8969425a265bd1b`.
* Frozen Phase 1 checkpoint `...\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip`,
  SHA-256 `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7` (re-verified by `test_frozen_core.py`).
* Baselines reproduced before any change: `tests/phase2a` 168 passed, 2 skipped (`.venv`, `python -I`); Phase 1 authority
  suites (`test_c5_loop`, `test_c2_uncertain_adversarial`, `test_c5_intent_adversarial`, `test_c4_harness`,
  `test_phase1_fail_closed`, `test_intent_discovery_unit`, `test_c5_intent_discovery`, `test_c7_rollback_boundary`) 134 passed.

## B. Governing plan and slice

No standalone Phase 2 plan document exists in the repository (searched `docs/**`, root `*.md`, the Phase 1 worktree).
Governing text: `docs/architecture/PHASE2A_ARCHITECTURE.md` ("[integration seam, NOT wired]"; Core integration "deliberately
not done: it would require editing frozen files") and `docs/plans/PHASE2A_REPORT.md` K ("Wiring needs edits to frozen files
and your decision"). The next slice is the Core <-> Supervisor integration boundary, as the brief expected.

**Discrepancy reported:** Phase 2A stated that wiring needs frozen-file edits. It does not. The frozen client runtime
already exposes the two seams needed (`TurnRunner._validate_ticket`, invoked by `ExecutionJournal.intent`, and
`TurnRunner._run_harness`), so the boundary was implemented as a pure composition layer. **No frozen file was modified,
and no authorization to modify one was needed or requested.**

## C. Architecture implemented

See `docs/architecture/PHASE2B_INTEGRATION_BOUNDARY.md`. In one line: the server-signed Phase 1 `ExecutionTicket`
(issued only after digest-bound confirmation and explicit approval) is re-verified on the client, turned into ONE bounded
supervisor authorization (`task_id = operation_id`, scope = op classes + the user's explicit executor + per-run workspace,
validity `[issued_at, deadline)`), submitted to `uri_supervisor`, run under targeted admission, and mapped back to the frozen
receipt vocabulary; `verified` is produced only from ledger `COMPLETE` (URI-observed postcondition).

Chain: User -> IntentDiscovery -> confirmed intent digest -> PairedCoordinator approval digest -> signed ticket -> client
claim -> `SupervisedTurnRunner._run_harness` -> `verify_authority` -> `SupervisorBridge.execute` -> `Supervisor.submit_task`
/ `admit_next(only_task_id)` / `run_attempt` / `reconcile` -> (outcome, evidence, failure) -> frozen receipt/settle -> URI.

## D. Files added / changed

Added (untracked):
* `uri_supervisor_bridge/__init__.py`, `authority.py` (verification -> `AuthorizedWork`), `bridge.py` (`SupervisorBridge`),
  `runner.py` (`SupervisedTurnRunner`, `SupervisedTurnService`).
* `tests/phase2b/`: `conftest.py` (synthetic signer + real paired stack), `test_authority.py`, `test_bridge_unit.py`,
  `test_bridge_e2e.py`, `test_bridge_restart.py`, `test_boundary.py`, `test_failclosed_extras.py`,
  `helpers/fake_harness.py` (SYNTHETIC), `helpers/bridge_child.py`.
* `docs/architecture/PHASE2B_INTEGRATION_BOUNDARY.md`, this report, `scripts/phase2b_checkpoint.py`.

Changed (Phase 2A candidate files, not frozen; diffed against the Phase 2A zip, exactly these four):
* `uri_supervisor/admission.py`, `uri_supervisor/supervisor.py`: `admit_next(only_task_id=None)`.
* `uri_supervisor/postconditions.py`: checker `file_regular_nonempty`.
* `tests/phase2a/test_frozen_core.py`: `ALLOWED_NEW` gains the Phase 2B paths.

Frozen Phase 1 files changed: **none**. `graphify update .` not run (would rewrite tracked baseline files).

## E. Frozen-Core preservation

* `tests/phase2a/test_frozen_core.py`: 8 passed after the slice (checkpoint hash, all 122 checkpoint files byte-identical,
  nothing changed outside checkpoint + allowed Phase 2 paths, HEAD still `e8e3b65`, Core never imports `uri_supervisor`,
  supervisor never imports Core, bypass-flag refusal superset).
* `tests/phase2b/test_boundary.py`: `uri_core`, `uri_harness_adapters`, `uri_supervisor`, `uri_ui` contain no reference to
  `uri_supervisor_bridge`; the bridge imports no intent/session/approval API; the runner overrides only
  `_validate_ticket`/`_run_harness`/`_runner`; `NOT_STARTED` prefix identical to the frozen runtime.
* `git status` tracked modifications are the same 11 Phase 1 overlay files as before the slice (overlay is inside the frozen zip).

## F. Authority / confirmation integration evidence (TESTED)

`tests/phase2b/test_authority.py` (31 incl. parametrised) and the e2e suite show: forged signature, foreign key, every binding
field, server generation, freshness window, deadline -> refused; tampered `arguments` (instruction or file) with a valid
ticket -> `ARGUMENT_DIGEST_MISMATCH`; approval digest tampering, a different confirmed-intent digest, a dropped intent
digest, or a ticket whose approval digest was computed for another operation -> `APPROVAL_DIGEST_MISMATCH`; wrong
capability/verifier -> refused; provider/model ids validated as data (fullmatch); 14 hostile `expected_file` names refused;
instruction bounds. End to end: declined approval and unconfirmed typed text reach neither the supervisor nor an executor
(zero ledger tasks); a verified intent replayed through the frozen server guard creates no second task; a server-generation
change before execution refuses the old ticket at the bridge; the bridge changes neither `intent` nor `session_update`.

## G. Supervisor integration evidence (TESTED, SYNTHETIC executor)

`test_bridge_unit.py` (24) and `test_bridge_e2e.py` (15); `test_bridge_restart.py` (14), `test_boundary.py` (7), `test_failclosed_extras.py` (2); 93 collected in all: honest run -> `verified`, ledger COMPLETE, completion record
`verified` citing `uri_verified` postcondition evidence, exactly one copied-out result, authorization row carries the ticket
digests and `allowed_executors=[provider]`, `valid_until_us == deadline`; false claim / success-shaped string / `ok:true` then
exit 3 / free-text "Success!" / hang -> never verified, retried once under the SAME `auth_id`, then FAILED; side effects in
the workspace (`empty_output`, `wrong_file`, `partial_then_die`) -> NEEDS_USER -> `execution_uncertain`, never retried; quota
before any activity -> clean `quota` pause (frozen `WAITING_FOR_MODEL`, checkpoint, same provider refused, other provider
proceeds after a fresh approval, exactly one effect); quota after any activity -> uncertain; executor substitution (selected
provider not registered, or registered but not Phase 1-usable) -> `NOT_STARTED`, zero tasks; binary mismatch between the
Phase 1-qualified executable and the supervisor binding -> refused (D-B3); targeted admission ignores a higher-priority foreign
task; a settled ticket leaves no admittable work; a user `retry` decision cannot run without new authority; executor-supplied
session id cannot enter argv; grandchild killed; instruction text appears in neither argv nor the ledger request.

## H. Crash / restart / replay evidence (TESTED, SYNTHETIC)

`test_bridge_restart.py`: the bridge is killed (`os._exit`) in a child process at 9 supervisor points and 2 recovery points
(`after_submit`, `after_admit_commit`, `after_intents`, `after_spawning_marked`, `after_pid_record`, `after_spawn_resumed`,
`mid_stream`, `after_terminal_event_recorded`, `after_attempt_ended`, `recovery_after_fence`, `recovery_before_decision`).
After restart: the task is never RUNNING/RECOVERING/QUEUED/RETRY_SAFE; its authorization is closed; no attempt is
ADMITTED/SPAWNING/RUNNING; the restart launches nothing (effect counter unchanged); replaying the same ticket returns
`DUPLICATE_OPERATION` -> `execution_uncertain` with no new attempt; a second restart changes no recovery decision; a NEW ticket
still runs and verifies while the old task is untouched. A RETRY_SAFE leftover from a crash before spawn becomes FAILED
(`AUTHORITY_REVOKED_RESTART`) instead of running; an uncertain task stays NEEDS_USER across restart and a user `retry` is
un-admittable without new authority; two bridges on one client root are refused (`SUPERVISOR_ALREADY_RUNNING`).

NOT TESTED: power loss / OS write reordering (plan exists, needs a VM).

## I. Real executor evidence vs synthetic

* REAL (re-run today, opt-in `URI_PHASE2A_LIVE=1`, no login): Codex CLI 0.158.0 and Claude Code 2.1.287 each ran through
  the supervisor on a read-only prompt and ended with a terminal error claim, exit 1, task RETRY_SAFE (never COMPLETE).
  Codex: configured model rejected for this account; Claude: expired OAuth session. Log:
  `evidence\phase2b\phase2a_live_recheck.log`. **A successful real executor run and real resume remain NOT DEMONSTRATED.**
* Through the BRIDGE no real executor ran: the frozen Phase 1 `HarnessRegistry` reports both CLIs `NATIVE_UNQUALIFIED` and
  not authenticated, so the bridge refuses them (`NOT_STARTED:HARNESS_HARNESS_NOT_USABLE`) exactly as designed. Qualifying
  them requires native login evidence (owner action, C7 gate 4); I did not fake it.
* Everything in F-H is SYNTHETIC (fake harness speaking the generic NDJSON dialect) against the REAL supervisor, REAL ledger,
  REAL paired server, REAL client persistence/DPAPI and REAL Windows job containment.

## J. Test results and baseline comparison

| Run | Result | Baseline |
|---|---|---|
| `tests/phase2b` run 1 (concurrent with the full Phase 1 run) | 87 passed, 2 failed | failures were `ImportError: planted` from `test_c1_source_pin.py` planting a shadow module in the shared tree at the same instant: environmental, not a code result |
| `tests/phase2b` run 2 | 93 passed | – |
| `tests/phase2b` run 3 | 93 passed | – |
| `tests/phase2a` after the slice (`-I`) | 168 passed, 2 skipped | identical to baseline |
| `tests/phase2a/test_frozen_core.py` | 8 passed | identical |
| Phase 1 authority suites (`-I`) | 134 passed (pre-slice; no Core file changed) | identical |
| Phase 1 full repository suite (`-I`, excludes `tests/phase2a`, `tests/phase2b`) | 2674 passed, 12 skipped, 12 failed, 876 s (`evidence\phase2b\phase1_full_after_slice.log`) | Phase 2A report: 2842 passed (= 2674 + the 168 Phase 2A tests then included), 12 skipped, 11 known failures + 1 environmental |

Failure comparison, ID by ID: eleven failures are the identical eleven baseline IDs (`step3_test::test_drive`,
`step4_test::test_download`, `test_capability_directory` privacy, `test_m20_feasibility_validation`, 2x `test_m20_recovery_loop`,
2x `test_m20_semantic_interpreter_resilience`, `test_orchestrator_session_workflow`, `test_usage_import_boundary`,
`test_workflow_restart_recovery`). The Phase 2A twelfth (missing evidence zip) now passes because the zip is present. The new
twelfth, `test_c1_source_pin.py::test_package_or_extension_named_like_a_bootstrap_module_never_runs` (`assert not marker.exists()`),
occurred while `tests/phase2b` run 1 was importing `uri_core` in the same tree at the same instant (its own symmetric symptom:
`ImportError: planted`); the shadow-module test is not isolation-safe against a concurrent importer. Re-run alone afterwards:
`test_c1_source_pin.py` 12 passed. Classified environmental (concurrency), not a code result; no Core file changed in this slice.

## K. Self-audit defects and repairs

| ID | Severity | Root cause | Repair | Regression test | Failed before repair? |
|---|---|---|---|---|---|
| D-B1 | Medium (injection) | `re.match` + `$` accepted `"out.txt\n"` (`$` matches before a trailing newline), so a newline could reach a file name | `fullmatch` for file, provider and model patterns | `test_expected_file_must_be_a_bare_safe_name[out.txt\n]` | Yes (DID NOT RAISE) |
| D-B2 | High (quota bypass) | Phase 2A consults breakers only on CLAIMED pools; my per-provider quota pool was declared but not claimed, so a quota-hit provider was silently re-admitted | quota pool is also claimed (capacity 1) | `test_quota_on_one_provider_does_not_block_the_users_explicit_choice_of_another` | Yes (`verified` instead of `NOT_STARTED:EXECUTOR_NOT_ADMITTED`) |
| D-B3 | High (executor substitution) | Supervisor binding and Phase 1 registry each named an executable; a binding pointing at a different binary ran unqualified code under a qualified provider name | the binary run must be the file the registry qualified (`EXECUTOR_BINARY_MISMATCH`); a binding without an explicit executable inherits the qualified one | `test_supervisor_runs_only_the_binary_phase1_qualified`, `test_binding_without_explicit_executable_uses_the_qualified_one` | Yes (two attempts ran) |
| D-B4 | Medium (stale authority) | Restart revocation only looked at tasks with open authorization; a RETRY_SAFE task whose authorization had already been closed survived restart as admittable-looking work | restart also fails every QUEUED/RETRY_SAFE task | `test_uncertain_task_survives_restart_as_uncertain_and_user_retry_needs_new_authority` | Yes (`RETRY_SAFE` != `FAILED`) |
| D-B5 | Low | COMPLETE tasks kept an open authorization until the ticket deadline (harmless: terminal state, but violated "settled ticket leaves no open authority") | authority closed on COMPLETE and at restart for any still-open row | restart suite assertion `valid_until_us <= now` | Yes (11 parametrised failures) |
| H-1 | hardening | `LedgerError` raised mid-run propagated out of the bridge | caught -> `execution_uncertain` (`SUPERVISOR_ERROR:<code>`) after best-effort authority closure | none (not reproduced) | n/a |
| H-2 | hardening | copy-out failure after COMPLETE returned before closing authority | authority closed first | none (not reproduced) | n/a |

Test-side corrections (not product defects): wrong expected code for a ticket past its own deadline (`TICKET_DEADLINE_PASSED`
is correct), `approval_status` literal is rejected by pydantic before the signature (`TICKET_SHAPE`), the boundary test
matched words in comments, a stale ledger handle after restart, and two fake scenarios (`partial_then_die`,
`quota_after_write`) initially wrote the declared output file, which honestly VERIFIES under the declared postcondition
(Phase 1 semantics); they now produce a side file instead.

## L. Remaining limitations / NOT DEMONSTRATED

* Real Codex/Claude success path, real session resume, live qualification through the bridge: NOT DEMONSTRATED (auth/model).
* Power loss: NOT TESTED. Local-model executors: NOT QUALIFIED (not added; Strata RESEARCHED / NOT IMPLEMENTED / NOT REQUIRED).
* UI / worker composition: `SupervisedTurnService` exists; the frozen worker still composes Phase 1 `TurnService`. No launcher
  switched. UI approval screens unchanged.
* Absence proofs cover the declared workspace only (pinned by `test_effect_outside_the_declared_workspace_is_not_detected_by_absence_proof`).
  Any non-empty content in the declared output file satisfies the postcondition, exactly as Phase 1's `harness_output_check`.
* Approval-digest recomputation duplicates the server formula; a server change fails closed, never open.
* A dispatched attempt that the supervisor FAILS with absence proven is still settled `execution_uncertain` by the frozen server
  (Phase 1 rule); the bridge does not try to claim more than `NOT_STARTED` when the executor never ran.
* Ledger retention, snapshot/narration integration into Core replies, and multi-task scheduling policy are untouched.

## M. Implementation-status ledger for Phase 2

| Slice | Status |
|---|---|
| 2A Durable Task Supervisor (`uri_supervisor`) | IMPLEMENTED, TESTED (168 + crash points); NOT QUALIFIED (no real success run, no power loss); NOT FROZEN |
| 2B Core <-> Supervisor boundary (`uri_supervisor_bridge`) | IMPLEMENTED, TESTED (93, SYNTHETIC executor, real server/ledger); NOT QUALIFIED; NOT FROZEN |
| Worker/UI composition on the bridge | PLANNED (`SupervisedTurnService` exists, unused) |
| Real executor qualification (Codex, Claude) | BLOCKED on native login / model configuration (owner action) |
| Local-model executors | RESEARCHED, NOT IMPLEMENTED, NOT REQUIRED |
| Power-loss qualification | PLANNED (`PHASE2A_POWER_LOSS_TEST_PLAN.md`), NOT RUN |

## N. Recommendation

**ACCEPT CANDIDATE** for Phase 2B as an integration boundary (not as a qualified or frozen component). Reasons: no frozen
file touched; authority consumed only from the signed ticket; every brief requirement in "Integration requirements" has a
passing test or a reused frozen guard; crash/restart/replay tested at 11 points; five self-found defects reproduced and
repaired. Not FROZEN because real-executor success, power loss and worker/UI composition remain undemonstrated.

## O. New checkpoint

`C:\Users\cheta\.codex\worktrees\uri-phase2a\evidence\phase2b-candidate-20261007.zip`
SHA-256 `55ed7f98d2fe2298dac6174e42c2469aa362565142e945e3fc2de69107fba972`, 59 files (Phase 2A + Phase 2B material, tests,
reports, `MANIFEST.json` with per-file SHA-256, `GIT_HEAD.txt`, `GIT_STATUS.txt`), base `e8e3b65`, cut by
`scripts/phase2b_checkpoint.py`. Sidecar `phase2b-candidate-20261007.json` carries the same hash. The copy of this report
inside the zip predates this hash line (a zip cannot contain its own hash); the sidecar is authoritative.
Status: CANDIDATE, NOT FROZEN. Run logs: `evidence\phase2b\*.log`.
