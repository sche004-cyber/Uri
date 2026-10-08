# URI UI phase: Living Companion

Date: 2026-10-08. Author: Claude. Status: PLAN FROZEN for slices 1-7 (this document), implementation tracked in `UI_IMPLEMENTATION_STATUS.md` and `UI_TASKS.md`.

Branch `phase/ui-living-companion`, worktree `C:\Users\cheta\Development\uri-ui-phase`, baseline `037229c` (see `UI_ISOLATION_EVIDENCE.md`).

## 1. Acceptance criteria (defined before implementation)

| # | Criterion | How it is proven |
|---|---|---|
| A1 | A recognizable, animated URI Energy Orb with distinct, intuitive states: unavailable, idle, listening, thinking, speaking, working, awaiting approval, success, error | widget tests per state (semantics label + painter parameters), screenshot set in `docs/ui_phase/screenshots/`, state table in `UI_DESIGN_REFERENCE.md` |
| A2 | Spatially continuous transitions among Companion, Workspace and Dashboard; the same orb instance persists | widget test asserts one `EnergyOrb` element identity across mode changes; recorded transition screenshots |
| A3 | Command-driven transitions through a restricted UI-state controller using local/mock events ("URI dashboard" etc.), manual override always available | unit tests on `UiPresentationController` and the local command parser; widget test typing the phrase |
| A4 | Usable Workspace: conversation (existing `UriConversationPane`/`UriCommandDock` reused), task creation + progress, documents/office workflow panel, harness/provider/model selection, permissions and approvals, context/files, results, history, progressive disclosure | widget tests on each region with `MockUriClient` and the mock work simulator |
| A5 | Dashboard: capabilities, current tasks, models, connected clients, permissions, readiness; honest labels (Configured / Qualified / Unavailable / Simulated) | widget test asserts every mock-only region carries the `Simulated` badge |
| A6 | Guided onboarding covering the brief's 8 topics with the same honesty labels | widget test walks all steps |
| A7 | Intelligence overview with routing/harness/model/context/tasks/approvals/errors, memory graph clearly marked prototype, no fabricated internal reasoning | widget test: no "reasoning trace" text, prototype badge present |
| A8 | Graceful offline / mock mode: `main_living.dart` runs with no server | manual run on Windows + widget test with `MockUriClient` only |
| A9 | Reduced-effects mode keeps every state distinguishable with no shader/blur | widget test renders orb with `reducedEffects: true` for every state; screenshots |
| A10 | Repeatable automated tests, `flutter analyze` clean for new code, all 205 baseline tests still pass | `UI_TEST_EVIDENCE.md` with command output |
| A11 | No unintended change outside the boundary in `UI_ISOLATION_EVIDENCE.md` | `git diff --stat <baseline>` listed in the evidence file |
| A12 | Interface contracts for future Brain connectivity documented and mocked, no Core/Supervisor change | `UI_INTERFACE_CONTRACTS.md` + Dart abstract classes under `lib/living/contracts/` |

## 2. Decisions and discoveries

### 2.1 Rendering technology (decision)

Procedural Flutter rendering, hybrid CPU/GPU:

* Particles, halo, rim, state overlays: `CustomPainter` driven by one `Ticker`; particle positions are pure functions of time and a fixed seed (no per-particle mutable state), so a frame costs one pass over ~100 particles and the painter is deterministic for tests.
* Core swirl: an optional runtime fragment shader (`shaders/orb_core.frag`, `FragmentProgram.fromAsset`) layered under the painter. Flutter 3.47 ships Impeller as the Windows default, which runs runtime shaders natively.
* Glass surfaces: `BackdropFilter` blur inside a `GlassPanel` widget, bounded to a few panels per screen.
* `EffectsSettings.reducedEffects` turns off the shader, blur and mask-filter glow at once; the painter alone still renders every state distinctly (A9).

Blender / Blender MCP: not used. Blender is not installed on this machine (`C:\Program Files\Blender Foundation` absent, `where blender` empty) and no Blender MCP server is configured in this session. A GLB pipeline would add a 3D viewer dependency to a Flutter desktop app whose whole UI is 2D, and an exported animation cannot react to live state (listening/thinking/approval) without a second real-time system on top. Procedural rendering gives the state reactivity the brief needs with no new dependency. Recorded as a decision, re-openable if the owner wants a sculpted 3D hero asset for marketing surfaces.

New dependencies: none. (The `flutter_shaders_ui` and `glow_orb` packages were considered; both wrap the same `FragmentProgram` API and would add surface for one effect. The shader here is ~40 lines.)

### 2.2 Design language (decision)

"Obsidian Cyan" palette and `UriGlass` theme extension (tokens in `UI_DESIGN_REFERENCE.md`). Added as a fifth `UriThemeChoice` so the four user-approved Hybrid themes (`docs/design_library/approved/hybrid_ui_2026-09-16.md`) stay untouched; the living experience defaults to Obsidian Cyan and keeps working under the other four (the orb reads `accent`).

### 2.3 State truthfulness (constraint carried from Phase 2 closure)

`docs/architecture/PHASE2CLOSE_UI_READINESS.md` section 3 fixes what an orb state may be derived from. This phase implements that mapping as `CompanionSignal` sources:

* `AppStateCompanionSource`: derives from real `AppState` fields (`isSendingAsk`, last turn `stage`, `lastConnectionErrorDetail`, backend reachability).
* `MockCompanionSource` / `MockWorkSimulator`: scripted, always flagged `simulated: true`, used by `main_living.dart` and tests.
* No source for "speaking" or "listening" exists in the baseline tree (no voice). They are rendered from mock events only and labelled Simulated in every surface that names them.

### 2.4 Integration posture (decision)

Additive only. The Hybrid app (`main.dart`, `app.dart`, screens, services) is byte-identical. The living experience has its own plugin-free root (`lib/living/living_app.dart`) and entry (`lib/main_living.dart`, mock client). The integration plan (`UI_INTEGRATION_PLAN.md`, written at handoff) proposes how `UriApp` would mount it behind a preference once the Brain connectivity contracts are accepted.

### 2.5 Reuse

* Conversation: `UriConversationPane`, `UriCommandDock` (Hybrid, tested).
* Theme: `UriColors`, `UriSpace`, `UriRadius`, `UriBreakpoints`, `buildUriTheme`.
* Models: `UriTurn`, `TaskItem`, `ProviderEntry`, `ActiveBrainInfo`, `CapabilityInfo`, `HomeSummary`.
* Mock backend: `MockUriClient`.
* Supervised execution vocabulary (`ExecutionStatus` states) for the Orb mapping, by name only; the living UI does not spawn the worker.

## 3. Architecture

```
lib/main_living.dart                      entry: MockUriClient + mock sources, no server
lib/living/living_app.dart                plugin-free root: MaterialApp(theme) > LivingShell
lib/living/presentation/
    presentation_controller.dart          UiPresentationMode {companion, workspace, dashboard}
                                          UiPresentationController (ChangeNotifier), UiCommand (sealed),
                                          parseLocalUiCommand(String)
    living_shell.dart                     one EnergyOrb instance (GlobalKey) animated between docks;
                                          mode content cross-fades under it
lib/living/companion/
    companion_state.dart                  CompanionState enum, CompanionSignal (state, label, progress, simulated)
    companion_sources.dart                CompanionStateSource (abstract), AppStateCompanionSource,
                                          MockCompanionSource, CompositeCompanionSource
    energy_orb.dart                       EnergyOrb widget + OrbParams per state + painter
    orb_shader.dart                       FragmentProgram loader with graceful fallback
    effects_settings.dart                 EffectsSettings (reducedEffects) InheritedNotifier
lib/living/contracts/                     proposed adapter contracts + mocks (see UI_INTERFACE_CONTRACTS.md)
    intelligence_snapshot.dart            IntelligenceSnapshotSource
    readiness_report.dart                 ReadinessSource (onboarding + dashboard readiness)
    work_items.dart                       WorkItemSource (tasks/documents/office workflows), MockWorkSimulator
lib/living/screens/
    companion_mode_view.dart
    workspace_mode_view.dart              rail + conversation + context panel (progressive disclosure)
    dashboard_mode_view.dart
    onboarding/living_onboarding_flow.dart
    intelligence/intelligence_overview_view.dart
lib/living/widgets/
    glass_panel.dart, status_badge.dart (Configured/Qualified/Unavailable/Simulated), ...
lib/theme/glass_theme.dart                UriGlass ThemeExtension
shaders/orb_core.frag
test/living/*_test.dart
```

Rules:

* Presentation never authorizes. Approve/cancel buttons call `AppState.approve/cancel` (mock client in this phase) exactly as the Hybrid Chat does; the simulator's "approval" is a mock event and is labelled.
* `UiPresentationController` accepts only mode changes and a focus hint. It cannot send text, approve, select an executor or change settings. The user can always switch mode manually; a command-driven switch never overrides an in-progress manual drag/resize.
* Every mock-backed region renders a `Simulated` badge. Real `AppState` data (mock client in this phase, HTTP client later) renders without it.

## 4. Slices (order chosen for dependency, not priority)

1. Design tokens: Obsidian Cyan palette, `UriGlass`, `GlassPanel`, `EffectsSettings`.
2. `CompanionState` + `EnergyOrb` (painter, shader, reduced mode) + tests + screenshots.
3. `UiPresentationController` + `LivingShell` transitions + command parser + tests.
4. Workspace and Dashboard views on mock sources + work simulator + tests.
5. Onboarding flow + tests.
6. Intelligence overview + memory-graph prototype + tests.
7. Performance/accessibility pass (frame timing from a real Windows run, semantics labels, reduced motion), polish, docs, handoff.

## 5. Edge and failure cases to cover

* Shader asset missing or failing to load: orb keeps rendering (painter only), no exception surfaces.
* Window too small (Companion mode 440x680) and too wide (1920+): no overflow (tests at 440x680, 900x700, 1280x900, 1920x1080).
* Mode switch during an in-flight ask: conversation state untouched (same `AppState` guarantee as Compact).
* Command text that is also a legitimate chat message ("show me the dashboard numbers"): parser requires the "URI <mode>" prefix form and exact mode words; anything else is sent as chat.
* Reduced effects toggled live: no rebuild errors, orb continues.
* Theme other than Obsidian Cyan: all living widgets read tokens from the theme, none hardcode cyan.

## 6. Out of scope (explicit)

Live Core connection, voice capture, real harness qualification, real memory backend, Windows window resizing for Companion mode (the Hybrid `platform_window_controller` already exists; the living shell exposes the hook but `main_living.dart` does not wire it, to avoid touching the shared OS window behaviour during this phase), merge/deploy.
