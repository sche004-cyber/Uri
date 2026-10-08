# M35 URIv1 — A2.8G: Detection-to-RAR Query Construction Boundary Audit

**Type:** Forensic analysis only. No query-construction repair, no D1R modification, no RAR modification, no model addition, no architecture change. No commit, no push.
**Governing evidence:** `M35_URIV1_A2_8F_EXECUTION_REPORT.md`, `M35_URIV1_A2_8F_TELEMETRY.json`/`..._AGGREGATES.json` (unmodified — read only), `scripts/m35_a2_8f_detector_d1r.py`, `scripts/m35_a2_8f_run.py`, `uri_v1/turn/rar_deterministic.py`, `uri_v1/turn/rar_contracts.py` (all unmodified).
**Status:** `VERIFICATION_READY`

```xml
<development_state>
  <current_phase>FORENSIC_SEAM_ANALYSIS</current_phase>
  <allowed_actions>inspect raw A2.8F telemetry, re-derive figures, trace each of the 18 target references end-to-end through query/candidate construction and RAR's cascade, classify each failure by owning seam, audit the query contract and candidate pool</allowed_actions>
  <prohibited_actions>modify D1R, modify RAR, modify query construction, modify candidate construction, add a model, change architecture, commit, push</prohibited_actions>
  <exit_criteria>18-case end-to-end trace complete, 15 unresolved cases individually classified by evidence-derived failure owner, exact-ID investigation complete, query contract audited field-by-field, candidate pool audited per case, RAR cascade audited against known mechanisms A/B, information-loss map complete, next question recommended</exit_criteria>
  <stop_condition>VERIFICATION_READY</stop_condition>
</development_state>
```

---

## Acceptance criteria (defined before analysis)

1. Every A2.8F headline figure this task asks to verify must be recomputed from raw telemetry, not copied from report prose.
2. All 18 target references must be traced with real telemetry values (detected span, signals supplied, candidates supplied, RAR rule/outcome) — none inferred.
3. Every one of the 15 unresolved cases must be assigned a failure owner from evidence (which fields were present/absent/malformed at each seam), with the specific mechanism named, not a generic label.
4. The exact-ID investigation must determine, per T1 case, whether Level 0 was structurally reachable at all (not just whether it fired) — distinguishing "never could have fired" from "could have fired but was blocked."
5. Known mechanisms A and B (Level 5-before-Level-6; Level 4a token-overlap-only negation) must be checked for explicitly, and any newly-observed RAR behavior must be named as a new, distinct mechanism rather than folded into A/B if it does not match them.
6. No repair proposed or implemented anywhere in this document.
7. The final failure-owner aggregation must sum to exactly 15.

Self-review: all seven met. Criterion 1 → §1. Criterion 2 → §2. Criterion 3 → §3, §10 (table). Criterion 4 → §5. Criterion 5 → §7. Criterion 6 → throughout (read-only). Criterion 7 → §10 (9+1+2+2+1=15).

---

## 0. Evidence recovered

- **Workspace:** HEAD `e8e3b65259c45fc823addc3ef8969425a265bd1b`, unchanged. Corpus SHA-256 `0ea5447354481041181538244ef70b6dc58a72267dd95263d61dbdb55ab07380`, verified matching at the start of this task.
- **Read this session:** `M35_URIV1_A2_8F_EXECUTION_REPORT.md`, `M35_URIV1_A2_8F_TELEMETRY.json` (raw, every field of every relevant row inspected directly), `scripts/m35_a2_8f_detector_d1r.py` (re-read in full to trace each mechanism's exact output construction), `scripts/m35_a2_8f_run.py` (re-read to confirm exactly how detector output becomes a `RARQuery`), `uri_v1/turn/rar_deterministic.py` and `uri_v1/turn/rar_contracts.py` (both re-read this session for the cascade-level and field-by-field audits — unchanged since earlier sessions' full reads, cited as durable where already established, re-verified line-by-line for the specific mechanisms this task needed).
- **Durable, not re-derived:** A2.8E's known mechanisms A (Level 5 pre-empting Level 6) and B (Level 4a token-overlap-only negation elimination); A2.8E/A2.8F's five-case candidate-metadata tracking set (`NB-J-02`, `NB-J-04`, `NB-D-04`, `NB-D-07`, `NB-H-01`); the pre-RAR candidate/anchor source audit's finding that no production builder exists for `ActiveContext` anywhere in the repository.
- **Legacy repository:** `C:\Users\cheta\Development\uri-agent` — accessible (confirmed), no new inspection needed this session beyond what is already durable evidence (no legacy mechanism was found relevant to query/candidate construction for natural-language reference detection in any prior M35 session). **Not `LEGACY_INSPECTION_UNAVAILABLE`.**
- **Not modified:** D1R, RAR, `rar_contracts.py`, the corpus, any candidate-construction code. Confirmed via `git status`/`git diff` at the end of this task (§13).

---

## 1. A2.8F verification (recomputed from raw telemetry)

| Claim | Recomputed | Verdict |
|---|---|---|
| D1 corrected detection recall 67.9% | 57/84 = 67.86% | ✅ |
| D1R detection recall 89.3% | 75/84 = 89.29% | ✅ |
| D1R target-18 detection 18/18 | 18/18 confirmed (none of the 18 target case/refs shows `SILENT_DETECTION_MISS` under `D1RxC1`) | ✅ |
| Target-18 final resolution 3/18 | `CORRECT_RESOLUTION` at `D1RxC1` for exactly `NB-G-04:r2`, `NB-L-10:r1`, `NB-L-10:r2` — 3/18 | ✅ |
| C1 whole-corpus resolution coverage 19.0% | 16/84 = 19.05% | ✅ |
| C2 whole-corpus resolution coverage 10.7% | 9/84 = 10.71% | ✅ |
| Zero new unsafe bindings | `INCORRECT_CONFIDENT_BINDING` count unchanged at 1 (`NB-H-06`) between D1 and D1R, both C1 and C2 | ✅ |
| `INVENTED_CANDIDATE = 0` | 0, scanned directly across all 1,455 rows | ✅ |
| Zero genuine boundary violations | 0 (the one false positive already found/fixed within A2.8F's own session is reflected in the current file) | ✅ |
| C1 zero detection regressions | Re-confirmed: `regression_check` shows 0 regressions, 0 new wrong bindings at C1 | ✅ |
| Disclosed C2 `NB-F-05` regression | Re-confirmed: `NB-F-05:r1` flips `CORRECT_RESOLUTION` (D1) → `MISSED_RESOLVABLE_CASE` (D1R) at C2 only | ✅ |
| 9 remaining undetected (T2: 7, T5-compound: 1, T8: 1) | Re-confirmed: exactly `NB-B-03`, `NB-B-05:r2`, `NB-G-04:r1`, `NB-I-02:r2`, `NB-I-06:r2`, `NB-L-01:r2`, `NB-L-02:r2`, `NB-L-04:r2`, `NB-H-02:r1` show `SILENT_DETECTION_MISS` under `D1RxC1` | ✅ |

**No material discrepancy found. All A2.8F figures independently reconfirmed; proceeding to trace.**

---

## 2. End-to-end trace, all 18 target references (C1)

Full per-case telemetry (detected span, signals supplied, candidate pool with titles/types, RAR rule and outcome) is reproduced verbatim from `M35_URIV1_A2_8F_TELEMETRY.json` in §3's failure table. Summary of what transits each seam, aggregated across all 18:

| Seam | What is preserved | What is normalized | What is dropped |
|---|---|---|---|
| Detected span → `reference_expression` | The literal detected text, verbatim | Case is preserved (no lowercasing at this seam — RAR itself lowercases internally) | Nothing at this specific hop — the full detected span (including any over-capture) passes through unchanged |
| Detector `coarse_type` → `RAREvidence.target_type_hint` | The value if non-`None` | None | If `coarse_type` is `None` (no head-noun match in `GENERAL_TYPE_HEAD_WORDS`), `target_type_hint` is simply absent — **not** inferred from any other source |
| Detector `recency_hint` → `RAREvidence.recency_hint` | The value if non-`None` | None | Same as above |
| Detector `negation_spans` → `RAREvidence.negation_spans` | Verbatim tuple | None | None dropped, but **always empty for every one of the 18 target cases** (none of T1/T3/T4/T5-simple/T6/T7 involves a negation-bearing clause) |
| Query → candidate pool | `variants[].available_candidates`, resolved through `candidate_library` into `RARCandidate` objects (id, title, candidate_type, domain_tags, is_attachment) — unchanged from A2.8D/A2.8E/A2.8F's own construction | `recency_rank` is **always 0** for every candidate in every one of these 18 cases (the deliberate `oracle_recency=False` boundary choice, unchanged since A2.8D) | No candidate field is dropped by this seam; every `RARCandidate` field the corpus provides reaches RAR |
| Candidates → RAR cascade | All fields RAR's own dataclass defines | RAR's own internal `clean_tokens()`/`stem_title()` normalization (case-folding, delimiter-splitting) — unchanged, pre-existing RAR behavior | Nothing new dropped by RAR itself; RAR uses exactly what it is given |

**No field is silently dropped between a populated detector output and the `RARQuery` RAR receives** — every non-`None` detector field reaches `RAREvidence` unchanged. **The failures traced in §3 are therefore not a transport/plumbing problem** (nothing is lost in transit) **but are entirely about what the detector chose to populate, how it shaped the span, and what RAR's cascade does with exactly that input** — a materially different, more precise conclusion than "information is lost between components."

---

## 3. Fifteen unresolved cases — individual failure-owner classification

All 15 are references where `D1R` **detected** the reference (18/18 detection, §1) but the outcome is not `CORRECT_RESOLUTION`. Classified using the ownership classes from the task's Phase 3, with a new class (`X`) introduced only where evidence required it.

### 3.1 T1 — alphanumeric code/ID (4 cases): all four — **Q (query-construction failure)**

`NB-A-01`, `NB-A-03`, `NB-A-04`, `NB-A-05` all show `rule_used: TYPE_FILTER`, `rar_failure_class: NO_CANDIDATE` — **RAR's Level 4b type filter, not Level 6, is what rejects every one of these.**

**Root cause, verified directly against `m35_a2_8f_detector_d1r.py`'s code:** the T1 mechanism hardcodes `coarse_type` to the literal string `"document"` for every code/UUID match (`whole_text_spans.append((full_span, "document", "code_id_shape"))` — no computation, no lookup, a fixed literal). The real candidates in every one of these four cases have `candidate_type` = `"pdf"` (three cases) or `"approval"` (one case, `NB-A-03`) — **never `"document"`**. RAR's Level 4b requires an *exact* string match (`c.candidate_type.lower() == target_type.lower()`); `"document" != "pdf"` and `"document" != "approval"`, so `type_matches` is empty and RAR returns `UNKNOWN`/`NO_CANDIDATE` **immediately, before Level 6 (lexical title matching) is ever reached.**

**Verified this would very plausibly resolve if the type hint were absent or correct:** for `NB-A-01`, the reference tokens (`invoice`, `20417` after `clean_tokens`' delimiter-splitting of `"INV-20417"`) both appear in the candidate title `invoice_INV-20417.pdf`'s own tokens (`invoice`, `inv`, `20417`, `pdf`) — a strong, discriminating lexical match Level 6 is specifically designed to catch, that Level 4b's premature, wrongly-typed filter never lets it reach. The same pattern holds for `NB-A-03` (`PO-5521` in `"Purchase order PO-5521 - 6 laptops"`) and `NB-A-05` (`INV-20388` in `"invoice_INV-20388.pdf"`).

**This is a single root cause across all 4 cases, not 4 independent findings.**

### 3.2 T3 — possessive-'s NP (4 of 5; `NB-J-03` is a success, §3.3): all four — **Q (query-construction failure, a second, distinct mechanism from §3.1)**

`NB-C-03`, `NB-F-02`, `NB-G-03`, `NB-L-11:r2` all show `rule_used: TERM_DISCRIMINATION`, `rar_failure_class: NO_CANDIDATE` — this time genuinely at **Level 6**, RAR's absent-entity check.

**Root cause, verified per case:** D1R's possessive-NP mechanism captures up to 3 trailing words after the `'s` marker, and in every one of these 4 cases it captures **at least one word beyond the semantically relevant reference** — words that belong to the *rest of the sentence*, not the reference itself:
- `NB-C-03`: detected `"Daniel's against the job"` (true reference: `"Daniel's"`) — `"against"` and `"job"` are leaked from the following clause `"against the job spec"`.
- `NB-F-02`: detected `"Daniel's interview again"` (true reference: `"Daniel's interview"`) — `"again"` is a leaked sentence-final adverb.
- `NB-G-03`: detected `"Tom's extension number"` (true reference: `"Tom's"` alone, per ground truth) — `"extension"` and `"number"` are semantically part of the user's question but not part of what the corpus marks as the referring expression.
- `NB-L-11:r2`: detected `"Daniel's offer letter alone"` (true reference: `"Daniel's offer letter"`) — `"alone"` is leaked from `"...alone for now"`.

**Verified mechanism:** RAR's Level 6 computes `substantive` tokens from the *entire* reference expression, then checks `unmatched_substantive = [t for t in substantive if t not in all_pool_tokens]`. In every case above, the leaked extra word(s) (`against`, `job`, `again`, `extension`, `number`, `alone`) do not appear in *any* candidate's tokens, while the true head word (`daniel`, `tom`) **does** appear and would, alone, have uniquely matched. Because `unmatched_substantive` is non-empty, RAR's absent-entity safety check fires and returns `NO_CANDIDATE` for the *entire* query — it does not partially credit the tokens that did match. **The detector's over-capture, not RAR's matching logic, is what poisons the query** — RAR is behaving exactly as its own documented invariant requires ("if the user query contains substantive discriminating tokens that appear in NONE of the candidates, the referent is absent from the pool") given input that itself contains spurious tokens.

### 3.3 T3's fifth case, `NB-J-03` — **A (appropriate abstention)**

Ground truth's own `expected_outcome` for `NB-J-03` is `UNKNOWN` (no candidate genuinely matches "September's P&L" — the pool contains an August expense report and a Q3 budget spreadsheet, neither the named report). D1R detects `"September's P&L"` cleanly (no over-capture here — the possessive-NP's captured body, `"P&L"`, is genuinely part of the reference). RAR's `TERM_DISCRIMINATION`/`NO_CANDIDATE` outcome **matches** the ground truth's own expectation exactly. **This is not a failure at all** — it is one of the 15 "not `CORRECT_RESOLUTION`" cases only because `CORRECT_RESOLUTION` is definitionally impossible when the correct answer is abstention.

### 3.4 T4 — possessive-pronoun determiner (3 of 4; `NB-G-04:r2` is a success)

**`NB-J-01` ("his reply") — Q (query-construction: missing type-hint inference).** Detected span `"his reply"` correctly, `coarse_type: None`. RAR's Level 6 finds `substantive = []` because `"reply"` is itself one of RAR's own `STOPWORDS` (`rar_deterministic.py`'s `STOPWORDS` set explicitly includes `"reply"` alongside other action-verb-like words: `"send"`, `"forward"`, `"review"`, `"share"`, etc.) — so the query is treated as a pure, anchor-less pronoun reference (`"his"`), landing in the `PRONOUN_BINDING`/`AMBIGUOUS` branch against the 2-candidate pool of Marcus Hale contacts. **Verified this would resolve correctly to `UNKNOWN` (matching ground truth) if `target_type_hint="email"` had been supplied:** Level 4b would filter the pool to type `email`, find zero matches (both candidates are type `record`), and return `UNKNOWN`/`NO_CANDIDATE` immediately — the exact expected outcome. D1R's `GENERAL_TYPE_HEAD_WORDS` maps `"email"`/`"emails"`/`"message"` to `"email"` but does **not** include `"reply"` as a synonym — a genuine, narrow vocabulary-completeness gap in an otherwise-general mechanism, not a new capability requirement.

**`NB-L-04:r1` ("my most recent letter") — C (candidate-construction: the already-known five-case recency-rank interaction, now a sixth case).** `rule_used: TEMPORAL_RELATION`, `rar_failure_class: INSUFFICIENT_METADATA`. `recency_hint="latest"` is correctly supplied; RAR's Level 5 `has_ordering` check finds every candidate's `recency_rank == 0` (the deliberate boundary choice, §2) and returns `AMBIGUOUS`/`INSUFFICIENT_METADATA` rather than attempting to guess among the 4 letter candidates. **This is not a new finding** — it is the identical mechanism already tracked for `NB-J-02`/`NB-J-04`/`NB-D-04`/`NB-D-07`/`NB-H-01` (A2.8E §10, A2.8F §8), now observed on a sixth case not previously in that tracked set. Recorded as an extension of the existing tracking set, not a new discovery (§9).

**`NB-L-08:r3` ("my reply to Priya") — X (a new evidence-derived class: no structured recipient/addressee field), compounded by a Q-class span truncation.** Detected span is `"my reply"` only — D1R's NP scanner correctly stops at `"to"` (one of the general stop-words `_NP_STOP_WORDS`, needed elsewhere to prevent exactly the kind of over-capture seen in §3.2), truncating away `"to Priya"`, the one piece of surface text that names the discriminating information. **But tracing further: even if the full span `"my reply to Priya"` had reached RAR, resolution would still not follow** — `"reply"` is an RAR stopword (as in `NB-J-01` above) and `"priya"` does not appear in the correct candidate's own title tokens (`"Re: Onboarding dates"` → `re`, `onboarding`, `dates`). **The real missing capability is structural, not lexical:** RAR has no evidence field anywhere in its contract (`RAREvidence` or `RARCandidate`) that represents "this email's recipient/addressee" — the corpus's own ground truth resolves this case using information (who an email was sent to) that no field in the current query or candidate contract can carry at all, regardless of how well or badly the detector captures the surface span. This is recorded as a new class, `X`, distinct from `Q`/`C`/`R`: **an evidence-contract gap** — the missing piece is not lost in transit and not a RAR cascade defect; it is a concept the contract has no place to put.

### 3.5 T5-simple, `NB-L-11:r1` ("both CVs") — **R (RAR limitation: no plural/morphological normalization)**

`rule_used: TERM_DISCRIMINATION`, `rar_failure_class: NO_CANDIDATE`. Detected span is clean and correct (`"both CVs"`, exactly the ground-truth span). Tracing token-by-token: `clean_tokens("both CVs")` → `both`, `cvs`. Both candidate titles (`CV_Amara_Okafor.pdf`, `CV_Daniel_Reyes.pdf`) tokenize to `cv` (singular) via the same `clean_tokens()` function — **`"cvs"` (plural) never equals `"cv"` (singular) as a string**, so this substantive token is `unmatched_substantive` despite being the semantically identical word. `"both"` also matches no candidate token (expected — it is a quantifier, not a content word, and RAR's `STOPWORDS`/`GENERIC_TYPE_WORDS` lists do not include it). **This is a genuine, previously-uncharacterized RAR limitation** — `clean_tokens()` performs no stemming or singular/plural normalization anywhere in the resolver. It is distinct from known mechanisms A and B. **A second, compounding factor**, not the earliest failure point but worth recording: the ground truth's own `plural_reference: true` / two-candidate `intended_candidate_ids` expectation has no representable outcome in `RAROutcome` at all — `RESOLVED` structurally carries exactly one `candidate_id` (enforced by `validate_rar_resolution`); even a perfect token match against both CVs could not produce the ground truth's literal expected shape without a plural-`RESOLVED` concept RAR's contract does not have.

### 3.6 T6, `NB-G-01` ("she") — **A (appropriate abstention by RAR's own explicit design), diverging from the benchmark's expectation**

`rule_used: TERM_DISCRIMINATION`, `rar_failure_class: PRONOUN_BINDING`, single candidate in the pool. Tracing the code: Level 6's pure-pronoun branch explicitly reads `if len(candidates_list) >= 2: AMBIGUOUS ... else: UNKNOWN` — **RAR never resolves a bare pronoun with zero anchor evidence, even against a singleton candidate pool.** This is not an accident of this input; it is the resolver's own documented invariant (the code comment reads "Pure pronoun or deictic reference without anchor"), applied consistently regardless of pool size. **Reading 1 (the one adopted here as primary):** this is *appropriate*, conservative, by-design abstention — a bare "she" could in principle refer to someone entirely outside the supplied candidate pool, so refusing to resolve merely because the pool happens to contain exactly one person-typed record is the safer behavior, consistent with RAR's zero-first-item-bias discipline applied to a degenerate one-item case. **Reading 2 (recorded, not adopted):** this diverges from the corpus's own `expected_outcome: RESOLVED`, so it could be read as a genuine limitation (`R`) if a future evidence contract wanted "singleton anchor" to count as sufficient. **Both readings are recorded; this document does not resolve which is correct**, since doing so would be a design/policy judgment, not a forensic finding — it is reported as `A`, with the caveat explicit.

### 3.7 T7's remaining case, `NB-F-03` ("the harbour street lease") — **R (a second, new RAR limitation)**

`rule_used: TERM_DISCRIMINATION`, `rar_failure_class: NO_CANDIDATE`. Detected span is exactly correct (matches ground truth verbatim — this is one of the two cases the T7 engineering fix specifically targeted, and detection succeeded cleanly). Tracing tokens: `substantive = [harbour, street, lease]`. Candidate `Lease_Agreement_Harbour_St_v2_draft.docx` tokenizes (via `clean_tokens`, which splits on `_`/`.`/`-`) to `lease`, `agreement`, `harbour`, `st`, `v2`, `draft`, `docx` — **`harbour` and `lease` both match directly and uniquely** (the other candidate, a staff roster, shares neither token) — but `"street"` matches nothing, because the candidate's own filename abbreviates it to `"st"`. `unmatched_substantive = ["street"]` is non-empty, so the *entire* query is rejected as absent-entity, **even though two of the three substantive tokens matched strongly and uniquely.** **This is a genuinely new, previously-undocumented RAR limitation, distinct from mechanisms A and B**: Level 6's absent-entity check is all-or-nothing across the full substantive-token set — a single non-matching token (here, caused by an ordinary real-world abbreviation, "St." for "Street," not a corpus artifact) overrides however many other tokens matched uniquely and strongly. Named here as **Mechanism C** for cross-reference in future work (not adopted as terminology beyond this document, since naming a new standing mechanism is itself a design act this forensic task does not take).

---

## 4. Failure-owner tally (15 cases)

| Owner | Count | Cases |
|---|---|---|
| **Q — query-construction failure** | **9** | `NB-A-01`, `NB-A-03`, `NB-A-04`, `NB-A-05` (§3.1, one shared root cause); `NB-C-03`, `NB-F-02`, `NB-G-03`, `NB-L-11:r2` (§3.2, one shared root cause); `NB-J-01` (§3.4) |
| **C — candidate-construction failure** | **1** | `NB-L-04:r1` (§3.4 — extends the already-known recency-rank tracking set) |
| **R — RAR limitation** | **2** | `NB-L-11:r1` (§3.5, plural/stemming), `NB-F-03` (§3.7, all-or-nothing absent-entity check / "Mechanism C") |
| **A — appropriate abstention** | **2** | `NB-J-03` (§3.3, matches ground truth exactly), `NB-G-01` (§3.6, by RAR's own explicit design, with the caveat recorded) |
| **X — new evidence-derived class (evidence-contract gap)** | **1** | `NB-L-08:r3` (§3.4 — no addressee/recipient field exists in the contract at all) |
| **Total** | **15** | |

**`Q` (query construction) is the dominant owner — 9 of 15 (60%), resolving into exactly two distinct, precisely-named root causes** (§3.1's hardcoded-wrong-type-hint mechanism, 4 cases; §3.2's possessive-NP over-capture mechanism, 4 cases) plus one narrower vocabulary gap (`NB-J-01`). **Neither of these two dominant Q-class root causes involves RAR's cascade at all** — they are both about what D1R constructs and hands to RAR, fully within the scope this task's Phase 10 explicitly forbids repairing here.

---

## 5. Exact-ID / code investigation (Phase 4)

Traced precisely for all four T1 cases, per the task's explicit sub-questions:

| Question | `NB-A-01` (`INV-20417`) | `NB-A-03` (`PO-5521`) | `NB-A-04` (UUID) | `NB-A-05` (`INV-20388`) |
|---|---|---|---|---|
| Does the literal identifier survive normalization? | Yes, verbatim in the query | Yes | Yes | Yes |
| Is it placed in the correct query field? | Yes — `reference_expression` (the only field an exact/lexical match can use) | Yes | Yes | Yes |
| Is the candidate identifier available? | Yes — candidate exists, `id` is a UUID unrelated to the human code | Yes | Yes — candidate's `id` **is** the same UUID | Yes |
| Does the exact-ID comparison (Level 0) ever have a chance to fire? | **No — structurally impossible.** `candidate.id` is an opaque UUID (`e71b3a98-...`); the human-readable code `"INV-20417"` exists only in `candidate.title`, never in `candidate.id` or `candidate.exact_aliases` (no candidate in this corpus populates `exact_aliases`) | **No — same structural reason** (`candidate.id` is `obj-2d47ba`, unrelated to `"PO-5521"`) | **Yes, structurally possible** — the detected code **is** the candidate's actual `id` | **No — same structural reason** |
| Does it actually fire? | No (never could) | No (never could) | **No — blocked by query construction**, not structurally impossible | No (never could) |
| Reason it doesn't fire (`NB-A-04`) | — | — | Level 0 requires `ref_norm == c.id.strip().lower()` exactly; D1R's span is `"file 38e1b5c4-..."` (the code/ID mechanism prepends the intro word `"file"` when present), so `ref_norm` is `"file 38e1b5c4-..."`, never equal to the bare UUID `"38e1b5c4-..."` — **the intro-word-inclusion design choice is what blocks the match**, not a limitation of Level 0 itself | — |
| What actually blocks resolution instead | Level 4b's hardcoded-wrong `target_type_hint="document"` (§3.1) rejects the pool before Level 6 can use the strong lexical match that does exist | Same as `NB-A-01` | Same as `NB-A-01`/`NB-A-03` (Level 4b), **in addition to** Level 0 being blocked as described above | Same as `NB-A-01` |

**Conclusion: for three of the four T1 cases (`NB-A-01`, `NB-A-03`, `NB-A-05`), RAR's exact-ID capability (Level 0) was never a viable path at all** — the human-readable code and the candidate's opaque `id` are two different identifier systems, and no candidate in this corpus registers the human code as an `exact_aliases` entry. **The realistic resolution path for these three was always Level 6 (lexical title matching), which the wrong type hint blocks.** **For the fourth (`NB-A-04`), Level 0 was genuinely reachable and would have resolved correctly with the bare UUID alone — query construction's intro-word inclusion is what specifically prevents it.** These are two different findings that happen to share a symptom (`NO_CANDIDATE`) and a cluster label (T1), not one finding.

---

## 6. Query contract audit (Phase 5)

Every field `RARQuery`/`RAREvidence` defines (`rar_contracts.py`), audited for producer/consumer/populatability:

| Field | Intended meaning | Producer (this experiment) | Consumer (RAR level) | Can D1R populate it? | Does the current harness populate it? | Does RAR actually use it? | Duplication/loss? |
|---|---|---|---|---|---|---|---|
| `reference_expression` | The surface text to resolve | D1R (span) | Levels 0, 2, 6 (token/title matching) | Yes | Yes | Yes | None |
| `local_evidence.recency_hint` | Ordinal/temporal signal | D1R (closed lexicon) | Levels 3, 5 | Yes | Yes, when present | Yes | None — but only usable in combination with `RARCandidate.recency_rank` (§6, next row) |
| `local_evidence.target_type_hint` | Type constraint | D1R (`GENERAL_TYPE_HEAD_WORDS` lookup, or hardcoded for T1) | Level 4b | Yes, but **incompletely** (missing `"reply"→email`, §3.4; hardcoded wrongly for T1, §3.1) | Yes, when non-`None` | Yes — and can actively **harm** resolution when wrong (§3.1) | None lost; the value that reaches RAR is exactly what D1R computed, right or wrong |
| `local_evidence.negation_spans` | Per-clause exclusion phrases | D1R (per-clause scan) | Level 4a | Yes | Yes | Yes | None for these 18 cases (all empty — no negation present in any target-18 raw text) |
| `local_evidence.candidate_verbs` | Verbs co-occurring with the reference | Never populated by D1R (or by D1, or by the real production path) | **Never read by `rar_deterministic.py` at all** (grep-confirmed: `candidate_verbs` appears only in the dataclass definition, never in any conditional in `resolve_rar_deterministic_extended`) | Not attempted | No | **No — dead field** | Not a loss for these 18 cases since RAR never reads it regardless |
| `local_evidence.clause_text` | The clause containing the reference | Never populated in `RAREvidence` construction (D1R tracks it internally as `D1RReference.clause_text` but the harness's `build_query()` never passes it into `RAREvidence.clause_text`) | **Never read by `rar_deterministic.py` at all** (same grep result as above) | Yes, trivially — D1R already computes it | **No — computed but discarded at the query-construction seam** | No — dead field regardless | This is the one genuine **transport loss** found in this audit: D1R computes `clause_text` for every detected reference, and it is dropped before reaching `RARQuery`. **It would not currently change any outcome even if wired through, since RAR never reads this field** — recorded as a real but currently inert seam, not a live cause of any of the 15 failures. |
| `deterministic_anchor` (all sub-fields) | Levels 0/1 anchors (`exact_id`, `selected_ui_id`, `current_attachment_id`, `unique_title_match`, `deterministic_recency`) | Never populated by D1R, by design (the frozen boundary, unchanged since A2.8D) | Levels 0, 1 | **Deliberately not attempted** — populating this would require the detector to compare against the candidate pool, which the frozen boundary prohibits | No | N/A (never constructed) | Not a loss — a deliberate scope boundary, not an oversight |
| `RARCandidate.recency_rank` | Ordinal recency across the pool | Not a query field at all — constructed by the harness from candidate metadata, never by any detector | Levels 3, 5 | N/A — outside detector scope entirely | **No, deliberately `0` for every candidate** (the `oracle_recency=False` boundary choice) | Yes, when non-uniform | The root cause of the `C`-class case (§3.4, `NB-L-04:r1`) and the five previously-tracked cases — **not a query-contract gap, a candidate-construction one** |

**Semantic mismatch identified:** `target_type_hint` expects a value from RAR's own type vocabulary (matched via exact string equality against `candidate.candidate_type`), but D1R's type-inference vocabulary (`GENERAL_TYPE_HEAD_WORDS`) was pruned during A2.8F's overfitting repair to a smaller set than the corpus's actual `candidate_type` values in use (`pdf`, `approval`, `calendar_event`, `report`, `letter`, `spreadsheet`, `record`, `document`, `email`, `image`) — several of these (`approval`, `calendar_event`, `report`) have **no corresponding head-noun mapping in D1R's general vocabulary at all**, and one (T1's hardcoded `"document"`) is actively wrong for the cases that hit it. **This is the precise, evidence-grounded form of "what the detector knows vs. what RAR can receive": RAR's type-matching is exact-string, zero-tolerance, and D1R's vocabulary-to-type mapping is neither complete nor, in one case, correct, relative to the actual type vocabulary the corpus's own candidates use.**

---

## 7. Candidate-construction audit (Phase 6), 15 unresolved cases

| Case | Classification | Evidence |
|---|---|---|
| `NB-A-01` | `CORRECT_CANDIDATE_PRESENT` | The exact invoice candidate is in the pool; excluded only by Level 4b's wrong type filter (§3.1) |
| `NB-A-03` | `CORRECT_CANDIDATE_PRESENT` | Same pattern |
| `NB-A-04` | `CORRECT_CANDIDATE_PRESENT` | Same pattern, plus the Level 0 exact-ID blocking (§5) |
| `NB-A-05` | `CORRECT_CANDIDATE_PRESENT` | Same pattern |
| `NB-C-03` | `CORRECT_CANDIDATE_PRESENT` | `CV_Daniel_Reyes.pdf` is in the pool; excluded by query over-capture (§3.2), not by candidate absence |
| `NB-F-02` | `CORRECT_CANDIDATE_PRESENT` | Calendar event candidate present |
| `NB-G-03` | `CORRECT_CANDIDATE_PRESENT` | Employee record present |
| `NB-J-01` | `CORRECT_CANDIDATE_ABSENT` | Ground truth's own annotation states no email-type object exists in this pool at all (only the two person-contact records) — the pool correctly lacks the true referent; `UNKNOWN` (RAR's actual near-outcome, family-mismatched as `AMBIGUOUS`) is the objectively right family of answer |
| `NB-L-04:r1` | `CORRECT_CANDIDATE_PRESENT_INSUFFICIENT_METADATA` | The correct letter candidate (`Offer letter - Daniel Reyes`) is present; what's missing is `recency_rank` ordering to distinguish it from 3 other letters, not the candidate itself |
| `NB-L-08:r3` | `CORRECT_CANDIDATE_PRESENT_INSUFFICIENT_METADATA` | The correct email candidate is present; what's missing is a recipient/addressee metadata field (§3.4), not the candidate |
| `NB-L-11:r1` | `CORRECT_CANDIDATE_PRESENT` (both) | Both CV candidates are present; excluded by the plural/stemming token mismatch (§3.5) |
| `NB-G-01` | `CORRECT_CANDIDATE_PRESENT` | The single employee record is present; RAR's own anchor-required design declines regardless (§3.6) |
| `NB-F-03` | `CORRECT_CANDIDATE_PRESENT` | The lease document is present; excluded by the all-or-nothing absent-entity check on an abbreviation mismatch (§3.7) |
| `NB-J-03` | `CORRECT_CANDIDATE_ABSENT` | Ground truth's own annotation: no candidate genuinely represents "September's P&L" — correct abstention (§3.3) |

**13 of 15 unresolved cases have `CORRECT_CANDIDATE_PRESENT` (or present-but-metadata-insufficient) — the candidate pool itself is essentially never the problem.** Only 2 (`NB-J-01`, `NB-J-03`) have a genuinely absent correct candidate, and in both of those RAR's near-outcome is already close to or exactly the right family of answer. **This strongly reinforces §4's finding that query construction, not candidate construction, is the dominant seam** — the correct referent is almost always sitting in the pool RAR receives; what fails is either the query's own shape (over-capture, wrong type hint) or RAR's matching/ranking logic given an otherwise-adequate query.

---

## 8. RAR cascade audit (Phase 7) — known mechanisms A/B, and what's newly observed

| Case | Exposes Mechanism A (L5-before-L6)? | Exposes Mechanism B (L4a relational exclusion)? | Exposes a new limitation? | Correctly abstains? |
|---|---|---|---|---|
| `NB-A-01`/`03`/`04`/`05` | No (never reaches L5 — rejected at L4b, §3.1) | No (no negation present) | No — the L4b type-filter issue is a query-construction defect (wrong input), not a resolver defect | No |
| `NB-C-03`/`F-02`/`G-03`/`L-11:r2` | No | No | No — L6's absent-entity behavior is working exactly as designed on a poisoned query (§3.2) | No |
| `NB-J-01` | No | No | No — same STOPWORDS-driven pronoun-only path, a query gap not a cascade gap | No (lands `AMBIGUOUS`, not the correct `UNKNOWN`) |
| `NB-L-04:r1` | **Yes — Mechanism A's precondition (`recency_rank` absence) is exactly why L5 does not commit here; this is the safe, non-firing side of Mechanism A**, not a new mechanism | No | No | Yes — `INSUFFICIENT_METADATA` is a safe abstention |
| `NB-L-08:r3` | No | No | No new cascade mechanism — the failure is upstream of the cascade (§3.4, contract gap) | Yes (`AMBIGUOUS`/`PRONOUN_BINDING`, safely) |
| `NB-L-11:r1` | No | No | **Yes — new: no plural/stemming normalization in `clean_tokens()`, an absent capability, not a decision-ordering issue like A or a token-overlap-scope issue like B** | Yes (`UNKNOWN`, safely) |
| `NB-G-01` | No | No | Arguably new (or simply RAR's documented anchor-required invariant, §3.6) — not A or B | Yes |
| `NB-F-03` | No | No | **Yes — new "Mechanism C": Level 6's absent-entity check is all-or-nothing across the full substantive-token set, so one non-matching token overrides several strong unique matches** | Yes (safely abstains, but on a case where a partial-credit approach would have resolved correctly) |

**Neither known mechanism A nor B is newly exposed by any of these 15 cases as a *firing* defect.** `NB-L-04:r1` touches Mechanism A's precondition but on its *safe* side (abstention, not wrong binding) — consistent with, not contradicting, A2.8F's finding that D1R introduces zero new unsafe bindings. **Two genuinely new resolver properties are observed** (§3.5's plural/stemming gap, §3.7's "Mechanism C" all-or-nothing absent-entity check) — both are `R`-class findings, both currently manifest as *safe* abstention rather than unsafe binding, and neither was previously characterized in A2.8C/A2.8D/A2.8E.

**The five-case candidate-metadata tracking set is preserved, unchanged, and now explicitly joined by a sixth case:**

| Case | Status this session |
|---|---|
| `NB-J-02` | Unchanged — `CORRECT_ABSTENTION` under D1R, identical to D1 (A2.8F §8) |
| `NB-J-04` | Unchanged — `CORRECT_ABSTENTION` |
| `NB-D-04` | Unchanged — `MISSED_RESOLVABLE_CASE` |
| `NB-D-07` | Unchanged — `MISSED_RESOLVABLE_CASE` |
| `NB-H-01` | Unchanged — `MISSED_RESOLVABLE_CASE` |
| **`NB-L-04:r1` (new, this session)** | **`MISSED_RESOLVABLE_CASE` via the identical `recency_rank`-absence mechanism** — recorded as extending the tracked set from 5 to 6 cases, not as a new mechanism |

---

## 9. Existing-mechanism reuse (Phase 9)

- **A general-purpose type-vocabulary or head-noun-to-object-type mapper:** none found anywhere in `uri_v1/` or (per already-durable evidence from the A2.8C/A2.8D-era audits) `uri_core/` beyond RAR's own hardcoded `GENERIC_TYPE_WORDS` set (itself narrow and not designed as a general NLP resource).
- **A code/ID-to-candidate-alias resolver:** none found. `RARCandidate.exact_aliases` exists as a contract field but is never populated by any construction path in this corpus (confirmed by direct inspection of `candidate_library` — no entry anywhere includes an `exact_aliases`-equivalent value), and no code anywhere derives aliases from a title's embedded code/ID substring.
- **A stemmer/plural-normalizer:** none found in `rar_deterministic.py`'s `clean_tokens()`/`stem_title()` (both perform only delimiter-splitting and extension-stripping, never morphological normalization) or anywhere else in `uri_v1/turn/`.
- **A recipient/addressee-aware evidence field:** none found in `RAREvidence`, `RARCandidate`, or (per already-durable evidence from the pre-RAR source audit) any `uri_core/` mechanism inspected in that prior session — `CapabilityContextResolver`'s Gmail-specific extraction (durable prior evidence, not re-derived here) does track a message's `from` field but nothing resembling a `to`/addressee concept was found there either.
- **`clause_text` wiring:** trivially available — D1R already computes it (§6); it is simply discarded one seam later, in `m35_a2_8f_run.py`'s `build_query()`, which never reads `found["clause_text"]`. This is the one place existing information genuinely goes unused for a reason that is not "the mechanism doesn't exist" but "the harness doesn't pass it through" — though, as noted in §6, wiring it through would not currently change any outcome since RAR itself never reads `RAREvidence.clause_text`.

**No existing URI mechanism, in `uri_v1/` or (per durable prior evidence) `uri_core/`, already solves any of the 9 `Q`-class cases' root causes, the `NB-L-11:r1` stemming gap, or the `NB-L-08:r3` addressee-field gap.** The `C`-class case's missing information (`recency_rank`) has a real, already-identified but disconnected source (`uri_core.FileStore`/`TurnState`, per durable prior evidence, not re-derived here).

---

## 10. Consolidated evidence table, all 18 target references

| Case:ref | Detected expression | Detector result | Query rep. | Correct candidate | Metadata | RAR levels reached | Outcome | Earliest failure point | Owner | Smallest missing capability | Existing mechanism? |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `NB-A-01:r1` | `invoice INV-20417` | Detected | type=`document` (wrong) | Present | pdf | 0(no)→1(no)→2(no)→4b(reject) | `UNKNOWN` | Query construction (wrong type hint) | Q | Correct/absent type hint for code-shaped references | No |
| `NB-A-03:r1` | `PO-5521` | Detected | type=`document` (wrong) | Present | approval | 0→1→2→4b(reject) | `UNKNOWN` | Query construction | Q | Same | No |
| `NB-A-04:r1` | `file <uuid>` | Detected | type=`document` (wrong); span includes intro word | Present (id==uuid) | pdf | 0(blocked by intro word)→4b(reject) | `UNKNOWN` | Query construction (two independent causes) | Q | Bare-ID span for Level 0 + correct type hint | No |
| `NB-A-05:r1` | `INV-20388` | Detected | type=`document` (wrong) | Present | pdf | 0→1→2→4b(reject) | `UNKNOWN` | Query construction | Q | Same as A-01 | No |
| `NB-C-03:r1` | `Daniel's against the job` | Detected (over-capture) | no type | Present | pdf | 0→1→2→3→4→5→6(reject, unmatched tokens) | `UNKNOWN` | Query construction (span over-capture) | Q | Tighter possessive-NP body boundary | No |
| `NB-F-02:r1` | `Daniel's interview again` | Detected (over-capture) | no type | Present | calendar_event | ...→6(reject) | `UNKNOWN` | Query construction | Q | Same | No |
| `NB-G-03:r1` | `Tom's extension number` | Detected (over-capture) | no type | Present | record | ...→6(reject) | `UNKNOWN` | Query construction | Q | Same | No |
| `NB-J-03:r1` | `September's P&L` | Detected (clean) | no type | Absent | — | ...→6(reject, correctly) | `UNKNOWN` | N/A — correct | A | None — correct abstention | N/A |
| `NB-L-11:r2` | `Daniel's offer letter alone` | Detected (over-capture) | no type | Present | letter | ...→6(reject) | `UNKNOWN` | Query construction | Q | Same possessive-NP boundary fix | No |
| `NB-G-04:r2` | `our insurance certificate` | Detected (clean) | no type | Present | pdf | ...→6(resolve) | `RESOLVED` (correct) | N/A — success | — | — | — |
| `NB-J-01:r1` | `his reply` | Detected (clean) | no type (`"reply"` unmapped) | Absent (by design) | — | ...→6(pronoun path) | `AMBIGUOUS` (near-miss of `UNKNOWN`) | Query construction (vocabulary gap) | Q | `"reply"→email` in type vocabulary | No |
| `NB-L-04:r1` | `my most recent letter` | Detected (clean) | `recency_hint=latest` | Present | letter | ...→5(insufficient metadata) | `AMBIGUOUS` | Candidate construction | C | `recency_rank` ordering (known gap) | Yes, disconnected (`uri_core`) |
| `NB-L-08:r3` | `my reply` (truncated) | Detected (truncated by design) | no type | Present | email | ...→6(pronoun path) | `AMBIGUOUS` | Evidence contract (no addressee field) | X | Recipient/addressee evidence field | No |
| `NB-L-11:r1` | `both CVs` | Detected (clean) | no type | Present (both) | pdf | ...→6(reject, "cvs"≠"cv") | `UNKNOWN` | RAR cascade (no stemming) | R | Plural/stemming token normalization | No |
| `NB-G-01:r1` | `she` | Detected (clean) | no type | Present (single) | record | ...→6(pronoun, no-anchor) | `UNKNOWN` | RAR cascade (by design) | A/R (dual-flagged) | Singleton-anchor policy decision | N/A (policy, not capability) |
| `NB-F-03:r1` | `the harbour street lease` | Detected (clean) | no type | Present | document | ...→6(reject, "street"≠"st") | `UNKNOWN` | RAR cascade ("Mechanism C") | R | Partial-credit / abbreviation-tolerant matching | No |
| `NB-L-10:r1` | `the Q3 forecast` | Detected (clean) | no type | Present | spreadsheet | ...→6(resolve) | `RESOLVED` (correct) | N/A — success | — | — | — |
| `NB-L-10:r2` | `the October agenda` | Detected (clean) | no type | Present | document | ...→6(resolve) | `RESOLVED` (correct) | N/A — success | — | — | — |

---

## 11. Information-loss map — earliest impossibility point

For every one of the 15 unresolved cases, the earliest point at which successful resolution becomes impossible:

- **9 cases (`Q`):** impossibility begins **at query construction** — before the query ever reaches RAR, either because the wrong `target_type_hint` is already baked in (T1, 4 cases), the span already contains spurious extra tokens (T3, 4 cases), or a real type synonym is simply missing from the vocabulary (`NB-J-01`). RAR is not the owner of any of these — it correctly processes exactly the (flawed) input it is given.
- **1 case (`C`, `NB-L-04:r1`):** impossibility begins **at candidate construction** — the query itself is fine; the candidate pool's `recency_rank` field, uniformly `0` by deliberate boundary design, is what makes Level 5 unable to commit.
- **1 case (`X`, `NB-L-08:r3`):** impossibility begins **before either seam, at the contract level** — no field in `RAREvidence` or `RARCandidate` could carry the needed information even with a perfect detector and a perfectly-populated candidate pool.
- **2 cases (`R`):** the query and candidates are both adequate; impossibility begins **inside RAR's own cascade** (Level 6's exact-token-match-only comparison in `NB-L-11:r1`'s case, and Level 6's all-or-nothing absent-entity check in `NB-F-03`'s case).
- **2 cases (`A`):** no impossibility in the sense of a defect — the observed outcome is correct or by-design (`NB-J-03`, `NB-G-01`).

**The dominant earliest-failure seam, by a wide margin, is query construction (9/15, 60%) — before the query ever reaches RAR or the candidate pool is even consulted.** This is consistent with, and sharpens, §4's failure-owner tally: not only is `Q` the largest class, its failures are also the *earliest* in the pipeline, meaning fixing them (not attempted in this document) would not require touching RAR, the candidate pool, or the corpus at all.

---

## 12. Latent-risk findings (not new repairs, recorded as evidence)

1. **The T1 hardcoded `"document"` type hint is a systematic, not case-specific, defect** — it will misfire identically on any future alphanumeric-code reference whose candidate's real type is not literally `"document"`, which based on the corpus's own type vocabulary (pdf, approval, calendar_event, report...) is the common case, not the exception.
2. **The T3 possessive-NP over-capture is also systematic** — any sentence where a possessive phrase is immediately followed by more sentence content within the 3-word body cap will risk the same poisoning, not just these 4 corpus cases.
3. **`clause_text` is computed and silently discarded** (§6) — currently inert (RAR never reads it), but a future change to RAR that *did* start using clause-scoped context would silently receive nothing from this pipeline unless the harness's `build_query()` is separately updated — a latent wiring gap worth remembering.
4. **The candidate-metadata tracking set has grown from 5 to 6 cases** (§8) purely from broader, correct detection — as detection recall continues to improve in any future work, more latent-risk cases of this same kind should be expected to surface, not fewer.

---

## 13. Files touched this session

**None.** This was a read-only forensic analysis. Confirmed via `git status --short` / `git diff --stat` at the end of this task: `uri_v1/turn/` unchanged, `scripts/m35_a2_8f_detector_d1r.py` unchanged, `scripts/m35_a2_8f_run.py` unchanged, `docs/plans/M35_URIV1_A2_8F_TELEMETRY.json`/`..._AGGREGATES.json` unchanged. **File created:** this document only.

---

## 14. Unresolved evidence gaps

1. **Whether `NB-J-01`'s missing `"reply"→email` vocabulary gap is representative of other verb-shaped nouns** (e.g., "his request", "her approval") that RAR's own `STOPWORDS` list also excludes as action-verbs but which function as head nouns in other natural references — not systematically checked against the full corpus in this session.
2. **`NB-G-01`'s dual `A`/`R` classification was deliberately left unresolved** as a policy question (§3.6) — this document does not, and should not, decide whether RAR's singleton-anchor-required behavior is correct.
3. **The exact frequency, beyond this 18-case sample, of Level 6's all-or-nothing absent-entity check ("Mechanism C", §3.7) causing false rejections on abbreviation/near-synonym mismatches** is unmeasured — only one instance was observed here.
4. **Whether `uri_core`'s Gmail-specific `CapabilityContextResolver` extraction (durable prior evidence) has any addressee/recipient concept for non-Gmail capabilities** was not re-verified this session (cited as already-established that no `to`-field concept was found there in a prior session, not independently re-checked here).

---

## 15. Smallest justified next experimental question

**Per §4/§11's evidence, `Q` (query construction) is the dominant, earliest-failing seam (9/15, 60%), resolving into exactly two named, mechanical root causes** (T1's hardcoded wrong type hint; T3's possessive-NP over-capture) that together account for 8 of the 9 `Q` cases, **with zero RAR modification and zero candidate-construction change required to address them** — both are entirely upstream of RAR, in how D1R constructs its output.

The smallest evidence-justified next question, consistent with the task's own instruction to recommend only what the dominant failure class supports:

> **Would a bounded, deterministic query-construction repair — specifically (a) deriving `target_type_hint` for code/ID-shaped references from the candidate pool's own type vocabulary or omitting it entirely rather than hardcoding `"document"`, and (b) tightening the possessive-NP body capture to stop before it crosses into unrelated sentence content — recover most or all of the 8 cases these two mechanisms explain, without introducing new unsafe bindings or touching RAR/candidate construction at all?**

This is **not recommended as a model addition** — nothing in this audit's evidence points to a missing semantic capability for these 8 cases; both root causes are named, mechanical, and fully within D1R's own existing code shape. The 2 `R`-class and 1 `C`-class and 1 `X`-class cases are explicitly **not** folded into this recommendation — they belong to different seams (RAR's own cascade, candidate metadata, and the evidence contract respectively) and would need separately-scoped experiments, not bundled into a query-construction fix. **Not designed or implemented in this document.**

---

## Summary for User Review

**Failure-owner counts (15 unresolved target-18 cases):** `Q` (query construction) = **9**, `C` (candidate construction) = **1**, `R` (RAR limitation) = **2**, `A` (appropriate abstention) = **2**, `X` (evidence-contract gap) = **1**.

**Earliest dominant failure seam: query construction, before RAR or the candidate pool is even reached (9/15, 60%)** — resolving into exactly two mechanical root causes: (1) T1's alphanumeric-code mechanism hardcodes `target_type_hint="document"`, which is wrong for every real candidate type in this corpus (`pdf`/`approval`) and causes Level 4b to reject the pool before Level 6's strong lexical match could ever be tried (4 cases); (2) T3's possessive-NP mechanism over-captures 1-2 trailing words beyond the true reference, poisoning Level 6's absent-entity check even when the true head word matches uniquely (4 cases, +1 narrower vocabulary gap).

**Newly discovered defects/findings:**
- A genuine (currently inert) transport gap: D1R computes `clause_text` per reference but the harness discards it before building the `RARQuery` — has no current effect since RAR never reads that field.
- Two new RAR-cascade properties, neither matching known mechanisms A/B: no plural/stemming normalization in `clean_tokens()` (`NB-L-11:r1`), and an all-or-nothing absent-entity check that rejects on any single unmatched token even with strong partial matches elsewhere (`NB-F-03`, informally named "Mechanism C").
- Confirmed the exact-ID (Level 0) path was **structurally unreachable** for 3 of 4 T1 cases regardless of query quality (the human code and the candidate's opaque UUID are different identifier systems, and no candidate registers an alias) — only 1 case (`NB-A-04`) had a genuinely viable Level 0 path, blocked specifically by an intro-word-inclusion design choice.
- The candidate-metadata tracking set grows from 5 to 6 cases (`NB-L-04:r1` added, identical known mechanism).

**Existing URI mechanisms that may already address a seam:** only the `recency_rank` gap (`C`-class) has a known, already-identified but architecturally disconnected source (`uri_core.FileStore`/`TurnState`, durable prior evidence). No existing mechanism anywhere in `uri_v1/` or `uri_core/` addresses the type-vocabulary gap, the possessive-NP boundary, the stemming gap, or the addressee-field gap.

**Files created:** [docs/plans/M35_URIV1_A2_8G_DETECTION_TO_RAR_BOUNDARY_AUDIT.md](docs/plans/M35_URIV1_A2_8G_DETECTION_TO_RAR_BOUNDARY_AUDIT.md). **Files modified: none.**

**Recommended next experiment:** a bounded, deterministic query-construction repair qualification targeting exactly the two named `Q`-class root causes (wrong hardcoded type hint; possessive-NP over-capture) — no RAR change, no candidate-construction change, no model. Not implemented.

No production modification. No architecture change. No commit. No push. Stopped at `VERIFICATION_READY`.
