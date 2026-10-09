# URI Scheduler — Discovery

Date: 2026-10-09 (Asia/Kolkata). Branch `phase/scheduler`, worktree `C:\Users\cheta\Development\uri-scheduler`,
based on `99f8041` (tip of `integration/ws-hardening-20261009`, the active Working System hardening line).

## 1. Acceptance criteria for this discovery

| id | criterion |
|---|---|
| D-AC1 | Every location named in the brief is inspected from primary evidence (files, git, running state), not from summaries |
| D-AC2 | Each existing capability is classified: implemented / tested / accepted / proposed / absent |
| D-AC3 | The decision "reuse, adapt or build" is stated per capability, with the reason |
| D-AC4 | Anything that could not be verified is named, with its effect on the decision |

## 2. What was inspected and what it actually is

| Location | Evidence | Classification | Decision |
|---|---|---|---|
| `C:\Users\cheta\Development\scheduler_proto` | Not a git repository. Flutter app, 7 Dart files (`models/event.dart`, `repositories/event_repository.dart`, `screens/calendar_screen.dart`, …), `shared_preferences` persistence, 1 test file (CRUD + ordering). Last modified 2026-09-16 | **Prototype calendar UI** (create/edit/delete events in a month grid). No execution, no timezone model (naive `DateTime` + `TimeOfDay`), no due detection, no recurrence, no persistence beyond app preferences | Not reusable as a scheduler. Nothing adapted |
| `C:\Users\cheta\Development\qwen_scheduler_benchmark` (+ `uri_scheduler_app/`) | Not a git repository. `PROPOSAL.md` is a model-generated plan for a Flutter "scheduler" calendar app; `lib/main.dart` (122 lines) is the Flutter counter template, byte-identical in both copies; the planned `lib/models`, `repository`, `services`, `screens` directories are empty | **Proposed only** (a model benchmark artefact, 2026-09-16) | Not reusable |
| Core (`uri_core/`) | grep for `schedul|cron|recurr|due_at|run_at` across `uri_core`: only incidental hits (`native_tool_loop.py`, `process_tree.py`) | **Absent**: Core has no time-based scheduling | Build |
| Operational Intelligence (`uri_operational_intelligence/`, accepted on the WS line) | `planner.py`, `triage.py`, `answer.py` mention "schedule" only as a *word in user requests*; `answer.py` explicitly forbids the Brain claiming it scheduled anything; `task_ledger.py` records turn-level tasks, no due times; `perf_monitor.py`/`brain_health.py` sample on demand | **Absent** as a scheduler. No background timer loop exists | Build; keep the Brain out of the scheduling path |
| Phase 2 supervisor (`uri_supervisor/`, accepted, Phase 2 closure r6 + OQ r7) | `supervisor.py` (submit → admit → intent → contained spawn → stream → reconcile), `admission.py` (pools, atomic admission, quota breakers with provider reset), `executors.py` (`CLAUDE_CODE` spec: `-p --output-format stream-json --permission-mode dontAsk --tools Read,Edit,Write,Glob,Grep --strict-mcp-config`, forbidden bypass flags, env allow-list), `recovery.py` (quota detection from persisted stream), single-supervisor lock, kill-on-close job containment (SUP-1) | **Accepted and tested** durable executor for harness work. It has a "scheduler epoch" but it is an *admission* scheduler (who runs next), not a *time* scheduler (when) | **Reuse unchanged** as the execution layer |
| Phase 2 bridge (`uri_supervisor_bridge/`) | `bridge.py` (one Core ticket → one supervisor task; restart revokes unfinished authority), `qualification.py` (Phase 2D signed qualification records, live `claude auth status` probe, client-profile homes ISO-1) | **Accepted**. The bridge requires a Core-issued interactive execution ticket, which a time-triggered job does not have | Reuse `qualification.py` (gate) and copy the bridge's restart/settlement discipline into a scheduler-specific runner; do not edit the bridge |
| Windows Task Scheduler | `Get-ScheduledTask`: `\URIServer` (Running, at-logon, legacy server per `scripts/uri_server_ctl.ps1`), no URI scheduler task. `uri_server_ctl.ps1` shows the house pattern (per-user AtLogOn, RestartCount, IgnoreNew) | **Implemented for the legacy server only** | Reuse the pattern for an owner-gated `URIScheduler` logon task; do not touch `URIServer` |
| Approvals / notifications | `uri_core/core/approval_store.py`, `approval_gate.py`, `approval_resumption.py` gate Core *capability* actions within a turn; the Living UI has `services.work` items and the Phase 2 supervised execution screen; no push/OS notification pathway exists | **Accepted for turn-time approvals**; not addressable for artifact review of a background job without changing frozen Core | Build a scheduler-owned review record (artifact-hash bound) and surface it in the UI |
| UI | `uri_ui/lib/living/` (Living Companion default shell, WS-D4): Companion, Workspace, Dashboard; Dashboard tiles name their data source | **Accepted** WS UI | Add one Dashboard tile + a Scheduler view (new files); no change to the conversation path |
| Claude CLI on this PC | `claude --version` → 2.1.287. `claude auth status` → `loggedIn:false` in the owner profile *and* in the URI client profile. A real `claude -p` call returned `Failed to authenticate: OAuth session expired and could not be refreshed`. The desktop app session is authenticated by its host, not by the CLI's credential store | **Installed, not authenticated** (consistent with Phase 2C: "Claude CLI BLOCKED (login)") | Gate must detect this and block, never substitute |
| Claude qualification | `uri-ws-final/work/c1/ws-final/client/control/supervisor/qualification/` does not exist: no Phase 2D record for any provider on the live install | **Not qualified** | Live runs need a login, then either the Phase 2D record (production) or the explicitly labelled `probe` mode (isolated test) |
| Creative tooling | Pillow 12.3.0 (no libraqm → no complex-script shaping), ffmpeg on PATH, no Blender, no ImageMagick/gifsicle | Available: Pillow + ffmpeg | URI-owned Pillow renderer; Latin-script greeting text only (Devanagari needs raqm — recorded limitation) |
| A2UI | Not present in the repository | **Absent** | Not a prerequisite; evaluated in the architecture doc as a future presentation format |

## 3. Unverified items

- `india.gov.in/calendar` returned HTTP 403 to the research tool, and the DoPT annexure PDFs were not fetched directly; the
  2026/2027 dates come from secondary transcriptions of the cited Office Memoranda (see FESTIVAL_CALENDAR_PLAN.md). Effect:
  every activation shows the dates for owner approval; nothing is activated by default.
- The Sikkim 2026 gazette (Notification 89/Home/2025, Gazette Extraordinary No. 391) was not obtained; the only table found is
  internally inconsistent. Effect: Sikkim records are `unverified` and never scheduled until the owner confirms them.
- Whether `qwen_scheduler_benchmark` was ever run or scored is not recorded anywhere found. No effect (not reused).

## 4. Self-review

D-AC1..D-AC4 met. Correction recorded: the brief's phrase "existing scheduler prototypes" suggested reusable scheduling
logic; primary evidence shows both are calendar-UI artefacts with no execution semantics.
