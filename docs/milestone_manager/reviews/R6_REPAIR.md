# Repair of review R6 findings (2026-10-21)

Pre-repair candidate `3ba9af68`. All 5 findings accepted; none disputed. Regression proof: `test_r6_*` against the
pre-repair code (`3ba9af68` + new test file): **4 failed, 0 passed**. After repair: 124 passed.

Note on the R6-01 test: the first draft truncated the segment *after* the anchor refresh, which is a real loss and
was correctly refused; the test now restores the anchors to their post-`init` state before cutting the segment, which
is what a power loss before the refresh leaves.

| Finding | Repair | Test |
|---|---|---|
| R6-01 | `_only_unapplied_batches`: an own count-0 warning is not a problem when all own events beyond the anchor belong to incomplete batches of this segment | `test_r6_01_*` (recover rc 0, batch abandoned, retry clean, no conflict) |
| R6-02 | `init_host`: git work tree with segment changes vs HEAD ⇒ `UNCOMMITTED_SEGMENTS` (host file removed again); HOST_REGISTERED event with adopted counts; residual documented (architecture §18) | `test_r6_02_*` |
| R6-03 | acknowledged recover ⇒ `write_anchors_force`; CLI prints the result with `abandon_error` if abandonment fails | `test_r6_03_*` |
| R6-04 | warning text names ANCHORS_ADOPTED; `_write` adds a `last_warnings` entry when it prepends ANCHORS_ADOPTED; §7 rows updated | `test_r6_04_*` |
| R6-05 | handoff references `evidence/rehearsal/verify.json` | doc |
