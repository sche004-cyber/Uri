# Superseded by W1-A0-closure-2 (2026-10-11 ~09:20 UTC)

- **What happened:** round 16 independently accepted candidate `67aff5042c0f166392281e072fb5f9db906779c5`
  (ACCEPT WITH FINDINGS). The qualification then reported 178 "new" Python gate failures and blocked as
  REPAIR_FAILED ("no change made") after three repair attempts.
- **Root cause (coordinator diagnosis):** the gate command listed `tests/web` and `tests/assist`, which do not exist
  at baseline `ffdf534`.
  - pytest exited 4 ("file or directory not found"), ran 0 tests, and the driver accepted that empty baseline as
    COMPLETED_WITH_RESULT. With nothing to compare against, every container-environmental failure counted as new.
  - The 0-test baseline is a driver defect, queued for the lifecycle follow-up: refuse a baseline gate that ran 0
    tests.
- **Evidence:**
  - The same gate run manually on `ffdf534` over its existing folders (`tests/ws tests/oi tests/a2ui`): 558 passed,
    37 failed, 24 skipped, 161 teardown errors. 178 failing tests, mostly Windows-only `msvcrt` and `powershell`.
  - The candidate fails 179. The only candidate-only failure,
    `tests.ws.test_ws_hardening::test_host_requests_are_explicit_fresh_and_used_once`, is timing-flaky on both
    commits (baseline 4/5 pass, candidate 3/5) and was already in `allowed_flaky`.
  - Therefore: no regression. The "178 new failures" result above is **invalid evidence**, kept here unaltered as
    history.
- **Fix:** the Python gate now runs only the test folders that exist in the checkout (owner approved,
  2026-10-11; `W1-A0-closure.json.before-gatefix` keeps the old command). No gate was loosened.
- **Why a new state directory:** the driver has no supported "re-run the gates" resume from FIXING with pending gate
  findings, and editing `state.json` would break the hash chain.
  - `W1-A0-closure-2` re-plans the same candidate.
  - It requires a fresh independent review of the exact commit, then the corrected gates, then D1.
  - This directory is kept unchanged as the audit trail of rounds 1-16, repairs P1-P17 and diagnoses D1-D8.
