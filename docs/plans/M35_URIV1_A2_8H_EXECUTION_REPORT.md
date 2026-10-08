# M35 URIv1 — A2.8H: Deterministic Query-Construction Repair Qualification — Execution Report

**Type:** Experimental qualification only. No RAR modification, no candidate-construction modification, no model, no production integration. No commit, no push.
**Governing evidence:** `M35_URIV1_A2_8G_DETECTION_TO_RAR_BOUNDARY_AUDIT.md` (the 9 Q-class failures and their 2 root causes), `M35_URIV1_A2_8F_EXECUTION_REPORT.md`/telemetry (D1R baseline, unmodified).
**Status:** `VERIFICATION_READY`

```xml
<development_state>
  <current_phase>QUALIFY_QUERY_CONSTRUCTION_REPAIR</current_phase>
  <allowed_actions>implement D1RQ as a fork of D1R with exactly the two frozen Q1/Q2 repairs, run against the full corpus, compare to D1R/D1/D0, trace all 8 target cases causally</allowed_actions>
  <prohibited_actions>modify D1R, modify RAR, modify candidate construction, repair NB-J-01/stemming/absent-entity/aliasing/clause_text/recency_rank, add a model, integrate into production, commit, push</prohibited_actions>
  <exit_criteria>D1RQ implemented as a separate module, Q1/Q2 causal traces complete for all 8 target references, whole-corpus regression check complete, T1/T3-specific checks complete, known risks preserved, invariants confirmed, reproducibility confirmed</exit_criteria>
  <stop_condition>VERIFICATION_READY</stop_condition>
</development_state>
```

---

## Acceptance criteria (defined before implementation)

1. D1R must not be modified — D1RQ is a fork into a separate module; D1R's own A2.8F telemetry stays independently re-derivable.
2. Q1 must remove the unsupported type assertion without substituting a different benchmark-fitted one (`code→pdf`/`code→approval` explicitly prohibited).
3. Q2 must use only general, closed, corpus-independent word classes — verified by checking whether the repair changes any case's span by comparing to that case's own ground truth (it must not, and `NB-G-03` is the proof case: the repair leaves its span unchanged because no general rule applies there).
4. The whole corpus, not just the 8 targets, must be scored, with every possessive-NP-firing case (not just the 4 targets) checked for regression.
5. All six items in the explicit out-of-scope list (Phase 2) must remain untouched — verified by diffing D1RQ against D1R and confirming no other mechanism changed.
6. `INVENTED_CANDIDATE = 0` and `BOUNDARY_VIOLATION = 0` maintained.
7. Corpus hash verified before/after; deterministic cells (D0/D1/D1R/D1RQ) bit-identical across repeated runs.

Self-review: all seven met. Criterion 1 → §2 (`git diff` empty on D1R's/D1's files). Criterion 2 → §3. Criterion 3 → §5, §7 (`NB-G-03` unchanged, exactly as predicted). Criterion 4 → §6, §8. Criterion 5 → §2. Criterion 6 → §9. Criterion 7 → §10.

---

## 0. Baseline reconfirmed

| Claim (from A2.8G, re-verified this session) | Value |
|---|---|
| D1R detection recall (C1) | 75/84 = 89.29% |
| D1R resolution coverage (C1) | 16/84 = 19.05% |
| 9 Q-class cases, 2 root causes explaining 8 of them | Confirmed by re-reading A2.8G §3.1/§3.2/§4 before implementation |
| `NB-J-01`, stemming, absent-entity, aliasing, `clause_text`, `recency_rank` explicitly out of scope | Confirmed, none touched (§2) |

---

## 1. Frozen repair scope

**Q1 (T1, 4 cases):** the code/UUID mechanism no longer asserts `target_type_hint="document"` — it asserts **no type at all** (`None`). This is the removal of an unsupported guess, not the addition of a different one; `code→pdf`/`code→approval` mappings were **not** added anywhere.

**Q2 (T3, 4 cases):** the possessive-NP body capture is bounded by two general, closed English word classes (a preposition set and a degree/repetition-adverb set) plus a cap reduced from 3 to 2 words. **Not** tuned by comparing to ground truth — verified directly: `NB-G-03`'s span (`"Tom's extension number"`) is **unchanged** by the repair, because neither general rule applies to it (`"extension"`/`"number"` are ordinary nouns, not prepositions or adverbs) — exactly the outcome a genuinely general (not benchmark-fitted) rule predicts, and reported honestly rather than special-cased.

---

## 2. Files created (D1R, D1, RAR untouched)

- [scripts/m35_a2_8h_detector_d1rq.py](scripts/m35_a2_8h_detector_d1rq.py) — a fork of D1R, differing **only** in the Q1/Q2 mechanisms documented in the file's own header.
- [scripts/m35_a2_8h_run.py](scripts/m35_a2_8h_run.py) — a fork of the A2.8F runner, adding D1RQ as a fifth detector column alongside D0/D1/D2/D1R; writes to a **new** telemetry file.
- `docs/plans/M35_URIV1_A2_8H_TELEMETRY.json` (1,905 rows — 79 cases × 5 detectors × 3 C-conditions, plus per-reference rows).

**Confirmed unmodified this session** (`git diff --stat` empty): `scripts/m35_a2_8f_detector_d1r.py`, `scripts/m35_a2_8f_run.py`, `scripts/m35_a2_8d_detector_d1.py`, everything under `uri_v1/turn/`. A2.8F's own telemetry/aggregates files untouched.

---

## 3. Causal trace, all 8 target references (C1)

| Case:ref | D1R span / type | D1R outcome | D1RQ span / type | D1RQ outcome | What changed |
|---|---|---|---|---|---|
| `NB-A-01:r1` | `"invoice INV-20417"` / `document` | `MISSED_RESOLVABLE_CASE` (L4b `TYPE_FILTER`, `NO_CANDIDATE`) | same span / `None` | **`CORRECT_RESOLUTION`** (L6 `TERM_DISCRIMINATION`) | Type assertion removed → L4b no longer rejects → L6's real lexical match (`invoice`, `20417` both in candidate title tokens) fires |
| `NB-A-03:r1` | `"PO-5521"` / `document` | `MISSED_RESOLVABLE_CASE` (L4b) | same / `None` | **`CORRECT_RESOLUTION`** (L6) | Same mechanism |
| `NB-A-04:r1` | `"file 38e1b5c4-..."` / `document` | `MISSED_RESOLVABLE_CASE` (L4b) | same span / `None` | `MISSED_RESOLVABLE_CASE` (L6 `NO_CANDIDATE`) | Type assertion removed, but **still unresolved** — see §5 (out-of-scope identifier mismatch) |
| `NB-A-05:r1` | `"INV-20388"` / `document` | `MISSED_RESOLVABLE_CASE` (L4b) | same / `None` | **`CORRECT_RESOLUTION`** (L6) | Same mechanism as A-01/A-03 |
| `NB-C-03:r1` | `"Daniel's against the job"` | `MISSED_RESOLVABLE_CASE` (L6 `NO_CANDIDATE`) | `"Daniel's"` | **`CORRECT_RESOLUTION`** (L6) | Span boundary stops before `"against"` (preposition) → no spurious unmatched tokens → `"daniel"` matches uniquely |
| `NB-F-02:r1` | `"Daniel's interview again"` | `MISSED_RESOLVABLE_CASE` | `"Daniel's interview"` | **`CORRECT_RESOLUTION`** | Span stops before `"again"` (adverb) |
| `NB-G-03:r1` | `"Tom's extension number"` | `MISSED_RESOLVABLE_CASE` | **unchanged**: `"Tom's extension number"` | `MISSED_RESOLVABLE_CASE` (unchanged) | **No general rule applies** — honest non-fix, §7 |
| `NB-L-11:r2` | `"Daniel's offer letter alone"` | `MISSED_RESOLVABLE_CASE` | `"Daniel's offer letter"` | **`CORRECT_RESOLUTION`** | Span stops before `"alone"` (adverb) |

**6 of 8 target references move to `CORRECT_RESOLUTION` (75%). 1 (`NB-A-04`) moves from a blocked-at-L4b query to a truthfully-reached-but-still-unresolved L6 query — informative evidence per the task's own framing ("moving a failure from malformed query construction to truthful downstream abstention is still useful"), not a fix. 1 (`NB-G-03`) is unchanged, honestly, because no general structural signal applies.**

---

## 4. Whole-corpus results and regression check

| Metric | D0 | D1 | D1R | **D1RQ** |
|---|---|---|---|---|
| Detection recall (C1) | 15.5% | 67.9% | 89.3% | **89.3% (unchanged — Q1/Q2 touch evidence construction, not detection)** |
| Resolution coverage (C1) | 0.0% | 14.3% | 19.0% | **26.2% (+7.1 pts)** |
| Resolution coverage (C2) | 0.0% | 8.3% | 10.7% | **15.5% (+4.8 pts)** |
| `INCORRECT_CONFIDENT_BINDING` (C1, C2) | 0 | 1 | 1 | **1 (unchanged — `NB-H-06`, untouched by this repair)** |
| `INVENTED_CANDIDATE` (all cells) | 0 | 0 | 0 | **0** |
| Boundary violations (all cells) | 0 | 0 | 0 | **0** |
| K-category false-positive binding | 0 | 0 | 0 | **0** |
| K-category false-positive safe abstention | 2 | 6 | 7 | **7 (unchanged)** |
| Unattributed detector finds (C1) | 18 | 46 | 58 | **58 (unchanged)** |

**Regression check (D1RQ vs. D1R, paired by case_id:ref_key), both C1 and C2: 0 regressions, 0 new wrong bindings, everywhere.** Gains: 6 at C1 (the 6 target successes above), 4 at C2 (`NB-A-03`, `NB-A-05`, `NB-F-02`, `NB-L-11:r2` — `NB-A-01` and `NB-C-03` land in safe `AMBIGUOUS`/`MULTIPLE_PLAUSIBLE` at C2 instead, §6).

---

## 5. T1-specific checks (Phase 6)

| Check | `NB-A-01` | `NB-A-03` | `NB-A-04` | `NB-A-05` |
|---|---|---|---|---|
| Literal code preserved | ✅ `INV-20417` intact in span | ✅ `PO-5521` intact | ✅ UUID intact | ✅ `INV-20388` intact |
| No unsupported semantic type invented | ✅ `coarse_type: None` | ✅ | ✅ | ✅ |
| Query no longer carries `"document"` constraint | ✅ | ✅ | ✅ | ✅ |
| Candidate pool effect | None — same pool as D1R | None | None | None |
| Level 4b still rejects? | **No — no longer triggered** (no type hint to filter on) | No | No | No |
| Level 6 receives literal lexical evidence? | ✅ — and resolves correctly | ✅ resolves | ✅ reached, but no match (§ below) | ✅ resolves |
| Level 0 remains unavailable (identifier-system mismatch)? | ✅ — confirmed unchanged: `candidate.id` is a UUID unrelated to `"INV-20417"`, never compared | ✅ same | **Partially — Level 0 is structurally reachable here** (the candidate's `id` *is* the detected UUID) **but remains blocked by the unrepaired intro-word prefix** (`"file "`), exactly as A2.8G characterized and exactly as this repair's frozen scope (Q1 = type hint only) leaves untouched | ✅ same as A-01/A-03 |

**Level 6 success reported as Level 6 success, never conflated with Level 0 exact-ID success, per the task's explicit instruction** — the `rule_used` field in every telemetry row (`TERM_DISCRIMINATION` for all four, confirmed directly, never `EXACT_ID`) makes this distinction mechanically verifiable, not just asserted in prose.

---

## 6. T3-specific checks (Phase 7)

| Check | `NB-C-03` | `NB-F-02` | `NB-G-03` | `NB-L-11:r2` |
|---|---|---|---|---|
| Original (D1R) span | `"Daniel's against the job"` | `"Daniel's interview again"` | `"Tom's extension number"` | `"Daniel's offer letter alone"` |
| Revised (D1RQ) span | `"Daniel's"` | `"Daniel's interview"` | **unchanged** | `"Daniel's offer letter"` |
| Words removed | `against`, `the`, `job` | `again` | none | `alone` |
| Structural reason | `"against"` is in the general preposition stop-set | `"again"` is in the general adverb stop-set | No stop-word or cap violation triggers before `"number"` (2-word cap reached exactly at `"extension number"`, and neither word is a stop-word) | `"alone"` is in the general adverb stop-set |
| True referential head retained? | ✅ `"Daniel"` | ✅ `"Daniel"` | ✅ `"Tom"` (already present, unaffected either way) | ✅ `"Daniel"` |
| Effect on Level 6 | Spurious tokens removed → unique match on `"daniel"` | Spurious token removed → unique match | No change — `"extension"`/`"number"` still absent from candidate tokens | Spurious token removed → unique match |
| Absent-entity rejection changes? | Yes — no longer triggers | Yes — no longer triggers | **No — still triggers**, honestly, on genuine evidence (the extra words are real, ordinary nouns a general rule cannot distinguish from a legitimately longer reference without consulting the answer) | Yes — no longer triggers |
| Final outcome | `CORRECT_RESOLUTION` | `CORRECT_RESOLUTION` | `MISSED_RESOLVABLE_CASE` (unchanged) | `CORRECT_RESOLUTION` |

**All other possessive-NP-firing cases in the whole corpus checked for regression** (`NB-C-01`, `NB-G-06`, `NB-H-02`, `NB-L-09` — none of the 8 targets): in every one, the span shortened by exactly the same general rule (dropping a trailing preposition/adverb), but **the `scoring_class` outcome is identical between D1R and D1RQ in all four cases** (`CORRECT_RESOLUTION`, `MISSED_RESOLVABLE_CASE`, `SILENT_DETECTION_MISS`, and `UNATTRIBUTED_DETECTOR_FIND` respectively, unchanged) — these were already unattributed noise or already-correct/already-failing for reasons unrelated to the trailing words removed. **Zero regression anywhere in the corpus from the Q2 mechanism**, confirmed exhaustively, not just on the 4 targets.

---

## 7. Causal attribution summary (Phase 5's outcome categories)

| Outcome category | Cases |
|---|---|
| Query repair → correct resolution | `NB-A-01`, `NB-A-03`, `NB-A-05`, `NB-C-03`, `NB-F-02`, `NB-L-11:r2` (6) |
| Query repair → appropriate abstention (at C2, under distractors) | `NB-A-01`, `NB-C-03` land in safe `AMBIGUOUS` at C2 specifically (still resolved at C1) |
| Query repair → candidate/identifier-system limitation exposed (unchanged from A2.8G, not newly created) | `NB-A-04` |
| Query repair insufficient | `NB-G-03` |
| Query repair → RAR limitation exposed | None newly exposed |
| Query repair → unsafe binding | **None — zero anywhere** |

**Correcting query construction was sufficient to resolve 6/8 targets outright, moved 1 (`NB-A-04`) to a truthfully-reached-but-still-blocked state whose blocking cause (intro-word prefix vs. Level 0) is precisely the same one A2.8G already named and this task's scope deliberately left unrepaired, and left 1 (`NB-G-03`) honestly unchanged because no general rule applies.**

---

## 8. Measurements (Phase 10)

| Metric | Value |
|---|---|
| Detection recall (C1/C2) | 89.3% / 89.3% (unchanged from D1R — expected, Q1/Q2 do not touch detection) |
| Detection precision | Not separately recomputed this session (unchanged detection set as D1R; A2.8F's own D1R precision figures apply unchanged) |
| Target-8 query repair rate | 6/8 (75%) reach `CORRECT_RESOLUTION`; 8/8 (100%) reach a truthfully-constructed query (no case retains the unsupported type assertion or the over-captured span) |
| Correct span rate for Q2 targets (4 cases) | 3/4 (75%) span now matches ground truth exactly; 1/4 (`NB-G-03`) legitimately does not, by design |
| Unsupported type-hint count (T1) | 4 → **0** (all four now `None`) |
| RAR invocation count (C1, gt+K rows, per detector) | D0: 31, D1: 63, D1R: 83, **D1RQ: 83 (unchanged — same detections, same invocation count)** |
| Candidate-pool changes | **None, anywhere** — confirmed by direct inspection; D1RQ never touches `build_candidate_pool()` |
| Final resolution coverage C1/C2 | **26.2% / 15.5%** (up from D1R's 19.0%/10.7%) |
| Correct abstentions | Increased alongside resolution (safe outcomes at C2 for `NB-A-01`/`NB-C-03`, §6) |
| Incorrect confident bindings | **1, unchanged** (`NB-H-06`, untouched) |
| Newly exposed RAR failures | **None** |
| Regressions | **0** |
| False positives | **0 new** (K-category false-positive-binding remains 0; safe-abstention count unchanged at 7) |
| Invented candidates | **0** |
| Boundary violations | **0** |
| Latency | Sub-millisecond per RAR call (unchanged order of magnitude from all prior A2.8-series measurements); detector-only latency `UNMEASURED` (not separately instrumented, same as A2.8F) |
| CPU/RAM | `UNMEASURED` |
| Model calls | **0** (confirmed — `m35_a2_8h_detector_d1rq.py` imports only `re` and `dataclasses`, identical import profile to D1R) |

---

## 9. Invariants (Phase 8)

- `INVENTED_CANDIDATE = 0` — confirmed across all 1,905 rows.
- `BOUNDARY_VIOLATION = 0` — confirmed across all 1,905 rows.
- The repair does not choose the referent, inject candidate IDs, inspect ground truth during execution (verified: `m35_a2_8h_detector_d1rq.py` has zero references to `ground_truth`, `expected_`, `intended_candidate` anywhere), derive semantic type from benchmark labels (Q1 removes a type assertion; it adds none), bypass or reorder RAR (RAR's own cascade is called exactly as in every prior A2.8-series experiment, completely unmodified), or modify candidate records.

---

## 10. Reproducibility

```
Pre-run:  0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380
Post-run: 0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380
```

Match. The full pipeline was run twice; **D0, D1, D1R, and D1RQ (all four deterministic detector columns) were bit-identical across both runs**, apart from `latency_ms`. Only D2 (model-assisted, unaffected by this experiment) varied between runs, in the same small, already-characterized way prior sessions observed. No investigation needed beyond what A2.8F already established about D2's expected nondeterminism.

---

## 11. Known risks preserved (Phase 11)

The candidate-metadata/recency-rank tracking set, now six cases (five from A2.8E/A2.8F plus `NB-L-04:r1` added in A2.8G/A2.8F), **re-verified bit-identical in outcome between D1R and D1RQ**:

| Case | D1R | D1RQ | Changed? |
|---|---|---|---|
| `NB-J-02:r1` | `CORRECT_ABSTENTION` | `CORRECT_ABSTENTION` | No |
| `NB-J-04:r1` | `CORRECT_ABSTENTION` | `CORRECT_ABSTENTION` | No |
| `NB-D-04:r1` | `MISSED_RESOLVABLE_CASE` | `MISSED_RESOLVABLE_CASE` | No |
| `NB-D-07:r1` | `MISSED_RESOLVABLE_CASE` | `MISSED_RESOLVABLE_CASE` | No |
| `NB-H-01:r1` | `MISSED_RESOLVABLE_CASE` | `MISSED_RESOLVABLE_CASE` | No |
| `NB-L-04:r1` | `MISSED_RESOLVABLE_CASE` | `MISSED_RESOLVABLE_CASE` | No |

**D1RQ, like D1R before it, never touches candidate-pool construction — the latent `recency_rank`-absence risk A2.8E first identified remains exactly as open as it has been through every subsequent experiment.** The six out-of-scope items from Phase 2 (`NB-J-01`'s vocabulary gap, RAR stemming, RAR's all-or-nothing absent-entity check, candidate aliasing, `clause_text` wiring, `recency_rank` wiring) are all confirmed untouched by direct code diff against D1R and RAR.

---

## Summary for User Review

**D1RQ implemented as a clean fork of D1R** (D1R itself, D1, and RAR all confirmed unmodified). Exactly the two frozen repairs: **Q1** removes the code/UUID mechanism's unsupported `"document"` type assertion (asserts nothing, not a different guess); **Q2** bounds the possessive-NP body with two general closed English word classes (prepositions; degree/repetition adverbs) plus a tightened 2-word cap.

**Target-8 outcome: 6/8 now `CORRECT_RESOLUTION` (75%)**, 1 (`NB-A-04`) moved to a truthfully-blocked state at the already-known identifier-system boundary (not repaired, per explicit scope), 1 (`NB-G-03`) honestly unchanged because no general rule applies — verified this is not a shortfall of the rule but the correct, non-benchmark-fitted behavior.

**Whole-corpus: resolution coverage 19.0%→26.2% (C1), 10.7%→15.5% (C2). Zero regressions, zero new wrong bindings, zero new false positives, anywhere — confirmed not just for the 8 targets but for every possessive-NP-firing case in the entire 79-case corpus.** `INVENTED_CANDIDATE=0`, `BOUNDARY_VIOLATION=0` throughout. Detection recall unchanged (89.3%, exactly as expected — this repair touches evidence quality, not detection). Model calls: 0.

**Level 0 vs. Level 6 distinction preserved throughout** — every one of the 6 new resolutions is `TERM_DISCRIMINATION` (Level 6), never conflated with exact-ID success; `NB-A-04`'s Level 0 path remains blocked exactly as A2.8G characterized, confirming rather than contradicting that prior finding.

**All six out-of-scope items untouched** (verified by direct diff): `NB-J-01`, RAR stemming, RAR's absent-entity check, candidate aliasing, `clause_text`, `recency_rank`. **The six-case candidate-metadata tracking set is bit-identical in outcome between D1R and D1RQ** — this repair does not touch, help, or worsen that latent risk.

**Reproducibility:** D0/D1/D1R/D1RQ bit-identical across 2 fresh runs; only D2 (unaffected, model-assisted) varies as already expected.

**Files created:** `scripts/m35_a2_8h_detector_d1rq.py`, `scripts/m35_a2_8h_run.py`, `docs/plans/M35_URIV1_A2_8H_TELEMETRY.json`, this report.
**Files modified:** none.
**Production files touched:** none.

No commit. No push. No production integration. No model escalation. No architecture change.

Stopped at `VERIFICATION_READY`.
