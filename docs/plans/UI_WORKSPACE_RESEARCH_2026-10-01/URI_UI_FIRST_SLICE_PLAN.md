# UI-S1 — Shared conversation, truthful state and Compact continuity

Date: 2026-10-01 (Asia/Calcutta). **Proposed first slice for review; no production implementation authorized.** Product direction: User-selected Combined URI Experience. This is a planning identifier, not an opened or accepted milestone.

URI should feel like one intelligent companion: simple when the user wants simplicity, powerful when work requires it, and transparent when the user wants to understand its capabilities.

## Authority, baseline and entry gate

Preserve [Hybrid design authority](../../design_library/UI_DESIGN_AUTHORITY.md), [approved Hybrid structure](../../design_library/approved/hybrid_ui_2026-09-16.md) and [frozen blueprint](../UI_HYBRID_FROZEN_BLUEPRINT.md). Companion is existing Compact; Workspace is standalone Chat with existing Tasks, files/results and configuration; Intelligence Overview is progressive disclosure within Home. Five destinations, composer ordering, runtime approval controls and four themes remain the baseline. No new layout reference is selected.

Implementation source root is `C:/Users/cheta/Development/uri-m37-m39-integration`; planning edits in this package are in `_V1`. Direct source inspection on 2026-10-01 corroborated the reused Flutter components and Core routes below. The recovery adapter is moving under Antigravity ownership. Neither its dirty code nor the earlier rejected `3c8087b` checkpoint supplies an implementation baseline. No native launch, test or screenshot was performed for this planning revision.

**Required handoff before UI-S1:** exact final recovery commit, independently accepted verdict referencing that commit, binary/config identity, approved scope, canonical request/approval/result trace, Windows lifecycle evidence, known limitations and rollback checkpoint. Do not fill these fields from an uncommitted snapshot or assume acceptance from a report title. Confirm that the repaired desktop serves the authenticated canonical client path. Reconcile only the slice's dependencies; do not repeat completed architecture/security audits.

Antigravity retains active desktop recovery and future UI implementation/repair. Claude and Codex remain planning/independent plan review only under the UI override; Qwen performs implementation review. Governing active scope determines acceptance/release assignments. This proposal neither invokes another agent nor changes role or release authority.

Required lifecycle before code: use the [audit](URI_UI_CURRENT_STATE_AUDIT.md) as evidence input to the slice's Stage 1 root-cause record, reconcile against the accepted recovery commit; obtain Stage 2 canonical architecture and Stage 3 migration/plan acceptance in the required governance paths; then Stage 4 component, integration, canonical-loop and Windows validation. This package does not declare those stages frozen or passed. New contracts are not excused as local bug fixes.

## Minimum shared components and state contracts

Paths below are relative to the implementation source root. Existing members are source evidence; preservation rules are proposed acceptance contracts, not guarantees already live-tested.

| Responsibility | Reuse / owner | Contract across A, B and C |
|---|---|---|
| Identity and session | `services/app_state.dart` AppState; `services/uri_client.dart`; HttpUriClient authenticated session | One principal/client/session. Mode or navigation changes never create a conversation or send a request. Logout follows existing state-clearing rules |
| Presentation/navigation | `app.dart`, `widgets/app_shell.dart`, AppState.isCompact/setCompact; window controller | Compact/Workspace change only presentation. Preserve selected destination and restore existing workspace bounds; Home opens existing destinations, not a second configuration tree |
| Conversation and composer | `screens/ask/ask_uri_screen.dart`: UriConversationPane/UriCommandDock; AppState.conversation/composerDraft/attachments/conversationModelOverride/isSendingAsk | Preserve draft text, staged attachments, transcript/turn identity, model override and pending response. Attachment association stays fixed to its submitted turn. Preserve scroll anchor and sensible keyboard focus across remounts |
| Decision and result | `models/uri_turn.dart`, `widgets/turn_card.dart`, existing task/approval callbacks | Same proposal/decision in either mode. Approve/cancel remain explicit server-bound actions. Show returned sources/draft/generatedFile only when present; OS-open uses existing authenticated file adapter |
| Status/error explanation | Existing TurnCard processing/connection/failure blocks; existing load/error components | Shared wording and semantics. Request pending is not confirmed tool execution; response arrival is not proof of a side effect. Missing execution/verification evidence stays unknown |
| Home information | `screens/home/home_screen.dart`, HomeSummary, existing provider/connections/settings views | Four backed summaries; pending approvals/tasks are one queue. Show current, loading, unavailable and stale states honestly. Reuse links to existing details; no catalogue/projection added in UI-S1 |
| Visual identity | `theme/uri_theme.dart`: UriColors/UriSpace/UriRadius and persisted theme | Graphite, Deep Navy, Slate + Teal, Light Professional. Same tokens/focus/status meaning in Compact, Workspace and Home |

Do not create a parallel AppState, event bus, runtime client, task store, component library or speculative DTO. Share the existing status rendering where duplication is demonstrated; otherwise keep current components. New freshness/typed result contracts for broad catalogue views remain separately reviewed work in the backlog.

## Bounded proposed scope

Objective: complete a real supported request using existing conversation, attachment, decision and result actions, while preserving state through the current Compact/Workspace transition and explaining the actual outcome accurately.

Proposed edit seams after acceptance: only demonstrated presentation/state-continuity defects in `uri_ui/lib/screens/ask/ask_uri_screen.dart`, `widgets/compact_overlay.dart`, `widgets/turn_card.dart`, and the presentation/state portions of `app.dart` and `services/app_state.dart`; existing theme tokens resolve touched controls. Relevant Flutter tests may be extended. These are candidate seams for review, not write authorization. Reuse the existing window controller unchanged; a native-controller defect belongs to a separately scoped owner/repair decision.

1. Establish the accepted baseline and reproduce slice-specific gaps. Reuse working behavior without rewriting it or claiming an existing capability as newly delivered.
2. Make shared coarse feedback truthful in both modes. Retain neutral processing during POST `/ask`; use returned proposal/approval/needsConnection/result/failure fields. Do not display simulated steps, percentages, specialist selection or verification badges. Distinguish a completed conversation response from confirmed action execution. A transport failure with uncertain side effects must say that completion is unconfirmed and must not offer an automatic re-execution action. If that distinction requires a new runtime contract, hold it for separate integration rather than inventing one locally.
3. Preserve existing draft, attachments, model override, in-flight response and decision state through repeated Compact/Expand and navigation. Use existing picker and OS-open behavior, existing Copy feedback, supported connection actions and approval controls. Preserve their callbacks and authorization semantics.
4. Apply only local Impeccable legibility/edge-state improvements to touched controls: clear hierarchy, restrained spacing, accessible targets/focus, long-text handling, helpful errors, theme-consistent controls. Keep existing geometry and bounds; the 420×580 reference versus 440×680 native implementation remains a measured compatibility question, not a unilateral resize instruction.
5. Produce native before/after evidence and review findings against the frozen structure, source data and functionality criteria. Repair within accepted slice scope through Antigravity.

Protected: `uri_desktop_adapter.py`, `run_desktop_server.py`, `launch_desktop.ps1`, `stop_desktop.ps1`, role configuration, Windows runner/generated plugin files, Core endpoints/auth/approval/dispatcher, and Memory/RAR/Edge/Harness/Office implementation. Preserve unrelated dirty files in both trees. A defect here is reported to its owner, never silently repaired by UI-S1.

Deferred: event-stream/snapshot/replay/idempotency implementation; new artifact collection/preview/editor; drag/drop; tray/global hotkeys/OS notifications; voice; durable task cancellation; new Home metric tiles; M36–M39 inventory/verification integrations; graphs; specialist promotion; skill enabling; improvements/S9 learning. Existing retry behavior is a known integration-review dependency, not something this slice validates as safe merely through UI tests. If acceptance exposes duplicate execution, stop that scenario and route it to the runtime owner.

## Acceptance and proportionate test plan

| Criterion | Required evidence |
|---|---|
| One session and one submission | Repeated mode switches before/during/after ask preserve client session, turn IDs, draft, attachment association and model override; request-count assertion and canonical trace demonstrate no toggle-triggered submission |
| Working supported path | Native picker → canonical supported fixture request → real result/source/draft/file where applicable → result review/open; actual tool discovery, runtime authorization, execution and feedback into Brain response recorded |
| Truthful state and decisions | Pending ask, proposal/approval, needs connection, successful result, runtime failure and uncertain transport outcome remain distinguishable. Narrative success never overrides failed execution; absent receipt never says content-verified |
| Approval boundary intact | Real fixture proposal; explicit approve and decline in separate cases; same pending identity across Compact/Workspace; actual server result/queue refresh. Existing cancel-proposal is not labeled stop-running-task |
| Existing shell and themes | Home/Chat/Tasks/Connections & Providers/Settings, standalone Chat and four themes retained. No Home composer, duplicated approval count, fabricated capability or metric |
| Native usability | Keyboard completion, visible focus, Narrator labels, readable long filenames/errors, no overflow at target bounds/DPI/text scales; transition/minimize/restore does not steal focus or lose state |

Existing test candidates inspected: `compact_overlay_test.dart`, `chat_lifecycle_test.dart`, `ask_uri_flow_test.dart`, `turn_card_test.dart`, `attachment_ui_test.dart`, `four_theme_persistence_test.dart`, `http_uri_client_test.dart`. Extend only meaningful uncovered behaviors. Run `flutter analyze` and the affected tests, reporting exact results and pre-existing failures. Goldens/semantics/overflow tests supplement native observations and never establish backend authority.

No `uri_ui/integration_test/` directory was present in the inspected integration tree. After separate acceptance of required test/dependency scope, add or reuse a Windows integration harness and run it on `-d windows`; otherwise record the automation gap and retain mandatory live verification. Flutter documents [desktop integration testing](https://docs.flutter.dev/testing/integration-tests) and [accessibility guideline testing](https://docs.flutter.dev/ui/accessibility/accessibility-testing). Those checks complement actual Windows plugin, focus, file-open and Narrator evidence; they cannot replace it.

## Actual Windows screenshot validation

Antigravity or the assigned Windows validation operator captures the running native URI app after recovery acceptance. Use authorized synthetic fixture data. Do not start/stop the active repair runtime for this planning package. Text wireframes and the direction SVG remain explanatory only; they cannot satisfy this gate.

Capture baseline and candidate from known source/binary/config revisions, using identical fixture/state/window settings. Record PNG path, SHA-256, timestamp/timezone, commit/binary/config identity, Windows/Flutter version, logical and physical bounds, display DPI, text scale, theme, action sequence and sanitized session/turn/approval/result references. No secrets or private user data in captures. Keep uncropped originals as evidence; annotated copies may explain findings without replacing originals.

Minimum capture matrix:

- All four themes: Workspace 1280×900 and current native Compact 440×680, at 100% DPI/text scale; same conversation/decision content for comparison.
- Graphite and Light Professional: narrow Workspace at 900 logical width and Compact, at 150%/200% display scaling and 200% text scaling; record actual available display bounds. Evaluate the 420×580 reference fit in widget fixtures, and on Windows only if the accepted native controller can reach it without a new implementation change.
- Native states: empty conversation; draft plus staged file; request pending; actual approval; declined/successful/failed result; needs connection; unavailable/uncertain outcome. Capture the same turn before Compact, in Compact, and after Expand.
- Minimize/restore and keyboard/Narrator operation: before/after captures plus action log. A still image cannot prove focus behavior, request uniqueness or assistive usability; include observations and runtime evidence.

Impeccable review checks hierarchy, spacing, uncluttered disclosure, readable status, actionable decision contrast, theme consistency and edge cases. Native Flutter review checks overflow/semantics, keyboard, text scaling, plugin behavior and lifecycle. No purple gradients, nested-card clutter, fabricated charts or bouncy motion. New motion is unnecessary; preserve restrained existing behavior and reduced-motion preferences.

Every capture has a pass/finding/NOT RUN disposition with the criterion and affected control. Reviewer reports concrete findings against the frozen blueprint; missing Windows access leaves the live gate open rather than replacing screenshots with HTML/browser renders. Screenshot similarity alone cannot approve behavior or execution truth.

## Review handoff and rollback

Deliver the final recovery handoff, exact bounded file scope, reconciled lifecycle records, acceptance fixtures, test logs/known failures, native capture manifest and runtime trace to the assigned reviewers. Codex/Claude review this plan; Qwen reviews Antigravity's implementation; Antigravity repairs. No milestone completion, freeze, commit or push is claimed by this package.

Rollback UI presentation to the final independently accepted recovery/UI commit without replaying a request or deleting execution/approval records. Do not reset an entire dirty worktree. Stop for an unsupported canonical path, required protected-file change, missing authoritative status, new security/authority contract, or absent recovery acceptance. Record the gap and retain the owning dependency. Later Intelligence Overview work follows the [data readiness matrix](URI_UI_CAPABILITY_MAPPING.md#intelligence-overview-data-readiness--combined-direction).
