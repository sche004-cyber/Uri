# M35 — Batch A2: Needle 3 Semantic Decoder Integration & Qualification — Report

## 1. Branch / worktree / HEAD

- Worktree: `C:\Users\cheta\Development\Uri\_V1`
- Branch: `m35-uri-v1-parallel-architecture`
- HEAD: `e8e3b65259c45fc823addc3ef8969425a265bd1b` (unchanged — nothing committed)
- Original prototype worktree `C:\Users\cheta\Development\uri-agent`: verified untouched before and after this batch (`git status --porcelain` still shows the same 65 protected paths, `git log -1` still `e8e3b65`).

## 2. Files changed

All new, all inside the new worktree. `uri_core/` and `uri_ui/` were only read, never written.

```
uri_v1/turn/needle_wire.py            (new)
uri_v1/turn/needle_decoder.py         (new)
uri_v1/turn/needle_bridge_runtime.py  (new — subprocess-side script)
uri_v1/turn/__init__.py               (modified — re-export new symbols)
test_m35_uriv1_a2_needle_decoder.py   (new — synthetic unit tests)
test_m35_uriv1_a2_needle_live.py      (new — real Needle inference tests)
docs/plans/M35_URIV1_A2_NEEDLE_DECODER_REPORT.md  (this file)
```

`uri_v1/turn/contracts.py` and `uri_v1/turn/decoder.py` were **not modified** — the A1.1-frozen `DecodedRequest`/`DecodeInput` shapes and the provider-neutral `SemanticDecoder` interface accommodated Needle without changes.

## 3. Needle runtime: reused vs. newly adapted

**Reused (transport-level only, read-only, nothing copied):**
- The existing `.venv-needle` Python virtualenv at the prototype root, invoked as an external interpreter by path. Not copied, not modified.
- The general *shape* of a subprocess speaking newline-delimited JSON over stdio to an offline `needle.Needle(...)` instance — the same pattern used by `uri_core/core/edge/adapters/ensemble.py`'s `NeedleSubprocessAdapter` and `scripts/m33_2_needle_bridge.py`.
- The offline-mode environment variables (`NEEDLE_TELEMETRY=0`, `DO_NOT_TRACK=1`, `HF_HUB_OFFLINE=1`) and the `generation=3` choice, matching prior repository precedent (verified working, confirmed no network calls were needed once these were set).

**Newly adapted / reimplemented, not imported:**
- `uri_v1/turn/needle_bridge_runtime.py` is a **fresh** bridge script, not a reuse of `scripts/m33_2_needle_bridge.py`. The old bridge's `Bridge` class hardcodes tool-selection/capability-routing policy (`weather.lookup`, `Gmail.search_messages`, `calendar.list_events`, an `_INTENTS` name-mapping table) — exactly the "old capability selection" the batch spec forbids inheriting. The new bridge is decode-only, generic, and schema-agnostic: it accepts `system` and `schema` per request rather than choosing from a baked-in tool table, and it never distinguishes "capability" from "structured extraction" the way the old bridge did.
- `uri_v1/turn/needle_decoder.py`'s `NeedleBridgeTransport` is a **fresh** reimplementation of the same ping/decode/close-over-stdio pattern as `NeedleSubprocessAdapter`, not an import of it. Rationale: `NeedleSubprocessAdapter` lives in `uri_core/core/edge/adapters/ensemble.py` alongside `_deterministic_core` and `EnsembleAdapter`, a benchmark harness bundled with old tier-routing/benchmark policy in the same file. Importing the class directly would create a real dependency edge from `uri_v1` into that module. Per the batch instruction ("if the old adapter is too coupled, implement a minimal URIv1-specific runtime adapter instead"), a minimal reimplementation was chosen. The two classes are structurally similar (same Popen/JSONL protocol) by design, not coincidence — this is "reuse the transport pattern," not "reuse the policy."

This decision was made after reading both `ensemble.py`'s `NeedleSubprocessAdapter` (lines 32–146) and `scripts/m33_2_needle_bridge.py` in full.

## 4. Exact wire schema

`uri_v1/turn/needle_wire.py::WIRE_SCHEMA` (JSON Schema, passed as Needle's single offered tool):

```json
{
  "name": "decode_request",
  "description": "Always call this exactly once to record the semantic decoding of the current user message.",
  "parameters": {
    "type": "object",
    "properties": {
      "goal": {"type": "string"},
      "intent_family": {"type": "string", "enum": ["retrieve","create","modify","communicate","execute","analyze","compare","research","navigate","converse","unspecified"]},
      "operations": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "status": {"type": "string", "enum": ["requested","prohibited"]}}, "required": ["name","status"]}},
      "references": {"type": "array", "items": {"type": "object", "properties": {"expression": {"type": "string"}, "kind": {"type": "string", "enum": ["pronoun","previous_action","document_or_file","temporal_ordinal","other"]}}, "required": ["expression"]}},
      "temporal_references": {"type": "array", "items": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}},
      "constraints": {"type": "object", "properties": {"included_items": {"type": "array", "items": {"type": "string"}}, "excluded_items": {"type": "array", "items": {"type": "string"}}, "length_limit": {"type": "string"}, "language_constraints": {"type": "string"}}},
      "output_preferences": {"type": "object", "properties": {"artifact_type": {"type": "string"}, "tone": {"type": "string"}, "audience": {"type": "string"}, "language": {"type": "string"}, "language_variant": {"type": "string"}}},
      "entities": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "category": {"type": "string"}}, "required": ["name"]}},
      "ambiguities": {"type": "array", "items": {"type": "object", "properties": {"description": {"type": "string"}}, "required": ["description"]}}
    },
    "required": ["goal"],
    "additionalProperties": false
  }
}
```

`SYSTEM_PROMPT` instructs Needle to decode only the current message, never resolve pronouns/references, never use outside knowledge, and always call `decode_request` exactly once. The schema deliberately contains no tool names, capability IDs, Graphify nodes, workflow IDs, provider names, Edge decisions, execution plans, or final answers — verified by `WireSchemaContaminationTests` in the unit suite (§18).

Confirmed via `needle.Needle.__init__`/`complete` signature inspection (`inspect.signature`) in the actual installed `cactus-needle==3.0.2` package: `Needle(tools=None, system=None, weights=None, tool_index_path=None, buffer_size=65536, auto_date=True, generation=None)`, `complete(text='', max_new_tokens=512) -> dict`. No Python-level "forced call" parameter exists (a `--forced` flag is documented only for the native C runner, not the Python binding) — this matters for the qualification results below.

## 5. Normalization architecture

`normalize_wire(wire, input_data, raw_confidence=None) -> DecodedRequest` in `needle_wire.py`. Validation-and-mapping only, no semantic reasoning:

- Requires a non-empty `goal` string; missing/blank → `DecodeError(MISSING_REQUIRED_STRUCTURE)`.
- Enum fields (`intent_family`, `OperationStatus`, `ReferenceKind`, `EntityCategory`) fall back to their neutral default (`UNSPECIFIED`/`REQUESTED`/`OTHER`) on an unrecognized value rather than erroring — a deterministic default, not an inference.
- An operation name appearing both `requested` and `prohibited` → `DecodeError(OPERATION_ERROR)` (contradiction, not resolved by guessing).
- A wire reference claiming `is_resolved: true` → `DecodeError(CONTEXT_INVENTION)`: Step 1 must never resolve a reference (governing rule 3), so a wire payload asserting resolution is treated as invalid rather than trusted.
- `included_items`/`excluded_items` overlap → `DecodeError(CONSTRAINT_ERROR)`.
- Every unresolved reference and every current-turn attachment deterministically produces a `ContextDependency` stating context is required — a mapping rule (governing rule 8), not a guess about where Step 2 should look.
- Attachments come **only** from `DecodeInput.attachments`, never from the wire payload — Needle is never asked to invent attachment identity.
- Confidence: Needle exposes exactly one overall float per response (confirmed both from `research_notes/Edge runtime evaluation/needle.md` and from every one of the 18 live qualification responses below — `confidence` always a single top-level float, never per-field). `_confidence_bucket()` deterministically buckets that single value into `SemanticConfidence.overall`; the four aspect-level fields (`goal`, `operations`, `references`, `constraints`) are always set to `UNCERTAIN` rather than derived from the overall value — fabricating per-field confidence from a single number would violate section 13's explicit prohibition.
- Malformed top-level shape (non-dict wire, non-dict `constraints`/`output_preferences`) → `DecodeError(MALFORMED_OUTPUT)` / `DecodeError(CONSTRAINT_ERROR)` / `DecodeError(OUTPUT_PREFERENCE_ERROR)` as appropriate.

## 6. `NeedleSemanticDecoder` structure

```
DecodeInput
  -> NeedleBridgeTransport.decode(raw_text)   # subprocess JSONL round trip
  -> raw Needle response envelope
  -> NeedleSemanticDecoder.decode_with_result():
       - envelope.success == False           -> NeedleDecodeResult(error=MALFORMED_OUTPUT)
       - 0 function_calls                    -> NeedleDecodeResult(error=MISSING_REQUIRED_STRUCTURE)
       - >1 function_calls                   -> NeedleDecodeResult(error=MALFORMED_OUTPUT)
       - exactly 1 call named decode_request -> normalize_wire(call.arguments, input_data, raw_confidence)
                                                   -> NeedleDecodeResult(decoded_request=...) or (error=...)
```

`decode()` (the `SemanticDecoder` interface method) raises `DecodeError` on failure, matching the provider-neutral interface contract. `decode_with_result()` is the non-raising variant used by qualification/live tests so a failure is data, not a caught exception. Both paths guarantee: **never a fabricated `DecodedRequest`** (section 17) — every non-`ok` outcome carries a typed `DecodeErrorReason`.

## 7. Qualification prompts

All 10 required cases (section 10) and all 8 stress cases (section 11) were run against the real Needle 3 runtime via a dedicated qualification script (`needle_qualify.py`, executed through `.venv-needle`'s interpreter; not committed — a throwaway harness, its logic is now embodied in `test_m35_uriv1_a2_needle_live.py`'s `REQUIRED_CASES`/`STRESS_CASES` lists). Each case used a fresh `Needle` agent instance with `generation=3`, `max_new_tokens=300..512` depending on the probe iteration, and the final `WIRE_SCHEMA`/`SYSTEM_PROMPT` from §4.

## 8–13. Expected vs. actual, per-dimension pass/fail, failure taxonomy, malformed/context-invention/negation/reference rates

### Required cases

| Case | Text | Structural outcome | Semantic result vs. expected | Failure categories |
|---|---|---|---|---|
| R1 | Convert this to PDF. | **No call emitted** (`function_calls: []`, `confidence: 1.0`) | Complete miss: no goal, no "this" reference, no PDF preference | `MISSING_REQUIRED_STRUCTURE`, `OVERCONFIDENT_ERROR` (max confidence on total non-response) |
| R2 | Bring that file up. | Call emitted, `goal: ""` → normalizer rejects | No goal, no "that file" reference captured | `MISSING_REQUIRED_STRUCTURE`, `REFERENCE_ERROR` |
| R3 | Do the same thing for them. | 1 call, `goal: "retrieve"` — **structurally valid** | Neither "same thing" nor "them" captured as references; "retrieve" mislabels a repeat-prior-action request | `REFERENCE_ERROR`, `GOAL_ERROR` |
| R4 | Don't send it. Just draft the email. | 1 call, `goal: "draft the email"` — **structurally valid** | No `operations` array at all — "send" prohibited and "draft" requested both missing, despite the engine's own internal `validation.negation: true` flag firing correctly | `NEGATION_ERROR`, `OPERATION_ERROR` |
| R5 | Find the previous approval, compare it with this one and draft a revised order. | **3 duplicate/garbled calls** (`goal: "previous approval"`, `"comparison_comparison"`, `"draft_order"`) | Rejected outright (`MALFORMED_OUTPUT`, >1 call); field values themselves are template-fragment nonsense, not real language | `MALFORMED_OUTPUT` |
| R6 | Committee/latest-letter/tomorrow case | 1 call, `goal: "communicate"`, `intent_family: "create"`, `operations: []` — **structurally valid** | Misses "latest letter" and "earlier decisions" as references, misses "tomorrow" as a temporal reference, mislabels the goal (comparison/reconciliation intent reduced to generic "communicate") | `GOAL_ERROR`, `REFERENCE_ERROR`, `TEMPORAL_ERROR` |
| R7 | Compare 2025/2026, exclude before 2025, one page. | **2 duplicate calls** (`goal: "2025"`, `goal: "2026"`) | Rejected outright; no `constraints.included_items`/`excluded_items`/`length_limit` populated in either call despite `validation.negation: true` firing | `MALFORMED_OUTPUT`, `CONSTRAINT_ERROR` |
| R8 | Draft a short formal email in Indian English to the Chief Warden. | **No call emitted** (`confidence: 1.0`) | Complete miss of an unambiguous, fully explicit instruction | `MISSING_REQUIRED_STRUCTURE`, `OVERCONFIDENT_ERROR` |
| R9 | Do not summarize this; compare the exact figures in a table. | 1 call, `goal: "compare"`, `intent_family: "compare"` — **structurally valid, correct family** | No `operations` (summarize-prohibited missing), no `output_preferences.structure`/format for "table" | `OPERATION_ERROR`, `OUTPUT_PREFERENCE_ERROR` |
| R10 | What was approved yesterday? | **No call emitted** (`confidence: 1.0`) | Complete miss, including the explicit "yesterday" temporal expression | `MISSING_REQUIRED_STRUCTURE`, `TEMPORAL_ERROR`, `OVERCONFIDENT_ERROR` |

**Structural success rate (produced a valid `DecodedRequest`, right or wrong content): 4/10 (40%)** — R3, R4, R6, R9.
**Semantic-dimension pass rate on those 4 structurally-valid cases: 0/4 fully correct** — every one of them still missed at least one required dimension (references, negation-as-operation, or temporal capture).

### Stress cases (observational, no accept/reject scoring required by spec)

| Case | Text | Outcome |
|---|---|---|
| S1 | Hello | No call (`confidence: 1.0`) — reasonable non-response for a greeting, but indistinguishable in the response shape from R1/R8/R10's outright misses |
| S2 | Thanks | No call (`confidence: 0.86`) |
| S3 | Open calculator. | No call (`confidence: 1.0`) — missed an explicit, simple command |
| S4 | Don't open it yet. | 1 call, `goal: "retrieve"` — negation not represented in `operations` |
| S5 | Send it to him after they approve it. | No call |
| S6 | Compare the attached PDF with this spreadsheet. | No call — missed an explicit attachment-comparison request entirely |
| S7 | Make something I can submit tomorrow. | 1 call, `goal: "create"`, `intent_family: "create"` — no temporal capture of "tomorrow", no ambiguity entry for the unresolved artifact type despite the schema offering one |
| S8 | No, I meant the earlier one. | 1 call, `goal: "retrieve"` — no reference for "the earlier one" |

### Failure taxonomy tallies (18 live cases: 10 required + 8 stress)

| Category | Count | Notes |
|---|---|---|
| `MISSING_REQUIRED_STRUCTURE` | 9 | 8 no-call cases + 1 empty-goal case (R2) |
| `MALFORMED_OUTPUT` | 2 | R5 (3 calls), R7 (2 calls) |
| `REFERENCE_ERROR` | 5 of 5 applicable | Every case requiring reference detection (R1, R2, R3, R5, R6) failed to capture any reference |
| `NEGATION_ERROR` | 3 of 3 applicable | R4, R7, R9 — engine internally flagged `validation.negation: true` in all 3, but 0/3 propagated a prohibited operation into the wire output |
| `TEMPORAL_ERROR` | 2 of 2 applicable | R6 ("tomorrow"), R10 ("yesterday") both missed |
| `GOAL_ERROR` | 2 | R3 ("retrieve" for a repeat-action request), R6 ("communicate" for a comparison/reconciliation request) |
| `OPERATION_ERROR` | 3 | R4, R7 (via MALFORMED_OUTPUT), R9 |
| `CONSTRAINT_ERROR` | 1 | R7 |
| `OUTPUT_PREFERENCE_ERROR` | 1 | R9 (table structure not captured) |
| `CONTEXT_INVENTION` | **0 observed** | No fabricated entities/identities appeared in any wire `arguments` object across all 18 cases — see note below |
| `OVERCONFIDENT_ERROR` | 7 | Every no-call case reported `confidence >= 0.82` (6 of 8 reported exactly `1.0`) — see §12 |
| `AMBIGUITY_ERROR`, `ENTITY_ERROR` | 0 explicit failures | `ambiguities`/`entities` arrays were simply never populated by Needle in any of the 18 cases — a coverage gap rather than a wrong-content error |
| `UNKNOWN_FIELD` | 0 | No unrecognized top-level keys appeared in any wire payload |

**Malformed-output rate: 2/18 (11%)** (strict "more than one call" definition). If "no call" is folded into the same "did not produce usable structure" bucket, the combined structural-failure rate is **11/18 (61%)**.

**Context-invention rate: 0/18 (0%) at the wire-argument level.** This is a positive finding, but with an important caveat: Needle's free-text `reasoning` field *did* repeatedly hallucinate irrelevant domain content across calls (e.g. reasoning about "file compression", "calculator", "SMS", "advance tool" for inputs that mention none of those things — likely bleed-through from whatever the base weights were originally tuned on for tool selection). `normalize_wire()` never reads `reasoning`, so none of that hallucination reached `DecodedRequest`. This is a design point worth keeping, not a coincidence: discarding `reasoning` (per the existing research note's own recommendation) is what kept the 0% context-invention rate at the contract boundary.

**Negation accuracy:** the engine's own internal `validation.negation` boolean was **3/3 (100%) correct** on the cases that needed it (R4, R7, R9) — Needle's grammar/validation layer does detect negation. But **0/3 (0%)** of that detection reached the structured `operations` array Step 1 actually needs. This is the single most fixable-looking gap: the signal exists in the raw response envelope but the schema/system-prompt combination used here never got the model to act on it.

**Unresolved-reference accuracy: 0/5 (0%)** on the required cases that explicitly need at least one unresolved reference recorded (R1, R2, R3, R5, R6).

## 12 (continued). The `OVERCONFIDENT_ERROR` finding

This is the most consequential single finding of A2. In every one of the 8 "no call" outcomes, `confidence` was still reported — 6 of 8 at exactly `1.0`, the other 2 at `0.86`–`0.97`. Needle's documented confidence contract (`research_notes/Edge runtime evaluation/needle.md`, §"structured proposal/confidence") describes confidence as calibrated against *the call it did make*; it says nothing about calibrating "I declined to call the offered tool at all" against the instruction to always call it. The practical effect: **a naive downstream consumer reading only `confidence` would treat Needle's worst failure mode (total non-compliance with an explicit, simple, unambiguous instruction) as its most confident output.** Confidence must never be used as a signal for whether Step 1 succeeded — only the presence and count of `function_calls` combined with `normalize_wire`'s own validation can determine that. `NeedleSemanticDecoder` was built to reflect this: it never inspects `confidence` to decide success/failure, only `function_calls` and normalizer outcome.

## 13. Confidence observations

- Confidence is a single float in `[0, 1]` on the **entire** response, never per-field — confirmed against every one of the 18 live responses, consistent with the vendor's documented "minimum of a calibrated post-hoc head and call-token decoding probability" contract cited in the existing research note.
- Observed range across all 18 cases: `0.1962` (R2, empty-goal call) to `1.0` (multiple no-call cases).
- Fully stable/deterministic across repeats: 3 repetitions each of 3 prompts ("Convert this to PDF.", "Don't send it. Just draft the email.", "Do the same thing for them.") produced **bit-for-bit identical** `confidence` values (to the reported 4 decimal places) and identical `function_calls` — greedy decoding, no sampling variance under these settings.
- No field-level confidence exists to map; `SemanticConfidence`'s four aspect fields are deliberately left `UNCERTAIN` rather than fabricated from the overall value (§5, §18).
- Per spec §13: no execution/escalation threshold was implemented in A2 — `NeedleDecodeResult` exposes `raw_confidence` for later batches to use, but `NeedleSemanticDecoder` itself makes no accept/reject decision based on it.

## 14. 16./17. Latency, cold/warm, repeatability, malformed/error handling

- **Cold** (subprocess spawn + first `.decode()` call, including `needle.Needle(...)` construction inside the bridge): **733 ms** (single measurement through the full `NeedleBridgeTransport` → subprocess → `needle.Needle()` path).
- **Warm** (10 repeated `.decode()` calls against an already-loaded agent, same process): **min 58.6 ms, median 187.8 ms, max 211.4 ms** (measured through the transport, includes JSONL round-trip + `agent.complete()` + normalization attempt).
- Raw `agent.complete()` call time alone (from the earlier, more granular probe, 18 fresh-agent-per-call live-qualification runs): ranged **58.6 ms to 443.5 ms** (min/median/max reported in §"stats" below), with per-agent load time (`needle.Needle(...)` construction) separately measured at **~450–500 ms** the first time a given `(system, schema)` key is used.
- Needle process startup: the bridge caches agents by `(system, schema)` key inside a single long-lived subprocess (`DecodeOnlyBridge._agent`), so repeated Step-1 calls with the same schema/system reuse the loaded agent — no reload observed across the 10 warm repetitions or the 18 qualification calls when the schema/system stayed constant.
- Memory: Needle's own self-reported `peak_ram_mb` was consistently **~100.9–101.4 MB** across all 18 live qualification calls (stable, not growing across calls). A `psutil` RSS read against the wrapping Python subprocess process itself measured only ~3.9 MB, which reflects psutil measuring the thin Python wrapper process rather than the native engine's own memory (the native engine allocates outside what `psutil.Process.memory_info().rss` attributes to the wrapper in this measurement) — Needle's self-reported `peak_ram_mb` is treated as the more meaningful figure here, consistent with the existing research note's guidance to also independently verify these self-reported fields (not fully done in A2; flagged as an open item in §23).
- Repeatability: full bit-for-bit determinism observed (see §13) — no malformed-output variance across repeats of the same prompt under identical settings.
- Validation/error handling (§17): confirmed working as designed — every live case, structurally valid or not, produced either a `NeedleDecodeResult` with `decoded_request` set, or one with a typed `error` set; `test_decode_never_raises_uncaught_and_always_yields_result_or_typed_error` asserts this over all 18 required+stress prompts and passes. No fallback to a larger model was implemented (out of scope, per §17/§22).

## 18. Static/unit test results

`test_m35_uriv1_a2_needle_decoder.py` (synthetic, no live Needle required):
```
25 passed, 8 subtests passed
```
Covers: wire-schema contamination check (no tool/capability/Graphify/provider/execution terms), `DecodeInput` boundary (exactly `raw_text`+`attachments`, no history-shaped field, genuinely frozen), valid-wire normalization (minimal and full-field), invalid-wire handling (missing/empty goal, non-dict wire, requested/prohibited contradiction, resolved-reference-claim rejected as context invention, included/excluded overlap, malformed nested objects), enum fallback behavior, confidence bucketing (including the "never fabricate per-field confidence" invariant), attachment propagation from `DecodeInput` only, and absence of any capability/tool ID field on `SemanticOperation`.

`test_m35_uriv1_a2_needle_live.py` (real inference, auto-skipped if the Needle virtualenv is absent):
```
4 passed, 18 subtests passed
```
Covers: bridge loads and reports `status: ready`; decoding all 18 required+stress prompts never raises uncaught and always yields either an `ok` result or a typed error; a batch run over all 10 required cases completes without crashing (evidence capture only, no semantic pass/fail assertion — see the module docstring for why); repeatability of an identical prompt.

## 19. Regression

Full re-run of A0 + A1 + A1.1 + A2 test files together:
```
59 passed, 64 subtests passed in 8.21s
```
(`test_m35_uriv1_a0_skeleton.py`, `test_m35_uriv1_a1_decoded_request.py`, `test_m35_uriv1_a1_1_contract_hardening.py`, `test_m35_uriv1_a2_needle_decoder.py`, `test_m35_uriv1_a2_needle_live.py`.) No regressions. `uri_core` package import still succeeds (exercised by the A0 suite).

## 20. Architecture boundary confirmation

- `SemanticDecoder` (`uri_v1/turn/decoder.py`) remains provider-neutral: unmodified in A2, contains zero Needle-specific code.
- `NeedleSemanticDecoder` implements it exactly (`decode(DecodeInput) -> DecodedRequest`), living entirely in `needle_decoder.py`.
- No Step 2/3 code was written: no session/context resolution, no Graphify, no ARN, no Edge escalation gate, no tool/capability selection, no execution.
- `DecodeInput` carries only `raw_text` and `attachments` (verified by `test_decode_input_only_carries_current_turn_material`) — no session history, Graphify, prior turns, ARN, or tool data reaches Needle, confirmed both by the dataclass shape and by the system prompt's explicit "only the current message" instruction.
- The wire schema and every normalized `DecodedRequest` field were checked for tool/capability/routing contamination (§18) — none found.

## 21. Recommendation

**REJECT the current (base, generation-3, untuned) Needle 3 weights for the full multi-field `decode_request` wire schema as specified in this batch.**

Basis (per the evidence-integrity standard — semantic accuracy, not "does the code run"):
- Structural success rate on the 10 required cases: 40% (4/10 produced any valid `DecodedRequest` at all).
- Of those 4 structurally-valid cases, 0% were semantically complete against their stated expectations (§8–13).
- Unresolved-reference capture: 0% (0/5 applicable required cases) — this is a core Step-1 responsibility (governing rule 3) and the model does not do it at all under this schema.
- Negation representation in structured output: 0% (0/3), despite the engine's own internal negation detector firing correctly 100% of the time — the signal exists but is not reaching the schema.
- A dangerous confidence/reliability inversion: the model's worst failure mode (declining to call the tool at all, 8/18 cases) is reported with the *highest* confidence values observed (6/8 at exactly 1.0).
- The transport, bridge, and deterministic normalizer all performed exactly as designed — every failure mode above was caught and surfaced as a typed `DecodeError`, never silently fabricated. **The engineering did not fail; the model did not perform the task.**

**ACCEPT WITH CONDITIONS is plausible for a narrower future attempt**, specifically:
1. Decompose the single 9-field `decode_request` schema into several much smaller single/few-field extraction calls (closer to the old bridge's narrow `record.extract` pattern, which the vendor's own benchmark suite — DSTC8/SNIPS field-F1 — suggests is closer to what small extraction models are actually evaluated against), and re-qualify each narrower call independently.
2. Evaluate a fine-tuned Needle checkpoint instead of base generation-3 weights — the vendor's own documentation states base weights carry a calibration head that fine-tuning invalidates (reporting `confidence: None` when tuned), implying base weights were never the vendor's intended production configuration for anything beyond simple tool selection.
3. Independently verify whether the native C runner's `--forced` flag (unavailable through the Python binding used here) meaningfully changes the "declines to call at all" failure mode, since forcing is the one documented lever this qualification could not test.

Full REJECT (not ACCEPT WITH CONDITIONS) is the A2 recommendation, because none of the three conditions above were tested in this batch — they are directions for a follow-up qualification, not partial evidence of viability.

## 22. Specific limitations discovered

- Base Needle 3 (generation 3) frequently declines to call an offered tool at all (8/18 live cases), even under an explicit system-prompt instruction to always call it, with no Python-level "forced call" override available.
- When it does call, the `reasoning` free-text field is frequently incoherent or hallucinated relative to the actual input (referencing calculators, file compression, SMS, weather — domains absent from every test prompt), suggesting strong bias bleed-through from whatever narrow tool-selection distribution the base weights were originally exposed to.
- Multi-call emission for what should structurally be exactly one call (2/18 cases, both on the two most information-dense required prompts, R5 and R7) — the model appears to fragment a single request into several partial, low-quality calls when asked to reason over more clauses.
- Zero reference/entity/ambiguity array population across every one of 18 live cases, even when the schema explicitly offers those arrays and the prompt clearly warrants them.
- Confidence is not a usable proxy for "did the model do the task" — see §12's `OVERCONFIDENT_ERROR` finding.
- `psutil`-based RSS measurement of the wrapper subprocess undercounts actual native-engine memory; only the model's self-reported `peak_ram_mb` (~101 MB, stable) was usable in A2. Independent OS-level memory verification (per the existing research note's own recommendation) was not performed and remains open.

## 23. Questions exposed for Step 2

- If Step 1 cannot reliably produce unresolved-reference records, Step 2 (Context Resolution) cannot assume it will receive them — does Step 2's design need a fallback path for "Step 1 produced no references at all, but the raw text clearly contains an unresolved pronoun/reference"? A2 deliberately does not answer this (out of scope — no semantic inference in the normalizer), but Step 2's design should account for it explicitly rather than silently assuming Step 1 output is complete.
- Given the 61% combined structural-failure rate, what should the pipeline do when `NeedleSemanticDecoder.decode()` raises `DecodeError`? A2 provides the typed error but implements no retry, fallback, or escalation policy — that decision is explicitly deferred (§17, §22 non-goals).
- Should confidence be dropped from the pipeline's decision-making entirely, given the demonstrated inversion, or only excluded from *success/failure* determination while still being logged for observability? A2 takes the latter, narrower position (`raw_confidence` is preserved on `NeedleDecodeResult` but never used for control flow) — a later batch should decide if even that is too much trust.
- Independent, OS-level network-silence and memory verification (per `research_notes/Edge runtime evaluation/needle.md`'s own acceptance-benchmark section) was not performed in A2 and should gate any production acceptance regardless of the semantic-accuracy verdict above.

## 24. Confirmation original URI remained untouched

Verified before and after this batch: `git status --porcelain` in `C:\Users\cheta\Development\uri-agent` shows the same 65 protected paths (unchanged in count or content), and `git log -1` there still reports `e8e3b65259c45fc823addc3ef8969425a265bd1b` on `master`. No file in `uri_core/` or `uri_ui/` was written to; the only interaction with the original worktree was read-only execution of its pre-existing `.venv-needle\Scripts\python.exe` interpreter as an external process, which does not modify any file on disk.
