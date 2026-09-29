# Edge Specialist Pair: Canonical Architecture (Stage 2 draft)

- **Lifecycle stage:** Stage 2. **Status: `DRAFT` for review.** Not accepted, not implemented, not wired.
- **Date:** 2026-09-29. **Author:** Claude (planning thread). Independent review: Codex, per the User's audit routing.
- **Stage 1 input:** `docs/research/EDGE_SPECIALIST_PAIR_ROOT_CAUSE_AUDIT.md` (cited as "S1A §n").
- **Architecture owner:** M33.2 is the sole owner of the Edge / Second-Brain architecture (`URI_STATE.yaml` → M33.2 `owns_architecture`). This design is written as a **proposed additive amendment** to `docs/architecture/M33_2_EDGE_SECOND_BRAIN_CANONICAL_ARCHITECTURE.md`, following the G1–G3 precedent. It changes no frozen file. Whether to record it as amendment "G4" is a User acceptance step (migration plan §1).

## 0. Acceptance criteria (defined before drafting)

| ID | Criterion |
|---|---|
| B-1 | Every major decision cites the Stage-1 finding it addresses (lifecycle §5). |
| B-2 | Existing accepted mechanisms are reused wherever they exist. Each new mechanism is named, minimal, and justified by a gap shown in S1A. |
| B-3 | There is **one routing authority**: S6, extended by projection (M33.2 G2). No second router. |
| B-4 | Neither model is an authority for eligibility, grounding, permission, capability availability or execution. |
| B-5 | Needle can be bypassed entirely, and either specialist can be replaced, without redesigning URI Core. |
| B-6 | The User's 16 proposal-semantics constraints (thread root) are each satisfied, and §16 maps them. |
| B-7 | The User's measured-value principle governs which specialist gets which task class. The original role split is the starting hypothesis. |
| B-8 | The lifecycle's 12 Stage-2 questions and 10 canonical-loop invariants are answered. |
| B-9 | Anything the current architecture cannot establish without a new semantic mechanism is stated as an explicit decision, with options. |

## 1. Governing inputs and how they combine

1. **Role split** (User, thread root 10:36). Needle 3 proposes exactly one registered tool with exact grounded arguments for a direct request inside a separately qualified envelope, and handles **only** simple, direct tasks. Granite does bounded semantic work outside Needle's envelope and may make one replacement proposal inside its own qualified envelope. The configured Brain does interpretation, clarification, planning, composition, and anything outside both envelopes. The URI runtime owns every authority.
2. **Measured value** (User, project chat 10:48). "Do not assign Edge roles from assumptions about model size or intended purpose. Discover candidate strengths, independently test them, compare overlapping workloads, and give each qualified specialist the tasks where it provides the best measured value."

**Reconciliation (no conflict).** The role split is the *starting hypothesis* and sets two hard bounds:
- Needle is never assigned anything outside the direct class.
- No specialist does Brain work (interpretation, planning, composition beyond its qualified envelope).

Inside those bounds, the measured-value rule decides the assignment for **each task class**. Both models are qualified on overlapping classes, and the class goes to the one with the best measured value, or to neither. In particular, if Granite measures better on direct tool proposals (Stage-1 suggests it may: 11/12 vs 7/12, S1A §3.1), Granite gets that class, and Needle gets it only where it wins. Needle may end up with no class at all, and the design has to work in that case.

## 2. Where this sits in the canonical loop

Canonical loop (`URI_CANONICAL_AGENT_LOOP_ARCHITECTURE.md` §2): OBSERVE → DECIDE → VALIDATE → ROUTE → EXECUTE → RECORD → RE-ENTER? → RESPOND.

The specialist pair is an **alternative, bounded producer of the DECIDE output** for a narrow set of task classes, placed exactly where M33.2 already places Edge proposals:

```text
OBSERVE (Turn State; build_turn_state_and_directory, decision_engine.py:1029)
  + trusted intake spans, RAR/S1 bindings, attachments (uri_v1 M36/S1)
        |
        v
SpecialistRoute (projection of S6 evaluate_intelligence_route; no new router)
   uses: EdgeSettings (mode, Edge ON/OFF, explicit model), EdgeRuntimeInventory,
         SpecialistProfile (pinned qualification per task class), DirectEnvelopeCheck
   -> DETERMINISTIC | EDGE(specialist, task_class) | CAPABLE | LIMITATION | CLARIFY
        |
   EDGE ------> specialist proposal (untrusted)
        |          |
        |          v
        |     SpecialistProposalValidator (deterministic)
        |          | accept                         | reject(reason)
        |          v                                v
        |   canonical translate -> gates -> approval   next-ranked qualified specialist
        |   -> execute (M33.2 §2.1 seam)                (at most one replacement) or
        |   -> evidence/verify -> RECORD                 configured Brain / CLARIFY /
        |                                                LIMITATION
        v
CAPABLE: configured Brain, unchanged (native tool loop)
```

**Brain discovery is unchanged.** The configured Brain still sees the full catalogue through `build_tool_schemas` (`tool_schema.py:180-226`). Specialists see only the bounded envelope projection (M33.2 §5).

## 3. Components

### 3.1 Reused, unchanged

| Component | Where | Used for |
|---|---|---|
| Turn State and capability directory | `uri_core/core/decision_engine.py:1029`, `capability_directory.py` | Availability, shortlist source, feasibility |
| Trusted intake, verbatim grounding, negation and affirmative gates | `uri_v1/memory/uri_adapter/envelope.py:16-93`; `uri_v1/memory/contracts.py:238,298` | Structural eligibility and argument provenance (S1A §4, RC-2, RC-3) |
| RAR, S1 binding, clarification rounds, `tentative_eligible` | `uri_v1/turn/rar_*`, `uri_v1/reference_clarification/*` | Bound arguments, pronouns, missing/ambiguous references → CLARIFY (RC-1, T13–T16) |
| Capability metadata | `uri_core/capabilities/base.py` (`EffectType`, `ApprovalRequirement`, `RiskLevel`, `wrong_binding_impact`) | Authority-sensitive exclusion (RC-4) |
| S6 routing and Edge settings | `uri_core/core/edge/routing_policy.py:145-216`; `settings.py`; `runtime_inventory.py` | Edge-off, `EDGE_ONLY`, `HYBRID`, `MAIN_BRAIN_PREFERRED`, explicit model, resource admission |
| Edge contracts | `uri_core/core/edge/contracts.py` (`EdgeIntelligenceProvider.propose_tools`, `extract`, `EdgeProposal`) | Provider-neutral specialist port |
| Canonical translation and gates | `tool_call_translator.py:34-77`; `decision_gates.py:223-538` | Registered/offered check, availability, permission, approval |
| Execution seam | `native_tool_loop.execute_translated_batch` (`:250`), M33.2 §2.1 | Accepted proposals enter the same path as the Brain's |
| In-turn duplicate refusal | `native_tool_loop.py:206-221` (`executed_signatures`) | Side-effect dedup within a turn |
| Approval single-use consumption | `approval_store.py:179,233,298`; `approval_resumption.py` | Cross-turn approval dedup |
| Pinned qualification record pattern | `uri_v1/edge/registry.py:26-66` (pattern only; M37 file untouched) | "Separately qualified envelope" = a digest-pinned record |
| Evaluation events, route performance, lease residency | `uri_v1/evaluation/events.py` (S7), `route_performance.py` (S8), `uri_core/core/edge/lease_ownership.py` (S10) | Telemetry, G3 preference among qualified routes, residency |

### 3.2 New (minimum)

Each exists because S1A shows a gap that no accepted component fills.

| ID | Component | Kind | Why it is needed (S1A) | Why it is minimal |
|---|---|---|---|---|
| N1 | **SpecialistProfile** | Deployment-owned data plus loader | RC-12: `EdgeSettings.edge` selects one model; the pair needs role-per-task-class selection. The measured-value rule needs a place to record per-class winners. | Reuses the existing single `edge` selection: the user selects one *profile id* (`runtime_id`/`model_id` pair naming the profile), so the settings schema does not change. The profile maps `task_class → ranked qualified specialists → artifact hash → pinned qualification record digest`, following the M37 registry pattern. |
| N2 | **DirectEnvelopeCheck** | Pure deterministic function | RC-1: eligibility cannot come from the model. S6's `edge_sufficient` has no producer (RC-12). | Composes only existing facts (§5). No new semantics, keywords or model call. |
| N3 | **SpecialistProposalValidator** | Pure deterministic function | RC-2 (value grounding missing on the live path), RC-5 (exactly one call), RC-6 (suppressed calls), plus envelope membership | Runs *before* the unchanged translator and gates and adds no authority. It can only reject. |
| N4 | **SpecialistAttemptLedger** | Per-turn, append-only record | Constraint 13: fallback and resume must never repeat a completed side effect. `executed_signatures` is in-turn and exempts read-only actions (`native_tool_loop.py:214`). | Records stage, proposal hash and dispatch receipt. A fallback is refused once any dispatch receipt exists for that turn. |
| N5 | **ExtractionValidator** | Pure deterministic function | RC-7, RC-8, W10–W13 | Closed schemas with explicit `ABSENT`, closed enums, verbatim-span values, and URI-side numeric parsing of the span |
| N6 | **`route_specialist()`** | Projection of S6 | B-3 | Same pattern as the existing `route_clarification_wording` projection (`routing_policy.py:218`). It calls `evaluate_intelligence_route`; it is not a second router. |
| N7 | **Specialist adapters** | Provider adapters behind `EdgeIntelligenceProvider` | RC-9 (encoding), RC-6 (suppressed channel), RC-11 (placement recording) | One per provider. Needle: stdio, `complete()` only, never `run()` (M33.2 §4.2), explicit UTF-8 both ends, suppressed calls kept in a quarantined field. Granite: loopback-only Ollama (M33.2 §4.2 loopback assertion), schema-constrained output. |

**Not introduced:** no new router, dispatcher, executor, approval path, capability registry, verifier authority, or keyword/intent classifier.

## 4. Authority boundaries

| Decision | Owner | A model can… | A model can never… |
|---|---|---|---|
| Is a specialist allowed at all (mode, Edge ON/OFF, explicit selection, resources) | S6 via `route_specialist` | — | influence it |
| Is this request inside a task-class envelope | N2 (deterministic) over RAR/S1/M36 facts and capability metadata | — | assert `simple=true`, confidence or eligibility |
| Which specialist gets this task class | N1 (pinned qualification ranking); G3 preference only among qualified routes | — | promote itself |
| Which registered action, for a direct task | The specialist proposes, N3 validates | propose one offered action | propose an unoffered, unregistered or out-of-envelope action that executes |
| Argument values | RAR/S1 bindings and trusted intake spans | copy a bound value | invent, modify, truncate or default a value that executes |
| Permission, approval, availability | Existing gates and ApprovalGate | — | bypass them |
| Execution, verification, completion status | Canonical execution plus verifier evidence | — | claim success |

## 5. Needle-eligibility: what the existing architecture can and cannot establish

This answers the User's work item 3.

**Can establish deterministically, reusing accepted contracts** (S1A §4 probe):

| Envelope property (User's list) | Mechanism |
|---|---|
| (3) every required argument explicitly supplied or already bound | S1 `BindingState.CONFIRMED` for each reference slot (`rar_clarification_contract.py:30`), or a trusted-intake literal span grounded `RAW_VERBATIM` (`envelope.py:58-84`). Otherwise → canonical CLARIFY. |
| exclude missing/ambiguous arguments, pronouns, earlier-session references | RAR/S1 (no CONFIRMED binding → clarification round) |
| exclude negation, contrast, quoted instructions, correction/recovery wording | M36 `negated()` over the whole turn plus `affirmative_around()` (positive closed allowlist; User decision 2026-09-28) |
| exclude retrieved/attachment content and injection | M33.2 §4.3 `untrusted_content_present`; the turn carries attachment-derived or retrieved text → ineligible |
| exclude send/upload, delete/overwrite, privilege changes | Capability metadata. The envelope shortlist contains only actions with `EffectType.READ_ONLY`, `ApprovalRequirement.NONE`, and `wrong_binding_impact` NONE or RECOVERABLE. |
| exclude unsupported modalities or capabilities | Directory availability plus shortlist (M33.2 §5.1: a `None` shortlist makes the call ineligible) |
| (2) one registered capability | The offered shortlist is non-empty and bounded, and N3 requires exactly one emitted call |

**Cannot establish without a new semantic mechanism:**
- **(1) exactly one requested operation**, and
- **(4)–(8) no composition, generation, interpretation, arithmetic or recovery**, where the wording stays inside the closed affirmative vocabulary.

S1A §4 shows the residual concretely: `Find report.xlsx and read it.`, `Send report.xlsx.` and `Summarize report.xlsx.` all pass every accepted structural gate.

**Why the obvious fixes are not acceptable:**
- **Keywords.** A verb-to-operation table routes by surface form. It creates a second routing authority beside S6 (G2), and it fails on paraphrase in both directions. If it were precise enough to certify the operation, it would also *choose* the tool, which makes Needle redundant for that class.
- **Task-specific Python semantics.** Forbidden by lifecycle Stage 1 ("no new regexes or routing hacks") and by ADR-018's model-centric principle.
- **Model self-confidence.** Needle's confidence is `None` or uncalibrated (M33.2 §9.1; B.3), and neither model abstains reliably (RC-1).
- **A model-generated `simple=true`.** It is the same model judging its own admission, and Stage-1 shows the custom classification was degenerate (S1A §3.3).
- **A universal Needle front door.** Needle would run on every request (the User forbade this), and the gate would rest on the component whose judgement is in question.

**The smallest missing capability** is independent *operation-class evidence*: a signal, not produced by the proposing specialist, that the request asks for exactly one operation of a class the envelope covers. Three ways to supply it are open:

| Option | What it is | Cost | Evidence today |
|---|---|---|---|
| **E-a (recommended default)** | No new mechanism. Admit on the structural envelope above. The specialist may abstain. The in-vocabulary residual is a **measured, qualification-gated** property, contained by read-only/approval-free actions, exact grounding and an action-scoped reply (§9). | None added. Accepts a bounded, measured residual. | Consistent with M33.2 §6 `EXECUTE_PROPOSAL`, where a validated Edge proposal of an offered action executes through the canonical gates with no semantic re-check, exactly as the Brain's action choice is treated. |
| E-b | A reviewed, closed operation-class table over the frozen M36 `AFFIRMATIVE_ACTIONS` vocabulary, plus an exactly-one-action-word rule. Deterministic and fails closed. | This is keyword classification, so it needs the User's explicit acceptance. It probably leaves Needle little to do. | Not tested. |
| E-c | Independent structured evidence from a *different* qualified role (the other specialist or the configured Brain), cross-checked deterministically against the proposal. | A second model call on the direct path | Stage-1 custom classification was poor (Granite 20–24%, degenerate JSON mode). Not supported today. |

This is the one open design decision (D-1, migration plan §7). The rest of this document assumes **E-a**. The pluggable `OperationEvidence` input to N2 (§6 step 4) lets E-b or E-c be added later without changing any other component.

## 6. Routing sequence

Every step is deterministic unless marked.

0. **Edge enabled?** If `EdgeSettings.enabled` is false → no specialist is called (constraint 16). Continue with deterministic mechanisms, then the configured Brain, or return a limitation if the mode forbids it.
1. **Deterministic sufficient?** If an existing URI fast path or deterministic mechanism fully handles the turn (for example the M39 office grammar or an M37 qualified capability) → `DETERMINISTIC`. S6 already returns this first (`deterministic_sufficient`).
2. **Binding.** Run the existing RAR/S1 binding for every reference slot. Any slot `PENDING`, `REJECTED` or `EXPIRED` → **CLARIFY** through the existing clarification path. No specialist is called. Specialists are never asked to recover missing information (constraints 1, 8 and 11).
3. **Task-class candidates.** From `SpecialistProfile`, list the task classes whose structural preconditions (N2) hold for this turn: for example `DIRECT_TOOL_V1`, `EXTRACTION_V1`.
4. **N2 DirectEnvelopeCheck** for `DIRECT_TOOL_V1`: negation false, affirmative context true, all slots CONFIRMED or RAW_VERBATIM, no untrusted content, a bounded non-empty envelope shortlist, and `OperationEvidence` (E-a: always "not supplied"; E-b/E-c later). Result: `edge_sufficient` true or false plus reason codes.
5. **`route_specialist` → S6.** Call `evaluate_intelligence_route` with `role=SUBSTANTIVE` for a direct tool proposal. It executes the user's request, so it is *not* G2 supporting work, and an explicit model selection or `MAIN_BRAIN_PREFERRED` therefore bypasses it. Pass `edge_role_qualified` (from the pinned record for this class and this specialist), `edge_sufficient` (from N2), `edge_warm` and `resource_admitted`. S6 returns `EDGE`, `CAPABLE`, `LIMITATION` or `DETERMINISTIC`.
6. **Specialist selection.** On `EDGE`, take the top-ranked qualified specialist for the task class from N1. The ranking is fixed by the qualification result; S8/G3 may only reorder among qualified specialists.
7. **Invoke** the specialist (model call) with the bounded request (§8). Deadline from the profile.
8. **N3 validation** → `ACCEPTED` or `REJECTED(reason)`.
9. **Accepted** → canonical translate → `evaluate_gates` → approval if required (none in `DIRECT_TOOL_V1`) → `_execute_canonical` through the M33.2 §2.1 seam → execution evidence → RECORD → action-scoped RESPOND (§9). Constraint 12.
10. **Rejected, or timeout/transport error** → N4 checks whether anything was dispatched this turn (never, when rejection happens before step 9). If the next-ranked specialist is qualified for the same task class, and S6 still returns `EDGE`, make **one** replacement call (steps 7–9). Otherwise → S6 with `edge_sufficient=false` → `CAPABLE` in `HYBRID`, or `LIMITATION` in `EDGE_ONLY`.
11. **Granite-class work** (`EXTRACTION_V1`, and later `TRANSFORM_V1` if qualified) follows the same steps with `role=SUPPORTING` when the output is context for the Brain (G2 assistance), or `SUBSTANTIVE` when the output is the user's result. Its output goes through **N5**, never N3, and it is a *candidate* (M33.2 §10), never a tool call.

**Bypass vs rejection.** *Bypass* means the specialist was never called, because of steps 0–5 (reason codes such as `edge_disabled_by_user`, `binding_pending`, `negated_turn`, `non_affirmative_context`, `untrusted_content`, `no_envelope_capability`, `edge_role_unqualified`, `main_brain_bypass`, `resource_limited`). *Rejection* means the specialist was called and N3 or N5 refused its output. Both are recorded, with separate counters.

## 7. Proposal states and rejection reasons (N3)

Closed enum. Every rejection keeps its reason; nothing is repaired or defaulted.

| State / reason | Condition |
|---|---|
| `ACCEPTED` | All checks below pass |
| `REJECT_EMPTY` | No emitted call (including "only suppressed calls") |
| `REJECT_SUPPRESSED_ONLY` | Recorded separately from `REJECT_EMPTY` for Needle telemetry. Suppressed calls are **never promoted** (constraint 7). |
| `REJECT_MULTIPLE_CALLS` | More than one emitted call (constraint 6; RC-5) |
| `REJECT_UNOFFERED` | Tool name not in this turn's envelope shortlist (same check as `tool_call_translator.py:47`) |
| `REJECT_UNREGISTERED` | `tool_name_to_contract_target` returns `None` |
| `REJECT_OUT_OF_ENVELOPE` | Target action not `READ_ONLY` + approval `NONE` + impact NONE/RECOVERABLE, or not declared in the profile's envelope for this task class |
| `REJECT_SCHEMA` | Unknown key, wrong type, or missing required parameter |
| `REJECT_ARGUMENT_UNGROUNDED` | A value is not **byte-equal** to its declared grounding source (below) |
| `REJECT_ARGUMENT_EXTRA` | A value supplied for an optional parameter that has no grounding source this turn (no manufactured defaults, constraint 8) |
| `REJECT_TRANSPORT` / `REJECT_TIMEOUT` / `REJECT_MALFORMED` | Provider failure (M33.2 §11) |

**Per-parameter grounding declarations** live in the SpecialistProfile's envelope entry for each action. They are data. Each parameter declares exactly one grounding kind:
- `BOUND_SOURCE:<slot>`: the value must equal the canonical identifier of the CONFIRMED binding for that slot.
- `LITERAL_SPAN:<slot>`: the value must equal the **entire** trusted-intake span for that slot. A sub-span match is not accepted: `ground()` alone accepts sub-spans, which would let `sales.xlsx` pass inside `Q1 sales.xlsx`.
- `VERBATIM_TURN`: the value must equal the trusted turn text, for legacy `request_text` parameters documented as "the user's original request, verbatim".
- `NONE`: the parameter must be absent.

A parameter without a declaration makes the action ineligible for the envelope. Comparison is exact on the Unicode code points the trusted intake recorded (no case-folding or normalisation), so W06/T06 `café` → `cafe` is rejected.

**Semantic acceptance beyond schema** (constraint 5) therefore means: the call is registered and offered, it is inside the envelope, and every argument is provenance-exact. The operation's *identity* is the E-a residual in §5. It is measured, not asserted.

## 8. What reaches each specialist

Following the M33.2 §4.1 inventory, no more:
- **Direct tool proposal:** `user_text`; the bounded envelope shortlist's `describe()` entries (no full catalogue); for each bound slot, the *bound value* labelled as a slot value (the model copies it; it does not extract it). Never credentials, grants, approvals, other users' data, conversation history beyond the declared excerpt bound, or attachment or retrieved text (that would make the turn ineligible).
- **Extraction:** the source text, delimited and labelled `untrusted_content`, separate from the instruction (fixes RC-7's instruction/data mixing); the closed output schema (N5); the field list. Values are returned as **verbatim source spans**; URI parses numbers and dates from the span.

## 9. Result feedback, follow-up grounding and truthful status

- **Execution result → reasoning.** The canonical RECORD step writes the result into Turn State: attempt history, grounded entities, and the S11 result version where the capability produces one. The next turn's reasoning therefore sees it, whether that is the Brain, a specialist or deterministic code. Constraint 12.
- **Re-entry.** If execution returns an error, partial or unavailable status, the turn re-enters through S6 with `edge_sufficient=false`. The Brain receives the attempt and its evidence (`HYBRID`/`MAIN_BRAIN_PREFERRED`), or the user receives the limitation (`EDGE_ONLY`). A specialist never interprets a failure (no recovery reasoning).
- **Action-scoped reply.** A reply from the specialist path states only the action that ran and its real result: for example "Located `report.xlsx` in `<root>`", using the deterministic template path allowed by G1. It never says "done" about the *request*. This caps the E-a residual (a request that also asked for something else) at an honest partial answer, never a false completion.
- **Follow-up grounding.** Results carry source ids and hashes (M36 SourceRegistry, S11 ledger), so "open it again" binds through RAR/S1 like any other reference.

## 10. Side effects, interruption and resume

- `DIRECT_TOOL_V1` is limited to read-only, approval-free actions. It has no external side effects by construction (N3 `REJECT_OUT_OF_ENVELOPE`).
- **N4 SpecialistAttemptLedger** (per user, per turn, append-only): `turn_id`, `stage`, `specialist_id`, `proposal_sha256`, `validator_state`, `dispatch_receipt` (canonical execution id or null). **Rule:** once a dispatch receipt exists for a turn, no fallback stage may dispatch; any fallback is limited to Brain *reasoning over the recorded result*. This covers the read-only exemption in `executed_signatures`.
- **Resume after interruption.** On restart the ledger is read. A turn with a dispatch receipt resumes from RECORD/RESPOND and never re-dispatches. A turn without one restarts from routing. Approval-gated work (later classes only) keeps using ApprovalStore single-use consumption and workflow step status; `complete_step_externally` (`workflow_executor.py:30`) already refuses double completion.

## 11. Configuration behaviour

| Setting | Behaviour |
|---|---|
| Edge OFF (`enabled=false`) | Both specialists bypassed. Deterministic mechanisms stay on. The Brain is available unless the mode forbids it (G2). |
| `EDGE_ONLY` | Deterministic, then qualified specialists only. Outside every envelope, or after a rejection with no qualified replacement → `LIMITATION` (S6 `_edge_only_guard`, `routing_policy.py:47`). **Never** a silent Brain or cloud call (constraint 15). |
| `HYBRID` | Efficiency-first: specialist when S6 returns `EDGE`, otherwise the Brain. |
| `MAIN_BRAIN_PREFERRED` | Direct tool proposals (SUBSTANTIVE) go to the Brain when one is available. Specialists do SUPPORTING work only (for example extraction assistance), and substantive work only when the Brain is unavailable (S6). |
| Explicit model selected | That model is the Capable Brain for substantive work (G2). Specialists are limited to SUPPORTING work. |
| Profile missing or record digest mismatch | `edge_role_qualified=false` → bypass (unknown is ineligible, M33.2 §3). |

## 12. Failures and timeouts

These reuse M33.2 §11. Specialist-specific rules:
- Per-class deadline declared in the profile. On timeout the call is cancelled and never reused.
- A transport error, including encoding errors (RC-9), is `REJECT_TRANSPORT` → step 10.
- Retry storms are prevented: at most one replacement call per turn per task class.
- Runtime not ready → `SUPPRESS` with the S6 status code.
- Resource governor refusal → `resource_limited`.

## 13. Telemetry (content-free)

Follows M33.2 §9.2 (`UsageMeter` layout, user-scoped, month-partitioned, retention window) and the S7 event conventions. One event per specialist stage:
- `trace_id`, `turn_id` (opaque), `profile_id`, `task_class`, `specialist_id`, `model_id`, `artifact_sha256`, `placement` (cpu/gpu), `route` (S6 target plus reason codes)
- `bypass_reason` or `validator_state`, `rejection_reason`, `replacement_index` (0/1)
- `latency_ms` (model call only; separately queue, validation and execution), `cold_load_ms`, `rss_bytes` or `vram_bytes` where observable, else `UNAVAILABLE`
- `dispatch_receipt_present`, `execution_status`, `verification_status`, `final_route`

No prompt text, argument values, file names or document text are recorded. Argument checks are logged as outcome codes only.

## 14. Isolation

- Profiles and records are deployment-owned and read-only to users and models.
- Settings are per user (`user_scoped_path`). The ledger and telemetry are per user.
- The runtime lease pool is per process (M33.2 §10). Specialist conversation state is reset between requests (Stage-1 reset Needle history per case), so no user's text can reach another user's request.

## 15. Replaceability

Every specialist is an `EdgeIntelligenceProvider` implementation named in a profile. Replacing Needle or Granite means a new adapter plus a new pinned qualification record. The routing, validators, ledger and gates do not change. An empty ranking for a task class is a valid profile: the class is simply never routed to a specialist.

## 16. The User's 16 proposal-semantics constraints

| # | Constraint | Where satisfied |
|---|---|---|
| 1 | Resolve missing, stale or ambiguous arguments through canonical binding/clarification | §6 step 2 |
| 2 | Invoke Needle only after eligibility is established | §6 steps 3–5 (N2 + S6 + pinned record) |
| 3 | Otherwise bypass to Granite or the Brain | §6 steps 5, 10, 11 |
| 4 | Exactly one registered call with exact grounded arguments | N3 (§7) |
| 5 | Schema validity is not semantic acceptance | §7 grounding declarations; §5 residual measured |
| 6 | Empty, suppressed, multiple, invented/modified, mismatched, unregistered or transport-failed output cannot execute | §7 reasons |
| 7 | Never promote `suppressed_calls` | `REJECT_SUPPRESSED_ONLY` |
| 8 | Never manufacture defaults | `REJECT_ARGUMENT_EXTRA`, `REJECT_ARGUMENT_UNGROUNDED` |
| 9 | Preserve explicit rejection reasons | §7 closed enum; §13 |
| 10 | Granite only inside its separately qualified envelope | N1 pinned record per class; §6 step 10 |
| 11 | Do not force Granite to recover missing information | §6 step 2 precedes every specialist call |
| 12 | One canonical validate → authorize/approve → execute → verify → feedback path | §6 step 9; §9 |
| 13 | Fallback and resume never repeat a completed side effect | N4 (§10) |
| 14 | Preserve Edge-off, `EDGE_ONLY`, provider choice, isolation, timeouts, failures | §11, §12, §14 |
| 15 | `EDGE_ONLY` never silently substitutes a capable/cloud provider | S6 guard (§11) |
| 16 | Edge-off bypasses both specialists | §6 step 0 |

## 17. Proposed envelopes (hypotheses to qualify)

These are *candidate* task classes. Which specialist, if any, owns each one is decided by measurement (qualification plan §4–§6).

- **`DIRECT_TOOL_V1`.** One offered read-only, approval-free registered action. All parameters declared with a grounding kind and satisfied by CONFIRMED bindings, whole trusted spans or the verbatim turn. Affirmative, non-negated turn. No untrusted content. Candidate registered actions (from `uri_workspace/capabilities_registry.json` and Gmail):
  - zero-argument lookups: `system_performance`, `recall_memory`, `read_attached_file` (attachment bound as current), Gmail `list_labels`;
  - bound-identifier reads: Gmail `read_message(message_id)` and `read_thread(thread_id)`, with the id bound from session context;
  - literal-identifier lookups: `fetch_drive_spreadsheet(spreadsheet_id)` and `extract_student_records(roll_number)`, taking a whole trusted span.

  **There is no registered "locate/read a local file by name" action today** (S1A RC-10). Adding one is a separate capability under its own lifecycle and is not part of this design.
  Initial hypothesis: Needle and Granite are **both** candidates.
- **`EXTRACTION_V1`.** Closed-schema extraction of explicitly present fields from supplied untrusted text, as verbatim spans with explicit `ABSENT`. Output is a candidate only. Monetary values are shown with their source span and never used in a consequential action without confirmation (D1 impact rules). Initial hypothesis: Granite (JSON mode) and Needle are **both** candidates.
- **`TRANSFORM_V1`** (short transformations and drafts). **Not in the initial scope.** It would be separately qualified later, and drafting quality has no deterministic oracle (Batch A L-8).

## 18. The 10 canonical-loop invariants

1. **Discovery:** through SpecialistProfile plus the directory projection.
2. **How the Brain knows it is available:** it does not need to. Specialists are routed by S6 before or instead of the Brain, and the Brain's discovery is unchanged.
3. **When to use it:** N2 plus S6 plus the pinned per-class ranking.
4. **Action contract:** registered action schemas plus the profile's grounding declarations.
5. **Runtime state:** Turn State, bindings, trusted intake, settings, inventory, profile, ledger.
6. **Permissions and approvals:** the existing gates. The initial direct envelope is read-only and approval-free.
7. **Execution:** the M33.2 §2.1 seam into `_execute_canonical`.
8. **Result to reasoning:** RECORD into Turn State; re-entry on failure (§9).
9. **Follow-up grounding:** result source ids and hashes, via RAR/S1.
10. **End-to-end test:** qualification plan §8 (live canonical path).

## 19. Stage-2 lifecycle questions

1. §2. 2. §18 invariant 2. 3. Turn State, bindings, trusted intake, settings (§3). 4. Registered actions only; no new actions. 5. Canonical execution envelopes plus the ledger record. 6. Existing gates; read-only initial envelope. 7. Results through M36 sources and S11; no Graphify writes. 8. Session state and S11; nothing durable beyond existing stores. 9. No. The bounded shortlist is progressive by construction. 10. Yes: specialist → Brain via S6 (§6 step 10). 11. M33.2 owns routing and contracts. Canonical execution owns execution. RAR/S1 owns binding. 12. Reuse per §3.1. The experimental ensemble adapter is benchmark-only. The Stage-1 runners stay experimental. Nothing is retired.

## 20. Traceability (lifecycle §5)

| Decision | Stage-1 finding |
|---|---|
| Eligibility is never model-produced (N2) | RC-1 |
| Exact per-parameter grounding (N3) | RC-2; T05, T06, T12, T13, W04–W06 |
| Reuse the M36 negation/affirmative gates | RC-3; S1A §4 |
| Envelope limited to read-only, approval-free actions; action-scoped reply; E-a residual measured | RC-4; T17–T20; X1–X3 |
| Exactly one call | RC-5; T09, T10, T16 |
| Never promote suppressed calls | RC-6; T11, T15 |
| Closed extraction schemas, spans, `ABSENT`, URI numeric parsing | RC-7; W02, W04–W06, W09–W11, W13, W14 |
| Extraction output is a candidate; confirmation for consequential values | RC-8; W12 |
| Explicit UTF-8 adapter contract | RC-9; W03 |
| Qualification on registered actions only | RC-10 |
| Placement recorded and matched | RC-11 |
| SpecialistProfile plus projection routing | RC-12 |
| Per-class assignment by measurement | User principle 10:48; Stage-1 Granite > Needle on direct |

## 21. Not in this design

Implementation; live wiring (S13/INT-gated, PR-only); any change to frozen M33.2/M33.3/M36/M37/M38 files; new registered capabilities; `TRANSFORM_V1`; E-b or E-c; qualifying either model; any governance-state change.

## 22. Self-review against §0

- **B-1** Pass (§20). **B-2** Pass (§3; each new item names its gap). **B-3** Pass (N6 is a projection like `route_clarification_wording`). **B-4** Pass (§4). **B-5** Pass (§15; an empty ranking is valid). **B-6** Pass (§16). **B-7** Pass (§1, §17: both models are candidates for both classes). **B-8** Pass (§18, §19). **B-9** Pass (§5, with options).

Gaps found in the first draft and repaired:
1. The draft classified a direct tool proposal as G2 SUPPORTING work. That would let a specialist *execute the user's request* even when the user explicitly selected a model or chose `MAIN_BRAIN_PREFERRED`, which contradicts G2 ("Edge must not replace or downgrade that substantive role"). It is now SUBSTANTIVE (§6 step 5, §11).
2. The draft used M36 `ground()` directly as the argument check. `ground()` accepts a sub-span of the intake span, so a truncated filename could still ground. N3 now requires equality with the *whole* span or the bound value (§7).
3. The draft assigned `DIRECT_TOOL_V1` to Needle and `EXTRACTION_V1` to Granite. That assumed roles from intended purpose, which the User ruled out at 10:48. Both are now candidates for both classes, and assignment comes from measurement.
4. The draft allowed a fallback after a read-only dispatch "because read-only is idempotent". A second read after a failed first read can still duplicate cost and audit entries, and `executed_signatures` exempts read-only calls. N4 now forbids any second dispatch in a turn on the specialist path.
