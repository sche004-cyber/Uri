# Integration receipt — G1-02 follow-up (git-control digest single read) (2026-10-23)

Authority: owner decision OPEN-21 (2026-10-22): evidence-based evaluation and conditional integration; require
independent exact-commit acceptance, regression evidence, frozen-Core integrity and the existing lifecycle gates.
Push approved through the session's permission prompt; fast-forward; no force-push.

| Item | Value |
|---|---|
| Canonical before | `8ff6186b7c42bc4e8f997ba38b4581dc9fc5a20e` (re-checked with `ls-remote` immediately before the push) |
| Canonical after | `b19442000414ae833eee7097a7082aed4bb4d854` (`ls-remote` 2026-10-23T02:43:48Z) |
| Reviewed code | `ac3dcbae357393bb507ff2e6c716e2e50666c27a` (branch `repair/lifecycle-gitctl-g1-02-single-read-20261022`) |
| Independent review | driver `D:/uri-dev/lifecycle/LIFECYCLE-GITCTL-G102` (v2 driver from canonical): R1 `codex_cli` REJECT on `7ee76f10` (G2-01 MEDIUM, the v2 digest still read `info/refs`), driver repair `ac3dcbae`, R2 `codex_cli` ACCEPT, no findings; QUALIFICATION ok (dev_workflow 428 -> 431 / 0 failed); VERIFIED, `evidence_ok_for_candidate: true` |
| Integration-specific change | `b1944200` = `--no-ff` merge of canonical `8ff6186b` into `ac3dcbae`; no conflicts; the 3 G1-02 files (`scripts/dev_workflow/lifecycle.py`, `tests/dev_workflow/test_lifecycle_git_control_v2.py`, `docs/dev_workflow/LIFECYCLE_GIT_CONTROL_V2_PLAN_AND_ACCEPTANCE.md`) byte-identical to `ac3dcbae`; canonical had not touched them since `38a6d124` |
| Regression on the exact merge | full `tests/dev_workflow` (incl. Milestone Manager tests): 923 passed, 5 skipped (Linux-gated), 0 failed, 56 min (`D:/uri-dev/gitctl-v2-evidence/devworkflow_b1944200.log`) |
| Frozen integrity | `ws_frozen_check` ok on the merge and on a clean canonical checkout `D:/uri-dev/uri-canon-b1944200` |
| What it fixes | G1-02 (LOW, FB1 on `3def4023`): the legacy and v2 control digests are now read once, so a v1-bound run's comparison and its v2 binding describe the same state; G1-01 comment corrected; G1-03 resume rule documented |
| Rollback | `git revert -m 2 b1944200` as a new commit (parent 2 = `8ff6186b`) |
