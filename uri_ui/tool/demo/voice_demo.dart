// Interactive demonstration and performance harness for the companion
// presence: the live CompanionPresence widget (tickers, transitions, the
// waveform glide) driven by a scripted voice session in real time.
//
// The voice audio is genuine speech (System.Speech fixtures in
// test/fixtures/voice), measured block by block and delivered on the wall
// clock exactly as a live capture or playback tap would deliver it. The
// sessions are scripted, so everything on screen is labelled SIMULATED. No
// microphone is opened and no sound is played.
//
// Interactive:
//   flutter run -d windows -t tool/demo/voice_demo.dart
//
// Performance (profile mode; writes a JSON summary and exits):
//   flutter run --profile -d windows -t tool/demo/voice_demo.dart \
//     --dart-define=PERF=90 --dart-define=SCENARIO=cycle \
//     --dart-define=IDENTITY=lunar --dart-define=SIZE=panel \
//     --dart-define=OUT=<file.json>
//
// SCENARIO: cycle (every state and both speakers, repeating), idle (the idle
// companion only), voice (user and URI turns back to back).
// SIZE: floating 280x380, panel 480x560, workspace 720x460 (logical px).
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/companion_theme.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/voice/companion_presence.dart';
import 'package:uri_ui/living/voice/voice_level.dart';
import 'package:uri_ui/living/voice/voice_script.dart';
import 'package:uri_ui/living/voice/voice_session.dart';
import 'package:uri_ui/theme/uri_theme.dart';

// Settings come from the environment at run time (falling back to
// --dart-define), so one profile build can run every scenario.
String _env(String k, String dartDefine, String fallback) =>
    Platform.environment[k] ?? (dartDefine.isEmpty ? fallback : dartDefine);

final int perfSeconds =
    int.tryParse(
      _env('URI_VOICE_PERF', const String.fromEnvironment('PERF'), '0'),
    ) ??
    0;
final String scenario = _env(
  'URI_VOICE_SCENARIO',
  const String.fromEnvironment('SCENARIO'),
  'cycle',
);
final String identityName = _env(
  'URI_VOICE_IDENTITY',
  const String.fromEnvironment('IDENTITY'),
  'lunar',
);
final String sizeName = _env(
  'URI_VOICE_SIZE',
  const String.fromEnvironment('SIZE'),
  'panel',
);
final String outPath = _env(
  'URI_VOICE_OUT',
  const String.fromEnvironment('OUT'),
  'voice_perf.json',
);
final String fixtures = _env(
  'URI_VOICE_FIXTURES',
  const String.fromEnvironment('FIXTURES'),
  'test/fixtures/voice',
);

const Map<String, Size> sizes = {
  'floating': Size(280, 380),
  'panel': Size(480, 560),
  'workspace': Size(720, 460),
};

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

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final app = _DemoState();
  runApp(_DemoApp(state: app));
  if (perfSeconds > 0) {
    await _Perf(app).run(Duration(seconds: perfSeconds));
    exit(0);
  }
}

/// Everything the demo can change. A plain ChangeNotifier so the performance
/// driver and the buttons go through the same paths.
class _DemoState extends ChangeNotifier {
  _DemoState() {
    user = _Clip.load('user_request');
    uri = _Clip.load('uri_reply');
  }

  late final _Clip user;
  late final _Clip uri;
  final VoiceSessionController voice = VoiceSessionController(simulated: true);
  final EffectsSettings effects = EffectsSettings();
  VoiceScriptPlayer? _player;
  int _turn = 0;

  CompanionIdentity identity = CompanionIdentity.values.firstWhere(
    (i) => i.name == identityName,
    orElse: () => CompanionIdentity.lunar,
  );
  String size = sizes.containsKey(sizeName) ? sizeName : 'panel';
  CompanionSignal signal = const CompanionSignal.idle().copyWith(
    simulated: true,
  );

  void setIdentity(CompanionIdentity id) {
    identity = id;
    notifyListeners();
  }

  void setSize(String s) {
    size = s;
    notifyListeners();
  }

  void setState(CompanionState s, [String? detail]) {
    signal = CompanionSignal(
      state: s,
      detail: detail,
      simulated: true,
      sourceName: 'voice_demo',
    );
    notifyListeners();
  }

  void _play(List<(int, VoiceSignal)> events) {
    _player?.stop();
    _player = VoiceScriptPlayer(VoiceScript(events), voice)..play();
  }

  void listen() => voice.add(ListeningStarted('l${++_turn}'));

  void userSpeaks() => _play(
    VoiceScript.userTurn(
      clip: user.pcm,
      words: user.words,
      text: user.text,
      sessionId: 'u${++_turn}',
    ),
  );

  void uriReplies() => _play(
    VoiceScript.uriTurn(
      clip: uri.pcm,
      words: uri.words,
      text: uri.text,
      utteranceId: 'r${++_turn}',
    ),
  );

  /// URI starts its reply; 1.8 s in, the user starts talking over it.
  void bargeIn() {
    final r = 'r${++_turn}';
    final u = 'u${++_turn}';
    final reply = VoiceScript.uriTurn(
      clip: uri.pcm,
      words: uri.words,
      text: uri.text,
      utteranceId: r,
    );
    final interrupt = VoiceScript.userTurn(
      clip: user.pcm,
      words: user.words,
      text: user.text,
      sessionId: u,
      startMs: 1800,
      leadInMs: 0,
    );
    // The audio owner stops URI's playback at the barge-in, so its later
    // level frames never arrive; its late "ended" report still does.
    _play([
      ...reply.where((e) => e.$1 < 1800 || e.$2 is UriSpeechEnded),
      ...interrupt.where((e) => e.$2 is! ListeningStarted),
    ]);
  }

  void micFailure() {
    _player?.stop();
    voice.add(const VoiceFailure('Microphone unavailable'));
  }

  void cancel() {
    _player?.stop();
    voice.add(const VoiceReset('Cancelled'));
  }

  /// Stops delivering events mid-utterance, as a crashed audio owner would.
  void dropSignal() => _player?.stop();
}

class _DemoApp extends StatelessWidget {
  const _DemoApp({required this.state});
  final _DemoState state;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: Listenable.merge([state, state.effects]),
      builder: (context, _) {
        final palette = CompanionTheme.paletteFor(state.identity);
        return MaterialApp(
          debugShowCheckedModeBanner: false,
          theme: buildUriTheme(palette),
          home: EffectsSettingsScope(
            settings: state.effects,
            child: Scaffold(
              backgroundColor: palette.canvas,
              body: Row(
                children: [
                  Expanded(
                    child: Center(
                      child: SizedBox.fromSize(
                        size: sizes[state.size],
                        child: CompanionPresence(
                          identity: state.identity,
                          signal: state.signal,
                          voice: state.voice,
                        ),
                      ),
                    ),
                  ),
                  if (perfSeconds == 0) _Controls(state: state),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _Controls extends StatelessWidget {
  const _Controls({required this.state});
  final _DemoState state;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    Widget section(String t) => Padding(
      padding: const EdgeInsets.fromLTRB(0, 14, 0, 6),
      child: Text(t, style: TextStyle(color: c.inkSoft, fontSize: 12)),
    );
    Widget chips(List<(String, VoidCallback, bool)> items) => Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        for (final (label, onTap, on) in items)
          ChoiceChip(
            label: Text(label),
            selected: on,
            onSelected: (_) => onTap(),
          ),
      ],
    );
    final s = state.signal.state;
    return Container(
      width: 340,
      color: c.surface,
      padding: const EdgeInsets.all(16),
      child: ListView(
        children: [
          Text(
            'Companion presence',
            style: TextStyle(
              color: c.ink,
              fontSize: 16,
              fontWeight: FontWeight.w600,
            ),
          ),
          Text(
            'Scripted session, genuine speech audio. Not live.',
            style: TextStyle(color: c.warning, fontSize: 12),
          ),
          section('Identity'),
          chips([
            for (final id in CompanionIdentity.values)
              (id.label, () => state.setIdentity(id), state.identity == id),
          ]),
          section('Companion state (authoritative signal)'),
          chips([
            for (final (st, d) in const [
              (CompanionState.idle, null),
              (CompanionState.thinking, 'Understanding your request'),
              (CompanionState.working, 'Drafting the reply'),
              (CompanionState.awaitingApproval, 'Send the reply to Mr Rai?'),
              (CompanionState.success, 'Reply drafted'),
              (CompanionState.error, 'The last request failed'),
              (CompanionState.unavailable, 'URI server unreachable'),
            ])
              (st.label, () => state.setState(st, d), s == st),
          ]),
          section('Voice'),
          chips([
            ('Listen', state.listen, false),
            ('User speaks', state.userSpeaks, false),
            ('URI replies', state.uriReplies, false),
            ('Barge-in', state.bargeIn, false),
            ('Microphone failure', state.micFailure, false),
            ('Drop signal', state.dropSignal, false),
            ('Cancel', state.cancel, false),
          ]),
          section('Size'),
          chips([
            for (final k in sizes.keys)
              (k, () => state.setSize(k), state.size == k),
          ]),
          section('Accessibility'),
          SwitchListTile(
            dense: true,
            title: const Text('Reduced motion'),
            value: state.effects.reducedMotion,
            onChanged: state.effects.setReducedMotion,
          ),
          SwitchListTile(
            dense: true,
            title: const Text('Reduced effects'),
            value: state.effects.reducedEffects,
            onChanged: state.effects.setReducedEffects,
          ),
        ],
      ),
    );
  }
}

/// Drives a scenario and records every frame's build and raster time.
class _Perf {
  _Perf(this.app);
  final _DemoState app;
  // Per-frame build, raster and total time in ms, in typed buffers (12 bytes
  // a frame). The first 10-minute run held the FrameTiming objects and its
  // RSS growth was partly the harness measuring itself; the second used
  // boxed records and still grew. Typed buffers keep the harness's own
  // footprint near 1 MB for 10 minutes at 144 fps.
  final _FloatBuf _build = _FloatBuf();
  final _FloatBuf _raster = _FloatBuf();
  final _FloatBuf _total = _FloatBuf();

  void _onTimings(List<FrameTiming> timings) {
    for (final t in timings) {
      _build.add(t.buildDuration.inMicroseconds / 1000.0);
      _raster.add(t.rasterDuration.inMicroseconds / 1000.0);
      _total.add(t.totalSpan.inMicroseconds / 1000.0);
    }
  }

  final List<Map<String, Object>> _windows = [];
  final List<(int, int)> _rss = [];

  Future<void> run(Duration length) async {
    // Let the window, the shaders and the first frames settle before
    // measuring, so start-up is not reported as steady-state cost.
    await Future<void>.delayed(const Duration(seconds: 4));
    SchedulerBinding.instance.addTimingsCallback(_onTimings);
    final clock = Stopwatch()..start();
    final driver = _driver(clock);
    var windowStart = 0;
    while (clock.elapsed < length) {
      await Future<void>.delayed(const Duration(seconds: 5));
      _rss.add((clock.elapsedMilliseconds, ProcessInfo.currentRss));
      _windows.add(
        _summary(windowStart, _raster.length, clock.elapsedMilliseconds),
      );
      windowStart = _raster.length;
    }
    driver.cancel();
    SchedulerBinding.instance.removeTimingsCallback(_onTimings);
    final report = {
      'scenario': scenario,
      'identity': app.identity.name,
      'size': app.size,
      'logical_size':
          '${sizes[app.size]!.width.toInt()}x${sizes[app.size]!.height.toInt()}',
      'device_pixel_ratio':
          ui.PlatformDispatcher.instance.views.first.devicePixelRatio,
      'seconds': length.inSeconds,
      'mode': kReleaseMode ? 'release' : (kProfileMode ? 'profile' : 'debug'),
      'overall': _summary(0, _raster.length, clock.elapsedMilliseconds),
      'windows_5s': _windows,
      'rss_bytes': [
        for (final (t, r) in _rss) {'t_ms': t, 'rss': r},
      ],
      'max_rss': ProcessInfo.maxRss,
      'simulated': true,
    };
    // A failed write must still end the run: a performance harness that
    // hangs on its own report would be measured as an idle window.
    try {
      File(outPath)
          .writeAsStringSync(const JsonEncoder.withIndent(' ').convert(report));
    } catch (e) {
      stderr.writeln('VOICE_PERF_WRITE_FAILED $outPath: $e');
    }
    stdout.writeln('VOICE_PERF_DONE frames=${_raster.length} out=$outPath');
  }

  Map<String, Object> _summary(int from, int to, int tMs) {
    if (to <= from) return {'t_ms': tMs, 'frames': 0};
    double pct(List<double> v, double p) => v[((v.length - 1) * p).round()];
    final build = _build.slice(from, to)..sort();
    final raster = _raster.slice(from, to)..sort();
    final total = _total.slice(from, to)..sort();
    return {
      't_ms': tMs,
      'frames': to - from,
      'build_p50': pct(build, .5),
      'build_p99': pct(build, .99),
      'raster_p50': pct(raster, .5),
      'raster_p90': pct(raster, .9),
      'raster_p99': pct(raster, .99),
      'raster_max': raster.last,
      'total_p50': pct(total, .5),
      'total_p99': pct(total, .99),
      'over_16ms': total.where((v) => v > 16.7).length,
    };
  }

  Timer _driver(Stopwatch clock) {
    // A fixed, repeating timeline. Each step names what the authoritative
    // signal says and what the voice channel does.
    final steps = <(int, void Function())>[];
    var t = 0;
    void at(int dt, void Function() f) {
      steps.add((t, f));
      t += dt;
    }

    switch (scenario) {
      case 'idle':
        at(1000, () => app.setState(CompanionState.idle));
      case 'voice':
        at(8200, app.userSpeaks);
        at(9600, app.uriReplies);
      default:
        at(2500, () => app.setState(CompanionState.idle));
        at(1500, app.listen);
        at(8200, app.userSpeaks);
        at(
          3000,
          () => app.setState(
            CompanionState.thinking,
            'Understanding your request',
          ),
        );
        at(
          4000,
          () => app.setState(CompanionState.working, 'Drafting the reply'),
        );
        at(9600, () {
          app.setState(CompanionState.idle);
          app.uriReplies();
        });
        at(
          5000,
          () =>
              app.setState(CompanionState.awaitingApproval, 'Send the reply?'),
        );
        at(2000, () => app.setState(CompanionState.success, 'Reply drafted'));
    }
    final cycle = t;
    var next = 0;
    var base = 0;
    return Timer.periodic(const Duration(milliseconds: 20), (_) {
      final now = clock.elapsedMilliseconds;
      while (base + steps[next].$1 <= now) {
        steps[next].$2();
        next++;
        if (next == steps.length) {
          next = 0;
          base += cycle;
        }
      }
    });
  }
}

/// A growable buffer of float32 values.
class _FloatBuf {
  Float32List _data = Float32List(4096);
  int length = 0;

  void add(double v) {
    if (length == _data.length) {
      _data = Float32List(_data.length * 2)..setAll(0, _data);
    }
    _data[length++] = v;
  }

  List<double> slice(int from, int to) =>
      List<double>.of(_data.sublist(from, to));
}
