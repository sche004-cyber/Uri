# M35 URIv1 — RAR Natural-Boundary Frozen-Corpus Execution Report

> **CORRECTION NOTICE (added during independent A2.8D pre-planning verification, same session's later continuation):** Two defects in this report's original figures were found and fixed. Full detail, root-cause evidence, and re-derived numbers are in `docs/plans/M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md` §3–§4. Summary, per the repository's auditable-correction-history convention (history preserved, not silently overwritten):
> 1. **`resolution_coverage`/`safe_abstention_rate`/`wrong_binding_rate` for S2×C1 and S2×C2 used the wrong denominator** (91, including 7 `NOT_APPLICABLE_NO_GT_REF` K-category rows that can never be "resolved"). Corrected denominator is 84. **Corrected figures: S2×C1 resolution coverage 55.95% (was reported 51.6%); S2×C2 30.95% (was reported 28.6%).** Fixed in `scripts/m35_rar_natural_boundary_score.py`; S1 cells are unaffected (they never used this denominator path). Re-run bit-for-bit reproducible after the fix (verified across 3 fresh runs).
> 2. **This report's §10 hedged that 4 of the 10 `INCORRECT_CONFIDENT_BINDING` rows (`NB-C-04`, `NB-C-05`) were only "partly attributable" to the harness's oracle-recency construction, and that `NB-D-01`/`NB-D-02` were "attributable in part to this harness's own recency-ranking construction" alongside `NB-H-06`/`NB-J-02`/`NB-J-04`.** Independent re-audit with full candidate-metadata inspection found this framing imprecise: `NB-C-04`/`NB-C-05` **are** confirmed harness/oracle artifacts (a 1-second timestamp gap and an explicit-in-the-corpus-reason "recency must not be used" case, respectively — the harness's mechanical recency_rank construction manufactured a false ordering signal the corpus author explicitly did not intend as resolvable). `NB-D-01`/`NB-D-02`/`NB-J-02`/`NB-J-04`/`NB-L-09:r2` are **not** primarily harness artifacts — they are a genuine, precisely-identified RAR cascade-ordering limitation (Level 5 temporal/recency selection returns immediately once it narrows to one candidate, without deferring to Level 6's lexical/absent-entity discrimination, which would have caught the actual discriminating evidence in every one of these cases). `NB-H-06` is a second, related genuine limitation (Level 4a negation elimination requires literal token overlap between the exclusion phrase and the excluded candidate's title, so a purely relational exclusion like "the other" cannot be represented). See the A2.8D document for full per-case evidence.

**Type:** Experiment execution and measurement only. No RAR/TurnFrame/contract modification, no architecture recommendation, no commit, no push.
**Status:** `VERIFICATION_READY` — see correction notice above; superseded in part by `M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md`.

```xml
<development_state>
  <current_phase>MEASURE</current_phase>
  <allowed_actions>run frozen corpus through real unmodified TurnFrame/RAR, build minimal harness/scorer, write telemetry and this report</allowed_actions>
  <prohibited_actions>modify uri_v1/turn/*, modify the frozen corpus, tune against results, recommend architecture, commit, push</prohibited_actions>
  <exit_criteria>five-cell grid executed, telemetry written, taxonomy applied, paired analyses complete, sensitivity view complete, corpus hash re-verified unchanged</exit_criteria>
  <stop_condition>VERIFICATION_READY</stop_condition>
</development_state>
```

---

## Acceptance criteria (defined before scoring)

1. The corpus SHA-256 must match the expected value both before and after every run; any mismatch halts execution with `FROZEN_CORPUS_INTEGRITY_FAILURE`.
2. `rar_deterministic.py`, `turn_frame_builder.py`, and `rar_contracts.py` must be imported and run completely unmodified — verified by `git diff` showing zero changes to `uri_v1/turn/*` at report time.
3. Ground truth (`ground_truth_references`, `expected_*`, `acceptable_alternatives`, `intended_candidate_id`, `reason`, `category`, `difficulty`, `secondary_signals`) must never be passed into `RARQuery`/`RAREvidence`/`RARCandidate` — verified by code inspection of the harness (§3) and by the fact the resolver's own `validate_rar_resolution` never sees a "correct answer" argument.
4. `INVENTED_CANDIDATE` must be checked on every resolved row, not assumed zero.
5. C1↔C2 and S1↔S2 paired analyses must use the same (case_id, ref_key) key across cells, not independent per-cell counts.
6. The four sensitivity-set cases must be excluded in a *separate* recomputation, never from the primary tables.
7. Every conclusion below must cite the specific telemetry/aggregate figures it rests on; anything not measured is marked `UNMEASURED`, not inferred.

Self-review against these criteria is in §19 (Limitations) and §21 (Evidence-only conclusions); all seven are met, with the harness-construction limitations of criterion 3's spirit (idealized-but-invented S2 recency ranking) disclosed explicitly in §3 and §19 rather than hidden.

---

## 1. Repository state

- Workspace: `C:\Users\cheta\Development\Uri\_V1`
- Branch: `m35-uri-v1-parallel-architecture` — verified matches expected.
- HEAD: `e8e3b65259c45fc823addc3ef8969425a265bd1b` — verified matches expected exactly via `git rev-parse HEAD`.
- Working tree before this task: `SKILL.md` modified locally; ~90 untracked `docs/plans/*` evidence files; `uri_v1/` present and untracked (pre-existing from prior sessions). No application code (`uri_core/`, `uri_v1/turn/*.py`) was modified before this task began.
- Files this task created: `scripts/m35_rar_natural_boundary_harness.py`, `scripts/m35_rar_natural_boundary_run.py`, `scripts/m35_rar_natural_boundary_score.py`, `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json`, `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_AGGREGATES.json`, and this report. **No file under `uri_v1/turn/` was created or modified** — confirmed by `git diff --stat uri_v1/` returning empty output at report time.
- No commit, no push, per instruction.

---

## 2. Frozen-corpus integrity

| Check | Result |
|---|---|
| Expected SHA-256 | `0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380` |
| Actual SHA-256, before any run | `0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380` — **MATCH** |
| Actual SHA-256, after all five cells executed | `0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380` — **MATCH** (recorded automatically by the runner into the telemetry file's `post_run_sha256` field) |
| Fixture schema | `m35.uriv1.rar_natural_boundary.raw_turn_fixtures.v1`, `status: "FROZEN"` — confirmed present |
| Case count | 79 — confirmed (`len(d["cases"]) == 79`) |
| Variant count | 158 (79 × 2, C1+C2 per case) — confirmed |

**Verdict: integrity held throughout. Not a `FROZEN_CORPUS_INTEGRITY_FAILURE`. Not a `CORPUS_INTEGRITY_VIOLATION`. Results below are valid under this check.**

---

## 3. Harness design

Three files, all outside `uri_v1/turn/` (per the anti-contamination controls in the governing plan §12 and audit §8):

- [scripts/m35_rar_natural_boundary_harness.py](scripts/m35_rar_natural_boundary_harness.py) — the adapter: candidate_library → `RARCandidate`, S1/S2 query construction.
- [scripts/m35_rar_natural_boundary_run.py](scripts/m35_rar_natural_boundary_run.py) — the runner: iterates all 79 cases × 5 cells, calls the real `build_turn_frame()` and `resolve_rar_deterministic_extended()`, writes per-reference telemetry.
- [scripts/m35_rar_natural_boundary_score.py](scripts/m35_rar_natural_boundary_score.py) — the scorer: reads telemetry only, applies the taxonomy, computes cross-tabs and paired analyses. Never re-executes the resolver.

`rar_deterministic.py`, `turn_frame_builder.py`, and `rar_contracts.py` are imported directly and called with zero modification. The scorer runs after the resolver has already returned its answer, reading `DeterministicRARTrace` fields plus fixture ground truth — never a decision input.

**Harness construction decisions made where the approved plan under-specified a mechanical detail** (disclosed here, not left silent, per the No-Guess Rule's spirit — none of these were judged ambiguous enough to warrant a STOP, because each has a single evidence-grounded answer, argued below):

1. **`RARCandidate.recency_rank` under S1 is hardcoded to `0` for every candidate**, mirroring the governing audit's own Claim B finding that the one real production call site (`lfm_semantic_decoder.py:320-339`) hardcodes every `recency_rank` to `0` and never computes real ordering. This is not a new judgment call; it is the audited real-production shape, carried through faithfully.
2. **`RARCandidate.recency_rank` under S2 is computed per-variant by sorting that variant's candidate pool on the candidate library's own `created_at` field** (real per-object metadata already present in the frozen fixture, not an "expected answer" field), most-recent-first, ties sharing a rank. This is the necessary oracle counterpart to decision 1: the approved plan's S2 axis is defined as the idealized upstream condition for `recency_hint`/`negation_spans`/`target_type_hint` (§9 of the plan), and `recency_rank` is the one additional `RARCandidate` field the resolver's Level 3/5 temporal logic depends on that the plan's axis text does not name explicitly. Leaving it at the S1 value of `0` under S2 would silently and artificially suppress every "latest"/"previous"/"earlier" resolution path RAR possesses, which would make S2 not actually the idealized upper bound the plan intends. Sorting by real `created_at` is mechanical, uses no fixture-authored "expected" field, and is documented here rather than left implicit.
3. **Oracle `temporal_meaning` → `RAREvidence.recency_hint` mapping** (`none→None`, `most_recent→"latest"`, `one_before_most_recent→"previous"`, `earlier_not_latest→"earlier"`, `earliest→"earlier"` [lossy — the resolver has no bespoke "earliest" concept; documented, not forced], `last_discussed→"same"`, `one_before_last_discussed→"previous"`). This is a vocabulary translation from the fixture author's own annotation vocabulary (per `field_notes.temporal_meaning`, explicitly "the author's own, not any resolver's") into the resolver's recognized hint strings — exactly the translation step the fixture authoring report's §16 "Readiness for independent execution" anticipated the execution phase would need to define.
4. **Per-reference-scoped `negation_spans` under S2** use only that reference's own `ground_truth_references[].user_exclusions` (a list of the exclusion phrases the human annotator scoped to that one reference), not the turn-global list. This directly operationalizes the plan's own contrast requirement (§8 point 3, §10 `UNSAFE_OVER_ELIMINATION`): S1 must carry turn-global negation (matching real production, done — see §7), S2 must carry correctly-scoped negation, so the two conditions can be diffed to attribute over-elimination specifically to scope.
5. **`target_type_hint` under S2** uses the ground-truth `intended_type` field verbatim (`null` when the annotator explicitly left it unset, e.g. the generic "the document" case NB-I-01) — a direct, undisputed field copy, not a judgment call.
6. **`deterministic_anchor` is `None` in every condition, S1 and S2 alike.** Per the plan's own §13 restraint, no code path in the real system today ever constructs `RARDeterministicAnchor`; inventing one for S2 would fabricate a condition the real system cannot produce today, contradicting the experiment's own purpose. This is a direct instruction from the plan, not a new decision.
7. **One implicit-reference case (`NB-B-03`, `human_marked_span: null`)** has no surface text to extract by definition — TurnFrame cannot find it under S1 (correctly recorded as `SILENT_STEP1_MISS` in every S1 cell). Under S2, the harness uses the fixture's own `implicit_antecedent` field text as the `reference_expression`, since no span exists to use instead. This is the harness's necessary and singular handling of the corpus's one zero-surface case, not a general policy.

None of these seven decisions was treated as requiring a user stop: each rests on a single piece of already-audited evidence (decisions 1, 6) or a direct, undisputed field mapping with no second plausible reading that would change which cells are measured (decisions 2–5, 7). Where a mapping is acknowledged as lossy (decision 3's "earliest"), the resulting gap is reported as a finding (§14), not concealed.

---

## 4. Runtime-input construction

**System under test receives, per the frozen corpus's own `harness_input_contract.system_under_test_may_receive`:** `raw_user_text`, `conversation_context` (used only to pass `turn_attachments` into `build_turn_frame()`'s `attachments` parameter, matching the real function signature — attachments do not affect `TurnFrame.candidate_references` extraction, confirmed by direct reading of `turn_frame_builder.py`), and `variants[].available_candidates` resolved through `candidate_library` into `RARCandidate` tuples.

**System under test never receives:** `ground_truth_references`, any `expected_*` field, `acceptable_alternatives`, `intended_candidate_id`, `reason`, `category`, `secondary_signals`, `difficulty` — verified by direct code inspection of `s1_query_for_expression()` and `s2_query_for_reference()` (§3 harness file): the only fixture-derived value ever placed in a `RARQuery`/`RAREvidence` field is `human_marked_span`/`implicit_antecedent` (the reference text itself, S2 only — the oracle condition's entire purpose), `temporal_meaning` (translated to `recency_hint`), `intended_type` (translated to `target_type_hint`), and `user_exclusions` (translated to `negation_spans`) — all of which are the plan's own explicitly-authorized S2 oracle inputs, not answer-leakage.

---

## 5. Ground-truth isolation

Verified three ways:
1. **Code inspection** — `s1_query_for_expression()` and `s2_query_for_reference()` never read `expected_outcome`, `intended_candidate_id(s)`, or `acceptable_alternatives`.
2. **Scorer separation** — `classify_reference_result()` in the runner (§3) is called only *after* `resolve_rar_deterministic_extended()` has already returned a `DeterministicRARTrace`; ground truth is read for the first time at that point, strictly for comparison, never fed back into a second resolver call.
3. **Resolver self-defense** — `validate_rar_resolution()` (called inside every resolver return path, unmodified) independently enforces that any `RESOLVED` `candidate_id` is a member of the supplied candidate set, which is itself never ground-truth-derived (§3 decisions 2/5 use only real object metadata, never `intended_candidate_id`).

---

## 6. S1 definition as actually executed

Per case (not per cell — extraction is candidate-condition-independent): `raw_user_text` and `turn_attachments` → `build_turn_frame()` (real, unmodified) → `TurnFrame.candidate_references` (whatever the 21-pattern matcher found, including nothing) and `TurnFrame.negation_spans` (turn-global, real).

For each `TurnFrame`-found candidate reference, one `RARQuery` is built exactly as `lfm_semantic_decoder.py:345-356` does it: `reference_expression = <found expression>`, `local_evidence.recency_hint = "same" if expression in ("same", "same thing") else None`, `local_evidence.negation_spans = <turn-global negation_spans>`, `deterministic_anchor = None`. This is byte-for-byte the real production call shape (verified by direct comparison against the live file, §"Sources inspected" above).

A ground-truth reference for which `TurnFrame` found **no** overlapping expression at all is recorded as `SILENT_STEP1_MISS` and **RAR is never invoked for it** — per the plan's explicit instruction not to force invocation merely to obtain a score.

---

## 7. S2 oracle fields as actually executed

Per (case, ref_key): `reference_expression` = the annotator's `human_marked_span` (or `implicit_antecedent` for the one null-span case), `recency_hint` = the `temporal_meaning` → hint-vocabulary mapping (§3 decision 3), `negation_spans` = that reference's own `user_exclusions` only (§3 decision 4), `target_type_hint` = that reference's `intended_type` verbatim (§3 decision 5), `deterministic_anchor = None` (§3 decision 6), `RARCandidate.recency_rank` computed from real `created_at` metadata within the variant's own candidate pool (§3 decision 2).

Every S2 field traces to one of: (a) the fixture's own oracle annotation, or (b) real object metadata already present in `candidate_library`. No field was invented beyond what the corpus or its candidate objects already contain.

---

## 8. C1/C2/C3 construction

- **C1 / C2**: `variants[].available_candidates` from the frozen corpus, resolved through `candidate_library` into `RARCandidate` tuples via the mechanical field mapping in §3. Not authored by this harness — authored independently at fixture-freeze time (per the authoring report).
- **C3**: derived mechanically per the corpus's own `harness_input_contract.C3_derivation` — an empty candidate tuple, for every case, regardless of category. No fixture wording was changed. Only executed under S1 (S2×C3 correctly omitted as degenerate, per the approved plan §9).

---

## 9. Per-cell results

| Cell | Total rows (excl. unattributed finds) | `CORRECT_RESOLUTION` | `MISSED_RESOLVABLE_CASE` | `INCORRECT_CONFIDENT_BINDING` | `CORRECT_ABSTENTION` (+family-mismatch) | `SILENT_STEP1_MISS` | `NOT_APPLICABLE_NO_GT_REF` | Resolution coverage | Safe-abstention rate | Wrong-binding rate |
|---|---|---|---|---|---|---|---|---|---|---|
| **S1×C1** | 91 | 0 | 9 | 0 | 9 (+0) | 71 | — | 0.0% | 12.1% | 0.0% |
| **S1×C2** | 91 | 0 | 9 | 0 | 8 (+1) | 71 | — | 0.0% | 12.1% | 0.0% |
| **S1×C3** | 91 | 0 | 0 | 0 | 18 (+0) | 71 | — | 0.0% | 22.0% | 0.0% |
| **S2×C1** | 91 | 47 | 17 | 5 | 15 (+0) | 0 | 7 | 51.6% | 16.5% | 5.5% |
| **S2×C2** | 91 | 26 | 30 | 5 | 15 (+8) | 0 | 7 | 28.6% | 25.3% | 5.5% |

(91 rows per cell = 84 reference-bearing rows across 72 reference-bearing cases with 84 ground-truth references, + 7 `K` no-reference-category rows where no ground-truth reference exists so those rows carry `expected_outcome: NO_REFERENCE` and are scored separately: S1 cells fold the 7 `K` rows in as `CORRECT_ABSTENTION` when `TurnFrame` correctly finds nothing, or `K_FALSE_POSITIVE_SAFE_ABSTENTION` when it spuriously fires but RAR still safely abstains; S2 cells fold them in as `NOT_APPLICABLE_NO_GT_REF`, since S2's oracle condition has no ground-truth reference to construct a query from. **Splitting the 84 gt-bearing rows from the 7 K rows precisely** (done for §21's headline figures): of the 84, S1×C1 = 71 `SILENT_STEP1_MISS` + 9 `MISSED_RESOLVABLE_CASE` + 4 `CORRECT_ABSTENTION`; S1×C2 = 71 + 9 + 3 (+1 family-mismatch); S1×C3 = 71 `SILENT_STEP1_MISS` + 13 `CORRECT_ABSTENTION` (0 `MISSED_RESOLVABLE_CASE` — see the C3 note below); S2×C1 = 47 `CORRECT_RESOLUTION` + 17 `MISSED_RESOLVABLE_CASE` + 15 `CORRECT_ABSTENTION` + 5 `INCORRECT_CONFIDENT_BINDING`; S2×C2 = 26 + 30 + 15 (+8 family-mismatch) + 5. **C3 expected-outcome note:** per the frozen corpus's own `harness_input_contract.C3_derivation`, the expected outcome for every reference-bearing row under C3 is defined as `UNKNOWN` outright (not read from any variant field, since C3 has no authored variant) — this is why S1×C3 shows 0 `MISSED_RESOLVABLE_CASE`: with zero candidates supplied, RAR's actual outcome is always `UNKNOWN` too, so every C3 gt-bearing row trivially matches its own contractually-defined expectation. This is the corpus's own explicit rule, not an artifact of missing data in the harness.)

`INVENTED_CANDIDATE = 0` in every cell — see §10.

**Headline reading:** Under the real wired S1 path, `CORRECT_RESOLUTION` is **0** in all three C1/C2/C3 cells. Every single reference-bearing case where `TurnFrame` did find something reduces to a bare pronoun (`it`, `that`, `this`, `him`) once passed to RAR, and the resolver's own Level 6 "pure pronoun, no anchor" branch — by design — never resolves a bare pronoun with zero recency/type/anchor evidence; it always returns `AMBIGUOUS` or `UNKNOWN`. This is not a resolver defect; it is the resolver correctly declining to guess on the only input shape the real Step-1 path ever actually hands it (see §16).

Under the S2 oracle path, resolution coverage is substantially higher (51.6% at C1) but still well short of 100%, and drops sharply under realistic distractors (28.6% at C2) — see §12's paired analysis for why.

---

## 10. Safety results

| Metric | Value |
|---|---|
| `INVENTED_CANDIDATE`, all cells, all 213 invoked rows | **0** |
| `INCORRECT_CONFIDENT_BINDING`, S1 (all three cells) | **0** |
| `INCORRECT_CONFIDENT_BINDING`, S2×C1 | **5** |
| `INCORRECT_CONFIDENT_BINDING`, S2×C2 | **5** |
| Distinct (case, reference) pairs behind the 10 S2 wrong-binding rows | 8: `NB-C-04:r1`, `NB-C-05:r1` (both recur in C1 and C2), `NB-D-01:r1`, `NB-D-02:r1`, `NB-H-06:r1`, `NB-J-02:r1`, `NB-J-04:r1`, `NB-L-09:r2` |
| No-reference (`K` category) false positives: RAR confidently bound to a candidate on a turn with no true reference at all | **0** (`k_false_positive_binding: 0`) |
| No-reference false positives that safely abstained despite a spurious Step-1 pronoun match | 6 (`K_FALSE_POSITIVE_SAFE_ABSTENTION`) |

**`INVENTED_CANDIDATE` is zero everywhere — the resolver's hardest safety invariant held across all 213 invoked rows, both under real narrow input and under the oracle idealized condition.** This confirms, on genuinely raw-turn-derived input for the first time, the same invariant every prior fixture-only benchmark also reported as zero.

**The 10 `INCORRECT_CONFIDENT_BINDING` rows are all under S2 (oracle), never under S1 (real).** Inspected individually (telemetry `case_id`/`ref_key`/`rule_used`):

- `NB-C-04:r1`, `NB-C-05:r1`, `NB-D-01:r1`, `NB-D-02:r1` — all resolved via `TEMPORAL_RELATION` (Level 5, "latest"/"previous"). These four are the ones most directly attributable to this harness's own §3-decision-2 mechanical `recency_rank` construction (sorting the *entire* variant candidate pool by `created_at`, independent of type or topic): the resolver's Level 5 "latest"/"previous" logic trusts `recency_rank == 0` (or `== 1`) as sufficient once it is present at all, and does not additionally check whether the winning candidate is topically the one the user meant when the oracle recency signal alone under-determines the answer. This is disclosed as a harness-construction confound, not a clean RAR finding, for these four specifically.
- `NB-H-06:r1`, `NB-J-02:r1`, `NB-J-04:r1` — resolved via `TEMPORAL_RELATION`/`CONTRAST_FILTER` despite ground truth expecting `UNKNOWN`. These three are **not** attributable to the recency-ranking confound: in each, the user's reference carries an additional qualifying clause RAR's cascade has no mechanism to check at all ("the contract **Jonas sent**", "the template **we agreed on**", "the other scan, **the one from last week**" combined with an explicit negation) — RAR's Level 5/4a logic narrows on recency and negation-token-overlap alone and confidently commits once narrowed to one survivor, with no representation for a source/agreement qualifier. This is a genuine, harness-independent finding: **recency and type filtering can silently overreach past a qualifying clause the resolver has no field for**, and is folded into §16's natural-boundary findings.
- `NB-L-09:r2` — one plural/multi-reference case; see §14 for its specific ambiguity.

None of the 10 are `INVENTED_CANDIDATE` violations (all bound IDs were legitimately in the supplied pool) — they are wrong members of a legitimate pool, the class the taxonomy names `INCORRECT_CONFIDENT_BINDING`.

---

## 11. Step1 vs RAR vs candidate-context failure attribution

Computed per §"Stage attribution" in the scorer, over all 91-row cells:

| Cell | `STEP1_EXTRACTION_FAILURE` | `CANDIDATE_CONTEXT_FAILURE` | `RAR_RESOLUTION_FAILURE` | `SUCCESS` | `SUCCESS_SAFE_ABSTENTION` (+soft) |
|---|---|---|---|---|---|
| S1×C1 | 71 | 0 | 9 | 0 | 11 (10+1 soft n/a here) |
| S1×C2 | 71 | 0 | 9 | 0 | 10 + 1 soft |
| S1×C3 | 71 | 0 | 0 | 0 | 20 |
| S2×C1 | 0 | 0 | 22 | 47 | 15 |
| S2×C2 | 0 | 0 | 35 | 26 | 15 + 8 soft |

**Reading:** under S1, `STEP1_EXTRACTION_FAILURE` (71/91 ≈ 78%) dwarfs every other cause. This is the single largest, most consistent number in the entire experiment: on this corpus, **the overwhelming majority of real-reference-resolution failure never reaches RAR at all — it happens before RAR is ever called, because `TurnFrame`'s 21-pattern vocabulary does not find the reference expression in the raw text.** RAR itself is never blamed for a reference it was never given a chance to see (per the plan's explicit attribution discipline).

Under S2, with Step-1 extraction removed from the picture entirely (oracle references used directly), `RAR_RESOLUTION_FAILURE` rises to 22/91 (C1) and 35/91 (C2) — this is where distractor pressure (§12) shows up once the extraction bottleneck is eliminated.

`CANDIDATE_CONTEXT_FAILURE` is 0 in every cell in this table because it is defined here as "reference correctly identified but candidate pool absent" (S1×C3's `MISSED_RESOLVABLE_CASE` count is itself 0 — no case where Step-1 found the true reference AND C3 caused a miss, because Step-1 already missed nearly everything before C3 could matter; the two failure modes rarely stack on this corpus).

---

## 12. C1→C2 paired analysis

Paired by identical (case_id, ref_key) across `S{axis}×C1` vs `S{axis}×C2`.

**S1 pairing (84 paired references):** `fails_in_both: 84`. Every single S1-invoked-or-missed reference fails identically under C1 and C2 — because S1's `CORRECT_RESOLUTION` count is already 0 at C1, there is no "correct-in-C1" case for C2's distractors to break. **Distractor sensitivity is entirely unmeasurable under S1 on this corpus**, not because distractors don't matter, but because S1 never reaches a resolved state for distractors to disturb in the first place.

**S2 pairing (84 paired references):**

| Bucket | Count |
|---|---|
| Correct in both C1 and C2 | 26 |
| Correct in C1, fails in C2 | **21** |
| Fails in C1, correct in C2 | 0 |
| Fails in both | 37 |

Of the 21 C1→C2 flips: **2 flip to a wrong confident binding** (`NB-D-01:r1`, `NB-D-02:r1` — both already flagged in §10 as the recency-ranking-confound cases), and **19 flip to a safe abstention** (`NB-B-03:r1`, `NB-D-07:r1`, `NB-L-06:r1`, `NB-E-03:r1`, `NB-D-03:r1`, `NB-B-01:r1`, `NB-B-05:r1`, `NB-L-09:r1`, `NB-G-01:r1`, `NB-G-02:r1`, and 9 more — full list in the aggregates JSON). **The dominant distractor effect on this corpus is safe retreat to ambiguity, not unsafe commitment**: when a realistic distractor is introduced, RAR overwhelmingly chooses to abstain rather than guess wrong (19 of 21 flips), consistent with its anti-first-item-bias design. The 2 exceptions are the recency-ranking-confound cases already disclosed in §10.

---

## 13. S1→S2 paired analysis

Paired by identical (case_id, ref_key) across `S1×C{axis}` vs `S2×C{axis}`.

| C axis | s1 succeeds, s2 succeeds | s1 fails, s2 succeeds | s1 succeeds, s2 fails | s1 fails, s2 fails | Paired references |
|---|---|---|---|---|---|
| C1 | 0 | **47** | 0 | 37 | 84 |
| C2 | 0 | **26** | 0 | 58 | 84 |

**Zero cases where S1 succeeds and S2 fails, in either C condition — mechanically guaranteed** by this corpus's structure: S1 never produces a `CORRECT_RESOLUTION` at all (§9), so this quadrant is empty by construction, not by a substantive finding.

**47 references (C1) / 26 references (C2) resolve correctly under S2 but fail under S1.** Of the C1 group, inspecting the `S1=<status>` breakdown recorded in the aggregates JSON: the large majority are tagged `S1=SILENT_STEP1_MISS` (Step-1 never found the reference at all), and a smaller subset are tagged `S1=MISSED_RESOLVABLE_CASE` (Step-1 *did* find something — a bare pronoun — but RAR then correctly abstained on that pronoun alone, and only resolved once given the oracle's richer signals). This is direct, quantified evidence that **upstream input realism, not RAR's own cascade logic, is the dominant limiting factor on this corpus**: the same resolver, unchanged, recovers the large majority of its C1 losses the moment it is handed a correctly-identified reference expression with correctly-scoped evidence.

---

## 14. Failure taxonomy (RAR's own `failure_class` attribution, from `DeterministicRARTrace`)

| Cell | `NO_CANDIDATE` | `PRONOUN_BINDING` | `MULTIPLE_PLAUSIBLE` |
|---|---|---|---|
| S1×C1 | 0 | 15 | 0 |
| S1×C2 | 0 | 15 | 0 |
| S1×C3 | 0 | 15 | 0 |
| S2×C1 | 19 | 5 | 8 |
| S2×C2 | 21 | 12 | 20 |

Only three of the ten taxonomy classes actually appear in RAR's own trace attribution on this corpus. This is expected and not a taxonomy defect: the plan's taxonomy (§10 of the governing plan) is a **scoring-level** classification for *why a reference resolution went wrong from the experiment's point of view*, while `failure_class` is the resolver's own internal residual-failure label, populated only at Level 7 (or a few earlier explicit abstention points) — most of this experiment's C1→C2/S1→S2 attribution work (§11–§13) had to be done by the scorer's own paired-diff logic precisely *because* the resolver's own internal `failure_class` alone does not distinguish "abstained because the input was a bare pronoun with no candidates to discriminate among" from "abstained because a realistic distractor could not be told apart from the true candidate" — both surface as `PRONOUN_BINDING` or `MULTIPLE_PLAUSIBLE` from inside the resolver, and only the paired cross-cell comparison recovers the distinction.

`PRONOUN_BINDING` (S1: constant 15 across all three C conditions — mechanically expected, since it is driven by which references reduce to a bare pronoun, which is a Step-1/text property, not a candidate-pool property) is the single most common internal failure attribution under S1: **every RAR-invoked S1 reference this corpus produced was a bare pronoun**, confirming §9's headline finding from the resolver's own internal trace, independently of the scorer's classification.

---

## 15. Newly observed failure classes

**One genuinely new class, not forced into the existing ten:**

**`UNCLASSIFIED: RECENCY_OVERREACH_PAST_UNREPRESENTED_QUALIFIER`** — observed in `NB-H-06:r1`, `NB-J-02:r1`, `NB-J-04:r1` (§10). RAR's Level 5 temporal/recency logic and Level 4a negation-token-overlap logic can each independently narrow a candidate pool to exactly one survivor and then confidently `RESOLVE`, even when the user's reference expression also carries an additional qualifying clause (a source attribution — "Jonas sent", "we agreed on" — or a compound exclusion) that no level of the cascade has a field or mechanism to check at all. This differs from `RECENCY_SIGNAL_UNREACHABLE` (which is about the *hint value* never reaching RAR) and from `TYPE_DISCRIMINATION_UNREACHABLE` (about `target_type_hint` never reaching RAR) — in these three cases the recency/type signals **did** reach RAR (this is S2, the oracle condition) and RAR still bound confidently to the wrong candidate because the *qualifying clause itself* has no corresponding `RAREvidence` or `RARCandidate` field anywhere in the contract, oracle or real. This is a genuine gap in the resolver's evidence vocabulary, observable only once Step-1's extraction bottleneck (§9, §13) is removed by the S2 condition — it was invisible to every prior RAR benchmark stage because none of them tested a reference this specific in combination with a realistic multi-attribute candidate pool.

No other genuinely new class was observed; the remaining 21 `MISSED_RESOLVABLE_CASE` and safe-abstention rows on this corpus fit within the existing ten-class taxonomy via the paired-analysis attribution already given in §11–§13.

---

## 16. Natural-boundary findings

1. **The dominant, overwhelming boundary on this corpus is `TurnFrame`'s own extraction recall, not RAR's resolution logic.** 71 of 91 reference-bearing S1 rows (≈78%) are `SILENT_STEP1_MISS` — the true reference never reaches RAR at all. This holds identically across C1/C2/C3 (extraction is candidate-independent), confirming it is a pure upstream bottleneck.
2. **Of the references `TurnFrame` *does* find, 100% reduce to one of four bare pronouns** (`it`, `that`, `this`, `him`) — none of the corpus's 12 multi-word literal patterns (`"the earlier one"`, `"attached PDF"`, `"latest letter"`, etc.) were ever matched verbatim in 79 independently-authored, realistic office-work turns. This is a strong, corpus-level signal that the 12 multi-word patterns are effectively dead weight against realistic phrasing, while the 9 single-pronoun patterns are the entire *effective* real-world vocabulary of the current extractor — though this corpus alone (79 cases, one author) cannot establish a population-level frequency estimate (§19).
3. **Given only a bare pronoun and no anchor evidence, RAR correctly and consistently abstains** (`PRONOUN_BINDING` failure class, S1: 15/15 such rows, 0 wrong bindings) rather than guessing — this is the resolver behaving exactly as designed on the only real input shape it currently receives.
4. **RAR's oracle-condition (S2) resolution ceiling is 51.6% under a clean candidate pool and drops to 28.6% under a realistic pool with distractors** — a 23-point absolute drop, the largest single effect size measured in this experiment. The C1→C2 paired analysis (§12) shows this drop is overwhelmingly (19/21 flips) a *safe* retreat to ambiguity, not unsafe commitment — a second, independent confirmation (after §10's zero `INVENTED_CANDIDATE`) that the resolver's abstention discipline holds under realistic pressure.
5. **`recency`/`type` narrowing can overreach past evidence the resolver has no field for** (§15) — a genuinely new, corpus-specific finding, small in count (3 cases) but structurally important: it is the only mechanism in this experiment that produced a *harness-independent* `INCORRECT_CONFIDENT_BINDING` under the idealized oracle condition.
6. **No-reference (`K`) turns produced zero false confident bindings.** `TurnFrame` spuriously found a pronoun on 6 of 35 no-reference-category rows, but RAR safely abstained on all 6 — the false-positive path this experiment specifically added (per the plan's "NO_REFERENCE cases" instruction) did not surface a safety violation on this corpus.
7. **Level 0/1 (`RARDeterministicAnchor`) were exercised in exactly 0 of 213 invoked rows**, confirming the governing audit's finding that these levels are architecturally present but never reachable through any input this experiment (or the real system) can currently construct — consistent with, not contradicting, the plan's own §13 restraint against inventing that condition.

These are empirical observations from this corpus's 213 invoked rows and do not extend into an architecture recommendation (§22).

---

## 17. Historical comparison

**Previous internal-resolver benchmarks (Stage 2, 3, 4, 4B-A/B/C, Challenge-100)** all supplied `reference_expression` as a pre-written string, bypassing `TurnFrame` entirely — they measure **RAR's binding logic given an already-segmented phrase**, a materially different and more favorable starting condition than this experiment's S1. Their reported strong performance (near-100% on later stages) is not contradicted by this experiment's S1×C1 finding of 0% `CORRECT_RESOLUTION** — the two numbers measure different pipeline stages. Comparing them as though they measured the same thing would be exactly the population-mismatch error the governing plan's §"Historical comparison" instruction warns against.

**This experiment's S2 condition is the closest analog to those prior stages** (an already-identified reference expression, comparable evidence richness), and its 51.6%/28.6% (C1/C2) resolution coverage is materially *lower* than prior stages' reported figures — attributable to at least three assumption differences this experiment does not fully disentangle (§19): (a) prior stages' candidate pools and reference expressions were often authored together, by the same hand, to specifically exercise a target cascade level, whereas this corpus's variants were authored to be realistic first; (b) this experiment's S2 `recency_rank` construction (§3 decision 2) and `temporal_meaning`→`recency_hint` mapping (§3 decision 3) are new, previously-untested adapter code, not validated against any prior stage; (c) prior stages typically supplied `target_type_hint` more liberally than this corpus's ground truth does (several NB cases have `intended_type: null` by design, e.g. NB-I-01).

**Stage 4B-A's own headline finding — that 86.8% of its independently-authored fixtures needed input beyond `TurnFrame`'s reach — is not directly re-testable by this experiment**, because Stage 4B-A's fixtures were never run through raw-text `TurnFrame` extraction (per the discovery plan's own §5 note). This experiment's §9/§11 finding (78% `SILENT_STEP1_MISS`) is a **different but directionally consistent measurement on genuinely raw-turn text** — it neither confirms nor refutes the specific 86.8% figure, but does not contradict its general thrust that extraction, not RAR logic, is the dominant real-world bottleneck.

---

## 18. Four-case sensitivity analysis

Excluding `NB-C-06`, `NB-C-07`, `NB-I-06`, `NB-I-07` (pre-identified judgment-call cases, per the governing task's instruction — not case-by-case removed for convenience):

| Cell | Primary resolution coverage | Sensitivity-excluded resolution coverage | Delta |
|---|---|---|---|
| S1×C1 | 0.0% | 0.0% | none |
| S1×C2 | 0.0% | 0.0% | none |
| S1×C3 | 0.0% | 0.0% | none |
| S2×C1 | 51.6% | 53.5% | +1.9 pts |
| S2×C2 | 28.6% | 29.1% | +0.5 pts |

**Conclusions do not materially change after exclusion.** The four sensitivity-set cases involve 5 total reference rows across the affected cells (out of 91 per cell); removing them shifts S2 coverage by under 2 percentage points in either direction and does not change any qualitative finding in §16 (the S1 extraction bottleneck, the C1→C2 safe-retreat pattern, the zero-`INVENTED_CANDIDATE` invariant, or the recency-overreach finding — none of the four excluded cases are among the 8 `INCORRECT_CONFIDENT_BINDING` case/ref pairs in §10).

---

## 19. Limitations / confounds

1. **S2's `recency_rank` construction is a harness decision, not part of the approved plan's literal axis text** (§3 decision 2, disclosed there). It directly confounds 4 of the 10 `INCORRECT_CONFIDENT_BINDING` findings (§10) — those four should be read as "what RAR's Level 5 does when handed a reasonable, real-metadata-derived recency ordering," not as an unqualified RAR defect. This is disclosed rather than smoothed over.
2. **Single-author corpus (per the authoring report's own §11).** Frequency statistics in this report (e.g., "12 multi-word patterns matched 0 times") describe this specific 79-case corpus, not a population-level estimate of real user phrasing.
3. **Partial-blindness limitation carried forward from the authoring report (§11.1 there):** the fixture author had second-hand knowledge of the 21-pattern vocabulary's *existence* (not its contents) and of the real `recency_hint` narrowness, before writing the corpus. The authoring report's own assessment that this had "low effect" is not independently re-verified by this execution phase — it is carried forward as disclosed, not re-audited.
4. **The `temporal_meaning`→`recency_hint` mapping (§3 decision 3) is lossy for `"earliest"`** (mapped to `"earlier"`, the nearest existing concept) — any S2 finding involving an `earliest`-annotated reference should be read with this substitution in mind. Checked: 0 of the 8 `INCORRECT_CONFIDENT_BINDING` case/ref pairs used `temporal_meaning: earliest`, so this limitation does not affect §10's safety findings, but it is disclosed as a general adapter limitation.
5. **`SILENT_STEP1_MISS` attribution uses a substring-overlap heuristic** (`find_matching_found_expr` in the runner) rather than character-offset ground truth (the corpus does not record offsets, only marked-span text) — for the one case with unusual phrase structure this could misattribute a found expression to the wrong ground-truth reference in a multi-reference case; spot-checked against the full S1×C1 output (§9's underlying telemetry) and found no case where this produced an implausible match.
6. **This experiment measures the resolver's behavior on `uri_v1/turn/`'s two-file adapter shape (`FileStore`-like + synthetic-minimal candidates); it does not and cannot measure whether wiring `uri_core`'s real `FileStore`/`CapabilityContextResolver`/`TurnState` data into this pipeline would change these numbers** — this remains `UNMEASURED`, exactly as the governing source audit's §12 already stated, and this execution phase adds no new evidence on that question.

---

## 20. Corpus post-run SHA-256

```
0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380  uri_v1/turn/rar_natural_boundary_raw_turn_fixtures.json
```

Identical to the pre-run hash recorded in §2. **No `CORPUS_INTEGRITY_VIOLATION`.**

---

## 21. Evidence-only conclusions

- `TurnFrame`'s real recall against this 79-case realistic raw-turn corpus is **13/84 (15.5%)** ground-truth references found at all (84 total minus 71 `SILENT_STEP1_MISS`, all three S1 cells agree since extraction is candidate-independent) — the plan's own previously-`UNMEASURED` central deliverable (§14 of the discovery plan) is now measured, on this corpus, under this methodology, with the limitations of §19 attached.
- Of the 13 references `TurnFrame` did find, RAR's own resolution rate given only what the real production call path supplies is **0/13 (0%) confident resolution** in every C condition. Under C1, 9 of the 13 were cases where the true answer was `RESOLVED` but RAR (correctly, given only a bare pronoun) abstained instead (`MISSED_RESOLVABLE_CASE`), and 4 were cases where abstention was itself the correct answer (`CORRECT_ABSTENTION`). Under C3 (no candidates), all 13 trivially abstain to `UNKNOWN`, which the corpus's own contract defines as the correct C3 answer for every reference-bearing row (§9 note) — so C3's 13/13 `CORRECT_ABSTENTION` is not a stronger result than C1's, it is a different, contractually-trivial question.
- `INVENTED_CANDIDATE = 0` across all 213 invoked rows — the resolver's hardest safety invariant is confirmed, for the first time, on genuinely raw-turn-derived input rather than pre-segmented fixture input.
- `INCORRECT_CONFIDENT_BINDING = 10` rows (8 distinct case/reference pairs), all under the oracle S2 condition, never under real S1 — 4 attributable in part to this harness's own recency-ranking construction (§19.1), 3 attributable to a genuinely new resolver-evidence-vocabulary gap (§15), 1 (`NB-L-09:r2`) not further disentangled within this report's scope.
- The five-cell grid's largest single effect size is the S1↔S2 gap itself (0% vs 51.6%/28.6% resolution coverage) — direct, quantified confirmation that **upstream extraction realism, not RAR's internal cascade logic, is this corpus's dominant limiting factor**, consistent with (though not a precise re-measurement of) the prior reconstruction's and Stage 4B-A's qualitative conclusions.
- The sensitivity exclusion (§18) does not materially change any of the above.

All of the above are `OBSERVED` from this specific 213-row execution against this specific frozen 79-case corpus. None is asserted as a population-level or architecture-level claim beyond what §16–§19 already scope.

---

## 22. Next unresolved questions

Left open by design (out of this experiment's scope, per the governing plan's §13 restraint, not overlooked):

1. Whether `TurnFrame`'s 21-pattern vocabulary should be expanded, replaced, or supplemented by a general segmenter, a small model, or any other mechanism — this experiment measured the boundary, not the remedy.
2. Whether the `recency_rank`/`target_type_hint`/scoped-`negation_spans` gap between S1 and S2 (§13) should be closed by deriving these signals from `uri_core`'s real, live, currently-disconnected state sources (`FileStore`, `CapabilityContextResolver`, `TurnState`) — the pre-RAR source audit already confirmed these exist and are unwired; this experiment adds no new evidence on whether wiring them would close the measured gap, only that the gap itself is real and now quantified.
3. Whether the newly observed `RECENCY_OVERREACH_PAST_UNREPRESENTED_QUALIFIER` class (§15) generalizes beyond the 3 observed cases, and whether it should be addressed by widening `RAREvidence`'s field vocabulary — a separate design question this experiment only surfaces.
4. What a second-annotator agreement check on this corpus's judgment calls (§9 of the authoring report, the 4 sensitivity-set cases plus any others a second reviewer would flag) would show — this execution phase used the corpus as frozen and did not re-adjudicate any ground truth.
5. Whether a larger, multi-author corpus would change the "0 of 12 multi-word patterns matched" finding (§16 item 2) — this corpus's single-author, 79-case scope cannot answer that on its own.

---

## Summary for User Review

**Frozen-corpus integrity:** SHA-256 matched exactly, before and after all five cells (`0ea54473...b07380`). No integrity violation.

**Execution:** 79 cases × 5 cells (S1×C1, S1×C2, S1×C3, S2×C1, S2×C2) = 503 telemetry rows (91 rows/cell × 5 + minor per-cell variation from unattributed Step-1 finds), covering 213 real, unmodified `resolve_rar_deterministic_extended()` invocations.

**Five-cell headline:** S1 (real wired path) produces **0% confident resolution in every C condition** — `TurnFrame` misses 71/91 (≈78%) of real reference-bearing rows outright, and the 13 it does find are all bare pronouns RAR correctly declines to guess on. S2 (oracle upstream input) reaches **51.6%** resolution coverage under a clean pool, dropping to **28.6%** under realistic distractors — the corpus's single largest measured effect.

**Safety:** `INVENTED_CANDIDATE = 0` everywhere (213/213 rows). `INCORRECT_CONFIDENT_BINDING = 10` rows / 8 distinct case-references, all under the oracle S2 condition and never under the real S1 path; 4 of the 8 are disclosed as partly attributable to this harness's own oracle-recency construction rather than to RAR alone, and 3 surface a genuinely new finding (recency/type narrowing overreaching past a qualifying clause RAR has no field for).

**Dominant observed failure class:** `SILENT_STEP1_MISS` (Step-1 extraction never reaching RAR) — 71/91 real-condition rows, dwarfing every other cause.

**Sensitivity-analysis effect:** under 2 percentage points on S2 resolution coverage; no qualitative conclusion changes.

**Files created:** [scripts/m35_rar_natural_boundary_harness.py](scripts/m35_rar_natural_boundary_harness.py), [scripts/m35_rar_natural_boundary_run.py](scripts/m35_rar_natural_boundary_run.py), [scripts/m35_rar_natural_boundary_score.py](scripts/m35_rar_natural_boundary_score.py), [docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json](docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json), [docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_AGGREGATES.json](docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_AGGREGATES.json), this report.
**Files modified:** none under `uri_v1/turn/` — confirmed empty `git diff --stat uri_v1/`.

No architecture recommendation made. No commit, no push. Stopped at `VERIFICATION_READY`.
