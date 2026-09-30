# Dynamic Planning Slice 1: Independent Audit (Claude, repository evidence)

Status of the audited slice: **PROVISIONAL / NOT FROZEN** (unchanged by this audit, whatever the verdict).
Audit only. No repair was made; no slice, frozen or live-app file was edited.

- Target: `sche004-cyber/Uri`, branch `claude/dynamic-planning-slice1-2eemmh`, head `c5d47a0` (report) over code `3bbf8f77090ea7803178bff87835e67444d2e9f9`.
- Base: frozen line `5bbf738` (M36/M37/M38 CLOSED_FROZEN at `bd7c450`).
- Context: Codex was paused for quota (Chetan, 2026-09-29 10:53). Codex had already finished an audit of this slice (`/mnt/project-files/CODEX_AUDIT_DYNAMIC_PLANNING_c5d47a0.md`, verdict REPAIRS_REQUIRED). Per the coordinator's brief this audit (a) re-verifies each Codex finding from repository evidence and (b) adds new probes in areas Codex did not cover. Codex's report was treated as a claim, not evidence.
- Environment: Linux, Python 3.11.15. `pytest` and the repo's `requirements.txt` were installed into the container; `google-api-python-client`/`google-auth-oauthlib` were also installed because two existing test modules import them and `requirements.txt` does not declare them (pre-existing, outside the slice). No network model, no spend.

## 1. Acceptance criteria (defined before the checks)

The slice passes this audit only if all of these hold:

| # | Criterion |
|---|---|
| A1 | Only new files; none outside `uri_v1/execution/planning/` plus its tests, driver, fixtures and docs; `verify.py` and all frozen files unchanged. |
| A2 | No planning module imports `uri_v1.memory`; `oracle.py` does not import the runner, binder or actions; no existing module imports the package. |
| A3 | Full suite: 1404 pass, and the only failure is the accepted `tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged`, failing only on slice paths. |
| A4 | Qualification: 34/34 expected typed outcomes and all six safety counters at 0, reproduced by rerunning the driver; battery/gate/fixture digests equal the recorded ones and are unchanged since the freeze commit. |
| A5 | Anchors, governance (37 + validator), M36/M37/M38 qualification and the 113-test review set still pass. |
| A6 | No untrusted proposal, and no user-supplied source file, can produce a false `VERIFIED`, an unauthorized effect or a wrong source binding. |
| A7 | Every failure path reachable from untrusted input (provider text, proposal, user files) ends in a typed `PlanOutcome` / `Rejection`, never an uncaught exception, and never leaves a run record without a terminal event. |
| A8 | The implementation report's claims match what the code and reruns show. |

## 2. Reruns (all COMPLETED_WITH_RESULT, evidence in `docs/reviews/dynamic_planning_slice1_audit/`)

| Check | Command | Observed | Criterion |
|---|---|---|---|
| File scope | `git diff --name-status 5bbf738 c5d47a0` | 29 files, all `A`; `verify.py` diff empty | A1 met |
| Imports | AST scan of `uri_v1/execution/planning/*.py`; repo grep for importers | no `uri_v1.memory`; oracle imports only `edge.report`, `officefile`, `verify`, `workspace`, `.contracts`; no outside importer | A2 met |
| Full suite | `python3 -B -m pytest -q -p no:cacheprovider tests/` | **1404 passed, 1 failed, 9 skipped** (`full_suite.txt`) | A3 met |
| Guard failure content | replicated the guard's own `git diff` + allowlist | 17 disallowed paths, **all** slice additions under `fixtures/dynamic_planning/`, `scripts/dynamic_planning_qualification.py`, `tests/test_dynamic_planning_*` (`m37_guard_disallowed.txt`) | A3 met |
| Slice tests | `pytest tests/test_dynamic_planning_*.py` | **102 passed** (report says 101; see D-7) | A8 partly |
| Qualification | `python3 -B scripts/dynamic_planning_qualification.py` (separate worktree) | 34/34; counters 0/34, 0/34, 0/16, 0/16, 0/34, 0/34; C33 miss 1/1; battery `2c366419…`, gate `f2dfc937…` (`qual_run_a.*`) | A4 met |
| Battery integrity | `git diff --quiet 44fa36e HEAD -- fixtures/dynamic_planning`; `44fa36e` ancestor of `4f7fe9d`; sha256 of every fixture | unchanged since the freeze commit; all digests equal report §2 | A4 met |
| Anchors | `python3 scripts/m33_3_r_anchors.py` | ok, changed [] | A5 met |
| Governance | `pytest tests/governance`; `uri_state_validator.py` | 37 passed; VALID | A5 met |
| M36/M37/M38 quals | `scripts/m36_memory_…`, `m37_edge_…`, `m38_harness_qualification.py` | exit 0 each; M37/M38 `gate_passed: true`; M36 wrong_confirmed 0, invented_ids 0 | A5 met |
| Review set | the 5-file review command from report §4 | 113 passed | A5 met |

The M36–M38 scripts rewrite tracked result files under `docs/plans/`; those rewrites were discarded in the audit worktree. The audit's own checkout is clean apart from this report.

## 3. Codex findings, re-verified

Probe script: `audit_probes.py`; raw output `audit_probes.txt` / `audit_probe_results.json`.

| Codex | Codex severity | This audit | Evidence |
|---|---|---|---|
| F1 driver accepts a changed battery via `--cases` | HIGH | **CONFIRMED, downgraded to LOW** | Probe F1: one description changed, exit 0, gate passed, result file records `battery_sha256=581a577b…` instead of `2c366419…`. Migration plan §2 requires the digests to be *recorded before the first qualifying run*; it does not require run-time enforcement, and the result JSON exposes the changed digest, so the substitution is detectable, not silent. Still worth hardening (refuse a battery/gate whose LF digest differs from the pinned value unless an explicit non-qualifying flag is passed). |
| F2 substituted adapter writes outside and still `VERIFIED` | HIGH | **CONFIRMED, MEDIUM, limitation needing Chetan's accept/reject** | Probe F2: replacing the `(inspect_structure, 1)` adapter with one that writes a file outside the workspace, then calls the real handler: `VERIFIED`, file exists. The runner checks contract metadata and qualification digest, not the identity of the injected callable (`runner.py:124-128`). It needs control of trusted in-process wiring, not proposal text, and it is the same class as M36's M-2 plus the shared retained limitation "no OS sandbox". Stage 2 (§2.5 "injected approved action adapters") assumes the adapters are trusted, but neither the plan nor the implementation report states this limitation. Options: document it as a retained limitation, or bind adapter identity (for example pin each adapter's `module:qualname` and code-object digest in the qualification record and check it in the runner). |
| F3 unexpected verifier exception escapes | MEDIUM | **CONFIRMED, MEDIUM; reachable through a real component** | Probe F3: `record_and_verify` raising `RuntimeError` escapes `PlanRunner.run`. Probe F3b: the real ledger's own error type `ResultVersionError` is a `RuntimeError` subclass (`uri_v1/results/version_ledger.py:42`; raised for "blob integrity failure", "unsupported ledger schema") and escapes the same way, because `runner.py:110` catches only `ValueError`/`OSError`. No false `VERIFIED`. |
| F4 "planning modules never open paths" is too broad | LOW | **REJECTED as a finding against the slice** | The implementation report and plans do not contain that wording (grep of the report, Stage 2 and Stage 3). Their actual claim, no `uri_v1.memory` import and sources reached only through the injected resolver, holds (A2). The file I/O Codex listed is the pinned qualification record, `bundle/plan.json`/`proposal.json` and the scratch report, all inside the qualification path or the run workspace. If the wording came from the audit brief, the brief was too broad, not the slice. |

## 4. New findings (areas Codex did not cover)

| ID | Severity | Location | Reproduction | Expected vs observed |
|---|---|---|---|---|
| **N1** | **MEDIUM** | `runner.py:148-154` (adapter call); root in frozen `officefile._read` | Probes N1-bad_crc / encrypted / bad_method: a user workbook in a registered root whose sheet member has a bad CRC, the zip encryption flag, or an unsupported compression method, bound by a normal C01 proposal | Expected: typed `NOT_ATTEMPTED` with `RUN_ABORTED`, as for `XLSX_NOT_ZIP`. Observed: `zipfile.BadZipFile`, `RuntimeError` and `NotImplementedError` escape `PlanRunner.run`; no `PlanOutcome`; the RunStore holds `RUN_STARTED` with **no terminal event** (probe N1x). Triggered by ordinary user data, not trusted code. No false `VERIFIED`. The repair belongs in the slice's runner (treat any adapter exception as a typed abort), not in frozen `officefile.py`. Whether the frozen M37 Edge path has the same gap was not checked (out of scope). |
| **N2** | **MEDIUM** | `provider_port.py:53-58` (`parse_raw`); `contracts.py:297-298` (`SemanticProposal.parse`) | N2a: provider text with 200k nested arrays → `RecursionError` escapes `FixtureProvider.propose` (and so `run_proposal`). N2b: `compile_proposal` on a dict nested 5000 deep → `RecursionError` from `canonical()`, which catches only `TypeError`/`ValueError` | Stage 2 §2.8 and the provider docstring say malformed output is "a typed no-completion". Observed: uncaught exception. Untrusted model output reaches this path. No false success. |
| N3 | LOW | `runner.py:72` | Build a `CompiledPlan` directly with an extra `inspect` node that feeds nothing (the compiler rejects the same proposal with `UNREACHABLE_OUTPUT/UNUSED_NODE`) | The runner's only plan gate is `isinstance(plan, CompiledPlan)`; it executed the unused node and returned `VERIFIED` (the oracle only walks from the writer). Same trusted-caller class as F2. Hardening: re-derive the plan from `proposal_sha256`/`snapshot_sha256`, or make `CompiledPlan` constructible only by the compiler. |
| N4 | LOW | `runner.py:98-101`, `156-162` | Writer writes the report, then returns an invalid output shape | Outcome `NOT_ATTEMPTED` with `executed` = all six nodes and `plan_report.json` left in scratch. No false success, but "NOT_ATTEMPTED" says nothing ran when every node ran. A distinct status or reason family for post-start aborts would be clearer. |
| N5 | INFO | `bindings.py` / frozen `Workspace.create` | Original mutated between `verify_source` and copy-in | `NOT_ATTEMPTED INPUT_NOT_CURRENT`. **Safe.** |
| N6 | INFO | `contracts.py:_text` | Sheet literal with U+202E (bidi override) or U+007F | Compiles (exact-match only, so no binding impact). Lone surrogate is rejected. Only matters if literals are later echoed to a UI. |
| N7 | INFO | `compiler.py` | `items` lists `cmp.comparison` twice | Compiles and verifies with the item duplicated. Harmless. |
| N8 | INFO | `provider_port.parse_raw` | 50 MB provider text | Fully parsed (~0.5 s) before the 64 KiB cap rejects it (`LIMIT_EXCEEDED/PROPOSAL_BYTES`). A real adapter should cap raw bytes before parsing. |
| N9 | INFO | `bindings.HandleTable.resolve` | Hand-built `Handle` | `HANDLE_FABRICATED`. **Safe.** (A caller in-process can still set the private sentinel; same trusted-code class as F2.) |
| D-7 | LOW (report accuracy) | report §4 | `pytest --co tests/test_dynamic_planning_*.py` | Report says 101 slice tests; 102 are collected and pass (1303 + 102 − 1 = 1404). The totals are right; the per-slice count is off by one. |

Probes that came back safe and match Codex: source ids only by the closed hex id (no paths, lookalikes, UNC, ADS), duplicate JSON keys refused, forged report content `NOT_VERIFIED`, stale candidate hash refused.

## 5. Self-review against the criteria

- A1–A5: met on rerun evidence.
- A6: met for untrusted proposals and user files. No probe produced a false `VERIFIED` from proposal text or source data. The two `VERIFIED`-despite-wrong cases (F2, N3) need control of trusted in-process wiring.
- A7: **not met.** N1 (user files), N2 (provider text) and F3 (real ledger error) escape as uncaught exceptions; N1 also leaves an orphan `RUN_STARTED`.
- A8: mostly met; D-7 is a count error; F2's trust assumption is undocumented.

Corrections made while drafting: my first N4 probe tripped the output ceiling on the first node rather than the writer, so it did not show what it was meant to show; I replaced it with the writer-shape probe above. Codex's F4 was first read as a report claim; the grep showed the wording is not in the repo, so I rejected it rather than confirming it.

## 6. Unverified

- Windows: not run here (Codex ran Windows and saw one extra, environment-limited failure in `tests/dev_workflow/test_visible_worker.py`). This does not change the verdict.
- The frozen M37 Edge path's handling of damaged zip members (N1's root cause) was not tested. That would be an M37 question and does not change this verdict.
- Real providers: none exist in the slice; semantic ability is unmeasured (disclosed in report §6.13).
- "Digests recorded before the first qualifying run": git proves that the freeze commit precedes the implementation commits. It cannot prove that no local run happened earlier. CLAIMED_ONLY; does not affect the verdict.

## 7. Verdict

**REPAIRS_REQUIRED** (small and local to the slice; no frozen file needed).

- Must repair: N1, N2, F3. Make `PlanRunner.run` end every started run in a typed `PlanOutcome` with a terminal run event, whatever an adapter or recording/verification step raises. Bound the nesting depth before JSON parsing and canonicalization, or treat `RecursionError` as `PROPOSAL_INVALID`.
- Chetan's decision: F2, accept it as a documented retained limitation (trusted adapters, no OS sandbox), or require adapter-identity binding.
- Hardening (optional): F1 run-time digest check, N3 plan re-derivation, N4 status wording, D-7 count fix, N8 raw-size cap.

What held: the untrusted-proposal compiler, closed source-id binding, DAG and type checks, per-node revalidation, handle discipline and the independent oracle. The qualification (34/34, six counters at 0) reproduces exactly. The frozen boundary is intact, and the only suite failure is the accepted guard.

## 8. Correction history

- **2026-09-29, audit evidence:** the committed probe script `dynamic_planning_slice1_audit/audit_probes.py` made the slice's own boundary test `test_no_existing_module_imports_planning` fail on this branch, because the test scans every `*.py` in the repo. The full-suite result in §2 was measured before the file was added, so it still stands for `c5d47a0`. The file was renamed to `audit_probes.py.txt` so it is not collected.
- **F2 status after the repair** (Chetan chose to close it; see implementation report §8): the rerun probe F2 gives `NOT_ATTEMPTED ADAPTER_NOT_QUALIFIED`, and the outside file is not written. The other probes are unchanged, except N4, whose buggy writer is now refused before it runs. That probe no longer shows what N4 describes; N4 remains a LOW observation about status wording. The residual limitations RL-1 and RL-2 are recorded there.
