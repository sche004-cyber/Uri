# INT-ARN-1 — Stage 1: Evidence & Root-Cause Audit

**Status:** Amended Stage 1 audit; independent re-audit pending
**Milestone:** INT-ARN-1 (Real RAR/reference clarification in desktop `/ask`)  
**Governance:** [URI Four-Stage Development Lifecycle](../governance/URI_FOUR_STAGE_DEVELOPMENT_LIFECYCLE.md)  
**Branch:** `experimental/desktop-recovery-repair` | **Planning checkout HEAD:** `a5920b0`
**Date:** 2026-10-02  

---

## 1. What Exact Problem Are We Solving?

The deterministic Reference Anchor Resolution (RAR) engine (`uri_v1/turn/rar_deterministic.py`, `uri_v1/turn/rar_contracts.py`) and the M33.3 S1 clarification/binding engine (`uri_v1/reference_clarification/`) are completely disconnected from the real authenticated desktop `/ask` production path (`uri_core/app/server.py`).

When a user query requires entity disambiguation (for example, referring to "the quarterly budget spreadsheet" when three similarly named files exist in Drive, or "the email from Sarah" among multiple threads), the current runtime either:
1. Allows the model to guess or hallucinate an ungrounded candidate ID,
2. Emits a generic `MISSING_PARAMETER` failure, or
3. Outputs an unstructured plain text clarification turn without candidate IDs, attribute narrowing, option caps, or binding authority.

Furthermore, an independent pre-audit identified critical execution-path defects:
- **Binding Transport Disconnect (H1):** Canonical execution single-action and chain-action paths call `dispatch.dispatch_explicit()` and `dispatch.dispatch_chain_explicit()` without passing `reference_bindings`. In turn, `multi_action_dispatch.py` invokes `MultiActionExecutor.execute()` with no reference bindings (`None`). Under `uri_core/capabilities/wrong_binding.py:112`, passing `None` causes the S2 Wrong-Binding Gate to return `GateOutcome.NOT_APPLICABLE`, completely disabling the safety gate in production.
- **Resumed Approval Bypass (H2):** Natural-language approval resumption (`approval_resumption.py:208-235`) replays stored arguments through `dispatch_explicit()` without renewing binding checks or verifying that referenced entities still exist. Similarly, the direct `/approve` endpoint (`server.py:2248-2289`) consumes and executes the stored action without re-checking source freshness or binding validity.
- **Incomplete Route Coverage (H3):** The canonical LEGACY path (`canonical_execution.py:282-342`) executes through `ApprovalGate.execute_tool()` with no MultiActionExecutor/S2 gate. Both ready read branches (`canonical_execution.py:559-609`, call at `:820-845`), both native `_execute_canonical()` sites (`native_tool_loop.py:223-228,318-322`), `/ask/stream` (`server.py:2179-2194`), legacy fallback and its direct/multi-action/workflow routes, M30.7 continuation, lifecycle intents and Edge all need an entry-boundary binding gate or explicit exclusion. Earlier lifecycle/Edge seams cannot see future Brain slots and must use pending-round state plus their narrow contracts, never a text keyword classifier.
- **Streaming Premature Ingestion (M1):** In `POST /ask/stream` (`server.py:2179,2191`), a typed clarification response payload could enter `stream_first_turn()` instead of being routed to the authenticated `/ask` handler.

INT-ARN-1 connects the verified, deterministic RAR and clarification engine to desktop `/ask` while enforcing fail-closed binding gates across all execution routes.

---

## 2. What Already Exists in the Codebase and Runtime?

The URI repository already contains fully implemented, frozen components designed for reference clarification:

### 2.1 Frozen RAR & Clarification Logic (`uri_v1/`)
- **RAR Contracts (`uri_v1/turn/rar_contracts.py`):** `RARCandidate` (scoped ID, title, type, ordinal recency, owner, attachments, aliases), `RARQuery` (expression, candidate pool, local evidence, anchors), and `RARResolution` (`RESOLVED`, `UNKNOWN`, `AMBIGUOUS`). Resolution validation explicitly rejects invented or ungrounded IDs.
- **Deterministic Resolver (`uri_v1/turn/rar_deterministic.py`):** `resolve_rar_deterministic_extended()` provides deterministic resolution and diagnostic scores (explicitly uncalibrated). Truncates ambiguity sets deterministically while preserving full round scope.
- **Clarification Contracts & Builder (`uri_v1/turn/rar_clarification_contract.py`, `uri_v1/reference_clarification/builder.py`): Four clarification kinds (`CHOOSE_ONE`, `CONFIRM_ONE`, `CHOOSE_ATTRIBUTE`, `FREE_INPUT_ONLY`), three response kinds (`CANDIDATE_SELECTION`, `ATTRIBUTE_SELECTION`, `FREE_TEXT`), 5-option presentation cap, full candidate-set fingerprinting, and round scope tracking.
- **Binding Lifecycle & Authority (`uri_v1/reference_clarification/binding.py`, `authority.py`):** `BindingService` manages registration, response processing, re-resolution, single-use enforcement, and expiration. `classify_authority()` enforces D4/D5 certainty rules (`EXACT_ID`, `EXACT_ALIAS`, anchored `ACTIVE_UI`, anchored `CURRENT_ATTACHMENT`, verbatim `EXACT_TITLE`). Model-only preference never binds. `tentative_eligible()` restricts non-deterministic bindings to actions with declared `NONE` or `RECOVERABLE` impact.
- **Attribute Narrowing & Adaptive UI (`uri_v1/reference_clarification/attribute_narrowing.py`, `template_renderer.py`, `render_validator.py`):** `recommend_axis()` computes non-degenerate splits across grounded metadata. `validate_render()` validates model-drafted questions against slot facts, falling back safely to deterministic templates.
- **Safeguards (`uri_v1/reference_clarification/safeguards.py`):** `ClarificationSafeguards` tracks progress and enforces cost ceilings to prevent clarification loops.

### 2.2 Existing Production Execution & Capability Infrastructure (`uri_core/`)
- **Wrong-Binding Gate (`uri_core/capabilities/wrong_binding.py`):** Evaluates action impact against reference bindings. Blocks unconfirmed bindings on consequential actions (`GateOutcome.CONFIRMATION_REQUIRED`), permits tentative bindings on recoverable actions (`ALLOWED_TENTATIVE_RECOVERABLE`), but evaluates to `NOT_APPLICABLE` when `reference_bindings is None`.
- **Capability Executor (`uri_core/capabilities/executor.py`):** `MultiActionExecutor.execute()` accepts `reference_bindings` and evaluates `evaluate_wrong_binding_gate()`. `execute_chain()` passes `step.get("reference_bindings")` to `self.execute()`.
- **Approval Gate & Store (`uri_core/core/approval_gate.py`, `approval_store.py`):** `ApprovalStore` persists `ProposedAction` records (`action_id`, `capability_id`, `session_id`, `arguments`, `arguments_fingerprint`, `status`). `ApprovalGate` validates decisions and consumes approvals before dispatch.
- **Two proposal sites:** `canonical_execution.py:177-180` and `approval_gate.py:186-191` call `ApprovalStore.propose()`; neither supplies per-action/per-slot source identity. `approval_store.py:379-415` explicitly reconstructs fields and would drop a newly added field without a loader change. `ApprovalGate.decide():280-285` consumes before direct `ToolDispatcher.execute_tool()` at `:308-312`, which has no S2 binding gate. Natural-language multi-action resumption consumes at `approval_resumption.py:215-220`; its legacy branch currently calls `decide()` at `:170` and again at `:191`.
- **Candidate Sources:** `FileStore` (`uri_core/core/file_store.py`), Gmail search (`uri_core/capabilities/gmail/capability.py`), Drive search (`uri_core/tools/drive_search.py`), `TurnState` current-turn attachments (`uri_core/core/turn_state.py`), and Memory retrieval (`uri_v1/memory/`).

### 2.3 Existing Flutter UI (`uri_ui/`)
- **Card Widget (`uri_ui/lib/widgets/clarification_card.dart`):** Interactive card supporting candidate buttons, attribute chips, free text entry, and lock states.
- **Clarification Models (`uri_ui/lib/models/clarification.dart`):** `ClarificationRequest` and `ClarificationResponse` models matching S1 wire specifications.
- **Turn Card (`uri_ui/lib/widgets/turn_card.dart`):** Container for turn rendering in chat.
- **Ask Screen (`uri_ui/lib/screens/ask/ask_uri_screen.dart`):** Primary desktop interaction screen.

---

## 3. What Does the Live System Actually Do Today?

Tracing the live production call path reveals where reference clarification and binding enforcement break down:

```
POST /ask (server.py:1653)
  ├── 1. Natural Language Approval Resumption (server.py:1675 -> approval_resumption.py:208)
  │      └── Calls dispatch_explicit() with stored arguments.
  │          [GAP: No binding re-check, no source freshness check]
  ├── 2. Lifecycle Intent Seam (server.py:1712)
  ├── 3. Experimental Edge-First Seam (server.py:1739)
  │      └── Social-only local route.
  ├── 4. Workflow Continuation / Canonical Routing (server.py:1768 -> canonical_execution.py:740)
  │      ├── Decision Engine generates decision (decision_engine.py:490).
  │      │   [GAP: No reference_slots schema in prompt, no structured slot proposal]
  │      ├── If MISSING_PARAMETER or mode=clarification:
  │      │   └── canonical_execution.py:446-468 emits plain text awaiting_user_response.
  │      │       [GAP: No RAR query, no candidate IDs, no interactive card]
  │      ├── Ready Read Prefix (canonical_execution.py:820-845):
  │      │   └── Dispatches read actions before main block.
  │      │       [GAP: Does not gate on reference dependencies]
  │      └── Action Execution (_execute_canonical -> canonical_execution.py:212,255):
  │          ├── Single action: calls dispatch.dispatch_explicit() (canonical_execution.py:223)
  │          │   [GAP: Does NOT pass reference_bindings]
  │          └── Chain action: calls dispatch.dispatch_chain_explicit() (canonical_execution.py:272)
  │              [GAP: Steps list does NOT include reference_bindings]
  └── 5. Legacy Fallback (server.py:1878)
         └── Calls context.orchestrator.process_user_input() directly.
             [GAP: Bypasses canonical gating completely]
```

### Dispatch Breakdown (`multi_action_dispatch.py`):
In `MultiActionDispatch.dispatch_explicit()` (`multi_action_dispatch.py:236`):
```python
result = executor.execute(
    capability, action_name, bound_inputs,
    user_approved=user_approved, admin_approved=admin_approved,
    # reference_bindings is NOT passed!
)
```
In `MultiActionDispatch.dispatch_chain_explicit()` (`multi_action_dispatch.py:265`):
```python
result = executor.execute_chain(
    steps, user_approved=user_approved, admin_approved=admin_approved,
    # steps lack reference_bindings!
)
```

### Gate Inaction (`wrong_binding.py`):
In `evaluate_wrong_binding_gate()` (`wrong_binding.py:112-113`):
```python
if reference_bindings is None:
    return decide(True, GateOutcome.NOT_APPLICABLE)
```
Because `canonical_execution.py` and `multi_action_dispatch.py` omit `reference_bindings`, `reference_bindings` is always `None`, rendering S2's wrong-binding safety gate completely inoperative.

---

## 4. What Concrete Evidence Proves the Gap or Defect?

Empirical code inspection verifies each defect cited in the independent audit:

1. **H1 — Bindings cannot reach the executor:**
   - `uri_core/core/canonical_execution.py:223-226`: `dispatch.dispatch_explicit()` takes only `capability_id, action_name, inputs, session_id, user_text, principal`.
   - `uri_core/core/canonical_execution.py:264-274`: `steps` dictionaries contain only `capability, action, inputs`.
   - `uri_core/core/multi_action_dispatch.py:236-239`: `executor.execute()` called without `reference_bindings`.
   - `uri_core/core/multi_action_dispatch.py:265-267`: `executor.execute_chain()` called without passing step bindings.
   - `uri_core/capabilities/wrong_binding.py:112-113`: Returns `GateOutcome.NOT_APPLICABLE` when `reference_bindings is None`.
   - `desktop_recovery_allowlist.py:20-49`: `multi_action_dispatch.py` is not allowlisted.

2. **H2 — Resumed approvals bypass binding checks:**
   - `uri_core/core/approval_resumption.py:232-235`: Natural-language approval replays stored `record.arguments` into `dispatch_explicit()` with `user_approved=True` without validating whether referenced files, emails, or entities still exist or match their original fingerprints.
   - `uri_core/app/server.py:2248-2289` (`/approve`): Resolves context and calls `orchestrator.decide_action()`, executing through `approval_gate.py:308` (`dispatcher.execute_tool()`) without renewed binding checks.
   - `uri_core/core/approval_store.py:150-168`: `ProposedAction` dataclass stores arguments and fingerprint, but does not retain binding identity (`ref_key`, `candidate_id`, `source_locator`, `source_version`, `binding_status`).

3. **H3 — Uncovered execution routes:**
   - `uri_core/core/native_tool_loop.py:223-228`: `_execute_canonical()` is invoked independently per native tool call without reference binding transport.
   - `uri_core/app/server.py:1878-1884`: Legacy fallback invokes `orchestrator.process_user_input()` directly when canonical routing returns fallback, with no reference binding gate.
   - `uri_core/core/canonical_execution.py:820-845`: Ready read prefix dispatches read actions before the normal block without gating on reference dependencies.
   - `uri_core/core/canonical_execution.py:282-342`: Canonical LEGACY tool execution bypasses `MultiActionExecutor` entirely; a slot-bearing decision needs pre-dispatch checking or exclusion in this approved file.
   - `uri_core/core/canonical_execution.py:559-609`: The web/fetch and Gmail search ready-prefix branches are separate entry cases.
   - `uri_core/core/native_tool_loop.py:318-322`: A second native chain execution site exists beyond `:223-228`.
   - `uri_core/app/server.py:1752-1799`: M30.7 early workflow continuation invokes canonical routing **before** native/default canonical or legacy fallback; a fallback-only guard cannot cover it.
   - `uri_core/core/orchestrator.py:4936,5261-5266,2651,2916,6051-6061` and `uri_core/core/workflow_capability_router.py:510`: Legacy multi-action, direct capability and workflow execution/continuation can execute beneath `server.py:1878-1884`. `orchestrator.py` must not grow; router/dispatcher edits are not approved.
   - `uri_core/app/server.py:1692-1725`: Lifecycle `enable`, `disable`, `connect`, `disconnect`, `remove` mutate state before canonical Brain slots exist. `:1730-1748` Edge is social-only. Both are excluded by pending-round state and their narrow existing contracts, not a reference keyword classifier.

4. **M1 — Streaming route bypass:**
   - `uri_core/app/server.py:2179,2191`: `_ask_stream_eligible()` does not check for `payload.clarification_response`. A typed clarification response payload submitted to `/ask/stream` could enter `stream_first_turn()` instead of the authenticated clarification intake handler.

5. **Historical S4 Replay Evidence:**
   - `docs/plans/M33_3_S4_STATE.md:29`: Offline replay on curated inventories demonstrated residual wrong bindings when live candidate inventories were not strictly qualified and re-checked.

---

## 5. Is the Problem Local or Architectural?

The problem is an **integration-level boundary and transport gap**:
- The individual algorithms (`uri_v1` RAR resolver, S1 clarification builder, binding state machine) and UI components (`ClarificationCard`) are sound and frozen.
- However, the plumbing between the Brain's decision prompt, the execution dispatchers (`canonical_execution.py`, `multi_action_dispatch.py`), the safety gates (`wrong_binding.py`), the approval resumption paths, and the desktop client was left disconnected.
- This requires an integration architecture that connects these components across the full agent loop without modifying frozen algorithms or loosening safety gates.

---

## 6. Is There Already an Existing Capability or Module Intended to Solve It?

Yes:
- `uri_v1/turn/` and `uri_v1/reference_clarification/`: Own the deterministic RAR and clarification logic.
- `uri_core/capabilities/wrong_binding.py`: Owns the S2 Wrong-Binding Gate.
- `uri_core/capabilities/executor.py`: Already accepts `reference_bindings` in `execute()` and `execute_chain()`.
- `uri_ui/lib/widgets/clarification_card.dart` and `uri_ui/lib/models/clarification.dart`: Already define the UI presentation and response contracts.

None of these components require rewriting; they require end-to-end integration and wire transport.

---

## 7. What Dimension Is the Issue?

The defect spans three specific dimensions:
1. **Integration & Transport:** Transporting `reference_bindings` from canonical execution down to `MultiActionExecutor.execute()`.
2. **Routing & Dispatch Safety:** Every entry in the [Stage 3 complete inventory](../plans/INT_ARN_1_PLAN.md) needs a binding gate or fail-closed exclusion at its entry boundary, including canonical LEGACY, both ready-prefix branches, both native sites, stream, fallback descendants, workflows, lifecycle, approvals and Edge.
3. **State & Durability:** Persist clarification rounds and per-action/per-slot approval identity through both proposal sites and `_load()`, then revalidate under the authenticated principal **immediately before each `consume()`**, independently of the legacy dispatcher. Drift must leave approval unconsumed.

---

## 8. What User-Visible Failure Demonstrates the Problem?

1. **Broken Disambiguation:** A desktop user asking "delete the project draft" or "send the presentation to Chetan" receives a plain text response or an error, rather than an interactive card presenting the grounded candidate options.
2. **Silent Unconfirmed Consequential Actions:** If an ungrounded or tentative binding reaches dispatch, the S2 gate is bypassed (`reference_bindings=None`), risking consequential execution on the wrong entity without user confirmation.
3. **Stale Approval Execution:** If an approval is requested for an action targeting "document A", and the document is modified or deleted before the user approves via natural language ("yes") or the desktop button, the system executes against the stale/altered entity without re-verifying the binding.
4. **Streaming Protocol Failure:** Submitting a clarification choice through a streaming-enabled client enters `stream_first_turn`, failing to resolve the pending clarification round.
