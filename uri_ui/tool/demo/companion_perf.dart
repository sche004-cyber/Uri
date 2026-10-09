// Focused performance harness for Companion Settings.
//
// Runs the real living app (or, for render-cost measurement, one large
// companion) with a given frame-rate mode and render quality, records every
// engine frame's build and raster time, the companion clock's deliveries, the
// adaptive cap over time, process RSS and the Dart heap, then writes one JSON
// report and exits. Build in profile mode; nothing here is a benchmark of a
// mock: the shell, the clock, the governor and the shaders are the product's.
//
//   flutter build windows --profile -t tool/demo/companion_perf.dart
//
// Driven by rnd/companions/settings/run_companion_perf.ps1, through these
// environment variables:
//
// | variable | meaning |
// |---|---|
// | URI_CP_OUT | absolute path of the JSON report (required) |
// | URI_CP_SECONDS | run length, default 30 |
// | URI_CP_IDENTITY | solar, sakura, lunar, moonlit or classic |
// | URI_CP_FPS | adaptive, fps30, fps60, fps90, fps144 |
// | URI_CP_QUALITY | full, balanced, performance |
// | URI_CP_LAYOUT | shell (Companion mode of the app) or large (one companion filling the window) |
// | URI_CP_CYCLE | 1: step the companion through its states every 4 s |
//
// Preferences are in memory only; the shared preferences file is never read
// or written.
import 'dart:async';
import 'dart:convert';
import 'dart:developer' as developer;
import 'dart:io';
import 'dart:isolate' show Isolate;
import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' show FramePhase, FrameTiming;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/companion/frame_clock.dart';
import 'package:uri_ui/living/companion/living_companion.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/services/window_visibility.dart';
import 'package:uri_ui/theme/uri_theme.dart';

final Map<String, String> env = Platform.environment;
String opt(String k, String d) => env[k]?.isNotEmpty == true ? env[k]! : d;

/// Growable float storage without boxing every sample.
class FloatBuf {
  Float32List _d = Float32List(4096);
  int length = 0;
  void add(double v) {
    if (length == _d.length) {
      final n = Float32List(_d.length * 2)..setAll(0, _d);
      _d = n;
    }
    _d[length++] = v;
  }

  List<double> toList() => List<double>.generate(length, (i) => _d[i]);
}

final FloatBuf build = FloatBuf();
final FloatBuf raster = FloatBuf();
final FloatBuf finishS = FloatBuf();
int? firstFinishUs;

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final out = env['URI_CP_OUT'];
  if (out == null || out.isEmpty) {
    stderr.writeln('URI_CP_OUT is required');
    exit(2);
  }
  final seconds = int.parse(opt('URI_CP_SECONDS', '30'));
  final identity = opt('URI_CP_IDENTITY', 'lunar');
  final fps = opt('URI_CP_FPS', 'adaptive');
  final quality = opt('URI_CP_QUALITY', 'full');
  final layout = opt('URI_CP_LAYOUT', 'shell');
  final cycle = env['URI_CP_CYCLE'] == '1';

  // In-memory preferences seeded with the run's settings.
  // ignore: invalid_use_of_visible_for_testing_member
  SharedPreferences.setMockInitialValues({
    CompanionPreferences.keyChoice: identity,
    CompanionPreferences.keyFrameRate: fps,
    CompanionPreferences.keyQuality: quality,
  });

  final appState = AppState(
    MockUriClient(),
    preferencesStore: LivingPreferencesStore(),
  );
  final services = LivingApp.buildDefaultServices(appState);
  final capChanges = <Map<String, num>>[];
  final sw = Stopwatch()..start();
  var lastCap = -1.0;
  void noteCap() {
    final c = services.frameGovernor.effectiveCap;
    if (c != lastCap) {
      lastCap = c;
      capChanges.add({'t_s': sw.elapsedMilliseconds / 1000, 'cap': c});
    }
  }

  services.frameGovernor.addListener(noteCap);
  await bindWindowVisibility(services.frameClock);
  final lifecycle = <Map<String, Object>>[];
  final lifecycleListener = AppLifecycleListener(
    onStateChange: (st) =>
        lifecycle.add({'t_s': sw.elapsedMilliseconds / 1000, 'state': st.name}),
  );

  SchedulerBinding.instance.addTimingsCallback((List<FrameTiming> ts) {
    for (final t in ts) {
      final fin = t.timestampInMicroseconds(FramePhase.rasterFinish);
      firstFinishUs ??= fin;
      build.add(t.buildDuration.inMicroseconds / 1000);
      raster.add(t.rasterDuration.inMicroseconds / 1000);
      finishS.add((fin - firstFinishUs!) / 1e6);
    }
  });

  if (layout == 'large') {
    final prefs = services.companionPrefs;
    services.companionPrefs.restoreFrom(await SharedPreferences.getInstance());
    services.frameGovernor.install();
    runApp(_Large(services: services, prefs: prefs));
    // The shell does this in LivingApp; here the governor learns the display
    // rate directly, so a fixed cap means the same thing in both layouts.
    await WidgetsBinding.instance.endOfFrame;
    final view = WidgetsBinding.instance.platformDispatcher.views.first;
    services.frameGovernor.updateDisplay(view.display.refreshRate);
  } else {
    runApp(
      LivingApp(appState: appState, services: services, skipOnboarding: true),
    );
  }

  // Samples: RSS and Dart heap every 5 s.
  final rss = <Map<String, num>>[];
  final heap = <Map<String, num>>[];
  final vm = await _VmService.connect();
  final ticks0 = services.frameClock.ticks;
  final perSecond = <Map<String, num>>[];
  var lastTicks = ticks0;
  var lastFrames = 0;
  var phase = 0;
  const states = [
    CompanionState.idle,
    CompanionState.listening,
    CompanionState.thinking,
    CompanionState.working,
    CompanionState.speaking,
    CompanionState.awaitingApproval,
  ];
  for (var s = 1; s <= seconds; s++) {
    await Future<void>.delayed(const Duration(seconds: 1));
    noteCap();
    final t = services.frameClock.ticks;
    perSecond.add({
      't_s': s,
      'frames': build.length - lastFrames,
      'companion_frames': t - lastTicks,
      'cap': services.frameGovernor.effectiveCap,
      'hidden': services.frameClock.hidden ? 1 : 0,
      'clock_running': services.frameClock.isRunning ? 1 : 0,
      'view_w': WidgetsBinding
          .instance
          .platformDispatcher
          .views
          .first
          .physicalSize
          .width,
    });
    lastTicks = t;
    lastFrames = build.length;
    if (cycle && s % 4 == 0) {
      services.demo.emit(states[++phase % states.length], detail: 'perf cycle');
    }
    if (s % 5 == 0 || s == 1) {
      rss.add({'t_s': s, 'rss': ProcessInfo.currentRss});
      final h = await vm?.memoryUsage();
      if (h != null) heap.add({'t_s': s, ...h});
    }
  }

  double pct(List<double> v, double q) {
    if (v.isEmpty) return 0;
    final s = [...v]..sort();
    return s[math.min(s.length - 1, (s.length * q).floor())];
  }

  final b = build.toList(), r = raster.toList();
  final f = finishS.toList();
  final span = f.isEmpty ? 0.0 : f.last - f.first;
  final report = {
    'config': {
      'identity': identity,
      'fps': fps,
      'quality': quality,
      'layout': layout,
      'cycle': cycle,
      'seconds': seconds,
      'build': 'profile',
    },
    'display_hz': services.frameGovernor.displayHz,
    'window': {
      'width': WidgetsBinding
          .instance
          .platformDispatcher
          .views
          .first
          .physicalSize
          .width,
      'height': WidgetsBinding
          .instance
          .platformDispatcher
          .views
          .first
          .physicalSize
          .height,
      'dpr': WidgetsBinding
          .instance
          .platformDispatcher
          .views
          .first
          .devicePixelRatio,
    },
    'overall': {
      'frames': b.length,
      'span_s': span,
      'fps': span > 0 ? b.length / span : 0,
      'companion_frames': services.frameClock.ticks - ticks0,
      'build_p50': pct(b, 0.5),
      'build_p90': pct(b, 0.9),
      'raster_p50': pct(r, 0.5),
      'raster_p90': pct(r, 0.9),
      'raster_p99': pct(r, 0.99),
      'raster_max': r.isEmpty ? 0 : r.reduce(math.max),
      'over_16ms': [
        for (var i = 0; i < b.length; i++)
          if (math.max(b[i], r[i]) > 16.67) 1,
      ].length,
    },
    'per_second': perSecond,
    'cap_changes': capChanges,
    'lifecycle': lifecycle,
    'rss': rss,
    'heap': heap,
    'vm_service': vm != null,
  };
  lifecycleListener.dispose();
  try {
    File(out)
        .writeAsStringSync(const JsonEncoder.withIndent(' ').convert(report));
  } catch (e) {
    stderr.writeln('report write failed: $e');
  }
  exit(0);
}

/// One companion filling the window: isolates the shader's cost.
class _Large extends StatelessWidget {
  const _Large({required this.services, required this.prefs});
  final LivingServices services;
  final CompanionPreferences prefs;

  @override
  Widget build(BuildContext context) {
    final p = services.companionPrefs;
    final id = p.choice.identity;
    final theme = id == null
        ? UriThemeChoice.obsidianCyan
        : CompanionPreferences.themeFor(p.choice, UriThemeChoice.obsidianCyan);
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: buildUriTheme(resolveUriColors(theme, Brightness.dark)),
      home: EffectsSettingsScope(
        settings: services.effects,
        child: CompanionPreferencesScope(
          preferences: p,
          child: CompanionClockScope(
            clock: services.frameClock,
            child: Scaffold(
              backgroundColor: Colors.black,
              body: LayoutBuilder(
                builder: (context, box) {
                  final side = box.biggest.shortestSide * 0.9;
                  return Center(
                    child: LivingCompanion(
                      state: CompanionState.idle,
                      size: side,
                    ),
                  );
                },
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Minimal client for this process's own VM service: Dart heap figures, so
/// RSS growth can be split into Dart heap and native (engine, driver).
class _VmService {
  _VmService(this._ws, this._isolate);
  final WebSocket _ws;
  final String _isolate;
  int _id = 0;
  final Map<String, Completer<Map<String, dynamic>>> _pending = {};

  static Future<_VmService?> connect() async {
    try {
      var info = await developer.Service.getInfo();
      if (info.serverUri == null) {
        info = await developer.Service.controlWebServer(enable: true);
      }
      final uri = info.serverWebSocketUri;
      if (uri == null) return null;
      final ws = await WebSocket.connect(uri.toString());
      final svc = _VmService(
        ws,
        developer.Service.getIsolateId(Isolate.current)!,
      );
      ws.listen((m) {
        final j = jsonDecode(m as String) as Map<String, dynamic>;
        final c = svc._pending.remove('${j['id']}');
        c?.complete((j['result'] as Map?)?.cast<String, dynamic>() ?? {});
      });
      return svc;
    } catch (_) {
      return null;
    }
  }

  Future<Map<String, num>?> memoryUsage() async {
    try {
      final id = '${++_id}';
      final c = Completer<Map<String, dynamic>>();
      _pending[id] = c;
      _ws.add(
        jsonEncode({
          'jsonrpc': '2.0',
          'id': id,
          'method': 'getMemoryUsage',
          'params': {'isolateId': _isolate},
        }),
      );
      final r = await c.future.timeout(const Duration(seconds: 3));
      return {
        'heap_used': r['heapUsage'] as num? ?? -1,
        'heap_capacity': r['heapCapacity'] as num? ?? -1,
        'external': r['externalUsage'] as num? ?? -1,
      };
    } catch (_) {
      return null;
    }
  }
}
