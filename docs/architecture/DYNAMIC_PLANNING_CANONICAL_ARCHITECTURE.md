# Dynamic Planning: Stage 2 Canonical Architecture Plan

Status: **ACCEPTED FOR STEPS 1-5 by Chetan 2026-09-29 01:10Z (decisions D1-D3 recorded in §10). PLANNING ONLY.** Nothing is implemented, committed, pushed, frozen, or wired into production.
Date: 2026-09-28. Author: Claude (planning thread). Same-provider document; it has not been independently audited.

Primary authority: Codex, *Independent canonical implementation review: experimental dynamic planning*
(`docs/research/DYNAMIC_PLANNING_CANONICAL_IMPLEMENTATION_REVIEW.md`, verdict **NEEDS_ARCHITECTURE_REWORK**), plus its
companion `DYNAMIC_PLANNING_CANONICAL_REVIEW_EVIDENCE.json`. Both files are untracked in Chetan's `_V1` checkout. The
review was uploaded to this thread, and the JSON is in the project folder. Findings F1 to F12 below mean that review's §3 table.

Governing lifecycle: `docs/governance/URI_FOUR_STAGE_DEVELOPMENT_LIFECYCLE.md`. This is the Stage 2 output. Its eventual
repository home is `docs/architecture/DYNAMIC_PLANNING_CANONICAL_ARCHITECTURE.md`, committed only after acceptance.

---

## 0. Acceptance criteria for this plan (defined first, re-checked in §11)

- **AC-1:** Every major design decision cites the Stage 1 finding (F1 to F12) or review section it addresses. Nothing in the Stage 1 evidence is rewritten or dropped (lifecycle §5.1).
- **AC-2:** No experimental planner, runner, scorer, or transform engine is promoted or copied.
- **AC-3:** Every "reuse" claim names a file and interface that I checked in the current repo.
- **AC-4:** The first slice changes **zero** frozen files and zero M36/M37/M38 files, or it explicitly flags any such change as a decision.
- **AC-5:** The plan covers all nine topics Chetan named: proposal, contracts, compiler/DAG, bindings, execution, verification, partial escalation, Needle, and configurable Brain.
- **AC-6:** It gives an exact first slice, the files and interfaces, the qualification gates, the migration order, and the genuine decisions.
- **AC-7:** It stays minimal. No abstraction appears that the first slice does not exercise, except where Chetan asked for a design (partial escalation, Needle, Brain). Those are specified at interface level only.
- **AC-8:** It states what could not be verified and whether that affects the plan.

## 1. Evidence base and what I verified myself

| Claim | How I checked it | Result |
|---|---|---|
| Review baseline `62d564c` exists | `git cat-file` on sche004-cyber/Uri | It exists. It is the head of branch `codex/m36-m38-canonical-audit`, on top of `379769f` and `833d6ed`. |
| Review regression: 107 passed | Reran the exact command from §4 of the review on Linux at `62d564c` | **107 passed.** At `c7832b9` (tip of `claude/project-thread-2vamlf`), the same command gives **113 passed.** |
| Reuse-map files exist | Checked each path at both `62d564c` and `c7832b9` | All present. Two paths in the review are missing their `uri_core/` prefix (`core/tool_schema.py`, `core/multi_action_dispatch.py`); the real paths are `uri_core/core/...`. |
| Chain projection drops node IDs (`canonical_execution.py:264`) | Read the source | Confirmed. `steps` carries only `capability`, `action`, `inputs`. |
| `uri_v1` never imports `uri_core` | grep | Confirmed by module docstrings (`uri_v1/wording/*`) and M33.3/M36 governance tests. |
| ADR-018 and the lifecycle | Read `URI_Model_Centric_Architecture_Docs/URI_ADR_018_*`, lifecycle §STAGE 2 and §5 | The Stage 2 questions and traceability rule are applied in §3 and §4. |
| Evidence JSON | Parsed it | Consistent with the review: 18/18 subset vs 14/18 exact; probe outputs match the §4 table; `head` = `62d564c`; Windows Python 3.13. |

**Unverified, with impact:**
- The experimental sources (`experimental/dynamic_planning_benchmark/*`) are untracked on Chetan's PC, so I could not read them. The F1 to F12 line citations and the fresh probe results are Codex's claims. **Impact: none on the design.** The plan does not reuse any experimental code, and it treats every one of those findings as a design requirement, whether or not the individual line claims hold.
- No live model was run (spend policy). Semantic-provider quality is **not** assumed anywhere below.

**Material finding (not in the review):** there are two divergent M36 to M38 candidate lines. One is Codex's `62d564c` (`833d6ed` merge + `379769f` Windows hardening). The other is Claude's `4cd360f → f9ac385 → c7832b9` on `claude/project-thread-2vamlf`. `git diff 62d564c c7832b9` touches 30 files, including `uri_v1/execution/{verify,workspace,officefile}.py`, `harness/contracts.py` and `memory/recorder.py`. The public interfaces this plan consumes are identical on both lines. `acceptance.py`, `lineage.py`, `run_record.py`, `memory/sources.py` and `edge/report.py` are byte-identical, and the `verify_candidate`, `make_memory_verifier`, `Workspace.create` and `read_workbook_structure` signatures match. **So the plan does not depend on which line is chosen, but the M36 to M38 freeze call must pick one** (§10, D1).

## 2. Architecture

```text
trusted user turn + Memory context + CapabilitySnapshot (read-only projection, hashed)
  → ProposalProvider (configured Main Brain | capable provider | test double)      UNTRUSTED
      emits SemanticProposal (JSON, closed schema): action instances, typed literals,
      symbolic port references, source *candidates by id*, desired outputs, declared "cannot" items
  → [optional ProposalAdvisor, e.g. Needle: advisory flags only; OFF by default]
  → ProposalCompiler (deterministic): schema → contracts → ports/types → DAG → limits
      → CompiledPlan (immutable, sha256) | typed Rejection | PartialPlan(supported ∪ unresolved)
  → Binder: source ids → hash-bound WorkspaceInputs via SourceRegistry (no path, no fuzzy, no latest)
  → PlanRunner: Workspace(COPY_IN_COPY_OUT) → topological, sequential, per-node live revalidation
      → handles issued only from schema-valid node results; failed node halts its descendants
  → record_and_verify (existing): RUN_RESULT → Memory CLAIMED_ONLY → registered URI verifier
      → verifier independently recomputes the report from hash-bound inputs + CompiledPlan
  → Completion = verifier status only. Grounded result + evidence refs returned to reasoning.
```

### 2.1 Untrusted semantic proposal (F1, F5, F9, F10)
- `SemanticProposal` is data with a closed schema `uri.plan.proposal.v1`: `nodes[] {id, action, action_version, inputs{port: {from:"<node>.<port>"} | {source:"<source_id>"} | {sources_ambiguous:["<id>",…]}}, literals{…}}`, `outputs[]`, `cannot[] {reason_code, text}`.
- The model chooses semantics: which sheets, which headers, which comparison, and in what order. The runtime never infers intent from keywords, filenames, years or tool-name spelling (F1). No runner-side argument injection is allowed (F5).
- A proposal can only reference `source_id`s from the trusted candidate list that the runtime put in the prompt context. An unknown id is rejected. It is never corrected to a "closest" file (F10).
- Malformed output, a missing output, a transport failure or a timeout gives a **typed no-completion** (`PROPOSAL_INVALID` / `PROVIDER_UNAVAILABLE`). It never defaults to CAN_DO (F5, F9).
- The raw proposal and its sha256 are persisted in the run bundle, separate from any reconciliation (F9).

### 2.2 Typed capability contracts (F2, F4)
- `CapabilityContract` is a **read-only projection** of an approved handler's declaration. It is not a second registry. Fields: `action_id`, `version`, `mechanism` (`DETERMINISTIC` | `SEMANTIC`), `inputs{port: PortType, required}`, `outputs{port: PortType}`, `literals{name: LiteralSpec}`, `effect` (`READ_ONLY` | `SCRATCH_WRITE`), `approval` (`NONE` in slice 1), `verifier_coverage` (acceptance kind it is covered by), `qualification` (record id + sha, or `UNQUALIFIED`).
- `PortType` is a **closed vocabulary**, not JSON primitives. For slice 1 it is `SOURCE_XLSX`, `WORKBOOK_STRUCTURE`, `STRUCTURE_SELECTION`, `STRUCTURE_COMPARISON`, `REPORT_ARTIFACT`. Compatibility means equal types, with no coercion.
- `CapabilitySnapshot` is an immutable tuple of contracts plus a sha256, pinned per plan. Missing metadata excludes a contract from composition. It never triggers a default (F2). Renaming an action while keeping its declared ports keeps it composable, because matching is by declared ports, not by spelling (F4 probe "arbitrary rename").
- Composition metadata only. The snapshot grants no execution or installation authority.

### 2.3 Deterministic proposal compiler and DAG validation (F3)
`compile(proposal, snapshot, candidates, limits) -> CompiledPlan | Rejection | PartialPlan`. The checks run in this order, and each has its own typed reason:
1. schema and size limits (nodes ≤ 16, edges ≤ 32, literals bounded);
2. unique node ids; `action`+`action_version` present in the snapshot;
3. every required input port is bound exactly once; each `from` names an existing producer node and output port of the **same PortType**; `source` names a trusted candidate of the right type;
4. literal validation against `LiteralSpec` (type, length, enum). Literals that depend on data (sheet or header names) are validated against actual data at run time, never guessed;
5. acyclic (Kahn), and every declared output is reachable;
6. every node's mechanism is `DETERMINISTIC` and qualified (slice 1). A `SEMANTIC` node is not compiled for execution;
7. a verifier covers every terminal output.

The compiler preserves repeated action instances, multiple producers, branches and joins. It never re-sorts by a tier order or chains nodes to their predecessor (F3). Order constraints come only from edges. Operations that don't commute stay in the proposed edge order.

`CompiledPlan` is canonical JSON with its sha256. It records `proposal_sha256`, `snapshot_sha256`, per-node `(action_id, version, qualification_sha)`, the edges, and the bound sources as `(source_id, content_sha256)`.

### 2.4 Explicit runtime bindings and handles (F10, F11, F12)
- `Handle` is an opaque runtime-issued token: `(user_id, task_id, run_id, node_id, port, value_sha256)`, kept in a per-run table owned by the runner. Models and proposals never see or create handles. They use only symbolic `node.port` references.
- A handle is issued only after the node's result validates against its output PortType. A failed node issues nothing. A consumer of an unissued handle fails with `UNBOUND_INPUT`, never with an empty table (F12).
- Sources are bound once at compile time through `SourceRegistry.locate`/`fingerprint` and then `Workspace.create` (hash-checked copy-in). The binder accepts no filesystem path, no fuzzy sheet match, no "latest file" and no first-match (F10, F11). Sheet or header literals that don't exist in the actual structure fail as `LITERAL_NOT_IN_SOURCE`.
- Ambiguous candidate sources give `NEEDS_CLARIFICATION` with the candidate ids. Slice 1 does not auto-bind. Later clarification uses the frozen RAR/clarification contracts unchanged.

### 2.5 Bounded deterministic execution (F4, F12)
- `PlanRunner` is a composition controller over **injected approved action adapters**. It is not a new dispatcher. It runs sequentially in topological order. Parallelism is out of scope.
- Before each node, it re-validates the node's `(action_id, version, qualification_sha)` against the live snapshot provider. On a mismatch, it stops that node and every unfinished descendant with `CAPABILITY_CHANGED`, and requires a fresh proposal and compile (F4).
- Per-node wall-clock and output-size ceilings apply, plus a whole-run ceiling. Unknown outcomes are never retried. Slice 1 has no side effects beyond scratch, so replay is trivially safe; a replay rule for effects is deferred.
- Actions in slice 1 are pure functions over `officefile` structures, with typed failure on any invalid input (F12). No `eval` and no arithmetic at all.

### 2.6 Independent verification (F6, F7, F8, F11)
- Completion is **only** the registered URI verifier's status, reached through the existing `lineage.record_and_verify` → `Recorder.outcome` (CLAIMED_ONLY) → `Recorder.invoke_verifier`. Proposal shape, tool names, model CAN_DO and runner exit status never count as completion (F6, F7).
- Acceptance is derived deterministically from the CompiledPlan and not from the proposal: `only_changed [report path]` + `output_workbook_exists`-equivalent (see §4) + `report_recomputes {path, task_class}`.
- **The plan hash is bound into acceptance without changing any M37 file.** `task_class = "PLANNED_STRUCTURE_REPORT@" + plan_sha256` (89 chars, within `acceptance._name`'s 128 limit). `make_memory_verifier` already rejects `ACCEPTANCE_TAMPERED` if the acceptance hash differs from `RUN_STARTED` (`verify.py:273` onwards). The CompiledPlan is stored in `workspace.bundle/plan.json`, outside `files/`, so the executor diff never covers it.
- The recompute oracle reads `bundle/plan.json`, checks its sha256 against the `task_class` suffix, re-checks every manifest copy's hash, and then **recomputes the report by a separate direct implementation** that walks the plan over `read_workbook_structure` results. It never calls `PlanRunner` or the binder. It compares canonical bytes. This gives independent execution. It is not independent authorship of `officefile` (disclosed, as in M37's `edge/report.recompute`).
- Integrity checks on the originals (`Workspace.originals_unchanged`), with deletion counted as a change (F11), are already enforced inside `make_memory_verifier`.

### 2.7 Partial escalation (F8), design now, implementation in slice 2
- `PartialPlan` is produced by the compiler when the proposal's `cannot[]` items, or nodes that are uncompilable or unqualified, leave an unresolved remainder. Partitioning is **by DAG closure, not by keywords** (F8). `supported` is the nodes whose full ancestor set is supported. `unresolved` is everything else, including all descendants of unresolved nodes. The compiler checks that `supported ∩ unresolved = ∅` and that `supported ∪ unresolved = all nodes`.
- An aggregate or join that consumes any unresolved node is itself unresolved. It is never presented as a complete total.
- `PartialEscalationArtifact` extends the **concept** of M37 `EscalationRequest`, not its closed enum. Its fields are the ones listed in review §9: identities; proposal, snapshot, acceptance and plan hashes; source ids and hashes; completed node receipts (verifier record ids); unresolved nodes with typed reasons and minimal context; the dependency closure; `effects_performed: []`; and `requested_role` (never a model name).
- The task stays `PARTIAL` while unresolved work exists. Slice 2 produces the artifact and a verified read-only partial report, and dispatches nothing. Routing it to the Main Brain, a capable provider, a harness or the user is a separate, later step. It reuses the M38 capsule only where the remainder fits M38's existing closed envelope.

### 2.8 Optional Needle (F9)
- `ProposalAdvisor` port: `advise(proposal, snapshot) -> AdvisoryReport {flags[], ranking?, raw_sha256}`. It is schema-validated, and malformed or missing output is recorded as `ADVISOR_INVALID` and ignored. The advisor can **only** add a flag that turns a would-be completion into `NEEDS_CLARIFICATION` or an escalation. It can never admit, bind, authorize or verify anything.
- **Default: bypassed.** No Needle call in slice 1. Needle ablation (deterministic only, provider only, Needle pre-check, selective post-check) is a qualification experiment in the provider-qualification step (§7 step 6), with a predeclared cost/latency budget. The existing `uri_v1/turn/needle_*` modules are consumed unchanged, if at all.

### 2.9 Configurable Main Brain / capable provider
- `ProposalProvider` port: `propose(goal_context, snapshot_view, candidates) -> ProviderResult {raw_text, parsed?, provider_id, model_id, config_sha256, latency_ms, error?}`. Identity is recorded exactly and never substituted silently.
- Which provider is used comes from the user's existing configured Brain/provider routing (D2 modes, Edge OFF / EDGE_ONLY semantics). The planner never hard-codes Granite, Qwen or a model tier. `EDGE_ONLY` never calls a capable provider. `Edge OFF` removes specialist inference but not deterministic capability.
- Slice 1 ships a `FixtureProvider` (a recorded or hand-authored proposal, clearly labelled a test double) and one real adapter behind the port for qualification only. Real calls go only through Chetan's subscription session or a local model (Ollama/LM Studio), in line with the spend policy.

## 3. Stage 2 lifecycle questions (lifecycle §STAGE 2), answered

| # | Answer |
|---|---|
| 1 Where in the loop | After context assembly and Brain reasoning, before dispatch. It is a compile, validate and execute sub-loop whose result returns to reasoning. Slice 1 is isolated, with an offline entry point only. |
| 2 Brain discovery | Through a CapabilitySnapshot view in the proposal prompt. In production it is projected from the existing per-turn `uri_core/core/capability_directory.py`, not a second catalogue. |
| 3 State/context | Trusted candidate source ids from SourceRegistry/Memory; snapshot; user/task/run/trace ids. |
| 4 Actions/schemas | §2.2, and §4's four actions. |
| 5 Returns | Verifier status + report result version (S11 ledger) + evidence refs, or a typed Rejection, `NEEDS_CLARIFICATION` or PARTIAL. |
| 6 Permissions/approval | Slice 1 is read-only plus scratch. No approval is needed and none is inferred. Write-back stays behind the existing `WritebackApproval` (out of slice). |
| 7 Memory | Existing Recorder: CLAIMED_ONLY claim, then a verifier record. No new Memory record kinds. |
| 8 Graph/session/runtime | No Graphify/graph dependency. Run lineage goes in the existing RunStore. |
| 9 Progressive discovery | Not in slice 1 (four actions). A shortlist is deferred until the snapshot grows. |
| 10 Model escalation | Via PartialEscalationArtifact (slice 2), and routing later. |
| 11 Owner | `uri_v1/execution/planning/` under OD-5 placement. Runtime authority stays with existing verify/lineage/workspace. |
| 12 Reuse/retire | §5. The experimental planners are retired as production candidates. The legacy `WorkflowPlanner` is kept for compatibility and is not generalized. |

The ten integration-completeness questions (lifecycle §4) are **not** met by slice 1 by design. Slice 1 is not integration-complete, and it must not be reported as such.

## 4. Exact first implementation slice

**Slice 1 = the review's §8 slice.** It produces an isolated, independently recomputed structure report comparing two hash-bound workbooks. It is offline, has no production wiring, and makes zero edits to existing files.

Actions (all `DETERMINISTIC`, effect `READ_ONLY` except the last, which is `SCRATCH_WRITE`):

| action_id v1 | inputs → outputs | literals | implementation |
|---|---|---|---|
| `uri.plan.workbook.inspect_structure` | `source: SOURCE_XLSX → structure: WORKBOOK_STRUCTURE` | none | `officefile.read_workbook_structure` on the workspace copy |
| `uri.plan.structure.select` | `structure → selection: STRUCTURE_SELECTION` | `sheets[]`, optional `headers[]` | exact-match filter. A missing name gives `LITERAL_NOT_IN_SOURCE` |
| `uri.plan.structure.compare` | `left, right: STRUCTURE_SELECTION → comparison: STRUCTURE_COMPARISON` | `match_on: "sheet_name"` (enum) | join on exact sheet name: shared / only-left / only-right headers |
| `uri.plan.report.write` | `items: 1..4 × (STRUCTURE_SELECTION \| STRUCTURE_COMPARISON) → report: REPORT_ARTIFACT` | none | writes canonical `plan_report.json` into `files/` |

The slice exercises repeated instances (two inspects, two selects), a branch and a join, symbolic bindings, grounding by the model (which sheets and headers), rename, remove and version change, a genuinely unsupported goal, and independent recomputation. It deliberately excludes cell values, business arithmetic, write-back and harness dispatch.

Acceptance for a compiled plan: `only_changed: ["plan_report.json"]` and `report_recomputes: {path: "plan_report.json", task_class: "PLANNED_STRUCTURE_REPORT@<plan_sha256>"}`. (`output_workbook_exists` is not used because the report is JSON. `report_recomputes` fails if the file is missing.)

Run recording: `RunStore.append(run_id, "RUN_STARTED", {"executor": "LOCAL_EDGE", "capability_id": "uri.plan.compiled", "plan_sha256": …, task_id, trace_id, workspace_dir, manifest, manifest_sha256, acceptance, acceptance_sha256})`. `LOCAL_EDGE` is the existing closed executor value for URI-local deterministic execution (`run_record.py:22`). `make_memory_verifier` reads only the keys it already reads.

Verifier registration: the qualification bootstrap calls `recorder._bootstrap_verifiers` once, with `{VERIFIER_ID: (VERIFIER_TYPE, VERIFIER_VERSION, make_memory_verifier(run_root, recompute=dispatch))}`, where `dispatch` routes `PLANNED_STRUCTURE_REPORT@*` to the planning oracle and everything else to `uri_v1.edge.report.recompute`, unchanged. Edge behaviour is identical. See D2 for the one labelling trade-off.

## 5. Reuse map (checked at `c7832b9`; interfaces identical at `62d564c`)

| Need | Reused as-is | Not reused / why |
|---|---|---|
| Workbook reading | `uri_v1/execution/officefile.py` `read_workbook_structure`, `WorkbookReadError` | Experimental `read_sheet_range` fuzzy fallback (F11) |
| Hash-bound sources | `uri_v1/memory/sources.py` `SourceRegistry.scan/locate/fingerprint` | Pilot path-as-handle executor (F11) |
| Scratch workspace + diff | `uri_v1/execution/workspace.py` `Workspace.create/diff/originals_unchanged`, `WorkspaceInput`, `new_run_id` | `DIRECT_ORIGINAL` (refused by design) |
| Acceptance | `uri_v1/execution/acceptance.py` `AcceptanceCriteria` (`only_changed`, `report_recomputes`) | New acceptance kinds (not needed) |
| Claim → verify → lineage | `uri_v1/execution/lineage.py` `record_and_verify`; `verify.py` `make_memory_verifier`, `verify_candidate`; `run_record.py` `RunStore`; `results/version_ledger.py` | Experimental `RepairedURIVerifier` and scorers (F6, F7) |
| Trusted verifier bootstrap | `uri_v1/memory/recorder.py` `_bootstrap_verifiers` (process-start only) | Any new registration API |
| Capability qualification discipline | Pattern from `uri_v1/edge/registry.py` (`QualificationRecord` exact id+version+sha, pinned digest) | Widening M37's closed `TaskClass` (review §7) |
| Escalation concept | `uri_v1/edge/contracts.py` `EscalationRequest` (field pattern) | Its closed task enum; M38 capsules for arbitrary DAGs |
| Clarification/binding | Frozen RAR/`uri_v1/reference_clarification/`/ARN.1, consumed later through existing interfaces | ARN.2, learned weights |
| Production catalogue/dispatch (later) | `uri_core/core/capability_directory.py`, `tool_schema.py`, `capabilities/base.py` ActionSchema, `multi_action_dispatch.py`, `canonical_execution.py`, `workflow_recovery.py` (design and regression cases) | Direct import into `uri_v1` (generation boundary); `WorkflowPlanner` templates |
| Specialist advice | `uri_v1/turn/needle_*` (later, unchanged, advisory) | Needle keyword tripwires / default CAN_DO (F9) |

**Explicitly not promoted:** `dynamic_planner.py`, `contract_driven_planner.py`, every experimental runner, `expanded_tool_registry.py`, the pilot `real_tool_executor.py`, model-name routing and automatic partial commits (review §5 Q13, §7).

## 6. Files and interfaces expected (slice 1, and the partial-escalation file for slice 2)

New files only, in `uri_v1/execution/planning/` (never importing `uri_core` or `experimental/`):

```text
__init__.py
contracts.py         PortType(Enum); LiteralSpec; CapabilityContract; CapabilitySnapshot(contracts, sha256)
                     SemanticProposal.parse(raw: dict) -> SemanticProposal   # raises ProposalInvalid(code)
                     PlanNode(node_id, action_id, version, inputs{port: SourceRef|PortRef}, literals)
                     CompiledPlan(nodes, edges, sources, proposal_sha256, snapshot_sha256).sha256/canonical()
                     Rejection(code, detail); PartialPlan(supported, unresolved, reasons)   # PartialPlan used in slice 2
compiler.py          compile(proposal, snapshot, candidates, *, limits) -> CompiledPlan | Rejection | PartialPlan
bindings.py          bind_sources(plan, sources, candidates) -> tuple[WorkspaceInput]
                     HandleTable.issue(node_id, port, value, port_type) / .get(node_id, port)  # no default, no latest
actions.py           the four slice-1 actions + snapshot() -> CapabilitySnapshot (pinned qualification sha)
runner.py            PlanRunner(user_id, scratch_root, run_store, recorder, ledger, sources, snapshot_provider)
                       .run(plan, *, task_id, trace_id, session_id) -> PlanOutcome
                     PlanOutcome(status, run_id, verification_status, claim_record_id, verifier_record_id, rejection|None)
oracle.py            recompute(task_class, workspace, report_path) -> bool   # independent re-derivation
                     verifier_entries(run_root) -> dict                      # composed dispatch, edge unchanged
provider_port.py     ProposalProvider(Protocol).propose(...) -> ProviderResult; FixtureProvider
                     ProposalAdvisor(Protocol).advise(...) -> AdvisoryReport; NullAdvisor (default)
partial.py           (slice 2) PartialEscalationArtifact; build_partial(plan, receipts) -> artifact
```

Tests and qualification:

```text
tests/test_dynamic_planning_contracts.py     schema, PortType closure, snapshot hashing, rename-by-ports
tests/test_dynamic_planning_compiler.py      gate 1 cases (§7)
tests/test_dynamic_planning_bindings.py      gate 3 cases
tests/test_dynamic_planning_execution.py     gate 4 cases
tests/test_dynamic_planning_verification.py  gate 5 cases, incl. forged report / wrong literal / tampered plan.json
tests/test_dynamic_planning_boundaries.py    no uri_core / experimental imports; frozen hash manifest unchanged
fixtures/dynamic_planning/qualification_cases.json   frozen battery (hash pinned before first run)
fixtures/dynamic_planning/workbooks/                 small generated .xlsx fixtures
scripts/dynamic_planning_qualification.py            bootstrap, run battery, derive counters from observations
docs/architecture/DYNAMIC_PLANNING_CANONICAL_ARCHITECTURE.md  (this plan, once accepted)
docs/plans/DYNAMIC_PLANNING_MIGRATION_PLAN.md                 (Stage 3)
```

**Existing files modified in slice 1: none.** If implementation finds that an unchanged interface can't do the job, it stops and amends this plan before editing (review §8).

## 7. Qualification gates

Freeze the battery, the oracle, the hashes and the thresholds **before** the first qualifying run. Expected outcomes are for the scorer only; neither the provider nor the runner ever sees them.

| Gate | Slice | Must show |
|---|---|---|
| G1 Contract/compiler | 1 | Arbitrary rename with the same ports still compiles. Add/remove/version/port-type mutation is handled correctly. Duplicate or unknown ids, missing/duplicate/mistyped ports, cycles and unreachable outputs are rejected. Reversed non-commuting order is preserved. Two inspect instances and two consumers compile. An unsupported goal (`cannot[]` only, or an unknown action) gives **no executable success**. |
| G2 Semantics | 1 (compiler only), provider step for real models | With test doubles: proposal errors surface as typed rejections. With real providers (later): proposal accuracy, compiler acceptance and final verified completion are reported **separately**, on blinded paraphrase/negation/new-entity cases. |
| G3 Binding/isolation | 1 | Fabricated, cross-user/task/run, unissued or failed-node handles fail. Unknown or ambiguous source ids fail or clarify. Stale hash (edited after scan) gives `INPUT_NOT_CURRENT`. Invalid sheet/header literal fails. Zero first-match/latest substitution and zero empty-default fallback. |
| G4 Execution/authority | 1 | Snapshot changed between compile and node gives `CAPABILITY_CHANGED` and descendants stop. Node failure halts descendants. Ceilings fire. Proposal fields cannot add sources, approvals or effects. |
| G5 Independent verification | 1 | Forged report bytes, correct actions with wrong literals, an extra artifact, an omitted section, a tampered `bundle/plan.json`, a plan hash mismatch, a modified or deleted original and post-verification change are all **not VERIFIED**. A provider timeout or malformed output gives no run. |
| G6 Partial work | 2 | Disjointness and coverage are proven. An aggregate that consumes an unresolved node is unresolved. No magic-label partitioning. The task stays PARTIAL. Zero effects. |
| G7 Routing/cost | provider step | Needle ablation within its budget. Configured Brain preserved. EDGE_ONLY/Edge OFF respected. No silent substitution. Exact model/provider/prompt identity pinned. |
| G8 Frozen/regression | every slice | Protected-file hash manifest unchanged. M33.3/RAR/ARN anchors and governance validator pass. The review regression command (107 at `62d564c` / 113 at `c7832b9`) still passes. M36/M37/M38 suites pass, with baseline failures adjudicated. |
| G9 Canonical loop/live | separately authorized | Real user turn → proposal → compile → gates → execute → verify → grounded reply, through the real UI. PR-only per the live-app guardrail. |

**Safety counters**, derived from observed events and never initialised as a literal pass: false verified completion = 0; unauthorized effect = 0; wrong source binding = 0; undeclared execution (a node not in the CompiledPlan) = 0; undetected original modification = 0; unresolved reported complete = 0. Report numerators and denominators, abstentions and final routes.

## 8. Migration order

1. **Accept Stage 2** (this doc) and settle D1 to D3. Commit the doc to `docs/architecture/` on a planning branch once it is accepted.
2. **Stage 3 migration plan** (`docs/plans/DYNAMIC_PLANNING_MIGRATION_PLAN.md`): freeze the G1 to G5 battery and hashes, the protected-file manifest, and the rollback point (base SHA from D1).
3. **Slice 1a:** `contracts.py`, `compiler.py`, `bindings.py` (pure), plus tests for G1 and G3.
4. **Slice 1b:** `actions.py`, `runner.py`, `oracle.py`, plus tests for G4 and G5, plus the qualification script with `FixtureProvider`.
5. **Fresh Opus audit** of slice 1 (execution and failure paths, not tests alone). The result stays PROVISIONAL.
6. **Provider qualification:** a real configured Brain through the subscription session or a local model; Granite as a candidate, not an assumption; the Needle ablation (G2, G7).
7. **Slice 2:** `partial.py` + G6. Read-only partial reports only.
8. **Production adapter** (separate authorization, PR-only, behind an off-by-default flag and killswitch). It projects the directory as a snapshot, preserves node ids and ports in `canonical_execution`, and applies per-node gates through the existing dispatcher. Then G9.
9. **Research cleanup:** mark the experimental planners `REJECTED_FOR_PRODUCTION`, keeping them as negative controls, and add an import guard. Nothing is deleted.

Rollback at every step means deleting `uri_v1/execution/planning/` and its tests. Nothing else references it.

## 9. Relation to the product target

Dynamic planning is **not** on the critical path to URI_WORKING_PRODUCT_BASELINE. The Office demonstrator (M39) uses M37/M38's closed task classes. Steps 1 to 5 are isolated and can run alongside M39 without blocking it. Step 8 is the point where dynamic planning would widen what the live product can do, so it belongs after the baseline unless Chetan says otherwise (D3).

## 10. Decisions (resolved by Chetan, 2026-09-29 01:10Z)

- **D1 Base line:** not picked manually. Stage 3/4 builds on whichever M36 to M38 line wins the pending freeze/reconciliation (`62d564c` Codex vs `c7832b9` Claude). Until then **`c7832b9` is the working line** if one is needed. Consequence: slice 1 must depend only on the interfaces identical on both lines (§1), and must re-run G8 on the winning line before its audit.
- **D2 Verifier label:** **reuse the existing verifier** (`uri.verifier.execution.script_workbook.v1`) with the composed recompute. **No edit to `verify.py` while M38 is under audit.** A distinct planning verifier identity is added only once that boundary is safely available (M38 frozen, and the boundary change authorized).
- **D3 Timing:** proceed with isolated **Steps 1 to 5 alongside M39**. **Hold all live/production wiring** (Step 8, G9) until URI_WORKING_PRODUCT_BASELINE is reached.

Already settled by the repo or governance: model-versus-runtime authority (ADR-018), v1 placement (OD-5), no `uri_core` import, frozen RAR/ARN/M33.3, no integration authorization, and the spend policy. Implementation is routed through the project pipeline (Sonnet implementation thread), not Antigravity as the review suggested.

## 11. Self-review against §0

- **AC-1:** §2 subsections cite F1 to F12. F1 to F12 are each addressed: F1 §2.1, F2 §2.2, F3 §2.3, F4 §2.2/§2.5, F5 §2.1, F6/F7 §2.6, F8 §2.7, F9 §2.1/§2.8, F10 §2.1/§2.4, F11 §2.4/§2.6, F12 §2.4/§2.5. **Pass.**
- **AC-2:** §5 lists every experimental artifact as not promoted. There is no copied logic. **Pass.**
- **AC-3:** Reuse paths were checked at both SHAs. The two path typos in the review were corrected. **Pass.**
- **AC-4:** Slice 1 modifies no existing file. The one place where a modification would be cleaner is raised as D2. **Pass.**
- **AC-5:** §2.1 to §2.9. **Pass.**
- **AC-6:** §2 to §8 and §10. **Pass.**
- **AC-7:** Partial escalation, Needle and the provider are interface-only. Slice 1 has four actions and no scheduler, shortlist, arithmetic or write-back. **Pass.**
- **AC-8:** §1 lists what is unverified and its impact. **Pass.**

Gaps found in the first draft and repaired:
1. The first draft used a new RunStore executor value, which would have edited `run_record.py`. It was replaced with the existing `LOCAL_EDGE`.
2. The first draft passed the CompiledPlan to the verifier through the run record. `make_memory_verifier`'s `recompute(task_class, workspace, path)` cannot see the run record, so the plan is now bound through the acceptance `task_class` suffix and `bundle/plan.json`.
3. The first draft used `output_workbook_exists` for a JSON report, which would always FAIL. It was dropped; `report_recomputes` already fails when the file is missing.
4. Recompute independence was overstated. It now says independent execution, shared `officefile` reader.
