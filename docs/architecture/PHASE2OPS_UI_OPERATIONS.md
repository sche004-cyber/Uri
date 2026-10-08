# URI Phase 2 UI / operations slice, architecture

Status: IMPLEMENTED CANDIDATE, TESTED (automated: in-process, real processes, Flutter widget, live Dart-to-worker),
Codex NATIVE run through the new lifecycle (see the report), NOT INTEGRATED into the frozen launchers, NOT FROZEN,
NOT CUT OVER. Uncommitted, local only, on the accepted Phase 2D candidate (`evidence\phase2d-candidate-20261007-r2.zip`,
SHA-256 `cbec537a...68688d`, Codex round 3: "PHASE 2D ACCEPTED — MORE PHASE 2 SLICES REMAIN") over the frozen Phase 1
Core (`final-closure-20261005-phase1.zip`, SHA-256 `31a34dcb...efeb98cf7`, base commit `e8e3b65`).

## What this slice is, in the governing documents

The Phase 2C report (section P) and the Phase 2D review left "UI/operations connection + human qualification" as the
next REQUIRED Phase 2 work (Codex round 3, section D: `PHASE2C_NATIVE_QUALIFICATION_REPORT.md:271-272`,
`C6_UI_INTEGRATION_CONTRACT.md:47-50`, `PHASE2D_COMPOSITION.md:122-123`). There is no official "2E/2F" numbering; this
slice is named "UI/operations" (`phase2ops` in paths). The C6 contract (binding on any UI that drives the paired
runtime) is kept in full: the UI talks only to the client worker over framed stdio, never to the server, never holds
credentials, never approves on its own, never defaults or switches an executor.

## Chain as composed by this slice

```
URI Flutter UI (Tasks -> "Supervised execution", shown only when <client_root>/control/ui-supervised-profile.json opts in)
  -> SupervisedWorkerRuntime (uri_ui/lib/services/supervised_runtime.dart) spawns scripts/run_uri_supervised_worker.py
     (same interpreter, same manifest, same client root as the frozen worker; preflight must report
      worker_profile=phase2d-supervised, production_cutover=false, execution_lifecycle)
  -> turn_start / turn_intent (frozen frames) -> approval_required + execution_proposal
  -> approval card: task, result file, capability, executor (provider, model, kind), effect scope, qualification,
     approval digest, proposal digest; executor choice LOCKED while a card is pending
  -> execution_begin {turn_id, approval_digest, proposal_digest}   (returns at once with an execution_id)
       worker thread: runner.decide(approve) -> server approval -> ticket -> claim -> SupervisedTurnRunner
       -> verify_authority -> SupervisorBridge -> uri_supervisor -> qualified executor -> receipt -> settle
  -> execution_status polled: durable record + live ledger + journal + server turn   (never UI memory)
  -> execution_cancel at any non-terminal point; execution_list on (re)open
  -> receipt card (state, reason, settlement code, executor, qualification, timestamps, ledger task/attempt,
     journal state, server turn state, output sha256/bytes, cancellation flag, explicit UNCERTAIN wording)
```

Frozen files changed: **none**. `uri_ui/lib/services/paired_runtime.dart`, `paired_runtime_screen.dart` and
`settings_shell.dart` are in the Phase 1 checkpoint and are byte-identical. The one Phase 1 (non-checkpoint) UI file
touched is `uri_ui/lib/app.dart`: the Tasks destination mounts `SupervisedExecutionEntry`, which renders nothing unless
the installation opted in.

## New / changed modules

| Module | Responsibility |
|---|---|
| `uri_supervisor_bridge/execution.py` (new) | `execution_proposal` (what an approval binds to), `ExecutionRegister` (durable per-execution JSON under `control/supervisor/executions/`, restart reconciliation), `ExecutionController` (begin in a worker thread, status = record + read-only ledger + read-only journal + server `GET /client/v1/turns/{id}/status`, cancel at every phase, bounded close), `ledger_view` / `journal_view` (read-only SQLite) |
| `uri_supervisor_bridge/worker_service.py` | `execution_begin` / `execution_status` / `execution_cancel` / `execution_list` frames; `execution_proposal` on every `approval_required` reply; `EXECUTION_IN_PROGRESS` for every turn command while one execution is in flight; `turn_decide` (blocking, frozen semantics) kept |
| `uri_supervisor_bridge/runner.py` | three observation hooks on the ONE execution the controller drives (`on_starting`, `on_dispatch(work)`, `on_outcome(work, outcome, evidence, failure)`); they cannot change the outcome, the receipt or the frozen order |
| `scripts/run_uri_supervised_worker.py` | dispatches the four frames; `preflight` reports `execution_lifecycle`, `mid_run_cancel`, `execution_active`; `snapshot`/`consent`/`commit` wait while an execution is in flight; `close` and stdin EOF withdraw an in-flight execution (job kill) before the ledger closes |
| `uri_ui/lib/services/supervised_runtime.dart` (new) | `SupervisedWorkerRuntime` (opt-in probe, spawn, profile check, frames), `ExecutionProposal`, `SupervisedTurn`, `ExecutionStatus`, `ExecutionSummary`, `SupervisedRuntime` interface |
| `uri_ui/lib/screens/tasks/supervised_execution_screen.dart` (new) | the screen and the Tasks entry |
| `uri_supervisor_bridge/qualification.py` | Phase 2D low findings R3-1/R3-2: fixture evidence must name exactly the record's models; a missing or malformed list is `EVIDENCE_CONTENT_MISMATCH`, never a crash |

## Authority: what moved, what did not

Nothing moved. Core still issues the approval request, the ticket and the settlement; the client journal still records
intent/claim/receipt; the supervisor ledger still owns admission, fencing, containment and reconciliation. The slice adds
a worker-owned, durable **observation** of one execution and a **proposal digest** that binds the UI's approval to the
exact selection the worker will dispatch. The UI holds execution ids only.

| Claim | Mechanism | Evidence |
|---|---|---|
| Approval bound to the exact proposal | `proposal_digest = sha256(canonical{client_id, session_id, turn_id, kind, provider, model, capability_id, argument_digest, approval_digest})`; `execution_begin` must echo it AND the server's `approval_digest`; a mismatch drops the pending turn (`APPROVAL_DIGEST_MISMATCH` / `PROPOSAL_DIGEST_MISMATCH`) | `test_lifecycle.py::test_wrong_approval_or_proposal_digest_*`, `::test_changing_an_authority_field_invalidates_the_approval` |
| Changing an authority field after approval needs a new approval | another provider/model/arguments/turn = another digest; after `begin` the frozen ticket (`ARGUMENT_DIGEST_MISMATCH`) and the bound selection (`AUTHORITY_SELECTION_MISMATCH`, Phase 2C D-C1) still hold; the UI locks the executor choice while a card is pending | same tests; widget test "approval card ... nothing is sent until Approve and run" |
| Typed text never approves | the frozen server holds the session (`TURN_CAPACITY`) while an approval is pending; only `execution_begin`/`turn_decide` structured frames decide | `::test_typed_text_never_begins_an_execution`; widget test "typing approve never begins an execution" |
| Lifecycle: queued -> approving -> starting -> running -> terminal | record phases written by the execution thread at: begin, before the approval post, after the server authorized dispatch (`on_starting`), just before the bridge runs the work (`on_dispatch`), and at settlement | `::test_begin_returns_at_once_and_settles_to_completed_with_receipt` (timestamps monotonic) |
| Terminal states never invent success | `completed` only from `SETTLED_VERIFIED`; `SETTLED_EXECUTION_UNCERTAIN`, unmapped codes, any exception after the first server call -> `uncertain`; `failed` only from `SETTLED_FAILED`; `cancelled` only when nothing ran (denied before approval, or `NOT_STARTED:CANCELLED`); `quota_paused` from `WAITING_FOR_MODEL` | `::test_failure_shapes_never_become_completed` (false claim, empty output, wrong file -> uncertain; quota -> quota_paused), `test_reconnect.py::test_server_unreachable_at_settle_is_uncertain_not_completed` |
| Mid-run cancel kills the executor and its descendants | `execution_cancel` -> `SupervisorBridge.cancel(task_id)` -> `Supervisor.request_cancel` -> job-object kill at the next poll; `cancelled_killed`; no re-admission; `uncertain` (`CANCELLED_AFTER_DISPATCH`) | `test_cancel.py::test_cancel_while_running_*` (pid dead, attempt `cancelled_killed`, one attempt, no open authorization, journal + server `execution_uncertain`), `::test_cancel_kills_descendants_too` (grandchild pid dead), real frames in `test_worker_process.py`, REAL Codex in the report |
| Cancel before the approval is posted = denial | the thread checks the flag before `decide(approve)`; `approve=False` -> `APPROVAL_DENIED`, server turn `cancelled`, zero tasks | `::test_cancel_before_the_approval_is_posted_denies_the_turn` |
| Cancel between approval and dispatch never spawns | `on_dispatch` sees the flag and calls `bridge.cancel` before `execute`; `NOT_STARTED:CANCELLED`, no task row | `::test_cancel_between_approval_and_dispatch_never_spawns` |
| Cancel after a terminal state is refused | `EXECUTION_TERMINAL`; the record is unchanged | `::test_cancel_after_terminal_is_refused_and_changes_nothing` |
| Reconnect: the UI never forgets an execution | durable register; `execution_list` on open; a new worker re-reads ledger/journal/server for every record | `test_reconnect.py::test_completed_execution_survives_a_worker_restart`, Dart live test part 3 |
| Worker restart / crash mid-run | kill-on-close job ends the executor; the next worker runs the frozen journal recovery (`claimed` -> `execution_uncertain`), the bridge revokes authority, the register marks the record `uncertain` (`WORKER_RESTARTED`, ledger facts attached); nothing relaunches | `test_worker_process.py::test_worker_crash_mid_run_*` (REAL processes), `test_reconnect.py::test_in_flight_execution_is_uncertain_after_restart_*` |
| Server unreachable at settle | exception after the claim -> `uncertain`; ledger COMPLETE and journal `verified` are reported as facts, the server turn stays `executing`; URI does not call it done | `::test_server_unreachable_at_settle_is_uncertain_not_completed` |
| Stale UI state cannot override | every display is a fresh `execution_status`; cancel/begin/decide on a terminal execution are refused | `::test_stale_ui_state_cannot_override_the_record`; widget test "stale UI state yields to the worker" |
| The record's own `completed` is never relayed on its word (review round 1, OPS-1) | `corroborate()`: harness execution `completed` only while ledger COMPLETE + journal `verified` + server `reply` (same operation) + code `SETTLED_VERIFIED`; local execution only while the server answers `reply`; else `uncertain` / `UNCORROBORATED_COMPLETION:<gaps>` with `recorded_state` kept; applied to status AND list | `test_reconnect.py::test_ops1_*`; widget test "uncorroborated record" |
| Every execution owns its ticket operation (round 4, OPS-1R residual) | when the ticket verifies, the controller claims the ticket's `operation_id` for this `execution_id` in a create-once index (`control/supervisor/executions/operations/`); `corroborate()` requires `operation_id`, ownership, `task_id == operation_id` for harness records, the server's operation equal to it, and the client journal row `verified` — for local executions too. A duplicate record under another id is `OPERATION_NOT_OWNED`. Trust limit: index, register, journal and ledger share the local client root. | `test_ops1_*` (c6) |
| A harness record cannot pose as a local one (round 3, OPS-1R residual) | a record with no `task_id` is `TASK_OMITTED` when its proposal kind is `client_external_harness` or when the server's `operation_id` names an existing supervisor task | `test_ops1_*` (c5) |
| Nested shapes are validated on both sides (round 3, OPS-2R residual) | Python `_well_typed` checks `proposal`/`evidence` contents; Dart decoders use tolerant readers that never throw on a wrong shape | `test_ops2_*` (nested cases); widget tests + analyzer |
| Valid-JSON but malformed records never abort listing/restart (OPS-2, OPS-2R) | `ExecutionRegister.get()` returns an uncertain `RECORD_SCHEMA` stub unless the id is the file's, the state is a known state and every field the worker reads has its type (`_well_typed`) | `test_reconnect.py::test_ops2_*` |
| The ledger names the one record a task was run for (round 2, OPS-1R) | `SupervisorBridge.execute(work, context={"execution_id"})` writes the id into the task's `request_json` (durable; no authority); `corroborate()` requires `ledger.request.execution_id == record.execution_id`, session equality across record/proposal/ledger/server, and server `operation_id == task_id`; a faithful copy under another id is `LEDGER_EXECUTION_MISMATCH`. Trust limit: the register and the ledger share the local client root; a same-user process that rewrites BOTH is outside this check (same limit as the Phase 2D records). | `test_reconnect.py::test_ops1_*` (c3, c4) |
| The approval card shows the exact arguments (C6; OPS-3) | indented JSON of `approval_request.arguments` + argument digest on the card | widget test "exact arguments object verbatim" |
| Duplicate / replay | second `execution_begin` for the same turn: `TURN_NOT_PENDING` (or `EXECUTION_IN_PROGRESS`); `turn_decide` after `execution_begin`: `TURN_NOT_PENDING`; one attempt, one result file; frozen server guards unchanged | `::test_duplicate_begin_and_replay_cannot_execute_twice` |
| One execution per client at a time | `EXECUTION_IN_PROGRESS` for `turn_*`, `execution_begin`, `snapshot`, `consent`, `commit` while one runs; status/cancel/list/preflight/identity stay open | `::test_one_execution_at_a_time_everything_else_waits`, real frames test |
| No secrets in records or frames | the record holds digests, ids, the user's request text and public evidence fields; never tickets, signatures, tokens, keys | `::test_record_never_contains_secrets_or_tickets` |
| Provider choice preserved | no fallback anywhere; `quota_paused` and every failure leave the next choice to the user; an unusable harness cannot be selected | `::test_unqualified_provider_fails_closed_before_any_task`; widget tests "quota pause ...", "no executor is preselected ..." |
| Phase 2D preserved | signed client-bound records, expiry, evidence re-hash + content, launch-chain pins, per-run revalidation, native record = probed model, frozen-file protection: all unchanged (Phase 2D suite 95 -> 97 with the R3 tests) | `tests/phase2d` + `tests/phase2a/test_frozen_core.py` |

## Opt-in, not cutover

`<client_root>/control/ui-supervised-profile.json` = `{"schema": "uri.phase2ops.ui_profile.v1", "worker_profile":
"phase2d-supervised"}`. The Dart runtime reads the manifest (`interpreter`, `source_root`, `client_root`) exactly as the
frozen runtime does and starts `scripts/run_uri_supervised_worker.py` from the pinned source root. No manifest field,
launcher, shortcut, scheduled task or port changes; the frozen `PairedRuntimeScreen` still starts the frozen worker. The
opt-in file cannot enable fixture qualification; only the live test harness (`SupervisedWorkerRuntime.spawn(extraArgs:)`)
passes `--allow-fixture-qualification`, and `fromManifest` never does. Removing the file removes the entry.

## Deliberate limitations (NOT IMPLEMENTED / NOT VERIFIED)

* An execution does not outlive its worker. The worker is the UI's child (frozen C1 contract); closing the UI closes
  the worker, which withdraws the execution (job kill, record `uncertain`). A detached execution service would be a
  Core/launcher change (C7 territory), not this slice.
* After a server restart the cached runner generation is stale (frozen behaviour); the worker reports `uncertain`
  for an in-flight execution and the UI must reopen (new worker). Tested only as "server unreachable at settle".
* `execution_status` includes the server's own view only when the server is reachable; otherwise
  `server_turn.error` is reported, never assumed.
* The human finger on the real Flutter button is NOT VERIFIED: the Dart live test drives the real widget code's
  runtime, and widget tests drive the real screen with a fake worker; the physical click is DEFERRED (user physical
  presence required). It does not block this slice; it is part of the owner's acceptance before cutover.
* Native execution inside the real worker PROCESS still needs the CLI authenticated in the client profile
  (Phase 2D limit, USER INTERACTION REQUIRED). The real Codex lifecycle and cancel ran in-process under the shell's
  run-scoped authentication, exactly like the Phase 2C/2D evidence.
* Physical power loss: unchanged, NOT VERIFIED (SIMULATED abrupt termination only).
* Chat (`/ask`) is not moved to the paired runtime: C6 owner decision 2 is still open; the slice wires the real UI through
  a dedicated Tasks entry/screen, which is what the C6 contract allows without that decision.
