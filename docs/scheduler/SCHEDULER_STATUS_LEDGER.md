# URI Scheduler — Status Ledger

Ladder: **Proposed → Implemented → Qualified → Frozen**. "Qualified" means demonstrated by the stated evidence level;
levels are never merged: **S** automated simulation (scripted harness in-process), **W** worker-level integration (real
accepted supervisor + synthetic Claude stand-in process), **P** process-level (real service process + HTTP API), **L** live
(real Claude CLI). Nothing is Frozen.

| capability | status | evidence level | evidence |
|---|---|---|---|
| One-time schedules (local wall time, IANA zone) | Qualified | S, P | `test_timespec_calendar.py`; live test journals step 2–4 |
| Recurring schedules (hourly…yearly, interval, weekdays, end) | Implemented, unit-tested | S | `test_daily_weekly_monthly_yearly`, `test_interval_and_end` |
| Calendar-relative schedules (T−2 days, configurable time) | Qualified (logic); **not activated** | S, P | engine + process tests; owner approval pending |
| Asia/Kolkata default, DST-safe conversion | Qualified | S | `test_once_is_local_wall_time_in_kolkata`, `test_dst_zone_gap_is_normalized` |
| Persistence across restart | Qualified | S, P | `test_due_run_..._persists_across_restart`, `test_kill_during_run_then_restart_recovers` |
| Missed-execution detection (run late / skip / deadline → MISSED) | Qualified | S | `test_missed_execution_runs_late_then_deadline_means_missed`, `test_skip_policy` |
| Duplicate prevention (unique key, CAS claim incl. job state, single instance, deterministic task id; recovery never re-runs finished work, uncertain work goes to the owner) | Qualified | S, W, P | `test_duplicate_scheduler_refused`, `test_duplicate_startup_and_api`, `test_crashing_executor_retries_then_fails`, `test_r1_restart_reconciles_before_rerunning`, `test_r2_*` |
| Calendar refresh moves/withdraws, never duplicates | Qualified | S | `test_calendar_refresh_moves_not_duplicates` |
| Pause / resume / cancel / reschedule | Qualified | S, P | `test_cancel_pause_resume_reschedule`; API |
| Cancel while running (executor killed) | Qualified | W | `test_cancel_while_running_kills_executor` |
| Retry with backoff; uncertain never auto-retried | Qualified | S, W | engine + supervised tests |
| Interrupted execution recovery (process killed mid-run; reconciliation with the supervisor ledger) | Qualified | S, P | `test_interrupted_run_is_requeued_with_context`, `test_r1_*`, `test_r2_*`, `test_kill_during_run_then_restart_recovers` (executor PID gone after kill) |
| Harness unavailable → BLOCKED, no substitution | Qualified | S, **L** | `test_harness_unavailable_blocks_then_recovers`; live journal `live_blocked_probe` (real `claude.exe`, `NOT_AUTHENTICATED`) |
| Quota exhaustion → breaker + QUOTA_DEFERRED | Qualified | S, W | `test_quota_defers_without_fallback`, `test_quota_opens_breaker_and_defers` (synthetic quota stream) |
| Ownership / permission enforcement | Qualified | S, P | `NOT_OWNER` assertions; authority-widening refusals |
| Audit receipts (attempt receipts, hash-chained append-only events) | Qualified | S, P | `verify_chain` in tests and `/status` |
| Claude harness adapter (gate + supervised run) | Implemented; gate Qualified at L for the *unavailable* path; generation path Qualified at W only | W, L(blocked) | live generation **BLOCKED**: CLI not logged in (owner action) |
| Phase 2D qualification gate for scheduled runs | Implemented, tested only for "no record" | S | no Claude record exists on any install |
| Festival calendar data 2026–2027 (GoI) | Implemented; dates from secondary transcriptions | — | FESTIVAL_CALENDAR_PLAN.md |
| Sikkim festival dates | Proposed (unverified, excluded) | — | owner confirmation needed |
| GIF template (package, instructions, collect) | Qualified at W/P with synthetic content; L pending | W, P | fixture E2E journal |
| URI renderer + animated-GIF verification + legibility | Qualified | S, P | `test_renderer_gif.py`; journals step 6/9 |
| Review: approve / refine / regenerate / reject, sha256-bound, approval invalidation | Qualified | S, P | `test_review_binding_refine_regenerate_reject`; fixture E2E steps 8–10 |
| No publication path | Qualified (by absence + assertion) | S, P | no endpoint; `published: False` asserted |
| Local HTTP API with token | Qualified | P | `test_duplicate_startup_and_api` (401 without token) |
| UI: Dashboard tile + Scheduler view | Implemented, widget-tested | S | `uri_ui/test/scheduler_view_test.dart`; not exercised in the built Windows app |
| NL request → proposal ("make me a GIF two days before…") | Proposed | — | button-driven proposal only |
| Windows lifecycle (URIScheduler logon task) | Proposed (script, dry-run verified) | — | registration is RED |
| A2UI presentation | Proposed (evaluation only) | — | — |

| Calendar dates beyond the approved proposal / moved dates wait for owner confirmation | Qualified | S | `test_r1_dates_beyond_the_shown_preview_wait_for_confirmation`, `test_calendar_refresh_moves_not_duplicates`; UI widget test |
| Claude executor write permission (`--allowedTools Edit(./**)` under `dontAsk`) | Implemented; not observed live | — | docs-based; first live run will show it |
