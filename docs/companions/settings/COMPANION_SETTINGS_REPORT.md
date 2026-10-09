# Companion visual, voice and settings completion: closure report

Phase brief: "URI — Companion Visual, Voice & Settings Completion", 2026-10-09.
Plan of record and acceptance criteria: `COMPANION_SETTINGS_PLAN.md` (written
before implementation). Branch `phase/companion-voice`, worktree
`C:\Users\cheta\Development\uri-companion-voice`.

## 0. Status ledger

| Item | Researched | Implemented | Tested | Measured on the real app | Independently accepted | Integrated |
|---|---|---|---|---|---|---|
| Selected companion in every mode (Companion, Workspace, Dashboard, onboarding, picker) | yes | yes | yes | yes, captures | yes (Codex r4; integration r2) | yes (canonical) |
| Companion-driven theme (existing `UriColors`/`UriGlass`) | yes | yes | yes | yes, captures | yes (Codex r4; integration r2) | yes (canonical) |
| Companion Settings page | yes | yes | yes | yes, captures | yes (Codex r4; integration r2) | yes (canonical) |
| Per-companion appearance (size, particles, glow, atmosphere, animation) | yes | yes | yes | captures | yes (Codex r4; integration r2) | yes (canonical) |
| Frame rate (Adaptive, 30, 60, 90, 144) | yes | yes | yes | yes, profile build | yes (Codex r4; integration r2) | yes (canonical) |
| Render quality (Full, Balanced, Performance) | yes | yes | yes | yes, profile build | yes (Codex r4; integration r2) | yes (canonical) |
| Statistics overlay | yes | yes | yes | capture | yes (Codex r4; integration r2) | yes (canonical) |
| No frames while minimised | yes | yes | yes | yes, profile build | yes (Codex r4; integration r2) | yes (canonical) |
| Voice list, previews, rate / pitch / volume | yes | yes | yes | parameters measured on rendered audio | yes (Codex r4; integration r2) | yes (canonical) |
| Voice service interface (`VoiceServiceAdapter`) | yes | yes | yes (fake adapters) | scripted recording only, SIMULATED | yes (Codex r4; integration r2) | yes (canonical) |
| Live microphone capture, URI reply speech | yes | **no (deferred)** | no | no | no | no |
| Speaking styles, microphone gain | yes | shown unavailable with reason | yes | n/a | yes (Codex r4; integration r2) | yes (canonical) |
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
| AC-9 | Adaptive responds to pressure and recovers | met with a gap: responds and recovers (tests, contention runs); back-off verified by tests, not yet against a live Brain | §4.4 |
| AC-10 | Memory bounded or explained | met (growth is not companion-specific: a no-companion control grows similarly; plateau not established) | §4.5 |
| AC-11 | Voice interface; simulated labelled; live deferred | met | §5 |
| AC-12 | Only real voices and measured parameters | met | §5 |
| AC-13 | Boundaries, formatting, line endings, output paths | met | §7 |
| AC-14 | Independent Codex verdict | met: Codex round 4 ACCEPT; integration rounds ACCEPT WITH FINDINGS (repaired / recorded) | §6 |
| AC-15 | Integration after acceptance with receipt | met: fast-forward of `integration/git-sync-20261008`, receipt | `INTEGRATION_RECEIPT.md` |

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

GPU time per frame = mean own GPU 3D share ÷ mean engine frames per second
(seconds 4 onward). Samples whose process counters were absent (dedicated
VRAM reads 0, which happens on the last sample as the process exits) are
excluded: 8 of 9 samples per run. The all-sample means, which include that
zero, are about 11 % lower and are given in brackets.

| Identity | Full | Balanced (0.75) | Performance (0.5) |
|---|---|---|---|
| Lunar | 1.23 ms (1.09) | 0.99 ms (0.88), −20 % | 0.64 ms (0.57), −48 % |
| Solar | 0.49 ms (0.43) | 0.42 ms (0.38), −14 % | 0.32 ms (0.29), −34 % |
| Sakura | 0.39 ms (0.35) | 0.34 ms (0.30), −14 % | 0.26 ms (0.23), −33 % |

Savings are smaller than the pixel ratio because the offscreen pass, the
upscale and the rest of the frame are fixed costs. `capture2/quality_*.png`
shows each companion stays recognisable; Performance softens Lunar's crater
detail and Sakura's petal edges. Run `matrix1/large-*` is superseded: the
harness had not told the governor the display rate (fixed in the next build).

*Correction (round 2 review):* the first draft of this table filtered samples
by "GPU share above zero" without saying so, which also dropped one valid
Solar sample (Solar Full read 0.56 ms); the rule above replaces it.

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

**Real Brain (controlled, `perf/brain`)**, run under the machine-wide URI
GPU lease (`gpu_lease run --purpose benchmark`, waited until another
session's regression chain released it) with this phase's own Runtime v1
instance: the pinned llama.cpp b11425 binary, the frozen model and argv, on
private port 18499 (`rnd/companions/settings/brain_contention.py`). No other
session's Brain was touched; every process was stopped at the end. Decode =
256 tokens of the Runtime v1 calibration prompt, temperature 0, MTP on.

*Order 1, Brain first, then the companion (14:47:56–14:55:12).* (A lease fit
check run shortly before, while another session held the lease, read a margin
of about 60 MB for Runtime v1; that reading was not saved as evidence.)

| Condition | Brain decode tok/s | Companion frames/s during generation | Raster p99 | Frames > 16.7 ms |
|---|---|---|---|---|
| Brain alone, before | 159.3 / 161.9 / 161.8 | — | — | — |
| Companion fixed 144 | 45.2–46.7 | 144.5 | 12.4 ms | 6 of 14 480 |
| Companion Adaptive (build before the back-off fix) | 47.5–48.2 | 103.7 (cap alternated 144 / 90 every ~8 s) | 10.3 ms | 2 of 12 369 |
| Companion fixed 30 | 50.0–50.2 | 29.9 | 2.7 ms | 1 of 3 037 |
| Brain alone, after the companion exited | 50.9 / 51.2 | — | — | — |

The decode rate fell from 160 to about 50 tok/s **as soon as the companion
window opened, and stayed there after it closed**. That persistence rules out
live contention as the whole cause. The most likely mechanism, **inferred and
not measured here**, is the VRAM demotion recorded for the frozen Runtime v1
by the Adaptive Runtime R1 research (branch `research/adaptive-runtime`): the
server asks for 15.26 GiB of a 16 GiB card, and a process that takes a few
hundred MB afterwards (this app holds about 300 MB dedicated) leaves part of
the model in system memory for the life of the server. These runs did not
record per-allocation residency, so the mechanism is not directly shown. Frame
rate then only moves the result a little: 30 FPS left 50 tok/s, 144 left 46.

*Order 2, companion first, then the Brain (14:59:08–15:05:17)*, i.e. URI's window
already open when the Brain starts, which the lease's fit check accounts for:

| Condition | Brain decode tok/s | Companion frames/s | Raster p99 / frames > 16.7 ms (360 s) |
|---|---|---|---|
| Companion Adaptive, Brain generating for 120 s | 132.7–146.9 (62 requests, median about 140) | 144.7 during, 145.2 before, 146.6 after | 3.6 ms / 24 of 51 814 (0.05 %) |
| Brain alone, after the companion exited | 160.9 / 160.5 | — | — |

With the Brain healthy, the companion was unaffected while it generated (the
generation runs on the GPU's compute queue: whole-adapter 3D utilisation
stayed about 11 %) and the Brain ran about 12 % slower with the companion
animating at 144 FPS. Adaptive stepped down once, to 90, for 8 s while the
model loaded, and returned.

**Findings.**
1. (AMBER, owner) *Start order decides the Brain's speed, not the companion's
   settings.* Opening this URI window after the Brain had loaded left the
   Brain at about a third of its speed until it restarted (one run; mechanism
   inferred above). This belongs to the
   frozen Runtime v1 memory budget and the working-system host's start policy
   (the lease's fit check and calibration already exist for it), not to the
   companion; it is recorded here because the companion is such a window.
2. (fixed) *Adaptive oscillated* between 144 and 90 under sustained load in
   the first run, because three calm windows at 90 were enough to try 144
   again. Since this report's back-off fix, a step up that is followed by
   stress within ten windows doubles the calm needed for the next one (3, 6,
   12, 24, 30 windows; forgotten after 30 calm windows). Verified by
   deterministic tests (`adaptive backs off instead of oscillating under
   sustained load`: at most one probe a minute, the cap at 90 for more than 100
   of 120 windows). The UI-first run did not sustain stress, so the back-off
   has **not** yet been observed against a live Brain.
3. The previous phase's measurement (100–108 frames/s, 17 % late frames while
   a Brain generated) was not reproduced in either order here; that run was
   uncontrolled (another session's Brain, unknown start order and load).


### 4.5 Memory

Four 30-minute runs (`perf/soak`), each with RSS and the Dart heap (read from
the app's own VM service) every 5 s. Three ran together at a fixed 60 FPS
with the companion stepping through six states every 4 s (a resident Brain was
in VRAM, idle, for most of it); the control ran alone later.

| Run | Frames | RSS at 150 s → 30 min | RSS growth | Dart heap used: min–max; first-third → last-third mean |
|---|---|---|---|---|
| Lunar, Full (direct shader) | 114 k at 63/s | 131 → 150 MB | +18.8 MB | 10.3–20.3 MB; 13.5 → 16.3 MB |
| Lunar, Balanced (offscreen path) | 114 k at 63/s | 131 → 146 MB | +15.0 MB | 10.6–16.9 MB; 12.8 → 14.7 MB |
| Classic Energy Orb (own ticker, uncapped) | 248 k at 138/s | 139 → 172 MB | +33.0 MB | 10.7–16.4 MB; 12.2 → 15.1 MB |
| **Control: no companion, no living code** (one rotating square, uncapped) | 266 k at 147/s | 121 → 144 MB | +22.9 MB | 10.0–17.5 MB; 11.2 → 13.9 MB |

**What this shows.** Every run grows, the control included: a Flutter window
with no companion code at all grows by a similar amount in the same time. The
growth is therefore not specific to the companions, the offscreen quality path
or the frame clock. These runs cannot apportion it exactly: the companion runs
may still add something within the spread between runs. Most of it is native
(RSS), not Dart heap. The Dart heap rises by 2 to 3 MB in every run, the
control included, which is consistent with the harness's own timing arrays
(12 bytes per frame in doubling buffers: about 1.4 MB of data for the Lunar
runs and 3.2 MB for the control); that attribution is not separately proven.
No run shows a plateau within 30 minutes, so whether this Flutter 3.47.2
Windows build levels off is not established.

*Correction (round 2 review):* the first draft said the Dart heap showed "no
trend" and that frame caps reduce the growth "in proportion"; both were
stronger than the data and are withdrawn.

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

Codex CLI (`codex exec`, model gpt-6-sol, reasoning medium, read-only
sandbox) on a fresh `core.autocrlf=false` clone (`C:\Users\cheta\Development\csr`).
Every result is a claim; each finding was checked against the code before it
was repaired.

| Round | Head | Verdict | Findings | Repairs |
|---|---|---|---|---|
| 1 | `a978cf5` | REJECT | B1 classic orb outside the frame clock (rate setting and minimise did not apply); B2 voice stage overlapped the Companion-mode controls at 800×600; N3 window listener never removed; N4 listing timeout left PowerShell running | `ebe3828`: rate shown unavailable for classic, every ticker muted while minimised; pill above the companion when there is no room below; removable listener; kill on timeout |
| 2 | `f73575d` | REJECT | B1 pill still overlapped the orb at 640×480; B2 §4.2 GPU table not reproducible from the stated formula; N3 listener remover never called; N4 §4.5 heap ranges understated, two overclaims; N5 contention script could leave the measured app running; N6 31 evidence CSVs CRLF | `cecb911`: no stage where no free place exists (below about 560 px), narrow Dashboard likewise; §4.2 recomputed with a stated rule, correction recorded; remover runs on clock disposal; §4.5 corrected, overclaims withdrawn; cleanup kills the app; CSVs LF |
| 3 | `a83efe7` | ACCEPT WITH FINDINGS | N1 VRAM demotion and the 60 MB margin stated as established; N2 contention cleanup matched the checkout name; N3 two Brain logs CRLF | `417cd26`: mechanism stated as inferred, unsaved reading labelled; cleanup stops this checkout's exact executable; logs LF |
| 4 | `417cd26` | **ACCEPT** | none | — |
| Integration 1 | `ed8a655` | ACCEPT WITH FINDINGS | window binding could outlive a disposed clock | `c0fc8b9` (merged as `6f06c31`) |
| Integration 2 | `6f06c31` | ACCEPT WITH FINDINGS | the binding test does not simulate disposal during initialisation | recorded as a limitation |


## 7. Boundaries and repository hygiene

* `037229c..HEAD` changes only `docs/`, `rnd/` and `uri_ui/`; no Core, Runtime,
  launcher, script or frozen file. Inside `uri_ui` outside `lib/living`,
  `test/living`, `tool`, `shaders`, `test/fixtures`: `pubspec.yaml` (one asset
  line), `assets/voice/voice_engine.ps1`, `lib/main_living.dart`,
  `lib/services/windows_voice_catalog.dart`, `lib/services/window_visibility.dart`
  (this phase) and `lib/theme/*` (living companions phase).
* `dart format` was run only on files this phase created or whose committed
  version was already formatted (`companion_orb.dart` is hand-aligned and was
  not formatted). Changed source and text files are LF; the evidence CSVs,
  which the Windows counter sampler writes with CRLF, were normalised to LF
  before commit (content otherwise unchanged).
* Every perf runner resolves its output directory to an absolute path; the
  app writes only there.
* Four accepted assertions in `living_shell_test.dart` were adapted because the
  default orb changed from the Energy Orb to Solar; the classic-orb checks now
  select the classic orb first. Full suite on the source branch: `flutter test` 391 passed, 2 skipped (baseline before this phase: 338 passed, 2 skipped); on the integrated tree 427 passed, 3 skipped (`INTEGRATION_RECEIPT.md`); `flutter analyze` on every changed path: no issues.

## 8. Known limitations

1. No live voice (deferred, §5). The voice frames are a scripted recording,
   labelled SIMULATED.
2. One machine, one GPU, device pixel ratio 1.0, Windows only.
3. Resolved at integration (`ed8a655`): the working-system entry installs the
   voice catalog and the minimise binding. The binding's test does not
   simulate disposal during plugin initialisation (Codex integration round 2).
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
