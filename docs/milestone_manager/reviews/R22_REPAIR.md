# Repair of review R22 findings (2026-10-22)

Pre-repair candidate `aa70a5ba`. All 5 findings accepted. Regression proof: the new `test_r22_*` tests against
`aa70a5ba` code: **16 failed, 0 passed**. Two of them fail on the old code partly for a structural reason rather
than the defect alone: `test_r22_04_*[60]` (the old code handled 60 correctly but has no `MIN_RESUME_CHARS`) and
`test_r22_02_single_host_flow_binds_without_conflict` (no `bound_commit` key); the discriminating tests are the
other 14. After repair: 205 passed.

| Finding | Repair | Test |
|---|---|---|
| R22-01 | `store.check_free_text` refuses secrets in actor/session/reason (and over-long actors) in `reanchor` and `recover` before the lock; CLI `recover` checks actor, session and `--reason` before recovering | `test_r22_01_*` (6) |
| R22-02 | the fold keeps `bound_commit` (the commit a positive status rests on) and raises `CANDIDATE_CHANGED` when the candidate differs from it, at STATUS_SET (basis reviews, approvals, integration record compared) and at MILESTONE_UPDATED; the indicator stays RED while candidate and bound commit differ, even after the conflict is resolved; the lock lets the candidate return to the bound commit; INTEGRATED and DONE bases now record `commit` | `test_r22_02_*` (4) |
| R22-03 | `autocommit` commits only the ledger's own changed paths (`commit --only -- <paths>`); other staged work stays staged | `test_r22_03_*` |
| R22-04 | `resume_brief` clamps `max_chars` to `MIN_RESUME_CHARS` (200) and never slices negatively | `test_r22_04_*` (4) |
| R22-05 | help text says ids are shown by `conflicts` | `test_r22_05_*` |
