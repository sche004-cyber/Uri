# URI Scheduler — Independent Audit Record

Reviewer: Codex CLI 0.158.0, model `gpt-6-sol`, reasoning `medium`, read-only sandbox, through the local `codex-exec`
bridge (owner rule: audits run on Codex). Review clone: `C:\Users\cheta\Development\sra` (`core.autocrlf=false`), diff
`99f8041..<candidate>`. Every Codex finding was re-checked against the code by Claude before being accepted or disputed.

## Round 1 — candidate `152c8e9` — **REJECT**

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| 1 | Blocking | API token authenticates the caller, but the caller names its own `principal` | confirmed (`service.py` read `principal` from the body) | **repaired**: one principal per service (`--owner`); mismatch → 403 `PRINCIPAL_MISMATCH`; reads filtered by owner; test added |
| 2 | Blocking | Claude gets Read/Edit/Write with no enforced filesystem boundary | partly confirmed. Claude Code docs: `dontAsk` denies every un-approved Edit/Write and anything outside the working directory — which also means the accepted profile could not write its output at all | **repaired + limitation** (historical; superseded by R2-4: only `Edit(./**)` is passed): `--allowedTools Edit(./**) Write(./**)` scoped to the per-attempt workspace; boundary = Claude Code permission engine, not an OS sandbox; not yet verified live; owner acceptance requested |
| 3 | Blocking | restart requeues every interrupted occurrence even if the work had finished | confirmed | repaired in `04e9eaa` (reconcile artifact rows and the supervisor ledger first); round 2 found a remaining crash window, closed in round-2 repairs |
| 4 | High | calendar refresh / later years schedule dates the owner never saw | confirmed (proposal preview is 400 days) | **repaired**: only shown dates are confirmed; others `AWAITING_CONFIRMATION` until the owner confirms; tests + UI *Confirm date* |
| 5 | High | exceptions in package/execution leave the occurrence `RUNNING` | confirmed | **repaired**: every claimed occurrence is settled (`_execute_settled`); params validated at proposal; test |
| 6 | High | cancelling a job leaves pending reviews approvable | confirmed | **repaired**: cancel closes every open state; review refuses `JOB_CANCELLED`; test |
| 7 | High | cancel/dispatch race: claim ignores job state | confirmed | **repaired**: job state inside the claim's compare-and-set; test |
| 8 | High | `festival.key` reaches the output file name (path traversal) | confirmed | **repaired**: slug validation at proposal, slugged names, resolved-path containment check; test |
| 9 | Medium | oversize GIF can still become a candidate | confirmed | **repaired**: size budget is part of `ok`; test |
| 10 | Blocking | real Claude generation not run | confirmed (documented as NOT RUN) | **open — owner action**: Claude CLI login; cannot be repaired by the agent |

## Round 2 — candidate `04e9eaa` — **REJECT**

Round-1 status per Codex: F1, F4, F5, F6, F7, F8, F9 RESOLVED; F2 PARTIAL (relies on the permission engine; no live
evidence; path-scoped `Write` rules are not consulted); F3 PARTIAL (new crash window). F10 documented truthfully; Codex
states it alone does not block acceptance as a development candidate, only claims of live end-to-end qualification.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R2-1 | Blocking | `_resume_collection` claimed the occurrence and reopened the attempt in two transactions; a crash between them made `recover()` (which looked only at open attempts) requeue completed work | confirmed | **repaired**: claim + reopen in one transaction; `recover()` reconciles the LATEST attempt whether ended or not; test `test_r2_crash_between_collection_claim_and_attempt_reopen_never_reruns` |
| R2-2 | High | an exception after the harness completed (render/IO/recording) went to `_retry_or_fail`, re-running Claude | confirmed | **repaired**: `_post_harness_failure` retries COLLECTION from the workspace with backoff (`COLLECT_PENDING`), bounded by the attempt budget; `_execute_settled` consults the supervisor before choosing; test `test_r2_render_failure_after_harness_retries_collection_only` |
| R2-3 | Medium | docs overstated "duplicates impossible" | confirmed | **repaired**: architecture/ledger state the exact scope of the guarantee (re-run only when the ledger proves no start or no effect; otherwise owner) |
| R2-4 | Medium | `Write(./**)` is not consulted; `Edit(./**)` is the operative rule | confirmed against the Claude Code permissions documentation | **repaired**: only `--allowedTools Edit(./**)` is passed; docs explain it; limitation retained (permission engine, not OS sandbox; not observed live) |

## Round 3 — candidate `02938ca` — **REJECT**

Codex: R2-1 RESOLVED, R2-4 RESOLVED (live enforcement unverified; owner-acceptance limitation), R2-2/R2-3 PARTIAL because of
R3-1/R3-2. F10 and the F2 limitation confirmed as owner-gated items, not reasons for rejecting a development candidate.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R3-1 | High | a COMPLETE supervisor task whose output is missing/invalid goes to `_retry_or_fail` and re-runs Claude, contradicting the no-rerun claim | confirmed; this is intended behaviour (nothing usable exists), but it was undocumented and the docs claimed no rerun | **repaired (documented as a distinct authorized retry)**: "Content retry" defined in the architecture (policy budget, backoff), receipts carry `content_retry: true`, ledger and duplicate-guarantee text updated |
| R3-2 | High | an exception after the artifact insert (e.g. in `_finish`) sends the attempt to collection again, creating a second version of the same work | confirmed | **repaired**: `_settle_recorded_artifact` files the attempt's existing artifact for review in `_post_harness_failure` and at the start of `_resume_collection`; test `test_r3_failure_after_artifact_insert_does_not_duplicate` |
| R3-3 | Low | audit row 2 still shows `Edit(./**) Write(./**)` | confirmed | **repaired**: row labelled historical, pointing to R2-4 |

## Round 4 — candidate `e7a44bf` — **REJECT**

Codex: R3-3 RESOLVED; R3-1/R3-2 PARTIAL only because of R4-1. Docs on F10/F2/no OS task found truthful.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R4-1 | High | policy accepted unvalidated (`retry_backoff_s: []`, non-finite `max_attempts`) → settlement raises, occurrence stuck `RUNNING`; retry bound defeated | confirmed | **repaired**: `_validate_policy` (known keys, bounded integers, 1-5 backoffs, valid time); `_backoff_s` never raises for a stored malformed policy; test `test_r4_policy_is_fully_validated` |
| R4-2 | High | a cancel recorded after `_execute` checked it but before `_finish` committed was overwritten by `AWAITING_REVIEW` | confirmed | **repaired**: `_finish` re-reads the occurrence inside its transaction; `CANCEL_REQUESTED` wins, the attempt's candidate artifact is marked `REJECTED`; test `test_r4_cancel_during_run_wins_over_completion` |
| R4-3 | High | greeting text could be placed off-canvas yet pass legibility (size/contrast only) | confirmed | **repaired**: text anchors restricted to [0.05, 0.95]; legibility measured on rendered glyph pixels (on-canvas fraction ≥ 0.98, minimum glyph area, fill/stroke contrast, background sampled under the glyphs); test `test_r4_greeting_must_be_visible_on_canvas` |
| R4-4 | High | hourly schedules ignored the configured hour and restarted each day | confirmed | **repaired**: anchored at start date + time, interval carried across days; test `test_r4_hourly_is_anchored_and_crosses_days` |
| R4-5 | High | `scripts/scheduler_task_ctl.ps1` missing from the exact-path guard lists | confirmed | **repaired**: added to `ALLOWED_NEW` and `WS_EXACT` (byte-preserving edit) |

## Round 5 — candidate `f21160d` — **REJECT**

Codex: R4-1..R4-5 RESOLVED. F10/F2 owner-gated, not the reason for rejection.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R5-1 | High | a cancel recorded while `harness.gate()` ran was overwritten by `BLOCKED_HARNESS` (and the same pattern on other non-`_finish` settlements), so the recheck could re-queue cancelled work | confirmed; reproduced by a failing test before the fix | **repaired**: the cancellation check moved into `_set_occ`, the single choke point for every occurrence transition: a running occurrence with `CANCEL_REQUESTED` always settles `CANCELLED` (retry time cleared); test `test_r5_cancel_during_gate_is_not_overwritten_by_blocked` |

## Round 6 — candidate `8a73605` — **REJECT**

Codex: R5-1 RESOLVED (all `_set_occ` callers traced; no legitimate transition wrongly converted).

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R6-1 | High | a cancel recorded while an AVAILABLE gate ran had no attempt to stop; `_execute` then created an attempt and launched the harness, discarding the result afterwards | confirmed; reproduced by a failing test | **repaired**: the attempt-creating transaction re-reads the occurrence and settles `CANCELLED` before any attempt exists; `ClaudeHarness.cancel` records the withdrawal (bridge discipline) so a task cancelled before submission is never submitted and one cancelled between admission and spawn is ended `spawn_failed`; tests `test_r6_cancel_during_available_gate_never_runs_harness`, `test_r6_harness_cancel_before_spawn_never_spawns` |

## Round 7 — candidate `4b1caa0` — **REJECT**

Codex: no other Blocking/High finding in the final pass; F10/F2 truthfully documented owner gates.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R7-1 (R6-1 PARTIAL) | High | a cancel after the harness's post-admission check but before the supervisor marks the attempt active gets `NOT_RUNNING_HERE`; the process starts. The accepted bridge has the same gap | confirmed by reading `Supervisor.request_cancel` / `_supervise` (the kill set is honoured from the first poll, `request_cancel` only accepts active attempts) | **mitigated + recorded limitation**: `ClaudeHarness.cancel` pre-arms the supervisor's kill set when the attempt is admitted but not yet active, so the executor is killed at the first supervision poll if it is still running — best effort, effects before that poll are possible (test `test_r7_cancel_between_admission_and_active_is_pre_armed`). A never-start guarantee requires changing the accepted supervisor: owner decision. Classified as a limitation of the accepted Phase 2D cancellation contract (bridge `cancel` docstring: a cancellation after dispatch is never a clean close), not a new scheduler defect |

## Round 8 — candidate `6cefc66` — **ACCEPT WITH FINDINGS**

Codex: R7-1 mitigation correct (pre-armed entry honoured at the first poll; AUTOINCREMENT attempt ids rule out a wrong-attempt
kill); the residual window is consistent with the accepted Phase 2 post-dispatch cancellation contract. No new Blocking/High.

| # | Codex severity | finding | disposition |
|---|---|---|---|
| R8-1 | Medium | "milliseconds after start / before Claude Code can initialise" overstated: `_supervise` checks process exit before the kill set and has no timing bound | **repaired**: code comment, architecture and audit now say best-effort kill at the first poll if still running, with possible effects before cancellation |
| R8-2 | Low | a pre-armed entry can stay in the supervisor's kill set after the attempt ended | **repaired**: the entry is discarded when `run` returns |

Owner-gated items carried forward (not code defects): F10 real Claude generation NOT RUN (CLI login); F2 filesystem boundary
is Claude Code's permission engine, not an OS sandbox (owner acceptance); R7-1 residual cancellation window (owner acceptance,
or an owner decision to change the accepted supervisor).

## Round 9 (closure) — candidate `f59aad5` (scope `7496bba..f59aad5`) — **REJECT**

Scope: owner calendar corrections, calendar v2 data, logon-task procedure, security and cancellation record. Codex could not run
tests (sandbox temp dir); every finding below was confirmed by Claude in the code and, for C1, by a test that fails on the
pre-repair engine.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| C1-01 | High | `tick()` selects due work without the engine mutex; `_dispatch` re-reads the row and claims whatever state it finds, so a correction between selection and claim could run a moved or disputed date | **confirmed and older than the corrections**: a calendar refresh in that gap had the same effect, and the late-run branch could reset `AWAITING_CONFIRMATION` to `SCHEDULED`. `test_r9_occurrence_changed_after_selection_is_never_claimed` FAILED on `f59aad5` (the moved occurrence ran) | **repaired**: everything up to the claim runs under the engine mutex (`_pre_claim`); an occurrence that is not `SCHEDULED`-and-due or `REVISION_QUEUED` is never claimed; the claim CAS also requires an eligible state and (for scheduled work) `due_at_us <= now` |
| C1-02 | Medium | start skips stored corrections that no longer apply, but `correct_calendar` replays all rows, so one obsolete row blocks every later correction | confirmed; `test_r9_obsolete_correction_never_blocks_later_ones` FAILED on `f59aad5` | **repaired**: one replay policy (`_applicable`) for start and for new corrections; skipped rows stay in the append-only record and are reported (`not_applied`) |
| C3-01 | Medium | the live gate accepted any JSON with `simulated: false` and `verdict: PASS` | confirmed | **repaired**: `result.json` + sibling `attempts.json` + `journal.json` of one live run must agree (mode live, not simulated, PASS, LIVE available harness, verified chain, a LIVE `claude_code` attempt). Stated as an owner-run safeguard against a wrong or partial file, not proof against a file the owner forges |
| C3-02 | Medium | `uninstall -Apply` without `-State` left a running service; the command-line check matched any process containing both strings | confirmed | **repaired**: rollback with `-Apply` requires `-State`; the process must carry `-m uri_scheduler.service run` and `--state <State>` as one argument (a look-alike and a sibling state dir are left alone in the test) |

Codex also verified: calendar validates (77 occurrences, sources present, Sikkim 2027 absent, Bakrid history kept); correction
rows are append-only and audited; the shipped calendar is never written; trigger bound to the current user; `uri_supervisor`
unchanged; F2 and R7-1 remain recorded as unresolved; the cancel-window record matches its measurement and is not a guarantee.

## Round 10 (closure) — candidate `2da36ad` — **REJECT**

Round-9 status: C1-02 FIXED; C1-01, C3-01, C3-02 PARTIAL.

| # | Codex severity | finding | Claude verification | disposition |
|---|---|---|---|---|
| R10-01 | High | `materialize()` / `refresh_calendar()` did not take the engine mutex; a reconciliation could change a row after `_pre_claim` read it, and the late-run branch could set a moved, unconfirmed occurrence back to `SCHEDULED` | confirmed by reading (the round-9 test covered only `correct_calendar`, which holds the mutex) | **repaired**: `materialize` and `refresh_calendar` run under the engine mutex (RLock, re-entrant from `confirm`/`correct_calendar`); every pre-claim transition (missed, late-run) first re-checks that state and due time are unchanged (`_still`). Test `test_r10_reconciliation_and_pre_claim_are_serialized` (stale read is never acted on; materialize blocks while another holder has the mutex) |
| R10-02 | Medium | the live gate accepted an empty journal and did not bind result and attempts to one run | confirmed | **repaired**: the journal must contain the live service start, v1 and v2 verified with the result's hashes, and the v2 approval; `v1.gif`/`v2.gif` must hash to those values; at least two attempts, all LIVE by `claude_code` |
| R10-03 | Medium | a quoted argument containing the expected text matched; a reused PID could be stopped | confirmed | **repaired**: Windows' own argument splitting (`CommandLineToArgvW`), fixed positions (`<python> -m uri_scheduler.service run ... --state <State>`, full-path comparison), and the process start time must match `service.json` within 120 s. The test runs a real scheduler service process and look-alikes (extra argv, one quoted argument, wrong start time, other state dir) |

## Round 11 (closure) — candidate `a3d4d0f` — **ACCEPT WITH FINDINGS**

Codex: R10-01 / C1-01 **FIXED** (reconciliation and pre-claim serialized; the claim compare-and-set requires an eligible,
due state and an active job; the harness run is outside the mutex, so no deadlock with HTTP threads or the service loop).
C1-02 FIXED. Remaining findings concern only the owner-gated, not-activated logon-task script:

| # | Codex severity | finding | disposition |
|---|---|---|---|
| R10-02 (PARTIAL) | Medium | attempts were not linked to the run's own occurrence | **repaired** (`<this commit>`): every attempt must carry the `occ_id` that journal step `3.persisted_before_due` recorded; test adds attempts of another run |
| R10-03 (PARTIAL) | Medium | a process with the same command and state started within 120 s of the record is accepted | **recorded residual**: such a process is itself a scheduler service for that state directory (the service holds a single-instance lock per state dir), so stopping it is the intended rollback |
| R11-01 | Medium | `uninstall -Apply -State <wrong dir>` stopped and unregistered `URIScheduler` anyway | **repaired**: the registered task's `--state` argument (parsed with Windows' argument splitting) must equal `-State`, otherwise the rollback refuses and changes nothing. Verified by reading only: exercising it needs a registered task, which this phase must not create |

Accepted candidate for integration: this commit (code verified by round 11; the two repairs above are confined to the
dry-run-tested, owner-gated script). Owner gates unchanged: F10 live Claude (login), F2, R7-1, festival activation, logon task.
