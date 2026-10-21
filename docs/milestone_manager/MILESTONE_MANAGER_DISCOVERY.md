# Milestone Manager — discovery

Date: 2026-10-21. Base: canonical `ec2fab54` (fetched from `uri-repo` on 2026-10-21; the local ref
`integration/git-sync-20261008` is stale at `348677b7` and was not used). Method: ODRD (altitude, depth, range,
speed, efficiency). Evidence classes: **FACT** = read in code, git or a committed record at the cited location;
**REPORTED** = taken from a document, receipt outside git or memory note and not re-checked; **INFERENCE** = my
judgement.

## 1. Question

How can URI keep its whole development state (milestones, tasks, decisions, evidence, reviews, owner approvals,
dependencies, unfinished work) so that it survives context exhaustion, quota exhaustion, session or harness changes,
restarts and power loss, without a second source of truth beside Lifecycle V3?

## 2. What exists (capability map)

| # | Mechanism | Location | What it holds | Strength | Gap for project-level tracking |
|---|---|---|---|---|---|
| E1 | Lifecycle V3 driver | `scripts/dev_workflow/lifecycle.py` (2410 lines) | per-run `state.json`, hash-chained `events.jsonl`, `rounds/`, `repairs/`, `gates/<sha>/`, `receipt.json`, `RECEIPT.md`, `REPORT.html` (FACT, `lifecycle.py:227-257`, `URI_DEVELOPMENT_LIFECYCLE.md` §5) | exact-SHA review binding, independence checks (`is_independent` `:353`), verdict recomputation (`effective_verdict` `:340`), baseline-aware gates, integration gate with `authorized` + `expected_target_tip` (`integrate` `:1597`), resume from the chain (`_chained_events` `:1046`) | one run = one config = one `state_dir`; no cross-run registry, no dependencies, no next action, no decisions, no project roadmap (FACT, LC-7 in P0 evidence 50). Revisions create new state dirs (`-c`, `-u<n>`), so a milestone's history is spread over many dirs (FACT: `D:/uri-dev/lifecycle/LIFECYCLE-REVIEWER-TIERS-r1..r12`) |
| E2 | Lifecycle write safety | `lifecycle.py:103` `write_json`, `:253` event append | atomic tmp + replace for JSON | — | no `fsync`, no file lock, `seq` from `len(history)`; a crash between the event append and `save()` makes `verify` report TAMPER (FACT for the code; consequence INFERENCE). Two concurrent `run`s on one state dir are unprotected (FACT: no lock in the module) |
| E3 | AO-4 state manager | `scripts/dev_workflow/state_manager.py` | Markdown `docs/plans/<id>_STATE.md`, `RecoveryState` (`:100`: required model, resume stage, completed/remaining steps) | recovery-packet idea | Markdown parse, not used by lifecycle.py (FACT) |
| E4 | P0 registers | `D:/uri-dev/uri-p0-audit` branch `audit/p0-comprehensive-20261021` @ `8e1d6324` (local, not pushed): `developmental.md` (354 lines), `decisions.md` (159 lines, DEC-001..DEC-090, OPEN-01..OPEN-10) | capability inventory, roadmap, defects, next actions, decisions with provenance classes | the best current picture; explicit append/correct rules | hand-maintained Markdown; not on canonical; not machine-checkable; "interim until P1 Milestone Manager" (FACT, `developmental.md:3-5`) |
| E5 | Older ledgers | `URI_MILESTONE_TRACKER.md`, `PROJECT_MEMORY.md`, `docs/governance/URI_ACTIVE_MILESTONE.md` | prose | — | stale since `925ad45c` (2026-10-08); stop at Phase 1 / M33 (FACT, `git log`; finding DOC-1) |
| E6 | Scheduler store | `uri_scheduler/store.py` | SQLite WAL, `synchronous=FULL`, `BEGIN IMMEDIATE`, append-only hash-chained `event` table enforced by triggers, sha-bound owner `review` table (FACT, `:22-74`, `:96-98`, `:144`) | best crash-safe pattern in the repo | product runtime store, one principal, own process lock; wrong domain to write development records into (INFERENCE) |
| E7 | OI TaskLedger | `uri_operational_intelligence/task_ledger.py` | per-task JSON, temp + fsync + replace (`:55-62`), owner lock (`:75`), steps with `depends_on`, `recover()` marks in-flight steps UNCERTAIN (`:250`) | crash-safe writes, dependency notion, restart recovery | runtime request tasks, not development milestones; must not be duplicated (INFERENCE) |
| E8 | Supervisor ledger | `uri_supervisor/ledger.py` | SQLite WAL ledger, checked `transition()` (`:217`), epochs/watermark recovery | transaction discipline | not hash-chained; runtime domain |
| E9 | Core stores | `uri_core/...` approval_store, growth_ledger, experience, user_memory, sessions | JSON, plain `open("w")` | — | not crash-safe; do not copy (FACT for the write calls) |
| E10 | Graphify | runtime `uri_core/core/graphify_index.py` (pointers to capabilities/skills/workflows/memory/services); dev skill `.agents/skills/graphify` | runtime index has an authority boundary and no document ingestion; the dev skill can graph Markdown/JSON | — | no `graph.json` built in this checkout (FACT: `graphify-out/` holds only detect files); runtime index is the wrong layer for development records (INFERENCE) |
| E11 | A2UI | `uri_a2ui/catalog.py:37-40` `Card`/`Badge` tones; lifecycle status surface `lifecycle.py:2302-2327` | semantic tones neutral/accent/success/warning/danger | ready-made status surface | no colour names; five indicators map 1:1 to the five tones (INFERENCE) |
| E12 | Antigravity "Milestone Manager V1" | `C:/Users/cheta/.gemini/antigravity/scratch/uri-milestone-manager-v1/` (outside every repo) | one `milestones_ledger.json` rewritten whole by `save_ledger`, a schema, `verify` = path-existence check | — | no history, no chain, no lock, cites non-existent commits `43224b1a`, `36395b09` (FACT, P0 evidence 50 §e and own read). Rejected as a base |
| E13 | Mission Control, Skill Command Center, Developer Studio, Session Launcher | docs only: "future / out of scope" lines (`docs/ui_v2/completion/00_COMPLETION_PLAN_AND_ACCEPTANCE.md:37`, `docs/office/unified/00_DISCOVERY_RESEARCH_AND_ROADMAP.md:20`) | — | — | no specification or code in any of 179 refs (FACT, P0 G1 grep) |
| E14 | "Lifecycle V3.1" | `docs/dev_workflow/DEV_LIFECYCLE_3B_PLAN_AND_ACCEPTANCE.md:49` | "planned V3.1 persistent task/cache architecture", cache keyed by baseline SHA + command + toolchain | — | label only (FACT) |
| E15 | Reviewer tiers 3-5 | branch `milestone/lifecycle-owner-attested-review-20261017` @ `67d45317` | session/owner-attested review | — | not integrated, no completed test run, last completed review REJECT (FACT per P0 evidence 50); canonical `SKILL.md:116-121` still says a separate Claude review is never an independent ACCEPT (finding POL-P0-1) |

Reviewer availability 2026-10-21 (FACT, probe 16:10 UTC): `claude auth status` = `loggedIn: false`; Codex CLI
`0.158.0` installed, rate-limited until 2026-10-22 14:03 (REPORTED in P0 register). The owner's amendment of
2026-10-21 states that independent subagents qualify as reviewers for this milestone.

## 3. Findings

| ID | Finding | Evidence | Consequence for design |
|---|---|---|---|
| MM-F1 | No project-level registry exists in code in any ref | P0 G1 grep; E4/E5 | build one; keep it small |
| MM-F2 | Lifecycle V3 already owns per-run execution truth (stages, reviews, gates, integration); duplicating it would create two sources of truth | E1 | Milestone Manager links to lifecycle runs and imports read-only snapshots; it never re-decides a lifecycle verdict |
| MM-F3 | The hash-chained JSONL event format is already the project's evidence idiom (lifecycle, scheduler) | E1, E6 | reuse the idea (genesis 64 zeros, sha256 over canonical JSON) |
| MM-F4 | Lifecycle writes have no fsync and no lock | E2 | Milestone Manager must add both; lifecycle fix is out of scope (recommended for V3.1, see plan) |
| MM-F5 | Much review history lives outside git (`D:/uri-dev/lifecycle/`, `uri-*-live/`) and is lost if that disk is lost | P0 register §N | the registry should be committable to git, and evidence should be recorded by path + SHA-256 so loss is detectable |
| MM-F6 | Decisions exist only as Markdown rows with collisions in old ids (OD-n, D-n) | E4 `decisions.md` rules | keep DEC-NNN as the stable id; import rows verbatim with provenance; supersede, never overwrite |
| MM-F7 | Status vocabulary GREEN/BLUE/YELLOW/RED/WHITE is already defined in `developmental.md:13-22` | E4 | reuse the same legend; derive it, never store it |
| MM-F8 | Roadmap numbering differs: `developmental.md` §C (DEC-088) lists P1 = "Milestone Manager + Lifecycle V3.1" and P11 Multi-Client; the owner prompt of 2026-10-21 for this task lists P0 = Milestone Manager, P1 = Lifecycle V3.1 ... P10 Brain Runtime Optimization and no P11 | both texts | record as a new decision row that supersedes the numbering part of DEC-088 only; P11 kept and flagged as an open question |
| MM-F9 | Runtime stores (scheduler, OI, supervisor, Core) are product state; development state must not be written into them | E6-E9 | separate development-only package under `scripts/dev_workflow/` |
| MM-F10 | Python 3.13 stdlib is the established tooling base; `sqlite3` is used in 11 non-test modules | agent survey | no new dependency is needed for either persistence option |

## 4. External technique survey (RANGE), applied

| Technique | Source idea | Adopted? | How |
|---|---|---|---|
| Event sourcing | state = fold of an append-only event log; snapshots are caches | yes | events are the only truth; projection cache is disposable |
| Hash chains / tamper evidence | each record carries the previous hash (as in lifecycle, scheduler, git) | yes | per-segment chain; `verify` |
| Write-ahead durability | write + flush + fsync before acknowledging | yes | `os.fsync` on every append |
| Torn-write recovery | a crash can leave a partial last record; databases truncate it on recovery | yes | reads ignore an unterminated tail; `recover` quarantines it |
| Optimistic concurrency control | write carries the version it read; reject on mismatch | yes | `--expect-version`; CONFLICT error |
| Leases (Chubby, Kubernetes) | ownership with expiry; takeover only after expiry | yes | task claim lease |
| Per-writer logs merged by key (CRDT-like, Git union) | each writer appends to its own file, merges never conflict textually | yes | one segment per host; cross-segment concurrent updates are detected by version, not hidden |
| Durable workflow engines (Temporal, Airflow) | replayable history, activities, retries | no | heavy services; Lifecycle V3 already is the workflow engine |
| Issue trackers (GitHub Issues, Linear, Jira) | milestones, dependencies, owners | no | remote, account-bound, paid or online; violates local-first |
| Knowledge graphs | typed edges for dependencies | partly | dependencies are explicit edges; graph export left to the dev Graphify skill, not a new store |
| ADRs (architecture decision records) | one immutable record per decision, supersession links | yes | decision events with `supersedes` / `superseded_by` |

## 5. Assumptions (not verified; each says whether it affects the verdict)

| ID | Assumption | Affects? |
|---|---|---|
| A1 | One machine (owner PC) runs most writers; cloud sessions write rarely and sync by git | design handles both; no |
| A2 | Event volume stays below ~50,000 events over the project's life | performance only; N3 measured at 10,000 |
| A3 | The owner wants the registry in git eventually (durability lesson MM-F5) | storage location is configurable; no |
| A4 | Agents relay owner approvals faithfully (an agent cannot prove the owner said something) | yes for assurance: approvals are labelled OWNER_RELAYED with source and quote, never "verified" |

## 6. Re-check of this document against acceptance criteria R1 and R7

- R1: E1-E15 cover lifecycle, AO-4, scheduler, memory/task stores, OI, supervisor, Graphify, A2UI, P0 registers,
  older ledgers, Antigravity prototype, planned components; each with a path. Met.
- R7: every row is labelled or cites code; assumptions are listed separately. Met.
- Correction made during drafting: I first planned to import lifecycle helpers from `lifecycle.py`; the survey shows
  importing it pulls in `lifecycle_providers` and `containment`, and `State.event` is coupled to `state.json`. The
  design therefore re-implements the 20-line chain check for lifecycle files instead of importing the driver.
