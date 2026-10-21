# Repair of review R9 findings (2026-10-22)

Pre-repair candidate `2fe3615f`. All 3 findings accepted. Regression proof: `test_r9_*` against `2fe3615f` + new test
file: **8 failed** (the first version of the R9-02 test passed on the old code because the old `init-host` also
waited for the lock at its append; it was strengthened so that the lock holder creates the same-id segment during the
hold, which the old code then wrote into while the new code refuses with `HOST_ID_TAKEN`). After repair: 144 passed.

| Finding | Repair | Test |
|---|---|---|
| R9-01 | `recover`: own anchor count 0 ⇒ always the ANCHOR_LOSS note (no dependency on complete events) | `test_r9_01_*` (single/batch × cuts at 1, 30, 120 bytes) |
| R9-02 | `init-host` body under `os_lock(home/.lock)`; checks, writes and undo inside; `ANCHOR_MISMATCH` when earlier anchors disagree | `test_r9_02_*` |
| R9-03 | adopted anchors (own entry count 0) written before HOST_REGISTERED; §7 row names `init-host` | `test_r9_03_*` (process killed with `os._exit(9)` between append and refresh) |
