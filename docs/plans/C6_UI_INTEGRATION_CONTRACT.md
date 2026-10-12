# C6: UI roles and paired-runtime integration contract (proposed)

Date: 2026-10-05. Status: **PROPOSED. Not reviewed or accepted.** Written during the third Phase 1 review. Everything is uncommitted. This document describes what exists, sets the contract the UI must keep, and lists the decisions only the owner can make. It does not redesign any screen.

## Sources

- `docs/plans/UI_HYBRID_FROZEN_BLUEPRINT.md`: the frozen UI. It defines the presentation modes Workspace (desktop), Compact (the same session in a floating window) and Mobile, and five destinations: Home, Chat, Tasks, Connections & Providers, Settings.
- `SERVER_CLIENT_OWNERSHIP.md` (Phase 0 outputs): the Flutter UI and Develop mode belong to the client. A UI mode is UX only and never grants authority.
- `PHASE1_IMPLEMENTATION_PLAN.md`: C6 preserves existing user-visible flows. Historical data is migrated copy-first, and only after the owner maps installations to clients.
- The code that exists today: `uri_ui/lib/services/paired_runtime.dart` (`WorkerPairedRuntime`) and `uri_ui/lib/screens/settings/paired_runtime_screen.dart` (`PairedRuntimeScreen`, reached from the existing Settings shell).

## UI roles: what is defined and what is not

| Role | Defined by | Status |
|---|---|---|
| Workspace, Compact, Mobile presentation | Frozen blueprint | Defined. A presentation switch keeps the session and in-flight state. It never starts a new turn or repeats one. |
| Home, Chat, Tasks, Connections & Providers, Settings | Frozen blueprint | Defined. The legacy server still backs them. Not yet wired to the paired runtime. |
| Paired runtime (executor choice, clarification, confirmation, approval) | Phase 1 C5/C6 code | Implemented as one Settings screen. The integration contract is below. |
| Develop mode | Ownership matrix | Defined only as a client UX mode with no authority. Its screens are not specified. |
| "Companion", "Intelligence" | Not defined in any governing document or in Flutter code | **Owner decision required.** I did not invent them. |

## Integration contract (binding on any UI that drives the paired runtime)

The UI talks to the client worker only, through framed stdio (`run_uri_client_worker.py`). It never talks to the server directly, holds credentials or executes anything.

| Worker command | UI use | Invariants the UI must keep |
|---|---|---|
| `turn_start {session_id, text, reasoning}` | Send the user's words with the user's explicit reasoning choice | `reasoning` is always the user's explicit pick. The UI never defaults to, or silently switches to, another row. |
| `turn_intent {…, intent_decision}` | Confirm (`digest`), abandon, or select a displayed option | Send `confirm` only with the digest and revision the user was shown. Send `select` only with a `candidate_id` that was on screen. |
| `turn_decide {turn_id, approve}` | Approve or decline the exact arguments shown | Show `approval_request.arguments` verbatim before the button is enabled. Never auto-approve. |
| `harness_discover` | Show each harness's honest state and required action | Show `usable:false` and the native-login action. Never offer an unqualified harness as runnable. |
| `preflight`, `identity`, `session` | Readiness and status | Show "UI pending / unqualified" honestly. No green state is fabricated. |

What the UI must render from turn results:

1. **Clarification** (`INTENT_CLARIFICATION`): the question plus the server's options. Allow a typed answer. Never preselect an option.
2. **Confirmation** (`INTENT_CONFIRMATION_REQUIRED`, `INTENT_CONFIRMED_NOT_EXECUTED`): the exact arguments, each bound reference ("X means Y"), and a provenance note for any slot whose source is `interpreted_from_request`. That note now exists on the screen: "Read from your words by the selected Brain".
3. **Approval** (`approval_required`): capability, exact arguments, reversibility.
4. **Uncertainty** (`SETTLED_EXECUTION_UNCERTAIN`, `INTENT_EXECUTION_UNCERTAIN`): show the server message. Offer no "retry" button for that request. The user may type a new request.
5. **Brain failure** (`SELECTED_MODEL_UNAVAILABLE`, `BRAIN_OUTPUT_INVALID`, `ADAPTER_NOT_QUALIFIED`): say the selected source failed and nothing was done. Offer an explicit choice of source. No automatic fallback.
6. **Provider quota** (`WAITING_FOR_MODEL`): the task is saved. The same provider is refused, and the user must pick another one explicitly.

Presentation modes: switching Workspace, Compact or Mobile while a clarification, confirmation or approval is pending keeps the turn and session IDs and the pending card. It never resubmits. This is the frozen blueprint's R2 rule, applied to paired turns.

## Not yet done (C6 remaining work)

- Connect Chat (Workspace, Compact, Mobile) to `WorkerPairedRuntime` behind an explicit per-installation switch. The legacy `/ask` stays the default until C7.
- Brain row selection in the UI. The server composition offers no Brain row while the C1 policy is `lazy-not-selected` (see the third review report). The screen offers only the deterministic row plus harness rows.
- Voice and dictation parity (`uri-dictation@f1e13e9` is the strongest candidate, deferred).
- A pinned UI release build: the client manifest needs `ui_binary` and `ui_sha256`, and `preflight` must report `PINNED_IN_CLIENT_INSTALLATION`.
- Historical owner and key mapping, and copy-first migration. Both need separate owner authorization.

## Owner decisions needed

1. Define "Companion" and "Intelligence", or confirm they are not Phase 1 roles.
2. Decide whether Chat may move to the paired runtime before C7, as an opt-in per installation.
3. Decide which Brain rows may be offered once the C5 Brain activation policy change is reviewed.
