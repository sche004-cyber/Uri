# Ember - Live Windows Qualification

Run: 2026-10-14 19:44-19:55 UTC on the owner's PC (RX 7900 GRE 16 GB, Windows 11).
UI tree: this branch at `59157120`. Runtime: disposable materialization of the same commit
(`C:\Users\cheta\Development\uri-fire-companion-rt`, receipt `candidate_head 59157120`), provisioned installation
`ws-fire`, port 18300, started by the guarded working-system launcher (self-test: real installation ok, every
negative refusal held). Brain: Runtime v1 (qwen3.6-35b-a3b, llama.cpp Vulkan) under the GPU lease with the owner's
one-run `-OverrideGpu` (`evidence/live/OWNER_GPU_OVERRIDE_AUTHORIZATION.json`).

Method: the ORIGINAL production `main()` in a real Windows window, driven by `integration_test`
(`live/fire_live_driver.dart`, `live/run_fire_live.py`). URI, its worker, Core server and Brain are real; only the
input is automated (Flutter taps and TestTextInput, not a physical mouse or keyboard, and no human). Preferences and
APPDATA are redirected to a fixture folder; the owner's own preference file was hashed before and after
(`689C8685...340E` both times). UI-first order: the Brain host started only after the window reported ready.
Evidence: `evidence/live/` (16 screenshots in `screens/`, `observations.json`, `runner-log.json`,
`gpu-samples.json`, `brain_host.json`, `frames_summary.json`, `flutter-test.log`, `live_grid.jpg`).

## Journeys

| # | Journey | Result | Evidence |
|---|---------|--------|----------|
| 1 | Start URI | PASS: shell in 10.3 s; companion shows Unavailable while no Brain is loaded (depleted Ember). | 01, observations "1 start" |
| 2 | Select the fire companion | PASS through the real Settings picker (scroll, tap the Ember card); choice persisted (`uri.living.companion.choice = ember`). Note: the fixture preferences kept Ember from an earlier attempt, so the "default companion" recorded at start was already Ember; the tap still re-selected it. The default for a new install is unchanged (Solar), asserted by tests. | 02, 03 |
| 3 | Idle | PASS: idle Ember in Companion mode once the Brain was READY. | 05 |
| 4 | Wake phrase | NOT AVAILABLE: canonical URI has no wake-word recogniser. Not simulated. | observations "4 wake phrase" |
| 5 | Listening and responding | PARTIAL: single click showed URI's prompt bubble ("I'm here. What's next?") in Companion mode; a typed turn "Hello URI" from the companion composer moved to the Workspace conversation and completed (COMPLETE, 2.0 s). UX-1: the bubble overlaps the "Idle" status label under the companion (screenshot 06); not yet checked whether the same happens with Solar. Companion states observed from the authoritative source: thinking -> speaking -> idle. No microphone turn was made (listening with a real voice not exercised in this run). | 06, 07, 08 |
| 6 | Conversation <-> dashboard | PASS: double click opened the Workspace; Dashboard shown; back to conversation. | 09, 10 |
| 7 | Real task | PASS: "remember that the science lab is closed on Friday" -> Core APPROVAL_REQUIRED, approval card, companion awaitingApproval (listening pose + pulse). | 11, 12 |
| 8 | Task completed | PASS (task) / FINDING (expression): Core SETTLED_VERIFIED, "Done. The result was independently verified by URI". The companion went straight to idle: the integrated-profile companion source never emits `success`, so the joyful expression is not reached in the working system (F-SUCCESS). | 13 |
| 9 | Recoverable error | PASS: Brain host stopped through its own stop file (graceful, lease released); companion Unavailable (depleted). A request then failed with "The local Brain is not ready (STOPPED)"; companion showed Attention needed (concerned). | 14, 15 |
| 10 | Return to idle | PASS: Brain restarted (launcher, UI already open); "What is 9 plus 6?" -> "15"; companion thinking -> speaking -> idle. | 16 |

The `flutter test` process reported FAILED although every journey completed: 12 framework assertions
"setState() or markNeedsBuild() called during build" were raised by `VoiceInputSettings.initState` ->
`LiveVoiceService.ensureStarted` when the Settings list builds its voice section. That code is canonical and
unchanged by this branch (PRE-1, pre-existing defect; follow-up proposed).

## Performance in the live run (debug build, so frame times are inflated)

`evidence/live/frames_summary.json`: idle phase p50 2.6 ms, p90 3.3 ms, 0.4 % frames over 16.7 ms; error phase
p50 3.8 ms, 0.3 %. During generation (text streaming in the conversation) 11-21 % of frames exceeded 16.7 ms in this
debug build; a profile-build measurement during generation was not made.

## Brain coexistence (M-4)

- The Brain does not fit honestly on this card next to the desktop: 15.3 GB required, 13.5 GB free (dwm 1.4 GB,
  URI window 0.33 GB, other apps 0.35 GB). It ran only because of the one-run override, and URI itself reported:
  "Brain: Ready - GPU memory taken. Another app took GPU memory after the Brain loaded (1.0 GB moved to system
  memory)" (screenshot 16 area, conversation panel).
- Decode speed in that demoted state: greeting 48.2 tok/s; same 88-token prompt with Ember on screen 49.7 and
  52.5 tok/s; with Solar 48.3 and 82.3 tok/s; after the Brain restart 67.7 tok/s (3 tokens). The start-up speed check
  reported 133 tok/s before the demotion.
- Verdict: INCONCLUSIVE for "Ember vs Solar" (two samples each, high variance, Brain already demoted by memory it
  could not get). What is measured: Ember holds about 40-65 MB more dedicated VRAM than Solar while shown
  (decoded atlases) and frees it when another companion is chosen; Ember's GPU time is about 4 % of Solar's.
  On a card with no margin, 40-65 MB is part of the margin the Brain already lacks.
