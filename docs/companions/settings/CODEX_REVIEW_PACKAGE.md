# Independent review package: companion visual, voice and settings completion

For the independent reviewer (Codex). Verify from primary evidence; treat the
candidate's report as claims. The reviewer is read-only: no repair, commit,
push or merge.

## Identity

| | |
|---|---|
| Repository | `uri-repo` = `github.com/sche004-cyber/Uri` (local object store shared by the worktrees) |
| Canonical development branch | `integration/git-sync-20261008`, tip `037229c` (verified with `git ls-remote uri-repo` on 2026-10-09) |
| Candidate branch | `phase/companion-voice` (local, not pushed) |
| Review clone | a fresh `core.autocrlf=false` clone of the candidate branch (path given in the prompt) |
| This phase's commits | `e697dde`, `3b34aa1`, `da245aa`, `45e7b6e`, plus the evidence/report commits after them (`git log --oneline 8fad876..HEAD`) |
| Earlier, never independently accepted, commits that integration would also bring in | `07a2f38` (solar orb R&D), `bd542f2`, `d7a052f` (living companions), `4c463e6`, `8fad876` (voice presence) |
| Already accepted ancestor | `569cf7c` (UI living companion, Codex round 6 accepted with findings) |

**Integration scope is `037229c..HEAD`**, so acceptance must cover every commit
after `569cf7c`, not only this phase's.

## What this phase claims

1. The selected companion (Solar, Sakura, Lunar, Moonlit Blossom, or the
   accepted classic Energy Orb) is the one orb in Companion mode, Workspace,
   Dashboard and onboarding; the same element survives mode changes and
   companion switches. `lib/living/companion/living_companion.dart`,
   `presentation/living_shell.dart`.
2. A living companion decides the app theme through the existing
   `UriColors`/`UriGlass` contract (`CompanionPreferences.themeFor`); the free
   theme choice applies only to the classic orb. No new theme system.
3. Companion shaders are byte-identical to the accepted artwork (test with
   FNV-1a hashes in `test/living/companion_settings_test.dart`).
4. Companion Settings (`screens/settings/companion_settings_section.dart`):
   picker; per-companion size, particles, glow (±12 %), atmosphere, animation
   intensity, in each identity's vocabulary; frame rate Adaptive/30/60/90/144
   with rates above the display disabled; render quality Full/Balanced/
   Performance; measured statistics overlay; voices; voice waveform switch.
5. Preferences: one store, `uri.living.companion.*` keys only, per-companion
   looks, corrupt values fall back (`companion_preferences.dart`).
6. One frame clock (`companion/frame_clock.dart`) mutes its ticker between
   paints so a cap reduces frames actually produced; stops with no listener;
   suspends while minimised (`services/window_visibility.dart`, because
   Windows reports only `inactive` on minimise). Adaptive policy is pure and
   tested. Windows timer resolution raised to 1 ms only while pacing
   (`fine_timer.dart`).
7. Render quality renders the shader offscreen at 0.75 or 0.5 resolution and
   scales up (`CompanionOrbPainter`).
8. Voice: `VoiceCatalog` lists installed System.Speech and OneCore voices
   through a bundled PowerShell bridge (`assets/voice/voice_engine.ps1`,
   inputs only through environment variables); previews run out of process.
   Rate, pitch and volume are offered because measurement showed each changes
   the audio (`docs/companions/settings/evidence/voice/voice_params.json`);
   style and microphone gain are shown unavailable. `VoiceServiceAdapter` +
   `VoiceServiceBinding` are the interface a future voice service feeds; **no
   live voice service exists on this line**; the only voice frames are a
   scripted System.Speech recording labelled SIMULATED.

## Changes the reviewer should check closely

* `living_shell_test.dart`: four accepted assertions were adapted because the
  default orb is now Solar, not the Energy Orb (classic-orb checks now select
  classic first; `EnergyOrb` is found inside the shell slot). Is each
  adaptation faithful to the original intent?
* `voice_session.dart`: `VoiceSessionController.simulated` became settable.
* `companion_sources.dart`: `CompositeCompanionSource.addSource`.
* `living_app.dart`, `living_scope.dart`, `workspace_mode_view.dart`: these
  files are also edited by the parallel `integration/ws-hardening-20261009`
  line; the candidate kept its hunks away from that line's hunks.

## Reproduce (from `uri_ui/`, Windows, Flutter 3.47.2)

```
flutter pub get
flutter analyze lib/living lib/services/windows_voice_catalog.dart lib/services/window_visibility.dart lib/main_living.dart tool test/living
flutter test
flutter run -d windows -t tool/capture/settings_capture_app.dart --dart-define=OUT=<absolute dir>
flutter build windows --profile -t tool/demo/companion_perf.dart
```

From the repository root:

```
powershell -NoProfile -File rnd/companions/settings/run_matrix.ps1 -OutDir <dir>
python rnd/companions/settings/summarize.py <dir>
python rnd/companions/settings/measure_voice_params.py <dir>
```

A read-only sandbox cannot run `flutter test` (it writes build output); the
candidate's own runs are recorded in the report, and the candidate re-runs
every gate unsandboxed after review.

## Integrity commands

```
git diff --name-only 037229c..HEAD | cut -d/ -f1 | sort | uniq -c      # expected: docs, rnd, uri_ui only
git diff --name-only 569cf7c..HEAD -- uri_ui | grep -v -e '^uri_ui/lib/living/' -e '^uri_ui/test/living/' -e '^uri_ui/tool/' -e '^uri_ui/shaders/' -e '^uri_ui/test/fixtures/'
git diff 4c463e6..HEAD -- uri_ui/shaders                                 # expected: empty
git ls-files --eol -- $(git diff --name-only 8fad876..HEAD) | grep -v 'i/lf'   # expected: empty
```

## Known limitations (stated by the candidate)

No live microphone or URI speech; Windows only verified; one GPU (RX 7900 GRE)
at device pixel ratio 1.0; Brain contention observed only as available (other
sessions own the Brain); `window_visibility` must also be bound by any other
entry point that mounts `LivingApp` (the working-system entry on the parallel
line does not yet); the classic orb ignores the appearance sliders by design.

## Requested output

An explicit verdict (ACCEPT, ACCEPT WITH FINDINGS, or REJECT) and findings with
severity (blocking / non-blocking), file and line, and the evidence that
supports each.
