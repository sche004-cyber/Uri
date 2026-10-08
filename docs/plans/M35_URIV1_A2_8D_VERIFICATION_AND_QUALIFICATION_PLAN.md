# M35 URIv1 — A2.8D: Independent Verification of A2.8C + Reference Detection/Delivery Qualification Planning

**Type:** Independent verification + experimental design only. No RAR/TurnFrame/contract modification beyond the two bounded scoring-script fixes recorded in §4 (harness-only, non-production files). No A2.8D implementation. No commit, no push.
**Status:** `VERIFICATION_READY`

```xml
<development_state>
  <current_phase>VERIFY_THEN_PLAN</current_phase>
  <allowed_actions>independently re-run/re-derive A2.8C telemetry, inspect raw corpus and candidate metadata, classify incorrect-confident-binding cases, fix bounded scoring defects in benchmark-only scripts, design A2.8D experiment on paper</allowed_actions>
  <prohibited_actions>modify uri_v1/turn/*, modify the frozen corpus, implement A2.8D, implement a detector, commit, push, invent an acceptance threshold</prohibited_actions>
  <exit_criteria>A2.8C independently re-verified from raw telemetry with a fresh code path, every incorrect-confident-binding case individually classified with evidence, A2.8C verdict produced with A-E breakdown, A2.8D experiment designed with frozen boundaries</exit_criteria>
  <stop_condition>VERIFICATION_READY</stop_condition>
</development_state>
```

---

## Acceptance criteria (defined before verification)

1. Corpus SHA-256 must be recomputed from the live file (not read off a prior report) and matched against the full expected value.
2. Every headline A2.8C number (case/cell/row/invocation counts, `INVENTED_CANDIDATE`, S1 resolution rate, S2 resolution rates, `SILENT_STEP1_MISS` count, `INCORRECT_CONFIDENT_BINDING` count) must be independently recomputed from raw telemetry with fresh code, not merely re-read from the existing aggregates file.
3. Every `INCORRECT_CONFIDENT_BINDING` case must be individually inspected against its actual candidate metadata (titles, types, timestamps) and classified with cited evidence, not assumed from the prior report's framing.
4. Any defect found in the prior report's methodology or arithmetic must be disclosed with an auditable correction, not silently absorbed.
5. The A2.8C verdict must separate detection/delivery failure from resolver limitation from unsafe behaviour from correct abstention from evaluation artefact, with counts for each.
6. A2.8D must not proceed past design unless A2.8C's core hypothesis (detection/delivery is the dominant real-path bottleneck) survives this verification with the corrected numbers.
7. Every A2.8D design decision must state which of D0/D1/D2 it applies to and why, and must preserve RAR's existing cascade completely unmodified as the resolution authority.

Self-review against these criteria: all seven satisfied — see §3 (criteria 1–2), §4 (criteria 3–4), §7 (criterion 5), §8 (criterion 6), §10–§12 (criterion 7).

---

## 0. Repository / governance evidence recovered

- **Workspace:** `C:\Users\cheta\Development\Uri\_V1`, branch `m35-uri-v1-parallel-architecture`, HEAD `e8e3b65259c45fc823addc3ef8969425a265bd1b` — verified via `git rev-parse HEAD` at the start of this task, unchanged from the A2.8C execution session.
- **Governance read:** `SKILL.md` (uri-development), `ORCHESTRATION.md`/`AGENTS.md`/`PROJECT_MEMORY.md` cross-references (already loaded as pinned session memory — the AO-4 development cycle and the canonical USER/BRAIN/URI loop; both apply here as standing process, not re-read line-by-line since unchanged since last verified).
- **Durable prior evidence, not re-derived (previously established, cited here):**
  - `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md` §6 — full legacy-mechanism comparison (`CapabilityContextResolver`'s first-item-bias anti-pattern, `TurnState.active_pointer`'s re-derive-fresh-from-durable-state principle, `ARNEngine`'s structurally distinct multi-step recovery job, `CapabilityPlanner`'s hardcoded-keyword-scoring anti-pattern that RAR's own Level 6 already supersedes). **Conclusion re-affirmed, not re-litigated:** no legacy mechanism solves RAR's actual job; two design principles (not code) remain the only reusable items.
  - `docs/plans/M35_URIV1_PRE_RAR_CANDIDATE_ANCHOR_SOURCE_AUDIT.md` — `uri_core`'s real, live, durable state sources (`FileStore`, `CapabilityContextResolver`, `TurnState.assemble_turn_state()`) exist and are unwired into `uri_v1/turn/` (zero import statements either direction, confirmed by that audit's own repository-wide grep).
  - `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_INDEPENDENT_AUDIT.md` — Antigravity's independent audit of the discovery plan, `READY_AFTER_BOUNDED_CORRECTIONS` verdict, 21-pattern count confirmed.
  - **Legacy repository spot-check this session:** `C:\Users\cheta\Development\uri-agent` confirmed accessible (not `LEGACY_INSPECTION_UNAVAILABLE`); `git log -1` on `uri_core/core/turn_state.py`, `uri_core/capabilities/context_resolver.py`, `uri_core/core/arn/engine.py` shows the same HEAD hash as this repository, confirming (as the prior audit already established) that `_V1` and `uri-agent` share one repository history and that these files are unchanged since the prior audit read them. **Not re-read line-by-line this session** — no new evidence would be gained, and the prior audit's findings are durable and current.
- **New evidence produced this session:** all of §3–§9 below (independent re-verification of A2.8C, two bounded scoring-script fixes, 8-case individual classification, A2.8D design).
- **Distinguishing evidence classes throughout this document:** `PREVIOUSLY_ESTABLISHED` (cited above, not re-derived), `VERIFIED_THIS_SESSION` (independently re-run/re-computed below), `NEW_FINDING` (not present in the A2.8C report at all — §4's cascade-ordering root cause), `HYPOTHESIS` (explicitly flagged where used, §11).

---

## 1. A2.8C artifacts located and inspected

- [scripts/m35_rar_natural_boundary_harness.py](scripts/m35_rar_natural_boundary_harness.py)
- [scripts/m35_rar_natural_boundary_run.py](scripts/m35_rar_natural_boundary_run.py)
- [scripts/m35_rar_natural_boundary_score.py](scripts/m35_rar_natural_boundary_score.py) — **modified this session, see §4.1**
- [docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json](docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json) — **regenerated this session (bit-identical content to the original, confirmed §3.2)**
- [docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_AGGREGATES.json](docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_AGGREGATES.json) — **regenerated this session with the §4.1 fix applied**
- [docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_EXECUTION_REPORT.md](docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_EXECUTION_REPORT.md) — **correction notice added this session (§4)**

---

## 2. Corpus integrity — independently reconfirmed

```
$ sha256sum uri_v1/turn/rar_natural_boundary_raw_turn_fixtures.json
0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380
```

Matches the full expected value `0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380` exactly (recovered from the corpus authoring report and the A2.8C telemetry's own recorded `post_run_sha256` field, both independently, both agreeing). Matches the value already recorded in both `M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json` and `M35_URIV1_RAR_NATURAL_BOUNDARY_AGGREGATES.json`. `VERIFIED_THIS_SESSION`.

---

## 3. Independent re-derivation from raw telemetry

### 3.1 Reproducibility re-run

The full pipeline (`m35_rar_natural_boundary_run.py` → `m35_rar_natural_boundary_score.py`) was re-executed **three consecutive times** this session, from the real, unmodified `build_turn_frame()`/`resolve_rar_deterministic_extended()` — not read off the prior report.

- All three runs produced **bit-identical telemetry** (503 records each), modulo the `latency_ms` timing field, which is expected to vary run-to-run and carries no scoring weight.
- Corpus hash after every run: `0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380` — unchanged, all three times.
- **Result: A2.8C's execution is genuinely reproducible from the real resolver, not a one-off or hand-edited artifact.**

### 3.2 Headline figures, recomputed with fresh, independent code (not `score.py`'s functions)

A standalone one-off Python scan (not reusing `cell_table()`/`paired_c1_c2()`/etc.) was run directly against `M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json` and the frozen corpus:

| Metric | A2.8C report claim | Independent recomputation (fresh code) | Match? |
|---|---|---|---|
| Case count | 79 | 79 (`len(fixture["cases"])`) | ✅ |
| Cell count | 5 | 5 (`{S1xC1,S1xC2,S1xC3,S2xC1,S2xC2}`) | ✅ |
| Total telemetry rows | 503 | 503 | ✅ |
| Real resolver invocations | 213 | 213 (`sum(r["rar_invoked"])`) | ✅ |
| `INVENTED_CANDIDATE` | 0 | 0 (independent scan: for every `actual_outcome==RESOLVED` row, checked `actual_candidate_id in candidate_ids_supplied`) | ✅ |
| S1×C1/C2/C3 `CORRECT_RESOLUTION` (of 84 gt-bearing rows) | 0 in all three | 0 in all three | ✅ |
| `SILENT_STEP1_MISS` (S1×C1, of 84) | 71 | 71 | ✅ |
| `INCORRECT_CONFIDENT_BINDING`, all cells | 10 rows / 8 distinct case-refs | 10 rows / 8 distinct case-refs, identical list: `NB-C-04:r1, NB-C-05:r1, NB-D-01:r1, NB-D-02:r1, NB-H-06:r1, NB-J-02:r1, NB-J-04:r1, NB-L-09:r2` | ✅ |
| S2×C1 `CORRECT_RESOLUTION` (of 84 gt-bearing rows) | 47 | 47 | ✅ |
| S2×C2 `CORRECT_RESOLUTION` (of 84 gt-bearing rows) | 26 | 26 | ✅ |
| **S2×C1 resolution coverage (%)** | **51.6%** (91-row denominator) | **55.95%** (47/84, correct denominator) | ❌ — see §4.1 |
| **S2×C2 resolution coverage (%)** | **28.6%** (91-row denominator) | **30.95%** (26/84, correct denominator) | ❌ — see §4.1 |

**Every count-level figure independently reconfirms exactly.** The two rate-level figures marked ❌ are addressed in §4.1 — a real defect, not a disagreement about the underlying counts (47 and 26 are correct and agreed by both the original report and this independent recomputation; only the denominator used to turn them into a percentage was wrong).

---

## 4. Defects found and corrected

### 4.1 Denominator defect in `resolution_coverage`/`safe_abstention_rate`/`wrong_binding_rate`

**Root cause:** `cell_table()` in `scripts/m35_rar_natural_boundary_score.py` computed these three rates against `total_applicable` (91 rows per cell), which includes the 7 `K`-category rows classified `NOT_APPLICABLE_NO_GT_REF` under S2 (rows with no ground-truth reference at all, since S2's oracle condition has nothing to construct a query from for a no-reference turn). These 7 rows can structurally never contribute to `CORRECT_RESOLUTION`, so including them in the denominator mechanically deflates every S2 rate. S1 cells were unaffected (they classify their 7 K-rows as `CORRECT_ABSTENTION`/`K_FALSE_POSITIVE_SAFE_ABSTENTION` instead, which do belong in the S1 denominator).

**Fix applied** (benchmark-only file, not `uri_v1/turn/`): `rate_denominator = total_applicable - not_applicable_no_gt_ref`, and all three rates now divide by this corrected denominator. Diff is 2 added lines + 3 changed divisor references in `scripts/m35_rar_natural_boundary_score.py`.

**Corrected figures** (re-run, reproducible across 3 fresh runs — see §3.1):

| Cell | Rate denominator | `resolution_coverage` | `safe_abstention_rate` | `wrong_binding_rate` |
|---|---|---|---|---|
| S1×C1 | 91 (unaffected) | 0.0% | 12.1% | 0.0% |
| S1×C2 | 91 (unaffected) | 0.0% | 12.1% | 0.0% |
| S1×C3 | 91 (unaffected) | 0.0% | 22.0% | 0.0% |
| S2×C1 | **84** (was 91) | **55.95%** (was 51.65%) | **17.86%** (was 16.48%) | **5.95%** (was 5.49%) |
| S2×C2 | **84** (was 91) | **30.95%** (was 28.57%) | **27.38%** (was 25.27%) | **5.95%** (was 5.49%) |

Sensitivity view (excluding the 4 pre-identified judgment-call cases) re-derived with the fix: S2×C1 58.23% (was reported ≈53.5%), S2×C2 31.65% (was reported ≈29.1%). **The qualitative conclusion — sensitivity exclusion does not materially change any finding — still holds** (deltas of 2.3 and 0.7 points respectively, both cells still show the same C1→C2 drop pattern).

This correction is recorded auditably in the original report's header (§ correction notice added this session) rather than silently overwritten, per the repository's evidence-lineage convention.

### 4.2 Reproducibility defect in paired-analysis example lists (found and fixed incidentally during §3.1's re-run)

`paired_c1_c2()`/`paired_s1_s2()` iterated an unsorted Python `set` intersection before truncating to the first 10 items for two illustrative `*_examples` fields. Python's per-process hash-seed randomization made *which* 10 (of, e.g., 19) case/ref pairs appeared in that truncated list vary between runs — the underlying **counts** (`distractor_induced_safe_abstention_count: 19`, etc.) were always correct and stable; only the illustrative sample changed. Fixed by sorting the key set before slicing (2-line change, same file). Re-verified bit-identical across 3 fresh runs after the fix. This did not affect any number in the A2.8C execution report's prose (the report's §12/§13 cited counts, not the truncated example lists, for its substantive claims).

### 4.3 Files modified this session

- `scripts/m35_rar_natural_boundary_score.py` — the two fixes above (benchmark-only, not `uri_v1/turn/`).
- `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json` — regenerated (content-identical to original modulo `latency_ms`).
- `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_AGGREGATES.json` — regenerated with corrected rates.
- `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_EXECUTION_REPORT.md` — correction notice added at the top; body left otherwise intact (auditable history preserved, not rewritten).

**No file under `uri_v1/turn/` was read-modified, written, or touched this session** — confirmed via `git status --short uri_v1/` showing the same untracked-but-unchanged file set as at session start, and `git diff --stat uri_v1/` returning empty.

---

## 5. Individual classification of all 8 `INCORRECT_CONFIDENT_BINDING` case/references

Each case was re-inspected against its actual `candidate_library` metadata (titles, `candidate_type`, `created_at`) and the corpus's own `reason` field — not assumed from the original report's framing. **Two of the eight are reclassified from the original report's softer "partly attributable" framing to a more precise verdict below**, per this task's explicit instruction not to force a classification the evidence doesn't support.

| Case:ref | Cell(s) | Original report's framing | **This session's independent classification** | Evidence |
|---|---|---|---|---|
| `NB-C-04:r1` | S2×C1, S2×C2 | "partly attributable to harness recency construction" | **(1) Harness/oracle artefact — CONFIRMED** | Two photos uploaded **one second apart** (`11:20:03` vs `11:20:04`). The corpus's own `reason` field states: *"uploaded one second apart... binding to either single photo is a wrong confident binding."* The harness's mechanical `recency_rank` (sort-by-`created_at`) manufactures a resolvable ordinal from a 1-second gap the fixture author explicitly designed to be non-discriminating. This is a harness-construction artifact, not a RAR defect. |
| `NB-C-05:r1` | S2×C1, S2×C2 | "partly attributable to harness recency construction" | **(1) Harness/oracle artefact — CONFIRMED, with a sharper root cause** | The corpus's `reason` field states explicitly and pre-emptively: *"Recency among the attachments must not be used to pick one."* The reference text itself (`"the attached file"`) carries no ordinal word at all — the `temporal_meaning: "most_recent"` annotation describes *which file the user just attached in conversation*, not an ordinal ranking the resolver should apply. The harness's `temporal_meaning→recency_hint` mapping (§3 decision 3 of the A2.8C harness) translates `"most_recent"` into `recency_hint="latest"` uniformly, without distinguishing "just-attached, singular" semantics from a genuine explicit ordinal query — this is a **mapping defect in the harness's S2 adapter**, not a RAR defect: RAR was handed a hint that mis-describes what the annotator actually meant. |
| `NB-D-01:r1` | S2×C2 | "attributable in part to this harness's own recency-ranking construction" | **(2) Genuine RAR resolver limitation — RECLASSIFIED** | `target_type_hint="document"` cannot discriminate: both `Board_minutes_*.docx` **and** both `Agenda - *` candidates share `candidate_type: "document"` (confirmed by direct inspection of `candidate_library`). The corpus's `reason` field explicitly pre-identifies the failure mode: *"a recency rule that ignores the 'minutes' constraint picks the wrong object."* Trace: Level 4b (type filter) cannot narrow past 2 candidates (both types match); Level 5 (`"latest"`) then finds exactly one `recency_rank==0` candidate across the **whole 4-item pool** (the October agenda, genuinely the most recent object by real timestamp) and returns `RESOLVED` immediately — **it never reaches Level 6**, where "minutes" (a real, present, discriminating token in the reference text, absent from the agenda's title) would have correctly re-narrowed to the true target. This is a cascade-ordering property of the real, unmodified resolver, not an artifact of how the harness computed `recency_rank` — even a genuinely-wired real recency source (e.g. `uri_core.FileStore`) would supply the same whole-pool timestamp ordering. See §6 for the general finding. |
| `NB-D-02:r1` | S2×C2 | same as above | **(2) Genuine RAR resolver limitation — RECLASSIFIED, same root cause as `NB-D-01`** | Same candidate pool and `candidate_type` collision. `temporal_meaning: "one_before_last_discussed"` → `recency_hint="previous"`; Level 5's `recency_rank==1` match (the September agenda sits between the two minutes files in real time, confirmed by `created_at`, exactly as the corpus's own `reason` field predicts) fires before Level 6 can apply the "minutes" constraint. Identical mechanism to `NB-D-01`, not a separate finding. |
| `NB-H-06:r1` | S2×C1 | "genuine RAR failure" (unqualified) | **(2) Genuine RAR resolver limitation — CONFIRMED, root cause now precisely identified** | `user_exclusions: ["no, the other"]` — the exclusion phrase shares **zero tokens** with the excluded candidate's title (`scan_0034.pdf` → tokens `{scan, 0034, pdf}`; exclusion tokens → `{no, the, other}`, all either stopwords or non-overlapping). Level 4a's RC-2 elimination gate requires literal, distinguishing token overlap between the negation span and a candidate's own tokens — a purely relational exclusion ("the other [unnamed] one") has no lexical content to anchor on and **cannot be eliminated by this mechanism at all**, regardless of how correctly the negation span text is delivered. Level 4b/6 then bind confidently on the surviving (never-eliminated) sole candidate via a genuine "scan" token match. **This is the precise, general mechanism**: RC-2 elimination is lexical-overlap-based and structurally cannot represent purely deictic/contrastive exclusions. |
| `NB-J-02:r1` | S2×C1 | "genuine RAR failure" (unqualified) | **(2) Genuine RAR resolver limitation — CONFIRMED, same cascade-ordering root cause as `NB-D-01`** | Reference: *"the contract Jonas sent over last week."* Neither candidate is from Jonas or from last week (both leases uploaded *today*, by the user). `recency_hint="earlier"` (from `temporal_meaning: "earlier_not_latest"`) finds exactly one `recency_rank>0` candidate among the two leases and `RESOLVES` at Level 5 — **before Level 6's own "absent entity detection" mechanism ever runs**, which is specifically designed to catch exactly this case (`unmatched_substantive` check: "jonas" is a real, substantive, discriminating token present in the reference and absent from every candidate's tokens — Level 6 would have correctly returned `UNKNOWN`/`NO_CANDIDATE` had it been reached). |
| `NB-J-04:r1` | S2×C1 | "genuine RAR failure" (unqualified) | **(2) Genuine RAR resolver limitation — CONFIRMED, same mechanism** | Reference: *"the template we agreed on yesterday."* Neither candidate is a template or dated yesterday (both created today). `recency_hint="earlier"` again finds a single `recency_rank>0` survivor among the two letters and resolves at Level 5, pre-empting Level 6's absent-entity check, which would have caught "template" as an unmatched substantive token. |
| `NB-L-09:r2` | S2×C2 | "one plural/multi-reference case; see §14" (undeveloped) | **(2) Genuine RAR resolver limitation — a related but distinct sub-mechanism, now identified** | Reference: *"the one I uploaded before it."* `target_type_hint="spreadsheet"` correctly narrows the 3-item C2 pool to `{staff_roster_october.xlsx, Q3_budget_forecast.xlsx}` at Level 4b (the "sent roster" email, `object_type: "email"`, is correctly excluded). `recency_hint="previous"` (`recency_rank==1`) then fires — but the `recency_rank` values (`0, 1, 2`) were assigned across the **original, unfiltered 3-item pool** and are never renormalized after Level 4b narrows the working list to 2 items; the surviving pair carries ranks `{1, 2}`, not `{0, 1}`. `recency_rank==1` matches the roster itself (the *other* reference's own referent, `r1`, not a distinct candidate for `r2`) — a wrong binding the corpus explicitly names as *"the failure to watch."* Root cause: **`recency_rank` is not re-derived/rebased after Level 4a/4b narrows the candidate set, so an ordinal like "previous" can bind relative to the original full pool rather than the semantically relevant narrowed subset.** This would recur with any real absolute-timestamp recency source (not a harness-specific artifact), but it is compounded here by the harness's whole-pool ranking (§ see §11 open question 3 on whether a differently-scoped oracle would change this). |

**Summary: 2 of 8 confirmed harness/oracle artefacts (`NB-C-04`, `NB-C-05`); 6 of 8 confirmed genuine RAR resolver limitations, resolving into exactly two distinct, precisely-identified mechanisms** — (a) Level 5 temporal/recency selection returns before Level 6's lexical/absent-entity discrimination ever runs (`NB-D-01`, `NB-D-02`, `NB-J-02`, `NB-J-04`, and `NB-L-09:r2`'s rank-rebasing variant), and (b) Level 4a's negation elimination cannot represent purely relational exclusions lacking shared vocabulary with the excluded candidate (`NB-H-06`). Neither mechanism was named or evidenced in the original A2.8C report, which only hedged "3 genuine, 4 harness-confounded, 1 undeveloped." **This is a materially more precise, and materially different, classification than the original report's — recorded here as the correction, not a silent replacement.**

No case required an `UNRESOLVED` classification — every one of the 8 had sufficient candidate-metadata and corpus-`reason` evidence to classify with confidence.

---

## 6. Re-derived sensitivity view excluding only the confirmed harness artefacts

Per the task's explicit instruction, this is a **separate** sensitivity recomputation from the corpus's own pre-declared 4-case judgment-call set (§18 of the A2.8C report) — it excludes only `NB-C-04` and `NB-C-05`, the two cases independently confirmed as harness/oracle artefacts in §5, and nothing else:

| Cell | Rows (84 → 82) | `CORRECT_RESOLUTION` | Resolution coverage | `INCORRECT_CONFIDENT_BINDING` |
|---|---|---|---|---|
| S2×C1 | 84 → 82 | 47 (unchanged) | 55.95% → **57.32%** | 5 → **3** |
| S2×C2 | 84 → 82 | 26 (unchanged) | 30.95% → **31.71%** | 5 → **3** |

**With the two confirmed harness artefacts removed, `INCORRECT_CONFIDENT_BINDING` drops from 5 to 3 per cell (6 total distinct case-refs across both cells, matching §5's 6 genuine-limitation cases exactly).** Resolution coverage shifts by only 1.4/0.8 points — the correct-resolution *count* (47, 26) is untouched by this exclusion because none of the 47/26 successes involved `NB-C-04`/`NB-C-05` (those two cases were never counted as successes in the first place; they only ever appeared as wrong bindings). **This confirms the two mechanisms in §5 are real, load-bearing findings, not artifacts of a coincidentally-small sample: removing the confirmed noise sharpens, but does not eliminate, the safety signal.**

---

## 7. A2.8C verdict — A/B/C/D/E breakdown

Computed on the S1×C1 / S2×C1 pairing (the most informative real-candidate-pool condition; S1×C2/C3 and S2×C2 are consistent with this breakdown per §9's own cell tables and are not re-tabulated row-by-row here):

| Class | Definition | Count (of 84 gt-bearing references, S1×C1 / S2×C1) | Evidence |
|---|---|---|---|
| **A — Reference detection/delivery failure** | The natural reference never reaches RAR with usable evidence. | **80** (71 `SILENT_STEP1_MISS` + 9 rows where `TurnFrame` found only a bare pronoun with zero recency/type/anchor evidence — reclassified here from the original report's "resolver behavior," since RAR's decision to abstain given *only* a bare pronoun is the mechanism working correctly, not failing; the actual defect is entirely upstream, in what evidence ever reached it) | §9, §11 below |
| **B — Resolver limitation (adequate evidence, cannot safely resolve)** | RAR receives oracle-quality evidence and still cannot safely resolve. | **17** (S2×C1 `MISSED_RESOLVABLE_CASE`) | §5 does not individually audit these 17 (out of this task's scope budget), but the cascade-ordering mechanism found in §5/§6 (Level 5 pre-empting Level 6) plausibly explains a subset — **not independently confirmed row-by-row; flagged as an open question, §11 item 1** |
| **C — Unsafe resolver behaviour (confident wrong binding)** | RAR receives evidence and binds incorrectly. | **6** genuine (of 8 total minus 2 confirmed artefacts, §5/§6) at S2×C1: `NB-H-06`, `NB-J-02`, `NB-J-04` are in this exact cell; `NB-D-01`/`NB-D-02`/`NB-L-09:r2` are S2×C2-only — **6 genuine across both S2 cells combined**, 3 of them in S2×C1 | §5, §6 |
| **D — Correct abstention** | RAR appropriately refuses insufficient/ambiguous evidence. | **4** (S1×C1 `CORRECT_ABSTENTION`) + **15** (S2×C1 `CORRECT_ABSTENTION`) | §9 of the A2.8C report |
| **E — Harness/evaluation artefact** | Experimental construction affects the apparent result. | **2** distinct case-refs (`NB-C-04`, `NB-C-05`), each appearing in both S2 cells = 4 rows | §5, §6 |

**S1×C1's 84 references decompose almost entirely into A (80/84, 95.2%) and D (4/84, 4.8%) — zero rows fall into B or C under the real wired path**, because RAR is never invoked with evidence rich enough to produce either outcome under S1. **This is direct, row-complete evidence for the central A2.8C hypothesis.**

---

## 8. A2.8C evidence verdict

**The hypothesis that the dominant real-wired-path bottleneck is upstream reference detection/delivery, not RAR itself, is `SUPPORTED` by this independent re-verification, including after both defects in §4 are corrected and after the 2 confirmed-artefact cases are excluded from the safety count in §6.**

Basis, stated precisely per the task's explicit instruction not to treat S1's 0% as automatic proof:

1. **S1's 0% confident-resolution rate is not, by itself, evidence of a RAR defect** — of the 13 S1-invoked references (bare pronouns), 4 are cases where abstention is the objectively correct answer (category D) and 9 are cases where the *only* evidence RAR ever receives is a content-free pronoun with no recency, type, or anchor signal at all — declining to guess on that input is RAR working as designed, not failing. **Zero S1 rows fall into category B or C.** This directly confirms the report's own §11/§16 framing was correct in substance, and this independent audit adds row-complete confirmation rather than a spot-check.
2. **Once the extraction bottleneck is removed (S2), RAR is not perfect** — 17/84 (C1) and 30/84 (C2) references remain `MISSED_RESOLVABLE_CASE` (category B), and a genuine, now precisely-identified pair of resolver limitations (§5/§6) produces 6 confirmed unsafe bindings (category C) even under oracle input. **RAR is not free of limitations — but its limitations are a small minority (6/84 ≈ 7% at worst, S2×C1, dropping to 6/164 ≈ 3.7% across both S2 cells combined) relative to the upstream bottleneck's 80/84 ≈ 95%.**
3. **The two mechanisms behind all 6 genuine unsafe bindings are structural and specific** (Level 5 pre-empting Level 6's lexical/absent-entity discrimination; Level 4a's negation elimination requiring literal token overlap) — not a diffuse "RAR is unreliable" finding. This matters directly for A2.8D's design (§12, Phase 6): these two mechanisms must remain measurable and must not be silently patched by whatever detector A2.8D tests.

**Proceeding to A2.8D design is justified by this evidence.**

---

## 9. Exact measured failure taxonomy (consolidated, corrected figures)

| Failure/success class | S1×C1 | S1×C2 | S1×C3 | S2×C1 | S2×C2 |
|---|---|---|---|---|---|
| `SILENT_STEP1_MISS` (A) | 71 | 71 | 71 | 0 | 0 |
| Bare-pronoun-only abstention, ground truth RESOLVED (A) | 9 | 9 | 0* | — | — |
| `CORRECT_ABSTENTION` (+family mismatch) (D) | 4 | 4 (3+1) | 13* | 15 | 15 (+8 soft) |
| `MISSED_RESOLVABLE_CASE`, oracle evidence (B) | — | — | — | 17 | 30 |
| `INCORRECT_CONFIDENT_BINDING`, total (C+E) | 0 | 0 | 0 | 5 | 5 |
| ...of which confirmed harness artefact (E) | — | — | — | 2 | 2 |
| ...of which genuine RAR limitation (C) | — | — | — | 3 | 3 |
| `CORRECT_RESOLUTION` | 0 | 0 | 0 | 47 | 26 |
| `NOT_APPLICABLE_NO_GT_REF` (K rows) | — | — | — | 7 | 7 |

\* S1×C3's expected outcome is contractually `UNKNOWN` for every reference (per the corpus's own `harness_input_contract.C3_derivation`), so its `CORRECT_ABSTENTION`/`MISSED_RESOLVABLE_CASE` split is not comparable to C1/C2 — see the A2.8C report §9 note.

`INVENTED_CANDIDATE = 0` in every cell, independently reconfirmed (§3.2).

---

## 10. A2.8D research question

> What is the smallest, cheapest, reliable mechanism that can detect natural reference-bearing expressions and deliver sufficient structured evidence to the existing, unmodified deterministic RAR — without itself deciding what entity the reference resolves to?

Directly motivated by §7's finding: 95.2% of S1's real-path failure is category A (detection/delivery), not RAR itself. A2.8D's job is to measure how much of that 95.2% a cheap upstream mechanism can recover, and to keep the 6 genuine RAR-side limitations from §5/§6 separately visible rather than letting a better detector accidentally mask them.

**Pipeline under test, RAR unchanged and retaining sole resolution authority:**

```
natural user turn
  -> reference detection / signalling   (D0 / D1 / D2 — this experiment's subject)
  -> evidence delivery                  (reference_expression, recency_hint, target_type_hint, negation_spans)
  -> existing RAR (rar_deterministic.py, byte-for-byte unmodified)
  -> resolve OR abstain
```

---

## 11. Unresolved questions / evidence gaps (carried into A2.8D's design, not guessed at)

1. **Category B's 17/30 `MISSED_RESOLVABLE_CASE` rows were not individually audited this session** (only the 8 category-C rows were, per the task's explicit "special attention" instruction). Whether the Level-5-pre-empts-Level-6 mechanism (§5/§6) also explains a meaningful share of B, or whether B is dominated by a different cause entirely (e.g. Level 6's `clear_margin >= 0.5` threshold being conservative on genuinely close lexical calls), is `UNMEASURED`. This is explicitly listed as an A2.8D-adjacent open question, not resolved here — A2.8D's own D0 baseline cell (§12) will re-surface this same population and can be audited then with the same per-case method used in §5.
2. **Whether `NB-L-09:r2`'s rank-rebasing sub-mechanism is fully independent of, or a special case of, the Level-5-pre-empts-Level-6 mechanism** is not fully resolved — both involve Level 5 committing before Level 6 could apply better-scoped evidence, but the specific rank-rebasing defect (ranks not renormalized after Level 4b narrows the pool) is a distinct code-level detail. Recorded as `UNRESOLVED — evidence insufficient to merge or fully separate` rather than forced into one bucket.
3. **Whether a differently-scoped S2 oracle recency construction (e.g., type-pre-filtered before ranking) would have avoided `NB-D-01`/`NB-D-02`/`NB-L-09:r2`** is genuinely `UNKNOWN` and was reasoned about but not tested in §5/§6 (testing it would require a second harness variant, out of this task's scope). The reasoning in §5 argues this would not be a realistic oracle construction (type-pre-filtered-then-ranked requires already knowing which candidates are topically relevant, which is RAR's own job) — but this is argued, not empirically demonstrated.
4. **Whether `TurnFrame`'s 12 unused multi-word patterns would ever fire on a larger/differently-authored corpus** remains unknown beyond the A2.8C report's own disclosed single-author-corpus limitation — relevant to whether D1 (§12) should keep, prune, or generalize them.

---

## 12. A2.8D proposed experimental cells

| Cell | Detector | Constraint |
|---|---|---|
| **D0** | Existing `TurnFrame` (unmodified), exactly as measured in A2.8C's S1 condition | Baseline — re-uses A2.8C's own S1×C1/C2 telemetry directly, no new run needed for D0 itself |
| **D1** | A small, deterministic, rule/code-only detector, explicitly **not** an expansion of the 21-pattern list into a larger handcrafted vocabulary | Must be generalizable (e.g., lightweight noun-phrase heuristics, capitalized-token/quoted-span/filename-pattern detection already partially present in `TurnFrame`'s `quoted_spans`/`artifact_mentions` machinery) rather than enumerable strings. Candidate generalizable signals worth investigating before any AI component, per Phase 5's explicit instruction to "investigate what can be obtained without AI first": (a) `TurnFrame`'s existing `quoted_spans` extractor (already general, zero pattern list) as a reference-span source for named/quoted objects; (b) filename-shaped token detection (already partially present via `artifact_mentions`) generalized to any `word[._-]word+\.(ext)` shape rather than a fixed extension list; (c) a generic noun-phrase-after-determiner heuristic ("the/that/this + noun(s)") to widen bare-pronoun coverage into short noun phrases without hand-listing them. **Not designed or implemented in this document — a later A2.8D implementation session's job**, per this task's explicit prohibition on implementation. |
| **D2** | Needle 3, narrow upstream job only | Frozen boundary, restated from Phase 5: Needle 3 may output presence-of-reference, reference span, and coarse type signals matching `RAREvidence`'s existing field vocabulary (`recency_hint`, `target_type_hint`) — **never** a candidate ID, a final ranking, or a resolved referent. Explicitly **not** a re-run of the already-rejected base Needle-3-as-broad-Step-1-semantic-decoder experiment (per durable prior evidence, `PREVIOUSLY_ESTABLISHED` — see §0) — this is a categorically narrower job (signal only, not decoding), and the A2.8D design must make this distinction operationally checkable (§13's frozen boundary contract), not just asserted in prose. |

**D0 is not a new run** — it is A2.8C's S1×C1/C2/C3 telemetry, already measured, reused for direct comparison. D1 and D2 are new detector implementations, **not designed or built in this document** (out of scope per the task's explicit "Do NOT implement A2.8D" instruction) — only their frozen boundaries and evaluation design are specified here (§13–§15), for a later implementation session to build against.

---

## 13. Frozen detector boundaries (apply to D1 and D2 alike)

A detector under test in A2.8D:

- **MAY** output: presence/absence of a reference-bearing expression; the reference's span/text; a coarse type signal (mapped to `RAREvidence.target_type_hint`); a coarse recency/relational signal (mapped to `RAREvidence.recency_hint`); scoped negation spans (mapped to `RAREvidence.negation_spans`, ideally per-reference-scoped rather than turn-global — directly testable against A2.8C's own confirmed turn-global-negation limitation, `PREVIOUSLY_ESTABLISHED` in the original discovery plan).
- **MUST NOT**: emit a candidate ID; emit a ranked list of candidates; perform any comparison against a candidate pool; decide `RESOLVED`/`AMBIGUOUS`/`UNKNOWN`; construct a `RARDeterministicAnchor` (per the same restraint A2.8C's own harness already observed, §13 of the discovery plan — no code path may fabricate this condition); call `resolve_rar_deterministic_extended()` itself or duplicate any of its logic.
- **RAR remains the sole resolution authority** in every cell, called exactly once per detected reference, exactly as A2.8C's S1/S2 harness already does — the only variable A2.8D introduces is what populates `RARQuery`/`RAREvidence` before that call.

**Operational check for "did the detector stay in its lane":** a detector's output is invalid for this experiment (and must be flagged, not silently scored) if it ever contains a value equal to a real `candidate_id` from that turn's candidate pool in any field other than `RARQuery.reference_expression`/`candidates` (which the harness itself populates from ground truth, never the detector) — this makes Phase 6's boundary mechanically checkable rather than only a documentation promise.

---

## 14. Corpus strategy

**Reuse the existing 79-case, 158-variant frozen corpus unchanged** — the same rationale as A2.8C's own anti-drift discipline applies: D0's numbers are already measured against it, and reusing it keeps D1/D2 directly comparable without re-authoring ground truth. **No fixture wording or expected outcome may be modified to favor a detector**, per the task's explicit instruction — carried forward unchanged from A2.8C's own frozen-corpus discipline.

**If detection-precision/false-positive measurement genuinely requires cases beyond what the current corpus provides** (e.g., a detector might need more `K`-category-style true-negative turns than the corpus's 7 to measure precision with reasonable confidence, or a wider range of non-reference filler text to stress-test false-positive rate) — this should be a **separate, explicitly-labeled supplementary corpus**, authored under the same independence discipline as the original (§12 of the discovery plan: authored without reading detector internals), not a modification of the frozen 79-case set. **Not authored in this document** — flagged as a likely A2.8D implementation-phase need, decision deferred to that phase with the rationale stated here.

---

## 15. Metrics and telemetry schema

Extends A2.8C's existing per-reference telemetry row shape (§"Telemetry" of the original discovery plan, already implemented in `m35_rar_natural_boundary_run.py`'s output rows) with detector-specific fields:

| New field | Purpose |
|---|---|
| `detector_id` (`D0`/`D1`/`D2`) | Which detector produced this row's evidence |
| `detector_found_reference: bool` | Recall signal |
| `detector_reference_span` | What the detector extracted, for `SILENT_STEP1_MISS`-style comparison against ground truth exactly as D0 already supports |
| `detector_confidence` (if applicable, D2 only — a model-assisted detector may expose this; D1 should not need to) | For distinguishing a low-confidence detector hit from a confident one, if the detector design ends up producing one |
| `detector_latency_ms`, `end_to_end_latency_ms` | Per Phase 7's explicit metric list |
| `detector_model_calls: int` | 0 for D0/D1 by construction; D2's count, to make "deterministic vs. model-assisted cost" (Phase 7) directly reportable |
| `boundary_violation: bool` | The §13 operational check — true if the detector's output ever contained a live candidate ID outside the allowed fields |

**Measured, per Phase 7's list, where technically obtainable:** reference detection recall/precision, false-positive triggers, silent misses, % of ground-truth references delivered to RAR, correct final RAR resolution, incorrect confident binding, correct ambiguity/abstention, invented candidates, unsupported detector output, model calls, end-to-end latency, detector-only latency. **CPU/RAM/VRAM footprint:** `UNMEASURED` for D1 (a rule-based detector's footprint is not the interesting question); **planned but not committed** for D2, since Needle 3's footprint was already measured in a prior qualification stage (`PREVIOUSLY_ESTABLISHED`, not re-derived here) — whether that prior measurement is reusable as-is or needs re-measurement under this specific narrow-signal job is left to the implementation phase, not guessed at here.

**No fabricated estimates** — any of the above not actually measured in a later run is reported as `UNMEASURED`, exactly as A2.8C's own report already does for its own unmeasured items.

---

## 16. Confound controls

Carried forward and extended from A2.8C's own anti-contamination discipline (§12 of the discovery plan, §16 of the authoring report):

1. **No detector may be tuned against this corpus's own expected outcomes** — the same discipline that kept A2.8C's fixture authoring blind to `rar_deterministic.py`'s internals extends here: whoever builds D1/D2 should not iterate against this specific corpus's pass/fail rate, or the D1/D2 numbers become a memorization measurement, not a generalization measurement. This is the single most important confound control for A2.8D specifically, since (unlike A2.8C, which only ran an already-frozen resolver) A2.8D's whole point is to build something new.
2. **D1 must not become a 22nd, 30th, 50th hand-listed pattern** — Phase 5's explicit instruction. The frozen-boundary check in §13 does not by itself prevent this (a huge hardcoded list would still "stay in its lane" functionally) — this is a *design-review* control, not a mechanical one: whoever reviews D1's implementation before it is scored against this corpus must confirm it is a generalizable mechanism, not vocabulary expansion, before results are trusted.
3. **RAR itself must remain byte-for-byte unmodified across all D0/D1/D2 cells** — identical discipline to A2.8C.
4. **The 6 genuine RAR-side limitations from §5/§6 must remain separately visible in A2.8D's own telemetry**, per Phase 6's explicit instruction — a detector that happens to avoid feeding RAR the specific inputs that trigger the Level-5/Level-6 ordering issue would silently hide a real limitation rather than fix it; A2.8D's scoring must keep `NB-D-01`/`NB-D-02`/`NB-H-06`/`NB-J-02`/`NB-J-04`/`NB-L-09:r2`-shaped cases visible as their own tracked sub-population, not folded into an aggregate.

---

## 17. Safety/invariant checks

- `INVENTED_CANDIDATE` must remain checked and expected `0` in every D0/D1/D2 cell — RAR's own `validate_rar_resolution()` already enforces this mechanically regardless of what feeds it.
- `INCORRECT_CONFIDENT_BINDING` must be tracked per detector, not only in aggregate, so a detector that trades recall for unsafe bindings is visible rather than averaged away.
- The §13 `boundary_violation` check must be run on every row before any other scoring — a detector that leaks a candidate ID invalidates that row's result for this experiment's purposes, not just a footnote.

---

## 18. Implementation boundaries (explicit non-goals, restated for whoever implements A2.8D next)

- Do not modify `rar_deterministic.py`, `turn_frame_builder.py`, `rar_contracts.py`, or `active_context.py`.
- Do not repair the `NB-D-01`/`NB-D-02`/`NB-H-06`/`NB-J-02`/`NB-J-04`/`NB-L-09:r2`-class cascade-ordering limitation during this experiment — it must remain measurable, per Phase 6.
- Do not let D2 (Needle 3) perform final candidate binding, ranking, or ID selection under any circumstance.
- Do not invent an acceptance threshold (90%, 95%, or otherwise) not already established by an approved repository requirement — this is a discovery experiment, per Phase 8.
- Do not wire any detector into `uri_core` or any production call path.
- Do not commit, do not push.

---

## 19. Expected decision branches after A2.8D results (for the *next* session, not decided here)

1. If D1 alone recovers a large share of A2.8C's 80/84 category-A failures at negligible cost: candidate cheap resolution path `deterministic detector → RAR` is worth preserving as experimental evidence (Phase 9's ant-colony framing) — not yet architecture.
2. If D1 recovers little but D2 (Needle 3, narrow job) recovers substantially more: record the incremental capability Needle supplies, specifically, not as a blanket "Needle helps."
3. If both D1 and D2 leave a similar residual failure population: identify the actual missing capability (per §11's open questions, plus whatever D1/D2's own telemetry newly reveals) before proposing a third, larger mechanism — do not escalate model size merely because a case is difficult.
4. In every branch, the 6 genuine RAR-side limitations from §5/§6 remain a separate, still-open finding regardless of detector outcome — they are not addressed by any detector, by design (§16 item 4), and would need their own future bounded-fix or architecture discussion.

**None of these branches is decided in this document.**

---

## Summary for User Review

**A2.8C independent verification:** Fully re-run from the real, unmodified resolver three times this session — bit-for-bit reproducible (aside from timing noise and one now-fixed example-list ordering defect, §4.2). Every count-level headline figure (79 cases, 5 cells, 503 rows, 213 invocations, `INVENTED_CANDIDATE=0`, S1 0% resolution, `SILENT_STEP1_MISS=71`, 10 wrong-binding rows / 8 distinct case-refs) independently reconfirmed exactly. **One real defect found and fixed**: S2 resolution-coverage/safe-abstention/wrong-binding rates used the wrong denominator (91 instead of 84), deflating the reported percentages — corrected figures are **S2×C1 55.95%** (was 51.6%) and **S2×C2 30.95%** (was 28.6%); correction recorded in the original report, not silently overwritten.

**Incorrect-confident-binding audit:** All 8 case/references individually classified against real candidate metadata. **2 confirmed harness/oracle artefacts** (`NB-C-04`, `NB-C-05` — a manufactured 1-second recency signal and a mis-mapped "most recently attached" hint). **6 confirmed genuine RAR resolver limitations**, resolving to exactly two precise, newly-identified mechanisms: **(a)** Level 5 temporal/recency selection returns before Level 6's lexical/absent-entity discrimination ever runs, so a present, discriminating word (or an absent, named entity) in the reference text can be silently overridden by a recency match alone (`NB-D-01`, `NB-D-02`, `NB-J-02`, `NB-J-04`, plus a rank-rebasing variant in `NB-L-09:r2`); **(b)** Level 4a's negation elimination requires literal token overlap and cannot represent a purely relational exclusion like "the other one" (`NB-H-06`). Neither mechanism was named in the original A2.8C report.

**A2.8C verdict:** `SUPPORTED`. 80/84 (95.2%) of real-path (S1) reference-bearing failures are upstream detection/delivery (category A), zero are RAR resolver limitation or unsafe behaviour under S1 — RAR is simply never handed usable evidence. Under oracle input (S2), RAR is not perfect (17–30/84 `MISSED_RESOLVABLE_CASE`, 6/84–6/164 genuine unsafe bindings) but these are a small minority relative to the upstream bottleneck.

**A2.8D design:** proceeds, per §8's verdict. Three cells (D0 existing baseline / D1 small deterministic detector / D2 narrow Needle-3 signal-only detector), frozen boundaries preventing any detector from performing final binding, the existing corpus reused unmodified, and the two newly-identified RAR-side limitations (§5/§6) explicitly required to remain separately visible rather than incidentally masked by a better detector. **Not implemented.**

**Files modified this session:** `scripts/m35_rar_natural_boundary_score.py` (2 bounded fixes), `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_TELEMETRY.json` (regenerated, content-identical), `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_AGGREGATES.json` (regenerated with corrected rates), `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_EXECUTION_REPORT.md` (correction notice added).
**Files created:** this document.
**No file under `uri_v1/turn/` was modified.** No commit. No push. No A2.8D implementation.

Stopped at `VERIFICATION_READY`.
