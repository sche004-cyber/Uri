# Dynamic Planning: Stage 3 Migration & Integration Plan (Slice 1)

Location change (Chetan, 2026-10-01 12:23, "Move, then freeze"): the slice code now lives in `uri_v1/planning/`, not `uri_v1/execution/planning/`, so the frozen `uri_v1/execution/` package holds only frozen code. Paths below are as originally planned; see the slice report §12.

Status: **DRAFT FOR STAGE 3 ACCEPTANCE. PLANNING ONLY.** It is not implemented, not frozen, and it has no milestone number or INT event (review §8).
Date: 2026-09-29. Author: Claude (planning thread). Same-provider document; it has not been independently audited.
Maps to: Stage 1, the Codex review (F1 to F12, §10 gates). Stage 2, `DYNAMIC_PLANNING_STAGE2_CANONICAL_PLAN.md` (the §-refs below as "S2 §x").
Decisions in force (Chetan, 2026-09-29 01:10Z): D1 base = the winning M36 to M38 line, working line `claude/project-thread-2vamlf` until then. D2 reuse the existing verifier id and no `verify.py` edit. D3 Steps 1 to 5 run alongside M39, and there is no live/production wiring before URI_WORKING_PRODUCT_BASELINE.

---

## 1. Base and rollback point

- **Working base:** tip of `claude/project-thread-2vamlf` when implementation starts. At writing that is `21bcc63`, a descendant of `c7832b9`. The implementer records the exact SHA as `BASE` in the implementation report.
- I checked the reused interfaces at `21bcc63` against `c7832b9` and `62d564c`. `acceptance.py`, `lineage.py`, `run_record.py`, `officefile.py`, `verify.py`, `memory/sources.py` and `edge/report.py` are byte-identical between `c7832b9` and `21bcc63`. `workspace.py` differs only in approval-text helpers; `Workspace.create/diff/originals_unchanged` are unchanged. `62d564c` has the same public signatures (S2 §1).
- **If the freeze picks the other line:** rebase the slice (new files only, so no conflicts are expected) and re-run G8 and the full slice battery on it before audit.
- **Rollback:** delete `uri_v1/execution/planning/`, `tests/test_dynamic_planning_*.py`, `fixtures/dynamic_planning/` and `scripts/dynamic_planning_qualification.py`. Nothing else references them. `BASE` is the rollback point.

## 2. Module disposition

| Kind | Modules |
|---|---|
| **New** (only these may appear in the diff) | `uri_v1/execution/planning/{__init__,contracts,compiler,bindings,actions,runner,oracle,provider_port}.py`; `tests/test_dynamic_planning_{contracts,compiler,bindings,execution,verification,boundaries}.py`; `fixtures/dynamic_planning/**`; `scripts/dynamic_planning_qualification.py`; `docs/architecture/DYNAMIC_PLANNING_CANONICAL_ARCHITECTURE.md`; `docs/plans/DYNAMIC_PLANNING_MIGRATION_PLAN.md`; `docs/plans/DYNAMIC_PLANNING_SLICE1_IMPLEMENTATION_REPORT.md` |
| **Reused unchanged** | `uri_v1/execution/{officefile,workspace,acceptance,lineage,verify,run_record}.py`, `uri_v1/memory/{sources,recorder}.py`, `uri_v1/results/version_ledger.py`, `uri_v1/edge/report.py` (`recompute`, called by the composed dispatch) |
| **Modified** | **None.** Any need to modify stops the work, and the plan is amended first (review §8, D2). |
| **Deprecated/retired** | None in slice 1. The experimental planners get the `REJECTED_FOR_PRODUCTION` marker in step 9 (S2 §8), in a separate docs change on Chetan's checkout. They are untracked, so no pipeline thread can edit them. |
| **Untouched boundaries** | Frozen M33.3/RAR/ARN (anchors in `scripts/m33_3_r_anchors.py`), `uri_core/**`, `uri_v1/{turn,reference_clarification,wording,memory,edge}/**`, `uri_v1/execution/harness/**`, `uri_v1/office/**` (M39), `server.py`, `file_store.py`, `uri_ui/**`, `docs/governance/**` |

## 3. Compatibility and flags

- There is no production entry point, so no feature flag is needed. The only entry points are `scripts/dynamic_planning_qualification.py` and the tests. The package must not be imported by any existing module; a boundary test asserts this.
- Verifier bootstrap: `oracle.verifier_entries(run_root)` returns `{VERIFIER_ID: (VERIFIER_TYPE, VERIFIER_VERSION, make_memory_verifier(run_root, recompute=_dispatch))}`. `_dispatch(tc, ws, p)` routes `tc.startswith("PLANNED_STRUCTURE_REPORT@")` to the planning oracle and anything else to `uri_v1.edge.report.recompute`, unchanged. It is used **only** by the qualification script and tests, and each calls `_bootstrap_verifiers` once per process (tests use a subprocess or the existing M37 test fixture pattern). Edge verdicts under the composed dispatch must be identical (compatibility test C-1).
- D2 labelling: Memory receipts carry the existing verifier id. The planning origin is identifiable from `criteria_sha256` / the `PLANNED_STRUCTURE_REPORT@<plan_sha256>` task class. This is disclosed in the implementation report.

## 4. Step-by-step sequence (Steps 3 to 5 of S2 §8)

Each step ends with its checks run (COMPLETED_WITH_RESULT) and one bounded commit containing new files only.

**4.1 Fixtures first (frozen before any qualifying run)**
- `fixtures/dynamic_planning/make_workbooks.py` writes minimal `.xlsx` files with `zipfile` and a fixed `date_time=(2020,1,1,0,0,0)`, so the bytes are deterministic and the hashes pinned. Workbooks: `wb_a.xlsx` (sheets Orders[Id,Date,Amount], Vendors[VendorId,Name]); `wb_b.xlsx` (Orders[Id,Date,Amount,Region], Returns[Id,Reason]); `wb_same_as_a.xlsx` (content-identical to A, different name); `wb_formula_err.xlsx` (Orders with one `#REF!` cell); `wb_malformed.xlsx` (not a zip); `wb_big_header.xlsx` (header > MAX_HEADER_CELLS).
- `qualification_cases.json` holds the case list in §5, with scorer-only expectations kept in a separate `expected` object that the runner never loads. `threshold_gate.json` holds the counters in §6. Record both file sha256s in the implementation report **before** the first qualifying run.

**4.2 Slice 1a: contracts, compiler, bindings (pure; no filesystem except fixtures)**
- `contracts.py`, `compiler.py`, `bindings.py` as specified in S2 §2.2 to §2.4 and §6.
- Tests: G1 and G3 cases (§5), plus unit tests for canonical hashing (dict key order, unicode) and `SemanticProposal.parse` on malformed input (non-dict, extra keys, oversize).

**4.3 Slice 1b: actions, runner, oracle, provider port**
- `actions.py`: the four actions (S2 §4) and `snapshot()`. The snapshot's per-contract qualification is a pinned `QualificationRecord`-style JSON (`fixtures/dynamic_planning/capability_qualification.json`, sha pinned in `actions.py`), following the `uri_v1/edge/registry.py` pattern without importing or changing its `TaskClass`.
- `runner.py`: S2 §2.5 and §4 run recording (`executor: "LOCAL_EDGE"`, `capability_id: "uri.plan.compiled"`, `plan_sha256`). `bundle/plan.json` is written **before** `RUN_STARTED`. `record_and_verify(..., verifier_id=VERIFIER_ID)`. `PlanOutcome.status ∈ {VERIFIED, NOT_VERIFIED, REJECTED, NEEDS_CLARIFICATION, NOT_ATTEMPTED}`. Only `VERIFIED` from the verifier counts as completed.
- `oracle.py`: S2 §2.6. The recompute is a direct walk over `read_workbook_structure` results. It must not import `runner` or `bindings` (enforced by a boundary test).
- `provider_port.py`: `ProposalProvider`/`ProposalAdvisor` Protocols, `FixtureProvider`, `NullAdvisor`. No real provider adapter in this step.
- Tests: G4, G5, C-1, and the boundaries test (§7).

**4.4 Qualification script and report**
- `scripts/dynamic_planning_qualification.py [--cases PATH] [--out PATH]`: bootstraps the verifier, runs every case through `FixtureProvider → compile → run`, then scores **afterwards** against `expected`, deriving the §6 counters from observed events. It writes `docs/plans/DYNAMIC_PLANNING_SLICE1_QUALIFICATION_RESULTS.json` and exits non-zero if any safety counter is non-zero or a threshold is missed.
- Implementation report `docs/plans/DYNAMIC_PLANNING_SLICE1_IMPLEMENTATION_REPORT.md`: BASE, battery/threshold hashes, each check's command and result, disclosed limitations, and the D2 label note.

**4.5 Step 5: fresh Opus audit** (separate thread). It starts from repo evidence, reruns everything, and adds adversarial probes beyond §5. Stop at the verdict. The slice stays PROVISIONAL / NOT FROZEN whatever the result.

## 5. Frozen battery (slice 1)

Every case is a (proposal, candidates, snapshot-mutation?) triple. "No success" means the outcome is not `VERIFIED` and no report result version is recorded as verified.

| ID | Gate | Case | Scorer expectation |
|---|---|---|---|
| C01 | G1 | Happy path: inspect A, inspect B, select Orders on each, compare on sheet_name, write | VERIFIED; report lists shared headers Id/Date/Amount, only-right Region |
| C02 | G1 | Same as C01 with nodes listed in reverse order in JSON | Same plan sha as C01 (canonicalized), VERIFIED |
| C03 | G1 | Two consumers of one inspect (select Orders and select Vendors from A) + write both | VERIFIED |
| C04 | G1 | Snapshot where `inspect_structure` is renamed `load_workbook_structure` with identical ports; proposal uses the new name | VERIFIED |
| C05 | G1 | Proposal uses the old name after the rename | REJECTED `UNKNOWN_ACTION` |
| C06 | G1 | Duplicate node id | REJECTED `DUPLICATE_NODE` |
| C07 | G1 | Edge to a non-existent port | REJECTED `UNKNOWN_PORT` |
| C08 | G1 | Type mismatch (WORKBOOK_STRUCTURE into compare) | REJECTED `PORT_TYPE_MISMATCH` |
| C09 | G1 | Cycle select↔compare | REJECTED `CYCLE` |
| C10 | G1 | Required input unbound | REJECTED `UNBOUND_REQUIRED_INPUT` |
| C11 | G1 | Action version not in snapshot | REJECTED `UNKNOWN_ACTION_VERSION` |
| C12 | G1 | Only `cannot[]` ("book a flight"), no nodes | REJECTED `NO_EXECUTABLE_PLAN`; never success |
| C13 | G1 | Node/edge/literal size limits exceeded | REJECTED `LIMIT_EXCEEDED` |
| C14 | G1 | Report output not reachable from declared outputs | REJECTED `UNREACHABLE_OUTPUT` |
| C15 | G3 | `source` id not in trusted candidates | REJECTED `UNKNOWN_SOURCE` |
| C16 | G3 | Two candidates with the same file name in different roots; the proposal marks one source port `{"sources_ambiguous": [id1, id2]}` | NEEDS_CLARIFICATION with both ids; no run |
| C17 | G3 | Candidate hash stale (file edited after scan) | NOT_ATTEMPTED `INPUT_NOT_CURRENT` |
| C18 | G3 | Literal sheet `orders` (wrong case) | NOT_ATTEMPTED (RUN_ABORTED `LITERAL_NOT_IN_SOURCE`); no fuzzy match |
| C19 | G3 | Proposal supplies a filesystem path instead of a source id | REJECTED `PROPOSAL_INVALID` |
| C20 | G3 | Proposal supplies a handle-shaped token | REJECTED `PROPOSAL_INVALID` |
| C21 | G3 | `wb_malformed.xlsx` as source | NOT_ATTEMPTED typed `XLSX_NOT_ZIP`; downstream nodes not run |
| C22 | G4 | Snapshot mutated (select version bumped) between compile and run | NOT_ATTEMPTED `CAPABILITY_CHANGED`; descendants not run |
| C23 | G4 | Capability removed after compile | as C22 |
| C24 | G4 | `wb_big_header.xlsx` | typed `XLSX_HEADER_TOO_WIDE`; descendants not run |
| C25 | G4 | Proposal adds `approval`/`effect`/extra keys | REJECTED `PROPOSAL_INVALID` |
| C26 | G5 | Runner patched (test hook) to write forged report bytes | NOT_VERIFIED |
| C27 | G5 | Runner patched to drop one comparison section | NOT_VERIFIED |
| C28 | G5 | Runner patched to write an extra artifact | NOT_VERIFIED (`only_changed` FAIL) |
| C29 | G5 | `bundle/plan.json` tampered after RUN_STARTED | NOT_VERIFIED |
| C30 | G5 | Original A modified between run and verification (test hook wrapping `invoke_verifier`) | NOT_VERIFIED (`original_integrity`) |
| C31 | G5 | Original A deleted between run and verification (same hook; `verify_source` returns False on a missing file, `sources.py` `verify_source`) | NOT_VERIFIED |
| C32 | G5 | FixtureProvider returns malformed JSON / raises timeout | NOT_ATTEMPTED `PROPOSAL_INVALID` / `PROVIDER_UNAVAILABLE`; no run |
| C33 | G5 | Correct action names, wrong literal (selects Vendors where the scorer expects Orders) | VERIFIED as executed (verifier checks the plan it was given); **scored as a semantic miss**, not a safety counter. This keeps proposal accuracy separate from runtime correctness (review §10.2). |
| C-1 | compat | The existing M37 edge WORKBOOK_INSPECT fixture under the composed dispatch | Same verdict as the unmodified edge verifier |

The test hooks for C26 to C28 live only in tests (monkeypatch). There is no production-reachable hook.

## 6. Thresholds and counters (`threshold_gate.json`)

- Must be exactly 0, derived from events: `false_verified_completion` (VERIFIED where the oracle, rerun by the scorer from pristine fixtures, disagrees, or any of C26 to C31 VERIFIED); `unauthorized_effect` (any change outside the run's `files/` other than RunStore/Memory/ledger appends; checked by hashing the fixture roots before and after); `wrong_source_binding`; `undeclared_execution` (an action invoked for a node not in the CompiledPlan, counted by an adapter-call recorder); `undetected_original_modification`; `unresolved_reported_complete` (any REJECTED/NEEDS_CLARIFICATION/NOT_ATTEMPTED reported as VERIFIED).
- Must be 100%: expected typed outcome on C01 to C32 and C-1.
- Reported, not gated: C33 semantic miss count; latency p50/p95 per case.
- Numerators and denominators are always reported. No counter is initialised to a passing value.

## 7. Test plans

- **Component:** the six `tests/test_dynamic_planning_*.py` files cover C01 to C33 and C-1 as pytest cases, plus the unit tests in §4.2.
- **Boundaries (`test_dynamic_planning_boundaries.py`):** (a) AST scan: no `uri_core`, `experimental`, `server`, `file_store` or `uri_ui` import anywhere under `planning/`; `oracle.py` doesn't import `runner`/`bindings`. (b) No existing module imports `uri_v1.execution.planning`. (c) sha256 manifest of every reused file in §2 pinned at BASE, asserting it is unchanged.
- **Integration (offline):** the qualification script end to end.
- **Regression (G8), run at BASE and at HEAD with identical results required:**
  - `python -B -m pytest -q -p no:cacheprovider tests/`
  - the review command: `python -B -m pytest -q -p no:cacheprovider test_multi_action_capabilities.py test_m33_p1_permission_seam.py tests/test_m37_edge_execution.py tests/test_m38_harness.py tests/governance/test_uri_state_validator.py`
  - `python scripts/m33_3_r_anchors.py`; the M36/M37/M38 qualification scripts (gates unchanged)
  - `git diff --name-only BASE HEAD` ⊆ the §2 "New" list (the audit checks this)
- **Behavioural/live:** none in slice 1 (D3). The live verification plan belongs to the separately authorized production stage (S2 §8 step 8, G9), after the baseline.

## 8. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Composed verifier dispatch changes Edge verdicts | C-1; the dispatch falls through to the unchanged `edge.report.recompute` for every non-planning task class |
| Plan/verifier drift (verifier checks a different plan than was run) | Plan sha in the acceptance task class, and the acceptance sha checked against RUN_STARTED by the existing verifier; C29 |
| Oracle shares a bug with the runner | Separate code path (boundary rule); C26 to C28; shared `officefile` disclosed |
| Test double overstates semantic ability | C33 scored separately; the real provider comes only in step 6 |
| Verifier bootstrap is process-global | Only the script and tests bootstrap; tests isolate by subprocess |
| Base line changes after freeze | New-files-only diff; rerun G8 on the winning line |
| Label ambiguity (D2) | Disclosed; distinct id added only once the M38 boundary is available |
| POSIX/OS sandbox gaps | Not exercised: slice 1 runs no scripts or subprocesses (the verifier's `script_exit_zero` path is not used) |

## 9. Approval and safety impact

Read-only access to hash-bound fixture copies; one scratch report; no write-back, network, subprocess, model call or live-app change. No new permission, grant or approval path. No frozen or provisional file changed. No governance state changed. Spend: none (FixtureProvider only).

## 10. Implementation handoff (for the coordinator)

- **Milestone:** Dynamic Planning Slice 1 (no milestone number). **Role:** Implementation (Sonnet 5, medium).
- **Predecessor:** tip of `claude/project-thread-2vamlf` (record the SHA); M36 to M38 PROVISIONAL / NOT FROZEN.
- **Accepted plans:** Stage 2 (`plans/DYNAMIC_PLANNING_STAGE2_CANONICAL_PLAN.md`) and this Stage 3 plan, with D1 to D3.
- **Frozen/boundary:** §2 "Untouched boundaries" and "Modified: none". No `verify.py` edit.
- **Required checks:** §4 to §7.
- **Stop conditions:** any needed edit outside the §2 "New" list; any safety counter > 0 that isn't fixable inside the new files; completing §4.4. Commit and push to its own branch; no PR, freeze or live wiring. Then a fresh Opus audit (step 5).
