# M35 URIv1 — A2.8F: Deterministic Residual Recovery Qualification — Execution Report

**Type:** Experimental qualification only. No production integration, no RAR modification, no model addition, no architecture change. No commit, no push.
**Governing evidence:** `M35_URIV1_A2_8E_RESIDUAL_CHARACTERIZATION_REPORT.md` (the 27-case residual and 8-cluster taxonomy), `M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md` (frozen detector boundaries), `M35_URIV1_A2_8D_TELEMETRY.json` (corrected, unmodified — D1's baseline).
**Status:** `VERIFICATION_READY`

```xml
<development_state>
  <current_phase>QUALIFY_BOUNDED_REVISION</current_phase>
  <allowed_actions>design D1R as a new, separate module targeting T1/T3/T4/T5-simple/T6/T7 only, repair the two disclosed D1 overfitting instances, run against the full corpus, score, compare to corrected D1</allowed_actions>
  <prohibited_actions>modify D1 itself, modify RAR, target T2/T5-compound/T8, add a model, integrate into production, commit, push</prohibited_actions>
  <exit_criteria>D1R implemented as a separate module, target-18 recovery measured, whole-corpus regression check complete, overfitting repairs measured before/after, candidate-metadata tracking preserved, new residual set identified, next question recommended</exit_criteria>
  <stop_condition>VERIFICATION_READY</stop_condition>
</development_state>
```

---

## Acceptance criteria (defined before implementation)

1. D1 (`scripts/m35_a2_8d_detector_d1.py`) must not be modified — D1R is a separate module, and its own file's baseline telemetry must remain independently re-derivable.
2. Every new mechanism must be documented as `cluster → general mechanism → implementation rule → expected generalization → false-positive risk`, and must not reference a benchmark case ID, expected entity name, expected candidate ID, or corpus-specific token sequence.
3. T2, T5-compound, and T8 must not be targeted — verified by inspecting D1R's own mechanism list against A2.8E's cluster definitions.
4. The whole corpus, not just the target 18, must be scored — regressions and new unsafe bindings must be visible, not hidden.
5. RAR must run completely unmodified; a detector success that exposes a known RAR limitation must be scored as a detector success, not a detector failure.
6. Corpus hash verified before and after; deterministic outputs (D0/D1/D1R) must be bit-identical across repeated runs.
7. No fabricated measurement; `UNMEASURED` used where a figure genuinely was not collected.

Self-review: all seven met. Criterion 1 → §2 (`git diff` empty on D1's file). Criterion 2 → §3. Criterion 3 → §3 (explicit scope check). Criterion 4 → §5–§6. Criterion 5 → §7. Criterion 6 → §8. Criterion 7 → §9.

---

## 0. Baseline verification (recomputed from raw telemetry, not assumed)

| Claim (from A2.8E) | Recomputed this session | Match? |
|---|---|---|
| D1 detection recall = 67.9% | 57/84 = 67.86% | ✅ |
| D1 resolution coverage = 14.3% | 12/84 = 14.29% | ✅ |
| D2 detection recall = 3.6% | 3/84 = 3.57% (this session's fresh D2 run found 2/84 — see §8; the 3.6% figure is A2.8E's, re-confirmed reproducible in aggregate character, not bit-identical per-run, since D2 is model-assisted and expected to vary) | ✅ (baseline figure), variation expected and disclosed |
| D1 is a clean superset of D0 | Re-confirmed: every D0 success/detection this session is also a D1 success/detection | ✅ |
| True D0∧D1∧D2 residual = 27 | Re-derived from this session's own D0/D1 columns (D1's own file, unmodified) | ✅ |
| 8-cluster taxonomy (T1:4, T2:7, T3:5, T4:4, T5:1+1, T6:1, T7:3, T8:1) | Re-verified against the frozen corpus's `ground_truth_references` for all 27 case/refs | ✅ |

**All headline A2.8E figures independently reconfirmed before proceeding.**

---

## 1. Scope (per the task's explicit instruction)

**Targeted:** T1 (4), T3 (5), T4 (4), T5-simple (1), T6 (1), T7 (3) — **18 references total**.
**Explicitly not targeted:** T2 (bare proper names — `POSSIBLY_DETERMINISTIC`, a materially different precision question), T5-compound (`"either...except"` — `SEMANTIC_CAPABILITY_REQUIRED`, would disguise clause-interpretation as a regex), T8 (zero-surface reference — a session/discourse-state gap, not a language-detection gap; no D1-style mechanism could address it by construction).

---

## 2. Files created (D1 not modified)

- [scripts/m35_a2_8f_detector_d1r.py](scripts/m35_a2_8f_detector_d1r.py) — the revised detector, a **separate module**, not an edit to D1.
- [scripts/m35_a2_8f_run.py](scripts/m35_a2_8f_run.py) — runner; imports D1's own unmodified module for the baseline column and D1R's new module for the revision column, writes to a **separate telemetry file**.
- [scripts/m35_a2_8f_score.py](scripts/m35_a2_8f_score.py) — scorer.
- `docs/plans/M35_URIV1_A2_8F_TELEMETRY.json`, `..._AGGREGATES.json`.
- This report.

**`scripts/m35_a2_8d_detector_d1.py` was not modified** — confirmed via `git diff --stat` returning empty for that file. `docs/plans/M35_URIV1_A2_8D_TELEMETRY.json`/`..._AGGREGATES.json` were not touched this session. **No file under `uri_v1/turn/` was touched** — confirmed via empty `git diff --stat uri_v1/`.

---

## 3. Mechanisms added/generalized (cluster → mechanism → rule → generalization → risk)

| Cluster | General mechanism | Implementation rule | Expected generalization | False-positive risk |
|---|---|---|---|---|
| **T1** (4 refs) | Alphanumeric code/ID orthographic shape | `\b[A-Z]{2,6}-?\d{2,6}\b` (code) + standard 8-4-4-4-12 hex UUID shape; an intro word (invoice/order/PO/file/ticket/ref/reference/id) is folded into the span when immediately preceding | Any invoice/PO/ticket/reference-number style code, any domain | Low — the shape (letters immediately followed by digits, or a UUID) rarely occurs by orthographic accident |
| **T3** (5 refs) | English possessive marker (`'s`) headed NP | `\b\w+'s\b` + up to 3 following words, with a negative lookahead so the body cannot swallow a second possessive (fixed during pre-flight testing, see §4a below) | Any possessive-headed reference, proper or common noun | Low-moderate — contractions ("it's"/"that's"/"what's") excluded via a small closed stem list, not corpus phrases |
| **T4** (4 refs) | Same existing D1 mechanism (determiner-headed NP); word-class completion | Widen determiner alternation to include `my/your/our/his/her/its/their` | Closed, complete English possessive-pronoun class | Same as D1's already-audited determiner mechanism — no new risk category |
| **T5-simple** (1 ref) | Same existing mechanism; word-class completion | Widen determiner alternation to include `both/all/any` (`either`/`neither` deliberately excluded — those belong to T5-compound, out of scope) | Small closed quantifier set | Same as above |
| **T6** (1 ref) | Same existing bare-pronoun mechanism; pure completion | Add `she`/`he` to the closed 9-pronoun set | Two of the most common English pronouns, an oversight, not a scope boundary | Same as D1's already-audited pronoun mechanism |
| **T7** (3 refs) | Engineering fix to the existing NP-scanning mechanism (not new linguistic capability) | (a) word-token shape widened to accept digits/`&`; (b) NP scanner rewritten from a single greedy regex with a fixed word cap (all-or-nothing failure) to a token-based scan returning the longest valid prefix actually found, with no failure mode | Any noun phrase containing a digit/alphanumeric token, or exceeding the old fixed cap, in any domain | Lower than the old regex — the token scan stops deterministically at the first real stop-word/comma rather than attempting a long greedy consumption |

None of the six mechanisms references a benchmark case ID, an expected referent name, an expected candidate ID, or a corpus-specific entity list — verified by re-reading `m35_a2_8f_detector_d1r.py` in full after implementation (the same self-check A2.8E applied to D1).

**Two bugs found and fixed during pre-flight testing, before any scored run** (both are general robustness fixes, verified by re-reading the fix: neither references a case ID or corpus wording):
- The possessive-NP body capture could swallow a second, later possessive into one match (`"what's Tom's extension number"` collapsing to one rejected match with stem `"what"`, discarding the real `"Tom's"`) — fixed with a negative lookahead so the body stops before a token that itself starts a new possessive.
- A bare comma was not a phrase boundary for the NP scanner, letting a match run across an unrelated appositive clause (`"...for this, that's the scanned contract"`) — fixed by treating a comma between tokens as a stop condition, a general English phrase-boundary rule.

---

## 4. Overfitting repairs (measured before/after, not silently altered)

### 4a. Negation pattern (`"no, the other"`)

**Before (D1):** literal pattern `r"\bno,?\s+the\s+other\b"`, closely mirroring `NB-H-06`'s exact wording.
**After (D1R):** a general structural rule — a relational exclusion is recognized when any negation cue (`don't/dont/do not/not/never/no/cannot/can't/shouldn't/won't/except`) co-occurs in the same clause as the demonstrative phrase `"the other"` or `"another"`, regardless of their exact relative wording or punctuation. This preserves the same general *capability* (detecting a purely relational exclusion with no named content) without requiring the specific phrase to appear verbatim.
**Measured effect:** `NB-H-06` still reaches the same negation-scoping evidence under D1R as under D1 (confirmed by direct telemetry comparison — both supply the same effective exclusion signal), and its outcome is unchanged (`INCORRECT_CONFIDENT_BINDING`, the already-verified genuine RAR limitation — §7). **The repair is behavior-preserving for this case while being genuinely more general** (it would also fire on, e.g., `"not the other one"` or `"the other file, not this"`, which the old literal pattern would have missed).

### 4b. Type-hint vocabulary

**Before (D1):** `TYPE_HEAD_WORDS` mixed genuinely general words with 9 corpus-flavored additions (`letter`, `invoice`, `roster`, `minutes`, `agenda`, `certificate`, `scan`, plus `contract`/`template` mapped to `None`).
**After (D1R):** `GENERAL_TYPE_HEAD_WORDS` keeps only words also present in `rar_deterministic.py`'s own `GENERIC_TYPE_WORDS` vocabulary or explicitly named in `RARCandidate`'s own module docstring (`document`, `spreadsheet`, `pdf`, `image`, `email`, `person`, `record`, `workflow`) — a mechanical reuse of an existing, already-approved repository vocabulary, not a new one. All 9 corpus-flavored additions were removed entirely.
**Measured effect: one real, disclosed regression.** `NB-F-05` (`"Open the roster"`) flips from `CORRECT_RESOLUTION` (D1, using the removed `roster→spreadsheet` mapping) to `MISSED_RESOLVABLE_CASE` (D1R, `MULTIPLE_PLAUSIBLE`) under condition C2, where a distractor spreadsheet is present and the type filter that previously disambiguated it is now absent. **This is the direct, measured cost of the overfitting repair — reported plainly, not concealed.** No other regression was caused by this specific change (§6's full regression check found only this one case).

---

## 5. Target-18 recovery (C1)

| Cluster | Target refs | Detected (D1R) | `CORRECT_RESOLUTION` (D1R) | Detail |
|---|---|---|---|---|
| T1 | 4 | **4/4** | 0/4 | All four land in `MISSED_RESOLVABLE_CASE` — RAR receives the code/ID span but never confidently binds (see §12 for why: the reference expression e.g. `"invoice INV-20417"` does not exact-match any candidate's `id` field verbatim, and no candidate title contains the code as a token, so neither Level 0 nor Level 6 fires) |
| T3 | 5 | **5/5** | 0/5 | 4 land in `MISSED_RESOLVABLE_CASE`, 1 (`NB-J-03`) in `CORRECT_ABSTENTION` (matches ground truth's own expected `UNKNOWN`) |
| T4 | 4 | **4/4** | **1/4** (`NB-G-04:r2`) | 1 `CORRECT_ABSTENTION_FAMILY_MISMATCH`, 2 `MISSED_RESOLVABLE_CASE` |
| T5-simple | 1 | **1/1** | 0/1 | `MISSED_RESOLVABLE_CASE` |
| T6 | 1 | **1/1** | 0/1 | `MISSED_RESOLVABLE_CASE` |
| T7 | 3 | **3/3** | **2/3** (`NB-L-10:r1`, `NB-L-10:r2`) | `NB-F-03` still `MISSED_RESOLVABLE_CASE` |
| **Total** | **18** | **18/18 (100%)** | **3/18 (16.7%)** | |

**Detection recovery for the target 18 is complete (18/18) — every reference D1R was designed to detect, it detects.** Resolution recovery is much smaller (3/18) — **this is expected and correctly attributed to RAR's own cascade behavior, not to a detector shortfall** (§7): D1R's job (per the frozen boundary) is only to deliver evidence; whether RAR then confidently resolves is downstream of evidence quality interacting with RAR's own, unmodified logic.

---

## 6. Whole-corpus results and regression check

| Metric | D0 | D1 (baseline) | D1R (revision) |
|---|---|---|---|
| Detection recall (C1) | 15.5% | 67.9% | **89.3%** (75/84) |
| Detection recall (C2) | 15.5% | 67.9% | 89.3% |
| Resolution coverage (C1) | 0.0% | 14.3% | **19.0%** |
| Resolution coverage (C2) | 0.0% | 8.3% | **10.7%** |
| `INCORRECT_CONFIDENT_BINDING` (C1) | 0 | 1 | **1** (unchanged — `NB-H-06`, §7) |
| `INVENTED_CANDIDATE` (all cells) | 0 | 0 | **0** |
| Boundary violations (all cells) | 0 | 0 | **0** (after a false-positive in the check itself was found and fixed — §6a) |
| K-category false-positive binding | 0 | 0 | **0** |
| K-category false-positive safe abstention | 2 | 6 | **7** (+1 — a new spurious detection that still safely abstains, no safety cost) |
| Unattributed detector finds (C1) | 18 | 46 | **58** (+12 — more over-detection, expected from a broader detector; see §6b) |

### 6a. Boundary-check false positive found and fixed

The initial run flagged **2** rows as `boundary_violation=True`, both `NB-A-04` (T1's UUID case: `"use file 38e1b5c4-... for this, that's the scanned contract"`). Investigation found this was a **false positive in the boundary-check logic itself**, not a genuine violation: the ground truth's own canonical span for this reference **is** the literal UUID the user typed in their own turn, and T1's mechanism correctly extracted it verbatim from `raw_user_text`. The original check (`span contains a candidate_id substring` → violation) could not distinguish "the detector echoed an ID the user actually wrote" from "the detector fabricated/leaked an ID it should not know." **Fixed:** the check now also requires the candidate_id to be **absent from the raw user text** before flagging a violation — i.e., a genuine violation is the detector introducing an ID the user never wrote, not faithfully reporting one the user did write. Re-run after the fix: **0 genuine boundary violations**, confirmed. This is disclosed as a benchmark-infrastructure defect in this session's own boundary-check implementation, not a detector defect — D1R never fabricated anything; the check was simply too broad.

### 6b. Regression check (D1R vs. corrected D1, paired by case_id:ref_key)

| C axis | Regressions (`CORRECT_RESOLUTION` → not) | New wrong bindings | Gains (not `CORRECT_RESOLUTION` → `CORRECT_RESOLUTION`) |
|---|---|---|---|
| C1 | **0** | **0** | **4** (`NB-F-04:r1`, `NB-G-04:r2`, `NB-L-10:r1`, `NB-L-10:r2`) |
| C2 | **1** (`NB-F-05:r1` — §4b's disclosed, measured overfitting-repair cost) | **0** | **3** (`NB-F-04:r1`, `NB-G-04:r2`, `NB-L-10:r2`) |

**Zero new unsafe (`INCORRECT_CONFIDENT_BINDING`) rows introduced anywhere.** The single C2 regression is the direct, expected, and already-disclosed cost of §4b's overfitting repair — not an unexplained side effect. **One gain (`NB-F-04:r1`) was not one of the 18 explicitly targeted references** — a genuine, unplanned generalization benefit from the T7 engineering fix (the token-scan mechanism recovering a case its design was not specifically aimed at), reported honestly rather than retrofitted into the target list.

---

## 7. Detector success vs. RAR behaviour (kept separate, per the task's explicit instruction)

`NB-H-06` remains D1R's one `INCORRECT_CONFIDENT_BINDING` — **unchanged from D1**, and for the identical, already-verified reason (A2.8D execution report §9, A2.8E §10): Level 4a's negation elimination cannot represent a purely relational exclusion lacking shared vocabulary with the excluded candidate. §4a's negation-mechanism repair generalizes the *pattern* that supplies this evidence but does not and cannot repair the *underlying RAR limitation* — the outcome is identical because the limitation is RAR's, not the detector's. **This is scored as a pre-existing RAR limitation being reached again, not a new or worsened detector defect**, exactly per the task's instruction that a correct detection exposing a known RAR defect is still a detector success.

No new RAR failure mechanism was observed. All of D1R's `MISSED_RESOLVABLE_CASE` outcomes on the target 18 (§5) reflect RAR's own cascade not confidently binding given the evidence supplied — not a new behavior, but the same conservative-abstention behavior already characterized throughout A2.8C–A2.8E.

---

## 8. Candidate-metadata interaction (Phase 8) — the five tracked cases

| Case:ref | D1 scoring_class | D1R scoring_class | `recency_hint` supplied (both) | Changed? |
|---|---|---|---|---|
| `NB-J-02:r1` | `CORRECT_ABSTENTION` | `CORRECT_ABSTENTION` | `earlier` | No |
| `NB-J-04:r1` | `CORRECT_ABSTENTION` | `CORRECT_ABSTENTION` | `earlier` | No |
| `NB-D-04:r1` | `MISSED_RESOLVABLE_CASE` | `MISSED_RESOLVABLE_CASE` | `earlier` | No |
| `NB-D-07:r1` | `MISSED_RESOLVABLE_CASE` | `MISSED_RESOLVABLE_CASE` | `latest` | No |
| `NB-H-01:r1` | `MISSED_RESOLVABLE_CASE` | `MISSED_RESOLVABLE_CASE` | `earlier` | No |

**D1R does not change candidate-metadata construction at all** — both D1 and D1R are run through the identical `build_candidate_pool(..., oracle_recency=False)` path in this session's harness (`m35_a2_8f_run.py`, unchanged from `m35_a2_8d_run.py`'s own convention); `RARCandidate.recency_rank` is `0` for every candidate under both detectors, by the same deliberate boundary choice A2.8D established (a detector's job is evidence delivery, never candidate-pool construction). **All five tracked cases are bit-identical in outcome between D1 and D1R** — confirming that D1R's mechanism additions operate strictly within the detector's frozen boundary and do not, even incidentally, touch the candidate-metadata dimension that A2.8E's Phase 6 finding was about. **The latent risk A2.8E identified (that `NB-D-04`/`NB-D-07`/`NB-H-01` would plausibly flip to `INCORRECT_CONFIDENT_BINDING` if `recency_rank` were ever populated) remains exactly as open and exactly as real under D1R as it was under D1** — this experiment neither increases nor decreases that risk, since it never touches the field the risk depends on.

---

## 9. Performance/resource measurements

| Metric | D0 | D1 | D1R | D2 |
|---|---|---|---|---|
| Model calls | 0 | 0 | **0** | 1/case |
| Detector-only latency | `UNMEASURED` (embedded in `build_turn_frame()`) | `UNMEASURED` | `UNMEASURED` (not separately instrumented from RAR's own call in this harness) | ~151 ms/case (measured, A2.8D) |
| CPU | `UNMEASURED` | `UNMEASURED` | `UNMEASURED` | `UNMEASURED` |
| RAM | `UNMEASURED` | `UNMEASURED` | `UNMEASURED` | ~101 MB peak (measured, A2.8D) |
| RAR invocation count (C1, gt-bearing + K rows) | 31 | 63 | **83** | 3 |

D1R's whole-corpus run (79 cases × 4 detectors × 3 C-conditions) completed in well under a minute of wall-clock time for the deterministic detectors (D0/D1/D1R); the dominant cost in the full pipeline remains D2's ~12-second batch subprocess call, unaffected by this session's changes. **No model call was added anywhere in D1R** — confirmed by direct code inspection (`m35_a2_8f_detector_d1r.py` imports only `re` and `dataclasses`).

---

## 10. Corpus hashes and reproducibility

```
Pre-run:  0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380
Post-run: 0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380
```

Match, before and after. Ground truth was not altered — confirmed by code inspection of `m35_a2_8f_run.py` (ground truth is read only inside `_classify()`, after RAR has already returned).

**Reproducibility check:** the full pipeline was run twice. **D0, D1, and D1R (all deterministic code paths) were bit-identical across both runs**, apart from the `latency_ms` timing field (expected). **D2 (Needle 3, model-assisted) differed between runs** — one case (`NB-D-07:r1`) landed in a different RAR outcome bucket (`AMBIGUOUS`/`TEMPORAL_RELATION` vs. `UNKNOWN`/`TYPE_FILTER`) due to Needle producing a different `coarse_type` value on the second run, both still scored `MISSED_RESOLVABLE_CASE` either way — a small, expected, and fully disclosed instance of the model-assisted nondeterminism the task's own instructions anticipated. **This is not investigated further as an anomaly; it is the expected behavior of the one non-deterministic component in the pipeline**, and it does not affect any deterministic-detector conclusion in this report.

---

## 11. Exact residual set after D1R (C1)

Of the original 27-case residual, **18 are now detected** (the full target set). **9 remain `SILENT_DETECTION_MISS`**, exactly matching the 9 references A2.8E scoped out of this experiment's target (T2's 7 bare-proper-name cases, T5-compound's 1 case, T8's 1 case):

| Case:ref | Cluster (A2.8E) | D1R result |
|---|---|---|
| `NB-B-03:r1` | T8 (zero-surface) | `SILENT_DETECTION_MISS` |
| `NB-B-05:r2` | T2 (bare name) | `SILENT_DETECTION_MISS` |
| `NB-G-04:r1` | T2 (bare name) | `SILENT_DETECTION_MISS` |
| `NB-I-02:r2` | T2 (bare name) | `SILENT_DETECTION_MISS` |
| `NB-I-06:r2` | T2 (bare name) | `SILENT_DETECTION_MISS` |
| `NB-L-01:r2` | T2 (bare name) | `SILENT_DETECTION_MISS` |
| `NB-L-02:r2` | T2 (bare name) | `SILENT_DETECTION_MISS` |
| `NB-L-04:r2` | T2 (bare name) | `SILENT_DETECTION_MISS` |
| `NB-H-02:r1` | T5-compound | `SILENT_DETECTION_MISS` |

**Detection-level residual is now exactly the 9 references A2.8E already predicted would remain out of scope — no cluster boundary blurred, no case silently detected by accident, none of T2/T5-compound/T8 was solved.**

**Resolution-level residual (references detected but not `CORRECT_RESOLUTION`) is larger — 15 of the 18 target references** (§5) — these remain unresolved not because detection failed, but because RAR's own cascade, unmodified, does not confidently bind given the evidence D1R supplies. This is the new, more precise question for the next phase.

---

## 12. Evidence-driven next question (not decided)

D1R fully closes the *detection* gap for its target scope (18/18) at zero model cost and zero new unsafe bindings, but only converts 3/18 into confident *resolutions*. Inspecting why (not exhaustively, but per the cases already surfaced in §5): T1's alphanumeric codes are detected but never match any candidate's `id` field or title tokens exactly (RAR's Level 0 requires an exact match against `candidate.id`, and the detected span `"invoice INV-20417"` includes the intro word, which breaks that exact match even when the bare code would have matched — an observed mechanism-design tradeoff, not fixed here per the explicit instruction against forcing a benchmark-specific patch); T3/T4's possessive/pronoun-determiner NPs mostly lack a matching lexical token in any candidate's title (the underlying office-vocabulary head noun, e.g. "extension number", "interview", isn't itself a candidate title word).

**Per the task's own stop rule (§12 of the task prompt): none of this indicates a target cluster secretly requires semantic interpretation — every miss traced above is a specific, nameable RAR-cascade or evidence-construction property (Level 0's exact-match requirement, Level 6's lexical-overlap requirement), not an unexplained gap.** The smallest evidence-driven next question is therefore:

> **Now that detection recall is 89.3% and delivery evidence is real, what is the smallest change to *how detected spans are packaged into a `RARQuery`* (not to RAR itself, and not a new detection mechanism) — e.g. stripping intro words before the exact-ID match, or a bounded within-span retry — that would let already-detected T1/T3/T4 evidence actually reach RAR's Level 0/6 in a form those levels can use?**

This is deliberately narrower than "improve RAR" (prohibited) or "add another detection mechanism" (already exhausted for this scope) — it targets the query-construction seam between a now-good detector and an unmodified resolver. **Not designed or implemented in this document.**

---

## Summary for User Review

**Baseline reconfirmed:** D1 recall 67.9%, coverage 14.3%, D1 superset of D0, 27-case residual and 8-cluster taxonomy all independently re-verified from raw telemetry before implementation began.

**D1R implemented as a separate module** (D1 itself never modified) targeting exactly T1/T3/T4/T5-simple/T6/T7 (18 references), explicitly excluding T2/T5-compound/T8. Every mechanism documented as cluster→mechanism→rule→generalization→risk; none references corpus-specific content (re-verified by self-audit, same discipline A2.8E applied to D1). Two pre-flight bugs found and fixed (possessive-body swallowing a second possessive; missing comma phrase-boundary) — both general robustness fixes, not corpus tuning.

**Two overfitting repairs measured, not silently applied:** the `"no, the other"` negation pattern generalized to a structural rule (behavior-preserving on `NB-H-06`, genuinely broader); the corpus-flavored type vocabulary pruned to only repository-approved general words (**one measured regression**, `NB-F-05` under C2 — reported plainly as the direct cost).

**Target-18 detection: 18/18 (100%).** Target-18 resolution: 3/18 (16.7%) — the gap is RAR's own cascade, not a detection shortfall (§7). **Whole-corpus: detection recall 67.9% → 89.3%, resolution coverage 14.3% → 19.0% (C1) / 8.3% → 10.7% (C2). Zero regressions at C1, one disclosed regression at C2 (the type-vocabulary repair's direct cost), zero new unsafe bindings anywhere, `INVENTED_CANDIDATE = 0`, 0 genuine boundary violations** (one false-positive in the boundary-check itself found and fixed — §6a).

**Candidate-metadata interaction (Phase 8): unchanged.** All five tracked cases (`NB-J-02`, `NB-J-04`, `NB-D-04`, `NB-D-07`, `NB-H-01`) are bit-identical in outcome between D1 and D1R — D1R never touches candidate-pool construction, so the latent RAR-limitation risk A2.8E identified remains exactly as open as before.

**New residual after D1R: the same 9 references A2.8E already scoped out (T2's 7, T5-compound's 1, T8's 1) — no scope creep, no accidental solves.** Recommended next question: investigate query-construction (not detection, not RAR) as the seam preventing detected-but-unresolved T1/T3/T4 evidence from reaching RAR usably. Not implemented.

**Files created:** `scripts/m35_a2_8f_detector_d1r.py`, `scripts/m35_a2_8f_run.py`, `scripts/m35_a2_8f_score.py`, `docs/plans/M35_URIV1_A2_8F_TELEMETRY.json`, `docs/plans/M35_URIV1_A2_8F_AGGREGATES.json`, this report.
**Files modified:** none.
**Production files touched:** none — `uri_v1/turn/` untouched; D1 itself (`scripts/m35_a2_8d_detector_d1.py`) untouched; A2.8D's own telemetry/aggregates untouched.
**No commit. No push. No production integration. No model escalation. No architecture change.**

Stopped at `VERIFICATION_READY`.
