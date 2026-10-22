# Repair of review R16 findings (2026-10-22)

Pre-repair candidate `f07da5d0`. Both findings accepted. Regression proof: `test_r16_*` against `f07da5d0` + new test
file: **11 failed, 0 passed**. After repair: 178 passed.

| Finding | Repair | Test |
|---|---|---|
| R16-01 | `resolve_conflict` records `seen` = the (event hash, conflict type) pairs of the open conflicts it resolves; the fold closes only conflicts whose pair is in `seen` | `test_r16_01_*` (the reviewer's late-sync scenario: BASIS_INVALID stays open and is listed) |
| R16-02 | `RESERVED_MILESTONE_RE`; `create_milestone` refuses with `RESERVED_ID` | `test_r16_02_*` (10 ids) |
