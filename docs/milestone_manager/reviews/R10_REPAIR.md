# Repair of review R10 findings (2026-10-22)

Pre-repair candidate `1838e2df`. Both findings accepted. `init_host` was rewritten to a fixed order that never
exposes a registered host without anchors, and to offer a working acknowledged path.

| Finding | Repair | Test |
|---|---|---|
| R10-01 | order: verify segments (plain `read_segment`, no host needed) → compare earlier anchors (`_anchor_disagreements`) → git check → write adopted anchors with own entry count 0 → host file → HOST_REGISTERED → refresh | `test_r10_01_anchors_exist_before_the_machine_is_registered` (spy at the host-file write), `test_r10_01_kill_before_the_host_file_leaves_an_unregistered_home`, `test_r9_03_*` (kill after the append) |
| R10-02 | `init-host --acknowledge-loss` (store + CLI); `ANCHOR_MISMATCH` message names it; HOST_REGISTERED `anchor_problems` ⇒ ANCHOR_LOSS | `test_r10_02_*` (truncated segment; corrupt anchors file) |

Regression proof against `1838e2df` + new test file (`-k "r10_ or r9_03"`): 4 failed, 1 passed. Honest notes:
- `test_r10_01_kill_before_the_host_file_*` also passes on the old code (killing inside `_write_local` before it
  writes anything leaves the same state in both versions); the discriminating test for R10-01 is the spy test.
- `test_r9_03_*` fails on the old code only because its kill hook was moved from the 2nd to the 1st
  `write_anchors` call (the new code has one call after the append); it is a behaviour test of the new order, not
  a regression proof.

After repair: 148 passed.
