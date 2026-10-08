# Independent canonical implementation review: experimental dynamic planning

Date: 2026-09-28. Reviewed checkout: `62d564cf9d2fa25e5a9860d20dcc7070b112badb` plus the existing untracked experimental files. Reviewer: independent Codex session. Scope: source inspection, retained-evidence recomputation, fresh offline adversarial probes, and focused existing regression tests. No production implementation, milestone promotion, freeze, commit, or push.

## 1. Verdict

**NEEDS_ARCHITECTURE_REWORK.**

The intended architecture is compatible with ADR-018 when semantic planning remains a model proposal and URI deterministically compiles, validates, binds, executes, and verifies that proposal. Neither experimental planner implements that architecture. The replacement `ContractDrivenPlanner` retains benchmark strings, tool-name switches, fixed operation ordering, and synthetic partial escalation. Its runner supplies the semantics and arguments through hard-coded branches while discarding the Granite response.

The reported 18/18 result is reproducible as a permissive **tool-set/decision classification score**, not as verified task completion. Ten steps were invoked in one retained case; correct ten-step dataflow or output was not independently established. `FALSE_VERIFIED_COMMIT = 0` is an essential acceptance requirement, but these experiments do not establish it.

Accept the engineering hypotheses—contract-based composition, typed dataflow, runtime-owned handles, bounded continuation, and isolated unresolved work—for design. Reject promotion of either planner, their execution engines, or their commit scorers. Granite remains a promising experimentally exercised bounded worker, not a canonically qualified general planner. Needle remains an optional qualified specialist within its independently demonstrated envelope.

## 2. Authority and review limits

The governing basis is ADR-018, the AI Operating Policy, Model ↔ Runtime Contract, M22 architecture, the tracker/memory, ORCHESTRATION, the four-stage lifecycle, `docs/governance/URI_ACTIVE_MILESTONE.md`, and the machine authority `docs/governance/URI_STATE.yaml`.

- M36/M37/M38 remain provisional and unfrozen. Their implementation permissions are milestone-specific, not permission for this new planner or production integration. All three machine records have `integration_authorized: false`.
- The additive batch audit at `833d6ed` with repairs at `379769f` accepts M36/M37 with limitations for presentation to a freeze decision. M38 still needs fresh subscription-backed Windows live qualification. This review does not reopen their completed audit or substitute new closure evidence.
- The machine file retains older audit/dependency descriptions alongside the newer narrative batch audit. This is a documentary reconciliation issue, not authorization to change milestone states here.
- M33.3 is frozen within its offline/fixture scope; S9 learning remains deferred; S13 requires a future INT-* integration authorization. ARN.1 is closed; ARN.2 is not authorized. Frozen RAR/ARN/M33.x artifacts must remain unchanged.
- `uri_v1` must not import `uri_core`. Direct cross-generation reuse is therefore not interchangeable with reuse of a design or a later adapter.

Graphify oriented the inspection toward existing registries, dispatch, workflow recovery, RAR, and verification. Its broad/truncated graph results are navigation evidence only; findings below come from current source. The experiments are untracked, so their content hashes, not HEAD alone, identify the reviewed candidate; see [the companion evidence JSON](DYNAMIC_PLANNING_CANONICAL_REVIEW_EVIDENCE.json). No live model benchmark or personal-account operation was run. Retained telemetry cannot independently establish the identity/configuration of the live models that originally produced it.

## 3. Material findings

| ID | Severity | Evidence and consequence | Required disposition |
|---|---|---|---|
| F1 | High | `contract_driven_planner.py:20` names `equipment_rentals_q3.xlsx`, `commercial_procurement_fy26.xlsx`, specific tables and `vendor_master`. `plan():212` treats `2022`/`supplier_bids_2022` as missing data; discretionary phrases are also named. A prompt mentioning a year is not source-availability evidence. | Remove semantic regex/template planning from the canonical path; use grounded model proposals and actual source/registry evidence. |
| F2 | High | `_build_contract_map():125` assigns categories mainly by exact tool name. It reads parameter properties but does not use them, stores required parameter names as `consumes`, never uses those for planning, and reads no output contracts. The alternate names `remove_duplicates`/`combine_tables` are explicitly recognized. | Require declared, versioned input/output semantics and validate compatibility; never infer executability from spelling. |
| F3 | High | `plan():277` sorts a fixed `tool_tier_order`, then assigns every node the preceding node as its sole dependency. Tools are deduplicated by name, suppressing repeated reads or multiple applications of the same transform. | Compile edges from explicit typed bindings; allow repeated action instances, multiple producers, branches and joins; reject cycles/missing producers. |
| F4 | High | Registry maps are cached in `__init__():120`. Removing `join_tables` from the same supplied list after initialization still emits it. Arbitrarily renaming `read_table` to `load_dataset` while preserving its description/schema causes escalation. The runner reconstructs the planner per fixture, hiding the first defect. | Pin an immutable registry snapshot for each plan; revalidate live capability/version/qualification/permissions before each node. Invalidate the unfinished remainder on change. |
| F5 | Critical | `adversarial_runner.py:274` makes an HTTP call but never parses/uses its response and ignores transport failure. Lines 289–389 inject filename, dates, identifier, keys, filters, equations and draft content. Joins/comparisons invoke extra reads outside the plan; the adversarial sheet reader at line 93 fabricates HEAVY/450 cells when lookup fails. | No completion after absent/invalid grounding; no runner-supplied business arguments or undeclared calls. Evaluate the actual model proposal and complete execution trace. |
| F6 | Critical | Adversarial plan scoring at line 233 uses expected-tool subset inclusion. Execution statuses are logged but do not gate continuation/COMMIT (391–416). `false_verified_commits` starts at zero and is never incremented. Original `benchmark_runner.py:471` increments argument accuracy unconditionally on admitted execution. | Independent output oracle and runtime acceptance receipt must govern completion; derive counters from observed violations. Reject extra unauthorized steps and mismatched arguments/dataflow. |
| F7 | Critical | `RepairedURIVerifier.verify():439` checks first-tool name/expected arguments, then returns COMMIT without checking execution result. The two-step branch at 490 checks names/order, not results or semantic outputs. Fresh injection of `status: error, error: permission_denied` returned COMMIT and `false_verified_commit: false`. | Retire this scorer as a verification authority. Production must use registered trusted verifier evidence, not matching proposal shape. |
| F8 | High | Replacement partial detection at line 232 uses `UNKNOWN/UNREGISTERED/ANOMALY` strings or the word `isolate`, with fabricated `unregistered_record` fallback. Runner lines 323/406 use fixture `is_partial` and `partial_target`, filter by `rate_code: HEAVY`, and assert the cohort was committed without partition verification. | Partition from validated records and uncertainty evidence; prove disjointness, coverage and independence; no partial mutation in the first slice. |
| F9 | High | Adversarial Needle gate defaults missing output to CAN_DO and overrides with keyword tripwires. Repaired gate at `granite_repaired_orchestration_runner.py:159` reconciles refusals via reason strings and defaults malformed/missing output to CAN_DO. Retained ADV_P02/P03 have planner CAN_DO but final COMMIT_ESCALATE; perfect planner decision score does not measure final system correctness. | Schema-validate advisory specialist output, record raw versus reconciled proposals separately, and measure final route. Execution authority stays in runtime gates. |
| F10 | High | Repaired orchestration lines 270–280 inject `file_orders_xls`, `Orders`, `pending`, `West`; lines 311–332 overwrite later targets with the most recent file/first search hit. Pilot similarly overwrites `file_id` (`pilot_runner.py:209`). | Bind only explicitly named producer ports; a latest-handle slot cannot safely represent multiple files or references. Never silently correct a model target to another file. |
| F11 | High | Pilot `real_tool_executor.py:191` accepts any existing filesystem path as a handle. It has hard-coded real files and a fixed legacy workstation path (26–37). `read_sheet_range():345` chooses a fuzzy sheet and substitutes five rows after invalid range parsing. Integrity checks at 181 miss deletion because an empty current hash is excluded. Pilot COMMIT at `pilot_runner.py:339` is based on expected tool names; its false-commit summary is literal zero. | Recover library techniques only. Enforce user/task-scoped SourceRegistry handles and exact ranges, reject missing/ambiguous references, and use workspace/hash verification. |
| F12 | Medium | Expanded engine defaults missing handles to empty tables, missing columns to omitted values, unsupported aggregate operations to sum (`expanded_tool_registry.py:607`). Restricted-character `eval` at 603 is not unrestricted code injection, but permits expensive powers and unbounded expressions; float aggregation lacks an explicit money/rounding policy. | Typed failure for invalid handles/schema/operations; bounded arithmetic interpreter and explicit units, precision, rounding and date semantics. |

The label `DETERMINISTIC_CORE` in the replacement is assigned to every selected tool except the name `extract_fields`; that name is not recognized by its contract map. `create_output_draft` is labeled deterministic even though substantive drafting is semantic. Deterministic formatting of verified fields is valid; creating a recommendation or interpreting policy is not made deterministic by naming the tool a draft writer.

## 4. Fresh evidence and score interpretation

Offline probes executed against the reviewed source produced:

| Probe | Actual result |
|---|---|
| Unsupported weather request | CAN_DO, empty tools and plan |
| “Do not delete anything; read records from the table” | ESCALATE based on `delete` |
| Read records from 2022 | ESCALATE without storage lookup |
| Sort then deduplicate versus deduplicate then sort | Identical fixed read → dedupe → sort plan |
| Read a table twice and join | Only one read node |
| Compatible arbitrary rename of read_table | ESCALATE |
| Remove join_tables after planner construction | Still selects join_tables |
| Deduplicate nonexistent handle | `status: ok`, empty table |
| Failed tool result sent to repaired verifier | COMMIT, correct=True, false_verified_commit=False |

Recomputing the retained adversarial classification yields 18/18 with the runner's subset metric. Exact tool-set equality yields 14/18; the differences are extra aggregate, dedupe, or interval operations. Exact equality alone is also insufficient—some extra steps may be legitimate—but any such steps need declared semantics, authorization and a complete oracle. Neither score proves correct arguments, order or output. The telemetry also records two positive paraphrase cases ending in escalation despite correct planner classification.

Existing regression command:

```text
python -B -m pytest -q -p no:cacheprovider test_multi_action_capabilities.py test_m33_p1_permission_seam.py tests/test_m37_edge_execution.py tests/test_m38_harness.py tests/governance/test_uri_state_validator.py
```

Result: **107 passed in 34.63 seconds**. This supports reuse of those existing seams; it does not qualify the proposed planner or satisfy live acceptance. No broad baseline audit was repeated.

## 5. Answers to the requested audit questions

| # | Answer |
|---|---|
| 1 | No. The replacement derives a tool subset from regex categories, not a semantic plan from complete I/O contracts. |
| 2 | Yes: domain filenames/tables/year tripwires, recognized alternate tool names, runner constants and fallback targets remain. |
| 3 | Partly at construction; not robustly runtime-aware. Mutation cases rebuild the object and cover only a recognized rename and removed join. |
| 4 | No. Fixed rank sorting plus a predecessor chain replaces actual producer/consumer construction. |
| 5 | The intended split is sound; implementation conflates deterministic transforms with semantic planning/drafting and substitutes runner semantics for model semantics. |
| 6 | Experimental executors own handle dictionaries, but scopes, explicit ports and provenance are inadequate. Canonical Workspace/SourceRegistry/RunStore are the correct ownership basis. |
| 7 | Only as one validated semantic proposal permitting bounded continuation under repeated runtime gates; a model decision grants no authority. New evidence/ambiguity stops affected continuation. |
| 8 | No in the experiments. Yes as an existing architectural mechanism in v1 Recorder + registered verifier + lineage, subject to task-specific acceptance strength. |
| 9 | Not proven. Formalize independent verified artifacts first; defer irreversible partial commit and shared aggregate mutations. |
| 10 | Optional role-specific advisory use, qualification- and cost-gated. Never a universal mandatory hop or safety authority. |
| 11 | Discovery, schema declarations, heterogeneous dispatch, `$from` references, workflow dependency/recovery checks, scoped sources, claim/verifier lineage and copy-in/out already exist. See reuse map. |
| 12 | Recover pure execution/library adapters and existing dispatch/recovery patterns; reject legacy workflow templates as the planner. Respect the no-uri_core-import boundary. |
| 13 | Both experimental planners/runners, general Granite planner qualification, expanded transform engine, model-name-specific routing, and automatic partial commits remain experimental. |
| 14 | Isolated v1 typed contract compiler/binder with one read-only multi-source reporting composition and independent recomputation; no production wiring. |
| 15 | All qualification gates in section 10, followed by separately authorized canonical-loop and live tests before claiming integration completion or freeze. |

## 6. Canonical target architecture

The configurable Main Brain or a separately qualified bounded specialist interprets the user goal and proposes transformations, typed literals, explicit source references, desired outputs and constraints. This semantic proposal is untrusted. A **ContractDrivenPlanner** is preferably a deterministic compiler of that proposal, not Python intent inference.

```text
Trusted user/context + current capability snapshot
  → configured semantic provider: transformation/grounding proposal
  → contract compiler: compatible action instances + explicit bindings
  → runtime validation: DAG, sources, schemas, authority, resource limits
  → bounded deterministic execution with per-node live revalidation
  → executor claims + URI-observed outputs
  → registered independent verifier
  → completion decision + grounded result feedback
```

`CapabilityContract` is a read-only projection of the authoritative descriptor/action declaration, not a second mutable tool registry. It supplies capability/action identity, version, qualification identity, input/output port types, effect/approval/permission metadata, limitations, deterministic versus semantic mechanism and verifier coverage. Schemas alone cannot determine what the user means or select among two semantically different compatible transformations. Unknown metadata prevents composition rather than triggering guessed defaults.

`PlanNode` represents an action **instance**, so one action can occur several times. `ExecutionDAG` stores explicit producer/output-port → consumer/input-port bindings, plus necessary ordering constraints from the proposed semantics. Matching JSON primitive types is not enough: table schema, row-set lineage, key space, units, cardinality and scope matter. Sorting and deduplication do not commute by default. Compiler validation includes unique node IDs, existing ports, compatible types, complete required inputs, acyclicity, node/edge limits and approved mechanism coverage.

`RuntimeBinding`/`HandleBinding` names a runtime-owned object scoped to user, task, run, producer and output port, with source/result version hashes. Models may reference permitted symbolic ports, never create arbitrary paths or handles. The executor issues handles only from successful schema-validated results. There is no implicit “latest file/table” replacement or first-match binding.

`DeterministicExecutionEngine` is a composition controller over existing approved execution boundaries, not an alternative tool dispatcher. Sequential topological execution is sufficient initially; parallel scheduling is unnecessary. A failed node halts its descendants. Registry/version/qualification changes invalidate unfinished affected nodes and require a fresh proposal/compile where needed. Completed effects are preserved; unknown outcomes never retry automatically.

`VerificationResult` carries verifier identity/version, acceptance hash, input/output hashes, node/partition coverage, evidence references and status. Reuse the existing v1 lineage status/result wherever possible. `CommitDecision` consumes trusted verification and authority evidence, never model `CAN_DO` or textual claims. Separate artifact completion, persistence, write-back and external side effects. A verifier must independently recompute the intended result; a hash authenticates criteria but cannot make weak criteria adequate.

URI Core in the user's conceptual ownership list means runtime responsibility. It does not require moving v1 execution code into the existing `uri_core` package. Preserve OD-5 placement under `uri_v1/execution/` and the generation boundary.

## 7. Reuse map and experimental disposition

| Mechanism | Existing source | Treatment |
|---|---|---|
| Brain-facing authoritative catalogue | `uri_core/core/capability_directory.py`; `core/tool_schema.py` | Future production adapter projects the same per-turn directory; do not create another curated catalogue or build it twice. Not directly imported into v1. |
| Rich action contract | `uri_core/capabilities/base.py` Action/ActionSchema; `capabilities/registry.py` | Reuse existing parameters, returns, effects, permissions, approvals and wrong-binding concepts. Direct reuse in legacy integration only; v1 gets a typed projection/adapter at the future seam. Existing ActionSchema is not a full nested dataflow/output verifier. |
| Qualified local availability | `uri_v1/edge/registry.py` | Reuse its exact-version/hash qualification discipline and current inspector descriptor. Its closed TaskClass registry is not already a generic transform catalogue. Do not widen M37 silently or set qualification_run in ordinary execution. |
| Real action execution and `$from` | `uri_core/capabilities/executor.py`; `core/multi_action_dispatch.py` | Existing principal/action permissions and chain references are valuable. `$from` returns None for missing paths and execute_chain is a sequential controller, not a validated DAG engine. Future adapter must validate before handing it a chain. |
| Canonical proposal/gates/result feedback | `uri_core/core/decision_engine.py`, `decision_gates.py`, `canonical_execution.py` | Preserve the current production path. The canonical chain projection currently drops explicit node IDs (canonical_execution.py:264); dependency fields need an accepted additive contract before production use. |
| Scoped source identities and copy-in/out | `uri_v1/memory/sources.py`; `execution/workspace.py` | Direct v1 reuse, hash recheck, confinement and source freshness. Explicit WritebackApproval stays separate. |
| Claims, independent verification, results | `uri_v1/memory/recorder.py`; `execution/lineage.py`, `verify.py`, `acceptance.py`, `run_record.py`; `results/version_ledger.py` | Direct reuse, as-is. Reuse report_recomputes with a trusted injected recomputation callback. Do not auto-promote executor observations to VERIFIED. Frozen S11 store consumed unchanged. |
| Workbook structural inspection | `uri_v1/execution/officefile.py` | Direct reuse within its bounds. It reads names/headers/error cells, not general cell values or business calculations. |
| Dependency validation and resumption | `uri_core/core/workflow_recovery.py`; `workflow_executor.py` | Recover design and regression cases for missing edges/cycles, durable status and skip-completed effects. No direct import into v1; eventual legacy adapter may reuse them. |
| Binding, clarification, narrowing | frozen RAR contracts; `uri_v1/reference_clarification/`; ARN.1 | Consume unchanged through future approved interfaces. D3/D5 certainty and wrong-binding rules remain authoritative; semantic preference never binds. No ARN.2 or learned weights. |
| Specialist routing and residency | `uri_core/core/edge/routing_policy.py`, `runtime_inventory.py`, `lease_ownership.py`; provider/model routing | Preserve D2 modes, explicit selected Brain, Edge OFF and native model capabilities. Read/reuse interfaces after authorized integration; do not alter frozen S6. |
| External harness | `uri_v1/execution/harness/` | Reuse capsule/claims/verification posture when the task fits the existing supported envelope and caller authorizes it. Current capsules map closed workbook task classes to goals; arbitrary DAG escalation is not already supported. M38 remains provisional/live-unqualified as documented. |
| Legacy file/spreadsheet/document primitives | FileStore; read_attached_file; document/Drive adapters; openpyxl/pathlib/hashlib techniques used in pilot | Recover exact bounded adapters after source/path/permission review. Pilot imports libraries; this alone is not proof it reuses canonical adapter authority. No workstation-specific mappings. |
| Legacy WorkflowPlanner | `uri_core/core/workflow_planner.py` | Preserve for compatibility; its template routes must not become the generic planner. |

Accepted as design evidence: typed capability composition, runtime state piping, reducing redundant prose-only model turns, independent verification, scoped unresolved work, and compact model shortlists. Rejected as production mechanisms: either experimental planner; keyword authority gates; synthetic benchmark arguments; latest-handle overwrites; permissive scorers; original transform engine; fixed model tiers. Keep retained telemetry immutable as historical evidence with this review qualifying its interpretation.

## 8. Minimal implementation slice and exact proposed files

**First slice: isolated, independently recomputed workbook-structure reporting from two hash-bound inputs.** A configurable semantic provider proposes which named sheets/headers to include or compare. Runtime reads both workbooks using the existing bounded inspector, binds each branch independently, joins only the specified structural facts, and writes a new report in scratch. The verifier rereads original hash-bound inputs and recomputes the report. This tests repeated action instances, branching, joins, semantic grounding, opaque bindings and result evidence without implementing accounting, arbitrary spreadsheet cells, mutating originals or a general transform library.

Qualification also exercises an equivalent registry rename, removed/changed capability, reordered operations and a genuinely unsupported goal. Neither worker nor runner receives expected answers. Test doubles establish compiler behavior only; actual model proposals establish semantic qualification separately.

Proposed **new files**, subject to Stage 2/3 review; no file is created here except this review and its evidence JSON:

```text
docs/architecture/DYNAMIC_PLANNING_CANONICAL_ARCHITECTURE.md
docs/plans/DYNAMIC_PLANNING_MIGRATION_PLAN.md
uri_v1/execution/planning/__init__.py
uri_v1/execution/planning/contracts.py        # nodes, ports, snapshot projection, partial artifact
uri_v1/execution/planning/compiler.py         # semantic-proposal → validated DAG
uri_v1/execution/planning/bindings.py         # scoped runtime values, no path fallback
uri_v1/execution/planning/runner.py           # bounded execution through injected approved adapters
uri_v1/execution/planning/structure_report.py # inspector adapter + independent report recomputation
uri_v1/execution/planning/provider_port.py    # configurable untrusted proposal interface
tests/test_dynamic_planning_contracts.py
tests/test_dynamic_planning_compiler.py
tests/test_dynamic_planning_bindings.py
tests/test_dynamic_planning_execution.py
tests/test_dynamic_planning_verification.py
fixtures/dynamic_planning/qualification_cases.json
fixtures/dynamic_planning/threshold_gate.json
scripts/dynamic_planning_qualification.py
```

Existing v1 workspace, acceptance, verifier, recorder, results and M37 modules should be **consumed unchanged**. The new snapshot projection contains composition metadata for actual approved handlers; it owns neither installation nor execution authority. No general-purpose registry fork. If implementation discovers that unchanged interfaces cannot satisfy this bounded task, amend the plan before editing them.

**Later production integration, separately authorized and qualified:** expected code edits are `uri_core/core/decision_engine.py`, `decision_gates.py`, `canonical_execution.py`, `multi_action_dispatch.py`, `uri_core/capabilities/executor.py` and `uri_core/core/tool_schema.py`, with a new `uri_core/core/planning_adapter.py` and corresponding integration tests. Restrict those edits to validated DAG projection, preserved IDs/ports, per-node gates and evidence feedback through the established dispatcher. Use provider/model routing already in place. An accepted adapter can call the v1 service without v1 importing uri_core. No edits to frozen RAR/ARN/S6/S11, `orchestrator.py`, server routes or UI are expected for the first slice. Final production file scope must be confirmed by its Stage 2/3 plan rather than assumed from this list.

Governance/tracker/memory state updates belong to the later accepted implementation or integration transition. Do not invent a milestone number or INT event in this review.

## 9. Partial escalation and Needle recommendations

`PartialEscalationArtifact` should extend the **concept** of existing EscalationRequest; do not force arbitrary partitions into its closed M37 task enum or expand M38 capsules implicitly. Carry:

- user/task/run/trace identity; goal/proposal/registry/acceptance versions and hashes;
- input source identities and hashes; explicit partition keys and membership digests;
- completed node/result versions and verifier receipt IDs;
- unresolved members/nodes, typed reasons, minimal needed context and relevant confirmed findings;
- dependency closure, blocked consumers and the reason independence is established;
- separately approved effect scope, performed effects/unknown outcomes, idempotency keys and resume checkpoint;
- requested provider role and applicable policy, without a fixed model name.

Prove `completed ∩ unresolved = ∅` and full accounting of the requested input population. Verify each completed partition against predeclared acceptance. Exclude descendants of unresolved nodes; aggregates requiring unresolved rows cannot be presented as complete totals. Cross-record constraints, transactions and shared writes invalidate naive independence. The whole task remains PARTIAL while unresolved work exists. First slice permits independent read-only findings and scratch artifacts only. Later partial external/local authoritative writes need a separate approved transactional/idempotency design. No broad user approval may be inferred from a model decision.

Needle can advise tool ranking, ambiguity flags, eligibility reasoning, constraint interpretation or specialist output quality where that role has evidence. It cannot authorize, confirm bindings, certify results or disable runtime gates. Start the first slice with Needle bypassed by default. Compare deterministic-only shortlist, semantic provider alone, Needle pre-check, and selective Needle post-check on the same blinded cases, including malformed outputs and false-negative refusals. Record raw proposals, runtime reconciliation reasons, cold/warm load, p50/p95 end-to-end latency, calls, tokens and final error rates. Add a hop only when its measured error/cost reduction outweighs its overhead within a predeclared budget. Do not extrapolate the experimental 113–119 ms mean gate timings to production benefit.

Granite is a configurable bounded grounding provider candidate. The adversarial planner experiment gives it no causal completion evidence because its response was unused. The repaired/real-tool experiments supply narrower tool-calling observations but are weakened by injected defaults and permissive verification. Require clean independent role qualification before canonical eligibility. Qwen3.5-9B is a resident reference/comparator, never a fixed escalation tier or the defined Main Brain. Escalation targets are configured Main Brain, configured capable provider, specialist provider, external harness or user clarification, subject to policy. EDGE_ONLY must not silently call a capable provider; Edge OFF removes specialist inference, not deterministic capability.

## 10. Required qualification before any freeze

1. **Contract/compiler:** arbitrary tool rename with unchanged declared semantics; registry add/remove/version/schema mutation; duplicate/unknown IDs; missing or conflicting ports; cycles; reversed noncommuting operations; repeated action instances; two sources/two consumers; unknown goal must not return executable success.
2. **Semantics:** independently authored blinded goals, paraphrases, negation, reordered clauses, new domains/entities, multiple similar capabilities, missing policy, unavailable source, novel unsupported operation. Separate model proposal accuracy from compiler acceptance and final completion. Expected fixture outcomes are scorer-only.
3. **Binding/isolation:** fabricated, expired, cross-user/task/run handles; ambiguous files; two same-type outputs; invalid sheet/range; stale/corrected input; failure before producing a handle; scope/path escapes. Zero first-match/latest-handle substitution and zero silent data fallback.
4. **Execution/authority:** denied capability/action scope, approval required/denied/negated, changed registry after planning, node failure, unknown outcome, time/resource ceilings, duplicate/replayed checkpoint, persistence restart. All affected descendants stop; completed effects do not repeat. Proposed source/approval fields cannot grant authority.
5. **Independent verification:** inject correct-tool/wrong-arguments, failed results, fabricated report, omitted rows, extra actions/artifacts, wrong precision/units, partial output presented as whole, malformed/missing model call, provider timeout, forged verifier receipt, stale acceptance/hash, post-verification changes, missing/deleted originals. A forged success must be rejected even when every selected tool name is correct.
6. **Partial work:** disjointness/coverage, genuine unresolved record without magic UNKNOWN label, shared constraints, blocked aggregate, independent partition receipt, safe resume, no duplicate work. Literal word `isolate` is not evidence of an anomaly.
7. **Routing/cost:** optional Needle ablation, explicit configured Brain preserved, EDGE_ONLY/Edge OFF, provider unavailable, no silent model substitution, cold versus resident models, only useful model calls. Qualification is tied to exact model/provider/version/prompt/task envelope.
8. **Frozen/regression:** approved protected-file hash manifest; existing M33/RAR/ARN/governance tests; relevant action/permissions/approval/continuation/M36–M38 regressions with baseline failure adjudication. No accepted milestone status change from these tests.
9. **Canonical-loop/live integration gate:** after separate authorization, real user turn → context/Brain proposal → discovery → validated action/DAG → gates → execution → URI verification → evidence fed back to reasoning → grounded response. Live UI/chat must expose partial status, clarification and genuine failure correctly. A stand-alone CLI composition passing offline tests is not integration-complete.

Freeze the battery, oracle, hashes and thresholds before qualification. Mandatory safety counters are independently derived: false verified completion = 0; unauthorized effects = 0; wrong source binding = 0; undeclared execution = 0; undetected original modification = 0; unresolved work misreported complete = 0. Report numerators/denominators, abstention, unnecessary escalation, exact semantic/output correctness and final routes. Do not hard-code any counter to zero. No readiness or freeze based only on unit tests, tool-set membership or a small model battery.

## 11. Migration, risks, rollback and recommended order

Preserve `dynamic_planner.py`, original runners and telemetry as historical experimental evidence. In a later approved documentation/research cleanup, add an explicit REJECTED_FOR_PRODUCTION marker and point to this review; do not rewrite prior results. Replace the benchmark's use of either planner only after the new compiler/oracle is qualified, keeping the rejected version as a negative control. Ban experimental imports in production and add a guard. No immediate deletion, copy into production or broad deprecation of the existing canonical workflow engine.

Key risks are scope/type confusion despite syntactically compatible schemas, weak acceptance laundering, partial-result completeness errors, stale qualification, inherited approval, wrong-target substitutions, duplicate effects on resume, model-specific shortcuts, and crossing frozen generation boundaries. The first slice's read-only inputs and new scratch report limit these risks. Existing verifier subprocesses have disclosed OS isolation limits; avoid running model-authored code in this slice.

Rollback: retain baseline `62d564c` and unchanged M36–M38/frozen anchors; new isolated package can be disabled/removed from its explicit qualification entry point without changing production. Future production mode is opt-in with a dedicated killswitch; invalid proposal/verification never falls through to an ungated executor. Rollback after effects preserves the journal and never reruns already completed effects. Scratch results remain versioned evidence; original files and external accounts are untouched.

Recommended order:

1. Accept this Stage 1 evidence as the basis for a Stage 2 design; reconcile stale documentary pointers without changing milestone decisions.
2. Claude plans/pre-audits the generic proposal/compiler/binding architecture under the current governance; use standing auto-approval only within its permitted routine scope.
3. Produce Stage 3 exact migration, authority adapter, acceptance oracle and protected-file/test plan. Explicitly retain no production wiring in the first slice.
4. Antigravity initiates an authorized bounded implementation package. Implement contracts/compiler/bindings first, then the inspector/report adapters, trusted recomputation and claim lineage; run adversarial qualification.
5. Independently audit actual execution and failure paths. Granite/Needle role qualification follows the clean oracle, never precedes it as claimed production authority.
6. If authorized, open the distinct production-integration stage and qualify the canonical agent loop and live user behavior. Preserve M38's separate live gate and frozen S13/INT boundary.
7. Only the authorized release/freeze process may advance status; this report neither approves its own target design nor declares production readiness.

No unresolved constitutional decision requires user interruption now: the repository already resolves model-versus-runtime authority, configurable Brain identity, v1 placement, frozen boundaries and the absence of integration permission. The remaining work is a concrete architecture/migration review, not permission to promote the experiment.
