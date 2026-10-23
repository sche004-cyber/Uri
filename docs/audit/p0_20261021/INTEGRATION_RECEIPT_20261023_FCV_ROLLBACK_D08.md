# Integration receipt — FCV-ROLLBACK-D08 (AP-6 / OPEN-06), P0-verified

Executor: Milestone Manager thread (DEC-103 §6). Authority: DEC-104 (AP-6 conditional authorisation; D08-03 narrowly
scoped exception for the four pinned secure-recovery files; the MM copy's stricter wording also satisfied).
P0 role: independent read-only verification, 2026-10-23.

| Item | Value | P0 check |
|---|---|---|
| Canonical before | `1d29ed85` | ancestor of new tip |
| Canonical after | `3cbc08cb4363ac7963be90df6a66eebcab311f3a` (fast-forward to a `--no-ff` merge; pushed 11:15:42Z, lease pinned to `1d29ed85`) | `ls-remote` = this value; `1d29ed85..3cbc08cb` = 3 commits (`4ae062cb`, `c91de8aa`, merge) |
| Reviewed content | merge parents `1d29ed85` + `c91de8aa`; changes only the 3 AP-6 files, byte-identical to `c91de8aa` | `diff --name-only`, `diff --quiet` (update 5) |
| Four pins | blob, SHA-256, bytes of `uri_web/{__init__,netpolicy,records,safe_fetch}.py` equal canonical `c036a901` and `SUPPORT_FILES` | P0 computed (update 3); FB2 re-checked every row |
| Driver runs | r1 `4ae062cb` 07:32:39Z, r2 `c91de8aa` 09:08:34Z, both BLOCKED NO_INDEPENDENT_REVIEWER (codex QUOTA, claude AUTH) | `state/events.jsonl` |
| Reviews | FB1 `4ae062cb`, FB2 `c91de8aa`: COMPLETED_WITH_RESULT, ACCEPT WITH FINDINGS | records read |
| Tests by P0 | `test_fcv11_guarded_rollback.py` 16 passed on `c91de8aa` with the fixture (SHA-256 `31a34dcb...`); new d08_02 tests fail on `4ae062cb` | own detached worktrees |
| Gates on `3cbc08cb` | dev_workflow 923 passed; oi+ws 840; governance 113, no skips; office_u2+phase1 322; ws_frozen_check exit 0; a2ui/assist/ssrf/web 25 ids = `c036a901` baseline | log tails read; id diff by P0 |
| Collection | gate checkout: 12,182 collected, 196 errors, all 196 under untracked `work/c1/rollback_*` / `negative_restore_*` written by the governance tests (0 elsewhere); clean checkout: 12,182 collected, exit 0 | P0 grep of the error lines; +5 = test functions 10 -> 15 in the rollback test file |
| Ledger | FCV-ROLLBACK-D08 INTEGRATED; `verify` ok, 388 events, 0 conflicts | `milestones verify/show` (code `c036a901`) |
| Rollback | `git revert -m 1 3cbc08cb` (parent 1 = canonical `1d29ed85`; new commit, no force-push) | parent order confirmed |

Open LOW / docs: D08R2-01 (stale "14 tests"), D08R2-02 (ast command not recorded), P0-D08-A (attribution of the
D08-03 wording), HYG-1 (governance rollback tests leave restored trees under `work/c1` that whole-repo collection then
imports; pre-existing). Not live-verified (offline source-rehearsal tool; nothing is started). State: INTEGRATED.
