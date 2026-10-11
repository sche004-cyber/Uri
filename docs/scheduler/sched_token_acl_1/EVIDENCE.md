# SCHED-TOKEN-ACL-1 evidence (2026-10-11, Windows 11, owner's PC)

> **Not evidence for the current code.** Everything below was recorded on commit `1465e16`, the first ACL design. That
> design was repaired (`33fc419`, review `review/`), then replaced by the check-and-refuse redesign (plan, "Amendment
> 2026-10-11"), after the in-place repair attempt SCHED-TOKEN-ACL-1b was stopped in round 5 (receipt in `review-1b/`).
> The Windows gates and the live run must be re-run on the final commit of `phase/sched-token-acl`, including
> `secure-state` on a copy of the canonical state folder. Until then, there is no Windows evidence for that commit.

## Tests (commit `1465e16`, before the review repairs)

| Gate | Result |
|---|---|
| `tests/scheduler` | 77 passed (71 at baseline + 6 new in `test_state_acl.py`) |
| `tests/a2ui` | 107 passed |
| `scripts/ws_frozen_check.py` | `"ok": true` |

## Live run

`python -m uri_scheduler.service run --state <temp> --mode fixture --port 18599`. A file `pre-existing.txt` was created before the start.

| What | Result |
|---|---|
| Ready line | `{"ready": true, "port": 18599, "mode": "fixture", ...}` |
| State folder ACL | exactly one entry: `CHETANPC\cheta:(OI)(CI)(F)` |
| `api-token` ACL | exactly one entry: `CHETANPC\cheta:(F)`, not inherited |
| `pre-existing.txt` ACL | `CHETANPC\cheta:(I)(F)` only; the old inherited entries are gone |
| `/status` with the token | 200 |
| `/status` without the token | 401 |

The service process was stopped afterwards (`taskkill`).

## Before the fix

An `api-token` written by the canonical scheduler on the same PC showed inherited entries for several SIDs, plus `ChetanPC\CodexSandboxUsers:(I)(M)`, `NT AUTHORITY\SYSTEM:(I)(F)`, `BUILTIN\Administrators:(I)(F)` and the user.
