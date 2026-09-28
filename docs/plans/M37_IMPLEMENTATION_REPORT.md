# M37 Edge Minimum — implementation report

State: `M37_IMPLEMENTED_PROVISIONAL_NOT_FROZEN`. Implemented and self-qualified by Claude Code on 2026-09-28. Not independently audited, not frozen, not integrated. Independent audit is part of the batched Codex package (`docs/plans/URI_BATCH_M36_M37_M38_AUDIT_PACKAGE.md`).

## Authority, baseline, dependency

- User instruction 2026-09-28 (project thread "batched independent audits"): plan and implement the Edge minimum without stopping for a per-milestone audit; keep it PROVISIONAL; record dependencies on unaudited predecessors; no freeze.
- Baseline: `405db1ff21f11f6927fe1b74990ff6b88a97a28d` (M36 repair commit, fast-forward of Codex's `be4451c`), branch history from `sche004-cyber/uri-agent` `m35-uri-v1-parallel-architecture`. The `sche004-cyber/Uri` repository was empty when this work started.
- **Recorded dependency on unaudited M36:** `MemoryContextPackage` (`build_context`), `Recorder.outcome`, `Recorder.invoke_verifier`, `_bootstrap_verifiers`, `SourceRegistry.{scan,locate,fingerprint,verify_source,roots}`, `TrustedInput`, `negated`; plus frozen S11 `ResultVersionLedger.record_generated`. No M36 or M33.3 file is modified.

## What was built

| Area | Files | Summary |
|---|---|---|
| Acceptance | `uri_v1/execution/acceptance.py` | Closed item vocabulary, workspace-relative paths only, canonical SHA-256. |
| Workbook reader | `uri_v1/execution/officefile.py` | Dependency-free `.xlsx` structure (sheets, header row, error cells); size, ratio and DTD guards. |
| Workspace | `uri_v1/execution/workspace.py` | `COPY_IN_COPY_OUT` of named hash-bound inputs; copy hash re-check; URI-computed diff; symlink/special-file containment violations; single-writer lock; approval-gated write-back refusing unverified runs, untrusted/negated approvals, other users and changed originals. `DIRECT_ORIGINAL` refused in the minimum. |
| Verification | `uri_v1/execution/verify.py` | Fresh verification copy; script run in its own process group with scrubbed env and timeout; acceptance evaluation; M36 verifier callable that first checks claim ↔ run record ↔ live workspace consistency. |
| Lineage | `uri_v1/execution/run_record.py`, `lineage.py` | Hash-chained append-only run store; S11 versions for changed artifacts; claim (`CLAIMED_ONLY`) then registered verifier. |
| Edge | `uri_v1/edge/*.py` | Contracts, AST script inspection, compatibility diagnosis, exact literal remap, digest-pinned qualification registry, resolver (Memory gate, live hash gate, qualified-capability gate), local runner, report recompute, telemetry. |

## Acceptance criteria disposition (plan §0)

| ID | Result | Evidence |
|---|---|---|
| AC-E1 | Met | Plan §1 cites M36 §16.3, VG-1, LF-1, Paperclip §19, OD-3..OD-5. |
| AC-E2 | Met | `CapabilityRegistry` eligibility; `test_unqualified_registry_never_completes_locally`; `test_qualification_record_is_digest_pinned_and_version_exact`; LOCAL counts as complete only on `VERIFIED` (E10, E11). |
| AC-E3 (E-5) | Met in tests | Real `build_context` packages from real S1 bindings: current (local), changed file (CLARIFY), user correction (CLARIFY), fork conflict (CLARIFY). No Memory change. |
| AC-E4 | Met | `original_modified` = 0 over 40 battery runs; `test_local_repair_is_claimed_then_verified_by_uri`. |
| AC-E5 | Met | Claim `CLAIMED_OUTCOME`, verdict `VERIFIED_OUTCOME` superseding it; forged candidate change after the claim → `FAILED`. |
| AC-E6 | Met | `test_escalation_carries_only_unresolved_remainder_and_hashed_facts` (no data cells, no script text). |
| AC-E7 | Met | Content-free telemetry test; avoidance rate reported. |
| AC-E8 | Met | Import-boundary test; changed-path test against `405db1f`; frozen anchors `ok=True`. |
| AC-E9 | Met | Below. |

## Validation (all runs in this cloud container: Linux, Python 3.11.15)

- M37 tests: `python -m pytest tests/test_m37_*.py` → **29 passed**.
- Qualification driver: `python scripts/m37_edge_qualification.py` → gate **PASSED**, 20 cases × 2 runs. `decision_accuracy` 1.0; `false_local_success` 0; `unsafe_local_on_ambiguous_or_dynamic` 0; `stale_corrected_or_conflict_not_clarified` 0; `original_modified` 0; claims recorded claim-first; determinism mismatches 0. Reported: avoidance rate 0.40 (8/20, a property of the battery mix), local-attempt failures 2 (E10, E11, both escalated with evidence), latency p50 22 ms / p95 280 ms. Raw results: `docs/plans/M37_QUALIFICATION_RESULTS.json`. Pinned evidence: `docs/plans/M37_EDGE_QUALIFICATION_EVIDENCE.json` (SHA-256 LF-normalized, pinned in `uri_v1/edge/registry.py`).
- `tests/` suite (M36, frozen M33.3, M31, governance, dev workflow, M37): see "Regression" in the batch package; before commit, **763 passed, 1 skipped**.
- Governance validator suite: **37 passed** after adding the M37 entry.
- Frozen anchors (`scripts/m33_3_r_anchors.py`): `ok=True`, `changed=[]`.

## Known issues and limitations (disclosed)

1. **M36 scope-guard test.** `tests/test_m36_memory_adversarial.py::test_core_adapter_import_boundaries_and_frozen_scope` asserts that every path changed since `291c9da` is an M36 path. Once M37 files are committed it fails for that reason only. By User decision (2026-09-28, "Leave and disclose") M36 is left byte-identical; the test passes at `405db1f`. M37's own `test_m36_and_frozen_files_unchanged` performs the equivalent check against `405db1f` with M37/M38 paths allowed.
2. **Same-author battery.** The battery and gate were written by the implementer after the implementation was drafted, and they passed on the first measured run. That is weak evidence: an independent auditor should add cases, especially for scripts using other access patterns (pandas `usecols`, `csv`, `iter_rows` with positional headers, sheet access by index).
3. **Static inspection is heuristic.** It recognizes openpyxl and pandas name-based access. Unrecognized access patterns are not flagged as dynamic; the URI verifier is then the backstop (a failed local attempt escalates). No wrong local completion is possible, but avoidance can be lost.
4. **No OS sandbox for verification runs.** Scratch copy, scrubbed env, own process group and timeout only; network is not blocked at OS level.
5. **No local model qualified.** `Mechanism.EDGE_MODEL` exists; no qualification record names one.
6. **Windows not exercised.** Written for Windows (msvcrt locks, `CREATE_NEW_PROCESS_GROUP`, `taskkill`) but only run on Linux here. The user's primary environment is Windows; the auditor should run the suites there.
7. **pandas not installed** in this container, so no battery case executes a pandas script; pandas patterns are covered by static-inspection tests only.
8. The driver re-bootstraps the verifier registry per case so each case's verifier points at its own temporary run store. Production bootstrap happens once per process (`verifier_entries`).

## Not done (out of scope)

No harness invocation, no Office demonstrator, no production wiring, no S6/M31/uri_core change, no write-back in any automated flow, no freeze.
