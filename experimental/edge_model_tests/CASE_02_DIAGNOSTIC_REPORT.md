# Focused Diagnostic Report: CASE_02 Intent Extraction Bias vs Capability

**Document ID:** `DIAG-CASE02-2026-09-28-01`  
**Date:** 2026-09-28  
**Author:** Antigravity (Gemini 3.8 Flash)  
**Status:** DIAGNOSTIC_ANALYSIS_ONLY  
**Branch:** `m35-uri-v1-parallel-architecture`  
**Task Under Test:** `CASE_02_INTENT`: *"Calculate total revenue for Q3 from revenue.csv"*  
**Target:** `revenue.csv` | **Expected Intent:** `CALCULATE`  
**Candidates Evaluated:** LiquidAI LFM2.5-350M (LM Studio Q8_0) & Qwen3.5-0.8B (Ollama Q8_0)  
**Resident Reference Model Note:** Qwen3.5-9B is a resident reference/capable model, not the Main Brain.  
**Safety Invariant:** `FALSE_VERIFIED_SUCCESS == 0` (authoritatively maintained)

---

## 1. Diagnostic Objective & Setup

In prior combination benchmarks, both **LFM2.5-350M** and **Qwen3.5-0.8B** failed `CASE_02_INTENT` by outputting `intent: "EXTRACT"` instead of `intent: "CALCULATE"`, despite the task clearly requesting: *"Calculate total revenue for Q3 from revenue.csv"*.

The objective of this focused diagnostic is to isolate the root cause:
- **Hypothesis A (Schema/Order Bias):** The tiny models latched onto `"EXTRACT"` because it was presented as the first literal option in the pipe-delimited pseudo-schema (`"intent": "EXTRACT"|"CALCULATE"`).
- **Hypothesis B (Capability Limitation):** The models lack the semantic comprehension to distinguish calculation/aggregation from direct value extraction.

### Controlled Invariants
- Task wording: *"Calculate total revenue for Q3 from revenue.csv"* (unchanged)
- Expected output: `{"decision": "LOCAL", "intent": "CALCULATE", "target": "revenue.csv"}` (unchanged)
- Routing, Needle 3 logic, temperature (`0.0`), runtime settings: unchanged
- Authoritative Verifier: `EdgeTaskVerifier` (unchanged)
- Consistency: 3 deterministic repeats per variant at `temperature=0.0`.

---

## 2. Experimental Variants Tested

1. **Variant 1 (Current Order):**  
   Schema: `{"decision": "LOCAL", "intent": "EXTRACT"|"CALCULATE", "target": "<filename>"}`  
   Instruction: *"Extract the exact intent and target filename."*
2. **Variant 2 (Reversed Order):**  
   Schema: `{"decision": "LOCAL", "intent": "CALCULATE"|"EXTRACT", "target": "<filename>"}`  
   Instruction: *"Extract the exact intent and target filename."*
3. **Variant 3 (Definitions + Current Order):**  
   Schema: `{"decision": "LOCAL", "intent": "EXTRACT"|"CALCULATE", "target": "<filename>"}`  
   Instruction with explicit definitions:
   - `EXTRACT`: read/select an existing value without deriving a new result
   - `CALCULATE`: derive a new numeric result from provided data
4. **Variant 4 (Definitions + Reversed Order):**  
   Schema: `{"decision": "LOCAL", "intent": "CALCULATE"|"EXTRACT", "target": "<filename>"}`  
   Instruction with explicit definitions:
   - `EXTRACT`: read/select an existing value without deriving a new result
   - `CALCULATE`: derive a new numeric result from provided data
5. **Variant 5 (Neutral List + String Schema):**  
   Schema: `{"decision": "LOCAL", "intent": string, "target": "<filename>"}`  
   Instruction with options list `['CALCULATE', 'EXTRACT']` and explicit definitions.

---

## 3. Diagnostic Results Matrix

All 3 runs per variant were 100% deterministic (identical outputs across repeats at `temp=0.0`).

### 3.1 LiquidAI LFM2.5-350M (LM Studio Q8_0)

| Variant | Schema / Prompt Presentation | Emitted Intent | Verifier Decision | Correct? | Mean Latency | Order Sensitive? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **V1 (Current)** | `"intent": "EXTRACT" \| "CALCULATE"` | `EXTRACT` | `REJECT` | ❌ No | 344.1 ms | Baseline |
| **V2 (Reversed)** | `"intent": "CALCULATE" \| "EXTRACT"` | `CALCULATE` | **`VERIFIED_LOCAL_SUCCESS`** | ✅ **Yes** | 314.7 ms | **FLIPPED** |
| **V3 (Def + Current)** | Defs + `"EXTRACT" \| "CALCULATE"` | `EXTRACT` | `REJECT` | ❌ No | 312.7 ms | Followed schema |
| **V4 (Def + Reversed)** | Defs + `"CALCULATE" \| "EXTRACT"` | `CALCULATE`* | `ESCALATE`* | ❌ No* | 322.0 ms | **FLIPPED** |
| **V5 (Neutral List)** | Defs + `['CALCULATE', 'EXTRACT']` | `EXTRACT` | `REJECT` | ❌ No | 313.0 ms | Followed def order |

*\*Note on V4:* In V4, LFM correctly selected `intent: "CALCULATE"`, but also copied `CALCULATE` into the `decision` field (`"decision": "CALCULATE"`), causing the verifier to classify it as an ungrounded non-LOCAL decision (`refused_safe_local_task`).

---

### 3.2 Qwen3.5-0.8B (Ollama Q8_0)

| Variant | Schema / Prompt Presentation | Emitted Intent | Verifier Decision | Correct? | Mean Latency | Order Sensitive? |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **V1 (Current)** | `"intent": "EXTRACT" \| "CALCULATE"` | `EXTRACT` | `REJECT` | ❌ No | 1302.1 ms (cold) / 438 ms | Baseline |
| **V2 (Reversed)** | `"intent": "CALCULATE" \| "EXTRACT"` | `CALCULATE` | **`VERIFIED_LOCAL_SUCCESS`** | ✅ **Yes** | 435.6 ms | **FLIPPED** |
| **V3 (Def + Current)** | Defs + `"EXTRACT" \| "CALCULATE"` | `EXTRACT` | `REJECT` | ❌ No | 395.4 ms | Followed schema |
| **V4 (Def + Reversed)** | Defs + `"CALCULATE" \| "EXTRACT"` | `EXTRACT` | `REJECT` | ❌ No | 441.9 ms | Latched to defs |
| **V5 (Neutral List)** | Defs + `['CALCULATE', 'EXTRACT']` | `EXTRACT`* | `ESCALATE`* | ❌ No* | 392.3 ms | Schema bleed |

*\*Note on V5:* In V5, Qwen recognized the calculation semantics by setting `"decision": "CALCULATE"`, but output `"intent": "EXTRACT"`, showing context distraction under longer definitions.

---

## 4. Key Findings & Analysis

### Finding 1: Pure Positional / Schema Ordering Bias Confirmed (V1 vs V2)
When presented with the simple task capsule:
- **Variant 1 (`"EXTRACT"|"CALCULATE"`):** Both LFM2.5-350M and Qwen3.5-0.8B emitted `EXTRACT` in 100% of runs.
- **Variant 2 (`"CALCULATE"|"EXTRACT"`):** Both LFM2.5-350M and Qwen3.5-0.8B emitted `CALCULATE` in 100% of runs, achieving **`VERIFIED_LOCAL_SUCCESS`**.

**Conclusion:** Without changing a single word of the user task (*"Calculate total revenue for Q3 from revenue.csv"*), merely flipping the token order in the schema string reversed the output for both models. This demonstrates that tiny models operating under greedy decoding (`temperature=0.0`) have a severe recency/prefix bias towards the first literal enum token in pipe-delimited schema strings.

### Finding 2: Fragility Under Multi-Sentence Definition Prompts (V3, V4, V5)
When multi-line definitions were injected into the instruction:
1. Both models showed sensitivity to which definition was listed first (`EXTRACT` was defined first in the prompt text).
2. The extra tokens diluted schema adherence: in V4 (LFM) and V5 (Qwen), the models exhibited schema bleed, copying `CALCULATE` into the `"decision"` field instead of leaving `"decision": "LOCAL"`.
3. Adding verbose definitions to tiny models (350M–800M) introduces noise and prompt distraction rather than semantic clarity.

---

## 5. Formal Diagnostic Classification

Per the diagnostic decision criteria:

$$\mathbf{PRIMARY\_CLASSIFICATION:\; SCHEMA\_AND\_ORDER\_PRESENTATION\_BIAS}$$
$$\mathbf{SECONDARY\_CLASSIFICATION:\; PROMPT\_DISTRACTION\_UNDER\_VERBOSE\_DEFINITIONS}$$

### Explicit Answers to Diagnostic Inquiries
1. **Did output change when enum order changed?**  
   **Yes, completely and deterministically.** In both LFM2.5-350M and Qwen3.5-0.8B, flipping `"EXTRACT"|"CALCULATE"` to `"CALCULATE"|"EXTRACT"` converted `CASE_02` from a rejected failure to `VERIFIED_LOCAL_SUCCESS`.
2. **Did neutral definitions consistently produce `CALCULATE`?**  
   **No.** Adding definitions introduced competing cues and field bleed (`"decision": "CALCULATE"`), indicating that verbose definitions in tiny generalists degrade structured JSON fidelity.
3. **Is this a model capability limitation or a capsule design flaw?**  
   **It is primarily a task capsule design flaw.** The use of inline pipe-separated strings (`"EXTRACT"|"CALCULATE"`) in minimal JSON schemas creates an unintended positional default. Tiny models (350M–800M) lack the logits mass to overcome the strong prefix prior of the first listed token.

---

## 6. Actionable Capsule Improvement Recommendations

Rather than escalating to larger models (such as the resident capable Qwen3.5-9B), the task capsule design should be improved for tiny Edge generalists:

1. **Eliminate Pseudo-Regex Pipe Enums in Example JSON:**  
   Replace `"intent": "EXTRACT"|"CALCULATE"` with a dedicated tool parameter or a schema array where no option appears as the inline value.
2. **Grammar / Constrained Decoding at the Runtime Level:**  
   In production, pass true JSON schemas (e.g. via Ollama `format: {schema...}` or LM Studio structured output `response_format`) rather than loose in-prompt JSON templates.
3. **Task-Specific Intent Gating by Needle 3:**  
   Because Needle 3 is a specialized decision model, Needle can pre-filter whether a turn is an `extraction` or an `aggregation/calculation` during Step 1 dispatch, providing a single unambiguous target schema to the bounded worker.

---

## 7. Artifact Summary

- [`case_02_diagnostic.py`](file:///c:/Users/cheta/Development/Uri/_V1/experimental/edge_model_tests/case_02_diagnostic.py): Reproducible test harness executing all 5 variants across both models with 3 repeats.
- [`case_02_diagnostic_results.json`](file:///c:/Users/cheta/Development/Uri/_V1/experimental/edge_model_tests/case_02_diagnostic_results.json): Full raw outputs, timestamps, latencies, and verifier records.
- [`CASE_02_DIAGNOSTIC_REPORT.md`](file:///c:/Users/cheta/Development/Uri/_V1/experimental/edge_model_tests/CASE_02_DIAGNOSTIC_REPORT.md): This report.
