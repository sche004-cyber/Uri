# M35 — Batch A2.1: Needle 3 Narrow-Schema Semantic Qualification — Report

## 1. Branch / HEAD / Worktree

- Worktree: `C:\Users\cheta\Development\Uri\_V1`
- Branch: `m35-uri-v1-parallel-architecture`
- Git HEAD: `e8e3b65259c45fc823addc3ef8969425a265bd1b` (strictly uncommitted — nothing committed or pushed)
- Protected prototype worktree: `C:\Users\cheta\Development\uri-agent` verified completely untouched before, during, and after this batch (`git status --short` still shows the exact same 65 protected paths, `git log -1` still `e8e3b65`).

---

## 2. Files Changed

All new/modified files live strictly inside `C:\Users\cheta\Development\Uri\_V1`:

```text
uri_v1/turn/needle_narrow.py             (new — narrow schema definitions, dataclasses, normalizers, extraction harness)
uri_v1/turn/needle_merge.py              (new — deterministic merger from narrow results to DecodedRequest)
uri_v1/turn/needle_decoder.py            (modified — generalized decode() signature with default fallback)
uri_v1/turn/__init__.py                  (modified — re-exported new Batch A2.1 symbols)
test_m35_uriv1_a2_1_needle_narrow.py     (new — 20 synthetic unit tests)
test_m35_uriv1_a2_1_needle_narrow_live.py(new — 7 live inference qualification tests)
scripts/m35_needle_narrow_probe.py       (new — 72-turn live qualification probe script)
scripts/narrow_qualification_results.json(new — full raw qualification telemetry output)
scripts/audit_semantic_accuracy.py       (new — evaluation audit helper)
docs/plans/M35_URIV1_A2_1_NEEDLE_NARROW_REPORT.md (this file)
```

`uri_v1/turn/contracts.py` and `uri_v1/turn/decoder.py` were **not modified** — the deep-frozen `DecodedRequest` contract remained untouched.

---

## 3. Narrow Schemas A / B / C / D

Four independent, minimal, flat JSON schemas were defined:

### Schema A: Goal / Intent (`extract_goal`)
```json
{
  "name": "extract_goal",
  "description": "Always call this exactly once to extract the primary goal and intent family of the current message.",
  "parameters": {
    "type": "object",
    "properties": {
      "goal": {"type": "string", "description": "One concise phrase stating the user's intended outcome."},
      "intent_family": {"type": "string", "enum": ["retrieve","create","modify","communicate","execute","analyze","compare","research","navigate","converse","unspecified"]}
    },
    "required": ["goal"],
    "additionalProperties": false
  }
}
```

### Schema B: Operations / Negation (`extract_operations`)
```json
{
  "name": "extract_operations",
  "description": "Always call this exactly once to extract requested and prohibited operations from the current message.",
  "parameters": {
    "type": "object",
    "properties": {
      "requested_operations": {"type": "array", "items": {"type": "string"}, "description": "Operations or actions requested by the user."},
      "prohibited_operations": {"type": "array", "items": {"type": "string"}, "description": "Operations or actions explicitly prohibited, forbidden, or negated by the user."}
    },
    "required": ["requested_operations", "prohibited_operations"],
    "additionalProperties": false
  }
}
```

### Schema C: References / Temporal Expressions (`extract_references`)
```json
{
  "name": "extract_references",
  "description": "Always call this exactly once to record unresolved references and temporal expressions.",
  "parameters": {
    "type": "object",
    "properties": {
      "references": {"type": "array", "items": {"type": "string"}, "description": "Unresolved referring expressions (pronouns like 'this', 'that', phrases like 'that file'). Do not resolve them."},
      "temporal_references": {"type": "array", "items": {"type": "string"}, "description": "Temporal expressions mentioned in the text (e.g. 'yesterday', 'tomorrow')."}
    },
    "required": ["references", "temporal_references"],
    "additionalProperties": false
  }
}
```

### Schema D: Constraints / Output Preferences (`extract_constraints`)
```json
{
  "name": "extract_constraints",
  "description": "Always call this exactly once to extract explicit constraints and output preferences.",
  "parameters": {
    "type": "object",
    "properties": {
      "constraints": {
        "type": "object",
        "properties": {
          "included_items": {"type": "array", "items": {"type": "string"}},
          "excluded_items": {"type": "array", "items": {"type": "string"}},
          "length_limit": {"type": "string"},
          "language_constraints": {"type": "string"}
        }
      },
      "output_preferences": {
        "type": "object",
        "properties": {
          "artifact_type": {"type": "string"},
          "tone": {"type": "string"},
          "audience": {"type": "string"},
          "language": {"type": "string"},
          "language_variant": {"type": "string"},
          "length": {"type": "string"},
          "structure": {"type": "string"}
        }
      }
    },
    "required": ["constraints", "output_preferences"],
    "additionalProperties": false
  }
}
```

---

## 4. Rationale for Each Schema

- **Schema A (Goal / Intent)**: Isolates the core intent of the turn into a 2-field extraction without distracting the model with lists of operations, constraints, or reference resolution. Tests whether Needle can classify intent when unburdened by broader schema syntax.
- **Schema B (Operations / Negation)**: Directly targets Batch A2's primary puzzle: Needle's internal negation detector fired on all negative cases, but never propagated into structured output under the 9-field schema. Isolating requested vs. prohibited operations directly tests whether the negation signal can surface into structured output.
- **Schema C (References / Temporal)**: Directly targets the 0% reference capture rate observed in A2. Tests whether Needle can extract referring expressions (pronouns, noun phrases) and temporal expressions without asking it to resolve them or reason about execution.
- **Schema D (Constraints / Preferences)**: Isolates formatting, audience, and scope boundaries so the model does not have to balance operational verbs with stylistic constraints.

All schemas strictly exclude tool names, capability IDs, Graphify concepts, provider names, routing choices, execution plans, and Edge decisions.

---

## 5. Live Qualification Prompt Set

The standard battery of 18 prompts was evaluated across all 4 extractors (72 live inferences total):

### Required Prompts (10)
- **R1**: "Convert this to PDF."
- **R2**: "Bring that file up."
- **R3**: "Do the same thing for them."
- **R4**: "Don't send it. Just draft the email."
- **R5**: "Find the previous approval, compare it with this one and draft a revised order."
- **R6**: "The committee has already changed its view twice and the latest letter doesn't seem to match what was decided earlier. I need something I can put up tomorrow."
- **R7**: "Compare only the 2025 and 2026 decisions, do not use anything before 2025, and keep the result under one page."
- **R8**: "Draft a short formal email in Indian English to the Chief Warden."
- **R9**: "Do not summarize this; compare the exact figures in a table."
- **R10**: "What was approved yesterday?"

### Stress Prompts (8)
- **S1**: "Hello"
- **S2**: "Thanks"
- **S3**: "Open calculator."
- **S4**: "Don't open it yet."
- **S5**: "Send it to him after they approve it."
- **S6**: "Compare the attached PDF with this spreadsheet."
- **S7**: "Make something I can submit tomorrow."
- **S8**: "No, I meant the earlier one."

---

## 6. Per-Schema Structural Success

Structural success requires Needle to emit valid function call syntax that can be normalized without throwing structural decode errors:

| Extractor | Required (n=10) | Stress (n=8) | Total (n=18) | Structural Success % |
|---|---|---|---|---|
| **Schema A (Goal)** | 6 / 10 | 8 / 8 | 14 / 18 | 77.8% |
| **Schema B (Operations)** | 6 / 10 | 7 / 8 | 13 / 18 | 72.2% |
| **Schema C (References)** | 5 / 10 | 6 / 8 | 11 / 18 | 61.1% |
| **Schema D (Constraints)** | 4 / 10 | 8 / 8 | 12 / 18 | 66.7% |
| **Monolithic A2 Schema** | 4 / 10 | 3 / 8 | 7 / 18 | 38.9% |

**Observation**: Narrowing schemas marginally improved superficial *structural* compliance (from 38.9% to 61–77%), but structural success simply allowed the engine to emit calls. The crucial question is what was inside those calls.

---

## 7. Per-Schema Semantic Accuracy

Semantic accuracy evaluates whether the extracted fields match the actual meaning of the prompt:

| Extractor | Required (n=10) | Stress (n=8) | Total (n=18) | Semantic Accuracy % |
|---|---|---|---|---|
| **Schema A (Goal)** | 2 / 10 (20%) | 0 / 8 (0%) | 2 / 18 | **11.1%** |
| **Schema B (Operations)** | 0 / 10 (0%) | 0 / 8 (0%) | 0 / 18 | **0.0%** |
| **Schema C (References)** | 0 / 10 (0%) | 0 / 8 (0%) | 0 / 18 | **0.0%** |
| **Schema D (Constraints)** | 0 / 10 (0%) | 0 / 8 (0%) | 0 / 18 | **0.0%** |

### Schema A Semantic Breakdown
- **Severe Mode Collapse / Bias**: Needle collapsed into `intent_family: compare` on **13 of the 14 emitted calls** (92.8%), and `intent_family: retrieve` on the 14th. It never emitted `create`, `modify`, `communicate`, `execute`, `analyze`, `research`, `navigate`, or `converse`.
- S1 ("Hello") -> `goal: approval, family: compare`.
- S2 ("Thanks") -> `goal: compare, family: compare`.
- S3 ("Open calculator.") -> `goal: calculator, family: compare`.
- S4 ("Don't open it yet.") -> `goal: compare, family: compare`.
- R3 ("Do the same thing for them.") -> `goal: convert, family: retrieve` (hallucinating "convert" from prompt R1!).
- Only R7 ("Compare only 2025 and 2026...") and R9 ("compare exact figures...") received plausible intent classifications, solely because they happened to contain the word "compare".

---

## 8. Reference Accuracy (Strict Reference Gate)

The Strict Reference Gate mandates testing Schema C **without regex fallbacks, pronoun heuristics, or hardcoded tables**.

- Required cases needing unresolved reference capture: R1 ("this"), R2 ("that file"), R3 ("same thing", "them"), R4 ("it"), R5 ("this one", "previous approval"), R6 ("latest letter", "what was decided earlier").
- **Calls Declined**: R1, R2, R4, R5, R6 **ALL produced NO CALL** (`declined=True`, `calls=0`). Every single critical referring expression case was declined outright.
- **Hallucination & Repetition**: When Needle did emit calls (R7–R10, S1–S5), it entered a pathological token-repetition loop, emitting `refs: ["2025", "2026"], trefs: ["2025", "2026"]` on **every single one of them**:
  - R8 ("Draft a short formal email in Indian English to the Chief Warden.") -> `refs: ["2025", "2026"]`!
  - R9 ("Do not summarize this; compare the exact figures in a table.") -> `refs: ["2025", "2026"]`!
  - R10 ("What was approved yesterday?") -> `refs: ["2025", "2026"]`!
  - S1 ("Hello") -> `refs: ["2025", "2026"]`!
  - S8 ("No, I meant the earlier one.") -> `refs: ["2026", "2016", "2027"]`!
- **Unresolved-reference capture accuracy: 0 / 5 (0.0%)**.
- **Conclusion on Reference Gate: FAILED COMPLETELY.** Base Needle 3 is structurally and semantically incapable of reference extraction.

---

## 9. Negation Accuracy (Negation Gate)

The Negation Gate evaluated whether isolating requested vs. prohibited operations allows Needle's internal negation signal to surface into structured output:

- **R4 ("Don't send it. Just draft the email.")**: **NO CALL EMITTED** (`declined=True`, `confidence=1.0`). The canonical negation prompt was declined entirely.
- **R9 ("Do not summarize this; compare the exact figures in a table.")**: 1 call emitted, but `requested_operations: []`, `prohibited_operations: []`! Both the requested action ("compare") and prohibited action ("summarize") were completely omitted.
- **S4 ("Don't open it yet.")**: 1 call emitted, with:
  `requested_operations: ["open calculator"]`
  `prohibited_operations: ["draft the email"]`
  It hallucinated "open calculator" as requested, and hallucinated "draft the email" (from R4!) as prohibited!
- **Cross-Prompt Bleed-Through**:
  - R7 -> `requested: ["draft the email"], prohibited: ["2026"]`
  - S3 -> `requested: ["open calculator"], prohibited: ["draft the email"]`
  - S6 -> `requested: ["don't open it"], prohibited: ["open calculator"]`
  - S8 -> `requested: ["don't open it"], prohibited: ["open calculator"]`
- **Negation Recall**: **0 / 3 (0.0%)**.
- **Prohibited-Operation Precision**: **0.0%**.
- **Conclusion on Negation Gate: FAILED COMPLETELY.** Separating operations into narrow schemas did not unlock negation; it induced cross-prompt hallucination bleed-through.

---

## 10. Temporal Accuracy

- R6 ("tomorrow") -> **No call emitted** (0%).
- R10 ("What was approved yesterday?") -> Emitted `trefs: ["2025", "2026"]` instead of "yesterday" (0%).
- S7 ("submit tomorrow") -> **No call emitted** (0%).
- **Temporal extraction accuracy: 0.0%**.

---

## 11. Constraints and Output Preferences Accuracy

- In Schema D, R1 through R6 produced **0 calls** or empty records.
- On R7 through R10 and S1 through S8, Needle emitted corrupted tokens:
  - `length_limit: "10"` or `"12"`
  - `language_constraints: "F"` or `"Hello"`
  - `language: "F"`
  - `structure: None` (even for R9's explicit "table")
  - `tone: None` (even for R8's explicit "formal")
  - `audience: None` (even for R8's explicit "Chief Warden")
- **Constraint Accuracy**: **0.0%**.
- **Output Preference Accuracy**: **0.0%**.

---

## 12. No-Call Rates

Needle persistently declined to call the narrow tools:

| Extractor | Total Evaluated | Emitted Calls | Declined Calls | No-Call Rate |
|---|---|---|---|---|
| Schema A | 18 | 14 | 4 | **22.2%** |
| Schema B | 18 | 13 | 5 | **27.8%** |
| Schema C | 18 | 11 | 7 | **38.9%** |
| Schema D | 18 | 12 | 6 | **33.3%** |
| **Combined** | **72** | **50** | **22** | **30.6%** |

Across all narrow extraction calls, nearly **one out of every three calls** was declined outright.

---

## 13. Malformed-Call Rates

- Duplicate / multi-call rate: 0 / 72. (Narrow schemas successfully prevented the multi-call fragmentation observed in A2).
- Unparseable JSON rate: 0 / 72.
- Hallucinatory content rate in emitted arguments: 36 / 50 emitted calls (72.0%) contained hallucinated strings from other prompts or synthetic tokens (`"F"`, `"2025"`, `"2026"`).

---

## 14. Confidence Observations & Inversion Confirmation

The confidence inversion discovered in Batch A2 was **fully confirmed and reproduced** across all four narrow schemas:

- Mean confidence on declined calls:
  - Schema A: **0.9240** (Max: **1.0000**)
  - Schema B: **0.8501** (Max: **1.0000**)
  - Schema C: **0.7829** (Max: **1.0000**)
  - Schema D: **0.5451** (Max: **1.0000**)
- In multiple instances where Needle failed completely by declining to call an explicit tool (e.g. R1, R4 in Schema A; R1, R2, R4 in Schema B; R1, R2, R4, R5, R6 in Schema C), Needle reported confidence of **1.0000**.
- **Definitive Conclusion**: Needle's confidence score measures internal next-token certainty on the empty response, not task completion. **Needle confidence remains completely unsuitable for control flow or qualification.**

---

## 15. Latency per Extractor

Timing was measured end-to-end across the subprocess JSONL transport:

| Extractor | Cold Startup | Warm Min | Warm Median | Warm Max | Warm Mean |
|---|---|---|---|---|---|
| **Schema A** | 242.5 ms | 51.0 ms | 188.0 ms | 242.5 ms | 169.6 ms |
| **Schema B** | 266.9 ms | 60.5 ms | 220.8 ms | 333.4 ms | 204.1 ms |
| **Schema C** | 308.2 ms | 52.1 ms | 323.6 ms | 690.1 ms | 325.4 ms |
| **Schema D** | 341.2 ms | 77.5 ms | 287.9 ms | 813.0 ms | 341.7 ms |

---

## 16. Sequential Total Latency

Running the four narrow schemas sequentially ($A \rightarrow B \rightarrow C \rightarrow D$):

- **Mean Sequential Latency**: **1,036.8 ms (~1.04 seconds)**.
- **Median Sequential Latency**: **1,155.0 ms (~1.15 seconds)**.
- **Max Sequential Latency**: **1,379.6 ms (~1.38 seconds)** (Prompt S7).
- **Min Sequential Latency**: 254.8 ms (Prompt R4, fast only because 3 of the 4 calls declined instantly in under 60ms).

### Economic & Latency Verdict
Spending **1.0 to 1.4 seconds** of sequential edge runtime on Step 1 is fundamentally unacceptable for a reflex layer—especially when that 1 second yields 0% reference capture and 0% negation recall.

---

## 17. Parallel Feasibility

- Running 4 concurrent subprocesses or threads:
  - Theoretical latency bottleneck: $\max(A, B, C, D) \approx 325–340\text{ ms}$.
  - Memory cost: $4 \times 101\text{ MB} \approx 404\text{ MB}$ RAM footprint.
- **Feasibility Verdict**: Concurrency would consume ~400MB of RAM on the user's local device while still producing 0% semantic accuracy. Parallelization cannot fix model incapacity.

---

## 18. Deterministic Merge Result

- `merge_narrow_results` successfully executed on 18 of 18 prompt results without runtime errors.
- The merger preserved deep immutability, propagated attachments from `DecodeInput`, generated deterministic context dependencies for references, and maintained typed `DecodedRequest` contract validity.
- The merger strictly followed the zero-semantic-invention rule: missing fields from failed extractors remained empty or neutral.

---

## 19. Combined `DecodedRequest` Quality

Because the underlying narrow extractors failed semantically, the merged `DecodedRequest` payloads are critically degraded:
- **R3**: Goal was set to `"convert"` (from R1) and intent family to `retrieve`; references contained `"this"` (absent from prompt) and temporal contained `"tomorrow"` (absent from prompt).
- **R4**: No goal, no operations, no references (pure blank request).
- **R7**: Goal was `"compare"`, requested operation was `"draft the email"` (hallucinated), prohibited operation was `"2026"` (hallucinated), and constraints were empty.
- **R8**: No goal, references were `"2025"` and `"2026"` (hallucinated), and output preferences were blank.

Combined `DecodedRequest` quality is **0 / 10 usable for downstream URIv1 Step 2**.

---

## 20. Regressions

The complete test battery across all M35 batches was executed:

```powershell
python -m pytest test_m35_uriv1_a0_skeleton.py test_m35_uriv1_a1_decoded_request.py test_m35_uriv1_a1_1_contract_hardening.py test_m35_uriv1_a2_needle_decoder.py test_m35_uriv1_a2_needle_live.py test_m35_uriv1_a2_1_needle_narrow.py test_m35_uriv1_a2_1_needle_narrow_live.py
```

**Result:**
```text
============================= 86 passed in 30.49s =============================
```

- `test_m35_uriv1_a0_skeleton.py`: 7 passed
- `test_m35_uriv1_a1_decoded_request.py`: 15 passed
- `test_m35_uriv1_a1_1_contract_hardening.py`: 8 passed
- `test_m35_uriv1_a2_needle_decoder.py`: 25 passed
- `test_m35_uriv1_a2_needle_live.py`: 4 passed
- `test_m35_uriv1_a2_1_needle_narrow.py`: 20 passed
- `test_m35_uriv1_a2_1_needle_narrow_live.py`: 7 passed

Zero regressions across any previous batch.

---

## 21. Architecture Boundary Confirmation

- No imports or dependencies on `uri_core` were introduced.
- No Step 2 (Context Resolution), Graphify, ARN, or Edge execution code was written.
- `DecodeInput` carries only current-turn material (`raw_text` and `attachments`).
- All narrow schemas and normalized results are strictly semantic, with zero capability/tool IDs.

---

## 22. Final Recommendation

# **REJECT**

Base Needle 3 (generation 3, untuned weights) is **fundamentally unsuitable as the Step-1 Semantic Decoder** for URIv1.

### Evidence Summary:
1. **The Narrow Schema Hypothesis Failed**: Decomposing the 9-field schema into four narrow schemas (Goal, Operations, References, Constraints) did not unlock semantic extraction.
2. **Reference Gate Failed (0%)**: Needle cannot extract unresolved references or pronouns.
3. **Negation Gate Failed (0%)**: Separating requested and prohibited operations failed to surface negation, inducing cross-prompt hallucination.
4. **Persistent No-Call Behavior (30.6%)**: Needle frequently declines to call tools even under direct system prompt mandates.
5. **Confidence Inversion Confirmed**: Declining to call tools routinely reports confidence = `1.0`.
6. **Prohibitive Sequential Latency (~1,040 ms)**: Decomposed extraction costs >1 second of edge runtime for zero semantic yield.

---

## 23. Recommended Next Step-1 Candidate

Per the Batch A2.1 instructions:
- **Do NOT attempt further prompt engineering or schema hacking on base Needle 3.**
- **Do NOT build regex/heuristic crutches to prop up Needle.**
- **Evaluate the planned Local 2B–4B Agentic / Reasoning Model tier** (e.g. Qwen2.5-Coder-1.5B/3B, Gemma-2-2B, or SmolLM2-1.7B via llama.cpp / Ollama) as the concrete Step-1 Semantic Decoder.
- Needle may remain useful later as an auxiliary ultra-fast classifier, keyword matcher, or reflex gatekeeper, but cannot serve as the Step-1 semantic decoder.

---

## 24. Confirmation Original URI Untouched

- Worktree `C:\Users\cheta\Development\uri-agent` was checked with `git status --short`.
- Exactly 65 modified/untracked files as existed prior to M35.
- No files in `uri-agent` were modified, added, deleted, or committed.

---

## 25. Confirmation No Commit / Push Occurred

- Worktree `C:\Users\cheta\Development\Uri\_V1` was checked with `git log -1`.
- HEAD remains `e8e3b65259c45fc823addc3ef8969425a265bd1b`.
- All changes remain uncommitted and local. No git commit, push, merge, or PR occurred.
