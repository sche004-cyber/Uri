# URI Scheduler — Architecture

Status: implemented and tested on branch `phase/scheduler` (see SCHEDULER_STATUS_LEDGER.md for the per-capability ladder).
Nothing here is frozen, merged or registered with Windows.

## 1. Acceptance criteria (defined before implementation)

| id | criterion | evidence |
|---|---|---|
| A-AC1 | Scheduler runs without the Brain, a UI window or a conversation | `uri_scheduler` imports no OI/Brain module; service process alone runs jobs (`test_service_process.py`, live test journal) |
| A-AC2 | One-time, recurring and calendar-relative schedules; Asia/Kolkata default; DST-safe | `timespec.py`; `test_timespec_calendar.py` |
| A-AC3 | Jobs persist across restarts; missed executions detected; no occurrence is created twice and no finished harness work is re-run by the scheduler's own recovery | `store.py` UNIQUE(job, key) + CAS claim + OS lock + restart reconciliation; `test_engine.py`, `test_service_process.py` |
| A-AC4 | Pause, resume, cancel, reschedule; history and audit receipts | engine API; hash-chained `event` table; attempt receipts |
| A-AC5 | Owner confirmation before activation; ownership enforced on every mutation | `propose`/`confirm(proposal_sha256)`; `NOT_OWNER` tests |
| A-AC6 | Harness execution through the accepted supervisor, authority re-validated at dispatch, no paid/other-provider substitution | `harness.py`; `test_supervised.py`; live-blocked journal |
| A-AC7 | Review bound to artifact sha256; refinement invalidates prior approval; nothing published | `engine.review`; tests; no publish endpoint exists |
| A-AC8 | No frozen file changed; accepted gates not weakened | regression chain on materialized tree; guard lists extended by exact path only |

## 2. Placement

```
                   +------------------------------- URI Scheduler service (python -m uri_scheduler.service run) -----+
 Living UI  --HTTP-->  API 127.0.0.1 + bearer token   |   run loop (tick every N s)                                       |
 (Dashboard tile,     propose/confirm/pause/review    |     materialize (timespec + calendar) -> occurrence rows         |
  Scheduler view)                                     |     due? missed? deadline? -> CAS claim -> authority re-check     |
                                                      |     harness gate (installed, Phase 2D qualified, auth probe)     |
                                                      |     task package -> uri_supervisor (accepted, unchanged)         |
                                                      |         contained Claude Code (client-profile home)              |
                                                      |     collect -> URI renderer -> GIF verify -> artifact + review   |
                                                      |   scheduler.db (WAL, FULL)   supervisor/ledger.db   outputs/      |
                                                      +-------------------------------------------------------------------+
```

The scheduler is an operational service beside Core, like the OI host and the supervised worker: Core (frozen) is not
edited, and the Brain is never consulted for timing, authority or execution.

## 3. Components

| module | responsibility |
|---|---|
| `timespec.py` | `once` / `recurring` (hourly…yearly, interval, weekdays, end) / `calendar_relative` (offset days, local time). Local wall time → UTC through `zoneinfo`; DST gaps normalized; months without the day skipped (RFC 5545). Stable occurrence keys (`festival:year` for calendar events) |
| `calendar_store.py` | Versioned calendar files with per-occurrence `source` and `status` (`published` / `unverified` / `withdrawn`); owner confirmation of unverified records; `diff` between versions |
| `store.py` | SQLite (WAL, `synchronous=FULL`, `BEGIN IMMEDIATE`): job, occurrence (UNIQUE job+key), attempt (UNIQUE supervisor task id), artifact (UNIQUE occurrence+version), review (append-only trigger), event (append-only triggers + SHA-256 hash chain), calendar snapshots |
| `engine.py` | Proposal/activation, materialization (insert, calendar-move, withdraw), tick (rechecks, due detection, missed/deadline policy, CAS claim), dispatch (authority re-validation, gate, attempt, package, run, collect, render, validate, artifact), retry/backoff, quota deferral, uncertainty escalation, restart recovery, review actions, UI overview |
| `harness.py` | Gate + supervised execution. Reuses `uri_supervisor.Supervisor`, `CLAUDE_CODE` spec and quota breakers; Phase 2D `compose_client`/`native_auth_probe`; restart revocation copied from `SupervisorBridge` |
| `gif_task.py` | `festival_gif.v1` template: package, instructions, output collection, render + validation |
| `renderer.py` | Declarative `uri.scene.v1` → frames (2× supersampled, Pillow) → shared-palette GIF with a size ladder; structural loop safety; legibility check |
| `service.py` | Single-instance process, run loop, local HTTP API, CLI (`run`, `status`, `festivals`) |
| `scripts/scheduler_task_ctl.ps1` | Owner-gated `URIScheduler` logon task (plan/dry-run by default) |
| UI | `scheduler_client.dart`, `screens/scheduler/scheduler_view.dart`, one Dashboard tile |

## 4. State machines

Job: `PROPOSED → ACTIVE ⇄ PAUSED → CANCELLED`. Activation requires the owner and the exact `proposal_sha256` of the
interpretation that was shown (dates, sources, exclusions, authority, policy).

Occurrence: see the docstring of `uri_scheduler/engine.py`. Terminal: `APPROVED`, `REJECTED`, `FAILED`, `MISSED`,
`CANCELLED`. Owner recovery: `retry` (BLOCKED/QUOTA/FAILED/NEEDS_ATTENTION/MISSED), `reschedule`, `cancel`.

## 5. Behaviour decisions

| topic | decision |
|---|---|
| Missed execution | Due + grace (default 600 s) passed: policy `run_late` (default; flagged `late`, event `occurrence.missed_execution_detected`) or `skip`. A calendar occurrence whose festival day has begun (deadline = festival date 00:00 local) becomes `MISSED`; an explicit owner reschedule past it is honoured |
| Duplicates | UNIQUE(job, key); compare-and-set claim (including the job state); OS file lock `scheduler.lock` (second process exits `SCHEDULER_ALREADY_RUNNING`, code 3); supervisor's own lock; deterministic supervisor task id per attempt (uuid5) so one attempt can never create two tasks; an artifact already recorded for an attempt is filed for review, never rendered twice. Scope of the guarantee: after a crash or a URI-side failure, a harness run is repeated only when the supervisor ledger proves the earlier run never started or left no effect; finished work is collected, not re-run; anything in between goes to the owner (`NEEDS_ATTENTION`). The one deliberate exception is the content retry below |
| Content retry | When a FINISHED harness run produced unusable output (files missing or invalid, or the rendered GIF fails the animated/legibility/size gate), the scheduler asks the harness for new content as a new attempt under the job's retry budget (`max_attempts`, backoff). This is a separate, policy-authorized generation, recorded with `content_retry: true` in the attempt receipt; it is not a duplicate of usable work, because nothing usable exists to collect |
| Calendar refresh | Same key → occurrence **moved** (event `occurrence.moved_by_calendar`); removed record → `CANCELLED` (`CALENDAR_WITHDRAWN`); owner-rescheduled occurrences are never moved by the calendar |
| Owner-confirmed dates (review round 1, F4) | Activation confirms exactly the festival dates shown in the proposal (`confirmed_dates`). Any occurrence whose festival date was not shown — beyond the preview window, a newly published year, or a date moved by a calendar refresh — is created/moved into `AWAITING_CONFIRMATION` and never runs until the owner confirms that date (`confirm_occurrence`, UI *Confirm date*) |
| Retry | Failures retry with backoff (300 s, 1800 s) up to `max_attempts` (3); revision requests get a fresh budget but never reuse an attempt identity |
| Harness unavailable | `BLOCKED_HARNESS` with the gate code; no attempt consumed; automatic re-check every 1800 s; owner Retry/Reschedule/Cancel; event states "no other or paid provider is ever used" |
| Quota | Supervisor detects quota from the persisted stream and opens the per-provider breaker; occurrence `QUOTA_DEFERRED` until the provider reset (or +3600 s); no attempt consumed |
| Uncertain outcome | `NEEDS_ATTENTION`, never auto-retried (supervisor semantics: effects may have happened) |
| Interrupted process | Startup reconciles every `RUNNING` occurrence against its LATEST attempt (ended or not) before anything re-runs (review rounds 1-2, F3/F1): artifact already recorded → `AWAITING_REVIEW`; supervisor task `COMPLETE` → `COLLECT_PENDING` (URI collects and renders the finished files; the harness is not re-run); executor never spawned, or every declared effect proven absent with no tool activity → requeued with its context; otherwise → `NEEDS_ATTENTION` (owner decides). Collection is claimed and its attempt reopened in one transaction. URI-side failures after the harness finished (render, file I/O) retry collection with backoff and never re-run the harness (round 2, F2). Supervisor-side: restart revokes unfinished task authority (bridge discipline); the executor died with its kill-on-close job |
| Cancellation | Before running: `CANCELLED`. Recorded while the gate runs: settled before any attempt exists. After the attempt exists: the supervisor task is withdrawn (never submitted; or ended `spawn_failed` between admission and the post-admission check; or killed through its job object while running) and the result discarded. Every occurrence transition honours a recorded cancellation (`_set_occ`). **Residual window (recorded limitation, inherited from the accepted supervisor/bridge):** a cancel arriving after the post-admission check but before the supervisor marks the attempt active cannot stop the process start; the kill is pre-armed and happens at the first supervision poll, milliseconds after start. A never-start guarantee needs a change to the accepted supervisor (owner decision) |
| Authority | Job grant fixed at proposal and re-validated at every dispatch: harness `claude_code` only, tools ⊆ {Read, Edit, Write, Glob, Grep}, `network`/`publish`/`paid_services` must be false (setting any is refused as an owner decision). Supervisor scope: `read`/`local_write` inside a fresh per-attempt workspace, the one executor, validity ≤ festival deadline. The claim's compare-and-set includes the job state, so a job cancelled after selection is never claimed (round 1, F7). Template parameters are shape-checked (`festival.key` must be a slug) and output names are slugged and path-contained (round 1, F8) |
| Filesystem boundary of the Claude executor (rounds 1-2, F2/F4) | Enforced by Claude Code's own permission engine, not by an OS sandbox: `--permission-mode dontAsk` (accepted profile) denies anything outside the working directory and every un-approved edit; the scheduler adds ONE rule, `--allowedTools Edit(./**)`, relative to the per-attempt workspace (the process cwd). Claude Code applies Edit rules to all built-in file-editing tools including Write; path-scoped Write rules are not consulted, so none is passed. Without this rule `dontAsk` would deny the output files entirely. The supervisor fingerprints only the workspace, so a write elsewhere would not be detected by URI. **Recorded limitation, owner acceptance required**; based on the Claude Code permissions documentation, not yet observed in a live run |
| API identity (round 1, F1) | One service instance acts for exactly one principal (`--owner`). The bearer token authenticates that principal; a request naming another principal is refused `403 PRINCIPAL_MISMATCH`; reads are filtered to the owner's jobs |
| Review | Every decision names the artifact sha256, and the file on disk is re-hashed at decision time. Refine on an approved version records `approval.invalidated` and returns it to candidate; the new version supersedes it. Regenerate keeps the original. Reject closes the candidate. Review rows are append-only. There is no publish/send/share endpoint |
| Timezone | Stored as UTC µs; displayed in the job's IANA zone (default Asia/Kolkata, no DST, but the code is DST-safe) |

## 6. Claude path

Gate (every dispatch, nothing cached in the engine): resolve `claude` → native `claude.exe` (Phase 2 rule); qualification
`phase2d` (signed client record, production) or `probe` (isolated qualification only, labelled `PROBE_ONLY` in every
receipt); live `claude auth status` with `USERPROFILE`/`HOME` = the client-profile home (verified: the CLI's
`configDirectory` follows `USERPROFILE`). Execution: supervisor task with the frozen `CLAUDE_CODE` argv; instructions on
stdin; postcondition `scene.json` regular and non-empty, observed by URI. Claude researches from its own knowledge plus
the calendar record (no web tool is granted: adding `WebSearch` would widen unattended permissions — owner decision).

## 7. Windows lifecycle

Today the service runs while something starts it (developer shell, test driver, or a future launcher hook). Persistent
operation while URI is closed needs an OS launcher. Recommended: a per-user **AtLogOn** task `URIScheduler`
(`scripts/scheduler_task_ctl.ps1`), mirroring `URIServer`: no elevation, restart on failure, `IgnoreNew`. Missed-execution
detection covers the gaps (PC asleep/off): occurrences are run late on the next start until their deadline.
**Not done (RED):** registering the task. Not qualified in isolation either, because "isolation" on this PC would still mean
registering a task on the production machine; the script's `plan`/dry-run output was verified to change nothing.

## 8. A2UI

A2UI (agent-to-UI declarative surfaces) could later render the review card and the proposal dialog from scheduler-supplied
JSON. The scheduler API is already declarative (overview/proposal are plain JSON with every field the UI shows), so an A2UI
adapter would be a presentation layer only. Not a prerequisite; not implemented.

## 9. Known limits

- Greeting text must be Latin script (Pillow has no libraqm here); Devanagari greetings are refused by validation, not mis-rendered.
- The renderer's motif vocabulary is fixed (glow, rays, bokeh, mandala/rangoli, lotus, diya, lantern, crescent, star,
  polygon, particles, text). Rich illustration (Blender/diffusion) is out of scope without new tools or paid services.
- Render time measured on this PC: 480×480 × 60 frames ≈ 52 s; 320×320 × 30 frames ≈ 6 s. Acceptable for background work.
- Local API: same-user trust (token file readable by the user), as Phase 1 C1.
- The natural-language request ("make me a GIF two days before every major Indian festival") is not routed from the
  conversation yet; the UI exposes it as a button that shows the interpreted schedule for confirmation.
