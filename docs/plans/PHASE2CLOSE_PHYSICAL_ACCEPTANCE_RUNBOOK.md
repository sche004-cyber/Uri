# Phase 2 physical acceptance runbook

Date 2026-10-08. Author: Claude. Status: **PREPARED. No gate below has been performed by the owner.** Every gate starts
as PENDING. A gate becomes PASS only when the owner performs it and records the observation with
`scripts/phase2close_acceptance.py record`. Automation results are listed beside each gate as supporting evidence;
they never replace the physical observation.

Worktree: `C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent` (detached at `e8e3b65`, uncommitted). All commands
run from that directory in Windows PowerShell. `PY` below means `.\.venv\Scripts\python.exe`.

Nothing in this runbook changes `Launch URI.bat`, the `URIServer` scheduled task, port 8000, shortcuts, provider
configuration or production data. Every root is created under `work\c1\acceptance-*` on a port in 18300-18339.

## 0. Before the session (automated, about 2 minutes)

```powershell
.\.venv\Scripts\python.exe -I scripts\phase2close_acceptance.py preflight --out ..\evidence\phase2close\acceptance_preflight_owner.json
```

Expected: `"ready_for_session": true`. The preflight checks the accepted candidate hash (`9a0be52c...affb50a`), the
frozen Phase 1 checkpoint hash (`31a34dcb...efeb98cf7`), that every frozen file is byte-identical, the worktree
interpreter and Flutter. It also reports, without changing anything: the Codex/Claude versions, their login state in
YOUR shell profile, whether a Windows release build exists and whether Hyper-V cmdlets exist.

Then provision an isolated acceptance installation:

```powershell
.\.venv\Scripts\python.exe -I scripts\phase2close_acceptance.py provision --grant-harness
```

It prints the campaign folder (`work\c1\acceptance-<stamp>`), the server start command and the app launch command.
Keep the campaign folder path; every `record` call uses it (written `$C` below).

## 1. Gates

Result vocabulary: PASS (observed as expected), FAIL (observed otherwise; describe it), BLOCKED (could not be
performed; say why). Record each gate immediately after performing it:

```powershell
.\.venv\Scripts\python.exe -I scripts\phase2close_acceptance.py record $C "PA-2 approve" PASS --note "deterministic row, remember_fact, receipt shown"
```

### PA-1 launch the real app against the Phase 2 profile

1. Window 1: run the printed server command (`run_uri_phase2_server.py --manifest ...`). Keep it open.
2. Window 2: run the printed app command (`$env:URI_CLIENT_MANIFEST = ...; cd uri_ui; flutter run -d windows`).
3. In the app open Tasks. Expect the card "Supervised execution (Phase 2, opt-in)". Open it.
4. Expect the line `Worker profile: phase2d-supervised · production cutover: false · mid-run cancel: true`, an
   "Executor" list with "URI deterministic rules (no Brain)" and one row per harness showing its honest state.
   No executor is preselected. "Send" reads "Choose an executor first".

PASS when all four observations hold. Automated support: widget tests "no executor is preselected ...", "the entry
on Tasks renders nothing unless the installation opted in"; live Dart bridge runs (real worker + server processes).

### PA-2 approve supervised work (no login needed)

1. Choose "URI deterministic rules (no Brain)". Type `remember that the acceptance session started today`. Send.
2. Expect an approval card: task, capability `remember_fact`, executor `uri-deterministic`, effect, reversibility, the
   exact arguments JSON, argument digest, approval digest, proposal digest. "Approve and run" is the only way forward.
3. Type `approve` in the text box and press nothing else. Expect no change (typed text never approves).
4. Press "Approve and run". Expect the execution card to reach `COMPLETED`, settlement `SETTLED_VERIFIED`.

PASS when 2-4 hold. Automated support: `test_deterministic_row_runs_through_the_same_lifecycle`, widget test
"typing approve never begins an execution".

### PA-3 deny supervised work

1. Same executor, type `remember that this one must not be saved`. Send. On the card press "Decline".
2. Expect the outcome `APPROVAL_DENIED` / "You declined; nothing was changed." No execution card appears.

### PA-4 cancel before dispatch

Before dispatch is a short window; timing it by hand is not reliable. Perform both:

1. Pending card: open a card (any executor) and close the app window instead of deciding. Restart the app (PA-6
   steps). Expect: the history lists no execution for that card. (Server side, the worker now releases the abandoned
   card on close - CAP-1 - which `collect` cannot show; the real-process test below proves it.)
2. Immediately after "Approve and run" on a harness row (needs PA-8/PA-10), press "Cancel execution" at once. Expect
   either `CANCELLED` (`CANCELLED_BEFORE_START`, nothing ran) or, if dispatch had already happened, `UNCERTAIN`
   (`CANCELLED_AFTER_DISPATCH`). Record which one you saw; both are correct, a `COMPLETED` is a FAIL.

Automated support: `test_cancel_before_the_approval_is_posted_denies_the_turn`,
`test_cancel_between_approval_and_dispatch_never_spawns`, `test_cap1_close_and_stdin_eof_release_pending_cards_over_real_frames`.

### PA-5 cancel after dispatch (needs PA-10)

1. Choose the Codex row. Type
   `use the harness to write a detailed essay of at least 2000 words about durable task supervisors into essay.txt`.
   Send, approve.
2. When the card shows `RUNNING` with a supervisor attempt, press "Cancel execution".
3. Expect `UNCERTAIN`, reason `CANCELLED_AFTER_DISPATCH`, attempt `cancelled_killed`, and the wording "URI cannot
   prove a clean outcome ... Nothing is retried automatically". In Task Manager no `codex` process remains.

Automated support: real Codex mid-run cancel (`evidence\phase2close\run*\native\`, in-process composition, owner's
shell login - see ISO-1 below for why that is not the worker-process path).

### PA-6 close, restart, reconnect

1. Start a long harness execution (as PA-5 step 1) or, without a harness, complete PA-2 first.
2. Close the app window while the execution runs. Expect the worker to withdraw it (job kill).
3. Relaunch the app (PA-1 step 2), open the screen. Expect the history to list the execution: `uncertain`
   (`WORKER_CLOSED_DURING_EXECUTION` or `WORKER_RESTARTED`) for the interrupted one, `completed` for PA-2.

Automated support: `test_close_during_execution_*`, `test_completed_execution_survives_a_worker_restart`,
`test_worker_crash_mid_run_*` (real processes), Dart live test part 3.

### PA-7 worker and server interruption

1. Server: during a harness execution press Ctrl+C in window 1. Expect the card to report `uncertain` or a status
   error, never `completed`. Restart the server command, reopen the screen: the record stays `uncertain`; a new
   request in a new screen works.
2. Worker: during a harness execution end the `python ... run_uri_supervised_worker.py` process in Task Manager.
   Expect the executor process to disappear too, and on reopening the screen the record shows `uncertain`
   (`WORKER_RESTARTED`).

### PA-8 native Codex login in the CLIENT profile (owner credential action)

Codex must be logged in INSIDE the acceptance client profile, never through your own profile. ISO-1 (found in this
closure): Codex ignores `USERPROFILE`; only `CODEX_HOME` isolates it. The worker now pins `CODEX_HOME` to the client
profile, so the login must be made with the same pin:

```powershell
$cr = (Get-Content "$C\campaign.json" | ConvertFrom-Json).client_root
$env:USERPROFILE = "$cr\home"; $env:HOME = "$cr\home"; $env:APPDATA = "$cr\home\roaming"
$env:LOCALAPPDATA = "$cr\home\local"; $env:CODEX_HOME = "$cr\home\.codex"
codex login
codex login status          # expect: Logged in ...
```

Use a NEW PowerShell window for this and close it afterwards, so these variables do not leak into other work. Then
persist the client's qualification. The script probes under the same pins, with every provider credential variable
(`CODEX_API_KEY`, `CLAUDE_CODE_OAUTH_TOKEN`, `*_API_KEY`, `*_TOKEN`, ...) REMOVED from its environment, so only a
login stored under the client profile can succeed, and writes a signed record ONLY when the probe and
`codex login status` both succeed (review round 1, D1):

```powershell
.\.venv\Scripts\python.exe -I scripts\phase2close_acceptance.py qualify $C --provider codex_cli --model gpt-6-sol
```

PASS when `"persisted": true`. Before the owner's login the same command returns `"persisted": false` (verified
2026-10-08, campaign `acceptance-20261008-045345`; an earlier record written before the ISO-1 pin was VOIDED and
moved to `VOIDED_qualification\`).

### PA-9 native Claude login in the CLIENT profile (owner credential action)

Same window discipline, `USERPROFILE`/`HOME` set to `$cr\home` (Claude Code resolves its config through the process
home). Run `claude`, complete the sign-in, then `claude auth status` (expect `"loggedIn": true`), then
`qualify $C --provider claude_code`.

### PA-10 native execution inside the worker process

**Currently BLOCKED by EXE-1** (found in this closure, 2026-10-08): the worker's sanitized environment
(`runtime_identity.child_environment`) has a three-entry PATH (venv, System32, git). The npm shim `codex.CMD` then
fails with `"node" is not recognized`, so the worker re-validation cannot run `codex --version` and the client's
Codex record is not composed (observed: real worker `harness_discover` -> codex_cli `NOT_INSTALLED`, empty
`qualification_live`). Claude's shim starts under the same PATH. Resolving EXE-1 widens what the worker may execute,
so it needs the owner's decision (options in `PHASE2CLOSE_C7_READINESS.md`, item EXE-1). After that decision and
PA-8, PA-10 is: PA-5 performed from the real app, the worker process running Codex under the client profile login.

### PA-11 controlled power-loss durability (throwaway VM)

Needs a Windows VM the owner may power off hard. Not this PC: preflight found no Hyper-V cmdlets here; enabling
Hyper-V is a system change for the owner. Any hypervisor with a hard power-off works (Hyper-V `Stop-VM -TurnOff`,
VirtualBox `VBoxManage controlvm <vm> poweroff`, VMware `vmrun stop <vmx> hard`).

1. VM: Windows 11, the worktree copied in, Python 3.13 venv, virtual disk with host write cache disabled or a
   flush-honouring setting. Network reachable from the host.
2. VM autostart (Task Scheduler, at log-on of a dedicated auto-logon user):
   `python scripts\phase2close_powerloss_harness.py guest --ledger D:\pl\ledger.db --host <host-ip> --port 47710`
3. Host, FULL series (200 iterations):
   ```powershell
   .\.venv\Scripts\python.exe -I scripts\phase2close_powerloss_harness.py host --port 47710 --iterations 200 --out ..\evidence\phase2close\powerloss_full `
     --power-off "powershell -NoProfile -Command Stop-VM -Name URI-PL -TurnOff -Force" `
     --power-on  "powershell -NoProfile -Command Start-VM -Name URI-PL"
   ```
4. Control series: change the guest task to add `--synchronous NORMAL`, fresh ledger folder, same host command with
   `--out ..\evidence\phase2close\powerloss_normal` (any iteration count; it must lose at least one acknowledged step).
5. Assess both series together (the host's own `SERIES_ALL_PASS` is never a verdict on durability):
   ```powershell
   .\.venv\Scripts\python.exe -I scripts\phase2close_powerloss_harness.py assess --full ..\evidence\phase2close\powerloss_full `
     --control ..\evidence\phase2close\powerloss_normal --out ..\evidence\phase2close\powerloss_assessment.json
   ```
   `assess` recomputes both series from their raw `acks.jsonl` (the summary and iterations files must agree with it) and
   requires a FULL series of >= 200 iterations that all pass (guest reports `synchronous` FULL, every iteration
   acknowledged work, no power command failed) AND a NORMAL control that lost at least one acknowledged step. Its best
   result is `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION` with `"qualified": false`. Record PA-11 PASS only if you
   also attest that the recorded `power_method` was a real hypervisor power cut (not a guest shutdown, not a process
   kill). If the control loses nothing, the rig is too weak: record BLOCKED, not PASS (`PHASE2A_POWER_LOSS_TEST_PLAN.md`).

Automated support (SIMULATED, never a qualification): `tests/phase2close/test_powerloss_harness.py` and a local
`simulate` run (process kill instead of power cut) prove the acks, the boot report, the comparison and the
recovery checks work end to end.

### PA-12 C7 cutover authorization (owner decision)

Not a test. The owner reads `PHASE2CLOSE_C7_READINESS.md` and either records BLOCKED with the open items or gives a
written authorization naming manifests, ports and launch entries (C7 gate 10). This runbook never performs cutover.

## 2. After the session

```powershell
.\.venv\Scripts\python.exe -I scripts\phase2close_acceptance.py collect $C --out ..\evidence\phase2close\acceptance_collected.json
```

It gathers every execution record of the campaign client, every `CLIENT_REFUSAL` line of the server log (VAL-1
observation: any `TICKET_CLOCK_OR_GENERATION` line now has a known cause and was retried once) and the gate log. Stop
the server window (Ctrl+C). The campaign folder can be deleted afterwards; nothing outside it was created.

## 3. Gate summary

| Gate | Needs | Status |
|---|---|---|
| PA-1 launch | owner at the PC | PENDING |
| PA-2 approve | owner | PENDING |
| PA-3 deny | owner | PENDING |
| PA-4 cancel before dispatch | owner (part 2 needs PA-10) | PENDING |
| PA-5 cancel after dispatch | owner + PA-10 | PENDING (blocked by EXE-1) |
| PA-6 close/restart/reconnect | owner | PENDING |
| PA-7 worker/server interruption | owner | PENDING |
| PA-8 Codex client-profile login | owner credential action | PENDING |
| PA-9 Claude client-profile login | owner credential action | PENDING |
| PA-10 native execution in worker | owner decision on EXE-1 + PA-8 | BLOCKED (EXE-1) |
| PA-11 power loss | owner VM + hypervisor | PENDING |
| PA-12 cutover authorization | owner decision | PENDING |
