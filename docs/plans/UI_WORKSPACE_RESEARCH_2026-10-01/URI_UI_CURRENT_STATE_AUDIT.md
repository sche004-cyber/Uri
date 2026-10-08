# URI UI current-state audit

Date: 2026-10-01 (Asia/Calcutta). Author: Codex. Status: read-only research delivered; **not release verification, implementation approval, or milestone closure**.

## Scope and evidence

The inspected primary baseline is `C:/Users/cheta/Development/uri-m37-m39-integration`, HEAD `3c8087bc00da31b5e265f38f690db5b1f9275703`, branch `experimental/desktop-recovery-repair`. At the initial inspection it had an untracked `docs/plans/DESKTOP_RECOVERY_REAUDIT_VERDICT.md`. File hashes and probe conditions are in [SOURCE_EVIDENCE.json](SOURCE_EVIDENCE.json). Active repair work changed during drafting; the following findings describe the baseline, not an acceptance judgment on those later edits.

### Concurrent-repair update at delivery

The final hash comparison detected changes to `uri_desktop_adapter.py`, `run_desktop_server.py`, `launch_desktop.ps1` and `stop_desktop.ps1`; a subsequent Git diff also showed a change to `uri_workspace/model_roles.json`. These were concurrent external edits, not edits made by this planning assignment. The observed diff removes the intercepting middleware and replaces it with a `/desktop/status` inventory endpoint; it also revises model-role loading, port/PID startup and UI/server shutdown handling. The inventory explicitly distinguishes importable components from execution. This is meaningful source progress, **not proof of completed canonical M36–M39 integration, endpoint classification, live lifecycle correctness or independent acceptance**. The endpoint's route/security projection also needs the active repair's review; this assignment did not audit the new endpoint.

No fresh accepted recovery report, committed repair checkpoint, tests or live UI evidence was supplied during this assignment. F01–F04 therefore remain **baseline findings requiring reconciliation**, not assertions that the later dirty implementation still contains every defect. All source line references to those four moving files refer to the original baseline. [DELIVERY_SOURCE_DRIFT.json](DELIVERY_SOURCE_DRIFT.json) records the comparison and delivery status. Re-read the final repaired commit and independent verdict before implementing any backlog item.

Reference trees: legacy `C:/Users/cheta/Development/uri-agent`, `master` at `e8e3b65259c45fc823addc3ef8969425a265bd1b`; URI v1 `C:/Users/cheta/Development/Uri/_V1`, detached `62d564c` with substantial unrelated dirty work; experimental Git ref `claude/harness-first-edge` at `86de4c02a8bed2e3ff8ee4193c3616ee99aa410b`. The experimental ref was inspected with `git show`, without checkout or invocation of Claude. No branch, index, launcher, runtime configuration, application source, test, or dependency was changed.

Evidence labels used throughout this package:

- **S — Source:** observed implementation at the primary snapshot; does not prove a live control works.
- **R — Recorded:** prior audit/qualification report, attributed to its revision/environment; not reproduced here.
- **P — Probe:** fresh read-only process/network observation.
- **D — Design:** proposed future contract or behavior, not existing functionality.
- **U — Unverified:** insufficient runtime evidence; absence of evidence is not a runtime failure claim.

Graphify queries located `AppState`, `AskUriScreen`, `UriTurn`, `CapabilityRegistry`, `GraphifyIndex`, server and approval paths. The `_V1` graph was used for orientation only: direct primary-tree inspection supersedes its older source locations. No graph rebuild or installation ran.

## Findings that govern this plan

1. **Recovery remains rejected.** Both `docs/plans/DESKTOP_RECOVERY_INDEPENDENT_CODEX_AUDIT.md` and the newer re-audit report return REJECT. The latter evaluates `3c8087b`: desktop middleware intercepts `/ask`, bypassing canonical authentication, context, approval resumption and response finalization. Current source confirms the intercept at `uri_desktop_adapter.py:425–437` [S/R]. Do not accept a UI success state from this adapter as integration evidence.
2. **M36–M38 qualification and desktop connectivity are different facts.** The newer freeze record `docs/plans/URI_BATCH_M36_M37_M38_FREEZE_RECORD.md` freezes `bd7c450` with documented limitations and supersedes `62d564c`. Its historical implementation reports still say provisional. This package uses the newer record for component qualification, not as proof of live desktop wiring [R].
3. **M39 is an isolated Office capability/demonstrator.** `docs/reviews/M39_RECHECK_e9c891f.md` records successful Linux reproduction but Windows and live closing gates NOT RUN, and keeps M39 provisional. `M39_LIVE_APP_INTEGRATION.md` is a prepared, unapplied design. The desktop adapter does not call `OfficeSession` [S/R].
4. **The UI already contains much of the desired shell.** Five destinations, standalone Chat, internal history/activity, shared compact mode, four themes, real HTTP bindings and plugin adapters exist [S]. A complete rewrite is unnecessary.
5. **Old prose can describe obsolete code.** `uri_client.dart` still says only a mock client exists; actual `main.dart` constructs `HttpUriClient`. The chat/provider design-library READMEs retain 2026-09-15 layouts, superseded by current source and the approved Hybrid record. Their reference patterns remain useful; their current-state paragraphs are historical [S].

## Fresh runtime observations and limits

The process probe found no `uri_ui` process. No port-8000 listener was returned; `GET http://127.0.0.1:8000/health` failed with connection refused [P]. Python processes existed, but their identity was not inferred from names. A Release `uri_ui.exe` exists, dated 2026-10-01; existence/timestamp does not establish which source or backend it uses [S].

Native Windows control is disabled in this session. Therefore **no fresh launch, click, keyboard, resize, minimize/restore, approval, or screenshot test was performed**. No server was started or stopped: doing so would disturb the active recovery environment and create runtime state. No widget/full-suite tests ran. Existing test files are coverage candidates, not passes from this assignment. Historical design-library screenshots are reference-app captures, not current URI screenshots.

## Functional inventory

Source paths below are relative to the primary root. Every row is S/U unless a stronger label is explicit.

| Surface/control | Actual source path and binding | Assessment and remaining observation |
|---|---|---|
| Launch/reopen | `launch_desktop.ps1`; `run_desktop_server.py`; `stop_desktop.ps1` | Health wait and named launcher mutex exist. Re-audit identifies port conflict, UI publication race and shutdown ownership defects. Phase 0 owner: active recovery. |
| First run/login | `main.dart`; `app.dart:_RootGate`; `screens/bootstrap/`, `screens/auth/` | Preferences, address, theme and session load before `runApp`; health bootstrap precedes login. Startup latency and error recovery need observation. |
| Navigation | `widgets/app_shell.dart:24`; `app.dart:318` | Home, Chat, Tasks, Connections & Providers, Settings. Chat is actually routed; obsolete Chat→Home warning is resolved in source. Verify focus preservation and narrow layout. |
| Chat/send | `screens/ask/ask_uri_screen.dart`; `AppState.ask`; `http_uri_client.dart:310,393` | One POST `/ask`, pending turn and final parsing. Enter sends; Shift+Enter preserved. HTTP client has no streaming subscription. Canonical behavior blocked by adapter. |
| Model choice | Composer selector; `listProviders`, `setActiveBrain`, model override | Existing provider choice available. Requested model may fall back to serving label; distinguish requested from measured actual model. |
| Attach/open | `platform_file_picker.dart`; upload/list/download `/files`; `platform_attachment_opener.dart` | Real picker injected only by main; downloaded bytes written to temporary file and opened via OS. No embedded document preview. Test canceled picker, invalid filename, missing viewer, stale session and cleanup policy. |
| Generated result | `ActionResult.generatedFile`; `turn_card.dart` | One generated file and draft text supported; multi-artifact/version model absent. File open callback is not proof of a generated file. |
| History/new chat | `screens/history/history_screen.dart`; `AppState.resumeSession`; `/history` | Source supports list/resume/delete/new session. Verify attachment association and in-flight transition handling. |
| Execution feedback | `TurnStage`; `_ProcessingBlock`; final `execution.status` parsing | Coarse state only. No authoritative step-by-step task event stream or replay contract. Preserve neutral processing until events exist. |
| Approve/cancel | `tasks_screen.dart`; `turn_card.dart`; `/approve`, `/cancel` | Real pending-action queue, single-use runtime gate. Verify through desktop `/ask`, not isolated `ApprovalGate` tests. |
| Compact/expand | `compact_overlay.dart`; `platform_window_controller.dart` | Shared AppState/transcript/composer; actual Windows resize to 440×680 and bounds restoration. Approved prototype was 420×580; test both and reconcile rather than silently change the spec. |
| Minimize/restore | Native frame; launcher window activation | No tray/notification lifecycle established. Verify task persistence after minimize and no unsolicited foreground activation on completion. |
| Connections | `connections_providers_screen.dart`; OAuth authorization/disconnect | Separate service and provider sections. OAuth requires actual consent; configuration/authenticated/verified states must remain distinct. |
| Settings/themes | `settings_shell.dart`; `theme/uri_theme.dart`; `ThemeStore` | Four palettes and local persistence. Composer still has hard-coded blue send color and dark mic color at `ask_uri_screen.dart:496–509`; source-level drift. |
| Memory | `memory_settings_screen.dart`; `memory_context_settings_screen.dart`; `/memory` | Core memory view/edit/delete/confirm/reject and context settings. Not a UI for M36's record/retrieval/provenance model. |
| Capabilities | `capabilities_settings_screen.dart`; `/capabilities` | Runtime catalogue represented. Client collapses HTTP/network/parse errors into empty list, obscuring unavailable vs truly empty. |
| Voice | `ask_uri_screen.dart:492` | Noninteractive icon with explicit unavailable tooltip. Planned, not a broken implemented microphone. |
| Accessibility | Material controls, tooltips, keyboard composer | Full focus, Narrator, scaling, contrast and reduced-motion acceptance not established by source inspection. |

## Prioritized defect and verification inventory

Severity denotes impact; confidence denotes evidence, not an acceptance verdict. IDs are reused by the backlog.

| ID | Priority | Evidence / reproduction prerequisite | User impact | Disposition |
|---|---|---|---|---|
| F01 | P0 | S/R: middleware `/ask` short circuit; future test anonymous/foreign-session ask and pending approval resumption | Authority bypass and inconsistent behavior | Phase 0 active repair; consume its audit, do not duplicate implementation |
| F02 | P0 | S/R: `_execute_harness_task:216` probes CLI/writes instruction but returns processed; imports of memory/RAR are not actual calls | False successful execution and fabricated integration | Phase 0 active repair; require real run/verifier/lineage evidence |
| F03 | P1 | S/R: occupied port warns then starts; mutex released before UI readiness; stop targets process name | Duplicate app/server or unrelated process termination | Phase 0 active repair with owned-process tests |
| F04 | P1 | S/R: role JSON has no located consumer; adapter constants substitute configuration | Model selection screen can misdescribe serving runtime | Phase 0 runtime-consumed config evidence |
| F05 | P1 | S: `_askOnce` catches `ClientException` and retries without server idempotency proof | Ambiguous transport failure could duplicate a turn/action | Re-audit retry semantics after recovery; source comment's assurance is insufficient |
| F06 | P1 | S: `listCapabilities:1560`, history/tasks readers degrade to empty | Backend outage looks like no abilities/no work | Typed load outcome; preserve last value as stale, with freshness |
| F07 | P1 | S: client POST-only ask vs server `/ask/stream`; no durable task lifecycle | Long work has no grounded intermediate feedback or reconnect state | Additive event projection after canonical recovery |
| F08 | P2 | S: hard-coded composer blue/dark icon | Theme inconsistency; possible contrast risk (not measured) | Token repair and four-theme captures |
| F09 | P2 | S: fixed compact window, prototype/runtime size mismatch | Scaling/keyboard task controls may not fit | Responsive text-scale/DPI observation, then reconcile bounds |
| F10 | P2 | S: native file open only, singular generated file | Weak review workflow for several artifacts | Incremental artifact collection/preview contract; no fake preview |
| F11 | P2 | U: no native keyboard/Narrator/DPI evidence | Unknown accessibility barriers | Acceptance evidence task, not speculative source defect |
| F12 | P3 | S: stale client/theme comments and design-library reality descriptions | Implementers can reintroduce resolved defects | Documentation reconciliation in future accepted scope |

## Required live battery after recovery

Use a disposable authorized fixture workspace and test accounts, the exact repaired release binary/commit, backend identity and redacted logs. Record screenshot, action sequence, expected/actual state, task/trace ID, server evidence and cleanup for each scenario.

| Scenario | Required result |
|---|---|
| Cold/warm launch, two concurrent launches, occupied port, second unrelated URI binary | One owned backend/UI; explicit conflict refusal; no unrelated process affected |
| Chat greeting, real file read, Office fixture, failure and offline/reconnect | Canonical request→discovery→validation→execution→feedback; truthful terminal state |
| File picker cancel, unsupported/large file, two equal filenames, missing OS viewer | No silent success or cross-file association; actionable rejection/open error |
| Approve/decline/expired approval/replayed approval/foreign session | Correct binding, no execution before decision, no duplicate action |
| All destinations and settings/provider verification/save failure | Correct content, preserved draft/session, actual API response shown |
| Compact/expand mid-turn, minimize/restore, 100/150/200% DPI, 1/1.5/2× text scale | Same task/session/attachments; controls remain reachable; workspace bounds restored |
| Tab/Shift+Tab, Enter/Shift+Enter, Escape, Narrator | Logical traversal, named controls, no focus trap or accidental approval |
| History resume/delete, empty/offline collections, long error, several artifacts | Accurate scope, unavailable differs from empty, no completion from prose |

This audit supplies a baseline and reproduction plan. It does not close Antigravity's recovery or promote any capability to Operational.

## Product-decision planning update — 2026-10-01

The User selected the Combined URI Experience: Companion (A), primary Unified Workspace (B), and progressively disclosed Intelligence Overview (C). This changes planning direction, not the recorded recovery verdict, source snapshot or milestone state. Existing baseline findings above are preserved as historical evidence; moving repair files remain Antigravity-owned.

Targeted read-only corroboration in `C:/Users/cheta/Development/uri-m37-m39-integration` located shared AppState (compact flag, conversation, composerDraft, attachments, conversationModelOverride and isSendingAsk), UriConversationPane/UriCommandDock, CompactOverlay, UriTurn/ActionResult, existing POST `/ask`, and Core inventory/usage/memory/provider/task routes. The [readiness supplement](URI_UI_CAPABILITY_MAPPING.md#intelligence-overview-data-readiness--combined-direction) distinguishes existing backend sources from future projections. No API execution, source edit, recovery re-audit, native launch or screenshot capture occurred in this revision. The integration tree's `uri_ui/integration_test/` directory was absent; inspected unit/widget tests are candidates, not results.

The [first slice](URI_UI_FIRST_SLICE_PLAN.md) is a bounded proposal over existing client contracts and state continuity. It depends on the final independently accepted recovery commit and the required lifecycle/plan gates. Actual Windows before/after screenshots, native actions and canonical traces are required for its later validation. SVG/text wireframes are not acceptance evidence. Production code/tests, recovery implementation, governance state, tracker and project memory remain outside this documentation revision.
