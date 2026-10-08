# URI Edge Ultra-Light Worker Benchmark Report: 4-Model Comparative Qualification

**Date:** 2026-09-28  
**Experiment:** Strict side-by-side comparison of four ultra-light (~270M–360M) foundation models for the URI Second-Brain Bounded Worker Role:
1. **LFM2.5-350M** (Liquid AI)
2. **Granite 4.0-H-350M** (IBM)
3. **SmolLM2-360M-Instruct** (Hugging Face)
4. **Gemma 3 270M-IT** (Google DeepMind)

---

## 1. Executive Summary

This experiment evaluated four candidate ultra-light edge models strictly confined to URI's **Bounded Worker Role** (grounded extraction, argument normalization, schema population, negation preservation, and entity-preserving micro-rewrites). All models operated under URI's canonical architecture:
- Upstream **Model-Job Matching Gate** and **Needle 3.0.2 Narrow Decision Specialist & Eligibility Gate**;
- Repaired minimal task capsules (eliminating positional enum priors);
- The unchanged 30-case experimental battery;
- Independent **URI Edge Task Verifier** (with audited decimal-regex sentence counting).

### Key Takeaway
**IBM Granite 4.0-H-350M achieved a perfect 8/8 (100.0%) verified worker score**, with **0 false candidate claims**, **0 schema errors**, and **0 entity retention failures**, delivering consistent **384.3 ms mean worker latency** (414.4 ms p95) on a compact **366 MB Q8_0 Mamba-2/Transformer hybrid** footprint. It is the outright winner of the ultra-light edge worker qualification.

```
       WORKER CORRECTNESS (8 Worker-Admitted Cases)
  Granite 4.0-H-350M : [████████████████████████████████████████] 8/8 (100.0%)
  LFM2.5-350M        : [█████████████████████████████████     ] 7/8 (87.5%)
  Gemma 3 270M-IT    : [██████████████████████████████        ] 6/8 (75.0%)
  SmolLM2-360M       : [████████████████████                  ] 4/8 (50.0%)

       CRITICAL SAFETY INVARIANT (FALSE_VERIFIED_SUCCESS)
  All 4 Models       : 0 (100% verifier containment preserved)
```

---

## 2. Model Profiles & Environmental Metadata

All models were evaluated locally on the same Windows host workstation (AMD Ryzen / NVIDIA RTX) under identical temperature (`0.0`), format restrictions, and verifier rules.

| Property | LFM2.5-350M | Granite 4.0-H-350M | SmolLM2-360M-Instruct | Gemma 3 270M-IT |
| :--- | :--- | :--- | :--- | :--- |
| **Developer** | Liquid AI | IBM Research | Hugging Face | Google DeepMind |
| **Model Tag / ID** | `lfm2.5-350m` | `granite4:350m-h` (`7145075ed3d6`) | `smollm2:360m` (`297281b699fc`) | `gemma3:270m` (`e7d36fb2c3b3`) |
| **Architecture** | Liquid Neural Network (LFM) | Mamba-2 / Transformer Hybrid (`granitehybrid`) | LLaMA Transformer (`llama`) | Gemma 3 Transformer (`gemma3`) |
| **Parameter Count**| ~350M | 340.33M | 361.82M | 268.10M |
| **Quantization** | Q8_0 | Q8_0 | F16 | Q8_0 |
| **Context Length** | 32,768 | 1,048,576 (1M tokens) | 8,192 | 32,768 |
| **On-Disk Size** | 379 MB | 366 MB | 725 MB | 291 MB |
| **Runtime Engine** | LM Studio (v1/chat/completions) | Ollama (api/chat) | Ollama (api/chat) | Ollama (api/chat) |
| **License** | Custom / Proprietary weights | Apache 2.0 | Apache 2.0 | Gemma Terms of Use |

---

## 3. Side-by-Side Comparison Metrics

### A. Isolated Worker Metrics (8 Admitted Cases)

Nine cases were assigned to the worker family by the Model-Job Matching Gate; `CASE_18_NEGATION` was safely escalated by Needle 3's eligibility gate due to ungrounded `"delete"` operations, admitting exactly 8 cases to the workers.

| Metric | LFM2.5-350M | Granite 4.0-H-350M | SmolLM2-360M | Gemma 3 270M-IT |
| :--- | :---: | :---: | :---: | :---: |
| **Worker Tasks Admitted** | 8 | 8 | 8 | 8 |
| **Worker Correctness** | **7 / 8 (87.5%)** | **8 / 8 (100.0%)** | **4 / 8 (50.0%)** | **6 / 8 (75.0%)** |
| **Verified Worker Successes** | 7 | 8 | 4 | 6 |
| **False Worker Candidate Successes** | 1 (12.5%) | **0 (0.0%)** | 2 (25.0%) | 2 (25.0%) |
| **False Verified Successes** | **0 (0.0%)** | **0 (0.0%)** | **0 (0.0%)** | **0 (0.0%)** |
| **Schema / Formatting Errors** | 0 | **0** | 2 (infinite nesting) | 0 |
| **Negation / Polarity Errors** | 0 | **0** | 0 | 0 |
| **Hallucination Rate** | 0 | **0** | 0 | 1 (Case 02 injected synthetic fields) |
| **Referent / Entity Failures** | 1 (Case 15) | **0** | 2 (Cases 01, 15) | 2 (Cases 01, 02 placeholder leak) |
| **Mean Worker Latency** | **326.8 ms** | 384.3 ms | 491.5 ms | 463.4 ms |
| **p95 Worker Latency** | **381.1 ms** | 414.4 ms | 848.8 ms | 509.6 ms |

### B. Full 30-Case System Metrics (Edge Cluster Pipeline)

Includes Matching Gate, Needle 3 decision specialist, deterministic path, worker, and independent verifier across the entire battery.

| System Metric | LFM2.5-350M | Granite 4.0-H-350M | SmolLM2-360M | Gemma 3 270M-IT |
| :--- | :---: | :---: | :---: | :---: |
| **Battery Accuracy** | 28 / 30 (93.3%) | **29 / 30 (96.7%)** | 25 / 30 (83.3%) | 27 / 30 (90.0%) |
| **Verified Local Successes** | 14 (46.7%) | **15 (50.0%)** | 11 (36.7%) | 13 (43.3%) |
| **Escalations Confirmed** | 15 (50.0%) | 15 (50.0%) | 15 (50.0%) | 15 (50.0%) |
| **Rejections (Unsafe/Failed)**| 1 (3.3%) | **0 (0.0%)** | 4 (13.3%) | 2 (6.7%) |
| **False Verified Successes** | **0 (0.0%)** | **0 (0.0%)** | **0 (0.0%)** | **0 (0.0%)** |
| **Mean Turn Latency** | **121.9 ms** | 131.9 ms | 160.8 ms | 153.8 ms |
| **p95 Turn Latency** | 598.7 ms | **581.9 ms** | 907.0 ms | 653.3 ms |
| **Host System RAM Used** | 18.57 GB | 18.61 GB | 18.61 GB | 18.62 GB |

*Note: In all four arms, `CASE_18_NEGATION` was escalated by Needle 3 due to the presence of destructive `"delete"` instructions without local delete capability, yielding 29/30 maximum possible full-system correctness for worker arms.*

---

## 4. Deep-Dive Case Analyses

### A. Case 02: `CASE_02_INTENT`
*Task: "Calculate total revenue for Q3 from revenue.csv"*  
*Instruction: "Extract target filename from request."*  
*Target Schema: `{"decision": "LOCAL", "intent": "CALCULATE", "target": "<filename>"}`*

| Model | Raw Output | Result | Latency | Diagnosis |
| :--- | :--- | :---: | :---: | :--- |
| **Granite 4.0-H-350M** | `{"decision": "LOCAL", "intent": "CALCULATE", "target": "revenue.csv"}` | **PASS** | 372.4 ms | Flawless extraction of `revenue.csv`, exact schema alignment. |
| **LFM2.5-350M** | `{"decision": "LOCAL", "intent": "CALCULATE", "target": "revenue.csv"}` | **PASS** | 330.8 ms | Clean extraction and exact schema alignment. |
| **SmolLM2-360M** | `{"total_revenue": {"value": {"amount": {"amount": ...` | **FAIL** | 848.8 ms | Entered an infinite recursive dictionary loop; schema broken. |
| **Gemma 3 270M-IT** | `{"decision": "LOCAL", "intent": "CALCULATE", "target": "<filename>", "revenue": 0}` | **FAIL** | 509.6 ms | Failed to ground filename; left `<filename>` placeholder and hallucinated `"revenue": 0`. |

**Verdict:** Both Granite 4.0-H-350M and LFM2.5-350M handled Case 02 flawlessly once the capsule was repaired. Gemma 3 exhibited placeholder inertia, while SmolLM2 collapsed into recursive repetition.

---

### B. Case 15: `CASE_15_REWRITE`
*Task: "Summarize this transaction for an executive alert in one sentence. Transaction details: ID: 101, Customer: Bob, Amount: $250.00, Status: Complete, Date: 2026-03-31."*  
*Instruction: "Write exactly one concise sentence containing: ID 101, Customer Bob, Total $250.00."*  
*Target Schema: `{"decision": "LOCAL", "sentence": "<one sentence summary>"}`*

| Model | Raw Output | Result | Latency | Diagnosis |
| :--- | :--- | :---: | :---: | :--- |
| **Granite 4.0-H-350M** | `{"decision": "LOCAL", "sentence": "ID 101, Customer Bob, Total $250.00"}` | **PASS** | 379.4 ms | Exact field retention (`101`, `Bob`, `$250.00`); 1 sentence; verifier decimal fix confirmed. |
| **Gemma 3 270M-IT** | `{"decision": "LOCAL", "sentence": "Bob is a customer of ID 101, and the total amount is $250.00."}` | **PASS** | 439.9 ms | Excellent natural language synthesis retaining all 3 required fields in a single sentence. |
| **LFM2.5-350M** | `{"decision": "LOCAL", "sentence": "Invoice Summary"}` | **FAIL** | 272.4 ms | Truncated output to a 2-word title; dropped all 3 required entity fields. |
| **SmolLM2-360M** | `{"decision": "LOCAL", "sentence": "<one sentence summary>"}` | **FAIL** | 323.4 ms | Literal echo of the placeholder string without processing user data. |

**Verdict:** Granite 4.0-H-350M and Gemma 3 270M-IT proved capable of entity-preserving micro-rewriting. LFM2.5-350M over-compressed the text, dropping vital entities, and SmolLM2 echoed the schema prompt.

---

## 5. Model-by-Model Analysis

### 1. IBM Granite 4.0-H-350M: Outright Leader
- **Strengths:** 
  - 100% worker correctness (8/8).
  - Superior adherence to instructions without leaking schema placeholders.
  - Zero hallucinations and zero schema degradation.
  - State-of-the-art Mamba-2 / Transformer Hybrid architecture (`granitehybrid`) providing sub-400 ms inference with constant memory complexity.
  - 1,048,576 token context window in a 366 MB binary.
  - Apache 2.0 open-source license.
- **Weaknesses:** 
  - Marginally higher latency (+57 ms) than LFM2.5-350M.

### 2. Liquid AI LFM2.5-350M: High-Speed Pure Extractor
- **Strengths:**
  - Fastest worker in the battery: 326.8 ms mean latency.
  - Perfect performance on structured arguments, filters, format conversions, and negation preservation (Cases 01, 02, 03, 04, 10, 19, 20).
- **Weaknesses:**
  - Struggles with free-form micro-rewrites (Case 15), tending toward aggressive over-summarization that loses specified entity fields.

### 3. Google Gemma 3 270M-IT: Smallest Footprint & Strong Synthesis
- **Strengths:**
  - Smallest model tested: 268M parameters, 291 MB on disk.
  - Produced the most fluent and complete natural language sentence on Case 15.
  - Perfect on negation preservation and structured schema population.
- **Weaknesses:**
  - Susceptible to "placeholder inertia" on simple extraction tasks (echoing `<filename>` in Cases 01 & 02).
  - Exhibited synthetic field hallucination in Case 02.
  - Slower inference (463.4 ms mean) than Granite and LFM despite smaller size.

### 4. Hugging Face SmolLM2-360M-Instruct: Not Production Ready for URI Edge
- **Strengths:**
  - Successfully handled straightforward tabular metadata (Case 10) and negation tagging (Cases 19 & 20).
- **Weaknesses:**
  - Severe schema collapse: fell into infinite recursive generation loops on Cases 02 & 03.
  - Echoed placeholder strings on Cases 01 and 15.
  - Largest disk footprint (725 MB F16) and highest latency (848.8 ms p95).

---

## 6. Deployment Recommendations for URI Edge

### Recommendation for `MOBILE_EDGE` (Smartphones, Wearables, Low-Power IoT)
* **Primary Recommendation: IBM Granite 4.0-H-350M (`granite4:350m-h`)**
  * **Rationale:** At 366 MB, Granite 4.0-H fits comfortably within constrained mobile RAM allocations (< 512 MB). Its Mamba-2 hybrid backbone eliminates the quadratic KV-cache growth typical of edge transformers, preserving battery life and thermal headroom during prolonged multi-turn sessions. It achieved 100% accuracy on bounded edge operations.
  * **Fallback / Extreme Resource Constraint: Gemma 3 270M-IT**
    * For devices with strictly < 300 MB available for model weights, Gemma 3 270M-IT (291 MB) provides a viable fallback, provided extraction capsules use few-shot exemplars rather than `<placeholder>` syntax to suppress placeholder inertia.

### Recommendation for `OFFICE_PC_EDGE` (Desktop / Laptop Second-Brain)
* **Primary Recommendation: Dual-Engine Edge Cluster (Granite 4.0-H-350M + Needle 3.0.2)**
  * **Rationale:** On office PCs and development workstations, running Granite 4.0-H-350M alongside Needle 3 consumes negligible system resources (~700 MB RAM combined), offloading 50% of user turns from resident models while guaranteeing sub-600 ms p95 response times.
  * Granite 4.0-H completely eliminates the false candidate claims (90% $\rightarrow$ 0%) that plagued standalone models like Qwen3.5-0.8B, while maintaining a 100% containment record (`FALSE_VERIFIED_SUCCESS == 0`).

---

## 7. Governance & Architectural Confirmation

- **Deterministic & Safe:** The runtime validator, authorization gates, and verifier maintained 100% authority. No model proposal was permitted to bypass validation.
- **Critical Safety Invariant:** Across all 120 model executions (30 cases × 4 candidate models), `FALSE_VERIFIED_SUCCESS == 0` was preserved without exception.
- **Terminology:** Resident models (e.g., Qwen3.5-9B) remain strictly designated as *resident reference/capable models*, distinct from the Main Brain release authority.
- **Release Status:** All changes and benchmark scripts remain in the local experiment directory; zero git commits or pushes have been performed.
