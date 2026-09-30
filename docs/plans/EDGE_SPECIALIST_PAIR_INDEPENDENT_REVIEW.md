# Edge Specialist Pair (Needle 3 + Granite `granite4:350m-h`): Independent Pre-Implementation Review

- **Target:** docs-only commit `8305f9c` on `claude/needle-granite-planning-nqic37` (parent `5bbf738`, the M36/M37/M38 freeze commit). Four documents: `docs/research/EDGE_SPECIALIST_PAIR_ROOT_CAUSE_AUDIT.md` (S1A), `docs/architecture/EDGE_SPECIALIST_PAIR_CANONICAL_ARCHITECTURE.md` (S2A), `docs/plans/EDGE_SPECIALIST_PAIR_QUALIFICATION_PLAN.md` (QP), `docs/plans/EDGE_SPECIALIST_PAIR_MIGRATION_PLAN.md` (MP).
- **Reviewer:** Claude, a separate thread independent of the planning thread. Codex is paused by the User (quota), so this review stands in for the Codex review that MP step 0 names.
- **Date:** 2026-09-29.
- **Scope:** review only. Nothing here implements, edits the plan, edits frozen or live-app files, runs a model, or decides the open eligibility question (D-1), which is the User's.

## Verdict

**`REPAIRS_REQUIRED` (plan-level; no redesign of the authority model).**

The authority model is sound. It matches S6 as the code implements it. The frozen-scope handling is correct, and the qualification method is well built: dev/holdout split, worst-of-3 scoring, zero-count invariants and predeclared bounds. Two HIGH findings block acceptance as written:

1. On the current repository, the `DIRECT_TOOL_V1` envelope is **empty under the plan's own rules**. The battery therefore cannot measure the direct class, which is the class the Needle-vs-Granite hypothesis is about, without contrived phrasing or changes the plan lists as unauthorized.
2. Under E-a, the residual gate G-D3 is decided by how the oracle is authored, not by model behaviour. Existing evidence predicts that E-a fails it. That matters for the User's D-1 choice.

## 0. Acceptance criteria (defined before reviewing)

| ID | Criterion |
|---|---|
| R-1 | Every reused mechanism the plan cites exists at the cited place and behaves as claimed. This is checked in source and, where practical, by running it offline. |
| R-2 | The new components are sufficient for the 16 constraints, and those described as reject-only really can only reject. |
| R-3 | The battery can measure per-task-class value for **both** models on overlapping, realistic workloads, and its gates are internally consistent. |
| R-4 | Nothing touches or requires touching frozen M33.x/M36/M37/M38 scope or live-app files without saying so. |
| R-5 | Stage-1 numbers quoted by the plan reproduce from the raw records. |
| R-6 | The User's fixed decisions hold: URI holds all authority; Edge-off bypasses both models; EDGE_ONLY never substitutes; roles come from measurement; Stage-1 stays exploratory. |
| R-7 | Every finding has a severity, evidence and a stated effect on the verdict. Anything unverified is named. |

## 1. Evidence checked directly

Commands were run on a checkout of `8305f9c`, with no model calls.

- `git diff --name-only 5bbf738 8305f9c` lists only the four `docs/` files.
- `pytest tests/test_m37_edge_resolution.py -k "frozen or boundaries"` gives **2 passed** at `8305f9c`, so the frozen-file guard and the import boundary hold.
- `uri_core` and `uri_v1` have no imports of each other in either direction (grep), which confirms MP §11.
- Stage-1 in `/mnt/project-files/needle_granite_stage1/`: all 12 manifest SHA-256 entries match. `direct_tool_results.json` summary gives Granite 33/36 positive (11/12), Needle 21/36 (7/12), and must-withhold Granite 0/24 and Needle 3/24 (0/8 and 1/8). These **reproduce** S1A §3.1.
- Offline probe of the frozen M36 `negated()` / `affirmative_context()`. It reproduces S1A §4 for the sampled rows (T05, T06, T13, X1–X3, "Where is …", T17, T20). It was extended to phrasings of the S2A §17 candidate actions (table in H-1).

### 1.1 Citations that hold

| Plan claim | Result |
|---|---|
| Gates check parameter presence only, and only where an action schema exists (`decision_gates.py:480-503`) | Holds |
| `translate_tool_calls` accepts batches and merges them into `multi_action` (`tool_call_translator.py:80-136`). The offered-name check is at `:47`. | Holds |
| `executed_signatures` exempts read-only actions (`native_tool_loop.py:213-221`) | Holds |
| Canonical seam `execute_translated_batch` at `native_tool_loop.py:250`; `_execute_canonical` at `canonical_execution.py:479` | Holds |
| ApprovalStore `propose/decide/consume` at `:179/:233/:298`; `complete_step_externally` at `workflow_executor.py:30` | Holds |
| `ground()` accepts sub-spans (`envelope.py:58-84`) | Holds. It also **case-folds**, which the plan does not mention. N3's "no case-folding" rule is therefore new and stricter, as intended. |
| S6 behaviour for Edge OFF, HYBRID, MAIN_BRAIN_PREFERRED, explicit model and EDGE_ONLY (`routing_policy.py:162-215`) | Holds. Classing a direct tool proposal as `SUBSTANTIVE` is correct under G2. |
| M37 import boundary forbids `uri_v1.reference_clarification` in `uri_v1/edge`, `uri_v1/execution` (`test_m37_edge_resolution.py:242-250`) | Holds. The MP §3 package placement is justified. |
| RC-9: the Needle bridge writes non-ASCII JSON with no stdout encoding set (`m33_2_needle_bridge.py:165`); the parent uses UTF-8 (`ensemble.py:74`) | Holds as an inference. The experimental bridge is still unsupplied, and S1A says so. |
| VG-1 requires predeclared numeric thresholds (`URI_EXTERNAL_HARNESS_VIABILITY_GATE.md:89-95`) | Holds for "material advantage". See M-7 for "unacceptable regression". |

## 2. Findings

### HIGH

**H-1. The `DIRECT_TOOL_V1` envelope is empty on the current repository, under the plan's own admission rules. D-POS cannot be authored from realistic requests.**

S2A §5 and §7 admit an action only if it is `READ_ONLY`, has approval `NONE`, has `wrong_binding_impact` NONE or RECOVERABLE, and every parameter has a satisfiable grounding source. It also requires the turn to pass the M36 affirmative gate. Checked against the S2A §17 candidates:

- **(a) Impact is undeclared everywhere, which means CONSEQUENTIAL.** None of the 17 `active_tools` entries in `uri_workspace/capabilities_registry.json` declares `wrong_binding_impact`. Gmail `list_labels`, `read_message` and `read_thread` leave it `None` (`gmail/capability.py:41-77`; only `create_draft` declares RECOVERABLE at `:107`). Undeclared means CONSEQUENTIAL, fail-closed (`wrong_binding.py` module docstring; `base.py:158-160`). So `REJECT_OUT_OF_ENVELOPE` applies to **every** candidate. Declaring impacts would mean editing `uri_core/capabilities/gmail/capability.py` and the workspace registry. Those are live-app files. They are not in MP's file list, and MP §9 lists them as unauthorized.
- **(b) The grounding sources have no producers.**
  - `LITERAL_SPAN` needs a trusted-intake span keyed to the slot. `URIIntake.capture(spans=…)` is called only by qualification scripts and tests, usually with the whole turn as the span, and by the M39 office grammar, which recognises `.py`/`.xlsx` filenames only. Nothing produces a span for a spreadsheet id, a roll number or a Gmail id.
  - `BOUND_SOURCE` needs an S1 CONFIRMED binding. RAR/S1 binds memory-source candidates. No path binds a Gmail `message_id` or `thread_id`, although S2A §17 relies on "id bound from session context".
  - `untrusted_content_present` exists only as a default-`False` field (`edge/contracts.py:44`, `edge/trace.py:27`), and nothing sets it. As an N2 input it fails open unless N2 computes it itself.
- **(c) The M36 affirmative gate rejects natural phrasings of the candidates.** Offline probe results:

  | Request | `affirmative_context` |
  |---|---|
  | "Show my Gmail labels." / "How many unread emails do I have?" | False |
  | "Check system performance." / "How is my computer doing?" | False |
  | "What do you remember about my manager?" / "Recall what I told you about Ravi." | False |
  | "Read the attached file." / "Read the attachment." | False |
  | "Read message 18c2f0a9b." / "Read thread …" / "Read that email." | False |
  | "Get the record for roll number 2021CS042." | False |
  | "Open spreadsheet 1AbC…" (id removed) / "Get 2021CS042." / "Read it." | True |

  The vocabulary is file- and office-oriented (`contracts.py:262-283`), so only terse forms pass.
- **(d) Some candidates are unavailable.** `fetch_drive_spreadsheet` is `unavailable_missing_dependency` in the registry. Gmail needs the Google client libraries (not installed here) and a connected account.

**Effect.** QP D-POS asks for at least 150 holdout cases over at least 6 live actions. Under the rules above, those cases would be contrived terse strings against actions the envelope would reject anyway. That does not measure per-class value for either model, and it does not test the User's hypothesis that Needle suits direct calls.

**Repair.** Pick one and state it in S2A §17 and QP §3.1:
- **(i)** Name the prerequisites as separately authorized items. These are impact declarations (a live-app change), span and binding producers for each candidate identifier kind, and an N2-computed untrusted-content flag. Sequence them before battery authoring.
- **(ii)** State that `DIRECT_TOOL_V1` has no qualifiable workload today. Defer it, and consider tying it to D-3: local-file requests are where the affirmative gate and the M39 span grammar already work. Qualify `EXTRACTION_V1` first.

Either way, D-POS should be authored from sampled real requests, not only phrasings built to pass the gate.

**H-2. Under E-a, G-D3 is decided by the oracle rather than measured. The evidence predicts E-a fails it.**

- **Evidence.** Stage-1 T17–T20: Granite withheld 0/8 and Needle 1/8. When an unsupported verb was asked, both substituted an available read tool. M33.3 Batch A shows Needle abstained 0/16. The probe shows that "Send it.", "Share it.", "Translate it.", "Rewrite it." and "Open it and send it." all pass `negated()=False` and `affirmative_context()=True`. Under E-a, N3 does not check operation identity (S2A §7, last paragraph).
- **What follows.** A large share of D-RES cases will execute a substituted read. QP §3.1 scores D-RES as correct when "only an oracle-listed harmless read executes". If the oracle lists the substituted read as harmless, G-D3 is vacuous. If it does not, failure is near-certain for both models.
- **The reply has the same problem.** The S2A §9 action-scoped reply ("Located `report.xlsx`") in answer to "Send report.xlsx" does not claim the send, but it silently drops it. URI_WORKING_PRODUCT_BASELINE item 9 requires failures to be surfaced.

**Repair.**
- Fix the "harmless read" oracle rule in QP before authoring, and rule that a read substituted for a different requested operation is an incorrect execution.
- Require the specialist-path reply to state generically that only the named action was performed and nothing else in the request was acted on.
- Disclose in MP §7 D-1 that existing evidence predicts E-a leaves `DIRECT_TOOL_V1` unassigned.

### MEDIUM

**M-1. The E-a precedent is overstated.** S2A §5 says E-a matches M33.2 §6 `EXECUTE_PROPOSAL` ("executes … with no semantic re-check"). M33.2 §6, however, evaluates "task complexity" before a proposal can execute, and `evaluate_routing` returns ESCALATE on `task_complex` before it considers `proposal_valid` (`routing_policy.py:77-80`). E-a in effect fixes `task_complex=false` with no producer. That is the same gap under another name, and it should be disclosed in D-1.

**M-2. Only N3, N4 and N5 are reject-only.**
- N2 *produces* `edge_sufficient=true`, which is the positive admission S6 routes on.
- N1 *chooses* the specialist.
- Under E-a, N2 is the whole eligibility decision, and its failure mode is false admission. Z-8 bounds that only for D-STRUCT.

S2A §3.2's "can only reject" wording should be limited to N3–N5, and N2 should be described as the admission authority it is.

**M-3. N1 does not fit S6's single-model readiness without change.**
- `edge_eligibility` checks `inventory.selection_status(settings.edge["runtime_id"], settings.edge["model_id"])` (`routing_policy.py:150`). `EdgeSettings.edge` is exactly one pair (`settings.py:72-76`), and `EdgeSettingsStore.update` validates that pair against the inventory.
- A "profile id" in that pair is not a runtime in the inventory. It returns `unavailable` unless the inventory gains a synthetic entry, and the plan does not mention one. `edge_warm`, `resource_admitted` and `edge_role_qualified` are per specialist. S2A §6 step 10 ("S6 still returns EDGE") would evaluate the profile, not the replacement specialist.

**Repair.** Specify per-specialist S6 evaluation, for example by projecting the settings onto each specialist, and state whether `runtime_inventory.py` changes.

**M-4. Asking the model for argument values adds only error.** Under S2A §7, every admissible value is known to URI before the call: a bound value, a whole span, the verbatim turn, or absent. S2A §8 even hands the bound value to the model to copy. The model's only real decision is which tool to pick from the shortlist. Having it copy values creates RC-2 errors for N3 to reject, and it pushes D-POS toward measuring copy fidelity.

**Recommendation.** The specialist returns the tool choice only, and URI fills the arguments from the declarations. The battery then measures selection. It also needs a deterministic baseline for a one-entry shortlist, where no model is needed. This changes what "value" means for the direct class; it is not a safety defect.

**M-5. Pronouns and bound references are defined inconsistently.** S2A §5 excludes pronouns only when no CONFIRMED binding exists, and §17 relies on session-bound identifiers. QP D-STRUCT lists "pronouns" as a structural exclusion where "the specialist is never called". "Read it." passes the affirmative gate. The oracle should key on binding state, not on whether a pronoun appears.

**M-6. The QP §7 dimensions cannot show the value of `EXTRACTION_V1`.**
- As SUPPORTING work, extraction adds a model call ahead of a Brain call. M33.2 §12 and §2.2 forbid mandatory serial Edge-plus-Main inference, except as deadline-bounded parallel assistance.
- Latency, Brain avoidance and memory cannot show a benefit here. What is needed is Brain task success with and without the assist, plus an assistance deadline. F-FLOW has only 30 such flows.
- Separately, the S2A §5 exclusion "turn carries attachment-derived or retrieved text → ineligible" reads as covering extraction too, whose input is untrusted by definition. State that it applies to `DIRECT_TOOL_V1` only.

**M-7. The Brain arm in QP §7 is not implementable as written.**
- The first option, Chetan's subscription Claude Code session, has no URI Brain transport. `subscription_oauth` "intentionally has no runtime implementation" (`provider_registry.py:86-87`).
- Using the harness as URI's Brain also conflicts with the project rule that harnesses are not URI's Brain. As of today, a local Ollama Brain is the only feasible B0/B1/B2 Brain.
- VG-1's recorder note requires numeric thresholds for "unacceptable regression" as well. QP §7 fixes only the advantage thresholds.

### LOW

- **L-1.** G-D1 says "(so at least 142/150)", but 142/150 = 0.9467, which is below the point gate of 0.95. The binding count is 143/150 (lower bound 0.914).
- **L-2.** QP repair note 3 says a 0.90 lower bound is unreachable with 30–40 cases "even at 100%". In fact 30/30 gives 0.905, so it is reachable only at 100%. The conclusion (use a point gate) still holds, but the stated reason is wrong.
- **L-3.** G-E3 allows at most 1 injected value in 50 documents, an upper bound of 9.1%. That is the weakest gate, on the most consequential extraction failure. Disclose it as such or raise n.
- **L-4.** S2A §11 cites `_edge_only_guard` (`routing_policy.py:47`). That function wraps the M33.2 `evaluate_routing`, not S6. S6's EDGE_ONLY behaviour is at `:179-180` and `:196-200`. The claim is correct; the citation is not.
- **L-5.** `Action.__post_init__` derives `read_only` from `effect_type`, so an action declared `read_only=False` with no `effect_type` reports `EffectType.READ_ONLY`. I verified this by constructing an `Action`. Gmail `create_draft` is declared that way. `base.py` is an anchored M33.3 file, so leave it. N3's approval conjunct still excludes `create_draft`, but N3 must never rely on `effect_type` alone. Add a battery case for it.
- **L-6.** S6 lives in `routing_policy.py`, M33.3-R, which is CLOSED_FROZEN. MP step 7 should say N6 goes in a **new** file, not an edit to it.
- **L-7.** D-4 edits the same frozen guard that M39's authorized allowlist edit changed (`ba0db5e`/`736464a`, not on this base). Record the ordering and merge dependency.
- **L-8.** The S2A §2 diagram lists CLARIFY as a `SpecialistRoute` output, but S6 has no CLARIFY target; it comes from the binding step. This is presentation only.

## 3. What holds (R-6)

- URI holds all authority. Neither model decides eligibility, grounding, permission or execution (S2A §4). This is consistent with M33.2 §1.
- Edge OFF means no specialist call, and EDGE_ONLY means no Capable-Brain or cloud call. Both match S6 as implemented and are gated as Z-6 and Z-7.
- Roles come from measurement. Both models are candidates for both classes, assignment happens on the dev split and is confirmed on the holdout, and "Needle unassigned" is an accepted outcome.
- Stage-1 is kept exploratory, and none of its numbers is used as a gate.
- No frozen or live-app file is touched. No milestone identity is self-assigned; EXP, G4 and INT are proposals only.

## 4. Comment on the eligibility card (D-1). The decision stays with the User.

- **E-a** (structural gates plus a measured residual) adds no mechanism. Given H-2 and M-1, though, the likely result is `DIRECT_TOOL_V1` unassigned: an honest outcome, reached at the cost of building and running the direct battery.
- **E-b** (a closed operation-class table) is keyword routing. Combined with M-4 (URI fills the arguments) and a small shortlist, it leaves the specialist close to redundant for that class, as S2A itself argues.
- **E-c** (second-model evidence) has no supporting evidence. Stage-1 classification was degenerate.
- **A path the card does not list:** defer `DIRECT_TOOL_V1`, which needs H-1's prerequisites anyway, and qualify `EXTRACTION_V1` first. That class is measurable now, once M-6 is addressed.

## 5. Not verified, and its effect

| Item | Effect |
|---|---|
| Full test suite not run. The commit is docs-only; the guard and boundary tests were run. | None on the verdict |
| No model run (out of scope; no device) | None. This is a design review. |
| Experimental Needle bridge not supplied (as S1A says) | RC-9 stays an inference; no effect |
| Gmail capability could not be instantiated (Google libraries absent). The `Action` metadata finding was shown by constructing an `Action` directly and reading the source. | None |
| The planning thread's card wording was not read. D-1 options were taken from MP §7 and S2A §5. | Minor. §4 comments on the documented options. |

## 6. Self-review against §0

- **R-1** Met: §1.1, and H-1, M-1, M-3, L-4 and L-5 correct cited claims from source.
- **R-2** Met: M-2, M-4 and H-2.
- **R-3** Met: H-1, H-2, M-5, M-6, M-7 and L-1–L-3, with the statistics computed with SciPy.
- **R-4** Met: §1, L-6 and L-7.
- **R-5** Met: §1.
- **R-6** Met: §3.
- **R-7** Met: every finding cites evidence, and §5 lists the gaps.

Corrections made while drafting:
1. I first recorded `ground()` as "exact". It case-folds, and the text now says so.
2. I first read the S2A §17 "zero-argument lookups" as automatically admissible because they have no arguments. The probe shows the affirmative gate excludes their natural phrasings, so they are now part of H-1(c).
