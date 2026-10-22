# Repair of review R12 findings (2026-10-22)

Pre-repair candidate `61b01ac4`. All 3 findings accepted. Regression proof: `test_r12_*` against `61b01ac4` + new test
file: **4 failed** (both R12-01 cases, R12-02, R12-03). Honest note: on the old code `test_r12_03_*` fails partly
because its kill hook targets `store.unlink_retry`, which does not exist there (the old code unlinked directly), so
for R12-03 the evidence is the reviewer's experiment `r12_initkill.py` plus the new behaviour test. After repair:
158 passed.

| Finding | Repair | Test |
|---|---|---|
| R12-01 | `_write` appends the ledger-loss events (LOSS_RECORDED, ANCHORS_ADOPTED) as a first batch and folds them into the projection before calling `build(p)` | `test_r12_01_*` (interrupted acknowledged registration; interrupted plain registration) |
| R12-02 | `unlink_retry` (PermissionError backoff) for the marker; failure after fsync ⇒ warning | `test_r12_02_*` |
| R12-03 | marker `id`; `pending_id` on HOST_REGISTERED / LOSS_RECORDED; `recorded_pending_ids` in the fold; a recorded marker is only removed | `test_r12_03_*` |
