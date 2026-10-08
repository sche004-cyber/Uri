# Festival GIF — Live Test

Driver: `scripts/scheduler_live_test.py` (real `python -m uri_scheduler.service run` process, real HTTP API, real
scheduler clock — no manual tick, no injected time). Evidence: `docs/scheduler/evidence/<leg>/` (`journal.json`,
`result.json`, `events.json`, `attempts.json`, `overview.json`, service logs, GIFs). State databases were moved out of the
repository to `C:\Users\cheta\Development\uri-scheduler-state\evidence_state` (outside the repository) to keep the commit small.

## 1. Acceptance criteria

| id | criterion |
|---|---|
| L-AC1 | Task created through URI (API), persisted before its due time, nothing runs early |
| L-AC2 | Triggered by the scheduler at its due time (measured delay) |
| L-AC3 | The REAL Claude harness generates the GIF content |
| L-AC4 | A real animated GIF is produced and independently verified |
| L-AC5 | Artifact appears in the review interface; one refinement produces v2 (parent v1); v2 approved by sha256; nothing published |
| L-AC6 | Restart, missed execution, unavailable Claude, duplicate startup, cancellation and quota are exercised |
| L-AC7 | Simulated and genuine harness execution are never conflated |

## 2. Results by leg

### Leg A — `fixture_e2e` (genuine scheduler + supervisor, **SYNTHETIC Claude stand-in**) — PASS

| step | time (UTC, 2026-10-08) | result |
|---|---|---|
| 1 service started | 21:02:18.625 | pid recorded, mode `fixture` |
| 2 proposed + confirmed through API | 21:02:18.676 / .699 | `Once at 2026-10-09 02:33:33 (Asia/Kolkata)` |
| 3 persisted before due | 21:02:18.712 | row `SCHEDULED`, 74.3 s before due |
| 4 triggered by the scheduler | 21:03:34.023 | **1.01 s** after due (tick 5 s) |
| 5 harness finished | 21:03:40.062 | supervisor `COMPLETE` (URI-observed postcondition), attempt mode `FIXTURE` |
| 6 GIF v1 verified (by the driver, independently) | 21:03:40.189 | `GIF89a`, 30 frames, 320×320, animated, 6 distinct sampled frames, sha256 `b1065534…` |
| 7 in review interface | 21:03:40.189 | `/overview` pending approval, version 1 |
| 8 refine "More floral energy" | 21:03:40.194 | occurrence `REVISION_QUEUED` |
| 9 GIF v2 verified | 21:03:46.285 | parent = v1, sha256 `22c4ee0e…` ≠ v1, concept records the change |
| 10 approve v2 by sha256 | 21:03:46.321 | occurrence `APPROVED`, v2 `APPROVED`, v1 `SUPERSEDED`, every review event `published: false` |

What is genuine here: the scheduler process, persistence, timing, claim, supervisor admission, contained spawn, stream
interpretation, postcondition check, renderer, GIF verification, review flow, audit chain. What is **simulated**: the
creative content (written by `tests/scheduler/helpers/fake_claude.py`; its research.md says so).

### Leg B — `live_blocked_probe` (genuine scheduler + **REAL Claude CLI gate**) — BLOCKED AS EXPECTED

Same driver, `--mode live --qualification probe --client-home C:\Users\cheta\Development\uri-scheduler-state\client_home` (an isolated, empty client
profile; at run time it lived at `work/scheduler_client_home` inside the worktree, as the journal's argv shows, and was
moved outside the repository afterwards so that a future login's credential file can never be committed). The task was persisted 29.5 s before due and triggered 0.85 s after due. The gate resolved the real native
executable (`…\@anthropic-ai\claude-code\bin\claude.exe`, version 2.1.287), ran `claude auth status` under the client home
and got `loggedIn: false`. Result: occurrence `BLOCKED_HARNESS` / `NOT_AUTHENTICATED`, no attempt consumed, event
`harness.unavailable` with recovery options and `substitution: none (no other or paid provider is ever used)`, automatic
re-check at +30 min. This is genuine evidence for the "Claude unavailable" requirement.

### Leg C — live generation with real Claude — **NOT RUN (BLOCKED: owner login)**

The Claude CLI on this PC is not authenticated in any profile (owner profile: `OAuth session expired and could not be
refreshed`; client profile: never logged in). Logging in is an owner action. Once done, run:

```
python scripts/scheduler_live_test.py --evidence docs/scheduler/evidence/live_claude --mode live --qualification probe --client-home C:\Users\cheta\Development\uri-scheduler-state\client_home --lead-s 90
```

L-AC3 (real Claude generation) and the live parts of L-AC5 therefore remain **unverified**. This affects the final verdict:
the end-to-end chain is qualified with a synthetic harness, and the real-harness link is qualified only up to the gate.

## 3. Other required scenarios (L-AC6)

| scenario | level | evidence | result |
|---|---|---|---|
| Process restart (persistence) | process | `test_kill_during_run_then_restart_recovers` | job and occurrence survive; second `scheduler.started` |
| Kill during execution | process | same test | executor PID gone after the scheduler was killed (kill-on-close job); restart → `occurrence.interrupted` → requeued → completed → GIF served |
| Missed execution | simulation (scripted clock) | `test_missed_execution_runs_late_then_deadline_means_missed`, `test_skip_policy` | run late with `late=1` + event; past deadline → `MISSED`; `skip` policy → `MISSED` |
| Unavailable Claude | **live** + simulation | Leg B; `test_harness_unavailable_blocks_then_recovers` | blocked, recheck, recovers when available |
| Duplicate scheduler startup | process | `test_duplicate_startup_and_api` | second process exits 3, `SCHEDULER_ALREADY_RUNNING` |
| Cancellation | worker + simulation | `test_cancel_while_running_kills_executor`, `test_cancel_pause_resume_reschedule` | running executor killed, result discarded; pending cancelled |
| Quota error | worker (synthetic quota stream) | `test_quota_opens_breaker_and_defers` | supervisor quota decision, breaker open, `QUOTA_DEFERRED`, no attempt consumed, no fallback |

A real provider quota was not induced (it would consume the owner's quota on purpose); the quota path uses the accepted
supervisor's detection on a synthetic stream (`Claude AI usage limit reached|…`).

## 4. Windows lifecycle

Not tested: no OS task was registered (RED). The service ran as a normal user process started by the driver.
`scripts/scheduler_task_ctl.ps1 -Action plan|install` (without `-Apply`) was run and verified to change nothing
(`Get-ScheduledTask URIScheduler` → none).

## 5. Verdict

**Scheduler, persistence, trigger timing, recovery, review/refine/approve: QUALIFIED (process level, synthetic harness).
Real Claude generation: BLOCKED pending the owner's Claude CLI login.** The full completion criterion ("demonstrated
through the actual harness") is not yet met.
