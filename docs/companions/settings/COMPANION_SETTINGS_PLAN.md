# Companion visual, voice and settings completion: plan

Written 2026-10-09, before implementation, against the owner brief "URI —
Companion Visual, Voice & Settings Completion". It is the plan of record for
this phase; the closure report records what was actually done.

## 0. Starting point (verified, not assumed)

| Fact | Evidence |
|---|---|
| Worktree `uri-companion-voice`, branch `phase/companion-voice`, HEAD `8fad876` (code `4c463e6`), clean except untracked `graphify-out/converted/` | `git status`, `git log` |
| Canonical development branch: `integration/git-sync-20261008` on `uri-repo` (`github.com/sche004-cyber/Uri`), tip `037229c` | `git ls-remote uri-repo`; `WS_HARDENING_PLAN.md` on `integration/ws-hardening-20261009` names it the same way |
| `037229c` is an ancestor of this branch; so are `569cf7c` (UI living companion, Codex r6 accepted with findings), `07a2f38` (solar orb R&D, unaccepted), `bd542f2`/`d7a052f` (living companions, unaccepted) | `git merge-base --is-ancestor` |
| The local branch named `integration/git-sync-20261008` is stale (`f8de153`); only `uri-repo/integration/git-sync-20261008` is authoritative | `git for-each-ref` |
| A parallel line `integration/working-system-20261008` → `integration/ws-hardening-20261009` also contains `569cf7c` and edits `living_app.dart`, `living_scope.dart`, `workspace_mode_view.dart` (around its settings list head and context panel), `dashboard_mode_view.dart`, `living_composer.dart`. It does not touch `living_shell.dart`, the companion files or the settings block below "Orb style" | `git diff 569cf7c integration/ws-hardening-20261009` |
| The living shell still draws the accepted `EnergyOrb`; `CompanionOrb`, `CompanionController` and `CompanionScope` exist but are not mounted | `living_shell.dart:204`, `companion_theme.dart` |
| Client preferences: `SharedPreferences` under the `uri.living.*` namespace (`LivingPrefs`), because every `uri_ui` build on this PC shares one `shared_preferences.json` with the live Hybrid app | `living_app.dart` |
| Voice: no voice service exists on this line or on canonical. The designated architecture (uncommitted in `_V1`, preserved on `preserve/v1-harness-voice-research-20261004`) is an opt-in Windows adapter reusing System.Speech recognition and synthesis | `CAMERA_VOICE_GEMMA_CANONICAL_ARCHITECTURE.md` |
| Installed voices: System.Speech `Microsoft David Desktop`, `Microsoft Zira Desktop` (en-US); Windows OneCore `Microsoft David`, `Microsoft Zira`, `Microsoft Mark` (en-US) | PowerShell enumeration, 2026-10-09 |
| A Runtime v1 Brain (`llama-server`, 15.25 GB VRAM, port 18470) is resident, started 07:11 by the working-system host for another session; another session runs Codex | process and GPU counters, 07:24 |

## 1. Acceptance criteria

| ID | Criterion | Evidence required |
|---|---|---|
| AC-1 | The selected companion is the one living orb in every mode of the shell (Companion, Workspace, Dashboard) and in onboarding; the same element survives mode changes and companion switches without a restart of its clock | widget tests on element identity; captures |
| AC-2 | The selected companion themes the app through the existing `UriColors`/`UriGlass` contract; no fixed cyan; text contrast is the palette's measured contrast | test that theme follows companion; captures of each companion with its settings |
| AC-3 | Original companion shaders unchanged byte for byte; tables unchanged except as recorded | `git diff` on `shaders/companion_*.frag`; table drift test |
| AC-4 | Companion Settings exist: companion picker, appearance (size, particle density, glow, atmosphere, animation intensity, voice-reactive waveform), performance (Adaptive / 30 / 60 / 90 / 144 where the display supports it, render quality, statistics overlay), voice and audio | widget tests; captures |
| AC-5 | Every control either works or is shown unavailable with the reason; no fabricated voice, no inert slider | per-control test or measurement |
| AC-6 | Preferences persist across restart and companion switches; visual preferences per companion, performance and audio global; one store, namespaced, corrupt values fall back | round-trip and corruption tests |
| AC-7 | Fixed frame-rate settings control actual rendering (frames produced per second, measured from `FrameTiming`), and the companion schedules no frames when hidden | profile-build measurement; test that the clock stops without listeners |
| AC-8 | Render quality changes the companion's measured rendering cost, and the companion stays recognisable at every offered quality | measurement; captures at each quality |
| AC-9 | Adaptive mode responds to measured frame-time pressure and recovers; it is tested deterministically and observed under real Brain activity, labelled as uncontrolled if it was not controlled | policy tests; perf run with foreign-GPU record |
| AC-10 | Memory growth is bounded or explained with evidence | long-run RSS with a control |
| AC-11 | Voice: a clean adapter interface that a voice service feeds; the presence consumes it; synthetic demos labelled simulated; live capture and live URI speech recorded as deferred | tests; ledger |
| AC-12 | Voice settings list the voices actually installed, mark unusable ones, preview through the OS engine, and expose only the parameters that measurably change the output | enumeration + measured preview audio |
| AC-13 | Boundaries: no Core/Runtime, frozen, launcher or production change; no formatting churn; LF line endings; perf output only under the evidence directory | integrity commands |
| AC-14 | Independent Codex review gives an explicit verdict; findings repaired and re-reviewed | review records |
| AC-15 | Integration only after AC-14 and combined regression; receipt written | receipt |

## 2. Design decisions

1. **One companion choice, theme derived.** `CompanionPreferences.selected` is a
   living identity or `classic` (the accepted Energy Orb, kept so no accepted
   functionality is lost). For a living companion the theme is derived from
   `CompanionTheme.choiceFor`; the stored free theme choice applies only to the
   classic orb. No second theme store.
2. **One frame clock.** A shared `CompanionFrameClock` drives the companion
   and the voice waveform. It mutes its ticker between paints, so a capped rate
   really means fewer frames rasterised (Impeller re-renders the whole scene
   for every produced frame, so skipping `setState` alone would save nothing).
   It stops when nothing listens and Flutter stops frames when the window is
   hidden.
3. **Adaptive is measured, not assumed.** It starts at the display rate and
   steps down a tier only when frame times measured by `FrameTiming` overrun
   the current interval, and steps back up after sustained headroom.
4. **Render quality is real resolution.** Below full quality the shader is
   rendered into a smaller offscreen image and scaled up, which reduces the
   fragment work in proportion to the pixel count.
5. **Appearance controls are identity-aware.** They scale each identity's own
   parameters (`particles`, `flare`, `exposure`, time rate) and are labelled in
   that identity's vocabulary (embers, petals, stars and mist; corona, energy
   ribbons, halo). Glow is limited to ±12 % so detail is not washed out.
6. **Voice is an interface plus the OS engines that exist.** A `VoiceCatalog`
   enumerates System.Speech and OneCore voices; previews run in a separate
   PowerShell process, never inside the renderer. Parameters are offered only
   where measurement shows they change the audio.
7. **Edits to files the parallel working-system line also edits stay out of the
   hunks it touched**, so the later merge of the two lines is mechanical.

## 3. Out of scope

Live microphone capture, URI reply speech, production deployment, launcher
changes, replacement of the live server, new speech models or downloads.
