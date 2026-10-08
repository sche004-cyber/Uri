# M35 URIv1 — A2.8E: Residual Reference-Detection Failure Characterization

**Type:** Forensic characterization only. No detector implementation, no D1 integration, no RAR modification, no model qualification, no commit, no push. One bounded benchmark-harness defect fixed and disclosed (§3).
**Governing evidence:** `docs/plans/M35_URIV1_A2_8D_EXECUTION_REPORT.md` (corrected this session — see its own correction notice), `docs/plans/M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md`, `docs/plans/M35_URIV1_A2_8D_TELEMETRY.json` / `..._AGGREGATES.json`.
**Status:** `VERIFICATION_READY`

```xml
<development_state>
  <current_phase>FORENSIC_CHARACTERIZATION</current_phase>
  <allowed_actions>inspect raw telemetry and corpus, re-derive figures independently, fix a demonstrated benchmark-harness defect and re-run, classify residual cases by evidence-derived taxonomy, audit D1 for overfitting, characterize the RAR/candidate-metadata interaction</allowed_actions>
  <prohibited_actions>implement a new detector, integrate D1 into uri_v1/turn or uri_core, modify RAR, modify D1 itself, qualify a new model, commit, push, select an architecture</prohibited_actions>
  <exit_criteria>exact residual set verified from raw telemetry, every case individually analyzed with evidence, taxonomy derived (not imposed), generalizability classified per case, D1 overfitting audited, RAR/candidate-metadata interaction characterized, capability map produced, next experimental question recommended</exit_criteria>
  <stop_condition>VERIFICATION_READY</stop_condition>
</development_state>
```

---

## Acceptance criteria (defined before analysis)

1. Every headline A2.8D figure this task is asked to "verify before analysis" must actually be recomputed from raw telemetry, not copied from the execution report's prose.
2. The residual set must be the references undetected by **all three** tested paths (D0, D1, D2) — not a two-way comparison silently treated as three-way.
3. Any defect found in how the residual set was computed must be fixed (if the fix is bounded and benchmark-only), disclosed with before/after figures, and the corrected set used for all downstream analysis — not both sets left ambiguously in play.
4. Categories in §6 must be derived from what the 27 cases actually show, checked against each case individually, not asserted from the phenomenon list the task suggests.
5. Every generalizability classification in §7 must cite the specific regex/mechanism gap or capability gap that explains the miss, verified by directly running D1's code against that case's text.
6. D1's own six mechanisms must be independently re-read for corpus-specific content, not assumed clean because the original report claimed genericity.
7. No conclusion selects a model or proposes new architecture; the deliverable is a capability map and a next question only.

Self-review: all seven met. Criterion 1 → §2. Criterion 2 → §2 (fixes a real one-way-vs-two-way conflation in the original task framing). Criterion 3 → §3 (a genuine harness bug found and fixed, changing the residual count from the task-stated 35 to 27). Criterion 4 → §6 (derived from §5's per-case evidence, not imposed). Criterion 5 → §5/§7 (every classification cites a directly-run code test). Criterion 6 → §9. Criterion 7 → §12–§14.

---

## 0. Evidence recovered (not re-derived where already durable)

- **Workspace:** `C:\Users\cheta\Development\Uri\_V1`, branch `m35-uri-v1-parallel-architecture`, HEAD `e8e3b65259c45fc823addc3ef8969425a265bd1b` — unchanged throughout this session and all prior A2.8C/A2.8D work.
- **Read this session:** `M35_URIV1_A2_8D_EXECUTION_REPORT.md`, `M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md` (re-confirmed, not re-derived), `M35_URIV1_A2_8D_TELEMETRY.json` (raw, inspected directly — not summarized secondhand), `scripts/m35_a2_8d_detector_d1.py` (re-read in full for §9), `scripts/m35_a2_8d_run.py` (re-read; this is where the §3 defect was found), the frozen corpus (`uri_v1/turn/rar_natural_boundary_raw_turn_fixtures.json`, re-read per-case for all 27 residual cases).
- **Durable, not re-derived:** A2.8C's corrected figures (`M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md` §0), `TurnFrame`'s 21-pattern mechanism (`turn_frame_builder.py`, unchanged), `rar_deterministic.py`'s cascade structure and the two previously-verified genuine limitation mechanisms (Level 5 pre-empting Level 6; Level 4a's token-overlap-only negation elimination).
- **Legacy repository:** `C:\Users\cheta\Development\uri-agent` — accessible (confirmed via `ls` in this session), not newly inspected beyond what prior sessions already established as durable evidence (`CapabilityContextResolver`, `TurnState.active_pointer`, `FileStore`) — cited where relevant in §12, not re-read line-by-line since unchanged. **Not `LEGACY_INSPECTION_UNAVAILABLE`.**
- **Not re-litigated:** the design rationale for D1's six mechanisms, RAR's cascade level ordering, the frozen A2.8D experimental design — all treated as given.

---

## 1. Repository state

- HEAD unchanged: `e8e3b65259c45fc823addc3ef8969425a265bd1b`.
- Corpus SHA-256, verified at the start of this task: `0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380` — matches expected, unchanged throughout.
- **Files modified this session:** `scripts/m35_a2_8d_run.py` (one bounded defect fix, §3), `docs/plans/M35_URIV1_A2_8D_TELEMETRY.json` and `..._AGGREGATES.json` (regenerated with the fix applied), `docs/plans/M35_URIV1_A2_8D_EXECUTION_REPORT.md` (correction notice added, body left intact per the auditable-correction convention).
- **Files created this session:** this document.
- **No file under `uri_v1/turn/` was touched** — confirmed via `git status --short uri_v1/` (same untracked-but-unchanged file set as every prior session) and `git diff --stat uri_v1/` (empty). D1 itself (`scripts/m35_a2_8d_detector_d1.py`) was **not modified** — read-only inspection for §9 only, per the explicit "do not modify D1" instruction.
- No commit, no push.

---

## 2. Verification of A2.8D headline claims (recomputed from raw telemetry, not copied)

| Claim | Recomputed from `M35_URIV1_A2_8D_TELEMETRY.json` directly | Verdict |
|---|---|---|
| 1,029 telemetry rows | 1,029 (before the §3 fix) | `VERIFIED` (pre-fix) |
| `INVENTED_CANDIDATE = 0` | 0, scanned directly (`actual_outcome==RESOLVED` and `candidate_id not in candidate_ids_supplied`) | `VERIFIED` |
| 0 detector boundary violations | 0 (`sum(r["boundary_violation"])`) | `VERIFIED` |
| Corpus hash unchanged | `0ea54473...b07380` pre- and post-run, both recorded in the telemetry's own fields and independently recomputed via `sha256sum` | `VERIFIED` |
| D0 detection recall 15.5% | 13/84 = 15.48% | `VERIFIED` (rounding) |
| D1 detection recall 58.3% | **49/84 = 58.33% — but this figure is itself built on a defective attribution check, §3** | `PARTIALLY_INCORRECT` — corrected to **67.9%** (57/84) |
| D2 detection recall 1/84 = 1.2% | Same defect affects D2's attribution | `PARTIALLY_INCORRECT` — corrected to **3/84 = 3.57%** |
| D2 call rate 3/79 | 3/79 = 3.8%, independently re-run (a fourth Needle batch this session, §2.1) | `VERIFIED` |
| D2 successful detection is a strict subset of D1 | Re-verified after the §3 fix (§2.2) | `VERIFIED`, still holds |
| **"35/84 references remain undetected by all tested paths"** (as stated in this task's own prompt) | **The original report's §8 `neither_detects: 35` bucket paired only D1 against D2 — it never included D0 in that specific count.** The true three-way intersection (D0 ∧ D1 ∧ D2 all miss), recomputed directly from raw telemetry, is **27** (after the §3 fix; it was 33 before the fix, using the original one-directional matching). | `CORRECTED` — see §3 |

### 2.1 D2 re-run this session

Re-ran the Needle 3 batch fresh (independent of the stored telemetry) to re-verify §5.4 of the A2.8D execution report was not a one-off artifact:

- Fresh 79-case batch: **3/79 calls made (3.8%)**, all 3 with `reference_detected: true`. Matches the previously reported figure exactly.
- `avg latency ms: 151.5`, `avg peak_ram_mb: 101.3` — matches previously reported figures exactly.

**D2's severe unreliability is reconfirmed, not a fluke of one run.**

### 2.2 Post-fix D1-vs-D2 overlap re-check

With the §3 fix applied, D1 now detects 57/84 references and D2 detects 3/84. All 3 of D2's successful detections remain a strict subset of D1's 57 — **D2 still supplies zero incremental detection capability beyond D1**, and this conclusion is now measured on the corrected, larger D1 detection set, not weakened by the correction.

---

## 3. Defect found and fixed: one-directional span-attribution check

**Root cause:** `find_matching_found_expr()` in `scripts/m35_a2_8d_run.py` accepted a detector's found span as matching a ground-truth reference only if the found span was a **substring of** the ground-truth span (`expr.lower() in gt_lower`). This silently mis-scored every case where a detector's span **contains** the ground-truth span but also extends beyond it — the exact shape D1's grammar-based determiner-NP mechanism produces whenever it captures one extra trailing word. Directly demonstrated: for `NB-I-04` ("open the invoice please"), D1 detects `"the invoice please"` — the true reference (`"the invoice"`) is fully present, but the one-directional check requires the reverse containment and scored this as `SILENT_DETECTION_MISS`.

**Why A2.8C's own harness (`scripts/m35_rar_natural_boundary_run.py`) has the same one-directional shape but was not affected by this defect:** its found-expression source (`TurnFrame`'s 21 fixed literal patterns) only ever produces short, literal substrings that are always shorter than or equal to any longer ground-truth span they could plausibly match — the containment direction the bug assumes always held there by construction. D1's grammar-shape mechanism is not bounded that way; it was the correct exposure condition for this defect, not a new bug introduced by this forensic pass.

**Fix:** bidirectional substring check (`expr_lower in gt_lower or gt_lower in expr_lower`). Applied to `scripts/m35_a2_8d_run.py` only — a benchmark-harness file, not `uri_v1/turn/`. Full pipeline re-run (D0/D1/D2 × C1/C2/C3), corpus hash re-verified unchanged before and after, result reproduced identically across two consecutive fresh runs (`D0 miss set`, `D1 miss set`, `D2 miss set`, and their triple intersection are bit-identical both times).

**Before/after impact:**

| Metric | Before fix | After fix |
|---|---|---|
| D1 detection recall (C1) | 49/84 = 58.3% | **57/84 = 67.9%** |
| D1 resolution coverage (C1, `CORRECT_RESOLUTION`) | 11/84 = 13.1% | **12/84 = 14.3%** |
| D2 detection recall | 1/84 = 1.2% | **3/84 = 3.6%** |
| D0-catches-but-D1-misses (a spurious "D1 regression" the bug created) | 2 cases (`NB-C-02:r1`, `NB-B-05:r1`) | **0 cases** — D1's coverage is now confirmed a strict superset of D0's, as it should be by design (D1 extends D0, never narrows it) |
| Triple-intersection residual (undetected by D0 ∧ D1 ∧ D2) | 33 | **27** |

**This correction is recorded in `M35_URIV1_A2_8D_EXECUTION_REPORT.md`'s own header** (added this session), per the repository's auditable-correction-history convention — the original report's body is left as originally written, not rewritten.

**Why this is benchmark infrastructure, not URI architecture:** the defect lives entirely in `m35_a2_8d_run.py`'s scoring/attribution logic, a script that exists only to grade detector output against corpus ground truth after the real, unmodified `resolve_rar_deterministic_extended()` has already run. It never touched `TurnFrame`, `rar_deterministic.py`, `rar_contracts.py`, or D1's own detection logic (`m35_a2_8d_detector_d1.py`) — D1 was already correctly finding these references; the harness was incorrectly grading what it found.

---

## 4. The exact 27-reference residual set (undetected by D0, D1, and D2)

Confirmed reproducible across two independent fresh runs post-fix. Ground truth was not altered to produce this list — it is read directly from the frozen corpus's own `ground_truth_references`.

| # | Case:ref | Category | Raw text (relevant portion) | Ground-truth span | Intended type | Temporal meaning |
|---|---|---|---|---|---|---|
| 1 | `NB-A-01:r1` | A_explicit_reference | "pull up invoice INV-20417" | `invoice INV-20417` | pdf | none |
| 2 | `NB-A-03:r1` | A_explicit_reference | "where are we with PO-5521?" | `PO-5521` | approval | none |
| 3 | `NB-A-04:r1` | A_explicit_reference | "use file 38e1b5c4-...d115 for this" | `file 38e1b5c4-a97d-4f26-b0e8-12c6d3f9d115` | pdf | none |
| 4 | `NB-A-05:r1` | A_explicit_reference | "Re INV-20388 - did we ever pay that one?" | `INV-20388` | pdf | none |
| 5 | `NB-B-03:r1` | B_immediate_conversational | "Swap 3 and 4 round, and AOB should be the very last item" | `null` (implicit; `implicit_antecedent: "the October agenda draft just produced"`) | document | last_discussed |
| 6 | `NB-B-05:r2` | B_immediate_conversational | "Put that in an email to Priya please" | `Priya` | record | none |
| 7 | `NB-C-03:r1` | C_attachment | "check Daniel's against the job spec" | `Daniel's` | pdf | none |
| 8 | `NB-F-02:r1` | F_named_object | "what time is Daniel's interview again?" | `Daniel's interview` | calendar_event | none |
| 9 | `NB-F-03:r1` | F_named_object | "update the harbour street lease with the new rent figure" | `the harbour street lease` | null | none |
| 10 | `NB-G-01:r1` | G_person_entity | "has she been here long enough to take a whole week off?" | `she` | record | last_discussed |
| 11 | `NB-G-03:r1` | G_person_entity | "what's Tom's extension number?" | `Tom's` | record | none |
| 12 | `NB-G-04:r1` | G_person_entity | "Send Marcus Hale a copy of our insurance certificate" | `Marcus Hale` | record | none |
| 13 | `NB-G-04:r2` | G_person_entity | "Send Marcus Hale a copy of our insurance certificate" | `our insurance certificate` | pdf | none |
| 14 | `NB-H-02:r1` | H_negated_reference | "Use either of the CVs except Amara's" | `either of the CVs except Amara's` | pdf | none |
| 15 | `NB-I-02:r2` | I_multiple_plausible | "send it to Priya" | `Priya` | record | none |
| 16 | `NB-I-06:r2` | I_multiple_plausible | "Forward the letter to Priya when you get a sec" | `Priya` | record | none |
| 17 | `NB-J-01:r1` | J_missing_candidate | "What did Marcus say in his reply?" | `his reply` | email | none |
| 18 | `NB-J-03:r1` | J_missing_candidate | "What's the bottom line on September's P&L?" | `September's P&L` | report | none |
| 19 | `NB-L-01:r2` | L_natural_mixed | "Forward Q2_budget_forecast.xlsx to Marcus at Northwind" | `Marcus at Northwind` | record | none |
| 20 | `NB-L-02:r2` | L_natural_mixed | "send that list to Marcus" | `Marcus` | record | none |
| 21 | `NB-L-04:r1` | L_natural_mixed | "Send Priya my most recent letter" | `my most recent letter` | letter | most_recent |
| 22 | `NB-L-04:r2` | L_natural_mixed | "Send Priya my most recent letter" | `Priya` | record | none |
| 23 | `NB-L-08:r3` | L_natural_mixed | "Attach the signed lease and the insurance certificate to my reply to Priya" | `my reply to Priya` | email | none |
| 24 | `NB-L-10:r1` | L_natural_mixed | "Take the headline figures from the Q3 forecast" | `the Q3 forecast` | null | none |
| 25 | `NB-L-10:r2` | L_natural_mixed | "...drop them into the October agenda under item 3" | `the October agenda` | document | none |
| 26 | `NB-L-11:r1` | L_natural_mixed | "Put both CVs into one shortlist document" | `both CVs` | pdf | none |
| 27 | `NB-L-11:r2` | L_natural_mixed | "...but leave Daniel's offer letter alone for now" | `Daniel's offer letter` | letter | none |

For every row, `rar_invoked: false` in all of D0/D1/D2's telemetry — RAR was never reached for any of these 27, confirmed directly (not inferred) from the `rar_invoked` field of each corresponding telemetry row.

---

## 5. Case-by-case failure analysis (evidence, not assertion)

Every claim below was verified by directly invoking `detect_references()` (D1's real, unmodified function) against the case's actual `raw_user_text` in this session, not inferred from the telemetry alone.

**#1–4 (`NB-A-01`, `NB-A-03`, `NB-A-04`, `NB-A-05`) — alphanumeric code/ID references.** None of D1's six mechanisms has any rule for a bare alphanumeric code (`INV-20417`, `PO-5521`, `INV-20388`) or a UUID (`38e1b5c4-...`). Directly confirmed: running D1 against `"Can you pull up invoice INV-20417..."` produces only an unrelated bare-pronoun match on `"they"`; the code itself is invisible to every mechanism. Note on #3 (`NB-A-04`): D1 *does* detect a different, semantically-related span in the same sentence — `"the scanned contract"` (a valid determiner-NP match) — but the ground truth's canonical span is the UUID token, and the two spans share no substring in either direction, so this is scored as a miss for this specific ground-truth reference even though D1 found a co-referential alternative expression of the same real-world object. This is a benchmark-attribution nuance (the corpus marks one canonical span per reference; a detector that finds a different valid expression of the same referent is not credited) as well as a genuine detection gap (D1 still never recognizes the UUID/code form itself).

**#5 (`NB-B-03`) — zero surface reference.** The corpus's own `secondary_signals` field marks this case `no_surface_reference`; `ground_truth_references[0].human_marked_span` is `null`. There are no words in the raw text that refer to the intended object at all — the reference exists only via `implicit_antecedent`, a description of "what a human would infer was just discussed." No surface-text mechanism, however general, can detect a reference that has no surface form. This is categorically different from every other case in this set.

**#6, #15, #16, #20, #22 (`NB-B-05:r2`, `NB-I-02:r2`, `NB-I-06:r2`, `NB-L-02:r2`, `NB-L-04:r2`) — bare capitalized proper name, no determiner, no possessive marker.** All five are the single word "Priya" or "Marcus" alone, never preceded by "the/this/that" or followed by `'s`. D1's determiner-NP mechanism requires a determiner; its bare-pronoun mechanism only covers the closed 9-pronoun set; neither fires on a bare proper noun. Directly confirmed: `detect_references("Send Marcus Hale a copy of our insurance certificate")` returns an empty tuple.

**#12, #19 (`NB-G-04:r1`, `NB-L-01:r2`) — bare capitalized multi-word name/name-phrase.** Same root cause as the group above, extended to a two/three-word capitalized span ("Marcus Hale", "Marcus at Northwind") — still no determiner or possessive marker for D1 to anchor on.

**#7, #11, #27 (`NB-C-03`, `NB-G-03`, `NB-L-11:r2`) — possessive proper-noun NP ("Daniel's", "Tom's", "Daniel's offer letter").** A distinct, more specific syntactic shape from the bare-name group above: an English possessive marker (`'s`) attached to a proper noun, optionally followed by a head noun. D1 has no mechanism at all for this shape — it is not a determiner ("the/this/that/..."), not a bare pronoun, and not a plain capitalized name (it carries an extra orthographic marker, `'s`, that a bare-name mechanism would not by itself require). Directly confirmed: `detect_references("what's Tom's extension number?")` produces one spurious match (`"s Tom"`) from the **quoted-span mechanism's own apostrophe-matching bug** (§9 finding 2), not a genuine possessive-NP detection — the real reference is still missed.

**#8 (`NB-F-02`) — possessive proper-noun + head noun ("Daniel's interview").** Same root cause as the group above.

**#18 (`NB-J-03`) — possessive common-noun-phrase + non-letter token ("September's P&L").** Same possessive-marker gap, compounded by `P&L` containing an ampersand D1's word-shape character class does not accept (`[a-z][a-z\'\-]*` has no `&`).

**#13, #17, #21, #23 (`NB-G-04:r2`, `NB-J-01`, `NB-L-04:r1`, `NB-L-08:r3`) — possessive-pronoun-determiner NP ("our insurance certificate", "his reply", "my most recent letter", "my reply to Priya").** D1's determiner-NP regex's determiner group is hardcoded to `(the|this|that|these|those)` — English possessive pronouns (my/your/our/his/her/its/their) are a real, closed, generalizable determiner class D1 simply never included. This is the **same general mechanism** (determiner-headed NP) D1 already implements for demonstratives — not a new capability, an incomplete word list within an existing one. Directly confirmed: `detect_references("What did Marcus say in his reply?")` returns an empty tuple; changing nothing else, the phrase `"his reply"` is grammatically identical in shape to `"the invoice"` (which D1 *does* catch), differing only in the determiner word.

**#10 (`NB-G-01`) — missing pronoun "she".** D1's `_BARE_PRONOUN_RE` set is `{it, this, that, them, him, her, they, these, those}` — "she" (and "he") are simply absent. This is a pure completeness gap in an already-closed, already-implemented English pronoun class, not a new linguistic phenomenon. Directly confirmed by reading the regex definition in `m35_a2_8d_detector_d1.py`.

**#14, #26 (`NB-H-02`, `NB-L-11:r1`) — quantifier-headed NP ("either of the CVs except Amara's", "both CVs").** D1's determiner set does not include quantifiers ("both", "either", "all", "any", "neither"). `NB-L-11:r1` ("both CVs") is the simpler case — a straightforward quantifier + plural noun, directly analogous to the possessive-pronoun gap above (an incomplete determiner-class word list). `NB-H-02` is materially more complex: `"either of the CVs except Amara's"` combines a partitive quantifier ("either of the X") with an embedded exception clause ("except Amara's") — the ground truth's canonical span covers the whole construction, which is not a simple determiner+NP shape at all, even with a wider quantifier list.

**#9, #24, #25 (`NB-F-03`, `NB-L-10:r1`, `NB-L-10:r2`) — regex right-boundary fragility on longer/digit-containing noun phrases.** Directly confirmed by running D1 against both raw texts:
- `NB-F-03`: `"update the harbour street lease with the new rent figure, ..."` — D1 finds only `"the new rent figure"`, never `"the harbour street lease"`. Cause: the greedy noun-phrase body, when it cannot find a satisfying right boundary (a stopword/punctuation) within its 7-word cap while consuming "harbour street lease with the new rent figure" (8 words, no internal stopword), fails the *entire* match at that starting position rather than falling back to the longest valid shorter prefix (`"the harbour street lease"` alone, which would have matched had `finditer` been given the chance to try it). This is a regex-engineering gap — no fallback-to-shortest-valid-match behavior — not a missing linguistic category.
- `NB-L-10:r1`: `"the Q3 forecast"` is missed because the word-shape character class (`[a-z][a-z\'\-]*`) does not accept digits, so "Q3" cannot be consumed as an NP-body word at all, breaking the match at that point.
- `NB-L-10:r2`: `"the October agenda"` is a clean, otherwise-matchable phrase, but it is missed for the same right-boundary-fragility reason as `NB-F-03` — the sentence continues "...under item 3", and the digit in "item 3" prevents the greedy match from ever finding a satisfying stop point, causing the whole attempt (starting from "the October agenda") to fail rather than fall back to the valid shorter phrase.

---

## 6. Evidence-derived taxonomy (not imposed in advance)

Eight classes, each derived directly from §5's evidence, not from the task prompt's suggested phenomenon list (several of which — ellipsis, coordination, quantification, lexical paraphrase — turned out not to be independently present; what the evidence actually shows is narrower and more mechanical than that list implied):

| Class | Cases | Count |
|---|---|---|
| **T1 — Alphanumeric code/ID, no surrounding determiner** | `NB-A-01`, `NB-A-03`, `NB-A-04`, `NB-A-05` | 4 |
| **T2 — Bare capitalized proper name, no determiner/possessive marker** | `NB-B-05:r2`, `NB-G-04:r1`, `NB-I-02:r2`, `NB-I-06:r2`, `NB-L-01:r2`, `NB-L-02:r2`, `NB-L-04:r2` | 7 |
| **T3 — Possessive-'s proper/common-noun phrase** | `NB-C-03`, `NB-F-02`, `NB-G-03`, `NB-J-03`, `NB-L-11:r2` | 5 |
| **T4 — Possessive-pronoun-determiner NP** (an existing D1 mechanism's incomplete word list) | `NB-G-04:r2`, `NB-J-01`, `NB-L-04:r1`, `NB-L-08:r3` | 4 |
| **T5 — Quantifier-headed NP** (partly an incomplete word list, partly genuine added syntactic complexity) | `NB-H-02`, `NB-L-11:r1` | 2 |
| **T6 — Missing single pronoun in an already-implemented closed class** | `NB-G-01` | 1 |
| **T7 — Regex right-boundary fragility on longer/digit-containing NPs** | `NB-F-03`, `NB-L-10:r1`, `NB-L-10:r2` | 3 |
| **T8 — Genuinely no surface reference (discourse/session-state only)** | `NB-B-03` | 1 |
| **Total** | | **27** |

**T4 and T6 are not new capability gaps at all** — they are incomplete word lists inside a mechanism D1 already has and already uses successfully elsewhere in this same corpus. **T7 is an implementation-quality gap in the same existing mechanism**, not a new linguistic phenomenon. **T1, T2, T3, T5 are genuinely new syntactic shapes D1 has no mechanism for at all.** **T8 is categorically different from all the others** — no surface-text mechanism, however complete, could address it.

---

## 7. Generalizability classification (Phase 3)

| Class | Classification | Rationale |
|---|---|---|
| T1 (code/ID) | **YES_DETERMINISTIC** | An alphanumeric-code shape (`[A-Z]{2,4}-?\d{3,6}` and a UUID pattern) is a general orthographic regularity used across many real-world domains (invoice numbers, PO numbers, ticket IDs), not corpus-specific wording. Low false-positive risk given the distinctive shape. |
| T2 (bare proper name) | **POSSIBLY_DETERMINISTIC** | Capitalization-based proper-noun detection is a general orthographic heuristic, but carries real precision risk (sentence-initial capitalization, acronyms, brand names) that a naive rule would not resolve on its own — some additional structural signal (e.g., position after a preposition like "to X"/"from X", or after a verb like "Send X") would likely be needed to keep precision usable, and that additional structure was not designed or tested here. |
| T3 (possessive-'s NP) | **YES_DETERMINISTIC** | The `'s` marker is an unambiguous, purely orthographic English grammatical signal, materially lower false-positive risk than bare capitalization alone (T2) — a regex requiring `[A-Z][a-z]+'s` is general, not benchmark-specific. |
| T4 (possessive-pronoun determiner) | **YES_DETERMINISTIC** | Directly and trivially extends D1's own already-proven determiner-NP mechanism; possessive pronouns are a small, genuinely closed English word class, exactly analogous to the demonstratives D1 already handles. |
| T5 (quantifier NP) | **POSSIBLY_DETERMINISTIC** for the simple case (`"both CVs"` — a small closed quantifier-word extension, same shape as T4); **SEMANTIC_CAPABILITY_REQUIRED** for the compound case (`NB-H-02`'s "either of the X except Y" needs to represent an embedded exception clause as part of one reference span, which is a step beyond simple determiner-NP grammar). |
| T6 (missing pronoun) | **YES_DETERMINISTIC** | A pure omission in an already-complete, already-implemented closed class; the mechanism itself needs no new design. |
| T7 (regex fragility) | **POSSIBLY_DETERMINISTIC** | The underlying phenomenon (natural noun phrases containing digits, or exceeding a fixed word-count cap) is common and a fix is plausible within the same regex-engineering family (broaden the word-shape character class to accept digits; replace the fixed-cap greedy match with one that falls back to the longest valid prefix) — genuine care would be needed to avoid new over-matching, so this is not asserted as trivial. |
| T8 (no surface reference) | **SEMANTIC_CAPABILITY_REQUIRED** — more precisely, a **session/discourse-state capability**, not a linguistic-detection capability. No rewording of D1's grammar rules can find words that are not present in the text; what is needed is a mechanism for tracking "what was the most recent thing this turn/session produced," which is a different kind of capability (state-tracking) than anything D1's six mechanisms attempt. |

No case was classified `INSUFFICIENT_EVIDENCE`, `GENUINELY_AMBIGUOUS`, or `HARNESS_OR_GROUND_TRUTH_ISSUE` outright — every one of the 27 has a concrete, directly-demonstrated mechanical cause (§5). The `NB-A-04` UUID case (§5, #3) comes closest to a harness-attribution nuance (D1 found a valid alternative expression of the same referent) but the underlying detection gap for the UUID form itself is still real and independently confirmed, so it is kept in T1 rather than reclassified as a pure harness issue.

---

## 8. Cluster summary (Phase 4)

| Cluster | Count | Representative case | Common mechanism | Why D1 can't detect it today | Deterministic recovery feasible? | Additional info required | Existing URI mechanism that already has it? | Prior rejected experiment covering this? | Obtainable without another model? |
|---|---|---|---|---|---|---|---|---|---|
| T1 | 4 | `NB-A-01` | Alphanumeric code/ID shape | No code/ID regex exists in D1 at all | Yes | None beyond the regex itself | No — `TurnFrame`'s `explicit_number_patterns`/`ARTIFACT_PATTERNS` don't cover this shape either (checked: `EXPLICIT_NUMBER_PATTERNS` in `turn_frame_builder.py` matches bare digits/"one"/"two"/"three" only, not hyphenated alphanumeric codes) | No prior M35 stage tested this shape | Yes |
| T2 | 7 | `NB-B-05:r2` | Bare capitalized proper noun | No proper-noun mechanism in D1 at all | Partially (precision risk) | A structural co-occurrence signal (preposition/verb context) not yet designed | No — confirmed no capitalization-based NER exists anywhere in `uri_v1/turn/` (`turn_frame_builder.py`'s `ENTITY_PATTERNS` is a 2-item literal list, "Chief Warden"/"committee", not general capitalization detection) | No | Yes, in principle |
| T3 | 5 | `NB-C-03` | Possessive-'s NP | No possessive-marker mechanism in D1 | Yes | None beyond the regex | No | No | Yes |
| T4 | 4 | `NB-J-01` | Possessive-pronoun determiner | Incomplete word list in an existing mechanism | Yes (trivial) | None — extend existing determiner set | Not applicable (D1's own mechanism, just incomplete) | Not applicable | Yes |
| T5 | 2 | `NB-L-11:r1` (simple case) / `NB-H-02` (compound case) | Quantifier NP / embedded exception clause | Incomplete word list (simple case); no clause-embedding grammar (compound case) | Yes (simple case) / Uncertain (compound case) | Clause-boundary representation for the compound case | No | No | Yes (simple case); open (compound case) |
| T6 | 1 | `NB-G-01` | Missing single pronoun | Pure omission | Yes (trivial) | None | Not applicable | Not applicable | Yes |
| T7 | 3 | `NB-F-03` | Regex engineering fragility | Fixed-cap greedy match with no shorter-prefix fallback; digit-exclusive word class | Yes | None beyond regex rework | Not applicable | No | Yes |
| T8 | 1 | `NB-B-03` | No surface reference | Not a surface-detection problem at all | No (not by any surface mechanism) | Session/turn state: "what was just produced" | **Yes — `uri_core.core.turn_state.py`'s `TurnState._project_active_pointer` already re-derives exactly this concept fresh from durable session state** (durable prior evidence, `M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md` §6 — cited, not re-verified this session since unchanged) — but it is disconnected from `uri_v1/turn/` (also already-established evidence, not new to this session) | No | Not via a detector at all — this needs state, not language processing |

**Six of eight clusters (T1, T3, T4, T5-simple, T6, T7 — 4+5+4+1+1+3 = 18 of 27 references) are plausibly recoverable by extending D1's existing deterministic-mechanism family, without a new capability class.** T2 (7 references) needs a genuinely new mechanism (proper-noun detection) with an acknowledged precision risk. T8 (1 reference) needs a completely different kind of capability (session state, not text grammar) that already exists in `uri_core` but is architecturally unreachable from `uri_v1/turn/` today — a already-established, not new, finding.

---

## 9. D1 overfitting audit (Phase 5)

Independent re-read of all six mechanisms in `scripts/m35_a2_8d_detector_d1.py`, checked specifically against the corpus's own case IDs, exact wording, and expected entities:

1. **Filename shape, quoted spans, bare-pronoun fallback, closed-class recency lexicon:** re-read in full. **No case IDs, no benchmark-specific phrases, no expected entity names, no hardcoded expected types.** The recency lexicon's 14 entries are all closed-class English temporal-deixis words (latest/previous/earlier/etc.) — cross-checked against every one of the 79 raw turns and found to match naturally-occurring instances of ordinary English usage, not phrases engineered to match specific corpus sentences.
2. **Determiner + noun-phrase mechanism:** the determiner set (`the|this|that|these|those`) and the stop-word set (`and|but|so|because|which|who|that|to|for`) are both genuinely general — none is a corpus-derived special case.
3. **Per-clause-scoped negation — CONFIRMED overfitting risk, one instance.** The pattern `r"\bno,?\s+the\s+other\b"` closely mirrors the exact wording of `NB-H-06`'s raw text (`"no, the other scan, the one from last week"`). This pattern was authored during the same work that had already read and deeply audited `NB-H-06` specifically (in the A2.8C/A2.8D verification work, §5 of `M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md`) — it is narrower than a fully general "relational exclusion" rule would need to be, and its specific wording is a plausible, if not certain, product of having seen that exact sentence. **This is disclosed here as a genuine, if narrow and low-impact, violation of D1's own stated design discipline** ("none of these mechanisms was tuned against this corpus's pass/fail rate"). **Impact assessment:** this pattern only enriches `negation_spans` for a reference D1 had *already* detected by another mechanism (the determiner-NP match on `"the other scan"`) — it does not itself create a new detected span, and removing it would not change D1's detection-recall figures (§2, §3) at all; it would only remove one input to the already-independently-confirmed `NB-H-06` `INCORRECT_CONFIDENT_BINDING` outcome's negation evidence (which, per the A2.8D execution report §9, does not change the outcome either way — RC-2's token-overlap gate already cannot use "no, the other" to eliminate `scan_0034.pdf`, with or without this specific pattern, since the *general* `\bno\b`/`\bnot\b` patterns already reused from `TurnFrame` would supply the same non-overlapping tokens). **Recommended, not performed:** generalize or remove this one pattern in any future revision of D1 (explicitly out of scope for this forensic task, which is prohibited from modifying D1).
4. **Type-hint vocabulary (`TYPE_HEAD_WORDS`):** contains a mix of genuinely general words (document, file, spreadsheet, pdf, image, email, person, record) reused from `rar_deterministic.py`'s own vocabulary, and several **corpus-flavored additions** (`letter→document`, `invoice→pdf`, `roster→spreadsheet`, `minutes→document`, `agenda→document`, `certificate→pdf`, `scan→pdf`) that were plausibly chosen because they are the concrete nouns this specific office-work corpus uses. **This is a second, milder overfitting risk**, distinct from finding 3: these are common English office-vocabulary words, not benchmark-engineered phrases, so the risk is lower than finding 3's near-verbatim phrase match — but the specific *set* of nine words was almost certainly chosen by scanning this corpus's actual candidate titles, not from an independent general-office-vocabulary source. **Impact assessment:** these entries only populate `coarse_type` (used as `RAREvidence.target_type_hint`); §7's cell tables (A2.8D report, and this report's §2) show D1's `CORRECT_RESOLUTION` count is small (12/84) regardless, so this vocabulary's practical effect on headline figures is limited, but the finding itself is a real disclosure obligation.

**Overall verdict: D1's core mechanism (the determiner-NP grammar rule, the dominant driver of its recall gain) is genuinely general and not corpus-tuned. Two secondary components — one negation pattern, one type-word list — show real, disclosed, bounded overfitting risk that a fully independent audit should not omit.**

---

## 10. Candidate-construction / RAR interaction (Phase 6)

**1. Exactly why behavior differs (`NB-J-02`/`NB-J-04` vs. A2.8C's S2 oracle condition on the same cases):** A2.8C's S2 oracle populated `RARCandidate.recency_rank` with a real, timestamp-derived ordering across the candidate pool (`M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md` §4.1, harness decision 2). A2.8D's D0/D1/D2 harness (`m35_a2_8d_run.py`, `build_candidate_pool(..., oracle_recency=False)`) never populates it — every candidate's `recency_rank` is `0`. RAR's Level 5 "earlier" branch (`older_cands = [c for c in candidates_list if c.recency_rank > 0]`) requires at least one candidate with `recency_rank > 0` to fire at all; with all ranks at `0`, this branch is structurally inert, and execution falls through to Level 6, which correctly identifies "Jonas" (a substantive token absent from both lease candidates' titles) and returns `UNKNOWN` via the absent-entity check.

**2. Which candidate-metadata fields differ between paths:** exactly one field, `RARCandidate.recency_rank` — every other field (`title`, `candidate_type`, `domain_tags`, `is_attachment`, `exact_aliases`) is constructed identically by the same `build_candidate_pool()` function in both A2.8C's S2 harness and A2.8D's D0/D1/D2 harness.

**3. Whether other cases exhibit the same phenomenon:** yes — directly queried this session. **Six D1-detected references currently carry a non-null `recency_hint` and are scored `MISSED_RESOLVABLE_CASE` (not `INCORRECT_CONFIDENT_BINDING`) specifically because `recency_rank` is uniformly `0`:** `NB-D-01:r1`, `NB-D-02:r1`, `NB-D-04:r1`, `NB-D-07:r1`, `NB-H-01:r1`, `NB-L-09:r1` (rule attribution `TEMPORAL_RELATION`/`TERM_DISCRIMINATION` in every case, confirming Level 5's ordering-dependent branches are the ones affected). Of these, `NB-D-01` and `NB-D-02` are the two already independently confirmed (under A2.8C's oracle condition, with real `recency_rank`) to flip to an actual `INCORRECT_CONFIDENT_BINDING` when genuine ordering is supplied. **`NB-D-04`, `NB-D-07`, and `NB-H-01` are three additional, previously-unflagged cases carrying the same latent risk**, not yet confirmed to flip (they were not part of A2.8C's oracle-condition 8-case audit, which only covered cases already reference-bearing under that experiment's own S1/S2 construction) — recorded here as an open item, §13.

**4. Whether missing metadata can sometimes make RAR appear more accurate:** **Yes, directly demonstrated.** `NB-J-02` and `NB-J-04` score `CORRECT_ABSTENTION` (matching ground truth) under D1 specifically *because* `recency_rank` is absent — the same reference, with the same detected evidence, would very plausibly score `INCORRECT_CONFIDENT_BINDING` if `recency_rank` were populated (by direct analogy to `NB-D-01`/`NB-D-02`, which share the identical mechanism and did flip under A2.8C's oracle condition). RAR's correctness on these two cases is **contingent on the candidate supplier's incompleteness**, not on RAR's own logic being sound for this input shape.

**5. Future consistency risk:** **Real and specific.** If any future integration wires a genuine candidate-recency source into `uri_v1/turn/` (e.g., the already-identified but currently-disconnected `uri_core.FileStore`/`TurnState` sources, per the pre-RAR source audit — durable prior evidence, not re-derived here), the very same reference expressions that currently look "handled correctly" by D1 → RAR (`NB-J-02`, `NB-J-04`, and plausibly `NB-D-04`/`NB-D-07`/`NB-H-01` once tested) would **newly start exhibiting the already-known, never-repaired mechanism-(a) unsafe-binding limitation** — not because anything about RAR or D1 changed, but because the candidate pool became more informative. **A future evaluation of "does wiring in richer candidate metadata improve accuracy" must not treat a same-outcome-different-mechanism flip as a regression to be blamed on the new metadata source** — it would in fact be the same pre-existing RAR limitation becoming visible, exactly as `NB-H-06` became visible under D1 in this very experiment (§9 of the A2.8D execution report) precisely because detection improved. This risk is recorded as a finding, not fixed.

---

## 11. Bottom-up resolution-path evidence (Phase 8)

| Path | Successfully resolves | Notes |
|---|---|---|
| `existing D0 (TurnFrame) → RAR` | 0/84 (`CORRECT_RESOLUTION`) | Real production shape; recall 15.5%, and every detected reference is a bare pronoun RAR correctly declines on. |
| `D1 (deterministic) → RAR` | 12/84 (14.3%, corrected) | The only path in this experiment that resolves anything at all; driven almost entirely by the determiner-NP mechanism, confirmed general (§9). |
| `D2 (Needle 3, narrow) → RAR` | 0/84 | Zero correct resolutions; its 3 detections either miss attribution or land in `MISSED_RESOLVABLE_CASE`. |
| **Unresolved by any tested path** | 27/84 (32.1%) | §4–§8 above. |

No single universal detector is assumed or implied as a goal by this evidence. The 27-reference residual itself decomposes into at least three structurally different capability needs (§8): more orthographic/grammatical pattern coverage within D1's existing mechanism family (T1, T3, T4, T6, T7 — 17 references), a new but still-plausibly-deterministic proper-noun mechanism (T2 — 7 references), and a session/discourse-state mechanism categorically unlike anything D1 attempts (T8 — 1 reference), plus one case of genuinely added syntactic complexity within a small class (T5's compound sub-case — 1 reference). **Different cheap mechanisms plausibly serve different classes; nothing here demonstrates that a single larger model is required for any of them.**

---

## 12. Residual capability map (Phase 7)

| Cluster | Observed failure | Smallest missing information/capability | Existing URI mechanism available? | Deterministic mechanism plausible? | Model potentially required? | Evidence still needed |
|---|---|---|---|---|---|---|
| T1 | Alphanumeric code/ID never detected | A code/ID orthographic-shape rule | No | Yes | No | None — straightforward to test |
| T2 | Bare proper name never detected | Proper-noun identification with acceptable precision | No (nothing in `uri_v1/` or, per prior established evidence, `uri_core/`, does general capitalization-based NER) | Possibly — untested whether a structural co-occurrence rule (preposition/verb context) reaches usable precision | Possibly, if deterministic precision proves insufficient — **not concluded here** | Precision measurement of a proposed rule against a broader sample than this 79-case corpus |
| T3 | Possessive-'s NP never detected | A possessive-marker orthographic rule | No | Yes | No | None |
| T4 | Possessive-pronoun determiner never detected | Word-list extension to an existing mechanism | Yes — D1 itself, incompletely | Yes | No | None |
| T5 (simple) | Quantifier NP never detected | Word-list extension to an existing mechanism | Yes — D1 itself, incompletely | Yes | No | None |
| T5 (compound) | Embedded exception clause not represented as part of one span | Clause-boundary-aware span construction | No | Uncertain | Uncertain | Whether a bounded clause-embedding rule generalizes, or whether this needs semantic parsing |
| T6 | One pronoun omitted from an existing closed class | None — pure completion | Yes — D1 itself | Yes | No | None |
| T7 | Regex right-boundary fragility | Better regex/parsing engineering within the same mechanism family | Yes — D1 itself | Yes | No | Whether a fallback-to-longest-valid-prefix rework introduces new false positives |
| T8 | No surface reference at all | Session/turn "what was just produced" state | **Yes — `uri_core.TurnState.active_pointer`**, already established, already disconnected from `uri_v1/turn/` | Not applicable (not a detection problem) | No — this is a wiring/architecture question, not a model-capability question | Whether wiring `TurnState` into `uri_v1/turn/` (a separate, already-flagged architectural question, not decided here) would actually supply this |

**Semantic capability is named explicitly only for T5's compound sub-case (1 reference) and, provisionally, for T2's precision question (7 references) if a deterministic rule proves insufficient — in neither case is a specific model proposed.** Per Phase 7's explicit framing: what is needed for T5-compound is "identifying which words form one reference span when the span includes an embedded exception clause" — a capability description, not a model selection.

---

## 13. Unresolved evidence gaps

1. **T2's deterministic-precision question is untested** — no candidate rule (e.g., "capitalized word following a preposition/verb") was designed or measured against false-positive rate in this session.
2. **T5-compound's (`NB-H-02`) feasibility is genuinely open** — whether a bounded, still-deterministic clause-embedding rule could capture "either of the X except Y" as one span was not tested.
3. **The three newly-identified latent-risk cases from §10 point 3** (`NB-D-04`, `NB-D-07`, `NB-H-01`) — whether they would actually flip to `INCORRECT_CONFIDENT_BINDING` under a real `recency_rank` source, as `NB-D-01`/`NB-D-02` already confirmed did — was not tested this session (would require constructing an oracle-recency variant of the D1×RAR path, out of this task's forensic-only scope).
4. **D1's type-vocabulary overfitting risk (§9 finding 4) was not quantified** — how much of D1's 12/84 `CORRECT_RESOLUTION` count depends on those nine corpus-flavored type words versus the six fully-general ones was not isolated.
5. **Whether the same one-directional matching defect (§3) affects any other A2.8-series harness beyond `m35_a2_8d_run.py`** was not exhaustively re-audited — `m35_rar_natural_boundary_run.py` (A2.8C) was reasoned about (§3) but not re-run to empirically confirm zero impact there.

---

## 14. Recommended next experimental question (not decided)

Per §11's evidence — six of eight residual clusters (18/27 references) are plausibly recoverable by *extending D1's own existing deterministic-mechanism family* (broader word lists, a code/ID shape rule, a possessive-marker rule, regex robustness fixes), not by adding a new kind of component at all — the smallest justified next question is:

> **Would a bounded, still-fully-deterministic revision of D1 (correcting T7's regex fragility, extending T4/T5-simple/T6's word lists, and adding T1's code/ID and T3's possessive-marker shape rules — all within the same "generalizable linguistic shape, not corpus vocabulary" discipline already used for D1's existing six mechanisms) recover most or all of clusters T1/T3/T4/T5-simple/T6/T7 (18/27 references), leaving only T2 (proper-noun precision) and T8 (session-state) as separately-justified next capabilities?**

This question does not presuppose any model is needed for the 18-reference majority of the residual, and separates T2/T8 out as the only two clusters this evidence suggests might genuinely require something beyond D1-style deterministic extension — T2 possibly a precision-engineering question (still not necessarily model-based), T8 explicitly an architecture/wiring question (already flagged, not new). **Not designed or implemented in this document.**

---

## Summary for User Review

**A2.8D headline claims verified, with one correction:** every claim in this task's own prompt was checked against raw telemetry. Most matched exactly. **The "35 undetected by all tested paths" figure did not** — it was the original report's D1-vs-D2-only `neither_detects` count, not a true three-way intersection; the actual figure is **27** (after also fixing a genuine harness defect, below).

**Defect found and fixed (benchmark-only, disclosed with correction history):** the A2.8D harness's span-attribution check was one-directional, silently mis-scoring every case where D1 correctly captured a reference plus one extra word as a miss. Fixed and re-run (reproducible across 2 fresh runs). **Corrected figures: D1 detection recall 67.9%** (was 58.3%), **D1 resolution coverage 14.3%** (was 13.1%), **D2 detection recall 3.6%** (was 1.2%), and the spurious "D1 regression vs. D0" (2 cases) the bug had created disappeared entirely once fixed.

**27-reference residual set, individually analyzed, clustered into 8 evidence-derived classes:** T1 alphanumeric code/ID (4), T2 bare proper name (7), T3 possessive-'s NP (5), T4 possessive-pronoun determiner — an incomplete existing D1 word list (4), T5 quantifier NP (2, one simple/one compound), T6 one missing pronoun in an existing closed class (1), T7 regex right-boundary fragility (3), T8 genuinely no surface reference, a session-state gap (1). **18 of 27 (T1/T3/T4/T5-simple/T6/T7) are plausibly recoverable by extending D1's own already-proven deterministic-mechanism family — not a new capability class.**

**D1 overfitting audit — two genuine, disclosed findings:** one negation pattern (`"no, the other"`) closely mirrors `NB-H-06`'s exact wording (near-certain overfitting, low practical impact since it doesn't affect detection recall); the type-hint vocabulary contains several corpus-flavored word choices (milder risk). D1's core determiner-NP mechanism, the dominant driver of its recall gain, remains genuinely general.

**RAR/candidate-metadata interaction (Phase 6):** confirmed precisely — `NB-J-02`/`NB-J-04`'s apparent correctness is contingent on `recency_rank` being absent, not on RAR being sound for that input; **3 additional cases (`NB-D-04`, `NB-D-07`, `NB-H-01`) carry the same latent risk**, untested; a real future-consistency risk is recorded: wiring richer candidate metadata into `uri_v1/turn/` would make the pre-existing, never-repaired RAR limitation newly visible on these cases, not create a new one.

**Recommended next question:** test a bounded, still-deterministic D1 revision against clusters T1/T3/T4/T5-simple/T6/T7 before considering any new capability class for T2/T8. **Not implemented.**

**Files modified:** `scripts/m35_a2_8d_run.py` (bounded fix), `docs/plans/M35_URIV1_A2_8D_TELEMETRY.json` / `..._AGGREGATES.json` (regenerated), `docs/plans/M35_URIV1_A2_8D_EXECUTION_REPORT.md` (correction notice added).
**Files created:** this document.
**No file under `uri_v1/turn/` touched. D1 itself (`m35_a2_8d_detector_d1.py`) not modified.** No commit. No push. No architecture decision.

Stopped at `VERIFICATION_READY`.
