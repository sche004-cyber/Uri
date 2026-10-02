# INT-ARN-1 — Stage 2: Canonical Architecture Design

**Status:** Frozen Stage 2 Architecture Document  
**Milestone:** INT-ARN-1 (Real RAR/reference clarification in desktop `/ask`)  
**Governance:** [URI Four-Stage Development Lifecycle](../governance/URI_FOUR_STAGE_DEVELOPMENT_LIFECYCLE.md)  
**Prerequisite:** [Stage 1 Root-Cause Audit](../research/INT_ARN_1_ROOT_CAUSE_AUDIT.md)  
**Branch:** `experimental/desktop-recovery-repair` | **HEAD:** `554041e`  
**Date:** 2026-10-02  

---

## 1. Overview and Design Principles

This document defines how Reference Anchor Resolution (RAR) and reference clarification canonically integrate into URI's desktop agent loop. Derived strictly from the findings of the [Stage 1 Root-Cause Audit](../research/INT_ARN_1_ROOT_CAUSE_AUDIT.md), this architecture guarantees:
1. **Model/Runtime Division:** The Brain proposes reference slots and drafts user-facing questions; the deterministic runtime validates proposals, gathers authorized evidence, executes deterministic resolution, enforces binding authority, and gates execution.
2. **Fail-Closed Binding Enforcement:** Every reference-bearing execution path carries verified `reference_bindings` to `MultiActionExecutor.execute()`; any missing, unconfirmed consequential, or stale binding halts dispatch.
3. **Approval Integrity:** Resumed approvals (via natural language or API) re-verify source freshness and binding validity immediately before dispatch.
4. **Exhaustive Route Coverage:** All 8 execution routes across URI either enforce the wrong-binding gate or fail closed with an explicit exclusion.

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
   - Retained `binding_identity` in `ProposedAction` within `ApprovalStore`.
6. **What permissions and approvals apply?**  
   - Source inspection requires caller capability grants (e.g. `gmail_search`, `drive_search`).
   - S2 Wrong-Binding Gate enforces that `TENTATIVE` bindings can only execute declared `NONE/RECOVERABLE` actions; `CONSEQUENTIAL` actions require explicit `CONFIRM_ONE` selection.
   - Standard capability approvals (`USER_APPROVAL_REQUIRED`) remain independently required.
7. **How does execution happen?**  
   Execution is performed solely by `MultiActionExecutor.execute()` or `execute_chain()`, receiving explicit, verified `reference_bindings` transported through `canonical_execution.py` and `multi_action_dispatch.py`.
8. **How does the result return to reasoning?**  
   Upon execution completion, the real execution result envelope is returned to the Brain to draft the grounded natural-language response.
9. **How are follow-up references grounded?**  
   Executed bindings are recorded in session evidence facts and M36 factual task history, providing stable anchors for subsequent conversational turns.
10. **How is it tested end-to-end?**  
    Validated through an exhaustive 4-level test strategy: component unit tests, route dispatch tests across all 8 execution paths, agent-loop behavioral tests with mocked Brains, and live desktop UI acceptance tests.

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
3. Exact-file amendment: `uri_core/core/multi_action_dispatch.py` is added to the allowlist (pending User approval).

### 4.2 Approval Record Binding Identity Retention & Resumption Re-check (Addressing H2)
To prevent executing against stale, deleted, or altered entities upon approval:
1. `uri_core/core/approval_store.py`:
   - `ProposedAction` dataclass is extended with `binding_identity: Optional[Dict[str, Any]] = None` (storing `ref_key`, `candidate_id`, `source_locator`, `source_version`, `status`, and `declared_impact`).
2. Natural-Language Approval Resumption (`uri_core/core/approval_resumption.py:~208`):
   - Before calling `dispatch_explicit()`, if `record.binding_identity` is present:
     - Verify source freshness: re-check that the entity at `source_locator` exists and its version/fingerprint matches `source_version`.
     - Re-check caller authorization for the capability and target entity.
     - Re-verify declared impact against current capability descriptor.
     - Reconstitute `ReferenceBinding` and pass as `reference_bindings` to `dispatch_explicit()`.
     - If any check fails (entity missing, modified, permission revoked), fail closed: abort dispatch, log audit failure, and return an explicit error envelope.
3. API Approval Endpoint (`uri_core/app/server.py:~2248` `/approve`):
   - Inside `ApprovalGate.decide()`, before calling `dispatcher.execute_tool()`:
     - Re-verify `binding_identity` and source validity under the same rules as above.
     - Pass verified `reference_bindings` into `execute_tool()`.
     - Fail closed if validation fails.

### 4.3 Comprehensive Route Coverage Matrix (Addressing H3)
All 8 execution routes across URI must enforce reference binding validation or fail closed:

| Route | Production Path | Binding Gate Enforcement / Exclusion | Fail-Closed Mechanism |
|---|---|---|---|
| **1. Canonical Single** | `canonical_execution.py:223` -> `dispatch_explicit` | Transports verified `reference_bindings` to `executor.execute()`. | S2 gate blocks execution if binding is missing/unconfirmed for consequential action. |
| **2. Canonical Chain** | `canonical_execution.py:264` -> `dispatch_chain_explicit` | Embeds `reference_bindings` per step; forwarded to `executor.execute_chain()`. | Chain halts at first step with invalid/unconfirmed binding; subsequent steps aborted. |
| **3. Ready Read Prefix** | `canonical_execution.py:820` -> `_execute_canonical` | Evaluates prefix read actions before main block. | If any prefix action requires an unconfirmed/pending reference, prefix execution is suppressed (returns empty). |
| **4. Native Tool Loop** | `native_tool_loop.py:223` -> `_execute_canonical` | Translates native tool call into single-action contract with `reference_bindings`. | If native tool call references an unresolved entity, execution returns `unavailable` with gate block. |
| **5. Legacy Fallback** | `server.py:1878` -> `process_user_input` | Explicit fail-closed exclusion. | If turn context indicates pending reference clarification or unresolved reference slots, legacy fallback is strictly forbidden from executing tools. |
| **6. Approval Resumption** | `approval_resumption.py:208` -> `dispatch_explicit` | Re-checks retained `binding_identity`, source freshness, and impact before dispatch. | If source is deleted, modified, or expired, aborts dispatch and returns fail-closed error. |
| **7. API /approve** | `server.py:2248` -> `approval_gate.decide` | Re-checks `binding_identity` and passes `reference_bindings` to `execute_tool()`. | Rejects approval consumption and fails closed if entity state has drifted. |
| **8. Edge Seam** | `server.py:1739` -> `try_harness_first` | Explicit fail-closed exclusion. | Edge route is strictly social-only. Returns `None` immediately if query contains reference slots or pending clarification. |

### 4.4 Streaming Route Intercept (Addressing M1)
In `uri_core/app/server.py`:
- In `POST /ask/stream`: Before evaluating `_ask_stream_eligible()` or launching `stream_first_turn()`, inspect `payload.clarification_response`.
- If `payload.clarification_response is not None`:
  - Bypass streaming entirely and delegate immediately to `_fallback_to_ask()` (which executes the authenticated `ask()` handler synchronously and emits the terminal SSE `message` event).
- In `_ask_stream_eligible()`: Explicitly return `False` if `payload.clarification_response is not None`.

---

## 5. Persistence, State, and Durability

1. **Durable Clarification Journal:**  
   Persisted under `uri_workspace/users/<user-id>/reference_clarification/` via atomic write/rename. Keyed by `user_id` and `round_id`. Contains round contract, candidate scope IDs, fingerprints, original task pointer, and TTL.
2. **Approval Store Compatibility:**  
   Extends `ProposedAction` in `uri_workspace/approvals.json` with backward-compatible optional `binding_identity`. Legacy records without binding identity continue to deserialize safely.
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
