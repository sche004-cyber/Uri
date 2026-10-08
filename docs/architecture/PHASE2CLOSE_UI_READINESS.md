# Next-phase UI readiness (Phase 2 closure)

Date 2026-10-08. Author: Claude. Status: **READINESS ANALYSIS + INTERFACE CONTRACTS. No screen was designed or
redesigned.** The target experiences below are requirements for the next UI phase, not claims that they exist. Any
visual decision in that phase must follow the repository's reference-first process (`uri-ux-design` skill,
`docs/design_library/`), starting from the real backend capability listed here.

## 1. What exists, by line of development (inspected 2026-10-08)

| Area | Phase 2 tree (`.codex\worktrees\uri-phase2a\uri-agent`, base `e8e3b65`) | `_V1` line (`Development\Uri\_V1`, 62 commits past `e8e3b65` + uncommitted) |
|---|---|---|
| Structure | Hybrid UI (5 destinations, Compact toggle, Mobile) per `UI_HYBRID_FROZEN_BLUEPRINT.md` | same base structure; approved records `hybrid_ui_2026-09-16`, `clarification_card_2026-09-27`, `harness_management_2026-10-03`, `voice_status_2026-10-04` |
| Supervised execution | `screens/tasks/supervised_execution_screen.dart`, `services/supervised_runtime.dart` (INDEPENDENTLY ACCEPTED), `services/task_handoff.dart` (closure) | absent |
| Paired runtime | frozen `paired_runtime*.dart` | as of its own history |
| Voice | none | `widgets/desktop_voice.dart`, `services/voice_event.dart` (status strip, Windows listener; hardware speech acceptance outstanding per the approved record) |
| Compact window | presentation toggle | `services/platform_window_controller.dart` ("Companion Compact window"), `widgets/compact_overlay.dart` |
| Harness management UI | supervised screen's executor rows | `widgets/desktop_harness_test.dart`, desktop harness services |
| Onboarding | `screens/onboarding/brain_onboarding_screen.dart`, `onboarding_screen.dart` (legacy server) | same files, later revisions |
| Living Energy Orb | not found | not found (`grep` for Orb in `uri_ui/lib`: no match) |
| Interactive Brain/capability visualization | not found | not found |

Consequence: the next UI phase cannot start on either tree alone. Reconciling the two lines (C7 readiness P2-6) is a
precondition and an owner decision.

## 2. Target experiences: readiness and the backend each one must read

| Target | Status | Backend source of truth (exists) | Missing before UI work | Hard rules it must keep |
|---|---|---|---|---|
| Living Energy Orb companion | DESIGN ONLY (state contract below) | worker `preflight`, `execution_status`, turn states | visual design (owner); line reconciliation | the Orb shows URI's state, never invents it; no state without a source (section 3) |
| Voice Companion <-> Workspace transitions | PLANNED | presentation modes (frozen blueprint R2 rule); `_V1` voice strip | voice parity decision (C6); line reconciliation | a presentation switch keeps session and in-flight state and never resubmits; voice NEVER approves (an utterance is typed text) |
| Unified conversation, Tasks, supervised execution | PARTIAL: handoff seam IMPLEMENTED/TESTED; Chat action awaits C6 decision 2 | `TaskHandoff`, `SupervisedExecutionEntry.open(context, draft:)`, `execution_list` | owner decision 2 (recommended B); Context Capsule / Task Compiler (design only) for the unified thread (option D) | separate steps: intent -> proposal -> approval -> execution -> receipt |
| Interactive Brain / capability visualization | DESIGN ONLY | `harness_discover` (installed, auth state, qualification, required action, usable), qualification report rows (level, models, expiry), server policy rows, client grants | read-only API contract (section 4); design | display only; a visualization never selects, approves or qualifies |
| Guided onboarding (roles, providers, models, permissions, connection, authentication, readiness) | PARTIAL (legacy onboarding screens) | `preflight`, `harness_discover.required_action`, `scripts/phase2close_acceptance.py preflight/qualify` logic, grants | owner decision on roles (C6 decision 1: "Companion", "Intelligence"); EXE-1 for native rows | the UI never performs or proxies a CLI login and never reads credentials; it shows the exact owner action |
| Approval, progress, cancellation, recovery, receipt presentation | IMPLEMENTED (accepted cards in the supervised screen) | execution record + ledger + journal + server, corroborated | extraction into shared widgets (next phase) | digests shown; exact arguments verbatim; `uncertain` wording; no retry button on uncertain |

## 3. Orb/companion presentation-state contract (design only)

A presentation state is a pure function of authoritative state. Proposed mapping, to be validated in the design
phase; every input below already exists in the worker protocol:

| Presentation state | Derived from | Never derived from |
|---|---|---|
| unavailable | screen `sx-unavailable` condition (no opt-in / worker failed preflight) | a timer or a guess |
| idle | no pending turn, `execution_list.active == null` | UI memory of an old run |
| listening | voice listener state (`_V1` `voice_event`), only while the strip says listening | microphone permission alone |
| needs you: clarify/confirm | `INTENT_CLARIFICATION` / `INTENT_CONFIRMATION_REQUIRED` | the Brain's free text |
| needs you: approve | `approval_required` with an `execution_proposal` | typed or spoken "approve" |
| working | `execution_status.state in {queued, approving, starting, running}` | elapsed time |
| done | `completed` (corroborated) | the record's own `completed` without corroboration |
| attention | `uncertain`, `failed`, `quota_paused`, `APPROVAL_REFUSED_NOT_APPLIED` | — |

## 4. Interfaces the next phase can rely on (exist and are tested)

| Interface | Path | Contract |
|---|---|---|
| `SupervisedRuntime` (Dart) | `uri_ui/lib/services/supervised_runtime.dart` | `preflight`, `discoverHarnesses`, `startTurn`, `intentDecision`, `decide`, `beginExecution(turnId, approvalDigest, proposalDigest)`, `executionStatus`, `cancelExecution`, `listExecutions`, `close` |
| Execution vocabulary | `uri_supervisor_bridge/execution.py` | `ACTIVE_STATES`, `TERMINAL_STATES`, reasons (`CANCELLED_BEFORE_APPROVAL`, `CANCELLED_BEFORE_START`, `CANCELLED_AFTER_DISPATCH`, `WORKER_RESTARTED`, `WORKER_CLOSED_DURING_EXECUTION`, `UNCORROBORATED_COMPLETION:*`, `APPROVAL_REFUSED_NOT_APPLIED:*`) |
| Conversation handoff | `uri_ui/lib/services/task_handoff.dart`; `SupervisedExecutionEntry.open(context, draft:)` | draft only; no authority |
| Opt-in | `<client_root>/control/ui-supervised-profile.json` | per installation; removing it removes the entry |
| Acceptance tooling | `scripts/phase2close_acceptance.py` | preflight / provision / qualify / record / collect |

## 5. Recommended reusable patterns to extract first (next phase, not now)

1. Approval card (proposal + exact arguments + digests + two buttons) -> `widgets/supervised/approval_card.dart`.
2. Execution card (state, reason, settlement, ledger/journal/server line, receipt, uncertain wording, cancel).
3. Executor picker (no preselection; unusable rows disabled with the required action).
4. Clarification/confirmation cards (the `_V1` approved `clarification_card` record is the visual reference).
Extraction was deliberately NOT done in the closure: it would reopen the independently accepted screen for no
Phase 2 gain.

## 6. Dependencies and order

1. Owner: choose the target development line (P2-6) and C6 decisions 1-3 (+ voice parity).
2. Integration slice: bring the Phase 2 supervised runtime and screen onto the chosen line (they are additive files
   plus one `app.dart` mount).
3. Extract the shared widgets (section 5) with their existing tests.
4. Design phase (reference-first) for Orb, transitions, Brain visualization and onboarding, on the state contract of
   section 3 and the interfaces of section 4.
5. EXE-1 decision before any onboarding step promises native harness rows.
