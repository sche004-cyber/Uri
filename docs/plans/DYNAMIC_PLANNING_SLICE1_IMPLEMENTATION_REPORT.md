# Dynamic Planning Slice 1: Implementation Report

Status: **PROVISIONAL / NOT FROZEN.** Implementation of migration-plan Steps 3 and 4 (Stage 2 §8), for the fresh independent audit in Step 5. Same-provider self-report; every claim below is a lead for the audit, not evidence.
Plans: `docs/architecture/DYNAMIC_PLANNING_CANONICAL_ARCHITECTURE.md` (Stage 2), `docs/plans/DYNAMIC_PLANNING_MIGRATION_PLAN.md` (Stage 3). Decisions D1 to D3 (Chetan, 2026-09-29 01:10Z).

## 1. Base

- **Current base: the frozen M36-M38 line `5bbf738`** (CLOSED_FROZEN at `bd7c450`, the line D1 now names). The slice's three commits (plan docs, battery freeze, implementation) were rebased onto it without conflicts, because they add new files only.
- History: implementation started on `4292528` (the plan docs on `21bcc63`, the D1 working line at the time) and was first pushed as `67e0e94` (freeze) and `bdb4834`. The rebase supersedes those SHAs with the same content and order; the freeze commit is now `44fa36e`.
- Rollback point: `5bbf738`.

## 2. Frozen battery (recorded before the first qualifying run)

These digests were recorded and committed (originally `67e0e94`, now `44fa36e`) before `scripts/dynamic_planning_qualification.py` was first run against the battery. Digests are over LF-normalized bytes for the JSON files (the script uses the same normalization) and raw bytes for the workbooks.

| File | sha256 |
|---|---|
| `fixtures/dynamic_planning/qualification_cases.json` | `2c36641926db04e679fb937ce10d0fff141c7989e049618caf9759002fd0f419` |
| `fixtures/dynamic_planning/threshold_gate.json` | `f2dfc9371871eb994ff22f4e5a6d0802864980d9dab03e521a8dac04938c50ff` |
| `fixtures/dynamic_planning/capability_qualification.json` (pinned in `actions.py`) | `98c1d78e22138ce6f83c767f0524b4564f81658b3f99efda2bfaaa8b834e7c49` |
| `fixtures/dynamic_planning/make_workbooks.py` | `02079cbddad55c5c7efbbe6ee766ed3de986ff3d8860c450cd45ae78d1acf9f2` |
| `workbooks/wb_a.xlsx` and `wb_same_as_a.xlsx` | `cec400e4af19eb279a7ff4a76c8cde8cacad2ce86c5bd92abbeb67ba95e08bec` |
| `workbooks/wb_b.xlsx` | `7a360f54b71967a6efc7053e9ae9799796560367ee277a73fe768e8d414c0cc0` |
| `workbooks/wb_big_header.xlsx` | `87f890af7122ed25c1795867da4e72e10f10a0f8c8d4f658b84d74bd99346c5d` |
| `workbooks/wb_formula_err.xlsx` | `ce00b21bc0fbf59af0d679238d6ae6c1d76dd1306a877fe01c561f7e9a2c8e00` |
| `workbooks/wb_malformed.xlsx` | `a2299a934d0befe8931ddabf7672fa4467e0e0abc0034caa98e7908c19bf6015` |

`make_workbooks.py` regenerates byte-identical workbooks (fixed zip entry time, stored entries); two independent runs produced the digests above.

Battery notes, fixed at freeze time:
- C32 is split into `C32a` (malformed JSON) and `C32b` (timeout) so each has one typed expectation.
- C13 exercises the node limit. The edge and literal limits are covered by unit tests.
- The runner reads only `cases`; the scorer reads `expected` after every case has run.


## 3. What was built (new files only)

| File | Role (Stage 2 ref) |
|---|---|
| `uri_v1/execution/planning/contracts.py` | Closed `PortType`; `LiteralSpec`, `InputSpec`, `CapabilityContract`, hashed `CapabilitySnapshot`; `SemanticProposal.parse` (closed schema `uri.plan.proposal.v1`, typed `ProposalInvalid`); `CompiledPlan` (canonical JSON + sha256, `task_class`); `Rejection`, `ClarificationRequired`, `PartialPlan` (interface only) (§2.1 to §2.4) |
| `uri_v1/execution/planning/compiler.py` | `compile_proposal(proposal, snapshot, candidates, *, limits)` (§2.3) |
| `uri_v1/execution/planning/bindings.py` | `candidates_from_registry`, `bind_sources`, `valid_value`, `Handle`, `HandleTable` (§2.4) |
| `uri_v1/execution/planning/actions.py` | The four actions, `default_catalog`, `snapshot`, `adapters`, `renamed`; qualification record pinned by digest (§4) |
| `uri_v1/execution/planning/runner.py` | `PlanRunner.run`, `PlanOutcome`, `plan_acceptance`, `run_proposal` (§2.5, §4) |
| `uri_v1/execution/planning/oracle.py` | `recompute`, `expected_report`, `dispatch`, `verifier_entries` (§2.6, migration §3) |
| `uri_v1/execution/planning/provider_port.py` | `ProposalProvider`/`ProposalAdvisor` protocols, `FixtureProvider` (test double), `NullAdvisor` (§2.8, §2.9) |
| `tests/test_dynamic_planning_{contracts,compiler,bindings,execution,verification,boundaries}.py` | Component, boundary and integration tests (migration §7) |
| `fixtures/dynamic_planning/**` | Workbooks and generator, battery, gate, capability qualification record |
| `scripts/dynamic_planning_qualification.py` | Qualification driver and scorer (migration §4.4) |
| `docs/plans/DYNAMIC_PLANNING_SLICE1_QUALIFICATION_RESULTS.json` | Output of the driver (named by migration §4.4) |

**Existing files modified: none.** `verify.py` is untouched (D2). No live-app, frozen, M36/M37/M38, M39 or experimental file is touched, and no existing module imports the package (boundary test).

## 4. Checks run (all COMPLETED_WITH_RESULT on Linux, Python 3.11.15)

| Check | Command | BASE `5bbf738` (first run at `4292528`) | HEAD |
|---|---|---|---|
| Full suite | `python -B -m pytest -q -p no:cacheprovider tests/` | 1303 passed, 9 skipped (1283 at `4292528`) | **1404 passed, 1 failed**, 9 skipped (the new slice tests included; failure in §4.1). **Correction:** 102 slice tests at `3bbf8f7`, not 101 (audit D-7); the totals were right. Current head: §8. |
| Review regression | `python -B -m pytest -q -p no:cacheprovider test_multi_action_capabilities.py test_m33_p1_permission_seam.py tests/test_m37_edge_execution.py tests/test_m38_harness.py tests/governance/test_uri_state_validator.py` | 113 passed | 113 passed |
| Frozen anchors | `python scripts/m33_3_r_anchors.py` | ok, changed [] | ok, changed [] |
| M36/M37/M38 qualification | `python scripts/m3{6_memory,7_edge,8_harness}_qualification.py` | exit 0 each, gates passed | exit 0 each, gates passed |
| Governance | `python -B -m pytest -q -p no:cacheprovider tests/governance` and `python scripts/governance/uri_state_validator.py` | 37 passed, VALID | 37 passed, VALID |
| Slice tests | `python -B -m pytest -q -p no:cacheprovider tests/test_dynamic_planning_*.py` | n/a | 102 passed at `3bbf8f7` (was misreported as 101; see §8) |
| Slice qualification | `python -B scripts/dynamic_planning_qualification.py` | n/a | exit 0, gate passed |

### 4.1 G8 is not identical: one frozen M37 scope guard fails (decided: accepted)

`tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged` passes at BASE and fails at HEAD. It asserts that every path changed or added since M36 baseline `179fe10` under `tests`, `scripts` and `fixtures` starts with an M37/M38 prefix. The plan puts this slice's tests, driver and fixtures at `tests/test_dynamic_planning_*.py`, `scripts/dynamic_planning_qualification.py` and `fixtures/dynamic_planning/**`. The production package `uri_v1/execution/planning/` is already allowed. M36 to M38 are CLOSED_FROZEN, and Chetan ruled (2026-09-29 05:21) that dynamic planning gets no allowlist entry in that test. So this failure stays, and no frozen file was edited.

Relocation was tried in the rework and reverted, because it only passes by placement:
- Under `uri_v1/execution/planning/` it passes the scope guard but fails the separate frozen M37 import check (`test_edge_and_execution_import_boundaries`). The test harness builds real M36 stores (`uri_v1.memory.recorder`, `sources`, `log`), and that check allows only `uri_v1.memory.contracts` inside `uri_v1/execution`.
- In a new top-level directory outside every guard's scope, both frozen checks pass, but only because the files sit where no guard looks.

Options for Chetan: (a) keep the plan locations and accept this one documented failure until governance allows a successor rule; (b) allow an exact-path entry covering only the slice's test, driver and fixture paths (the production package is already covered); (c) approve a dedicated top-level qualification directory for successor-milestone harnesses as a governance rule rather than a workaround.

**Decision (Chetan, 2026-09-29 05:31): option (a).** The files stay at the plan locations and this is the one documented expected failure of the full suite at this commit. It is not a regression in frozen code. No frozen file is edited and nothing is relocated. Any other failure in a rerun is a real defect.

### 4.2 Rework on the frozen line (Chetan, 2026-09-29 05:21: keep the SourceResolver/adapter approach)

- `bindings.py` no longer imports `uri_v1.memory`. It declares a `SourceResolver` protocol (`scan`, `fingerprint`, `verify_source`), and the caller injects the resolver; M36's `SourceRegistry` satisfies it structurally. No planning production module imports anything from `uri_v1.memory`. That is stricter than the frozen M37 rule, which allows `uri_v1.memory.contracts`.
- New boundary tests: no planning production module imports `uri_v1.memory` or the test harness. A new binding test shows that only hash-verified resolver refs become candidates.
- The battery, gate, qualification record and workbooks are unchanged; the §2 digests still hold.

The M36 to M38 qualification scripts rewrite their own tracked result files under `docs/plans/` (timestamps and latencies). Those rewrites were reverted and are not part of this slice.

## 5. Qualification results (`DYNAMIC_PLANNING_SLICE1_QUALIFICATION_RESULTS.json`)

- Battery sha256 `2c366419…f0f419`, gate sha256 `f2dfc937…c50ff` (both as recorded in §2).
- Expected typed outcome: **34 / 34** (C01 to C31, C32a, C32b, C-1). C33 is reported separately.
- Safety counters (numerator / denominator, derived from observed events):

| Counter | Result |
|---|---|
| false_verified_completion | 0 / 34 |
| unauthorized_effect | 0 / 34 |
| wrong_source_binding | 0 / 16 (runs that started) |
| undeclared_execution | 0 / 16 (runs that started) |
| undetected_original_modification | 0 / 34 |
| unresolved_reported_complete | 0 / 34 |

- Reported, not gated: C33 semantic miss 1 / 1 (expected: the wrong literal is verified as executed and scored as a miss); latency p50 ≈ 1 ms, p95 ≈ 36 ms per case on this machine (volatile).
- Negative control (not part of the gate): forcing C26 and C30 to report VERIFIED, adding an extra executed node to C22 and corrupting one C01 manifest hash made the counters read 2, 1, 1, 1 and 2 as expected, so they are not constant zeros.

**Run history (preserved, not overwritten).** Run 1 crashed in the scorer (NO_OUTPUT): it read the first ledger output as the report, which in C28 is the extra artifact. Fixed in the driver to read the `plan_report.json` change. Run 2 completed with the gate **failed**, 32 / 34: C22 and C23 flagged "halted at wrong node" because the scorer compared the expected halt node with the last *executed* node, while a node refused for CAPABILITY_CHANGED is stopped before it runs. The runtime behaviour (sa refused, no descendant run) matched the expectation; the scorer now reads the node named in the RUN_ABORTED event. Run 3 passed as above. Run 4, on the frozen line after the rework, passed with the same result. The battery and gate files were not changed between runs (digests in §2 still match). Run 2's results file is kept for the audit at `/mnt/project-files/audits/dynamic_planning_slice1/qual_run2_results_superseded.json`.

## 6. Deviations and disclosed limitations

1. **Compiler check order (deviation from Stage 2 §2.3).** Acyclicity is checked on the resolved references before port types. With the closed slice-1 vocabulary every cycle also mismatches a type, so the documented order would make CYCLE unreachable and C09 untestable. Literal specs are checked in the same pass as references; port types are then checked before the output, qualification and coverage checks.
2. **`report.write` takes a multi-ref `items` port** accepting STRUCTURE_SELECTION or STRUCTURE_COMPARISON (Stage 2 §4 "1..4 × (SELECTION | COMPARISON)"). Compatibility is still exact membership in the declared set; nothing is coerced.
3. **Oracle identifies node semantics by `verifier_coverage`**, recorded per node in the CompiledPlan, not by action spelling, so a renamed action (C04) stays verifiable.
4. **Capability qualification is self-qualification** (`capability_qualification.json`, status QUALIFIED) by the implementer, PROVISIONAL until the Step 5 audit, as with M37.
5. **Per-node revalidation** compares `(action_id, version, qualification_sha, verifier_coverage)` and the adapter's presence, as specified. It does not re-compare a live contract's port declarations.
6. **Ceilings are checked, not pre-empted.** Node wall-clock is measured after the pure action returns, and the run ceiling is checked between nodes. Slice-1 actions are bounded by `officefile`'s own limits.
7. **Handle identity checks** (`HandleTable.resolve`: fabricated, cross user/task/run) are exercised by unit tests; the runner itself looks values up by `(node, port)` in a fresh per-run table and never hands handles out.
8. **D2 label.** Memory receipts carry the existing verifier id `uri.verifier.execution.script_workbook.v1`. A planning verdict is identifiable only by its acceptance task class `PLANNED_STRUCTURE_REPORT@<plan_sha256>` / `criteria_sha256`.
9. **Shared reader.** The oracle's execution path is separate, but it shares `officefile.read_workbook_structure` with the actions (Stage 2 §2.6).
10. **Plan inconsistency.** Migration plan §2's "New" list omits `docs/plans/DYNAMIC_PLANNING_SLICE1_QUALIFICATION_RESULTS.json`, which §4.4 requires the driver to write. It is committed as §4.4 says.
11. **Windows not run.** All checks ran on Linux only. `wb_malformed.xlsx` is a text file, so a Windows autocrlf checkout could change its bytes (and its §2 digest); nothing reads that digest at run time, and the XLSX_NOT_ZIP outcome does not depend on line endings.
12. **graphify** is not installed in this environment and `graphify-out/` is untracked, so `graphify update .` was not run.
13. **No live provider, no spend.** FixtureProvider only (D3, spend policy). Semantic ability is not measured.
14. **Trusted adapters, no OS sandbox (audit F2; retained limitation, PENDING CHETAN'S CONFIRMATION).** The runner checks each node's contract metadata and qualification digest against the live snapshot, but not the identity of the injected adapter callable. Whoever wires the runner in-process can substitute an adapter under the same `(action_id, version)` that writes outside the workspace, and the run can still verify, because the verifier checks the workspace, not the host. This needs control of trusted in-process wiring, not proposal text or user data, and is the same class as the shared "no OS sandbox" limitation retained at the M36-M38 freeze and M36's M-2. The audit recommends accepting it as documented; no adapter-identity check is added unless Chetan chooses one (the alternative: pin each adapter's `module:qualname` and code digest in the qualification record and check it before each node).
15. **Plan re-derivation needs the pinned snapshot.** `PlanRunner.run` now takes the snapshot the plan was compiled against (`snapshot=`; `run_proposal` passes it). Without it, or with one whose hash differs from `plan.snapshot_sha256`, the run is refused as PLAN_NOT_COMPILED before anything is recorded.

## 7. Next

§4.1 is decided (accepted failure). Next:

Step 5: a fresh independent audit that starts from repository evidence, reruns everything above, and adds adversarial probes beyond the battery. The slice stays PROVISIONAL / NOT FROZEN whatever the result. The slice now sits on the frozen line, so the migration-plan §1 rebase contingency is closed.

## 8. Repair round 1 (independent Claude audit of `c5d47a0`, verdict REPAIRS_REQUIRED)

Audit report: `docs/reviews/dynamic_planning_slice1_audit/` on `claude/project-thread-vhp2g6` (`b4eae6b`). All repairs are in the slice's own files; no frozen file, `verify.py` or battery/gate file changed (`git diff --quiet 44fa36e -- fixtures/dynamic_planning` holds).

| Finding | Repair | Regression test |
|---|---|---|
| F3 (MEDIUM) verifier-path exception escapes | Any exception from `record_and_verify` (including the ledger's `ResultVersionError`) returns `NOT_VERIFIED` with reason `VERIFICATION_ERROR:<type>` (ValueError/OSError keep their message) and appends RUN_ABORTED unless the run already has a VERIFICATION event | `test_ledger_error_during_recording_is_not_verified_with_a_closed_record`, `test_any_verifier_path_exception_is_not_verified` |
| N1 (MEDIUM) damaged workbook crashes, run left open | Any other adapter exception is a typed abort `ACTION_FAILED` (exception type in the RUN_ABORTED `detail`); any unexpected runner exception is `RUNNER_ERROR`; setup and RUN_STARTED failures are `NOT_ATTEMPTED` with no run recorded; if the store itself cannot take RUN_ABORTED the reason ends `\|RUN_NOT_CLOSED` | `test_damaged_user_workbook_is_a_typed_abort_with_a_closed_record[bad_crc,encrypted,bad_method]`, `test_any_adapter_exception_is_a_typed_abort`, `test_a_broken_run_store_still_returns_a_typed_outcome` |
| N2 (MEDIUM) deep nesting crashes the parser | `parse_raw` refuses raw text over 256 KiB before parsing (also N8), catches `RecursionError`, and refuses nesting deeper than 16; `SemanticProposal.parse` checks depth iteratively before canonicalizing (`PROPOSAL_INVALID/NESTING_DEPTH`); `run_proposal` turns a raising provider into `PROVIDER_UNAVAILABLE` | `test_deeply_nested_provider_text_is_a_typed_invalid_proposal`, `test_oversized_provider_text_is_refused_before_parsing`, `test_deeply_nested_proposal_dict_is_rejected_not_crashed`, `test_run_proposal_turns_a_raising_provider_into_a_typed_outcome` |
| F1 (LOW) changed battery accepted | Driver pins the battery and gate digests and exits 2 on a mismatch; `--non-qualifying` runs anyway, labelled NON_QUALIFYING with the gate forced to fail | `test_qualification_driver_refuses_a_changed_battery` |
| N3 (LOW) hand-built plan runs | Before anything is recorded, the runner rebuilds the proposal from the plan, recompiles it against the pinned snapshot and candidates, and requires the byte-identical plan (including `proposal_sha256`); a supplied raw proposal must hash to `proposal_sha256`. Otherwise `REJECTED/PLAN_NOT_COMPILED`; a non-`CompiledPlan` now gets the same typed refusal instead of `ValueError` | `test_runner_refuses_a_hand_built_plan_the_compiler_would_reject`, updated `test_runner_refuses_anything_but_a_compiled_plan` |
| N4 (LOW) NOT_ATTEMPTED after every node ran | An abort after every node executed is `NOT_VERIFIED` (reason = abort code); partial aborts stay `NOT_ATTEMPTED` as the frozen battery expects | `test_run_that_executed_every_node_is_not_labelled_not_attempted` |
| D-7 (LOW) test count | §4 corrected (102 at `3bbf8f7`, history kept) | n/a |
| F2 (HIGH→MEDIUM, decision) | Not changed; retained limitation §6.14, pending Chetan | n/a |

Re-running the audit's own probe script (adjusted only to pass `snapshot=` to direct `runner.run` calls): N1 ×3 `NOT_ATTEMPTED/ACTION_FAILED` with `RUN_STARTED, RUN_ABORTED`; N2a `PROPOSAL_INVALID`; N2b `PROPOSAL_INVALID/NESTING_DEPTH`; F3 and F3b `NOT_VERIFIED`; N3 `REJECTED`; N4 `NOT_VERIFIED/OUTPUT_TYPE_INVALID`; F1 refused (no result file); F2 still `VERIFIED` with the outside file written (by design, §6.14); N5, N9 safe.

Checks at the repair head (Linux, Python 3.11.15, all COMPLETED_WITH_RESULT):

| Check | Result |
|---|---|
| Full suite | **1418 passed, 1 failed** (only the accepted `test_m36_and_frozen_files_unchanged`), 9 skipped |
| Slice tests | 116 passed |
| Slice qualification | exit 0: 34/34, counters 0/34, 0/34, 0/16, 0/16, 0/34, 0/34; C33 miss 1/1; battery and gate digests as §2 |
| Review regression set | 113 passed |
| Anchors / governance validator | ok, changed [] / VALID |
| M36, M37, M38 qualification | exit 0 each (rewritten result files reverted) |
