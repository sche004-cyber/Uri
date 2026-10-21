# Milestone Manager — acceptance criteria (frozen before design)

Written 2026-10-21 before the architecture was chosen, as required by the repository's Verification-First standard.
Every criterion names how it is checked. "Test" means an automated pytest in `tests/dev_workflow/test_milestones_*.py`.

## Research and design (deliverables 1-5)

| ID | Criterion | Check |
|---|---|---|
| R1 | Existing URI capabilities (Lifecycle V3 driver, AO-4 state manager, scheduler, memory/task stores, Graphify, P0 registers, Antigravity prototype) are mapped with file:line or path evidence | DISCOVERY doc review |
| R2 | At least two viable persistence architectures are compared on durability, concurrency, crash recovery, git-friendliness, dependencies and cost | ARCHITECTURE doc |
| R3 | One architecture is recommended with plain-language trade-offs | ARCHITECTURE doc |
| R4 | Schemas for milestone, task, decision, dependency, review, approval, evidence and checkpoint are defined | DATA_MODEL doc |
| R5 | Integration boundaries with Lifecycle V3/V3.1, Mission Control, Skill Command Center, Session Launcher, Capability Registry and harnesses are written, with one owner per kind of state | ARCHITECTURE doc |
| R6 | Migration from `developmental.md`, `decisions.md`, lifecycle state dirs and git receipts preserves provenance and never deletes the source; markdown stays authoritative until promotion | DATA_MODEL + IMPLEMENTATION_PLAN; importer tests |
| R7 | Confirmed facts are separated from assumptions | doc review |

## Implementation (functional)

| ID | Criterion | Check |
|---|---|---|
| F1 | Append-only event store; no command rewrites or deletes an earlier event | test: file prefix unchanged after any command |
| F2 | Each event is hash-chained; `verify` detects an edited, deleted, reordered or inserted event | test (tamper cases) |
| F3 | A torn last line (power loss mid-write) is detected; reads ignore it and report it; `recover` moves it to quarantine without losing the complete events | test |
| F4 | Concurrent writers are serialised by an OS file lock released on process death; N parallel processes appending M events each produce N*M events and a valid chain | test (multiprocess) |
| F5 | Optimistic concurrency: an update with a stale `--expect-version` is refused with a CONFLICT error and nothing is written | test |
| F6 | Milestone assignment is a lease: a second agent cannot take an unexpired assignment; an expired one may be taken over and the takeover is recorded (amended 2026-10-21: was "task claim"; task leases belong to Lifecycle V3.1) | test |
| F7 | Evidence-integrity guard: ACCEPTED needs an independent review (reviewer differs from implementer) with ACCEPT / ACCEPT WITH FINDINGS bound to the exact commit; PENDING/RUNNING/FAILED/... result classes never satisfy a positive state | test |
| F8 | INTEGRATED needs a recorded owner integration approval and an integration record naming the target commit | test |
| F9 | Owner approvals are recorded only with a source reference and the owner's own words; an agent cannot mark its own request approved without them; approval records carry the assurance class | test |
| F10 | Decisions are never overwritten: supersede and correct create new events linked both ways; the original text stays readable | test |
| F11 | Dependencies: cycles are refused; a milestone is "ready" only when all its dependencies are ACCEPTED, INTEGRATED or DONE; the ready list is computed (amended 2026-10-21: was "task") | test |
| F12 | Status indicators GREEN/BLUE/YELLOW/RED/WHITE are derived (not stored), each with accessible text, phase, issue and next action | test |
| F13 | `resume` (including Lifecycle V3.1 task summaries when available, read-only) answers the seven continuity questions for a milestone in bounded output (size limit) | test |
| F14 | Importers for `developmental.md` roadmap/capabilities and `decisions.md` keep source path, commit (when given), line and file SHA-256; re-import is idempotent; a changed source row is recorded as a new revision, never an overwrite | test |
| F15 | Lifecycle link/sync reads a Lifecycle V3 state dir read-only, verifies its event chain, and records stage, blocker, candidate and verdict with hashes | test (fixture state dir built by the real driver helpers or a byte-identical sample) |
| F16 | Secret-like strings (API keys, tokens, private keys, passwords) are refused in any free-text field | test |
| F17 | State is always derived from the verified log; no cache is trusted (amended 2026-10-21 after review R1-02/06/08: was "projection cache is disposable; incremental rebuild") | test |
| F18 | `status --json` has a versioned, documented schema for Mission Control and other consumers | test |

## Non-functional

| ID | Criterion | Check |
|---|---|---|
| N1 | Python standard library only; no new dependency, model, service or paid API | import scan test |
| N2 | Does not modify `lifecycle.py` or any frozen/protected path (`scripts/ws_frozen_check.py` passes) | gate |
| N3 | 10,000 events: full rebuild < 3 s and `status` < 1 s on the owner PC class; store < 10 MB | perf test (recorded) |
| N4 | Works on Windows (owner PC) and POSIX | tests run on Windows; POSIX lock path covered by code review |
| N5 | Existing `tests/dev_workflow` suite shows no new failures versus base `ec2fab54` | gate (baseline vs candidate) |

## Lifecycle

| ID | Criterion | Check |
|---|---|---|
| L1 | At least one independent review (fresh isolated subagent qualifies, owner amendment 2026-10-21) returns ACCEPT or ACCEPT WITH FINDINGS on the exact final commit, with no open blocking finding | review records under `docs/milestone_manager/reviews/` |
| L2 | Every repair is re-reviewed | review records |
| L3 | All work committed on the isolated branch; handoff lets a new session resume without chat history | HANDOFF doc |
| L4 | No canonical integration without separate owner authorisation and reconciled P0 prerequisites | integration readiness section |

## Amendment log

| Date | Change | Reason |
|---|---|---|
| 2026-10-21 | F6, F11, F13 rescoped from tasks to milestones; tasks read via `uri-dev/task-ledger-contract/1` | ownership split agreed with the parallel Lifecycle V3.1 session (`v1-2e`); avoids two sources of truth for tasks |
| 2026-10-21 | F17 amended: no projection cache | review R1 showed a cache that guards read can be forged or stale; full verified fold measured at 0.3 s for 10k events (N3) |
| 2026-10-22 | F5 clarified: a refused command writes nothing of its own; when the write first finds an unrecorded ledger loss, that loss is recorded on its own (LEDGER_LOSS_RECORDED) and the command is not executed | review R13-03; architecture §25 |
