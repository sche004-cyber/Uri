# Repair of review R15 findings (2026-10-22)

Pre-repair candidate `255b9079`. Both findings accepted. Regression proof: `test_r15_*` against `255b9079` + new test
file: **2 failed, 0 passed**. After repair: 167 passed.

| Finding | Repair | Test |
|---|---|---|
| R15-01 | an id must name exactly one conflict-raising *event*; all open conflicts of that event on the entity are resolved together; the `NO_CONFLICT_ID` listing shows each id once; data model §20 wording corrected | `test_r15_01_*` (two hosts create MM-X and LDEC-900; resolve by id; ACCEPTED reached) |
| R15-02 | the LEDGER_LOSS_RECORDED refusal names `--id <id>` for each recorded event; warnings and the recover note mention `--id` | `test_r15_02_*` |
