# LIFECYCLE-V3.1-STORAGE: post-integration cleanup, development memory, test supervision

Plan and acceptance criteria (written before implementation, CLAUDE.md Verification-First standard).

| Field | Value |
|---|---|
| Milestone | `LIFECYCLE-V3.1-STORAGE` (`developmental.md` P.9, owner decision DEC-098, 2026-10-22) |
| Scope source | P.9 scope, widened by the owner prompt of 2026-10-22 ("Post-Integration Lifecycle & Memory Optimization": cleanup, development memory, test supervision) |
| Baseline | canonical `uri-repo/integration/git-sync-20261008` @ `8ff6186b7c42bc4e8f997ba38b4581dc9fc5a20e` (verified with `git fetch` on 2026-10-22) |
| Candidate | branch `milestone/lifecycle-v31-storage-20261022`, worktree `D:/uri-dev/uri-lc-storage` |
| Task ledger | `TASK-20261022-d2ba3338` (`~/.uri-dev/task_ledger.sqlite3`) |
| Capability class | `INTERNAL` (developer tooling; no URI user UI). It is verified by tests, a sandbox rehearsal and a read-only dry run on the real machine. There is no Stage 8 UI journey, because nothing in `uri_ui` or the URI runtime changes. |

## 1. Discovery summary (evidence: canonical `8ff6186b`)

What already exists and is reused, not rebuilt:

| Need | Existing mechanism (reused) |
|---|---|
| Persistent task knowledge across sessions | `scripts/dev_workflow/task_ledger.py`: SQLite ledger with hash-chained events and a `context` table. Rows carry `path`+`blob` and `commit_sha`. `packet()` gives budgeted retrieval with staleness detection (`_freshness`) and a verified `packet_cache`. It also has `redact()`, `is_secret_path()`, `record_test()`, resource `leases`, `handoff`, `recover`. |
| Milestones, decisions, approvals, evidence | `scripts/dev_workflow/milestones/`: an append-only, hash-chained, crash-safe event store (`os_lock`, `atomic_write_bytes`, `file_sha256`), plus `resume`, `verify-evidence` and `importers.parse_decisions` |
| Process containment | `scripts/dev_workflow/containment.py`: `spawn` (Windows Job Object, KILL_ON_JOB_CLOSE), `kill_tree`, `finish` |
| Checkpoint zip and manifest pattern | `scripts/phase2close_checkpoint.py` (refuses to overwrite; per-file sha256 manifest) |

Gaps this milestone fills:

1. **No session-start brief across tasks.** `packet` and `handoff` are per task. MM `resume` is per milestone, and no authoritative MM home exists (owner decision AP-14 open).
2. **No retrieval across tasks or decisions.** There is no index over ledger rows, `decisions.md` and lifecycle receipts.
3. **The ledger has no place for lessons, failed approaches or environment limitations.** Only generic `note` and `constraint` exist.
4. **No cleanup tool.** Disk holds 100+ worktrees and many runtime materialisations. The only cleanup code is the driver's own `add_worktree`/`drop_worktree`.
5. **No evidence archive with integrity verification and restore** for lifecycle state, logs and live-run folders.
6. **Test supervision.** Driver gates buffer stdout and stderr in memory and write the log only after the process exits (`lifecycle.py:809-872`), so a log cannot be watched while the gate runs. `scripts/phase2d_regression.py` runs pytest with no timeout. `scripts/phase2close_chain.py` kills only the direct child on timeout. Neither the driver nor the chain has a duplicate-run lock. The driver re-runs every candidate gate even on an unchanged tree.
7. **The 2026-10-22 Phase 1 watcher incident** (`docs/audit/p0_20261021/P0_CLOSURE_20261022.md` Addendum L). A shell loop waited about 307 minutes for `^rc=` in a log file that the producer never wrote to, because a `sed` substitution was missing its `g` flag. The test run itself had finished at 18:07 IST. The root cause class is completion inferred from log text at a guessed path, with no timeout and no tie to the actual process.

Out of scope (recorded, not done here): driver gate-output streaming and driver evidence reuse. These are changes to `lifecycle.py` gate semantics and need their own review (follow-up LC-STORAGE-F1). `phase2close_chain.py` is not modified either, because its pass criteria are pinned evidence. Supervision is offered as a wrapper around it.

## 2. Design

Three stdlib-only modules under `scripts/dev_workflow/`, plus a small extension to the task ledger. `psutil` is used only if present (it is already declared in `requirements.txt`). No new dependency, and no protected path is touched (`ws_frozen_check` list).

### 2.1 `testrun.py`: supervised test runs

- `start --name N [--cwd D] [--timeout S] [--stall S] [--kill-on-stall] [--lock auto|none|<class>] [--reuse] [--task T --actor A] -- <cmd...>`.
  - The run starts inside `containment.spawn` (Job Object). Stdout and stderr stream to `<runs>/<run-id>/output.log` as the run goes, not buffered.
  - `run.json` is written atomically at start and on every heartbeat. It is finalised from the **actual process exit status**.
  - Final state is one of `COMPLETED` (exit 0), `FAILED` (non-zero), `TIMED_OUT` (tree killed), or `STALLED_KILLED` (no output for `--stall` seconds with `--kill-on-stall`; tree killed).
  - The final record holds `exit_code`, `duration_s` and the `log_sha256` of the closed log.
  - Default runs dir is `~/.uri-dev/runs` (`URI_DEV_RUNS`).
- `--timeout` is mandatory and has no unbounded value. The process tree is killed through the job.
- `status <run-id>` derives the state from `run.json` plus the liveness of the supervisor (pid **and** creation time, so a reused pid is not mistaken for the supervisor). The states are:
  - `RUNNING`;
  - `STALLED` (alive, no new output for the stall window);
  - `COMPLETED` / `FAILED` / `TIMED_OUT` / `STALLED_KILLED`;
  - `MISSING_MARKER` (the supervisor is gone and no final record exists, such as after a crash or reboot);
  - `NOT_FOUND`.
- `wait <run-id> --timeout S` waits on a **run id**, never on a log pattern. It returns at once for a finished, missing-marker or unknown run, and gives up after its own bounded timeout (exit code `WAIT_TIMEOUT`). This removes the incident class: a watcher can no longer wait on a file the producer never writes, and it cannot outlive the run.
- **Duplicate-run lock.** `--lock auto` takes an OS lock (`milestones.store.os_lock`, which the OS releases if the holder dies) keyed on command + working directory. A second identical run is refused with `DUPLICATE_RUN` and names the active run id. `--lock <class>` (for example `phase1`) serialises a whole class of heavy runs across trees.
- **Exact-tree evidence reuse** (`--reuse`). The reuse key is the sha256 of the argv, resolved repository identity, the working directory relative to the repository root, the git **tree** id of `HEAD`, and a digest of the complete inherited environment plus Python interpreter identity. The source tree and environment are rechecked before reuse.
  - Reuse needs a clean tree (`git status --porcelain` empty, untracked files included).
  - The earlier run must be final `COMPLETED` or `FAILED`, and its log hash must still match.
  - A reused result is reported as `REUSED` with the original run id and carries the same exit code. It never upgrades a result, and the driver's mandatory gates are not changed.
- **Environmental failure detection.** On a failed run, the tail of the log is matched against a fixed table:
  - missing module (`ModuleNotFoundError`);
  - Playwright or browser missing;
  - GPU lease refused;
  - disk full;
  - port in use;
  - `jsonschema`, per PH1-GATE-1.

  Matches are recorded as `env_failures`, so an environmental failure is visibly separated from a code failure. The exit code is never changed.
- **Ledger link.** With `--task`, a final `COMPLETED` or `FAILED` run on a clean tree is recorded with `Ledger.record_test`: commit = `HEAD`, the log path, and pass only on exit 0.
- `select --base <rev> [--head <rev>]` is advisory targeted-regression selection: tests under `tests/` and the root `test_*.py` files that import a changed module or have a changed path. It prints the list and the reason for each test. It never replaces a mandatory gate (that rule is printed with the output).

### 2.2 `devmemory.py`: development memory

The index is a **derived, rebuildable index, never a source of truth**. It is stored in `~/.uri-dev/devmemory.sqlite3` (`URI_DEVMEMORY`), uses SQLite FTS5, and has `meta.derived = true`.

- **Sources**, all read-only:
  1. task ledger (tasks, non-superseded context rows, open findings);
  2. `decisions.md` (DEC and OPEN rows, via `importers.parse_decisions`);
  3. Milestone Manager projection, when `--mm-home` or `URI_MM_HOME` is given;
  4. lifecycle `receipt.json` files under `--receipts-root`;
  5. the housekeeping archive index (cold-tier pointers).
- **Provenance.** Every item stores `source`, `ref` (task id, ctx sha, DEC id, receipt path, archive id), `commit_sha`/`path`/`blob` where known, and `confidence`. Confidence values:
  - `VERIFIED`: a hash-chained ledger row, or a receipt with `evidence_ok_for_candidate: true`;
  - `RECORDED`: a decisions.md `REPO-RECORD` or `OWNER-PROMPT` row, or an MM event;
  - `REPORTED`: `MEMORY-ONLY` or `ANTIGRAVITY-RECOMMENDATION` rows.
- **Tiers** are derived:
  - `hot`: active tasks' `next_action`, open blocking findings, open owner decisions, `constraint` and `environment` rows of active tasks, `lesson` and `failed_approach` rows;
  - `warm`: everything else indexed;
  - `cold`: superseded decisions, closed tasks' detail, archive pointers.
- **Deduplication.** The item id is the sha256 of `source|ref|text`. Identical text from several refs is stored once and keeps its other refs in `also_refs`. `stats` reports the deduplication saving.
- **Invalidation.** `refresh` stores a fingerprint per source: ledger file `(size, mtime_ns)` plus every task's `chain_head`; file sha256 for `decisions.md`, receipts and the archive index; MM segment heads. Only changed sources are rebuilt. Each refresh also records the canonical tip. Items with a `path`+`blob` are marked stale when the blob at canonical differs. Items with a `commit_sha` absent from the repository are stale. Items that are ancestors of canonical are labelled `integrated`. Stale items are excluded from `brief` and shown only by `recall --include-stale`, with the reason.
- **Sensitive data.** All text passes through `task_ledger.redact`, and rows whose path is secret-looking (`is_secret_path`) are dropped. `stats` shows the number of redactions.
- **Budgets.** `brief --budget-tokens N` (default 1200) and `recall --budget-tokens N` (default 800). Tokens are estimated as ceil(chars/4). The output states the estimate, the omitted count and how to fetch more (`recall`, `task_ledger context-get`).
- **Commands:**
  - `refresh`;
  - `rebuild`;
  - `brief`: canonical tip, active tasks with next action and blocker, open blocking findings, open owner decisions, hot lessons and environment limits;
  - `recall "<query>" [--task T] [--kind K]`: bm25-ranked, with provenance per hit;
  - `stats`;
  - `remember --task T --kind lesson|failed_approach|environment|procedure "<text>" --actor A`. This writes **to the task ledger**, the source of truth, and refreshes the index.
- **Ledger extension.** `CONTEXT_KINDS` and `PACKET_ORDER` gain `lesson`, `failed_approach`, `environment` and `procedure`. These are additive, and existing rows and tests are unaffected.

### 2.3 `housekeeping.py`: post-integration cleanup and evidence archive

Every destructive step is dry-run first, approval-gated where needed, idempotent, journalled and receipted.

- `inventory --repo R --canonical-ref REF [--root DIR ...] [--records FILE ...] --out PLAN.json`. This is a read-only dry run that writes a plan of items. Each item has an `id`, `kind`, `path`, `class`, reasons, a `fingerprint` and a proposed `action`.
- **Worktrees** (`git worktree list --porcelain`). The classes are:
  - `PROTECTED`, never acted on: the main worktree, a locked worktree, the current directory, a worktree of a non-terminal ledger task, or a branch with commits on neither canonical nor any remote.
  - `REFERENCED`, approval required: the path is cited by an authoritative record (`--records`: decisions.md, developmental.md, audit and MM docs, receipts) or by a ledger row or v3 link.
  - `DIRTY`, approval required: uncommitted or untracked changes.
  - `EVIDENCE`, approval required: it holds untracked evidence files (`receipt.json`, `events.jsonl`, `state.json`, `RECEIPT.md`, `*.junit.xml`).
  - `DISPOSABLE`: clean, unlocked, HEAD reachable from canonical or a remote ref, not referenced, idle for at least `--min-age-hours` (default 24). Action: `git worktree remove` without `--force`, so git itself refuses a dirty tree. The receipt records the restore command (`git worktree add --detach <path> <sha>`).
  - `PRUNABLE`: a registration whose directory is missing. Action: per-item `git worktree remove <path>` (§5 C-1; the global `git worktree prune` is never used).
- **Directories under `--root`** that are not worktrees (see §5 C-3: a directory holding registered worktrees is PROTECTED):
  - `ESSENTIAL_EVIDENCE`: contains evidence markers, or is referenced by a record. Never removed; it may be archived to the cold tier as a copy.
  - `CACHE`: `__pycache__` and `.pytest_cache`. Disposable and regenerable.
  - `AMBIGUOUS`: anything else.
- **Branches.** A local branch is `OBSOLETE_BRANCH` when its tip is an ancestor of canonical, it is not checked out, and it is not under the `preserve/`, `receipts/`, `audit/`, `ledger/` or `accepted/` prefixes. Action: delete the ref with `git update-ref -d <ref> <sha>` (compare-and-swap), and record the sha for `git branch <name> <sha>` restore. Tags are never touched.
- `apply --plan PLAN.json [--approve ID ...] [--classes ...]`:
  - It acts only on `DISPOSABLE`, `PRUNABLE`, `CACHE` and, when listed in `--classes`, `OBSOLETE_BRANCH`. It also acts on items the owner explicitly `--approve`s.
  - `PROTECTED` and `ESSENTIAL_EVIDENCE` items are refused even when approved.
  - An approved `DIRTY`, `EVIDENCE` or `REFERENCED` worktree is **archived first** (verified zip, below) and then removed. The archive id goes into the receipt, so the removal can be reversed with `restore`.
  - Each item is re-inventoried and its fingerprint compared before acting (`SKIPPED_CHANGED` if it moved). Removable file contents and link metadata are fingerprinted, and the source is checked again immediately before removal. Approved archive-then-remove refuses a source with links because the archive does not restore them.
  - A hash-chained write-ahead journal records `INTENT` before and `DONE` or `FAILED` after each action. For archived removals it records the verified archive and restore metadata in `ARCHIVE_READY` before removal, so crash recovery can carry the pointer forward. The receipt (`housekeeping_receipt.json` + `.md`) is written atomically and records freed bytes, restore commands and the plan sha256.
  - Re-applying a plan reports `ALREADY_DONE` items and performs nothing twice.
- `archive <dir> --to <archive root> [--label L]`:
  - writes ZIP_DEFLATED to a temp file plus `manifest.json` (per-file sha256 and size);
  - re-opens and verifies every member against the manifest;
  - `os.replace`s it into place and appends to the hash-chained `archive_index.jsonl`;
  - never deletes the source.
- `verify-archive <id|zip>` and `restore <id|zip> --to <new empty dir>`. Restore refuses a non-empty target and zip-slip paths, and checks every file hash.
- `recover` finds journal `INTENT` entries without an outcome after a crash, re-checks the real state and records `RECOVERED_DONE` or `RECOVERED_NOT_DONE`. It never repeats a destructive step blindly.

## 3. Acceptance criteria

Each criterion has a test ID. "Test" means an automated test in `tests/dev_workflow/test_lc_storage.py` unless stated otherwise.

| ID | Criterion |
|---|---|
| TS-1 | A supervised run of a passing, a failing and a crashing command records `COMPLETED`, `FAILED`, `FAILED`. The exit code comes from the process; `run.json` is final and `log_sha256` matches the log. |
| TS-2 | A run that exceeds `--timeout` is killed **with its child processes** (a grandchild that sleeps is gone afterwards) and is recorded `TIMED_OUT`. |
| TS-3 | A run with no output for `--stall` is reported `STALLED` while alive, and `STALLED_KILLED` with `--kill-on-stall`. |
| TS-4 | `status` of a run whose supervisor died without a final record reports `MISSING_MARKER`. A pid reused by another process is not treated as alive (creation time mismatch). |
| TS-5 | `wait` on an unknown id returns `NOT_FOUND` at once. On a finished run it returns at once with its state. With a short `--timeout` on a running run it returns `WAIT_TIMEOUT` within the bound. Watcher incident regression: a run whose log never contains a marker string still completes `wait` correctly, because `wait` uses the run id. |
| TS-6 | A second identical run while the first is active is refused `DUPLICATE_RUN` and names the active run. After the first ends, the lock is free (also after the holder is killed). |
| TS-7 | `--reuse` on a clean, identical tree returns `REUSED` with the earlier run id and exit code, without executing. It does not reuse when the tree is dirty, the tree id differs, the argv differs, or the earlier log hash no longer matches. |
| TS-8 | A failure log containing `ModuleNotFoundError: No module named 'jsonschema'` is classified `ENV_MISSING_MODULE:jsonschema`. The exit code is unchanged. |
| TS-9 | `--task` records the result with the ledger's `record_test` (pass only on exit 0, commit = HEAD, log path), and only for a clean tree. |
| DM-1 | `refresh` indexes ledger rows, decisions.md rows, receipts and archive pointers with provenance (`source`, `ref`, `confidence`). A second `refresh` with unchanged sources rebuilds nothing (reported `unchanged`). |
| DM-2 | `brief` stays within `--budget-tokens`, lists active tasks' next actions, open blocking findings and open owner decisions, excludes stale items, and states omitted counts. |
| DM-3 | `recall` returns the relevant row for a query (precision check on a fixture of at least 20 items, with the expected item ranked first for each of at least 5 queries), each with provenance. |
| DM-4 | Invalidation: changing a file recorded with `path`+`blob` on canonical, or recording a non-existent commit, marks the item stale with a reason. Moving the canonical tip triggers re-evaluation. A superseded decision goes to `cold`. |
| DM-5 | Secrets (for example `password=hunter2`, `sk-...` keys) never appear in the index or output, and secret-looking paths are not indexed. |
| DM-6 | Deduplication: identical text from two refs is stored once, with `also_refs`. |
| DM-7 | `remember` writes to the task ledger (the chain verifies) and the item is then recallable. The index refuses to be the target of `remember` without a ledger task. |
| DM-8 | Deleting the index file and running `rebuild` reproduces the same items (derived, not truth). |
| HK-1 | `inventory` is read-only: the repository's refs, worktree list and file tree are byte-identical before and after (digest check). |
| HK-2 | Classification on a sandbox repository: main, locked, active-task, unmerged-branch worktree → `PROTECTED`; dirty → `DIRTY`; untracked receipt → `EVIDENCE`; record-cited → `REFERENCED`; clean merged idle → `DISPOSABLE`; missing dir → `PRUNABLE`; merged branch → `OBSOLETE_BRANCH`; `preserve/*` branch → not listed. |
| HK-3 | `apply` removes only `DISPOSABLE`, `PRUNABLE` and `CACHE` items (plus `OBSOLETE_BRANCH` when asked). It refuses `PROTECTED` and `ESSENTIAL_EVIDENCE` even with `--approve`. An approved `DIRTY` worktree is archived, verified, then removed, and `restore` brings back its uncommitted file byte-identical. |
| HK-4 | A plan item that changed after `inventory` (new commit, new file, newly locked) is `SKIPPED_CHANGED`, not acted on. |
| HK-5 | Idempotence: applying the same plan twice performs each action once (`ALREADY_DONE` the second time), and the receipt and journal verify. |
| HK-6 | Crash safety: a journal with an `INTENT` and no outcome (simulated crash) is resolved by `recover` from the real state. |
| HK-7 | Archives: `verify-archive` detects a modified member, and `restore` refuses a non-empty target and a zip-slip member. |
| HK-8 | Restore of a removed `DISPOSABLE` worktree and of a deleted `OBSOLETE_BRANCH` works from the receipt's restore commands. |
| G-1 | Regression: `tests/dev_workflow` (all existing ledger, MM and lifecycle tests) shows no new failures against the baseline `8ff6186b` (driver gate). `ws_frozen_check` passes, and no protected path changes. |
| G-2 | Security: no new dependency, no network use, no secret printed. The tools never run `git push`, never touch remotes or tags, and never delete outside the plan. The reviewer checks this. |
| L-1 | Live (real machine, read-only): `housekeeping inventory` over the real repository and `D:/uri-dev`, plus `devmemory refresh/brief/recall`, run on the real ledger and the P0 `decisions.md`. Results go into evidence with measured counts, sizes, timings and brief token size. No destructive apply on the real machine without owner approval. |
| P-1 | Measurements recorded: inventory wall time, reclaimable bytes by class, brief tokens compared with a full `decisions.md` plus handoff read, refresh time when unchanged compared with full rebuild, and reuse savings for a repeated targeted gate. |

## 4. Owner-only decisions (not started; recorded as blockers or questions)

- **AP-14:** authoritative Milestone Manager home. Until it is decided, the milestone is registered in the task ledger only, and `devmemory` reads MM only when a home is given. The rehearsal ledger belongs to the MM thread and is not written.
- **Real-disk destructive cleanup** (`apply` on the owner's machine): the owner approves the dry-run plan first.
- **Canonical integration** of this milestone: the driver stops at `OWNER_AUTHORIZATION` (`authorized: false`).

## 5. Corrections made during implementation (recorded, not overwritten)

| # | Earlier plan text | Evidence | Correction |
|---|---|---|---|
| C-1 | §2.3 PRUNABLE action "`git worktree prune` for that entry" | `git worktree prune` is global. The real-machine inventory found a missing `.work/audit_R1` registration that belongs to P0's running PH1-GATE-1 driver run. | Per-item `git worktree remove <path>`, which works on a missing directory. Test `test_hk3_prune_is_per_item_never_global`. |
| C-2 | §2.3 PROTECTED list had no rule for lifecycle driver work trees | The same live run (stage FIXING) | Worktrees inside a lifecycle `state_dir` (`state.json` + `events.jsonl`) whose stage is not COMPLETE are PROTECTED, missing ones included. Test `test_hk2_driver_work_trees_of_unfinished_runs_are_protected`. |
| C-3 | §2.3 directories under `--root` classified by markers only | D:/uri-dev live-run folders hold nested registered worktrees, which a directory removal would delete behind git's back. | A directory holding registered worktrees is PROTECTED, and its worktrees are handled individually. Test `test_hk2_dir_holding_worktrees_is_protected`. |
| C-4 | HK-1 "inventory is read-only" | `git status` may rewrite a worktree's index stat cache. | All three tools run git with `--no-optional-locks`. |
| C-5 | §2.2 open owner questions taken from the register as they are | Live brief listed OPEN-18 and OPEN-21 as open after their commits (3def4023, ac3dcbae) were integrated. The register row had not been updated. | An open question citing a commit that canonical contains is shown as "possibly resolved" and listed last. The register row is not changed. Test `test_dm4_open_question_citing_integrated_commit_is_flagged`. |
| C-6 | — | The CLI output garbled `§` on a Windows pipe. | stdout and stderr are forced to UTF-8. Test `test_dm_cli_output_is_utf8`. |
| C-7 | Baseline `8ff6186b` | Canonical moved to `b1944200` (G1-02 follow-up, P0 thread) on 2026-10-22/23. No shared files. | Canonical merged into the candidate (`823fddff`). Driver baseline is `b1944200`. |
| C-8 | §2.3 EVIDENCE vs DIRTY order | An untracked receipt also makes a tree dirty, so the tree was labelled DIRTY. | Evidence takes precedence in the label. Both classes need approval and an archive first. |
| C-9 (I-1) | §2.3 REFERENCED items carried only the cited path | Live plan: 98 clean REFERENCED worktrees (72.2 GiB), cited mostly by inventory-style records that list every worktree. | Every cited item carries `cited_by` (the record files), so the owner can judge each citation. Test `test_i1_citation_names_its_record`. |
| C-10 (I-2) | §2.3 an approved REFERENCED/DIRTY/EVIDENCE worktree is archived first | Archiving a clean worktree whose HEAD a ref keeps duplicates gigabytes of committed content. | An approved worktree that is clean, has no untracked evidence and whose HEAD is kept by canonical, a remote or a local ref is removed without an archive (no `--force`; restore command recreates it). Everything else is still archived and verified first. Test `test_i2_approved_clean_referenced_tree_removed_without_archive`. |
| C-11 (I-3) | §2.3 one CACHE item per cache directory | Live plan: 14,769 cache items (1.7 GiB). Per-item rechecks re-read every record; inventory took 3,279 s. | One `caches` item per top-level directory, rechecked as a group (any member changed or protected: the group is skipped). Directory classes are memoised per context. Tests `test_i3_caches_grouped_and_rechecked_as_a_group` plus the driver's R1-02/R2-01/R3-01 regressions adapted to the group. |

### 5.1 Fallback review FB-1 (`2bc93d8d`, REJECT) and repairs (`de101e31`)

Driver run r2 stopped BLOCKED NO_INDEPENDENT_REVIEWER on `2bc93d8d` (Codex QUOTA, claude_cli AUTH). The V3.1
fallback reviewer (a fresh, isolated Claude subagent using the driver's `review_prompt`) recorded REJECT. The raw
output is `D:/uri-dev/lc-storage-evidence/fallback-review/review_R1_2bc93d8d.txt`, and ledger review `V1` holds the
recomputed verdict. It confirmed R1-01..R3-04 FIXED.

| Finding | Repair |
|---|---|
| N-01 HIGH: ignored files (`.env`, `uri_workspace/evidence/`, `work/c1/`) were removed automatically or by I-2 without an archive | Worktree classification lists ignored entries. Any entry that is not a pure cache (`__pycache__`, `.pytest_cache`, `*.pyc`) makes the tree DIRTY, which means approval plus a verified archive. I-2 also requires `ignored_count == 0`. Plan action texts say what apply does. This corrects C-10's "byte for byte" claim, which was false for ignored content. |
| N-02 HIGH: a missing detached worktree that alone kept a commit reachable was PRUNABLE | A missing registration whose HEAD is on no ref is PROTECTED. Missing registrations get a restore command. |
| N-03 HIGH: secret flags were stored verbatim | A flag is redacted when any part of its name is a secret word. `-u user:pass` and Authorization/Bearer values are redacted too. |
| N-04 MEDIUM: a merged branch checked out after inventory was deleted | The branch recheck protects checked-out, ledger-task and preserved-prefix branches. |
| N-05 LOW: `rebuild` could delete a non-index file | It refuses unless the file is a derived index with no ledger tables. |
| N-06 LOW: recover misjudged grouped caches | The INTENT records member paths, and recover checks them. |
| N-07 LOW: the cache walk entered nested repositories | It stops at any directory containing `.git`. |
| N-08 LOW: `--reuse` key ignores gitignored inputs and installed packages | Documented limitation, not repaired. `--reuse` is opt-in, never upgrades a result, and no driver gate uses it. Do not use it across `.env` or dependency changes. |
| N-09 LOW: a read-only ledger open leaves `-wal`/`-shm` files | Accepted: SQLite creates them for WAL databases. Content is unchanged. |
| M-01 (coordinator, live gate): the R3-03 source identity hashes directory mtimes, so the full `tests/dev_workflow` gate run on `2bc93d8d` was reported "source changed" and could not be recorded on its commit | Measured on the clean checkout `2bc93d8d` with stat snapshots around a full gate run: no tracked file changed and git status stayed clean, but the mtime of `tests/dev_workflow` changed because a test created and deleted a temporary file. The source identity now fingerprints tracked files only. Untracked files still present at the end are caught by the final git status. Documented limit: an untracked file created and removed during the run is not detected. Regression test `test_m01_temporary_file_in_tracked_dir_keeps_result_bindable` fails before the repair and passes after it. The R3-03 rewrite-and-restore tests still pass. |

`17fae297` normalises line endings to LF. It contains no content change: `git diff --ignore-cr-at-eol` is empty.
Earlier coordinator edits on Windows had written CRLF into the three new modules.

### 5.2 Fallback review FB-2 (`573e3268`, REJECT) and repairs

Driver run r3 stopped BLOCKED NO_INDEPENDENT_REVIEWER on `573e3268`. The FB-2 fallback reviewer (raw:
`D:/uri-dev/lc-storage-evidence/fallback-review/review_FB2_573e3268.txt`, ledger review `V2`) confirmed N-01..N-07 and
M-01 FIXED, N-08/N-09 DOCUMENTED and R1-01..R3-04 not regressed. The full `tests/dev_workflow` gate on `573e3268`
passed 998 tests (exit 0). It is the first full gate whose result `testrun` bound to its commit in the ledger, which
confirms M-01 live.

| Finding | Repair |
|---|---|
| FB2-01 MEDIUM blocking: a local edit hidden by assume-unchanged/skip-worktree was removed automatically | `git ls-files -v` hidden entries make a worktree DIRTY, which needs approval plus a verified archive. They are part of the fingerprint and the I-2 condition. |
| FB2-02 LOW: commits kept only by a detached worktree's own HEAD reflog were lost on removal | A worktree whose reflog holds commits that no branch, tag, remote or canonical has is PROTECTED. |
| FB2-03 LOW: an archive holds working files, not staged index content | Documented limit. The working-tree state is archived; a partially staged change keeps only its working version. Approve such trees only after committing or stashing what should be kept. |
| FB2-04 LOW: a hand-edited cache item could name any directory | apply refuses cache items whose members are not `__pycache__`/`.pytest_cache` below a top-level directory of a plan root. |
| FB2-05 LOW: camelCase secret flags (`--accessToken`) were kept | Flag names are also split on camelCase, and `passphrase` is a secret word. |
| FB2-06 LOW: `devmemory --index <ledger>` wrote into the ledger | `Index()` refuses any existing file that is not a derived index (all commands). |

Regression tests `test_fb2_*` fail on `573e3268` (5 failed) and pass after the repair.

### 5.3 Fallback review FB-3 (`7562b6e1`, REJECT) and repairs

Driver run r4 stopped BLOCKED NO_INDEPENDENT_REVIEWER on `7562b6e1`. The FB-3 reviewer (raw:
`D:/uri-dev/lc-storage-evidence/fallback-review/review_FB3_7562b6e1.txt`, ledger review `V3`) confirmed every earlier
finding FIXED or DOCUMENTED. The full gate on `7562b6e1` passed 1003 tests (exit 0) and was recorded on the commit.

The repair addresses each class once rather than each instance:

| Finding | Repair |
|---|---|
| FB3-01 MEDIUM blocking: a local canonical branch was listed as OBSOLETE_BRANCH and deleted; the next recheck aborted apply without a receipt | The ref that `--canonical-ref` resolves to is never a branch item, at inventory or at recheck. A recheck error is a per-item FAILED, so a receipt is always written. |
| FB3-02 MEDIUM blocking: testrun treated a tree with hidden index edits as clean (false PASS bound to HEAD; REUSED pass on a failing HEAD) | `tree_state` marks such a tree dirty, so it gets no ledger binding and no reuse. |
| FB3-03 LOW: relative-path worktree reflog not found (fail open) | The gitdir comes from `git rev-parse --absolute-git-dir`. A `.git` that cannot be resolved means PROTECTED. |
| FB3-04 LOW: only 500 reflog commits were checked | One shared check, `_commits_only_in_log`, reads every entry and uses `cat-file --batch-check` plus `rev-list --stdin`. Note: the regression test fails on `7562b6e1` because the function did not exist there, not by exercising the truncation itself. |
| FB3-05 LOW: deleting a branch dropped commits kept only by its reflog | A branch whose reflog alone holds commits, or whose reflog cannot be checked, is not listed. The branch recheck applies the same rule. |
| FB3-06 LOW: `--DBPassword`, `--githubtoken` etc. were kept | Acronym boundaries split too, and strong secret words match as substrings. |

Regression tests `test_fb3_*`: 6 fail on `7562b6e1` (and FB3-04 as noted), and all pass after the repair.

### 5.4 Fallback review FB-4 (`ab983066`, REJECT), gate failure M-02, and repairs

Driver run r5 stopped BLOCKED NO_INDEPENDENT_REVIEWER on `ab983066`. FB-4 (raw:
`D:/uri-dev/lc-storage-evidence/fallback-review/review_FB4_ab983066.txt`, ledger review `V4`) found FB3-02 NOT_FIXED.
That is a recurrence, so the root cause was diagnosed before repair: repository-wide checks depended on the cwd, and
reflogs were parsed from files instead of read through git. The full gate on `ab983066` FAILED 1 of 1010 and was
recorded as FAIL on the commit: `test_ts4_missing_marker_when_supervisor_dies`.

| Finding | Repair |
|---|---|
| FB4-01 MEDIUM blocking (recurrence of FB3-02): index flags were read only below a subdirectory cwd | `tree_state` reads them from the repository root. |
| FB4-02 MEDIUM blocking: deleting a symbolic branch deleted its target | Symbolic refs, and refs that a symbolic ref points to (found while testing this repair), are never listed and are protected at recheck. Deletion uses `update-ref --no-deref`. |
| FB4-03 LOW: hand-edited branch items could name tags or remote refs | Apply refuses branch items that are not valid `refs/heads/*` names. |
| FB4-04 LOW: reflog checks failed open on reftable | Reflogs are read with `git reflog show` (any ref backend). An unreadable reflog means protect. |
| FB4-05 LOW: canonical given as a SHA: the branch holding it was listed | When canonical is not a named ref, a branch at canonical's tip is not listed. A first, broader version of this rule (any branch at canonical's tip) was too strict, because merged branches at canonical are normal, and it was narrowed before commit. |
| FB4-06 LOW: `--accesskey`, `--privatekey`, `--sshkey`, `--pw` were kept | `pw` added. Flag names ending in `key` or `keys` are redacted. |
| M-02 (coordinator, gate failure): `status` reported MISSING_MARKER for a live run when a read met the supervisor's atomic `run.json` replace | Reproduced cross-process: 4 of 4,000 reads before the repair, 0 after. `_load` retries transient failures. If a run is still unreadable after the retries, its state is UNREADABLE, which `wait` keeps polling through. It is never reported as MISSING_MARKER. |

Regression tests `test_fb4_*` and `test_m02_*`: 7 fail on `ab983066`, and all pass after the repair (94 in total).

### 5.5 Driver run r6 (Codex available again)

r6 round 1 was a driver-counted Codex review (`codex_cli`, 4 tests run, 7 files inspected). It returned REJECT,
confirmed the 26 earlier findings it checked as FIXED, and raised R1-01 MEDIUM: a missing worktree registration that
belongs to an active ledger task was PRUNABLE. The driver's implementer committed `7e659bc7`. The coordinator had
wrapped the driver in a 900 s shell timeout, which killed it after that commit and before the repair was recorded.
`lifecycle verify` reported the chain intact. The resumed run then stopped BLOCKED REPAIR_FAILED ("no change made").
Coordinator follow-up:
the repair is correct. The implementer's regression test compared git's `/` worktree path with a Windows `\` path
and failed for that reason only, so it was fixed to compare normalised paths. That gives 98 tests passing. A clean
revision r7 re-audits from round 1. Lesson: run the driver under `testrun` with a bound matched to its budget, never
a short shell timeout.

### 5.6 Driver run r7 and the FB2-03 correction

r7 round 1 was a driver-counted Codex review (4 tests run, 7 files inspected). It returned REJECT on `ac2a17b3` with
three findings, all repaired by the driver in `0899af6e`:

- R1-01 HIGH: ignored non-cache files inside cache directories were deleted without an archive.
- R1-02 HIGH: common curl credential arguments stayed visible.
- R1-03 MEDIUM: deleting the development-memory index lost its rebuild inputs.

Codex then ran out of quota again, and the run stopped BLOCKED NO_INDEPENDENT_REVIEWER on `0899af6e`. Codex
reported N-01 (which became R1-01) and FB2-03 as NOT_FIXED.

**Correction (FB2-03 is no longer a documented limit).** §5.2 recorded FB2-03 as a documented limit. That record is
superseded here, and the earlier text is kept. An approved archive-then-remove of a worktree now stores
`git diff --cached --binary` as a verified `staged.patch` extra. Its sha256 is in the manifest and checked by
`verify-archive`. Restore writes it to `.housekeeping-extra/`. If git fails, the removal fails closed. Test
`test_fb2_03_staged_content_survives_archive_and_restore`.

### 5.7 Fallback review FB-5 (`3b91df77`, ACCEPT WITH FINDINGS), ledger acceptance, and the follow-up

Driver run r8 stopped BLOCKED NO_INDEPENDENT_REVIEWER on `3b91df77`. The FB-5 reviewer (raw:
`D:/uri-dev/lc-storage-evidence/fallback-review/review_FB5_3b91df77.txt`, ledger review `V5`) returned **ACCEPT WITH
FINDINGS** with four LOW findings and confirmed all 49 earlier findings FIXED or DOCUMENTED. The full gate on
`3b91df77` passed 1027 tests (exit 0) and is recorded on the commit. `task_ledger accept` recorded ACCEPTED (seq 182)
with provenance SUBAGENT_FALLBACK and basis r8 NO_INDEPENDENT_REVIEWER (event seq 14). Eight blocking or fixed
findings were closed with that evidence first. The milestone is registered in the authoritative Milestone Manager
(`D:/uri-dev/state/milestone-manager`, DEC-100) as `LIFECYCLE-V3-1-STORAGE`, with the review, the gate evidence and
the r8 lifecycle link.

The four LOW findings are repaired in a follow-up commit, which needs its own independent review before it can
replace `3b91df77` as the integration candidate:

| Finding | Repair |
|---|---|
| FB5-01: a missing registration's HEAD reflog was not checked | The admin directory is found from `worktrees/*/gitdir`. Its reflog is read with `git reflog show worktrees/<id>/HEAD`, and per-worktree refs there mean PROTECTED. Unknown means PROTECTED. |
| FB5-02: per-worktree refs (`refs/worktree/*`, `refs/bisect/*`, `refs/rewritten/*`) were ignored | They are read in the worktree and checked with `_unreferenced`. Unknown means PROTECTED. |
| FB5-03: `staged.patch` honoured diff config (external diff, color, noprefix, textconv) | Plumbing `git diff-index --cached -p --binary --full-index --no-ext-diff --no-textconv --no-color --src-prefix=a/ --dst-prefix=b/ HEAD`. The test checks that the patch applies with each config set. |
| FB5-04: `recover` without `--repo` marked worktree INTENTs done | The INTENT records the repository. Without it, the result is UNRESOLVED and is never guessed. |

### 5.8 FB-6 (`7cdf97d0`, ACCEPT WITH FINDINGS), second ledger acceptance, and the P-1 performance repair

Driver run r9 stopped BLOCKED NO_INDEPENDENT_REVIEWER on `7cdf97d0`. FB-6 (raw:
`D:/uri-dev/lc-storage-evidence/fallback-review/review_FB6_7cdf97d0.txt`, ledger review `V25`) returned **ACCEPT WITH
FINDINGS** with two LOW residuals:

- FB6-01: `GIT_DIFF_OPTS` can make a zero-context staged patch.
- FB6-02: `recover` with a relative or mismatched repo can mark a prune done.

The full gate on `7cdf97d0` passed 1033 tests (exit 0, recorded on the commit), and `task_ledger accept` recorded
ACCEPTED (seq 208).

**P-1 finding after acceptance (coordinator, live).** The read-only real-machine inventory on the accepted code
TIMED_OUT at its 3 h bound. `testrun` killed it as designed. Profiling showed two causes:

- The record scan walked the driver `.work` checkouts under `D:/uri-dev/lifecycle` and read every `.md`/`.json` in
  them. The context took 186 s, and apply rebuilds it for every recheck.
- `content_snapshot` hashed every file of every worktree (8,300 opens for three worktrees, 10-26 s per worktree).

Repair (this commit):

- The record walk skips `.work` and nested checkouts, and caches parsed record files by (path, size, mtime).
- The snapshot binds scandir metadata (mode, size, mtime_ns) without opening files. Tracked content stays bound by
  git status and HEAD, and archives still hash every stored byte.

Measured on the real repository and records:

| Step | Before | After |
|---|---|---|
| Context build | 186 s | 3.6 s |
| Recheck context | 186 s | 0.8 s (cached records) |
| Per-worktree classification | 10-26 s | 0.7-1.5 s |

Cited paths fell from 8,228 to 8,038. The 190 removed came only from `.work` copies, which were false citations.
Tests `test_p1_*`. A performance change after acceptance needs its own independent review before it replaces
`7cdf97d0`.

## 6. Lifecycle

INTERNAL work. The driver runs with `codex_cli` (gpt-6-sol, probe OK 2026-10-22) as primary reviewer and `claude_cli` as fallback; `claude auth status` shows it is not logged in today, so it is configured but unavailable. The gate is `tests/dev_workflow`. Integration mode is `fast-forward` with `authorized: false`.
