# UI phase tasks

Status vocabulary (per brief): Researched/proposed, Prototyped, Implemented, Tested, Independently accepted, Integrated, Production-active.

| ID | Task | Status | Evidence |
|---|---|---|---|
| T0 | Isolation: branch + worktree + baseline record | Implemented | `UI_ISOLATION_EVIDENCE.md` |
| T1 | Obsidian Cyan palette + `UriGlass` + `GlassPanel` + `EffectsSettings` | Tested | `test/living/energy_orb_test.dart` (theme test), screenshots |
| T2 | `CompanionState`, `CompanionSignal`, sources | Tested | `living_shell_test.dart` (priority, AppState-derived thinking) |
| T3 | `EnergyOrb` painter + shader + reduced mode | Tested | `energy_orb_test.dart` (22), screenshots 01-03, 12 |
| T4 | `UiPresentationController`, command parser | Tested | `presentation_controller_test.dart` (6) |
| T5 | `LivingShell` spatial transitions + keyboard | Tested | `living_shell_test.dart` (orb identity, Back, Esc/Ctrl+N) |
| T6 | Companion mode view | Tested | screenshots 01-03, 12 |
| T7 | Workspace mode view | Tested | screenshots 04-08, 13; shell tests |
| T8 | Dashboard mode view | Tested | screenshot 09-10; shell test (badges, sources) |
| T9 | Mock work simulator + contracts | Tested | `work_simulator_test.dart` (3), `UI_INTERFACE_CONTRACTS.md` |
| T10 | Onboarding flow | Tested | `onboarding_test.dart` (2), screenshot 11 |
| T11 | Intelligence overview + memory graph prototype | Tested (graph: Prototyped) | `intelligence_snapshot_test.dart` (2), shell test, screenshot 07 |
| T12 | Tests + screenshots + performance/accessibility notes | Tested | `UI_TEST_EVIDENCE.md` |
| T13 | Docs: design reference, status, contracts, test evidence, integration plan | Implemented | `docs/ui_phase/*.md`, `docs/design_library/approved/living_companion_2026-10-08.md` |
| T14 | Independent Codex read-only review request | see `UI_TEST_EVIDENCE.md` section 6 | |

## Open items for the owner

* Accept or reject the visual direction (Obsidian Cyan + orb).
* P2-6 target line and C6 decisions (see `UI_INTEGRATION_PLAN.md` section 0).
* Whether Companion mode should resize the OS window (I5) in the integrated app.
