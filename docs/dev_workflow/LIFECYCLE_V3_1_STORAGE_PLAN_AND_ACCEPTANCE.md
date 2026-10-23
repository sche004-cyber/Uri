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

## 6. Lifecycle

INTERNAL work. The driver runs with `codex_cli` (gpt-6-sol, probe OK 2026-10-22) as primary reviewer and `claude_cli` as fallback; `claude auth status` shows it is not logged in today, so it is configured but unavailable. The gate is `tests/dev_workflow`. Integration mode is `fast-forward` with `authorized: false`.
