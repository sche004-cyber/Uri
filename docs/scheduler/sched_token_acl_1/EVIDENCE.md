# SCHED-TOKEN-ACL-1 evidence (2026-10-11, Windows 11, owner's PC)

> **Stale after review (R2-04).** Everything below was recorded on commit `1465e16`, before the independent-review
> repairs `33fc419` (R1-01) and the R2 follow-up (SCHED-TOKEN-ACL-1b: `/reset /T` of explicit entries, R2-01).
> The Windows gates and the live run must be re-run on the final commit of `phase/sched-token-acl`; until then this
> page is not Windows evidence for that commit. Linux gate results are in `review/` and `review-1b/`.

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
