# Report H: Can existing deterministic checks stop the specialists' wrong actions?

Question (owner's direction, 2026-10-01): before adding any model-based verification, would URI's **existing** deterministic grounding and ambiguity mechanisms have prevented the incorrect actions EPQ-1 recorded?

Method: offline replay of the recorded holdout outputs (first repeat) through existing URI code, imported read-only. No model was called and no file outside `experiments/` was changed. Script: `boundary_replay.py`; output: `results/boundary_replay.json`.

| Check | Existing component |
|---|---|
| D1 | M36 `negated(text)` (frozen) |
| D2 | M36 `affirmative_context` on the request with the proposal's verbatim arguments removed, as `affirmative_around` does (frozen) |
| D3 | deterministic RAR `resolve_rar_deterministic_extended`, with the trusted attachment list as candidates. AMBIGUOUS or UNKNOWN means clarify; resolving to a different file than the one proposed means block |
| D4 | `uri_core` `plausible_matches`: the proposed action must be among the request's top-k capability-relevance matches |

## 1. Per-check discrimination (select proposals that URI containment would have executed)

| Check | Granite JSON: wrong blocked / right lost | Needle: wrong / right | Granite native: wrong / right |
|---|---|---|---|
| D1 M36 negation | 5/22 · 7/28 | 7/25 · 5/21 | 1/20 · 9/34 |
| D2 M36 affirmative allowlist | 19/22 · **27/28** | 24/25 · **20/21** | 18/20 · **33/34** |
| D3 RAR reference | 1/22 · 0/28 | 3/25 · 0/21 | 5/20 · 1/34 |
| D4 relevance top-3 or top-5 | 19/22 · 16/28 | 21/25 · 12/21 | 17/20 · 21/34 |
| D1 + D3 | 6/22 · 8/28 | 10/25 · 5/21 | 6/20 · 10/34 |
| D1 + D3 + D4 | 21/22 · 18/28 | 24/25 · 14/21 | 19/20 · 23/34 |
| all four | 22/22 · 28/28 | 25/25 · 21/21 | 20/20 · 33/34 |

## 2. End to end (M36 gate, deterministic rules, specialist, check, then Brain on block or rejection; holdout 138)

| Specialist | no extra check | D1 + D3 | D1 + D3 + D4 | all | Main Brain alone |
|---|---|---|---|---|---|
| Granite JSON | 86 ok / 45 wrong / 49 Brain | 87 / 44 / 51 | 91 / 37 / 70 | 91 / 37 / 76 | 109 / 17 / 138 |
| Needle | 82 / 54 / 50 | 83 / 53 / 52 | 93 / 40 / 73 | 94 / 38 / 79 | |

With every check on, the Granite hybrid's 37 wrong results come from: 13 from the experimental deterministic rules (the filename bug; 3 after fix1), 7 from the Brain's own fallbacks, and **17 from specialist extraction, route and label outputs, where no deterministic check exists**.

## 3. Findings

1. **Existing deterministic checks block wrong specialist actions only by also blocking right ones.** The allowlist (D2) and capability relevance (D4) block 76–96% of wrong executions and also 57–97% of correct ones. In effect, they work by not using the specialist for selection at all. Neither can tell a right tool choice from a wrong one, because both judge the wording of the request, not the proposal's meaning.
2. **RAR is the one existing check that discriminates.** On reference cases it blocked 1–5 wrong executions and lost 0–1 correct ones, and it turns the ambiguous-attachment case into a clarification (report D, W3). Its coverage is narrow: it applies only where a trusted candidate set exists, and it returns `UNKNOWN / PRONOUN_BINDING` for "it" even with one candidate, so it relies on a session binding producer (the M36 envelope) for follow-ups.
3. **M36 negation routing is already accounted for** in the hybrid (negated requests go to the Brain). As a post-check on proposals, it blocks some wrong actions but loses correct ones such as "Search Drive, not Gmail…".
4. **For extraction, routes and labels, no existing deterministic check can tell right from wrong.** N5 verbatim grounding accepts any real span, including injected decoys. Enums are closed but not checkable against meaning.
5. **Even with every check, Edge in front of the Brain stays below the Brain alone** (91 against 109 successful turns; 37 against 17 wrong), while still cutting Brain calls to 51–57% of turns.

## 4. What this means for the integration boundary

- **Execution permission must not follow from gate validity.** URI's gates answer "may this run?" (authority, availability, schema). Nothing in the current pipeline answers "is this what the user asked for?" for a specialist proposal. That gap is the architectural finding, and it applies equally to the Main Brain's own native tool calls; the Brain is simply wrong less often.
- **Deterministic context resolution belongs before the specialist, not after it.** Run RAR and the binding state (M36) first. Clarify on AMBIGUOUS or UNKNOWN references. Offer a specialist only a request whose references are already bound. This is the only boundary here that removes wrong actions without removing right ones.
- **A specialist proposal that RAR and binding cannot confirm should go to the Brain or the user, not to execution.** Gate validity alone is not enough.
- **Narrow candidate capabilities for a later, focused qualification** (measured, not assumed):
  - a deterministic-first reference-bound read path (RAR resolved plus a single read-only action), where no model chooses at all;
  - abstention or escalation as a specialist's only job, scored on false-accept rate. Needle was relatively best here and still failed;
  - extraction only behind a confirmation step for any consequential value, because N5 cannot detect a planted span.
- **Not recommended:** adding a second small model as a semantic verifier of the first. Replacement turned a safe rejection into a wrong execution (report D §3), and the pair produced more wrong results than either model alone.

## 5. Limits

- 138 holdout cases, first repeat; per-check counts are small (20–34 executed proposals per arm).
- D3 uses the trusted attachment list from the battery's conversation state as RAR candidates. Real candidate sets come from URI's session and file store.
- ARN was not tested: it exists only untracked in `_V1` and is not on the frozen line or this branch.
- The deterministic rules in the hybrid are the experimental EPQ-1 rules; with fix1, 10 fewer wrong results come from that layer, which does not change any finding.
- Not independently audited (Codex pending).
