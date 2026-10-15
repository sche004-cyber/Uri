# Ember V2.1 - Live Windows qualification

## Setup

- **App:** the real Windows app, production `main()`, built from this worktree (V2.1 assets at `9933ca2b`).
- **Backend:** the real integrated worker, paired Core server (port 18300) and Runtime v1 Brain, from the disposable
  runtime `uri-fire-companion-v2-rt` (receipt `a86ed350`, backend unchanged since V2).
- **Harness:**
  - `live/run_fire_v21_live.py` is V2's runner retargeted to this worktree.
  - `live/fire_v21_live_driver.dart` is V2's driver; the only change is that the coexistence turns alternate Ember
    and Solar.
  - Input transport is automated (Flutter taps and TestTextInput in the real window); nothing in URI is mocked. This
    is **automated UI interaction, not a human usability study**.
- **Preferences:** redirected to a fixture folder; the owner's own preferences are never touched.
- **GPU:**
  - The Brain host starts only after the runner sees the lease FREE and no `llama-server` running.
  - It goes through the guarded launcher with `-OverrideGpu` (OD-V21-1: the VRAM fit was 210 MB short because of
    other GPU users).
  - The driver proves the Brain is ours by the server pid in this runtime's `brain_host.json`.
  - Graceful stops only, through the runtime's own stop file.

## Runs

| Run | Mode | Result | Evidence |
|---|---|---|---|
| 1 | First-time user, real Brain | **PASS**, all journeys | `evidence/live/run1_first/` |
| 2 | Returning user, no Brain | **PASS** for every journey step. The test process reported one failure at teardown: `OiConversation was used after being disposed` (`refreshStatus` after dispose). This is the known pre-existing defect PRE-2 in unchanged canonical code (`oi_conversation.dart`), the same as V2's run 2. | `evidence/live/run2_returning/` |

Assets in these runs: the painted V2.1 build (`9933ca2b`). The transparency build (`73e84a6d`) is covered by the
live run 3 in the section "Transparency build (run 3)" below.

After the runs, none of this session's processes were left. The lease was then taken by the parallel FCV recovery
session, whose own Brain and UI were not touched.

## Journeys (run 1 unless noted)

| # | Journey | Result |
|---|---|---|
| 0-2 | First-time user: default companion (Solar), select Ember in Settings | PASS. Stored choice `ember`; one Ember widget (`first-01..03`). |
| 3 | Startup before the Brain | Ember shows **depleted** with "Unavailable - Brain STOPPED", then "unavailable" through loading. This is the known F-STARTUP behaviour (`04_STARTUP_PROPOSAL_V21.md`), unchanged because the fix is AMBER. (`first-04`) |
| 3b | Blinks before the Brain | 4 blinks in 15 s; gaps 3.6, 0.5 (double blink), 3.8 s |
| 4 | Wake phrase | NOT AVAILABLE: no wake-word recogniser in canonical URI |
| 5 | Brain ready, idle | PASS. Brain READY in about 2 min, ours (`our_brain: true`, pid 12336). Ember idle shows the whole figure inside the disc over its painted backdrop (`first-05`). |
| 5 | Conversation | PASS. "Hello URI" -> COMPLETE at 139.6 tok/s. Companion thinking -> **success** ("Done"), the joyful clip (`first-06..08`). The short greeting recorded no `speaking` state; `speaking` was recorded in the coexistence and recovery turns. (Corrected after review R1-09.) |
| 6 | Companion <-> workspace, dashboard | PASS (`first-09`, `first-10`) |
| 7 | Task needing approval | PASS. Approval card shown, companion `awaitingApproval` (`first-11..12`). |
| 8 | Task completed | PASS. Core `SETTLED_VERIFIED`, companion success -> idle after the hold (`first-13..14`). |
| 8c | Blinks in idle | 4 blinks in 20 s; gaps 0.5 (double), 5.1, 5.9 s. Irregular. |
| C | Coexistence, Ember and Solar alternating, 3 pairs | All COMPLETE; tok/s in `05_MEASUREMENTS_V21.md` |
| 9 | Recoverable error: the runner stops our Brain | PASS. Companion `unavailable`, then "Attention needed" with a clear Brain-unavailable card; the request fails with `BRAIN_UNAVAILABLE`. The code is evidenced by the screenshot `first-16`; the driver's structured record has it as null (R1-09). |
| 10 | Recovery: our Brain restarted (lease free again) | PASS. Reply "15" COMPLETE; states error -> thinking -> speaking -> success (`first-17`). Unlike V2 run 4, the lease was not taken by another session in the gap, so this journey is no longer BLOCKED. |
| R1 | Returning user (run 2) | PASS. Ember restored with no choice (`returning-02`). |
| R2 | Blinks while shown (run 2) | 5 blinks in 25 s; gaps 3.7-4.9 s |
| R3 | Settings with the voice section (run 2) | PASS. No framework errors (PRE-1 stays fixed). |

## UX notes from the screenshots (pre-existing, not V2.1 regressions)

- **F-STARTUP:** a first-time user sees the sad, depleted Ember until the Brain is ready. Proposal in
  `04_STARTUP_PROPOSAL_V21.md`.
- **PRE-2:** the teardown race above.
- **Simulated badges:** the workspace side panel shows SIMULATED documents and results. That is canonical UI
  behaviour, not Ember.

## V2.1-specific observations

- **Presentation:** the whole figure (feet, floor light, crest) is visible in the disc, over the painting's own
  brown backdrop. V2 cut off the feet and crest.
- **Small sizes:** in the workspace sidebar avatar the whole figure is now shown, so it is smaller than V2's
  head-and-shoulders crop; the face stays readable (`first-08`, `first-16`).
- **Error and concern:** the concerned expression (V2's derived clip) reads correctly over the new backdrop
  (`first-16`).

## Transparency build (run 3)

- **When and what:** 2026-10-15 08:35 UTC, returning-user mode, no Brain, on the transparent assets of `73e84a6d`.
  Assets were unchanged through the final commit. Atlas SHA-256 prefixes from `manifest.json`: idle `d042061fe1c4`,
  depleted `a5b1bcece9be`, joyful `ca36a998e7c5`.
- **Evidence:** `evidence/live/run3_returning_transparent/`.
- **Result:** PASS for R1-R3. Ember was restored with no choice. Blinks were irregular: 5 in 25 s, gaps 3.1-6.3 s.
  Settings opened with no framework errors. The test process again exited with the PRE-2 teardown failure.
- **What the screenshots show:** Ember drawn from its transparent atlas inside the current host. There is no square
  and no visible disc edge; the depleted haze reads as soft atmosphere (`returning-02`).
- **Limits (review R2-03):**
  - With no Brain the state is `unavailable`, so only the **depleted** clip was seen live. The glow-only clips (idle,
    joyful, thinking and others) were seen only in the perf harness window (`evidence/perf_transparent/*/ember_*.png`)
    and in the rendering tests, not in the full app.
  - `returning-brain_host.json` in this folder is a stale copy of run 2's file: no Brain host ran in run 3. Ignore it.
