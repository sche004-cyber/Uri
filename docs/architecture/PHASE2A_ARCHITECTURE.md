# URI Phase 2A: Durable Task Supervisor, architecture

Status: candidate, uncommitted, local only. Built on the frozen Phase 1 Core checkpoint
`final-closure-20261005-phase1.zip` (SHA-256 `31a34dcb...defeb98cf7`, base commit `e8e3b65`).
Nothing in `uri_core`, `uri_harness_adapters` or `uri_ui` was modified or imports the new package.

## Boundary

```
User intent -> URI Core (frozen, authority) -> [integration seam, NOT wired] -> uri_supervisor
                                                      |
        Durable Task -> Admission -> Fenced Attempt -> Effect Intent -> Effect/Evidence
                    -> Reconciliation -> Verified State -> Snapshot / Narration
```

`uri_supervisor` is a library. Core integration (approval verification before `submit_task`, UI routes) is
deliberately not done: it would require editing frozen files. The seam is `Supervisor.submit_task(...)`: the caller
must be Core code that already holds a confirmed, in-scope authorization. Phase 2A records and re-checks that scope
(op classes, executors, workspace, validity window) but cannot authenticate an approval itself.

## Modules

| Module | Responsibility |
|---|---|
| `schema.py`, `ledger.py` | SQLite ledger, WAL + `synchronous=FULL`, `BEGIN IMMEDIATE` transactions, append-only tables, invariant triggers, checked state transition, authority clock |
| `admission.py` | Resource pools, versioned executor registrations, atomic multi-claim admission, round-based aging, reservation, leases, circuit breakers |
| `supervisor.py` | Task intake, intent declaration, fenced spawn, stream recording, preemption, startup recovery, lease reaping, human decisions, re-examination |
| `recovery.py` | One reconciliation procedure for every attempt end (clean, crashed, interrupted) |
| `winproc.py` | Named kill-on-close Job Object per attempt, process identity (pid + creation time), identity-checked termination |
| `executors.py`, `stream.py` | Declarative executor specs (data), byte-level NDJSON splitter, declarative event rules |
| `postconditions.py` | URI-observed checks (file, hash, git, command, external reconciler, terminal success) and pre-attempt fingerprints |
| `snapshot.py`, `narration.py` | Bounded deterministic manager snapshot; evidence-grounded, mechanically verifiable narration |
| `crashpoints.py` | Inert-by-default deterministic crash injection used by the qualification tests |

## Task states

`QUEUED` (pre-admission, needed for the queue) then `RUNNING`, `RECOVERING`, and one of `COMPLETE`, `RETRY_SAFE`,
`UNCERTAIN`, `FAILED`, `NEEDS_USER`. `RETRY_SAFE` re-enters admission. Detailed reasons live in `reason_code`,
`recovery_decision` and `uncertainty` rows, not in the state vocabulary. `RESUME` is a decision action, `COMPENSATE` is
an effect, neither is a state.

| From | To | Requirement (enforced by trigger) |
|---|---|---|
| QUEUED | RUNNING | atomic admission (attempt, admission, claims, fence) |
| RUNNING | RECOVERING | attempt fenced |
| RUNNING / RECOVERING | COMPLETE | completion record: every required postcondition's latest result is PASS with `uri_verified` evidence (or a read-only task's clean terminal claim) |
| RECOVERING | RETRY_SAFE / FAILED / UNCERTAIN / NEEDS_USER | one recovery decision per (task, attempt) |
| RETRY_SAFE | RUNNING | new admission, new fencing token |
| UNCERTAIN | NEEDS_USER | escalation only, releases nothing |
| UNCERTAIN / NEEDS_USER | COMPLETE / RETRY_SAFE / FAILED | `uri_observed`/`uri_verified` evidence about the effect recorded AFTER entering the state, or a recorded user decision |

## Attempt sequence (each step its own FULL-durability transaction)

1. `admit`: attempt row (its id is the fencing token), admission, all claims, task to RUNNING.
2. `declare_intents`: one `effect_intent` per declared effect, with parameter hash, idempotency key, class, and a
   pre-attempt fingerprint for `local_write`.
3. `SPAWNING`: refused by trigger without admission, intent, held claims and current fence (rules A, B).
4. Spawn suspended into a new named job, record pid + creation time + job name, only then resume.
5. Stream: raw complete lines persisted first, interpretation in the same transaction, tails kept as incomplete.
6. Attempt ends; reconcile: fence, inspect process, re-derive terminal and session evidence from raw lines, evaluate
   postconditions by fresh observation, classify effects, decide, commit decision + state + claim release + breaker
   feedback atomically.

## Effect classes and recovery outcomes

| Class | Absent / ambiguous evidence | Outcome |
|---|---|---|
| read | always safe | RETRY_SAFE |
| idem_write | retry only with the original key and equal params (trigger) | RETRY_SAFE, action RETRY_SAME_KEY |
| local_write | pre-attempt fingerprints of declared paths equal now: absence proven. Otherwise unproven | RETRY_SAFE or NEEDS_USER |
| external | reconciler FOUND: never repeat; keyed: retry with same key; unkeyed or unreachable | UNCERTAIN / NEEDS_USER |

## Clocks

Leases use monotonic deadlines valid only in the epoch that wrote them. A restart begins a new `scheduler_epoch`;
old claims are never expired by deadline, and keep consuming capacity until recovery proves the attempt dead. Validity
decisions (grants, provider reset times) use an authority clock with a persisted high-water mark, so a wall-clock step
back cannot revive an expired authorization. Queue aging counts admission rounds, not time.

## Temporal model

Events: `occurred_at_us`, `recorded_at_us`, immutable, ordered by `seq`. Versioned facts (`executor_registration`,
`authorization`): `valid_from_us`, `valid_until_us` (half-open), `recorded_at_us`, `superseded_at_us`, with
`registration_as_believed()` for bitemporal reads. Corrections are new rows. All instants are UTC microseconds; tasks
keep the user's IANA `timezone` string.
