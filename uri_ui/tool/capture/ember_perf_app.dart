// Real-window performance harness: Ember versus a shader companion.
//
// Runs as a Windows desktop app (same engine and backend as the product),
// shows one companion at the largest Companion-mode size, steps through every
// CompanionState, and records engine FrameTimings plus process RSS. It also
// writes a few frames as PNG so the run can be checked visually.
//
//   flutter run -d windows --profile -t tool/capture/ember_perf_app.dart \
//     --dart-define=OUT=<dir> --dart-define=ID=ember [--dart-define=SECONDS=6]
//
// GPU and VRAM are sampled outside the process by run_ember_perf.ps1 (Windows
// GPU performance counters), because Flutter cannot see them.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/rendering.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/widgets.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/ember_companion.dart';

const String outDir = String.fromEnvironment('OUT', defaultValue: 'ember_perf');
const String idName = String.fromEnvironment('ID', defaultValue: 'ember');
const int secondsPerState = int.fromEnvironment('SECONDS', defaultValue: 6);
const double side = 476; // 320 dp x presence scale x max size preference

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final id = CompanionIdentity.values.byName(idName);
  final state = ValueNotifier<CompanionState>(CompanionState.idle);
  final key = GlobalKey();
  runApp(
    Directionality(
      textDirection: TextDirection.ltr,
      child: ColoredBox(
        color: const Color(0xFF1A1410),
        child: Center(
          child: RepaintBoundary(
            key: key,
            child: SizedBox(
              width: side,
              height: side,
              child: ValueListenableBuilder<CompanionState>(
                valueListenable: state,
                builder: (_, s, _) => CompanionOrb(
                  identity: id,
                  state: s,
                  attention: s == CompanionState.awaitingApproval,
                ),
              ),
            ),
          ),
        ),
      ),
    ),
  );

  final timings = <Map<String, Object>>[];
  var current = CompanionState.idle;
  SchedulerBinding.instance.addTimingsCallback((list) {
    for (final t in list) {
      timings.add({
        'state': current.name,
        'build_ms': t.buildDuration.inMicroseconds / 1000,
        'raster_ms': t.rasterDuration.inMicroseconds / 1000,
        'total_ms': t.totalSpan.inMicroseconds / 1000,
      });
    }
  });

  Directory(outDir).createSync(recursive: true);
  final rss = <Map<String, Object>>[];
  await Future<void>.delayed(const Duration(seconds: 3)); // decode, warm up
  final t0 = DateTime.now();
  for (final s in CompanionState.values) {
    current = s;
    state.value = s;
    final start = DateTime.now();
    var shot = false;
    while (DateTime.now().difference(start).inMilliseconds <
        secondsPerState * 1000) {
      await Future<void>.delayed(const Duration(milliseconds: 500));
      rss.add({
        't': DateTime.now().difference(t0).inMilliseconds / 1000,
        'state': s.name,
        'rss_mb': ProcessInfo.currentRss / 1048576,
      });
      if (!shot && DateTime.now().difference(start).inMilliseconds > 2000) {
        shot = true;
        final boundary =
            key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
        final img = await boundary.toImage();
        final png = await img.toByteData(format: ui.ImageByteFormat.png);
        File('$outDir/${idName}_${s.name}.png')
            .writeAsBytesSync(png!.buffer.asUint8List());
        img.dispose();
      }
    }
  }
  await Future<void>.delayed(const Duration(milliseconds: 500));
  final lib = EmberLibrary.shared;
  File('$outDir/${idName}_perf.json').writeAsStringSync(
    const JsonEncoder.withIndent(' ').convert({
      'identity': idName,
      'side_px': side,
      'seconds_per_state': secondsPerState,
      'frames': timings,
      'rss': rss,
      'ember_resident_bytes': lib.residentBytes,
      'ember_failure': lib.lastFailure,
      'pid': pid,
    }),
  );
  stdout.writeln('EMBER_PERF_DONE $outDir/${idName}_perf.json');
  exit(0);
}
