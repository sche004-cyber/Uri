# M35 URIv1 — A2.8I: Post-Repair End-to-End Residual Audit (D1RQ → candidate construction → RAR)

**Type:** Forensic audit only. No repair, no architecture change, no model qualification, no production integration. No commit, no push.
**Subject path:** D1RQ (`scripts/m35_a2_8h_detector_d1rq.py`) → existing candidate construction (`scripts/m35_rar_natural_boundary_harness.py::build_candidate_pool`, `oracle_recency=False`) → existing RAR (`uri_v1/turn/rar_deterministic.py::resolve_rar_deterministic_extended`).
**Status:** `VERIFICATION_READY`

```xml
<development_state>
  <current_phase>POST_REPAIR_RESIDUAL_AUDIT</current_phase>
  <allowed_actions>read repository evidence, recompute A2.8H metrics from raw telemetry, re-execute the deterministic pipeline and run diagnostic counterfactual probes in the session scratchpad only, classify every residual, write this report</allowed_actions>
  <prohibited_actions>modify D1RQ/D1R/D1/RAR/contracts/harness/corpus/telemetry, implement any repair, add a model, integrate into production, commit, push</prohibited_actions>
  <exit_criteria>A2.8H independently verified; complete residual population tabulated; every residual owned; nine undetected re-evaluated; RAR/candidate/contract inventories complete; path map complete; next experiment selected with rationale; evidence gaps disclosed</exit_criteria>
  <stop_condition>VERIFICATION_READY</stop_condition>
</development_state>
```

---

## Acceptance criteria (defined before the audit)

1. **AC1** — Every A2.8H quantitative claim is recomputed from the raw telemetry JSON (not the report prose), and additionally re-derived by an independent re-execution of the deterministic pipeline; every discrepancy is recorded as a correction, not silently absorbed.
2. **AC2** — The residual population is the *complete* set of ground-truth-bearing references whose D1RQ outcome is not correct (not only previously targeted cases), with every required field (Phase 2) populated from telemetry/re-execution, not inferred.
3. **AC3** — Every residual has exactly one *primary* (earliest-failure) owner, supported by a stated mechanism and, where possible, a counterfactual probe; secondary blockers are recorded separately so the primary tally sums exactly to the residual count.
4. **AC4** — "Information exists but is disconnected" is kept distinct from "information/capability does not exist", with the repository location (and checkout) named for every "exists" claim.
5. **AC5** — Every uri_core reference names its checkout: in this document "uri_core" means `C:\Users\cheta\Development\Uri\_V1\uri_core` (tracked in this repository at HEAD `e8e3b65`), unless stated otherwise.
6. **AC6** — Nothing in the repository is modified except the creation of this file; all diagnostic code lives in the session scratchpad.
7. **AC7** — Unverifiable items are stated explicitly with their effect on the verdict (§15).
8. **AC8** — The next-experiment recommendation cites Phase 9/10 criteria (safety, generality, determinism, isolation, evidence quality) and is not a count ranking or a "bigger model" recommendation.

Self-review against these criteria is in §17.

---

## 1. Repository / baseline identity

| Item | Value |
|---|---|
| Worktree | `C:\Users\cheta\Development\Uri\_V1` |
| Branch | `m35-uri-v1-parallel-architecture` |
| HEAD | `e8e3b65259c45fc823addc3ef8969425a265bd1b` |
| **Important:** tracked status of the subject code | `uri_v1/` (including `rar_deterministic.py`, `rar_contracts.py`, the corpus) and every `scripts/m35_*` file are **untracked** (`git status`: `?? uri_v1/`, `?? scripts/m35_a2_8h_detector_d1rq.py`, …). Git history therefore cannot attest to their content; identity is pinned below by SHA-256 instead. |
| Corpus `uri_v1/turn/rar_natural_boundary_raw_turn_fixtures.json` | `0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380` (matches A2.8H pre/post hashes) |
| `uri_v1/turn/rar_deterministic.py` | `e02af25bb7009d12d829c8b8fc92e487d3da75aeaa160092db617458278fb649` |
| `uri_v1/turn/rar_contracts.py` | `4cc9aa43726a870ca2e9ab1b19f6bf9d72dcb74c8a2818856776af95195b6819` |
| `scripts/m35_a2_8h_detector_d1rq.py` | `49f5faa9b37051fec876f5523383b4e965422976562c52e12fc38c970bfa6b82` |
| `scripts/m35_a2_8h_run.py` | `46d92285496ab3485cbd011c0768d4ad4f50d5675cb463b8f07157bba19c3c76` |
| `scripts/m35_a2_8f_detector_d1r.py` | `0347977372a3dfefa9d42780168b7724ce857eb8941696ec21e590fbff41be75` |
| `scripts/m35_a2_8d_detector_d1.py` | `a095ec7d4abc4588a0beb65168f6ca03b102316a9eec1e7495a4f5f9cc141ba3` |
| `scripts/m35_rar_natural_boundary_harness.py` | `6d666873e12f13a04403d956e65bfedf2b7394792244448a61038b7cb1f093b6` |
| `docs/plans/M35_URIV1_A2_8H_TELEMETRY.json` | `7b62aacbcedd7ae438892366953500957e87816c913ea5847e64e400a4b12a18` (unchanged by this audit) |

---

## 2. Evidence inspected

**Prior reports (read directly):** `docs/plans/M35_URIV1_A2_8H_EXECUTION_REPORT.md` (full), `M35_URIV1_A2_8G_DETECTION_TO_RAR_BOUNDARY_AUDIT.md` (full), `M35_URIV1_A2_8E_RESIDUAL_CHARACTERIZATION_REPORT.md` (§9–§14), `M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md` (§5, §11 — source of Known A/B), `M35_URIV1_PRE_RAR_CANDIDATE_ANCHOR_SOURCE_AUDIT.md` (§3–§12), `M35_URIV1_A2_8F_EXECUTION_REPORT.md`, `M35_URIV1_A2_8C_RESOLUTION_PATH_QUALIFICATION.md`, `M35_URIV1_A2_8_ADAPTIVE_INTELLIGENCE_ARCHITECTURE_PLAN.md`, `M35_URIV1_A2_9_NATIVE_PROBLEM_SOLVING_TRACE_REPORT.md`, `M35_URIV1_A2_5_RAR_BOUNDED_REFINEMENT_STAGE4_REPORT.md`, `M35_URIV1_A2_5_RAR_STAGE4B_REQUALIFICATION_AUDIT_REPORT.md`, `M35_URIV1_A2_8_TEST_RELEVANCE_AND_REGRESSION_MANIFEST.md` (headers/verdict sections of the last six).

**Raw telemetry (parsed field-by-field):** `docs/plans/M35_URIV1_A2_8H_TELEMETRY.json` (1,905 records), `M35_URIV1_A2_8F_TELEMETRY.json`, `M35_URIV1_A2_8D_TELEMETRY.json` (incorrect-binding identity cross-check). No A2.8H aggregates file exists (§15).

**Implementation source (read in full):** `scripts/m35_a2_8h_detector_d1rq.py`, `scripts/m35_a2_8h_run.py`, `scripts/m35_a2_8f_score.py`, `scripts/m35_rar_natural_boundary_harness.py`, `uri_v1/turn/rar_deterministic.py`, `uri_v1/turn/rar_contracts.py`. Read in part: `uri_v1/turn/turn_frame.py`, `turn_frame_builder.py` (ENTITY_PATTERNS, attachments), `active_context.py`, `lfm_semantic_decoder.py:306-360` (the one production RAR call site), `uri_core/core/turn_state.py` (`_project_active_pointer`, `assemble_turn_state`), `uri_core/core/graph_store.py`, `uri_core/core/graph_ingest.py`, `uri_core/core/graphify_index.py`, `uri_core/core/file_store.py` (`StoredFile.created_at`), `uri_core/core/drafting_memory.py`. D1R→D1RQ code diff computed mechanically (comments/docstrings stripped).

**Corpus:** full fixture file (79 cases, 42 library entries, `conversation_context.prior_turns`/`turn_attachments`, per-case `reason`).

**Tests executed (read-only):** `test_m35_uriv1_a2_5_deterministic_rar.py`, `test_m35_uriv1_a2_5_rar_adversarial_safety.py`, `test_m35_uriv1_a2_5_candidate_invention_fix.py` → **25 passed, 48 subtests passed**; `test_m35_uriv1_a2_5_rar_contracts.py`, `test_m35_uriv1_a2_5_rar_stage4_refinements.py` → **50 passed** (`-p no:cacheprovider`). RAR fixture suites evaluated in memory only (§15 for scoring caveat).

**Diagnostic scratchpad scripts (not in repository):** `rerun.py` (independent deterministic re-execution, D0/D1/D1R/D1RQ × C1/C2/C3), `probes.py` (counterfactual probes P1–P5, defined in §4), `unattr.py`, `detail.py`. They import the unmodified repository modules and write only to the scratchpad.

**Graphify:** `graphify query` failed — `graphify-out/graph.json` does not exist in this worktree (§15). Direct source reading was used instead.

---

## 3. Independent A2.8H verification

Method: (a) recomputed every figure from `M35_URIV1_A2_8H_TELEMETRY.json` using the A2.8F scorer's own denominator rule (ground-truth rows excluding `UNATTRIBUTED_DETECTOR_FIND` and `NO_REFERENCE`, n = 84); (b) independently re-executed D0/D1/D1R/D1RQ → RAR from source twice (1,008 reference rows each run) and compared `scoring_class`, span, outcome, candidate, rule and failure class row-by-row with the telemetry: **0 mismatches, both runs; corpus hash identical before/after.**

| # | A2.8H claim | Recomputed | Verdict |
|---|---|---|---|
| 1 | Detection recall 89.3% | 75/84 = 89.29% (C1, C2, C3 identical) | ✅ Confirmed |
| 2 | C1 resolution coverage 26.2% | 22/84 = 26.19% | ✅ Confirmed |
| 3 | C2 resolution coverage 15.5% | 13/84 = 15.48% | ✅ Confirmed |
| 4 | Target-eight: 6 correct | `NB-A-01`, `A-03`, `A-05`, `C-03`, `F-02`, `L-11:r2` → `CORRECT_RESOLUTION` at C1 | ✅ Confirmed |
| 5 | `NB-A-04` "reaches known identifier mismatch" | Reaches Level 6, `UNKNOWN/NO_CANDIDATE`. **Refined:** there is no identifier-system mismatch for this case — the candidate's `id` *is* the typed UUID. Probe: the bare UUID span resolves via `EXACT_ID` at **both C1 and C2**. The blocker is the span's `"file "` prefix (Q), exactly as A2.8G §5 and A2.8H §5 themselves state; the brief's "identifier mismatch" wording applies to A-01/A-03/A-05, not A-04. | ⚠️ Confirmed outcome, wording corrected |
| 6 | `NB-G-03` unchanged | Span `"Tom's extension number"` and `MISSED_RESOLVABLE_CASE` identical in D1R and D1RQ | ✅ Confirmed |
| 7 | Zero regressions | Paired D1R vs D1RQ by case:ref at C1, C2, C3: 0 regressions; changed rows are exactly the 6 (C1) / 4 (C2) gains | ✅ Confirmed |
| 8 | Zero new incorrect confident bindings | Count unchanged: 1 at C1, 1 at C2. **Identity correction:** the C2 incorrect binding is **`NB-B-05:r1`** (`"that in an email"` → email `obj-c06f97`, rule `TYPE_FILTER`), **not `NB-H-06`** (which is `CORRECT_ABSTENTION` at C2). A2.8H §4/§8 and A2.8G §1 both attribute the C2 binding to `NB-H-06`; the D1, D1R and D1RQ telemetry all show `NB-B-05:r1`. The count claim stands; the attribution was wrong in two prior reports and a second, distinct unsafe mechanism was therefore never characterized (§14). | ⚠️ Count confirmed, attribution **refuted** |
| 9 | Zero new false positives | K-category rows identical (7 `DETECTOR_FALSE_POSITIVE_SAFE_ABSTENTION`, 0 bindings); unattributed finds 58 = 58, but 8 unattributed span strings changed (shortened possessives). Caveat: unattributed finds are never sent to RAR by the runner, so their binding behaviour is unmeasured by the telemetry (§14, §15). | ✅ Confirmed (with caveat) |
| 10 | `INVENTED_CANDIDATE = 0` | 0 across 1,905 rows | ✅ |
| 11 | `BOUNDARY_VIOLATION = 0` | 0 across 1,905 rows | ✅ |
| 12 | Model calls = 0 | D1RQ imports only `re`, `dataclasses`, `typing`; RAR/contracts/harness import no model code. Note: the same A2.8H run executed the D2 (Needle) column with `d2_availability = "AVAILABLE"` — the "0" applies to the D1RQ path, not to the run. | ✅ Confirmed for the D1RQ path |
| 13 | Six new resolutions at Level 6, not Level 0 | All six `rule_used = TERM_DISCRIMINATION`; no `EXACT_ID`/`EXACT_ALIAS` anywhere in D1RQ telemetry | ✅ |
| 14 | Candidate-metadata tracking set unchanged | `NB-J-02`, `J-04`, `D-04`, `D-07`, `H-01`, `L-04:r1` identical D1R vs D1RQ | ✅ |
| 15 | Deterministic reproducibility | Independently re-executed twice: bit-identical to telemetry on all deterministic fields. A2.8H's own "two runs" cannot be checked (only one telemetry file persisted); substituted by independent re-execution. | ✅ (by substitution) |
| 16 | Corpus hash unchanged | `0ea54473…07380` pre/post (telemetry) and before/after this audit's re-runs | ✅ |
| 17 | D1RQ differs from D1R only by Q1/Q2 | Mechanical diff: Q1 (`"document"` → `None`, two sites), Q2 (stop-word lookahead, cap 3→2) **plus one undisclosed change: `re.IGNORECASE` added to `_POSSESSIVE_RE`.** Analysed as non-material (the character classes were already case-complete; the flag's only effects are case-insensitive stop-word matching and accepting `'S`; no corpus turn contains `'S`). | ⚠️ Minor undisclosed deviation, non-material |
| 18 | RAR invocation counts (C1) D0 31 / D1 63 / D1R 83 / D1RQ 83 | Recomputed 15 / 63 / 82 / 82 | ⚠️ Not reproduced (non-material to any verdict) |

**Material discrepancy resolution:** only item 8 is material (safety attribution). It does not change any A2.8H count, so the A2.8H qualification verdict stands, but the corrected identity is carried forward and `NB-B-05:r1` is analysed in §5/§14. Items 5, 17 and 18 are recorded corrections that do not affect the verdict.

---

## 4. Complete current residual population

**Definition.** A residual is a ground-truth-bearing reference (n = 84) whose D1RQ outcome is neither `CORRECT_RESOLUTION` nor `CORRECT_ABSTENTION`. `CORRECT_ABSTENTION_FAMILY_MISMATCH` (safe, but the wrong abstention family) is included as a low-severity residual.

| Condition | Correct resolution | Correct abstention | **Residual** | of which: missed-resolvable / silent miss / family mismatch / incorrect binding |
|---|---|---|---|---|
| C1 (authoritative) | 22 | 15 | **47** | 34 / 9 / 3 / 1 |
| C2 | 13 | 17 | **54** | 36 / 9 / 8 / 1 |

C1 is the authoritative population (clean pool; isolates pipeline behaviour from distractor ambiguity). C2 adds 8 residuals not present at C1 and removes one (`NB-H-06`, which is safe at C2); these are listed in §4.2.

**Probe legend** (diagnostic only, scratchpad; C1 unless stated): **P1** = ground-truth span + D1RQ's own signals, `recency_rank=0`; **P2** = the harness's existing oracle query `s2_query_for_reference` (GT span, GT type, GT temporal meaning, GT per-reference exclusions), `recency_rank=0`; **P3** = P2 with real `created_at`-derived ranks (`build_candidate_pool(oracle_recency=True)`); **P4** = D1RQ's actual query with real ranks; **P5** = D1RQ query plus `RARDeterministicAnchor(current_attachment_id=…)` when exactly one turn attachment exists. Abbreviations: CR correct resolution, CA correct abstention, MRC missed resolvable, SDM silent detection miss, CAFM family mismatch, ICB incorrect confident binding.

### 4.1 C1 residual population (47)

"Relevant context" beyond the pool is given in §5's justification column (prior turns, attachments, exclusions) to keep this table readable.

| # | Case:ref | Cat | User expression (GT span) | GT referent (GT type) | Det? | D1RQ span / mechanism | Query signals rec/type/neg | C1 pool (n; types) | RAR rule reached -> outcome/failure | C1 | C2 | Probes P1/P2/P3/P4 (C1) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | NB-A-04:r1 | A | `file 38e1b5c4-a97d-4f26-b0e8-12c6d3f9d115` | scan_0034.pdf (pdf) | Yes | `file 38e1b5c4-a97d-4f26-b0e8-12c6d3f9d115` / code_id_shape | - / - / - | 1; pdf | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/MRC/MRC |
| 2 | NB-B-01:r1 | B | `it` | Reference letter for Amara Okafor (letter) | Yes | `it` / bare_pronoun | - / - / - | 1; letter | TERM_DISCRIMINATION -> UNKNOWN/PRONOUN_BINDING | MRC | MRC | MRC/CR/CR/MRC |
| 3 | NB-B-02:r1 | B | `it` | Lease_Agreement_Harbour_St.pdf (None) | Yes | `it` / bare_pronoun | - / - / - | 2; pdf,tool_result | TERM_DISCRIMINATION -> AMBIGUOUS/PRONOUN_BINDING | MRC | MRC | MRC/MRC/MRC/MRC |
| 4 | NB-B-03:r1 | B | (no surface) implicit: the October agenda draft just produced | Agenda - October board meeting (draft) (document) | No | - | - | 1; document | not invoked | SDM | SDM | MRC/CR/CR/n/a |
| 5 | NB-B-04:r1 | B | `that` | Annual leave request - Tom Becker, 14-18 Oct (approval) | Yes | `that` / bare_pronoun | - / - / - | 1; approval | TERM_DISCRIMINATION -> UNKNOWN/PRONOUN_BINDING | MRC | MRC | MRC/CR/CR/MRC |
| 6 | NB-B-05:r1 | B | `that` | Summary of Q3 budget forecast (report) | Yes | `that in an email` / determiner_noun_phrase | - / email / - | 2; record,report | TYPE_FILTER -> UNKNOWN/NO_CANDIDATE | MRC | **ICB** | MRC/CR/CR/MRC |
| 7 | NB-B-05:r2 | B | `Priya` | Contact: Priya Nair - HR (record) | No | - | - | 2; record,report | not invoked | SDM | SDM | CR/CR/CR/n/a |
| 8 | NB-C-02:r1 | C | `this` | IMG_20260924_1402.jpg (image) | Yes | `this as a travel expense` / determiner_noun_phrase | - / - / - | 1; image | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/CR/CR/MRC (P5: CR) |
| 9 | NB-C-07:r1 | C | `the file I sent you first thing this morning` | CV_Amara_Okafor.pdf; CV_Daniel_Reyes.pdf (None) | Yes | `the file I sent you first thing this morning` / determiner_noun_phrase | - / document / - | 3; pdf,spreadsheet | TYPE_FILTER -> UNKNOWN/NO_CANDIDATE | CAFM | CAFM | CAFM/CAFM/CA/CAFM |
| 10 | NB-D-01:r1 | D | `the latest board minutes` | Board_minutes_Sep.docx (document) | Yes | `the latest board minutes` / determiner_noun_phrase | latest / - / - | 2; document | TEMPORAL_RELATION -> AMBIGUOUS/INSUFFICIENT_METADATA | MRC | MRC | MRC/MRC/CR/CR |
| 11 | NB-D-02:r1 | D | `the one before that` | Board_minutes_Aug.docx (document) | Yes | `the one before` / determiner_noun_phrase | previous / - / - | 2; document | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/CR/CR |
| 12 | NB-D-03:r1 | D | `the budget forecast` | Q2_budget_forecast.xlsx (spreadsheet) | Yes | `the budget forecast look like last quarter` / determiner_noun_phrase | - / - / - | 2; spreadsheet | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/CR/MRC |
| 13 | NB-D-04:r1 | D | `the earlier agenda, the one we used before the September meeting` | Agenda - September board meeting (document) | Yes | `the earlier agenda` / determiner_noun_phrase | earlier / - / - | 2; document | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/CR/CR |
| 14 | NB-D-05:r1 | D | `the older version of the Harbour Street lease` | Lease_Agreement_Harbour_St.pdf (None) | Yes | `the older version` / determiner_noun_phrase | - / - / - | 2; pdf | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | CAFM | MRC/MRC/CR/MRC |
| 15 | NB-D-06:r1 | D | `the last thing you did for me` | Search: overdue invoices (3 found) (None) | Yes | `the last thing you did` / determiner_noun_phrase | - / - / - | 2; action,tool_result | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/CR/MRC |
| 16 | NB-D-07:r1 | D | `the invoice before the latest one` | invoice_INV-20388.pdf (pdf) | Yes | `the invoice before the latest one` / determiner_noun_phrase | latest / - / - | 2; pdf | TEMPORAL_RELATION -> AMBIGUOUS/INSUFFICIENT_METADATA | MRC | MRC | MRC/MRC/CR/**ICB** |
| 17 | NB-E-04:r1 | E | `the Word doc` | Lease_Agreement_Harbour_St_v2_draft.docx (document) | Yes | `the Word doc` / determiner_noun_phrase | - / - / - | 3; document,pdf | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | CAFM | MRC/MRC/MRC/MRC |
| 18 | NB-E-05:r1 | E | `the vendor record for the courier company` | Vendor: Brightline Couriers Ltd (record) | Yes | `the vendor record` / determiner_noun_phrase | - / record / - | 2; record | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/MRC/MRC |
| 19 | NB-E-06:r1 | E | `the site photos` | site_photo_01.jpg; site_photo_02.jpg (image) | Yes | `the site photos` / determiner_noun_phrase | - / image / - | 2; image | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/MRC/MRC |
| 20 | NB-F-03:r1 | F | `the harbour street lease` | Lease_Agreement_Harbour_St_v2_draft.docx (None) | Yes | `the harbour street lease` / determiner_noun_phrase | - / - / - | 2; document,spreadsheet | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | CAFM | MRC/MRC/MRC/MRC |
| 21 | NB-F-06:r1 | F | `the paperwork for the place we're renting` | Lease_Agreement_Harbour_St.pdf (None) | Yes | `the paperwork` / determiner_noun_phrase | - / - / - | 3; csv,pdf,spreadsheet | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | CAFM | MRC/MRC/MRC/MRC |
| 22 | NB-G-01:r1 | G | `she` | Employee: Lena Fischer (record) | Yes | `she` / bare_pronoun | - / - / - | 1; record | TERM_DISCRIMINATION -> UNKNOWN/PRONOUN_BINDING | MRC | MRC | MRC/CR/CR/MRC |
| 23 | NB-G-02:r1 | G | `Marcus, the solicitor` | Contact: Marcus Hale - Hale & Partners Solicitors (record) | Yes | `the solicitor` / determiner_noun_phrase | - / - / - | 1; record | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/CR/CR/MRC |
| 24 | NB-G-03:r1 | G | `Tom's` | Employee: Tom Becker (record) | Yes | `Tom's extension number` / possessive_np | - / - / - | 1; record | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | CR/CR/CR/MRC |
| 25 | NB-G-04:r1 | G | `Marcus Hale` | Contact: Marcus Hale - Northwind Supplies (accounts); Contact: Marcus Hale - Hale & Partners Solicitors (record) — AMBIGUOUS expected | No | - | - | 3; pdf,record | not invoked | SDM | SDM | CA/CA/CA/n/a (P1 at C2: **ICB**) |
| 26 | NB-G-06:r1 | G | `the new hire's offer` | Offer letter - Daniel Reyes (letter) | Yes | `the new hire's offer` / determiner_noun_phrase | - / - / - | 2; letter | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/MRC/MRC |
| 27 | NB-H-01:r1 | H | `the draft we were editing earlier` | Lease_Agreement_Harbour_St_v2_draft.docx (document) | Yes | `the draft we were editing earlier` / determiner_noun_phrase | earlier / - / - | 2; document,pdf | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/CR/CR/CR |
| 28 | NB-H-02:r1 | H | `either of the CVs except Amara's` | CV_Daniel_Reyes.pdf (pdf) | No | - | - | 2; pdf | not invoked | SDM | SDM | MRC/MRC/MRC/n/a |
| 29 | NB-H-03:r1 | H | `the board minutes` | Board_minutes_Sep.docx (document) | Yes | `the board minutes` / determiner_noun_phrase | - / - / - | 2; document | TERM_DISCRIMINATION -> AMBIGUOUS/MULTIPLE_PLAUSIBLE | MRC | MRC | MRC/MRC/MRC/MRC |
| 30 | NB-H-04:r1 | H | `the actual spreadsheet` | Q3_budget_forecast.xlsx (spreadsheet) | Yes | `the actual spreadsheet` / determiner_noun_phrase | - / spreadsheet / no,not | 2; report,spreadsheet | TYPE_FILTER -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/MRC/MRC |
| 31 | NB-H-05:r1 | H | `the proper one from the insurers` | insurance_certificate_2026.pdf (pdf) | Yes | `the proper one` / determiner_noun_phrase | - / - / not | 2; pdf | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/MRC/MRC |
| 32 | NB-H-06:r1 | H | `the other scan, the one from last week` | (none — UNKNOWN expected) (pdf) | Yes | `the other scan` / determiner_noun_phrase | earlier / - / no,the other | 1; pdf | CONTRAST_FILTER -> RESOLVED | **ICB** | CA | **ICB**/**ICB**/**ICB**/**ICB** |
| 33 | NB-I-02:r2 | I | `Priya` | Contact: Priya Nair - HR (record) | No | - | - | 3; letter,record,report | not invoked | SDM | SDM | CR/CR/CR/n/a (P1 at C2: **ICB**) |
| 34 | NB-I-04:r1 | I | `the invoice` | invoice_INV-20417.pdf; invoice_INV-20388.pdf — AMBIGUOUS expected | Yes | `the invoice please` / determiner_noun_phrase | - / - / - | 2; pdf | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | CAFM | CAFM | CA/CA/CA/CAFM |
| 35 | NB-I-06:r2 | I | `Priya` | Contact: Priya Nair - HR (record) | No | - | - | 4; letter,record | not invoked | SDM | SDM | CR/CR/CR/n/a (P1 at C2: **ICB**) |
| 36 | NB-I-07:r1 | I | `the money one` | Q3_budget_forecast.xlsx (None) | Yes | `the money one` / determiner_noun_phrase | - / - / - | 2; spreadsheet | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | CAFM | MRC/MRC/MRC/MRC |
| 37 | NB-J-01:r1 | J | `his reply` | (none — UNKNOWN expected) (email) | Yes | `his reply` / determiner_noun_phrase | - / - / - | 2; record | TERM_DISCRIMINATION -> AMBIGUOUS/PRONOUN_BINDING | CAFM | CAFM | CAFM/CA/CA/CAFM |
| 38 | NB-L-01:r2 | L | `Marcus at Northwind` | Contact: Marcus Hale - Northwind Supplies (accounts) (record) | No | - | - | 3; record,spreadsheet | not invoked | SDM | SDM | CR/CR/CR/n/a |
| 39 | NB-L-02:r1 | L | `that list` | Search: overdue invoices (3 found) (tool_result) | Yes | `that list` / determiner_noun_phrase | - / - / - | 2; record,tool_result | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/MRC/MRC |
| 40 | NB-L-02:r2 | L | `Marcus` | Contact: Marcus Hale - Northwind Supplies (accounts) (record) | No | - | - | 2; record,tool_result | not invoked | SDM | SDM | CR/CR/CR/n/a |
| 41 | NB-L-04:r1 | L | `my most recent letter` | Offer letter - Daniel Reyes (letter) | Yes | `my most recent letter` / determiner_noun_phrase | latest / - / - | 5; letter,record | TEMPORAL_RELATION -> AMBIGUOUS/INSUFFICIENT_METADATA | MRC | MRC | MRC/MRC/CR/CR |
| 42 | NB-L-04:r2 | L | `Priya` | Contact: Priya Nair - HR (record) | No | - | - | 5; letter,record | not invoked | SDM | SDM | CR/CR/CR/n/a |
| 43 | NB-L-06:r1 | L | `the latest invoice` | invoice_INV-20417.pdf (pdf) | Yes | `the latest invoice` / determiner_noun_phrase | latest / - / - | 2; pdf | TEMPORAL_RELATION -> AMBIGUOUS/INSUFFICIENT_METADATA | MRC | MRC | MRC/MRC/CR/CR |
| 44 | NB-L-07:r1 | L | `that one` | Annual leave request - Lena Fischer, 21-25 Oct (approval) | Yes | `that` / bare_pronoun | - / - / - | 2; approval | TERM_DISCRIMINATION -> AMBIGUOUS/PRONOUN_BINDING | MRC | MRC | MRC/MRC/MRC/MRC |
| 45 | NB-L-08:r3 | L | `my reply to Priya` | Re: Onboarding dates (email) | Yes | `my reply` / determiner_noun_phrase | - / - / - | 3; email,pdf | TERM_DISCRIMINATION -> AMBIGUOUS/PRONOUN_BINDING | MRC | MRC | CR/CR/CR/MRC |
| 46 | NB-L-09:r1 | L | `this month's roster` | staff_roster_october.xlsx (spreadsheet) | Yes | `this month's roster` / determiner_noun_phrase | previous / - / - | 1; spreadsheet | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/CR/CR/MRC |
| 47 | NB-L-11:r1 | L | `both CVs` | CV_Amara_Okafor.pdf; CV_Daniel_Reyes.pdf (pdf, plural) | Yes | `both CVs` / determiner_noun_phrase | - / - / - | 3; letter,pdf | TERM_DISCRIMINATION -> UNKNOWN/NO_CANDIDATE | MRC | MRC | MRC/MRC/MRC/MRC |

Candidate metadata common to every row (from `build_candidate_pool`): `id`, `title` (filename or synthetic title), `candidate_type` (benchmark `object_type`), `domain_tags` (synthetic `origin`/`status`/`direction`/`counterparty` values flattened), `is_attachment` (= "is file-shaped", §8), `recency_rank = 0` always, `exact_aliases = ()`, `owner = None`, `description = None`.

### 4.2 C2 population delta

Residual at C2 but correct at C1 (8): `NB-A-01:r1` (AMBIGUOUS: invoice PDF vs email "Query on invoice INV-20417"), `NB-C-03:r1` (CV vs interview calendar event, both "Daniel"), `NB-E-01:r1` ("the spreadsheet" — roster vs Q3 budget; corpus: "employee IDs" points to the roster by meaning), `NB-E-03:r1` ("the email [from Priya]" — received vs draft-outgoing, both counterparty Priya), `NB-F-05:r1` ("the roster" — file vs action record "Sent staff_roster_october.xlsx…"), `NB-L-03:r1` (attached-this-turn spreadsheet vs an older non-attached one), `NB-L-05:r1` ("approve the leave request" — pending vs already-approved), `NB-L-10:r1` (Q3 forecast file vs Summary-of-Q3 report; corpus `reason` says the summary is an acceptable source). All eight land in safe `AMBIGUOUS`. Correct at C2 but residual at C1: `NB-H-06:r1`. **Unsafe at C2: `NB-B-05:r1` (ICB).**

---

## 5. Earliest-failure taxonomy

Categories as specified: **D** detection, **Q** query/evidence construction, **C** candidate construction, **R** RAR behaviour, **A** appropriate abstention, **S** session/discourse state, **E** evidence-contract gap, **H** harness/ground truth. Two evidence-required new classes: **X1 — disconnected anchor/state source** (the information exists in URI *and* the contract already has a slot for it, but no producer populates it; distinct from E, where the contract has no slot, and from Q, where the detector mis-shapes what it does see); **N — missing semantic capability** (correct interpretation needs world/lexical-semantic knowledge not represented anywhere in URI).

"Primary" = the earliest point after which correct resolution is impossible on the current path. "Then" = what would still block after the primary owner were fixed (from probes P1–P5 or code trace).

| # | Case:ref | Primary | Then | Justification (mechanism; probe evidence) |
|---|---|---|---|---|
| 1 | NB-A-04:r1 | **Q** | — | Span keeps intro word `"file "`, so Level 0's `ref_norm == c.id` can never match. Bare UUID → `EXACT_ID` at C1 and C2 (probe). Identifier systems coincide here. |
| 2 | NB-B-01:r1 | **S** | — | Bare "it" with the antecedent only in the prior URI turn (draft letter). RAR's no-anchor pronoun rule abstains by design. P2 resolves at C1 only because the oracle hands `type=letter` to a singleton pool; fails at C2 (Amara's CV shares the name). |
| 3 | NB-B-02:r1 | **S** | H (minor) | "it" after a tool action; antecedent in prior turn. P2/P3 still AMBIGUOUS. The corpus lists the tool result as an acceptable alternative that the scorer does not credit. |
| 4 | NB-B-03:r1 | **S** | — | T8, zero surface. Nothing to detect; requires "last produced object" state. |
| 5 | NB-B-04:r1 | **S** | — | "undo that" → the object of the previous action (prior turn). Same pattern as #2. |
| 6 | NB-B-05:r1 | **Q** | S | NP scanner crosses `in` (not in `_NP_STOP_WORDS`) → span `"that in an email"`; the object-to-be-created noun `email` becomes `target_type_hint`. C1: L4b rejects (safe). **C2: L4b finds exactly one email and binds with zero substantive evidence → ICB.** With the correct span `that`, the case still needs discourse state (S). |
| 7 | NB-B-05:r2 | **D** | — | T2 bare name. P1 resolves at C1 and C2. |
| 8 | NB-C-02:r1 | **X1** | Q (span `this as a travel expense`) | The only identifying fact is that the image is attached to this turn (`turn_attachments`, `TurnFrame.attachments`, uri_core `current_turn_attachments`). `RARDeterministicAnchor.current_attachment_id` exists but is never constructed. P5 (anchor supplied) → CR at C1 and C2. |
| 9 | NB-C-07:r1 | **Q** | C | "file" → `document` type hint (general vocabulary) mismatches `pdf`; L4b UNKNOWN instead of AMBIGUOUS. "first thing this morning" not in recency lexicon. P3 (oracle temporal + real ranks) → CA. Safe. |
| 10 | NB-D-01:r1 | **C** | R (Known A, latent) | `recency_hint=latest` correct; every `recency_rank=0` → `INSUFFICIENT_METADATA`. P4 → CR at C1 **but ICB at C2** (Level 5 binds the newer agenda before Level 6 checks "minutes"). |
| 11 | NB-D-02:r1 | **C** | S; R (Known A, D) | `previous` supplied; no rank 1 exists → falls to L6 where `before` is an unmatched "entity" token. P4 → CR at C1, **ICB at C2**. Correct semantics are "one before the last discussed" (S). |
| 12 | NB-D-03:r1 | **Q** | N | NP over-capture across verb (`…look like last quarter`). Even the GT span is AMBIGUOUS; P3 resolves at C1 only through an "earlier" approximation; the corpus requires calendar reasoning ("last quarter" in September → Q2). P3 fails at C2. |
| 13 | NB-D-04:r1 | **C** | R (Known D) | `earlier` supplied; no ranks → L6, where `earlier` is treated as an unmatched entity token. P4 → CR at C1, safe AMBIGUOUS at C2. |
| 14 | NB-D-05:r1 | **Q** | C | `older` is not in the recency lexicon; span truncated at `of`. P3 (hint + ranks) → CR. |
| 15 | NB-D-06:r1 | **Q** | C | `last` (alone) not in the recency lexicon. P3 → CR at C1 and C2. "things you did" ↔ `origin=uri_action` exists only as a flattened tag. |
| 16 | NB-D-07:r1 | **Q** | C | The recency lexicon matches `latest` inside "the invoice **before** the latest one" (first-match precedence; no compositional ordinal). Masked today by missing ranks; **P4 → ICB at C1 and C2**; P3 (correct `previous`) → CR. |
| 17 | NB-E-04:r1 | **Q** | R (Known D); vocabulary absent | "Word doc" not mapped to a type/format; even with the GT type (P2) L4b rejects because `word`/`doc` are unmatched. `media_type` exists in the file reference but is not mapped into `RARCandidate`. |
| 18 | NB-E-05:r1 | **R** | R (Known C) | The type word `record` is not in `GENERIC_TYPE_WORDS`, so L6 counts it as an unmatched entity token; `courier` ≠ `Couriers` (no stemming). `vendor` alone discriminates uniquely. |
| 19 | NB-E-06:r1 | **R** | E | `photos` ≠ `photo` (Known C). Plural intended set: `RESOLVED` can hold one candidate only. |
| 20 | NB-F-03:r1 | **R** | — | Known D: `street` vs `St`; `harbour` + `lease` match uniquely. |
| 21 | NB-F-06:r1 | **N** | — | Paraphrase ("paperwork for the place we're renting" → lease). No lexical overlap anywhere; world knowledge. Safe abstention. |
| 22 | NB-G-01:r1 | **S** | (A-reading) | "she" = person named in the prior turn. A2.8G classed this A/R; the corpus supplies the antecedent in `prior_turns`, so the missing input is discourse state. The A reading (RAR should never bind an anchorless pronoun) stays valid as policy. P2 resolves only in the singleton C1 pool. |
| 23 | NB-G-02:r1 | **R** | D (partial: "Marcus," not captured) | `solicitor` ≠ `Solicitors` (Known C). P2 (GT type) resolves because L4b's singleton check needs only *one* matching token (`marcus`). |
| 24 | NB-G-03:r1 | **R** | — | **Reclassified from Q (A2.8G/A2.8H).** The span faithfully contains the user's words; `extension number` names an attribute being asked about, not the referent. L6's all-or-nothing absent-entity check (Known D) rejects although `tom` matches uniquely. A2.8H itself showed no general surface rule can remove the tokens. With partial credit: C1 would resolve; C2 would be safe AMBIGUOUS (record vs leave request). |
| 25 | NB-G-04:r1 | **D** | **R/C latent unsafe** | T2. P1 → correct AMBIGUOUS at C1 but **ICB at C2** (the email whose `counterparty` tag is "Marcus Hale (Northwind Supplies)" out-scores both contact records through the tag bonus). |
| 26 | NB-G-06:r1 | **R** | N | Known D: `new`/`hire` unmatched though `offer` matches uniquely. Full semantics ("new hire" = Daniel) is N. |
| 27 | NB-H-01:r1 | **Q** | C | Exclusion "Not the signed lease" sits in a sibling clause (split on ` - `), so the reference gets empty `negation_spans`; `editing` is an unmatched entity token. P2 (scoped exclusion) → CR via CONTRAST_FILTER. |
| 28 | NB-H-02:r1 | **D** | R (Known C/D) | T5-compound undetected. With the full GT query (P2), L4a correctly eliminates Amara's CV, but L4b's singleton check rejects Daniel's CV because `either`/`cvs`/`except`/`amara` don't match it. |
| 29 | NB-H-03:r1 | **Q** | R (abbreviation) | Exclusion "leave out the August ones" is in a sibling clause (`, but`) and `leave out` is not a negation cue. Even when scoped (P2), L4a cannot eliminate `Board_minutes_Aug` because `august` ≠ `aug`. Safe AMBIGUOUS. |
| 30 | NB-H-04:r1 | **R** | Q | L4b singleton check: the only non-type token `actual` is unmatched → UNKNOWN (modifier treated as entity, Known D variant). Negation passes only cue words (`no`,`not`), never the excluded phrase "the summary" (Q), but type filtering alone would suffice. |
| 31 | NB-H-05:r1 | **Q** | R (Known C/D), S | Span truncated at `from` loses `insurers`, the only discriminating word; with the full GT span `insurers` ≠ `insurance` and `proper` unmatched. "not that one" is a relational exclusion of the prior-turn antecedent (Known B/S). |
| 32 | NB-H-06:r1 | **R** | S | **Known B.** "the other scan" + negation: L4a eliminates nothing (no lexical overlap); the contrast shortcut then **binds the only remaining candidate** — which is exactly the excluded one. Identical under P1–P4. Unsafe at C1. |
| 33 | NB-I-02:r2 | **D** | **R/C latent unsafe** | T2. P1 → CR at C1, **ICB at C2** (email "Onboarding dates", counterparty Priya, scores 2.0 vs contact 1.0). |
| 34 | NB-I-04:r1 | **Q** | — | Politeness marker `please` captured into the span becomes an unmatched token → UNKNOWN instead of AMBIGUOUS. P1 → CA. Safe. |
| 35 | NB-I-06:r2 | **D** | **R/C latent unsafe** | T2. P1 → CR at C1, **ICB at C2** (draft email "Re: Onboarding dates"). |
| 36 | NB-I-07:r1 | **N** | — | Topic knowledge ("money" → budget). Safe. |
| 37 | NB-J-01:r1 | **Q** | R (STOPWORDS) | `reply` → email not mapped; also `reply` is in RAR's verb STOPWORDS. P2 (GT type email) → correct UNKNOWN. Safe family mismatch. |
| 38 | NB-L-01:r2 | **D** | — | T2. P1 → CR at C1 and C2. |
| 39 | NB-L-02:r1 | **S** | R (Known D) | "that list" = tool result just shown (prior turn). `list` is unmatched against "Search: overdue invoices (3 found)" even with the GT type. |
| 40 | NB-L-02:r2 | **D** | S at C2 | T2. P1 → CR at C1; safe AMBIGUOUS at C2 (needs conversation topic "Northwind"). |
| 41 | NB-L-04:r1 | **C** | — | `latest` supplied; ranks missing. P4 → CR at C1 and C2. |
| 42 | NB-L-04:r2 | **D** | — | T2. P1 → CR at C1; safe AMBIGUOUS at C2. |
| 43 | NB-L-06:r1 | **C** | R (Known A, latent) | `latest` supplied; ranks missing. P4 → CR at C1, **ICB at C2** (the newer email about the invoice wins Level 5 across the whole pool). |
| 44 | NB-L-07:r1 | **S** | N | "Open that one" corefers with the answer to the same turn's question ("which leave request hasn't been signed off"); mapping "hasn't been signed off" → `status=pending` is semantic. The status value exists as a flattened tag. |
| 45 | NB-L-08:r3 | **Q** | E at C2 | **Reclassified from X (A2.8G).** Span stops at `to`; the GT span resolves at C1 (P1, P2) because `counterparty: Priya Nair` does reach RAR as a `domain_tag`. At C2, received and draft emails share the counterparty; only `direction` separates them, and it survives only as an untyped tag while `reply` is a STOPWORD (E). |
| 46 | NB-L-09:r1 | **R** | Q | L6 all-or-nothing: `month` unmatched, `roster` matches uniquely. (L4b's singleton check is "any token matches", which is why P2 resolves.) Also the clause-level recency `previous` belongs to the sibling reference r2 ("before it") and leaks onto r1 (Q, harmless today). |
| 47 | NB-L-11:r1 | **R** | E | Known C (`cvs` ≠ `cv`); plural `RESOLVED` not representable. |

**Primary-owner tally, C1 (sums to 47):**

| Owner | Count | Cases |
|---|---|---|
| **Q** query/evidence construction | **14** | A-04, B-05:r1, C-07, D-03, D-05, D-06, D-07, E-04, H-01, H-03, H-05, I-04, J-01, L-08:r3 |
| **R** RAR behaviour | **10** | E-05, E-06, F-03, G-02, G-03, G-06, H-04, H-06, L-09:r1, L-11:r1 |
| **D** detection | **8** | T2 ×7 (B-05:r2, G-04:r1, I-02:r2, I-06:r2, L-01:r2, L-02:r2, L-04:r2), T5-compound ×1 (H-02) |
| **S** session/discourse state | **7** | B-01, B-02, B-03 (T8), B-04, G-01, L-02:r1, L-07 |
| **C** candidate construction | **5** | D-01, D-02, D-04, L-04:r1, L-06 |
| **N** missing semantic capability (new) | **2** | F-06, I-07 |
| **X1** disconnected anchor source (new) | **1** | C-02 |
| **A** appropriate abstention | 0 | (all appropriate abstentions already count as correct; `NB-G-01` retains an A reading) |
| **E** evidence-contract gap | 0 primary | secondary in E-06, L-11:r1 (plural), L-08:r3 at C2 (direction), exclusion role (§9) |
| **H** harness/ground truth | 0 primary | secondary in B-02 (acceptable alternative not credited); primary for C2 `NB-L-10:r1` |
| **Total** | **47** | |

**C2-only residuals (8):** Q ×2 (A-01: the head noun "invoice" signals the document rather than the email about it, but the pruned type vocabulary drops that; C-03: the discriminating context "job spec" is in the clause, not the trimmed span); N ×2 (E-01 "employee IDs" → roster; L-05 "approve" implies `pending`); E ×2 (E-03 direction "from Priya"; F-05 object vs action-record-about-object); X1 ×1 (L-03: "attached this turn" not represented per candidate); H ×1 (L-10:r1: AMBIGUOUS between two answers the corpus deems acceptable).

**Reclassifications vs A2.8G/A2.8H (auditable correction history):** `NB-G-03` Q→R; `NB-L-08:r3` X→Q (at C1), with the E-component confirmed only at C2; `NB-G-01` A/R→S (A reading retained). Reasons are in rows 22, 24 and 45 above.

---

## 6. The nine undetected references, re-evaluated

The set is unchanged since A2.8F (verified: exactly these 9 are `SILENT_DETECTION_MISS` under D1RQ at C1/C2/C3).

### 6.1 T2 — bare proper names (7: B-05:r2, G-04:r1, I-02:r2, I-06:r2, L-01:r2, L-02:r2, L-04:r2)

- **If detected with a perfect span (P1), current downstream behaviour is:** C1 → 6 CR + 1 correct AMBIGUOUS (all 7 correct); C2 → 2 CR (B-05:r2, L-01:r2), 2 safe AMBIGUOUS (L-02:r2, L-04:r2), **3 incorrect confident bindings (G-04:r1, I-02:r2, I-06:r2)**.
- **Why the bindings are unsafe:** the harness flattens synthetic `counterparty` into `domain_tags`, and RAR Level 6 adds +1 to a candidate whose tags contain a query token. A name therefore scores higher on an *email whose counterparty is that person* than on the person's own contact record (Priya: email 2.0 vs contact 1.0; "Marcus Hale": email 4.0 vs each contact 2.0). This is a RAR scoring property combined with a candidate-construction flattening, not a detection property. It is newly identified here.
- **False-trigger risk of detecting every bare capitalized name:** a diagnostic scan of all 79 turns found 31 non-sentence-initial capitalized words. Five fall in reference-free roles: `Marcus` in NB-J-01 (resolution "not needed and ambiguous"), `Marcus` in NB-L-06 (inside a negated sentence; the oracle deliberately lists no reference), `August` inside an exclusion (NB-H-03), and `Friday` ×2 in K-category turns (NB-K-03, NB-K-07). On this corpus the trigger-level false-positive burden is small. The binding-level risk above is the dominant hazard.
- **Existing gating information in URI:** (i) candidate `candidate_type` (`record` for people) exists and Level 4b could narrow on it, but a detector asserting "person/record" from a bare capitalized token would be an unsupported type guess — the same defect class Q1 just removed. (ii) uri_core `GraphStore` (`uri_core/core/graph_store.py`) stores typed entities per user, but its own docstring states that entity resolution and fuzzy matching are "explicitly future work" (exact-key dedupe only). No path connects it to `uri_v1`. (iii) `TurnFrame.entity_surface_mentions` exists, but `ENTITY_PATTERNS` contains two hard-coded phrases (`Chief Warden`, `committee`), not a mechanism.
- **Deterministic contextual gating possible?** Trigger gating (capitalized token after `to`/`send`/`at`, not sentence-initial, not a weekday/month) looks deterministic and would cover all 7 on this corpus. That was not built or measured for precision (§15). It would **not** address the binding hazard, which sits downstream.
- **Where it belongs:** detection is necessary but not sufficient. Safe T2 needs downstream entity-type awareness — "a person reference prefers person records over objects associated with the person" — in RAR scoring or candidate construction. **T2 detection should not be enabled before the downstream counterparty-tag hazard is qualified.**

### 6.2 T5-compound — `NB-H-02` ("Use either of the CVs except Amara's as the example")

The missing semantic operation is **set construction followed by relational subtraction bound to one reference**: "either of {CVs}" defines a candidate set (a choice-of-any quantifier over a type-restricted plural), "except Amara's" subtracts a possessor-identified member, and the result is a single referent. The pieces exist separately: D1RQ's quantifier determiners exclude `either` on purpose; the possessive mechanism fires on `Amara's` as a separate span, which then **binds confidently to the excluded CV** if sent to RAR (§14); L4a's lexical elimination works when given the exclusion (P2 eliminates Amara's CV). What is missing is (a) a detector output that ties the exclusion to the reference as a *role* (excluded member) rather than an independent reference, and (b) a RAR result check tolerant of the quantifier/plural tokens (P2 still fails in L4b on `either`/`cvs`/`except`). (a) is an evidence-contract gap (no reference-role field); (b) is Known C/D.

### 6.3 T8 — `NB-B-03` ("Swap 3 and 4 round, and AOB should be the very last item")

Required state: a **session "last produced/last discussed object" pointer** — the ID of the artifact URI produced in the immediately preceding turn — plus the edit-operation cue that makes an imperative with no referring words apply to it. **Correction to A2.8E §12:** A2.8E listed `uri_core.TurnState.active_pointer` as an existing, disconnected source for T8. Reading `uri_core/core/turn_state.py::_project_active_pointer` directly shows it projects a *paused workflow / pending clarification* (`kind: paused_workflow | awaiting_clarification_answer | none`), not a last-produced artifact. A bounded grep of uri_core (`last_draft|last_artifact|active_artifact|last_output|last_produced|recent_artifact|current_draft`) found no produced-artifact pointer. The closest existing sources are `ConversationHistoryStore` text (durable, disconnected; per the pre-RAR audit) and `CapabilityContextResolver`'s per-capability last result (live, disconnected, capability-keyed; per the pre-RAR audit, not re-read here). The corpus itself carries the antecedent only as prior-turn *text*. **Classification: S — the specific state needed is not represented anywhere found; related state exists but is disconnected and differently shaped.**

---

## 7. Consolidated RAR limitation inventory

| ID | Limitation (code location) | Current residuals affected (C1 unless noted) | Status on current path |
|---|---|---|---|
| **Known A** | Level 5 temporal selection commits before Level 6 lexical/absent-entity validation (`rar_deterministic.py:567-692`); ranks are not rebased after 4b narrowing (L-09:r2 variant) | None fire today, because every `recency_rank = 0` → safe `INSUFFICIENT_METADATA`. **Latent (P4, real ranks):** J-02, J-04, D-07 at C1; D-01, D-02, D-07, L-06, L-09:r2 at C2 → incorrect bindings | **Masked, not resolved.** Still affects the path the moment recency is wired. |
| **Known B** | L4a elimination is lexical-overlap only; the contrast shortcut (`:486-496`) then binds the sole survivor even when *nothing was eliminated* | H-06 (ICB, C1); H-05 ("not that one", secondary) | **Active, unsafe.** |
| **Known C** | No plural/stemming/derivational normalization in `clean_tokens` (`:91-98`) | L-11:r1 (cvs), E-06 (photos), E-05 (Couriers), G-02 (Solicitors), H-05 (insurers/insurance), H-02 (secondary) | Active, safe (abstains) |
| **Known D** | L6 absent-entity check is all-or-nothing (`:786-795`), while L4b's singleton check is "any token matches" (`:539`) — **inconsistent evidence rules between levels**; type words not in `GENERIC_TYPE_WORDS` (`record`, `letter`, `report`, `approval`, `tool_result`…) and temporal/modifier words (`earlier`, `before`, `actual`, `proper`) count as entity tokens | F-03, G-03, G-06, L-09:r1, E-05, H-04 primary; E-04, H-05, H-02, D-02, D-04, H-01, L-02:r1 secondary | Active, safe (abstains). Widest reach of any RAR limitation. |
| **New F** | L6 domain-tag bonus plus counterparty-flattened tags: a person name prefers objects *associated with* the person over the person's record (`:167-168`) | None today (names undetected). **Latent:** G-04, I-02:r2, I-06:r2 at C2 if T2 is detected | Latent, unsafe |
| **New G** | L4b singleton binding with **zero** substantive evidence: when the query has no substantive tokens, a type hint alone binds the single type match (`:526-558`) | B-05:r1 at C2 (ICB, with the Q type defect) | **Active, unsafe** (C2) |
| **New H** | Anchorless pronoun policy: never resolves a bare pronoun, even with one candidate (`:851-871`) | B-01, B-04, G-01 (pools of 1), plus B-02, L-07 | By design; correct absent S-state |
| **New I** | `STOPWORDS` contains nouns-as-verbs (`reply`, `review`, `share`…) (`:50-58`) | J-01, L-08:r3 (secondary) | Active, safe |
| Contract | `RESOLVED` carries exactly one `candidate_id` (`rar_contracts.py:181-194`) | E-06, L-11:r1 | Active (E) |

**Multiple limitations per residual:** H-02 (C + D), E-05 (C + D), H-05 (C + D + B), D-02 (A latent + D), G-04/I-02:r2/I-06:r2 (F latent once detected).
**Would richer candidate metadata expose further latent failures?** Yes, demonstrably: real `created_at` ranks add 3 incorrect bindings at C1 and 5 at C2 (P4). The full oracle with real ranks (P3) additionally reproduces A2.8D's two known harness artefacts (C-04, C-05) — consistent with A2.8D §5.
**Does any named limitation no longer affect the path?** None is resolved. Known A is only masked, by the very candidate-construction gap (C) that blocks 5 residuals. RAR itself is unchanged: 75/75 of its unit/contract tests pass (§2).

---

## 8. Candidate and identifier-system inventory

| Question | Finding | Exists-but-disconnected vs does-not-exist |
|---|---|---|
| Correct candidate present? | Every residual with a non-empty intended set (45 of 47) has all its intended candidates in its C1 pool (verified mechanically); J-01 and H-06 expect abstention and correctly have none | — |
| Human-readable identifiers (INV-20417, PO-5521) | Exist only inside `title` (filename/synthetic title). `id` is an opaque UUID/`obj-*`. `exact_aliases` is never populated by any construction path in the corpus, harness, or production call site (`lfm_semantic_decoder.py:320-338`). A-01/03/05 now resolve at L6 via title tokens, not Level 0. | Code **exists** (title/filename; uri_core `FileStore` filename) but no alias registry exists. uri_core `GraphStore` dedupes by exact key and declares alias/entity resolution future work → **does not exist** |
| UUID typed by user (A-04) | Candidate `id` equals the UUID — no identifier mismatch; blocked by span prefix only | n/a (Q) |
| Recency | `created_at` exists for all 42 library entries and in uri_core `StoredFile.created_at` (`file_store.py:105`); `build_candidate_pool(oracle_recency=False)` and the production call site force `recency_rank=0` | **Exists, disconnected** (5 residuals; unsafe to wire before Known A — §7) |
| Attached-this-turn | `conversation_context.turn_attachments` exists; `TurnFrame.attachments` exists; uri_core `current_turn_attachments` exists (pre-RAR audit §3). The harness sets `is_attachment = (representation == file_reference_shape)`, meaning "is a file", **not** "attached this turn" — a semantic substitution | **Exists, disconnected; contract field mis-populated** (C-02, C2 L-03) |
| Media type / format | `file_reference.media_type` exists (FileStore shape), not mapped to `RARCandidate` | Exists, disconnected (E-04 partially; "Word" ↔ docx alias vocabulary **does not exist**) |
| Counterparty / direction / status / origin | Exist on synthetic candidates; flattened into untyped `domain_tags`. `RARCandidate.owner` is never populated. | Exists, **flattened** — partially connected, semantics lost (L-08:r3@C2, E-03@C2, L-07, L-05@C2, D-06; hazard F) |
| Candidate type | Present; the vocabulary differs from D1RQ's general head-noun vocabulary (`record` vs `person`; `pdf`/`approval`/`report`/`calendar_event`/`tool_result` have no head-noun mapping) and from RAR's `GENERIC_TYPE_WORDS` | Exists; **vocabularies disconnected** from each other |
| Primary vs derived object (email *about* invoice; action *about* roster; summary *of* forecast) | No relation field; only title word overlap | **Does not exist** (C2 A-01, F-05, L-10:r1; hazard F) |

---

## 9. Evidence-contract gaps (information produced or available upstream, not transported)

| # | Upstream information | Where it dies | Contract slot? | Residuals that would benefit (evidence) |
|---|---|---|---|---|
| 1 | `clause_text` (D1RQ computes per reference) | `m35_a2_8h_run.py::build_query` never passes it; RAR never reads `RAREvidence.clause_text` | Yes (dead) | **None today** — RAR does not read it. Would only matter for a future consumer (e.g. C2 C-03 "job spec", H-01/H-03 exclusion scoping). Reconfirms A2.8G: real but inert. |
| 2 | Turn attachments | Not mapped to `RARDeterministicAnchor.current_attachment_id` (never constructed anywhere) | Yes | C-02 (P5 → CR at C1 and C2); C2 L-03 needs a per-candidate "attached this turn" flag instead |
| 3 | `created_at` → `recency_rank` | Forced to 0 in candidate construction | Yes | D-01, D-02, D-04, L-04:r1, L-06 (+D-05, D-06, C-07 with Q) — **but exposes Known A** |
| 4 | Prior turns / conversation history | No slot in `RAREvidence`; `ActiveContext.recent_relevant_turns` exists but has no builder | No | S: B-01, B-02, B-03, B-04, G-01, L-02:r1, L-07 (+L-02:r2 at C2) |
| 5 | Excluded-phrase content and **reference role** (target vs excluded) | D1RQ puts only cue words (`no`, `not`) in `negation_spans` and emits excluded NPs ("the signed lease", "Amara's", "the summary", "the Q3 one") as ordinary references | Partial (`negation_spans` strings); no role field | H-01, H-03, H-04, H-05, H-02; **and 5 excluded/irrelevant-object confident bindings among unattributed spans** (§14) |
| 6 | Counterparty / direction / status / origin as typed fields | Flattened to `domain_tags` | No typed slot (`owner` unused) | L-08:r3@C2, E-03@C2, L-07, L-05@C2, D-06; prevents hazard F |
| 7 | `media_type` | Not mapped | No | E-04 (partial) |
| 8 | Plural referent | `RESOLVED` is single-valued | No | E-06, L-11:r1 |
| 9 | `candidate_verbs` | Never produced, never read | Yes (dead) | None |

---

## 10. Resolution-path map (whole corpus, C1; first detector at which each reference is correct)

| Layer | New correct resolutions | New correct abstentions | Cumulative correct (of 84) |
|---|---|---|---|
| D0 (TurnFrame) → RAR | 0 | 4 (C-07, G-05, I-02:r1, L-09:r2)* | 4 |
| D1 → RAR | 12 (A-02, C-01, E-01, E-02, E-03, F-01, F-05, L-01:r1, L-03, L-05, L-08:r1, L-08:r2) | 10 | 26 |
| D1R → RAR | 4 (F-04, G-04:r2, L-10:r1, L-10:r2) | 2 (I-06:r1, J-03) | 32 |
| D1RQ → RAR | 6 (A-01, A-03, A-05, C-03, F-02, L-11:r2) | 0 | 37 (22 CR + 15 CA) |

\* `NB-C-07:r1` is a correct abstention at D0 (bare "this") but becomes a family mismatch from D1 onward (the fuller span gets a wrong `document` type hint) — the only degradation of a correct outcome across the layer history. No correct resolution was ever lost.

By category, correct resolutions at D1RQ: A 4/5, C 2/7, E 3/6, F 4/6, G 1/7, L 8/19, and **B 0/6, D 0/7, H 0/6 under every deterministic detector (D0, D1, D1R, D1RQ)**. C2: D1 first-resolves 7, D1R 3, D1RQ 4 (13 total).

RAR levels that produced the 22 C1 correct resolutions: L6 `TERM_DISCRIMINATION` 16, L4b `TYPE_FILTER` 4, L2 `EXACT_TITLE` 2. **Levels 0, 1, 3, 5 and the L4a contrast path have produced zero correct resolutions on any deterministic path in this corpus.** L5.5 produced 3 correct abstentions (C-04, C-05, C-06).

---

## 11. Deterministic contribution analysis

- **D1 (determiner-NP grammar)** contributed the most: 12 of 22 correct resolutions, plus 10 abstentions.
- **D1R (completing word classes, token-scan NP)** added 4 resolutions (+18% relative), mostly through the T7 NP engineering fix.
- **D1RQ (removing a wrong type assertion; possessive boundary)** added 6. These are *repairs of D1R-introduced query defects* on references D1R had already detected. They are not new capability.
- **Ceiling of the surface/query layer with the current downstream (probes):**
  - Perfect GT spans with D1RQ's signals (P1): C1 CR 22 → 30 (+8, six of them T2 names); C2 CR 13 → 15 (+2) **with 4 incorrect confident bindings** (B-05:r1 plus 3 new).
  - Perfect oracle query, rank 0 (P2): C1 38 CR, C2 21 CR, 0 ICB at C2 and 1 at C1 (H-06). Much of the C1 gain comes from oracle *type* labels handed to singleton pools (B-01, B-04, G-01, B-03). Those labels are not derivable from the surface (they encode discourse state), and they do not survive C2.
  - Perfect oracle query plus real recency (P3): C1 47 CR / 5 ICB; C2 26 CR / 5 ICB.
- **Of the 14 Q-primary residuals, only 5 resolve with a perfect query and no other change** (B-05:r1, H-01, I-04, J-01, L-08:r3 — and B-05:r1 only in the singleton C1 pool). Four more need recency too (C-07, D-05, D-06, D-07). D-03 resolves at C1 only through an "earlier" approximation of "last quarter" and fails at C2 (N). A-04 needs only a bare-ID span, which the GT span itself does not provide. E-04, H-03 and H-05 also need RAR changes.

---

## 12. Current capability gaps (genuinely absent anywhere in URI, as far as inspected)

1. Morphological normalization (plural/stem/derivation) and abbreviation tolerance in RAR (Known C; `St`/`Street`, `Aug`/`August`) — **absent**, deterministic class.
2. Partial-credit / consistent evidence-sufficiency policy across RAR levels (Known D; plus the permissive commits in A, B, G) — **absent** as a unified policy.
3. Entity-type-aware scoring (person reference → person record over associated objects) — **absent** (hazard F).
4. Primary-vs-derived object relation (object vs email/action/summary about it) — **absent**.
5. Reference role/polarity (target vs excluded) in detector output and RAR input — **absent**.
6. Plural `RESOLVED` — **absent** from the contract.
7. Last-produced/last-discussed artifact pointer — **absent** (correction to A2.8E, §6.3).
8. Alias registry for human-readable codes and format names ("Word" ↔ docx) — **absent** (GraphStore declares entity resolution future work).
9. Semantic capabilities: paraphrase/world knowledge (F-06, I-07, C2 E-01), calendar-relative temporal reasoning (D-03), state-predicate mapping ("hasn't been signed off" → pending, "approve" ⇒ pending: L-07, C2 L-05), role descriptions ("the new hire" → Daniel: G-06) — **absent**, non-deterministic in character (**N**).
10. Compositional ordinals ("the X before the latest one") in the recency lexicon — **absent** (D-07). It is latent unsafe once ranks exist.

## 13. Disconnected existing capabilities

1. **Candidate recency:** `created_at` (corpus; uri_core `FileStore.StoredFile.created_at`) → `RARCandidate.recency_rank` exists; the producer forces 0 (harness `oracle_recency=False`; production `lfm_semantic_decoder.py:328,337`). The harness already contains the connected path (`oracle_recency=True`).
2. **Turn attachments:** `turn_attachments` / `TurnFrame.attachments` / uri_core `current_turn_attachments` → `RARDeterministicAnchor.current_attachment_id` / `RARCandidate.is_attachment` exist; the anchor is never constructed, and `is_attachment` is populated with a different meaning.
3. **Conversation history:** corpus `prior_turns`; uri_core `ConversationHistoryStore`, `TurnState.recent_conversation`; `ActiveContext.recent_relevant_turns` (no builder). Present but with no RAR contract slot, and not shaped as a last-produced-object pointer.
4. **Candidate relational metadata** (`counterparty`, `direction`, `status`, `origin`): present, reaches RAR only as untyped tags; `RARCandidate.owner` exists, unused.
5. **`media_type`**: present in the FileStore reference shape, unmapped.
6. **`clause_text`**: computed by D1RQ, dropped at `build_query`, unread by RAR.
7. **Typed entity store:** uri_core `GraphStore` (per-user typed entities) — exists; no connection to `uri_v1`; no alias resolution.
8. **Type vocabularies:** three (D1RQ head nouns, RAR `GENERIC_TYPE_WORDS`, corpus `candidate_type`) exist but are not reconciled.

---

## 14. Safety-relevant failures

| Kind | Case(s) | Mechanism | Current / latent |
|---|---|---|---|
| Incorrect confident binding | `NB-H-06:r1` @C1 | Known B contrast shortcut binds the excluded sole candidate | **Current** |
| Incorrect confident binding | `NB-B-05:r1` @C2 | Q: NP crosses `in`, object-to-create noun becomes the type hint; New G: L4b binds on type alone | **Current** (misattributed in A2.8G/A2.8H as NB-H-06) |
| Latent ICB when recency is wired | C1: J-02, J-04, D-07; C2: D-01, D-02, D-07, L-06, L-09:r2 | Known A (+ D-07 recency-lexicon precedence) | Latent (P4) |
| Latent ICB when T2 names are detected | C2: G-04:r1, I-02:r2, I-06:r2 | New F (counterparty tag bonus) | Latent (P1) |
| Excluded / irrelevant objects bound confidently | Unattributed D1RQ spans: "the signed lease" (H-01, C1+C2), "Amara's as the" (H-02, C1), "the summary" (H-04, C1+C2), "the Q3 one" (L-01, C1), "the August ones" → August expense report (H-03, C2) | Evidence-contract gap #5 (no reference role). **The runner never sends unattributed spans to RAR, so the telemetry cannot see this.** Probed here in the scratchpad. | Latent (would be current in any integration that resolves every detected span) |

**Current unsafe residuals: 2 references (1 at C1, 1 at C2).** Latent unsafe demonstrated by probes: 8 recency-wiring bindings (3 C1 + 5 C2), 3 T2-detection bindings (C2), 5 distinct excluded/irrelevant-object bindings.

---

## 15. Evidence gaps

| Gap | Effect on verdict |
|---|---|
| `uri_v1/` and all `scripts/m35_*` are untracked; content identity rests on SHA-256 taken this session, not git history | Does not affect this audit's findings (bit-for-bit reproduction), but no historical attestation exists that RAR was unmodified between A2.8D and now. Reproduction of A2.8H telemetry is the substitute evidence. |
| No A2.8H aggregates/scorer file exists; A2.8H figures appear to have been computed ad hoc | None — all figures recomputed here |
| A2.8H's "two runs bit-identical" cannot be checked (one telemetry file) | None — replaced by two independent re-executions |
| A2.8H RAR invocation counts (31/63/83/83) not reproduced (15/63/82/82) | None — not used by any conclusion |
| `graphify-out/graph.json` absent in this worktree; graphify could not be used | None — direct source reading used |
| RAR fixture suites scored in memory with a simplified rule (outcome + candidate id, no acceptable alternatives / mode split): diagnostic 24/24, challenge 93/100, stage3 96/103, stage4b 116/136. These do not match the prior reports' figures (e.g. stage3 99/103, stage4b 122/136 FULL / 102/136 DET-ONLY) because of the scoring method. The official eval scripts were not run because they write result files into the repository. | Does not affect the verdict; RAR's 75 pytest unit/contract tests pass, and the D1RQ path reproduces bit-for-bit |
| T2 contextual-gating precision was not measured beyond a 79-turn capitalization scan | Affects only the *feasibility* of T2 detection, not the recommendation (which defers T2 on binding-safety grounds) |
| uri_core search for a last-produced-artifact pointer was a bounded keyword grep plus direct reads of `turn_state.py`/`drafting_memory.py`; `CapabilityContextResolver` was not re-read (pre-RAR audit cited as durable) | Could change the T8/S classification from "absent" to "disconnected" if such a pointer exists under different naming. Does not affect the next-experiment recommendation. |
| Probes P1–P5 are diagnostic counterfactuals (oracle inputs), not qualified repairs | They show *where* failures belong, not that any repair is safe. Every "latent ICB" is demonstrated under the probe input, not under any designed mechanism. |
| Single-author synthetic corpus (79 cases; non-file candidates are synthetic by necessity, per the pre-RAR audit §8) | Frequencies are corpus-specific; mechanisms are code-level and general |
| Legacy repository `C:\Users\cheta\Development\uri-agent` not re-inspected this session | None — no legacy claim is made here; every "uri_core" in this document means `C:\Users\cheta\Development\Uri\_V1\uri_core` |

---

## 16. Smallest justified next experiment

**Phase 9 — cost/value inventory by cluster (no numeric score):**

| Cluster | Refs (C1 primary) | Unsafe? | Current behaviour | Smallest repair class | Deterministic? | Reuse existing mechanism? | New semantic capability? | Blast radius | Evidence needed first |
|---|---|---|---|---|---|---|---|---|---|
| RAR commit-validation (Known A, B-shortcut, New G, New F) | 1 primary (H-06) + current B-05@C2 + **all 11 latent ICBs** | **Yes — the entire unsafe set** | Wrong binding (2 current) / masked | RAR-internal consistency rule: no commit at L4a/L4b/L5 that L6-style evidence contradicts; no commit on zero evidence | Yes | Yes — L6's existing absent-entity check; harness's existing `oracle_recency=True` | No | One module (`rar_deterministic.py`); gates C, T2, anchor wiring | Paired rank-0/real-rank corpus runs; RAR's 75 tests + fixture suites; J-category abstention preservation |
| RAR lexical normalization / partial credit (Known C, D) | 9 primary + ≥7 secondary | No (safe abstention today); relaxing D risks new ICBs in J/K cases | Abstention | Normalization + a consistent any/all evidence rule | Yes | Partly (L4b "any" rule already exists) | No | RAR L4a/L4b/L6 | Must follow commit-validation; J-02/J-04/J-06-type cases are the guard |
| Candidate recency wiring (C) | 5 (+4 with Q) | **Unsafe to do first** (+8 latent ICB) | Safe abstention | Populate `recency_rank` from `created_at` | Yes | Yes (`oracle_recency=True`) | No | Candidate construction | Needs Known A qualified first |
| Q residual defects (NP stop-set gaps `in`/`as`/`please`/verbs, recency lexicon, bare-ID span, exclusion scoping) | 14 | 1 current (B-05@C2) | Mostly abstention | Detector rules | Yes | Yes (D1RQ) | No | Detector | 5 of 14 resolve with a perfect query alone |
| T2 names (D) | 7 | **Latent unsafe** (3 at C2) | Silent miss | Detector gating + downstream entity-type awareness | Trigger yes; binding safety needs RAR/C | Partly | No | Detector + RAR | Hazard F must be qualified first |
| Attachment anchor (X1) | 1 (+L-03@C2) | No | Abstention | Construct `current_attachment_id` from turn attachments | Yes | Yes (Level 1 exists, TurnFrame carries attachments) | No | Harness/query construction | Small; low generality in this corpus |
| Session/discourse state (S) | 7 | No | Abstention | New last-produced/last-discussed pointer + contract slot | Deterministic source, new wiring | Partly (history exists; pointer absent) | No, but a new state capability | **Architectural** (cross-package uri_core ↔ uri_v1) | Requires a User-level architecture decision |
| Semantic (N) | 2 (+2 C2) | No | Safe abstention | — | No | No | Yes | — | Correct behaviour today is abstention; no repair justified |
| Plural / role contract (E) | secondary in 2 + exclusion hazard | Latent (excluded-object bindings) | Abstention | Contract fields | Yes | No | No | Contract change | Architecture review |

**Phase 10 — selection.** The recommended next experiment is:

> **RAR commit-evidence consistency qualification (Known A first, with the Known-B contrast shortcut, New G type-only singleton binding and New F tag-bonus measured as tracked sub-mechanisms).** A deterministic, RAR-internal experiment run under **paired candidate conditions — `recency_rank = 0` (current) and `created_at`-derived ranks (the harness's existing `oracle_recency=True` path)** — plus the T2 ground-truth-span probe. It asks: can one rule — "no level may commit a binding that the resolver's own Level-6 lexical/absent-entity evidence contradicts, and no binding may be committed on zero substantive evidence" — eliminate all 2 current and 11 latent incorrect bindings (`H-06`, `B-05:r1`@C2; `J-02`, `J-04`, `D-07`@C1; `D-01`, `D-02`, `D-07`, `L-06`, `L-09:r2`@C2; `G-04`, `I-02:r2`, `I-06:r2`@C2 under T2 spans) while keeping all 22/13 current correct resolutions, keeping the 5 C-class gains real recency makes available, and keeping RAR's 75 tests passing?

**Rationale against the Phase 10 criteria:**
- **Safety:** this is the only cluster that contains every current and every demonstrated latent unsafe binding. Every other candidate experiment either leaves those in place (lexical normalization, attachment anchor) or would *activate* them (recency wiring activates 8, T2 detection activates 3).
- **Generality:** one inconsistency explains Known A, the B-shortcut and New G. Levels 4a/4b/5 commit without the evidence check that Level 6 applies too strictly. This is a cascade property, not a corpus pattern.
- **Deterministic / current mechanism:** it reuses RAR's own existing absent-entity logic and the harness's existing real-recency path. It needs no new data source, contract field or model.
- **Architectural isolation:** confined to `uri_v1/turn/rar_deterministic.py`, with no contract, detector or production change.
- **Evidence quality:** every targeted failure is reproduced from source in this audit (P1/P4 probes, telemetry) rather than inferred. A2.8D had already characterized A and B independently.
- **Enablement:** it is the precondition for safely connecting the most valuable disconnected capability (recency, 5 residuals plus 4 Q-with-C). It is also a precondition for T2 detection (7 residuals).

**Explicitly not recommended now:** relaxing Known D (partial credit) in the same experiment — it is the guard that currently keeps J-category absent-entity cases safe, so it should be qualified only after commit validation, as its own experiment. Wiring recency or enabling T2 detection before this qualification. Session-state wiring (needs a User architecture decision). Any model for the N residuals, whose correct current behaviour is abstention. A larger model in general: nothing in this evidence points to model capacity as the limiting factor for any D/Q/C/R/S/X1 residual.

### Phase 11 — architectural questions

**Have deterministic surface/query improvements reached diminishing returns relative to downstream deterministic mechanisms? Yes.** Evidence:
1. With *perfect* ground-truth spans (P1), C1 correct resolutions rise only from 22 to 30 (six of the eight are T2 names). C2 rises from 13 to 15 and **gains 3 new unsafe bindings**. The surface ceiling is low, and at C2 it is unsafe.
2. Only 22 of 47 C1 residuals (D 8 + Q 14) are surface/query-owned. Of the 14 Q cases, only 5 resolve with a perfect query and no downstream change.
3. Categories B (conversational), D (recency) and H (negated) have **0 correct resolutions under all four deterministic detectors**. Their blockers are candidate recency (C), discourse state (S), negation transport/role (E) and RAR evidence rules (R), not detection.
4. RAR Levels 0, 1, 3 and 5 have **never** produced a correct resolution on any path in this corpus. They are starved of inputs (anchors, recency, state) that exist elsewhere in URI but are not connected.
5. D1RQ's gains repaired defects that D1R introduced; they did not add capability. The last two surface iterations added +4 and +6 resolutions, while one downstream input (real recency, P4) adds +6 C1 resolutions by itself — but it cannot be enabled safely until RAR's commit validation is qualified.

**Which failures need a capability not represented anywhere in URI?**
- **Genuinely absent (semantic, N):** paraphrase/world knowledge (F-06, I-07, C2 E-01), calendar-relative reasoning (D-03), state-predicate interpretation (L-07, C2 L-05), role descriptions (G-06's full semantics).
- **Genuinely absent (deterministic, not yet built):** morphological/abbreviation normalization, a consistent evidence-sufficiency policy, entity-type-aware scoring, primary-vs-derived object relations, reference role/polarity, plural resolution, an alias registry, compositional ordinals, and a last-produced-artifact pointer.
- **Disconnected, not absent (do not treat as new capability):** candidate recency (`created_at`), turn attachments, conversation history, typed relational metadata (counterparty/direction/status/origin), `media_type`, `clause_text`, and the uri_core `GraphStore` entity store. Five C residuals, one X1 residual, part of the S residuals, and most C2-only E residuals depend on these connections rather than on new capability. The recency connection must come after the recommended RAR qualification.

---

## 17. Self-review against acceptance criteria

| Criterion | Met? | Where |
|---|---|---|
| AC1 recompute + independent re-execution; corrections recorded | Yes — 18 claims checked; 1 material correction (C2 ICB identity), 3 non-material | §3 |
| AC2 complete population, all fields | Yes — 47 C1 rows (all fields from re-execution/telemetry) + 8 C2-only | §4 |
| AC3 one primary owner each, sums exactly | Yes — 14+10+8+7+5+2+1 = 47; C2-only 2+2+2+1+1 = 8 | §5 |
| AC4 disconnected vs absent, with locations | Yes | §8, §12, §13 |
| AC5 uri_core checkout named | Yes — header of §15 and AC5 | §15 |
| AC6 no repository modification except this file | Yes — scratchpad-only diagnostics; telemetry and corpus hashes unchanged after the audit; RAR eval scripts not run because they write files | §2, §15 |
| AC7 unverifiables stated with effect | Yes | §15 |
| AC8 recommendation cites criteria, no count ranking, no model | Yes | §16 |

Gaps found in the first draft and repaired before return: (1) the draft carried A2.8H's "C2 ICB = NB-H-06" forward; the telemetry refuted it and the finding was added to §3/§14. (2) The draft treated `NB-L-08:r3` as a pure contract gap per A2.8G; P1/P2 showed it resolves at C1 with the full span, so it was reclassified with the reason recorded. (3) The draft reused A2.8E's "TurnState.active_pointer supplies T8"; direct reading of `turn_state.py` refuted it (§6.3). (4) "Zero new false positives" originally hid that unattributed spans are never RAR-evaluated; the excluded-object binding probe was added (§14). (5) The draft called `NB-G-03` Q per A2.8H; the mechanism is RAR's all-or-nothing check on faithfully captured user words, so it is now R, with the prior classification cited.

**Files created:** `docs/plans/M35_URIV1_A2_8I_POST_REPAIR_END_TO_END_RESIDUAL_AUDIT.md` (this file). **Files modified:** none. **Production files touched:** none. No commit. No push.

VERIFICATION_READY
