# SCHED-TOKEN-ACL-1 — Windows evidence at `fda7883` (2026-10-11)

Evidence only; no code was changed. Raw transcripts (full paths, exact `icacls` and command output; checked to contain
no token value) are in `windows_evidence_fda7883/`: `a_new.txt`, `b_open.txt`, `c_copy.txt`, `g1.log`..`g4.log`. Below,
`<temp>` abbreviates the temp root and `icacls` file lists are shortened to the file name. Owner's PC: Windows 11 Pro (NT 10.0.26200), Python 3.13.15, git 2.55.0.windows.3,
user `CHETANPC\cheta`. Worktree `C:\Users\cheta\Development\uri-sched-acl`.

## 1. Commit

```
git fetch uri-repo phase/sched-token-acl
git checkout --detach fda7883a496e1020b80c92a644d02afa03c2fb6a
git rev-parse HEAD  ->  fda7883a496e1020b80c92a644d02afa03c2fb6a   (matches)
git diff --stat 11ec4a21 fda7883a  ->  only docs/scheduler/sched_token_acl_1/review-1c/{RECEIPT.md,REPORT.html,receipt.json}
```

**Differs from the brief:** in this clone `origin` is `sche004-cyber/uri-agent`, which has no
`phase/sched-token-acl`; the URI repository (`sche004-cyber/Uri`) is the remote `uri-repo`
(`git ls-remote uri-repo refs/heads/phase/sched-token-acl` -> `fda7883a…`). All fetches and the push used `uri-repo`.

## 2. Gates (results exactly as printed)

| Command | Result |
|---|---|
| `python -m pytest -c scripts/phase2d_pytest.ini --rootdir=. -q tests/scheduler` | `89 passed, 3 skipped in 81.86s (0:01:21)`, exit 0 |
| `python -m pytest -q -rs tests/scheduler/test_state_acl.py` | `18 passed, 3 skipped in 8.19s`, exit 0 |
| `python -m pytest -q tests/a2ui` | `107 passed in 3.69s`, exit 0 |
| `python scripts/ws_frozen_check.py` | `"ok": true`, `"protected_changed_vs_baseline": []` (phase-1 frozen: 121 checked, no drift), exit 0 |

Skips in `test_state_acl.py` (the same 3 are the skips of the `tests/scheduler` run), all POSIX-only:

```
SKIPPED [1] tests\scheduler\test_state_acl.py:92: POSIX: needs root to plant a file owned by another uid
SKIPPED [1] tests\scheduler\test_state_acl.py:229: POSIX ordering probe through os.chmod
SKIPPED [1] tests\scheduler\test_state_acl.py:268: POSIX branch: os.chmod
```

The Windows-qualified tests (`skipif(not WIN)` at lines 102, 113, 308) RAN and PASSED:
`test_foreign_explicit_entry_inside_is_refused`, `test_foreign_explicit_entry_on_folder_is_refused`,
`test_missing_user_sid_fails_closed`. All 18 passing tests (from `-rA`): new folder created locked; open folder refused
not repaired; state path that is a link refused; link inside refused; foreign explicit entry inside / on folder refused;
secure-state moves an old folder into a locked one; copy failure leaves the original; final-rename failure restores the
original; link inside changes nothing; refuses while running; secure-state then run check passes; token new each launch
and user-only; service refuses on an open folder; refuses when the folder cannot be created; token write OSError leaves
no token; exits 4 when the token step fails; missing user SID fails closed.

## 3. Live checks

Temp root (new, never the real scheduler state): `C:\Users\cheta\AppData\Local\Temp\sacl-live-20261011-202455`.
Each run command: `python -m uri_scheduler.service run --state <folder> --mode fixture --port 18599` from the worktree.

### a. New folder — as expected

`<temp>\new` did not exist before (`Test-Path` False). Ready line:

```
{"ready": true, "port": 18599, "mode": "fixture", "startup": {"interrupted": [], "harness": []}}
```

```
> icacls <temp>\new
<temp>\new CHETANPC\cheta:(OI)(CI)(F)
> icacls <temp>\new\api-token
<temp>\new\api-token CHETANPC\cheta:(F)
```

One user entry each; neither is inherited (no `(I)`). The token file holds 43 characters (value not recorded).

| Request | HTTP |
|---|---|
| `GET http://127.0.0.1:18599/status` with `Authorization: Bearer <api-token>` | **200** |
| same, without the header | **401** |

Stopped with `taskkill /PID 7104 /T /F` -> `SUCCESS`. (The exit code of a force-killed process is not meaningful and
was not captured.)

### b. Open folder — as expected

`New-Item -ItemType Directory <temp>\open`; it inherits the temp folder's entries:

```
<temp>\open S-1-5-21-3041004764-4181285226-2913346969-18481432:(I)(OI)(CI)(M)
            S-1-5-21-3378200114-4252682979-2014257123-3837942712:(I)(OI)(CI)(M)
            S-1-5-21-3988682181-3972818837-1439910506-4245611555:(I)(OI)(CI)(M)
            ChetanPC\CodexSandboxUsers:(I)(OI)(CI)(M)
            S-1-5-21-3702941007-2275081338-2633963748-4136210280:(I)(OI)(CI)(M)
            S-1-15-3-3557520199-3666692283-3112367039-3524159787-2791857073-3163583606-3692855932:(I)(F)
            S-1-15-3-3557520199-3666692283-3112367039-3524159787-2791857073-3163583606-3692855932:(I)(OI)(CI)(IO)(F)
            CHETANPC\cheta:(I)(OI)(CI)(F)
            NT AUTHORITY\SYSTEM:(I)(OI)(CI)(F)
            BUILTIN\Administrators:(I)(OI)(CI)(F)
```

(Observation, not a finding of this milestone: on this PC `%TEMP%` grants Modify to `CodexSandboxUsers` and four
other user SIDs, so an unprotected state folder there would be writable by them — the case this check refuses.)

Run command output and exit code:

```
{"error": "STATE_ACL_FAILED", "detail": "the state folder is not restricted to the current user; stop the scheduler and run `python -m uri_scheduler.service secure-state --state <folder>`"}
exit code: 4
```

`icacls <temp>\open` after the run: identical to before (compared as text: `True`), after both runs. The first run was
started with `Start-Process`, which did not report the exit code; the command was run again directly to capture it
(`4`), with the same output and the folder again unchanged.

### c. Migration of a copy — as expected

**Which "real" state:** this PC has no installed scheduler (no `URIScheduler` task; only the legacy `URIServer`) and
`--state` has no default, so there is no live production state folder. The real scheduler state folders on the PC are
those of the 2026-10-09 scheduler qualification; the most complete one,
`C:\Users\cheta\Development\uri-scheduler-state\evidence_state\fixture_e2e` (`scheduler.db` with WAL files,
`service.json`, `api-token`, `outputs`, `supervisor`, `work`), was COPIED to `<temp>\copy`. The original was only read:
SHA-256 of every file before and after the case compared equal (`True`).

`icacls <temp>\copy` before: the same inherited 10 entries as `open` above.

```
> python -m uri_scheduler.service secure-state --state <temp>\copy
{"secured": "<temp>\\copy", "previous_kept_at": "<temp>\\copy.pre-acl-1791730533"}
exit code: 0
> icacls <temp>\copy
<temp>\copy CHETANPC\cheta:(OI)(CI)(F)
> icacls <temp>\copy\*
api-token         CHETANPC\cheta:(F)
outputs           CHETANPC\cheta:(I)(OI)(CI)(F)
scheduler.db      CHETANPC\cheta:(I)(F)
scheduler.db-shm  CHETANPC\cheta:(I)(F)
scheduler.db-wal  CHETANPC\cheta:(I)(F)
scheduler.lock    CHETANPC\cheta:(I)(F)
service.json      CHETANPC\cheta:(I)(F)
supervisor        CHETANPC\cheta:(I)(OI)(CI)(F)
work              CHETANPC\cheta:(I)(OI)(CI)(F)
```

Siblings afterwards: `copy`, `copy.pre-acl-1791730533` (the old folder, kept), `new`, `open`. The copied entries inherit
only the user entry of the locked folder; `api-token` has its own explicit user entry. The run command on `<temp>\copy`
printed the ready line (`{"ready": true, "port": 18599, "mode": "fixture", "startup": {"interrupted": [], "harness":
[]}}`); stopped with `taskkill /PID 8856 /T /F` -> `SUCCESS`.

Afterwards: no `uri_scheduler.service` process running, no listener on port 18599. The temp root contains copies of
`api-token` files and was deleted after this record was written.

## 4. Limits respected

The real state folder was not modified (copied and hash-checked); no scheduled task was installed or changed; nothing
was merged; nothing was pushed to `integration/*`, `milestone/*` or `phase/uri-office`.

## 5. Summary

Every gate passed, with only the 3 POSIX-only tests skipped; the 3 Windows-qualified ACL tests ran and passed. All three
live checks matched the expected results (a: ready, user-only folder and token, 200/401; b: exit 4, `STATE_ACL_FAILED`,
ACL unchanged; c: secure-state ok, user-only folder, ready). Differences from the brief, none affecting the result: the
remote is `uri-repo` in this clone; there is no live production state folder, so the 2026-10-09 qualification state
was the one copied; exit codes of force-stopped processes were not captured.
