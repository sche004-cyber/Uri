# Repair of review R13 findings (2026-10-22)

Pre-repair candidate `3da86259`. All 3 findings accepted; they share one cause (the R12 pre-batch design), so the
design was replaced instead of patched: **record the loss, then refuse the command** (architecture §25).

Regression proof: `test_r13_*` against `3da86259` + new test file: **4 failed, 0 passed**. After repair: 162 passed.
Eight earlier tests that expected the first write after a loss to succeed were updated to the new rule (helper
`_loss_first`: first attempt refused with `LEDGER_LOSS_RECORDED`, retry runs); their original purpose (the loss is
recorded and blocks positive statuses) is unchanged.

| Finding | Repair | Test |
|---|---|---|
| R13-01 | a write that records a loss refuses the command (`LEDGER_LOSS_RECORDED`), so `resolve-conflict` can only close conflicts that existed before it ran | `test_r13_01_*` |
| R13-02 | `_write` returns only the command's own events; `recover` reports the refusal of its follow-up step as `abandon_error`; re-running `recover` is clean | `test_r13_02_*` (pending marker; unanchored own segment) |
| R13-03 | F5 clarification logged in `ACCEPTANCE_CRITERIA.md`; the CLI adds `warnings` to refusals | `test_r13_03_*`, `test_r6_04_*` (CLI warnings) |
