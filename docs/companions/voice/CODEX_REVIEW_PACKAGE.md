# Independent review package — companion presence (voice and state)

For an independent reviewer (Codex). Verify from primary evidence; do not take
the candidate report's claims on trust.

## Identity

| | |
|---|---|
| Branch | `phase/companion-voice` (local) |
| Worktree | `C:\Users\cheta\Development\uri-companion-voice` |
| Base | `d7a052f` — `phase/living-companions`, itself an **unaccepted** candidate |
| Candidate code commit | `4c463e6` (all code, tests, evidence) |
| Package commit | the commit that adds this filled-in package (docs only); see `git log --oneline d7a052f..phase/companion-voice` |
| Report | `docs/companions/voice/VOICE_PRESENCE_REPORT.md` |
| Evidence | `docs/companions/voice/evidence/` |

## Scope of change

```
git diff --stat d7a052f..4c463e6
```

Expected: new files under `uri_ui/lib/living/voice/`, `uri_ui/shaders/voice_waveform.frag`,
`uri_ui/test/living/voice_presence_test.dart`, `uri_ui/test/fixtures/voice/`,
`uri_ui/tool/capture/voice_capture_app.dart`, `uri_ui/tool/demo/voice_demo.dart`,
`rnd/voice/`, `rnd/companions/state_tables.{py,json}`, `docs/companions/voice/`;
modified only `uri_ui/lib/living/companion/companion_orb.dart`,
`rnd/companions/registry.js`, `uri_ui/pubspec.yaml`.

Integrity checks to run:

```
git diff --name-only d7a052f..4c463e6 -- uri_ui/lib | grep -v "^uri_ui/lib/living/voice/" 
# expected: only uri_ui/lib/living/companion/companion_orb.dart
# (checked by the candidate before submitting: as expected)
git diff --name-only d7a052f..4c463e6 -- uri_v1 uri_agent scripts uri_ui/lib/living/companion/companion_state.dart uri_ui/lib/living/companion/companion_sources.dart uri_ui/lib/living/companion/energy_orb.dart uri_ui/lib/living/presentation uri_ui/shaders/companion_*.frag uri_ui/shaders/orb_*.frag
# expected: empty (no Core/Runtime, no state contract, no accepted orb, no
# presentation controller, no existing shader touched; checked: empty)
```

## Reproduce (from `uri_ui/`, Windows desktop, Flutter 3.47.2)

```
flutter pub get
flutter analyze lib/living tool test/living
flutter test
flutter test test/living/voice_presence_test.dart
flutter run -d windows -t tool/capture/voice_capture_app.dart --dart-define=OUT=<dir>
python ../rnd/voice/sheets.py <dir>
python ../rnd/voice/state_metrics.py <dir> scaled
flutter build windows --profile -t tool/demo/voice_demo.dart
```

Then from the repository root:

```
powershell -NoProfile -File rnd/voice/run_matrix.ps1 -OutDir <perf dir>
python rnd/voice/summarize_perf.py <perf dir>
```

Interactive demonstration: `flutter run -d windows -t tool/demo/voice_demo.dart`.

Fixture regeneration (deterministic; WAV MD5 should be unchanged):
`powershell -NoProfile -File rnd/voice/make_fixtures.ps1`.

## Claims to verify, and where

1. **One waveform for both speakers.** `VoiceWaveformPainter.uniformsFor` has
   no speaker slot; the capture log line `SAME_AUDIO identical=5 different=0`
   and `sheet_same_audio.png`; test "the same audio as the user and as URI
   gives identical levels".
2. **Correct source.** Controller drops `AudioLevel` from the non-speaking
   stream — tests "audio from the stream that is not speaking is ignored",
   "nothing drives the waveform when voice is off".
3. **Equal effort drawn equally.** Per-stream bounded reference in
   `voice_level.dart`; test with a 9 dB quieter stream. Reviewer question: is a
   2.5 s / ±10 dB adaptive reference an acceptable reading of "same amplitude
   mapping for equivalent signals"?
4. **Recovery.** `reduceVoice` rules and watchdog; random-storm test; rapid
   widget test asserting the companion element is never remounted.
5. **State expression.** `state_tables.py` header; `state_metrics.py` output in
   the report §5; `sheet_states.png`. Reviewer judgement needed on whether
   Lunar's states differ enough.
6. **No simulated evidence presented as live.** Every voice capture carries the
   SIMULATED tag; report §0 and §10.
7. **Performance.** Report §8, raw JSON/CSV in `evidence/perf/`, hardware and
   method stated; Brain-active limitation stated.

## Known limitations (stated by the candidate)

No live microphone or live URI speech; synthetic stand-in for the user's
voice; Brain-active run limited (§8); one desktop GPU at device pixel ratio
1.0; not wired into `living_shell.dart`; screen-reader behaviour checked via
semantics only; base candidate itself unaccepted.

## Out of scope / requires owner

Adopting companions in the shell, choosing an audio owner and TTS, any merge,
any cutover.
