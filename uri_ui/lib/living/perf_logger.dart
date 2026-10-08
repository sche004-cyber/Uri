import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart';

/// Frame-timing sampler for the performance evidence in
/// `docs/ui_phase/UI_TEST_EVIDENCE.md`.
///
/// Enabled only when the `URI_LIVING_PERF` environment variable is set
/// (see `main_living.dart`); it prints one summary line per window of
/// frames to stdout. Nothing else in the UI reads it; it never renders.
/// Numbers from a debug build are pessimistic; the evidence file says
/// which build mode each sample came from.
class PerfLogger {
  PerfLogger({this.window = const Duration(seconds: 5)});

  final Duration window;
  final List<FrameTiming> _frames = [];
  Timer? _timer;
  bool _installed = false;

  void install() {
    if (_installed) return;
    _installed = true;
    SchedulerBinding.instance.addTimingsCallback(_onTimings);
    _timer = Timer.periodic(window, (_) => _flush());
  }

  void _onTimings(List<FrameTiming> timings) {
    _frames.addAll(timings);
  }

  void _flush() {
    if (_frames.isEmpty) {
      debugPrint('[perf] no frames in the last ${window.inSeconds}s (idle, nothing repainted)');
      return;
    }
    final build = _frames.map((f) => f.buildDuration.inMicroseconds / 1000).toList()..sort();
    final raster = _frames.map((f) => f.rasterDuration.inMicroseconds / 1000).toList()..sort();
    final total = _frames.map((f) => f.totalSpan.inMicroseconds / 1000).toList()..sort();
    double p(List<double> xs, double q) => xs[((xs.length - 1) * q).round()];
    final janky = total.where((t) => t > 16.7).length;
    debugPrint(
      '[perf] frames=${_frames.length} over ${window.inSeconds}s '
      'build p50=${p(build, .5).toStringAsFixed(2)}ms p95=${p(build, .95).toStringAsFixed(2)}ms '
      'raster p50=${p(raster, .5).toStringAsFixed(2)}ms p95=${p(raster, .95).toStringAsFixed(2)}ms '
      'total p95=${p(total, .95).toStringAsFixed(2)}ms >16.7ms=$janky',
    );
    _frames.clear();
  }

  void dispose() {
    _timer?.cancel();
    if (_installed) SchedulerBinding.instance.removeTimingsCallback(_onTimings);
  }
}
