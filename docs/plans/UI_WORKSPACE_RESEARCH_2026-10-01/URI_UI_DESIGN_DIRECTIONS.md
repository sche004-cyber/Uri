# Combined URI Experience — confirmed product direction

Date: 2026-10-01. **User product selection recorded: A + B + C as one combined experience. No redesign or production implementation authorized.** All preserve the approved Hybrid five-destination shell, shared session/runtime, standalone Chat and four palettes. The product-selection gate is satisfied; implementation remains gated on the final independently accepted desktop-recovery commit, plan review and applicable lifecycle/role gates.

## Reference basis and visual limits

Start from `docs/design_library/approved/hybrid_ui_2026-09-16.md`, `UI_DESIGN_AUTHORITY.md` and `UI_HYBRID_FROZEN_BLUEPRINT.md` in the primary tree. Supporting structures: Kiranism `src/features/chat/components/{conversation-list,chat-area,message-composer}.tsx`; shadcnstore `nextjs-version/src/app/(dashboard)/chat/components/` and its task table; Tabler `preview/pages/settings.astro` for settings master/detail. These are recorded structural references, not imported code or newly verified upstream file paths. Recheck upstream before using implementation details.

The library's old state descriptions are not current app evidence. Current source already implements standalone Chat and history. The approved record rejects fabricated deadline/halted-workflow tiles, embedded Home chat, duplicate primary histories and task-authoring kanban. None is proposed here. No direct inspection of the published Hybrid artifact or current native screenshot occurred in this assignment.

Schematic visual: [direction comparison](URI_UI_DIRECTION_SCHEMATICS.svg). It shows region allocation only, with illustrative text and no live data, qualification badge or pixel-matching claim. Colors use the recorded Graphite world. Detailed screens below are text wireframes, not working apps.

## A — Companion First

**Experience:** URI stays small beside everyday work. The workspace is an explicit expansion for review, long conversations and configuration. Useful when the user mostly works in Office or another app.

```text
┌ URI                         Expand ┐
│ Conversation                      │
│ User instruction                  │
│ URI reply / grounded task status  │
│ [Review decision / actual result] │
│                                   │
│ Attachment chips                  │
│ Attach  Ask URI…      Auto  Send   │
└───────────────────────────────────┘
           same session ↕
Workspace: sidebar | standalone Chat + optional result inspector
```

Layout: compact 420–480 logical width, adjustable height after native validation; slim header, comfortable single-column conversation, fixed accessible composer. Workspace keeps the existing rail and five destinations; Chat gets most space, results open on request. Advanced intelligence remains Home drill-downs.

Core interactions: invoke/restore explicitly, attach via picker, ask, inspect real task status, review approval, open actual file, expand and return without losing state. Completion is quiet; optional notifications never automatically foreground URI. Long decisions expand into workspace instead of squeezing unreadable controls.

Reuse: `CompactOverlay`, `UriConversationPane`, `UriCommandDock`, `AppState`, `platform_window_controller.dart`, `TurnCard`, attachment adapters. New: quiet notification adapter if selected, compact status summary and reliable native bounds/focus management. Tray/global hotkeys are separately planned dependencies, not assumed features.

Feasibility: strongest immediate source reuse, **low–medium UI effort** after recovery; native lifecycle/notification testing is the main uncertainty. Dependencies: Phase 0 owned-process recovery; truthful state/idempotency; four-theme scaling; artifact opening. Risks: long tasks and evidence review outgrow compact; discoverability of non-chat abilities; focus/DPI errors. Mitigation: explicit Expand/Abilities affordances, accessible workspace fallback.

## B — Unified Workspace

**Experience:** a task begins in conversation and ends in a reviewable file/result. Companion remains a useful alternate mode. This is the closest extension of the existing approved Hybrid structure and the **User-selected primary work environment** within the combined direction.

```text
┌ URI · task/session context ──────────────────────────────┐
│ Rail       │ Chat: conversation/history/activity │ Files │
│ Home       │ User instruction                    │ inputs│
│ Chat       │ URI response + real task timeline    │ result│
│ Tasks      │ Decision / verification summary      │ preview
│ Connections│                                      │ source│
│ Settings   │ Attach  Ask URI…        Auto  Send    │ details
└────────────┴──────────────────────────────────────┴──────┘
Inspector is optional; at narrow widths it becomes a sheet.
```

Layout: existing 5-item sidebar, conversation as main column, optional right inspector. No second inbox/task manager or permanently empty pane. New Chat, history/resume and task execution details remain inside Chat. Home is still a dashboard without a composer.

Core interactions: pick authorized inputs, clarify references, follow truthful milestones, inspect sources and candidate artifacts, compare versions when recorded, approve the specific writeback, resume history. A selected file synchronizes highlight between turn and inspector; it cannot authorize an action merely by being selected.

Reuse: source shell/Chat/history/approval/file widgets and HTTP bindings, four-theme tokens, FileStore, actual v1 verifier/run contracts when integrated. New: ArtifactCollection, read-only preview/inspector, TaskTimeline, pane resize/collapse, explicit result/verification DTO and typed collection states.

Feasibility: **medium incremental effort**, no rewrite. Dependencies: Phase 0 canonical integration; artifact access/hash/version projection; grounded event/snapshot contract; approved preview formats; native file interaction. Risks: multi-pane clutter, weak FileStore↔v1 run identity, stale approvals. Mitigation: single-column default, one inspected artifact, bound candidate revisions, no unsafe preview fallback.

## C — Intelligence Overview

**Experience:** users who maintain URI can inspect readiness and understand which abilities are useful, with work still performed in standalone Chat. It is an operational overview with controlled disclosure, not raw logs surrounding a chatbot.

```text
┌ URI ─────────────────────────────────────────────────────┐
│ Rail       │ Home / intelligence overview                 │
│ Home       │ 4 backed summaries + needs attention          │
│ Chat       │ Abilities (collapsed groups, observed status) │
│ Tasks      │ Models | Specialists | Tools/Skills | Memory  │
│ Connections│ Recent evidence-backed outcomes | Usage      │
│ Settings   │ Open detail → provenance / qualification     │
└────────────┴─────────────────────────────────────────────┘
Open Chat → the same workspace; no embedded Home composer.
```

Layout: moderate Home content density with vertically grouped readiness, abilities and usage. Models/providers, specialists, tools/skills and memory have separate names and provenance but share consistent rows. Drill-down reveals measured latency, evidence scope, version and limitations. Default summaries stay compact; unbacked graphs/counts are absent.

Core interactions: inspect why an ability is unavailable, open existing Connections & Providers configuration, view authorized evidence, navigate to a real pending approval, review measured outcomes, open a memory source or supported relationship view, eventually inspect a grounded improvement suggestion.

Reuse: Home metric components, capability catalogue, provider/connection settings, Core graph/usage/skill routes, memory/history UI. New: unified capability read model, qualification detail, M36 source inspector, partial-measurement usage view, task/run evidence links; improvements depend on later contracts.

Feasibility: **medium–high effort**, chiefly API/data truth work. Dependencies: actual M37/M38 inventory and qualification projection, M36 read authorization, task history/verification attribution and subscription availability discovery. Risks: technical dashboard dominates product identity, global/user state mixing, “installed” mistaken for “ready.” Mitigation: task-oriented ability copy, hidden advanced detail, explicit unknown/limited status and source dates.

## Historical direction comparison

| Criterion | A Companion First | B Unified Workspace | C Intelligence Console |
|---|---|---|---|
| Primary user scene | Working in another app | Completing a file/task in URI | Inspecting and maintaining URI readiness |
| First surface emphasis | Compact conversation | Chat plus contextual result review | Home operational overview |
| Existing reuse | Highest compact reuse | Highest shell/chat/artifact reuse | Reuses Home/configuration, needs richer read projections |
| New data dependencies | Low for basics; task status still required | Artifact/task/verification contracts | Highest qualification/memory/usage requirements |
| Main acceptance task | Ask while elsewhere → quiet result → expand | Select files → execute → verify → review/writeback | Inspect inability → configure → demonstrate actual task |
| Risk | Capabilities hidden | Pane complexity | Excessive density or misleading readiness |
| Relative effort | Low–medium | Medium | Medium–high |

**Decision — User, 2026-10-01:** combine B as the primary workspace, A as quick companion interaction, and C as progressively disclosed Home intelligence. The comparison above records the distinct user scenes, not competing implementation choices. Preserve one session/runtime, the approved Hybrid shell, existing Flutter components and four themes. The [first slice](URI_UI_FIRST_SLICE_PLAN.md) proposes existing conversation/decision/result functionality and Compact continuity; the richer inspector and intelligence projections remain later integration work.

Selection acceptance: chosen direction must preserve the session through compact/workspace transitions, keep Home free of chat, retain explicit decisions and honest unknown states, and pass the same native fixture task/keyboard/scaling matrix. The AI OS reference was not supplied as a URL/image in this assignment; C draws only on the user's stated concept, not an uninspected reference or invented feature list.
