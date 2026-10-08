# URI UI implementation backlog

Date: 2026-10-01. **Planning only.** Priorities and dependencies are proposals; production implementation is not authorized by this assignment. [Audit finding IDs](URI_UI_CURRENT_STATE_AUDIT.md), [contracts/roadmap](URI_UI_MASTER_PLAN.md), [capability evidence](URI_UI_CAPABILITY_MAPPING.md), [directions](URI_UI_DESIGN_DIRECTIONS.md).

## Execution rules

Primary root for source paths: `C:/Users/cheta/Development/uri-m37-m39-integration`. Current `3c8087b` is a rejected repair snapshot. Phase 0 tasks below are **handoff/acceptance dependencies owned by Antigravity's active repair**, not a duplicate implementation queue. No task is presently declared done. References to source paths are proposed edit seams; they do not grant access to frozen paths.

UI implementation and repair: Antigravity under accepted scope; independent implementation review: Qwen under the standing UI role override; Codex/Claude: planning/independent plan review. Production backend/release assignments follow active governing scope; do not infer a UI reviewer can release a backend/security change. Required unavailable model stages persist WAITING_FOR_MODEL; no substitution. No Claude invocation occurs for this package.

All new adapters, projections and features require separate Stage 1 audit, Stage 2 accepted architecture, Stage 3 bounded migration, Stage 4 canonical/native validation. A task's existing acceptance text is input to those stages, not their approval. A genuinely bounded local known-root-cause bug can use the governance exception only if all four exception conditions hold. The User selected the Combined URI Experience (A+B+C) on 2026-10-01; product selection is complete, implementation authorization is not. Do not open milestones or change tracker/memory from these proposed IDs.

## Phase 0 — consume the repaired functional baseline

| ID / priority | Deliverable / owner | Dependencies | Acceptance and evidence |
|---|---|---|---|
| UI-00 / P0 | Exact recovery handoff packet; Antigravity active repair | None within this planning package | Commit/binary/config hashes; dirty diff; active scope; frozen guard/anchor outputs; real test function inventory incl. T1/T2; known failures; rollback commit. New package must supersede REJECT explicitly, not reuse fabricated T5/T6 evidence |
| UI-01 / P0 | Canonical desktop authority and real execution; F01/F02 | UI-00 | Anonymous/cross-session/replay inputs rejected as applicable; request uses actual Core authenticated context/approval/finalization; real Memory/RAR/Edge/Harness/Office calls only where assigned; false CLI claim cannot complete; verifier receipt and feedback trace. Independent production-path audit and Windows fixture task |
| UI-02 / P1 | Owned startup/shutdown/model config; F03/F04 | UI-00 | Concurrent launches result in one owned UI/server; unhealthy occupied port refuses start; shutdown never kills unrelated instance/PID; actual runtime consumes tracked config; effective model metadata recorded. Windows lifecycle observations and adversarial tests, independent review |

**Gate G0:** UI-00..02 delivered under the active repair, independent review accepted within governing roles, live fixture results available. If only some capabilities are integrated, expose only those and carry the others as not connected; do not reopen frozen components merely to improve the dashboard.

## First bounded UI slice — review before implementation

[UI-S1: Shared conversation, truthful state and Compact continuity](URI_UI_FIRST_SLICE_PLAN.md) is the proposed first UI slice after G0. It selects only local presentation/continuity work from UI-07, UI-09/10/11 and UI-13, using existing accepted contracts. UI-08 records the combined product decision now; independent plan review remains pending. UI-04/05/06, new artifact projections and the expanded intelligence catalogue are later separately governed integration work, not prerequisites that this slice must implement.

G0 must name the final independently accepted recovery commit, reviewer verdict and live evidence. Recovery tasks UI-00..02 remain Antigravity's work. UI-S1 may consume that handoff and existing API fields; it must not modify recovery files or repair backend defects. A discovered backend dependency returns to the owning workflow and holds the affected slice criterion.

## Phase 1 — truthful client behavior and task continuity

| ID / priority | Scope / deliverable | Dependencies | Acceptance / validation |
|---|---|---|---|
| UI-03 / P1 | Typed load outcomes for catalogue/tasks/history/provider/memory; F06. `uri_client.dart`, `http_uri_client.dart`, `app_state.dart`, affected views | G0; accepted result-shape proposal | Empty success differs from unavailable, 401, malformed data and stale cache. Preserve timestamp/last value; retry never silently invents state. Client tests per transport outcome plus real offline/reconnect native screen. UI reviewer checks copy/source trace |
| UI-04 / P1 | Ask retry/idempotency review; F05. client `_askOnce`, canonical intake only if newly authorized | G0; Stage 1 ambiguous-failure reproduction | Server processes one task for a reused idempotency key; dropped connection after intake and approval never duplicates execution; pending outcome reconciled by task id; old client compatibility. Integration fault injection + live reconnect, independent authority review |
| UI-05 / P1 | Authoritative task event/snapshot contract; F07. canonical handler/dispatcher/approval/verifier projection | UI-01; UI-04 design; separate accepted integration plan | Schemas and owners frozen before implementation; ownership enforced from auth; sequence/revision/cursor limits; replay/snapshot retention; redaction; completion linked to actual outcome/receipts. Out-of-order/duplicate/missing/replayed/foreign-event adversarial tests; independent contract review |
| UI-06 / P1 | Grounded task reducer/timeline. `uri_turn.dart`, `app_state.dart`, `turn_card.dart`, HTTP transport | UI-05 implemented and independently reviewed; UI-03 | Narrative tokens or SSE done cannot complete task; no timer-based labels; structural verification clearly scoped; disconnect reconciles without resubmit; terminal revision stable. Reducer tests, captured real runtime events and Windows request→result trace |
| UI-07 / P1 | Approval/actual-model presentation. current decision blocks, provider/client model metadata | UI-01, UI-03; approval/revision field support | Show target/effect/expiry; changed candidate invalidates previous decision; approve/cancel remains server-gated; requested vs actually serving model distinct; missing model unknown. Replay/expiry/change tests plus live decline/approve flow |

**Gate G1:** honest outage/unknown/progress/terminal/approval handling; one canonical fixture task proven without duplicate invocation. A Phase 1 endpoint contract is not allowed to override M22 route classification, grants or user isolation.

## Phase 2 — reusable native design system

| ID / priority | Scope / deliverable | Dependencies | Acceptance / validation |
|---|---|---|---|
| UI-08 / P2 | Direction and reference freeze; product/design records in assigned docs | User combined selection RECORDED; current approved Hybrid evidence | Selected surfaces, reference and exact preserved constraints recorded; missing artifact access disclosed. Preserve the selected combined experience; implementation still requires recovery acceptance and lifecycle/plan gates. Codex/Claude plan review according to availability; no invocation while quota exhausted |
| UI-09 / P2 | Theme/token drift repair; F08. `uri_theme.dart`, composer/shared widgets | G1, UI-08 | All four themes propagate; blue send/dark mic hard-coded values replaced by appropriate roles; body/focus contrast measured; no palette replacement. Four-theme goldens/captures and independent visual review |
| UI-10 / P1 acceptance | Accessibility/keyboard foundation; F11. shell, composer, decisions, shared state widgets | UI-08/09 | Full task possible with keyboard; Enter/Shift+Enter clear; Escape non-destructive; labels/states/focus order Narrator-observed; 2× text scale and DPI usable; reduced motion honored. Semantics/guideline/widget tests + Windows Narrator/manual evidence |
| UI-11 / P2 | Shared loading/empty/error/stale/status components and responsive layout | UI-03/09/10 | Same language/spacing across affected screens; long filenames/URLs/errors readable; no nested-card clutter or empty decorative panels; list virtualization assessed. Widget overflow/scaling/goldens and independent review |
| UI-12 / P3 | Reconcile stale source/design documentation; F12 | UI-08; accepted docs scope | Correct only stale current-state claims; preserve historical decisions, qualification distinctions and user constraints; no milestone state changes. Documentation link/diff review |

**Gate G2:** selected direction plus all affected themes, focus, scaling and state components accepted. Existing OS/font/DPI render context is pinned for visual fixtures; no raw screenshot similarity alone establishes usability.

## Phase 3 — companion and artifact workspace

| ID / priority | Scope / deliverable | Dependencies | Acceptance / validation |
|---|---|---|---|
| UI-13 / P2 | Compact bounds/state continuity; F09. native controller, compact overlay, Chat host | UI-02, G2 | Reconcile 420×580 reference vs 440×680 runtime using observed fit; preserve draft/attachments/task/approval during transition; restored bounds clamped to current displays; no focus theft. Widget identity tests + Windows DPI/minimize/restore/multi-monitor checks |
| UI-14 / P2 | Multi-artifact projection/collection; F10. `ActionResult`, file/run refs, FileStore adapter | G1; new accepted artifact projection; frozen run APIs reused | Opaque auth-bound ids, actual file bytes/hash/version/source; pending verification distinct from usable output; denied cross-user download; no URI-local path grant. FileStore/run integration tests, same-name/version cases, real generated fixture review |
| UI-15 / P2 | Optional result inspector/read-only previews; Chat pane/components | UI-14, G2 | Pane opens only with content/user action; narrow sheet; supported formats bounded; unsupported formats honest OS-open action; stale/revoked artifact access handled. Golden/widget tests plus real file/viewer interaction and independent review |
| UI-16 / P2 | Picker/file-drop parity and open feedback; platform injected adapters | UI-14; separately accepted Windows drop adapter if selected | Cancel harmless; folder drop doesn't authorize recursion; same backend validations; upload state/removal correct; no-viewer error actionable; path/filename edge cases. Platform tests plus native picker/drop/viewer checks |
| UI-17 / P3 optional | Quiet OS notifications / tray or invoke shortcut, only selected subset | UI-02/13; separate native lifecycle plan | User settings control notifications; no automatic foregrounding; locked-screen sensitive content omitted; one owned instance; keyboard restore works. Native/manual tests and lifecycle independent review. Omit until a supported adapter exists |

**Gate G3:** selected authorized inputs → canonical task → verified candidate → actual artifact review → explicit required writeback decision; same workflow survives compact/expand/minimize. No desktop state “complete” without runtime settlement.

## Phase 4 — progressively expose actual intelligence

| ID / priority | Scope / deliverable | Dependencies | Acceptance / validation |
|---|---|---|---|
| UI-18 / P2 | Ability read model/catalogue/detail; Core capability + installed skill + M37/M38 redacted projections | G1/G2; capability projection accepted; integrated components identified | Installed/registered/qualified/available separate; version/provenance/scope visible; enabled skill not executable by implication; no raw secrets. Schema/access tests and live discovery→task demonstration; independent data-origin review |
| UI-19 / P2 | Memory search/provenance/correction; Core memory first, M36 only after accepted connection | UI-18; M36 read-access/source projection | Separate session facts/durable knowledge/history; authorized source links; no fake relevance score; correction/consent preserved; memory never binds or grants. Cross-user/expired-source tests and actual inspect/correct task |
| UI-20 / P3 conditional | Meaningful relationship view; GraphStore/Graphify projection | UI-19; actual sourced relationships; user scenario accepted | Correct data domain; typed sourced edges; observed/inferred distinction; empty graph absent; list alternative/keyboard access. Query/path isolation tests and source-backed example; no decorative network |
| UI-21 / P2 | Usage and provider availability view; `/usage`, per-turn measurements, future run usage | UI-03/18; metric coverage/attribution | Exact/partial/unavailable labels, units/intervals/sample count; no invented cost/remaining subscription/time saved; requested/actual model distinct. Aggregation fixture tests and displayed-versus-raw trace review |
| UI-22 / P2 | Home intelligence drill-downs / needs attention | UI-18/19/21; G3; chosen direction | Existing four backed tiles; no duplicate pending-task count; Home no composer; qualification and unmet prerequisites explanatory; settings deep links reuse existing configuration. Native navigation/focus/outage tests and independent design review |

**Gate G4:** every visible ability/metric has a current authorized source and evidence scope; historical qualification cannot become a deployment availability badge. Claims “operational” require canonical and live evidence.

## Phase 5 — improvements with evidence

| ID / priority | Scope / deliverable | Dependencies | Acceptance / validation |
|---|---|---|---|
| UI-23 / P3 deferred | Suggestion evidence/proposal contract, no policy mutation | G4; verified task/run history; separate Stage 1–3 approved design | Sample/period and evidence refs; clear assumptions/risks/qualification requirements; insufficient history yields none; authorization from established policy only. Independent architecture/privacy review; unsupported-history tests |
| UI-24 / P3 deferred | Inspect/dismiss/snooze/request-qualification UX | UI-23 implementation accepted, G2 | User controls proposal state; revoked evidence handled; dismissal never changes routing; no autonomous skill enabling or S9 learning. Client/contract tests + native evidence inspection and dismissal; independent review |

## Ordering, rollback and handoff

Critical path: recovery packet → canonical/lifecycle acceptance → retry and state contracts → grounded UI + chosen direction → token/accessibility foundation → artifact/compact task acceptance → intelligence data origin → suggestions. UI-18 may begin contract planning in parallel with UI-14 once G1 passes; production work remains dependency-gated and assigned by the accepted manager.

Each accepted batch must record: exact allowed read/write paths and prohibited features/frozen files; reused APIs; previous behavior and additive compatibility; fixture/data scope; reviewer independence; rollback commit/flag; test commands/results with failures/NOT RUN; native screenshots/actions; canonical execution receipts. Protect Memory/Edge/Harness/Office frozen files and unrelated dirty changes. Avoid blanket “all tests passed” when environment-specific or live gates did not run.

Rollback: restore last independently accepted UI binding/pane behind the approved flag, retaining current task/approval/artifact state and backend evidence. New DTO fields remain additive during migration; clients without them show supported coarse state. A visual rollback must never replay a write or recreate an approval. Security/canonical recovery remains required regardless of selected direction.

## Planning-package acceptance checklist

- Current source paths and evidence labels documented; source-only findings distinguished from live probes.
- Capability inventory includes all requested components and qualification/connectivity/API/UI gaps.
- Impeccable upstream versions, native-source support, browser limits, installer/hook review and remaining trial work documented.
- Three coherent directions with reference basis, dependencies, feasibility and schematic supplied.
- Proposed event/ability/artifact/memory/usage/improvement contracts and six-phase roadmap supplied.
- Prioritized repair tasks mapped to audit findings and gated behind active recovery.
- Production files, tests, launchers, dependencies, branches, frozen components and existing changes untouched by this assignment.

This package records the **confirmed combined product decision** and is ready for **first-slice plan review**, not implementation or release.
