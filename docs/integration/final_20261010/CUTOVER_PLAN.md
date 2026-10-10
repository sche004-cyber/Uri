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
| 2.3 | Provision fresh state | GREEN | `ws_provision.py --name production --port <18300-18339>` in the new root | port ≠ 8000; no legacy data imported; launcher `-SelfTest` exit 0 |
| 2.4 | Build the UI | GREEN | `flutter build windows` in a clean checkout of the accepted commit | executable hash recorded |
| 2.5 | Contain the legacy instance | **RED** | `scripts\uri_containment.ps1 -Apply` (disables `\URIServer`, moves shortcuts); record the printed backup folder | task disabled; shortcuts moved |
| 2.6 | Stop the legacy server | **RED** | stop the process tree on port 8000 at a time the owner chooses | port 8000 free |
| 2.7 | Start URI | **RED** | `Launch URI Working System.bat -RuntimeRoot <new root> -UiRoot <clean checkout>` (UI first, then Brain host) | integrated server identity proven; Brain host READY with calibration ≥ 60 tok/s; window open |
| 2.8 | New shortcut | **RED** | one shortcut to the launcher with the arguments above | opens the same installation; second launch reuses the window |
| 2.9 | Observe | GREEN | 24 h: Brain host report, residency alerts, scheduler status (still disabled), no unexpected restarts | report reviewed with the owner |

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
