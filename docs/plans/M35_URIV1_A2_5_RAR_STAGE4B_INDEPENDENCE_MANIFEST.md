# M35 — URIv1 Parallel Architecture
## Batch A2.5 Stage 4B-A — Independent RAR Benchmark Independence Manifest

## 1. Metadata & Worktree Information

- **Date / Timestamp**: 2026-09-22T06:48:00+05:30
- **URIv1 Worktree**: `C:\Users\cheta\Development\Uri\_V1`
- **Branch**: `m35-uri-v1-parallel-architecture`
- **HEAD Commit**: `e8e3b65259c45fc823addc3ef8969425a265bd1b` (verified via `git rev-parse HEAD`)
- **Author Role**: Benchmark Author (Intentionally Resolver-Unaware)
- **Protected Legacy Prototype**: `C:\Users\cheta\Development\uri-agent` (READ-ONLY, untouched)

## 2. Permitted Files Inspected & Independence Confirmation

### Files Inspected
During the execution of Batch A2.5 Stage 4B-A, **only one existing repository file was inspected**:
- `uri_v1/turn/rar_contracts.py`: neutral dataclass and enum definitions (`RARCandidate`, `RAREvidence`, `RARDeterministicAnchor`, `RARQuery`, `RARResolution`, `RARFixture`, `RAROutcome`, `validate_rar_resolution`).

### Strict Prohibited Material Exclusion Confirmation
Per the Critical Independence Rule:
- **DO NOT INSPECT RULE STRICTLY HONOURED**:
  - `uri_v1/turn/rar_deterministic.py` was **NOT opened, read, searched, or imported**.
  - No existing deterministic RAR tests were opened or executed.
  - No Stage 2 RAR fixtures were inspected.
  - No Stage 3 benchmark fixtures (`rar_stage3_blind_fixtures.py`) or reports were inspected.
  - No Stage 3 evaluation results or residual failure cases were inspected.
  - No Stage 4 refinement tests or reports were inspected.
  - No evaluation scripts (`scripts/m35_rar_deterministic_eval.py`, `scripts/m35_rar_stage3_eval.py`) were opened or run.
  - No qualification JSON files (`scripts/*_qualification_results.json`) were inspected.
  - No git diffs exposing prohibited implementation or test diffs were inspected.
- **ZERO RESOLVER EXECUTION**: `resolve_rar_deterministic_extended` and `resolve_rar_deterministically` were **NEVER executed**.
- **ZERO ACCURACY / QUALIFICATION SCORE PRODUCED**: No benchmark scoring, qualification, or evaluation was conducted in this session.

## 3. Benchmark Dataset Summary

- **Target File**: `uri_v1/turn/rar_stage4b_independent_fixtures.py`
- **Fixture Count**: 136 independently authored reference binding situations
- **SHA-256 Hash**: `f5678b2da1d08937578b69cbb4e1a7f98b3cb07339baa302243597943453142e`
- **Byte Size**: 136,444 bytes
- **Freeze State**: Completed and frozen. No further modifications permitted.

## 4. Domain Usage Distribution

The benchmark reflects URI's primary role as an institutional assistant while covering expanding general work, personal life, and cross-domain contexts:

| Domain | Target Range | Actual Count | Actual Percentage |
|---|---|---|---|
| **Office / Institutional** | 55% – 65% | 81 | **59.6%** |
| **General Work / Productivity** | 15% – 20% | 25 | **18.4%** |
| **Personal Assistant / Everyday** | 15% – 20% | 20 | **14.7%** |
| **Cross-Domain / Mixed Context** | 5% – 10% | 10 | **7.4%** |
| **Total** | 120 – 150 | **136** | **100.0%** |

### Representative Coverage per Domain
- **Office / Institutional (81 cases)**: Academic circulars, office orders, meeting minutes, disciplinary dockets, scholarship dossiers, hostel allotment lists, mess committee catering tenders, lab equipment quotations, casual/duty leave approvals, annual faculty appraisals, grading pipelines.
- **General Work / Productivity (25 cases)**: Sprint planning Kanban cards, client QBR presentation decks, architecture decision records (ADRs), retrospectives, roadmap drafts, user research customer discovery audio calls, pull requests, financial models, design mockups, incident postmortems, SaaS dashboards.
- **Personal Assistant / Everyday (20 cases)**: Electricity/broadband utility bills, flight e-tickets (PNR), medical prescriptions, grocery purchase receipts, hotel booking vouchers, apartment maintenance dues, health/car insurance policies, gym subscription renewal reminders, daughter's school fee receipts, household chore workflows.
- **Cross-Domain / Mixed Context (10 cases)**: Academic conference flights vs. family vacation tickets, home office broadband reimbursement vs. personal utility bills, university vs. personal email inboxes, institutional NAAC reports vs. personal ITR acknowledgments, academic preprint drafts vs. personal fiction novel chapters.

## 5. Ground-Truth Tri-State Outcome Distribution

Every case was annotated independently using ordinary human interpretation and the supplied structured scenario context:

| Outcome | Count | Percentage | Definition & Application |
|---|---|---|---|
| **RESOLVED** | 98 | **72.1%** | Exactly one supplied candidate is clearly and unambiguously the intended referent based on exact ID/alias, active UI focus, explicit attachment semantics, verbatim title, unique recency rank, distinguishing contrastive terms, or clear type constraints. |
| **AMBIGUOUS** | 24 | **17.6%** | Two or more supplied candidates are genuinely plausible and the supplied information is insufficient to determine exactly one (e.g., identical titles, two documents sharing generic terms, unanchored pronouns, or multiple candidates surviving negation). |
| **UNKNOWN** | 14 | **10.3%** | The intended referent is absent or not sufficiently represented in the bounded candidate pool (e.g., non-existent documents, absent ticket numbers, contradictory type requests, or total negation of all candidates). |
| **Total** | **136** | **100.0%** | |

## 6. Reference Behavior & Theme Coverage

The corpus incorporates natural human reference behaviors across all 136 cases:
- **Exact Identifiers & Aliases**: Formal office memo codes (`MEMO-ACAD-2026-088`), flight PNRs (`PNR-6E-9912`), leave request IDs (`LV-2026-052`), ticket IDs (`TKT-HOSTEL-9041`), engineering ADRs (`ADR-0024`), procurement quotes (`QUOT-EE-2026-119`).
- **Active Turn Context & UI Anchors**: Foreground selected items (`selected_ui_id`), focused table rows, highlighted requisition cards, active tabs, and email composition attachments (`current_attachment_id`).
- **Verbatim Titles & Shortened Names**: Exact file names (`Hostel_Fee_Structure_2026_2027.pdf`), colloquial abbreviations (`"the BOS resolution"`), and domain shorthand (`"the leave policy"`, `"the retro notes"`).
- **Active Pointer & Continuation**: Conversational pointers (`"the same circular"`, `"that order"`, `"the same workflow"`, `"the same project brief"`).
- **Schema & Type Constraints**: Semantic filtering across document, email, spreadsheet, workflow, person, presentation, and media objects.
- **Temporal & Version Offsets**: Explicit ordinal references (`"latest"`, `"current"`, `"previous"`, `"earlier"`).
- **Revision Relations**: Distinguishing `"the revised rules"` from `"the original award letter"`.
- **Contrast, Negation & Correction**: Natural conversational corrections (`"Not X, send Y"`, `"Skip the invoice"`, `"I meant the coordinator's note, not the assistant coordinator's"`).
- **Attachment & Ownership Semantics**: Explicit attachment phrases (`"the PDF attached to that order"`) and possessive ownership qualifiers (`"the dean's recommendation note"`, `"Sarah's appraisal review"`, `"mother's prescription"`).
- **Multi-Reference Turns**: 8 complex user utterances decomposed into 16 paired single-reference query cases (`S4B-075A/B`, `S4B-076A/B`, `S4B-077A/B`, `S4B-101A/B`, `S4B-102A/B`, `S4B-121A/B`, `S4B-122A/B`, `S4B-134A/B`).

## 7. Annotation-Boundary & Hard Cases Documented

To ensure benchmark transparency, difficult annotation cases were documented with explicit rationales:
- **S4B-020 (`Syndicate_Meeting_Minutes.docx`)**: Two candidates share the exact verbatim title with no date or meeting number in the query. Ground truth is strictly `AMBIGUOUS`.
- **S4B-048 (`"the latest tender document"`)**: Two tenders exist, but both share default `recency_rank == 0` with no relative ordering established. Ground truth is `AMBIGUOUS`.
- **S4B-054 (`"the recent ones"` after excluding July)**: Negation excludes July, leaving August and September minutes. The user did not specify one over the other; ground truth is `AMBIGUOUS` over the two survivors.
- **S4B-055 (`"the exam circular"` with only fee circulars)**: The user rejects both candidates and asks for an exam circular. Ground truth is `UNKNOWN`.
- **S4B-067 (`"he"` with two professors)**: Unanchored masculine pronoun with two plausible male faculty heads. Ground truth is `AMBIGUOUS`.
- **S4B-128 (`"the email from Dr. Sen"`)**: In a mixed personal/work environment, both university and personal Gmail accounts contain an email from a "Dr. Sen". Ground truth is `AMBIGUOUS`.

## 8. Dataset Quality Checks Performed Prior to Freeze

1. **Contract Invariant Validation**: Passed 100% via `validate_rar_resolution` (anti-invention, non-empty candidate IDs for `RESOLVED`, $\ge 2$ candidates for `AMBIGUOUS`, null candidate IDs for `UNKNOWN`).
2. **ID Uniqueness**: Verified all 136 fixture IDs are strictly unique.
3. **No Unrealistic Metadata**: Metadata fields restricted to valid dataclass parameters.
4. **Order Invariance**: Candidate arrays ordered naturally without positional bias assumptions.
5. **Human Language Realism**: Utterances reflect natural office/personal phrasing rather than artificial grammar puzzles.

## 9. Final Benchmark Author Confirmation

I confirm that:
1. `uri_v1/turn/rar_stage4b_independent_fixtures.py` was authored completely independently of resolver implementation details and historical evaluation logs.
2. The RAR resolver was never executed during this batch.
3. No RAR qualification score has been produced or inspected.
4. The benchmark is frozen and ready for independent evaluation in a separate session.
