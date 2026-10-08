# M35 URIv1 — Step 2 State Reconstruction: Needle 3 + Deterministic RAR

**Type:** Inspection / evidence reconstruction only. No implementation, no execution, no repair, no commit/push performed under this document.
**Workspace verified:** `C:\Users\cheta\Development\Uri\_V1`, branch `m35-uri-v1-parallel-architecture`, HEAD `e8e3b65259c45fc823addc3ef8969425a265bd1b`.
**Status:** `VERIFICATION_READY`

---

## 1. Executive State

URI v1 development physically advanced past its actual build position. A2.9 (Qwen3.5-9B native problem-solving trace, a *different* axis — closed-loop agentic reasoning, not Step-1 semantic decoding) was executed and is now `VERIFICATION_READY / PARKED / downstream reference experiment`. But **Step 2 — establishing the user's intent/problem reliably and cheaply — was never actually closed.**

As of this reconstruction:

- **Deterministic RAR** has a real, working implementation (`uri_v1/turn/rar_deterministic.py`) with a proven core on deterministic-anchor cases, but its true raw-turn coverage is **not quantifiable** from existing evidence — the only genuinely independent benchmark (Stage 4B) found 86.8% of its cases require reference-expression segmentation that RAR does not perform and that no code in this repo implements. RAR is not wired into any production pipeline.
- **Needle 3** was tested and **decisively rejected** as a full Step-1 semantic decoder across five separate batches (A2, A2.1, A2.3, A2.4R, and implicitly A2.2/A2.4 as comparison points). Two of those reports (A2.1 §23, A2.4R §11) explicitly propose a **narrower auxiliary/gatekeeper role** and state it "requires separate qualification" — but that qualification was never built or run.
- **A2.8D** is real, substantial, implemented code (a 6-variant Needle fast-path harness over a frozen 90-case benchmark) that has **zero documentation, zero tests, zero results, and zero qualification evidence anywhere in the repo.** It is not the same thing as the A2.8A–C "ARN"/BrainProfile architecture track. Its one production-adjacent file (`fast_path_gate.py`) is contaminated with literal hardcoded answers to its own benchmark's specific cases.
- The production semantic-decoder direction that actually succeeded moved to **Qwen3.5-9B resident dual-role** (A2.7, `QWEN3_5_9B_SEMANTICALLY_QUALIFIED`), not Needle — this happened *before* A2.8, and A2.8D's continued use of Needle post-dates that decision without acknowledging it.
- The "remembered pending direction" (Needle 3 + deterministic RAR in a narrow intent/uncertainty-gate role) is **not disproven**, but it is also **not established** — it is a hypothesis with two unfinished, structurally different prerequisite experiments, neither of which has been run.

---

## 2. Evidence Timeline

| Experiment | Question | Components | Evidence | Result | Status |
|---|---|---|---|---|---|
| A0 | Can a clean, isolated Step-1/2 skeleton be stood up? | 4 empty provider interfaces, placeholder contracts | 7 tests | Skeleton frozen, no logic | PROVEN (structural only) |
| A1 | What does a typed Step-1 semantic contract look like? | `DecodedRequest`, `SemanticOperation`, etc. | 15 new tests (22 total) | Contract frozen | PROVEN (contract only) |
| A1.1 | Does the contract need hardening before model integration? | Immutability, context-category neutrality, single decode signature | 8 new tests (30 total) | Contract hardened | PROVEN (contract only) |
| A2 (Batch A2) | Can base Needle 3 perform full 9-field monolithic decode from raw text? | Needle 3 gen-3, `.venv-needle` subprocess | 18 live cases | Structural 40%, semantic ~0%, overconfident-error pathology | REJECTED_FOR_THIS_ROLE |
| A2.1 | Does decomposing into 4 narrow schemas rescue Needle? | Needle 3, 4 narrow schemas, deterministic merger | 72 live inferences | Structural up, semantic ~0% across all 4 schemas | REJECTED_FOR_THIS_ROLE; narrow auxiliary role proposed (§23) |
| A2.2 | Can Qwen3.5-0.8B (reasoning-distilled) decode full schema? | Qwen 0.8B, constrained/unconstrained JSON modes | 18 prompts × 2 modes | Structural 94.4% constrained, semantic dismal, reference detection 0% | REJECTED_FOR_THIS_ROLE |
| A2.3 | Does full TurnFrame+ActiveContext scaffolding rescue Needle? | Needle 3, TurnFrame, ActiveContext, candidate-ID selection | 24 turns × variants | 95.8% contradiction rate, negation 0/24, active-context 0/24 | REJECTED_FOR_THIS_ROLE (permanently disqualified per report) |
| A2.4 | Is prior failure model-capacity-limited or harness-limited? | Qwen3-14B, TurnFrame/ActiveContext modes A/B/C | 54 live runs | Mode C 100% across all measured dimensions | PROVEN (harness validated; not a Needle verdict) |
| A2.4R | Fair head-to-head: Needle 3 vs Qwen3-14B, same harness, bias-corrected | Both models, Modes A–D | 86 invocations each | Needle: negation/active-context 0% all modes; Needle narrow-role signals (ref-presence 70%, reflex 78.8%) observed | REJECTED_FOR_THIS_ROLE (decoder); OBSERVED (narrow-role signal, unqualified) |
| A2.5 Stage 2 | Does deterministic RAR resolve references on self-authored fixtures? | `rar_deterministic.py`, 24 fixtures | 24/24 match | 100%, 0 wrong bindings | PROVEN (fit-biased — fixtures written during resolver dev) |
| A2.5 Stage 3 | Does RAR generalize to a larger, procedurally-independent set? | Same resolver, 103 fixtures | 91–92/103 | 88.3–89.3%, 0 wrong bindings; self-disclosed not truly blind | OBSERVED (not independent) |
| A2.5 Stage 4 | Do 4 targeted refinements (RC-1..RC-4) close the Stage 3 gaps? | Refined resolver, same 103 fixtures | 99/103 | 96.1%, 0 wrong bindings | OBSERVED (re-fit to same set, not independent) |
| A2.5 Stage 4B-A | Can a genuinely independent benchmark be constructed? | 136 fixtures, author never read resolver source | Independence confirmed | N/A (manifest only, no run) | PROVEN (independence property only) |
| A2.5 Stage 4B-B | What does RAR score on the independent set? | Resolver vs 136 independent fixtures, FULL + DET-ONLY modes | 122/136 FULL; 102/136 DET-ONLY | 89.7% FULL (6 wrong bindings, 4.4%); 75.0%/58.8% coverage DET-ONLY | OBSERVED (first nonzero wrong-binding rate) |
| A2.5 Stage 4B-C | Do 4B-B's own findings hold up under self-audit? | Reconciliation of 4B-B trace data | Corrected failure attribution; reference-expression provenance audit | True deterministic lower bound 19.9%, upper bound 73.5%, split unquantifiable; 86.8% of cases need unimplemented segmentation | OBSERVED + UNMEASURED (coverage split) |
| A2.6 | Can Qwen3.5-2B, with RAR+adaptive narrow feeds, decode Step-1? | Qwen3.5-2B, RAR, concurrent narrow feeds | 18 prompts + ladders | Goal 94.7% PASS; Requested Ops 73.7% FAIL; Negation 34.2% FAIL | REJECTED_FOR_THIS_ROLE (model); PROVEN (RAR+feed architecture) |
| A2.7 | Can Qwen3.5-9B resident dual-role decode + reason? | Qwen3.5-9B, RAR, narrow feeds, Main-Brain continuation | 38 frozen + 12 torture + 2 e2e | Goal 97.4%, Negation 100%, Torture 83.3% | PROVEN — `QWEN3_5_9B_SEMANTICALLY_QUALIFIED` |
| A2.8A | Does uncertainty discovery preserve structural signal cleanly? | `uncertainty_discovery.py`, `question_framing.py` | 12 cases | CUOR 0%, signal preservation 100% (after 1 fix) | PROVEN (12-case, explicitly self-limited) |
| A2.8B | Does RAR+ARN amplify raw model semantic accuracy? | 3 models × 4 modes | 144 live runs | +16.7–33.3pp on 2B/9B; **−16.7pp on sub-1B (LFM 350M)**; monolithic-prompt mode regresses both models | OBSERVED (small, 12-case base) |
| A2.8C | Does splitting resolution-path/capability-requirement help or hurt? | 3 models × 2 modes | 96 runs | Structured separation *reduces* accuracy on both 2B and 9B vs direct selection; 2B unsafe on precondition-gating | OBSERVED (small, 16-case base) |
| A2.8D | Can Needle 3, gated by a deterministic fast-path gate, safely handle bounded office turns? | Needle 3 (`needle_adapter.py`), `FastPathEligibilityGate`, 6 harness variants, 90 frozen cases | Code exists; **no run, no report, no test, no results artifact anywhere** | UNKNOWN (never executed-and-reported) | IMPLEMENTED_BUT_UNVERIFIED; contaminated (see §5) |
| A2.9 | Does Qwen3.5-9B natively self-initiate a closed reasoning loop (unrelated axis)? | Synthetic depot environment, 8 scenarios | 52 step events | 4/8 scenarios passed; 8/8 unprompted capability discovery, 0 fabricated capabilities | HYPOTHESIS — `VERIFICATION_READY / PARKED / downstream reference` |

---

## 3. Deterministic RAR State

**Implementation:** `uri_v1/turn/rar_deterministic.py` (956 lines) — 7-level cascade (Level 0 exact-ID/alias, Level 1 UI-anchor/attachment/unique-title, Level 2 verbatim/stem title, Level 3 recency-hint continuation, Level 4a negation/contrast elimination, Level 4b type-constraint filtering, Level 5 temporal/ordinal + Stage-4 "latest/current" recognition, Level 5.5 attachment binding, Level 6 discriminating term-overlap ranking, residual failure classification), backed by `rar_contracts.py`'s anti-invention validation gate (`validate_rar_resolution`).

**Proven, invariant across every evaluated stage including the failure case:**
- 0 invented candidate IDs, ever (Stage 2 through Stage 4B-C).
- Deterministic-anchor levels (exact ID/alias, UI selection, unique title, active attachment) resolve correctly when their inputs are genuinely available.
- Anti-first-item-bias holds: ties correctly return AMBIGUOUS rather than silently picking index 0.

**Not proven / actively contradicted by later evidence:**
- "0 wrong bindings" was reported by Stage 2, Stage 3, and Stage 4 — all three benchmarks were either self-authored during development (Stage 2), self-disclosed as not truly blind (Stage 3), or re-fit to the set that generated the applied fixes (Stage 4). The first genuinely independent benchmark (Stage 4B) found **6 wrong bindings out of 136 (4.4%)** — confident resolutions to a real but incorrect candidate.
- Coverage claims dropped under scrutiny: Stage 4B-B claimed ~59% deterministic coverage; the self-audit (Stage 4B-C) found this figure was an artifact of the benchmark supplying pre-segmented reference phrases, and that the true proven deterministic lower bound is **19.9% (27/136 cases)**, with the true upper bound **not separable from upstream-semantic dependency** given how the benchmark was constructed.

**What RAR does not solve (explicit, from code and reports):**
- Reference-expression segmentation from raw user text (it consumes an already-extracted `reference_expression` string — 86.8% of Stage 4B-C's realistic cases needed this and no deterministic segmenter exists in the repo).
- Production of `recency_hint`, `target_type_hint`, or scoped `negation_spans` — these are supplied as pre-decoded external inputs, not derived by RAR itself.
- Cross-reference consistency across multiple references within one turn.
- Broader intent/goal/operation understanding, tool/capability selection.
- Open-ended search/retrieval (that is legacy ARN, `uri_core/core/arn`, a distinct stateful engine — not RAR, and not the newer A2.8 sense of "ARN" either).

**Production wiring:** None. Every stage, including Stage 4's "ready for independent requalification" verdict, ran pure-Python qualification code only; `rar_deterministic.py` is not called from any production pipeline path.

---

## 4. Needle 3 State (separated by role)

### Role 1: Full Step-1 semantic decoder (monolithic or decomposed schema, free-text extraction)
**REJECTED_FOR_THIS_ROLE — decisively, across 3 independent batches (A2, A2.1, A2.3) plus a 4th comparative confirmation (A2.4R).**
- A2: reference capture 0/5, negation propagation 0/3, overconfident-error pathology (6/8 wrong no-calls reported confidence 1.0).
- A2.1: decomposing into 4 narrow schemas *increased* structural success but *collapsed* semantic accuracy to 0.0% on 3 of 4 schemas; hallucinatory content in 72% of emitted calls.
- A2.3: with full deterministic scaffolding (TurnFrame + ActiveContext) and candidate-ID selection instead of free text, negation discrimination and active-context resolution both measured **0/24 (0.0%)**; report states "the failure... was not in the architecture, but in the interpreting model" and permanently disqualifies base Needle 3 from further scaffolding experiments in this role.
- A2.4R: identical harness applied to Needle vs Qwen3-14B confirms Needle negation/active-context accuracy remains 0% across all 4 ablation modes, while Qwen3-14B reaches 100% under the same harness — ruling out harness confound as the cause of Needle's failure.

### Role 2: Narrow auxiliary/reflex-gate role (reference-presence detection, tool-invocation reflex, keyword/classifier gating)
**IMPLEMENTED_BUT_UNVERIFIED — explicitly proposed twice, never qualified.**
- A2.1 §23 (first proposal): "Needle may remain useful later as an auxiliary ultra-fast classifier, keyword matcher, or reflex gatekeeper, but cannot serve as the Step-1 semantic decoder."
- A2.4R §11 "Needle Narrow-Role Discovery" (second, more concrete proposal, with observed numbers): reference-presence detection 70.0% of turns, reflex tool-invocation 78.8% of turns. Verdict quoted verbatim: `POTENTIAL AUXILIARY ROLE — REQUIRES SEPARATE QUALIFICATION. Needle 3 cannot be used for any Step-1 role without a separate, purpose-built qualification suite. It is not promoted to production in any capacity.`
- **No such qualification suite was ever built or run.** The A2.8 Test Relevance Manifest subsequently classifies all Needle tests as `HISTORICAL_QUALIFICATION`/`SUPERSEDED` and states "Needle is deactivated... Closed experiment. Non-gating" — meaning that even as of A2.8, Needle's narrow-role hypothesis was treated as closed/dormant, not as an open pending item, despite never having been tested.
- A2.8D (see §5) later *does* build Needle-based tool-selection code (`needle_adapter.py`) and a deterministic fast-path gate, which is architecturally adjacent to this proposed role — but A2.8D was never qualified, is not the same benchmark design A2.4R proposed, and its supporting gate file is contaminated with hardcoded per-case answers (§5). It cannot be read as satisfying the A2.4R/A2.1 narrow-role qualification requirement.

### Not Needle — parallel decoder lineage that actually succeeded
Qwen 0.8B (A2.2, rejected), Qwen-14B (A2.4, control-only, too slow for production), Qwen3.5-2B (A2.6, sub-threshold), Qwen3.5-9B resident (A2.7, **qualified**) — this is a separate model lineage. The production Step-1 direction moved to Qwen3.5-9B resident dual-role before A2.8 began, independent of Needle's fate.

---

## 5. A2.8D Audit

**A2.8D is real, substantial, implemented code — not vaporware, not a stub.** Files: `uri_v1/edge/a2_8d_benchmark.py` (original 24-case suite), `a2_8d_stage1_benchmark.py` (90-case frozen superseding suite, Categories A–G: Reminder/Alarm/Calendar, Email, File/Document, Settings/Calculator, Main-Brain Escalation, Grounding-Blocked/Ambiguity, Near-Boundary/Edge), `a2_8d_stage1_harness.py` (6 progressive variants A–F: baseline raw Needle → narrow schema → gate-first → gate+narrow schema → gate+optimized prompting → gate+narrow schema+prompt+post-validation), `a2_8d_evaluator.py`, `needle_adapter.py` (real persistent-subprocess bridge to Needle 3 via `.venv-needle`, tool-selection style — distinct from the monolithic free-text decode style tested in A2/A2.1/A2.3), `fast_path_gate.py` (pure deterministic keyword-matching gate, no model call), `mock_email_store.py`, `contracts.py`. Compiled bytecode caches confirm prior execution/import.

**Zero qualification evidence exists anywhere in the repository:** no `docs/plans/` entry, no `docs/governance/` entry, no test file (`tests/` has A2.8A/B/C test files but none for A2.8D), no results artifact JSON in `scripts/`, and no row in the A2.8 Test Relevance and Regression Manifest. The manifest's own architecture-version table stops enumerating at "Stage 8 / A2.8A — Active Current Focus" and never mentions a Stage 9 or A2.8D/A2.8E at all.

**The only acknowledgment of A2.8D anywhere** is a discrepancy note inside the A2.9 plan document itself (`M35_URIV1_A2_9_NATIVE_PROBLEM_SOLVING_TRACE_PLAN.md`, line 15): "a substantial implemented-but-undocumented/unqualified harness... zero `docs/plans/` entry, zero `docs/governance/` entry, zero test file, zero results artifact, zero row in the A2.8 Test Relevance Manifest," and (line 27) "A2.8D not touched" — confirming its own authors treated it as background-only, explicitly out of scope for A2.9.

**Is A2.8D "our unfinished Needle + RAR intent-gate experiment," or a different hypothesis that happens to contain Needle?**
Evidence supports the latter, with qualification. A2.8D is architecturally distinct from both (a) the A2.4R narrow-role proposal (reference-presence/reflex detection, measured directly) and (b) the A2.8A–C "ARN"/BrainProfile architecture (`M35_URIV1_A2_8_ADAPTIVE_INTELLIGENCE_ARCHITECTURE_PLAN.md` Phases 1–10, uncertainty discovery, question framing, resolution-path qualification — none of which reference A2.8D, and A2.8C's own report contains zero mention of A2.8D). A2.8D is a self-contained "Edge-Brain fast-path" experiment: it tests whether bounded office turns (reminders, email, files, settings) can be routed to Needle-as-tool-selector behind a deterministic eligibility gate, across progressively more scaffolded variants. It borrows "Edge Brain/escalation" vocabulary loosely associated with the A2.8 architecture plan but was never wired into `uri_v1/turn/` (RAR) or `uri_v1/arn/` (the A2.8A–C uncertainty/resolution-path code). It also is not the same measurement A2.4R proposed (that was reference-presence/reflex-invocation detection in isolation; A2.8D is end-to-end tool-selection-and-argument-grounding).

**Contamination finding:** `fast_path_gate.py` is a package file (`uri_v1/edge/`), not a throwaway script, yet contains extensive literal hardcoding of answers to its own benchmark's specific cases — e.g. `"call Ravi"`, `"Thin Action"`, `"arthur harrison"`, `"Bangalore"`, `"7:30"`, `"500 * 0.10"` as substring checks feeding directly into argument-grounding decisions. This is exactly the anti-pattern the Test Relevance Manifest's "Permanent Harness Principle" forbids for code in production-package locations ("URI must NOT accumulate... hard-coded semantic interpretations disguised as application code"). Separately, the `expected_escalation` fixture label is confined to benchmark/scoring files and read only inside harness scoring logic (`a2_8d_stage1_harness.py` lines 221, 223, 316) — it does **not** leak into `FastPathEligibilityGate.evaluate()` itself, which is self-contained and blind to expected answers. So: no test-answer leakage into the live gate decision, but the gate's *argument-grounding* logic is itself hardcoded to its own benchmark's literal strings, which is a different and arguably worse form of contamination (it would appear to "work" only because it memorized its own test cases).

**Conclusion:** A2.8D is implemented but unqualified, architecturally separate from the two proposed Step-2 threads (A2.4R's Needle narrow-role, and the A2.8A–C ARN track), and would need the `fast_path_gate.py` hardcoding remediated before any legitimate qualification could run on it as currently written.

---

## 6. Current Step-2 Boundary

**HYPOTHESIS — not accepted by this reconstruction, stated for testing against future evidence:**

```
User message
  -> deterministic surface/reference processing (TurnFrame-style extraction — PROVEN as harness scaffolding in A2.3/A2.4/A2.4R, not evaluated standalone in this reconstruction)
  -> deterministic RAR where a reference expression is already segmented and a bounded candidate set exists
       - PROVEN on deterministic-anchor cases (exact ID, UI selection, unique title, active attachment)
       - UNMEASURED on raw, unsegmented user turns (86.8% of the one independent benchmark needed segmentation RAR doesn't perform)
  -> tiny-model assistance only for unresolved semantic/intent uncertainty
       - Needle 3: REJECTED as full decoder; narrow auxiliary role PROPOSED TWICE, NEVER QUALIFIED
       - Qwen3.5-9B resident: PROVEN as full Step-1 decoder + Step-2 continuation, but not "tiny" (9B, ~490-650ms typical latency) — the smallest *qualified* model, not necessarily the smallest *sufficient* one
  -> sufficiently established intent/problem
  -> downstream handoff
```

The evidence does not establish where the line between "deterministic mechanisms have done everything already demonstrated reliable" and "residual intelligence job" actually falls, because the segmentation gap (§3) means RAR's true raw-turn coverage is itself unmeasured. Two different residual jobs are both plausible candidates for "the smallest unresolved intelligence job remaining" — see §9.

---

## 7. Unfinished Checkpoints

1. **A2.4R's proposed Needle narrow-role qualification suite** (reference-presence detection, reflex tool-invocation) — explicitly required by that report's own verdict, never built, never run. Currently sitting in a "closed, non-gating, historical" status per the A2.8 Test Relevance Manifest despite never having been tested in its proposed narrow form.
2. **Deterministic reference-expression segmentation** — identified as a gap by Stage 4B-C's provenance audit (86.8% of realistic cases need it; no code implements it), but no report or plan anywhere proposes building it. It is inferred from evidence, not a stated pending item.
3. **A2.8D** — implemented, unqualified, undocumented, architecturally orphaned from both the A2.4R narrow-role idea and the A2.8A–C ARN track, and contaminated with per-case hardcoding in `fast_path_gate.py`. Needs an explicit disposition decision (remediate-and-qualify vs. formally abandon/archive) independent of which of items 1 or 2 is prioritized.
4. **`rar_challenge_fixtures.py`** (100 cases, `uri_v1/turn/rar_challenge_fixtures.py`) — found already on disk during Stage 3 construction, explicitly not adopted as evidence because its construction provenance could not be verified (Stage 3 report §5). Still present, still unused, still unaudited.
5. **RAR adversarial safety fixtures** (`rar_adversarial_fixtures.py`, `test_m35_uriv1_a2_5_rar_adversarial_safety.py`) — exist in the repo but were outside the scope of the 11 reports this reconstruction was asked to trace; not characterized here, flagged for a future pass.
6. **A2.8B/A2.8C's negative architectural finding** ("monolithic scaffolding penalty" — structured multi-step prompting regressed accuracy vs. direct selection on both tested models) is a proven result that has not been reconciled against the A2.8 architecture plan's own design, which assumes decomposition is beneficial (Phase 4, "safe decomposition rules"). This is a live tension inside the accepted A2.8 architecture plan itself, not just an unfinished checkpoint.

---

## 8. Contradictions / Ambiguities

Not resolved here by design — preserved per the task's audit-history requirement.

1. **"0 wrong bindings" (Stage 2, 3, 4) vs. "6 wrong bindings, 4.4%" (Stage 4B-B/C).** The only genuinely independent RAR benchmark found nonzero errors; every prior "0 wrong bindings" claim was measured on a fixture set with some form of authorship dependency on the resolver itself.
2. **Stage 4B-B's own failure-cause attribution vs. Stage 4B-C's correction of it.** 4B-B claimed one architectural cause (5 TERM_DISCRIMINATION / 1 TYPE_FILTER / 0 ACTIVE_POINTER, all "a single Level-6 vulnerability"); the self-audit found the true split is 4/1/1 across three distinct mechanisms, including one case where upstream semantic scaffolding (`recency_hint`) *caused* an unsafe binding rather than merely failing to prevent one.
3. **"~59% deterministic coverage" (Stage 4B-B, `Architecture C`) vs. "19.9% proven lower bound / unquantifiable split" (Stage 4B-C, `Architecture D`).** Direct downgrade after the reconciliation audit found the higher figure was an artifact of pre-segmented benchmark inputs.
4. **Stage 3's title ("Realistic Blind") vs. its own disclosed methodology** ("this batch's own Read-First requirement mandates inspecting `rar_deterministic.py` in full before building the benchmark... True implementation-blind construction was therefore never achievable"). Internal tension between framing and disclosed limitation, not fully resolved until Stage 4B-A's genuinely-independent construction.
5. **Stage 4's "ready for independent requalification" verdict vs. what independent requalification actually found.** Stage 4 framed its 96.1% result as near-final and integration-ready; Stage 4B/4B-C found new, previously-unanticipated failure mechanisms and a materially lower, differently-classified coverage picture.
6. **Which of the two candidate "nearest unfinished experiments" (§9) is actually next** — left unresolved per explicit user instruction; both are equally evidenced but structurally different, and this reconstruction was told to present both rather than choose.
7. **A2.8D's relationship to the accepted architecture** — it uses Needle post-dating the A2.7 decision to standardize on Qwen3.5-9B resident, without any report explaining why Needle was revived for A2.8D specifically. No document resolves whether this was an intentional parallel exploration (edge/low-power path vs. resident main-brain path) or drift. Not resolved here.

---

## 9. Single Nearest Unfinished Experiment — UNRESOLVED, AWAITING USER DECISION

Per explicit user instruction during this reconstruction, this section presents both evidenced candidates in full rather than selecting one, since the task's no-guess rule (§12 of the task brief) requires stopping when an ambiguity would materially change which experiment runs next.

### Candidate 1: Needle-3 narrow-auxiliary-role qualification
- **Experimental question:** Can Needle 3, tested in isolation on its own purpose-built benchmark (not a decoding benchmark repurposed), reliably perform (a) reference-presence detection and/or (b) reflex tool-invocation, at a quality bar sufficient to gate downstream escalation decisions?
- **Why it could be next:** This is the most literally "unfinished" checkpoint on record — two separate reports (A2.1 §23, A2.4R §11) explicitly proposed it and A2.4R states in writing that Needle "cannot be used for any Step-1 role without a separate, purpose-built qualification suite." That suite has never been built.
- **Existing reusable components:** `needle_adapter.py` (real subprocess bridge, tool-selection style — closest existing infrastructure, though built for A2.8D's different purpose and would need re-evaluation for fit); the observed A2.4R numbers (70.0% reference-presence, 78.8% reflex-invocation) as a prior baseline, not a validated result.
- **Model under test:** Needle 3, generation 3, base/untuned weights (`cactus-needle==3.0.2`) — consistent across every batch that touched Needle.
- **Explicit exclusions:** Full semantic decoding (settled, rejected); negation/active-context resolution (settled, rejected, 0% in every tested configuration); anything resembling the A2.8D end-to-end tool-selection-and-argument-grounding design (separate, contaminated, unqualified).
- **Deterministic success criteria:** UNMEASURED — no accepted threshold exists in any report for this specific narrow role. A2.6/A2.7 used ≥90% gates for negation/operations in the decoder role, but no equivalent gate has been proposed for reference-presence or reflex-invocation specifically.
- **Evidence required to close it:** A purpose-built, independently-constructed benchmark (learning from Stage 4B-A's independence methodology) isolating reference-presence detection and reflex-invocation as standalone measurable tasks, run against Needle 3, with an explicit pre-registered accuracy/safety threshold.

### Candidate 2: Deterministic reference-expression segmentation
- **Experimental question:** Can a deterministic (non-model) mechanism reliably extract the referring expression (the noun phrase to be resolved) from a raw, unsegmented user turn, closing the gap Stage 4B-C found (86.8% of realistic cases needed this and it does not exist)?
- **Why it could be next:** This gates whether RAR's true raw-turn coverage can ever be honestly measured at all — every RAR benchmark to date (Stage 2 through 4B) has supplied a pre-extracted `reference_expression` rather than raw text, which Stage 4B-C's own provenance audit states makes the "coverage split... cannot be mathematically quantified from the Stage 4B benchmark." Arguably more fundamental than Candidate 1 because it sits upstream of RAR itself, not just upstream of a still-hypothetical Needle role.
- **Why it might not be next:** No prior report or plan proposes this as pending work — it is inferred from Stage 4B-C's analysis, not a stated unfinished checkpoint the way Candidate 1 is. Building it would be new deterministic-mechanism work, not qualification of something already partially built.
- **Existing reusable components:** None identified — no segmentation code exists anywhere in the repo per this reconstruction's search. `rar_contracts.py` and `rar_deterministic.py` both assume `reference_expression` arrives pre-segmented.
- **Model/component under test:** N/A if pursued as pure deterministic mechanism (the point would be to avoid needing a model here); UNKNOWN whether a deterministic approach is sufficient or whether segmentation itself is the "residual intelligence job" that should go to a tiny model instead — this is itself an open question the experiment would need to settle.
- **Explicit exclusions:** Candidate binding/resolution logic (RAR already does this once a reference expression exists); broader intent/goal decoding (Qwen3.5-9B resident's job, already qualified).
- **Deterministic success criteria:** UNMEASURED — no accepted threshold exists.
- **Evidence required to close it:** A benchmark of raw (unsegmented) user turns with ground-truth reference-expression spans, tested against whatever segmentation approach is attempted, to determine actual raw-turn RAR coverage.

**A2.8D is explicitly not a candidate for "the" answer** in its current form — it is unqualified and contaminated (§5), and any future work on it would first require a remediation decision, not a continuation of the experiment as written.

---

## 10. Immediate Dependency Chain

```
Proven state:
  - Deterministic RAR core (deterministic-anchor levels 0-3) — PROVEN
  - Qwen3.5-9B resident dual-role decoder — PROVEN, QUALIFIED
  - Needle 3 full-decoder role — REJECTED (closed, not reopening)

Nearest pending experiment:
  - UNRESOLVED between Candidate 1 (Needle narrow-role qualification)
    and Candidate 2 (deterministic reference-expression segmentation) — see §9

Evidence needed:
  - Candidate 1: purpose-built independent benchmark for reference-presence/reflex-invocation, with a pre-registered threshold
  - Candidate 2: raw-turn benchmark with ground-truth reference-expression spans, to measure true RAR coverage

Next unknown (downstream of either):
  - Whether the resulting narrow mechanism (Needle-gate or deterministic-segmenter) closes enough of the Step-2 residual-intelligence gap that Qwen3.5-9B resident's role can be scoped down further, or whether 9B remains the necessary floor for anything beyond deterministic-anchor cases
```

No longer roadmap is stated here per the task's explicit instruction to keep this chain short.

---

## 11. A2.9 Disposition

`VERIFICATION_READY / PARKED / downstream reference experiment` — confirmed, unchanged. A2.9 tested Qwen3.5-9B's native closed-loop agentic reasoning behavior in a synthetic, non-URI-shaped environment; it is a separate axis from Step-1/Step-2 semantic decoding and reference resolution, and its own report frames itself as "disposable, experimental, proposal-only," not a production architecture decision. Nothing in this reconstruction found evidence that A2.9 should be continued, fixed, replicated, or drawn on for Step-2 architecture — consistent with the instruction not to do so.

---

## 12. Classification Summary

| Item | Classification |
|---|---|
| A0/A1/A1.1 skeleton and Step-1 contract | PROVEN (structural/contract only) |
| RAR deterministic-anchor levels (0–3: exact ID, UI selection, unique title, active attachment) | PROVEN |
| RAR lexical-discrimination levels (4–6: negation elimination, type filter, term-overlap ranking) | OBSERVED (6/136 wrong-binding rate known; not zero) |
| RAR raw-turn coverage (vs. pre-segmented benchmark coverage) | UNMEASURED |
| Deterministic reference-expression segmentation | UNKNOWN (no implementation exists anywhere in repo) |
| RAR production wiring | PENDING (never wired into any pipeline) |
| Needle 3 — full Step-1 semantic decoder role | REJECTED_FOR_THIS_ROLE |
| Needle 3 — narrow auxiliary/reflex-gate role | IMPLEMENTED_BUT_UNVERIFIED |
| Qwen3.5-9B resident dual-role decoder | PROVEN, QUALIFIED |
| Qwen3.5-2B / Qwen-14B / Qwen 0.8B decoder attempts | REJECTED_FOR_THIS_ROLE (each for stated reasons: sub-threshold, too slow, too small) |
| A2.8A uncertainty-discovery mechanism | PROVEN (12-case, explicitly self-limited scope) |
| A2.8B RAR+ARN amplification effect | OBSERVED (positive on 2B/9B, negative on sub-1B; small base) |
| A2.8C resolution-path decomposition | OBSERVED (decomposition regressed accuracy vs. direct selection; small base) |
| A2.8D harness (benchmark, gate, adapter) | IMPLEMENTED_BUT_UNVERIFIED; contamination flag on `fast_path_gate.py` |
| A2.9 native problem-solving trace | HYPOTHESIS — `VERIFICATION_READY / PARKED / downstream reference experiment` |
| "Needle 3 + deterministic RAR narrow intent-gate" remembered direction | HYPOTHESIS — neither disproven nor established; two unresolved prerequisite candidates identified (§9) |
