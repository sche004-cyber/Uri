# M35 URIv1 — A2.8D: Reference Detection/Delivery Qualification — Execution Report

> **CORRECTION NOTICE (added during A2.8E forensic residual-characterization pass, same session's later continuation):** `scripts/m35_a2_8d_run.py`'s `find_matching_found_expr()` (span-to-ground-truth attribution) used a **one-directional** substring check (a detector's found span was only accepted if it was a substring of the ground-truth span). This silently mis-scored every case where D1's grammar-shape detector correctly captured the true reference but included one extra trailing/leading word (e.g. detected `"the invoice please"` vs. ground truth's `"the invoice"` — the true reference words were fully present, but the check required the reverse containment direction) as `SILENT_DETECTION_MISS`. Fixed to a bidirectional check. **Corrected figures: D1 detection recall 67.9%** (was reported 58.3%); **D1 resolution coverage (C1) 12/84 = 14.3%** (was reported 11/84 = 13.1%); **D2 detection recall 3.6%** (was reported 1.2%, 2 more of D2's rare successful calls turn out to have been mis-scored the same way). The "35 undetected references" figure in the original report's §8 additionally conflated two different things: §8's `neither_detects` count paired only D1 against D2 (silently assuming D0's coverage was a subset of D1's, which is not true — D0 independently detects 2 references D1's grammar rules miss: `NB-C-02:r1`, `NB-B-05:r1`). The figure actually meaning "undetected by every one of D0, D1, and D2" is **27** (recomputed with the bidirectional-match fix), not 35. Full detail, evidence, and the corrected 27-case residual set are in `docs/plans/M35_URIV1_A2_8E_RESIDUAL_CHARACTERIZATION_REPORT.md`. History preserved per the repository's auditable-correction convention — the numbers below are left as originally reported, not silently rewritten.

**Type:** Experiment implementation and execution only. No RAR/TurnFrame/contract modification. No architecture change. No commit, no push.
**Governing design:** `docs/plans/M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md` (frozen, `VERIFICATION_READY`)
**Status:** `VERIFICATION_READY` — see correction notice above; superseded in part by `M35_URIV1_A2_8E_RESIDUAL_CHARACTERIZATION_REPORT.md`.

```xml
<development_state>
  <current_phase>EXECUTE</current_phase>
  <allowed_actions>implement D0/D1/D2 detectors and harness per the frozen plan, run against the frozen corpus, score, write telemetry and this report</allowed_actions>
  <prohibited_actions>modify uri_v1/turn/*, modify the frozen corpus, repair RAR's known limitations, tune D1/D2 against corpus pass/fail rate, select an architectural winner, commit, push</prohibited_actions>
  <exit_criteria>D0/D1/D2 executed against the frozen corpus, telemetry written, boundary checks clean, known RAR limitations verified still visible, report answers all 8 result-interpretation questions</exit_criteria>
  <stop_condition>VERIFICATION_READY</stop_condition>
</development_state>
```

---

## Acceptance criteria (defined before execution)

1. Corpus SHA-256 verified before and after the run; any mismatch halts with `FROZEN_CORPUS_INTEGRITY_FAILURE`.
2. `rar_deterministic.py` called completely unmodified, exactly as in A2.8C.
3. Neither D1 nor D2 output is ever compared against a candidate pool by anything other than RAR itself; every detector-produced span is scanned for a boundary violation (leaking a live `candidate_id`) before use.
4. D1 is a generalizable linguistic-shape mechanism, not an expansion of the natural-boundary corpus's own wording into a bigger hand-listed vocabulary — verified by inspecting the mechanism list itself (§4) against the corpus, not the reverse.
5. D2 is run against its actual real runtime; if it cannot execute truthfully, that is recorded honestly rather than papered over or substituted.
6. The six previously-established genuine RAR limitation cases (§0) remain individually visible in every detector's telemetry, not silently masked.
7. Every measurement in Phase 7's list is either reported with a real number or explicitly `UNMEASURED` — no fabricated figures.

Self-review: all seven met — §2 (criterion 1), §3–§4 (criteria 2–4), §5 (criterion 5), §9 (criterion 6), §7–§8 (criterion 7).

---

## 0. Governing evidence treated as authoritative (not re-derived)

Per the task's explicit instruction, the corrected A2.8C figures are treated as given, not re-litigated:

- 79 cases, 84 ground-truth-bearing references, 503 telemetry rows, 213 real resolver invocations, `INVENTED_CANDIDATE = 0`.
- Real (D0-equivalent) path: 0% confident resolution. `SILENT_STEP1_MISS = 71`. Category A (detection/delivery failure): 80/84 = 95.2%. Category D (correct abstention): 4/84. Category B/C on the real path: zero.
- Oracle (S2) resolution: **S2×C1 55.95%, S2×C2 30.95%** (corrected denominators).
- Six genuine RAR unsafe-resolution cases (`NB-D-01`, `NB-D-02`, `NB-H-06`, `NB-J-02`, `NB-J-04`, `NB-L-09:r2`), two mechanisms: (a) Level 5 recency selection can return before Level 6 lexical/absent-entity validation; (b) Level 4a negation elimination cannot represent purely relational exclusions ("the other one"). **Not repaired in this experiment. Verified still individually visible — §9.**

---

## 1. Repository state

- Branch `m35-uri-v1-parallel-architecture`, HEAD `e8e3b65259c45fc823addc3ef8969425a265bd1b` — unchanged throughout.
- Files created: `scripts/m35_a2_8d_detector_d1.py`, `scripts/m35_a2_8d_needle_inner_runner.py`, `scripts/m35_a2_8d_detector_d2_needle.py`, `scripts/m35_a2_8d_run.py`, `scripts/m35_a2_8d_score.py`, `docs/plans/M35_URIV1_A2_8D_TELEMETRY.json`, `docs/plans/M35_URIV1_A2_8D_AGGREGATES.json`, this report.
- **No file under `uri_v1/turn/` was modified** — confirmed via `git status --short uri_v1/` (same untracked-but-unchanged set as before this task) and `git diff --stat uri_v1/` (empty).
- Protected legacy repository `C:\Users\cheta\Development\uri-agent` — not touched this session (D2's Needle venv, `.venv-needle`, is a pre-existing sibling directory inside that checkout, invoked read-only as a subprocess interpreter exactly as `uri_v1/turn/needle_decoder.py`'s own `default_venv_python()` convention already does; no file inside it was created, modified, or deleted).
- No commit, no push.

---

## 2. Corpus integrity

```
Pre-run:  0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380
Post-run: 0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380
```

Match. No `FROZEN_CORPUS_INTEGRITY_FAILURE`. Ground truth was not altered — every `RARQuery`/`RAREvidence` value fed to RAR in every D0/D1/D2 cell traces to either a detector's own output or the candidate library's real object metadata, never to an `expected_*`/`intended_candidate_id`/`reason` field (verified by code inspection of `m35_a2_8d_run.py`: ground truth is read only inside `_classify()`, after `resolve_rar_deterministic_extended()` has already returned).

---

## 3. Harness implementation

`scripts/m35_a2_8d_run.py` runs, per case: (a) D0 = `build_turn_frame()` unmodified, exactly A2.8C's S1 construction; (b) D1 = `detect_references()` from the new deterministic module; (c) D2 = one batched subprocess call into the existing `.venv-needle` interpreter. For every detector-produced reference, a `RARQuery` is built (reference span → `reference_expression`, detector's `recency_hint`/`negation_spans`/`coarse_type` → `RAREvidence`, `deterministic_anchor=None` always) and `resolve_rar_deterministic_extended()` is called exactly once per (detector, C-axis, reference) — 5 × 3 = 9 cells total (D0/D1/D2 × C1/C2/C3).

**Candidate-pool construction is identical across all nine cells** (`build_candidate_pool(..., oracle_recency=False)` — every `RARCandidate.recency_rank` is `0`, mirroring the real production call site exactly as A2.8C's S1 did). This was a deliberate, not incidental, choice: it isolates the experiment's one variable (evidence *delivery* quality) from a second, orthogonal variable (candidate-pool *recency-ordering* richness) that A2.8C's own S2 oracle condition already covers separately. §8 discusses a direct, important consequence of this choice for the residual-visibility check.

**Boundary-violation check** (`boundary_violation()`): every detected span is scanned for containing a live `candidate_id` substring from that cell's own candidate pool before it is used to build a query; a hit short-circuits scoring for that row (`scoring_class = BOUNDARY_VIOLATION`) rather than letting it silently score as a success. **Result: 0 boundary violations across all 1,029 rows** — neither D1 nor D2 ever leaked a candidate ID.

---

## 4. D1 — deterministic detector design (as implemented, not merely as planned)

`scripts/m35_a2_8d_detector_d1.py`. Six mechanisms, each a generalizable shape rule, **none derived from or tuned against this corpus's specific wording** (the mechanisms were designed from the general shape of A2.8C's own failure — multi-word noun phrases outside `TurnFrame`'s 21 fixed patterns — before any scored run against this corpus):

1. **Filename shape** (`\b[\w][\w\-]*\.(pdf|docx?|...)\b`) — a general extension pattern, not an enumerated filename list.
2. **Quoted spans** — reused unchanged from `TurnFrame`'s own already-general mechanism (a generic `['"]...['"]` regex).
3. **Determiner + noun-phrase shape** (`\b(the|this|that|these|those)\s+<NP up to 6 words, stopping before a conjunction>`) — the dominant, most general mechanism, and the direct answer to A2.8C's own headline finding (`TurnFrame`'s 12 multi-word *literal phrases* never matched any of 79 realistic turns; a *grammatical shape* rule catches the general pattern those 12 literals were each one narrow instance of).
4. **Bare-pronoun fallback** — the same closed 9-pronoun set `TurnFrame` already uses, kept only as a fallback when nothing more specific covers that word.
5. **Closed-class temporal-deixis lexicon** (14 entries: "latest", "most recent", "previous", "the one before", "before that/it", "earlier", "earliest", "last week", "yesterday", "same", "revised", "original", "the other", "current") — a grammatical function-word class, not a domain-phrase vocabulary; mapped directly onto `RAREvidence.recency_hint`'s own existing recognized values.
6. **Per-clause-scoped negation** — re-derives `TurnFrame`'s own negation-pattern list but scopes each match to the clause it occurs in (via a self-contained clause splitter, independently re-implemented rather than importing `turn_frame_builder`'s private helper) instead of passing it turn-global. This directly targets the turn-global-negation limitation the governing discovery plan already flagged as a real production gap.

**Two defects found and fixed during pre-flight testing, before any scored run** (both are general robustness fixes to D1 itself, not corpus-specific tuning — verified by re-reading the fix: neither references any specific case ID or corpus wording): (a) the noun-phrase regex initially bled across coordinating conjunctions ("the document and tidy up the formatting" matched as one phrase) — fixed by excluding conjunction/preposition words from the phrase body itself, not just checking for them at the match boundary; (b) the clause splitter initially split sentence-terminal periods *inside* filenames (`"...xlsx to Marcus..."` from `"Q2_budget_forecast.xlsx to Marcus..."`) — fixed by masking filename-shaped tokens before sentence splitting. Both are documented in the module's own code comments.

**Type-hint mapping** reuses `rar_deterministic.py`'s own `GENERIC_TYPE_WORDS`-adjacent vocabulary (document/spreadsheet/pdf/image/email/person/record) rather than inventing a second, divergent type taxonomy.

---

## 5. D2 — Needle 3, narrow role, as actually executed

### 5.1 Availability

`scripts/m35_a2_8d_detector_d2_needle.py` located the existing `.venv-needle` interpreter (same convention as `uri_v1/turn/needle_decoder.py`'s `default_venv_python()`), confirmed `import needle` succeeds, and ran the full 79-case batch. **`d2_availability: "AVAILABLE"`** — this was a genuine runtime availability check, not assumed.

### 5.2 Frozen schema (boundary-compliant by construction)

```json
{"reference_detected": "bool", "reference_span": "string",
 "coarse_type": "enum[document,spreadsheet,pdf,image,email,person,record,none]",
 "recency_hint": "enum[latest,previous,earlier,same,none]"}
```

**No `candidate_id` field exists in this schema at all** — Needle is structurally unable to emit a resolution decision through it, satisfying the frozen boundary mechanically, not just by prompt instruction.

### 5.3 Pre-flight behavioral finding (recorded honestly, per the task's explicit instruction not to substitute another model)

A smoke test against 5 varied sentences, run **before** the scored batch, found Needle 3 (generation 3, the same base model the durable prior evidence already rejected as a broad Step-1 semantic decoder) declines to call the tool at all in the majority of cases, and — critically — one early test exposed that a *reused* agent object carries conversation state across `.complete()` calls, producing an answer that belonged to a *previous* test's text. **Fixed methodologically** (a fresh `needle.Needle(...)` agent is now constructed for every single case, confirmed in `m35_a2_8d_needle_inner_runner.py`'s own docstring and code) before any scored run — this was a test-harness bug on this session's part, not evidence about the model, and is disclosed as such rather than silently corrected.

### 5.4 Scored batch result (79 cases, fresh agent per case)

| Metric | Value |
|---|---|
| Cases with a result returned | 79 / 79 |
| Tool call actually made (`call_made`) | **3 / 79 (3.8%)** |
| Of those 3 calls, `reference_detected: true` | 3 / 3 |
| Of those 3, span non-empty and thus scorable | 1 / 3 (the other 2 had `reference_detected: true` but an empty `reference_span`, which `to_d1_shaped_reference()` correctly discards rather than feeding RAR a blank query) |
| Average latency per case | 151.5 ms |
| Average peak RAM | 101.3 MB |
| Batch wall-clock time, 79 cases | 12.4 s |

**D2's genuine, measured detection recall is 1/84 ≈ 1.2%** (§7) — the runtime executes truthfully and without error, but its behavioral reliability for even this much narrower job (a single boolean + span, not a full semantic decode) is not materially better than declining outright. **This is reported as a measured finding, not an excuse to substitute a different model** (none was substituted) and not a reason to discard the cell (it was run to completion against the full corpus, not aborted after the smoke test).

---

## 6. Reproducibility

The full A2.8D pipeline was **not** re-run multiple times end-to-end in this session (unlike A2.8C's three-run reproducibility check), because D2 involves a real subprocess model call whose exact latency (though not its structured output, per Needle's `generation=3` deterministic-decode behavior observed in spot checks) is expected to vary run-to-run — the task's own instruction anticipates this ("where model execution is inherently nondeterministic, preserve sufficient telemetry to expose run-to-run variation" rather than mandating identical repeats). D0 and D1 are pure deterministic code paths and inherit A2.8C's already-established reproducibility (§3.1 of the A2.8D verification document) by construction — neither was modified between the verification and execution phases. **D2's structured output (`call_made`, `arguments`) was not independently re-verified for run-to-run stability in this session** — flagged as an evidence gap, §11.

---

## 7. Headline measurements

| Metric | D0 (existing) | D1 (deterministic) | D2 (Needle 3, narrow) |
|---|---|---|---|
| Detection recall (of 84 gt references, C1) | 13/84 = **15.5%** | **49/84 = 58.3%** | 1/84 = **1.2%** |
| Detection precision (spans produced that map to a real reference, C1) | 13/31 = **41.9%** | 49/109 = **45.0%** | 1/1 = **100%** (n=1, not statistically meaningful) |
| Resolution coverage (RAR `CORRECT_RESOLUTION`, C1) | 0/84 = **0.0%** | **11/84 = 13.1%** | 0/84 = 0.0% |
| Resolution coverage (C2) | 0/84 = 0.0% | 7/84 = 8.3% | 0/84 = 0.0% |
| `INCORRECT_CONFIDENT_BINDING` (C1) | 0 | **1** (§9 — reclassified below, not a new defect) | 0 |
| `INVENTED_CANDIDATE` (all cells) | 0 | 0 | 0 |
| Boundary violations (all cells, all 1,029 rows) | 0 | 0 | 0 |
| K-category (no-reference) false-positive *binding* | 0 | 0 | 0 |
| K-category false-positive *safe abstention* (spurious detection, RAR still declines) | 2 | 6 | 0 |
| Detector calls per case | 0 (rule-based, code path) | 0 (rule-based, code path) | 1 |
| RAR calls (C1, reference-bearing + K rows, per detector) | 31 | 109 | 1 |
| End-to-end latency | `UNMEASURED` (not separately instrumented; RAR's own per-call latency is sub-millisecond per A2.8C) | `UNMEASURED` (same) | avg 151.5 ms/case (detector) + RAR's sub-ms |
| Detector-only latency | `UNMEASURED` (D0 is embedded in `build_turn_frame()`, not separately timed) | `UNMEASURED` (same reason) | avg 151.5 ms/case (measured) |
| CPU | `UNMEASURED` | `UNMEASURED` | `UNMEASURED` |
| RAM | `UNMEASURED` | `UNMEASURED` | avg 101.3 MB peak (measured, `peak_ram_mb` field from Needle's own response) |
| VRAM/model footprint | N/A (no model) | N/A (no model) | `UNMEASURED` this session (prior qualification stages measured this separately per the governing plan's own note; not re-measured here) |
| Deterministic vs. model-assisted cost | 0 model calls, pure regex/code | 0 model calls, pure regex/code | 1 model call/case, ~150ms, ~100MB |

**No acceptance threshold was invented or applied to any of the above** — every number is reported as a raw measurement, per Phase 8's explicit instruction.

---

## 8. D1 vs D2 six-way overlap breakdown

Paired by (case_id, ref_key), C1 condition, 84 gt-bearing references:

| Bucket | Count (C1) | Count (C2) |
|---|---|---|
| Both detect, RAR resolves correctly in both | 0 | 0 |
| Only D1 resolves correctly | **11** | **7** |
| Only D2 resolves correctly | 0 | 0 |
| Both detect, RAR fails/abstains in both | 1 | 1 |
| Only D1 detects (D2 misses) | **37** | **41** |
| Only D2 detects (D1 misses) | 0 | 0 |
| Neither detects | 35 | 35 |

**D2 supplies zero incremental detection capability beyond D1 on this corpus** — every single reference D2 ever detected, D1 also detected (D2's one successful detection, per §5.4, falls inside D1's own detected set; there is no case where D2 succeeds and D1 does not). **This directly answers A2.8D's research question's second branch (§19 item 2 of the governing plan): D2 (Needle 3, narrow role) adds no measured incremental capability over D1 on this corpus, at a real cost of ~150ms/case and a real model call, versus D1's zero-model-call, sub-millisecond deterministic path.**

---

## 9. Residual RAR-limitation visibility — the six known cases, per detector

| Case:ref | D0 (existing) | D1 (deterministic) | D2 (Needle) |
|---|---|---|---|
| `NB-D-01:r1` | `SILENT_DETECTION_MISS` | `MISSED_RESOLVABLE_CASE` | `SILENT_DETECTION_MISS` |
| `NB-D-02:r1` | `SILENT_DETECTION_MISS` | `MISSED_RESOLVABLE_CASE` | `SILENT_DETECTION_MISS` |
| `NB-H-06:r1` | `SILENT_DETECTION_MISS` | **`INCORRECT_CONFIDENT_BINDING`** | `SILENT_DETECTION_MISS` |
| `NB-J-02:r1` | `SILENT_DETECTION_MISS` | `CORRECT_ABSTENTION` | `SILENT_DETECTION_MISS` |
| `NB-J-04:r1` | `SILENT_DETECTION_MISS` | `CORRECT_ABSTENTION` | `SILENT_DETECTION_MISS` |
| `NB-L-09:r2` | `CORRECT_ABSTENTION` | `CORRECT_ABSTENTION` | `SILENT_DETECTION_MISS` |

**All six remain individually traceable in every detector's telemetry — none is silently masked.** Three findings from this table, none of which repairs or hides the underlying RAR limitations (per the task's explicit prohibition):

1. **`NB-H-06` is D1's one `INCORRECT_CONFIDENT_BINDING`** (the "1" in §7's table). This is **not a new detector-introduced defect** — it is the same already-verified RAR limitation (mechanism (b), §0: Level 4a negation elimination cannot represent "the other" because it shares no vocabulary with the excluded candidate's title) becoming *reachable* for the first time only because D1 detects the reference at all (D0 never invoked RAR on this case, so the limitation was invisible under D0, not absent). **Per the task's explicit instruction ("do not count correct detection → known RAR failure as a detector failure"), this is scored and reported as the pre-existing RAR limitation reaching RAR, not as a D1 defect.**
2. **`NB-J-02` and `NB-J-04` resolve correctly (`CORRECT_ABSTENTION`, matching ground truth's expected `UNKNOWN`) under D1**, despite being confirmed `INCORRECT_CONFIDENT_BINDING` cases under A2.8C's S2 oracle condition. This is explained precisely, not coincidentally: A2.8C's S2 oracle populated `RARCandidate.recency_rank` with a real timestamp-derived ordering (§4.1 of the verification document's decision 2), which let RAR's Level 5 "earlier" logic fire and pre-empt Level 6's absent-entity check (mechanism (a), §0). **D1's candidate pool never populates `recency_rank`** (§3 — a deliberate boundary choice, since ranking candidates is not a detector's job), so Level 5's "earlier" branch has no ordering to act on and correctly falls through to Level 6, which then correctly catches "Jonas" as a substantive token absent from every candidate. **This is not D1 "fixing" RAR — it is a direct, mechanistic consequence of D1 operating strictly within its frozen boundary** (never touching candidate-pool construction) and is recorded here as an important interaction effect, not a repair.
3. **`NB-D-01`/`NB-D-02` remain `MISSED_RESOLVABLE_CASE` under D1** (RAR correctly declines to guess, rather than binding wrongly, when `recency_rank` carries no ordering — consistent with finding 2's mechanism) — ground truth expected `RESOLVED`, so this is a coverage gap, not a safety violation; RAR's abstention here is the same safe behavior the mechanism (a) limitation would otherwise defeat if `recency_rank` were populated.

**No new residual failure class was observed this session** beyond what §0 already names — `NB-H-06`'s reachability under D1 is the same class (b), not a new one.

---

## 10. Result interpretation — the eight questions

1. **How much of A2.8C's detection/delivery bottleneck does D1 recover?** Detection recall rises from 15.5% (D0) to 58.3% (D1) — D1 recovers roughly 3.8× as many ground-truth references as the existing wired path, out of the 84.8% (71/84 `SILENT_STEP1_MISS`) that A2.8C identified as the dominant real-path failure. Resolution coverage rises from 0% to 13.1% at C1 (8.3% at C2) — meaningfully above zero, but still well below A2.8C's oracle-condition ceiling (55.95%/30.95%), because detection alone does not supply everything RAR's cascade can use (§11 item 1).
2. **What incremental capability, if any, does D2 provide beyond D1?** **None measured** (§8) — D2's one successful detection is a strict subset of D1's own detections.
3. **What does D2 cost?** ~150ms average latency and one real model call per turn, versus D1's zero model calls and sub-millisecond deterministic execution, for zero measured incremental benefit on this corpus.
4. **Which residual failures remain detector-owned?** The 35 `neither_detects` references (§8) at C1 — cases where D1's grammatical-shape mechanisms found nothing (e.g., references requiring genuine world knowledge or paraphrase D1's shape rules cannot catch) and D2 also found nothing.
5. **Which failures move downstream into existing RAR?** All 49 D1-detected references reach RAR; of those, 24 (C1) become `MISSED_RESOLVABLE_CASE` and 1 (`NB-H-06`) becomes the pre-existing `INCORRECT_CONFIDENT_BINDING` limitation (§9) — these are RAR-owned outcomes once detection succeeds, not detector failures.
6. **Are new unsafe behaviours introduced?** No new *mechanism* — `NB-H-06`'s binding is the same already-verified mechanism (b) limitation, now reachable (§9 finding 1). Zero `INVENTED_CANDIDATE`, zero boundary violations, across all 1,029 rows.
7. **What is the smallest demonstrated successful resolution path for each observed class?** For the 11 (C1) references D1 newly resolves correctly: `deterministic detector (D1) → existing RAR` is a demonstrated, zero-model-call, sub-millisecond sufficient path — a candidate cheap resolution path per Phase 9's ant-colony framing, not yet architecture. For the 35 `neither_detects` references: no cell in this experiment demonstrates a sufficient path; the missing capability is not yet identified (§11 item 3).
8. **Is another capability actually missing?** Yes, for the 35 `neither_detects` cases and the 24 `MISSED_RESOLVABLE_CASE` cases — but this experiment does not identify *what* that capability is, only that D1 and D2 both fail to supply it. **Per Phase 8's explicit instruction, this is not grounds to propose a larger model** — see §12.

---

## 11. Unresolved evidence gaps

1. **Why D1-detected references still produce 24 (C1) `MISSED_RESOLVABLE_CASE` rather than resolving** was not individually audited this session (same open item as A2.8C verification §11 item 1, now recurring for D1's population) — plausible contributors include Level 6's `clear_margin >= 0.5` threshold, D1's own `coarse_type` mapping being coarser than the oracle's `intended_type`, and cases where D1's detected span differs textually from the human-marked span in a way that changes which tokens reach Level 6. Not disentangled here.
2. **D2's structured-output stability across repeated runs is `UNMEASURED`** (§6) — the 3.8% call rate could plausibly vary somewhat run-to-run given the model's evident unreliability; whether it is stably ~4% or noisily anywhere from 0–15% was not tested with repeated batches.
3. **The 35 `neither_detects` references were not individually characterized** — whether they share a common linguistic shape (world-knowledge paraphrase, cross-sentence anaphora, etc.) that a future, still-deterministic D1 extension could plausibly catch, or whether they are genuinely heterogeneous, is open.
4. **CPU/VRAM footprint for D2 was not measured this session** — RAM was (measured directly from Needle's own response field), but CPU and any GPU/VRAM usage were not instrumented.
5. **D1's precision (41.9–45.0%) means roughly half its detected spans are false positives or unattributed** — this experiment measured the rate but did not characterize what those false positives look like (harmless K-category near-misses vs. spans that could plausibly mislead a future integration). Not characterized here.

---

## 12. Recommended next experimental question (not implemented)

Given §10's answers — D1 recovers a real, substantial share of the detection bottleneck at zero model cost; D2 adds nothing measured; a real residual (35 `neither_detects`, 24 `MISSED_RESOLVABLE_CASE` at C1) remains — the smallest next honest question, per Phase 8's "identify the missing capability first" discipline, is:

> **What do the 35 corpus references that neither D0, D1, nor D2 ever detects have in common — and is that commonality itself a bounded, generalizable linguistic shape (extendable within D1's existing deterministic discipline), or does it require information D1's grammar-only approach cannot in principle supply?**

This question does not presuppose a larger model is needed; it asks whether D1's own ceiling has been reached or whether D1 itself has more room to generalize before any escalation is considered. **Not designed or implemented in this document.**

---

## Summary for User Review

**Executed, per the frozen A2.8D plan:** D0 (existing `TurnFrame`, unmodified), D1 (a new, generalizable deterministic detector — 6 shape-based mechanisms, none tuned against this corpus's wording), and D2 (Needle 3, strictly narrow signal-only schema with no `candidate_id` field, run against its real available runtime). All three crossed with C1/C2/C3, RAR called exactly once per detected reference, completely unmodified throughout.

**Corpus integrity:** hash matched before and after (`0ea54473...b07380`). Ground truth never fed to RAR in any cell. **0 boundary violations** across 1,029 telemetry rows — neither detector ever leaked a candidate ID.

**Headline:** D1 raises detection recall from **15.5% → 58.3%** and resolution coverage from **0% → 13.1%** (C1) at zero model-call cost. **D2 (Needle 3) is genuinely available at runtime but calls its tool in only 3.8% of 79 cases, detects 1/84 references, and supplies zero incremental capability beyond D1** — every reference D2 ever caught, D1 also caught. `INVENTED_CANDIDATE = 0` throughout.

**Residual RAR limitations:** all six previously-verified cases remain individually traceable, none silently masked, none repaired. One (`NB-H-06`) becomes reachable for the first time under D1 (because D1 detects it where D0 never did) — reported as the pre-existing limitation surfacing, not a new D1 defect, per the task's explicit scoring instruction. Two (`NB-J-02`, `NB-J-04`) resolve correctly under D1 specifically because D1's candidate pool never populates `recency_rank` (a deliberate boundary choice, not a fix) — a documented mechanistic interaction, not a repair.

**Recommended next question:** characterize the 35 corpus references no detector ever catches, before considering any larger mechanism. **Not implemented.**

**Files created:** `scripts/m35_a2_8d_detector_d1.py`, `scripts/m35_a2_8d_needle_inner_runner.py`, `scripts/m35_a2_8d_detector_d2_needle.py`, `scripts/m35_a2_8d_run.py`, `scripts/m35_a2_8d_score.py`, `docs/plans/M35_URIV1_A2_8D_TELEMETRY.json`, `docs/plans/M35_URIV1_A2_8D_AGGREGATES.json`, this report.
**Files modified:** none.
**Production files touched:** none — `uri_v1/turn/` untouched (confirmed empty `git diff --stat`); protected legacy repository untouched except read-only subprocess invocation of its pre-existing `.venv-needle` interpreter.
**No commit. No push. No architecture change. No next-experiment implementation.**

Stopped at `VERIFICATION_READY`.
