# Harness-First Edge: Architecture Map (H1)

- **Status:** PROVISIONAL. Experimental design for qualification, not an accepted architecture and not wired into the live app.
- **Date:** 2026-10-01. **Author:** Claude (thread "Harness-first Edge track").
- **Branch:** `claude/project-thread-sqk105` on `sche004-cyber/Uri`, forked from `c17f593` (EPQ-1 harness freeze, itself on the Edge pair plan r2 `63557a6`, itself on the M36-M38 freeze `5bbf738`).
- **Inputs read:** readiness audit 2026-09-30 (README, Reports A-E), Edge specialist pair architecture r2, root-cause audit, qualification and migration plans, the two independent reviews, EPQ-1 pre-registration, setup report and interim report 1, the uncommitted `uri-agent` working tree (now preserved), and the source files cited below.

## 0. Acceptance criteria for this map

| ID | Criterion |
|---|---|
| H1-1 | Every pipeline stage names the existing URI component it reuses, with a file reference, or is marked NEW with the gap it fills. |
| H1-2 | One routing authority (S6). No stage chooses between Edge and Main Brain except S6. |
| H1-3 | RAR, S1 and ARN.1 keep their frozen authority. No model produces candidate IDs, bindings or a clarification bypass. |
| H1-4 | The Edge model receives only the bounded residue for its job, never the whole request plus raw context by default. |
| H1-5 | Every place where the experiment uses a test double or a fixture is labelled. |
| H1-6 | Claims about what works today are tied to source or a run; inferences are marked. |

## 1. What the current running app does with a turn (observed in source)

`uri-agent` working tree, preserved as `preserve/running-app-2026-10-01` (`869fae5`).

```text
POST /ask (server.py:1860)
  -> _edge_route_for_ask (server.py:1729)   Needle pre-route, ON by default (EdgeSettings.enabled=True,
                                            settings.py:28-30); runs BEFORE approval resumption
  -> approval resumption (M32.1)            deterministic yes/no for a pending action
  -> lifecycle intent seam (M33.1)          deterministic grammar, default off (env flag)
  -> orchestrator / canonical execution     semantic interpreter (model call) ->
                                            conversational classifier gate (needs the model's
                                            8-key result, conversational_classifier.py:150) ->
                                            decision engine (model) -> gates -> execute ->
                                            narrative drafting (model call)
```

**Why "hello" is slow (inference from source, latency measured in H3):** `is_conversational_no_capability_required` already recognises a bare greeting deterministically, but only after the semantic interpreter (a Main Brain call) has produced its structured result, and the fixed reply is then optionally paraphrased by narrative drafting (a second Main Brain call). The deterministic knowledge exists; it sits behind two model calls.

The Needle pre-route has its own literal greeting list (`{"hello","hi",...}`, server.py) that bypasses Needle but still sends the turn to the Main Brain.

## 2. Target flow and where each stage comes from

```text
USER turn (trusted text) + session context (attachments, pointers, pending approvals)
  |
  1. Intake + surface frame ............ uri_v1/turn/turn_frame_builder.py  (REUSED, frozen, no semantics)
  2. Pending-approval resumption ....... uri_core/core/approval_resumption.py classify_confirmation  (REUSED)
  3. Conversational fast path .......... uri_core/core/conversational_classifier.py whole-message patterns (REUSED)
                                         without the model gate; reply = deterministic template (G1 / composable Brain)
  4. Lifecycle grammar ................. uri_core/core/lifecycle_intent_interpreter.py interpret (REUSED)
  5. Negation gate ..................... uri_v1/memory/contracts.py negated (REUSED, frozen M36)
  6. Reference resolution (RAR) ........ uri_v1/turn/rar_deterministic.py (REUSED, frozen, anchor-pinned)
  7. Binding / clarification (S1) ...... uri_v1/reference_clarification/builder.py build_clarification,
                                         template_renderer.py (REUSED, frozen). CLARIFY options carry canonical IDs.
  8. Capability discovery .............. offered/feasible set from CapabilityDirectory (REUSED);
                                         capability_relevance.plausible_matches recorded as a diagnostic only (see §4)
  9. Structural admission .............. NEW (experimental): untrusted content present, multi-action surface
                                         (TurnFrame), negation -> task_complex / edge_sufficient=false
 10. Edge job (bounded residue) ........ NEW adapter over EPQ-1 transports (Needle bridge, Ollama Granite JSON)
                                         Jobs: SELECT_ACTION among the offered set; EXTRACT (closed schema);
                                         LABEL (closed enum). Model output = a choice or spans, never an ID it invents.
 11. Routing decision .................. uri_core/core/edge/routing_policy.py evaluate_intelligence_route (S6, REUSED,
                                         the only router). Inputs come from steps 2-10.
 12. Validation ........................ NEW validator (closed set, one choice, URI fills arguments from bindings or
                                         whole verbatim spans) + real tool_call_translator.translate_tool_calls +
                                         real decision_gates.evaluate_gates (REUSED)
 13. Execution / verification .......... real SystemPerformanceTool; every other action is a TEST DOUBLE in the
                                         experiment; approval-required actions are HELD, never executed
 14. Main Brain escalation ............. EPQ-1 Ollama adapter, local qwen3.5:9b (no metered spend); receives the
                                         prepared problem (bindings, offered set) and passes the same validation
```

## 3. Reused versus new

| Function | Component | Status |
|---|---|---|
| Surface frame (clauses, action verbs, references, negation spans) | `uri_v1/turn/turn_frame_builder.py` | Reused, frozen |
| Approval yes/no | `approval_resumption.classify_confirmation` | Reused |
| Greeting / thanks / farewell / self-question | `conversational_classifier` patterns | Reused (pattern part only) |
| Lifecycle commands | `lifecycle_intent_interpreter.interpret` | Reused |
| Negation | M36 `negated` | Reused, frozen |
| Reference resolution | RAR `resolve_rar_deterministic_extended` | Reused, frozen |
| Binding state, clarification round, option IDs, wording | S1 `build_clarification`, `render_template`, `presented_options` | Reused, frozen |
| Routing authority | S6 `evaluate_intelligence_route` | Reused |
| Tool translation and gates | `translate_tool_calls`, `evaluate_gates`, `CapabilityDirectory` | Reused |
| Model transports | EPQ-1 `NeedleAdapter`, `OllamaAdapter` (`c17f593`) | Reused (experiment code) |
| Session-context to RAR candidate adapter | `experiments/harness_first/pipeline.py` | **New seam** |
| Structural admission (edge_sufficient / task_complex producers) | same | **New seam**, experimental |
| Bounded Edge job prompts and validator | same | **New seam** |
| Completion-class scorer and latency recorder | `score.py` | **New**, experiment only |

## 4. Findings that shaped the design

1. **No deterministic text-to-capability mapping exists in URI, and the nearest mechanism is not safe to use as one.** Probe on the real directory (this thread, 2026-10-01): `plausible_matches("How much RAM is this computer using?")` returns `convert_document`; `"Read the attached file report.pdf."` returns `system_performance`; `"Search my Gmail for the NAAC circular"` returns nothing. M30.5A built it as a conservative unsupported-gate signal, not a selector. Building a keyword table would be a second router (Edge pair r2 §5.3, E-b) and needs the User's acceptance. So **choosing an action from free text is the semantic residue**, and it is the first Edge job measured. HARNESS_COMPLETE for capability actions is limited to cases where structure already decides (pending approval, lifecycle grammar, conversational turns).
2. **What the harness can take off the model is binding, clarification, negation, untrusted-content and multi-action admission.** EPQ-1 development results show these are exactly the isolated models' weakest families (AMBIGUITY 0-4/22, MULTISTEP 0-1/25, NEGATION 6-13/17), while action choice among offered tools is their strongest (ARGS 18-22/24).
3. **Arguments are filled by URI.** Following Edge pair r2 §7, the model chooses; URI fills identifier arguments from a CONFIRMED binding or a whole verbatim span. A value that cannot be filled this way is not executed.
4. **Extraction and labels have no live producer yet (X-P1).** The corpus supplies the closed schema; this is labelled in every record.

## 5. Completion classes (scored per turn)

| Class | Meaning |
|---|---|
| HARNESS_COMPLETE | No model call. Deterministic stages decided and, where applicable, executed. |
| HARNESS_PLUS_EDGE | Harness did binding/admission; one Edge job filled the residue; validator accepted. |
| HARNESS_PLUS_MAIN | Residue exceeded the admitted Edge envelope (or Edge was rejected) and went to the local Main Brain. |
| CLARIFY | S1 clarification (from RAR) or a validated model clarification request. |
| SAFE_FAILURE | Nothing executed and no success claimed. |

Critical gates: false success = 0, unauthorised execution = 0, invented binding/candidate = 0, bypassed clarification = 0.

## 6. Test doubles and fixtures (H1-5)

- Session context (attachments, last pointers, pending approvals) is a corpus fixture, not a live session store.
- Execution: `system_performance` runs for real; every other read-only action is a test double; approval-required actions are held.
- `EdgeRuntimeInventory` readiness is supplied by a stub that reports the configured Edge model ready (the real inventory reads per-user install state).
- Extraction and label schemas are supplied by the corpus (X-P1 absent).

## 7. What this map does not decide

Permanent Edge roles, live wiring into `/ask`, any change to frozen RAR/S1/M36/M37/M38 files, and any keyword routing table.
