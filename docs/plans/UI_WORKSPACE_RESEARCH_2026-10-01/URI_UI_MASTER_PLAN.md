# URI UI/UX master plan

Date: 2026-10-01. **Combined URI Experience selected by the User on 2026-10-01. Planning revision for review; production implementation remains unauthorized and lifecycle gates remain open.** Read [audit](URI_UI_CURRENT_STATE_AUDIT.md), [capability mapping](URI_UI_CAPABILITY_MAPPING.md), [directions](URI_UI_DESIGN_DIRECTIONS.md), [Impeccable adoption](URI_UI_IMPECCABLE_ADOPTION.md) and [backlog](URI_UI_IMPLEMENTATION_BACKLOG.md) together.

Concurrent-repair note: active recovery files changed during drafting. The audit preserves both the rejected baseline and the observed uncommitted progress. Phase 0 consumes the final independently reviewed repair; this plan neither reassigns that work nor assumes its outcome. Existing-projection descriptions below refer to the initial source snapshot unless otherwise marked.

## Product decision and boundaries

URI should feel like one capable colleague with a workspace: ask naturally, see the actual work, review the result, decide when a consequential action needs consent. Companion, workspace and intelligence overview are presentations of the same application, authenticated user, session and runtime. The default conversation does not require choosing a Brain, specialist or harness. Advanced details explain actual execution when requested.

Preserve the approved Hybrid shell: **Home, Chat, Tasks, Connections & Providers, Settings**; one collapsible sidebar, standalone Chat, internal history/activity, same-state Compact mode and four themes. Make the intelligence overview a progressively richer Home with drill-down sections, not a second application. Put working files and artifact review inside Chat. Tasks remains the pending-decision queue until a real general task API exists.

The User selected the combined direction: A is the quick companion, B is the primary unified workspace, and C is the progressively disclosed Intelligence Overview within Home. These are connected presentations of the same URI session/runtime, not competing applications. This product decision preserves the approved visual authority. Any change to the five destinations, frozen runtime interfaces or role model requires a separately reviewed decision. The published Hybrid artifact was not freshly inspected here; no pixel-equivalence claim is made. Existing recorded approval and source are the baseline.

Governing sources remain ADR-018, URI AI Operating Policy, Model↔Runtime Contract, M22 architecture, ORCHESTRATION, four-stage lifecycle and active milestone control. The current assignment explicitly authorizes only planning. Claude is not invoked. Codex remains planner; Antigravity owns the assigned recovery and future UI implementation; the standing UI override names Qwen implementation review and Antigravity repair. This document is not a role reassignment, milestone acceptance or release authorization. When a required model is unavailable, preserve the durable WAITING_FOR_MODEL checkpoint, not silent substitution.

## Confirmed experience and minimum shared contracts

**Governing product principle:** URI should feel like one intelligent companion: simple when the user wants simplicity, powerful when work requires it, and transparent when the user wants to understand its capabilities.

| Selected experience | Existing Hybrid location | Preserved boundary |
|---|---|---|
| Companion (A) | Same-window CompactOverlay | Quick conversation alongside other applications; explicit expand, no second session or automatic focus theft |
| Unified Workspace (B) | Standalone Chat plus existing Tasks/files/results/configuration destinations | Primary work environment; existing result/open actions first, contextual inspector later |
| Intelligence Overview (C) | Home with progressive disclosure and links to existing settings | Four backed summaries; no embedded Chat, invented readiness, or new primary destination |

Reuse the approved Hybrid reference and existing Flutter components. Preserve Graphite, Deep Navy, Slate + Teal and Light Professional through existing semantic tokens. The selected product direction does not authorize a replacement shell or palette.

Minimum shared component/state contracts are specified in [the first-slice plan](URI_UI_FIRST_SLICE_PLAN.md#minimum-shared-components-and-state-contracts): one AppState/UriClient/authenticated session; shared conversation/composer/TurnCard/attachment actions; shared coarse status and decision rendering; existing shell and themes; source-aware read state for Home. Component extraction is conditional on demonstrated duplication, not a new framework.

The first slice precedes the broad six-phase roadmap below and selects only bounded UI work using accepted existing response contracts. It does **not** depend on building the proposed event envelope. New backend projections retain their separate lifecycle gates. The existing audit and capability matrix are evidence inputs, not frozen Stage 1–3 approval artifacts. Before implementation, the accepted recovery commit must be reconciled into the required lifecycle records and the slice's plan review completed.

## Companion experience

Use the existing CompactOverlay and shared conversation/composer. The current native compact size is 440×680, while recorded reference size is 420×580; select final bounds only after DPI/text-scale acceptance. The panel contains URI identity, expand control, latest conversation, one grounded task summary, attachment chips, composer and relevant pending decision. Keep older conversation scrollable and allow user-controlled expansion rather than pinning the window over other work by default.

- **Invoke/restore:** initially retain ordinary Windows minimize/restore and explicit launcher activation. Tray/hotkey support is a later bounded native lifecycle addition, with conflict/focus/accessibility testing. No global key hook is assumed.
- **During work:** show a quiet status in URI; task completion never steals focus. Notification preferences distinguish approvals, failed tasks and results. Default to in-app indicators; optional OS notifications require explicit settings and a verified notification adapter. Aggregate repeated updates; omit filenames/content on lock-screen notifications by default.
- **Quick actions:** start a new chat, attach a file, review the pending decision, open the actual result. List only supported actions. Never add a decorative microphone or shortcut that pretends to operate.
- **Files:** picker first, with progress/rejection and removable staged chips. Windows drag/drop is a proposed later adapter, with the same validation/upload path, no automatic folder crawl, and a keyboard “Attach file” equivalent.
- **Expand:** retain draft, transcript scroll anchor, staged/turn attachments, task id, approval and model selection. Restore workspace bounds/focus after expand; clamp off-screen bounds after display changes. Minimize must not cancel a task or create another session.

## Workspace experience

Chat becomes the place to complete work, retaining its standalone destination. Default layout is conversation plus composer; a contextual **Files & results** pane opens only when files or artifacts exist and the user asks to inspect them. At small widths it becomes a sheet/full-page view. History/Activity remain inside Chat, with links back to the current task.

For a request such as “prepare my mess statement,” URI resolves selected evidence, clarifies missing reference/period/rules, performs supported tools, verifies the candidate workbook, then offers review and any necessary writeback approval. The UI does not contain a mess-specific router or fabricated checklist. Generic runtime events carry concrete labels only for steps that actually happened.

Each artifact card shows filename/type, provenance, draft/candidate state, verification scope and actions supported by its actual FileStore contract. Current OS opening is the safe first review action. Add text/table/image/PDF previews incrementally only for authenticated downloaded bytes with bounded sizes and appropriate viewers. Office documents with no preview use “Open in your app.” Do not introduce a web editor or another independent UI platform.

Approvals display the target, proposed effect, files/services involved, revision/expiry and what will happen. Review first; approve/decline remains runtime-bound. A failed save remains failed. A changed candidate invalidates the previous approval. Long tasks may need stop/resume only after the runtime publishes those contracts; do not relabel existing cancel-proposal as cancel-running-task.

Errors distinguish service unavailable, authorization needed, missing input, stale reference, execution failure, verification failure and outcome unknown. Offer the actual next action—connect, select evidence, retry after reconciliation, review output—without automatically rerunning an ambiguous write. Preserve the user's input and known task identity through recovery.

## Intelligence overview and ability management

Home retains its four backed summaries: pending approvals, unread email, connected services and Brain/provider configuration. Pending tasks and approvals are one source; no duplicate count. Omit deadline and halted-workflow tiles until real sources exist. Show independent loading/error/freshness states per summary.

An expandable **URI's abilities** section opens capability drill-downs: models/providers; qualified specialists; installed skills and runnable tools; authorized memory sources; recent verified results; measured usage; improvement proposals when supported. It must explain both what URI can do and why a specific ability cannot currently run. Installed, authenticated, available and qualified are separate labels with dates/scope. A model verified for provider connectivity is not a specialist qualified for spreadsheet transformation.

Reuse Connections & Providers for configuration. Avoid a second provider settings tree. Skills get provenance/version, dependencies, validation status, permitted effects, current registration and recent outcomes. Metadata “enabled” does not mean executable. Standard users see explanations and permitted actions; only existing server-admin routes can alter install-wide skill state. A catalogue screen cannot grant capabilities, network access or file access.

## Visual memory and knowledge

Start with searchable lists and source-backed detail. Separate **This conversation**, **Remembered facts**, and **Verified task history**. The current Core `/memory` view is not automatically M36. The future M36 projection needs source links, record kinds, freshness, verification/authority and correction semantics before it receives that label.

Show why a memory was considered relevant using recorded retrieval metadata; absent scores must not become invented percentages. Let the user inspect allowed evidence, correct user facts through existing consent-preserving operations, reject pending entries and remove entries where supported. For immutable event history, append a correction linked to the original rather than silently rewrite evidence. Explain the difference between deleting a memory entry and deleting its original file.

Graphify's capability index and per-user GraphStore are separate. Introduce a relationship view only when an authenticated query returns meaningful nodes/edges with sources. Default to “related files/facts” lists; a graph is an optional explanation for an actual path/dependency question. Every edge needs relationship type, provenance and observed/inferred distinction. Do not render repository Graphify data as personal knowledge or decorative simulated networks.

## Proposed execution event contract

**D: additive projection requiring architecture review and a separate integration plan.** Current server SSE emits `message`, `content`, `tool_call_detected`, `error`, `done`; it is narrative streaming, not a durable authoritative task lifecycle. Current Flutter uses POST `/ask`, not SSE. Reuse canonical request/auth/finalization machinery; do not add intercepting middleware or execute actions from event handlers.

Proposed envelope:

```json
{
  "schema_version": "1.0",
  "event_id": "opaque-runtime-id",
  "task_id": "opaque-task-id",
  "turn_id": "opaque-turn-id",
  "session_id": "opaque-session-id",
  "trace_id": "opaque-trace-id",
  "sequence": 12,
  "occurred_at": "2026-10-01T16:45:00Z",
  "type": "verification.completed",
  "state_revision": 4,
  "source": "uri_runtime",
  "payload": {
    "run_id": "opaque-run-id",
    "verification_status": "STRUCTURALLY_VERIFIED",
    "verification_scope": "workbook_structure",
    "receipt_id": "opaque-receipt-id"
  }
}
```

The sample illustrates schema only; it is not a recorded task. Runtime resolves ownership from authentication, not a client-supplied user id. Bind stream/snapshot/replay access to the same principal/session rules as task and file endpoints. Persist bounded redacted events or an authoritative snapshot with replay cursor; select retention and limits in the accepted migration plan. Never include secrets, raw prompts, private file content, chain-of-thought or unredacted CLI output.

| Event | Authoritative emitter/evidence | Minimum payload | Default presentation |
|---|---|---|---|
| `task.started` | Canonical handler after validated intake | task/turn ids, accepted time | Working on your request |
| `context.resolved` | Context/binding resolver | authorized source refs, resolution state, clarification round if needed | Using selected files / need a reference |
| `specialist.selected` | Runtime resolver after qualification/feasibility | specialist id, task class, qualification ref, route reason code | Working; route details collapsed |
| `tool.invoked` | Authorized dispatcher, not model proposal | invocation id, tool id, sanitized action summary | Reading selected files (only for actual read invocation) |
| `approval.requested` | Approval store/gate | approval id, target/effect summary, bound revision, expiry | Needs your decision |
| `progress.updated` | Actual executor milestones | step id, known completed/total units or null, label code | Concrete performed step; no timed fake percent |
| `artifact.generated` | FileStore/workspace recorder after candidate exists | artifact id/hash/version/type/size/run id, candidate state | Candidate ready; verification pending |
| `verification.completed` | URI verifier receipt | run/artifact ids, status/scope/receipt | Checked structure / verified contents as supported |
| `task.failed` | Reconciled runtime outcome | reason code, retryability, known side effects, safe next action | Couldn't complete / outcome unknown |
| `task.completed` | Runtime reconciler after required gates | terminal outcome, output refs, verification refs, writeback state | Result ready for review / applied, as actually true |

Use `task.cancelled`, `task.waiting_for_input` and `task.waiting_for_service` when supported; not all current TurnStage values express these. “Verification completed” may mean failed or structural-only, so it must not automatically render green success. Specialist selection is not progress toward completion. Receiving SSE `done` only closes narrative transport.

Client reduction: accept increasing revisions/sequences; deduplicate event IDs; never regress a terminal task; on gap/out-of-order/cursor expiry fetch authorized snapshot. Stream disconnect shows reconnecting/outcome unknown, not failed or completed. Repeated reconnect must not submit the original request again. New tasks require runtime idempotency tokens; retries must preserve them. Cancellation request stays pending until runtime settlement is confirmed. Source events for experimental adapters never masquerade as verified canonical results.

Execution details expand to a sanitized timeline of tool names, chosen model/harness, timing, actual outcome, verifier scope, approval decision and sources. Show no private reasoning. The user can understand the result without opening it.

## Onboarding and configuration

Use existing bootstrap/login/preferences/Brain onboarding; replace neither authentication nor provider controls. Offer a bounded discovery step for supported executables/runtimes and declared configuration locations. A detector may report installed CLI/version, reachable runtime and installed model inventory; it must not read private folders or open credentials. M38's redacted discovery can inform a future projection but is not a permission grant.

Sequence: connect to this URI runtime → sign in → inspect available execution choices → optionally verify selected provider → explicitly designate a workspace → grant only requested access → perform a fixture task → show its actual result. “Skip for now” remains useful when no Brain is configured. Show installed/authenticated/reachable/qualified independently and do not choose a paid route silently. Keep secrets out of screenshots/events; server changes use existing configuration endpoints, not direct UI file writes. Workspace selection is authorization for its stated scope, not consent to recursively ingest every file.

## Usage and efficiency

Core `/usage` already aggregates measured calls, known prompt/evaluation tokens, durations, outcomes and unavailable records; `estimated_cost` is unavailable in M22.7. Per-turn measured metadata exists. Add read-only usage UI before inventing new meters. Label partial coverage and whether durations are model time, tool time or end-to-end wall time. Do not sum overlapping timers as total duration or interpret CPU/disk snapshots as model token usage.

Use task/run attribution for local/external invocations, failures/retries, tool times and latency distribution when recorded. Subscription access is availability/auth mode; a fixed subscription fee is not measurable per-task API spend. Paid costs show only reported/receipted amounts, currency and source; unknown remains unavailable. “Time saved” is deferred until a disclosed baseline method and sufficient samples exist; allow the user to inspect assumptions, not headline an invented gain.

## Evidence-grounded improvement (future)

Name the user feature **Improvements**; “dreaming” can describe the concept without implying an autonomous system. It reviews authorized verified prior task outcomes and usage, proposing a reusable skill, requalification or cheaper qualified route. A suggestion card includes evidence links, period/sample count, observed repetition, proposed change, expected benefit/assumptions, risks and required qualification/approval. Inspect, dismiss, snooze and request a reviewed change are the first actions.

States: proposed → inspected → qualification requested → qualified proposal → awaiting required approval → applied via established runtime/development process; dismissed/expired may terminate. History is evidence only. Do not implement S9 learning, self-modification, automatically enable skills, change security policy or promote an unqualified model. Suggestions with unverifiable history stay absent. Dismissal is a user preference, not altered qualification or routing authority.

## Design-system foundation

Extend `UriColors`, `UriSpace`, `UriRadius`, shared state components and existing theme persistence. Four approved worlds remain Graphite, Deep Navy, Slate + Teal and Light Professional. Semantic roles cover canvas/surface/elevated, primary/secondary text, borders, accent/focus, selection and success/warning/danger. Remove hard-coded composer colors only in a future bounded assignment. Use separators and aligned rows instead of nested cards; no decorative charts or purple gradients.

Keep current typography identity initially. Proposed legibility floor: 14–16 logical-pixel main text, 12–13 metadata where readable, clear headings 18–24; test scaling rather than force fixed sizes. URI's local advisory skill suggests smaller text in places; use task readability and measured contrast to resolve that during accepted design review. Do not download fonts or replace native system expectations because generic Impeccable warns against them.

Spacing uses 4/8/16/24/32; align regions and keep stable control bounds. Initial adaptation bands to validate: compact 420–480 logical width; narrow workspace below 900; two-pane workspace from 1100 when sufficient actual content exists; large windows at 1440+. These are candidate breakpoints, not current app behavior. Pane min sizes and user resize controls must prevent clipping; collapse content into accessible sheets before shrinking text.

Use Material focusable controls, consistent icons and explicit selected/disabled/expanded labels. Targets at least 40×40 desktop, 44×44 navigation, with generous spacing; measure normal text 4.5:1 and meaningful controls 3:1. Tab/Shift+Tab order follows layout; Enter sends and Shift+Enter inserts newline; Escape dismisses optional panes without discarding drafts or deciding approvals. Future shortcuts must be documented and not override Windows/system/assistive commands.

Motion communicates a transition or new result: restrained cubic 150–250ms, no spring/bounce. Respect reduced-motion/accessible-navigation signals with immediate or small crossfade transitions. Avoid continuous animated status bars and overwhelming Narrator announcements; announce state changes politely and keep actionable errors discoverable.

Reuse/extend: `EmptyState`, `LoadingState`, `StatusPill`, `TurnCard`, clarification/approval blocks, attachment chips and headers. New components should be the smallest shared additions: typed `DataState`, grounded TaskTimeline, ArtifactCollection/Inspector, CapabilityDetail, MemorySourceDetail, UsageSummary and ImprovementProposal. Their client bindings are additive; platform plugins stay behind the existing injected adapters.

## Incremental roadmap

Every new capability/UI integration still requires Stage 1 audit → Stage 2 accepted architecture → Stage 3 bounded migration → Stage 4 component/integration/agent-loop/live validation. These six planning artifacts inform those stages; they are not automatically frozen substitutes. No new milestone number is assigned here.

| Phase | Deliverables and source seams | Dependencies / acceptance | Tests, independent review and risks |
|---|---|---|---|
| 0 Functional recovery | Consume Antigravity's canonical `/ask`, launcher ownership, role config, real M36–M39/harness evidence. Files: adapter, runner, launcher/stop, Core server; changes owned by active work | Repaired exact commit, consumed configs, authenticated/session-bound approval path, real harness/verifier outputs, frozen boundaries, real T1/T2 and owned process lifecycle | Existing recovery acceptance and independent audit, Windows live launch/health/ask/approve/stop. No parallel repair assignment. Gate on final repair, not its report title |
| 1 Functionality and truthful state | Typed client load/error/freshness; request/outcome identity; explicit actual vs requested model; grounded progress prototype using available states. `http_uri_client.dart`, `uri_client.dart`, `app_state.dart`, `uri_turn.dart`, `turn_card.dart`; additive runtime projection only if approved | Phase 0, canonical status contract, approved event/idempotency design. Empty/offline distinguished; no success from prose; resumption doesn't duplicate action | Client transport/error tests, adversarial duplicate/replay/disconnect/foreign-task tests, canonical behavioral trace and live UI. Independent production-path review. Risk: new DTOs accidentally weaken approval or misread old responses |
| 2 Core design system | Token reconciliation, shared loading/error/empty/status/focus components; shell/text-scale/keyboard consistency. `uri_theme.dart`, widgets, composer/shell/settings | Chosen direction; preserved approved themes/navigation; frozen semantic acceptance fixtures. All four palettes and size classes usable | Widget semantics/overflow, goldens, measured contrast, Narrator/DPI captures; Qwen independent UI implementation review per standing role. Risk: visual refactor breaks callbacks or loses state |
| 3 Companion and workspace | Same-window transition, optional notification lifecycle, contextual files/results inspector, multi-artifact support/preview; `platform_window_controller.dart`, `compact_overlay.dart`, `ask_uri_screen.dart`, attachment/model clients; FileStore projection | Phases 1–2; accepted artifact/task/cancellation contracts; any new platform adapter separately reviewed. Draft/session/approval retained on mode change; candidate vs writeback distinction | Widget persistence/preview tests, integration with real fixture files, Windows resize/minimize/restore/file-open/drag-drop if adopted. Independent review + real user task acceptance. Risk: focus theft, unsafe previews, large bytes, stale artifact authorization |
| 4 Intelligence dashboard | Home drill-downs for real abilities, qualified specialists/harnesses, skill ledger, memory/provenance, usage. `home_screen.dart`, capability/settings/connections clients; Core catalogue/graph/usage and future M36 projection | Phases 1–3, qualification provenance/read authorization, no fabricated metrics. Offline/unknown stale status clear; each ability accurately reflects integration and available task scope | API isolation/schema tests, fixture failure states, agent discovery demonstration, Windows progressive disclosure/keyboard live acceptance. Independent review of data origins and frozen boundaries. Risk: conflating Core vs v1 stores, global vs per-user data, misleading qualification |
| 5 Self-improvement experience | Evidence-backed read-only suggestion inbox; inspect/dismiss/qualification request. New projection over approved history/usage; do not alter S9 or runtime policy | Phase 4 plus complete verified outcome history, evidence retention/consent and separately accepted suggestion contract. Every proposal explainable; policy changes use established qualification/approval | Unsupported-history rejection, evidence access/expiry tests, no auto-promotion security tests, live inspect/dismiss flow. Independent policy/architecture review before implementation. Risk: learning inferred from anecdotes, privacy leakage, autonomous authority changes |

Migration policy: capture rollback commit after Phase 0; keep current response/client compatibility while adding projections; pilot new panes/projections behind explicit development flags default off; retain old OS-open path until preview acceptance. Switch one view/binding at a time; do not fork AppState, authentication or execution. Roll back a pane without rolling back verified execution records. Frozen runtime components remain untouched unless their governing process explicitly authorizes an amendment.

Gate evidence packet for each phase: exact source/binary/config revisions; source-path trace; test commands/results and known failures; fixture/data authorization; screenshots with action sequence; runtime event/result/verifier references; independence of reviewer; rollback point and unresolved limitations. An implementation report cannot approve itself. The combined product decision is recorded. The next review is the bounded [first UI slice](URI_UI_FIRST_SLICE_PLAN.md); production remains unauthorized by this assignment.
