# WS-FLAKE-1: fresh Brain-host requests rejected as stale (timing bug)

Baseline: canonical `integration/git-sync-20261008` @ `03f0bf2c` (verified with `git ls-remote`, 2026-10-12).
Candidate: `milestone/ws-flake-1-20261012`. Owner approval: 2026-10-12 ("Ok approved"); integration under D1.

## Problem
`uri_operational_intelligence/brain_health.write_host_request` stamps `requested_at = round(time.time(), 3)`.
Rounding to the nearest millisecond can put the stamp up to 0.5 ms in the future. `scripts/ws_brain_host.Host
.take_request` computes `age = now() - requested_at` and rejects `age < 0` as `IGNORED_INVALID_OR_STALE`. So a
request taken straight after it is written (the normal case for a quick restart/stop) is sometimes dropped. This is a
product bug, and it is why three `tests/ws/test_ws_hardening.py` tests fail at random (about 1 run in 3 to 8), which
refused the W1/A0 integration once.

## Fix
Stamp `requested_at` rounded DOWN to the millisecond, so it is never later than the moment it was written. No change
to the staleness window, the request schema or the host.

## Acceptance criteria
| # | Criterion | Evidence |
|---|---|---|
| WSF-AC1 | `requested_at` is never later than the time it was written, for any clock value (checked with a fixed clock just past a half-millisecond). | new regression test, fails on 03f0bf2c |
| WSF-AC2 | A request taken at the same instant it was written is ACCEPTED, never IGNORED_INVALID_OR_STALE. | new regression test, fails on 03f0bf2c |
| WSF-AC3 | Stale (older than REQUEST_MAX_AGE_S), invalid and reused requests are still refused. | existing tests pass |
| WSF-AC4 | The three formerly flaky tests pass 50 times in a row. | repeated run on the candidate |
| WSF-AC5 | Only `uri_operational_intelligence/brain_health.py`, the new test and this plan change; no frozen path. | driver scope check |
