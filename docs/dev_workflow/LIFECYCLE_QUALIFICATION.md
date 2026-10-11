# uri-development-lifecycle — qualification record

Append-only. Criteria: `LIFECYCLE_PLAN_AND_ACCEPTANCE.md` (L-AC1..L-AC20).

## 1. Automated tests (DEVTEST fixtures, scripted worker processes)

`python -m pytest tests/dev_workflow` → 114 passed (90 pre-existing AO-4 + 24 lifecycle), 2026-10-11, Linux.
Scripted processes prove the deterministic guarantees; they do not prove reviewer independence.

| Criterion | Test(s) |
|---|---|
| L-AC1 | `test_illegal_transition_is_refused` |
| L-AC2, L-AC3 | `test_scripted_reviewer_never_verifies_a_real_milestone`, `test_missing_reviewer_cannot_accept_and_rounds_are_bounded`, `test_reviewer_that_touches_the_implementation_worktree_is_not_independent`, `test_imported_accept_is_never_evidence` |
| L-AC4 | `test_reviewer_label_accept_with_high_finding_is_reject` |
| L-AC5, L-AC7, L-AC8, L-AC13 | `test_defect_rejected_repaired_reaudited_and_integrated`, `test_imported_reject_is_routed_to_repair`, `test_regression_proof_rules`, `test_repair_without_regression_test_is_not_committed` |
| L-AC6, L-AC12 | `test_repair_touching_protected_path_is_refused_and_stops`, `test_owner_decision_finding_stops_and_unblock_resumes`, `test_integration_without_owner_authorisation_stops_with_command` |
| L-AC9 | `test_same_finding_after_three_repairs_stops` |
| L-AC10, L-AC11 | `test_new_gate_failure_prevents_integration`, `test_gate_failure_is_routed_to_repair_and_then_reaudited`, `test_compare_by_identity_and_cause`, `test_flutter_machine_parser` |
| L-AC14 | `test_interrupted_run_resumes_and_tampering_cannot_skip_gates`, `test_forged_stage_without_evidence_is_blocked` |
| L-AC15 | `test_verify_detects_rewritten_verdict` |
| L-AC16 | `test_status_surface_is_valid_a2ui` |
| L-AC17 | `test_gpu_gate_without_lease_blocks` |
| process cleanup | `test_worker_timeout_kills_the_process_group` |

## 2. Live demonstration with real separate Claude processes (L-AC18)

`python -m scripts.dev_workflow.lifecycle_demo <dir>`; reviewer and implementer = `claude -p` (`claude_cli`,
model claude-opus-5-5; the CLI also reports internal claude-haiku-5-5 usage). Evidence under
`evidence/lifecycle_demo_*` (prompts, raw results, round/repair records, event chains, receipts).

**Demo 1 (2026-10-11T00:2xZ) — exposed a driver defect; stopped by the coordinator.** The real reviewer R1
REJECTed the defective candidate with two blocking findings (the defect, and missing test coverage for `feature()`).
The implementer added `tests/test_feature.py`, which correctly passes before and after a coverage repair; the driver
demanded that *every* test file fail before, and also treated a reviewer finding's file (`pkg/feature.py`) as a gate
test, so it refused the repair twice. Correction: every regression test must pass after; at least one must fail
before when a code/security defect is addressed; only gate findings name existing tests that must each fail before
(`test_regression_proof_rules`). The run was stopped (incomplete state kept as evidence).

**Demo 2 (2026-10-11T00:3xZ) — passed, on the driver as of that time** (before three later hardening changes:
implementation-worktree integrity snapshot, process-group kill on timeout, Flutter test ids from `root_url`):

| Step | Result |
|---|---|
| R1 reviewer, session `d8c73ae5-68d9-4086-b8a7-612aca42ca44`, candidate `a67c0b7` | REJECT (R1-01 HIGH divide by zero; R1-02 HIGH missing tests; R1-03 LOW) — independent: separate process, integrity OK |
| P1 implementer, session `72295bdd-7a54-468b-b9ca-c1dd2fc9d485` | changed `pkg/calc.py`, `tests/test_calc.py`, `tests/test_feature.py`; `test_calc.py` failed before (exit 1) and passed after; driver committed `7e7079c`; `core/` untouched |
| R2 reviewer, session `65e6d9bd-eff8-405e-a385-c8b9934aca0a`, candidate `7e7079c` | ACCEPT — fresh session, different SHA from R1 |
| Gates | `unit`: no new failures vs baseline |
| Integration, not authorised | BLOCKED `OWNER_AUTHORIZATION`, needs `git push origin 7e7079c…:refs/heads/canon`; remote unchanged |
| Missing reviewer (separate state) | WAITING_FOR_MODEL, verdict null — no ACCEPT |
| Owner authorisation (DEVTEST simulation) + `unblock` + `run` | fast-forward, remote `canon` `b12e845` → `7e7079c` verified by `ls-remote`; COMPLETE |
| `verify` | chain OK, no errors |

## 3. Independent review of the skill itself (L-AC20)

Run by the skill's own driver (pinned copy at the reviewed commit) with config `DEV-LIFECYCLE-1`; state, raw
outputs and receipts under `evidence/DEV-LIFECYCLE-1/` (copied after the run).

### R1 — candidate `12ac37a`, reviewer `claude -p` session `5cc2696e-28a7-46c2-af07-53e9acf39f25` (00:38-00:42Z)

Reviewer verdict **REJECT**, 4 HIGH + 4 MEDIUM blocking, 4 LOW, each with a working probe:
R1-01 a `binary` override let any executable act as an independent `claude_cli` reviewer for a real milestone
(probe reached COMPLETE and pushed); R1-02 evidence was read from `state.json` — an edited verdict reached VERIFIED
and `verify` passed; R1-03 a worker-planted git pre-commit hook smuggled out-of-scope and protected files into the
driver's repair commit; R1-04 a crashed/empty pytest or Flutter run passed its gate; R1-05 gates ran in the dirty
implementation worktree; R1-06 a detached worker child wrote after the integrity snapshot; R1-07 a refused repair
left staged files; R1-08 a regression-test timeout crashed the driver mid-FIXING; R1-09 lenient severity parsing;
R1-10 `_TEST` substring treated as DEVTEST; R1-11 gate timeouts left process trees; R1-12 docs over-claimed.
**These disprove first-version claims in this record (§1 rows L-AC2, L-AC10, L-AC14, L-AC15) and in
`URI_DEVELOPMENT_LIFECYCLE.md`; the earlier text is kept above as history and corrected by this section.**

The driver recorded the round as NOT_INDEPENDENT ("refs changed during review"). Cause, established by the
coordinator from the reflog: the coordinator's own commit `2250a3e` on the unrelated branch
`milestone/a0-assist-foundation-20261010` at 00:38:12Z. The refs snapshot covered every local branch — a false
positive (coordinator finding **C1**). The conservative outcome (no ACCEPT credit) was correct; the findings are
valid and were repaired.

Repairs were made by the skill's implementation session (the coordinator), not by the driver's implementer worker,
because the driver's repair path itself was among the defects (R1-03, R1-06, R1-07, R1-08). Each finding has a
regression test in `tests/dev_workflow/test_lifecycle.py` (`test_r1_01_*` … `test_r1_10_*`, `test_c1_*`,
`test_regression_proof_rules` for R1-08); R1-11 is covered by the shared process-group runner; R1-12 by the revised
docs. The repaired commit is re-reviewed by a fresh reviewer process (R2 below).

### R2–R5 — automatic loop (driver pinned at `d5fccdf`)

| Round | Candidate | Reviewer session | Verdict | Blocking | Repair (separate implementer process) |
|---|---|---|---|---|---|
| R2 | `d5fccdf` | fresh `claude -p` | REJECT | 5 (R2-01 forged duplicate round + resume_to; R2-02 git replace refs hide a protected change; R2-03 rewritten .git gitfile redirects the reset; R2-04 deleted test crashes the proof; R2-05 GPU lease busy treated as failure) | P1 → `c1ba808` |
| R3 | `c1ba808` | fresh | REJECT | 4 (redirected HEAD; cached non-completed baseline; resume after candidate move; config re-read every run) | P2 → `4346715` |
| R4 | `4346715` | fresh | REJECT | 1 (policy binding must cover the resolved protected list) | P3 → `6bcfd1d` |
| R5 | `6bcfd1d` | fresh | REJECT | 2 (gate-finding proof for class tests and Flutter; non-deterministic baseline keys) | P4 refused (see C2) |

All R2–R5 rounds are independent (separate process, fresh session, integrity verified). Findings narrowed each round
(5 → 4 → 1 → 2, none repeated more than once).

**C2 (coordinator finding, 02:0xZ).** P4 was refused because the driver treated the fixture helper
`tests/dev_workflow/lifecycle_fixture/worker.py` (under `tests/`, not a test file) as a regression test; pytest on it
exits 2. The retry would hit the same wall, so the coordinator stopped the run (driver PID and the implementer's
process group), saved the interrupted attempt's partial diff (`lifecycle-runs/DEV-LIFECYCLE-1/interrupted/
P5_partial.diff`, not committed, not recorded in state) and reset the worktree to `6bcfd1d`. Repair: only files
matching `regression_test_patterns` are proofs (`test_c2_helper_files_under_tests_are_not_regression_proofs`).

**Owner directive 2026-10-11 (continuation policy).** The fixed six-round stop was replaced by the evidence-based
continuation policy (L-AC22), implemented by the implementation session together with the visual report (L-AC21)
and C2 as an isolated change on this branch; the R5 findings stay pending for the driver's implementer worker, and
the whole branch is re-reviewed by fresh reviewer processes.

**Repair after the post-directive review (R1 of the re-review at `fbac437`).** The fresh reviewer reported four
blocking findings; the earlier R5 gate-proof finding was among them (still unrepaired at `fbac437`). Repairs, each with
a regression test in `tests/dev_workflow/test_lifecycle.py` (`test_r1r2_*`):
R1-01 the verdict is parsed from the worker's in-memory result, and `verify` re-derives every round's result from the
hashed raw output and checks `reviewer_result.txt` (a lingering `setsid` child can no longer turn a REJECT into ACCEPT;
the earlier §6 claim that such writes were caught by the clean-worktree checks was wrong for `state_dir` and is
corrected); R1-02 malformed `findings` make the result unparseable (NO_RESULT), never ACCEPT; R1-03 gate test ids
(junit classnames, Flutter paths relative to the gate `cwd`) are resolved to files, and an unresolvable gate test
refuses the repair; R1-04 hooks/config/`info/` and replace refs are bound at PLAN and any drift is BLOCKED (TAMPER),
including drift by the diagnosis worker. The R5 non-deterministic-baseline-key finding is not part of this repair.

### DEV-LIFECYCLE-1b (fresh state directory, driver pinned at `fbac437`)

| Round | Candidate | Reviewer session | Verdict | Blocking | Repair |
|---|---|---|---|---|---|
| R1 | `fbac437` | `91871433-89e7-479f-80e2-e1e97327c314` | REJECT | 4 (R1-01 HIGH verdict read from an unbound mutable result file; R1-02 malformed findings dropped; R1-03 gate proof for class/Flutter ids; R1-04 control-file baseline not anchored) + 5 LOW | P1 → `1f720ed` (separate implementer process) |
| R2 | `1f720ed` | `8900cfe1-e72c-4080-8460-a93c7f0eaa3e` | **ACCEPT WITH FINDINGS** | 0 (R2-01 MEDIUM non-blocking, R2-02 LOW) | — |

Gates on `1f720ed`: `dev_workflow` no new failures vs baseline; protected paths unchanged; receipt chain verified;
stage VERIFIED (integration policy `none`).

**Follow-up before integration (implementation session).** Two accepted findings would make the skill unusable
where it is meant to run: R2-02 (on Windows every hashed file is newline-translated, so every round fails verify)
and R2-01 (routine branch-tracking writes by other sessions to the shared git config read as TAMPER). Both repaired
with regression tests (`test_r2_01_*`, `test_r2_02_*`); the new commit is re-audited by a fresh reviewer before
canonical integration under owner decision D1. The other LOW findings (R1-05..R1-09) stay documented limitations.

**Correction (R3-01, re-audit of `39ed499`).** The R2-01 allowlist was too wide: it also ignored
`remote.<r>.fetch`, `mirror`, `tagopt` and `pruneTags`. A worker could add a fetch refspec mapping the target onto
another session's branch, pass the control-state check, and the integration fetch then force-moved that branch.
Repair: only `branch.*` and `remote.<r>.prune`/`skipDefaultUpdate` remain routine (fetch refspec, mirror, tagopt and
pruneTags changes are TAMPER again), and the integration fetch writes no local ref at all
(`git fetch --refmap= --no-tags --no-prune --no-write-fetch-head <remote> refs/heads/<target>`). Regression tests
`test_r3_01_*`.

## 4. DEV-LIFECYCLE-2 — Windows support and canonical remote (2026-10-11)

Plan and criteria: `DEV_LIFECYCLE_2_PLAN_AND_ACCEPTANCE.md` (DL2-AC1..AC12). Findings F1-F3 and L1-L3 came from an
independent review on the owner's Windows 11 PC.

### Linux (cloud session), candidate tests before the independent review

`python -m pytest tests/dev_workflow` → 212 passed, 5 skipped. The 5 skipped are the `windows_only` tests, listed by
name under "PLATFORM-GATED ... NOT VERIFIED on linux" in the summary (not silent skips). New tests:
`test_lifecycle_remote.py` (F1, F3; all 11 fail on `ce1a90c`, F1 with the PC's `AttributeError: module 'os' has no
attribute 'killpg'`) and `test_lifecycle_platform.py` (F2 logic with a fake kernel32: 9, plus the 5 Windows-only).

### Independent review

Recorded by the driver in the milestone's state directory; summarised here after the run.

### Windows (owner's PC)

First gate on the PC (Windows 11, Python 3.13.15, 2026-10-11), `python -m pytest tests/dev_workflow`:

| Commit | Failed | Passed | Skipped |
|---|---|---|---|
| `ce1a90c` (canonical baseline) | 72 | 114 | 6 |
| `f3706e03` (F1-F3, L1-L3) | 17 | 194 | 6 |

No new failure; 55 baseline failures fixed; all 25 new DL2 tests passed, including the 5 real Job Object tests. The
remaining 17 failures and 6 silent "Linux-only" skips became findings W-1..W-3 (plan, "Added after the first Windows
gate"), repaired on the PC in the commit after `f3706e03`: 10 new tests in `test_lifecycle_windows_cli.py` (all fail
on `ce1a90c` for their own reason), portable fixtures, a `linux_only` marker reported by name. The test of a reviewer
that leaves a detached forger behind (`test_r1r2_01_*[True]`) now runs on Windows against real Job Objects.

The gate counts on the exact candidate SHA after that repair, the independent review and the real DEVTEST round are
recorded in the milestone receipt; until they are, Windows stays NOT VERIFIED. A failure is recorded as NOT VERIFIED,
never as a pass.
