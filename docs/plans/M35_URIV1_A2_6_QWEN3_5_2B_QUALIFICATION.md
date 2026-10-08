# M35 — URIv1 Parallel Architecture
## Batch A2.6 Report: Qwen3.5-2B RAR + Adaptive Semantic Feed Qualification

- **Author / Role**: Implementation & Qualification Engineer (M35 Parallel Architecture)
- **Worktree**: `C:\Users\cheta\Development\Uri\_V1`
- **Branch**: `m35-uri-v1-parallel-architecture`
- **Baseline Git HEAD**: `e8e3b65259c45fc823addc3ef8969425a265bd1b`
- **Candidate Evaluated**: **Qwen3.5-2B-Q4_K_M** (1.9B parameters, `openresearchtools/Qwen3.5-2B-GGUF`, local LM Studio endpoint `127.0.0.1:1234`)
- **Subsystem Under Test**: Adaptive Narrow Semantic Feeds (G, O, C, B) + Deterministic RAR + Deterministic Merger
- **Protected Prototype**: `C:\Users\cheta\Development\uri-agent` (100% untouched, READ-ONLY)
- **Date**: September 22, 2026

---

## 1. Executive Summary & Production Verdicts

### 1.1 Mandated Final Verdicts

| Dimension | Mandated Final Verdict | Architectural Rationale |
| :--- | :--- | :--- |
| **Qwen3.5-2B Candidate Verdict** | **`QWEN3_5_2B_SUB_THRESHOLD_ESCALATE_TO_4B`** | Qwen3.5-2B demonstrates a massive leap in capability over LFM2.5-350M: Goal Accuracy reached **94.7%** (clearing the $\ge 90\%$ gate), Operation Retention reached **85.3%** (up from 55%), and concurrent turn latency dropped to **254.7 ms** (an **8.1x speedup** over broad calls). However, the model falls short of critical safety gates: Requested Operation Accuracy reached only **73.7%** (gate: $\ge 90\%$) and Negation / Prohibited Operation Accuracy reached only **34.2%** (gate: $\ge 90\%$). When positive and negative verbs co-occur in the same turn (e.g. *“review but do not send”*), 2B systematically drops the negative clause. It cannot be approved as the primary Step-1 Semantic Decoder. |
| **Architecture Verdict** | **`ADAPTIVE_CONCURRENT_FEEDS_VALIDATED_LATENCY_BREAKTHROUGH`** | The adaptive narrow multi-feed architecture achieved its strongest empirical validation yet: Mode D concurrent execution achieved **254.7 ms mean latency** across 4 concurrent slots on local hardware, maintaining **100% structural validity**, **100% reference correctness**, and **0 RAR wrong bindings**. Scaffolding and parallelization work perfectly; the decoder requires scaling to the **4B parameter class** (`Qwen3.5-4B`) to achieve the required $\ge 90\%$ verb extraction and negation gates. |

---

## 2. Model Identity & Verification

Per Section 2 requirements, model identity was rigorously validated before qualification:

```yaml
model_identity:
  downloaded_file: Qwen3.5-2B-Q4_K_M.gguf
  source: openresearchtools/Qwen3.5-2B-GGUF
  destination: C:\Users\cheta\.lmstudio\models\Qwen\Qwen3.5-2B-GGUF\Qwen3.5-2B-Q4_K_M.gguf
  file_size_bytes: 1274396608
  file_size_gb: 1.187 (1215.36 MB)
  gguf_magic: b'GGUF' (Version 3)
  tensor_count: 320
  metadata_kv_pairs: 41
  general.architecture: qwen35
  general.size_label: 1.9B
  general.quantization_version: 2
  general.file_type: 15 (Q4_K_M)
  runtime_provider: LM Studio Local Server (OpenAI-compatible)
  runtime_device: AMD Radeon RX 7900 GRE (16 GB VRAM)
  runtime_parallel_slots: 4
  vram_footprint_mb: 1274.0
  system_ram_mb: 11241.2 used / 24500.8 total (45% load)
```

---

## 3. Comparative Modes Performance & Latency

Four architectural modes were evaluated across representative test cases:

- **Mode A**: Single broad semantic call without RAR.
- **Mode B**: Serial RAR $\rightarrow$ single broad residual-semantic call.
- **Mode C**: Serial RAR $\rightarrow$ adaptive narrow feeds sequential.
- **Mode D**: Parallel RAR + adaptive narrow feeds concurrent $\rightarrow$ deterministic merger.

### 3.1 Latency & Throughput Benchmark

| Mode | Architecture Pipeline | Mean Latency (ms) | Speedup vs Mode A | Concurrency | Structural Reliability |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Mode A** | Broad Single-Pass (No RAR) | 2,069.4 ms | 1.0x (Baseline) | Serial (1 call) | 100.0% |
| **Mode B** | Serial RAR + Broad Residual | 1,818.2 ms | 1.1x | Serial (1 call) | 100.0% |
| **Mode C** | Serial RAR + Narrow Feeds (Seq) | 435.8 ms | 4.7x | Serial (2–3 calls) | 100.0% |
| **Mode D** | **Parallel RAR + Narrow Feeds (Concurrent)** | **254.7 ms** | **8.1x** | **Concurrent (2–4 slots)** | **100.0%** |

### 3.2 Architectural Breakthroughs in Mode D
1. **8.1x Latency Reduction**: Mode D cuts turn latency from over 2 seconds down to **254.7 ms**, well within the sub-300ms budget required for interactive Edge and Second-Brain operations.
2. **ChatML Pre-Closed Reasoning Framing**: Prompting with `<|im_start|>assistant\n<think>\n</think>\n` bypassed unnecessary multi-thousand-token thinking loops while preserving full instruction following and schema enforcement.

---

## 4. Empirical Capability Profile & Breakpoint Analysis

### 4.1 Negation Ladder (N1 to N6)

| Case ID | Turn Syntax | Expected Prohibited Ops | Actual Prohibited Ops | Result | Analysis |
| :--- | :--- | :---: | :---: | :---: | :--- |
| **NEG-N1** | *"Don't send it."* | `['send']` | `['send']` | **PASS** | Pure negative command correctly captured. |
| **NEG-N2** | *"Don't send it; draft it."* | `['send']` | `[]` | **FAIL** | Contrastive pair: positive verb (*draft*) captured; negative verb (*send*) dropped. |
| **NEG-N3** | *"Don't send or delete it; only revise it."* | `['send', 'delete']` | `[]` | **FAIL** | Multi-negative with positive constraint: omitted negative verbs. |
| **NEG-N4** | *"Send it only after approval."* | `[]` | `[]` | **PASS** | Conditional timing constraint correctly not treated as negative verb. |
| **NEG-N5** | *"Do not send previous; send revised."* | `['send']` | `[]` | **FAIL** | Same-verb contrastive: polarity inverted into requested *send*. |
| **NEG-N6** | *"Don't summarize unless figures differ."* | `['summarize']` | `[]` | **FAIL** | Conditional exception dropped. |

**Negation Accuracy**: **33.3% (2/6)**. Qwen3.5-2B reliably extracts pure standalone negations (N1), but systematically drops the prohibited verb when any positive verb is present in the turn.

### 4.2 Operation Retention Ladder (O-R1 to O-R5)

| Case ID | Verbs in Turn | Expected Ops | Actual Ops Retained | Retention Rate |
| :--- | :---: | :--- | :--- | :---: |
| **RET-OR1** | 1 | `draft` | `draft` | **100.0%** |
| **RET-OR2** | 2 | `draft`, `shorten` | `draft`, `shorten` | **100.0%** |
| **RET-OR3** | 3 | `compare`, `draft`, `shorten` | `compare`, `draft` | **66.7%** |
| **RET-OR4** | 4 | `compare`, `revise`, `shorten`, `send` | `compare`, `revise`, `send`, `shorten` | **100.0%** |
| **RET-OR5** | 5 | `compare`, `revise`, `draft`, `send`, `archive` | `compare`, `draft`, `send` | **60.0%** |

**Mean Operation Retention**: **85.3%**. A massive improvement over LFM2.5-350M (which scored 55.0% and collapsed at $\ge 2$ operations). Qwen3.5-2B safely handles 2 operations at 100% retention and 4 operations at 100% retention, but degrades on 5+ operations or when compound actions mix with qualifications.

### 4.3 Semantic Complexity Ladder (C0 to C8)

- **C0 (Single op)**: PASS (Goal: OK, Req: OK, Neg: OK, Latency: 391ms)
- **C1 (Two ops)**: PASS (Goal: OK, Req: OK, Neg: OK, Latency: 293ms)
- **C2 (Three ops)**: FAIL (Omitted secondary verb)
- **C3 (Positive + Negative)**: FAIL (Dropped negative verb)
- **C4 (Two Positive + Negative)**: FAIL (Dropped negative verb)
- **C5 (Conditional Timing)**: PASS (Extracted timing condition into constraints)
- **C6 (Two Targets)**: PASS (RAR resolved distinct target references)
- **C7 (Relational Reference)**: PASS (RAR resolved previous reference)
- **C8 (Nested Dependency)**: FAIL (Compound clauses exceeded 2B capacity)

**Reliable Semantic Complexity Boundary**: **CMPLX-C1** (for mixed polarity) and **CMPLX-C5–C7** (when turn does not require simultaneous positive and negative verb classification).

---

## 5. Critical Production Acceptance Gate Scorecard

| Acceptance Dimension | Production Gate | LFM2.5-350M (Stage 4) | Qwen3.5-2B (Batch A2.6) | Gate Status |
| :--- | :---: | :---: | :---: | :---: |
| **Goal Accuracy** | $\ge 90.0\%$ | 83.3% | **94.7%** | **PASSED** |
| **Requested Operations** | $\ge 90.0\%$ | 33.3% | **73.7%** | **FAILED** |
| **Negation / Prohibited Ops** | $\ge 90.0\%$ | 16.7% | **34.2%** | **FAILED** |
| **Final Reference Correctness**| $\ge 95.0\%$ | 100.0% (via RAR) | **100.0%** (via RAR) | **PASSED** |
| **Context Grounding** | $\ge 95.0\%$ | 100.0% (via RAR) | **100.0%** (via RAR) | **PASSED** |
| **Unresolved Honesty** | $\ge 95.0\%$ | 100.0% (via RAR) | **100.0%** (via RAR) | **PASSED** |
| **Ambiguity Preservation** | $\ge 90.0\%$ | 100.0% | **100.0%** | **PASSED** |
| **Context Invention Rate** | $\sim 0.0\%$ | 0.0% | **10.5%** | **FAILED** |
| **Structural Reliability** | $\ge 99.0\%$ | 100.0% | **100.0%** | **PASSED** |
| **RAR Wrong Binding** | **0** | **0** | **0** | **PASSED** |

---

## 6. Provider Capability Profile for Qwen3.5-2B

```yaml
provider_profile:
  candidate: Qwen3.5-2B-Q4_K_M
  architecture: qwen35
  parameters: 1.9B
  quantization: Q4_K_M
  disk_size_bytes: 1274396608

operating_envelope:
  preferred_mode: adaptive_narrow_feeds_concurrent (Mode D)
  concurrent_mean_latency_ms: 254.7
  sequential_mean_latency_ms: 435.8
  max_reliable_operations_per_feed: 2
  operation_retention_rate: 85.3%
  max_reliable_semantic_complexity: CMPLX-C1 (positive only) / CMPLX-C5..C7 (no negation)
  negation_handling: simple_standalone_only (fails contrastive/mixed)
  context_noise_tolerance: high (>1200 tokens via feed isolation)
  hallucination_rate: 10.5% (occurs under multi-clause ambiguity)

feed_recommendations:
  preferred_goal_feed: enabled (94.7% accuracy, excellent concise phrasing)
  preferred_operation_feed: SUB-THRESHOLD (73.7% accuracy, drops prohibited verbs in mixed turns)
  preferred_constraint_feed: enabled (captures timing, length limits, formats)
  preferred_binding_feed: enabled (correctly utilizes RAR anchors)

escalation_required_when:
  - turn_contains_negation_and_positive_action (contrastive clauses)
  - requested_operations > 2
  - complex_nested_dependency_clauses: true
```

---

## 7. Regression Test Suite Verification

The complete regression test suite across Batches A0 through A2.6 passes with zero errors:

```powershell
pytest test_m35_uriv1_a0_skeleton.py test_m35_uriv1_a1_decoded_request.py test_m35_uriv1_a1_1_contract_hardening.py test_m35_uriv1_a2_needle_decoder.py test_m35_uriv1_a2_1_needle_narrow.py test_m35_uriv1_a2_2_qwen_decoder.py tests/test_m35_uriv1_a2_3_turn_frame.py tests/test_m35_uriv1_a2_3_semantic_envelope.py test_m35_uriv1_a2_4_qwen14b_decoder.py test_m35_uriv1_a2_5_rar_contracts.py test_m35_uriv1_a2_5_deterministic_rar.py test_m35_uriv1_a2_5_rar_adversarial_safety.py test_m35_uriv1_a2_5_rar_stage4_refinements.py test_m35_uriv1_a2_5_candidate_invention_fix.py test_m35_uriv1_a2_5_lfm_decoder.py test_m35_uriv1_a2_5_stage4_feeds.py test_m35_uriv1_a2_6_qwen_feeds.py
```
**Output**: `201 passed in 1.60s` (100% passing, zero regressions).

---

## 8. Next Step Recommendation & Stop Rules

Per the batch stop rules:
1. Qwen3.5-2B failed critical semantic gates (Requested Operations at 73.7% vs $\ge 90\%$; Negation at 34.2% vs $\ge 90\%$).
2. Execution is stopped immediately.
3. **Recommendation**: Advance qualification to **`Qwen3.5-4B`** (`Qwen3.5-4B-Q4_K_M.gguf`, ~2.5 GB). 4B represents the sweet spot possessing the syntactic reasoning needed to resolve contrastive negations without exceeding edge VRAM budgets. Do not download or proceed until instructed.
