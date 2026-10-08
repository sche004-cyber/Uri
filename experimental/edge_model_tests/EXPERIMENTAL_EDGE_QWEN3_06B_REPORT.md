# URI Edge Ultra-Light Worker Benchmark Report: Qwen3-0.6B vs. IBM Granite 4.0-H-350M

**Date:** 2026-09-28  
**Candidate Model Evaluated:** **Qwen3-0.6B** (`qwen3:0.6b`, Ollama ID `7df6b6e09427`, Q4_K_M, 751.63M parameters, 522 MB on disk)  
**Reference Leader:** **IBM Granite 4.0-H-350M** (`granite4:350m-h`, Ollama ID `7145075ed3d6`, Q8_0, 340.33M parameters, 366 MB on disk)  
**Evaluation Scope:** Canonical 30-case battery (GPU and CPU modes) and a separate 7-case Supplementary Bounded Worker Challenge Set.  
**Critical Safety Invariant:** **`FALSE_VERIFIED_SUCCESS = 0`** maintained across all test executions.

---

## 1. Executive Summary & Decision

### Final Recommendation: **`KEEP_GRANITE350`**

While Qwen3-0.6B matches Granite 4.0-H-350M's **8/8 (100.0%)** score on the canonical worker subset when internal reasoning is suppressed, it **fails to demonstrate any capability, latency, or resource advantage** over Granite:
1. **Supplementary Challenge Discrimination:** When stressed with the 7-case supplementary bounded challenge set, Granite 4.0-H-350M achieved **5/7 (71.4%)**, while Qwen3-0.6B collapsed to **2/7 (28.6%)**, suffering from entity prefix truncation, currency symbol drops, and schema placeholder leakage.
2. **Resource Footprint:** Qwen3-0.6B is **42.6% larger on disk** (522 MB vs 366 MB) and requires **~43% more process RAM** (~668 MB vs ~466 MB RSS).
3. **Cold Start & Latency:** Qwen3-0.6B requires **2,104.7 ms** to load from disk into memory (nearly **4x slower** than Granite's 532.3 ms). On CPU, Qwen3-0.6B's warm mean latency is **817.4 ms** (p95: **1,693.3 ms**) compared to Granite's **700.0 ms** (p95: **831.7 ms**).

Therefore, Granite 4.0-H-350M remains the undisputed leading ultra-light candidate model for URI's Second-Brain Edge Worker role.

---

## 2. Model Profiles & Hardware Telemetry

| Property | IBM Granite 4.0-H-350M (Reference) | Qwen3-0.6B (Candidate) | Delta / Ratio |
| :--- | :--- | :--- | :---: |
| **Model Tag / Digest** | `granite4:350m-h` (`7145075ed3d6`) | `qwen3:0.6b` (`7df6b6e09427`) | — |
| **Architecture** | Mamba-2 / Transformer Hybrid (`granitehybrid`) | Dense Transformer (`qwen3`) | Linear vs Quadratic |
| **Parameter Count** | 340.33M | 751.63M (nominally 0.6B) | +120.8% |
| **Quantization** | Q8_0 | Q4_K_M | — |
| **Context Window** | 1,048,576 (1M) | 40,960 (40K) | — |
| **Binary Size on Disk**| **366 MB** | **522 MB** | +42.6% |
| **Cold Model Load Time**| **532.3 ms** | **2,104.7 ms** | **3.95x slower load** |
| **Cold Total Call Latency**| **1,232.9 ms** | **2,588.8 ms** | 2.10x slower |
| **Process Working Set (RSS)**| **466.5 MB** initial / 774.7 MB peak | **668.0 MB** initial / 820.0 MB peak | +43.2% RAM |
| **Process Threads (`llama-server`)**| 42 threads | 34 threads | — |
| **CPU Utilization (Inference)**| 27.3% | 20.0% | Both leave >70% idle |
| **Thinking Mode Override**| Native direct JSON (no thinking loop) | **Requires `"think": false`** (otherwise loops) | Risk of token exhaustion |

---

## 3. Performance on Canonical 30-Case Battery

Across the canonical battery, Qwen3-0.6B was tested in both Accelerated GPU mode (AMD Radeon RX 7900 GRE) and Pure CPU mode (`num_gpu: 0`):

| Evaluation Metric | Granite 4.0-H (GPU) | Granite 4.0-H (CPU) | Qwen3-0.6B (GPU) | Qwen3-0.6B (CPU) |
| :--- | :---: | :---: | :---: | :---: |
| **Worker Tasks Admitted** | 8 | 8 | 8 | 8 |
| **Worker Correctness** | **8 / 8 (100.0%)** | **8 / 8 (100.0%)** | **8 / 8 (100.0%)** | **8 / 8 (100.0%)** |
| **Verified Worker Successes** | 8 | 8 | 8 | 8 |
| **False Candidate Claims** | 0 | 0 | 0 | 0 |
| **False Verified Successes** | **0 (`INVARIANT`)** | **0 (`INVARIANT`)** | **0 (`INVARIANT`)** | **0 (`INVARIANT`)** |
| **Full System Accuracy (30 cases)**| 29 / 30 (96.7%) | 29 / 30 (96.7%) | 29 / 30 (96.7%) | 29 / 30 (96.7%) |
| **Worker Latency: Min** | 356.7 ms | 521.0 ms | **323.8 ms** | 578.9 ms |
| **Worker Latency: Mean** | **384.3 ms** | **700.0 ms** | 393.0 ms | 817.4 ms |
| **Worker Latency: Median** | 375.9 ms | **706.0 ms** | **364.0 ms** | 707.8 ms |
| **Worker Latency: p95** | **414.4 ms** | **831.7 ms** | 560.4 ms | 1,693.3 ms |
| **Worker Latency: Max** | **414.4 ms** | **831.7 ms** | 560.4 ms | 1,693.3 ms |
| **Full Turn Latency: Mean** | **131.9 ms** | **225.8 ms** | 141.8 ms | 254.6 ms |
| **Full Turn Latency: p95** | **581.9 ms** | **1,007.5 ms** | 668.6 ms | 1,446.6 ms |

*Note: In all runs, `CASE_18_NEGATION` was safely escalated by Needle 3 due to ungrounded `"delete"` operations, yielding 29/30 maximum attainable full-system accuracy.*

---

## 4. Supplementary Worker Challenge Set: Direct Discrimination

Because both models achieved 8/8 on the standard worker subset, a separate 7-case supplementary challenge battery was executed to evaluate entity preservation, currency formatting, multi-attribute extraction, distractor robustness, and dual negation.

| Case ID & Challenge Focus | IBM Granite 4.0-H-350M | Qwen3-0.6B | Discriminator Analysis |
| :--- | :---: | :---: | :--- |
| **SUPP_01: Multi-Entity Retention**<br>(Ticket, Customer, Agent, Priority) | **PASS** (2,241.8 ms)<br>`ticket: "TKT-409"` | **FAIL** (828.7 ms)<br>`ticket: "409"` | **Qwen truncated the entity prefix** (`TKT-` dropped), corrupting the identifier. Granite preserved exact entity. |
| **SUPP_02: Date, Currency, & ID**<br>(`TX-88219`, `2026-04-15`, `$1,420.50`) | **PASS** (440.2 ms)<br>`amount: "$1,420.50"` | **FAIL** (983.8 ms)<br>`amount: "1,420.50"` | **Qwen stripped the currency symbol**, failing exact normalization. Granite retained currency token. |
| **SUPP_03: Dual Negation**<br>(1 requested, 2 simultaneous prohibitions) | **FAIL (Soft)** (413.0 ms)<br>`"summarize user telemetry"` | **FAIL** (759.8 ms)<br>`["<op>"]`, `["<op1>", "<op2>"]` | **Qwen leaked template placeholders literally**. Granite grounded both prohibited operations cleanly. |
| **SUPP_04: Multi-Arg Extraction**<br>(File + 4 distinct filter attributes) | **PASS** (458.9 ms)<br>All 4 filters exact | **PASS** (1,021.8 ms)<br>All 4 filters exact | Both models passed; Granite was **2.2x faster**. |
| **SUPP_05: Distractor Robustness**<br>(Extraction amidst conversational noise) | **PASS** (395.4 ms)<br>`server_node_9`, `ERR_CONN_RESET` | **FAIL** (642.2 ms)<br>Dropped `"decision": "LOCAL"` | **Qwen dropped the outer schema envelope** under distractor pressure. Granite preserved schema structure. |
| **SUPP_06: Complex Filename**<br>(Spaces & multiple dots in filename) | **PASS** (391.2 ms)<br>Exact string | **PASS** (655.2 ms)<br>Exact string | Both models grounded the complex filename cleanly. |
| **SUPP_07: Exact 4-Field Rewrite**<br>(Dr. Patel, #774-B, 2026-09-01, Cleared) | **FAIL (Soft)** (445.2 ms)<br>`"decision": "CLEARED"` | **FAIL** (959.8 ms)<br>2 sentences generated | **Qwen violated the 1-sentence limit**. Granite retained all 4 fields (soft fail on schema key name). |
| **Overall Supplementary Score** | **5 / 7 (71.4%)** | **2 / 7 (28.6%)** | **Granite decisively outperforms Qwen3-0.6B on bounded robustness.** |

---

## 5. Architectural & Operational Insights

### A. The "Thinking Mode" Operational Hazard
Qwen3-0.6B is natively fine-tuned with a `<think> ... </think>` reasoning capability. When prompted with standard schema parameters, Qwen3-0.6B attempts to produce conversational chain-of-thought tokens. If `"think": false` is omitted:
- It exhausts the `num_predict: 150` token budget inside the `<think>` block, outputting an empty `""` JSON payload (`done_reason: length`).
- For a lightweight second-brain worker, this represents an operational vulnerability unless strict API wrappers enforce reasoning suppression.
- In contrast, Granite 4.0-H-350M requires zero parameter gymnastics; it natively generates direct JSON.

### B. Mamba-2 Hybrid vs. Dense Transformer on CPU
- **Granite 4.0-H-350M** utilizes a Mamba-2 / Transformer hybrid architecture (`granitehybrid`), resulting in constant recurrent state size and low memory bandwidth pressure. On CPU, its p95 latency remains tightly capped at **831.7 ms**.
- **Qwen3-0.6B** is a dense transformer. On CPU, its prompt evaluation phase is significantly heavier, causing p95 turn latency to spike to **1,693.3 ms** (nearly 1.7 seconds).

---

## 6. Tier-by-Tier Suitability Assessment

| Deployment Tier | IBM Granite 4.0-H-350M | Qwen3-0.6B | Assessment & Recommendation |
| :--- | :---: | :---: | :--- |
| **MOBILE_EDGE**<br>(Smartphones, Wearables, IoT) | **Leading Candidate** (366 MB, 532ms load, hybrid low-power) | **Unsuitable** (522 MB, 2.1s load, high battery/RAM draw) | Granite is vastly superior for mobile edge due to memory and thermal efficiency. |
| **OFFICE_PC_EDGE**<br>(Intel i7-11700, 16GB, Integrated UHD 750) | **Leading Candidate** (700ms CPU mean, 831ms p95, <800MB RAM) | **Marginal / Sub-Optimal** (817ms CPU mean, 1.7s p95, >800MB RAM) | Granite maintains sub-second p95 responsiveness on CPU. Qwen suffers from high variance and slower load. |
| **HOME_PC_EDGE**<br>(Desktop with Dedicated GPU, e.g. RTX/Radeon) | **Leading Candidate** (384ms GPU mean, 414ms p95) | **Viable Candidate** (393ms GPU mean, 560ms p95) | Qwen3-0.6B is viable when GPU acceleration is present, but provides no capability advantage over Granite. |

---

## 7. Governance & Architectural Confirmation

- **Critical Safety Invariant:** **`FALSE_VERIFIED_SUCCESS = 0`** maintained across all 60 canonical battery cases and 14 supplementary probe executions. The independent URI Verifier caught 100% of candidate failures.
- **Terminology:** Resident models (e.g., Qwen3.5-9B) remain strictly designated as *resident reference/capable models*, distinct from the Main Brain release authority.
- **Release Status:** No production code or frozen contracts have been altered. Zero git commits or pushes have been performed.
