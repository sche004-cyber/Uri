# Milestone Manager — architecture

Date: 2026-10-21. Inputs: `MILESTONE_MANAGER_DISCOVERY.md`, `ACCEPTANCE_CRITERIA.md`.

## 1. Role in one paragraph

Milestone Manager (MM) is URI's development-time project registry. It owns **project-level** state: the roadmap,
milestones, milestone dependencies and blockers, decisions, milestone acceptance/integration evidence references,
review verdict records on milestones, owner approval records, milestone assignment and milestone handoff notes. It
does **not** run work and does **not** own task state.

Coordination correction (2026-10-21, after a message from the parallel Lifecycle V3.1 session `v1-2e`, branch
`milestone/lifecycle-v3-1-task-intelligence-20261021`): the first draft of this design also kept tasks, task claim
leases, task checkpoints and task evidence. Lifecycle V3.1 owns exactly those (task ids `TASK-...`, task context and
evidence, execution transitions, review/acceptance gates, checkpoints, leases, recovery). Keeping both would create
two sources of truth, so MM now reads tasks only through the V3.1 read contract `uri-dev/task-ledger-contract/1`
(`python -m scripts.dev_workflow.task_ledger summary --milestone <ref> --json`) and never writes task state. V3.1
stores the MM milestone id as an opaque `milestone_ref`. Lifecycle V3 keeps owning execution of one milestone run (stages,
reviewer launch, gates, integration push). MM links to lifecycle runs and records read-only, hash-verified snapshots
of them. Mission Control (future) reads MM; Skill Command Center (future) owns skill qualification and only links
its records to MM tasks.

## 2. Persistence alternatives compared

| Criterion | **A. Hash-chained JSONL event log in a git-trackable folder** (recommended) | B. SQLite (WAL, `synchronous=FULL`) with append-only event table (scheduler pattern) | C. Keep Markdown registers only | D. Write into scheduler / OI TaskLedger |
|---|---|---|---|---|
| Durability after power loss | fsync per append; torn tail detected and quarantined | very good (SQLite journal) | depends on editor; no detection | good |
| History / never overwrite | inherent (append-only file, chain) | needs triggers (as scheduler does) | manual discipline | partial |
| Tamper evidence | per-segment chain + git history when committed | chain in table; binary file not diffable | none | scheduler yes, OI no |
| Concurrency on one PC | OS file lock (msvcrt/fcntl) released on process death; optimistic version checks | `BEGIN IMMEDIATE` | none | engine lock = one process |
| Multi-machine / cloud sessions | one segment per host; git merges never conflict textually; semantic conflicts detected by versions | binary DB cannot be merged; needs export/import | text merges conflict | no |
| Review by humans and agents | readable JSON lines, diffable in git | needs a tool | readable | needs a tool |
| Query speed at 10k events | fold ~0.1-0.5 s, cached projection | fastest | n/a | fast |
| Dependencies | stdlib | stdlib | none | runtime package import |
| Code size | ~1 small store module | similar | none | coupling cost |
| Domain fit | development records | development records | yes | **no**: runtime product state (MM-F9) |

Decision: **A**. In plain words: an append-only diary of small JSON lines is easy to keep in git, easy to read, and
cannot silently lose old entries; the folder lock and fsync give the safety SQLite would give, at our tiny volume.
SQLite (B) stays a fallback: if event volume ever makes the fold slow, a SQLite *projection cache* can be added under
`cache/` without changing the authoritative log. C fails continuity and integrity needs. D crosses the runtime /
development boundary.

## 3. Components

```
scripts/dev_workflow/milestones/
  store.py      EventStore: segments, OS lock, fsync append, torn-tail detection, chain verify, recover, git autocommit
  model.py      constants, validation, secret refusal, reducer (event -> projection), guards
  service.py    Manager: one method per command; validates against the projection *inside* the lock, then appends
  views.py      indicators, status board, ready list, resume brief, JSON export (schema uri-mm-status/1)
  importers.py  decisions.md, developmental.md, Lifecycle V3 state dirs (read-only)
  cli.py        `python -m scripts.dev_workflow.milestones <command>`
```

Ledger home (data, not code): a directory chosen by `--home` or `URI_MM_HOME`:

```
<home>/mm.json                 config: schema, host id, autocommit flag
<home>/events/<host>.jsonl     authoritative, append-only, hash-chained segment (one per host)
<home>/cache/projection.json   disposable fold cache (offsets + state); safe to delete
<home>/quarantine/             torn tails moved here by `recover`
<home>/.lock                   OS lock file (contents irrelevant)
```

Recommended deployment: `<home>` is a dedicated git worktree (for example orphan branch `ledger/milestones`), so every
append can be committed locally (`autocommit: true`) and pushed for off-machine durability only with owner approval.
Promotion of a ledger to authoritative is an owner decision (see implementation plan, phase 5).

## 4. State model

- **Events** are the only truth. Each event: `{v, seg, seq, ts, actor, session, kind, data, base, prev, hash}`;
  `hash = sha256(canonical JSON of all other fields)`; `prev` = previous hash in the same segment (genesis 64 zeros).
- **Projection** = deterministic fold of all events ordered by `(ts, seg, seq)`. Entities carry a `version` that
  increments on every event touching them.
- **Status indicators are derived**, never stored: RED (open blocker, unresolved conflict, lifecycle BLOCKED/WAITING)
  > YELLOW (open owner approval request, lifecycle BLOCKED OWNER_AUTHORIZATION) > GREEN (INTEGRATED, DONE) > WHITE
  (PLANNED, PAUSED, CANCELLED, SUPERSEDED) > BLUE (IN_PROGRESS, ACCEPTED). Same legend as `developmental.md`.

## 5. Integrity rules enforced in code (positive-claim guards)

| Claim | Required evidence (checked when the status is set) |
|---|---|
| milestone `ACCEPTED` | a review on that milestone, verdict ACCEPT or ACCEPT WITH FINDINGS, `blocking_open = 0`, commit equal to the milestone's `candidate_commit`, reviewer identity different from every implementer actor recorded on the milestone, result class `COMPLETED_WITH_RESULT` |
| milestone `INTEGRATED` | an APPROVED owner approval of kind INTEGRATION for the milestone, and an integration record naming the target commit and that it contains the candidate |
| milestone `DONE` | no approval request open, no blocker open, and status already ACCEPTED or INTEGRATED |
| approval `APPROVED`/`DENIED` | the owner's own words and a source reference; assurance `OWNER_RELAYED` (the recording agent is named) |
| decision text | never edited; `supersede` and `correct` add events and links both ways |

PENDING, RUNNING, FAILED, KILLED, TIMED_OUT, CANCELLED, NO_OUTPUT and BLOCKED result classes are stored but never
satisfy a guard (CLAUDE.md Evidence Integrity Rules).

## 6. Concurrency and multi-agent coordination

| Concern | Mechanism |
|---|---|
| Two processes write at once | exclusive OS lock on `<home>/.lock` around read-projection + validate + append; the OS releases it if the process dies (no stale lock files) |
| Lost update | `--expect-version N`: refused with CONFLICT when the entity moved |
| Milestone ownership (prevents duplicate milestone work, DEC-073) | `assign` writes a lease (agent, session, worktree, expiry); another actor is refused until release or expiry; takeover after expiry is recorded with `takeover_of`. Task-level leases belong to Lifecycle V3.1 |
| Two machines edit the same entity offline | each writes its own segment; after a git merge the fold sees two events built on the same base version and records a **conflict** (RED) until `resolve` |
| Review independence | review records name reviewer kind and id; the ACCEPTED guard refuses a reviewer that is also an implementer actor of the subject. Lifecycle V3 remains the place where independence is *verified* for driver reviews; MM records the class (`DRIVER_VERIFIED`, `SUBAGENT`, `SESSION`, `OWNER_ATTESTED`, `UNVERIFIED`) |
| Parallel worktrees | milestone records carry worktree and branch; `ready` lists milestones whose dependencies are met and that have no open blocker, approval request or live assignment by another actor |
| Handoff | `handoff` records done / next / files / commit at milestone level; `resume` prints the brief for the next agent and includes the V3.1 task summaries when that tool is present |

## 7. Session continuity

A new session runs `python -m scripts.dev_workflow.milestones resume <MILESTONE> --home <home>` and gets a bounded
brief (default 6,000 characters) answering:

1. What was requested? (objective, acceptance criteria reference)
2. What has been completed? (milestone status, V3.1 tasks ACCEPTED/INTEGRATED, evidence ids)
3. What evidence exists? (id, kind, result class, path, SHA-256)
4. What was rejected and why? (REJECT/REVISE reviews, superseded decisions, rejected alternatives)
5. What remains unfinished? (open V3.1 tasks, open blockers, unmet dependencies)
6. What is safe to do next? (next action, ready milestones, V3.1 task next actions)
7. What requires owner approval? (open approval requests)

plus the last handoff note and the linked lifecycle run stage. Recovery scenarios:

| Event | What happens |
|---|---|
| Context or quota exhaustion | nothing is lost: every recorded step is already fsynced; the next session runs `resume` |
| Session killed mid-command | lock released by OS; either the event was fully written (fsynced line) or not at all, or a torn tail exists |
| Power loss mid-append | torn tail ignored by reads, reported by `verify`, quarantined by `recover`; earlier events intact |
| Projection cache corrupted | `rebuild` (or automatic on parse failure) refolds from events |
| Harness or agent replaced | identity is a recorded string; claims expire; the new agent claims after expiry or release |
| Worktree deleted | MM stores commits and paths; `verify-evidence` reports missing files and SHA mismatches |
| Partial implementation | the last checkpoint names files and commit; lifecycle link shows the run stage |

## 8. Integration boundaries (one owner per kind of state)

| Kind of state | Owner | MM role |
|---|---|---|
| Roadmap, milestones, milestone dependencies, next actions, blockers, assignment | **MM** | authoritative (after promotion) |
| Tasks, task context/evidence, task checkpoints and leases | **Lifecycle V3.1 task ledger** | reads `summary --json` (contract `uri-dev/task-ledger-contract/1`); never writes |
| Decisions (DEC-NNN) | **MM** (after promotion; `decisions.md` until then) | import, supersede, correct |
| Owner approvals | **MM** record of the owner's words; lifecycle `authorized` flag for the push itself | MM records; lifecycle enforces |
| Lifecycle run stage, rounds, gates, findings, integration push | **Lifecycle V3** | link + read-only snapshot (`sync-lifecycle`) |
| Review verdict on a run | Lifecycle V3 (driver) or imported review file | MM stores a reference + class |
| Lifecycle V3.1 (in development in parallel) | task execution | MM consumes its summary contract; V3.1 never writes MM state |
| Mission Control (P6) | visualises and coordinates | consumes `status --json` (schema `uri-mm-status/1`); writes only through MM commands |
| Skill Command Center (P7) | skill qualification records | links a qualification to an MM task by id; no duplicate task list |
| Session Launcher | starts sessions | passes milestone id; new session calls `resume` |
| Capability Registry (runtime Core) | product capabilities | untouched; MM may reference capability ids as text |
| Harnesses (Claude, Codex, subagents) | do the work | write through CLI with `--actor`; never edit segments by hand |
| URI runtime stores (scheduler, OI, supervisor, Core) | product | untouched |

## 9. User experience

- `status` prints one line per milestone/task: indicator emoji **and** a text word (accessible without colour),
  phase, issue, next action. Example: `🟡 OWNER ACTION | P0-MILESTONE-MANAGER | phase INTEGRATION | issue: approval
  AP-3 integration authorisation | next: owner decides AP-3`.
- Owner decisions come first in the output; routine reviews appear only as counts unless `--verbose`.
- `status --a2ui` maps indicators to `uri_a2ui` Badge tones (GREEN=success, BLUE=accent, YELLOW=warning,
  RED=danger, WHITE=neutral), so a later Mission Control can reuse the lifecycle surface pattern. No Flutter screen
  is required for MM to be useful (owner requirement H). Stage 8 UI qualification: MM is classified INTERNAL
  (development tooling, no user-facing URI capability).

## 10. Security and privacy

- Free text is refused if it matches secret patterns (API keys, tokens, private keys, `password=`-style pairs).
- Evidence is stored as path + SHA-256 + summary, never file contents.
- No network access, no model calls. Git push is never done by MM.

## 11. Resource expectations

Stdlib Python only; one process per command; no daemon. Expected: ~300-500 bytes per event; 10,000 events ≈ 4-5 MB;
full fold ≈ sub-second; memory < 50 MB. Measured values are recorded in the implementation evidence (criterion N3).

## 12. Self-review (criteria R2, R3, R5)

- R2 met: four options compared on durability, history, tamper evidence, concurrency, multi-machine, readability,
  speed, dependencies, size, domain fit.
- R3 met: recommendation and plain-language reason in §2.
- R5 met: §8 gives one owner per kind of state.
- Gap found and repaired while drafting: the first draft let MM set a milestone INTEGRATED from a lifecycle snapshot
  alone. That would make MM re-decide a lifecycle outcome and bypass the owner record; §5 now requires the owner
  approval record as well.
- Remaining limitation (stated): tamper-evident, not tamper-proof; someone able to rewrite a whole segment can rebuild
  a consistent chain. Git commits of the ledger and the head hashes printed by `verify` are the anchor.
