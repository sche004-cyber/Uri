# M35 — Batch A2.2: Local Semantic Decoder Qualification — Installed Qwen Candidate — Report

## 1. Branch / HEAD / Worktree

- **Worktree**: `C:\Users\cheta\Development\Uri\_V1`
- **Branch**: `m35-uri-v1-parallel-architecture`
- **Git HEAD**: `e8e3b65259c45fc823addc3ef8969425a265bd1b` (strictly uncommitted)
- **Protected prototype**: `C:\Users\cheta\Development\uri-agent` confirmed completely untouched before, during, and after this batch (`git status --short` still shows the exact same 65 protected paths, `git log -1` still `e8e3b65`).

---

## 2. Candidate Model Verification

The model located in `C:\Users\cheta\.lmstudio\models\khazarai\Qwen3.8-max-Reasoning-Distilled-GGUF` was inspected prior to qualification:

- **Exact Filename**: `Qwen3.5-0.8B.Q8_0.gguf`
- **File Size**: `833,592,032 bytes` (833.59 MB)
- **Architecture**: `qwen35` (`Qwen3_5ForConditionalGeneration` with hybrid linear-attention SSM + full attention, 25 blocks)
- **Parameter Count**: `773M` (~0.8B parameters)
- **Quantization**: `Q8_0` (GGUF `file_type = 7`, quantized by Unsloth)
- **Context Capability**: `262,144 tokens` (256k context)
- **Tokenizer**: `gpt2` / `qwen35` with 248,320 vocab tokens, Jinja2 chat template
- **GGUF Metadata**:
  - `general.name`: `Unsloth_Gguf_Wzbqsw3K`
  - `general.size_label`: `773M`
  - `general.quantized_by`: `Unsloth`
- **Folder Name Discrepancy**: The folder name `Qwen3.8-max-Reasoning-Distilled-GGUF` originates from the Hugging Face repo path (`khazarai/Qwen3.8-max-Reasoning-Distilled-GGUF`). The model inside is **conclusively identified as the expected ~0.8B Q8_0 candidate** (`Qwen3.5-0.8B.Q8_0.gguf`).
- **Nature of Model**: This is a **Reasoning-Distilled** model. It natively generates internal thinking tokens (`reasoning_content`) before emitting final assistant text.

---

## 3. Runtime Environment & GPU Acceleration

- **Runtime**: LM Studio local server (`lms.exe` v0.3.40+) running on port 1234 (`http://127.0.0.1:1234/v1/chat/completions`).
- **Model Identifier**: `qwen-semantic-decoder` (model `qwen3.8-max-reasoning-distilled`).
- **Device Placement**: GPU-accelerated (`--gpu max`).
- **VRAM Usage**: **794.98 MiB** VRAM footprint.
- **Context Allocation**: 16,128 tokens in memory (parallel count = 4).
- **Transport**: `QwenLocalTransport` communicating over HTTP/JSON with OpenAI-compatible chat completions endpoint.

---

## 4. Structured Wire Schema Design

In accordance with Batch A2.2 Section 8, a single compact JSON wire format was defined in `uri_v1/turn/qwen_wire.py::QWEN_WIRE_SCHEMA`:

```json
{
  "type": "object",
  "properties": {
    "goal": {"type": "string"},
    "intent_family": {"type": "string", "enum": ["retrieve","create","modify","communicate","execute","analyze","compare","research","navigate","converse","unspecified"]},
    "requested_operations": {"type": "array", "items": {"type": "string"}},
    "prohibited_operations": {"type": "array", "items": {"type": "string"}},
    "prompt_supplied_context": {"type": "array", "items": {"type": "string"}},
    "constraints": {
      "type": "object",
      "properties": {
        "included_items": {"type": "array", "items": {"type": "string"}},
        "excluded_items": {"type": "array", "items": {"type": "string"}},
        "length_limit": {"type": "string"},
        "language_constraints": {"type": "string"}
      },
      "additionalProperties": false
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
      },
      "additionalProperties": false
    },
    "entities": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "category": {"type": "string"}}, "required": ["name"]}},
    "references": {"type": "array", "items": {"type": "string"}},
    "temporal_references": {"type": "array", "items": {"type": "string"}},
    "dependencies": {"type": "array", "items": {"type": "string"}},
    "ambiguities": {"type": "array", "items": {"type": "string"}}
  },
  "required": ["goal", "intent_family"],
  "additionalProperties": false
}
```

The schema and system prompt strictly exclude tool names, capability IDs, Graphify nodes, and routing terms.

---

## 5. Constrained vs. Unconstrained Mode Comparison (Section 9)

Both modes were evaluated across all 18 prompts:

| Mode | Structural Success | Parseable JSON | Adhered to Schema Keys |
|---|---|---|---|
| **Constrained Mode (`response_format: json_schema`)** | **17 / 18 (94.4%)** | 17 / 17 | 17 / 17 |
| **Unconstrained Mode (Plain JSON Prompting)** | **0 / 18 (0.0%)** | 17 / 18 | 0 / 18 |

### Unconstrained Mode Failure Analysis
In unconstrained mode, the 773M model **failed 100% of the time** to follow the requested schema:
- On R1 ("Convert this to PDF.") it invented its own schema:
  `{"conversion_type": "to_pdf", "input_text": "Convert this to PDF.", "output_format": "PDF document", "status": "ready"}`.
- On R4 ("Don't send it. Just draft the email.") it emitted requested operations and prohibited operations, but omitted `goal` and `intent_family` entirely.
- Across all 18 unconstrained prompts, it omitted the required `goal` field.
- **Finding**: For a 773M model, grammar/schema-constrained decoding is **strictly mandatory**.

---

## 6. Evaluation Dimensions (Section 11)

### 6.1 Goal Accuracy (~70%)
On short/direct prompts, Qwen captured the primary goal well:
- R1: `"Convert text to PDF"` (`create`)
- R2: `"Bring that file up"` (`retrieve`)
- R4: `"Draft an email"` (`create`)
- R7: `"Compare only decisions made in 2025 and 2026..."` (`compare`)
- R8: `"Draft a short formal email in Indian English (Hinglish) to the Chief Warden"` (`create`)
- R9: `"Compare exact figures in a table"` (`compare`)
- R10: `"Identify what was approved yesterday"` (`retrieve`)

**Critical Failure Modes**:
- **R6 (Token Exhaustion Failure)**: On the dense committee prompt, Qwen generated 600 reasoning tokens and exhausted its token limit before producing any content (`content = ""`, `reasoning_tokens = 600`).
- **R3**: `"Do the same thing for them."` -> Goal was `"Repeat your previous behavior pattern"` (meta-cognitive distortion).

---

### 6.2 Operations Accuracy & Negation Gate (~20%)
Qwen exhibited severe operational confusion:
1. **System Prompt Bleed-Through as Prohibitions**:
   In `QWEN_SYSTEM_PROMPT`, rule 1 instructs: *"Do NOT execute the task, do NOT draft the final answer, do NOT choose tools or capabilities."*
   Qwen repeatedly hallucinated these instructions as the **user's prohibited operations**:
   - R3: `prohibited: ['execute the task', 'draft the final answer', 'choose tools or capabilities']`
   - S5: `prohibited: ['draft final answer', 'choose tools or capabilities', 'execute the task']`
   - S6: `prohibited: ['execute task', 'draft final answer', 'choose tools or capabilities']`
2. **Operational Inversion**:
   - In S3 ("Open calculator."): It emitted `requested: []`, `prohibited: ['do not open', "don't summarize"]`! It treated an affirmative command as a prohibited action!
   - In S4 ("Don't open it yet."): It emitted `requested: ["don't_open_it_yet"]`! It put the prohibited action in `requested_operations`!
3. **Omission of Requested Actions in Negated Prompts**:
   - In R4 ("Don't send it. Just draft the email."): It captured `prohibited: ['send']`, but completely omitted the requested action `"draft the email"` (`requested: []`).

---

### 6.3 Reference Detection (Strict Reference Gate) — **0.0%**
The Strict Reference Gate evaluated whether Qwen could identify unresolved pronouns and noun phrases without regex heuristics or external assistance.

**Catastrophic Failure: Prompt Example Echoing**:
Instead of identifying references in the user message, Qwen repeatedly **copy-pasted the illustrative examples written in the system prompt** into the output:
- System prompt said: *"Record referring expressions (like 'this', 'that', 'it', 'them', 'that file', 'same thing', 'the earlier one') in 'references'..."*
- Resulting extractions:
  - R3: `refs: ['this', 'that file', 'same thing', 'the earlier one']` (Prompt only contained "same thing", "them"!)
  - R4: `refs: ['this', 'that file', 'the earlier one']` (Prompt only contained "it"! None of the others existed!)
  - R7: `refs: ['this', 'that', 'it', 'them', 'the earlier one']` (Prompt contained none of these!)
  - R8: `refs: ['this', 'that', 'it', 'them', 'the earlier one', 'same thing', 'the file', 'the same email']` (Prompt was an email to Chief Warden; zero pronouns existed!)
  - R9: `refs: ['this', 'that', 'it', 'them', 'the earlier one', 'same thing', ...]`
  - S3: `refs: ['this', 'that file', 'same thing', 'the earlier one']` (Prompt was "Open calculator."!)
- Conversely, on prompts that contained specific real references without matching the prompt's exact words:
  - R2 ("Bring that file up.") -> `refs: []` (Missed "that file" completely!).
  - R5 ("Find previous approval, compare it with this one...") -> `refs: []` (Missed "it", "previous approval", "this one"!).
  - S8 ("No, I meant the earlier one.") -> `refs: []` (Missed!).
- **Verdict on Reference Gate: 0.0%**. The 773M model cannot distinguish an instruction's examples from actual contextual extractions.

---

### 6.4 Temporal Extraction (~40%)
- Correctly extracted: S7 ("tomorrow"), R7 ("2025 decisions", "2026 decisions"), S5 ("after approval has been given").
- Missed: R10 ("yesterday" -> `temporal_references: []`), R6 ("tomorrow" -> token exhaustion timeout).

---

### 6.5 Constraints & Output Preferences (<10%)
- **Constraints**: Completely missed in R7 ("keep result under one page", "do not use anything before 2025" -> `length_limit: None`, `excluded: []`).
- **Output Preferences**: Completely missed in R8 ("Chief Warden", "Indian English", "short", "formal" -> all fields returned `None`).
- The small model does not attend to nested constraint structures when generating JSON.

---

### 6.6 Ambiguity Handling (<10%)
- Prompt S7 ("Make something I can submit tomorrow.") was not flagged as ambiguous.
- Instead, the model hallucinated output preferences for the missing artifact type.

---

### 6.7 Context Invention & System Prompt Bleed
- Severe context leakage:
  - Leaked internal system prompt developer directives into user operations.
  - Leaked system prompt illustrative examples into reference lists.
  - Hallucinated Hinglish descriptions into goal descriptions.

---

## 7. Latency and Token Economics

Measured over 18 prompts in constrained mode on GPU:

| Metric | Prompt Tokens | Reasoning Tokens | Content Tokens | Total Completion | Latency (ms) |
|---|---|---|---|---|---|
| **Min** | 234 | 47 | 31 | 123 | 1,042.6 ms |
| **Median** | 241 | 111 | 146 | 245 | 1,742.9 ms |
| **Mean** | 243.6 | 140.2 | 129.5 | 269.7 | **1,850.5 ms** |
| **Max** | 268 | **600** | 301 | **600** | **3,057.7 ms** |

### Key Economic Insights:
1. **The Reasoning Tax**: Over **52% of all generated tokens** were reasoning tokens (`140.2 / 269.7`).
2. **Latency Penalty**: Average turn latency was **1.85 seconds** on a full GPU offload. For a sub-billion model (773M), generating 140 reasoning tokens to arrive at an incorrect reference extraction is economically inefficient.
3. **Reasoning Starvation Risk**: On complex prompts (R6), reasoning consumed the entire token budget (600 tokens), leaving 0 tokens for JSON content and causing hard decode failures.

---

## 8. Acceptance Bar Evaluation (Section 12)

The acceptance criteria set a target of **approximately 90%+ reliability across critical semantic dimensions**:

| Dimension | Target | Qwen Candidate Score | Status |
|---|---|---|---|
| **Goal Accuracy** | 90%+ | ~70% | Below bar |
| **Operations Accuracy** | 90%+ | ~20% | Critical failure |
| **Negation Accuracy** | 90%+ | ~30% | Critical failure |
| **Reference Detection** | 90%+ | **0.0%** (Prompt echo) | Critical failure |
| **Constraints / Scope** | 90%+ | <10% | Critical failure |
| **Output Preferences** | 90%+ | <10% | Critical failure |
| **Unconstrained Syntax** | 90%+ | **0.0%** | Critical failure |

---

## 9. Final Recommendation

# **REJECT**

`Qwen3.5-0.8B.Q8_0` (Reasoning-Distilled, 773M parameters) is **REJECTED as URIv1's Step-1 Semantic Decoder**.

### Core Failure Reasons:
1. **Incapacity for In-Context Reference Extraction**: The model cannot identify pronouns or referring expressions in user text; it blindly copies the prompt's illustrative examples into the reference array.
2. **Operational & Negation Inversion**: It confounds negative constraints on itself with user-prohibited actions, and inverts requested vs. prohibited operations.
3. **Reasoning-Distilled Overhead Without Accuracy**: The reasoning tokens inflate latency to ~1.85 seconds while frequently exhausting token limits, without solving semantic extraction.
4. **Zero Unconstrained Adherence**: Fails 100% of the time to follow schema in unconstrained generation.

---

## 10. Recommended Next Step-1 Model / Architecture Path

1. **Abandon Sub-Billion (<1B) Models for Step 1**:
   Both Needle 3 (base weights) and Qwen 0.8B have now demonstrated that sub-billion models lack the in-context comprehension required to separate prompt instructions from user input and extract multi-aspect semantics.
2. **Target the Standard Local 2B–4B Agentic / Instruct Tier**:
   Evaluate a full, non-reasoning instruction-tuned model in the **1.5B to 3B parameter range**:
   - **`Qwen2.5-Coder-1.5B-Instruct`** / **`Qwen2.5-Coder-3B-Instruct`**
   - **`Gemma-2-2B-IT`**
   - **`SmolLM2-1.7B-Instruct`**
3. **Avoid Reasoning-Distilled Models for Step 1**:
   Reasoning-distilled models add unnecessary thinking latency and are prone to prompt-leakage hallucinations. Step 1 requires **direct, structured instruction following**, which standard Instruct checkpoints handle with much lower latency (~300–500ms on GPU) and zero reasoning-starvation risk.

---

## 11. Regression Battery

Full regression suite across all M35 batches (A0, A1, A1.1, A2, A2.1, A2.2):
```powershell
python -m pytest test_m35_uriv1_a0_skeleton.py test_m35_uriv1_a1_decoded_request.py test_m35_uriv1_a1_1_contract_hardening.py test_m35_uriv1_a2_needle_decoder.py test_m35_uriv1_a2_needle_live.py test_m35_uriv1_a2_1_needle_narrow.py test_m35_uriv1_a2_1_needle_narrow_live.py test_m35_uriv1_a2_2_qwen_decoder.py test_m35_uriv1_a2_2_qwen_live.py
```
**Result**: **98 passed, 0 failed in 71.85s (100% green)**.

---

## 12. Workspace Hygiene Confirmations

1. **Protected Repo Untouched**: `git status --short` in `C:\Users\cheta\Development\uri-agent` confirmed the same 65 untouched paths.
2. **No Git Commits or Pushes**: `git log -1` in `C:\Users\cheta\Development\Uri\_V1` confirmed HEAD remains `e8e3b65259c45fc823addc3ef8969425a265bd1b`. All work is uncommitted by design.
