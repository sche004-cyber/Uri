# M35 URIv1 — Independent Audit of RAR Natural-Boundary Discovery

**Document Type:** Independent Verification and Evidence Audit  
**Auditor:** Antigravity (Gemini 3.8 Flash, Development Loop Manager / Independent Auditor)  
**Target Documents Audited:**
1. `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md` (authored by Claude CLI)
2. `docs/plans/M35_URIV1_PRE_RAR_CANDIDATE_ANCHOR_SOURCE_AUDIT.md` (authored by Claude CLI)

**Repository State:**
- Primary Repository: `C:\Users\cheta\Development\Uri\_V1`
- Active Branch: `m35-uri-v1-parallel-architecture`
- Commit HEAD: `e8e3b65259c45fc823addc3ef8969425a265bd1b`
- Protected Legacy Repository: `C:\Users\cheta\Development\uri-agent` (Strictly READ-ONLY, inspected without modification)

**Audit Status:** `VERIFICATION_READY`

```xml
<audit_state>
  <current_phase>INDEPENDENT_EVIDENCE_AUDIT</current_phase>
  <allowed_actions>read code, verify AST/regex/imports, inspect test suites, verify historical evidence, apply bounded plan corrections, write independent audit report</allowed_actions>
  <prohibited_actions>implement benchmark code, execute RAR, train/qualify models, modify production call paths, modify protected legacy repository, git commit, git push</prohibited_actions>
  <exit_criteria>independent audit report complete with full claim matrix, taxonomy verification, experimental grid audit, corrections applied, and final execution readiness verdict</exit_criteria>
  <stop_condition>VERIFICATION_READY</stop_condition>
</audit_state>
```

---

## 1. Executive Summary & Audit Scope

This document provides a rigorous, code-grounded independent verification of the claims, findings, and experimental design set forth in Claude's RAR Natural-Boundary Discovery Plan and Pre-RAR Candidate Anchor Source Audit.

In accordance with AO-4 governance and the non-negotiable principle **"Do not trust model summaries or conversational memory; verify actual repository state"**, Antigravity independently inspected the production codebase, test suites, evaluation scripts, and historical benchmark artifacts in both `Uri\_V1` and `uri-agent`.

### Key Conclusions:
1. **Core Findings Validated:** Claude's primary discoveries are **factually sound and verified by code**. Specifically, RAR's deterministic resolution logic has only ever been tested against artificial/oracle inputs; `ActiveContext` lacks any production builder in `uri_v1`; and `TurnFrame`'s reference extraction is a bounded regex pattern matcher rather than general semantic segmentation.
2. **Key Refinements & Corrections Applied:**
   - **Pattern Count Correction:** `TurnFrame` contains **21 literal regex patterns** (9 single pronouns and 12 multi-word phrases), rather than 19.
   - **Active Pointer Clarification:** `TurnState._project_active_pointer` is not merely an unwired legacy concept; it is **actively implemented and wired** into `TurnState.assemble_turn_state()` in `uri_core/core/turn_state.py:175`. However, it remains completely disconnected from `uri_v1/turn/`.
   - **C3 Execution Reality:** Condition C3 (zero candidate pool) is the literal current condition of the `uri_v1` pipeline if invoked today, rather than a failure of live `uri_core` `/ask` production traffic (which does not invoke `uri_v1` RAR).
3. **Execution Readiness:** The proposed 5-cell 2D natural-boundary experiment is **grounded in code reality and ready to implement** (`READY_AFTER_BOUNDED_CORRECTIONS`).

---

## 2. Claim-by-Claim Evidence Matrix

Each claim from Claude's audit and plan was subjected to line-by-line verification against repository source code.

| Claim | Topic | Verdict | Primary File(s) & Lines | Verification Method & Evidence |
|---|---|---|---|---|
| **A** | TurnFrame Reference Extraction Mechanism | `VERIFIED_WITH_REFINEMENT` | `uri_v1/turn/turn_frame_builder.py:38-60, 183-207` | **AST & Regex Inspection:** Contains `REFERENCE_PATTERNS` tuple with **21 literal regex patterns** (9 pronouns + 12 phrases). Deduplicated per clause, sequential `r1`, `r2` IDs, zero semantic reasoning. Refines Claude's estimate of 19 patterns. |
| **B** | RAR Input Contract & Provenance | `VERIFIED_FACTUAL` | `uri_v1/turn/rar_contracts.py:15-65`, `uri_v1/turn/lfm_semantic_decoder.py:320-366`, `uri_v1/turn/lfm_multi_feed_runtime.py:200-213` | **Call Path Analysis:** `reference_expression` is passed from `TurnFrame`; `candidates` has 0 production builders; `recency_hint` is hardcoded literal `"same"`/`"same thing"`; `negation_spans` is turn-global; `target_type_hint` and `RARDeterministicAnchor` have 0 production construction sites. |
| **C** | RAR Level 0/1 (DET-ONLY) Live Reachability | `VERIFIED_FACTUAL` | `uri_v1/turn/rar_deterministic.py:112-140`, repo-wide grep | **Grep & AST Analysis:** Zero production calls construct `RARDeterministicAnchor`. Levels 0/1 are architecturally present in `rar_deterministic.py` but 100% dead/unreached in live runtime execution. |
| **D** | `uri_core/` is Active Production Backend | `VERIFIED_FACTUAL` | `scripts/run_uri_server.py:1-25`, `uri_core/app/server.py:1-50`, `uri_core/core/turn_state.py:1-240` | **Entrypoint & Runtime Inspection:** `run_uri_server.py` boots `uri_core.app.server:app`. Session management, TurnState assembly, FileStore, and CapabilityContextResolver are actively running in production. |
| **E** | Disconnection Between `uri_core` and `uri_v1/turn` | `VERIFIED_FACTUAL` | Repo-wide import search | **Zero Import Verification:** Grep confirmed 0 static or dynamic imports connecting `uri_core/` to `uri_v1/turn/`. No shared object injection or runtime bridges exist. |
| **F** | Candidate/Anchor State in `uri_core` | `VERIFIED_FACTUAL` | `uri_core/core/file_store.py:12-45`, `uri_core/capabilities/context_resolver.py:25-145`, `uri_core/core/turn_state.py:175-225` | **Code Inspection:** `FileStore.to_reference()` provides durable attachment metadata; `CapabilityContextResolver` preserves last-action IDs; `SessionState` tracks workflows; `TurnState` projects context. |
| **G** | Genuinely Absent Concepts | `VERIFIED_FACTUAL` | `uri_core/`, `uri_v1/` search | **Negative Verification:** Backend contains 0 tracking for `selected_ui_id`, no unique title matching across arbitrary entities, and no ranked recency across multiple candidates. |
| **H** | ARN vs. RAR Architectural Distinction | `VERIFIED_FACTUAL` | `uri_core/core/arn/engine.py:42-130`, `uri_v1/turn/rar_deterministic.py:1-440` | **Behavioral Comparison:** ARN is multi-step stateful recovery when search returns empty (`NOT_FOUND`); RAR is single-turn binding against an available bounded candidate set. Different problems entirely. |
| **I** | `CapabilityContextResolver` Lineage & Anti-Pattern | `VERIFIED_FACTUAL` | `uri_core/capabilities/context_resolver.py:128, 144` | **Code Verification:** Shares principle of retaining action output IDs without hallucination, but contains silent first-item bias (`messages[0]`, `attachments[0]`). RAR explicitly rejects first-item bias. |
| **J** | `TurnState.active_pointer` Status | `VERIFIED_WITH_REFINEMENT` | `uri_core/core/turn_state.py:175-225`, `uri_core/core/turn_manager.py` | **Code Verification:** Live and wired into `TurnState.assemble_turn_state()` in `uri_core`. Re-derives active pointer fresh each turn. Missing in `uri_v1/turn/`, not missing in `uri_core`. |

---

## 3. Deep-Dive Verification of Specific Claims

### Claim A: TurnFrame Reference Extraction Mechanism
- **Verification Target:** What does `TurnFrame` actually extract, and how?
- **Code Grounding:** `uri_v1/turn/turn_frame_builder.py:38-60` defines `REFERENCE_PATTERNS`.
- **Exact Pattern Count:** Exactly **21 regex patterns** (case-insensitive regex matching):
  1. `\bthe\s+one\s+we\s+just\s+created\b`
  2. `\bthe\s+earlier\s+one\b`
  3. `\bearlier\s+one\b`
  4. `\bsame\s+thing\b`
  5. `\bsame\s+version\b`
  6. `\bthat\s+file\b`
  7. `\bthis\s+file\b`
  8. `\bthis\s+one\b`
  9. `\blatest\s+letter\b`
  10. `\bprevious\s+approval\b`
  11. `\battached\s+pdf\b`
  12. `\bthis\s+spreadsheet\b`
  13. `\bthis\b`
  14. `\bthat\b`
  15. `\bit\b`
  16. `\bthem\b`
  17. `\bhim\b`
  18. `\bher\b`
  19. `\bthey\b`
  20. `\bthese\b`
  21. `\bthose\b`
- **Mechanism Details (`turn_frame_builder.py:183-207`):**
  - Runs `re.finditer` over lowercased clause text.
  - Matches are deduplicated per clause.
  - Generates `CandidateReference(id="r1", expression=match_text, ...)`.
  - Zero semantic inference, zero dependency parsing, zero noun-phrase chunking.
- **Finding:** Claude's report stated "19 patterns" based on approximate grouping; verified count is 21. Plan updated accordingly.

### Claim B: RAR Input Contract & Provenance
- **Verification Target:** What feeds `RARQuery` in production call paths?
- **Code Grounding:**
  - `lfm_semantic_decoder.py:345-356`:
    ```python
    for cand_ref in turn_frame.candidate_references:
        ref_expr = cand_ref.expression
        evidence = RAREvidence(
            recency_hint="same" if ref_expr in ("same", "same thing") else None,
            negation_spans=turn_frame.negation_spans,
        )
        query = RARQuery(
            reference_expression=ref_expr,
            candidates=tuple(candidates),
            local_evidence=evidence,
        )
        trace = resolve_rar_deterministic_extended(query)
    ```
  - `lfm_multi_feed_runtime.py:200-213`:
    ```python
    if referring_expression and candidate_pool:
        query = RARQuery(
            reference_expression=referring_expression,
            candidates=tuple(candidate_pool),
            local_evidence=RAREvidence(
                recency_hint="same" if referring_expression in ("same", "same thing") else None,
                negation_spans=turn_frame.negation_spans if turn_frame else (),
            ),
        )
        rar_trace = resolve_rar_deterministic_extended(query)
    ```
- **Provenance Breakdown:**
  1. `reference_expression`: `REAL_BUT_EXPERIMENTAL` (derived from `TurnFrame`'s 21 patterns).
  2. `candidates`: `BENCHMARK_SUPPLIED` (`ActiveContext` has 0 production builder sites; in `lfm_semantic_decoder.py:320-339`, all `recency_rank` values are hardcoded to `0`).
  3. `recency_hint`: `REAL_BUT_NARROW` (`"same"` if `ref_expr in ("same", "same thing") else None`).
  4. `negation_spans`: `REAL_BUT_UNSCOPED` (turn-global list from `turn_frame.negation_spans`, passed without clause association).
  5. `target_type_hint`: `CURRENT_GAP` (0 production call sites across `uri_v1/`).
  6. `RARDeterministicAnchor`: `CURRENT_GAP` (0 production construction sites across `uri_v1/`).

### Claim C: RAR Level 0/1 Reachability
- **Verification Target:** Does any live code invoke Level 0/1 deterministic anchor logic?
- **Code Grounding:** `uri_v1/turn/rar_deterministic.py:112-140`.
- **Finding:** Levels 0 and 1 evaluate `local_evidence.deterministic_anchor`. Because neither `lfm_semantic_decoder.py` nor `lfm_multi_feed_runtime.py` nor any other call site constructs `RARDeterministicAnchor`, these levels are unreachable in production. They were only executed inside synthetic test harnesses (`test_m35_uriv1_a2_5_deterministic_rar.py`, `scripts/m35_rar_deterministic_eval.py`).

### Claims D & E: `uri_core` Runtime Reality and Total Disconnection
- **Verification Target:** Is `uri_core` real, and is it connected to `uri_v1/turn/`?
- **Code Grounding:**
  - `scripts/run_uri_server.py:20`: imports `uri_core.app.server:app`.
  - `uri_core/core/turn_state.py`: assembled by `TurnManager` on every live request.
  - Search across all `.py` files in `uri_v1/turn/` for `uri_core` yields **0 hits**.
  - Search across all `.py` files in `uri_core/` for `uri_v1` yields **0 hits**.
- **Finding:** `uri_core` is the live backend, and `uri_v1/turn/` is an isolated experimental subsystem.

### Claims F & G: Available vs. Genuinely Absent Concepts
- **Available in `uri_core` (Situation B):**
  - Durable file attachments via `FileStore.to_reference()` (`file_id`, `filename`, `media_type`, `size_bytes`).
  - Follow-up ID binding via `CapabilityContextResolver`.
  - Session/workflow tracking via `SessionState.active_workflow_id`.
  - Full turn-context projection via `TurnState.assemble_turn_state()`.
- **Genuinely Absent in Repository (Situation A):**
  - UI focus / selection state (`selected_ui_id`).
  - Generalized artifact title matching across arbitrary documents.
  - Singular selection rule when multiple attachments exist.

### Claim H: ARN vs. RAR Architectural Distinction
- **Verification Target:** Are ARN and RAR redundant or conflicting?
- **Code Grounding:** `uri_core/core/arn/engine.py:42` vs. `uri_v1/turn/rar_deterministic.py:100`.
- **Finding:** ARN is an interactive, multi-step recovery process invoked when a capability query returns 0 results (`CandidateDiscoveryResult.EMPTY`), using eliminations and clarification recommendations. RAR is an intra-turn resolver that binds referring expressions to candidate entities before execution. They address completely distinct failure boundaries.

### Claim I: `CapabilityContextResolver` Lineage & Anti-Pattern
- **Verification Target:** What does `CapabilityContextResolver` do, and what does it teach RAR?
- **Code Grounding:** `uri_core/capabilities/context_resolver.py:128` (`_first_message`), `line 144` (`_first_attachment`).
- **Finding:** Takes index `[0]` blindly when multiple items match. RAR's design explicitly prevents this by returning `AMBIGUOUS` whenever two candidates tie or lack distinguishing evidence.

### Claim J: `TurnState.active_pointer`
- **Verification Target:** Where is `active_pointer` located and is it live?
- **Code Grounding:** `uri_core/core/turn_state.py:175`:
  ```python
  def _project_active_pointer(self, session: Session) -> Optional[ActivePointer]:
  ```
  Called by `TurnState.assemble_turn_state()` at line 120.
- **Finding:** It is fully implemented and live in `uri_core`. The plan originally implied it was an unwired paper design. The plan has been refined to note that it is live in `uri_core`, but disconnected from `uri_v1/turn/`.

---

## 4. Historical Evidence Validity Evaluation

Antigravity audited all prior benchmark datasets and qualification reports referenced in M35.

| Benchmark Stage | Fixture Count | Provenance & Independence | Realism Assessment | Reusability for Natural-Boundary Run |
|---|---|---|---|---|
| **Stage 2** | 24 | Self-authored by resolver implementer | Synthetic queries, hand-curated candidate sets. Tested basic cascade routing. | **Invalid for coverage:** Oracle inputs bypass `TurnFrame` and `ActiveContext` gaps. |
| **Stage 3** | 103 | Self-disclosed "not blind" procedural separation | Handcrafted expressions and candidate pools. Targeted Level 4-6 coverage. | **Invalid for coverage:** Does not test raw-text extraction or candidate-pool absence. |
| **Stage 4** | 103 (Refit) | Refitted to Stage 3 set (RC-1, RC-2) | Tuned tie-breaking and recency keywords. | **Invalid for coverage:** Measures code fixes against familiar synthetic data. |
| **Stage 4B-A** | 136 | Independently authored by separate agent session | Independent author, but provided pre-segmented `reference_expression` strings. | **Partial / Lower-Bound:** Proved 86.8% of cases needed signals beyond `TurnFrame`, but did not measure `TurnFrame` recall on raw text. |
| **Stage 4B-C** | 136 | Reconciliation run of Stage 4B-A | Isolated root causes (Mechanism A/B/C/D). | **Diagnostic Benchmark Only:** Excellent failure attribution, but still downstream of segmentation. |
| **Challenge 100** | 100 | Unverified provenance (`rar_challenge_fixtures.py`) | Hand-coded challenge cases, authorship unverified. | **Unusable:** High risk of test fixture drift or contamination. |

**Verdict:** Zero existing fixture sets start from raw user text or test `TurnFrame`'s extraction recall. A fresh raw-text benchmark starting upstream of `TurnFrame` is mandatory.

---

## 5. Experimental Grid Audit

### Evaluation of Claude's Proposed 2D Grid

Claude proposed a 5-cell 2D grid crossing **Axis 1 (Step-1 Input Realism)** and **Axis 2 (Candidate-Pool Realism)**:

```
                      C1: Clean Pool    C2: Realistic Distractors    C3: No Candidate Pool
S1: Real Wired Path     [S1 × C1]               [S1 × C2]                   [S1 × C3]
S2: Oracle Input        [S2 × C1]               [S2 × C2]                  (Degenerate)
```

### Verification Findings:
1. **Rejection of 1D Ladder:** The task prompt originally suggested a 1D ladder ("raw → plus surface info → plus other info → existing RAR"). Claude correctly rejected this. Input extraction and candidate pool availability are orthogonal failure points. A 1D ladder would confound Step-1 misses with candidate-pool deficits.
2. **Omission of S2 × C3:** If the candidate pool is empty ($C3$), an oracle reference expression ($S2$) can only produce `UNKNOWN` / `NO_CANDIDATES`. It yields no discriminatory signal. Omitting this cell is mathematically and experimentally correct.
3. **Condition C3 Clarification:** C3 must be reported as "the literal current state of the disconnected `uri_v1` pipeline," not as an active runtime bug in `uri_core`.
4. **Candidate Pool Realism for Attachments:** Candidate pools for attachment fixtures should mirror `uri_core/core/file_store.py`'s `StoredFile.to_reference()` schema (`file_id`, `filename`, `media_type`, `size_bytes`) to ensure structural fidelity without requiring live database connections.

---

## 6. Failure Taxonomy Audit

Antigravity verified the 10 proposed failure classes in §10 of the Natural-Boundary Plan against codebase behavior and edge cases:

1. `SILENT_STEP1_MISS`: Observable when raw turn has a referring expression, but `TurnFrame.candidate_references` extracts nothing because it is outside the 21-pattern vocabulary. RAR is never called. **(Verified: Fully observable under S1).**
2. `MISSING_CANDIDATE_CONTEXT`: Reference is extracted, but candidate pool is empty ($C3$) or lacks the target entity. **(Verified: Core failure under real unwired state).**
3. `CORRECT_ABSTENTION`: RAR outputs `AMBIGUOUS` or `UNKNOWN` when the input is genuinely underspecified. Counted as success. **(Verified: Upholds URI safe-abstention invariant).**
4. `INCORRECT_CONFIDENT_BINDING`: RAR resolves to a candidate ID that is incorrect according to ground truth. **(Verified: The critical safety failure observed in Stage 4B).**
5. `UNSAFE_OVER-ELIMINATION`: Candidate wrongly eliminated because `negation_spans` is turn-global rather than clause-bound. **(Verified: Directly grounded in `lfm_semantic_decoder.py:349`).**
6. `RECENCY_SIGNAL_UNREACHABLE`: Requires recency resolution ("latest", "previous"), but caller only provides `"same"` or `None`. **(Verified: Grounded in `lfm_semantic_decoder.py:348`).**
7. `TYPE_DISCRIMINATION_UNREACHABLE`: Requires type discrimination, but `target_type_hint` is missing in production caller. **(Verified: Grounded in absence of `target_type_hint`).**
8. `DISTRACTOR_CONFUSION`: Resolves correctly under $C1$, but binds incorrectly under $C2$ due to lexical or recency overlap. **(Verified: Measures Level 4b/6 robustness).**
9. `INVENTED_CANDIDATE`: RAR returns an ID not present in the candidate pool. Hard safety invariant; expected count is 0. **(Verified: Checked by `validate_rar_resolution`).**
10. `UNSUPPORTED_INPUT_TYPE`: True resolution requires semantic world knowledge beyond lexical/type/recency rules. **(Verified: Identifies true AI boundary).**

**Verdict:** The taxonomy is exhaustive, disjoint, and fully grounded in verifiable code mechanisms.

---

## 7. Plan Corrections Applied

In accordance with the audit authorization, Antigravity made minimal, bounded factual corrections directly to `docs/plans/M35_URIV1_RAR_NATURAL_BOUNDARY_DISCOVERY_PLAN.md`:

1. **Pattern Count Correction (§3, §4, §5, §9, §10, §13, §Summary):**
   - Corrected all occurrences of "19 patterns" / "~19 patterns" to **21 literal patterns** (9 single pronouns, 12 multi-word phrases) matching `uri_v1/turn/turn_frame_builder.py:38-60`.
2. **Active Pointer Reality Refinement (§6, line 94):**
   - Clarified that `TurnState.active_pointer` is already live and tested in `uri_core/core/turn_state.py:175` (`TurnState.assemble_turn_state()`), but is disconnected from `uri_v1/turn/`.
3. **Condition C3 Characterization (§9 Amendment, line 138):**
   - Refined C3 to state that it represents the literal condition of `uri_v1/turn/` if invoked today, without conflating it with the behavior of live `uri_core` `/ask` production traffic.

---

## 8. Anti-Contamination & Integrity Controls

The implementation of the benchmark must enforce the following frozen controls:
1. **Isolated Benchmark Files:** Fixtures must reside in a dedicated test file (e.g., `tests/test_m35_rar_natural_boundary.py` or `scripts/m35_rar_natural_boundary_eval.py`). No production code (`uri_v1/turn/*`) may be modified.
2. **No Reverse-Fitting:** Fixture text must be authored against realistic office-work scenarios without consulting `turn_frame_builder.py` pattern lists or `rar_deterministic.py` weights during authoring.
3. **Immutable Resolution Engine:** `rar_deterministic.py` must run completely unmodified.
4. **Separate Scoring Pipeline:** Taxonomy scoring must be computed by an external evaluator reading `DeterministicRARTrace` outputs and ground-truth labels.

---

## 9. Execution-Readiness Verdict

### Final Assessment: `READY_AFTER_BOUNDED_CORRECTIONS`

**Rationale:**
- Claude's core architectural findings and audit evidence are confirmed by independent code inspection.
- The minor factual inaccuracies (19 vs. 21 patterns, active pointer wiring nuance, C3 live traffic vs. disconnected pipeline distinction) have been corrected directly in the discovery plan.
- The 5-cell 2D experimental grid and 10-class failure taxonomy provide a sound, non-confounded method to measure the true natural boundary of deterministic RAR.
- The experiment is ready for implementation by the designated implementation worker.

---

## 10. Summary for User Review

1. **Independent Audit Complete:** Full verification of Claude's M35 RAR Discovery Plan and Source Audit has been executed against both `Uri\_V1` and protected `uri-agent`.
2. **Factual Integrity Verified:** Claude's primary claims are supported by code reality:
   - RAR has never been evaluated against real raw text in any milestone.
   - `ActiveContext` has no production builder in `uri_v1`.
   - Production call paths pass narrow or unscoped evidence (`recency_hint` only `"same"`, turn-global `negation_spans`, 0 `target_type_hint`).
   - `RARDeterministicAnchor` (Levels 0/1) is never reached in live code.
3. **Plan Refinements Applied:** Corrected pattern count to 21, reconciled active pointer status in `uri_core`, and clarified C3 operational context.
4. **Next Step:** Awaiting User acceptance to initiate benchmark fixture construction and execution under AO-4 process. Stop condition `VERIFICATION_READY` reached.
