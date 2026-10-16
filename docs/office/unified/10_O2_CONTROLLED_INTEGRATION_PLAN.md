# URI Office O2: controlled canonical integration (owner decision OD-R4, 2026-10-16)

Milestone `URI-OFFICE-O2-INTEG`. Branch `milestone/office-o2-integration-20261016` (worktree
`D:\uri-dev\uri-office-integ`). Baseline: canonical `integration/git-sync-20261008` on `uri-repo`
(`https://github.com/sche004-cyber/Uri`), verified tip **`85f6a0ec`** on 2026-10-16.

## 1. What is integrated

The accepted O2 readiness candidate `candidate/office-o2-readiness-20261015` @ `76b0f600` (Codex R12 ACCEPT; live r4
34/34 PASS; records `08_` and `09_`), plus the O2 documentation commits `e92265aa` and `9b3209d0`. Its ancestry is the
whole Office line, none of which is in canonical yet:

| Part | Accepted at | Record |
|---|---|---|
| Office M1 (Sheets panel, cell-patch saving) | `6348b1b1` (lifecycle M1-c3 VERIFIED) | `docs/office/review-c*/` |
| Office M2 (new workbook from files, roles) | `f50ae1e3` (Codex R13 ACCEPT) | `docs/office/` ledger `b51a3912` |
| Lifecycle `test_setup` step (2b917cfc), reviewed inside M1-c2 (open LOW R1-04) | M1-c2 VERIFIED `0dbb7bda` | `docs/office/review-c2/` |
| URI Assist subpixel repair (`uri_assist/onscreen.py`, additive tests) | `e0b5c298` independent ACCEPT | `uri-office-assist-repair-qualification-20261013/` |
| O2 unified workspace + O2P (printing, off) | `b4ea0fae` (Codex R7 ACCEPT) | `07_O2_REAL_APP_QUALIFICATION.md` |
| O2 readiness repairs + Excel repairs | `76b0f600` (Codex R12 ACCEPT) | `08_OFFICE_CAPABILITY_AUDIT_AND_O2_READINESS.md` |

Not integrated here: any Word/PowerPoint authoring, Excel insert-rows/formatting completion, folder-access settings
(OD-R1) — each is its own milestone after this one (OD-A3/A4).

## 2. Reconciliation (merge `ad416156`)

Canonical moved 61 commits since the Office line's merge base `1b5423bc` (DEV-LIFECYCLE-3/3A, FCV-R recovery, answer
streaming fixes). Six files conflicted; all are governance or materializer tooling:
- `scripts/ws_frozen_check.py`, `scripts/ws_materialized_verify.py`, `scripts/phase2close_chain.py`,
  `tests/phase2a/test_frozen_core.py`, `tests/governance/test_materialized_output.py`: **canonical's version**. The
  Office line carried older copies of governance commits whose re-based equivalents are in canonical
  (`2e2e4d11`=`35679a8b`, `ba0281c8`=`3d2f8e55`, `cf2477a4`=`67985570`, `122d397f`=`f64e7aaf`, `aa232e36`=`5a7ac301`),
  and canonical adds the owner-authorized FCV-01/FCV-05 frozen amendments.
- `scripts/oi_materialize_test_runtime.py`: canonical's version plus the Office additions (Office paths in the
  materialized runtime, RUNTIME_MODULES check, declared-wheel install).

## 3. Acceptance criteria

| ID | Criterion | Evidence |
|---|---|---|
| I-AC1 | The integration commit descends from canonical `85f6a0ec` (fast-forward possible) and contains `76b0f600`, `e92265aa`, `9b3209d0` | `git merge-base --is-ancestor` |
| I-AC2 | Frozen boundary intact: `scripts/ws_frozen_check.py` ok, no unapproved protected change versus canonical | checker JSON |
| I-AC3 | Every conflict resolved as in section 2; nothing from canonical lost (diff of the merge against canonical touches only Office paths, the Office line's accepted non-Office parts listed in section 1, and the materializer additions) | `git diff 85f6a0ec <tip>` file list |
| I-AC4 | Combined regressions: every `tests/` suite on the candidate has no new failure against canonical `85f6a0ec` (by test id); Flutter suite passes; page JS passes | regression summaries, driver gates |
| I-AC5 | Driver-counted independent review (Codex, lifecycle driver) ACCEPT or ACCEPT WITH FINDINGS on the exact integration commit, focused on the reconciliation and on regressions to canonical | driver receipt |
| I-AC6 | Live UI requalification on the integration commit (O2 journeys, Brain mode, packaged runtime): no regression against r4 | UI qualification record |
| I-AC7 | Integration receipt written by the driver; `verify` OK; canonical moved only by fast-forward, only after I-AC1..I-AC6 | `receipt.json`, `RECEIPT.md` |

Not in scope: production deployment, Office freeze (OD-R4 says so).

## 4. Self-review

Every row names its evidence. The owner's authorization is conditional (OD-R4); the driver's integration step uses
it only after I-AC1..I-AC6 hold. A moved canonical before integration means a new merge and new review (I-AC1).
