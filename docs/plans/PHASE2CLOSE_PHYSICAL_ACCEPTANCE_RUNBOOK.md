# Phase 2 physical acceptance runbook

Date 2026-10-08. Author: Claude. Status: **PREPARED. No gate below has been performed by the owner.** Every gate starts
as PENDING.

**Updated 2026-10-08 (Phase 2 operational qualification, `PHASE2OQ_REPORT.md`):** EXE-1 resolved by qualifying the
NATIVE binaries (no `node`, no PATH change); PA-8 to PA-10 rewritten around `login-guide`, `status` and the Codex
sandbox-backend choice; PA-11 has a concrete VirtualBox/VMware method and the guest OS unclean-shutdown witness (D8);
new gate PA-13 (Chat -> supervised handoff, C6 Option B). The superseded closure wording of PA-8 to PA-11 is kept in
the accepted candidate `phase2close-candidate-20261008-f.zip`. A gate becomes PASS only when the owner performs it and records the observation with
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

The Codex sandbox backend of the client profile is NOT chosen for you (see PA-10 and decision EXE-1b). To choose it at
provisioning time add `--codex-sandbox unelevated` or `--codex-sandbox elevated`; without a choice the worker refuses
Codex records with `CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED` (fail closed).

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

Codex must be logged in INSIDE the acceptance client profile, never through your own profile (ISO-1: Codex ignores
`USERPROFILE`; only `CODEX_HOME` isolates it, and the worker refuses a Codex record unless the executor environment
names the client profile's Codex home). The script prints the exact commands; it never runs them, never reads or copies
a credential:

```powershell
.\.venv\Scripts\python.exe -I scripts\phase2close_acceptance.py login-guide $C --provider codex_cli
```

Run what it prints in a NEW, non-elevated PowerShell window (it clears provider token variables, sets the client-profile
homes, then runs the NATIVE `codex.exe login` and `login status`), and close that window afterwards. Then check the four
separate states and persist the qualification:

```powershell
.\.venv\Scripts\python.exe -I scripts\phase2close_acceptance.py status $C
.\.venv\Scripts\python.exe -I scripts\phase2close_acceptance.py qualify $C --provider codex_cli --model gpt-6-sol
.\.venv\Scripts\python.exe -I scripts\phase2close_acceptance.py status $C
```

`status` reports `installed`, `authenticated_client_profile`, `qualified` and `operational` separately: logged in is not
qualified, qualified is not operational. `qualify` probes the NATIVE binary with every provider credential variable
removed (D1) and writes a signed record ONLY when the probe and the client-profile login status both succeed.
PASS when `qualify` prints `"persisted": true` and `status` shows `authenticated_client_profile: true, qualified: true`.

### PA-9 native Claude login in the CLIENT profile (owner credential action)

Same discipline: `login-guide $C --provider claude_code` (Claude Code resolves its config through the process home, so
`USERPROFILE`/`HOME` set to the client home isolate it), then `status`, `qualify $C --provider claude_code`, `status`.
The native `claude.exe` from the npm package is qualified, not `claude.cmd`.

### PA-10 native execution inside the worker process

EXE-1 is resolved (2026-10-08): the worker runs the NATIVE `codex.exe` from the npm vendor directory, pinned with every
executable and library of that directory (33 files on this PC) and nothing resolved by name; its PATH stays
venv + System32 + git. Automated evidence (`evidence\phase2oq\`): in the REAL worker process the native record
composes; with no client login the harness is shown unusable and Approve is refused before the server sees it
(`HARNESS_NOT_USABLE`); in the worker ENVIRONMENT (auth gate substituted, scripted local model) a run reaches
`SETTLED_VERIFIED` and a mid-run cancel kills the sandboxed child. None of that is PA-10.

**Decision EXE-1b (owner, before PA-10): the Codex Windows sandbox backend of the client profile.** A fresh Codex home
has none and Codex then refuses every command ("blocked by policy"). Measured 2026-10-08 (`evidence\phase2oq\sandbox_probes\`):

| Backend | Setup | Writes outside the workspace | Network from sandboxed commands |
|---|---|---|---|
| `unelevated` | none | denied (verified) | **NOT blocked** (verified: localhost and example.com reached) |
| `elevated` | one-time administrator setup by Codex (sandbox accounts) | denied (Codex documentation) | blocked per Codex's own messages (NOT verified here) |

Choose one with `provision --codex-sandbox ...` (or write `[windows]` / `sandbox = "..."` in
`<client_root>\home\.codex\config.toml` yourself). For `elevated`, run the native `codex.exe` once interactively in the
login window of PA-8 and accept its Windows sandbox setup (administrator prompt; the exact prompt was not exercised here).

Then PA-10 is: in the real app (PA-1), choose the Codex row (it must now read `authenticated`, `native qualified`,
usable), run PA-5. PASS when the run completes with `SETTLED_VERIFIED` and a verified `pong.txt`-style result, and the
PA-5 cancel ends `UNCERTAIN`/`CANCELLED_AFTER_DISPATCH` with no `codex` process left in Task Manager.

### PA-11 controlled power-loss durability (throwaway VM)

Needs a throwaway Windows VM the owner may power off hard. Never this PC. This PC (2026-10-08 preflight): no Hyper-V
cmdlets, no VirtualBox, no VMware; the Windows hypervisor IS present (VBS/WSL2), so VirtualBox 7 and VMware Workstation
run on the Windows Hypervisor Platform (slower, supported). The guest must be Windows (the supervisor's containment is
Windows-only); it needs only stock Python 3.13 and four items of this tree (`uri_supervisor\`,
`scripts\phase2close_powerloss_harness.py`, `tests\phase2a\helpers\fake_executor.py`, and the folder layout).

Recommended rig: **VirtualBox 7** (free). Owner actions: install VirtualBox, download a Windows 11 evaluation ISO.
1. VM: 2 vCPU, 4 GB, 64 GB VDI on a SATA controller with host I/O cache OFF, and flushes honoured:
   ```powershell
   VBoxManage storagectl URI-PL --name SATA --hostiocache off
   VBoxManage setextradata URI-PL "VBoxInternal/Devices/ahci/0/LUN#0/Config/IgnoreFlush" 0
   ```
   NAT networking: the guest reaches the host's harness at `10.0.2.2` (VirtualBox maps it to the host loopback, so no
   firewall rule is needed).
2. Guest: build the bundle on this PC (`.\.venv\Scripts\python.exe -I scripts\phase2oq_powerloss_bundle.py`, writes
   `..\evidence\phase2oq\powerloss_guest_bundle.zip` with a SHA-256 `MANIFEST.json`), copy it into the VM, extract to
   `C:\pl\uri`, install Python 3.13, create a local auto-logon user, add a second virtual disk `D:` for the ledger (same
   cache settings), then in an elevated PowerShell inside the VM:
   `C:\pl\uri\guest\install_guest_task.ps1 -IAmInsideTheThrowawayVM` (FULL); later rerun it with
   `-Synchronous NORMAL -Ledger D:\pl_normal\ledger.db` for the control. The guest reads its own System event log at
   every boot (D8 witness); keep the default event log settings. (The installer was not exercised on a VM here.)
3. Host, FULL series (200 iterations):
   ```powershell
   .\.venv\Scripts\python.exe -I scripts\phase2close_powerloss_harness.py host --port 47710 --iterations 200 --out ..\evidence\phase2oq\powerloss_full `
     --power-off "VBoxManage controlvm URI-PL poweroff" --power-on "VBoxManage startvm URI-PL --type headless"
   ```
   VMware Workstation alternative: `--power-off "vmrun stop <vmx> hard" --power-on "vmrun start <vmx> nogui"`.
4. Control series: guest task with `--synchronous NORMAL`, fresh ledger folder, `--out ..\evidence\phase2oq\powerloss_normal`
   (any count; it must lose at least one acknowledged step, otherwise the rig is too weak: record BLOCKED).
5. Assess (the only verdict; recomputed from the raw `acks.jsonl`):
   ```powershell
   .\.venv\Scripts\python.exe -I scripts\phase2close_powerloss_harness.py assess --full ..\evidence\phase2oq\powerloss_full `
     --control ..\evidence\phase2oq\powerloss_normal --out ..\evidence\phase2oq\powerloss_assessment.json
   ```
   Requirements: FULL >= 200 iterations all PASS at `synchronous` FULL; NORMAL control lost >= 1 acknowledged step; the
   power-off command is a recognised hard-off form; and (D8, new) EVERY iteration carries the guest OS's own
   unclean-shutdown event (Kernel-Power 41 / EventLog 6008) created after that boot's ready time, so a guest shutdown or
   reboot cannot pass. Best result: `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION`, `"qualified": false`. Record PA-11
   PASS only if you also attest the power method was a real hypervisor power cut of THAT VM.

Automated support (SIMULATED, never a qualification): `tests/phase2close/test_powerloss_harness.py` and a local
`simulate` run (process kill instead of power cut) prove the acks, the boot report, the comparison and the
recovery checks work end to end.

### PA-12 C7 cutover authorization (owner decision)

Not a test. The owner reads `PHASE2CLOSE_C7_READINESS.md` and either records BLOCKED with the open items or gives a
written authorization naming manifests, ports and launch entries (C7 gate 10). This runbook never performs cutover.

### PA-13 Chat -> supervised handoff (C6 Option B, owner accepted 2026-10-08)

1. In Chat (same app session as PA-1), send a short message and wait for URI's reply to settle.
2. Under YOUR message expect "Make this a supervised task" (absent while a reply is still pending or awaiting its own
   approval; absent on installations without the supervised opt-in). Press it.
3. Expect the supervised screen with your words in the composer, the banner "Draft from the conversation. Nothing has
   been sent ...", "Next: choose an executor.", no executor selected, Send disabled. Nothing new appears in Chat.
4. Edit a word: expect "Edited since it left the conversation." Choose the deterministic row, Send, then Decline.
5. Press Back: the conversation is unchanged, your original message is still there.

PASS when 2-5 hold. Automated support: widget tests "C6 B ..." in `uri_ui/test/supervised_execution_screen_test.dart`
and `uri_ui/test/chat_supervised_handoff_test.dart`.

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
| PA-5 cancel after dispatch | owner + PA-10 | PENDING |
| PA-6 close/restart/reconnect | owner | PENDING |
| PA-7 worker/server interruption | owner | PENDING |
| PA-8 Codex client-profile login | owner credential action | PENDING |
| PA-9 Claude client-profile login | owner credential action | PENDING |
| PA-10 native execution in worker | PA-8 + decision EXE-1b (sandbox backend) | PENDING (EXE-1 resolved; EXE-1b open) |
| PA-11 power loss | owner VM + hypervisor install | PENDING |
| PA-12 cutover authorization | owner decision | PENDING |
| PA-13 Chat -> supervised handoff | owner | PENDING |
