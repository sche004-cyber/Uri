# M35 URIv1 — Batch A2.8A Report & Closure Audit
## ARN Foundation — Uncertainty Discovery, Question Framing & Harness-Amplification Boundary

**Date:** September 22, 2026  
**Worktree:** `C:\Users\cheta\Development\Uri\_V1`  
**Branch:** `m35-uri-v1-parallel-architecture`  
**Baseline HEAD:** `e8e3b65259c45fc823addc3ef8969425a265bd1b`  
**Protected Prototype:** `C:\Users\cheta\Development\uri-agent` (100% Untouched / Read-Only)  
**Batch Status:** Completed & Audited  
**Final Milestone State:** `A2.8A_ACCEPTANCE_READY`

---

## 1. Executive Summary & Core Mission

Batch A2.8A establishes the initial architectural foundation for URIv1's **Adaptive Resolution Network (ARN)**. The primary objective was to investigate and resolve the fundamental architectural question:

> *«Can URI reliably determine what remains semantically uncertain after TurnFrame + RAR, preserve the structural information needed to resolve that uncertainty, and frame the right narrow questions without hard-coding the semantic answer?»*

And furthermore, to enforce the **Permanent Harness Principle**:
> *«URI is an intelligence-amplifying harness. It should improve how models receive, decompose, investigate, and resolve problems rather than accumulating hard-coded natural-language interpretations.»*

### Key Audited Results:
1. `[EMPIRICAL FINDING]` **Zero Observed Critical Uncertainty Omissions (CUOR = 0.0% on tested corpus)**: Across the 12-case benchmark covering explicit negation, multi-negation, conditionals, "unless", temporal deferrals, unresolved references, ambiguous references, contrastive clauses, multi-target operations, and implicit semantics, all critical ambiguities were discovered with **100.0% coverage** (0 omissions across the benchmark).
2. `[EMPIRICAL FINDING]` **Structural Signal Preservation Rate = 100.0% (Post-Audit Repair)**: Following the identification and repair of an unanchored modifier marker in Case 11, all **35 of 35 structural signals** across the 12 benchmark cases are preserved with character offsets and text spans, establishing that `StructuralSignal != SemanticConclusion`.
3. `[EMPIRICAL FINDING]` **Three-Way Question Framing Characterization**:
   - **Method A (Deterministic Structural Synthesis)**: Achieved **93.9% validity**, 100% neutrality, 100% atomicity, and 0 presuppositions.
   - **Method B (Model-Assisted Framing via Qwen3.5-9B)**: Achieved **30.3% validity**, 0 presuppositions, but exhibited high vulnerability to *signal loss through paraphrasing* (e.g., substituting "don't" with conceptual phrases like "prohibitions against") and marker collision repetition.
   - **Method C (Hybrid Framing with Validation Gating)**: Produced **no observed critical-omission or validation-safety failures** across the tested A2.8A benchmark (**93.9% validity**, with deterministic fallback preventing signal loss or hallucination).
4. `[ACTIVE CONTRACT]` **Invariant Enforced**: Cognitive/model-generated semantic framing must not silently become trusted semantic state without URI-owned validation appropriate to the downstream risk.
5. `[ACTIVE CONTRACT]` **Full Regression Integrity Maintained**: All 13 unit tests passed (`13 passed in 0.47s`), and the entire current contract regression suite passed (`143 passed, 86 subtests passed, 0 failures`).

---

## 2. Epistemological Classification Discipline

Throughout this report, every claim, contract, and forward plan is strictly classified into one of three distinct categories to avoid architectural confusion:

* `[ACTIVE CONTRACT]`: Behaviors, interfaces, invariants, and test assertions that are presently frozen and enforced in production or active test suites.
* `[EMPIRICAL FINDING]`: Observed benchmark results, quantitative metrics, failure modes, and hardware measurements obtained from actual test runs against local models on the tested corpus.
* `[FUTURE HYPOTHESIS]`: Forward-looking design directions, unverified architectures, planned stages, and experimental proposals that have not yet been empirically validated or frozen.

---

## 3. Preflight Audit & Manifest Corrections

Prior to implementation, a comprehensive audit was performed, and corrections were applied to [`docs/plans/M35_URIV1_A2_8_TEST_RELEVANCE_AND_REGRESSION_MANIFEST.md`](file:///C:/Users/cheta/Development/Uri/_V1/docs/plans/M35_URIV1_A2_8_TEST_RELEVANCE_AND_REGRESSION_MANIFEST.md):

### 3.1 Status Correction of A2.8
* `[ACTIVE CONTRACT]` **Previous Statement**: "Frozen"
* `[ACTIVE CONTRACT]` **Corrected Status**: `"ARCHITECTURE HYPOTHESIS — NOT FROZEN; BEING DECOMPOSED AND EMPIRICALLY VALIDATED THROUGH A2.8A+"`.
* `[FUTURE HYPOTHESIS]` **Decomposition Boundary**: The following components are explicitly non-frozen hypotheses undergoing stage-by-stage empirical validation:
  1. Active Context Compiler (Phases 1–4)
  2. Graphify 2.0 Integration & Multi-Layer Logical Memory
  3. Unified Local Brain Strategy & Model Selection
  4. Main Brain Routing & Escalation Protocol
  5. Step-2 Execution Integration
  6. Autonomous Strategy Learning & Self-Improvement

### 3.2 Status Correction of A2.7 Resident Brain
* `[ACTIVE CONTRACT]` **Previous Phrasing**: "Qwen3.5-9B is URI Step-1".
* `[ACTIVE CONTRACT]` **Corrected Invariant**: «*Resident-Main-Brain topology is qualified. Qwen3.5-9B Q4_K_M is the first empirically qualified provider for that topology.*»
* `[ACTIVE CONTRACT]` Model independence is strictly preserved: Models provide replaceable cognitive capacity; URI defines URI.

### 3.3 Test-Level Classification Updates
* `[ACTIVE CONTRACT]` `test_m35_uriv1_a2_6_qwen_feeds.py`: All 4 tests (`test_qwen_feed_prompts_contain_no_contaminating_examples`, `test_qwen_merger_combines_narrow_feed_outputs`, `test_qwen_merger_contradiction_safety`, `test_qwen_planner_activates_expected_feeds`) are classified as `CURRENT_REGRESSION` because they protect feed independence, deterministic merging, and absence of prompting contamination.
* `[ACTIVE CONTRACT]` `test_m35_uriv1_a2_7_resident_feeds.py`: Classified as `HISTORICAL_QUALIFICATION` (retained for evaluation harness math and empirical residency verification).
* `[ACTIVE CONTRACT]` `test_m35_uriv1_a2_needle_decoder.py`: The 10 historical monolithic wire assertions that failed due to the transition from monolithic Step-1 decoding to the modular TurnFrame + RAR + Adaptive Feed architecture are documented with traceable breakdowns confirming they are superseded by current feed tests.

### 3.4 Addition of Critical Signal Preservation Gap
* `[ACTIVE CONTRACT]` Added Coverage Gap 3 to the manifest: **Critical Signal Preservation Gap**.
* `[ACTIVE CONTRACT]` Rule: `StructuralSignal != SemanticConclusion`. A structural signal extractor records syntactic tokens and offsets without predicting the semantic directive.

---

## 4. Closure Investigation: Root Cause of the Lost Structural Signal

During initial benchmark execution, the aggregate preservation rate was reported as `34 / 35 = 97.1%`. As mandated by the closure audit, this single missing signal was traced down to root cause:

### 4.1 Root Cause Breakdown
1. **Benchmark Case**: `A28A-11-IMPLICIT-SEMANTICS`  
   - Input turn: `"Deal with the Dean's email appropriately."`  
   - Expected critical signals: `("appropriately", "deal")`
2. **Original Signal**: `"appropriately"`
   - Exact source span: character index `[27, 40]`
   - Signal type: `MODIFIER_MARKER` (implicit operational qualifier)
3. **Stage at Which It Disappeared**: `UncertaintyDiscoveryEngine.extract_structural_signals`.
4. **Why It Disappeared**:
   - `extract_structural_signals` had scanner loops for negation, contrast, conditional, temporal, coordination, action verbs, and unresolved references.
   - Although `_IMPLICIT_QUALIFIER_PATTERN` was defined in the module, `extract_structural_signals` omitted iterating over it.
   - In `discover_uncertainties`, `_IMPLICIT_QUALIFIER_PATTERN` was evaluated directly to create `UNC-001-MOD-SCOPE`, but set `anchored_signals=()`. Thus, the signal token was never added to the returned `signals` tuple.
5. **Whether Disappearance Was Expected or Defective**:
   - It was an **implementation defect** within A2.8A scope. The scanner pattern existed but was not registered in the signal extraction pass.
6. **Whether Uncertainty Discovery Compensated for It**:
   - **Yes.** In `discover_uncertainties`, `UNC-001-MOD-SCOPE` was still created. Thus, CUOR remained 0.0%. However, the signal was absent from the preserved signal list.
7. **Downstream Safety/Execution Relevance**:
   - Because `anchored_signals` was empty, Method A's template framing engine could not extract a token anchor, falling back to:
     `"What concrete operations are required by the qualifier \"indicated marker\"?"`
   - This produced a generic fallback string rather than the grounded token `"appropriately"`.

### 4.2 Repair Applied
1. `[ACTIVE CONTRACT]` Added `MODIFIER_MARKER = "MODIFIER_MARKER"` to `StructuralSignalType` in [`uri_v1/arn/uncertainty_contracts.py`](file:///C:/Users/cheta/Development/Uri/_V1/uri_v1/arn/uncertainty_contracts.py).
2. `[ACTIVE CONTRACT]` Updated `extract_structural_signals` in [`uri_v1/arn/uncertainty_discovery.py`](file:///C:/Users/cheta/Development/Uri/_V1/uri_v1/arn/uncertainty_discovery.py) to scan `_IMPLICIT_QUALIFIER_PATTERN` and emit `StructuralSignal(signal_type=StructuralSignalType.MODIFIER_MARKER, span_text=m.group(0), start_char=m.start(), end_char=m.end(), provenance="LexicalModifierScan")`.
3. `[ACTIVE CONTRACT]` Updated `discover_uncertainties` to anchor `m_sig` in `anchored_signals=(m_sig,)`.
4. `[ACTIVE CONTRACT]` Added focused regression test `test_modifier_scope_signal_preserved_and_anchored` to [`tests/test_m35_uriv1_a2_8a_arn_foundation.py`](file:///C:/Users/cheta/Development/Uri/_V1/tests/test_m35_uriv1_a2_8a_arn_foundation.py).
5. `[EMPIRICAL FINDING]` Re-running the benchmark confirmed that Case 11 signals preserved increased from `1/2` to `2/2`, elevating the benchmark-wide preservation rate to **35 / 35 = 100.0%**. Method A grounded question framing now generates:
   `"What concrete operations are required by the qualifier \"appropriately\"?"`

---

## 5. Correction of Safety & Promotion Overclaims

### 5.1 Evidence-Bounded Safety Characterization
* `[ACTIVE CONTRACT]` We do NOT claim "100% architectural safety" from a 12-case benchmark.
* `[EMPIRICAL FINDING]` **Corrected Audit Statement**:
  > *«Method C produced no observed critical-omission or validation-safety failures across the tested A2.8A benchmark.»*
* `[EMPIRICAL FINDING]` The measured `CUOR = 0.0%` is an empirical result for the 12-case test corpus, not a universal mathematical guarantee across all unseen natural-language inputs.

### 5.2 Separation of Invariant From Implementation
* `[ACTIVE CONTRACT]` **Model-Independent Architectural Invariant**:
  > *«Cognitive/model-generated semantic framing must not silently become trusted semantic state without URI-owned validation appropriate to the downstream risk.»*
* `[EMPIRICAL FINDING]` **Implementation Status**:
  > *«The currently implemented Hybrid Method C satisfied this invariant across the tested A2.8A corpus and is therefore a qualified implementation for the present stage.»*
* `[FUTURE HYPOTHESIS]` URI does NOT freeze the sequence `model → validator → deterministic template fallback` as ARN's permanent or final architecture. Future stages incorporating Graphify or targeted resolution strategies may alter the framing and resolution topology.

### 5.3 Correction of Strategy Promotion Policy
* `[ACTIVE CONTRACT]` Critical Uncertainty Omission Rate is a vital ARN evaluation metric.
* `[ACTIVE CONTRACT]` We do **NOT** freeze `CUOR == 0.0%` as the sole or universal future strategy-promotion threshold.
* `[FUTURE HYPOTHESIS]` Future strategy promotion will require multi-dimensional evaluation, including:
  1. Critical omissions
  2. Hallucination and candidate invention
  3. Grounding fidelity
  4. Semantic correctness
  5. Regression safety
  6. Execution latency
  7. Compute/resource footprint
  8. Authority and security boundaries

---

## 6. Preservation of the Core A2.8A Empirical Finding

### 6.1 What Was Discovered
`[EMPIRICAL FINDING]` Within the tested A2.8A corpus, constrained deterministic question framing substantially outperformed unconstrained model-assisted framing under the current validator:
- **Deterministic Synthesis (Method A)**: Produced 93.9% valid questions with zero leading presuppositions, zero ungrounded terms, and sub-millisecond latency.
- **Model-Assisted Formulation (Method B via Qwen3.5-9B)**: Succeeded in only 30.3% of questions due to a strong propensity to paraphrase or generalize exact lexical tokens (e.g. replacing `"don't"` with `"prohibitions against"`), thereby stripping the downstream solver of the concrete structural anchor.

### 6.2 What Must NOT Be Concluded
`[ACTIVE CONTRACT]` To prevent architectural overinterpretation, the following false conclusions are explicitly rejected:
1. **DO NOT CONCLUDE** that deterministic ARN is generally more intelligent than Qwen3.5-9B.
2. **DO NOT CONCLUDE** that local models are unnecessary for semantic resolution.
3. **DO NOT CONCLUDE** that Method A is permanently superior across all domains.
4. **DO NOT CONCLUDE** that Method C is ARN's final architecture.
5. **DO NOT CONCLUDE** that Qwen3.5-9B should be removed from URI's architecture.

`[EMPIRICAL FINDING]` The empirical result demonstrates that **question framing is sufficiently constrained** that URI can deterministically scaffold and validate questions, removing an unnecessary burden from expensive cognitive inference.

---

## 7. Future Graphify Boundary (Preserved & Unimplemented)

In accordance with strict batch scoping, **Graphify was not implemented or modified** during this audit.

* `[ACTIVE CONTRACT]` **Graphify Boundary Rule**:
  > *«Graphify is intended as targeted relationship/evidence lookup, not whole-database context injection.»*
* `[FUTURE HYPOTHESIS]` **Emerging Operational Loop**:
  $$\text{ARN Uncertainty Discovery} \longrightarrow \text{Targeted Graphify Lookup} \longrightarrow \text{Reassess Uncertainty} \longrightarrow \text{Invoke Cognition Only for Residual}$$
* `[FUTURE HYPOTHESIS]` **Multi-Layer Logical Memory Hypothesis**: Graphify may maintain multiple logical memory layers covering:
  - Entities and objects
  - Relationships and topologies
  - Evidence and provenance trails
  - Validity, authority, and stature boundaries
  - Temporal and current state transitions
* `[FUTURE HYPOTHESIS]` Neither the layer count nor schema definitions are frozen at this stage.

---

## 8. Benchmark Metrics (Audited)

### 8.1 Discovery & Signal Preservation Metrics

| Metric | Measured Value (Initial) | Measured Value (Post-Audit) | Target | Status |
| :--- | :---: | :---: | :---: | :---: |
| **Total Test Cases** | 12 | 12 | 12 | Complete |
| **Structural Signals Preserved** | 34 / 35 (97.1%) | **35 / 35 (100.0%)** | ≥ 95.0% | **PASSED** |
| **Uncertainty Discovery Coverage** | 100.0% | **100.0%** | 100.0% | **PASSED** |
| **Critical Uncertainty Omission Rate** | **0.0%** | **0.0%** | 0.0% on corpus | **PASSED** |
| **Total Uncertainties Discovered** | 33 | **33** | ≥ 22 | Comprehensive |

### 8.2 Question Framing Performance

| Metric | Method A (Deterministic) | Method B (Model-Assisted) | Method C (Hybrid Gated) |
| :--- | :---: | :---: | :---: |
| **Total Questions** | 33 | 33 | 33 |
| **Valid Questions** | 31 / 33 (**93.9%**) | 10 / 33 (**30.3%**) | 31 / 33 (**93.9%**) |
| **Presupposition Violations** | 0 (100% neutral) | 0 (100% neutral) | 0 (100% neutral) |
| **Atomicity Violations** | 0 (100% atomic) | 0 (100% atomic) | 0 (100% atomic) |
| **Ungrounded Referents** | 0 (100% grounded) | 0 (100% grounded) | 0 (100% grounded) |
| **Lost Critical Signal (Paraphrase)** | 0 | 18 / 33 (54.5%) | 0 (Filtered by gate) |
| **Marker Collision Flags** | 2 / 33 (6.1%)* | 5 / 33 (15.2%) | 2 / 33 (6.1%) |
| **Observed Critical Failures** | 0 | Drift on signals | **0 Failures** |

*\*Note: Duplicate question text flags occur when a turn contains multiple identical lexical tokens (e.g. two `"don't"` markers in `A28A-03`), which template framing renders identically unless disambiguated by clause index.*

---

## 9. Full Test Suite & Regression Verification

### 9.1 Unit Test Execution (`tests/test_m35_uriv1_a2_8a_arn_foundation.py`)
All 13 dedicated unit tests passed in 0.47 seconds:
- `test_structural_signal_preservation` — **PASSED**
- `test_structural_signal_does_not_hardcode_semantic_conclusion` — **PASSED**
- `test_critical_uncertainty_omission_rate_zero` — **PASSED**
- `test_temporal_deferral_uncertainty_discovered` — **PASSED**
- `test_rar_unresolved_and_ambiguous_propagation` — **PASSED**
- `test_multi_target_operation_coupling_preserved` — **PASSED**
- `test_question_coverage_and_neutrality_deterministic` — **PASSED**
- `test_leading_question_rejection` — **PASSED**
- `test_compound_question_rejection` — **PASSED**
- `test_ungrounded_referent_rejection` — **PASSED**
- `test_hybrid_framing_fallback_safety` — **PASSED**
- `test_uncertainty_provenance_tracking` — **PASSED**
- `test_modifier_scope_signal_preserved_and_anchored` (**New Regression Test**) — **PASSED**

### 9.2 Full Current Contract Regression Suite
```
test_m35_uriv1_a0_skeleton.py ................ [PASSED]
test_m35_uriv1_a1_1_contract_hardening.py .... [PASSED]
test_m35_uriv1_a1_decoded_request.py ......... [PASSED]
test_m35_uriv1_a2_5_deterministic_rar.py ..... [PASSED]
test_m35_uriv1_a2_5_candidate_invention_fix.py [PASSED]
test_m35_uriv1_a2_5_rar_adversarial_safety.py  [PASSED]
test_m35_uriv1_a2_5_rar_contracts.py ......... [PASSED]
test_m35_uriv1_a2_5_rar_stage4_refinements.py  [PASSED]
test_m35_uriv1_a2_5_stage4_feeds.py .......... [PASSED]
test_m35_uriv1_a2_6_qwen_feeds.py ............ [PASSED]
tests/test_m35_uriv1_a2_3_turn_frame.py ...... [PASSED]
tests/test_m35_uriv1_a2_8a_arn_foundation.py .. [PASSED]
```
**Total Results:** **143 passed, 86 subtests passed in 1.44s (0 failures, 0 regressions)**.

### 9.3 Repository & Prototype Status Check
- **Protected Legacy Prototype (`C:\Users\cheta\Development\uri-agent`)**: Verified **100% untouched**.
- **Worktree (`C:\Users\cheta\Development\Uri\_V1`)**: On branch `m35-uri-v1-parallel-architecture` at baseline HEAD `e8e3b65259c45fc823addc3ef8969425a265bd1b`.
- **Zero repository violations**: No commit, push, merge, or PR.

---

## 10. Audit Conclusion & Final Milestone Acceptance

### Answering the Primary Audit Question:
> *«Does the corrected evidence justify accepting A2.8A as a bounded ARN-foundation result without prematurely freezing its current implementation as URI's final ARN architecture?»*

**Verdict: YES.**

The evidence demonstrates that:
1. URI can reliably identify remaining semantic uncertainties following TurnFrame + RAR without hard-coding the semantic answer (`100% discovery coverage`, `0 observed omissions` across the benchmark).
2. URI preserves all critical structural tokens (`35 / 35 = 100.0% preservation` post-audit).
3. The model-independent invariant (`Cognitive framing must not become trusted state without URI-owned validation`) is fully satisfied by the qualified hybrid implementation.
4. Method C is qualified as an effective implementation for the present stage, while leaving the future ARN evolution (Graphify integration, multi-layer memory, and advanced resolution strategies) cleanly unfrozen.

**Final Stop Condition:** `A2.8A_ACCEPTANCE_READY`
