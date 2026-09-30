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
| Full suite | `python -B -m pytest -q -p no:cacheprovider tests/` | 1303 passed, 9 skipped (1283 at `4292528`) | **1404 passed, 1 failed**, 9 skipped (the 101 new tests included; failure in §4.1) |
| Review regression | `python -B -m pytest -q -p no:cacheprovider test_multi_action_capabilities.py test_m33_p1_permission_seam.py tests/test_m37_edge_execution.py tests/test_m38_harness.py tests/governance/test_uri_state_validator.py` | 113 passed | 113 passed |
| Frozen anchors | `python scripts/m33_3_r_anchors.py` | ok, changed [] | ok, changed [] |
| M36/M37/M38 qualification | `python scripts/m3{6_memory,7_edge,8_harness}_qualification.py` | exit 0 each, gates passed | exit 0 each, gates passed |
| Governance | `python -B -m pytest -q -p no:cacheprovider tests/governance` and `python scripts/governance/uri_state_validator.py` | 37 passed, VALID | 37 passed, VALID |
| Slice tests | `python -B -m pytest -q -p no:cacheprovider tests/test_dynamic_planning_*.py` | n/a | 101 passed |
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

## 7. Next

§4.1 is decided (accepted failure). Next:

Step 5: a fresh independent audit that starts from repository evidence, reruns everything above, and adds adversarial probes beyond the battery. The slice stays PROVISIONAL / NOT FROZEN whatever the result. The slice now sits on the frozen line, so the migration-plan §1 rebase contingency is closed.

## 8. F2 repair: adapter identity binding (Chetan, 2026-09-29 13:49)

Audit finding F2 (Codex, confirmed in `docs/reviews/DYNAMIC_PLANNING_SLICE1_INDEPENDENT_AUDIT.md`): a caller could swap an injected adapter under the same `(action_id, version)`, and the swapped adapter could write outside the workspace while the run still reached `VERIFIED`. Chetan chose to close the path rather than accept it. Sections 1 to 7 above describe `3bbf8f7`/`c5d47a0` and are kept as they were.

**Mechanism** (new `uri_v1/execution/planning/qualification.py`; changes to `actions.py`, `runner.py`):
- Each record entry (schema `uri.plan.qualification.v2`) binds a capability to three things. The first is `adapter`, a stable identity `<module>:<qualname>`. The second is `implementation`, the LF-normalized SHA-256 of the adapter's module and of the modules it relies on (`planning.actions`, `planning.contracts`, `execution.officefile`). The third is `contract_shape_sha256`, the contract minus its display name and qualification field, so the version, mechanism, ports, literals, verifier coverage and declared effect are all bound in the same record.
- The record pin moved from `actions.py` to `qualification.py`, because the record now hashes `actions.py`.
- `PlanRunner` calls `check_adapter(contract, adapter)` before every node, after the existing CAPABILITY_CHANGED check. On any failure the node never runs, and the run stops as `NOT_ATTEMPTED ADAPTER_NOT_QUALIFIED`, with the typed detail in the outcome and in `RUN_ABORTED`. The check refuses the adapter unless all of these hold:
  - the adapter is a plain function;
  - its identity is in the record, qualified, under the same contract shape;
  - that name resolves to this exact object;
  - its code comes from that module's file;
  - every bound module still hashes to the recorded value;
  - the contract carries the current record digest.

  A missing record fails as `RECORD_MISSING`, an unpinned one as `RECORD_DIGEST_MISMATCH` and a malformed one as `RECORD_MALFORMED`.
- `default_catalog()` applies the same match at compile time, so a catalog built around a swapped function carries `UNQUALIFIED` and is rejected with `UNQUALIFIED_ACTION`.
- Renaming (C04) still verifies. Trust binds to the implementation and the contract shape; the action name is a label.

**Qualification record digest changed**: `98c1d78e…` (report §2) is now `b0dcf1ec54d7eb256038dd53d4efdaac874cdbc4622fb8167f8e504a4e190a7a`. Any later edit to `actions.py`, `contracts.py` or `officefile.py` makes the four actions UNQUALIFIED until the record is regenerated with `qualification.record_entry` and re-pinned. That is the intended requalification step. The battery (`2c366419…`), gate (`f2dfc937…`) and workbooks are unchanged.

**Driver changes** (`scripts/dynamic_planning_qualification.py`), needed because the old driver wrapped every adapter:
- The adapter-call recorder now uses a new observation-only `PlanRunner(observer=...)` hook, called with the node id just before the adapter runs, so the adapters stay unwrapped.
- In C26 to C29 a swapped writer would now be refused before it runs, and those cases would stop testing the oracle. So the tampering writers are named functions in the driver, qualified only by a throwaway per-case record (`tamper_record`). They model a qualified writer that misbehaves, which is the risk the oracle exists for. The production record never qualifies them. The literal "swapped writer" scenario is covered by the new tests.

**Tests**: new `tests/test_dynamic_planning_adapter_identity.py` (19 tests). It covers:
- a valid unchanged adapter;
- same id with different code: a closure, a look-alike with a copied `__module__`/`__qualname__`, a patched module attribute, a wrapper, a callable object, and a genuine adapter in the wrong slot;
- a changed implementation hash, a module source changed after qualification, and a record edited without re-pinning;
- a changed contract shape or effect;
- a missing record, and four malformed records that are still pinned;
- entries that are not qualified.

With the runtime check disabled, 13 of the 19 fail. Three existing tests changed to match: the forged writer is now refused at compile time, the undeclared-output test uses qualified buggy adapters, and the record-tamper test patches the record path in `qualification`.

**Results (Linux, Python 3.11.15)**:
- Full suite: 1424 passed, 1 failed (only the accepted §4.1 guard; its 18 disallowed paths are all slice paths, now including the new test file), 9 skipped.
- Slice tests: 122 passed.
- Qualification: 34/34, six counters at 0, C33 miss 1/1.
- Anchors ok; governance 37 + VALID; M36/M37/M38 quals exit 0; review set 113 passed.
- Audit probe F2: now `NOT_ATTEMPTED`, and no outside file was written.

**Residual limitations (narrower than F2, need containment beyond this slice):**
- **RL-1:** a *qualified* adapter's own code still runs unsandboxed. If qualified code writes outside the workspace, nothing here prevents or detects it. The shared retained limitation "no OS sandbox" (M36 to M38 freeze) covers this. Closing it needs OS-level containment. The binding makes sure only reviewed, hash-pinned code gets that trust.
- **RL-2:** a caller running code in the same process could still forge a function's code object in place (reassign `__code__` to one compiled with the same file name). Only interpreter-level isolation stops that. It needs deliberate code-object forgery, not a swap in the adapter map.

Still open from the audit, and not part of this repair: N1, N2 and F3 (typed outcome on unexpected exceptions), F1, N3, N4, D-7. The slice stays PROVISIONAL / NOT FROZEN.
