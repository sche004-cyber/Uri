# Ember V2 - Live Windows Qualification

## Setup

- **Date and machine:** 2026-10-15, owner's PC (RX 7900 GRE 16 GB, Windows 11).
- **UI tree:** this branch at `a86ed350`.
- **Runtime:** disposable materialization of the same commit (`C:\Users\cheta\Development\uri-fire-companion-v2-rt`,
  receipt `candidate_head a86ed350`), installation `ws-firev2`, port 18300, started by the guarded working-system
  launcher.
- **Brain:** Runtime v1 (qwen3.6-35b-a3b, llama.cpp Vulkan). It was started by this runtime's own Brain host under
  the machine-wide GPU lease, with `-OverrideGpu` (OD-8: authorised for this run, lease to be followed).
- **Method:** the same as V1.
  - The ORIGINAL production `main()` runs in a real Windows window, driven by `integration_test`
    (`v2/live/fire_v2_live_driver.dart`, `v2/live/run_fire_v2_live.py`).
  - URI, its worker, the Core server and the Brain are all real. Only the input is automated: Flutter taps and
    TestTextInput, with no human and no physical mouse.
  - Preferences and APPDATA are redirected to fixture folders.
- **Harness edits:** the live-harness edits made after `a86ed350` (the OD-8 guards) stayed uncommitted until the
  runs were over, so the UI tree stayed at the runtime receipt's commit.

Evidence: `evidence/live/` contains one folder per run, each with screenshots (JPEG), observations, the runner log,
GPU samples and the Flutter log.

## Runs (all kept, none deleted)

| Run | What happened | Kept as |
|---|---|---|
| 1 | Between the lease check and the launch, another session (`uri-fcv-recovery-20261014`) took the lease and started its own Brain. Our launcher **attached** to that running server (`health 503 (attach)`; the worker reported `owned: false`, pid 5964). The run was **stopped before any turn was sent**. This was the right action under OD-8: no request may go to another session's Brain. Journeys 1-3 were valid until then. | `run1_aborted/` |
| 2 | Returning user (no Brain needed): **PASS** (see below). The test process reported one failure, raised **at teardown**: `OiConversation was used after being disposed`. `monitorTick` called `notifyListeners` after an in-flight probe completed, once the driver had disposed the app. That code (`oi_conversation.dart:269`) is unchanged canonical code: finding **PRE-2**. Every journey assertion before teardown passed. | `run2_returning/` |
| 3 | Our own Brain host took the lease and reached READY (148 tok/s calibration), but the driver's first ownership check was wrong. The worker's `owned` flag describes the worker, not the run, so the check read false for our own Brain, and the driver recorded BRAIN BLOCKED without sending turns. The Brain host was stopped gracefully (stop file; nothing killed; lease released). Harness defect, repaired: ownership is now proven by the server pid in this runtime's `brain_host.json`. | `run3_blocked/` |
| 4 | Full first-time run with our own Brain: journeys 1-9 completed (results below). Right after our Brain host stopped for the error journey, the other session took the lease and started its Brain (pid 4536). Our recovery launcher attached to it while it was still loading. The driver was **stopped before the recovery turn**: no request reached that Brain. Journey 10 is therefore **BLOCKED**. | `run4_first/` |

Guards added to the harness after runs 1 and 3 (OD-8):
- The runner starts the Brain only when the lease is FREE and no `llama-server` is running.
- The driver runs Brain journeys only when the Brain's pid equals the server pid recorded by this runtime's own
  Brain host.
- Known gap: the recovery restart was not guarded by the runner, which is why run 4 was stopped by hand. Recorded
  here; the harness is not product code.

## Journeys

| # | Journey | Result | Evidence (run 4 unless noted) |
|---|---|---|---|
| F1 | **First-time user start** | PASS: fresh preferences, no stored choice; shell in 15.1 s; default companion **Solar** | `first-01` |
| F2 | **Select Ember** in the real Settings picker (thumbnail tile) | PASS: Solar -> Ember through the picker; stored `uri.living.companion.choice = ember` | `first-02`, `first-03` |
| F3 | **First impression / startup** | PASS (behaviour) / FINDING: while the Brain loads, Ember shows *Unavailable - Brain LOADING* with the depleted face (**F-STARTUP**, `02_STATE_MATRIX_V2.md`) | `first-04` |
| 3 | Idle with the Brain ready | PASS | `first-05` |
| 4 | Wake phrase | NOT AVAILABLE: canonical URI has no wake-word recogniser. Not simulated. | observations |
| 5 | Conversation | PASS: single click shows the prompt bubble; "Hello URI" -> COMPLETE at 136 tok/s; companion **thinking -> speaking -> success** | `first-06..08` |
| 5b | **Success signalling (F-SUCCESS)** | **PASS, repaired**: the joyful expression shows after an `ok` turn ("Done"). In V1 it was never reached. | `first-08` |
| 6 | Conversation <-> dashboard | PASS | `first-09`, `first-10` |
| 7 | Real task with approval | PASS: "remember that the science lab is closed on Friday" -> APPROVAL_REQUIRED; companion awaitingApproval | `first-11`, `first-12` |
| 8 | Task completed | PASS: Core **SETTLED_VERIFIED**; companion **success -> idle** after the 4 s hold | `first-13`, `first-14` |
| B | **Natural blinking, live** | PASS: irregular blinks from the real widget. Before the Brain: 5.9 / 11.2 / 11.7 s (a double blink). In idle: 1.2 / 6.0 / 11.5 / 12.0 / 16.1 s (gaps 4.8, 5.5, 0.5, 4.0). Returning user: gaps 3.0 / 6.5 / 4.5 / 6.3 s. Fully closed lids were observed. | observations `3b`, `8c`, `R2` |
| 9 | Recoverable error | PASS: Brain host stopped gracefully; companion **Unavailable** (depleted); a request then -> **error** (concerned) | `first-15`, `first-16` |
| 10 | Return to idle after recovery | **BLOCKED**: the GPU lease was taken by a parallel session (see run 4). Not simulated. | runner log |
| R1 | **Returning user** | PASS (run 2): a second start with the same preferences restores **Ember** without any choice | `run2_returning/returning-01..02` |
| R3 | Settings with the voice section (**PRE-1**) | **PASS, repaired**: **0** "setState() or markNeedsBuild() called during build" assertions in all V2 runs, against **12** in the V1 live run | flutter logs |

## Brain coexistence (live, run 4)

Same request, 4 sentences each:

| Turn | Decode speed |
|---|---|
| Ember on screen, turn 1 | 111.8 tok/s |
| Ember on screen, turn 2 | 49.8 tok/s |
| Solar on screen, turn 1 | 48.3 tok/s |
| Solar on screen, turn 2 | 48.8 tok/s |
| Greeting | 136.3 tok/s |

Conditions while the Brain ran:
- It already had 2.1 GB outside device memory (`brain_host.json` residency `non_local_mib 2143`).
- Next to it were the desktop (0.39 GB), our window (0.37 GB) and **another session's URI window** (pid 5204, 0.33 GB).

The fall from about 112 to about 49 tok/s happened between two Ember turns, with nothing changed by this run.
After it, Ember and Solar measured the same.

**Verdict:** there is no evidence that Ember slows the Brain. The controlled numbers are in `03_MEASUREMENTS_V2.md`:
GPU 3D 0.14-0.29 % for Ember against 3.8-11 % for Solar. Even so, a clean A/B comparison of Brain speed is
**INCONCLUSIVE**: there are 2 samples each, the Brain was demoted, and another session's processes were present.
