# Repair of review R11 findings (2026-10-22)

Pre-repair candidate `5bb005f6`. All 5 findings accepted. Regression proof: `test_r11_*` against `5bb005f6` + new test
file: **6 failed, 0 passed**. After repair: 154 passed.

| Finding | Repair | Test |
|---|---|---|
| R11-01 | durable `local/pending_loss.json` written before the earlier anchors are replaced; removed only after HOST_REGISTERED records the problems; a retry includes the marker's problems (needs the flag, records them); a registered host's next write prepends LOSS_RECORDED; projection warns while pending; undo restores the marker state | `test_r11_01_*` (kill before the host file; kill before the append) |
| R11-02 | git subprocess calls in `init_host` wrapped: `OSError` ⇒ not in git | `test_r11_02_*` |
| R11-03 | `EventStore.locked()` re-reads `local/host.json` and refuses `NO_HOST_ID` if it changed | `test_r11_03_*` |
| R11-04 | ANCHOR_LOSS text: recording event kind + first recorded problem (`lost`, `anchor_problems`, or adoption) | `test_r11_04_*`; `test_r3_01_*` wording updated |
| R11-05 | unreadable host file treated as unregistered by `init_host` (restored on undo); NO_HOST_ID message says "missing or unreadable" | `test_r11_05_*` |
