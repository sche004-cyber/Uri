# Repair of review R20 findings (2026-10-22)

Pre-repair candidate `e008d3ff`. Both findings accepted. Regression proof: `test_r20_*` against `e008d3ff` + new test
file: **3 failed, 0 passed**. After repair: 186 passed (one assertion of `test_r15_01_*` that expected the refusal to
list ids was changed to expect no ids).

| Finding | Repair | Test |
|---|---|---|
| R20-01 | `NO_CONFLICT_ID` prints the count and `conflicts --entity <entity>`, no ids; `LEDGER_LOSS_RECORDED` prints each loss's detail next to its id; architecture §31 corrected | `test_r20_01_*` (2) |
| R20-02 | `conflict_rows(p, entity)` expands to every open member of each listed (entity, event) group; rows carry `subjects` | `test_r20_02_*` (duplicate review ids for MM-1 / MM-2) |
