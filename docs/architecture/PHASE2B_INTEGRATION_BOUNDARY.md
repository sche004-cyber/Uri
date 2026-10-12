# URI Phase 2B: Core <-> Supervisor integration boundary, architecture

Status: IMPLEMENTED CANDIDATE, TESTED (automated), NOT QUALIFIED with a real executor, NOT FROZEN. Uncommitted, local
only. Built on the Phase 2A candidate (`evidence\phase2a-candidate-20261007.zip`,
SHA-256 `c0b82fa040a52c3e829e4951c1e89d7bffa1c0576bf362ffdfbef51e8314751c`) over the frozen Phase 1 Core
(`final-closure-20261005-phase1.zip`, SHA-256 `31a34dcb...defeb98cf7`, base commit `e8e3b65`).

## Governing plan and the discrepancy to report

No standalone "Phase 2 plan" document exists in the repository. The governing Phase 2 text is
`docs/architecture/PHASE2A_ARCHITECTURE.md` (boundary diagram: `[integration seam, NOT wired]`; "Core integration
(approval verification before `submit_task`, UI routes) is deliberately not done: it would require editing frozen
files") and `docs/plans/PHASE2A_REPORT.md` section K ("Wiring needs edits to frozen files and your decision").
The next slice is therefore the Core <-> Supervisor integration boundary, as expected. The discrepancy: Phase 2A
assumed the wiring needs frozen-file edits. It does not. The frozen client runtime already exposes the two seams
this slice needs (`TurnRunner._validate_ticket`, invoked by the execution journal, and `TurnRunner._run_harness`),
so the boundary is a pure composition layer. No frozen file was modified.

## Where authority comes from and where it goes

```
User text ---> IntentDiscovery (frozen) ---> CONFIRMED intent, confirmed_digest
          ---> PairedCoordinator (frozen): gates, approval_digest = H(turn, op, capability, args_digest, intent_digest)
          ---> explicit user approval ---> ExecutionTicket signed by the server key (frozen C4 control: prepare)
          ---> client: journal.intent(ticket) -> online claim (dispatch authorized) -> journal.acknowledge
          ---> [Phase 2B] SupervisedTurnRunner._run_harness
                 verify_authority(signed ticket, approval_request, reasoning)  -> AuthorizedWork
                 SupervisorBridge.execute(work)                                 -> (outcome, evidence, failure)
          ---> frozen _execute builds the ExecutionReceipt -> journal.settle -> server settle (frozen) -> reply
```

The bridge consumes authority; it never creates, widens or reinterprets it:

| Property | Mechanism |
|---|---|
| Only confirmed/approved work reaches `submit_task` | `_run_harness` runs after the server claim; the only input is the signed ticket the frozen runner already verified; `verify_authority` re-verifies it (`verify_ticket`: signature, binding, generation, 60 s window, argument digest) |
| Confirmation is bound to the task, not a boolean | `approval_digest` is recomputed from turn, operation, capability, argument digest and the confirmed intent digest and must equal the ticket's; `digest(arguments) == ticket.argument_digest` |
| Stale/replayed confirmation cannot authorize changed work | edited arguments -> `ARGUMENT_DIGEST_MISMATCH`; other intent -> `APPROVAL_DIGEST_MISMATCH`; old generation/window -> `TICKET_REFUSED`; the frozen server guards (`INTENT_STATE_STALE`, `INTENT_ALREADY_EXECUTED`, `INTENT_EXECUTION_UNCERTAIN`) run before any ticket exists |
| Corrections rebind authority | frozen: a correction bumps the intent revision and invalidates `confirmed_digest`; the approval digest changes, so no earlier ticket matches |
| Abandoned/cancelled intent cannot execute | frozen: no ticket is issued; declined approval never reaches the bridge (tested: zero tasks in the ledger) |
| Executor selection cannot widen permissions | `reasoning.provider` is the user's explicit selection (exact policy rows); the bridge requires the Phase 1 `HarnessRegistry.selectable(provider)` (installed, authenticated, qualified, no fallback) AND a supervisor executor registered under that exact id AND that the binary the supervisor runs is the very file the registry qualified (`EXECUTOR_BINARY_MISMATCH` otherwise; D-B3); the authorization scope carries `allowed_executors=[provider]`, so admission can never choose another |
| Supervisor failure mid-run is uncertainty, not retry | a `LedgerError` after dispatch (busy, disk full, refused invariant) returns `execution_uncertain` (`SUPERVISOR_ERROR:<code>`) after closing the ticket's authority as far as the ledger allows |
| Retry/resume cannot gain authority | the task has ONE authorization row derived from the ticket (`[issued_at, deadline)`); retries are admitted against the same `auth_id` (tested); RESUME is bounded by the same row |
| Crash recovery preserves authority constraints | the supervisor's startup recovery decides; then the bridge revokes every still-open authorization and fails QUEUED/RETRY_SAFE leftovers (`AUTHORITY_REVOKED_RESTART`); nothing is re-launched (matches Phase 1 `ExecutionJournal.recover`) |
| Duplicate effects prevented | `task_id == operation_id` (UNIQUE): the same ticket can never create a second task (`DUPLICATE_OPERATION` -> `execution_uncertain`); Phase 2A fencing/absence proofs cover the attempt level |
| Failure stays failure despite success-shaped metadata | Phase 2A rules + URI-observed postcondition (`file_regular_nonempty`); `verified` only from ledger `COMPLETE` |
| Outcomes distinguishable | COMPLETE -> `verified`; UNCERTAIN/NEEDS_USER -> `execution_uncertain` (`SUPERVISOR_<state>:<reason>`); clean quota -> `quota` (frozen `_quota_wait`); never started -> `failed` with `NOT_STARTED:` (frozen server closes it, explicit retry allowed); anything else -> `failed` (frozen server: dispatched + failed = `execution_uncertain`) |
| Restart does not turn uncertain into new authority | revoked authorization + a user `retry` decision in the ledger stays un-admittable (tested); a new ticket is the only way forward |
| Identifier injection | task id / principal are canonical UUIDs validated by the frozen `Binding`; provider `^[a-z][a-z0-9_]{0,63}$`; model `^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$` (fullmatch); expected file is a bare safe name; instruction travels on stdin only; session ids validated by Phase 2A before any resume argv |
| Supervisor cannot mutate confirmed intent | the bridge imports no intent/session/approval API (structural test); it returns a receipt triple and nothing else; the frozen server supplies the post-execution session |

## Packages and files

```
uri_supervisor_bridge/            new (third package; imported by neither uri_core nor uri_supervisor)
  authority.py                    verify_authority -> AuthorizedWork; BridgeRefused codes
  bridge.py                       SupervisorBridge: ledger under <client_root>/control/supervisor, pools, registrations,
                                  execute(), settlement mapping, restart revocation
  runner.py                       SupervisedTurnRunner (overrides _validate_ticket, _run_harness only), SupervisedTurnService
tests/phase2b/                    authority, unit (real supervisor + synthetic tickets), e2e (real paired server),
                                  restart (child-process crash points), boundary, fail-closed extras; SYNTHETIC fake harness
uri_supervisor/admission.py       Phase 2A edit: admit_next(only_task_id=None)
uri_supervisor/supervisor.py      Phase 2A edit: admit_next passthrough of only_task_id
uri_supervisor/postconditions.py  Phase 2A edit: checker `file_regular_nonempty` (Phase 1 harness_output_check semantics)
tests/phase2a/test_frozen_core.py Phase 2A edit: ALLOWED_NEW gains the Phase 2B paths
```

## Ledger mapping for one harness task

`submit_task(task_id=operation_id, principal=principal_id, request={public ids and digests; NO instruction text},
authorization={scope: {allowed_op_classes: [read, local_write], allowed_executors: [provider], workspace: <run dir>,
ticket_digest, approval_digest, argument_digest}, issued_by: "uri_core.execution_ticket", valid_from_us: issued_at,
valid_until_us: deadline}, effects=[local_write on the fresh run directory], postconditions=[file_regular_nonempty on
<run dir>/<expected_file>], requirements={capabilities: [harness_task], executors: [provider]}, max_attempts=2)`.
Pools: `harness_slot` (capacity 1) plus one claimed quota pool per provider (`quota_<provider>`), so a quota breaker on
one provider never blocks the user's explicit choice of another. When `execute` returns, the task's authorization is
closed (`issued_by=uri_supervisor_bridge`, empty validity) and QUEUED/RETRY_SAFE leftovers are FAILED
(`BRIDGE_SETTLED_<why>`): a settled ticket never leaves re-admittable work.

## Deliberate limitations

* The approval-digest recomputation duplicates the server formula in `paired_coordinator`. If the server changes it,
  the bridge fails closed (`APPROVAL_DIGEST_MISMATCH`), never open.
* The declared postcondition is "regular non-empty output file" (Phase 1 semantics). Any non-empty content satisfies
  it; "partial" content in the declared file is indistinguishable from success for this task type, exactly as in
  Phase 1. Side effects elsewhere in the workspace make the task NEEDS_USER; effects outside the workspace are visible
  only to the executor's own sandbox (Phase 2A K).
* `quota` (clean pause) requires: quota decision, every effect proven absent by fingerprint, and no executor tool
  activity in any attempt. This is stricter than Phase 1's `tool_calls == 0`, never weaker.
* Worker/UI composition (`SupervisedTurnService`) exists but no launcher uses it; the frozen worker still composes
  the Phase 1 `TurnService`. Switching is a cutover decision, not part of this slice.
