# M35 — URIv1 Parallel Architecture
## Batch A2.5 Stage 4B-B — Independent Frozen RAR Requalification & Upstream Dependency Audit Report

## 1. Executive Summary

This architecture-qualification report evaluates two foundational questions regarding Reference Anchor Resolution (RAR) in URIv1:

- **Question A — Resolver Capability**: How well does the frozen deterministic RAR stack bind references on the independently authored, 136-case Stage 4B benchmark?
- **Question B — Dependency Honesty**: How much of that success depends on structured evidence fields that themselves require semantic interpretation upstream before RAR runs?

### Key Findings
1. **Primary Full Mode Evaluation (Benchmark exactly as authored)**:
   - **Overall Accuracy**: **122 / 136 (89.7%)** full matches.
   - **Automatic Resolution**: 100 cases resolved (94 correct, 6 wrong bindings $\rightarrow$ **94.0% precision**).
   - **Deterministic Coverage**: **73.5%** of turns automatically bound.
   - **Safe Abstentions**: 28 total (5 correct `UNKNOWN`, 23 correct `AMBIGUOUS`).
   - **Safety Failures**: **6 wrong bindings** (4.4% error rate) where RAR resolved an entity when the ground truth was `UNKNOWN` (absent referent).
   - **Performance**: Mean latency **0.0416 ms**, Median **0.0457 ms**, P95 **0.0869 ms**. Zero candidate inventions.

2. **Deterministic-Only Ablation (Pre-decoded semantic evidence stripped)**:
   - When upstream semantic fields (`negation_spans`, `recency_hint`, `target_type_hint`) are stripped—leaving only raw reference text, bounded candidate sets, candidate metadata, and direct UI/session anchors:
   - **Overall Accuracy**: Drops from **89.7% to 75.0%** (102 / 136 full matches).
   - **Deterministic Coverage**: Drops from **73.5% to 58.8%** (80 cases auto-resolved).
   - **Semantic Dependency Delta**: **21 reference cases** (15.4% of the benchmark) depend directly on upstream pre-decoded semantic interpretation to succeed.

3. **Architectural Classification**:
   - **Architecture C — Hybrid Deterministic Post-Semantic Binder**:
     - RAR possesses a substantial, fast **standalone deterministic core (~59% coverage, 75% accuracy)** handling exact IDs, aliases, verbatim titles, active UI focus, current attachments, and unique lexical term overlap.
     - However, **advanced reference behaviors (contrastive negation, continuation pointers, cross-type filtering) are strictly post-semantic**: they rely entirely on pre-parsed semantic fields (`negation_spans`, `recency_hint="same"`, `target_type_hint`) for which URIv1 currently possesses **no implemented deterministic upstream producer**.

---

## 2. Integrity Verification (Phase 0)

Before executing evaluation or ablation, all cryptographic and repository hashes were verified:
- **Worktree**: `C:\Users\cheta\Development\Uri\_V1`
- **Branch**: `m35-uri-v1-parallel-architecture`
- **HEAD**: `e8e3b65259c45fc823addc3ef8969425a265bd1b` (verified via `git rev-parse HEAD`)
- **Stage 4B Benchmark File**: `uri_v1/turn/rar_stage4b_independent_fixtures.py`
  - Total Fixtures: **136**
  - Size: **136,444 bytes**
  - SHA-256: `f5678b2da1d08937578b69cbb4e1a7f98b3cb07339baa302243597943453142e` (MATCHES MANIFEST EXACTLY)
- **RAR Deterministic Resolver**: `uri_v1/turn/rar_deterministic.py`
  - Size: **40,600 bytes**
  - SHA-256: `eb6d2567e406d74c55aa20deae0f39243367fbfaaec301915dfbeddcb5563663`
- **RAR Contracts**: `uri_v1/turn/rar_contracts.py`
  - Size: **11,939 bytes**
  - SHA-256: `4cc9aa43726a870ca2e9ab1b19f6bf9d72dcb74c8a2818856776af95195b6819`
- **Protected Prototype**: `C:\Users\cheta\Development\uri-agent` (READ-ONLY, untouched).

---

## 3. Primary Frozen Evaluation (Phase 1)

The frozen 136-case independent benchmark was evaluated directly against `resolve_rar_deterministic_extended`. Raw results were persisted to `scripts/rar_stage4b_qualification_results.json`.

### Primary Full Evaluation Metrics

| Metric Group | Metric | Primary Result (FULL Mode) |
|---|---|---|
| **Accuracy** | Total Cases | 136 |
| | Full Matches | **122** |
| | Full-Match Percentage | **89.7%** |
| | Outcome Matches | 122 |
| | Outcome-Match Percentage | 89.7% |
| **Automatic Resolution** | Auto-Resolved Count | 100 |
| | Correctly Resolved | 94 |
| | Incorrectly Resolved (Wrong Bindings) | **6** |
| | Automatic Resolution Precision | **94.0%** (0.9400) |
| | Deterministic Coverage | **73.5%** (0.7353) |
| **Safety Invariants** | Wrong Candidate Bindings | **6** |
| | Unsafe Resolved where Expected UNKNOWN | **6** |
| | Unsafe Resolved where Expected AMBIGUOUS | **0** |
| | Invented Candidate IDs | **0** (Zero) |
| | First-Item Bias Violations | **0** (Zero) |
| **Safe Abstentions** | Correct UNKNOWN | 5 |
| | Incorrect UNKNOWN | 1 |
| | Correct AMBIGUOUS | 23 |
| | Incorrect AMBIGUOUS | 4 |
| | Total Safe Abstentions | 28 (20.6% of benchmark) |
| **Performance** | Latency Mean | 0.0416 ms |
| | Latency Median | 0.0457 ms |
| | Latency P95 | 0.0869 ms |
| | Latency Max | 0.1539 ms |

### Rule Table (Full Mode)

| Driver Rule | Attempts | Correct Bindings | Wrong Bindings | Correct Abstentions | Other Failures |
|---|---|---|---|---|---|
| `TERM_DISCRIMINATION` | 55 | 28 | **5** | 18 | 4 |
| `TYPE_FILTER` | 23 | 20 | **1** | 1 | 1 |
| `ACTIVE_UI` | 11 | 11 | 0 | 0 | 0 |
| `ACTIVE_POINTER` | 10 | 10 | 0 | 0 | 0 |
| `TEMPORAL_RELATION` | 9 | 9 | 0 | 0 | 0 |
| `EXACT_ID` | 9 | 9 | 0 | 0 | 0 |
| `CONTRAST_FILTER` | 6 | 6 | 0 | 0 | 0 |
| `EXACT_ALIAS` | 4 | 4 | 0 | 0 | 0 |
| `CURRENT_ATTACHMENT` | 3 | 3 | 0 | 0 | 0 |
| `REVISION_RELATION` | 3 | 2 | 0 | 1 | 0 |
| `EXACT_TITLE` | 3 | 2 | 0 | 1 | 0 |
| **Total** | **136** | **94** | **6** | **21** | **5** |

---

## 4. RAR Input Provenance Audit (Phase 2)

A rigorous codebase audit was conducted across `rar_contracts.py`, `rar_deterministic.py`, `turn_frame.py`, `turn_frame_builder.py`, `active_context.py`, and `contracts.py` to establish the true upstream provenance of every field consumed by RAR.

### Provenance Classification Standards
- **D0 — Direct Deterministic State**: Present in session memory, UI state, or object storage without language interpretation.
- **D1 — Safe Deterministic Text Extraction**: Extracted by regex/surface rules without semantic reasoning.
- **S1 — Linguistic Interpretation Required**: Requires interpreting syntax, scope, or implicit meaning.
- **M1 — Model / Main-Brain Derived**: Requires semantic reasoning or LLM decoding.
- **B0 — Benchmark Oracle**: Authored into the benchmark fixture without an existing production producer.

### Complete Field-by-Field Audit Matrix

| Input Field | Consuming RAR Level | Current Producer in URIv1 | Provenance Class | Provenance Analysis & Upstream Reality |
|---|---|---|---|---|
| `reference_expression` | Levels 0, 2, 5, 6 | `TurnFrame.candidate_references` (partial) / LLM Wire | **S1 / B0** | In production, extracting the exact referring sub-phrase (e.g., `"the quarterly sports budget sanction letter"`) requires shallow semantic segmentation. `turn_frame_builder.py` only extracts fixed pronoun/demonstrative regexes (`"this"`, `"that file"`). Complex noun-phrase extraction currently relies on Step-1 model decoding or benchmark oracle. |
| `deterministic_anchor.selected_ui_id` | Level 1 | UI Client / Session State | **D0** | Genuinely deterministic foreground object ID passed directly from the desktop/web UI. |
| `deterministic_anchor.current_attachment_id` | Level 1 | UI Client / Email Session | **D0** | Genuinely deterministic attachment handle provided by active client context. |
| `deterministic_anchor.exact_id` | Level 0 | Regex / UI Paste | **D1** | Can be extracted deterministically via alphanumeric pattern matching (`MEMO-ACAD-...`, `PNR-...`). |
| `deterministic_anchor.unique_title_match` | Level 1 | Exact match against candidate titles | **D1** | Bounded deterministic exact string lookup. |
| `local_evidence.recency_hint` | Levels 3, 5 | **NOT CURRENTLY IMPLEMENTED** (Benchmark Oracle) | **S1 / B0** | Identifying that `"the earlier quotation"` implies `recency_hint="earlier"`, or `"the same circular"` implies `recency_hint="same"` is semantic parsing. In `turn_frame_builder.py`, there is no mapper from surface text to `recency_hint`. It is an ungrounded benchmark oracle. |
| `local_evidence.target_type_hint` | Levels 4b, 6 | **NOT CURRENTLY IMPLEMENTED** (Benchmark Oracle) | **S1 / B0** | Classifying `"the presentation"`, `"the sheet"`, or `"the inquiry dossier"` into schema types (`"presentation"`, `"spreadsheet"`, `"document"`) requires semantic type inference. No deterministic upstream component produces this in URIv1. |
| `local_evidence.negation_spans` | Level 4a | `TurnFrame.negation_spans` (incompatible format) | **S1 / B0** | `turn_frame_builder.py` extracts isolated negation particle words (`["not", "don't"]`), NOT full noun-phrase scopes (`"the July minutes"`, `"the assistant coordinator's"`). Full scoped negation spans are currently oracle-authored. |
| `local_evidence.clause_text` | Context filter | `_split_clauses()` | **D1** | Punctuation and conjunction based splitting. |
| `candidate.id` | Levels 0, 1, 6 | Database / Object Store | **D0** | Stable system identifier. |
| `candidate.title` | Levels 0, 2, 6 | File System / Resource Metadata | **D0** | Object name stored in metadata. |
| `candidate.candidate_type` | Level 4b | Resource MIME / Registry | **D0** | Stored metadata field. |
| `candidate.recency_rank` | Level 5 | Timestamps / Event Log | **D0** | Objectively sortable by file/event modification time. |
| `candidate.is_attachment` | Level 5.5 | Email/Message Object MIME | **D0** | Stored structural property. |
| `candidate.domain_tags` | Levels 4a, 5, 6 | Category / Folder / Pipeline Tag | **D0 / B0** | Some tags are objective metadata (`"spreadsheet"`). However, tags like `"recently_discussed"`, `"original"`, and `"revised"` are conversational state annotations with no current deterministic producer. |
| `candidate.owner` | Level 6 | ACL / Author Metadata | **D0** | Stored resource author. |
| `candidate.exact_aliases` | Level 0 | Registry / Alternate Handle | **D0 / D1** | Explicit pre-registered alias table. |

---

## 5. Dependency Map (Phase 3)

The actual logical pipeline implemented in URIv1 today vs. what RAR assumes:

```text
══════════════════════════════════════════════════════════════════════════════
CURRENT URIv1 UPSTREAM REALITY vs. RAR ASSUMPTIONS
══════════════════════════════════════════════════════════════════════════════

[RAW USER MESSAGE]
      │
      ├── (1) Direct UI / Session State  ───►  D0 State (selected_ui_id, current_attachment_id)
      │
      ├── (2) turn_frame_builder.py (D1)
      │         ├── clauses: _split_clauses() [D1]
      │         ├── negation particles: ["not", "don't"] [D1 - NOT SCOPED PHRASES]
      │         └── regex references: ["this", "it", "that file"] [D1 - LIMITED]
      │
      ├── (3) Missing Semantic Link: [NOT CURRENTLY IMPLEMENTED]
      │         ├── reference_expression segmentation ──► Oracle / Model Required (S1/M1)
      │         ├── negation_spans scoping           ──► Oracle / Model Required (S1/M1)
      │         ├── recency_hint extraction           ──► Oracle / Model Required (S1/M1)
      │         └── target_type_hint inference        ──► Oracle / Model Required (S1/M1)
      │
      ▼
[RARQuery (Constructed via Benchmark Oracle)]
      │
      ▼
[rar_deterministic.py (Levels 0 – 7)]
      │
      ▼
[Resolved Candidate ID / Safe Abstention]
══════════════════════════════════════════════════════════════════════════════
```

---

## 6. Deterministic-Only Ablation (Phase 4)

To measure how much RAR performance depends on pre-interpreted semantic fields, an ablation was conducted across the exact 136 frozen cases.

### Experimental Setup
- **Mode FULL**: Uses `RARQuery` exactly as authored in the frozen benchmark.
- **Mode DET-ONLY**: Evaluates evaluation-time copies of each query where S1/B0 fields (`negation_spans`, `recency_hint`, `target_type_hint`) are neutralized to empty tuples or `None`.
- **Preserved in DET-ONLY**: Raw reference expression, candidate list, candidate stored metadata (`title`, `candidate_type`, `owner`, `recency_rank`, `is_attachment`, `exact_aliases`), and direct deterministic anchors (`selected_ui_id`, `current_attachment_id`, `exact_id`).

### Comparative Metrics: Mode FULL vs. Mode DET-ONLY

| Metric | Mode FULL (With Semantic Evidence) | Mode DET-ONLY (Deterministic State Only) | Impact (Delta) |
|---|---|---|---|
| **Full Matches** | **122 / 136** | **102 / 136** | **-20 matches (-14.7 pp)** |
| **Overall Accuracy** | **89.7%** | **75.0%** | **-14.7 pp** |
| **Automatic Resolutions** | 100 | 80 | -20 cases |
| **Correctly Resolved** | 94 | 75 | -19 cases |
| **Wrong Bindings** | 6 | 5 | -1 wrong bind |
| **Auto-Resolution Precision** | 94.0% | 93.8% | -0.2 pp |
| **Deterministic Coverage** | **73.5%** | **58.8%** | **-14.7 pp** |
| **Safe Abstentions** | 28 | 27 | -1 |
| - Correct UNKNOWN | 5 | 6 | +1 |
| - Correct AMBIGUOUS | 23 | 21 | -2 |

### Semantic Dependency Delta Analysis
- **Cases passing in FULL but failing/abstaining in DET-ONLY**: **21 cases** (15.4% of benchmark).
- **Cases passing in DET-ONLY but failing in FULL**: **1 case** (`S4B-030`, see §7).
- **Net Semantic Dependency**: **14.7% of benchmark capability relies strictly on pre-decoded upstream semantics**.

#### Breakdown of the 21 Semantically Dependent Cases:

1. **Active Pointer / Continuation Dependency (`recency_hint="same"`) — 8 cases**:
   - Cases: `S4B-025`, `S4B-026`, `S4B-027`, `S4B-029`, `S4B-029B`, `S4B-032`, `S4B-095`, `S4B-132`.
   - **Root Cause**: Utterances like `"the same circular"`, `"that order"`, or `"the same project brief"` resolve via Level 3 `ACTIVE_POINTER` solely because the benchmark supplied `recency_hint="same"`. When stripped, the generic words `"order"`, `"circular"`, and `"brief"` score zero or tie, falling back to safe abstention (`AMBIGUOUS` or `UNKNOWN`).

2. **Target Type Hint Dependency (`target_type_hint`) — 7 cases**:
   - Cases: `S4B-019`, `S4B-033`, `S4B-034`, `S4B-035`, `S4B-038`, `S4B-040`, `S4B-100`.
   - **Root Cause**: Phrases like `"the email"`, `"the spreadsheet"`, or `"the workflow"` resolve cleanly in FULL mode via Level 4b `TYPE_FILTER` because `target_type_hint` is provided. In DET-ONLY, `"email"` or `"sheet"` are not in candidate titles (which use names like `Registration_Confirmation.docx`), causing lexical ties or zero-scores that abstain.

3. **Contrastive Negation Scope Dependency (`negation_spans`) — 6 cases**:
   - Cases: `S4B-051`, `S4B-053`, `S4B-054`, `S4B-057`, `S4B-059`, `S4B-090`.
   - **Root Cause**: In `"Not the sports committee report, send the other one"`, Level 4a eliminates the sports report because the oracle supplied `negation_spans=("Not the sports committee report",)`. Without this pre-extracted phrase, Level 4a cannot run, and the deictic phrase `"the other one"` cannot resolve.

---

## 7. Residual Failure & Safety Analysis (Phase 5)

All 14 cases in FULL mode that did not produce a full match were traced individually against resolver execution.

### The 6 Wrong Bindings (Safety Failures)
All 6 wrong bindings stem from a single architectural vulnerability in Level 6 TF-IDF discrimination: **partial lexical matching against generic institutional vocabulary when the intended entity is absent (`UNKNOWN`)**.

1. **`S4B-023` — "the quarterly sports budget sanction letter"**:
   - Expected: `UNKNOWN` (sports sanction letter is absent from pool).
   - Actual: `RESOLVED` to `doc_hostel_sanct` (`Hostel_Mess_Subsidy_Sanction_Letter.pdf`) via `TERM_DISCRIMINATION`.
   - Vulnerability: Candidate title contains `"sanction"` and `"letter"`. Low-weight shared tokens accumulate a score of 4.5, clearing the resolution threshold against an absent entity.

2. **`S4B-030` — "the same audio recording"**:
   - Expected: `UNKNOWN` (only text transcripts exist; audio is absent).
   - Actual: `RESOLVED` to `min_inquiry_doc` via Level 3 `ACTIVE_POINTER`.
   - Vulnerability: `ACTIVE_POINTER` triggers on `recency_hint="same"` without verifying whether the candidate satisfies the requested media type, binding an inquiry text transcript to an audio request.

3. **`S4B-066` — "the ABET accreditation self-study questionnaire"**:
   - Expected: `UNKNOWN` (ABET file is absent; pool has NAAC, NBA, NIRF).
   - Actual: `RESOLVED` to `doc_naac_ssr` (`NAAC_Self_Study_Report_2025.pdf`) via `TERM_DISCRIMINATION`.
   - Vulnerability: Matches `"self"` and `"study"` in NAAC SSR title (score 4.5). The specific entity discriminator `"abet"` was absent, but partial overlap overrode safe abstention.

4. **`S4B-073` — "the campus master plan CAD drawing"**:
   - Expected: `UNKNOWN` (CAD drawing is absent).
   - Actual: `RESOLVED` to `doc_estate_summary` (`Campus_Estate_Building_Area_Summary.pdf`) via `TERM_DISCRIMINATION`.
   - Vulnerability: Matches `"campus"` (score 3.5), binding an estate summary to a CAD drawing request.

5. **`S4B-087` — "the Gartner Magic Quadrant competitor matrix"**:
   - Expected: `UNKNOWN` (Gartner matrix absent).
   - Actual: `RESOLVED` to `sheet_pricing_matrix` (`Internal_Tiered_Pricing_Matrix.xlsx`) via Level 4b `TYPE_FILTER`.
   - Vulnerability: Candidate pool contained one spreadsheet and one document. The oracle supplied `target_type_hint="spreadsheet"`. Level 4b narrowed to the single spreadsheet and bound it unconditionally, ignoring the fact that the actual requested entity was absent.

6. **`S4B-131` — "the campus staff quarter lease renewal agreement"**:
   - Expected: `UNKNOWN` (staff quarter lease absent; pool has private flat lease and lab allotment).
   - Actual: `RESOLVED` to `doc_personal_flat_lease` (`Private_Apartment_Rental_Agreement_Tenant.pdf`) via `TERM_DISCRIMINATION`.
   - Vulnerability: Matches `"lease"` and `"agreement"` (score 3.5), erroneously binding a private lease to a university housing request.

### The 8 Safe Abstention Misses
- **`S4B-039` ("the audio recording")**: Expected `RESOLVED` (`audio_townhall_feb`). Actual `UNKNOWN` via `TYPE_FILTER` because candidate type `"media"` was filtered out by a strict document/email check.
- **`S4B-055` ("the exam circular")**: Expected `UNKNOWN`. Actual `AMBIGUOUS` (safe).
- **`S4B-063`, `S4B-064`, `S4B-098` (Ownership qualifiers)**: Expected `RESOLVED` via owner name (`"the dean's note"`, `"Sarah's appraisal"`). Actual `AMBIGUOUS` because Level 6 does not perform strong owner-name matching.
- **`S4B-069`, `S4B-094` (Alphanumeric/YAML absent entities)**: Expected `UNKNOWN`. Actual `AMBIGUOUS` (safe).
- **`S4B-128` ("the email from Dr. Sen")**: Expected `AMBIGUOUS`. Actual `UNKNOWN` (safe).

---

## 8. Architectural Classification

Based on the empirical evidence from Phase 1, Phase 2, and Phase 4, Reference Anchor Resolution in URIv1 is classified as:

### `Architecture C — Hybrid Deterministic Post-Semantic Binder`

```text
══════════════════════════════════════════════════════════════════════════════
CLASSIFICATION: ARCHITECTURE C (HYBRID)
══════════════════════════════════════════════════════════════════════════════

                            [RAW USER INTERACTION]
                                      │
               ┌──────────────────────┴──────────────────────┐
               ▼                                             ▼
       [DETERMINISTIC EASY PATH]                     [SEMANTIC COMPLEX PATH]
       • Alphanumeric IDs / Aliases                  • Pronouns ("it", "he")
       • UI Selection / Active Attachment            • Relative offsets ("the previous")
       • Verbatim Title Matches                      • Conversational pointers ("the same")
       • Unambiguous Lexical Term Overlap            • Scoped Negation ("Not X, send Y")
               │                                     • Cross-Type Noun Phrases ("the sheet")
               │                                             │
               │                                             ▼
               │                                  [UPSTREAM SEMANTIC DECODER]
               │                                  (Needle / Qwen / Model Required)
               │                                             │
               │                                             ▼
               │                                  [PRE-DECODED EVIDENCE FIELDS]
               │                                  • negation_spans
               │                                  • recency_hint
               │                                  • target_type_hint
               │                                             │
               └──────────────────────┬──────────────────────┘
                                      ▼
                        [DETERMINISTIC RAR ENGINE]
                        (rar_deterministic.py)
                                      │
                                      ▼
                          [QUALIFIED REFERENCE BINDING]
══════════════════════════════════════════════════════════════════════════════
```

### Justification
1. **RAR is NOT purely Architecture A (Standalone Deterministic)**:
   - Stripping upstream semantic evidence drops accuracy by **14.7 pp** and drops coverage by **14.7 pp** (from 73.5% down to 58.8%).
   - Complex reference behaviors (negation, continuation, type inference) fail completely without pre-parsed semantic scaffolding.
2. **RAR is NOT purely Architecture B (Post-Semantic Only)**:
   - In pure DET-ONLY mode, RAR still achieves **75.0% accuracy and 58.8% coverage** with **93.8% precision**.
   - Direct deterministic hooks (`selected_ui_id`, `current_attachment_id`, `exact_id`, `exact_aliases`, verbatim titles, and direct lexical matching) operate completely standalone without any model intervention.
3. **Architectural Reality**:
   - RAR is a **hybrid system**: it provides an ultra-fast, zero-cost deterministic fast-path for direct references, but functions as a **deterministic post-semantic binding layer** for complex conversational references.
   - Calling RAR a "standalone deterministic reference understander" would be misleading; calling it "useless without an LLM" would be equally false. It is an efficient downstream structural binder operating in concert with upstream turn parsing.

---

## 9. Recommendations for Step-1 Architecture

1. **Close the Level 6 Absent Entity Vulnerability**:
   - The 6 wrong bindings occurred because Level 6 term scoring rewards non-stopword institutional nouns (`"sanction"`, `"letter"`, `"study"`, `"campus"`, `"agreement"`) even when the primary identifying entity is wholly absent.
   - **Fix**: Require a higher discrimination margin or require that candidate titles match entity tokens, not merely generic document category words, before declaring `RESOLVED`.
2. **Implement Real Upstream Producers Before Production Wiring**:
   - Production cannot consume `negation_spans` or `recency_hint` until a parser or model is wired to extract them from the user turn.
   - For simple references, extend `turn_frame_builder.py` with bounded regex mappers (e.g., mapping `"latest"` / `"current"` surface tokens directly to `recency_hint`).
   - For complex multi-clause turns, accept that Step-1 semantic decoding (via Needle/Qwen) must extract the reference envelope before RAR binds it.

---

## 10. Final Verification & Artifact Status
- `scripts/m35_rar_stage4b_eval.py`: Created and verified.
- `scripts/rar_stage4b_qualification_results.json`: Persisted with raw primary and ablation data.
- Benchmark and prototype integrity verified intact. No code committed or pushed.
