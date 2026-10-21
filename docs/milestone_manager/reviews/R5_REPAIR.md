# Repair of review R5 findings (2026-10-21)

Pre-repair candidate `7c8e0a29`. All 9 findings accepted; none disputed. Regression proof: `test_r5_*` plus the
updated `test_r4_05_*` against the pre-repair code (`7c8e0a29` + new test file): **10 failed, 0 passed**. After
repair: 120 passed.

| Finding | Repair | Test |
|---|---|---|
| R5-01 | `recover(acknowledge_loss)`: anchor errors/warnings vs previous anchors ⇒ refused unless acknowledged; `anchor_problems` on STORE_RECOVERED ⇒ ANCHOR_LOSS; CLI `recover --acknowledge-loss` | `test_r5_01_*` |
| R5-02 | `import_register`: existing record from another register ⇒ `collisions`, CLI exit 1 | `test_r5_02_*` |
| R5-03 | records keep `original`; revisions keep `previous` | `test_r5_03_*` |
| R5-04 | `_write` prepends ANCHORS_ADOPTED when it will anchor an own segment at count 0 ⇒ ANCHOR_LOSS | `test_r5_04_*`, updated `test_r4_05_*` |
| R5-05 | `lamport_floor()` in store used by `reanchor` and `recover` | `test_r5_05_*` |
| R5-06 | one future-stamp warning naming the earliest future-stamped segment, explaining pinning; write warning mentions pinning | `test_r5_06_*` |
| R5-07 | `apply()` drops `_cidx` | `test_r5_07_*` |
| R5-08 | `read_anchors` validates entries (int count ≥ 0, 64-char head) | `test_r5_08_*` |
| R5-09 | registers read with `utf-8-sig` | `test_r5_09_*` |
