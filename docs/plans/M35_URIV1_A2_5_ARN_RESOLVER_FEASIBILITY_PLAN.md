# M35 — URIv1 Parallel Architecture
## Batch A2.5 Planning: ARN Resolver Feasibility

- **Worktree**: `C:\Users\cheta\Development\Uri\_V1`
- **Branch**: `m35-uri-v1-parallel-architecture`
- **Baseline Git HEAD**: `e8e3b65259c45fc823addc3ef8969425a265bd1b` (unchanged)
- **Protected prototype**: `C:\Users\cheta\Development\uri-agent` (inspected read-only only)
- **Status**: Planning document only. No production code, no model downloads, no Step 2, no commit/push.

---

## 0. Naming Collision — Must Be Resolved Before Any Implementation

`uri_core/core/arn/` in the protected prototype already defines **ARN = Adaptive Retrieval Narrowing**: a *recovery* engine triggered when a search returns empty/`NOT_FOUND` (`ARNEngine.trigger_recovery`), which iteratively narrows a candidate set through `Candidate`/`EliminatedCandidate`/`UserClue`/`SourceRecord` evidence, a `CostCeiling`, and `ClarificationRecommendation`. Its `ARNStatus` values (`ACTIVE`, `FOUND`, `USER_ELIMINATED_ALL`, `EXHAUSTED`) describe an open-ended *search* process, not a bounded, single-turn *reference identity* lookup. This is a real, shipped, tested subsystem (`docs/plans/ARN_1_COMPLETION_REPORT.md`, `test_arn_1_deterministic_narrowing.py`), most recently closed in the current `master` HEAD commit (`feat(arn.1): close accepted Batch ARN.1 deterministic narrowing core`).

The batch instructions define a **different** concept under the same three letters: "URI's explicit resource/reference identity mechanism" — a bounded, deterministic-first, single-turn lookup from an unresolved linguistic expression to a specific already-known object. These are related (both are "find the right object without guessing") but architecturally distinct: existing ARN is a multi-step, stateful, cost-bounded *search recovery loop*; the new mechanism is a single-turn, stateless, *reference-to-anchor lookup* that should usually resolve in one deterministic step and escalate to a narrow model only for the unresolved-language case.

**This plan keeps the user's chosen name in every section below because it is how the batch was specified**, but flags this explicitly as risk R1 (§13) and recommends that A2.5's own implementation batch (§14) either (a) rename the new mechanism before any code exists — e.g. **Reference Anchor Resolution (RAR)** or **Explicit Reference Binding (ERB)** — or (b) if the user intends the new mechanism to literally *be* a narrow front-end onto the existing `ARNEngine` (i.e., a single-candidate-set, no-recovery-loop invocation of the same evidence/elimination machinery), that relationship must be stated explicitly and the existing `uri_core.core.arn` models reused deliberately rather than shadowed by a same-named, differently-shaped `uri_v1` module. Silently building a second, incompatible "ARN" is the single highest-risk outcome of proceeding without resolving this.

For the rest of this document, "ARN" follows the batch's definition (explicit resource/reference identity), and "existing ARN"/"ARN.1" refers to the prototype's Adaptive Retrieval Narrowing engine.

---

## 1. Architectural Problem Statement

A2.4R proved the harness (`TurnFrame` + `ActiveContext` + `DecodedRequest` + deterministic normalizer) is sound, and that reference *detection* is achievable by a sufficiently capable model (Qwen3-14B: 100% reference detection, 87.5% active-context resolution in Mode D) — but reference *resolution* against real working-memory candidates is a narrow slice of that model's overall 100% success, is exactly the slice smaller/faster candidates have never been separately qualified on, and Qwen3-14B's 6.4–8.5s latency rules it out for production regardless of accuracy.

The open question A2.4R left unanswered (§13.3: "Conduct Intermediate Candidate Search") assumed the next step was searching for a smaller *general* Step-1 decoder. This batch's premise is that this assumption may itself be wrong: general semantic decoding (goal, operations, constraints, output preferences, *and* reference resolution, all from one model call) may be an unnecessarily hard composite problem when reference resolution against a **known, bounded candidate set** is a categorically easier, narrower task than general language understanding — closer to classification/reranking than generation. If true, decomposing Step 1 into (a) general semantic decoding minus reference resolution, plus (b) a narrow ARN Resolver for reference resolution specifically, could let each half be satisfied by a much smaller, faster model than a single monolithic decoder would need.

This plan is scoped to determining whether that premise holds, and if so, how to qualify candidates for the ARN Resolver half — not to building it.

## 2. ARN Definition (this batch's sense)

An ARN Resolver anchor is: **a deterministic binding from a reference (explicit UI selection, or an unresolved linguistic expression scoped by a bounded candidate set) to exactly one of: a specific known object identifier, `UNKNOWN`, or `AMBIGUOUS`.** It is never a search process, never opens new sources, never expands its own candidate set, and never estimates an object's existence from world knowledge. It answers "which one of these already-known things does the user mean," never "what things exist that might match."

This makes it explicitly narrower than existing ARN.1, which is designed to *search for and narrow toward* candidates it did not start with. The new ARN Resolver is invoked only after a candidate neighbourhood already exists (deterministic UI state or a bounded Graphify/retrieval result) — it makes no retrieval decisions itself.

## 3. Deterministic-vs-Model Responsibility Boundary

**Zero-model, deterministic path** — applies whenever URI's own application/UI state already names the object explicitly:
- Selected Gmail thread / file / workflow / document in the active UI.
- An attachment on the current turn (`DecodeInput.attachments`, already modeled in `uri_v1/turn/decoder.py`/`contracts.py` — see §15).
- An explicit object ID or URL pasted/referenced verbatim by the user.
- An active UI object the current turn is scoped to (e.g. "this" while a single document is open in the foreground).

None of these should ever reach a model. The existing `AttachmentReference`/`ContextDependencyCategory.CURRENT_ATTACHMENT` mapping in `needle_wire.py::normalize_wire` already demonstrates this pattern for attachments — deterministic, not inferred. The ARN Resolver's deterministic layer generalizes that pattern to the other explicit-object cases.

**Model-required path** — applies only when the user's language contains a reference that is *not* explicitly named by current UI/turn state:
- Pronouns/deictics ("it", "that", "them", "him/her/their").
- Relational expressions ("the previous one", "the revised order", "the same students", "the one before this").
- Any case where two or more candidates in the bounded neighbourhood are plausible without further discrimination.

The model's job in this path is narrow: given the reference expression, local turn evidence (negation/contrast spans from `TurnFrame`), deterministic anchors already resolved this turn, and a **bounded** candidate list (not URI's whole knowledge space), select the correct candidate ID, or abstain with `UNKNOWN`/`AMBIGUOUS`. It never proposes a candidate not in the supplied list (§8).

## 4. Minimum Information an ARN Resolver Requires

1. The reference expression itself (surface text — already produced by `TurnFrame.candidate_references`, §15).
2. Local turn evidence: clause containing the reference, negation/contrast spans in the same or adjacent clause (already `TurnFrame.negation_spans`/`clauses`).
3. Deterministic anchors already resolved this turn (so the model never re-decides something URI already knows with certainty — e.g. if the current attachment was already bound deterministically, the model should not be asked about it again).
4. A bounded candidate neighbourhood: each candidate carries a stable ID, a short label, and (where available) a resolved-type tag (document/email/workflow/person/etc.) and a recency/creation-order signal, since "previous"/"revised"/"latest" are inherently order-relative.
5. Nothing else. No full document contents, no persistent history beyond what active-context already compacts, no tool schemas, no capability IDs — mirroring the discipline `needle_wire.py`/`WIRE_SCHEMA` already enforces for the general decoder (§9, non-goals).

## 5. What Graphify/Retrieval Must Supply Before ARN Resolution

- A **bounded** candidate list (batch target: single digits to low tens, never "search the whole graph") for any reference that the deterministic layer could not already resolve.
- Each candidate must already carry: stable ID, human-readable label, type tag, and an ordering signal (creation/modification time or explicit sequence) sufficient to interpret "previous"/"latest"/"revised" relationally — the ARN Resolver must not be asked to infer temporal order from prose.
- Retrieval must be **read-only and non-adaptive within a single ARN Resolver call** — it supplies one fixed candidate set per resolution attempt; it is not the ARN Resolver's job to ask Graphify for more candidates mid-resolution (that would reintroduce the open-ended search behavior existing ARN.1 already owns, and blur the boundary in §0/§1).
- If Graphify/retrieval cannot produce any candidate for a reference, that is a legitimate `UNKNOWN` outcome, not an error — the resolver contract (§6) must represent "correctly determined there is nothing to bind to" as a valid, first-class result.

## 6. Proposed ARN Resolver Output Contract

Per reference (a turn may contain several — see §10), the resolver returns exactly one of three shapes; never a fourth "best guess anyway" shape:

```
ARNResolution:
    reference_expression: str          # verbatim surface text from TurnFrame
    outcome: Literal["RESOLVED", "UNKNOWN", "AMBIGUOUS"]
    candidate_id: Optional[str]        # set only when RESOLVED; MUST be a member of the supplied candidate set
    ambiguous_candidate_ids: Tuple[str, ...]  # set only when AMBIGUOUS; all MUST be members of the supplied set
    basis: Literal["DETERMINISTIC_ANCHOR", "MODEL_SELECTION"]
    raw_confidence: Optional[float]    # model's own reported value if any; never fabricated per-candidate (mirrors needle_wire.py's confidence-bucketing discipline, A2 report §5/§13)
```

`RESOLVED` requires `candidate_id` to be checked against the supplied candidate set before being trusted anywhere downstream — never accepted on the model's word alone (§8). `UNKNOWN` and `AMBIGUOUS` are both **safe abstentions**, distinguished in §7. There is deliberately no fourth outcome for "the resolver thinks it knows but isn't sure" — that case must be forced into either `RESOLVED` (if confidence is being used as an internal decision only, not exposed as a gradient) or `AMBIGUOUS`/`UNKNOWN`; letting a resolver return a low-confidence guess dressed as `RESOLVED` is exactly the failure mode existing Mode D normalization already exhibits (§13, risk R2).

## 7. UNKNOWN vs. AMBIGUOUS

- **`UNKNOWN`**: the candidate set contains **zero** plausible matches for the reference — either because retrieval genuinely found nothing, or because every supplied candidate is clearly wrong given the reference's type/relational qualifiers (e.g. reference says "the email", every candidate is a file). This is the correct outcome for `STEP2_CONTEXT_REQUIRED` cases from A2.4R's taxonomy (§4, R5/R6/R7/R10/T8-equivalent) where the needed context simply isn't in the bounded neighbourhood the resolver was given.
- **`AMBIGUOUS`**: the candidate set contains **two or more** plausible matches that the resolver cannot safely discriminate between given the available evidence (e.g. T3 from A2.4R: two budget spreadsheets, "open the spreadsheet"). The distinguishing feature from `UNKNOWN` is that real matching candidates *exist* — the failure is discrimination, not absence.

Both must be treated identically by the calling pipeline (neither one silently becomes a guess), but they carry different signals for Step 2/UX: `UNKNOWN` suggests "ask the user to specify" or "hand off to broader context resolution"; `AMBIGUOUS` suggests "present the specific candidates for disambiguation" (URI already has a related UX pattern in existing ARN.1's `ClarificationRecommendation`, §0 — worth reusing conceptually, not code, given the naming-collision risk).

## 8. Protecting Candidate IDs Against Model Invention

This is not optional hardening — it is a **currently demonstrated live gap** in the closest existing analog. `uri_v1/turn/local_semantic_wire.py::normalize_qwen14b_wire` (lines ~332–357) builds `artifact_map`/`entity_map` from `ActiveContext`, checks whether the model's returned `target_id` is a member, and correctly resolves when it is — but when `target_id` is **not** a member of either map, it falls through to:
```python
else:
    referent_hint = target_id
    is_resolved = True
```
i.e. it accepts the model's invented ID as if it were resolved. This is the exact failure mode item 8 asks A2.5 to prevent, and it already exists in reused A2.3/A2.4 infrastructure. **Any ARN Resolver implementation must close this**: an ID outside the supplied candidate set must always produce `UNKNOWN` (or be treated as `MALFORMED_OUTPUT`, mirroring `needle_wire.py`'s `DecodeErrorReason` taxonomy), never pass through as a resolved reference. This should be listed as a required regression fix alongside the new resolver (§19), not deferred.

Mechanism-level protection (§9) compounds this: a classifier/cross-encoder that scores supplied candidates structurally cannot invent an ID (its output space *is* the candidate set), which is one concrete argument for preferring that model class over free-generation for at least the "select from set" sub-task, even if a small generative model does the "is this even a resolvable reference" gating around it.

## 9. Candidate-Selection Mechanism

Three mechanisms, to be compared empirically rather than assumed:

1. **Constrained/classification selection** (tiny encoder or cross-encoder scores each `(reference, candidate)` pair; argmax or thresholded top-k): output space is structurally the candidate set plus an explicit "no match" class — cannot invent IDs by construction. Naturally supports `AMBIGUOUS` (multiple candidates above threshold) and `UNKNOWN` (nothing above threshold) as score-based outcomes rather than something a generative model has to be separately disciplined into saying.
2. **Constrained-decoding generative selection** (grammar/schema-constrained JSON, as already used for Needle/Qwen wire schemas): candidate IDs enumerated directly in the schema's `enum` for that turn, so the decoding grammar itself rejects any non-member token sequence — structural protection similar to (1), at generative-model cost.
3. **Free-form generative selection with post-hoc validation** (current Mode D pattern): cheapest to prompt-engineer, but is exactly the pattern shown broken in §8 unless the post-hoc validator is airtight. Should be qualified only as a fallback comparison point, not the default assumption.

Recommendation for A2.5's own experimental design (§16): qualify (1) and (2) as primary candidates, keep (3) only as an explicit negative control to demonstrate the invention-rate difference empirically rather than by assertion.

## 10. Multi-Reference Turns

A single turn may contain multiple references requiring independent resolution (A2.4R's C6: "Send the same version to him" — two references, one document-type, one person-type). The resolver contract (§6) is already per-reference, so multi-reference turns are a sequence/batch of independent `ARNResolution` calls (or one batched call returning a list, if the chosen model class supports batched scoring efficiently — relevant to the latency question, §"Latency"). Each reference's candidate neighbourhood may differ in type (documents vs. people vs. workflows) — the resolver must not assume a single shared candidate pool per turn. Cross-reference consistency (e.g. "send it to him" where "it" and "him" must be compatible with a single coherent prior action) is a **Step 2/relational** concern, not something the narrow resolver should attempt per-reference in isolation; flagged as an open question in §"Risks" (R3).

## 11. Relational Expressions

"Previous", "revised", "same", "before", "after", "attached", "his/her/their" split into two handling classes:

- **Attribute-relational** ("revised", "attached", "his/her/their"): resolvable by matching a candidate's type/ownership/attribute metadata already present in the bounded candidate descriptor (§4) — e.g. "attached" should match a `CURRENT_ATTACHMENT`-tagged candidate deterministically (§3), "his" should match a candidate whose owner/actor field matches the most recently mentioned male-referenced entity. Largely mechanical given the right candidate metadata; should not require full generative reasoning if the candidate descriptors carry the needed fields.
- **Order-relational** ("previous", "before", "after", "latest", "same" in the sense of "the same X as last time"): requires the candidate set to carry the ordering signal from §5. Given that signal, resolution reduces to selecting the correct index/offset in an already-sorted list, which a small classifier over `(reference, ordinal-annotated candidate)` pairs should handle without full language understanding — but this is an empirical claim the qualification suite (§Qualification) must test explicitly, not assume.

## 12. Local Contrast/Negation Effects

"Use the revised order, not the earlier one" requires the resolver to bind the *positive* clause's reference to a candidate while explicitly rejecting the *negated* clause's reference — not merely detecting that negation is present (which `TurnFrame.negation_spans` already does structurally) but applying it per-reference. This is the batch's own explicit warning against assuming zero-polarity understanding is enough, and A2.4R already demonstrated the general decoder's negation performance is highly model-dependent (Needle: 0%, Qwen3-14B: 100%) — there is no reason to assume a small ARN-specific model gets this for free. §"Qualification Fixture Taxonomy" makes contrast/negation cases mandatory, not optional, and §"Metrics" tracks accuracy on this dimension separately from plain reference detection so a candidate that resolves simple pronouns well but fails contrast cases is not mistaken for a viable candidate.

## 13. Confidence Representation

Following the precedent set in `needle_wire.py::_confidence_bucket` and the A2 report's explicit rule ("never fabricate per-field confidence"): if the chosen model class exposes a genuine calibrated score (a cross-encoder's similarity score, a classifier's softmax probability, or — for a generative candidate — whatever the runtime actually reports, as Needle's single overall float or Qwen's absence of a documented score), it is recorded on `ARNResolution.raw_confidence` for observability only. It must **never** be the sole basis for choosing `RESOLVED` vs. `AMBIGUOUS`/`UNKNOWN` without an explicit, empirically-chosen threshold validated against the qualification suite (§Metrics: candidate-order robustness, invented-ARN rate) — A2's own qualification found Needle's confidence anti-correlated with actual success (`OVERCONFIDENT_ERROR`, A2 report §12), which is a direct warning against trusting a model-reported score by default for exactly this kind of accept/reject decision.

## 14. When URI Should Escalate Rather Than Accept the ARN Result

- `AMBIGUOUS` with more than one plausible candidate → escalate to the user (disambiguation prompt) or to Step 2/broader context, never auto-select the top-scored candidate.
- `UNKNOWN` → escalate to Step 2's broader context resolution (Graphify/persistent memory) or to the user, never treated as "no reference existed."
- `candidate_id` returned outside the supplied candidate set → treat as a resolver malfunction (`MALFORMED_OUTPUT`-equivalent), never accept, always escalate/log (§8's fix, generalized into a standing runtime check, not just a qualification-time assertion).
- Any measured latency budget overrun (§"Latency Objective") in a live path → escalate to Step 2/asynchronous resolution rather than block the turn; this is a runtime policy decision for the eventual implementation batch, not something A2.5's qualification-only scope needs to resolve, but it must be named as a required design point for whoever implements A2.5's follow-on.

## 15. Reuse of `TurnFrame` and `ActiveContext`

**Reusable without modification** (verified by reading `uri_v1/turn/turn_frame.py` and `uri_v1/turn/active_context.py` in full):
- `TurnFrame.candidate_references` (id + expression + clause_index) is exactly the reference-expression input the ARN Resolver needs (§4.1) — already deterministic, already carries a stable per-turn ID.
- `TurnFrame.negation_spans`/`clauses` already supply the local contrast/negation evidence needed for §12.
- `ActiveContext.active_artifacts`/`active_entities` (id + name + type) are structurally close to the candidate descriptor shape needed in §4.4, though see below.

**Needs extension, not replacement:**
- Neither `ArtifactDescriptor` nor `EntityDescriptor` currently carries an explicit ordering/recency signal (§5, §11's order-relational requirement) or a `CURRENT_ATTACHMENT`-equivalent provenance tag distinguishing "explicitly attached this turn" from "in working memory from an earlier turn" — both are needed for deterministic attribute-relational resolution (§11) and should be added as optional fields in a follow-on implementation batch, not by widening scope here.
- `ActiveContext` is explicitly documented as "compact working memory for same-session turns," not a bounded-retrieval-result container — feeding it a Graphify-sourced candidate neighbourhood (§5) for references beyond current-session working memory is a plausible reuse, but the qualification suite (§Qualification) should test whether reusing the same shape for both "session working memory" and "retrieved candidate neighbourhood" causes confusion (e.g. a model conflating "recently discussed" with "retrieved as a candidate") before committing to it as the permanent contract.

## 16. Which Parts of A2.4R Remain Frozen as Control Infrastructure

- `TurnFrame`/`CandidateAction`/`CandidateReference` (`uri_v1/turn/turn_frame.py`) — frozen, reusable as-is per §15.
- `ActiveContext`/`ArtifactDescriptor`/`EntityDescriptor` (`uri_v1/turn/active_context.py`) — frozen for its existing role; extension fields for ARN (§15) should be additive, never a breaking change to the A2.4R contract.
- `DecodedRequest`, `normalize_wire`/`normalize_qwen14b_wire`'s deterministic-mapping discipline (validate-and-map, never infer) — the pattern, not necessarily the exact functions, is the frozen asset: any ARN Resolver normalizer must follow the same "fail truthfully rather than fabricate" rule (A2 report §17, reaffirmed here for §8's fix).
- Qwen3-14B Mode D remains the **architectural semantic-quality control only** — used to validate that a candidate ARN Resolver's ceiling is reachable in principle (i.e., if even Qwen3-14B given the bounded candidate set can't resolve a fixture, that fixture may be miscalibrated, not necessarily a resolver failure), never as a production candidate.
- Base Needle 3 remains **permanently rejected** for general Step-1 decoding (A2.4R verdict) — but per A2.4R §11, a narrow, purpose-built qualification of Needle for an auxiliary role (e.g. reference-presence detection, which it did at 70% in Mode C) is explicitly not closed off. This batch's candidate ladder (§"Candidate Model-Class Strategy") should include re-testing Needle 3 specifically for the *narrow* ARN Resolver task, separately from its rejected general-decoder role, since a schema-constrained "select from these N candidate IDs" task is much closer to the tool-call selection Needle was actually trained for than 9-field open-ended semantic decoding was.

---

## Qualification Fixture Taxonomy

Target: 50–100 fixtures, model-neutral (same fixture object usable by encoder/cross-encoder/generative candidates — a fixture is `{reference_context, candidate_set, expected_outcome}`, not a prompt string). Realistic URI administrative/email/document/workflow/file domain, continuing A2.4R's fixture style (not toy examples). Categories, each populated with multiple fixtures:

1. **Explicit deterministic ARN** (no model should be invoked) — selected Gmail thread, selected file, active UI object, explicit pasted ID/URL. Included to prove the deterministic layer short-circuits correctly, not to qualify a model.
2. **Single obvious candidate** — exactly one plausible match in the neighbourhood (baseline case, e.g. A2.4R's T2 "summarize the report" with one report).
3. **Multiple candidates, clearly discriminable** — 2–4 candidates where type/attribute metadata cleanly picks one (e.g. "the spreadsheet" among a spreadsheet and a PDF).
4. **Multiple candidates, genuinely ambiguous** — must produce `AMBIGUOUS`, not a guess (A2.4R's T3 pattern, several variants).
5. **No matching candidate** — must produce `UNKNOWN` (A2.4R's `STEP2_CONTEXT_REQUIRED` pattern, several variants).
6. **Pronouns** — it/that/them/him/her/they across varied antecedent types.
7. **Previous/revised/latest order-relational** — requires the ordering signal (§5, §11); include cases where the "obvious" recency reading is wrong (e.g. explicit correction turns like A2.4R's C3).
8. **Document/email/workflow-type references** — "the order", "the thread", "the workflow" — type-discriminating cases.
9. **Person-to-resource relations** — "his application", "send it to her" — entity-to-artifact binding.
10. **Multi-reference turns** — 2+ independent references per turn (§10), including mixed types (one document, one person) in the same turn.
11. **Local negation/contrast** — "use the revised one, not the earlier one" and variants (§12) — mandatory, not optional.
12. **Candidate-order perturbation** — identical fixture, candidate list order shuffled, to test positional bias (a known failure mode for small classifiers and for generative models with weak instruction-following alike).
13. **Distractor candidates** — plausible-looking but wrong-type or wrong-owner candidates mixed into the neighbourhood to test false-positive resistance.
14. **Malicious/malformed candidate IDs** — candidate IDs containing schema-breaking characters, duplicate IDs, empty-string IDs — tests the output-validation layer (§8), not the model's semantic quality.
15. **Hallucination pressure** — reference expressions that sound like they should resolve but the true answer is `UNKNOWN` (deliberately adversarial phrasing, e.g. a very specific-sounding reference to something not actually in the candidate set).
16. **Stale context** — candidate set includes both a stale and a current version of "the same" object (A2.4R's T5 pattern) — must resolve to current, not stale, when the reference doesn't explicitly ask for the old one.
17. **Active-object references** — "this", "the current one" scoped to a single foregrounded UI object (overlaps with category 1 for the deterministic case, but include linguistic-reference variants that still require the model path because the "active object" concept itself must be inferred from phrasing, not just UI state).
18. **Attachment references** — "the attached PDF", "this spreadsheet" bound to `DecodeInput.attachments`/`CURRENT_ATTACHMENT`-tagged candidates (§3, §11).

Every fixture is pre-tagged with its category and its correct `ARNResolution` (or, for category 1, "no model invocation expected" as the correct behavior) — mirroring A2.4R's `ContextCategory` discipline (§4 of that report) so scoring cannot penalize a model for correctly abstaining.

## Metrics

- **Reference detection** — did the candidate correctly identify that a reference needed resolution at all (inherited from `TurnFrame`, but re-verified per model since some candidate classes may see the reference expression pre-extracted rather than raw text).
- **Correct ARN selection rate** — `RESOLVED` with the right `candidate_id`, over all fixtures where a correct resolution exists (categories 2, 3, 6–11, 16–18).
- **UNKNOWN accuracy** — correct `UNKNOWN` over category-5/15 fixtures (no false `RESOLVED`).
- **AMBIGUOUS preservation** — correct `AMBIGUOUS` over category-4 fixtures (no arbitrary single-candidate guess).
- **Candidate-only compliance** — 100% required, zero tolerance: every `RESOLVED`/`AMBIGUOUS` candidate ID returned must be a literal member of the supplied set (§8, §14) — measured separately from semantic correctness because this is a hard safety gate, not a quality score.
- **Invented-ARN rate** — count of any `candidate_id` not in the supplied set, regardless of whether normalization downstream would have caught it — must be 0% for acceptance (§"Acceptance/Rejection Thresholds").
- **Multi-reference accuracy** — per-reference correctness rate specifically on category-10 fixtures, since a model might do well on single-reference turns but degrade on multi-reference turns.
- **Contrast/negation reference accuracy** — per-reference correctness specifically on category-11 fixtures, reported separately from overall accuracy per §12's explicit warning.
- **Candidate-order robustness** — accuracy delta between original-order and shuffled-order presentations of the same category-12 fixtures; a large delta indicates positional bias that would make production behavior order-dependent and fragile.
- **Latency** — cold and warm, min/median/max, matching the measurement discipline already used in the A2 report (§14 there).
- **RAM** — peak, self-reported where the runtime exposes it (as Needle does) plus an independent OS-level check where practical (flagged as an open gap in the A2 report, §22, that this batch's follow-on measurement should close rather than repeat).
- **CPU utilization** — where practical to measure without disproportionate qualification-harness effort; secondary to latency/RAM for the accept/reject decision.

**Explicit distinction required in every result table**: **wrong selection** (a `RESOLVED` with an incorrect `candidate_id` — actively dangerous, silently binds the wrong URI resource) must always be reported and weighted separately from **safe abstention** (`UNKNOWN`/`AMBIGUOUS` on a fixture that did have a correct answer — a missed opportunity, not a safety incident). A candidate model with a lower raw "correct selection" rate but a near-zero wrong-selection rate (i.e., its errors are abstentions, not wrong binds) is architecturally preferable to one with a higher raw rate but any nonzero wrong-selection rate, mirroring this batch's own stated principle that safe abstention beats silent wrong-binding.

## Acceptance/Rejection Thresholds

Proposed for the qualification stage (to be confirmed/adjusted once real data exists — these are starting bars, not final judgments, consistent with this repository's evidence-integrity standard):

- **Hard gate, zero tolerance**: invented-ARN rate must be 0% (any nonzero rate is an automatic reject for that candidate, regardless of other scores — §8's fix is non-negotiable).
- **Wrong-selection rate** (§"Metrics" distinction): should be near zero; a candidate with wrong-selection rate materially above its abstention rate should be rejected even if raw accuracy looks acceptable, since wrong binds are the actively dangerous failure mode.
- **Correct ARN selection rate**: no fixed number proposed yet — A2.5's own experimental stage should first establish what Qwen3-14B (as the semantic-quality ceiling, §16) achieves on the *new, narrower* ARN fixture suite before setting a numeric bar for smaller candidates, exactly as A2.4R did for the general decoder (establish the ceiling, then evaluate smaller models against a bounded gap from it, not against an arbitrary absolute number).
- **Contrast/negation accuracy**: must not regress materially below the candidate's plain-reference accuracy — a large gap here (as seen for general decoding in A2.4R, where negation was consistently the hardest dimension) is disqualifying even if aggregate accuracy looks acceptable.
- **Candidate-order robustness**: accuracy delta between shuffled and original order should be small (proposed starting bar: single-digit percentage points); a large delta disqualifies a candidate for production even at otherwise-acceptable accuracy, since it implies non-deterministic real-world behavior.
- **Latency**: sub-100ms warm is the stated target (§"Latency Objective"); a candidate exceeding this should not be automatically rejected but must be explicitly justified against the escalate-rather-than-block policy (§14) before proceeding past qualification.

## Candidate Model-Class Strategy

Per the batch's explicit instruction not to assume a generative LLM is required, and to begin at or below ~0.08B where practical:

1. **Tiny encoder/classifier models** (~20–100M range) — e.g. a small sentence-embedding model plus a lightweight scoring head, or a purpose-trained tiny classifier over `(reference, candidate)` pairs. Primary candidate class given §9's structural-invention-immunity argument.
2. **Cross-encoder/reranker models** (~80–150M range) — jointly encode reference+candidate and score relevance directly; typically stronger than bi-encoder classifiers on short-text matching tasks at moderate size cost.
3. **Tiny generative/instruct models** (~300–500M range, scaling up only if 1–2 fail) — schema-constrained generation (§9 mechanism 2) as a fallback if classification/reranking cannot handle the relational/contrast cases (§11, §12) that may need more compositional reasoning than a pure scoring model provides.
4. **Base Needle 3, re-qualified narrowly** (§16) — included in the ladder specifically for the "select from N enumerated candidate IDs" task shape, distinct from its rejected general-decoder role; cheap to re-test given the existing subprocess bridge infrastructure.

Ladder order: start at the smallest class/size that could plausibly handle the *narrowest* fixture categories (1, 2, 3, 6, 17 — simple, low-ambiguity cases) and only escalate size/class when qualification data shows a specific failure mode (e.g. contrast/negation, or order-relational reasoning) that the smaller class cannot handle, rather than pre-committing to a single model size for the whole taxonomy. Qwen3-14B Mode D stays the fixed semantic-quality ceiling throughout (§16) — never re-scored as a candidate, only used to sanity-check that a fixture has a reachable correct answer at all.

## Experimental Stages

1. **Stage 0 — Fixture construction and ceiling measurement.** Build the 50–100 fixture qualification suite (this plan's taxonomy). Run Qwen3-14B Mode D (reusing A2.4R's harness, extended with the bounded-candidate-set input shape from §4) against every fixture to establish the semantic ceiling and confirm no fixture is unanswerable in principle. No new small-model download yet.
2. **Stage 1 — Deterministic-layer validation.** Implement and test (as qualification-only harness code, not production `uri_v1` code) the zero-model deterministic path (§3) against category-1/17-deterministic fixtures, confirming it correctly short-circuits without ever invoking a model.
3. **Stage 2 — Smallest-class candidate qualification.** Evaluate the smallest tiny-encoder/classifier candidate against the full fixture suite, measuring every metric in §"Metrics", with the hard invented-ARN gate applied first (any nonzero rate ends that candidate's evaluation immediately — no partial credit).
4. **Stage 3 — Escalate only on demonstrated gap.** If Stage 2 fails specific categories (most likely candidates: 11 contrast/negation, 7/9 relational, 4 ambiguity discrimination), escalate to the cross-encoder class (still ~80–150M) and re-run only the failing categories plus a full-suite regression check, rather than re-running everything blindly.
5. **Stage 4 — Generative fallback only if 2–3 fail.** If neither classification nor cross-encoding class handles the relational/contrast categories adequately, evaluate the tiny generative/instruct class with schema-constrained decoding (§9 mechanism 2), and separately the narrowly-re-qualified Needle 3 (§16).
6. **Stage 5 — Latency/resource characterization on final candidate(s).** Full cold/warm/RAM/CPU measurement (§"Metrics") on whichever candidate(s) pass the accuracy/safety gates, explicitly testing whether the sub-100ms target (§"Latency Objective") is realistic on the user's current hardware — this determines whether ARN resolution can live in the synchronous edge/reflex path or must be an async escalation.
7. **Stage 6 — Recommendation.** Produce a qualification report (mirroring the A2/A2.4R report format) with an explicit ACCEPT / ACCEPT WITH CONDITIONS / REJECT verdict per candidate class, following this repository's evidence-integrity standard (verdict based on the metrics in §"Metrics", not on "the code ran").

## Stop Conditions

- **Immediate stop for a candidate**: any nonzero invented-ARN rate (§"Acceptance/Rejection Thresholds" hard gate) — no further tuning of that candidate within this qualification pass; move to the next class in the ladder.
- **Stage-level stop**: if Stage 2's smallest class achieves acceptable accuracy with zero invention and acceptable order-robustness on the *full* suite (not just easy categories), Stages 3–4 are skipped — do not escalate model size/class without a demonstrated gap.
- **Batch-level stop**: this batch (A2.5 planning) stops at the planning artifact. No model is downloaded, no `uri_v1` production code is written, Step 2 is not started, and the protected prototype is not touched — matching the explicit non-goals restated in §"Exact Proposed Batch A2.5 Implementation Boundary."
- **Escalation-to-user stop**: if Stage 0's ceiling measurement shows Qwen3-14B itself cannot reliably resolve a meaningful fraction of the fixture suite even with full context, that is evidence the *fixture design* or the *bounded-candidate-set premise* is flawed, not that smaller models will fail differently — this should pause the ladder and return to the user/architect before any further model evaluation, rather than silently absorbing a flawed baseline into "smaller models are just worse."

## Regression Requirements

Before and after any A2.5 implementation-stage work (i.e., the batch that actually builds the qualification harness code, not this planning batch):
- Full existing suite must stay green: the 116+ tests noted in the A2.4R report (A0 through A2.4R, including the live Needle single-pass tests) must continue passing unmodified.
- Any extension to `ArtifactDescriptor`/`EntityDescriptor` (§15) must be additive-only and re-verified against A2.3/A2.4R's existing fixtures to confirm no behavioral change to `ActiveContext`'s existing role.
- The candidate-invention fix identified in §8 (`local_semantic_wire.py`'s `target_id` fallback) should be corrected and covered by a new regression test as part of the implementation batch that follows this plan — it is a real defect in currently-reused infrastructure, independent of whether the ARN Resolver experiment itself proceeds.
- The protected prototype (`C:\Users\cheta\Development\uri-agent`) must be re-verified untouched (`git status --porcelain` path count and `git log -1` HEAD unchanged) at the start and end of every future A2.5-lineage batch, per this M35 program's standing practice.

## Risks

- **R1 — ARN naming collision** (§0): highest-priority risk. Proceeding to implementation without resolving whether this is a new concept needing a new name, or a narrow front-end onto existing `uri_core.core.arn`, risks two incompatible systems sharing one name in the same overall URI codebase, confusing future grep/search/onboarding and possibly future merge/reuse decisions between `uri_v1` and `uri_core`.
- **R2 — Candidate-invention gap already live in reused infrastructure** (§8): `local_semantic_wire.py`'s `target_id` fallback silently accepts unrecognized IDs today. Any A2.5 qualification result that reuses this normalizer path uncorrected would understate the real invented-ARN rate.
- **R3 — Cross-reference consistency in multi-reference turns** (§10): the plan explicitly scopes per-reference independent resolution as in-bounds and cross-reference coherence checking as out-of-bounds/Step-2-adjacent, but this boundary is a judgment call, not a settled fact — a future batch may find some multi-reference coherence genuinely belongs in the narrow resolver (e.g. "them" and an earlier "it" in the same turn referring to a shared prior action) rather than downstream.
- **R4 — `ActiveContext` shape overload** (§15): reusing one contract for both "session working memory" and "retrieved candidate neighbourhood" is efficient but unverified; qualification data may show it needs to split into two distinct contracts before an implementation batch commits to the reuse.
- **R5 — Ordering-signal availability**: §5's requirement that Graphify/retrieval supply an explicit ordering signal for order-relational references is a **new requirement on Graphify integration** that has not been verified against Graphify's actual current query surface (out of scope for this batch to verify — Graphify integration itself is explicitly a later-batch concern per the M35 program's non-goals) — if Graphify cannot cheaply supply this signal, §11's order-relational handling assumption weakens and may require the same model-based reasoning the plan is trying to avoid.
- **R6 — Hidden general-reasoning reintroduction**: the contrast/negation requirement (§12) and the multi-reference requirement (§10) are the two places most likely to quietly demand more general language understanding than a "narrow reference resolver" framing suggests — if Stage 2/3 qualification shows these categories require capability comparable to general semantic decoding (rather than a bounded classification/scoring task), that is evidence the ARN Resolver has re-derived a slice of the general decoding problem under a different name, and the decomposition premise (§1) should be revisited rather than pushed through with an oversized "narrow" model.

## Exact Proposed Batch A2.5 Implementation Boundary

(For the *next* batch, once this plan is reviewed — not performed here.)

**In scope for A2.5 implementation:**
- Resolve the naming question from §0 before writing any code.
- Build the qualification fixture suite (§"Qualification Fixture Taxonomy") as data/fixtures only, reusable across candidate classes.
- Build a qualification-only harness (not production `uri_v1` pipeline code) to run Qwen3-14B Mode D as the ceiling measurement (Stage 0) and, per the ladder (§"Experimental Stages"), the selected small-model candidates as they are evaluated.
- Fix the `local_semantic_wire.py` candidate-invention gap (§8, R2) as a regression correction to existing infrastructure.
- Extend `ArtifactDescriptor`/`EntityDescriptor` additively if Stage 0/1 qualification shows the ordering/provenance fields (§15) are required — additive only, re-verified against existing fixtures.
- Produce a qualification report in the A2/A2.4R format with an explicit ACCEPT/ACCEPT WITH CONDITIONS/REJECT verdict per evaluated candidate class.

**Explicitly out of scope for A2.5 implementation** (carried forward from this batch's own constraints and the M35 program's standing non-goals):
- No production `uri_v1` pipeline wiring of an ARN Resolver into the Step-1 flow — qualification only, same discipline as A2/A2.4R.
- No Step 2 (session/Graphify/persistent context resolution) implementation.
- No Graphify integration verification beyond what this plan flags as an open risk (R5) — that is Graphify's own integration batch's responsibility.
- No downloading, installing, or running any new model until the qualification plan and candidate ladder are reviewed and approved.
- No modification of the protected prototype under any circumstance.
- No commit, push, merge, or PR from the qualification batch without explicit separate instruction, matching every prior batch in this program.
