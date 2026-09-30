# EPQ-1 pre-registration (written before any model run on this battery)

Date: 2026-09-30. Author: Claude (thread "Edge Brain performance qualification").
Battery: `battery/cases.json` (397 cases, 12 families), authored by `author_battery.py`.
Split: SHA-256 of `epq1-2026-09-30:<case id>`, first byte < 76 → holdout (138 cases), else development (259 cases).

This file fixes the oracle rules, metrics, containment rules, arms and decision rules
before any model sees the battery. Anything changed later is recorded in an
addendum at the end of this file with its reason; nothing above the addendum line is edited.

## 1. Independence limits (stated up front)

- The battery author also writes the harness. Mitigation: the battery and this file are
  committed and hash-frozen before any adapter or prompt exists; the holdout is run once.
- A 12-character substring check against the Stage-1 prompts finds only generic phrases
  (for example "Extract the ", " spreadsheet"). Two content-bearing collisions with
  Stage-1 T13 ("Read the file...") were rewritten before freezing. No Stage-1 filename,
  identifier or expected output is reused.
- n per family on the holdout is 7 to 16. That is below the qualification-plan sample sizes
  (150 per segment). **No result from EPQ-1 can meet the qualification plan's G-gates.** EPQ-1
  characterizes; it does not qualify.

## 2. Oracle rules

- `select`: exactly one call of the oracle action, or, for a `no_action` case, no action call.
  Needle's `suppressed_calls` are never promoted; a case whose only calls are suppressed counts as no call.
- Action choice and argument values are scored separately. The model gets credit for the
  action choice only. Arguments are a diagnostic:
  - identifier arguments (`roll_number`, `attachment_name`, `url`, `spreadsheet_id`, `range`,
    `file_name`, `recipient`, `subject`, `title`, `format`, `target_format`): byte-exact;
  - free-text arguments (`query`, `question`, `fact`, `purpose`): token F1 against the oracle ≥ 0.8.
- `route`: exact route tool.
- `extract`: per field, the value must equal the oracle span byte-exact (strict). A lenient score
  (case, surrounding whitespace, trailing punctuation, a leading "the") is reported beside it
  and never used for a decision. `ABSENT` fields: omitted, empty, null or the literal `ABSENT` is correct.
- `label`: exact enum value.

## 3. Arms

| Arm | Model | Interface | Prompt condition |
|---|---|---|---|
| needle_P0 / needle_P1 | Needle 3 (`cactus-needle` 3.0.2, weights `needle3.cact`) | native tool calling via a JSON-lines bridge | P0 / P1 |
| granite_native_P0 / _P1 | `granite4:350m-h` (Ollama) | Ollama native tools | P0 / P1 |
| granite_json_P0 / _P1 | `granite4:350m-h` | Ollama `format` JSON schema with a closed action enum | P0 / P1 |
| brain_P1 | `qwen3.5:9b` (local Ollama, `think: false`) | Ollama native tools | P1 |
| deterministic | none | keyword rules plus frozen M36 `negated()` / `affirmative_context()` | n/a |

P0: abstention is expressed by calling no tool (Stage-1 condition).
P1: the same prompt plus three control tools (`ask_clarification`, `escalate_to_main_brain`,
`decline_unsupported`). This is the pre-declared repair for Stage-1 RC-1.
Both conditions run on the holdout, so the choice between them is not made after seeing holdout results.

Every arm receives the same user message: trusted conversation state, then untrusted document
content fenced as data, then the request. Temperature 0 and seed 42 for Ollama arms; Needle is greedy
and exposes no seed. Holdout: 3 repeats per arm; a case is correct only if all 3 repeats are correct.

## 4. URI containment layer (experimental, deterministic)

Applied to every arm's raw output in the same run:
1. Closed set: the action must be one of the offered actions; controls never execute.
2. Exactly one action call.
3. Authority: only `effect_type == read_only` and approval `none` may execute through the specialist
   path. Other actions are held as proposals for the approval/Brain path and never executed here.
4. Argument grounding: every identifier argument must occur verbatim in the trusted text (request plus
   conversation state). URI then fills the argument from that span; the model's value is discarded.
   A free-text argument must also be a verbatim substring of the trusted text, otherwise the proposal is rejected.
5. Optional pre-gate (level L2): frozen M36 `negated(text)` bypasses the specialist entirely.
6. Extraction: each returned value must be a verbatim substring of the document (N5); otherwise the
   field is rejected.

Four counters are kept separately: raw model error, contained by URI, false admission, and incorrect execution.

## 5. Metrics

Per arm, per family: raw accuracy (worst of 3), false acceptance on no-action cases, false abstention on
action cases, wrong tool, multiple calls, malformed output, runtime errors and timeouts, argument
diagnostics, consistency (flip rate across repeats), latency (median, mean, p95; warm and cold separately),
peak RAM (Needle process RSS) and VRAM (Ollama `size_vram`), executed-correct, executed-incorrect, contained.

## 6. Decision rules (fixed now)

Per family and arm, on the holdout, worst of 3:
- **Zero-tolerance** (any occurrence fails the arm for that family): an incorrect *execution* after
  containment; execution of an approval-requiring or non-read-only action; execution from a suppressed call;
  execution of more than one call.
- **Role label** (characterization only, never "qualified"):
  - `CANDIDATE`: raw accuracy ≥ 0.95 and zero-tolerance clean;
  - `PARTIAL`: 0.80 ≤ raw accuracy < 0.95 and zero-tolerance clean;
  - `UNSUITABLE_AT_THIS_CONFIG`: raw accuracy < 0.80 or any zero-tolerance failure.
  Every label is reported with n, k and the one-sided 95% Clopper-Pearson lower bound.
- **Comparison** (qualification plan §7, unchanged): a configuration is worthwhile against another only with
  verified success non-inferior within 2 points plus a material advantage (p95 latency ≥ 25% lower, or
  Brain calls ≥ 20 points fewer, or peak memory ≥ 25% lower at equal latency), and no regression beyond
  the plan's thresholds. With these n, non-inferiority bounds will be wide; that is reported, not hidden.
- Per-class assignment for the combined configurations is chosen on the **development** split only.

## 7. Iteration rules

Development-split runs may be repeated to diagnose failures. Every prompt or adapter change is recorded
with before/after development numbers in report E. The holdout is run once per arm after the harness is
frozen (second manifest). The holdout is never edited; a defective holdout case is marked VOID in an addendum.

---
Addenda (append only)
