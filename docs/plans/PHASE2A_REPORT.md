# URI Phase 2A: Durable Task Supervisor, implementation report

Date 2026-10-07. Author: Claude (implementer and self-auditor; this report is NOT an independent audit).
Worktree `C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`, detached at `e8e3b65` plus the frozen checkpoint overlay,
branch label `phase2a-durable-supervisor` (no commits). Nothing was committed, pushed, merged or cut over.

Labels: IMPLEMENTED, TESTED (automated test ran and passed), SIMULATED, NOT TESTED, BLOCKED.

## A. Implementation summary

New package `uri_supervisor/` (14 modules, about 3,000 lines) and `tests/phase2a/` (168 passed, 2 opt-in live skipped by default).
Architecture and state table: `docs/architecture/PHASE2A_ARCHITECTURE.md`. Power-loss plan: `docs/plans/PHASE2A_POWER_LOSS_TEST_PLAN.md`.

## B. Architecture

See the architecture doc. Boundaries: ledger (authority), admission (resources), supervisor (lifecycle), recovery (one decision
procedure), winproc (process containment), executors/stream (declarative adapters), postconditions (URI observation),
snapshot/narration (grounded output). Provider names occur only in `executors.py` (a test greps every other module).
Core integration is NOT wired (see K).

## C. Frozen-Core integrity (TESTED)

* Checkpoint SHA-256 recomputed: `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7` (matches).
* All 122 checkpoint files byte-identical in the Phase 2A tree; no other tracked or untracked file changed outside `uri_supervisor/`,
  `tests/phase2a/`, `docs/*/PHASE2A_*` (`test_frozen_core.py`, 8 passed). HEAD is still `e8e3b65`.
* No file in `uri_core`, `uri_harness_adapters`, `uri_ui` mentions `uri_supervisor`; `uri_supervisor` imports nothing from `uri_core`.
* Bypass-flag refusal is a superset of Phase 1's (and also refuses substrings and the final argv, which Phase 1 does not).
* Observation: the source `docs/plans/PHASE1_FINAL_CLOSURE_REPORT.md` in the Phase 1 worktree differs from the zip copy only in line
  endings; the Phase 2A tree uses the zip copy.
* Two local, untracked, git-excluded environment items were created to run Phase 1 tests: `.venv` (Phase 1 requires
  `.venv\Scripts\python.exe` in the root; installed from the Phase 1 venv's `pip freeze`) and `work/c1/checkpoints/c3-provisional-source.zip`
  (copied read-only from the Phase 1 worktree). Neither is part of the candidate.
* Phase 1 full suite on the Phase 2A tree, `python -I`: 2842 passed, 12 skipped, 12 failed. Eleven failures are the identical 11 IDs
  recorded in the Phase 1 final closure report (`step3_test::test_drive`, `step4_test::test_download`, capability-directory privacy,
  `test_m20_feasibility_validation`, 2x `test_m20_recovery_loop`, 2x `test_m20_semantic_interpreter_resilience`,
  `test_orchestrator_session_workflow`, `test_usage_import_boundary`, `test_workflow_restart_recovery`). The twelfth,
  `test_offline_checkpoint_restore_hashes_and_no_application_start`, failed only because an untracked evidence zip was absent from the fresh
  worktree; with the zip copied in, all 37 tests in that module pass. A first full run without `-I` produced 24 failed and 190 errors
  (`ISOLATED_INTERPRETER_REQUIRED`); it is discarded as an environment error, not a code result.
* Not done: `graphify update .` (CLAUDE.md rule). It rewrites tracked `graphify-out/` files and would alter the frozen baseline tree.

## D. Schema and transactions

22 tables, 52 triggers, 6 indexes. `PRAGMA user_version=1`; unknown versions fail closed.

Tables: `meta`, `scheduler_epoch`, `event`, `resource_pool`, `executor_registration`, `task`, `authorization`, `allowed_transition`,
`attempt`, `admission`, `claim`, `effect_intent`, `effect_observation`, `stream_event`, `stream_interpretation`, `evidence`,
`postcondition`, `postcondition_result`, `completion_record`, `uncertainty`, `recovery_decision`, `user_decision`.

Append-only (UPDATE and DELETE refused by trigger): event, admission, effect_intent, effect_observation, stream_event,
stream_interpretation, evidence, postcondition, postcondition_result, completion_record, recovery_decision, user_decision,
scheduler_epoch. Mutable with rules: task, attempt, claim, resource_pool, uncertainty (resolve once), registration and authorization
(supersede only).

Durability: WAL, `synchronous=FULL`, `foreign_keys=ON`, read back and fail-closed on every connection. Every authoritative write is its own
`BEGIN IMMEDIATE` transaction. Fencing token = `attempt_id` (AUTOINCREMENT, never reused).

Mechanical invariants (trigger-enforced, TESTED by bypassing Python with raw SQL): no SPAWNING without admission, effect intent, held claims
and current fence; stale-fence writes refused; COMPLETE needs a completion record whose required postconditions' latest results are PASS with
`uri_verified` evidence; exits from UNCERTAIN/NEEDS_USER need new effect-related URI evidence or a user decision; retries must reuse key and
params; `SUM(held)<=capacity`; illegal transitions refused.

## E. Recovery state machine (IMPLEMENTED, TESTED)

States `QUEUED, RUNNING, RECOVERING, COMPLETE, RETRY_SAFE, UNCERTAIN, FAILED, NEEDS_USER`. `QUEUED` is an addition to the brief's list, needed
for the queue. Transition table and evidence requirements are in the architecture doc. Reconciliation order: fence, process identity, terminal
and session evidence from raw lines, postconditions by fresh observation, effect classification, decision, atomic commit. One decision per
(task, attempt); re-running returns the same decision.

Deliberate decisions: escalation UNCERTAIN to NEEDS_USER needs no new evidence (it only restricts); an attempt whose process identity was never
recorded provably never ran (identity is made durable before the executor is resumed), so no effect can exist; a task with no declared effects
or no required postcondition is refused at intake; a read task may complete on a clean executor terminal claim (`terminal_success`), nothing else
may.

## F. Executor integration

* Declarative specs for Codex CLI, Claude Code and a generic NDJSON dialect. Adding a harness or local model is data.
* TESTED: parsing against 2 REAL captured streams (Codex 0.158.0 model-rejected, Claude Code 2.1.287 auth failure) and 7 SYNTHETIC fixtures
  (labelled; success paths could not be captured because neither CLI could authenticate, and I did not log in). Real finding: Claude reports an
  auth failure as `subtype:"success"` with `is_error:true`; a test pins that this is an error claim.
* TESTED (opt-in live, 2 passed): real Codex and real Claude Code each ran through admission, intent, contained spawn, raw stream persistence
  and reconciliation on a read-only task. Both ended with a terminal error claim and exit 1 and the task became RETRY_SAFE, never COMPLETE.
  Versions recorded on the attempt (0.158.0, 2.1.287). A successful real run was NOT TESTED.
* TESTED with a scripted fake executor: no terminal event, terminal then hang (killed after grace), truncated terminal tail, free-text success
  contradicting a failed command, quota text, grandchild process, partial write then death, unicode.
* NOT TESTED: local-model executors (only the data shape exists). Resume (`RESUME_SESSION`) is decided and the argv is built with validated ids,
  but resuming a real Codex or Claude session was NOT TESTED.

## G. Admission and resources (TESTED)

Pools are rows. Executor registrations are versioned rows (claims, capabilities, preemptible, quota pools). Admission of all claims for one
attempt is one transaction; a concurrent-admitter test and a multi-resource all-or-nothing test pass, plus trigger-level capacity checks.
Aging counts admission rounds (a ten-year wall-clock jump ages nothing); low priority is admitted within a bounded number of passes under
continuous high-priority arrivals; a capacity-blocked higher-ranked task reserves ALL pools it needs (documented utilisation trade-off);
unrelated pools still backfill. Epochs: a new `scheduler_epoch` per supervisor start; a second supervisor is refused by an OS file lock, and
if the lock is bypassed the stale supervisor's admission and renewals are refused. Old-epoch claims keep consuming capacity until recovery
proves the attempt dead. Monotonic origin change and wall-clock rollback tested. Breakers: quota opens a pool breaker (provider reset time if
the spec extracts one, else bounded exponential backoff 30s to 900s), one half-open probe, closes when the provider answers. Quota attempts do
not consume the retry budget. Preemption only at an executor-declared safe point, only for preemptible executors, never with a declared
non-idempotent effect.

## H. Snapshot and narration (TESTED)

Snapshot: stable schema block first (byte-identical, hash pinned), volatile block after it with ledger watermark, counts, True/False/Unknown
conditions (stale or never observed is Unknown; a reset monotonic origin is Unknown; restart makes all observations Unknown), bounded lists with
omitted counts, and ledger event ids per item. Narration: template sentences re-derived from cited rows; claims carry level
(executor says, URI observed, URI verified, URI state); `verify_claim` drops claims with no or corrupt citations, other tasks' evidence, wrong
numbers or text, or unsupported templates, and downgrades inflated levels. Executor free text is quoted as unverified and never parsed for
facts. An LLM layer is NOT implemented, only `filter_proposed_claims` for it.

## I. Tests

| Run | Result |
|---|---|
| `tests/phase2a`, system Python | 168 passed, 2 skipped (live, opt-in), about 47 s, stable over 6 consecutive runs |
| `tests/phase2a`, `.venv` `python -I` | 168 passed, 2 skipped |
| Live (`URI_PHASE2A_LIVE=1`) | 2 passed |
| Phase 1 full suite, `.venv` `-I` | 2842 passed, 12 skipped, 12 failed (11 identical baseline IDs + 1 environmental, see C) |

Per module: ledger 37, admission 25, recovery 23, stream 19, crash 19, self-audit 18, snapshot/narration 17, frozen-core 8, smoke 2, live 2.
Adversarial coverage: transition-boundary kills at 10 supervisor points and 5 recovery points (real `os._exit` in a child process), executor
death with supervisor (named job vanishes, grandchild dies), double startup, busy writers (40 concurrent), disk full (SQLite page limit), PID
reuse, stale fence, executor exit 0 without terminal, terminal then hang, truncated tail, postcondition proving effect without terminal,
ambiguous external effect never retried, starvation, priority reservation, wall rollback, epoch change, capability changes while queued.

## J. Self-audit findings (author's own attack, not independent)

Each defect below was reproduced by a regression test that failed on the pre-repair code, repaired, and re-run (all in `test_selfaudit.py`).

| # | Defect | Repair |
|---|---|---|
| D1 | Breaker feedback committed after the decision; a crash left a quota-exhausted provider looking healthy | Inside the decision transaction |
| D2 | A wall-clock step back revived an expired authorization | Authority clock with persisted high-water mark |
| D3 | A terminal success claim from a process that exited non-zero could complete a read task | Requires exit 0 (or killed after terminal) |
| D4 | Any new observation could release UNCERTAIN | Trigger limits to effect-related evidence kinds |
| D5 | Authorization scope not enforced at all | Op classes, executors, workspace (effect paths and cwd) enforced |
| D6 | Huge/unreadable directory fingerprints could compare equal and "prove" absence | Unprovable fingerprints never equal |
| D7 | Bypass flags in appended argv unchecked; only exact-token match | Check on final argv plus substrings |
| D8 | Executor-supplied session id could inject argv on resume | Id validation |
| D9 | Unbounded no-newline output exhausted memory | Bounded splitter; oversize lines become incomplete fragments |
| D10 | Lease renewal fsynced on every 50 ms poll | Throttled to a fraction of the lease |
| D11 | Dead run-loop's expired lease was never reaped | `reap_expired_leases` through recovery |
| D12 | Escalation reset the new-evidence watermark | Watermark kept inside the unresolved group |
| D13 | Snapshot reads not one consistent snapshot | Single WAL read transaction (no dedicated failing test) |
| D14 | Quota scan read all stderr | Last 200 lines (no dedicated failing test) |
| D15 | Running the same admission twice duplicated intents | Refused unless attempt is ADMITTED |
| D16 | Predictable job name could be squatted | Unguessable nonce |

D13 and D14 are hardening without a reproducing test. D5 was a missing control rather than a code bug.

## K. Limitations (read before relying on this)

* NOT TESTED: power loss or OS write reordering. Process kills do not model it. Plan written, not run (needs a VM).
* NOT INTEGRATED with Core: no route, UI or approval verification. `submit_task` trusts its caller to be Core holding a confirmed approval.
  Wiring needs edits to frozen files and your decision.
* Effects an executor performs outside its declared envelope are bounded only by the executor's own sandbox flags. Absence proofs cover
  declared paths only; directories over 20,000 entries or files over 256 MB are unprovable and escalate.
* External-effect reconcilers are in-process callables registered per run; after a restart without them, external effects stay unconfirmed
  (conservative).
* `command_passes` postconditions run in an ordinary subprocess without job containment.
* Windows only for spawn; containment limit: processes started by system services (Task Scheduler, WMI, COM) are not job members.
* No retention or compaction of stream and event rows; ledger grows without bound.
* Real success-path Codex/Claude streams and real session resume are unverified (no authentication available here).
* Stale evidence of the live checks: they depended on this machine's expired auth and rejected model, which may change.

## L. Checkpoint

Written outside the tree (so the tree is unchanged by it): see sidecar `evidence\phase2a-candidate-20261007.json` for path, SHA-256, manifest.
Base `e8e3b65`. The tree has no uncheckpointed Phase 2A changes after the checkpoint was cut; it also contains the (unchanged) Phase 1 overlay,
which is not part of the candidate zip.
