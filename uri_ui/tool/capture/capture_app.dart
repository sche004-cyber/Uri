// Offscreen capture harness for the living companions.
//
// Runs as a real Windows desktop Flutter app, so the frames it writes come
// from the same engine, the same Impeller backend and the same
// `FragmentShader` path the product uses. A widget test would not prove that:
// the test binding does not load runtime shader assets, so a green widget test
// says nothing about whether the companion renders.
//
// Usage:
//   flutter run -d windows -t tool/capture/capture_app.dart \
//     --dart-define=OUT=<dir> [--dart-define=ONLY=solar,sakura]
//
// It renders a matrix of (identity, state, time) into a RepaintBoundary, reads
// each one back with `toImage`, writes a PNG, and exits.
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/widgets.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_state.dart';

const String outDir = String.fromEnvironment('OUT', defaultValue: 'captures');
const String only = String.fromEnvironment('ONLY', defaultValue: '');

/// Size of every captured frame, in logical pixels.
const Size frameSize = Size(480, 480);

/// Every state the companion contract can report.
const List<CompanionState> allStates = CompanionState.values;

/// Times chosen to be mutually incommensurate, so no two frames land on the
/// same phase of any of the shaders' periods.
const List<double> stateTimes = <double>[
  3.0, 11.0, 17.0, 23.0, 31.0, 43.0, 53.0, 61.0, 71.0,
];

/// Temporal-stability probes: one state, times far apart. If the motion loops,
/// drifts to a fixed point, or accumulates shear, these show it.
const List<double> stabilityTimes = <double>[90.0, 240.0, 900.0, 3600.0];

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final boundaryKey = GlobalKey();
  final controller = _CaptureController();

  runApp(
    Directionality(
      textDirection: TextDirection.ltr,
      child: Center(
        child: RepaintBoundary(
          key: boundaryKey,
          child: SizedBox(
            width: frameSize.width,
            height: frameSize.height,
            child: ColoredBox(
              // Deliberately not pure black: the shaders output premultiplied
              // alpha, so a frame captured on black cannot show whether the
              // compositing is right. This is the darkest companion canvas.
              color: const Color(0xFF070912),
              child: _CaptureHost(controller: controller),
            ),
          ),
        ),
      ),
    ),
  );

  await controller.run(boundaryKey);
  exit(0);
}

class _CaptureController extends ChangeNotifier {
  CompanionIdentity identity = CompanionIdentity.solar;
  CompanionParams params = CompanionParams.of(
    CompanionIdentity.solar,
    CompanionState.idle,
  );
  double time = 0;

  void set(CompanionIdentity id, CompanionParams p, double t) {
    identity = id;
    params = p;
    time = t;
    notifyListeners();
  }

  Future<void> run(GlobalKey boundaryKey) async {
    final dir = Directory(outDir);
    if (!dir.existsSync()) dir.createSync(recursive: true);

    final wanted = only.isEmpty
        ? CompanionIdentity.values
        : CompanionIdentity.values
              .where((i) => only.split(',').contains(i.name))
              .toList();

    var written = 0;
    var failed = 0;

    for (final id in wanted) {
      await CompanionShaderCache.load(id);
      final failure = CompanionShaderCache.failureFor(id);
      if (failure != null) {
        stderr.writeln('SHADER_LOAD_FAILED ${id.name}: $failure');
        failed++;
        continue;
      }
      stdout.writeln('SHADER_LOADED ${id.name}: ${id.shaderAsset}');

      for (var i = 0; i < allStates.length; i++) {
        final state = allStates[i];
        set(id, CompanionParams.of(id, state), stateTimes[i]);
        if (await _shoot(boundaryKey, '${id.name}_${state.name}')) {
          written++;
        } else {
          failed++;
        }
      }
      for (final t in stabilityTimes) {
        set(id, CompanionParams.of(id, CompanionState.working), t);
        final tag = t.toInt().toString().padLeft(4, '0');
        if (await _shoot(boundaryKey, '${id.name}_working_t$tag')) {
          written++;
        } else {
          failed++;
        }
      }
    }
    stdout.writeln('CAPTURE_DONE written=$written failed=$failed');
  }

  Future<bool> _shoot(GlobalKey key, String name) async {
    // Three frames: an identity swap allocates a new shader asynchronously, so
    // one frame is not always enough for the boundary to hold the new uniforms.
    await _nextFrame();
    await _nextFrame();
    await _nextFrame();
    final bytes = await _grab(key);
    if (bytes == null) {
      stderr.writeln('CAPTURE_FAILED: $name');
      return false;
    }
    File('$outDir/$name.png').writeAsBytesSync(bytes);
    stdout.writeln('CAPTURED: $name.png ${bytes.length}');
    return true;
  }

  Future<void> _nextFrame() {
    final binding = WidgetsBinding.instance;
    binding.scheduleFrame();
    return binding.endOfFrame;
  }

  Future<Uint8List?> _grab(GlobalKey key) async {
    final object = key.currentContext?.findRenderObject();
    if (object is! RenderRepaintBoundary) return null;
    final image = await object.toImage(pixelRatio: 2.0);
    final data = await image.toByteData(format: ui.ImageByteFormat.png);
    image.dispose();
    return data?.buffer.asUint8List();
  }
}

class _CaptureHost extends StatefulWidget {
  const _CaptureHost({required this.controller});
  final _CaptureController controller;

  @override
  State<_CaptureHost> createState() => _CaptureHostState();
}

class _CaptureHostState extends State<_CaptureHost> {
  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onChange);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onChange);
    super.dispose();
  }

  void _onChange() => setState(() {});

  @override
  Widget build(BuildContext context) {
    return CompanionOrbFrame(
      identity: widget.controller.identity,
      params: widget.controller.params,
      seconds: widget.controller.time,
    );
  }
}
