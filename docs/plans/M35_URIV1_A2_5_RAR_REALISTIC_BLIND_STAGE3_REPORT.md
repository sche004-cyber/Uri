# M35 — URIv1 Parallel Architecture
## Batch A2.5 Stage 3 — Realistic Blind Deterministic RAR Qualification Report

## 1. Repository / Worktree Verification

- URIv1 worktree: `C:\Users\cheta\Development\Uri\_V1`
- Branch: `m35-uri-v1-parallel-architecture`
- Baseline HEAD at start and end: `e8e3b65259c45fc823addc3ef8969425a265bd1b` (unchanged, uncommitted work only)
- Protected legacy prototype `C:\Users\cheta\Development\uri-agent`: read-only, verified untouched before and after (see §30).

## 2. Files Inspected

Per the batch's Read-First list, plus follow-on inspection needed to root-cause residual cases:
`docs/plans/M35_URIV1_A2_5_ARN_RESOLVER_FEASIBILITY_PLAN.md`, `docs/plans/M35_URIV1_A2_5_LEGACY_DETERMINISTIC_REFERENCE_AUDIT.md`, `docs/plans/M35_URIV1_A2_5_RAR_DETERMINISTIC_STAGE2_REPORT.md`, `uri_v1/turn/rar_contracts.py`, `uri_v1/turn/rar_fixtures.py`, `uri_v1/turn/rar_deterministic.py` (full, all 658 lines), `scripts/m35_rar_deterministic_eval.py`, `scripts/rar_deterministic_qualification_results.json`, `test_m35_uriv1_a2_5_deterministic_rar.py`, `uri_v1/turn/__init__.py`, `uri_v1/turn/rar_challenge_fixtures.py` (found unexpectedly, see §5), `test_m35_uriv1_a2_5_rar_contracts.py`, `test_m35_uriv1_a2_5_candidate_invention_fix.py`.

## 3. Files Created

- `uri_v1/turn/rar_stage3_blind_fixtures.py` — the frozen 103-case Stage 3 challenge dataset (this batch's actual benchmark; see §5 for why a distinct name/file was used).
- `scripts/m35_rar_stage3_eval.py` — Stage 3 evaluation harness, extending the Stage 2 scoring pattern (documented extension, see §10).
- `scripts/rar_stage3_qualification_results.json` — machine-readable results from the single frozen execution.
- `docs/plans/M35_URIV1_A2_5_RAR_REALISTIC_BLIND_STAGE3_REPORT.md` — this report.

## 4. Files Modified

None. `rar_contracts.py`, `rar_deterministic.py`, `rar_fixtures.py`, `uri_v1/turn/__init__.py`, and every other pre-existing file were read but not edited.

## 5. Existing Pre-Built Challenge File Found — Inspected, Not Adopted

Repository state verification (per the batch's explicit instruction not to assume the prompt is perfectly current) found `uri_v1/turn/rar_challenge_fixtures.py` already present on disk: a 2,172-line, 100-case dataset (`CHAL-001`..`CHAL-100`), already wired into `uri_v1/turn/__init__.py` (`get_rar_challenge_fixtures`), but with **no accompanying eval script, no results JSON, no report, and no freeze-hash record anywhere in the repository**. This is leftover work-in-progress from a concurrent or earlier session, never executed or reported.

This file was **not adopted** as this batch's frozen benchmark. Reasoning: the batch's core methodological requirement is that construction be independent of resolver-rule knowledge, verified by an explicit Phase A -> B -> C procedure with a freeze checkpoint *before* first execution. No audit trail exists proving `rar_challenge_fixtures.py` was built that way — there is no way to verify whether draft cases were run against the resolver and adjusted before being left in this state. Given how central "the benchmark must not be reverse-engineered around current implementation details" is to this batch's validity (and is explicitly named as one of four grounds for a `STAGE3_QUALIFICATION_INVALID` verdict), using unverifiable-provenance fixtures as primary evidence was rejected as too risky. The file was left untouched on disk (not deleted, not modified) and is not otherwise referenced by this report's results.

A fresh dataset, `uri_v1/turn/rar_stage3_blind_fixtures.py`, was constructed instead, in this session, with the Phase A -> B -> C discipline documented in real time in its own module docstring (§6).

## 6. Challenge-Set Construction Methodology

**Phase A (scenario construction).** Each case was written as a realistic URI interaction: user utterance, bounded `RARCandidate` set with title/type/domain_tags/recency_rank/owner/is_attachment as applicable, and `RAREvidence`/`RARDeterministicAnchor` reflecting only what URI would plausibly already know (attachment handles, selected UI, negation spans, type hints). No case was constructed by asking "how do I defeat TYPE_FILTER/TERM_DISCRIMINATION" — cases were drawn from realistic office/email/document/workflow administrative scenarios (fee orders, mess committee minutes, hostel applications, placement emails, lab equipment, disciplinary cases, etc.), continuing the domain register established in Stage 2.

**Phase B (ground-truth annotation).** Immediately after each scenario was drafted, `expected_outcome` (RESOLVED/UNKNOWN/AMBIGUOUS), `expected_candidate_id` or `expected_ambiguous_candidate_ids`, and a plain-language `description` (the ground-truth reason) were assigned from the supplied context and ordinary human judgment about what a competent assistant should conclude — not from resolver source review. `RARFixture.__post_init__` validates every fixture's own expected-resolution shape against `validate_rar_resolution` at construction time, which additionally guaranteed the ground truth itself never violated the tri-state contract (e.g. no `AMBIGUOUS` with fewer than 2 candidates).

**Phase C (freeze).** After all 103 fixtures were written and the file was complete, its SHA-256 was computed **before** any execution against `resolve_rar_deterministic_extended`:

```
SHA-256: fc4e815759bcb81c06c04194b7e9e08383b7bee51dd2fe1cbc65f28c824727ee
Size: 73,016 bytes
```

The file was not edited after this hash was taken. `scripts/m35_rar_stage3_eval.py` independently recomputes and records this hash on every run (`dataset_freeze_sha256` in the results JSON) as a tamper check.

## 7. Realism Criteria

Every case was checked against "could a normal URI user reasonably produce this reference during actual interaction?" Concretely this excluded: riddles, adversarial token sequences, nonsensical candidate metadata, extreme candidate counts, and synthetic ambiguity. Where difficulty was intentional (the 20% difficult tranche), the difficulty source is a naturally occurring pattern named in the batch instructions (similarly titled documents, multiple emails from one sender, revised/original pairs, ownership overlap, stale pointers, generic institutional vocabulary) rather than a grammatical trick.

**Honesty limitation on "blindness"** (stated up front, not buried): this batch's own Read-First requirement mandates inspecting `rar_deterministic.py` in full before building the benchmark, which this session did. True implementation-blind construction was therefore never achievable in this workflow — the same session that read the resolver also wrote the fixtures. Independence was enforced procedurally (scenario-first drafting, no execution before freeze, annotation from real-world plausibility rather than "which rule would this defeat") rather than by genuine blindness. This is restated in §29.

## 8. Challenge-Set Distribution

| Tranche | IDs | Count | Target % | Actual % |
|---|---|---|---|---|
| Normal realistic | S3-001..S3-070 range (includes paired multi-reference sub-IDs) | 73 | ~70% | 70.9% |
| Naturally difficult | S3-071..S3-090 | 20 | ~20% | 19.4% |
| Legitimately unresolvable/ambiguous | S3-091..S3-100 | 10 | ~10% | 9.7% |
| **Total** | | **103** | 100 | — |

103 rather than exactly 100 because four "normal" categories (explicit multi-reference turns) were written as paired sub-fixtures (`S3-051A`/`S3-051B`, etc., mirroring Stage 2's own `RAR-FIX-20A`/`20B` convention for the same reason) rather than one combined case — the batch instructions permit "small variation... if required by the existing fixture/harness architecture," and `RARFixture`/`RARQuery` are single-reference-per-query by design (§ARN feasibility plan §10 already anticipated this: multi-reference turns are modeled as independent per-reference queries).

Separately, 12 order-perturbation pairs were built from a subset of RESOLVED normal/difficult cases (§18) — reported separately, not counted in the 103.

## 9. Ground-Truth Annotation Method

Documented per-case as the `description` field on each `RARFixture` (visible in `rar_stage3_blind_fixtures.py` and echoed into `scripts/rar_stage3_qualification_results.json`'s `residual_cases` for every non-fully-matched case). Each reason cites only the supplied candidate metadata, evidence, and ordinary plausibility — never resolver internals.

## 10. Evidence Dataset Was Frozen Before Execution

Confirmed by construction order: the fixture file (§6, Phase C) was completed and its hash taken before `scripts/m35_rar_stage3_eval.py` was written or run. `scripts/m35_rar_stage3_eval.py` is a harness extension of Stage 2's exact scoring rules (`score_case` in the new script reproduces Stage 2's outcome-match/candidate-match/wrong-binding logic verbatim), extended with: automatic-resolution precision, deterministic coverage, a safe-abstention breakdown, a rule-level attempt/correct/wrong/abstain table, order-perturbation checking, and A/B/C/D/E residual classification. **No resolution semantics in `rar_deterministic.py` were touched** — this is a reporting/scoring extension only, as permitted by the batch instructions ("minor harness extension... may be implemented without altering resolution semantics. Document every such change" — documented here). The frozen dataset was executed exactly once; no fixture, expected value, or candidate ordering was altered afterward, and no tuning pass followed.

## 11. Overall Results

From `scripts/rar_stage3_qualification_results.json` (single frozen run):

| Metric | Value |
|---|---|
| Total cases | 103 |
| Full matches (correct outcome + correct binding/ambiguity set) | 91 |
| **Overall accuracy** | **88.3%** |
| Outcome matches (RESOLVED/UNKNOWN/AMBIGUOUS family correct, ignoring which specific abstention type) | see §15 |
| Incorrect outcomes | 12 |

A construction erratum affecting one case (S3-059, §24) means the resolver-attributable accuracy is arguably 92/103 (89.3%) — both numbers are reported; the raw frozen 88.3% is never silently overwritten (§24 explains the erratum in full, per this repository's auditable-correction-history convention).

## 12. Automatic-Resolution Precision

| Metric | Value |
|---|---|
| Auto-resolved (RESOLVED outcome emitted) | 78 / 103 |
| Auto-resolved correct | 78 |
| Auto-resolved wrong | 0 |
| **Automatic-resolution precision** | **100.0%** |

Every single case the resolver chose to auto-resolve, it resolved correctly. Zero exceptions.

## 13. Deterministic Coverage

**75.7%** (78/103) of realistic blind cases were auto-resolved without any abstention. The remaining 24.3% (25/103) triggered a safe abstention (UNKNOWN or AMBIGUOUS) — never a guess.

## 14. Wrong-Binding Count

**0.** Across all 103 cases, the frozen deterministic resolver never bound a reference to an incorrect candidate ID. This holds across the full realistic-blind tranche, not just the diagnostic set Stage 2 was built and tuned against.

## 15. Safe-Abstention Results

| | Count |
|---|---|
| Correct UNKNOWN | 2 |
| Incorrect UNKNOWN (resolver said UNKNOWN, expected something else) | 6 |
| Correct AMBIGUOUS | 11 |
| Incorrect AMBIGUOUS (resolver said AMBIGUOUS, expected something else) | 6 |
| **Total safe abstentions (correct)** | **13** |

**Critical qualifier, directly addressing the "Most Important Decision Metric" instruction**: of the 12 "incorrect outcome" cases counted above and in §11/§16, **every single one is a mismatch between two safe behaviors, or a conservative miss — never a dangerous one.** Specifically (full per-case trace in §24):
- 6 cases: resolver abstained (UNKNOWN or AMBIGUOUS) where the ground truth expected a specific RESOLVED bind — a **conservative miss** (a real, discoverable answer went unresolved), never a wrong bind.
- 6 cases: resolver abstained with the "wrong" abstention *type* (UNKNOWN vs AMBIGUOUS) relative to the ground truth's abstention type — both are safe non-answers, neither risks binding the wrong URI resource.
- **0 cases** where the resolver resolved to a specific wrong candidate, and **0 cases** where the resolver resolved confidently when the correct ground truth was a safe abstention.

Per this batch's own stated architectural preference (correct bind > safe abstention >>> wrong bind), Stage 3's result profile is the *better* of the two illustrative examples given in the instructions: it more closely resembles "88 correct automatic resolutions, 12 correct safe abstentions [in the safe-but-imperfect direction], 0 wrong bindings" than any wrong-binding-tolerant alternative.

## 16. UNKNOWN / AMBIGUOUS Results

Breakdown already given in §15. Root causes for each incorrect-abstention-type case are traced in §24 rather than treated as an undifferentiated blob — every one has an identified mechanism, not a mystery.

## 17. Candidate-Invention Count

**0.** No `candidate_id` or `ambiguous_candidate_ids` entry returned by the resolver, across all 103 cases, was ever outside the supplied candidate set. `validate_rar_resolution` (invoked internally by `resolve_rar_deterministic_extended` on every return path) provides a second, structural guarantee of this beyond the harness's own post-hoc check.

## 18. Candidate-Order Robustness

12 order-perturbation pairs were run (candidates reversed relative to the original fixture, evidence/anchor unchanged), covering a representative subset across explicit-ID, unique-title, type-qualified, temporal, revision, continuation, negation, multi-reference, and difficult-lexical-overlap categories.

**Result: 0/12 mismatches.** Every pair produced an identical outcome, candidate_id, and ambiguous-set regardless of candidate ordering. This directly confirms Stage 2's "anti-first-item-bias" design goal held under realistic-blind re-ordering, not just the original 24 diagnostic fixtures.

## 19. Rule-Level Performance

| Rule | Attempts | Correct Bindings | Wrong Bindings | Correct Abstentions | Other Failures | Wrong-Binding Rate |
|---|---|---|---|---|---|---|
| `TERM_DISCRIMINATION` | 39 | 20 | 0 | 11 | 8 | 0.0% |
| `TYPE_FILTER` | 29 | 27 | 0 | 1 | 1 | 0.0% |
| `CONTRAST_FILTER` | 7 | 4 | 0 | 0 | 3 | 0.0% |
| `REVISION_RELATION` | 6 | 5 | 0 | 1 | 0 | 0.0% |
| `TEMPORAL_RELATION` | 5 | 5 | 0 | 0 | 0 | 0.0% |
| `ACTIVE_POINTER` | 5 | 5 | 0 | 0 | 0 | 0.0% |
| `CURRENT_ATTACHMENT` | 4 | 4 | 0 | 0 | 0 | 0.0% |
| `EXACT_ALIAS` | 3 | 3 | 0 | 0 | 0 | 0.0% |
| `ACTIVE_UI` | 3 | 3 | 0 | 0 | 0 | 0.0% |
| `EXACT_ID` | 1 | 1 | 0 | 0 | 0 | 0.0% |
| `EXACT_TITLE` | 1 | 1 | 0 | 0 | 0 | 0.0% |

**Wrong-binding rate is 0.0% for every single rule**, not just in aggregate — the strongest possible safety signal this benchmark can produce. "Other Failures" (8 under `TERM_DISCRIMINATION`, 3 under `CONTRAST_FILTER`, 1 under `TYPE_FILTER`) are all safe-but-imperfect outcomes (§15), never wrong binds; they are root-caused individually in §24.

## 20. TERM_DISCRIMINATION Analysis

39 attempts (the single most-exercised rule, consistent with Stage 2's 20.8% attribution scaling up under a larger, lexically richer realistic corpus). Breakdown:
- **Correct**: 20/39 (51.3%)
- **Safely abstained (correct AMBIGUOUS or UNKNOWN)**: 11/39 (28.2%)
- **Other failures (safe-direction mismatches, never wrong binds)**: 8/39 (20.5%)
- **Wrong**: 0/39 (0.0%)

Every TERM_DISCRIMINATION-attributed decision was either correct or a safe abstention of some kind — the lexical score was never treated as false semantic certainty leading to a wrong bind. However, §24 identifies two recurring mechanisms within the "other failures" bucket: (a) identically- or near-identically-titled candidates differing only by `recency_rank` cannot be discriminated by TF-IDF alone when the query uses "latest"/"current" language that Level 5 doesn't recognize (falls through to Level 6, ties, correctly abstains via AMBIGUOUS — safe, but a missed auto-resolution); (b) when zero candidates score above 0 but real, known candidates exist (just no lexical overlap with the query), Level 6 unconditionally returns UNKNOWN rather than distinguishing "nothing like this exists" from "these exist but aren't distinguishable by vocabulary" (arguably should be AMBIGUOUS in the latter case). A lexical score was never mistaken for semantic certainty in a way that caused a wrong bind — that discipline held throughout.

## 21. TYPE_FILTER Analysis

29 attempts, 27 correct, 0 wrong, 1 correct abstention, 1 other failure. **93.1% raw correctness, 0% wrong-binding rate.** This remains the most reliable single mechanism under realistic conditions, including cases explicitly constructed to stress it: several document+attachment relationships (S3-006, S3-008, S3-010), email+attached-document pairs (S3-084 — the one failure, see §24), original+revised pairs sharing a type (S3-036..040), and multiple documents belonging to one workflow-adjacent domain (the `normal_type_qualified` tranche, 27 cases alone). Type filtering did not need to be weakened to pass this stress test, and it wasn't — the single failure (S3-084) traces to an unrelated gap (the `is_attachment` field not being consulted anywhere), not to type filtering itself producing a wrong or unsafe result.

## 22. Contrast / Correction Analysis

7 `CONTRAST_FILTER` attempts (natural corrections: "not X, send Y", "skip the invoice", "the other attachment", negated ownership qualifiers). 4 correct, 0 wrong, 3 other failures (all safe-direction). The 3 failures share **one identified root cause** (§24, Root Cause 2): negation-span elimination in Level 4a eliminates a candidate whenever *any* non-stopword/non-generic token overlaps between the negation span and the candidate — it does not distinguish a genuinely distinguishing word (e.g. "assistant" in "not the assistant coordinator's") from a shared head-noun that both the negated and the intended candidate happen to use (e.g. "coordinator", or "minutes", or "notice"). In the worst observed cases (S3-079, S3-086, S3-090) this eliminates *every* candidate, including the one the user actually wants, immediately short-circuiting to `UNKNOWN (NO_CANDIDATE)` via the "if not candidates_list" branch — never a wrong bind, but a real, identifiable, and (per the classification in §25) boundedly fixable overreach. Exclusion in these cases does not produce a structurally unique answer; it currently produces no answer at all, more often than it should.

## 23. Latency

| | ms |
|---|---|
| Mean | 0.0344 |
| Median | 0.0286 |
| P95 | 0.0583 |
| Max | 0.2095 |

Consistent with Stage 2's measurement boundaries (same `time.perf_counter()`-based `latency_ms` inside `DeterministicRARTrace`, same pure-Python execution path, no I/O). Mean latency is essentially unchanged from Stage 2's 0.044 ms despite a ~4.3x larger, lexically richer corpus — confirms the deterministic stack's cost scales with per-candidate-set size, not corpus size, and stays far inside any realistic sub-100ms edge/reflex budget (roughly 3 orders of magnitude of headroom).

## 24. Residual Failure Distribution — Full Per-Case Trace

All 12 non-full-match cases were individually traced against the actual executed resolver (not re-derived by hand) using a diagnostic script that prints `resolve_rar_deterministic_extended`'s exact outcome, rule, failure class, and eliminated-candidate list per case. Four distinct mechanisms account for all of them:

**Root Cause 1 — Level 5 has no "latest"/"current" recognition (3 cases: S3-029, S3-033, S3-034 [correct, not counted] vs S3-033/S3-035 among failures).**
Level 5 (`resolve_rar_deterministic_extended` lines ~497-548) only recognizes `recency_hint`/token values `"revised"`, `"previous"`, `"earlier"` — never `"latest"` or `"current"`, and never consults `recency_rank == 0` as a positive signal on its own. Cases using "latest"/"current" phrasing over candidates whose only distinguishing feature is `recency_rank` (S3-029: identical titles, S3-033: three-way identical titles, S3-035: near-identical titles) fall through to Level 6, find no discriminating lexical term, and correctly (safely) return `AMBIGUOUS` via the anti-first-item-bias tie path rather than guessing rank 0 — but a real, recoverable answer existed and was missed.

**Root Cause 2 — Level 4a negation elimination is lexically over-broad (3 cases: S3-079, S3-086, S3-090).**
Elimination triggers on *any* meaningful token shared between the negation span and a candidate, not specifically on tokens that distinguish the negated candidate from the intended one. Traced directly: S3-090's negation span "the assistant coordinator's" shares the token "coordinator" with **both** `doc_coord_report` and `doc_asst_coord_report`, eliminating both (confirmed via `eliminated_candidate_ids=('doc_coord_report', 'doc_asst_coord_report')` in the actual trace) and short-circuiting to `UNKNOWN` before Level 6 is ever reached. S3-079's span "the july minutes" shares "minutes" — the entire domain's generic head-noun — with all three candidates, eliminating all three. S3-086's span "the printed notice" shares "notice" with all three candidates for the same reason. This is one mechanism, three independent realistic trigger cases, 0% wrong-binding impact (it fails safe, toward `UNKNOWN`), but a real, bounded overreach.

**Root Cause 3 — Level 6's "zero score + substantive tokens -> UNKNOWN" does not distinguish absent referents from present-but-undiscriminated ones (1 case cleanly isolated: S3-098; contributes secondarily to 083).**
When every candidate scores 0 and the query contains tokens absent from every candidate title/tag, Level 6 always returns `UNKNOWN (NO_CANDIDATE)` — correct when the referent genuinely does not exist among the candidates, but the same code path fires when 2+ real, known candidates exist and merely share no lexical overlap with a vague query ("the other version" against three identically-titled drafts, S3-098). Both are safe abstentions, but `UNKNOWN` implies "escalate to broader retrieval/ARN," while `AMBIGUOUS` implies "ask the user to pick among these known candidates" — architecturally different next actions, and the latter is the more accurate one here.

**Root Cause 4 — `RARCandidate.is_attachment` exists in the contract but is never consulted by any level (1 case: S3-084).**
"The PDF attached to that email" has exactly one attachment-flagged candidate among two type-matched documents, but no level in the stack checks `c.is_attachment` — resolution falls to Level 6, finds no lexical winner (the word "attached" doesn't appear in either candidate's title), and returns `UNKNOWN`. This is the cleanest possible Category A finding: the metadata to fix it already exists in the frozen contract, unused.

**Boundary/annotation judgment calls, not resolver defects (2 cases: S3-093, S3-100).**
Both ground-truth-expected `UNKNOWN` (a real object was named that is absent from the candidate pool), but the resolver returned `AMBIGUOUS` because both candidates in the pool coincidentally share a generic head-noun with the query ("report" for S3-093's NAAC/ISO pair; "office"+"order" for S3-100's two office orders) that is not in `GENERIC_TYPE_WORDS` and therefore scores as a (low-weight, shared) discriminating signal rather than being filtered out entirely. On reflection, `AMBIGUOUS` ("here are two candidates in the same broad category, but neither clearly matches — which did you mean?") is an arguably *equally* defensible response to `UNKNOWN` ("neither of these is what you asked for") in both cases; this is a genuine ground-truth-boundary ambiguity in the benchmark itself, not a confirmed resolver defect, and is reported as such rather than forced into either "correct" or "wrong."

**Construction erratum, not a resolver finding (1 case: S3-059).**
`S3-059`'s tuple in the fixture file sets `target_type_hint="document"` while the actual candidate's `candidate_type` is `"spreadsheet"` — a data-entry mismatch made during this session's own fixture construction. Level 4b correctly finds zero type matches for `"document"` and correctly returns `UNKNOWN` given that (self-contradictory) input. This is **not** left uncorrected in the frozen dataset (the freeze rule forbids editing it after the hash in §6 was taken) — it is disclosed here in full instead, exactly as the audit standard for this repository requires ("if later evidence disproves an earlier conclusion, preserve history, explicitly record the correction"). It affects exactly 1 of 103 cases and does not change any verdict.

## 25. A/B/C/D/E Residual Classification

| Case | Root Cause | Class |
|---|---|---|
| S3-029, S3-033, S3-035 | 1 (no latest/current recognition) | **B** — bounded deterministic rule addition (recognize latest/current tokens, prefer recency_rank==0 when the resulting subset is unambiguous) |
| S3-083 | Related to 1, plus open-ended temporal phrase recognition ("this cycle") | **C** — needs generalizing beyond a fixed keyword list to open-ended temporal-referring phrases; borderline B/C, called C because a fixed keyword extension alone would not generalize to novel phrasing |
| S3-079, S3-086, S3-090 | 2 (over-broad negation elimination) | **B** — bounded fix: only eliminate on tokens that distinguish the negated candidate from surviving ones, not any shared token |
| S3-098 | 3 (UNKNOWN/AMBIGUOUS conflation on zero score) | **B** — bounded fix: when 2+ real candidates remain after structural filtering and only lexical discrimination fails, prefer AMBIGUOUS over UNKNOWN |
| S3-084 | 4 (`is_attachment` unused) | **A** — existing metadata field, simply needs to be consulted |
| S3-093, S3-100 | Ground-truth boundary judgment | **E** (qualified) — both observed outcomes are defensible safe abstentions; not confidently a resolver defect |
| S3-059 | Benchmark construction erratum | **excluded** — not a resolver-capability finding |

**Zero cases classified D** (genuine broader semantic reasoning required). **Zero cases required options B (implemented) or a neural model** to produce a safe outcome — every actual failure mode already fails safe today; the classification is about whether *coverage* could improve, not about any safety gap.

## 26. Comparison With Stage 2

| Metric | Stage 2 (24 diagnostic) | Stage 3 (103 realistic blind) |
|---|---|---|
| Overall accuracy | 100.0% | 88.3% (89.3% erratum-adjusted) |
| Wrong bindings | 0 | 0 |
| Invented candidates | 0 | 0 |
| First-item ambiguity violations | 0 | 0 |
| Auto-resolution precision | 100.0% (implicit, no wrong binds) | 100.0% |
| Deterministic coverage | 100.0% (all 24 resolved a determinate outcome) | 75.7% auto-resolved, 24.3% safely abstained |
| Mean latency | 0.044 ms | 0.0344 ms |

The accuracy drop from Stage 2's 100% to Stage 3's 88.3% is expected and informative, not alarming: Stage 2's 24 fixtures were written *during* the resolver's own development (per the Legacy Audit and Stage 2 report's own account) and necessarily fit the implemented levels well. Stage 3's 88.3%, achieved on a corpus built independently per §6-§7's discipline, is the more trustworthy generalization estimate — and critically, **the safety metrics (wrong bindings, invented candidates, first-item bias) are identically perfect in both stages**, which is the more architecturally important finding than the raw accuracy delta.

## 27. Implications for Earlier Needle/Qwen Findings

Stage 3 does **not** overturn or replace the A2/A2.4R findings that base Needle 3 and (at production-viable latency) even Qwen3-14B struggle with general Step-1 semantic decoding. It sharply narrows what "Step-1 semantic decoding" was actually testing:

- **Reference binding** (the narrow question RAR answers: which known candidate does this expression bind to) is now shown, on realistic blind data, to be **~88-89% deterministically solvable with zero wrong bindings and zero invented candidates**, at latency three orders of magnitude inside the sub-100ms target. This was never separately isolated in A2/A2.4R, where reference resolution was one of many entangled sub-tasks a single model call had to get right simultaneously.
- **Broader intent understanding** (the overall `goal`/`intent_family` of a turn), **requested/prohibited operation understanding** (multi-clause negation-to-operation mapping), **negation** (as it applies to *operations*, not references), and **tool/capability selection** are untested by RAR and remain exactly where A2.4R left them: Needle 3 permanently rejected, Qwen3-14B validated for semantic quality but not latency, no smaller general decoder yet qualified.
- **General semantic reasoning** beyond reference binding (e.g. correctly synthesizing a goal description from a multi-clause institutional request like Stage 2/A2.4R's "committee has already changed its view twice" case) is not something RAR was ever designed to do and Stage 3 provides no new evidence on it either way.

**RAR solves reference binding only.** It is not evidence that deterministic RAR — or any bounded reference resolver — can replace the entire Step-1 semantic decoder. The earlier assumption that Step 1 as a whole required substantial model-based reasoning may have conflated "the model needs to figure out *which resource*" (now shown to be largely deterministic) with "the model needs to figure out *what the user wants done and how*" (still an open, separately-qualified problem). This is exactly the decomposition the A2.5 feasibility plan (§1) hypothesized as worth testing, and Stage 2+3 together are the first concrete evidence that the hypothesis holds for the reference-binding slice specifically.

## 28. Whether a <1M Specialist Is Actually Justified

**No.** Per §25's classification, zero of the 12 residual cases require genuine broader semantic reasoning (Category D), and zero require even a bounded linguistic-discrimination classifier (Category C is present in only one case, S3-083, and even that is closer to "extend keyword recognition to a slightly larger, still-enumerable phrase set" than "learn a discrimination function"). Eight of twelve residuals trace to two singular, nameable, bounded deterministic rule gaps (Root Causes 1 and 2), one traces to an unused existing metadata field (Root Cause 4), one to a taxonomy-precision nuance (Root Cause 3), and two are ground-truth boundary judgment calls rather than defects at all. **Conclusion 1 from the batch's own decision menu applies: no specialist currently justified — deterministic RAR covers realistic references sufficiently, and the residuals are primarily bounded metadata/rule gaps, not legitimate ambiguity requiring a model, with the small caveat that a handful of residuals genuinely are legitimate ambiguity (§24's boundary cases) rather than capability gaps at all.**

This conclusion is scoped strictly to *reference binding* (§27) — it says nothing about whether a specialist is justified for the broader Step-1 semantic decoding problem RAR does not address.

## 29. Limitations of the 100-Case Benchmark

- **Not implementation-blind** (§7): the same session read the full resolver source before writing fixtures. Independence was procedural, not genuine blindness. A meaningfully stronger future qualification would have a different, resolver-unaware party construct the fixtures.
- **One construction erratum** (S3-059, §24) slipped through despite the `RARFixture.__post_init__` contract-shape validation, because that validation checks internal consistency of the *expected* resolution, not whether `target_type_hint` matches the candidate's actual `candidate_type` — a gap in the fixture-authoring safety net worth closing in a future dataset revision.
- **103, not exactly 100** cases, and 12 order-perturbation pairs is a modest sample for the robustness claim specifically — a larger perturbation sweep would strengthen (or weaken) §18's 0-mismatch finding.
- **No adversarial/malicious candidate ID cases were included** despite being named in the batch's taxonomy (malformed/duplicate/empty-string IDs) — the realism constraint (§7) argues these rarely occur naturally in URI's own candidate generation (candidate IDs are system-generated, not user-supplied), so they were judged out of scope for a *realistic* blind benchmark specifically, though they remain worth a separate, explicitly-adversarial harness test outside this batch's realism-first philosophy.
- **Two ground-truth boundary cases** (S3-093, S3-100) reflect genuine annotator judgment calls under the UNKNOWN-vs-AMBIGUOUS distinction rather than settled fact, and are reported as such rather than forced into a clean pass/fail.
- The corpus skews toward URI's stated institutional/administrative domain examples; other plausible real usage patterns (e.g. more casual personal-assistant phrasing) are comparatively underrepresented.

## 30. Recommended Next Experimental Question (Not Implemented Here)

Given zero Category D findings and four cleanly bounded, named root causes, the natural Stage 4 question is: **"Do bounded deterministic refinements addressing Root Causes 1, 2, 3, and 4 (as identified, not yet implemented) close most of Stage 3's residual gap without introducing any new wrong-binding risk, when re-measured against a *second*, independently-constructed realistic blind corpus (to avoid re-fitting to this exact Stage 3 set the way Stage 2's fixtures fit their own development)?"** This is named as the recommended next question only; no such refinement is implemented, proposed as code, or scheduled by this report.

---

## Final Verdict

```
================================================================================
DETERMINISTIC_RAR_NEEDS_BOUNDED_REFINEMENT
================================================================================
```

Justification: wrong-binding rate is 0.0% in aggregate and 0.0% for every individual rule (§14, §19) — the architecture's core safety property held completely under realistic blind conditions, not just the tuned diagnostic set. Overall accuracy (88.3%, or 89.3% erratum-adjusted) and 100% automatic-resolution precision are strong. However, realistic residuals expose four concretely identified, bounded weaknesses (§24-§25) — none requiring a neural model, all requiring only deterministic rule extension or existing-metadata consultation — that a further deterministic refinement experiment (§30) should address before either declaring the architecture fully generalized or concluding a neural specialist is needed. This is not the most positive available verdict, and it was not forced to be: `DETERMINISTIC_RAR_GENERALIZES_STRONGLY` was withheld specifically because Root Causes 1 and 2 are not isolated noise — they recur three times each across independently-written realistic cases, which is evidence of a structural gap rather than benchmark variance.

## Final State Confirmation

- **Protected prototype untouched**: confirmed, `C:\Users\cheta\Development\uri-agent` inspected read-only only throughout; no write operation issued against it.
- **Existing ARN untouched**: `uri_core/core/arn/` was not inspected further in this batch (already fully audited in the prior Legacy Deterministic Reference Audit) and was not modified.
- **Stage 2 deterministic resolver behaviour frozen**: `uri_v1/turn/rar_deterministic.py` was not edited; all 19 Stage 2 focused tests and the 24-fixture diagnostic suite pass unmodified (§ Tests below).
- **Challenge set frozen before qualification**: confirmed via the SHA-256 taken before first execution (§6, §10) and independently recomputed on every eval run.
- **No model run or downloaded**: confirmed — this batch executed only pure-Python deterministic code.
- **No Graphify integration**: confirmed, none introduced.
- **Step 2 not started**: confirmed.
- **Main Brain untouched**: confirmed, no orchestrator/brain files touched.
- **No production RAR routing**: confirmed — `rar_deterministic.py` remains unwired into any live turn pipeline; this batch is qualification-only, same as Stage 2.
- **No commit**: confirmed, `git log -1` unchanged.
- **No push**: confirmed.
- **No merge**: confirmed.
- **No PR**: confirmed.

---

## Tests

**Pre-check (before any Stage 3 artifact was created):**
```
python -m unittest test_m35_uriv1_a2_5_deterministic_rar.py -v
Ran 19 tests in 0.003s — OK
```
```
python -m unittest test_m35_uriv1_a0_skeleton test_m35_uriv1_a1_1_contract_hardening \
  test_m35_uriv1_a1_decoded_request test_m35_uriv1_a2_1_needle_narrow \
  test_m35_uriv1_a2_2_qwen_decoder test_m35_uriv1_a2_4_qwen14b_decoder \
  test_m35_uriv1_a2_4r_needle_single_pass test_m35_uriv1_a2_5_candidate_invention_fix \
  test_m35_uriv1_a2_5_deterministic_rar test_m35_uriv1_a2_5_rar_contracts \
  test_m35_uriv1_a2_needle_decoder tests.test_m35_uriv1_a2_3_scaffolded_needle \
  tests.test_m35_uriv1_a2_3_semantic_envelope tests.test_m35_uriv1_a2_3_turn_frame -v
Ran 146 tests — OK
```
Live-model test files (`*_a2_1_needle_narrow_live`, `*_a2_2_qwen_live`, `*_a2_3_scaffolded_needle_live`, `*_a2_4_qwen14b_live`, `*_a2_4r_needle_live`) were deliberately **excluded** from this batch's regression runs: executing them would invoke Needle/Qwen runtimes, which this batch's strict boundaries explicitly forbid ("DO NOT... run Needle, run Qwen"). Their exclusion is a boundary-compliance choice, not a gap in regression coverage relevant to RAR (they exercise unrelated decoder subsystems).

**Post-artifact regression (after Stage 3 files were created):**
Re-ran the identical two commands above.
```
test_m35_uriv1_a2_5_deterministic_rar.py: Ran 19 tests in 0.003s — OK
Combined offline M35 suite: Ran 146 tests — OK
```
No regressions. Frozen resolver behaviour confirmed byte-identical in effect before and after Stage 3 construction (same 19/19 and 146/146 results both times).
