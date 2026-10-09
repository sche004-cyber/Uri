# Companion visual, voice and settings completion: closure report

Phase brief: "URI — Companion Visual, Voice & Settings Completion", 2026-10-09.
Plan of record and acceptance criteria: `COMPANION_SETTINGS_PLAN.md` (written
before implementation). Branch `phase/companion-voice`, worktree
`C:\Users\cheta\Development\uri-companion-voice`.

## 0. Status ledger

| Item | Researched | Implemented | Tested | Measured on the real app | Independently accepted | Integrated |
|---|---|---|---|---|---|---|
| Selected companion in every mode (Companion, Workspace, Dashboard, onboarding, picker) | yes | yes | yes | yes, captures | REVIEW_STATE | INTEGRATION_STATE |
| Companion-driven theme (existing `UriColors`/`UriGlass`) | yes | yes | yes | yes, captures | REVIEW_STATE | INTEGRATION_STATE |
| Companion Settings page | yes | yes | yes | yes, captures | REVIEW_STATE | INTEGRATION_STATE |
| Per-companion appearance (size, particles, glow, atmosphere, animation) | yes | yes | yes | captures | REVIEW_STATE | INTEGRATION_STATE |
| Frame rate (Adaptive, 30, 60, 90, 144) | yes | yes | yes | yes, profile build | REVIEW_STATE | INTEGRATION_STATE |
| Render quality (Full, Balanced, Performance) | yes | yes | yes | yes, profile build | REVIEW_STATE | INTEGRATION_STATE |
| Statistics overlay | yes | yes | yes | capture | REVIEW_STATE | INTEGRATION_STATE |
| No frames while minimised | yes | yes | yes | yes, profile build | REVIEW_STATE | INTEGRATION_STATE |
| Voice list, previews, rate / pitch / volume | yes | yes | yes | parameters measured on rendered audio | REVIEW_STATE | INTEGRATION_STATE |
| Voice service interface (`VoiceServiceAdapter`) | yes | yes | yes (fake adapters) | scripted recording only, SIMULATED | REVIEW_STATE | INTEGRATION_STATE |
| Live microphone capture, URI reply speech | yes | **no (deferred)** | no | no | no | no |
| Speaking styles, microphone gain | yes | shown unavailable with reason | yes | n/a | REVIEW_STATE | INTEGRATION_STATE |
| Production deployment, live-server cutover, launcher | n/a | **not authorised, not done** | | | | |

## 1. Acceptance criteria and results

| ID | Criterion (plan §1) | Result | Evidence |
|---|---|---|---|
| AC-1 | One companion element in every mode; survives mode and companion switches | met | `companion_settings_test.dart` "switching companion re-themes everything and keeps the one shell element"; `capture2/companion_*`, `settings_*`, `dashboard_*` |
| AC-2 | Companion decides the theme through the existing contract | met | test "the default companion is Solar and themes the app"; captures of all five choices |
| AC-3 | Shaders byte-identical | met | FNV-1a test of all seven `.frag` files; `git diff 4c463e6..HEAD -- uri_ui/shaders` empty |
| AC-4 | Settings exist with every listed control | met | `capture2/settings_*_picker|performance|voice.png` |
| AC-5 | Every control works or says it is unavailable | met | per-control tests; voice parameters measured (§5) |
| AC-6 | Persistence, per-companion looks, one namespaced store | met | round-trip, corruption and namespace tests |
| AC-7 | Fixed rates control rendering; nothing when hidden | met | §4.1, §4.3 |
| AC-8 | Quality changes cost; companion recognisable | met | §4.2, `capture2/quality_*` |
| AC-9 | Adaptive responds to pressure and recovers | BRAIN_AC9 | §4.4 |
| AC-10 | Memory bounded or explained | met (explained: engine baseline, control run; Dart heap bounded; plateau of the engine itself not proven) | §4.5 |
| AC-11 | Voice interface; simulated labelled; live deferred | met | §5 |
| AC-12 | Only real voices and measured parameters | met | §5 |
| AC-13 | Boundaries, formatting, line endings, output paths | met | §7 |
| AC-14 | Independent Codex verdict | REVIEW_AC14 | §6 |
| AC-15 | Integration after acceptance with receipt | INTEGRATION_AC15 | `INTEGRATION_RECEIPT.md` |

## 2. What was built

* **One companion everywhere.** `LivingCompanion` draws the chosen companion in
  Companion mode, the Workspace dock, the Dashboard, onboarding and the
  Settings picker, always at the same proportion (body about half its box,
  scale capped at 1.4 so the corona and petals stay in view). A living
  identity uses its own unchanged shader; the classic choice keeps the
  accepted Energy Orb with its seven styles and ten palettes. Switching
  companion cross-fades for 450 ms; the shell element is never remounted.
* **The companion is the theme.** `CompanionPreferences.themeFor` maps a living
  companion to its palette (Solar Ember, Sakura Bloom, Lunar Silver; Moonlit
  uses Lunar Silver so a rose workspace does not fight a silver moon). The free
  theme choice applies only to the classic orb. Nothing new was added to the
  theme system; every living widget already reads `UriColors`/`UriGlass`.
* **Companion Settings** (Workspace → Settings): picker with still previews;
  appearance in each identity's words (Embers / Petals and pollen / Stars and
  mist / Petals and mist; Corona and prominences / Energy ribbons / Halo and
  light shafts / Moon halo); performance; voice and audio.
* **Preferences**: `uri.living.companion.*` in the shared preferences file the
  living app already uses; per-companion looks; global performance and audio;
  unreadable values fall back to defaults; harnesses run on in-memory
  preferences and never touch the shared file.
* **Frame clock** (`frame_clock.dart`): one clock for the companion and the
  voice waveform. It mutes its ticker between paints (Impeller re-renders the
  whole scene for every produced frame, so skipping `setState` alone saves
  nothing), asks for 1 ms Windows timer resolution only while pacing (Dart
  timers otherwise fire on the 15.6 ms tick: measured 10 ms → 15.6 ms), stops
  with no listener, and is suspended while the window is minimised.
* **Adaptive governor**: starts at the display rate; a 2 s window with more
  than 5 % of frames over the current interval, or a 90th percentile above
  85 % of it, steps down one tier (144, 90, 60, 45, 30); three calm windows step
  back up.
* **Render quality**: the shader runs into an offscreen image at 0.75 or 0.5
  of the covered pixels and is drawn back with bilinear filtering.
* **Voice**: `VoiceCatalog` + `WindowsVoiceCatalog` (bundled PowerShell bridge,
  inputs only through environment variables, `-EncodedCommand`, previews out of
  process and stoppable); `VoiceServiceAdapter` + `VoiceServiceBinding` (an
  adapter error ends the turn with a notice; an adapter closing resets it);
  `VoiceStage` puts the same shared waveform and transcript beside the
  companion in every mode.

## 3. Captures (real Windows app, Impeller)

`evidence/capture2/` (final; `capture1/` is the first run, kept as history:
its voice stage overlapped the composer and the Workspace header, fixed in
`3b34aa1`). 42 frames, 0 failures, log in `capture_log.txt`:

* `companion_<c>.png`, `settings_<c>_picker.png`, `settings_<c>_performance.png`,
  `settings_<c>_voice.png`, `dashboard_<c>.png` for c in solar, sakura, lunar,
  moonlit, classic: every companion with its matching settings theme.
* `voice_companion_mode.png`, `voice_workspace_mode.png`: a scripted
  System.Speech recording fed through `VoiceServiceBinding`, labelled
  SIMULATED.
* `stats_overlay_solar.png`, `reduced_effects_solar.png`.
* `quality_<id>_<full|balanced|performance>.png`: fixed frames, same seed.

The capture harness is a debug build, so its statistics-overlay numbers are
debug-mode numbers and are not used as performance evidence.

## 4. Performance (profile build)

Conditions: AMD Radeon RX 7900 GRE (16 GB), Ryzen 9 5900X, Windows 11 26200,
2560×1440 panel, engine-reported refresh 144 Hz, app window 1264×681 logical at
device pixel ratio 1.0, Flutter 3.47.2 profile build of
`tool/demo/companion_perf.dart` (the product's shell, clock, governor and
shaders). Per-process counters from WDDM (`rnd/voice/sample_process.ps1`).
Each row records any other process holding more than 1 GB of VRAM.

### 4.1 Frame-rate settings control rendering (`perf/matrix1`, Lunar, Companion mode, 20 s)

| Setting | Engine frames/s | Companion frames/s | Raster p50/p90/p99 ms | Own GPU 3D % | CPU % |
|---|---|---|---|---|---|
| 30 FPS | 30.1 | 30.0 | 2.17 / 2.82 / 3.51 | 3.4 | 0.6 |
| 60 FPS | 60.2 | 60.1 | 2.00 / 2.55 / 3.37 | 4.5 | 1.0 |
| 90 FPS | 90.5 | 90.2 | 1.98 / 2.40 / 3.43 | 5.8 | 1.4 |
| 144 FPS | 148.9 | 149.5 | 1.98 / 2.92 / 4.16 | 9.4 | 2.2 |
| Adaptive | 148.4 | 148.9 | 1.72 / 2.17 / 3.15 | 9.5 | 2.0 |

The engine produces the frames the setting asks for, so the cost falls with
the setting. A resident Brain (12.6–14.3 GB VRAM, idle) was present in some of
these runs. At "144" the engine produced slightly more than 144 frames a second
on a display it reports as 144 Hz; noted, not explained.

### 4.2 Render quality changes cost (`perf/matrix2`, one large companion, uncapped)

GPU time per frame = own GPU 3D share ÷ frames per second:

| Identity | Full | Balanced (0.75) | Performance (0.5) |
|---|---|---|---|
| Lunar | 1.23 ms | 0.99 ms (−20 %) | 0.64 ms (−48 %) |
| Solar | 0.56 ms | 0.48 ms (−14 %) | 0.37 ms (−34 %) |
| Sakura | 0.39 ms | 0.34 ms (−13 %) | 0.26 ms (−33 %) |

Savings are smaller than the pixel ratio because the offscreen pass, the
upscale and the rest of the frame are fixed costs. `capture2/quality_*.png`
shows each companion stays recognisable; Performance softens Lunar's crater
detail and Sakura's petal edges. Run `matrix1/large-*` is superseded: the
harness had not told the governor the display rate (fixed in the next build).

### 4.3 Minimised window (`perf/matrix3/hidden-lunar-fps144`)

Measured first (`matrix2/hidden-*`, kept as history): minimising on Windows
reports only `AppLifecycleState.inactive`, keeps the view size, and the engine
went on producing about 64 frames a second (own GPU 7.7 %). Fixed in
`da245aa` (window minimise event) and `ebe3828` (every ticker muted, the
classic orb included). Re-measured: **0 frames and 0 % GPU while minimised**,
150 frames/s again within a second of restore.

### 4.4 Contention

**Synthetic (controlled, `perf/contention`)**: from second 30 to 70 a second
process of this harness (24 companions, uncapped) raised whole-adapter 3D
utilisation from 17 % to 82–87 %. The measured app was unaffected: 144 frames/s
before, during and after, raster p99 3.0 ms, one frame over 16.7 ms in 100 s,
for both Adaptive and fixed 144. Adaptive did not step down, so it does not
degrade quality for graphics contention the GPU absorbs. This load is
graphics work; it does not reproduce a language model saturating compute.

BRAIN_SECTION

### 4.5 Memory

Four 30-minute runs (`perf/soak`), each with RSS and the Dart heap (read from
the app's own VM service) every 5 s. Three ran together at a fixed 60 FPS
with the companion stepping through six states every 4 s (a resident Brain was
in VRAM, idle, for most of it); the control ran alone later.

| Run | Frames | RSS after warm-up (150 s) → 30 min | Growth | Per frame | Dart heap |
|---|---|---|---|---|---|
| Lunar, Full (direct shader) | 114 k at 63/s | 131 → 150 MB | +18.8 MB | 0.18 KB | 11.7–19.0 MB sawtooth, no trend |
| Lunar, Balanced (offscreen path) | 114 k at 63/s | 131 → 146 MB | +15.0 MB | 0.15 KB | 11.6–16.1 MB sawtooth, no trend |
| Classic Energy Orb (own ticker, uncapped) | 248 k at 138/s | 139 → 172 MB | +33.0 MB | 0.15 KB | 10.8–15.7 MB, levels off after 20 min |
| **Control: no companion, no living code** (one rotating square, uncapped) | 266 k at 147/s | 121 → 144 MB | +22.9 MB | 0.10 KB | ends 17.1 MB |

The harness itself keeps 12 bytes per frame of timing data (about 1.4 MB for
the Lunar runs, 3.2 MB for the control).

**Explanation.** The Dart heap is bounded in every run: it rises and falls
with garbage collection and does not trend. The growth is native, and a
trivial Flutter window with no companion code grows at the same order of
magnitude over the same time. So the growth is not caused by the companions,
the offscreen quality path or the frame clock; it belongs to the engine or
driver baseline of this Flutter 3.47.2 Windows build on this machine. Within
30 minutes none of the four runs, the control included, shows a clear plateau.
Frame-rate caps reduce it in proportion to frames drawn. The previous phase's
open question ("+19 MB in 10 minutes, plateau not established") is therefore
answered as "not the companion; engine baseline", and a plateau remains
unproven for the engine itself.

## 5. Voice

* Installed voices found on the reference PC (2026-10-09): System.Speech
  `Microsoft David Desktop`, `Microsoft Zira Desktop`; OneCore `Microsoft
  David`, `Microsoft Zira`, `Microsoft Mark`; all en-US. All five are listed,
  grouped by engine, each with a preview. Nothing was downloaded.
* Parameters offered only where measured (`rnd/companions/settings/
  measure_voice_params.py`, `evidence/voice/voice_params.json`): rate changed
  duration 7.14 → 21.33 / 2.55 s (System.Speech) and 6.03 → 12.06 / 3.06 s
  (OneCore); pitch moved median f0 175 → 131 / 232 Hz and 148 → 87 / 216 Hz;
  volume 30 % lowered level by 17.5 dB. Speaking styles: none of the installed
  voices offers any, shown unavailable. Microphone gain: URI captures no
  microphone audio in this build, shown unavailable (Windows sets the level).
* Additional engines investigated, not installed: local neural voices would
  need new model downloads and a new runtime; the brief rules out downloading
  large voice models to populate the menu, so the catalog interface is ready
  for them and nothing more was done.
* **Implemented**: voice catalog and previews; the adapter interface the voice
  service will feed; the shared waveform and transcript beside the companion
  in every mode; equal level mapping for both speakers (unchanged from the
  voice presence phase); interruption and stale-event rejection (unchanged
  reducer).
* **Deferred, not implemented**: live microphone capture and recognition, URI
  reply speech and playback, word timing from a live engine. URI's designated
  voice adapter (System.Speech, opt-in Windows adapter) exists only uncommitted
  in `_V1` and on `preserve/v1-harness-voice-research-20261004`; it is not on
  the canonical line and was not imported.

## 6. Independent review

REVIEW_SECTION

## 7. Boundaries and repository hygiene

* `037229c..HEAD` changes only `docs/`, `rnd/` and `uri_ui/`; no Core, Runtime,
  launcher, script or frozen file. Inside `uri_ui` outside `lib/living`,
  `test/living`, `tool`, `shaders`, `test/fixtures`: `pubspec.yaml` (one asset
  line), `assets/voice/voice_engine.ps1`, `lib/main_living.dart`,
  `lib/services/windows_voice_catalog.dart`, `lib/services/window_visibility.dart`
  (this phase) and `lib/theme/*` (living companions phase).
* `dart format` was run only on files this phase created or whose committed
  version was already formatted (`companion_orb.dart` is hand-aligned and was
  not formatted). Changed files are LF.
* Every perf runner resolves its output directory to an absolute path; the
  app writes only there.
* Four accepted assertions in `living_shell_test.dart` were adapted because the
  default orb changed from the Energy Orb to Solar; the classic-orb checks now
  select the classic orb first. Full suite: TESTS_LINE.

## 8. Known limitations

1. No live voice (deferred, §5). The voice frames are a scripted recording,
   labelled SIMULATED.
2. One machine, one GPU, device pixel ratio 1.0, Windows only.
3. The working-system entry point on the parallel line
   (`integration/ws-hardening-20261009`, `working_system_app.dart`) must also
   call `bindWindowVisibility` and set `voiceCatalog` when it adopts this code;
   until then a minimised working-system window keeps animating.
4. The classic orb ignores the appearance sliders and the frame-rate setting
   (shown unavailable with the reason).
5. Covered windows (not minimised) still render; Windows reports no occlusion
   to Flutter.
6. Native memory grows slowly in every Flutter window on this machine, the
   no-companion control included (§4.5); whether the engine plateaus beyond
   30 minutes is not established.

## 9. Evidence index

| Path | Content |
|---|---|
| `evidence/capture1/`, `evidence/capture2/` | real-app captures (capture2 final) |
| `evidence/perf/matrix1` | frame-rate settings; `large-*` superseded (display rate not set) |
| `evidence/perf/matrix2` | render quality; `hidden-*` = defect before the fix |
| `evidence/perf/matrix3` | minimised window after the fix |
| `evidence/perf/contention` | synthetic contention |
| `evidence/perf/brain` | controlled Brain contention |
| `evidence/perf/soak` | 30-minute memory runs |
| `evidence/voice/voice_params.json` | voice parameter measurements |
