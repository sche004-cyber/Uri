# P-GOV-1: perf-runner adoption (handoff to the companion-voice session)

Date: 2026-10-10. From: the final integration session. Status: **HANDOFF, not implemented on the canonical branch.**

`P_GOV_1_HANDOFF.md` item 3 names `rnd/voice/run_perf.ps1`, `rnd/companions/settings/run_companion_perf.ps1` and
`rnd/companions/settings/brain_contention.py`, and says the companion-voice session owns them. This session
implemented the advisory and the canonical caller (`docs/working_system/tools/capture_ws.ps1`). It does not change the
companion-voice runners. A first attempt to change them (rounds 1-10 of the Codex P-GOV-1 review) was reverted, and
the findings from those rounds are passed on here so the owner can adopt the advisory in one go.

## What the canonical branch provides

`python -m uri_operational_intelligence.gpu_lease advise --window [--mib 480] [--wait 1800]` prints JSON and exits
GO 0 / WAIT_HEAVY 75 / WILL_DEGRADE_BRAIN 76. The command is read-only and never takes the lock. It does not wait for a
lease held by the caller's own `gpu_lease run` (`own_lease: true`). It fails closed (WAIT_HEAVY) when the lease or the
census cannot be read, when per-process counters are missing, when more than 1 GiB of GPU memory is unattributed, and
when a Brain-sized process cannot be identified. Only a `llama-server` holding at least 12 GB counts as a resident
Brain.

## What a runner needs (from the Codex review findings)

1. Call the advisory before opening the window. Store the JSON next to the run.
2. If the verdict is not GO or WILL_DEGRADE_BRAIN, open no window and measure nothing.
3. A perf benchmark that gets WILL_DEGRADE_BRAIN marks the run invalid. Its summary must exclude or label that run.
4. Before any preflight, remove the old json, samples and advisory files of a reused tag. Stop if removal fails.
5. Print `LAUNCHED` only when the window exists (`MainWindowHandle != 0`). Report no window as skipped.
6. In `brain_contention.py`, start the UI-first server only after a real `LAUNCHED`. Read the runner's output with one
   reader that keeps a real deadline.
7. Clean up only the window this run launched. Check its pid together with its creation time and executable. Never
   stop a process by executable path: the owner's own window of the same build must survive. Clean up even when the
   runner has already exited, and mark that measurement invalid.
8. Summaries must ignore JSON files that are not perf runs, and must keep the file tag separate from the display label.
