# Repair of review R14 findings (2026-10-22)

Pre-repair candidate `b59c1f2a`. Both findings accepted. The reviewer's option 1 was taken: "seen" is made explicit.
Instead of trying to make "record, then tell the user" atomic (impossible across a process kill), resolving a
conflict now requires naming it by the id that only a display (`status`, `conflicts`, a refusal listing) shows.

Regression proof: `test_r14_*` against `b59c1f2a` + new test file: **3 failed, 0 passed**. After repair: 165 passed.
Four earlier call sites (`resolve_conflict(entity, note)`) were updated to the new API via the test helper `_resolve`,
which reads the ids from `views.conflict_rows` as a user reads them from `status`.

| Finding | Repair | Test |
|---|---|---|
| R14-01 | `Manager.resolve_conflict(entity, note, conflict_ids)` resolves only named ids (≥ 8 hex, unique); `NO_CONFLICT_ID` / `UNKNOWN_CONFLICT_ID`; `conflicts` CLI command; ids in every conflict line of `status`; §25 claim corrected with a dated note | `test_r14_01_*` (2) |
| R14-02 | CLI refusal output includes `autocommit_error` | `test_r14_02_*` |
