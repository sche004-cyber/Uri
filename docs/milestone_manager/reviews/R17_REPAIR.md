# Repair of review R17 findings (2026-10-22)

Pre-repair candidate `4f462be7`. The finding was accepted; both suggested fixes were applied. Regression proof:
`test_r17_*` against `4f462be7` + new test file: **1 failed, 0 passed**. After repair: 179 passed.

| Finding | Repair | Test |
|---|---|---|
| R17-01 | `conflict_fingerprint` over the displayed fields; `seen` stores (hash, type, fingerprint); a conflict whose content changed is not covered by the old resolution. `_check_basis` raises BASIS_INVALID when a basis reviewer is an implementer in the merged history | `test_r17_01_*` (the reviewer's scenario: after the second sync VERSION is open again and BASIS_INVALID is raised; indicator RED) |
