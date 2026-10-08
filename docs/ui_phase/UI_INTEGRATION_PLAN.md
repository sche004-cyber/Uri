# Proposed integration plan: Living Companion into URI

Date: 2026-10-08. Author: Claude. Status: PROPOSAL for the owner; nothing below has been done. The candidate stays on `phase/ui-living-companion` until an independent acceptance (Codex read-only review + User live acceptance) says otherwise.

## 0. Preconditions (owner decisions, in order)

1. **Target line (P2-6 in `PHASE2CLOSE_UI_READINESS.md`).** This candidate is built on the published consolidation tip `037229c` (`integration/git-sync-20261008`). If the owner chooses the `_V1` line instead, the living files are additive and port unchanged, but the four `_V1`-only pieces (voice strip, Companion Compact window controller, desktop harness widgets) would become real sources for Listening and for the Companion window size.
2. **C6 decision 2** (Chat on the paired runtime). Until decided, the Workspace conversation uses `AppState.ask` exactly as Hybrid Chat does.
3. **Visual direction acceptance.** The User accepts or rejects Obsidian Cyan + orb (record under `docs/design_library/approved|rejected/`).

## 1. Integration slices (each independently reviewable)

| Slice | Change | Touches | Risk |
|---|---|---|---|
| I1 | Merge the additive files (`lib/living/**`, `lib/theme/glass_theme.dart`, `shaders/`, `test/living/**`, `docs/ui_phase/**`) plus the two additive edits (`uri_theme.dart` fifth palette, `pubspec.yaml` shader entry) | no Hybrid screen, no service | low; 252 tests pass with them |
| I2 | Mount behind a preference: `Settings > Appearance > "Living Companion (preview)"` toggle (`uri.living.enabled`), read in `UriApp` to choose `LivingShell` or `AppShell` as the post-login tree, both over the same `AppState` | `app.dart` (one branch), `appearance_settings_screen.dart` (one switch) | low; default off |
| I3 | Real `CompanionStateSource` over `SupervisedRuntime` (contract section 1 in `UI_INTERFACE_CONTRACTS.md`) | new file in `lib/living/companion/`; reads the existing opt-in file and worker frames; no worker change | medium; needs the Phase 2 worker running, gated by the same opt-in |
| I4 | `ReadinessSource` adapter over `preflight` / `harness_discover` / `GET /devices` / grants | new file | medium; read-only frames only |
| I5 | Companion window sizing: reuse `platform_window_controller.dart` (`setCompactWindowMode`) on Companion mode enter/exit, same edge-triggered pattern as `UriHome` | `main.dart` hook already exists; one listener in `LivingShell` | low |
| I6 | `WorkItemSource` adapter: `GET /tasks` + `execution_list`; `create()` becomes a `TaskHandoff` draft, never an execution | new file | medium; approvals keep going through `approveTask` / `execution_begin` |
| I7 | Brain-originated `ui_present` frame (contract section 5): worker-side frame definition is a Supervisor-bridge change and therefore AMBER (shared contract) | `uri_supervisor_bridge/worker_service.py` (owner approval) | needs Phase 2 process |
| I8 | Voice source for Listening/Speaking | depends on the C6 voice-parity decision | out of scope until decided |

## 2. What must stay true after integration

* Presentation never authorizes (tests: typed "approve" never begins an execution; commands cannot send text).
* The Hybrid app's 205 tests keep passing with the living files present (verified now).
* `main.dart` remains plugin-isolated; the living root is plugin-free (verified: `lib/living/**` imports no plugin).
* Frozen files untouched: `paired_runtime*.dart`, `settings_shell.dart`, `supervised_execution_screen.dart`, everything under `uri_core/`, `uri_supervisor*`.

## 3. Acceptance evidence to produce per slice

For each slice: `flutter analyze` (0 errors), `flutter test` (all), a screenshot set from the real build via `docs/ui_phase/tools/capture_screenshots.ps1`, and an entry in `UI_TEST_EVIDENCE.md`. I3/I4/I6 additionally need a live Dart test against the real worker in the Phase 2 harness (`supervised_runtime_live_test.dart` pattern).

## 4. Rollback

Every slice is additive or behind `uri.living.enabled`. Rolling back is deleting `lib/living/`, the shader entry, the fifth palette and the toggle; no data migration exists (only `uri.living.*` preference keys, which are ignored when absent).
