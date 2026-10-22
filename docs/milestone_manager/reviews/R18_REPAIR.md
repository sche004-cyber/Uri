# Repair of review R18 findings (2026-10-22)

Pre-repair candidate `c455dee2`. All 3 findings accepted. Regression proof: `test_r18_*` against `c455dee2` + new test
file: **3 failed, 0 passed**. After repair: 182 passed.

| Finding | Repair | Test |
|---|---|---|
| R18-01 | displayed / typed id `<event 12>.<check 6>` (`model.display_id`); `resolve_conflict` refuses a bare event part and a stale check (`STALE_CONFLICT_ID`); all displays (`status`, `conflicts`, `NO_CONFLICT_ID`, `LEDGER_LOSS_RECORDED`) use it | `test_r18_01_*` (ids read after sync 1, sync 2 lands, resolve refused; BASIS_INVALID stays open) |
| R18-02 | cheap filters before fingerprinting in the fold; fingerprint cached on the conflict; display ids computed once per projection in the conflict index | `test_r18_02_*` (1,000 resolved conflicts: fold + status < 1.5 s) |
| R18-03 | fingerprint over present keys only; doc wording | `test_r18_03_*` |

During the repair the first version of display ids made `status` quadratic again (each line recomputed the group);
`test_r4_06_*` caught it before commit and the index-based computation replaced it.
