# LIFECYCLE V3.1 — Persistent Task Intelligence (roadmap P1, lifecycle half)

Milestone of the development lifecycle (`scripts/dev_workflow/`). Classification: **INTERNAL** (development tooling;
no URI runtime or UI change, so no Stage 8 live UI qualification applies). Boundary: development tooling only, never
imported by the URI runtime.

Baseline: canonical `integration/git-sync-20261008` @ `ec2fab5493578a4f5a805642153d56b4d5ea59fa` (verified with
`git fetch uri-repo` on 2026-10-21; matches the P0 audit baseline). Branch
`milestone/lifecycle-v3-1-task-intelligence-20261021`, worktree `D:/uri-dev/uri-lifecycle-v31`.
Concurrent work not touched: Ember V2.1 integration, URI Controls (`milestone/uri-controls-3-20261021`), Milestone
Manager (`milestone/milestone-manager-20261021`).

## 1. Problem (verified on ec2fab54)

Lifecycle V3 (`lifecycle.py`) keeps one hash-chained `events.jsonl` + `state.json` per *milestone run directory*.
Measured gaps:

| Gap | Evidence |
|---|---|
| No task identity: a run is named by its config file; each revision (`-r1`..`-r12`) is a new directory with no shared id | `D:/uri-dev/lifecycle/` holds 33 run dirs for 6 milestones |
| Context lives in chat and memory notes; a new session re-derives objective, decisions, findings and next action | P0 register `developmental.md` exists because nothing persistent does |
| `State.event` re-reads the whole `events.jsonl` on every append and rewrites `state.json` each time (O(n) per event) | `lifecycle.py:240-256` |
| Two writers on one run dir can interleave appends (no lock) | `State.event` opens the file in append mode without a lock |
| No record of an in-flight step, so an interrupted step is indistinguishable from one never started | no STEP event kind |
| Handoffs are hand-written (`AUDIT_HANDOFF.md`) and only exist on the unintegrated tiers branch | `67d45317` |

## 2. Design (ODRD)

**Range considered.** (a) event sourcing on JSONL files (V3's model), (b) SQLite transactional state machine with an
append-only, hash-chained event table, (c) an external workflow orchestrator (Temporal/Prefect class), (d) a context
cache built on embeddings. Chosen: **(b)**, with deterministic retrieval. Reasons: Python's stdlib `sqlite3` gives
atomic multi-row transactions, a cross-process lock and WAL crash safety with zero new dependencies; (c) adds a
server and a dependency for a single-machine developer; (d) needs a model/GPU and makes retrieval non-reproducible.
JSONL stays the format of V3 runs, which are linked and imported, never rewritten.

**One module** `scripts/dev_workflow/task_ledger.py` (+ CLI). Store: one SQLite file outside every worktree
(`URI_TASK_LEDGER`, default `~/.uri-dev/task_ledger.sqlite3`), `journal_mode=WAL`, `synchronous=FULL`,
`busy_timeout`. Every write is one `BEGIN IMMEDIATE` transaction.

| Concern | Mechanism |
|---|---|
| Task identity | `TASK-YYYYMMDD-<8 hex>` assigned once and stored; imports get a deterministic `TASK-V3-<12 hex>` from the source chain's first hash (idempotent re-import) |
| Events | per-task append-only `events` table, `seq` contiguous, `prev`/`hash` chained exactly like V3 (`sha256` of seq/ts/kind/data/prev); task row = projection with a `version` |
| Status machine | `OPEN, IN_PROGRESS, IN_REVIEW, REPAIR, ACCEPTED, INTEGRATED, INTERRUPTED, PAUSED, BLOCKED, ABANDONED`; explicit transition table; optimistic `expected_version` |
| Context continuity | `context` table: kinds objective/requirement/constraint/decision/progress/evidence/commit/test/finding/issue/next_action/note; content-addressed (`UNIQUE(task, sha)`) dedup; `key` supersession; optional `path`+`blob` or `commit` binding; `expires_at` |
| Retrieval | deterministic packet under a character budget: fixed sections first (objective, constraints, decisions, open findings, next action, last verified commit, latest tests), then evidence ranked by query-term overlap and recency; long items compressed to an excerpt plus a sha pointer (`context-get`) |
| Cache | `packet_cache` keyed by (task version, parameters, worktree HEAD, dirty fingerprint), TTL; any event bumps the version, so stale packets are never served |
| Invalidation | at retrieval: path-bound items re-hashed (`git hash-object`), commit-bound items checked with `git cat-file -e`; mismatch = STALE, excluded and counted |
| Sensitive data | `redact()` on every string entering the ledger (events, context, reviews, handoffs): key/token/private-key/password patterns; secret-bearing paths (`.env`, `*.pem`, `id_rsa*`, `credentials*`) refused as context |
| Crash safety | SQLite transaction = no partial record; `step-start` writes intent before work, `step-end` closes it; `recover` turns open steps and active tasks whose session lease expired into `INTERRUPTED` (never completed); worktree HEAD/dirty drift recorded as `WORKTREE_DRIFT`; atomic file exports (`tmp` + `replace`), stray `.tmp` cleaned |
| Concurrency | `BEGIN IMMEDIATE` serialises writers; leases: all-or-nothing multi-resource acquire in one transaction, never wait while holding (no deadlock), TTL expiry, monotonically increasing fencing token; task session lease `task:<id>` |
| GPU boundary | the ledger refuses `gpu*` lease names: GPU arbitration stays with `uri_operational_intelligence.gpu_lease` (one source of truth); a task may record that lease as evidence |
| Review & acceptance | `review-record` takes the reviewer's raw output file, re-parses the `AUDIT_RESULT` block with V3's own `parse_review`/`effective_verdict`, binds the exact commit, stores raw sha256 + provenance; reviewer must differ from every implementer actor; `accept` needs an independent ACCEPT/AwF on the task's current head and no open blocking finding; a new head invalidates acceptance |
| V3 reuse | `link-v3` + `sync-v3` read a V3 run (chain recomputed), import review rounds as `DRIVER_VERIFIED` only when V3's `accepted_review` conditions hold (independent, COMPLETED_WITH_RESULT, round.json hash bound); V3 code unchanged |
| Pause policy | `availability` records Claude/Codex availability; both unavailable → every active task `PAUSED` with checkpoint; only a `claude:`/`codex:` actor recorded available may resume; `antigravity:` and `subagent:` actors can never transition, resume or accept (reviewers may only record reviews; antigravity may only add notes/evidence) |
| Handoff | `handoff` writes `<ledger dir>/handoffs/<task>.json` + `.md`: id, status, last verified commit (git-checked), completed, remaining, blocking findings, required permissions, next executable action, chain head |
| Migration | `import-v3 <root>` discovers V3 run dirs, records each source file's sha256 before and after (unchanged proof), never writes to them |
| Milestone Manager boundary | the ledger stores only an opaque `milestone_ref`; it owns no milestone, roadmap, dependency or owner-decision state. Shared contract `docs/dev_workflow/contracts/task_ledger_contract.json` (task summary schema MM reads) |

**Trust boundary (stated, not hidden).** Actor identity is declared by the caller (`--actor kind:id`), as V3's
coordinator identity is. The ledger enforces role rules on declared identities and records them; it does not
authenticate them. Review verdicts are not caller claims: they are recomputed from the stored reviewer output.
The chain is tamper-evident, not tamper-proof (same statement as V3 `verify`).

## 3. Acceptance criteria (defined before implementation)

- AC-1 Task identity survives restart: a task created by one process is found, unchanged, by a new process;
  IDs are unique under concurrent creation.
- AC-2 Context survives session replacement: a new process (no shared memory) retrieves the same packet; objective,
  constraints, decisions, findings, commits, tests and next action are present without any chat input.
- AC-3 Interrupted work resumes correctly: an open step after a killed process becomes `STEP_INTERRUPTED` and the
  task `INTERRUPTED`; nothing interrupted is ever `ACCEPTED`/`INTEGRATED`; resume continues from the recorded
  checkpoint.
- AC-4 Concurrent tasks do not corrupt shared state: N processes appending to the same and different tasks leave
  contiguous seqs and intact chains; competing lease acquisitions give exactly one holder; a killed writer
  mid-transaction leaves no partial record.
- AC-5 Stale cache is invalidated: a changed bound file, a missing bound commit, an expired item, a new event, or a
  new worktree HEAD each make the next retrieval fresh and mark the item STALE where applicable.
- AC-6 Sensitive data never reaches task records: seeded keys/tokens/private keys/passwords are absent from the
  SQLite file bytes and handoff files; secret-bearing paths are refused.
- AC-7 Existing Lifecycle V3 reviews still work: the unchanged V3 suite passes; a V3 run with an independent
  ACCEPT imports as DRIVER_VERIFIED, a non-independent/imported round never does; source files byte-identical.
- AC-8 Independent subagent acceptance works: a subagent review output on the exact head commit accepts the task;
  same reviewer as implementer, wrong commit, REJECT, or a blocking finding each refuse acceptance.
- AC-9 Existing integrations unaffected: no file outside `scripts/dev_workflow/task_ledger.py`, its tests, docs,
  contract and the lifecycle SKILL.md text changes; frozen-file check (`scripts/ws_frozen_check.py`) unchanged.
- AC-10 Recovery requires no reconstruction from chat: `handoff` alone yields the next executable action, last
  verified commit, blocking findings and permissions; it is produced from the ledger only.
- AC-11 Pause policy: both developers unavailable pauses active tasks; antigravity/subagent actors cannot resume,
  transition or accept; an available developer can resume.
- AC-12 Performance: no GPU, no new dependency; append latency and retrieval latency measured against the V3
  `State.event` baseline at equal event counts and reported with numbers.
- AC-13 At least one independent reviewer verdict on the exact final commit; blocking findings repaired and
  re-reviewed.

## 4. Out of scope / owned elsewhere

Milestone registry, roadmap, dependencies, owner decisions, `developmental.md` import (Milestone Manager). Reviewer
tiers 3-5 mechanism inside the V3 driver (Q-3 `67d45317`, not integrated). Canonical integration (owner approval).
