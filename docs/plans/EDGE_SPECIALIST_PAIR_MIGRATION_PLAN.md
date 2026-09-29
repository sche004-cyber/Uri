# Edge Specialist Pair: Migration and Integration Plan (Stage 3 draft)

Status: **PLANNING DRAFT r2. Not accepted. No implementation, wiring, qualification or state change is authorized by this document.** r1 repairs the independent review (`0be2c32`, `REPAIRS_REQUIRED`); r0 is at `8305f9c`; §12 maps each finding to its repair.
Date: 2026-09-29. Branch: `claude/needle-granite-planning-nqic37`.
Inputs:
- S1A: `docs/research/EDGE_SPECIALIST_PAIR_ROOT_CAUSE_AUDIT.md`
- S2A: `docs/architecture/EDGE_SPECIALIST_PAIR_CANONICAL_ARCHITECTURE.md`
- QP: `docs/plans/EDGE_SPECIALIST_PAIR_QUALIFICATION_PLAN.md`
- `docs/governance/URI_FOUR_STAGE_DEVELOPMENT_LIFECYCLE.md`
- `docs/governance/URI_STATE.yaml`
- project spend, live-app and product-target rules

## 0. Acceptance criteria (defined before drafting)

| ID | Criterion |
|---|---|
| M-1 | Every step names its files, tests, entry gate and exit evidence, and none touches a frozen file. |
| M-2 | The governance scope is proposed only where governance requires one, and no identity is self-assigned. |
| M-3 | Live-app changes are PR-only for Chetan to review and apply, default off, with a stated rollback. |
| M-4 | The existing frozen-file guard is handled by an explicit decision, not routed around. |
| M-5 | Risks, open decisions and rollback boundaries are explicit. |
| M-6 | What stays unauthorized is stated. |
| M-7 | Sequencing respects the product-completion target: nothing here diverts the path to URI_WORKING_PRODUCT_BASELINE. |

## 1. Governance scope proposal (M-2)

**Findings:**
- `URI_STATE.yaml` defines namespaces as follows:
  - `Mxx` for governed milestones;
  - `EXP-*` for "research [that] may produce evidence for product architecture but does not automatically own production architecture";
  - `INT-*` for "explicitly authorized production-integration transitions" (none exist).
- Model qualification with no production wiring is research evidence, so it fits `EXP-*`.
- Changing how the Edge routes (the SpecialistProfile, N2, N3, N4, the `route_specialist` projection) touches architecture owned solely by M33.2, which is CLOSED_VERIFIED. M33.2 has taken additive amendments before (G1–G3).
- Live wiring is an `INT-*` event, the transition S13 describes as INT-gated.
- The dynamic-planning precedent committed Stage 1–3 docs with **no** `URI_STATE.yaml` change. Nothing in the lifecycle requires recording a planning status for a draft.

**Proposal (for Chetan to accept, amend or reject; nothing is registered by this document):**

| Scope | Proposed identity | When it is registered |
|---|---|---|
| Qualification research (QP) | `EXP-EDGE-SPECIALIST-PAIR` | When Chetan authorizes step 1 |
| Architecture change | Additive M33.2 amendment, provisionally "G4: qualified per-class Edge specialists" | When Chetan accepts S2A, after independent review |
| Live wiring | `INT-*` event (id chosen then) | Only after QP passes, L1 passes, and Chetan authorizes |

No `Mxx` number is proposed, because governance does not require one. M37 scope is untouched.

## 2. Sequencing against the product target (M-7)

Chetan's product-completion target lists "Edge Brain qualification" among the work to move to *after* URI_WORKING_PRODUCT_BASELINE is reached. So this plan proposes:
- Steps 0–1 (review, decisions, battery authoring) may proceed in parallel, because they are docs and fixtures and use no device time needed for the baseline.
- Steps 2–6 run when Chetan chooses to spend device time on them. The default is after the baseline.
- Step 7 (live wiring) comes after the baseline.

Chetan may pull this forward. The plan does not assume it.

## 3. Placement and boundaries

- **The isolated components live in a new package**, proposed `uri_v1/specialists/`. For the extraction-first path (recommended E-d) that means only N1 (profile loader plus the user-scoped opt-in record), N4 `SpecialistAttemptLedger`, N5 `ExtractionValidator` and N7 adapters. N2 `DirectEnvelopeCheck` and N3 `SpecialistProposalValidator` are built only if `DIRECT_TOOL_V1` reopens.
  - The package may import `uri_v1.memory.contracts` (for `negated()` and `affirmative_context()`) and `uri_v1.reference_clarification` (binding states).
  - It never imports `uri_core`, because `uri_v1` and `uri_core` may not import each other.
- **Not placed under `uri_v1/edge/` or `uri_v1/execution/`.** Those are M37 and M38 packages. Their import-boundary test (`tests/test_m37_edge_resolution.py:244`) forbids `uri_v1.reference_clarification`. The frozen-file guard's prefix allowlist would accept new files there, but using that allowance to avoid decision D-4 would be routing around a guard, which the operating rules forbid.
- **N6 `route_specialist()`** is a projection of S6 (`uri_core/core/edge/routing_policy.py`), so it belongs beside S6 in `uri_core`, in a **new file**. `routing_policy.py` is M33.3-R, CLOSED_FROZEN, and is not edited (review L-6). N6 evaluates S6 once per specialist through an in-memory settings view (S2A §6 step 5); `settings.py` and `runtime_inventory.py` are unchanged. It is live-app code, written only in step 7, as part of the PR for Chetan. Before then, the qualification harness calls `evaluate_intelligence_route` from test code, as a caller outside `uri_v1`.
- **The canonical seam** (`execute_translated_batch`, `uri_core/core/native_tool_loop.py:250`) is used unchanged.
- **No frozen file changes.** M33.2, M33.3, M36, M37 and M38 files, and `verify.py`, stay as they are.

## 4. Steps

| Step | Content | Files | Entry gate | Exit evidence |
|---|---|---|---|---|
| 0 | r0 independent review done (`0be2c32`, Claude standing in for Codex). This r1 repairs it. Chetan accepts, or accepts with repairs, and decides D-1 to D-5. A Codex re-review of r1 is optional, at Chetan's choice. | Review reports under `docs/plans/` | This commit | Chetan's recorded decisions |
| 1 | Before authoring, fix the extraction admission rule and schema set (S2A §6 step 11: declared closed schemas, requested only by a deterministic producer; E-SUB deferred). Then author and freeze the **extraction** battery (QP §2, §3.2, §3.3). The direct segments (QP §3.1) are not authored unless D-1 reopens after step P. | `fixtures/edge_specialist_pair/` (cases, oracle, fixtures, manifest) | Step 0 and D-4 | Manifest committed; substring-collision check output; holdout sealed |
| 2 | Implement N1, N4, N5 and N7 as isolated code, with fake-model unit tests for every applicable Z invariant (QP §5.2) and every N5 rejection | `uri_v1/specialists/*`, `tests/test_edge_specialists_*.py` | Step 1 and an implementation authorization | Tests green; full suite green except any failure accepted under D-4; no import of `uri_core` |
| 3 | Development-split runs of both models on `EXTRACTION_V1` on Chetan's device, placement-matched, local Ollama Brain for X-ASSIST; per-class assignment by QP §6. Optionally the QP §3.4 selection diagnostic, if Chetan wants direct-class evidence. | `scripts/edge_specialist_pair_run.py`, raw outputs under `/mnt/project-files/` (not the repo) | Step 2; device online | Per-arm tables; proposed profile with rankings |
| 4 | Holdout qualification (QP §5) and comparative experiment (QP §7), one run each; pinned qualification record | `fixtures/edge_specialist_pair/record.json` (digest-pinned) | Step 3; latency and memory budgets written into the profile | `COMPLETED_WITH_RESULT` runs; gate table with n, k and bounds; honest-outcome verdict |
| 5 | Independent audit (Codex when available) re-scores step 4 from raw outputs | Audit report | Step 4 | Audit verdict |
| 6 | L1 live canonical-path verification (QP §8) with read-only actions and real documents Chetan supplies | Test-side runner; evidence report | Step 5 passes; Chetan names the documents and accounts | Receipts, truthful replies, follow-up grounding, Z-5/6/7/12/13 evidence |
| 7 | `INT-*` proposal plus the smallest live PR: N6 in a new file beside S6; a call from the existing Edge routing point into `uri_v1/specialists` through a thin adapter; `URI_EDGE_SPECIALISTS` flag off by default | PR only (new files under `uri_core/core/edge/`, adapter file) | Step 6; URI_WORKING_PRODUCT_BASELINE (§2); Chetan's authorization | PR for Chetan's review and application; L2 checks after he applies it |
| X-P1 | **Extraction producer** (needed for live extraction routing and for E-SUB): a registered capability or deterministic flow that requests a declared closed schema. None exists today. | Own lifecycle and PR | Chetan's authorization | Then E-SUB is authored and L1 covers extraction admission |
| P | **Direct-class prerequisites** (only if Chetan wants `DIRECT_TOOL_V1` reopened): P-1 impact declarations on candidate actions (live-app change); P-2 span or binding producers per identifier kind (own lifecycle); P-3 is built inside N2; P-5 deployment configuration. P-4 (frozen M36 vocabulary) is not changed; its coverage loss is measured. | Separate lifecycles and PRs | Chetan's authorization for each | Then D-1 is re-decided on fresh evidence, and QP §3.1 is authored |

Each step stops at its exit, and the next step needs its entry gate. Steps 2–7 and P each need Chetan's explicit authorization. Step 7 is never merged or applied by a pipeline thread.

## 5. Flags, killswitch and rollback

| Control | Behaviour |
|---|---|
| `URI_EDGE_SPECIALISTS` (step 7) | Default off. Off means the Edge routes exactly as today. There is no code path into `uri_v1/specialists`. |
| Profile absent, or record digest mismatch | `edge_role_qualified=false`, so bypass (S2A §11). This is the runtime killswitch and needs no deploy. |
| Empty ranking for a class | That class never routes to a specialist (S2A §15) |
| Existing Edge OFF / `EDGE_ONLY` / explicit model | Unchanged semantics (Z-6, Z-7) |
| User has not opted into a profile (D-5) | The single `EdgeSettings.edge` selection behaves exactly as today; no second model runs |

**Rollback boundaries:**
- Before step 7: delete `uri_v1/specialists/`, its tests and its fixtures. Nothing else references them.
- After step 7: set the flag off, or revert the PR. No stored data changes format: ledger and telemetry are new, user-scoped files and can be deleted.
- There are no migrations of existing stores, and nothing to roll back in bindings, approvals or memory.

## 6. Frozen-file guard (M-4)

`tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged` (line 264) fails on any new path under `uri_v1`, `uri_core`, `uri_ui`, `tests`, `scripts` or `fixtures` outside its allowlist. Steps 1–3 add such paths. The two precedents both needed Chetan's word:
- **Dynamic planning:** Chetan accepted and documented one guard failure.
- **M39:** Chetan authorized a minimal, exact allowlist entry (`ba0db5e`).

This plan edits nothing. It lists the options as decision D-4 (§7).

**Ordering with M39 (added in r1, review L-7).** M39's authorized allowlist edits to this same guard (`ba0db5e`, then `736464a` making the M39 entries exact-match) are on `claude/project-thread-wb7tmm`, not on this plan's base (`5bbf738`). Any D-4 entry for this work must be written on top of whichever version of the guard is on the base at step 1. If M39 has not merged by then, the entry is prepared against `736464a`'s exact-match form and the merge order is recorded, so neither change silently drops the other's entries.

## 7. Unresolved decisions

| ID | Decision | Options | Recommendation | Needed by |
|---|---|---|---|---|
| **D-1** | How the "exactly one operation of an envelope class" property is established (S2A §5.3–§5.4) | E-a structural gates plus a measured residual (needs P-1 to P-5 first; **existing evidence predicts it leaves `DIRECT_TOOL_V1` unassigned**, and it effectively fixes S6's `task_complex=false` with no producer); E-b closed operation-class table over the frozen M36 vocabulary (keyword routing, needs explicit acceptance; with URI filling arguments it leaves the specialist close to redundant); E-c independent evidence from a second model (not supported by current evidence); **E-d defer `DIRECT_TOOL_V1` and qualify `EXTRACTION_V1` first** (added in r1 from the review) | **E-d** (revised in r1; r0 recommended E-a). The direct class cannot be measured today (S2A §5.1), and E-a is predicted to fail once it can. E-d spends effort only where a result is obtainable, and both models are still compared on extraction. | Step 0 |
| D-2 | Governance scope | §1 proposal (EXP id, M33.2 amendment G4, later INT) or another form | §1 proposal | Step 1 |
| D-3 | Local-file direct requests (Stage-1's main use case) | Leave out (no registered action exists, S1A RC-10); or a separate capability lifecycle for a typed read-only locate/read action. The review notes that local-file phrasing is where the M36 affirmative gate and the M39 filename grammar already work, so if the direct class ever reopens, this is its most measurable workload. | Leave out now. If Chetan later reopens the direct class, consider this action first. | Only if D-1 reopens |
| D-4 | Frozen-guard handling for new test, fixture, script and package paths (ordering with M39 per §6) | Exact allowlist entries (M39 precedent, a frozen-test edit Chetan must authorize); or accept and document the failure (dynamic-planning precedent) | Exact entries. A permanently red guard hides the next real violation. | Step 1 |

| D-5 | How a user opts into a two-model profile (added in r1, from review M-3) | A new user-scoped opt-in record owned by `uri_v1/specialists/` (no change to frozen `settings.py`); or a settings-schema amendment at the `INT-*` step | The new opt-in record, default off. The user's current single-model selection keeps its meaning (constraint 14). | Step 2 |

D-1 and D-5 are design decisions. D-2 to D-4 are governance and scope choices. Work proceeds on the recommendations until Chetan decides otherwise; none of them is acted on beyond planning in this branch.

## 8. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| E-a residual larger than measured (only if the direct class reopens under E-a) | Wrong read-only action executes | Contained to read-only, approval-free, declared-impact actions with URI-filled arguments; reply states nothing else was done; strict G-D3 oracle; runtime killswitch |
| Extraction adds a call without improving the Brain | Wasted latency on SUPPORTING work | X-ASSIST no-harm gate G-E6; §7 value and regression thresholds; assists are parallel or deadline-bounded |
| Local-only Brain baseline | The comparison says nothing about a cloud Brain | Stated in QP §7; a cloud baseline needs Chetan's spend approval first |
| Neither model passes | No specialist routing | A valid outcome (QP §5.3, §7). Report it and stop. |
| Pair has no measured edge over Granite-only | A second runtime for nothing | QP §7 honest outcome; recommend Granite-only |
| Stage-1 bias (superseded HEAD `62d564c`, synthetic tools, n=12) carries into expectations | Over-optimism | Fresh frozen battery; Stage-1 numbers are never used as gates |
| Affirmative allowlist loses paraphrased requests | Low specialist coverage | Reported (D-PARA). They go to the Brain; nothing unsafe. |
| Runtime or model artifact drift | Qualification no longer valid | Pinned digest; mismatch means bypass |
| Encoding faults (W03) | Crash or garbled args | Explicit UTF-8 adapter contract; T-FAIL segment; `REJECT_TRANSPORT` |
| Device offline | Steps 3–6 blocked | Steps 0–2 need no device |
| Diverting effort from the product baseline | Delays URI_WORKING_PRODUCT_BASELINE | §2 sequencing |
| Frozen-guard pressure | Temptation to use M37/M38 prefixes | §3 placement; D-4 |

## 9. What remains unauthorized

This document authorizes none of the following. Each needs Chetan's explicit word at its step:
- any code;
- the battery;
- any model run, live or offline;
- any `URI_STATE.yaml`, milestone or governance-state change;
- the EXP, G4 or INT identities;
- any frozen-test or allowlist edit;
- any live-app change (`server.py`, `file_store.py`, `uri_ui`, `uri_core`);
- any merge or application of the step-7 PR;
- marking Needle or Granite qualified for anything;
- `TRANSFORM_V1`, E-b, E-c, and reopening `DIRECT_TOOL_V1`;
- the step-P prerequisites (impact declarations, id producers) and X-P1 (an extraction producer), which are live-app or new-mechanism changes;
- the optional selection diagnostic (QP §3.4), which is a model run;
- new registered capabilities;
- metered API spend;
- any send, upload, delete, overwrite or permission change during qualification;
- reopening M33.2, M33.3, M36, M37 or M38.

## 10. Next authorized step

Chetan's acceptance of this r1 and his decisions D-1 to D-5 (D-1 is on the eligibility card in the planning thread, now with E-d). A Codex re-review of r1 is optional, at his choice, through the bridge thread when it is available. r0's next step (a Codex review of r0) was done instead by a separate Claude thread while Codex is paused.

## 11. Self-review against §0

- **M-1** Pass (§4 table; §3 frozen files untouched).
- **M-2** Pass (§1 proposes and registers nothing).
- **M-3** Pass (§4 step 7, §5).
- **M-4** Pass (§6, D-4).
- **M-5** Pass (§5, §7, §8).
- **M-6** Pass (§9).
- **M-7** Pass (§2).

Gaps found in the first draft and repaired:
1. The draft placed the new package at `uri_v1/edge/specialists/`, because the guard allowlist would pass it. That depends on the prefix permissiveness already raised as a LOW finding on M39's allowlist. It would also break the M37 import boundary for binding states. It now uses a separate package plus decision D-4 (§3, §6).
2. The draft put N6 in `uri_v1`. S6 is in `uri_core` (`uri_core/core/edge/routing_policy.py`), and `uri_v1` cannot import it, so N6 moved to the step-7 PR, and the isolated steps call S6 from test code (§3).
3. The draft started live wiring right after qualification. Chetan's product target puts Edge qualification after URI_WORKING_PRODUCT_BASELINE, so step 7 is now gated on the baseline (§2).

Checked, and a finding for step 7: today `uri_core` imports nothing from `uri_v1` and `uri_v1` imports nothing from `uri_core` (a grep for `from uri_v1` / `import uri_v1` under `uri_core`, and the reverse, both returned no matches on this branch). Step 7 would therefore create the **first** `uri_core` → `uri_v1` dependency. That is an integration-boundary decision in its own right, and it belongs to the `INT-*` event, not to this plan. The alternative is to place the step-7 adapter entirely in `uri_core` and copy nothing. That will be decided when the PR is designed, and it does not affect steps 0–6.

## 12. Revision r1: repairs after the independent review

Each finding was re-checked against source before it was accepted (S2A §23). r0 is at `8305f9c`; §11 is kept as written for r0.

| Review finding | r1 repair here |
|---|---|
| H-1 no qualifiable direct workload | §3 builds only extraction components first; §4 step 1 authors the extraction battery only; new step P lists the direct prerequisites as separately authorized items |
| H-2 E-a predicted to fail | §7 D-1 row discloses it |
| M-1 E-a precedent overstated | §7 D-1 row (`task_complex` with no producer); detail in S2A §5.3 |
| M-3 single-model S6 readiness | §3 N6 per-specialist settings view; new D-5 user opt-in; §5 row |
| M-7 no subscription Brain transport | §8 risk row; detail in QP §7 |
| L-6 N6 location | §3 and §4 step 7: new file; `routing_policy.py` not edited |
| L-7 guard ordering with M39 | §6 ordering paragraph; D-4 row. Checked: `ba0db5e` and `736464a` are on `origin/claude/project-thread-wb7tmm`, not on `5bbf738`. |
| Review §4 unlisted option | E-d added to D-1 and recommended; D-3 notes the local-file link |

**Self-review of r1 against §0.** M-1 to M-7 still pass. M-6 now also covers the step-P prerequisites and the optional diagnostic. What r0 got wrong: it sequenced battery authoring for a class whose admission rules no registered action can satisfy today, and it did not list the direct-class prerequisites as separate authorizations.

### Revision r2 (re-review `5f56992`, verdict `ACCEPTABLE_WITH_BOUNDED_REPAIRS`)

Docs-only repairs, each re-checked before it was applied:
- **N-1 (MEDIUM), extraction admission and field selection.** S2A §6 step 11 now requires a deterministic producer that names a declared closed schema; no free-text classification. No producer exists among the 17 registered actions (checked), so that is prerequisite X-P1. E-SUB and G-E5 are deferred with it; the other extraction segments start from a battery-supplied schema.
- **N-2 (LOW).** QP §9 no longer names the subscription session as the Brain.
- **N-3 (LOW).** S2A §5.1 P-4 states the probe convention: full string ("Get 2021CS042." is False) vs reference removed as `affirmative_around()` does ("Get ." is True). Both hold; the conclusion is unchanged.
- **N-4 (LOW).** S2A §5.4 corrects the Stage-1 description: 0/8 and 1/8 are withholding rates over T13–T20; on T17–T20 both models chose another tool 4/4 in all 3 repeats, sometimes `draft_message` rather than a read (re-checked from `direct_tool_results.json`).

The eligibility card's options are unchanged; none of these repairs affects them.
