# Edge Specialist Pair: Migration and Integration Plan (Stage 3 draft)

Status: **PLANNING DRAFT. Not accepted. No implementation, wiring, qualification or state change is authorized by this document.**
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

- **The isolated components live in a new package**, proposed `uri_v1/specialists/`: N1 profile loader, N2 `DirectEnvelopeCheck`, N3 `SpecialistProposalValidator`, N4 `SpecialistAttemptLedger`, N5 `ExtractionValidator` and N7 adapters.
  - The package may import `uri_v1.memory.contracts` (for `negated()` and `affirmative_context()`) and `uri_v1.reference_clarification` (binding states).
  - It never imports `uri_core`, because `uri_v1` and `uri_core` may not import each other.
- **Not placed under `uri_v1/edge/` or `uri_v1/execution/`.** Those are M37 and M38 packages. Their import-boundary test (`tests/test_m37_edge_resolution.py:244`) forbids `uri_v1.reference_clarification`. The frozen-file guard's prefix allowlist would accept new files there, but using that allowance to avoid decision D-4 would be routing around a guard, which the operating rules forbid.
- **N6 `route_specialist()`** is a projection of S6 (`uri_core/core/edge/routing_policy.py`), so it belongs beside S6 in `uri_core`. It is live-app code. It is written only in step 7, as part of the PR for Chetan. Before then, the qualification harness calls `evaluate_intelligence_route` from test code, as a caller outside `uri_v1`.
- **The canonical seam** (`execute_translated_batch`, `uri_core/core/native_tool_loop.py:250`) is used unchanged.
- **No frozen file changes.** M33.2, M33.3, M36, M37 and M38 files, and `verify.py`, stay as they are.

## 4. Steps

| Step | Content | Files | Entry gate | Exit evidence |
|---|---|---|---|---|
| 0 | Independent review of S1A, S2A, QP and this plan by Codex. Chetan accepts, or accepts with repairs, and decides D-1 to D-4. | Review report under `docs/plans/` | This commit | Codex report; Chetan's recorded decisions |
| 1 | Author and freeze the battery (QP §2–§3) | `fixtures/edge_specialist_pair/` (cases, oracle, fixtures, manifest) | Step 0 and D-4 | Manifest committed; substring-collision check output; holdout sealed |
| 2 | Implement N1–N5 and N7 as pure isolated code, with fake-model unit tests for every Z invariant (QP §5.2) and every rejection reason (S2A §7) | `uri_v1/specialists/*`, `tests/test_edge_specialists_*.py` | Step 1 and an implementation authorization | Tests green; full suite green except any failure accepted under D-4; no import of `uri_core` |
| 3 | Development-split runs of every arm on Chetan's device, placement-matched; per-class assignment by QP §6 | `scripts/edge_specialist_pair_run.py`, raw outputs under `/mnt/project-files/` (not the repo) | Step 2; device online | Per-arm tables; proposed profile with rankings |
| 4 | Holdout qualification (QP §5) and comparative experiment (QP §7), one run each; pinned qualification record | `fixtures/edge_specialist_pair/record.json` (digest-pinned) | Step 3; latency and memory budgets written into the profile | `COMPLETED_WITH_RESULT` runs; gate table with n, k and bounds; honest-outcome verdict |
| 5 | Independent Codex re-score and audit of step 4 from raw outputs | Audit report | Step 4 | Codex verdict |
| 6 | L1 live canonical-path verification (QP §8) with read-only actions | Test-side runner; evidence report | Step 5 passes; Chetan names the accounts and sheet | Receipts, truthful replies, follow-up grounding, Z-5/6/7/13 evidence |
| 7 | `INT-*` proposal plus the smallest live PR: N6 projection beside S6; a call from the existing Edge routing point into `uri_v1/specialists` through a thin adapter; `URI_EDGE_SPECIALISTS` flag off by default | PR only (for example `uri_core/core/edge/…`, adapter file) | Step 6; URI_WORKING_PRODUCT_BASELINE (§2); Chetan's authorization | PR for Chetan's review and application; L2 checks after he applies it |

Each step stops at its exit, and the next step needs its entry gate. Steps 2–7 each need Chetan's explicit authorization. Step 7 is never merged or applied by a pipeline thread.

## 5. Flags, killswitch and rollback

| Control | Behaviour |
|---|---|
| `URI_EDGE_SPECIALISTS` (step 7) | Default off. Off means the Edge routes exactly as today. There is no code path into `uri_v1/specialists`. |
| Profile absent, or record digest mismatch | `edge_role_qualified=false`, so bypass (S2A §11). This is the runtime killswitch and needs no deploy. |
| Empty ranking for a class | That class never routes to a specialist (S2A §15) |
| Existing Edge OFF / `EDGE_ONLY` / explicit model | Unchanged semantics (Z-6, Z-7) |

**Rollback boundaries:**
- Before step 7: delete `uri_v1/specialists/`, its tests and its fixtures. Nothing else references them.
- After step 7: set the flag off, or revert the PR. No stored data changes format: ledger and telemetry are new, user-scoped files and can be deleted.
- There are no migrations of existing stores, and nothing to roll back in bindings, approvals or memory.

## 6. Frozen-file guard (M-4)

`tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged` (line 264) fails on any new path under `uri_v1`, `uri_core`, `uri_ui`, `tests`, `scripts` or `fixtures` outside its allowlist. Steps 1–3 add such paths. The two precedents both needed Chetan's word:
- **Dynamic planning:** Chetan accepted and documented one guard failure.
- **M39:** Chetan authorized a minimal, exact allowlist entry (`ba0db5e`).

This plan edits nothing. It lists the options as decision D-4 (§7).

## 7. Unresolved decisions

| ID | Decision | Options | Recommendation | Needed by |
|---|---|---|---|---|
| **D-1** | How the "exactly one operation of an envelope class" property is established (S2A §5) | **E-a** structural gates plus a measured, contained residual; E-b closed operation-class table over the frozen M36 vocabulary (keyword routing, needs explicit acceptance); E-c independent evidence from a second model (not supported by current evidence) | **E-a.** It adds no semantic mechanism, and QP measures the residual directly (G-D3). | Step 0 |
| D-2 | Governance scope | §1 proposal (EXP id, M33.2 amendment G4, later INT) or another form | §1 proposal | Step 1 |
| D-3 | Local-file direct requests (Stage-1's main use case) | Leave out of `DIRECT_TOOL_V1` (no registered action exists, S1A RC-10); or a separate capability lifecycle for a typed read-only locate/read action first | Leave out now; propose separately if the product needs it | Step 1 (affects battery scope) |
| D-4 | Frozen-guard handling for new test, fixture, script and package paths | Exact allowlist entries (M39 precedent, a frozen-test edit Chetan must authorize); or accept and document the failure (dynamic-planning precedent) | Exact entries. A permanently red guard hides the next real violation. | Step 1 |

D-1 is the only design decision. D-2 to D-4 are governance and scope choices. Work proceeds on the recommendations until Chetan decides otherwise; none of them is acted on beyond planning in this branch.

## 8. Risks

| Risk | Effect | Mitigation |
|---|---|---|
| E-a residual larger than measured | Wrong read-only action executes | Contained to read-only, approval-free, grounded actions; action-scoped reply; G-D3 and G-D4 gates; runtime killswitch |
| Neither model passes | No specialist routing | A valid outcome (QP §5.3, §7). Report it and stop. |
| Pair has no measured edge over Granite-only | A second runtime for nothing | QP §7 honest outcome; recommend Granite-only |
| Stage-1 bias (superseded HEAD `62d564c`, synthetic tools, n=12) carries into expectations | Over-optimism | Fresh frozen battery on live actions; Stage-1 numbers are never used as gates |
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
- `TRANSFORM_V1`, E-b and E-c;
- new registered capabilities;
- metered API spend;
- any send, upload, delete, overwrite or permission change during qualification;
- reopening M33.2, M33.3, M36, M37 or M38.

## 10. Next authorized step

Independent Codex review of S1A, S2A, QP and this plan, through the existing bridge thread (queued while the device is offline). Then Chetan's acceptance and decisions D-1 to D-4.

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
