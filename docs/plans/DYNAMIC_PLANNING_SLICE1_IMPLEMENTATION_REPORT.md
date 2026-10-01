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
| `fixtures/dynamic_planning/capability_qualification.json` (pinned in `actions.py`) | `98c1d78e22138ce6f83c767f0524b4564f81658b3f99efda2bfaaa8b834e7c49` at freeze; **superseded in repair round 2 (§9) by `a91af8bb681e2a403990f43c558a087c35770e6dbb08e184b4014bfa7457431c`** (schema v2 adds each adapter's identity, implementation digest and boundary). This record is the capability qualification, not part of the battery or gate, whose digests are unchanged. |
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
14. **Adapter identity (audit F2): fixed in repair round 2 (§9); a narrower residual remains.** *History, kept:* at `458cbda` this item said the runner did not check the injected adapter's identity, so a swapped adapter under the same `(action_id, version)` could write outside the workspace and still verify, and it said "the audit recommends accepting it". **Correction (re-audit `1cab035`, R-3):** the audit listed both options (accept, or bind adapter identity) without recommending either; the recommendation to accept came from the coordinator. Chetan chose to bind identity (2026-09-29 13:49). Now every node's adapter must attest against the pinned record before it is called (§9), so a swapped, spoofed, code-swapped or helper-patched adapter is refused and cannot run or reach VERIFIED. **Correction (re-audit of `74474a2`, F2R-4):** that sentence was false at `74474a2`. An adapter rebuilt from the genuine code with private builtins or a private module reference (F2R-1), a replaced module global (F2R-2) and a patched method of a uri_v1 class (F2R-3) all passed attestation and reached VERIFIED. Repair round 3 (§10) closes those shapes. The bound that remains is §6.16.
15. **Plan re-derivation needs the pinned snapshot.** `PlanRunner.run` now takes the snapshot the plan was compiled against (`snapshot=`; `run_proposal` passes it). Without it, or with one whose hash differs from `plan.snapshot_sha256`, the run is refused as PLAN_NOT_COMPILED before anything is recorded.
16. **Outside-workspace effects of qualified code, and in-process tampering beyond attestation (narrower residual of F2; retained).** Attestation proves that the adapter is the qualified implementation. It does not contain what that implementation does. Not stopped (list made exact in repair round 3):
    - a qualified adapter's own writes outside the workspace;
    - process-wide patching of builtins, standard-library modules or `sys.modules` entries (for example `builtins.open`, confirmed by re-audit probe P5), including the `dataclasses` module used to re-derive generated methods;
    - C-level code;
    - editing both a source file and the record, then re-pinning the digest in `actions.py` (visible in git as re-qualification);
    - replacing `attestation.py`, the runner or `actions.QUALIFICATION_*` in the process;
    - effects of tampered module state on code that is not an adapter. Re-audit probe P3: a fake `hashlib` placed in `actions` is refused at the node, but it runs when `actions._qualified` hashes the record during planning.
    - any other in-process modification of URI's already-running code or state (module or class attributes, objects, interpreter internals) beyond the specific shapes attestation checks (§9, §10, §11). Attestation is not a containment boundary against a process that is already tampered with; containment is the effect guard or an OS sandbox. This ends the round-by-round chase of individual attribute kinds (re-audit of `06a920b`, I-4).

    All of these need an attacker who already controls the process. Preventing the outside write itself needs containment: an OS sandbox (the "no OS sandbox" limitation retained at the M36-M38 freeze) or the in-process effect guard prototyped in `docs/reviews/DYNAMIC_PLANNING_F2_TRUST_REVIEW.md` (audit hook; a material security choice awaiting Chetan). The guard would be a separate module wrapped around the adapter call and can be added or dropped without touching attestation.

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

## 9. Repair round 2: adapter identity binding (audit F2; Chetan 2026-09-29 13:49, option 2)

Chetan's decision: do not accept F2; bind qualification to a stable adapter identity and an implementation SHA-256, fail closed if the runtime adapter differs, check whether the declared boundary fits the same record, and record any outside-write containment need as a separate, narrower residual. All changes are in the slice's own files; no frozen file and no `verify.py` change (`git diff --name-status 5bbf738` is additions only).

**Mechanism.**
- `fixtures/dynamic_planning/capability_qualification.json` is now schema `uri.plan.qualification.v2`. Each capability carries `adapter {module, qualname, implementation_sha256}` and `boundary {effect, verifier_coverage, workspace_writes}`. Its digest is re-pinned in `actions.py` (§2).
- New `uri_v1/execution/planning/attestation.py`. `attest(adapter, contract)` returns `(None, digest)` only when all of these hold:
  - the record is present, matches its pinned digest and uses schema v2;
  - exactly one QUALIFIED entry names the adapter's `module:qualname`;
  - the implementation digest recomputed now equals the recorded one;
  - every function in the implementation runs the code compiled from its module file on disk;
  - the declared boundary equals the contract's mechanism, effect and verifier coverage, and a READ_ONLY entry declares no workspace writes while a writer declares only `plan_report.json`.
- **The implementation digest** covers:
  - the adapter's source;
  - every `uri_v1.*` function it reaches by global name, including the frozen `officefile` reader;
  - a fingerprint of every other global each of those functions uses: modules by name, classes by defining module and qualname, and constants by value.

  A global that resolves to a Python function outside `uri_v1.*` is refused, which covers a helper or a shadowed builtin swapped in at run time.
- **Runner.** Before each node, after the contract check, the runner calls `attest`. On any refusal the node is not called: the run aborts `ADAPTER_NOT_QUALIFIED`, and RUN_ABORTED's `detail` carries the refusal code. The attested digests are recorded per node in the RUN_RESULT executor claim (`adapters`).
- **Rename (C04).** Matching is by implementation, not by action name, so a renamed action over the same handler still attests.
- **Harness.** The qualification driver no longer wraps adapters, because wrapped adapters would now be refused. It observes adapter calls with `sys.setprofile`, independently of the runner's `executed` list. The tamper cases (C26-C29) corrupt the workspace the moment the genuine writer returns, and they are still caught by the verifier (`FAILED`). Tests that deliberately inject misbehaving adapters to exercise the runner's later defences now use an explicit `unattested` fixture.

**Adversarial tests** (`tests/test_dynamic_planning_attestation.py`, 21):
- **Valid unchanged adapter:** attests, verifies, and records its digests.
- **Same adapter id, different code:**
  - the audited F2 dict swap: refused before it runs, and no outside file is written;
  - a spoofed `module:qualname`: `IMPLEMENTATION_CHANGED`;
  - a `__code__` swap on the real function: `CODE_MISMATCH`;
  - a patched helper: `FOREIGN_FUNCTION`;
  - a patched constant: `IMPLEMENTATION_CHANGED`;
  - a shadowed builtin: `FOREIGN_FUNCTION`;
  - a replaced class: `FOREIGN_CLASS`;
  - a non-function callable: `NOT_A_FUNCTION`.
- **Changed hash:** a record hash that does not match the code gives `IMPLEMENTATION_CHANGED`; a record edited without re-pinning gives `RECORD_DIGEST`.
- **Missing record:** `RECORD_MISSING` at run time, with the node refused; before compile the contracts are UNQUALIFIED. A missing entry gives `NOT_IN_RECORD`.
- **Malformed record:** bad JSON, wrong top-level type, old schema, wrong `capabilities` type, missing `adapter`, short digest, or missing `workspace_writes` all give `RECORD_MALFORMED`; a duplicate entry gives `NOT_IN_RECORD`; a revoked status gives `NOT_QUALIFIED`.
- **Boundary:** a contract whose effect or coverage differs from the record, a READ_ONLY entry declaring writes, or a writer declaring a path other than the report all give `BOUNDARY_MISMATCH`.

**Boundary binding.** The declared boundary is bound into the same record and checked against the contract. Enforcement inside the workspace is still the verifier's `only_changed` check. Preventing writes *outside* the workspace needs containment, so it is recorded separately as the narrower residual §6.16, not used to leave identity unfixed.

**Re-audit nits folded in (re-audit `1cab035`).**
- R-1: the runner docstring no longer claims runs close on `KeyboardInterrupt`, `SystemExit` or `GeneratorExit`, or when the process is killed.
- R-3: §6.14 corrected; the recommendation to accept F2 came from the coordinator, not the auditor.

**Correction.** The F2 trust review commit `e69df0c` added evidence scripts under `docs/reviews/dynamic_planning_f2/` whose `.py` names broke the slice test `test_no_existing_module_imports_planning`. That commit was never run against the suite. They are renamed `*.py.txt` here, which the test does not scan.

**Checks at this head** (Linux, Python 3.11.15, all COMPLETED_WITH_RESULT):

| Check | Result |
|---|---|
| Full suite | **1439 passed, 1 failed** (only the accepted `test_m36_and_frozen_files_unchanged`, on slice paths), 9 skipped |
| Slice tests | 137 passed (116 + 21 attestation) |
| Slice qualification | exit 0: 34/34, counters 0/34, 0/34, 0/16, 0/16, 0/34, 0/34; C33 miss 1/1; C04 (renamed) VERIFIED; C26-C29 `FAILED` by the verifier; battery and gate digests unchanged |
| Audit probe script (repair-round-1 copy) | F2 now `NOT_ATTEMPTED`, outside file not written; N4 now refused by attestation (it injects a wrapped writer); all other probes as in §8 |
| Review regression set | 113 passed |
| Anchors / governance validator | ok, changed [] / VALID |
| M36, M37, M38 qualification | exit 0 each (rewritten result files reverted) |

Performance: attesting a node costs about 0.5 to 3 ms after the first call per module file (compiled modules are cached by file digest).


## 10. Repair round 3 (independent re-audit of `74474a2`, verdict REPAIRS_REQUIRED)

Re-audit report: `5eb0149` on `claude/project-thread-wjykgi`; copy at `/mnt/project-files/audits/dynamic_planning_slice1/CLAUDE_REAUDIT_74474a2.md`. All repairs are in `attestation.py`, plus the re-pinned record, tests and this report. No frozen file changed, and `verify.py` is unchanged.

| Finding | Repair | Regression test |
|---|---|---|
| F2R-1 (HIGH): the genuine code object with private builtins or private globals attests | Every function in the implementation must be its own module's function. Its `__globals__` must be that module's namespace, its `__builtins__` the real builtins, and the function must be found at its qualname in the module (through class dictionaries for methods). Otherwise `NOT_MODULE_FUNCTION`. | `test_genuine_code_with_private_builtins_is_refused_before_it_runs` (P1), `test_genuine_code_with_a_private_module_reference_is_refused` (P2); the spoofed-name test now expects `NOT_MODULE_FUNCTION` |
| F2R-2 (MED): a module global is fingerprinted by name only | A module global must be the `sys.modules` entry of its name, otherwise `FOREIGN_MODULE`. A builtin global must be its module's attribute, otherwise `FOREIGN_BUILTIN`. | `test_replaced_module_reference_in_the_real_module_is_refused` (P3) |
| F2R-3 (MED): methods of uri_v1 classes are not attested | **Closed, not documented** (coordinator default). Every uri_v1 class reached by the implementation joins it: the class source is added to the digest; methods defined in the class source are attested like functions (source digest, code check, home check); and a class must be its module's attribute with only uri_v1 or builtin bases and the plain metaclass. Methods a dataclass generated at import (no source file) are compared against the methods `dataclasses` generates now, from the field names, literal defaults and decorator arguments parsed from the class source with `ast` (nothing is executed). They must match in code, globals, builtins, defaults and closure; default factories are refused. Anything else gives `GENERATED_MISMATCH`. About 110 lines, all in `attestation.py`. | `test_patched_methods_of_uri_classes_are_refused` (P4: generated `__init__` replaced, source method replaced, method added, dataclass params changed, exception class given a method), `test_classes_and_their_methods_are_part_of_the_digest` <br>**Correction (re-audit of `06a920b`, R3-1):** "Closed" was false at `06a920b`. Only function-like class members were checked, so a non-function descriptor placed on `WorkbookStructure.sheets` attested, the run reached VERIFIED and it wrote outside the workspace (probe Q1). Repair round 4 (§11) closes that shape. |
| F2R-4 (LOW): report overclaims | §6.14 correction added (history kept); §6.16 now lists the remaining bound exactly. | n/a |
| F2R-5 (LOW, latent): unknown objects fingerprinted by type | Refused as `FOREIGN_OBJECT`. | `test_unknown_object_globals_are_refused_not_typed` |

The record digest is re-pinned to `9975a268c1301e01ec87430d1c2d632088460f71c29bb8465ff166b0d5dd553b`. The three digests that include classes (`inspect_structure`, `select`, `compare`) changed; `write_report` did not.

**The auditor's own probe script** was rerun against this head (`probes.py.txt`, run from `tests/` in a scratch copy and then removed):
- P1 and P2 are `NOT_MODULE_FUNCTION`, P3 is `FOREIGN_MODULE`, P4 is `GENERATED_MISMATCH`. All four runs are NOT_ATTEMPTED, and the adapter wrote nothing outside the workspace. For P3, the fake module still writes when it is called while the plan compiles; §6.16 records this.
- P5 still verifies with an outside write. It is process-wide builtin patching, which §6.16 lists.
- P6, P7, P9, P10 and P11 are refused as before. P8 (an unmodified copy of the globals) is now refused, which is harmless. P12 is unchanged, and P13 reproduces the new digests in a fresh interpreter.

**Checks at this head** (Linux, Python 3.11.15, all COMPLETED_WITH_RESULT):

| Check | Result |
|---|---|
| Full suite | **1445 passed, 1 failed** (only the accepted `test_m36_and_frozen_files_unchanged`), 9 skipped |
| Slice tests | 143 passed (137 + 6) |
| Slice qualification | exit 0: 34/34, counters 0/34, 0/34, 0/16, 0/16, 0/34, 0/34; C33 miss 1/1; battery and gate digests unchanged |
| Review regression set | 113 passed |
| Anchors / governance validator | ok, changed [] / VALID |
| M36, M37, M38 qualification | exit 0 each (rewritten result files reverted) |

**Unverified:** Windows and other CPython versions were not run. Code-object comparison and dataclass-generated code are specific to the interpreter; a mismatch there fails closed (no run) and is never a false VERIFIED. The record digests are source-based and do not depend on the interpreter version. **Correction (re-audit of `06a920b`, I-3):** mostly; the `repr` of a compiled `re.Pattern` global is part of a digest and could differ across CPython versions. Such a difference fails closed.

## 11. Repair round 4 (independent re-audit of `06a920b`, verdict REPAIRS_REQUIRED)

Re-audit report: `d3d26de` on `claude/project-thread-wjykgi`; copy at `/mnt/project-files/audits/dynamic_planning_slice1/CLAUDE_REAUDIT_06a920b.md`. All code changes are in `attestation.py` (the auditor's prototype for R3-1, plus the two optional latent items, which were small). No frozen file changed, `verify.py` is unchanged, and the record and its digest are unchanged (no current digest moved).

| Finding | Repair | Regression test |
|---|---|---|
| R3-1 (MED): a non-function descriptor on a uri_v1 class escapes class attestation | Every member of a uri_v1 class in the implementation must be function-like (attested as before), class or dataclass machinery of the expected type (`__module__`, `__doc__`, `__annotations__`, `__match_args__`, `__dataclass_params__` from `dataclasses`, `__dataclass_fields__`, `__hash__ = None`, the `__dict__`/`__weakref__` getset descriptors), or a plain value. Anything else gives `FOREIGN_MEMBER`. | `test_hook_object_on_a_uri_class_is_refused` (Q1 through the real runner: NOT_ATTEMPTED, detail `FOREIGN_MEMBER`, nothing written outside), `test_callable_object_replacing_a_method_is_refused` (Q2, now refused by rule) |
| R3-2 (LOW, latent): default argument values not attested | When a function has `__defaults__` or `__kwdefaults__`, their fingerprints join its digest part (absent, the part is unchanged, so existing digests hold). | `test_injected_default_arguments_change_the_digest` (Q5 gives `IMPLEMENTATION_CHANGED`) |
| R3-3 (LOW, latent): uri_v1 code reached through a module global is not hashed | A uri_v1 module used as a global is refused (`FOREIGN_MODULE`), so uri_v1 code is reached only by direct import and is always in the closure. | `test_uri_module_as_a_global_is_refused` |
| I-4 (recommendation) | §6.16 now says any other in-process modification of URI's running code or state is outside attestation; containment is the effect guard or an OS sandbox. | n/a |
| §10 "Closed" claim for F2R-3 | Corrected in place with the history kept. | n/a |

All four new tests fail on `06a920b` and pass at this head (checked by running them against the `06a920b` `attestation.py`).

**Checks at this head** (Linux, Python 3.11.15, all COMPLETED_WITH_RESULT):

| Check | Result |
|---|---|
| Full suite | **1449 passed, 1 failed** (only the accepted `test_m36_and_frozen_files_unchanged`, offenders all dynamic-planning paths), 9 skipped |
| Slice tests | 147 passed (143 + 4) |
| Slice qualification | exit 0: 34/34, counters 0/34, 0/34, 0/16, 0/16, 0/34, 0/34; C33 miss 1/1; gate passed; battery and gate digests unchanged |
| Review regression set | 113 passed |
| Anchors / governance validator | ok, changed [] / VALID |
| M36, M37, M38 qualification | exit 0 each (rewritten result files reverted) |

**Unverified:** Windows and other CPython versions, as in §10. The auditor's full probe script was not rerun here; the Q1, Q2 and Q5 shapes are covered by the new tests.

**Boundary test on Windows (coordinator, 15:42).** The integration readiness audit on Chetan's Windows PC reported that the branch tip failed "its own boundary test" (tip then `74474a2` or `06a920b`; that evidence is on Chetan's PC and was not seen here). Of the seven tests in `tests/test_dynamic_planning_boundaries.py`, only `test_no_existing_module_imports_planning` depends on the checkout: it walked every `.py` file under the repository root, tracked or not, so any untracked local file that mentions `execution.planning` (a scratch probe, a tool's output, a virtualenv not named `venv`/`.venv`) fails it, and an unreadable directory makes `rglob` raise. The other six read only the slice's own files and normalize CRLF. The test now scans `git ls-files` (falling back to `rglob` without git). Reproduced here: an untracked `tests/zz_untracked_probe.py` importing the planning package failed the old test and passes the new one. *Inferred, not verified:* that this is the failure the Windows audit saw.

**Python 3.13 test fix (readiness audit on Chetan's Windows PC, Python 3.13, against `28fcbf9`; relayed 2026-10-01).** `test_patched_methods_of_uri_classes_are_refused` built a `_DataclassParams` with the 3.11 constructor (6 arguments; 3.12+ needs 10), so it raised `TypeError` there (slice 146/147). Test-only: the test now copies the class's params and drops `frozen`. No attestation code changed. Reproduced and fixed here with Python 3.13: slice 147 passed and qualification 34/34 with counters 0 on 3.13. On 3.11 the slice is 147 passed and the full suite is 1449 passed / 1 failed (the accepted guard only). Windows itself was not run here.

## 12. Package move to `uri_v1/planning/` (Chetan, 2026-10-01 12:23, "Move, then freeze")

**Why.** The M37-L3 guard fix (`9395677` on `claude/project-thread-hrkr7o`) pins `uri_v1/execution/` to the M36-M38 freeze commit. With that fix, the 9 planning code files under `uri_v1/execution/planning/` were flagged as changes in frozen territory. Chetan chose to move them out, so the frozen `uri_v1/execution/` package holds only frozen code. The move does not shrink the guard failure: the files are now flagged as outside the M37/M38 scope instead, and the count stays at 27 paths, all slice paths.

**What changed.** Only the following; there is no logic change.
- The 9 files moved from `uri_v1/execution/planning/` to `uri_v1/planning/` (`git mv`; file contents are identical apart from the two lines below).
- `actions.QUALIFICATION_PATH` now goes up `parents[2]` instead of `parents[3]`, for the shallower location.
- Imports in the 7 slice test files and the qualification script now use `uri_v1.planning`.
- `test_dynamic_planning_boundaries.py` now uses the new package path, allowed prefix and forbidden import text (`uri_v1.planning`, `uri_v1 import planning`).
- The qualification record's adapter `module` fields and binding note now name `uri_v1.planning.*`.
- The implementation digests include the module name, so all four changed. They were recomputed:
  - `inspect_structure` `505dff2c…`;
  - `select` `02152cdc…`;
  - `compare` `944ac6d0…`;
  - `write_report` `8ff6aca1…`.
- The record digest is re-pinned in `actions.py` to `9998e2b238c2837d206e0505c77191d56391c7646ae37534f1da087c74fd2a26`. That is a re-qualification.
- The battery and gate digests are unchanged, because neither contains module paths.
- The migration plan and canonical architecture each gained a one-line note about the new location. Their planned paths are kept as history.

Every path `uri_v1/execution/planning/…` in §1-§11 of this report and in `docs/reviews/` now refers to `uri_v1/planning/…`. That earlier text is kept as written.

**Checks at this head** (Linux, all COMPLETED_WITH_RESULT):

| Check | Result |
|---|---|
| Full suite (Python 3.11.15) | 1449 passed, 1 failed (only the accepted `test_m36_and_frozen_files_unchanged`), 9 skipped |
| Guard offenders, recomputed with the current guard and with the `9395677` logic | 27 under each; all are `uri_v1/planning/`, `tests/test_dynamic_planning_*`, `scripts/dynamic_planning_*` or `fixtures/dynamic_planning/`; none is in `uri_v1/execution/` |
| Slice tests | 147 passed on Python 3.11 and on Python 3.13 |
| Slice qualification (Python 3.11) | exit 0: 34/34; all six counters 0; C33 semantic miss 1/1; gate passed; the results file differs only in latency |
| Review regression set | 113 passed |
| Anchors / governance | ok, changed [] / VALID, 37 passed |
| M36, M37, M38 qualification | exit 0 each (rewritten result files reverted) |

**Not run at this head:** Windows. The Windows Python 3.13 run (slice 147/147, qualification 34/34) was at `b6b2cb0`, before the move.
