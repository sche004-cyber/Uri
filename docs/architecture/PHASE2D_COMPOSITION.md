# URI Phase 2D: composition and closure slice, architecture

Status: IMPLEMENTED CANDIDATE, TESTED (automated), Codex NATIVE QUALIFIED through the composition (run-scoped
authentication), NOT INTEGRATED into the frozen launchers, NOT FROZEN, NOT CUT OVER. Uncommitted, local only, on the
Phase 2C candidate (`evidence\phase2c-candidate-20261007.zip`, SHA-256 `4e812653...1840f71`) over the frozen Phase 1
Core (`final-closure-20261005-phase1.zip`, SHA-256 `31a34dcb...efeb98cf7`, base commit `e8e3b65`).

## Governing plan and what this slice closes

The Phase 2C report (section P) left five items: production policy + persisted qualification, the F-C1 session
decision, worker/UI composition with a human-approval path, Claude native qualification (blocked on login), and
power loss (plan only). Task Compiler: "stays design-only until 1-2 are done" and the placement note calls it "an
optimisation seat, not a control" with "the authority chain sufficient without it"; this slice therefore leaves it
DESIGN ONLY (no code), see `PHASE2C_TASK_COMPILER_PLACEMENT.md`.

## Chain as composed by Phase 2D

```
User text
  -> SupervisedWorkerService  (frozen worker protocol: turn_start / turn_intent / turn_decide [+approval_digest] / turn_cancel)
  -> frozen server (Phase 2 profile): IntentDiscovery -> confirmed intent digest -> approval request -> explicit approval
     -> server-signed ExecutionTicket                      (policy rows from an explicit FILE, deterministic row implied)
  -> SupervisedTurnRunner: selection bound at begin (D-C1), verify_authority (Phase 2B)
  -> SupervisorBridge: registry.selectable (Phase 1 gate) + persisted qualification (binary hash, version, MODEL pin)
  -> uri_supervisor: targeted admission, fenced attempt, kill-on-close job, raw stream, reconciliation, bounded resume
  -> receipt (verified only from ledger COMPLETE) -> journal.settle -> server settle -> reply
```

## New modules

| Module | Responsibility |
|---|---|
| `uri_supervisor_bridge/qualification.py` | Persisted qualification records (`<client_root>/control/supervisor/qualification/<provider>.json`), `build_record`/`write_record`/`load_records`, `revalidate` (executable path identity + SHA-256 + `--version` + record digest + level), `native_auth_probe` (live `codex login status` / `claude auth status`, never a login, never a credential read), `compose_client` -> Phase 1 `HarnessRegistry` qualified from evidence + pinned `ExecutorBinding`s |
| `uri_supervisor_bridge/composition.py` | Server-side explicit policy file (`<state_root>/control/phase2_reasoning_policy.json`, schema `uri.phase2d.reasoning_policy.v1`, only `client_external_harness` rows, deterministic row implied, malformed file = refuse all), `phase2_server_composition`, `build_bridge`, `compose_and_build` |
| `uri_supervisor_bridge/worker_service.py` | `SupervisedWorkerService`: frozen `TurnService` protocol over the `SupervisedTurnRunner`; `turn_decide` optionally digest-bound; `turn_cancel` for pending turns; strict frame shapes |
| `scripts/run_uri_supervised_worker.py` | Opt-in worker PROFILE: same C1 gates as the frozen worker (isolated mode, bootstrap finder, source pin, cwd, sanitized env, fixture guard, per-client mutex, key/image identity) plus a Phase 2 source finder for the two Phase 2 packages, `compose_client` under the client-profile environment, guard admits exactly the qualified executable files |
| `scripts/run_uri_phase2_server.py` | Opt-in server PROFILE: frozen bootstrap with `phase2_server_composition(policy file)` |
| `scripts/phase2d_composition_qualification.py` | REAL-executor qualification through the composition and the UI frames; persists the record only when the direct probe AND the live auth status pass |
| `scripts/phase2d_pytest.ini`, `scripts/phase2d_regression.py` | Canonical contamination-safe test scope (never recurses into `work/`, `evidence/`, rollback residue) |

Phase 2A/2B edits (not frozen): `uri_supervisor/supervisor.py` (resume guard F-C1, `request_cancel`),
`uri_supervisor_bridge/bridge.py` (`qualified_models` pin, `cancel`, `CANCELLED` settlement), `tests/phase2a/test_frozen_core.py`
(`ALLOWED_NEW` gains the Phase 2D paths). Frozen Phase 1 files changed: **none**.

## F-C1 decision: Codex session persistence vs resume

Decided from URI's requirements, not convenience:

* URI owns task/intent/execution state; the executor's thread/session id is **resumable execution metadata**. It is
  persisted only on the `attempt` row of the task that produced it (needed for safe continuation), never elsewhere.
* Reuse is bounded to one path: a `RESUME_SESSION` retry of the **same task**, under the **same authorization row**
  (admission re-checks validity, so a revoked or expired authorization blocks the resume), with the **same executor
  registration** (a re-registered executor runs fresh and the refusal is recorded as `attempt.resume_refused`), the
  **same model** (the model travels with the authorized work, never with the session), and a session id that still
  validates (`valid_session_id`, bypass tokens refused).
* Missing, stale or invalid session: Codex answers with a terminal error claim; reconciliation treats it as an ordinary
  failed attempt (`RETRY_FRESH` if budget remains, else `FAILED RETRY_BUDGET_EXHAUSTED`). It can never produce
  COMPLETE and never bypasses the authority check: fail closed or the governed retry path.
* Settled/completed tasks are never re-admitted; a supervisor restart revokes the authority and fails the leftover
  (Phase 2B rule), so a resumable thread is abandoned after a restart (new ticket required).
* Codex thread persistence in the user's own Codex store: kept (no `--ephemeral`), because resume is a qualified
  capability (Phase 2C real evidence) and URI's correctness never depends on that store (failure = retry path). This is
  the product trade-off recorded in Phase 2C F-C1; the owner may still choose `--ephemeral` later (one spec change).

Tests: `tests/phase2d/test_session_resume.py` (normal continuation, cross-task reuse, re-registration, stale session
retry path, exhausted budget, revoked authority, expired window, completed task, bridge model/auth binding, restart).

## Qualification persistence and invalidation

A record is written only by a trusted qualification run (`phase2d_composition_qualification.py`) and only when the
direct probe succeeded AND the live auth status is ok. On every load (worker start, `harness_discover`) it is
re-validated; any drift invalidates it (reported, never silently inherited):

| Drift | Result |
|---|---|
| executable missing / different file at the path | `EXECUTABLE_MISSING` |
| executable bytes changed (npm `codex.CMD` shim included) | `EXECUTABLE_HASH_MISMATCH`; the bridge also pins the hash at run time (`EXECUTOR_BINARY_HASH_MISMATCH`, no task) |
| `--version` differs | `VERSION_MISMATCH` |
| record edited by hand | `RECORD_DIGEST_MISMATCH` (file unreadable / wrong schema: `RECORD_UNREADABLE` / `RECORD_SCHEMA`) |
| `FIXTURE_ONLY` record in a production profile | `LEVEL_NOT_ALLOWED` (only `--allow-fixture-qualification`, test profile) |
| provider refused/unknown (Antigravity) | `PROVIDER_REFUSED_OR_UNKNOWN` |
| model not in the record's `models` | bridge `NOT_STARTED:MODEL_NOT_QUALIFIED` before any task |
| authentication | never persisted; live probe each time (`AUTHENTICATED` / `NOT_AUTHENTICATED` / `AUTH_UNVERIFIED`), usable only when `AUTHENTICATED` |

Schema v2 (after independent review round 1; the v1 rows above remain and add to these):

| Drift / attack | Result |
|---|---|
| record edited and its digest recomputed | `RECORD_SIGNATURE_INVALID` (Ed25519 by the client key) |
| record copied from another client, or signed by another key | `RECORD_CLIENT_MISMATCH` / `RECORD_SIGNATURE_INVALID` |
| no trust anchor supplied by the composition | `NO_TRUST_ANCHOR` |
| record older than `expires_at` (default 30 days, max 90) | `RECORD_EXPIRED` |
| evidence missing, replaced, or about another provider/version/executable/model | `EVIDENCE_MISSING` / `EVIDENCE_HASH_MISMATCH` / `EVIDENCE_CONTENT_MISMATCH` |
| payload behind an unchanged launcher shim replaced (node, codex.js, vendor binaries) | `LAUNCH_CHAIN_HASH_MISMATCH` at load; `NOT_STARTED:EXECUTOR_LAUNCH_CHAIN_MISMATCH` at run |
| a launcher name (e.g. `node`) now resolves elsewhere on the executor PATH | `LAUNCH_CHAIN_RESOLUTION_CHANGED` / `EXECUTOR_LAUNCH_CHAIN_MISMATCH` |
| native `.cmd/.bat/.ps1` launcher without a pinned chain | `LAUNCH_CHAIN_NOT_PINNED` |

Trust limit: the signing key is protected by current-user DPAPI (Phase 1 C1, same-user logical isolation). A process running
as the same Windows user can sign records; schema v2 defends against edits, copies, stale evidence and payload replacement,
not same-user malware. OS-loader DLLs outside the pinned directories and programs the executor spawns are not pinned.

Codex is **not** URI's permanent Main Brain: it is one qualified `(provider, executable, model)` row the server may
offer and the client may run; the deterministic row is always offered; click-to-choose selection is unchanged.

## UI / worker composition and the human approval path

* The UI remains outside authority: it sends `turn_start`, `turn_intent` (digest-bound confirm/abandon/select) and
  `turn_decide {turn_id, approve[, approval_digest]}`; it never sees tickets, keys or private state. A frame with a
  `ticket`, `reasoning` or `arguments` key is a schema violation.
* The worker binds the approval to its own pending record (turn, session, reasoning, approval request). With
  `approval_digest` the UI must echo the digest it displayed; a mismatch drops the pending turn (`APPROVAL_DIGEST_MISMATCH`).
* Changes after approval: the server ticket carries the argument/approval digests; the bridge re-verifies the arguments
  it will run (`ARGUMENT_DIGEST_MISMATCH`); the selection is bound at begin (`AUTHORITY_SELECTION_MISMATCH`).
* Cancellation: pre-dispatch `turn_cancel` (server `APPROVAL_DENIED`, nothing runs); post-dispatch `SupervisorBridge.cancel`
  (job kill, no re-admission, `execution_uncertain`); worker death propagates through the kill-on-close job.
  The single-threaded worker protocol exposes no mid-run cancel frame (NOT IMPLEMENTED, documented).
  [Superseded by the UI/operations slice: `execution_begin` dispatches in a worker thread and `execution_cancel` is a
  real mid-run cancel over the same protocol (job kill, `uncertain`); see `PHASE2OPS_UI_OPERATIONS.md`. This line is
  kept as history.]
* Duplicate execution on reconnect/retry: pending state is memory-only (worker restart -> `TURN_NOT_PENDING`); a second
  live worker on the same client is refused by the frozen per-client mutex; the frozen server guards
  (`INTENT_ALREADY_EXECUTED`, `INTENT_EXECUTION_UNCERTAIN`, unique operation id -> `DUPLICATE_OPERATION`) hold.
  Known frozen-server property: a dropped `approval_required` turn holds its session (`TURN_CAPACITY`) until the server
  expires it (15 min idle / 60 min absolute); the user continues in a new session meanwhile.
* The frozen UI (`paired_runtime.dart`) is byte-identical and still spawns the frozen worker. Connecting it to the
  supervised worker needs either a UI change or a manifest/launcher change: both are cutover items (C7), not done.
  [Superseded by the UI/operations slice: the real Flutter UI now reaches the supervised worker through NEW files
  (`uri_ui/lib/services/supervised_runtime.dart`, `uri_ui/lib/screens/tasks/supervised_execution_screen.dart`, mounted
  from `uri_ui/lib/app.dart`) behind an explicit per-installation opt-in file; the frozen UI files are still
  byte-identical and the frozen worker is still what the frozen screen starts. Still NOT a cutover.]

## Test scope (contamination control)

`scripts/phase2d_pytest.ini` (`norecursedirs = work evidence uri_workspace ...`) and `scripts/phase2d_regression.py`
(explicit `--ignore` list, three suites: `phase2`, `authority`, `phase1-full`). Preserved evidence and rollback
residue are never collected and never deleted.

## Deliberate limitations

* Real native execution **inside the worker process profile** needs the CLI to be authenticated **in the URI client
  profile** (`HOME`/`USERPROFILE` = `<client_root>/home`, by the frozen sanitized environment). Forwarding the user's
  global `CODEX_HOME` would be "shared client authentication", a C7 stop condition, so it was not done. The real Codex
  composition evidence therefore ran the same composition in-process under the shell environment (run-scoped auth),
  exactly like Phase 2C. USER INTERACTION REQUIRED: `codex login` once in the client profile.
* Claude Code: `claude auth status -> loggedIn:false`; no record is persisted; the path fails closed with zero tasks.
* Power loss: SIMULATED abrupt termination only (`tests/phase2d/test_abrupt_termination.py`); physical power loss and
  OS write reordering NOT EXECUTED (plan unchanged).
* Executable pin covers the npm shim, not node or the package it starts (Phase 2C limit unchanged). [Superseded by
  schema v2 after independent review round 1: the launch chain (node, codex.js, package files, vendor binaries) is pinned
  and re-checked at load and before every run. Remaining limit: OS-loaded libraries outside the pinned directories,
  programs the executor spawns, and a check-to-spawn file swap (no immutable handle) are not covered.]
* Qualification validity is re-established before EVERY execution (record bytes unchanged since composition, signature,
  expiry, evidence, launch chain, version), not only at worker start (independent review round 2, R2-1). A native record
  qualifies exactly the one probed model (R2-2); fixture evidence must name the models it covers. [Since the UI/operations
  slice (independent review round 3, R3-1/R3-2): fixture evidence MUST carry `models`, a list equal to the record's; a
  missing or malformed list is `EVIDENCE_CONTENT_MISMATCH`, never a start-up crash and never a wider fixture set.]
