# Repair of review R19 findings (2026-10-22)

Pre-repair candidate `dc22ece1`. Both findings accepted. Regression proof: `test_r19_*` and the rewritten
`test_r14_01_status_points_to_the_conflicts_listing` against `dc22ece1` + new test file: **2 failed, 0 passed**.
After repair: 183 passed.

| Finding | Repair | Test |
|---|---|---|
| R19-01 | status issue lines name the count, types and entities of the open conflicts and point to `conflicts --entity <id>`; no conflict id is printed by `status` | `test_r19_01_*` (the reviewer's scenario: status names BASIS_INVALID, prints no id; `conflicts` lists VERSION and BASIS_INVALID), `test_r14_01_status_points_*` |
| R19-02 | docstring and architecture §26 note | doc/source |
