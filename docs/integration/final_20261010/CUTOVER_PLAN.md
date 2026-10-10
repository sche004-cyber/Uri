# URI production cutover plan (PROPOSED — not authorised, not executed)

Date: 2026-10-10. Author: Claude (final integration session). Status: **PLAN ONLY.** Nothing in this file has been run
against the live installation. Every step marked RED needs the owner's explicit approval at the time it is run. The
owner is away; this plan waits for them.

The plan reuses the accepted runbook `docs/governance/consolidation/URI_RUNTIME_BUILD_AND_ROLLBACK_RUNBOOK.md`
(sections 3 and 4) and the accepted containment tool `scripts/uri_containment.ps1`. It adds no new mechanism.

## 0. What is live today (verified 2026-10-10 17:43 local, read-only)

| Item | State |
|---|---|
| Legacy server | `C:\Users\cheta\Development\uri-agent\.venv\Scripts\python.exe scripts\run_uri_server.py --port 8000` (PIDs 7820/13088 after the 17:19 reboot), started by the scheduled task `\URIServer` |
| Shortcuts | the two `URI.lnk` files point to the legacy app (CUT-1) |
| Working system | development installations only (`uri-ws-hard`, staging trees); started by `Launch URI Working System.bat` |
| Runtime v1 Brain | not resident (started on demand by the Brain host under the GPU lease) |

## 1. Preconditions (1-4 before step 2; 5 before step 2.5)

1. The canonical commit to install is accepted by Codex and fast-forwarded on `uri-repo`
   `integration/git-sync-20261008`, with its integration receipt.
2. A fresh staging installation of the same production tree passed the staging qualification
   (`STAGING_QUALIFICATION.md`). Staging ran at `0215887`; a later canonical commit qualifies only if
   `git diff --stat 0215887 <commit> -- . ":!docs"` is empty (documentation and evidence only), otherwise staging is
   repeated.
3. The owner-only checks in `OWNER_RETURN_CHECKLIST.md` that gate activation are done, or the owner explicitly accepts
   cutover with them deferred.
4. Host stability: incident INC-1 (unexpected resets 2026-10-09/10) is understood or accepted by the owner.
5. Before the first RED step (2.5): step 2.1's backup exists and its restore dry-run passed.

## 2. Steps

| # | Step | Colour | Command / action | Verification |
|---|---|---|---|---|
| 2.1 | Back up legacy state | GREEN (read-only copy) | copy `uri-agent` state directories, `\URIServer` task XML (`Export-ScheduledTask`), both `URI.lnk`, to `D:\uri-backups\cutover-<date>\`; record SHA-256 of every file | hash manifest written; restore dry-run into a scratch folder |
| 2.2 | Build the runtime | GREEN | the only qualified procedure, the one staged: a clean checkout of the accepted commit, then `python scripts\oi_materialize_test_runtime.py <NEW, non-existent root> --venv <qualified venv>` (it refuses an existing destination). The tool labels its output a development test runtime; using that output for daily use is part of the owner's cutover decision (CUT-1). No separate production build tool exists | `git rev-parse HEAD` = e8e3b65; receipt `candidate_head` = the accepted commit (the launcher self-test follows provisioning, step 2.3) |
| 2.3 | Provision fresh state | GREEN | `ws_provision.py --name production` in the new root (port chosen in 18300-18339), **run from PowerShell** (exact command in 2a) (ENV-P1: the launcher runs under PowerShell and the frozen identity check hashes the `git` on PATH) | port ≠ 8000; no legacy data imported; launcher `-SelfTest` exit 0 |
| 2.4 | Build the UI | GREEN | `flutter build windows --release` in the SAME clean checkout the materializer used (the launcher accepts a UI only from the receipt's `candidate_source` at `candidate_head`, with no tracked change) | executable hash recorded; launcher `-SelfTest` `real_installation.ok` |
| 2.5 | Contain the legacy instance | **RED** | `scripts\uri_containment.ps1 -Apply` (disables `\URIServer`, moves shortcuts); record the printed backup folder | task disabled; shortcuts moved |
| 2.6 | Stop the legacy server | **RED** | stop the process tree on port 8000 at a time the owner chooses | port 8000 free |
| 2.7 | Start URI | **RED** | the start command in 2a, from `$Src`, with `-RuntimeRoot $Rt -UiRoot $Src` (UI first, then Brain host) | integrated server identity proven; Brain host READY with calibration ≥ 60 tok/s; window open |
| 2.8 | New shortcut | **RED** | one shortcut to the launcher with the arguments above | opens the same installation; second launch reuses the window |
| 2.9 | Observe | GREEN | 24 h: Brain host report, residency alerts, scheduler status (still disabled), no unexpected restarts | report reviewed with the owner |

## 2a. Exact commands (PowerShell; the sequence used in staging, `STAGING_QUALIFICATION.md`)

```powershell
$ErrorActionPreference = 'Stop'
$Commit = '0000000000000000000000000000000000000000'   # REPLACE with the full 40-character accepted canonical commit
if ($Commit -notmatch '^[0-9a-f]{40}$' -or $Commit -eq ('0' * 40)) { throw 'set $Commit to the accepted commit' }
$Short = $Commit.Substring(0, 7)
$Src   = "C:\URI\src-$Short"       # clean checkout: the materializer's candidate tree AND the UI root
$Rt    = "C:\URI\runtime-$Short"   # must not exist yet
$Venv  = 'C:\Users\cheta\Development\uri-ws-final\.venv'   # the venv the staging runtimes copied (a clean pip install is not separately qualified: runbook item R-3)
function Invoke-Step([string]$What, [scriptblock]$Cmd) {
  & $Cmd
  if ($LASTEXITCODE -ne 0) { throw "STEP FAILED ($What): exit $LASTEXITCODE. Stop here; nothing RED has run yet." }
}
if (Test-Path $Src) { throw "$Src exists" }; if (Test-Path $Rt) { throw "$Rt exists" }

# 2.2 runtime (GREEN)
Invoke-Step 'clone'    { git clone --no-checkout https://github.com/sche004-cyber/Uri.git $Src }
Invoke-Step 'fetch'    { git -C $Src fetch origin integration/git-sync-20261008 }
Invoke-Step 'ancestry' { git -C $Src merge-base --is-ancestor $Commit FETCH_HEAD }
Invoke-Step 'checkout' { git -C $Src checkout --detach $Commit }
Invoke-Step 'autocrlf' { git -C $Src config core.autocrlf false }
Set-Location $Src
Invoke-Step 'materialize' { python scripts\oi_materialize_test_runtime.py $Rt --venv $Venv }

# 2.3 provision, from PowerShell (ENV-P1), with the runtime's own interpreter (GREEN)
Set-Location $Rt
Invoke-Step 'provision' { .\.venv\Scripts\python.exe scripts\ws_provision.py --name production }

# 2.4 UI in the same tree (GREEN)
Set-Location "$Src\uri_ui"
Invoke-Step 'ui build' { flutter build windows --release }

# Self-test of THIS installation (GREEN): exit 0 AND real_installation.ok, or stop.
Set-Location $Src
$st = powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\launch_uri_working_system.ps1 -SelfTest -RuntimeRoot $Rt -UiRoot $Src | Out-String
if ($LASTEXITCODE -ne 0 -or -not ($st | ConvertFrom-Json).real_installation.ok) { throw "SELF-TEST FAILED; do not continue:`n$st" }
'GREEN steps complete. Continue with 2.5 and 2.6 (RED, owner present), then 2.7.'

# 2.7 start (RED; only after 2.5 and 2.6, with the owner's approval)
# powershell -NoProfile -ExecutionPolicy Bypass -File "$Src\scripts\launch_uri_working_system.ps1" -RuntimeRoot $Rt -UiRoot $Src
```

The new shortcut (2.8) runs the last command with the same arguments. `Launch URI Working System.bat` passes its
arguments through to the same script, so it can be used from `$Src` with the same `-RuntimeRoot` and `-UiRoot`.

## 3. Still disabled after cutover (unchanged by this plan)

Real-Claude scheduled execution; the `URIScheduler` Windows logon task; festival jobs and the 09:00 IST default; any
automatic execution. Voice cannot authorise a sensitive action (approval cards stay explicit clicks).

## 4. Rollback (any time, in this order)

1. Close URI; stop the Brain host (stop file or Stop Brain) and the integrated server (process tree by PID).
2. Remove the new shortcut.
3. `scripts\uri_containment.ps1 -Restore -BackupRoot <folder from 2.5>`; `Start-ScheduledTask -TaskName URIServer`.
4. Verify port 8000 answers and the legacy shortcuts open the legacy app.
5. Leave the new root in place for diagnosis (no data in it is needed by the legacy app), or delete it.

Rollback never touches the legacy state directories, which are not written by any cutover step.
