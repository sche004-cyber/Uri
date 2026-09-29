# Dynamic Planning Slice 1: Independent Re-audit of Repair Round 1 (Claude, repository evidence)

Status of the audited slice: **PROVISIONAL / NOT FROZEN** (unchanged by this audit, whatever the verdict).
Audit only. No repair was made; no slice, frozen or live-app file was edited. This report and its evidence directory are the only additions.

- Target: `sche004-cyber/Uri`, branch `claude/dynamic-planning-slice1-2eemmh`, head `458cbda949db8b88c858a645911f057fb9e57bd7` (repair round 1).
- Previous audit: `b4eae6b` on `claude/project-thread-vhp2g6` (`docs/reviews/DYNAMIC_PLANNING_SLICE1_INDEPENDENT_AUDIT.md`), verdict REPAIRS_REQUIRED on `c5d47a0` / code `3bbf8f7`.
- Base: frozen line `5bbf738` (M36/M37/M38 CLOSED_FROZEN at `bd7c450`).
- Codex is paused; this is a Claude audit. The implementation report §8, the implementer's claims and project memory were treated as leads, not evidence.
- Environment: Linux, Python 3.11.15. `pytest`, `requirements.txt`, `google-api-python-client` and `google-auth-oauthlib` installed into the container (the last two are imported by two pre-existing test modules and not declared in `requirements.txt`; pre-existing, outside the slice). No network model, no spend.
- Evidence: `docs/reviews/dynamic_planning_slice1_reaudit/` (all runs COMPLETED_WITH_RESULT).

## 1. Acceptance criteria (defined before the checks)

| # | Criterion |
|---|---|
| B1 | Every file changed since `5bbf738` is a slice addition (`A`); the repair touches only slice files; `verify.py`, all frozen files and the battery/gate/fixtures are unchanged. |
| B2 | Full suite: the only failure is the accepted `tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged`, and it fails only on slice paths. |
| B3 | Qualification reproduces 34/34 with all six counters at 0 and the frozen battery/gate digests; anchors, governance (37 + validator), M36/M37/M38 qualification and the 113-test review set pass. |
| B4 | Each must-repair finding (F3, N1, N2) is fixed: the prior audit's own probes, rerun on `458cbda`, end in a typed outcome with a closed run record. |
| B5 | Each LOW finding (F1, N3, N4, D-7) is fixed or its state is reported accurately. |
| B6 | The repair introduces no new false-`VERIFIED` path and no new uncaught exception reachable from untrusted input (provider text, proposal, user files). |
| B7 | The new runner interface (plan re-derivation against a pinned snapshot) refuses tampered plans and does not refuse valid plans (no liveness regression). |
| B8 | The implementation report describes the repairs and F2 accurately. |

## 2. Reruns

| Check | Command | Observed | Criterion |
|---|---|---|---|
| File scope | `git diff --name-status 5bbf738 458cbda`; `git diff --name-status 3bbf8f7 458cbda` | 29 files, all `A`; repair modifies 9 files, all slice (`uri_v1/execution/planning/{contracts,provider_port,runner}.py`, 3 slice test files, driver, report, results JSON) | B1 met |
| verify.py / fixtures | `git diff --quiet 5bbf738 458cbda -- uri_v1/execution/verify.py`; `git diff --quiet 44fa36e 458cbda -- fixtures/dynamic_planning` | both empty | B1 met |
| Imports | grep of `uri_v1/execution/planning/` for `uri_v1.memory`; grep of the repo for importers of the package | only a docstring mention; no outside importer | B1 met |
| Full suite | `python3 -B -m pytest -q -p no:cacheprovider tests/` | **1418 passed, 1 failed, 9 skipped** (`full_suite.txt`) | B2 met |
| Guard content | the guard's own `git diff` against `179fe10` minus its allowlist | 17 paths, all under `fixtures/dynamic_planning/`, `scripts/dynamic_planning_qualification.py`, `tests/test_dynamic_planning_*` (`m37_guard_disallowed.txt`) | B2 met |
| Slice tests | `pytest tests/test_dynamic_planning_*.py` | **116 passed** (`slice_tests.txt`), matches report §8 | B5 met |
| Qualification | `python3 -B scripts/dynamic_planning_qualification.py --out …` in a separate worktree | exit 0; `qualifying: true`; 34/34; counters 0/34, 0/34, 0/16, 0/16, 0/34, 0/34; C33 miss 1/1; battery `2c366419…`, gate `f2dfc937…`. Result JSON equals the committed `DYNAMIC_PLANNING_SLICE1_QUALIFICATION_RESULTS.json` except latency/python/platform fields (`qual_run.*`) | B3 met |
| Anchors | `python3 scripts/m33_3_r_anchors.py` | ok, changed [] | B3 met |
| Governance | `pytest tests/governance`; `scripts/governance/uri_state_validator.py` | 37 passed; VALID | B3 met |
| M36/M37/M38 quals | the three qualification scripts | exit 0 each; M37/M38 `gate_passed: true`; M36 `wrong_confirmed` 0, `invented_ids` 0 | B3 met |
| Review set | 5-file review command from report §4 | 113 passed | B3 met |

The M36–M38 scripts rewrite tracked result files under `docs/plans/`; those rewrites were discarded in the audit worktree.

## 3. Prior findings, re-verified

Method: the prior audit's probe script (`prior_audit_probes_with_snapshot.py`), changed only to pass `snapshot=` to its one direct `runner.run` call, rerun on `458cbda` (`prior_probes_at_458cbda.txt`); plus the new probes in §4.

| Finding | Prior | Now | Evidence |
|---|---|---|---|
| F3 verifier-path exception escapes | MEDIUM | **FIXED** | F3 (`RuntimeError` from `record_and_verify`) and F3b (the real ledger's `ResultVersionError`) → `NOT_VERIFIED`. Code: `runner.py` catches any `Exception` around `record_and_verify` and closes the run unless a VERIFICATION event exists. |
| N1 damaged workbook crashes, run left open | MEDIUM | **FIXED** | bad_crc / encrypted / bad_method → `NOT_ATTEMPTED/ACTION_FAILED`, events `RUN_STARTED, RUN_ABORTED` (N1x shows no open run). |
| N2 deep nesting crashes the parser | MEDIUM | **FIXED** | N2a (200k nested arrays) → `PROPOSAL_INVALID`; N2b (5000-deep dict to `compile_proposal`) → `PROPOSAL_INVALID/NESTING_DEPTH`. The depth check (`contracts.nesting_exceeds`) is iterative, so it cannot itself recurse. |
| F1 changed battery accepted | LOW | **FIXED** | R1: changed battery → exit 2, no result file, `REFUSED` on stderr; `--non-qualifying` → exit 1, `status: NON_QUALIFYING…`, `qualifying: false`, `gate_passed: false`; a CRLF copy of the frozen battery still qualifies (LF-normalized digest). |
| N3 hand-built plan runs | LOW | **FIXED** | N3 (extra unused node) → `REJECTED/PLAN_NOT_COMPILED`, nothing executed, no run recorded. See §4 for the wider tamper set. |
| N4 NOT_ATTEMPTED after every node ran | LOW | **FIXED** | N4 → `NOT_VERIFIED/OUTPUT_TYPE_INVALID`, events `RUN_STARTED, RUN_ABORTED`. |
| D-7 test count | LOW | **FIXED** | Report §4 now says 102 at `3bbf8f7`, with the original number kept as history. |
| F2 swapped trusted adapter → outside write, VERIFIED | MEDIUM, Chetan's decision | **UNCHANGED, as intended** | Still reproduces (`status=VERIFIED outside_exists=True`). Recorded as retained limitation §6.14, "PENDING CHETAN'S CONFIRMATION". The description is accurate on mechanism and scope, with one attribution error (R-3 below). |
| N5, N9 | INFO safe | still safe | `INPUT_NOT_CURRENT`; `HANDLE_FABRICATED`. |
| N8 50 MB provider text | INFO | **FIXED** | `parse_raw` refuses raw text over 256 KiB before parsing. |

## 4. New probes against the repair

Scripts `reaudit_probes.py`, `reaudit_probes2.py`; output `reaudit_probes.txt`, `reaudit_probes2.txt`. Each runs in fresh temporary roots through the slice's own harness (real M36 log, sources, recorder, S11 ledger, RunStore, registered verifier).

| ID | Probe | Observed | Verdict |
|---|---|---|---|
| R2 ×5 | Valid C01 proposal written with reversed node order, reversed key order, a bare (unlisted) `items` ref, a duplicated `items` ref, and indented raw text, through `run_proposal` | all `VERIFIED` | Re-derivation has no liveness regression for these forms |
| R3 | Compiled C01 run with `raw_proposal` = a different proposal / unparseable text / the same proposal reformatted | `REJECTED PROPOSAL_DIFFERS` / `REJECTED PROPOSAL_DIFFERS` / `VERIFIED` | Holds |
| R3-huge | Same proposal padded past the 256 KiB raw cap | `REJECTED PROPOSAL_DIFFERS` | Consistent with the provider port, which would never have parsed it; INFO |
| R4 ×3 | `snapshot=None`, `snapshot` omitted, a snapshot object with a different `sha256` | `REJECTED SNAPSHOT_MISMATCH`, no run recorded | Holds |
| R5 ×6 | Hand-altered `CompiledPlan`: order swapped, `proposal_sha256` changed, literal changed, source hash zeroed, qualification digest zeroed, candidate list shrunk | all `REJECTED PLAN_NOT_COMPILED` (`PLAN_DIFFERS` or `COMPILER_UNKNOWN_SOURCE`), nothing executed, no run recorded | Holds |
| R6-snapprov | Live snapshot provider raises mid-run | `NOT_ATTEMPTED/RUNNER_ERROR`, `RUN_STARTED, RUN_ABORTED` | Holds |
| R6-store-abort | Run store refuses the RUN_ABORTED append | `NOT_ATTEMPTED`, reason `ACTION_FAILED\|RUN_NOT_CLOSED` | Holds (the outcome says the record is open) |
| R6-store-start | Run store refuses RUN_STARTED | `NOT_ATTEMPTED/RUN_RECORD_ERROR:OSError`, no run | Holds |
| R6-writer | Writer adapter raises before writing | `NOT_VERIFIED/ACTION_FAILED`, `RUN_ABORTED` | See R-2 (INFO) |
| R6b-logload | M36 log `load()` fails after the verifier persisted its verdict | outcome `NOT_VERIFIED/VERIFICATION_ERROR:RuntimeError`; RunStore holds `VERIFICATION` with `status: VERIFIED`, no `RUN_ABORTED` | See R-4 (INFO) |
| R6b-SystemExit / KeyboardInterrupt | Adapter raises a `BaseException` | escapes `PlanRunner.run`; RunStore ends at `RUN_STARTED` | See R-1 (LOW) |
| R7-raises | `provider.propose` raises | `NOT_ATTEMPTED/PROVIDER_UNAVAILABLE` | Holds |
| R7-none | `provider.propose` returns `None` | uncaught `AttributeError` from `run_proposal` | See R-5 (INFO) |
| R8 | `parse_raw` boundaries | exactly 256 KiB accepted, +1 byte refused, 4-byte characters counted as bytes, depth 16 accepted, 17 refused | Holds |

No probe produced a false `VERIFIED`. Every probe driven by untrusted input (provider text, proposal content, user files) ended in a typed outcome with a closed run record.

## 5. New observations (none blocking)

| ID | Severity | Location | Observation | Suggested handling |
|---|---|---|---|---|
| R-1 | LOW (claim accuracy) | `runner.py` module docstring | The docstring says "nothing an adapter … raises escapes" and "Once RUN_STARTED is appended, the run record always gets a terminal event". `SystemExit`/`KeyboardInterrupt` from an adapter (or a Ctrl-C during a run) escape and leave `RUN_STARTED` open (R6b). Not reachable from proposal text or user files, and no code can close a run on a hard process kill anyway. | Narrow the docstring to `Exception`, or add a `BaseException` clause that closes the run and re-raises. Optional. |
| R-2 | INFO | `runner.py` (`executed.append` before the adapter call) | A node whose adapter raises is counted as executed, so a writer that fails before writing gives `NOT_VERIFIED` ("attempted in full") rather than `NOT_ATTEMPTED`. Both are non-success and the reason (`ACTION_FAILED`) is accurate. | None needed. |
| R-3 | LOW (report accuracy) | report §6.14 | "The audit recommends accepting it as documented" is not what the previous audit said. That audit listed both options (document, or bind adapter identity) for Chetan's decision without recommending one. The recommendation came from the project coordinator's decision card. The rest of §6.14 (mechanism, trusted-wiring precondition, same class as M-2 / no OS sandbox, the alternative) is accurate, and F2 still reproduces exactly as described. | Correct the attribution when the report is next touched. |
| R-4 | INFO | `runner.py` verifier-path handler | If recording fails after the verifier has persisted a VERIFIED verdict (R6b-logload), the caller gets `NOT_VERIFIED` while the RunStore shows `VERIFICATION: VERIFIED` and no abort. This is the conservative direction (the returned status is weaker than the record; no false `VERIFIED` is returned) and matches report §8's wording ("unless the run already has a VERIFICATION event"). | None needed; a future UI should take status from the outcome or the verifier record consistently. |
| R-5 | INFO | `run_proposal` | A provider that returns a non-`ProviderResult` (R7-none) raises `AttributeError`. The provider object is trusted wiring; its text is what is untrusted, and malformed text is handled. | Optional: treat a non-`ProviderResult` as `PROVIDER_UNAVAILABLE` when a real provider adapter is added. |
| R-6 | INFO | `runner._refusal` | The pinned `snapshot` argument is trusted as given: the runner compares its `sha256` attribute with the plan, not with its content or with `snapshot_provider()`. A caller that fabricates both the plan and a matching snapshot object is the trusted-wiring class of F2 and N3. Per-node revalidation against the live snapshot (qualification and verifier-coverage digests) still runs in `_execute`. | None for slice 1. |

The frozen M37 Edge path's handling of damaged zip members (the root of N1) was again not tested; it is an M37 question and outside this slice.

## 6. Self-review against the criteria

- B1–B3: met on rerun evidence.
- B4: met. All three must-repair findings reproduce as typed outcomes with closed run records using the prior audit's own probes.
- B5: met. F1, N3, N4, D-7 fixed; the regression tests named in report §8 all exist (13 names checked) and pass. The only removed test lines replace the old `ValueError("COMPILED_PLAN_REQUIRED")` expectation with the new typed `REJECTED/PLAN_NOT_COMPILED` and add `snapshot=` to the helper; no assertion was weakened.
- B6: met. No new false-`VERIFIED` path; no uncaught exception from untrusted input. R-1 and R-5 need trusted code or a process interrupt.
- B7: met for the tampering set in R3–R5 and the valid-form set in R2. The only information a compiled plan drops (listed vs bare single ref on a multi-ref port) is enumerated in `_proposals_of`, and only the writer's `items` port has `max_refs > 1`, so at most one fork exists in this slice.
- B8: mostly met; R-3 is an attribution error and R-1 a docstring overstatement.

Corrections made while drafting (kept for the record):
- My first R1 run printed `DEFECT`. The probe reused one output path for the refusal run and the `--non-qualifying` run, and read `out.exists()` after the second run had written it. The refusal run itself reported `out_written=False` and exit 2. The repair holds; the probe was wrong.
- My first R6 SystemExit/KeyboardInterrupt probe reported "0 open runs" because it looked for per-run directories; the RunStore is one hash-chained JSONL per user. Re-read through the store (`reaudit_probes2.py`): the run is left at `RUN_STARTED`. That is R-1.
- My first R6b-logload run used a non-hex trace id, which the recorder refused before verification (`invalid opaque identifier`), so it did not test the intended path. Rerun with a valid trace id gives the result above.

## 7. Unverified

- Windows: not run. Does not change the verdict.
- Real providers: none exist in the slice; semantic ability is unmeasured (report §6.13).
- Whether any qualifying run happened locally before the battery freeze commit remains CLAIMED_ONLY (unchanged from the previous audit); does not affect the verdict.
- F2 remains open pending Chetan's decision; this audit only checks that it is described accurately.

## 8. Verdict

**ACCEPT** (repair round 1 on `458cbda`). The slice stays **PROVISIONAL / NOT FROZEN**.

- All three MEDIUM findings (F3, N1, N2) and all four LOW findings (F1, N3, N4, D-7) are fixed, with regression tests, and reproduce as fixed with the previous audit's own probes.
- Suite 1418 passed / 1 failed (only the accepted guard, only on slice paths); qualification 34/34 with six counters at 0 on the frozen digests; anchors, governance, M36–M38 quals and the review set pass; `verify.py` and every frozen file are unchanged against `5bbf738`.
- The new plan re-derivation refused every tampered plan tried, and still verified every valid form tried.
- Open, non-blocking: F2 (Chetan's decision), R-1 docstring overstatement, R-3 report attribution. Both text fixes can ride the next change to the slice.
