# Repair of review R8 findings (2026-10-22)

Pre-repair candidate `ddc4e63b`. All 5 findings accepted. Root cause of R8-01/R8-02 (and of R6-01/R7-01 before
them): trying to decide from the torn bytes whether a tail was harmless. A power loss in progress and a truncation of
applied events leave byte-identical files, so no byte test can be both safe and non-blocking. The repair removes the
heuristics (`_torn_continues_batch`, `_only_unapplied_batches`, `_only_own_registration`) instead of refining them.

Regression proof: `test_r8_*` and the parametrised `test_r6_01_*` against `ddc4e63b` + new test file: **8 failed,
1 passed** (the 20-byte cut was already recorded for review there). After repair: 136 passed.

| Finding | Repair | Test |
|---|---|---|
| R8-01, R8-02 | own segment without anchor ⇒ `recover` always proceeds and always records one ANCHOR_LOSS (note in `anchor_problems`); never refused, never silent | `test_r6_01_*` (cuts at 20, 60, 65, 120, 400 bytes), `test_r8_02_*`, `test_r7_01_*` |
| R8-03 | `init-host` refuses any existing segment with that id | `test_r8_03_*` |
| R8-04 | failed `init-host` removes the segment file it created (never anchored or committed), so a git retry is clean | `test_r8_04_*` |
| R8-05 | failed `init-host` restores the previous anchors bytes; removes `.gitignore`/`local/` only if it created them | `test_r8_05_*` |

Behaviour consequence (documented in architecture §20): a power loss during a host's very first write now always
costs one review (`resolve-conflict LEDGER`), the same as a failed first anchor refresh (§17).
