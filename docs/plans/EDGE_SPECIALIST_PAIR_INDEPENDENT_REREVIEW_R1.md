# Edge Specialist Pair: Independent Re-Review of r1

- **Target:** docs-only commit `0bc6638` on `claude/needle-granite-planning-nqic37` (r1). It revises r0 (`8305f9c`) in response to the review `0be2c32` (`docs/plans/EDGE_SPECIALIST_PAIR_INDEPENDENT_REVIEW.md` on this branch).
- **Reviewer:** the same independent Claude thread that reviewed r0, standing in for Codex (paused). Review only: the plan is not edited, and nothing is implemented or run.
- **Date:** 2026-09-29.

## Verdict

**`ACCEPTABLE_WITH_BOUNDED_REPAIRS`.**

Every HIGH and MEDIUM finding from `0be2c32` is resolved in the r1 text, and all the LOW findings are resolved as well. The plan is still docs-only, the frozen boundaries are intact, and it follows the 10:36 and 10:48 principles. The new eligibility card is consistent with the evidence, and its recommendation (extraction first) follows from it.

Re-checking r1 found one new MEDIUM (N-1) and three LOW items (N-2 to N-4). None of them blocks Chetan's card decision. N-1 should be repaired in the documents before step 1 (battery authoring).

## 0. Acceptance criteria (defined first)

| ID | Criterion |
|---|---|
| RR-1 | Each finding from `0be2c32` is resolved in the r1 text, not merely acknowledged in a revision log. |
| RR-2 | r1 is docs-only, and the frozen guard and import boundary still pass. |
| RR-3 | r1 still follows Chetan's 10:36 role split and 10:48 measured-value rule. |
| RR-4 | The new card's options and recommendation match the repository evidence. |
| RR-5 | New defects introduced or exposed by r1 are identified, with severity. |
| RR-6 | Corrections to this reviewer's own earlier claims are recorded, not silently dropped. |

## 1. Evidence

- `git diff --name-only 5bbf738 0bc6638` lists only the four `docs/` files. With the `0bc6638` tree checked out, `pytest tests/test_m37_edge_resolution.py -k "frozen or boundaries"` gives **2 passed**.
- `ba0db5e` and `736464a` are ancestors of `origin/claude/project-thread-wb7tmm` and are not on the plan's base. This confirms the MP §6 ordering note.
- I read the full r1 text of S2A §3, §5–§9, §17, §21 and §23; QP §1–§12; MP §3–§12; and the S1A r1 diff. I also read the planning thread's new card.

## 2. Findings from `0be2c32`: resolution check

| Finding | Where r1 repairs it | Resolved? |
|---|---|---|
| H-1 direct envelope empty | S2A §5.1 (P-1 to P-5, each with its authority), §17 deferral, §21; QP §1 and §3.1 (deferred specification, authored from sampled real requests, D-PARA kept); MP step P; S1A RC-13 | **Yes** |
| H-2 residual decided by the oracle; the reply silently drops the rest | QP §3.1 D-RES rule fixed before authoring: any execution is incorrect and "harmless" entries are forbidden. S2A §9 adds a fixed "nothing else was done" sentence, enforced by Z-10. G-D3 and D-1 disclose that E-a is predicted to fail. | **Yes** |
| M-1 E-a precedent overstated | S2A §5.3 (`task_complex`, `routing_policy.py:77-80`); MP D-1 row; S1A §9 item 4 | **Yes** |
| M-2 not all components reject-only | S2A §3.2: N2 is named the admission authority, and the reject-only claim is limited to N3–N5 | **Yes** |
| M-3 single-model S6 readiness | S2A §6 step 5: a per-specialist in-memory settings view over real inventory entries; N1 opt-in; new D-5; `settings.py`/`runtime_inventory.py` unchanged | **Yes.** The view keeps the user's mode, Edge ON/OFF and explicit selection, so constraints 14–16 hold. |
| M-4 model copying values | S2A §7: choice only, URI fills, emitted values discarded and counted as `arg_copy_mismatch`; §8 sends no bound values; Z-2 restated; one-entry shortlist needs no model | **Yes** |
| M-5 pronoun vs binding state | S2A §5.2; QP D-STRUCT keys on binding state; new D-BOUND | **Yes** |
| M-6 extraction value and serial inference | S2A §6 step 11 (SUPPORTING is parallel or deadline-bounded); QP E-SUB, X-ASSIST, G-E5, G-E6 and the per-role value dimension | **Yes.** See N-1 for a gap this exposes. |
| M-7 Brain transport; regression thresholds | QP §7: local Ollama Brain only, with the reason and a cloud-spend stop rule; numeric regression thresholds added | **Yes.** One stale line remains (N-2). |
| L-1 142/150 | G-D1 and G-E1 now read 143/150 | Yes |
| L-2 wrong reason | Inline correction in QP §11 | Yes |
| L-3 weak injection gate | E-INJ raised to 150 documents; G-E3 ≤ 1/150 | Yes |
| L-4 citation | S2A §11 | Yes |
| L-5 defaulted `effect_type` | S2A §5.2 and §7; QP D-STRUCT case; Z-14 | Yes |
| L-6 N6 location | MP §3 and step 7: new file; `routing_policy.py` not edited | Yes |
| L-7 guard ordering with M39 | MP §6 | Yes (ancestry verified, §1) |
| L-8 CLARIFY in diagram | S2A §2 | Yes |

## 3. New findings on r1

**N-1 (MEDIUM). `EXTRACTION_V1` has no admission or field-selection producer, yet r1 calls it "qualifiable now".**
- S2A §6 step 11 says extraction "follows steps 0–10". The only producer of `edge_sufficient` there is N2, and N2 is defined for `DIRECT_TOOL_V1` only (§3.2, §6 step 4). Nothing in r1 says:
  - what decides that a turn is an extraction request;
  - which closed schema or field list applies; or
  - how a question like "What is the invoice number in this attachment?" (QP E-SUB) maps to a schema field.
- That mapping is interpretation. For the SUBSTANTIVE path it is the same unproduced `task_complex` gap that M-1 found for the direct class.
- What *is* measurable now: the field-accuracy segments (E-POS through E-NEG), where the battery supplies the schema, and X-ASSIST if the assist's schema is fixed per document type.
- What is not yet specified: the E-SUB / G-E5 path, and live L1 routing for substantive extraction.

Repair, in the documents before step 1, one of:
- (a) name a deterministic producer: extraction runs only when a registered capability or deterministic flow requests a declared closed schema, never from free-text classification;
- (b) defer E-SUB the same way as the direct class, and keep extraction to SUPPORTING and schema-given use.

Either way, the QP should say whether E-SUB scoring includes the routing decision or starts from a given schema. This does not change the card recommendation.

**N-2 (LOW).** QP §9 still says the run needs "his subscription Brain session". That contradicts QP §7 r1 (local Ollama Brain only) and should be removed.

**N-3 (LOW).** S2A §5.1 P-4 lists "Get 2021CS042." as `affirmative_context()` False, and S2A §23 says the review's True was wrong. Both results are correct under different conventions:
- On the full string it is False.
- With the reference removed it is True. That is the convention the design itself uses (`affirmative_around`, `envelope.py:87-93`), and the one S1A §4 used.

The P-4 row should state the convention. The conclusion of H-1 is unaffected, because P-2 (no roll-number span producer) excludes that action regardless.

**N-4 (LOW). The card context overstates Stage-1.** It says models "substituted reads 7 or 8 times in 8". The raw records show otherwise:
- The 0/8 and 1/8 figures are **withholding** rates over the must-withhold cases T13–T20. Half of those cases are missing-argument cases, not substitutions.
- On the four unsupported requests (T17–T20), both models chose another tool every time (Needle 4/4, Granite 4/4). Several of those choices were `draft_message`, not a read.

The recommendation is unaffected. **Correction to `0be2c32` (RR-6):** my H-2 wording ("Stage-1 T17–T20: Granite withheld 0/8 and Needle 1/8 … both substituted an available read") had the same conflation. The accurate statement is: withheld 0/8 (Granite) and 1/8 (Needle) over T13–T20; on T17–T20, both substituted another available tool 4/4. The original text of `0be2c32` is left unchanged, and this is the recorded correction.

## 4. Principles (RR-3)

- **10:48 measured value.** Both models are measured on every overlapping class. No role is assigned. Deferring the direct class comes from repository evidence (P-1 to P-5), not from model size or intended purpose. The optional QP §3.4 selection diagnostic gives both models a direct-choice comparison if Chetan wants one before funding the prerequisites.
- **10:36 role split.** It said Needle proposes "exactly one registered tool with exact grounded arguments". r1 has the model choose the tool and URI fill the arguments. That is stricter than the original wording, and consistent with "the URI runtime holds all authority". Chetan should still see it as a deliberate change to the literal role statement.
- **Fixed decisions.** Edge OFF bypasses both models (Z-6). EDGE_ONLY never substitutes (Z-7; S6 view preserves mode). Stage-1 stays exploratory. No frozen scope is reopened, and P-4 explicitly leaves the M36 vocabulary unchanged.

## 5. The new card (RR-4). The decision stays with Chetan.

- The card's four options match S2A §5.4 and MP D-1.
- Each option's stated consequence matches the evidence: E-a's predicted failure, E-b's near-redundancy under URI-filled arguments, and the absence of support for E-c.
- The recommendation (extraction first) follows from H-1.

Two notes for Chetan:
- The context line overstates Stage-1 slightly (N-4).
- "Compare both models on extraction now" holds for field accuracy and assists. Substantive answering needs the N-1 repair first.

## 6. Not verified

- The full test suite was not run; the change is docs-only, and the guard and boundary tests were run.
- No model was run.
- The planning thread's own probe outputs were not re-run beyond the one disputed row (N-3).

None of these affects the verdict.

## 7. Self-review against §0

- **RR-1** Met: §2 checks each finding against r1 text, not the revision log.
- **RR-2** Met: §1.
- **RR-3** Met: §4.
- **RR-4** Met: §5.
- **RR-5** Met: §3.
- **RR-6** Met: the N-4 correction.

One defect was found in my first draft of this re-review and repaired: I had treated the "Get 2021CS042." dispute as r1 being wrong. Re-running the probe showed both results are correct under different conventions (N-3), so the finding now asks for the convention to be stated rather than for a value to change.
