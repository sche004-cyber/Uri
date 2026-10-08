# M35 URIv1 — Test Relevance & Regression Manifest

**Batch:** A2.8 / A2.8A Pre-Execution  
**Status:** ARCHITECTURE HYPOTHESIS — NOT FROZEN; BEING DECOMPOSED AND EMPIRICALLY VALIDATED THROUGH A2.8A+  
**Target Repository:** `C:\Users\cheta\Development\Uri\_V1`  
**Branch:** `m35-uri-v1-parallel-architecture`  
**Baseline HEAD:** `e8e3b65259c45fc823addc3ef8969425a265bd1b`  
**Protected Prototype:** `C:\Users\cheta\Development\uri-agent` (Strictly READ-ONLY, untouched)

---

## 1. Governing Testing Principles

### Core Principle
> **"Tests serve URI's contracts. URI's architecture does not exist to serve historical tests."**

URI's architecture has evolved substantially during M35—progressing from initial monolithic single-pass Gemma ("Needle") decoding, through progressive scaffolding, deterministic Reference Anchor Resolution (RAR), multi-slot concurrent narrow feeds, resident Main-Brain qualification, to the model-independent Adaptive Intelligence Architecture (A2.8).

Consequently:
**AN EXISTING TEST IS NOT AUTOMATICALLY A VALID REGRESSION TEST.**

Before treating any existing test failure as an architectural regression, URI engineers and agents must validate that the test still protects an **ACTIVE** architectural contract.

### Test Intent Outranks Test Implementation
The permanent requirement is to protect the underlying safety, correctness, or authority invariant, not an accidental or obsolete implementation detail.
- *Example:* If an older test asserted `send in prohibited_operations`, the permanent invariant is: **URI must preserve the user's negative constraint and must never interpret SEND as immediately authorized.** Whether that is represented as a string in a tuple or as a bound operation structure is an implementation detail that must follow approved contracts.

### Permanent Harness Principle
> **"URI should hard-code control semantics, authority and deterministic system invariants — not human-language replies or an ever-growing catalogue of semantic interpretations."**

URI deterministically owns:
- authority, permissions, and approval requirements
- canonical state machines and execution lifecycle
- capability contracts and safe boundaries
- evidence provenance and validation
- deterministic reference anchor resolution (RAR)
- deterministic feed merge and routing enforcement

URI must **NOT** accumulate:
- canned natural-language replies
- phrase-to-semantic-answer mappings
- hard-coded semantic interpretations disguised as application code
- model reasoning encoded as brittle Python conditionals

RAR and ARN exist to make cognitive work easier and narrower for models, not to quietly become replacement language models written as Python heuristics.

### Hard Rule: No Silent Test Weakening
1. Never delete a test merely because it fails.
2. Never loosen assertions merely to turn a test green.
3. Never exclude a test solely because a new implementation fails it.
4. Any regression-gate removal, reclassification, or rewrite must explicitly trace to an approved architectural contract change or documented empirical finding.

---

## 2. Seven-Question Test Investigation Framework

For every failing, disputed, or legacy test, the following seven questions must be answered:
1. **What original requirement did this test protect?**
2. **Does that requirement still exist?**
3. **Has the requirement changed?**
4. **Is only the expected representation obsolete?**
5. **Was the test model-specific?**
6. **Was the test architecture-specific?**
7. **Does removing it create an actual coverage gap?**

Based on these answers, every test is assigned one of four formal classifications:
- `CURRENT_REGRESSION`: Protects an active, mandatory contract. Must remain a gating regression test.
- `SUPERSEDED`: Protects behavior URI has intentionally discarded or replaced. Must not gate new architecture.
- `REWRITE_REQUIRED`: Protects a requirement that remains valid, but its syntactic assertion or schema format is obsolete. Must be updated to match current contracts.
- `HISTORICAL_QUALIFICATION`: Built specifically to qualify or probe a historical model or closed experiment. Retained for empirical provenance, but non-gating for core URI development.

---

## 3. Architecture Version Awareness Mapping

| Architectural Stage | Milestone / Batch | Core Mechanism Introduced | Status / Contract State |
| :--- | :--- | :--- | :--- |
| **Stage 0: Skeleton** | M35 A0 | Pipeline interfaces, ContextPack, EdgeOutcome | Active / Frozen Baseline |
| **Stage 1: Contract** | M35 A1 / A1.1 | DecodedRequest, immutability, serialization | Active / Frozen Contract |
| **Stage 2: Monolithic Probe**| M35 A2.0 – A2.4R | Monolithic 4-bit Gemma ("Needle"), Qwen-7B, Qwen-14B | Closed Historical Probes |
| **Stage 3: Pre-Semantics** | M35 A2.3 | Deterministic TurnFrame & ActiveContext | Active / Frozen Preprocessor |
| **Stage 4: Deterministic RAR**| M35 A2.5 (1–4B) | Deterministic Reference Anchor Resolution & Invariants | Active / Frozen Core |
| **Stage 5: Parallel Feeds** | M35 A2.5 (Stg 4) | Adaptive Semantic Feed Planner & Deterministic Merger | Active / Frozen Merger |
| **Stage 6: Resident Brain** | M35 A2.7 | Resident 9B Dual-Role, Torture Set, Mode D Scaling | **Empirical Finding Qualified** (Resident topology qualified; Qwen3.5-9B is first qualified provider) |
| **Stage 7: Adaptive Intel** | M35 A2.8 | BrainProfile, ARN Contract, Lifecycle States | **ARCHITECTURE HYPOTHESIS — NOT FROZEN** (Decomposing in A2.8A+) |
| **Stage 8: ARN Core** | M35 A2.8A | Uncertainty Discovery, Question Framing & Validation | **Active Current Focus** |

### Clarification on A2.8 Non-Frozen Elements
A2.8 introduced valuable architectural hypotheses, but the following are **explicitly NOT frozen**:
- Complete ARN contract
- BrainProfile schema and dimension weighting
- Local Brain boundary definitions
- Exact `OperationLifecycle` representation
- Fixed semantic complexity thresholds
- Graphify integration ordering
- Context Compiler integration ordering
- Final resolver-selection architecture

These hypotheses are to be decomposed and empirically tested starting in Batch A2.8A.

### Clarification on A2.7 Resident Brain Status
The precise architectural status for Batch A2.7 is:
> **"The Resident-Main-Brain topology is qualified. Qwen3.5-9B Q4_K_M is the first empirically qualified provider for that topology."**

This must **NOT** be converted into an architectural decree that *"Qwen3.5-9B is URI Step-1"* or that every future deployment must run a 9B model. Models remain replaceable cognitive providers.

---

## 4. Comprehensive Test Relevance Manifest

### File-Level and Test-Level Classifications

| Test Suite / File | Individual Test / Focus | Classification | Traceable Rationale & Action |
| :--- | :--- | :--- | :--- |
| **`test_m35_uriv1_a0_skeleton.py`** | Full file (8 tests) | `CURRENT_REGRESSION` | Protects baseline pipeline types (`ContextPack`, `EdgeOutcome`). Mandatory gate. |
| **`test_m35_uriv1_a1_decoded_request.py`** | Full file (12 tests) | `CURRENT_REGRESSION` | Protects `DecodedRequest` fields, defaults, immutability. Mandatory gate. |
| **`test_m35_uriv1_a1_1_contract_hardening.py`** | Full file (11 tests) | `CURRENT_REGRESSION` | Protects deep immutability, serialization, and defensive copying. Mandatory gate. |
| **`tests/test_m35_uriv1_a2_3_turn_frame.py`** | Full file (8 tests) | `CURRENT_REGRESSION` | Protects deterministic syntactic extraction (actions, references, negations). Mandatory gate. |
| **`tests/test_m35_uriv1_a2_3_semantic_envelope.py`**| Full file (2 tests) | `CURRENT_REGRESSION` | Protects `ActiveContext` working memory bounding. Mandatory gate. |
| **`test_m35_uriv1_a2_5_rar_contracts.py`** | Full file (28 tests) | `CURRENT_REGRESSION` | Protects RAR tri-state outcomes and candidate anti-invention validator. Mandatory gate. |
| **`test_m35_uriv1_a2_5_deterministic_rar.py`** | Full file (21 tests) | `CURRENT_REGRESSION` | Protects 100% deterministic reference anchor resolution rules. Mandatory gate. |
| **`test_m35_uriv1_a2_5_rar_adversarial_safety.py`**| Full file (11 tests) | `CURRENT_REGRESSION` | Protects RAR against prompt injection, spoofing, and invented IDs. Mandatory gate. |
| **`test_m35_uriv1_a2_5_rar_stage4_refinements.py`**| Full file (29 tests) | `CURRENT_REGRESSION` | Protects RC1–RC4 precision rules and candidate reorder invariance. Mandatory gate. |
| **`test_m35_uriv1_a2_5_candidate_invention_fix.py`**| Full file (3 tests) | `CURRENT_REGRESSION` | Protects anti-invention boundary in reference resolution. Mandatory gate. |
| **`test_m35_uriv1_a2_5_stage4_feeds.py`** | Full file (13 tests) | `CURRENT_REGRESSION` | Protects adaptive feed planning and deterministic merger contradiction detection. Mandatory gate. |
| **`test_m35_uriv1_a2_6_qwen_feeds.py`** | `test_qwen_feed_prompts_contain_no_contaminating_examples` | `CURRENT_REGRESSION` | Model-independent prompt hygiene invariant (no leaked examples). Mandatory gate. |
| | `test_qwen_planner_activates_expected_feeds` | `CURRENT_REGRESSION` | Protects structural feed planning on TurnFrame action/negation cues. Mandatory gate. |
| | `test_qwen_merger_combines_narrow_feed_outputs` | `CURRENT_REGRESSION` | Protects deterministic merger aggregation without hallucination. Mandatory gate. |
| | `test_qwen_merger_contradiction_safety` | `CURRENT_REGRESSION` | Protects safety invariant: drop conflicting verbs from requested operations. Mandatory gate. |
| **`test_m35_uriv1_a2_7_resident_feeds.py`** | `test_semantic_torture_battery_loaded` | `HISTORICAL_QUALIFICATION` | Validates test fixture loader for A2.7 diagnostic battery. Non-gating for runtime URI. |
| | `test_contrastive_negation_scoring_positive` | `HISTORICAL_QUALIFICATION` | Verifies evaluation harness scoring math used in A2.7 report. Non-gating for runtime URI. |
| | `test_contrastive_negation_scoring_detects_omission`| `HISTORICAL_QUALIFICATION` | Verifies evaluation harness scoring math used in A2.7 report. Non-gating for runtime URI. |
| **`test_m35_uriv1_a2_needle_decoder.py`** | Monolithic wire tests (10 assertions) | `SUPERSEDED` | Traced below. Replaced by orthogonal narrow feeds in A2.5/A2.6. Non-gating. |
| | Schema hygiene & boundary tests (12 tests) | `HISTORICAL_QUALIFICATION` | Historical wire isolation assertions for Gemma-4B. Non-gating. |
| **`test_m35_uriv1_a2_needle_live.py`** | Full file (4 tests) | `HISTORICAL_QUALIFICATION` | Needle subprocess bridge tests. Needle is deactivated. Non-gating. |
| **`test_m35_uriv1_a2_1_needle_narrow.py`** | Full file (1 test) | `HISTORICAL_QUALIFICATION` | Historical probe of Needle candidate narrowing. Non-gating. |
| **`test_m35_uriv1_a2_1_needle_narrow_live.py`** | Full file (1 test) | `HISTORICAL_QUALIFICATION` | Live Needle narrow probe. Non-gating. |
| **`test_m35_uriv1_a2_2_qwen_decoder.py`** | Full file (11 tests) | `HISTORICAL_QUALIFICATION` | Historical monolithic decoder on Qwen-7B. Replaced by multi-feed. Non-gating. |
| **`test_m35_uriv1_a2_2_qwen_live.py`** | Full file (2 tests) | `HISTORICAL_QUALIFICATION` | Live Qwen-7B probe. Non-gating. |
| **`tests/test_m35_uriv1_a2_3_scaffolded_needle.py`**| Full file (5 tests) | `HISTORICAL_QUALIFICATION` | Proved Needle failed even with scaffolding. Closed experiment. Non-gating. |
| **`test_m35_uriv1_a2_3_scaffolded_needle_live.py`** | Full file (2 tests) | `HISTORICAL_QUALIFICATION` | Live scaffolded Needle probe. Closed experiment. Non-gating. |
| **`test_m35_uriv1_a2_4_qwen14b_decoder.py`** | Full file (10 tests) | `HISTORICAL_QUALIFICATION` | Control benchmark on 14B model. Closed experiment. Non-gating. |
| **`test_m35_uriv1_a2_4_qwen14b_live.py`** | Full file (1 test) | `HISTORICAL_QUALIFICATION` | Live 14B control probe. Non-gating. |
| **`test_m35_uriv1_a2_4r_needle_single_pass.py`**| Full file (5 tests) | `HISTORICAL_QUALIFICATION` | Historical A2.4R Needle probe. Non-gating. |
| **`test_m35_uriv1_a2_4r_needle_live.py`** | Full file (1 test) | `HISTORICAL_QUALIFICATION` | Live A2.4R Needle probe. Non-gating. |
| **`test_m35_uriv1_a2_5_lfm_decoder.py`** | Full file (8 tests) | `HISTORICAL_QUALIFICATION` | Stage 3 probe on LFM2.5-350M. LFM disqualified in Stage 4. Non-gating. |
| **`scratch/test_m35_a2_9_native_trace.py`** | Full file (36 tests) | `HISTORICAL_QUALIFICATION` | Deterministic-environment/scoring self-tests for the A2.9 Native Problem-Solving Trace pilot (Qwen3.5-9B closed-loop probe). Asserts no new mandatory architectural contract. Non-gating. |

---

## 5. Traceable Log of the 10 Superseded Monolithic Wire Assertions

The following 10 assertions inside `test_m35_uriv1_a2_needle_decoder.py` protect the obsolete monolithic single-pass `needle_wire.py` schema (`WIRE_SCHEMA` and `normalize_wire`). They are formally classified as `SUPERSEDED` and removed from active regression gating:

| Assertion / Test Name | Original Purpose | Why Representation Is Obsolete | Current Active Coverage | Classification |
| :--- | :--- | :--- | :--- | :--- |
| `test_minimal_valid_wire` | Assert minimal wire dict maps `goal` to `DecodedRequest` | Monolithic dictionary input replaced by narrow Feed G (`FeedGOutput`) | `test_qwen_merger_combines_narrow_feed_outputs` | `SUPERSEDED` |
| `test_full_wire_maps_every_field` | Assert single dict contains all 9 semantic dimensions | Monolithic single-pass output abandoned; feeds are orthogonal | `test_deterministic_merge_full_stack` in `a2_5_stage4_feeds.py` | `SUPERSEDED` |
| `test_unresolved_reference_produces_context_dependency` | Assert wire references create dependencies | References are now resolved via RAR, not monolithic wire parsing | `test_omitted_feed_handling_and_fallback_binding` | `SUPERSEDED` |
| `test_missing_goal_raises_missing_required_structure` | Assert wire raises if `goal` key missing from root dict | Feed G failure falls back to TurnFrame/Feed O in merger | `test_omitted_feed_handling_and_fallback_binding` | `SUPERSEDED` |
| `test_empty_goal_string_raises` | Assert wire raises on whitespace goal string | Merger normalizes whitespace or falls back gracefully | `test_omitted_feed_handling_and_fallback_binding` | `SUPERSEDED` |
| `test_non_dict_wire_raises_malformed_output` | Assert normalizer rejects non-dict payload | Multi-feed outputs are strongly typed dataclasses (`FeedXOutput`) | Dataclass constructor type safety | `SUPERSEDED` |
| `test_operation_requested_and_prohibited_contradiction_raises` | Assert wire raises exception on conflicting verb status | Merger resolves contradiction safely or escalates; does not crash | `test_contradiction_detection_safety` in `a2_5_stage4_feeds.py` | `SUPERSEDED` |
| `test_reference_claiming_resolved_is_context_invention` | Assert wire cannot self-claim `is_resolved: True` | RAR contract strictly validates candidate membership | `test_valid_resolved_passes_validation` in `a2_5_rar_contracts.py` | `SUPERSEDED` |
| `test_included_excluded_overlap_raises_constraint_error` | Assert wire raises on constraint overlap | Constraints handled in dedicated Feed C; merged without crash | `test_adaptive_feed_selection_with_constraints` | `SUPERSEDED` |
| `test_malformed_constraints_type_raises` | Assert wire raises on non-dict constraints | Feed C outputs typed `FeedCOutput` dataclass | Dataclass validation in `lfm_adaptive_feeds.py` | `SUPERSEDED` |

---

## 6. Non-Premature Freezing of Notable Cases (TORT-10 & TORT-11)

### Case 1: `TORT-10` — Temporal Deferral ("Hold off deploying until tomorrow at 10am")
- **Underlying Invariant:** **A temporally deferred operation must not be interpreted as immediately executable.**
- **Architectural Status:** Do **NOT** yet freeze a specific schema representation (such as `BoundSemanticOperation(..., lifecycle=DEFERRED)`).
- **Classification:** `REWRITE_REQUIRED`.
- **Guidance:** The requirement remains active and critical. However, the exact representation of deferred, conditional, or trigger-gated operations will be determined through future empirical evidence in ARN and Step-2 planning.

### Case 2: `TORT-11` — Disjoint Multi-Target Operations ("Sign affidavit and shred draft")
- **Underlying Invariant:** **Decomposition must not destroy the relationship between an operation and the object/target to which that operation applies.**
- **Architectural Status:** Do **NOT** yet freeze:
  - A particular bound-operation schema,
  - A blanket rule that all disjoint multi-target operations must escalate, or
  - A fixed Local vs. Main Brain handling assignment.
- **Classification:** `REWRITE_REQUIRED`.
- **Guidance:** Preserving operation-target coupling is an essential invariant. How URI enforces this (via joint feed framing, bound extraction, or Main-Brain escalation) will follow empirical evidence from ARN question framing.

---

## 7. A2.8A-Specific Regression Boundary

Batch A2.8A focuses **strictly and exclusively** on:
1. **Uncertainty Discovery:** Identifying missing, ambiguous, or un-anchored semantics after TurnFrame and RAR execute.
2. **Question Framing:** Formulating neutral, atomic, grounded semantic questions for cognitive feeds.
3. **Question Validation:** Enforcing that framed questions do not omit critical uncertainties, lead the model, or invent ungrounded referents.

### Gating Tests for Batch A2.8A
Tests gating Batch A2.8A must strictly validate:
- **Structural Signal Preservation:** TurnFrame syntactic cues (verbs, negation spans, references, markers) are faithfully preserved.
- **Unresolved Uncertainty Detection:** RAR `AMBIGUOUS` or `UNRESOLVED_REFERENCE` outcomes are accurately flagged as uncertainties requiring resolution.
- **Question Coverage & Completeness:** Every uncertain dimension generates a corresponding question spec.
- **Question Neutrality & Non-Leading Structure:** Questions must not bias or presuppose the answer.
- **Question Atomicity:** Each feed question asks about exactly one semantic concern.
- **Question Grounding:** Emitted questions reference only known entities and verified turn spans.
- **Validation Behavior:** Question validator rejects leading, malformed, or ungrounded questions.

### Explicitly Non-Gating for Batch A2.8A
Batch A2.8A **MUST NOT** be gated by:
- Tests requiring a specific local model (Gemma, LFM, Qwen-2B, Qwen-9B) to run live.
- Tests asserting binary `requested` vs `prohibited` on deferred temporal turns.
- Tests requiring monolithic wire dictionaries.
- Tests verifying Step-2 capability tool dispatch or Main-Brain continuation text.

---

## 8. Coverage Gap Analysis

The audit identifies three fundamental coverage gaps addressed by Batch A2.8A:

1. **Uncertainty Framing Gap:** Existing tests verify deterministic RAR resolution, but do not systematically test the translation of `RAROutcome.UNRESOLVED_REFERENCE` or `AMBIGUOUS` into neutral, structured feed questions.
2. **Question Validation Boundary Gap:** Existing feed planner tests verify which feed types are selected, but do not validate the linguistic neutrality, atomicity, or grounding of the framed prompts before dispatch.
3. **Critical Signal Preservation Gap:**
   - Earlier small-model experiments showed that vital semantic information disappears before reasoning occurs.
   - A2.8A must test whether URI preserves structurally important markers:
     `don't`, `do not`, `not`, `never`, `without`, `but`, `instead`, `rather than`, `if`, `unless`, `only if`, `until`, `after`, `before`, `once`, unresolved references, multiple verbs, multiple targets.
   - **Crucial Invariant: `StructuralSignal != SemanticConclusion`.**
     Detecting or preserving "don't" does **NOT** authorize URI to hard-code `SEND = PROHIBITED`. The harness preserves marker, location/span, candidate relationship, relevant verb/object, and provenance. Semantic interpretation remains cognitive unless governed by an already-frozen deterministic contract.

---

## 9. Current Test Suite Reporting Breakdown

```
================================================================================
CURRENT CONTRACT REGRESSION:
  135 / 135 passed (100% pass rate in 1.12s across 13 active test files)

A2.8A ARN TESTS:
  Gating tests being implemented in Batch A2.8A (test_m35_uriv1_a2_8a_arn_foundation.py)

HISTORICAL QUALIFICATION:
  95 tests retained as non-gating historical evidence (Gemma, LFM, Qwen-7B, Qwen-14B, scoring harness)

REWRITE REQUIRED:
  2 test cases (TORT-10 deferred timing, TORT-11 disjoint multi-target operations)

SUPERSEDED:
  10 monolithic wire assertions (explicitly traced in Section 5)
================================================================================
```
