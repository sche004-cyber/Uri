# Milestone Manager — handoff (living record)

This file is updated at every checkpoint so work can resume without chat history. Older checkpoints are kept.

## Identity

| Item | Value |
|---|---|
| Milestone | MILESTONE-MANAGER (roadmap P0 per owner prompt 2026-10-21; LDEC-001 in the rehearsal ledger) |
| Worktree | `D:/uri-dev/uri-milestone-manager` |
| Branch | `milestone/milestone-manager-20261021` (local only, not pushed) |
| Base | canonical `uri-repo/integration/git-sync-20261008` @ `ec2fab5493578a4f5a805642153d56b4d5ea59fa` (fetched 2026-10-21) |
| P0 records read (never modified) | `D:/uri-dev/uri-p0-audit`, branch `audit/p0-comprehensive-20261021` @ `8e1d6324` |
| Authorisation | research (original prompt) + full Lifecycle V3 development through independent acceptance (owner amendment 2026-10-21). Canonical integration needs a **separate** owner authorisation. |
| Parallel work | Lifecycle V3.1 session `v1-2e`, branch `milestone/lifecycle-v3-1-task-intelligence-20261021`, worktree `D:/uri-dev/uri-lifecycle-v31`; split agreed (LDEC-003): V3.1 owns tasks, MM owns milestones/roadmap/decisions/approvals; MM reads `task_ledger summary --json` (contract `uri-dev/task-ledger-contract/1`, exit 0 ok / 4 integrity failure / 3 refused / 2 error). V3.1 will message the contract commit hash. |

## How to resume

1. `git -C D:/uri-dev/uri-milestone-manager log --oneline ec2fab54..HEAD` and `git status`.
2. Read `docs/milestone_manager/ACCEPTANCE_CRITERIA.md`, then the latest file in `docs/milestone_manager/reviews/`.
3. Tests: `PYTHONPATH=. python -m pytest -c scripts/phase2d_pytest.ini --rootdir=. tests/dev_workflow/test_milestones.py -q -p no:cacheprovider`
   (`python -I` does not put the repo root on `sys.path` in this checkout; pre-existing, affects `test_lifecycle.py` too).
4. Rehearsal ledger (disposable): `D:/uri-dev/mm-ledger-rehearsal`;
   `python -m scripts.dev_workflow.milestones --home D:/uri-dev/mm-ledger-rehearsal resume MILESTONE-MANAGER --no-tasks`.

## Checkpoint log

| # | Date (UTC) | Commit | State | Next action |
|---|---|---|---|---|
| 1 | 2026-10-21 16:0x | — | worktree created; P0 registers read; lifecycle state dirs sampled | discovery |
| 2 | 2026-10-21 | `b00c43f4` | discovery, architecture, first implementation | tests |
| 3 | 2026-10-21 | `7ab9263c` | 49 tests pass; frozen check ok | docs + review |
| 4 | 2026-10-21 | `2ae7a79f` | data model, plan, rehearsal | independent review R1 |
| 5 | 2026-10-21 | (R1 repair commit, see `git log`) | **R1 = REJECT** (15 findings: 5 HIGH, 8 MEDIUM, 2 LOW), all repaired (`reviews/R1_REPAIR.md`); 77 MM tests pass | independent re-review R2 on the repair commit |
| 6 | 2026-10-21 | `4a54ebe1` | **R2 = REJECT** (14 new: 1 HIGH, 9 MEDIUM, 4 LOW; R1 11 fixed / 4 partial) | repair |
| 7 | 2026-10-21 | (R2 repair commit, see `git log`) | all R2 findings repaired (`reviews/R2_REPAIR.md`); 93 MM tests pass; R2 tests fail 16/16 on pre-repair code; N5 at `7ab9263c` 365 passed / 5 platform-gated / 0 failed; frozen check exit 0 | independent re-review R3; N5 re-run on the repair commit |
| 8 | 2026-10-21 | `5bce5bdf` | **R3 = REJECT** (8: 5 MEDIUM, 3 LOW; all R2 fixed) | repair |
| 9 | 2026-10-21 | (R3 repair commit, see `git log`) | R3 repaired (`reviews/R3_REPAIR.md`); 101 MM tests; R3 tests 8/8 fail pre-repair; N5 on `5bce5bdf` running (`D:/uri-dev/mm-gate-5bce5bdf`) | independent re-review R4 |
| 10 | 2026-10-21 | `c992b5ae` | **R4 = REJECT** (7: 4 MEDIUM, 3 LOW) | repair |
| 11 | 2026-10-21 | (R4 repair commit, see `git log`) | R4 repaired (`reviews/R4_REPAIR.md`); 111 MM tests; R4 tests 10/10 fail pre-repair; rehearsal re-run (P0 working copy now differs from `8e1d6324`, imported with commit None) | independent re-review R5 |
| 12 | 2026-10-21 | `7c8e0a29` | **R5 = REJECT** (9: 2 MEDIUM, 7 LOW); reviewer file-safety clean | repair |
| 13 | 2026-10-21 | (R5 repair commit, see `git log`) | R5 repaired (`reviews/R5_REPAIR.md`); 120 MM tests; R5 tests 10/10 fail pre-repair | independent re-review R6 |
| 14 | 2026-10-21 | `3ba9af68` | **R6 = REJECT** (5: 1 MEDIUM, 4 LOW); reviewer file-safety clean | repair |
| 15 | 2026-10-21 | (R6 repair commit, see `git log`) | R6 repaired (`reviews/R6_REPAIR.md`); 124 MM tests; R6 tests 4/4 fail pre-repair | independent re-review R7 |
| 16 | 2026-10-21 | `5b2a1427` | **R7 = REJECT** (3: 1 MEDIUM, 2 LOW); file-safety clean | repair |
| 17 | 2026-10-21 | (R7 repair commit, see `git log`) | R7 repaired (`reviews/R7_REPAIR.md`); 129 MM tests; R7 tests 5/5 fail pre-repair; N5 at `3ba9af68`: 436 passed / 5 platform-gated / 0 failed | independent re-review R8 |
| 18 | 2026-10-22 | `ddc4e63b` | **R8 = REJECT** (5: 3 MEDIUM, 2 LOW) in the R6/R7 recovery and init-host retry logic | simplify instead of patching |
| 19 | 2026-10-22 | (R8 repair commit, see `git log`) | R8 repaired by simplification (`reviews/R8_REPAIR.md`); 136 MM tests; R8 tests 8/9 fail pre-repair (the 9th, a 20-byte cut, was already handled) | independent re-review R9 |
| 20 | 2026-10-22 | `2fe3615f` | **R9 = REJECT** (3: 1 MEDIUM, 2 LOW); all R8 findings fixed | repair |
| 21 | 2026-10-22 | (R9 repair commit, see `git log`) | R9 repaired (`reviews/R9_REPAIR.md`); 144 MM tests; R9 tests 8/8 fail pre-repair | independent re-review R10 |
| 22 | 2026-10-22 | `1838e2df` | **R10 = REJECT** (2: 1 MEDIUM, 1 LOW); all R9 findings fixed except R9-03 partial | repair |
| 23 | 2026-10-22 | (R10 repair commit, see `git log`) | R10 repaired (`reviews/R10_REPAIR.md`); 148 MM tests; N5 at `ddc4e63b`: 445 passed / 5 platform-gated / 0 failed | independent re-review R11 |
| 24 | 2026-10-22 | `5bb005f6` | **R11 = REJECT** (5: 1 MEDIUM, 4 LOW); R10 findings fixed | repair |
| 25 | 2026-10-22 | (R11 repair commit, see `git log`) | R11 repaired (`reviews/R11_REPAIR.md`); 154 MM tests; R11 tests 6/6 fail pre-repair | independent re-review R12 |
| 26 | 2026-10-22 | `61b01ac4` | **R12 = REJECT** (3: 1 MEDIUM, 2 LOW); R11 all fixed | repair |
| 27 | 2026-10-22 | (R12 repair commit, see `git log`) | R12 repaired (`reviews/R12_REPAIR.md`); 158 MM tests; N5 at `1838e2df`: 460 passed / 5 platform-gated / 0 failed | independent re-review R13 |
| 28 | 2026-10-22 | `3da86259` | **R13 = REJECT** (3 MEDIUM, all from the R12 pre-batch design); reviewer stopped early after running a historical script with another reviewer's temp path (no repo/user data affected) | redesign |
| 29 | 2026-10-22 | (R13 repair commit, see `git log`) | record-then-refuse rule (`reviews/R13_REPAIR.md`, architecture §25); 162 MM tests; R13 tests 4/4 fail pre-repair | independent re-review R14 |
| 30 | 2026-10-22 | `b59c1f2a` | **R14 = REJECT** (2: 1 MEDIUM, 1 LOW); R13 all fixed; stress 2,847 reads 0 false alarms; N3 met | repair |
| 31 | 2026-10-22 | (R14 repair commit, see `git log`) | R14 repaired (`reviews/R14_REPAIR.md`); 165 MM tests; R14 tests 3/3 fail pre-repair; N5 at `61b01ac4`: 470 passed / 5 platform-gated / 0 failed | independent re-review R15 |
| 32 | 2026-10-22 | `255b9079` | **R15 = REJECT** (2: 1 HIGH regression from R14, 1 LOW); stress 2,966 reads 0 false alarms; N3 met | repair |
| 33 | 2026-10-22 | (R15 repair commit, see `git log`) | R15 repaired (`reviews/R15_REPAIR.md`); 167 MM tests; R15 tests 2/2 fail pre-repair | independent re-review R16 |
| 34 | 2026-10-22 | `f07da5d0` | **R16 = REJECT** (2 MEDIUM); R15 fixed; stress 2,445 reads 0 false alarms; N3 met | repair |
| 35 | 2026-10-22 | (R16 repair commit, see `git log`) | R16 repaired (`reviews/R16_REPAIR.md`); 178 MM tests; R16 tests 11/11 fail pre-repair; N5 at `b59c1f2a`: 478 passed / 5 platform-gated / 0 failed | independent re-review R17 |
| 36 | 2026-10-22 | `4f462be7` | **R17 = REJECT** (1 MEDIUM); R16 fixed; stress 2,278 reads 0 false alarms; N3 met | repair |
| 37 | 2026-10-22 | (R17 repair commit, see `git log`) | R17 repaired (`reviews/R17_REPAIR.md`); 179 MM tests; R17 test fails pre-repair | independent re-review R18 |
| 38 | 2026-10-22 | `c455dee2` | **R18 = REJECT** (2 MEDIUM, 1 LOW); R17 fixed; stress 2,714 reads 0 false alarms; N3 met | repair |
| 39 | 2026-10-22 | (R18 repair commit, see `git log`) | R18 repaired (`reviews/R18_REPAIR.md`); 182 MM tests; R18 tests 3/3 fail pre-repair; N5 at `f07da5d0`: 483 passed / 5 platform-gated / 0 failed | independent re-review R19 |
| 40 | 2026-10-22 | `dc22ece1` | **R19 = REJECT** (1 MEDIUM, 1 LOW); R18 fixed | repair |
| 41 | 2026-10-22 | (R19 repair commit, see `git log`) | R19 repaired (`reviews/R19_REPAIR.md`); 183 MM tests; R19 tests fail pre-repair | independent re-review R20 |
| 42 | 2026-10-22 | `e008d3ff` | **R20 = REJECT** (2 MEDIUM); R19 fixed | repair |
| 43 | 2026-10-22 | (R20 repair commit, see `git log`) | R20 repaired (`reviews/R20_REPAIR.md`); 186 MM tests; R20 tests 3/3 fail pre-repair | independent re-review R21 |
| 44 | 2026-10-22 | `8745a8d0` | **R21 = REJECT** (1 MEDIUM, 2 LOW); R20 fixed; full output-path sweep | repair |
| 45 | 2026-10-22 | `aa70a5ba` | R21 repaired (`reviews/R21_REPAIR.md`); 189 MM tests; N5 at `dc22ece1`: 498 passed / 5 platform-gated / 0 failed | independent re-review R22 |
| 46 | 2026-10-22 | `aa70a5ba` | **R22 = REJECT** (1 HIGH, 2 MEDIUM, 2 LOW); R21 fixed | repair |
| 47 | 2026-10-22 | `a28016d3` | R22 repaired (`reviews/R22_REPAIR.md`); 205 MM tests; R22 tests 16/16 fail pre-repair; frozen check exit 0; rehearsal re-run; N5 gate on `8745a8d0` stopped unfinished (superseded, not evidence) | independent re-review R23 |
| 48 | 2026-10-22 | `a28016d3` | **R23 = ACCEPT WITH FINDINGS** (3 LOW, 0 blocking; `reviews/R23_a28016d3.md`); N5 at `a28016d3`: 521 passed / 5 platform-gated / 0 failed (26 min, `evidence/devworkflow_a28016d3.log`); frozen check exit 0 | acceptance recorded |
| 49 | 2026-10-22 | (acceptance docs commit, docs only) | **INDEPENDENTLY ACCEPTED on `a28016d3`**; candidate isolated, not integrated | owner: integration authorisation; follow-up for R23-01..03 |

## Verification status (exact)

| Check | Status | Evidence |
|---|---|---|
| MM tests | COMPLETED_WITH_RESULT per candidate: 49 `7ab9263c`, 77 `4a54ebe1`, 93 `5bce5bdf`, 101 `c992b5ae`, 111 `7c8e0a29`, 120 `3ba9af68`, 124 `5b2a1427`, 129 `ddc4e63b`, 136 `2fe3615f`, 144 `1838e2df`, 148 `5bb005f6`, 154 `61b01ac4`, 158 `3da86259`, 162 `b59c1f2a`, 165 `255b9079`, 167 `f07da5d0`, 178 `4f462be7`, 179 `c455dee2`, 182 `dc22ece1`, 183 `e008d3ff`, 186 `8745a8d0` (each also re-run by the reviewer), 189 `aa70a5ba` (each also re-run by the reviewer), 205 on the R22 repair commit | reviewer re-runs on each candidate |
| R1 regression proof | COMPLETED_WITH_RESULT: new R1 tests on pre-repair code: 23 failed, 5 passed | `reviews/R1_REPAIR.md` |
| Frozen core (`scripts/ws_frozen_check.py`) | COMPLETED_WITH_RESULT at `7ab9263c`: ok; MM changes only add files under `scripts/dev_workflow/milestones/`, `tests/dev_workflow/test_milestones.py`, `docs/milestone_manager/` | `D:/uri-dev/mm-evidence/frozen_check_7ab9263c.log` |
| N5 full `tests/dev_workflow` regression | COMPLETED_WITH_RESULT at `7ab9263c`: 365 passed / 5 platform-gated / 0 failed (31 min); at `5bce5bdf`: 409 passed / 5 platform-gated / 0 failed (28 min); at `3ba9af68`: 436 passed / 5 platform-gated / 0 failed (28 min); at `ddc4e63b`: 445 passed / 5 platform-gated / 0 failed (29 min); at `1838e2df`: 460 passed / 5 platform-gated / 0 failed (29 min); at `61b01ac4`: 470 passed / 5 platform-gated / 0 failed (28 min); at `b59c1f2a`: 478 passed / 5 platform-gated / 0 failed (27 min); at `f07da5d0`: 483 passed / 5 platform-gated / 0 failed (28 min); at `dc22ece1`: 498 passed / 5 platform-gated / 0 failed (27 min). To be re-run on the accepted commit. | `evidence/devworkflow_7ab9263c.log`, `evidence/devworkflow_5bce5bdf.log`, `evidence/devworkflow_3ba9af68.log`, `evidence/devworkflow_ddc4e63b.log`, `evidence/devworkflow_1838e2df.log`, `evidence/devworkflow_61b01ac4.log`, `evidence/devworkflow_b59c1f2a.log`, `evidence/devworkflow_f07da5d0.log`, `evidence/devworkflow_dc22ece1.log` |
| Migration rehearsal | COMPLETED_WITH_RESULT, re-run on every repair commit (event count changes as the P0 working copy changes; see the file) | `evidence/rehearsal/verify.json`, `import_reports.json` |

## Open questions for the owner (not blocking development)

- Promote a ledger as authoritative, and where (rehearsal AP-12).
- Is P11 Multi-Client Deployment still on the roadmap (rehearsal AP-11)?
- Integration: P0 prerequisites unreconciled (P0 branch unpushed, OPEN-09; POL-P0-1 / OPEN-05 decides whether subagent acceptance counts for canonical). Canonical integration needs separate authorisation.

## Acceptance (2026-10-22)

| Item | Value |
|---|---|
| Accepted candidate | `a28016d3ae153ed460dc13375fc4202a5c4c8694` (code); later commits on the branch change only `docs/milestone_manager/` |
| Review | R23, fresh isolated subagent (assurance SUBAGENT, allowed by the owner amendment), COMPLETED_WITH_RESULT, ACCEPT WITH FINDINGS, BLOCKING_OPEN 0 |
| Review history | 23 rounds; R1-R22 REJECT, each repaired with regression tests (see `reviews/`) |
| Tests | 205 MM tests; full `tests/dev_workflow` 521 passed / 5 platform-gated (Linux only) / 0 failed on `a28016d3` |
| Frozen core | `scripts/ws_frozen_check.py` exit 0; additions only against `ec2fab54` |
| Open non-blocking | R23-01 (autocommit with non-ASCII ledger path or `diff.relative`), R23-02 (CANDIDATE_CHANGED fingerprint keys), R23-03 (resume notice length) |
| Integration | NOT integrated. Prerequisites still open: P0 branch unpushed (OPEN-09), POL-P0-1 (OPEN-05, whether subagent acceptance counts for canonical), separate owner integration authorisation |

## Correction (2026-10-22, later the same day)

The Acceptance section above is superseded and kept for history. The owner restated that the Lifecycle V3 driver
review is primary; R23 was a subagent review without a driver NO_INDEPENDENT_REVIEWER on a28016d3, so it did not
qualify. The driver then REJECTED a28016d3 with HIGH secret-refusal findings. Runs d1-d4, the fallback reviews FB,
FB2 and FB3 and their repairs are recorded in `reviews/DRIVER_RUNS_d1_d4.md` and `reviews/FB*_*.md`. The candidate
moved to branch `review/milestone-manager-a28016d3` (worktree `D:/uri-dev/mm-driver-a28016d3`). The milestone is
NOT accepted until a driver review, or a fallback review on a commit with a driver NO_INDEPENDENT_REVIEWER, accepts
the exact candidate and the gates pass.

| # | Date | Commit | State | Next action |
|---|---|---|---|---|
| 50 | 2026-10-22 | a28016d3 | driver d1 REJECT (8 rounds), BUDGET; owner: manual default-deny + budget 12 | d2 |
| 51 | 2026-10-22 | f76c2e17 | d2 REJECT x2 then NO_INDEPENDENT_REVIEWER; fallback FB REJECT | repair de0354ef |
| 52 | 2026-10-22 | de0354ef | d3 NO_INDEPENDENT_REVIEWER; fallback FB2 REJECT; owner: bounded F16 contract | repair 4aa3d40b |
| 53 | 2026-10-22 | 4aa3d40b | d4 NO_INDEPENDENT_REVIEWER; fallback FB3 REJECT (5 blocking) | repair FB3-01..06 + docs; driver d5 / fallback FB4 |
| 54 | 2026-10-22 | 1483a4ea | d5 NO_INDEPENDENT_REVIEWER; fallback FB4 REJECT (FB4-01 regression, FB4-02/03) | repair FB4 |
| 55 | 2026-10-22 | (FB4 repair, see `git log`) | FB4-01..06 repaired; 469 MM tests; frozen check to run on the commit | driver d6 when Codex returns (~13:38 IST), else fallback FB5; gates |

## Verification after the driver runs (living)

| Item | Value |
|---|---|
| Current candidate | head of `review/milestone-manager-a28016d3` (see `git log`) |
| MM tests | 469 passed on the FB4 repair commit |
| Full gates (dev_workflow; oi+ws; a2ui/assist/ssrf/web; ws_frozen_check) | not yet completed on a current candidate; runs on earlier candidates were stopped as superseded and marked "not evidence" in `D:/uri-dev/mm-evidence/gate_*` |
| Open LOW (non-blocking) | R23-01 (autocommit with non-ASCII ledger path or `diff.relative`), R23-02 (CANDIDATE_CHANGED keys not in the fingerprint), R23-03 (resume notice length), FB3-07 (crafted edge cases), FB3-08 (malformed hash-valid event makes the fold raise), FB3-10 / FB2-07 (prose false positives), FB4-06 remainder |
| Accepted | NO |

## Primary-path acceptance and integration preparation (2026-10-22)

| # | Date | Commit | State | Next action |
|---|---|---|---|---|
| 56 | 2026-10-22 | 10d07848 | gates: dev_workflow 785/0, oi+ws 793/0, a2ui/assist 25 failures identical on baseline ec2fab54 (node playwright missing), frozen ok | driver d6 |
| 57 | 2026-10-22 | f5347587 | driver d6 VERIFIED: Codex R4 ACCEPT WITH FINDINGS, gates no new failures; blocked only at fast-forward (based on ec2fab54) | owner go-ahead (2026-10-22) to merge onto canonical |
| 58 | 2026-10-22 | (integration candidate, see `git log`) | f5347587 + these records merged with canonical 38a6d124 on branch integ/milestone-manager-on-38a6d124 | v2 driver run d7 to VERIFIED, then owner integration authorisation |

Open LOW at f5347587: R23-01, R23-02, R23-03, FB2-05, FB2-07, FB3-07, FB3-08, FB3-10, FB4-06 (and D6 R4 findings, see
the d6 receipt). Canonical integration is not authorised (owner directive 2026-10-22).
