# LIFECYCLE-GITCTL-V2 - git control digest v2 (plan and acceptance)

Owner instruction 2026-10-22 (P0 closure session): unblock the two false-alarm driver blocks, then port the fix,
without overlapping other threads. Classification: P0 `docs/audit/p0_20261021/P0_CLOSURE_20261022.md` item I-5,
decision DEC-095 (no duplicate reviewer system: only the digest change is ported from `67d45317`, none of its
reviewer-tier code).

## Problem (evidence)

`git_control_digest` hashes every file under the shared repository's `.git/info/`. `git repack` (run by any
session's auto-gc) calls `git update-server-info`, which rewrites `.git/info/refs` and `.git/objects/info/packs`.
These files only serve dumb HTTP/FTP transports; git never reads them for local behaviour. Recorded false TAMPER /
EVIDENCE stops: LIFECYCLE-V3-1 r1 (2026-10-21 16:55:25Z, repair refused), r4 (22:30:04Z), r6 (2026-10-22 04:15:59Z,
EVIDENCE after ACCEPT and gates), MILESTONE-MANAGER-d1 (04:18:03Z). In each case hooks, control config, user/system
git config, replace refs, reviewer CLI and policy were unchanged.

## Change

`scripts/dev_workflow/lifecycle.py` only (plus a new test file):
1. `GENERATED_INFO = {"refs", "packs"}`; `git_control_digest(repo, legacy=False)` leaves those two `info/` files out;
   `legacy=True` gives the v1 digest unchanged.
2. `control_state()` binds `git_control_v2` instead of `git_control`.
3. `control_drift()`: a run whose anchor has no `git_control_v2` (bound with v1) is compared with the v1 digest,
   exactly as before.
4. `run()`: such a run is re-bound (`CONTROL_ANCHORED` with `git_control_v2`) only when it shows no drift at that
   moment; a run with drift is never re-bound.
5. The repair-window check and the review integrity snapshot use the v2 digest (same function before and after).

Not changed: what else is bound (hooks, non-routine config, `info/exclude`, `info/attributes`, `info/grafts`,
user/system git config and attribute/ignore files, replace refs, reviewer executable, managed policy), any review,
acceptance, gate, integration or owner-authorisation rule. No PROTECTED path (`ws_frozen_check`).

## Acceptance criteria

- AC-1 A rewrite of `.git/info/refs` or `.git/info/packs` alone is not control drift for a v2-bound run.
- AC-2 Any change of another `.git/info/` file (e.g. `exclude`, `attributes`) is still drift.
- AC-3 Every other control input keeps its v1 behaviour (existing tests in `tests/dev_workflow` pass unchanged).
- AC-4 A v1-bound run is compared with the v1 digest; it is upgraded to v2 only when clean, never over a drift.
- AC-5 The v1 digest (`legacy=True`) is byte-for-byte the previous function.
- AC-6 Tests: new `tests/dev_workflow/test_lifecycle_git_control_v2.py` (5 tests; 4 fail on canonical `2aa0141e`,
  the `info/attributes` guard passes on both); full `tests/dev_workflow` passes.
- AC-7 `ws_frozen_check` clean; only `scripts/dev_workflow/lifecycle.py`, the new test file and this document change.
- AC-8 Runs already in progress with the old driver copy are not affected (they use their own driver checkout).

## Evidence before review

| Item | Result |
|---|---|
| Candidate | `c9f3953c` on `repair/lifecycle-git-control-v2-20261022`, base canonical `2aa0141e` |
| New tests | 5 passed on `c9f3953c`; on `2aa0141e` 4 failed, 1 passed |
| Full `tests/dev_workflow` on `c9f3953c` | 321 passed, 5 skipped (Linux-gated), 0 failed, 25 min |
| `ws_frozen_check` | `unapproved_protected_changes: []` |
| Overlap | no active branch (V3.1, Milestone Manager) modifies `lifecycle.py` or the new test file |

## Review

Lifecycle V3 driver, Codex primary, `claude_cli` fallback (DEC-095). Started after the Milestone Manager d2 run
releases Codex capacity. Integration needs separate owner approval.

## Follow-up after fallback review FB1 (2026-10-22, owner directive: G1-02 investigation and regression test)

FB1 (ACCEPT WITH FINDINGS on `3def4023`, record `D:/uri-dev/lifecycle/LIFECYCLE-GITCTL-V2/fallback/FB1_subagent_3def4023.txt`)
raised three LOW findings. This follow-up, on branch `repair/lifecycle-gitctl-g1-02-single-read-20261022` cut from the
integration candidate `38a6d124` (V3.1 `4ef707ba` + `3def4023`), handles them:

- **G1-02 (code) - repaired.** Investigation: a v1-bound run read the control files three times on resume
  (`control_state` for v2, `control_drift` for the legacy digest, then the upgrade for the value it binds), so a
  change between reads could be bound without being compared. New `git_control_digests(repo)` returns both digests
  from one read; `control_state`/`control_drift` accept those digests; the upgrade in `run()` compares and binds from
  the same read. `git_control_digest` keeps its signature and values. Tests:
  `test_both_digests_come_from_one_read_and_match_the_single_digests`,
  `test_g1_02_upgrade_binds_the_state_it_compared_not_a_later_read` (simulates a change landing after the first read:
  the bound v2 value is the compared state and the later change is still caught as drift).
- **G1-01 (documentation) - corrected.** `git update-server-info` writes `.git/info/refs` and
  `.git/objects/info/packs`; the latter was never bound by v1. `packs` stays in `GENERATED_INFO` defensively; the code
  comment now says so.
- **G1-03 (documentation) - recorded.** A state directory planned or owner-unblocked by a v2 driver has no
  `git_control` key; a pre-v2 driver copy resuming it stops with a false GIT_CONTROL tamper (fail closed, never a
  bypass). Rule: once a run has been touched by a v2 driver, resume it only with a v2 (or later) driver copy.
