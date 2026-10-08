# UI implementation status

Date: 2026-10-08. Branch `phase/ui-living-companion`, worktree `C:\Users\cheta\Development\uri-ui-phase`, baseline `037229c`. Status vocabulary from the brief: Researched/proposed, Prototyped, Implemented, Tested, Independently accepted, Integrated, Production-active.

Nothing on this page is Independently accepted, Integrated or Production-active. "Tested" means automated tests in `uri_ui/test/living/` pass and the feature was exercised in the real Windows release build (screenshots in `docs/ui_phase/screenshots/`).

## Feature table

| Feature | Status | Where | Notes |
|---|---|---|---|
| Obsidian Cyan palette, `UriGlass`, `GlassPanel`, `AmbientBackground` | Tested | `theme/uri_theme.dart`, `theme/glass_theme.dart`, `living/widgets/glass_panel.dart` | fifth `UriThemeChoice`; four Hybrid themes untouched; contrast checked (design reference section 2) |
| Energy Orb: nine states, particles, halo, rim, state overlays | Tested | `living/companion/energy_orb.dart` | render tests per state (effects on/off), pixel-difference test for every state pair (A1), tween test, theme test |
| Energy Orb: seven styles x ten palettes (owner's references) | Tested | same file; `UI_ORB_OPTIONS.md` | every style renders every state; every palette renders on every style (idle + thinking); state tints override palettes; owner choice pending |
| Energy Orb: cursor gust reaction and click poke + question bubble | Tested | same file; `presentation/living_shell.dart` | gust test over all variants; click/double-click tests |
| `SupervisedCompanionSource` (Phase 2 worker contract) | Tested (fake runtime), not wired | `living/companion/companion_sources.dart` | `companion_sources_test.dart` |
| Energy Orb: runtime fragment shader core (plasma / sun / liquid styles, two hues) | Implemented, Tested in the release build | `shaders/orb_core.frag`, `living/companion/orb_shader.dart` | loads under Impeller on Windows (release build screenshots); falls back to the gradient core if the asset fails; widget tests run both paths without exceptions. Not measured on a GPU-less machine. |
| Reduced effects / reduced motion | Tested | `living/companion/effects_settings.dart` | OS `disableAnimations` honoured at startup in `main_living.dart`; test asserts no `BackdropFilter` and no shader under reduced effects (A9) |
| Glass blur policy | Tested | `living/widgets/glass_panel.dart` | blur is opt-in (composer only); dashboard tiles never blur (profile evidence in `UI_TEST_EVIDENCE.md`) |
| Companion state sources and priority merge | Tested | `living/companion/companion_sources.dart` | `AppStateCompanionSource` derives from UI-side facts (unavailable/thinking/awaitingApproval-with-proposal/working/success-with-result/error) and is flagged simulated under the mock client; listening/speaking exist only as mock events |
| UI-state controller + local command parser | Tested | `living/presentation/presentation_controller.dart` | sealed vocabulary; cooldown; Back; origin tracking |
| Living shell: spatially continuous transitions, one orb element | Tested | `living/presentation/living_shell.dart` | element identity asserted across all three forms; Esc / Ctrl+1-3 shortcuts |
| Companion mode | Tested | `living/screens/companion_mode_view.dart` | status line, "Review and decide", composer, mode chips |
| Workspace: conversation (reused `UriConversationPane`) + living composer | Tested | `living/widgets/living_composer.dart`, `workspace_mode_view.dart` | composer re-implemented (not `UriCommandDock`) to intercept commands; same `AppState.ask` path |
| Workspace: tasks (approvals from `AppState.tasks` + simulated work), progress, history | Tested | `workspace_mode_view.dart` | approve/cancel buttons only; mock client's `approveTask` path exercised by the Hybrid tests |
| Workspace: documents / office templates | Prototyped + Tested (mock) | `workspace_mode_view.dart`, `living/contracts/work_items.dart` | all data Simulated; creates scripted work |
| Workspace: settings (harness, Brain, reasoning, approval boundary, permissions, appearance, effects) | Tested | `workspace_mode_view.dart` | Brain selection uses the real `setActiveBrain` (mock client); harness list and permissions Simulated; reasoning mode is UI-only and says so |
| Workspace: context panel (Now, Executor, Context & files, Results) | Tested | `workspace_mode_view.dart` | opens at >= 1180 px or on demand |
| Dashboard: eight sourced tiles | Tested | `living/screens/dashboard_mode_view.dart` | every mock-backed tile badged Simulated; no unbacked metric |
| Onboarding: eight steps | Tested | `living/screens/onboarding/living_onboarding_flow.dart` | writes real `UserPreferences` (autonomy, focus areas, completion); connection test uses `AppState.checkConnection` (mock answers; badged) |
| Intelligence overview: pipeline, executor facts, signal sources | Tested | `living/screens/intelligence/intelligence_overview_view.dart` | facts only after Codex round 1 MAJOR 3: route is never inferred ("not reported by this client"), intent/approval/receipt are `done` only when an understanding / recorded decision / result exists; no reasoning text |
| Memory graph | Prototyped | same file | static ring layout over `MemoryEntry` rows; labelled PROTOTYPE on screen |
| Mock-mode entry with demo hooks | Tested (manual run + screenshots) | `lib/main_living.dart` | env vars documented in the file header |
| Performance sampler | Implemented | `living/perf_logger.dart` | numbers in `UI_TEST_EVIDENCE.md` |
| Adapter contracts | Researched/proposed (+ mocks Tested) | `living/contracts/*.dart`, `UI_INTERFACE_CONTRACTS.md` | no Core/Supervisor change |
| Companion OS window sizing | Researched/proposed | `UI_INTEGRATION_PLAN.md` I5 | the Hybrid `platform_window_controller` exists; deliberately not wired in this phase |
| Voice (listening/speaking) | Researched/proposed | contracts section 1 | no source in this tree |
| Blender / GLB assets | Researched, not adopted | `UI_PHASE_PLAN.md` 2.1 | Blender absent; procedural chosen |

## Which interactions work in the running preview

Typing and sending (mock replies, approvals via the Hybrid turn cards), `URI dashboard|workspace|companion|tasks|documents|intelligence|settings`, clicking the orb (poke + question + composer focus), double-clicking it (Workspace), sweeping the cursor over it (gust), choosing an orb style, the mode chips/rail items, Back after a command, starting a letter/spreadsheet/document/research item and approving or cancelling it, selecting a harness (mock) and a Brain (mock client), changing the approval boundary, reasoning mode, theme and effects, walking or skipping onboarding, re-checking readiness, Esc and Ctrl+1/2/3.

## What remains mocked

Harness discovery and qualification, clients, permissions/grants, readiness checks, all office work and documents, listening/speaking states, and (because `main_living.dart` uses `MockUriClient`) every `AppState` fact: conversation replies, tasks, providers, capabilities, memory entries, devices. The Simulated badge marks each of these on screen.
