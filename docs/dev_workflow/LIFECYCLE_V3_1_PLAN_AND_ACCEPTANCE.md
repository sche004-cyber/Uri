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
| Review & acceptance (amended 2026-10-21, see section 6) | `review-record` takes the reviewer's raw output file, re-parses the `AUDIT_RESULT` block with V3's own `parse_review`/`effective_verdict`, binds the exact commit, stores raw sha256 + provenance; reviewer must differ from every implementer actor; `accept` needs an independent ACCEPT/AwF on the task's current head and no open blocking finding; a new head invalidates acceptance |
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

## 5. Amendment (owner, 2026-10-21): runtime context continuity beyond the 32K window

Received while stage 1 (the development ledger, `b12d6582`) was being implemented. Unlike stages 1-4, this part
changes the URI runtime answer channel, so the milestone is now **INDIRECT** for this part (no new screen; the
user-visible effect is that long conversations keep working). The criteria below were written when the amendment
arrived, after the research map and before the code; they were not defined before stage 1.

### 5.1 Research: what existed (ec2fab54, verified file:line by a read-only research pass)

| Mechanism | State | Reused? |
|---|---|---|
| Live prompt builder `uri_operational_intelligence/answer.py:build_messages` | live; sent only the last 12 messages, no token check | extended |
| History `worker_bridge.py` `self.history` (24 messages, memory only) | live; lost on worker restart (CONTEXT-1) | kept; durable transcript added beside it |
| Measured usage `worker_bridge.py:_sink` (`prompt_n + cache_n + predicted_n`) | live; used only by the profile-shrink guard | reused for calibration and near-overflow detection |
| Profile window `runtime_profiles.describe(cfg)["ctx"]`, host profile | live | reused for `n_ctx` (smaller of the two) |
| `--ctx-checkpoints`, `--cache-ram`, stable-prefix layout (`answer.py:13-14`) | live (frozen argv) | reused: compaction keeps the prefix byte-stable between rollovers |
| `uri_core/core/context_budget.py` (`chars // 4`), `context_trimmer.py`, `conversation_history.py`, Graphify index, evidence/experience stores | frozen, legacy path only | not reused: frozen (`scripts/ws_frozen_check.py`), not on the WS path, and a fixed `chars//4` has no feedback: in the CC-1 simulation (a pessimistic 2.6 characters per token) it overflows the 32K window at turn 32, while the calibrated estimator never does. The real Qwen ratio was not measured here |
| Profiles with a bigger window | 64K only without Vision (P2); 64K+Vision (P1) unqualified; every change reloads the model | not used: continuity must not reload or raise VRAM |

### 5.2 Design

`uri_operational_intelligence/context_continuity.py` (new, not frozen), wired at `answer.build_messages` and
`worker_bridge` (`transcript=` path under the client's `control/oi/conversation/`), launcher passes it.

- **Monitoring.** Budget = `n_ctx` - answer `max_tokens` (tier) - 512 margin - fixed messages (system, memory
  evidence, current turn) - images x 1536 (per image, Qwen-VL scale) - 8 tokens per message. Characters per token
  start at 3.0, are used at 90 %, and are calibrated from each answer's measured `prompt_n + cache_n` (fast towards
  denser, slow towards sparser; persisted). A measured prompt + answer above 85 % of the window forces a rollover on
  the next turn. A server "exceeds the available context" reply before any text triggers one forced rollover and
  one retry.
- **Checkpoint before exhaustion.** The user turn is written (write-ahead) before the Brain is asked; every rollover
  writes a checkpoint record (boundary, through-turn, report) before the compacted prompt is sent.
- **Compaction.** Rollover when verbatim history would exceed 55 % of the free budget; keep the newest turns within
  30 % (hysteresis, so the prefix changes rarely). Turns before the boundary become one deterministic block: PINNED
  turns (user instructions, constraints, decisions, approvals; draft evidence) verbatim, else excerpts, else index
  lines; then a one-line digest of every other turn. Counts of everything excerpted, indexed or omitted are in the
  report and in the `answer.done` metrics (`metrics.context`); omission is announced inside the block.
- **Retrieval.** Earlier turns relevant to the current request (IDF-weighted word overlap) are placed verbatim
  (up to 1500 characters each, 12 % of the budget) just before the current turn, after the stable prefix.
- **Vision and VRAM.** No profile change, no reload, no new model, no GPU work; images are budgeted when present.

### 5.3 Criteria and evidence (tests/oi/test_context_continuity.py)

- CC-1 Over 300 simulated turns (> 128K cumulative tokens, tokenizer denser than the default estimate), no prompt
  plus reserve exceeds 32K; with no measurements at all the estimate alone stays inside the window.
- CC-2 Every rollover is checkpointed before the compacted prompt is used.
- CC-3 Pinned instructions/decisions/approvals from turns 3, 57, 151, 260 are all in the final prompt; under pinned
  overflow, excerpts/index lines are used and every pinned turn is accounted for (shown or counted as omitted).
- CC-4 A fact from a compacted, unpinned turn is retrieved verbatim for a related question; the original is stored.
- CC-5 Between rollovers the compacted prefix is byte-identical (prompt-cache reuse); no reload occurs.
- CC-6 Images reduce the budget by their token estimate; a current turn that cannot fit is reported, not sent.
- CC-7 Repeated rollover (>= 3 in 300 turns) with hysteresis (< 1 per 5 turns).
- CC-8 A restarted store composes the identical context and keeps the calibration; a crashed turn is kept and marked
  interrupted.
- CC-9 Compose latency and memory over 4000 stored messages are measured and bounded.
- CC-10 Through the real worker bridge and answer channel (fake llama-server): an 8K window over 31 long turns stays
  inside the budget, keeps a pinned instruction, records `metrics.context`, and a restarted worker continues from
  the transcript; a server overflow reply is retried once after a forced rollover; without a transcript path the
  bridge behaves as before.

Not verified here (stated, affects the live part of the verdict): a long conversation against the real Runtime v1
Brain (GPU) and through the Windows UI. The Brain was not running in this session (`/health` unreachable) and the
GPU is shared with concurrent milestones; live recovery accuracy with the real tokenizer is therefore NOT VERIFIED.

## 6. Review mechanism clarification (owner, 2026-10-21)

Owner: the existing Lifecycle V3 independent review mechanism stays primary and preferred; independent Claude or
Codex subagents are valid fallback reviewers only when it is unavailable or cannot operate; nothing replaces,
duplicates or bypasses it; fallbacks never weaken acceptance standards.

**Inspected (ec2fab54).** `lifecycle.py`: `reviewer_chain` (preferred `reviewer` then `reviewer_fallbacks`,
`INDEPENDENT_PROVIDERS = claude_cli, codex_cli`), `select_reviewer` with bounded attempts derived from the chain,
`is_independent` (bound CLI, driver-made config, containment, distinct session, integrity), escalation: every
reviewer UNAVAILABLE/FAILURE -> BLOCKED `NO_INDEPENDENT_REVIEWER` (self-rechecked next run, `REVIEWER_RECHECK`);
unusable results -> BLOCKED `NO_REVIEWER` (owner). `import_review` is never independent (D1). The tier-3 subagent
mechanism inside the driver exists only on the unintegrated branch `67d45317` (Q-3) and is not duplicated here.

**Verified gap, corrected.** The first ledger version (`b12d6582`) let `accept` use a subagent review exactly like a
driver review. Now: a DRIVER_VERIFIED verdict on the head is decisive (a later fallback ACCEPT cannot override a
driver REJECT); a fallback verdict counts only with a fallback basis read from a linked driver run's intact chain
(current blocker `NO_INDEPENDENT_REVIEWER`, run candidate = task head), recorded in the ACCEPTED event; and every
path needs a passing test result with its log on the exact head (gap found in self-review: the first version did
not require it). Tests: `test_fallback_needs_exhausted_chain_on_the_exact_commit`,
`test_driver_verdict_is_never_overridden_by_a_fallback`, `test_ac8_*`.

**This milestone's own review** follows the same order: the V3 driver with Codex (`gpt-6-sol`, probed 2026-10-21:
model probe and sandbox `git rev-parse HEAD` in the candidate both returned) as primary, `claude_cli` as in-driver
fallback (logged out on 2026-10-21), and a fresh read-only subagent only if the driver ends `NO_INDEPENDENT_REVIEWER`.

## 7. Review history (auditable; corrections kept)

| Round | Reviewer / path | Commit | Verdict | Outcome |
|---|---|---|---|---|
| r1 R1 | Lifecycle V3 driver, `codex_cli` `gpt-6-sol`, DRIVER_VERIFIED independent (session `codex_cli-430c1cf0`) | `5ee7e5c7` | REJECT, 6 blocking | All 6 reproduced by the reviewer and confirmed by the coordinator (below) |
| r1 P1 | driver repair worker (`codex_cli`) | from `5ee7e5c7` | — | REFUSED and rolled back: `TAMPER: git hooks or config changed during the repair`. Cause verified: `.git/info/refs` of the shared repository was rewritten at 16:55:25Z (git maintenance by a concurrent session; config and hooks unchanged). Canonical `git_control_digest` hashes `.git/info/*`; the fix (digest v2 ignoring `info/refs`, `info/packs`) exists only on unintegrated Q-3 `67d45317` and is not duplicated here. The r1 run stays BLOCKED TAMPER (an owner-kind block; not unblocked by the coordinator). |
| manual repair | coordinator | `5ee7e5c7` -> next commit | — | R1-01 provenance derived only (DRIVER_VERIFIED only from `sync_v3`); R1-02 an over-budget prompt is never sent (`CONTEXT_TOO_LARGE`, user-facing message, also before the overflow retry); R1-03 a pass needs its log and acceptance re-hashes the log of the latest TEST on the head; R1-04 every task-row string redacted (milestone_ref, branch); R1-05 answer row and turn state in one transaction; R1-06 a repeated keyed item becomes current again (CONTEXT_RESTORED event). Seven regression tests fail on `5ee7e5c7` and pass after the repair. |
| r2 R1 | driver, `codex_cli`, DRIVER_VERIFIED | `831f9cdc` | REJECT (R2-01..R2-04); R1-01..R1-06 FIXED | driver repair P1 `b013daf1` |
| r2 R2 | driver, `codex_cli`, DRIVER_VERIFIED | `b013daf1` | REJECT (R2-05..R2-08) | driver repair P2 `69c96143` |
| r2 R3 | driver, `codex_cli`, DRIVER_VERIFIED | `69c96143` | REJECT (R3-01..R3-05); R1-04, R2-07, R2-08 NOT_FIXED | driver repairs P3-P5 refused (regression, implementer failure); run BLOCKED REPAIR_FAILED (manual repair) |
| manual repair P6 | coordinator | `69c96143` -> next commit | — | class fixes instead of instances: one redaction choke point for every SQL parameter (`_RedactingDB`; secret-bearing worktree paths and lease names refused) for R1-04/R2-01/R2-05/R3-01; compaction tiers keep every user turn ahead of URI's text, assistant drafts labelled EVIDENCE (context, never instructions), omitted user turns named as ranges, standing-instruction cues pinned (R2-07/R3-02/R3-04); `verify()` replays status, commits, milestone_ref, findings and steps from the chain (R3-03); acceptance rechecks the driver's raw reviewer output hash like `lifecycle.verify` (R2-08/R3-05). Regression tests `test_r3_*` fail on `69c96143` (6 of 8; the other two are a redaction-idempotence property and a continuity check) and pass after. |
| r3 | driver, `codex_cli` then `claude_cli` | `ac9143e1` (P6 merged with canonical `9488c0fd`) | no result | BLOCKED `NO_INDEPENDENT_REVIEWER`: codex_cli QUOTA (resets 2026-10-22 03:19 IST), claude_cli AUTH; fallback basis for this exact commit |
| r3 fallback R1 | fresh isolated subagent (owner clarification 2026-10-21), driver reviewer prompt, read-only checkout; recorded with `task_ledger review` as SUBAGENT_FALLBACK, raw output `D:/uri-dev/lifecycle/LIFECYCLE-V3-1-r3/fallback/R1_subagent_ac9143e1.txt` | `ac9143e1` | REJECT (FB R1-01..R1-05 blocking, R1-06 LOW); all 19 earlier findings FIXED | — |
| self-found while recording | coordinator | `ac9143e1` | — | the reviewer reused ids `R1-0x` that it also listed as FIXED prior findings, so `record_review` closed the findings it had just opened (live ledger showed 0 open blocking after a REJECT). Same class as FB R1-03. |
| manual repair P7 | coordinator | `ac9143e1` -> next commit | — | every decision (accept, unblock, resume, integrated) first replays the task's chain and refuses on any mismatch; replay covers resume_to and every finding column and flags entries into ACCEPTED/INTEGRATED without their events (FB R1-01, R1-02); resume/unblock targets restricted; review findings namespaced `<review>/<id>`, a review never closes its own findings, and a FIXED claim closes earlier review findings only for a decisive review (fallback basis, development not paused), never owner/developer findings (FB R1-03, self-found); more secret formats (Basic auth, CLI password flags, pass/pwd keys, hf_, pypi-, Stripe, GitLab, npm, Azure keys) (FB R1-04); a recent turn above 25 % of the free budget is shown as an excerpt so a refused oversized request no longer blocks the next turn (FB R1-05); a new head voids an acceptance of another commit in every status (FB R1-06). Seven `test_fb_*` tests fail on `ac9143e1` and pass after. |
| r4 R1-R4 | driver, `codex_cli` (after the quota reset), DRIVER_VERIFIED | `49eb6485`, `ef61e265`, `462fda7a`, `d7be6e89` | REJECT x4 (FB-R1-04, R4-01..R4-08); every earlier finding FIXED by R4 | driver repairs P1 `ef61e265`, P3 `462fda7a`, P4 `d7be6e89` committed; P2, P5 refused (regressions); run BLOCKED TAMPER: `.git/info/refs` rewritten again at 22:30:04Z inside the P5 window (same false positive as r1; fix only on Q-3 `67d45317`) |
| manual repair P8 | coordinator | `d7be6e89` -> next commit | — | projection SEAL: after every write transaction the digest of all projection rows of each touched task (task row, findings, reviews, context, steps, V3 links, its leases, availability) is chained as a SEAL event; the first use of a sealed task in a write transaction must match its last seal (otherwise refused, never re-sealed: a self-found laundering hole, where the next write would have sealed an outside edit); packet and handoff use the same O(rows) check; decisions additionally replay the whole chain. Closes the class behind R3-03, FB R1-01, R4-02..R4-05, R4-08 for any column of any table. R4-06 quoted/separated CLI passwords; R4-07 uncommitted changes refuse acceptance. `recover` and pause skip and report tampered tasks. Legacy ledgers are sealed once on open. 12 of 26 `test_r4_*` fail on `d7be6e89` (the other 14 cover cases the driver's per-column repairs had closed). Bench 1000 events: 2.86 ms/event (V3 6.69), packet 10-14 ms, 1.09 MB vs V3 0.46 MB (one SEAL per write). |
| r5 | driver (Codex primary) | P8 commit | pending | `D:/uri-dev/lifecycle/LIFECYCLE-V3-1-r5` |

Known limitation (stated, not hidden): under extreme length a compacted block cannot hold every user turn. Turns the
classifier recognises are kept first (verbatim, then excerpt, then index); other user turns follow, newest first; every
omitted user turn is named by number in the prompt and in `metrics.context.omitted_user_turns`, and its full text stays
retrievable. In the 300-turn CC-1 simulation, 165 of 285 compacted unclassified user turns are shown as index lines and
120 are named as omitted; all four planted instructions are kept verbatim.
