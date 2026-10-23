# Integration receipt — FOLLOWUPS-AP32-AP6 (P3-01, D08R2-01/02, P0-D08-A, HYG-1, FU-01, P0-HYG-A), P0-verified

Executor: Milestone Manager session. Authority: owner in the MM session, verbatim "Owner authorises the canonical push of
reviewed commit 277e81f9." (MM ledger AP-37; relayed to P0), within DEC-104 scope. Owner also stated: M95 not authorised;
AP-2 deferred. Task `TASK-20261023-609bced0` (V3.1: INTEGRATED, accepted_commit `277e81f9`).

| Item | Value | P0 check |
|---|---|---|
| Canonical before / after | `3cbc08cb` -> `277e81f9b2242a727b43d9e924ea2226f07cef19` (fast-forward, 12:59:36Z, lease on `3cbc08cb`) | `ls-remote` = `277e81f9`; fetched tree `3ea518e2` = reviewed commit's tree |
| Commits / files | `ff1ece40`, `277e81f9`; 6 files: `conftest.py`, D08 record, `tests/governance/conftest.py`, `test_fcv01_rollback_amendment.py`, `test_fcv11_guarded_rollback.py`, `test_hyg1_cleanup.py` | `git log`/`diff --name-only 3cbc08cb..` |
| M95 excluded | `05d76123` not an ancestor | `merge-base --is-ancestor` false |
| Review | driver r2 NO_INDEPENDENT_REVIEWER on `277e81f9` 12:06:04Z; FB4 ACCEPT WITH FINDINGS (FU-02 LOW) | update 9 |
| Gates | governance 117+117, dev_workflow 923, oi+ws 840, office_u2+phase1 322, collect-all 12,186 exit 0, frozen 0, a2ui 25 = baseline, `work/` unchanged | update 9 |
| Ledgers | MM FOLLOWUPS-AP32-AP6 INTEGRATED, `verify` ok, 414 events, 0 conflicts; owner words present verbatim in the MM events | CLI + event grep |
| Rollback | `git revert --no-edit 3cbc08cb..277e81f9` | covers both commits |

Findings now FIXED in canonical: P3-01, D08R2-01, D08R2-02, P0-D08-A, HYG-1, FU-01, P0-HYG-A. Open: FU-02 (LOW, wording).
State: INTEGRATED. Not live-verified (tests and records only).
