# INT-ARN-1 — Stage 3: Real RAR/reference clarification in desktop `/ask` Migration & Integration Plan

**Status:** Stage 3 Migration & Integration Plan (Codex pre-audit revisions incorporated), 2026-10-02.  
**Branch:** `experimental/desktop-recovery-repair`, HEAD `554041e`.  
**Governance:** [URI Four-Stage Development Lifecycle](../governance/URI_FOUR_STAGE_DEVELOPMENT_LIFECYCLE.md)  
**Prerequisites:**  
- Stage 1: [Evidence & Root-Cause Audit](../research/INT_ARN_1_ROOT_CAUSE_AUDIT.md) (Frozen)  
- Stage 2: [Canonical Architecture Design](../architecture/INT_ARN_1_CANONICAL_ARCHITECTURE.md) (Frozen)  
Chetan's in-thread 08:46 UTC and 09:02 UTC approvals authorize planning this governed integration; this document does not declare implementation, component adoption, independent verification, freeze, or release. No code, test, governance-state, or runtime data is changed by this planning turn.

---

## 1. Goal, identity, and boundaries

Connect the already frozen `uri_v1` deterministic Reference Anchor Resolution (RAR) and M33.3 S1 clarification/binding engine to the real authenticated desktop `/ask` path. The Brain identifies the user's intended reference and writes the user-facing question; URI assembles only admissible evidence, checks RAR outcomes, presents an adaptive, grounded card, validates the answer, and feeds the resulting binding into a fresh Brain decision and existing execution gates. The visible outcome must survive a follow-up turn and be usable through the canonical agent loop. This respects the model/runtime division in [ADR-018:8-20,60-90](../../URI_Model_Centric_Architecture_Docs/URI_ADR_018_MODEL_CENTRIC_ARCHITECTURE.md), [AI policy:231-235](../../URI_Model_Centric_Architecture_Docs/URI_AI_OPERATING_POLICY.md), and [model/runtime contract:7-9,107-109,193-201](../../URI_Model_Centric_Architecture_Docs/URI_MODEL_RUNTIME_CONTRACT.md).

The name here means **reference clarification using RAR**, including the S1 port of ARN.1's attribute narrowing. It does not silently merge `EXP-ARN-URIV1` research with `URI-ARN-PRODUCTION`: the alias map forbids the bare ARN identity [URI_STATE.yaml:749-765](../governance/URI_STATE.yaml). Production ARN.1 is the separately verified NOT_FOUND recovery engine, paused after ARN.1 [ARN plan:45-55,168-194,372-392](ARN_ADAPTIVE_RETRIEVAL_NARROWING_PLAN.md), [ARN_1_STATE.md:14-39](ARN_1_STATE.md). Its optional case-summary evidence can inform a later recovery turn; this milestone does not implement ARN.2-5.

**Non-goals:** new RAR scoring or detector rules; editing frozen `uri_v1/`; learned preference/tie-break weights or repetition auto-promotion; new Gmail, Drive, Office, or Graphify permissions; broad retrieval or a new search index; new chat navigation/screen; autonomous consequential execution; porting the old harness-first `arn_state` field wholesale; release/commit by Codex.

---

## 2. Governance and lifecycle entry gates

- M33.3 S1-S12 closed within offline/fixture scope; S9 moved to Memory/D4 and S13 production integration was explicitly excluded pending a separate INT authorization [M33_3_CROSS_PLAN_STATE.md:8-11,146-150](M33_3_CROSS_PLAN_STATE.md), [URI_ACTIVE_MILESTONE.md:990-998](../governance/URI_ACTIVE_MILESTONE.md). The 08:46 UTC and 09:02 UTC User rulings supply the requested **INT-ARN-1 planning direction**, not evidence that those earlier gates have been completed.
- `integration_events: []` and `URI-RAR` still `EXPERIMENTAL` in the checked-in machine record [URI_STATE.yaml:633-644,647-676](../governance/URI_STATE.yaml). Before production enablement, the release authority must record this INT event and an explicit URI-internal `URI-RAR` adoption/qualification decision with its limitations. Cross-agent portability is not claimed. The S13 gate names S4 evidence, adoption, and INT authorization [M33_3_CROSS_PLAN_STATE.md:150-161](M33_3_CROSS_PLAN_STATE.md).
- S4 was an offline replay on curated inventories, not proof of live retrieval; it found wrong bindings requiring attention [M33_3_S4_STATE.md:29](M33_3_S4_STATE.md). INT-ARN-1 must qualify the live source producer with held-out cases and zero consequential false dispatch. This is a stop gate, not inherited success.
- The four-stage lifecycle requires a frozen root-cause audit, canonical architecture, migration plan, then implementation and end-to-end validation [URI_FOUR_STAGE_DEVELOPMENT_LIFECYCLE.md:28-63,63-85,91-151,151-193](../governance/URI_FOUR_STAGE_DEVELOPMENT_LIFECYCLE.md). In strict adherence to this lifecycle, Stage 1 has been frozen in [`docs/research/INT_ARN_1_ROOT_CAUSE_AUDIT.md`](../research/INT_ARN_1_ROOT_CAUSE_AUDIT.md) and Stage 2 in [`docs/architecture/INT_ARN_1_CANONICAL_ARCHITECTURE.md`](../architecture/INT_ARN_1_CANONICAL_ARCHITECTURE.md). This document represents the **Stage 3 Migration & Integration Plan**, incorporating the findings of the independent Codex pre-audit.
- Frozen M36-M39 code in `uri_v1/` is read/reused, never modified. Exact-file pins guard `uri_core/` and `uri_ui/`; the baseline allowlist includes `server.py`, `canonical_execution.py`, `decision_engine.py`, `uri_turn.dart`, `app_state.dart`, `http_uri_client.dart`, `uri_client.dart`, and `turn_card.dart` [desktop_recovery_allowlist.py:21-48](../../desktop_recovery_allowlist.py).
- **Approved frozen additions (2026-10-02 09:02 UTC):** Chetan approved adding `uri_ui/lib/screens/ask/ask_uri_screen.dart`, `uri_ui/lib/widgets/clarification_card.dart`, and `uri_ui/lib/models/clarification.dart` (if needed) to the allowlist.
- **Pending User approval additions:** To resolve audit findings H1, H2, and H3, the User has been asked to approve `uri_core/core/multi_action_dispatch.py`, `uri_core/core/approval_resumption.py`, and `uri_core/core/native_tool_loop.py`. These files are listed as **pending User approval**; implementation slices touching them must wait for explicit User approval before modifications begin.
- The repository's `URI_ACTIVE_MILESTONE.md` has additive historical M39 notes [lines 10-36](../governance/URI_ACTIVE_MILESTONE.md); the checked-in INT registry currently has no INT event. The implementation coordinator must reconcile milestone/governance records before claiming an active or accepted integration. This planning turn cannot edit those records.

---

## 3. Evidence of the current gap

### Frozen services to reuse

| Boundary | Current public behavior and constraint |
|---|---|
| RAR input/output | `RARCandidate` has ID/title/type/ordinal recency and optional owner, attachment, aliases; `RARQuery` has expression, candidates, local evidence, anchors; `RARResolution` has `RESOLVED/UNKNOWN/AMBIGUOUS`, basis, failure class and rule. Resolution validation rejects invented IDs [rar_contracts.py:25-69,76-160,160-224](../../uri_v1/turn/rar_contracts.py). `resolve_rar_deterministic_extended(query)` returns a trace with resolution and diagnostic scores, which are **not calibrated confidence** [rar_deterministic.py:82-93,235-282](../../uri_v1/turn/rar_deterministic.py). RAR may itself truncate an ambiguity set; the integration must retain exactly the returned scope [rar_deterministic.py:908-932](../../uri_v1/turn/rar_deterministic.py). |
| Clarification | Four kinds, three response kinds, binding states, impact enum, five-option cap, full `scope_candidate_ids`, candidate-set fingerprint and provenance fields are frozen [rar_clarification_contract.py:12-145,145-199](../../uri_v1/turn/rar_clarification_contract.py). `build_clarification` classifies a RAR resolution, picks candidate/attribute/free-input presentation and fingerprints the complete round scope [builder.py:29-145](../../uri_v1/reference_clarification/builder.py). |
| Binding and authority | `BindingService.register/respond/open_change/record_execution/authorize_redo` own the lifecycle, freshness, single-use/expiry checks and re-resolution [binding.py:37-80,86-140,140-309,309-391](../../uri_v1/reference_clarification/binding.py). `classify_authority` requires specific certainty-tier rule **and** supporting anchor; `tentative_eligible` requires grounded, non-model-only resolution and `NONE/RECOVERABLE` impact [authority.py:16-64](../../uri_v1/reference_clarification/authority.py). |
| Adaptive UI wording | `recommend_axis` finds a non-degenerate split of grounded title/type/owner/recency facts [attribute_narrowing.py:16-51](../../uri_v1/reference_clarification/attribute_narrowing.py); `SessionEvidence` records selections/clues/corrections but does not bind [session_adjunct.py:8-24](../../uri_v1/reference_clarification/session_adjunct.py). `ClarificationSafeguards` charges progress/cost [safeguards.py:8-23](../../uri_v1/reference_clarification/safeguards.py). Template output and `validate_render` provide safe fallback and slot/fact validation [template_renderer.py:9-42](../../uri_v1/reference_clarification/template_renderer.py), [render_validator.py:51-117](../../uri_v1/reference_clarification/render_validator.py). |
| Store | `InMemoryClarificationStore` holds rounds, bindings and queries only in process [store.py:11-45](../../uri_v1/reference_clarification/store.py). An integration-owned durable adapter is necessary for restart-safe round trips. |
| Production ARN.1 | `ARNEngine` can hold task-local candidates, record checked sources, apply a user clue, enforce a cost ceiling and recommend an axis without authoring text [engine.py:42-78,108-158,175-256](../../uri_core/core/arn/engine.py). `attach_not_found_recovery` adds `arn_state` only to a genuine empty-result envelope [integration.py:11-70](../../uri_core/core/arn/integration.py); canonical execution invokes it after dispatch [canonical_execution.py:899-909](../../uri_core/core/canonical_execution.py). |
| Memory | M36 `MemoryQuery` needs trusted, user/session-bound intake; `RetrievedCandidate` carries a verified source, tier, last-used time and locator [contracts.py:519-580](../../uri_v1/memory/contracts.py). `Retriever.retrieve` is session-first, caps candidates at 16, validates source fingerprints, can use factual task/outcome history, and has no learned ranking [retrieval.py:1-12,75-180](../../uri_v1/memory/retrieval.py). `MemoryIndex.open_tasks` exposes task labels and historical references, not current binding authority [index.py:218-236](../../uri_v1/memory/index.py). |

The existing decision path gives the Brain `recent_conversation`, an `active_pointer`, facts and explicit current-turn attachments [decision_engine.py:490-516](../../uri_core/core/decision_engine.py), [turn_state.py:365-459](../../uri_core/core/turn_state.py). It allows a plain `clarification` string in its structured decision [decision_engine.py:75-90,180-186](../../uri_core/core/decision_engine.py). `run_canonical_for_ask` obtains that decision and evaluates its gates [canonical_execution.py:740-815](../../uri_core/core/canonical_execution.py). `MISSING_PARAMETER` or `mode=clarification` produces a plain `awaiting_user_response` message, with no RAR round, candidate IDs or binding [canonical_execution.py:446-468](../../uri_core/core/canonical_execution.py). Thus the Brain can ask a question today, but the desktop cannot show or answer the frozen grounded clarification contract.

`POST /ask` takes session/text/model override and explicit attachment handles; it authenticates and validates handles before routing [server.py:1009-1021,1653-1664](../../uri_core/app/server.py). It runs approval resumption, lifecycle, experimental Edge chat, optional native tool loop, then canonical decision/legacy fallback [server.py:1666-1923](../../uri_core/app/server.py). Any integration must respect that ordering and intercept a typed answer before it can be mistaken for a new request or approval. The final response currently whitelists only status/execution/response/narrative/telemetry and drops any `arn_state` [server.py:1973-2092](../../uri_core/app/server.py). `conversation_history` is user-scoped per-session JSON [server.py:417-420](../../uri_core/app/server.py), [conversation_history.py:74-79,129-132,167-224](../../uri_core/core/conversation_history.py). `FileStore` is user-scoped at context construction, has session records and explicit handle lookup [server.py:424-442,1578-1595](../../uri_core/app/server.py), [file_store.py:194-261,288-315](../../uri_core/core/file_store.py). Gmail search returns bounded real messages and metadata; Drive search returns real file records [gmail/capability.py:187-216](../../uri_core/capabilities/gmail/capability.py), [drive_search.py:1-51](../../uri_core/tools/drive_search.py). Neither raw provider result nor transcript prose is itself a binding or proof of current access. The adapter must reauthorize and refresh before use.

The existing S2 wrong-binding gate is opt-in: `reference_bindings=None` is a strict no-op (`GateOutcome.NOT_APPLICABLE` at [wrong_binding.py:112](../../uri_core/capabilities/wrong_binding.py)). Canonical execution calls `dispatch_explicit` (~223) and `dispatch_chain_explicit` (~264) without `reference_bindings`, and `multi_action_dispatch.py:236,265` calls `executor.execute()` without bindings, completely bypassing S2 in production (H1). Resumed approvals in `approval_resumption.py:208-235` and `/approve` in `server.py:2248` dispatch without re-verifying binding identity or source validity (H2). Native tool loops (`native_tool_loop.py:223`), legacy fallback (`server.py:1878`), and the ready read prefix (`canonical_execution.py:820`) lack verified binding gates (H3). In `POST /ask/stream`, typed clarification responses can bypass `/ask` and enter `stream_first_turn` (M1).

Flutter already has a **fixture-only** `ClarificationRequest` parser and `ClarificationCard`, with candidate taps, attribute chips and free text [clarification.dart:72-159,161-228](../../uri_ui/lib/models/clarification.dart), [clarification_card.dart:18-60,103-160](../../uri_ui/lib/widgets/clarification_card.dart). The approved inline-card reference maps it to `TurnCard` and Kiranism's quick-reply structure [clarification_card_2026-09-27.md:1-13](../design_library/approved/clarification_card_2026-09-27.md), [chat/README.md:20-20,66-70](../design_library/chat/README.md). Today `UriTurn` has no clarification stage/payload [uri_turn.dart:8-25,97-139](../../uri_ui/lib/models/uri_turn.dart), `HttpUriClient.ask` sends only text/session/model override and parses a plain turn [http_uri_client.dart:310-413,420-536](../../uri_ui/lib/services/http_uri_client.dart), `AppState.ask` only sends a text turn [app_state.dart:497-539](../../uri_ui/lib/services/app_state.dart), and `ask_uri_screen.dart` constructs `TurnCard` without a clarification callback [ask_uri_screen.dart:225-242](../../uri_ui/lib/screens/ask/ask_uri_screen.dart).

---

## 4. Acceptance criteria and stop gates

1. **Source grounding:** for every option, produce a stable scoped ID, type, authorized locator, source class, observed version/fingerprint and factual display fields. Candidate IDs in a RAR result and card must be subsets of the real producer inventory; zero synthetic candidates in held-out and live traces. Missing provenance, permissions, stale/hidden/deleted source or incomplete exact-title collision scope causes abstention/refresh.
2. **Brain first:** the Brain, using a backward-compatible optional `reference_slots` proposal, identifies the expression and action parameter requiring a reference. Runtime validates span, slot, target, candidate membership and actions. No keyword table or file-extension heuristic may decide that a reference exists, select an entity, or overrule the Brain. URI may reject unsafe proposals and may ask the Brain for a new proposal.
3. **Adaptive question:** `CHOOSE_ONE`, `CONFIRM_ONE`, `CHOOSE_ATTRIBUTE`, `FREE_INPUT_ONLY` render when eligible. At most five displayed options; attribute groups use actual metadata; options have distinguishing sourced facts; no padding or invented label. The Brain drafts the question/labels from the bounded render request; `validate_render` checks them and the frozen template is the deterministic fallback. URI retains the escape path.
4. **Desktop interaction:** the card appears inline with the affected turn, clickable choice/attribute and text entry work with mouse/keyboard, and a submitted card locks while awaiting the response. The typed S1 payload round-trips to `/ask` with authenticated user and session; a click resolves through `BindingService`, not a client-supplied label or bare ID.
5. **Binding authority:** only `EXACT_ID`, `EXACT_ALIAS`, anchored `ACTIVE_UI`, anchored `CURRENT_ATTACHMENT`, or uniquely anchored/verbatim `EXACT_TITLE` can become `CONFIRMED`. Heuristic RAR (even with `DETERMINISTIC_ANCHOR` basis) is only `TENTATIVE`-eligible under R2.9; model-only preference never binds. Typed free input follows the same rule [URI_STATE.yaml:497-501](../governance/URI_STATE.yaml), [authority.py:23-64](../../uri_v1/reference_clarification/authority.py).
6. **Consequence:** a non-deterministic binding can proceed visibly only for a declared reversible `NONE/RECOVERABLE` action after the runtime gate; consequential or undeclared impact requires `CONFIRM_ONE` before execution. Existing user/admin approval remains independently required. No action dispatch occurs while a required binding is pending/rejected/stale.
7. **Full round scope:** option cap changes presentation only. Free input reruns against all IDs RAR returned for that round, including undisplayed IDs, never candidates RAR omitted. Unknown/free-input-only may trigger a newly authorized bounded lookup, then a **new** round rather than quietly expanding the old one [M33_3_CROSS_PLAN_STATE.md:89-100](M33_3_CROSS_PLAN_STATE.md).
8. **State/learning:** round, binding, original task pointer, source version, expiry, progress count and correction survive process restart per user; replay/cross-user/stale answers fail closed. Session clues and explicit corrections may aid this session's presentation. M36 factual history may add grounded candidates/recency only; no learned weights/frequency promotion [URI_STATE.yaml:487-500](../governance/URI_STATE.yaml).
9. **Canonical completion:** after a binding, the Brain receives the grounded selection and previous task, reasons afresh, proposes an action, and gets execution results back. No client or adapter asserts success from a click. A Change after a reversible tentative action follows S1 rebind/redo rules; edited results remain a separate version, with fresh approval if required [M33_3_ARN_ARCHITECTURE_AND_LT1B_RENDERER_PLAN.md:477-523](M33_3_ARN_ARCHITECTURE_AND_LT1B_RENDERER_PLAN.md).
10. **Latency/telemetry:** report p50/p95 added integration time and model-call count against same-task baseline; proposed gate is <=300 ms p95 CPU time for cached/session evidence and <=1.5 s p95 added wall time for a bounded source refresh, excluding the existing Brain/provider latency. Any breach requires measured analysis and explicit acceptance before default-on. Log stage durations, source classes/counts, outcome/rule, binding state, clarification rounds, stale/abstain reasons, fallback, corrections and dispatch result using user-scoped IDs/hashes; omit raw email/body/text and rendered labels from routine telemetry.
11. **Live battery:** on the desktop with real consented local files, attachments, Gmail/Drive result records and two users, demonstrate exact ID/title, ambiguous five-plus options, hidden-option free text, attribute narrowing, stale/deleted item, correction, restart, no result, reversible tentative action, consequential confirmation, and denial/approval. Zero cross-user candidates, wrong consequential dispatches or invented success.

---

## 5. Proposed architecture, exact seams, and route matrix

Create `uri_desktop_seams/reference_clarification/` (or `uri_integration/reference_clarification/` if Stage 2 chooses the broader ownership name) **outside both frozen app trees**. Keep a small surface:

1. `proposal.py`: validates an optional Brain-authored `reference_slots` structure (raw span, `ref_key`, target action/argument, relation/dependency, intended source class). It is an untrusted proposal, not binding authority. Existing decisions without slots retain existing behavior.
2. `evidence.py`: one source-to-candidate producer. Inputs: authenticated principal, session/turn, explicit current attachment IDs, relevant conversation/result records, FileStore, authorized Gmail/Drive read results, and optional M36 retrieval. Output: a provenance-bearing evidence envelope and its lossy `RARQuery` projection. `RARQuery` itself lacks source provenance, provider, dependency and freshness fields [M33_3_URI_BRAIN_ARCHITECTURE_PROPOSAL.md:162-184](M33_3_URI_BRAIN_ARCHITECTURE_PROPOSAL.md). Reject text-only transcript mentions as candidates unless an underlying source ID can be checked. Do not synthesize a `current_attachment_id` from older session uploads.
3. `service.py`: calls frozen RAR, `build_clarification`, `BindingService.register/respond`, render validation/template, safeguards, and source revalidation. It maps `BindingState` to the canonical turn outcome. An S1 `InMemoryClarificationStore` is never treated as durable.
4. `store.py`: per-user versioned round/binding journal plus safe loader. Reconstitute the frozen in-memory objects per transaction under a per-user, per-session lock; commit state atomically. Persist only bounded contract, source references/fingerprints, task pointer, expiry, status, and session clues needed for restart. Never persist auth tokens or trust serialized `CONFIRMED` without replaying the source/anchor validity check.
5. `wire.py`: stable `clarification` response projection matching the existing Flutter `ClarificationRequest`, with `trace_id`, question, grounded options/attribute filters, fingerprint and expiry. Add a separate `binding` display projection only when useful; never expose raw provider objects or internal candidate scope. An answer carries the existing `ClarificationResponsePayload` under an optional `clarification_response` field in `/ask` plus `session_id`; free text remains text inside that typed payload, never a new top-level `text` command.

### Allowlisted hooks and pending approvals table

| File | Status | Scope of amendment |
|---|---|---|
| `uri_core/app/server.py` | Allowlisted | 1. Add optional typed `clarification_response` to `AskRequest`.<br>2. Intercept typed response at intake and route to `/ask` handler before streaming eligibility (`POST /ask/stream`) or approval resumption.<br>3. In `/approve` (~2248), re-check retained `binding_identity` and source validity in `ApprovalGate.decide()` before dispatch.<br>4. Exclude legacy fallback from tool execution when reference slots are unresolved.<br>5. Pass integration context to canonical route and whitelist `clarification` payload in final responses. |
| `uri_core/core/decision_engine.py` | Allowlisted | Add optional `reference_slots` schema to the Brain decision prompt and validate its span, action target, and shape. No keyword classification; retain backward compatibility. |
| `uri_core/core/canonical_execution.py` | Allowlisted | 1. Post-decision/pre-dispatch boundary: call integration service when `reference_slots` are proposed; halt dispatch on pending/unsafe binding.<br>2. Pass verified `reference_bindings` to `dispatch.dispatch_explicit()` (~223) and embed in `steps` for `dispatch_chain_explicit()` (~264).<br>3. Gate ready read prefix (~820): suppress prefix dispatch if any action requires an unresolved reference. |
| `uri_core/core/multi_action_dispatch.py` | **Approved (09:24 UTC)** | 1. Accept `reference_bindings: Optional[Sequence[ReferenceBinding]] = None` in `dispatch_explicit()` (~236) and forward to `executor.execute()`.<br>2. In `dispatch_chain_explicit()` (~265), forward each step's `reference_bindings` to `executor.execute_chain()`. |
| `uri_core/core/approval_resumption.py` | **Approved (09:24 UTC)** | In natural-language approval resumption (~208-235), re-verify `record.binding_identity`, source freshness, locator, and impact before calling `dispatch_explicit()`; forward renewed `reference_bindings`; fail closed on drift/deletion. |
| `uri_core/core/native_tool_loop.py` | **Approved (09:24 UTC)** | In `_execute_canonical` call (~223), transport `reference_bindings`; fail closed if native tool call requires an unresolved reference entity. |
| `uri_ui/lib/models/uri_turn.dart` | Allowlisted | Add awaiting-clarification stage/payload and visible tentative-choice state; preserve wire/history decoding. |
| `uri_ui/lib/services/uri_client.dart`, `http_uri_client.dart`, `app_state.dart` | Allowlisted | Typed answer method through `/ask`, response decoding, pending-turn replacement, duplicate-submit guard; preserve text turn. |
| `uri_ui/lib/widgets/turn_card.dart` | Allowlisted | Inline existing `ClarificationCard` under Brain's question; route callback; show “Using X · Change” for tentative binding. |
| `uri_ui/lib/screens/ask/ask_uri_screen.dart` | **Approved (09:02 UTC)** | Bind `TurnCard` clarification response callback to `AppState.submitClarificationResponse()`. |
| `uri_ui/lib/widgets/clarification_card.dart` | **Approved (09:02 UTC)** | Support post-submit lock, safe retry rendering on expiration, accessibility and focus handling. |
| `uri_ui/lib/models/clarification.dart` | **Approved (09:02 UTC)** | Wire contract compatibility verification; minor schema adjustment only if required. |

### Comprehensive Route Coverage Matrix (Addressing H3)

All 8 execution routes across URI are mapped below with their mandatory binding gate or fail-closed exclusion:

| Route Index & Name | Production Path | Binding Gate Enforcement / Exclusion | Fail-Closed Mechanism | Dispatch-Level Verification Test |
|---|---|---|---|---|
| **1. Canonical Single Action** | `canonical_execution.py:223` -> `dispatch.dispatch_explicit()` | Transports verified `reference_bindings` to `MultiActionExecutor.execute()`. | S2 gate blocks execution (`GateOutcome.CONFIRMATION_REQUIRED`) if binding is unconfirmed on consequential action. | `test_canonical_single_dispatches_with_reference_bindings`: asserts `executor.execute` receives verified bindings; asserts dispatch halted on wrong binding. |
| **2. Canonical Chain Action** | `canonical_execution.py:264` -> `dispatch.dispatch_chain_explicit()` | Embeds `reference_bindings` per step; forwarded to `executor.execute_chain()`. | Chain halts at first step with unconfirmed/invalid binding (`status="halted"`), subsequent steps aborted. | `test_canonical_chain_dispatches_with_step_bindings`: multi-step chain asserting per-step binding transport and halting on wrong binding. |
| **3. Ready Read Prefix** | `canonical_execution.py:820-845` -> `_execute_canonical()` | Gated before main block; inspects read actions for reference dependencies. | If any prefix read action depends on an unresolved/pending reference slot, prefix dispatch is suppressed (`read_prefix = []`). | `test_ready_read_prefix_suppressed_when_reference_unresolved`: asserts read prefix does not dispatch against ungrounded entities. |
| **4. Native Tool Loop** | `native_tool_loop.py:223` -> `_execute_canonical()` | Translates native tool call into single-action contract with `reference_bindings`. | If native tool call references an entity requiring disambiguation without a binding, returns `unavailable` with gate block. | `test_native_tool_loop_enforces_reference_binding_gate`: asserts native tool loop halts and fails closed on ungrounded reference. |
| **5. Legacy Fallback** | `server.py:1878` -> `context.orchestrator.process_user_input()` | Explicit fail-closed exclusion. | If turn context indicates an active reference clarification round or unresolved slots, legacy fallback is forbidden from executing tools. | `test_legacy_fallback_fails_closed_on_unresolved_reference`: asserts fallback refuses tool dispatch when clarification is pending. |
| **6. Approval Resumption (Natural Language)** | `approval_resumption.py:208-235` -> `dispatch.dispatch_explicit()` | Re-verifies stored `record.binding_identity`, source freshness, locator, and impact before dispatch; passes renewed bindings. | If source entity is deleted, modified, or expired between proposal and approval, aborts dispatch and returns fail-closed error. | `test_approval_resumption_fails_closed_on_stale_source`: asserts natural-language "yes" fails closed if target document version drifted. |
| **7. API /approve Endpoint** | `server.py:2248` -> `approval_gate.decide()` -> `dispatcher.execute_tool()` | Re-verifies `binding_identity` and source validity in `decide()`; passes `reference_bindings` to dispatcher. | Rejects approval consumption and returns error envelope if entity state drifted or binding expired. | `test_approve_endpoint_fails_closed_on_altered_binding`: asserts `POST /approve` rejects execution when reference entity was deleted. |
| **8. Edge Seam (Harness First)** | `server.py:1739` -> `try_harness_first()` | Explicit fail-closed exclusion. Route is strictly social-only. | Returns `None` immediately if turn contains reference slots, action proposals, or pending clarification rounds. | `test_edge_seam_bypassed_on_reference_turn`: asserts reference-bearing query bypasses Edge seam and routes to canonical `/ask`. |

### Approval record binding identity retention (Addressing H2)
`ProposedAction` in `uri_core/core/approval_store.py` is extended with:
```python
binding_identity: Optional[Dict[str, Any]] = None
```
Capturing: `ref_key`, `candidate_id`, `source_locator`, `source_version`, `status` (`CONFIRMED`/`TENTATIVE`), and `declared_impact`. When `approval_resumption.py` or `server.py:approve()` processes an approval, it reads `record.binding_identity`, invokes the integration service's `revalidate_source_and_binding(principal, binding_identity)`, and constructs the active `ReferenceBinding` list. If the source entity is missing, modified, or permissions were revoked, execution is refused.

### Streaming intake intercept (Addressing M1)
In `uri_core/app/server.py`:
In `POST /ask/stream`:
```python
if payload.clarification_response is not None:
    async for chunk in _fallback_to_ask():
        yield chunk
    return
```
In `_ask_stream_eligible(context, payload)`:
```python
if payload.clarification_response is not None:
    return False
```
This guarantees that typed clarification responses are never routed to `stream_first_turn()`, and are always executed through the authenticated, state-managed `/ask` handler.

---

## 6. Per-turn protocol

1. **Intake:** `/ask` authenticates user, validates session and explicit current attachment handles. If `payload.clarification_response` is present, it is matched to the same user/session/round and processed immediately. A normal text turn follows current approval/lifecycle/Edge/native/canonical ordering. In `POST /ask/stream`, typed clarification responses bypass streaming eligibility and delegate directly to `/ask`.
2. **Brain proposal:** on the canonical decision path, the Brain sees relevant bounded context and may propose `reference_slots` attached to its action or clarification. URI validates it. If missing/invalid, preserve the present truthful clarification/failure; never infer a reference from a keyword classifier. Multiple slots form an S1 `ClarificationBundle` with dependencies; resolve only currently visible slots.
3. **Ground:** evidence producer enumerates only currently authorized source IDs. Same-turn attachments come from the validated handle list; FileStore session records, conversation outcomes, Gmail/Drive records and M36 history are checked for user/session scope, access and freshness. Search/retrieval is bounded; failure becomes `UNKNOWN`, not a manufactured candidate.
4. **Resolve:** build `RARQuery` with only verified anchors. Run frozen `resolve_rar_deterministic_extended`, validate its membership, then call `build_clarification` with the effective action's `wrong_binding_impact`. Certainty binds; eligible reversible heuristic can be TENTATIVE and visibly changeable; all other cases create a persisted round. A referenced action does not reach dispatch until this is settled.
5. **Present:** give the Brain a bounded `RenderRequest` (facts and slots, no authority to add options), validate draft; fall back to S1 template on unsafe/unavailable draft. Serialize displayed options only. Store the full RAR-returned scope and fingerprints server-side. Give the Brain the execution/clarification outcome for user-facing text; URI owns controls.
6. **Respond:** candidate click sends ID+scope fingerprint; attribute sends `a*` key+fingerprint; free input sends typed text. Before `respond`, reload the round, re-check current source records/locators/impact and TTL. `BindingService` makes the transition. Attribute choices produce another round; free input reruns full round scope. Expired/stale/rejected rounds show a safe retry and require a fresh Brain/source pass.
7. **Resume:** binding is recorded as an evidence fact, not a client command. Reconstruct the original goal, ask the Brain for a fresh action proposal, validate it against current capabilities/grants, bind the exact action argument to the verified candidate, and pass S2 reference bindings through all dispatch paths. Return actual execution result to Brain drafting and persist/audit it; if the user changes the topic, close the old round without executing it.

---

## 7. Persistence and migration

- Place the clarification journal under the existing per-user state root, e.g. `uri_workspace/users/<user-id>/reference_clarification/`, resolved through the same server-owned user-scoped path helper as conversation history/FileStore [server.py:350-442](../../uri_core/app/server.py). Never derive a path from a client-supplied user ID or session ID. The planning task does not read or alter that directory.
- Schema v1 contains `user_id`-scoped journal identity, opaque session/turn/ambiguity IDs, version, created/expires timestamps, S1 contract, RAR round scope IDs/fingerprints, source locators/versions, original request pointer, binding state, used marker, progress/cost, optional correction reference. Atomic write/rename and per-user/session lock prevent duplicate click races; load is bounded and validates schema before materializing S1 objects.
- `ProposedAction` in `ApprovalStore` includes `binding_identity` without breaking schema v1.0 deserialization.
- No backfill from conversation prose. Existing sessions begin with no pending round; old plain clarification messages stay readable. Feature-off ignores new journals and continues the old path. On schema upgrade, migrate only valid unexpired records; quarantine corrupt/unknown versions, preserve original bytes for audit and ask afresh. Deletion of a session/user removes its clarification records through an explicit lifecycle hook, with an integration test; TTL cleanup prunes expired rounds without touching source files. Do not couple this store to M36 Memory's factual history log.

---

## 8. Flutter presentation

Use the approved **inline clarification card** within the existing standalone chat workspace; no navigation redesign [clarification_card_2026-09-27.md:5-13](../design_library/approved/clarification_card_2026-09-27.md), [chat/README.md:20-20](../design_library/chat/README.md). Question sits below the user's turn; five or fewer grounded candidate buttons show title plus distinguishing metadata. Attribute mode uses the existing `a*` chips; a consistent “None of these / Enter something else” action opens text input. Tentative result shows “Using X · Change” before a reversible action. A consequential single candidate is explicitly confirmed. While submitting, disable duplicate taps; on rejected/stale/expired response show the server's safe retry instruction, not a locally assumed selection. Support focus order, Enter/Space, screen-reader names including distinguishing facts, narrow and compact widths. Historical cards render read-only state; only an active, unexpired server round can be answered. The card never supplies a capability, approval, fingerprint or candidate beyond its typed response.

---

## 9. Verification and implementation slices for Codex

**Before slice 1:** Stage 1 Root-Cause Audit and Stage 2 Canonical Architecture are frozen. Slices touching files pending User approval (`uri_core/core/multi_action_dispatch.py`, `uri_core/core/approval_resumption.py`, `uri_core/core/native_tool_loop.py`) wait for explicit User approval. Codex implements against the accepted frozen plan; it does not approve, declare VERIFIED, commit or push (AO-4 boundary [ORCHESTRATION.md:1-52](../../ORCHESTRATION.md)).

1. **Slice A — contracts and producer:**
   - Implement `uri_desktop_seams/reference_clarification/proposal.py`, `evidence.py`, `wire.py`.
   - Pure Brain-slot validation, provenance envelope and lossy `RARQuery` projection.
   - Real candidate adapters for FileStore, TurnState current attachments, authorized Gmail search, Drive search, and M36 retrieval.
   - Live-source qualification suite: test cross-user denial, stale/missing sources, duplicate titles, collision scope, boundedness, zero candidate invention. Compare against S4 controls.
2. **Slice B — state, binding transport, and approval re-checks:**
   - Implement durable per-user round journal and S1 adapter in `uri_desktop_seams/reference_clarification/store.py`, `service.py`.
   - Extend `ProposedAction` in `uri_core/core/approval_store.py` to record `binding_identity`.
   - Implement per-action binding transport in `uri_core/core/multi_action_dispatch.py` (Pending User Approval): update `dispatch_explicit()` and `dispatch_chain_explicit()` to accept and forward `reference_bindings`.
   - Implement approval resumption pre-dispatch re-checks in `uri_core/core/approval_resumption.py` (Pending User Approval) and `uri_core/app/server.py` (`/approve`): re-verify source freshness, locator, impact, and grants; fail closed on drift.
   - **Verification:** Unit and dispatch-level tests asserting the exact `reference_bindings` that `MultiActionExecutor.execute()` receives for single actions and multi-step chains; tests asserting approval resumption fails closed when source entity is modified or deleted.
3. **Slice C — canonical `/ask`, streaming intercept, and route matrix coverage:**
   - Update `uri_core/core/decision_engine.py` with optional `reference_slots` prompt schema.
   - Update `uri_core/core/canonical_execution.py`: post-decision binding resolution, pass bindings to `dispatch_explicit` and `dispatch_chain_explicit`, gate ready read prefix.
   - Update `uri_core/app/server.py`: intercept `clarification_response` before `_ask_stream_eligible()` and route directly to `/ask`; exclude legacy fallback on pending reference slots.
   - Update `uri_core/core/native_tool_loop.py` (Pending User Approval): transport bindings into `_execute_canonical()`.
   - **Verification:** Dispatch-level tests covering all 8 routes in the Route Matrix (canonical single, chain, read prefix, native/stream, legacy fallback, approval resumption, `/approve`, Edge seam), verifying binding gate enforcement or fail-closed exclusion. Test `POST /ask/stream` with native streaming enabled to prove typed clarification responses bypass streaming and execute through `/ask`.
4. **Slice D — Flutter presentation & interaction:**
   - Integrate approved files: `uri_ui/lib/screens/ask/ask_uri_screen.dart`, `uri_ui/lib/widgets/clarification_card.dart`, `uri_ui/lib/models/clarification.dart`.
   - Decode clarification card in `UriTurn` (`uri_turn.dart`); submit typed responses via `HttpUriClient`, `AppState`.
   - Embed `ClarificationCard` in `TurnCard`; implement post-submit locks, tentative "Change" callbacks, safe retry display, keyboard navigation, and accessibility semantics.
   - **Verification:** Flutter widget tests for all four clarification kinds, free text entry, 5-option cap, stale locks, and HTTP client wire serialization tests.
5. **Slice E — independent live acceptance:**
   - Run scoped Python and Dart test suites, verify frozen guard pins and SHA-256 hashes.
   - Execute the desktop live battery (§4): real consented local files, attachments, Gmail/Drive records, two-user isolation, ambiguous sets, hidden options, attribute narrowing, stale item detection, restart durability, and approval resumption.
   - Latency and telemetry audit: verify <=300 ms p95 CPU time for cached evidence and <=1.5 s p95 wall time for source refresh.
   - Trace actual production call paths to verify zero bypassed gates, zero ungrounded consequential executions, and full feedback into Brain reasoning.

---

## 10. Risks, rollback, open decisions

**Risks and controls:** S4's residual false bindings require live-source qualification; missing identity/provenance means abstain. RAR's own candidate truncation limits what free input can resolve; do not reconstruct hidden pre-RAR candidates. Gmail/Drive records may go stale or lose permission; refresh before bind and again before action. `MISSING_PARAMETER` and native/legacy routes may bypass a new hook; trace every production dispatch path and fail closed on a Brain-declared reference. Durable round state may outlive a session; use strict user/session/TTL checks. A choice is not an approval.

**Rollback:** `URI_INT_ARN_1_ENABLED` is process/runtime configurable, default **OFF during slices and qualification**; turn ON for a limited desktop cohort only after independent audit and the live battery, then default ON only after the release authority accepts measured success. Turning it OFF routes new text requests through the prior canonical behavior. Existing pending rounds become safely unavailable with a retry-as-text message; no side effect is replayed. Keep journals for diagnosis/forward migration, not for execution under the old path. Compare flag OFF/ON against the same fixed task battery.

---

## 11. User decisions and approvals

### Recorded Rulings (Chetan, 2026-10-02 09:02 UTC)
1. **Exact-file allowlist additions approved:** `uri_ui/lib/screens/ask/ask_uri_screen.dart`, `uri_ui/lib/widgets/clarification_card.dart`, and `uri_ui/lib/models/clarification.dart` (only if a schema mismatch requires it) — each pinned and recorded like existing entries.
2. **RAR Adoption:** After the live battery passes, `URI-RAR` may be recorded as adopted URI-internally with documented S4 limitations; `cross_agent_portable` stays false.
3. **Rollout Configuration:** After independent acceptance and the live battery, `URI_INT_ARN_1_ENABLED` defaults ON for the desktop (single user); it stays OFF during implementation slices and qualification.

### Approved 2026-10-02 09:24 UTC (Chetan, in-thread)
"Approve multi_action_dispatch.py, approval_resumption.py and native_tool_loop.py for INT-ARN-1":
- `uri_core/core/multi_action_dispatch.py` (H1: per-action binding transport to executor)
- `uri_core/core/approval_resumption.py` (H2: natural-language approval pre-dispatch binding re-check)
- `uri_core/core/native_tool_loop.py` (H3: native tool loop reference binding gate)

### Approved 2026-10-02 09:32 UTC (Chetan, in-thread)
"Approve approval_store.py and approval_gate.py for INT-ARN-1":
- `uri_core/core/approval_store.py` (H2: `ProposedAction.binding_identity`)
- `uri_core/core/approval_gate.py` (H2: `/approve` `decide()` binding re-check)

### Four-Stage Lifecycle Status
- **Stage 1 (Audit):** Complete & Frozen in [`docs/research/INT_ARN_1_ROOT_CAUSE_AUDIT.md`](../research/INT_ARN_1_ROOT_CAUSE_AUDIT.md).
- **Stage 2 (Architecture):** Complete & Frozen in [`docs/architecture/INT_ARN_1_CANONICAL_ARCHITECTURE.md`](../architecture/INT_ARN_1_CANONICAL_ARCHITECTURE.md).
- **Stage 3 (Migration Plan):** Accepted candidate in this document (`docs/plans/INT_ARN_1_PLAN.md`).
- **Stage 4 (Implementation):** Awaits independent pre-audit acceptance (all needed frozen files approved).
