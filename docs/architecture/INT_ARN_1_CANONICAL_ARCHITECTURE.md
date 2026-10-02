# INT-ARN-1 — Stage 2: Canonical Architecture Design

**Status:** Amended Stage 2 architecture; independent re-audit pending
**Milestone:** INT-ARN-1 (Real RAR/reference clarification in desktop `/ask`)  
**Governance:** [URI Four-Stage Development Lifecycle](../governance/URI_FOUR_STAGE_DEVELOPMENT_LIFECYCLE.md)  
**Prerequisite:** [Stage 1 Root-Cause Audit](../research/INT_ARN_1_ROOT_CAUSE_AUDIT.md)  
**Branch:** `experimental/desktop-recovery-repair` | **Amendment base:** `74677cc` (accepted with amendments at `f212b0d`)
**Date:** 2026-10-02  

---

## 1. Overview and Design Principles

This document defines how Reference Anchor Resolution (RAR) and reference clarification canonically integrate into URI's desktop agent loop. Derived strictly from the findings of the [Stage 1 Root-Cause Audit](../research/INT_ARN_1_ROOT_CAUSE_AUDIT.md), this architecture guarantees:
1. **Model/Runtime Division:** The Brain proposes reference slots and drafts user-facing questions; the deterministic runtime validates proposals, gathers authorized evidence, executes deterministic resolution, enforces binding authority, and gates execution.
2. **Fail-Closed Binding Enforcement:** Multi-action execution carries verified per-action `reference_bindings` to S2. Canonical LEGACY uses `ApprovalGate.execute_tool()` and lacks S2, so a reference-bearing contract needs an independent pre-dispatch check or exclusion. Other unbound routes are excluded at their entry boundaries.
3. **Approval Integrity:** Both proposal sites retain per-action/per-slot identity; both approval modes revalidate under the authenticated principal immediately before consumption. The legacy dispatcher has no S2 gate.
4. **Complete Route Coverage:** The Stage 3 entry inventory covers canonical, ready-read, native, stream, legacy descendants, workflow continuation, lifecycle, approvals and Edge, with an entry-boundary proof for each.

---

## 2. Where This Belongs in URI's Canonical Agent Loop

Reference clarification operates at the transition between Brain decision making and runtime execution dispatch:

```
User Request (with optional typed ClarificationResponse)
   ↓
[Intake Gate] Authenticate user, validate session & attachments
   ↓ (If clarification_response present: route directly to clarification handler)
Decision Context Assembly (Principal, TurnState, Attachments, FileStore, M36 History)
   ↓
Brain Decision (Model proposes action and optional reference_slots)
   ↓
Deterministic Proposal Validation (Span, ref_key, target action parameter)
   ↓
Evidence Assembly (Gather authorized candidate IDs from FileStore, Gmail, Drive, Attachments)
   ↓
Deterministic RAR Resolution (resolve_rar_deterministic_extended in uri_v1)
   ↓
Clarification Classification (build_clarification in uri_v1 with action wrong_binding_impact)
   ├── Certainty Match / Tentative Safe ──► Register binding in BindingService
   │                                         ↓
   │                                     Pass verified reference_bindings into Dispatch
   │                                         ↓
   │                                     Evaluate S2 Wrong-Binding Gate in Executor
   │                                         ↓
   │                                     Execute Action (with Approval Gate if required)
   │                                         ↓
   │                                     Feed Execution Result to Brain for Response
   │
   └── Ambiguous / Consequential Confirmation Required
                                             ↓
                                         Persist Round in Durable Per-User Journal
                                             ↓
                                         Brain Drafts Question (validate_render / template fallback)
                                             ↓
                                         Render Inline ClarificationCard in Desktop UI
                                             ↓
                                         Await User Response (Halts Dispatch)
```

The S2 branch in this diagram describes registered multi-action execution. Canonical LEGACY and approval consumption require the separate checks in sections 4.2-4.3; excluded routes never reach their executor for a pending reference turn.

---

## 3. Canonical Loop Completion Rule (The 10 Invariants)

1. **How is it discovered?**  
   It is not a separate discoverable tool. It is an intrinsic capability of URI's canonical execution pipeline. The Brain is informed via the decision schema that it may declare ambiguous reference spans in its decision.
2. **How does the Brain know it is available?**  
   The system prompt and Decision Contract schema define an optional `reference_slots` property on the action proposal.
3. **How does the Brain know when to use it?**  
   When the user's utterance contains an ambiguous, demonstrative, or anaphoric entity reference (e.g., "that document", "the spreadsheet", "her email") required to satisfy an action input parameter.
4. **What action contract does it expose?**  
   - Brain Proposal Schema: `reference_slots: [{"span": str, "ref_key": str, "target_action": str, "target_param": str, "source_class": Optional[str]}]`.
   - Wire Response: `clarification: ClarificationRequest` (matching Flutter `ClarificationRequest` schema: kind, question, options, attribute filters, fingerprint, expiry).
   - Wire Intake: `clarification_response: ClarificationResponsePayload` (round_id, response_kind, selected_candidate_id, selected_attribute, free_text, candidate_set_fingerprint).
5. **What runtime state does it need?**  
   - Durable per-user clarification journal (`uri_workspace/users/<user-id>/reference_clarification/`).
   - Session context, validated attachment handles, and live source inventories.
   - Versioned per-action/per-slot `binding_identity` in `ProposedAction` within `ApprovalStore`, separate from tool arguments.
6. **What permissions and approvals apply?**  
   - Source inspection requires caller capability grants (e.g. `gmail_search`, `drive_search`).
   - S2 Wrong-Binding Gate enforces that `TENTATIVE` bindings can only execute declared `NONE/RECOVERABLE` actions; `CONSEQUENTIAL` actions require explicit `CONFIRM_ONE` selection.
   - Standard capability approvals (`USER_APPROVAL_REQUIRED`) remain independently required.
7. **How does execution happen?**  
   Canonical registered single/chain actions use `MultiActionExecutor.execute()`/`execute_chain()` with verified per-action bindings and S2. Canonical LEGACY invokes `ApprovalGate.execute_tool()` (`canonical_execution.py:282-342`) and then `ToolDispatcher`, without S2; slot-bearing actions are excluded before that dispatch unless a complete independent check is implemented at the approved boundary. Legacy fallback, workflows, lifecycle and Edge are not silently treated as MultiActionExecutor routes; they obey section 4.3 exclusions.
8. **How does the result return to reasoning?**  
   Upon execution completion, the real execution result envelope is returned to the Brain to draft the grounded natural-language response.
9. **How are follow-up references grounded?**  
   Executed bindings become session evidence for follow-up turns. M36 factual task history may retain a task pointer, but it cannot supply current source authority or learned cross-session tie-breaking (D4); any later reference is reauthorized and revalidated.
10. **How is it tested end-to-end?**  
    Validated through component unit tests, entry-boundary tests for every row in the [Stage 3 route inventory](../plans/INT_ARN_1_PLAN.md), agent-loop behavioral tests with mocked Brains, and live desktop UI acceptance tests.

### Remaining Stage 2 lifecycle decisions

- **Graphify, session, durable memory and runtime state:** Graphify may suggest a capability, skill, workflow, service or memory pointer within its proven index scope, but it neither indexes document/email candidates nor proves their identity. Open a pointer through an authorized source before use. Session-selected references and corrections can inform the same-session turn; the versioned per-user clarification journal stores only active round/binding mechanics and TTL, and ApprovalStore stores approval identity. **D4** defers durable cross-session learned reference evidence and learned tie-breaking to URI-Memory; no new learned-reference database or promotion from transcript prose is part of INT-ARN-1. Existing M36 factual history can supply a checked pointer, not current source authority. [D4 ruling](../plans/M33_3_URI_BRAIN_ARCHITECTURE_PROPOSAL.md), [Graphify scope](../plans/M33_3_ARN_ARCHITECTURE_AND_LT1B_RENDERER_PLAN.md).
- **Progressive discovery:** The Brain discovers optional `reference_slots` in its existing decision schema, not as a new tool. URI first uses validated current-turn attachments and session evidence, then bounded, currently granted FileStore/Gmail/Drive retrieval when the proposed source class requires it; `UNKNOWN` or free input may start a new bounded round over newly checked sources. No silent unbounded search, fabricated candidate, or Graphify document/email grounding.
- **Model escalation:** No specialist or larger model is invoked just to improve clarification wording. The serving Brain drafts the question from bounded facts; `validate_render()` checks it and the deterministic template is the fallback. Any existing model routing/escalation remains governed by URI's normal decision path and cannot grant binding or approval authority.
- **Component ownership:** `uri_v1/turn` owns frozen RAR; `uri_v1/reference_clarification` owns frozen builder, binding and safeguards; a thin `uri_desktop_seams/reference_clarification/` adapter owns production evidence, journal and wire mapping; `canonical_execution.py` and `server.py` own entry guards; `MultiActionExecutor` owns S2; `ApprovalStore`/`ApprovalGate` own durable approval and pre-consumption integrity; Flutter owns display and typed response only.
- **Reuse and retirement:** Reuse frozen RAR/S1, existing FileStore and granted Gmail/Drive reads, TurnState, S2, approval store, and Flutter card. Do not fork their algorithms or create a parallel execution architecture. Keep old no-reference approvals/turns compatible; for reference-bearing turns, replace plain-text-only `MISSING_PARAMETER` handling with a grounded round and exclude unsafe fallback paths. Retire no unrelated capability, workflow or route in this milestone.

---

## 4. Addressing Stage 1 Root Causes

### 4.1 Per-Action Binding Transport Through Dispatch (Addressing H1)
To ensure bindings reach the executor and activate the S2 gate:
1. `uri_core/core/canonical_execution.py`:
   - Single-action dispatch (~line 223): Passes `reference_bindings=reference_bindings` to `dispatch.dispatch_explicit()`.
   - Multi-action chain dispatch (~line 264): Includes `"reference_bindings": action.get("reference_bindings")` inside each step mapping in `steps`, passed to `dispatch.dispatch_chain_explicit()`.
2. `uri_core/core/multi_action_dispatch.py`:
   - `dispatch_explicit()` accepts `reference_bindings: Optional[Sequence[ReferenceBinding]] = None` and passes it directly to `executor.execute(..., reference_bindings=reference_bindings)`.
   - `dispatch_chain_explicit()` accepts steps with `"reference_bindings"`; `MultiActionExecutor.execute_chain()` already extracts `step.get("reference_bindings")` and forwards it to `execute()`.
3. Exact-file amendment: `uri_core/core/multi_action_dispatch.py` has User approval (09:24 UTC); Stage 4 must register its exact blob pin and allowlist row before guard qualification.

### 4.2 Approval Record Binding Identity Retention & Resumption Re-check (Addressing H2)
`ProposedAction` stores a versioned sequence of identities, one for **each affected action and slot**: capability, action, exact argument/slot, `ref_key`, candidate ID, source class/locator, version or fingerprint, binding state, declared impact, round/session and expiry. This is separate from tool arguments. Both proposal sites (`canonical_execution.py:177-180`, `approval_gate.py:186-191`) supply it to the extended `ApprovalStore.propose()` (`approval_store.py:179-205`); `_load()` (`:379-415`) explicitly deserializes and validates it. Old no-reference records still load: a persisted boolean `requires_reference_binding` (missing key = False; set True at proposal when any validated slot existed) distinguishes them, and a record with that flag True but absent, corrupt or count-mismatched identity cannot execute. On `/approve`, registered multi-action records (`action_name` set) are never legacy-dispatched by `ApprovalGate.decide()`; the server delegates them to the same resume path as natural-language approval (pre-consumption recheck, then `dispatch_explicit()` with fresh `ReferenceBinding`s), or fails closed if that delegation is unavailable.

The authenticated principal's current grant, action descriptor/impact and each live source locator/version/fingerprint are checked against that saved identity immediately before the **exact consumption** in `ApprovalGate.decide()` (`approval_gate.py:280-285`, `/approve` path) and in `approval_resumption.py:215-220` (natural-language multi-action path). Legacy natural-language approval uses the gate once, avoiding its current double-decision sequence (`approval_resumption.py:170,191`). Drift returns an audited truthful failure with no consumption or dispatch. The multi-action branch passes freshly reconstructed `ReferenceBinding` objects to S2. The legacy branch relies on its independent pre-consumption check; `ToolDispatcher.execute_tool()` has no binding gate and receives no binding metadata as kwargs. Approval is separate from confirmation of a reference.

### 4.3 Complete entry coverage (H3)

The [Stage 3 inventory](../plans/INT_ARN_1_PLAN.md) gives the production line, binding decision and entry-boundary test for **each** route. Its canonical single/chain routes use S2. Canonical LEGACY (`canonical_execution.py:282-342`) does not and is excluded on slot-bearing decisions unless independently checked in that approved file. Both ready-prefix branches (`:559-609`, invoked at `:820-845`) and both native sites (`native_tool_loop.py:223,318`) are guarded before execution. `/ask/stream` delegates typed answers/pending rounds to authenticated `/ask`. `server.py` blocks **early M30.7 workflow continuation** (`:1752-1799`) on a pending round, and excludes pending-round or slot-bearing decisions from later legacy fallback and its `multi_action_dispatch.dispatch()`, direct capability, workflow creation/continuation and `workflow_capability_router.py` descendants. Lifecycle state mutations (`server.py:1692-1725`) and social-only Edge (`:1730-1748`) precede Brain slots; their exclusion uses pending-round state and their narrow contracts, never a reference keyword classifier. Natural-language and API approvals use the independent pre-consumption gate above. No change to `orchestrator.py`, `workflow_capability_router.py` or `dispatcher.py` is required or approved.

### 4.4 Streaming Route Intercept (Addressing M1)
In `uri_core/app/server.py`:
- In `POST /ask/stream`: Before evaluating `_ask_stream_eligible()` or launching `stream_first_turn()`, inspect `payload.clarification_response` **and** authenticated pending-round state.
- If a typed response or pending round exists:
  - Bypass streaming entirely and delegate immediately to `_fallback_to_ask()` (which executes the authenticated `ask()` handler synchronously and emits the terminal SSE `message` event).
- In `_ask_stream_eligible()`: Explicitly return `False` for either condition.

---

## 5. Persistence, State, and Durability

1. **Durable Clarification Journal:**  
   Persisted under `uri_workspace/users/<user-id>/reference_clarification/` via atomic write/rename. Keyed by `user_id` and `round_id`. Contains round contract, candidate scope IDs, fingerprints, original task pointer, and TTL.
2. **Approval Store Compatibility:**  
   Extends `ProposedAction` in `uri_workspace/approvals.json` with backward-compatible optional versioned per-action/per-slot `binding_identity`, explicitly loaded by `_load()`. Legacy no-reference records continue to deserialize safely; known reference-bearing records without valid identity fail closed.
3. **No Cross-User Leakage:**  
   Path resolution strictly follows `_resolve_context(user_id)`; client-supplied IDs are never used for filesystem paths.

---

## 6. Client Interface & Flutter Presentation

1. **Wire Schemas:**  
   Reuses existing `uri_ui/lib/models/clarification.dart` contracts (`ClarificationRequest`, `ClarificationResponsePayload`).
2. **UI Integration:**  
   - `TurnCard` in `uri_ui/lib/widgets/turn_card.dart` embeds `ClarificationCard` under the Brain's question.
   - `AskUriScreen` in `uri_ui/lib/screens/ask/ask_uri_screen.dart` binds the response callback to `AppState.submitClarificationResponse()`.
   - Card locks during submission; shows safe retry message on expiration/rejection.
