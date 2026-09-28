# M37 — Edge Minimum (local-first resolution and qualified local completion)

- **Status:** `M37_IMPLEMENTED_PROVISIONAL_NOT_FROZEN` once the implementation commit lands. Until an independent audit, M37 is PROVISIONAL / NOT FROZEN. Nothing here claims independent qualification or closure.
- **Date:** 2026-09-28. **Author / implementer:** Claude Code (Opus 5.5). Independent auditor for the batch: Codex (preferred, per User 2026-09-28).
- **Authority:** User instruction 2026-09-28 (project thread "batched independent audits"): "Edge minimum — plan and implement", building on unaudited M36 with the dependency recorded, then Harness Execution minimum, then one independent Codex audit package for Memory → Edge → Harness. No freeze, no production integration.
- **Baseline:** branch `m35-uri-v1-parallel-architecture` at `be4451c6fda7803a742e0ad48c7fec63140ec30b` (M36, Codex-built, PROVISIONAL, under separate Claude audit). Frozen M33.3 baseline `291c9daa48435200c4b56857d0e3bc630016e82a`.
- **Recorded dependency:** M37 consumes M36 `MemoryContextPackage`, `Recorder.outcome`, `Recorder.invoke_verifier`, `SourceRegistry` and the S11 `ResultVersionLedger` read/write API **without modifying any M36 or M33.3 file**. If the M36 audit requires a repair to any of those APIs, M37 must be re-qualified against the repaired M36.

## 0. Acceptance criteria (defined before drafting)

| ID | Criterion |
|---|---|
| AC-E1 | The plan derives Edge-minimum scope from repository evidence (M36 plan §16.3, VG-1, LF-1, Paperclip §19, OD-3..OD-5), not from invented requirements. |
| AC-E2 | Only *qualified* local mechanisms can complete work locally; unqualified or experimental mechanisms never complete a task (LF-1: correctness over avoidance). |
| AC-E3 | E-5: the Edge consumes `MemoryContextPackage` as-is; no Memory contract change. |
| AC-E4 | Local completion writes only to a URI-owned copy-in workspace; originals are never modified by M37. |
| AC-E5 | Every local completion is recorded in Memory as `CLAIMED_ONLY` and only a registered URI verifier can produce `VERIFIED` (M36 §7.8, D-A). |
| AC-E6 | When escalation is needed, the Edge emits only the unresolved remainder plus locally established, hashed facts (VG-1 G2) — the input the Harness minimum consumes. |
| AC-E7 | Avoidance is measurable (VG-1 G1): decision, mechanism, latency and avoided-escalation are recorded content-free. |
| AC-E8 | Frozen M33.3 files, M31, frozen S6 routing and M36 files are byte-identical; `uri_v1` does not import `uri_core`. |
| AC-E9 | Tests, a predeclared qualification battery with thresholds frozen before the run, a governance check and a self-review are produced; limitations are disclosed. |

## 1. What "Edge" means for this minimum (evidence)

- M33.2 defines the Edge as URI's local intelligence tier (small local models and deterministic preflight), strictly proposal-only, benchmark-gated, with no execution route of its own (`docs/plans/M33_2_EDGE_SECOND_BRAIN_MIGRATION_PLAN.md` §1). Its router is frozen S6 in `uri_core/core/edge/routing_policy.py` and routes *Brain* work only.
- M36 plan §16.3 records what the Edge minimum must provide: qualified local completion as a first-class source of value (VG-1 Arm C, G1), deterministic/local mechanisms before escalation (LF-1), no forcing beyond demonstrated capability, measurable avoidance, S6 unchanged, E-5 unchanged.
- Paperclip §19: deciding "this needs an agentic harness" is a separate, later routing layer that must not be added to frozen S6.
- OD-5: execution contracts live in `uri_v1/execution/`; `uri_v1` never imports `uri_core`.

Therefore the Edge minimum is **the `uri_v1` local-first resolution layer**: given a bound task and its Memory context, decide `LOCAL` / `ESCALATE` / `CLARIFY`; complete `LOCAL` work only with qualified mechanisms in a bounded workspace; hand verification to URI verifiers; hand the unresolved remainder to the Harness minimum. It is a new decision layer next to S6, not an extension of S6.

**Default chosen (not a User ruling):** the only mechanisms qualified in M37 are **deterministic**. A provider/transport-neutral `EdgeModelPort` is defined so a local model (Ollama, LM Studio, other) can be registered, but a model-backed capability is `EXPERIMENTAL` until a real-hardware qualification exists; it can never complete work in M37. No local model is available in the implementation environment, so claiming otherwise would be unsupported.

## 2. Scope

### 2.1 In scope (new files only)

`uri_v1/execution/` — shared execution infrastructure (used by M37 local completion and by M38 harness runs; OD-5 placement):
- `workspace.py` — `COPY_IN_COPY_OUT` workspace: copies only the named, hash-verified inputs from authorized roots into URI-owned scratch; verifies copy hashes; manifest with SHA-256; containment guard (no symlinks, no escape); single-writer lock; URI-computed `diff()` of changed artifacts; approval-gated write-back that refuses if the original changed since copy-in. `DIRECT_ORIGINAL` is represented and refused in the minimum (OD-3 allows it only by explicit per-task user choice; no such flow exists yet).
- `acceptance.py` — closed, hashed acceptance criteria (`script_exit_zero`, `workbook_has_sheets`, `workbook_has_columns`, `output_workbook_exists`, `no_formula_errors`, `only_changed`).
- `officefile.py` — bounded, dependency-free `.xlsx` structure reader (sheet names, header row, error-cell count; zip-bomb and size limits).
- `verify.py` — URI-owned verifier: copies the candidate workspace into a fresh verification directory, runs the script in a URI-controlled subprocess (scrubbed environment, timeout, cwd confined) and checks every acceptance item. Produces `VERIFIED` / `PARTIALLY_VERIFIED` / `FAILED` / `UNVERIFIABLE`. Also a factory producing the M36 verifier callable, which locates the run through the claim's `attempt_id`.
- `run_record.py` — append-only, schema-versioned per-user run records (`LOCAL_EDGE` or `HARNESS`), holding workspace manifest, capsule hash, URI-computed changes and verification reports. Lineage, not Memory.

`uri_v1/edge/`:
- `contracts.py` — task classes, `EdgeTask`, `CapabilityDescriptor`, `EdgeDecision`, `EscalationRequest`, reason codes.
- `inspect.py` — deterministic script inspection (AST: imports, workbook-name literals, sheet and column literals).
- `compat.py` — script↔workbook compatibility diagnosis; unique normalized-name remap proposals.
- `repair.py` — deterministic literal remap (token-exact rewrite of string literals only).
- `registry.py` — capability registry and qualification gate: a capability is eligible only when `QUALIFIED` at its exact version and its evidence file's digest matches.
- `resolver.py` — `resolve(task, context_package, registry, …)`.
- `local_runner.py` — executes a `LOCAL` decision in a workspace, records claim → verifier, writes the run record and telemetry.
- `telemetry.py` — content-free decision events.

Tests `tests/test_m37_edge_*.py`, battery `fixtures/m37_edge/`, driver `scripts/m37_edge_qualification.py`, evidence under `docs/plans/M37_*`.

### 2.2 Out of scope

Any change to M36, frozen M33.3 (S1–S12), S6, M31, `uri_core`, UI, `/ask` or production wiring; local-model qualification; harness invocation (M38); Office demonstrator; `harness_run_ref`; write-back to originals in any automated flow (the API exists, gated by explicit approval, and is exercised only in tests on temporary roots).

## 3. Task classes and qualification envelope

| Task class | Local mechanism | M37 qualification | Notes |
|---|---|---|---|
| `WORKBOOK_INSPECT` | `officefile` reader | QUALIFIED (deterministic) | structure only; no cell values leave the process except header names |
| `SCRIPT_INSPECT` | AST inspection | QUALIFIED | static only; never executes the script |
| `SCRIPT_WORKBOOK_DIAGNOSE` | inspect + compat | QUALIFIED | reports missing sheet/column literals and unique remaps |
| `SCRIPT_WORKBOOK_REPAIR` | literal remap | QUALIFIED **only** when every mismatch is a unique normalized remap and the script has no dynamic sheet/column access that inspection cannot see | anything else escalates |
| any class via `EdgeModelPort` | local model | EXPERIMENTAL | never completes work in M37 |

Normalization for a remap: case-fold, strip, collapse runs of whitespace/`_`/`-` to one space. A remap is proposed only if exactly one workbook name normalizes to the same form as the missing literal. Ambiguity → escalate (never guess).

Dynamic-access guard: repair is ineligible when the script builds sheet/column names at runtime (f-strings, concatenation, `.format`, variables as subscripts on the workbook/dataframe) — detected conservatively by AST.

## 4. Decision procedure (`resolve`)

1. Validate the `MemoryContextPackage` (schema `m36.context.v1`). If `degraded` is `CONFLICT`, `PENDING_CORRECTION` or `QUARANTINED_RECORDS` → `CLARIFY` (reason = the degraded code). `BUDGET_EXCEEDED` is treated as "no memory context", not as an error.
2. Every task input must be hash-bound (`source_id`, SHA-256) and live-verified through `SourceRegistry.verify_source`. If an input is missing/stale, or the package lists it under `stale` → `CLARIFY` (`STALE_INPUT`). Wrong-file safety outranks progress.
3. If the package's `corrections` show the user corrected a reference that is a task input to a different source → `CLARIFY` (`CORRECTED_REFERENCE`).
4. Select capabilities for the task class; keep only those passing the qualification gate. None → `ESCALATE` (`NO_QUALIFIED_CAPABILITY`).
5. Run the class's *pre-check* (pure, read-only). For repair: diagnose; if no mismatch → `LOCAL` with nothing to change (verify-only); if every mismatch has a unique remap and no dynamic access → `LOCAL`; otherwise → `ESCALATE` with the diagnosis attached.
6. `ESCALATE` produces an `EscalationRequest`: task id, class, hashed inputs with roles, acceptance criteria and hash, the local findings (workbook structure, script inspection, diagnosis), and an `unresolved` list naming exactly what was not resolved locally. No file content beyond names and structure is carried.

The resolver is pure given its inputs (no writes). It never calls a model in M37.

## 5. Local completion (`LocalRunner`)

1. Create a workspace from the task inputs (copy-in, hash re-check).
2. Apply the capability in the workspace only.
3. URI computes `changed_artifacts` from the workspace diff.
4. Record each changed artifact as an S11 result version; record Memory `OUTCOME` (`EXECUTION_OUTCOME`, `CLAIMED_ONLY`) with inputs = original `source_id@sha`, outputs = S11 `result_id@version@sha`, `attempt_id = run_id`.
5. Write the run record, then invoke the registered verifier `uri.verifier.execution.script_workbook.v1` through `Recorder.invoke_verifier`. Its verdict — not the capability — decides `VERIFIED`.
6. Return the decision, run id, claim record id, verifier record id and verdict. Write-back stays a separate, explicitly approved call.

## 6. Qualification (predeclared; thresholds frozen before the first measured run)

Battery `fixtures/m37_edge/battery.json` (authored before the driver run, hashed into the evidence): real generated `.xlsx` workbooks and real Python scripts using `openpyxl`, covering matched, renamed-case, renamed-separator, ambiguous, absent, dynamic-access, sheet-renamed, stale-input, corrected-reference, conflict-degraded and multi-mismatch cases.

Threshold gate `fixtures/m37_edge/threshold_gate.json`:
- `wrong_local_completion` = 0 (a LOCAL decision whose verifier verdict is not `VERIFIED`, or a LOCAL decision on a case whose expected decision is not LOCAL);
- `unsafe_local_on_ambiguous_or_dynamic` = 0;
- `stale_or_corrected_input_not_clarified` = 0;
- `original_modified` = 0;
- `decision_accuracy` = 1.0 against the predeclared expected decision per case;
- decisions identical across two runs (determinism).

The avoidance rate is **reported**, not thresholded: it is a property of the battery mix, not of quality.

## 7. Self-review and audit hand-off

The implementation report records commands, counts, failures, the M36 dependency, limitations and the exact Codex audit prompt (shared batch package: `docs/plans/URI_BATCH_M36_M37_M38_AUDIT_PACKAGE.md`).

## 8. Known limitations accepted for the minimum

- Static inspection cannot prove absence of dynamic behavior; the guard is conservative (escalates when unsure), so avoidance is under-estimated rather than correctness over-estimated.
- Verification runs the user's script in a subprocess without an OS sandbox. It runs only on URI's scratch copy, with a scrubbed environment and a timeout; network access is not blocked at OS level. Disclosed; an OS sandbox is future work.
- `.xls`/`.xlsm`/`.csv` are not covered by the structure reader in M37.
- No local model is qualified; the `EdgeModelPort` is interface-only.

## 9. Implementation notes (added after implementation; sections 0–8 are unchanged)

- `SCRIPT_INSPECT` from §3 was not built as a separate task class. Script inspection is part of `SCRIPT_WORKBOOK_DIAGNOSE`; nothing in the demonstrator needs a script-only report.
- The recompute check for report classes lives in `uri_v1/edge/report.py` and is injected into the execution verifier at bootstrap (`uri_v1/edge/local_runner.py:verifier_entries`). This keeps `uri_v1/execution` free of Edge imports.
- A LOCAL decision is only a *local attempt*. It becomes `LOCAL_VERIFIED` only on a `VERIFIED` verdict; any other verdict stays recorded in Memory and the task is escalated with the verification evidence attached (battery cases E10, E11).
- The run store uses its own sidecar file lock. `uri_v1.user_storage.locked_append` holds a module-global, non-reentrant thread lock that M36 `MemoryLog.guard()` already holds while a verifier runs, so reusing it there deadlocks.
- Write-back approval rejects negated wording with the M36 `negated()` helper from repair commit `405db1f` (audit finding F-2 applies equally to approvals).
- M36 dependency moved from `be4451c` to the M36 repair commit `405db1ff21f11f6927fe1b74990ff6b88a97a28d` (fast-forward). Edge does not bind files itself; it consumes hash-bound inputs and the context package, so the repaired negation/binding behavior (F-1, F-5, F-6) is upstream of M37.
