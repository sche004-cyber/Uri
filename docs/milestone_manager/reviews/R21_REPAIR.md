# Repair of review R21 findings (2026-10-22)

Pre-repair candidate `8745a8d0`. All 3 findings accepted. Regression proof: `test_r21_*` against `8745a8d0` + new
test file: **2 failed, 1 passed**. The passing one, `test_r21_01_no_refusal_or_warning_hands_out_ids`, is a guard
against future leaks in the other refusals (it passes on both versions because only the stale path leaked); the
discriminating tests are `test_r21_01_stale_refusal_prints_no_id` and `test_r21_02_*`. After repair: 189 passed.

| Finding | Repair | Test |
|---|---|---|
| R21-01 | `STALE_CONFLICT_ID` prints no new id, only `conflicts --entity <entity>`; architecture §31 corrected | `test_r21_01_*` (2) |
| R21-02 | detail keys include `unknown_previous`, `adopted`; ANCHORS_RESET conflicts carry `anchor_problems` | `test_r21_02_*` |
| R21-03 | data model §24 | doc |
