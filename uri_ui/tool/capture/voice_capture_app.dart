// Offscreen capture harness for the companion states and the shared voice
// waveform.
//
// Runs as a real Windows desktop Flutter app (same engine, same Impeller
// backend, same FragmentShader path as the product) and writes PNGs of the
// shipped composition: `PresenceLayout` + `PresenceComposition`, with the
// companion and the waveform given as deterministic frames so every image is
// reproducible.
//
// Voice frames are driven by genuine speech audio (System.Speech fixtures in
// test/fixtures/voice), measured block by block through the same
// VoiceLevelMapper and VoiceSessionController the live UI uses. The sessions
// are scripted, so every voice frame is SIMULATED as a session and is labelled
// so on screen.
//
// Usage (from uri_ui/):
//   flutter run -d windows -t tool/capture/voice_capture_app.dart \
//     --dart-define=OUT=<dir>
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/companion_theme.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/voice/companion_presence.dart';
import 'package:uri_ui/living/voice/voice_level.dart';
import 'package:uri_ui/living/voice/voice_script.dart';
import 'package:uri_ui/living/voice/voice_session.dart';
import 'package:uri_ui/living/voice/voice_waveform.dart';
import 'package:uri_ui/theme/uri_theme.dart';

const String outDir = String.fromEnvironment('OUT', defaultValue: 'captures');
const String fixtures = String.fromEnvironment(
  'FIXTURES',
  defaultValue: 'test/fixtures/voice',
);

/// One shot: everything the composition needs, fixed.
class Shot {
  Shot({
    required this.name,
    required this.identity,
    required this.size,
    required this.signal,
    required this.session,
    this.v = 0,
    this.seconds = 17,
    this.level = 0,
    this.flux = 0,
    this.attentionWave,
    this.reducedEffects = false,
    this.waveOnly = false,
  });

  final String name;
  final CompanionIdentity identity;
  final Size size;
  final CompanionSignal signal;
  final VoiceSession session;
  final double v;
  final double seconds;
  final double level;
  final double flux;

  /// 0..1 position in the approval pulse, or null for no pulse.
  final double? attentionWave;
  final bool reducedEffects;

  /// Render only the waveform rectangle (for the identical-pixels check).
  final bool waveOnly;
}

final ValueNotifier<Shot?> current = ValueNotifier<Shot?>(null);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final key = GlobalKey();
  runApp(_Host(boundaryKey: key));
  await _run(key);
  exit(0);
}

class _Host extends StatelessWidget {
  const _Host({required this.boundaryKey});
  final GlobalKey boundaryKey;

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<Shot?>(
      valueListenable: current,
      builder: (context, shot, _) {
        if (shot == null) return const SizedBox();
        final palette = CompanionTheme.paletteFor(shot.identity);
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          // Each shot must stand alone: no theme or text animating in from
          // the previous one.
          themeAnimationDuration: Duration.zero,
          theme: buildUriTheme(palette),
          home: Scaffold(
            backgroundColor: palette.canvas,
            body: Center(
              child: RepaintBoundary(
                key: boundaryKey,
                child: EffectsSettingsScope(
                  settings: EffectsSettings(
                    reducedEffects: shot.reducedEffects,
                  ),
                  child: SizedBox.fromSize(
                    size: shot.waveOnly
                        ? PresenceLayout.of(shot.size, 1).wave.size
                        : shot.size,
                    child: ColoredBox(
                      color: palette.canvas,
                      child: KeyedSubtree(
                        key: ValueKey(shot.name),
                        child: shot.waveOnly ? _waveOnly(shot) : _scene(shot),
                      ),
                    ),
                  ),
                ),
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _waveOnly(Shot s) =>
      VoiceWaveformFrame(seconds: s.seconds, level: s.level, flux: s.flux);

  Widget _scene(Shot s) {
    final view = resolvePresence(s.signal, s.session);
    final layout = PresenceLayout.of(s.size, s.v);
    var params = CompanionParams.of(s.identity, view.orbState);
    if (s.attentionWave != null) {
      params = params.withAttention(s.attentionWave!);
    }
    return PresenceComposition(
      layout: layout,
      orbScale: presenceScale(s.identity),
      voiceOpacity: PresenceLayout.voiceOpacity(s.v),
      view: view,
      session: s.session,
      transcriptSpeaker: view.speaker ?? s.session.speaker,
      orb: CompanionOrbFrame(
        identity: s.identity,
        params: params,
        seconds: s.seconds,
      ),
      waveform: (o) => VoiceWaveformFrame(
        seconds: s.seconds,
        level: s.level,
        flux: s.flux,
        presence: o,
      ),
    );
  }
}

class _Clip {
  _Clip(this.pcm, this.text, this.words);
  final PcmClip pcm;
  final String text;
  final List<WordTiming> words;

  static _Clip load(String name) {
    final pcm = decodeWavPcm16(File('$fixtures/$name.wav').readAsBytesSync());
    final json = jsonDecode(
      File('$fixtures/$name.timing.json').readAsStringSync(),
    ) as Map<String, dynamic>;
    return _Clip(pcm, json['text'] as String, VoiceScript.wordsFromJson(json));
  }
}

/// Replays [script] up to [ms] into a fresh controller: the same reducer, the
/// same level mapper, the same speaker gating as the live UI.
(VoiceSession, double, double) replay(VoiceScript script, int ms) {
  final c = VoiceSessionController(simulated: true);
  for (final e in script.until(ms)) {
    c.add(e);
  }
  final r = (c.session, c.level.value, c.flux.value);
  c.dispose();
  return r;
}

const _signals = <CompanionState, CompanionSignal>{
  CompanionState.idle: CompanionSignal.idle(),
  CompanionState.listening: CompanionSignal(state: CompanionState.idle),
  CompanionState.thinking: CompanionSignal(
    state: CompanionState.thinking,
    detail: 'Understanding your request',
  ),
  CompanionState.working: CompanionSignal(
    state: CompanionState.working,
    detail: 'Drafting the reply',
  ),
  CompanionState.awaitingApproval: CompanionSignal(
    state: CompanionState.awaitingApproval,
    detail: 'Send the reply to Mr Rai?',
  ),
  CompanionState.success: CompanionSignal(
    state: CompanionState.success,
    detail: 'Reply drafted',
  ),
  CompanionState.error: CompanionSignal(
    state: CompanionState.error,
    detail: 'The last request failed',
  ),
  CompanionState.unavailable: CompanionSignal(
    state: CompanionState.unavailable,
    detail: 'URI server unreachable',
  ),
};

Future<void> _run(GlobalKey key) async {
  Directory(outDir).createSync(recursive: true);
  final log = StringBuffer();
  var written = 0;
  var failed = 0;

  Future<Uint8List?> shoot(Shot s) async {
    current.value = s;
    for (var i = 0; i < 4; i++) {
      WidgetsBinding.instance.scheduleFrame();
      await WidgetsBinding.instance.endOfFrame;
    }
    final obj = key.currentContext?.findRenderObject();
    if (obj is! RenderRepaintBoundary) {
      failed++;
      stderr.writeln('CAPTURE_FAILED ${s.name}');
      return null;
    }
    final img = await obj.toImage(pixelRatio: 2.0);
    final png = await img.toByteData(format: ui.ImageByteFormat.png);
    img.dispose();
    final bytes = png!.buffer.asUint8List();
    File('$outDir/${s.name}.png').writeAsBytesSync(bytes);
    written++;
    stdout.writeln('CAPTURED ${s.name}.png ${bytes.length}');
    return bytes;
  }

  for (final id in CompanionIdentity.values) {
    await CompanionShaderCache.load(id);
  }
  await VoiceWaveformShader.load();
  if (VoiceWaveformShader.failure != null) {
    stderr.writeln('WAVEFORM_SHADER_FAILED ${VoiceWaveformShader.failure}');
  } else {
    stdout.writeln('WAVEFORM_SHADER_LOADED $kVoiceWaveformAsset');
  }

  final user = _Clip.load('user_request');
  final uri = _Clip.load('uri_reply');
  final userScript = VoiceScript(
    VoiceScript.userTurn(
      clip: user.pcm,
      words: user.words,
      text: user.text,
      sessionId: 'u1',
    ),
  );
  final uriScript = VoiceScript(
    VoiceScript.uriTurn(
      clip: uri.pcm,
      words: uri.words,
      text: uri.text,
      utteranceId: 'r1',
    ),
  );
  // The URI clip delivered as if it were the user's microphone: same audio,
  // other speaker. Used for the identical-pixels comparison.
  final uriAsUser = VoiceScript(
    VoiceScript.userTurn(
      clip: uri.pcm,
      words: uri.words,
      text: uri.text,
      sessionId: 'swap',
      leadInMs: 0,
    ),
  );

  const main = Size(480, 560);

  // 1. Companion states, every identity.
  const states = <CompanionState>[
    CompanionState.idle,
    CompanionState.listening,
    CompanionState.thinking,
    CompanionState.working,
    CompanionState.awaitingApproval,
    CompanionState.success,
    CompanionState.error,
    CompanionState.unavailable,
  ];
  for (final id in CompanionIdentity.values) {
    for (final st in states) {
      final listening = st == CompanionState.listening;
      await shoot(
        Shot(
          name: 'state_${id.name}_${st.name}',
          identity: id,
          size: main,
          signal: _signals[st]!,
          session: listening
              ? const VoiceSession(phase: VoicePhase.listening, sessionId: 'l')
              : const VoiceSession(),
          attentionWave: st == CompanionState.awaitingApproval ? 0.0 : null,
        ),
      );
    }
    // The approval pulse at its peak, to show its amplitude.
    await shoot(
      Shot(
        name: 'state_${id.name}_awaitingApproval_pulse',
        identity: id,
        size: main,
        signal: _signals[CompanionState.awaitingApproval]!,
        session: const VoiceSession(),
        attentionWave: 1.0,
      ),
    );
  }

  // 2. Voice, both speakers, every identity, several moments of real speech.
  const userTimes = <int>[900, 1700, 2600, 3800, 5200];
  const uriTimes = <int>[600, 2100, 3900, 5600, 7800];
  for (final id in CompanionIdentity.values) {
    for (final t in userTimes) {
      final (s, l, f) = replay(userScript, t);
      await shoot(
        Shot(
          name: 'voice_${id.name}_user_t${t.toString().padLeft(4, '0')}',
          identity: id,
          size: main,
          signal: const CompanionSignal.idle().copyWith(simulated: true),
          session: s,
          v: 1,
          seconds: t / 1000,
          level: l,
          flux: f,
        ),
      );
      log.writeln(
        'user t=$t phase=${s.phase.name} level=${l.toStringAsFixed(3)} transcript="${s.transcript}"',
      );
    }
    for (final t in uriTimes) {
      final (s, l, f) = replay(uriScript, t);
      await shoot(
        Shot(
          name: 'voice_${id.name}_uri_t${t.toString().padLeft(4, '0')}',
          identity: id,
          size: main,
          signal: const CompanionSignal.idle().copyWith(simulated: true),
          session: s,
          v: 1,
          seconds: t / 1000,
          level: l,
          flux: f,
        ),
      );
      log.writeln(
        'uri t=$t phase=${s.phase.name} level=${l.toStringAsFixed(3)} spoken=${s.spokenChars}',
      );
    }
  }

  // 3. Same audio, both speakers: the waveform alone must be pixel-identical.
  var identical = 0;
  var different = 0;
  for (final t in const <int>[700, 1900, 3300, 5100, 7400]) {
    final (su, lu, fu) = replay(uriAsUser, t);
    final (sr, lr, fr) = replay(uriScript, t);
    final a = await shoot(
      Shot(
        name: 'same_audio_as_user_t$t',
        identity: CompanionIdentity.lunar,
        size: main,
        signal: const CompanionSignal.idle(),
        session: su,
        seconds: t / 1000,
        level: lu,
        flux: fu,
        waveOnly: true,
      ),
    );
    final b = await shoot(
      Shot(
        name: 'same_audio_as_uri_t$t',
        identity: CompanionIdentity.lunar,
        size: main,
        signal: const CompanionSignal.idle(),
        session: sr,
        seconds: t / 1000,
        level: lr,
        flux: fr,
        waveOnly: true,
      ),
    );
    final same = a != null && b != null && _bytesEqual(a, b);
    same ? identical++ : different++;
    log.writeln(
      'same-audio t=$t user(level=${lu.toStringAsFixed(4)}, phase=${su.phase.name}) '
      'uri(level=${lr.toStringAsFixed(4)}, phase=${sr.phase.name}) png_identical=$same',
    );
  }
  stdout.writeln('SAME_AUDIO identical=$identical different=$different');

  // 4. Orb to waveform transition, mid-sentence.
  final (ts, tl, tf) = replay(userScript, 2600);
  for (final v in const <double>[0, 0.2, 0.4, 0.6, 0.8, 1]) {
    await shoot(
      Shot(
        name:
            'transition_sakura_v${(v * 100).round().toString().padLeft(3, '0')}',
        identity: CompanionIdentity.sakura,
        size: main,
        signal: const CompanionSignal.idle().copyWith(simulated: true),
        session: ts,
        v: v,
        seconds: 2.6,
        level: tl,
        flux: tf,
      ),
    );
  }

  // 5. Sizes: floating companion and a wide workspace panel.
  for (final entry in const <(String, Size)>[
    ('floating', Size(280, 380)),
    ('workspace', Size(720, 460)),
  ]) {
    final (s, l, f) = replay(uriScript, 3900);
    await shoot(
      Shot(
        name: 'size_${entry.$1}_solar_uri',
        identity: CompanionIdentity.solar,
        size: entry.$2,
        signal: const CompanionSignal.idle().copyWith(simulated: true),
        session: s,
        v: 1,
        seconds: 3.9,
        level: l,
        flux: f,
      ),
    );
    await shoot(
      Shot(
        name: 'size_${entry.$1}_solar_idle',
        identity: CompanionIdentity.solar,
        size: entry.$2,
        signal: const CompanionSignal.idle(),
        session: const VoiceSession(),
      ),
    );
  }

  // 6. Edge cases: approval named over URI speech, voice failure notice,
  // reduced effects fallback, silence at the start of a listener.
  final (aps, apl, apf) = replay(uriScript, 2100);
  await shoot(
    Shot(
      name: 'edge_approval_over_speech_moonlit',
      identity: CompanionIdentity.moonlit,
      size: main,
      signal: _signals[CompanionState.awaitingApproval]!.copyWith(
        simulated: true,
      ),
      session: aps,
      v: 1,
      seconds: 2.1,
      level: apl,
      flux: apf,
    ),
  );
  await shoot(
    Shot(
      name: 'edge_voice_failure_lunar',
      identity: CompanionIdentity.lunar,
      size: main,
      signal: const CompanionSignal.idle(),
      session: reduceVoice(
        replay(userScript, 2000).$1,
        const VoiceFailure('Microphone unavailable'),
      ),
    ),
  );
  final (fs, fl, ff) = replay(userScript, 2600);
  await shoot(
    Shot(
      name: 'edge_reduced_effects_solar_user',
      identity: CompanionIdentity.solar,
      size: main,
      signal: const CompanionSignal.idle().copyWith(simulated: true),
      session: fs,
      v: 1,
      level: fl,
      flux: ff,
      reducedEffects: true,
    ),
  );
  final (ss, sl, sf) = replay(userScript, 300);
  await shoot(
    Shot(
      name: 'edge_silence_before_speech_sakura',
      identity: CompanionIdentity.sakura,
      size: main,
      signal: const CompanionSignal.idle().copyWith(simulated: true),
      session: ss,
      level: sl,
      flux: sf,
    ),
  );

  File('$outDir/capture_log.txt').writeAsStringSync(log.toString());
  stdout.writeln('VOICE_CAPTURE_DONE written=$written failed=$failed');
}

bool _bytesEqual(Uint8List a, Uint8List b) {
  if (a.length != b.length) return false;
  for (var i = 0; i < a.length; i++) {
    if (a[i] != b[i]) return false;
  }
  return true;
}
