import 'dart:async';
import 'dart:math' as math;
import 'dart:ui' show FramePhase, FrameTiming;

import 'package:flutter/scheduler.dart';
import 'package:flutter/widgets.dart';

import 'companion_preferences.dart';
import 'fine_timer.dart';

/// The one clock every living animation runs on: the companion and the voice
/// waveform.
///
/// Why one clock. Flutter rasterises the whole scene for every frame that is
/// produced, and Impeller keeps no raster cache, so a widget that merely skips
/// `setState` on some vsyncs saves nothing: its ticker still produces the
/// frame and the shader runs again. A rate cap is only real if frames are not
/// *scheduled*. This clock mutes its ticker between paints and wakes it with a
/// timer just before the next one is due, so at a 60 FPS cap on a 144 Hz panel
/// the app produces about 60 frames a second, not 144.
///
/// It starts when the first animation listens and stops when the last one
/// leaves, and Flutter itself stops frames while the window is hidden, so a
/// hidden or unmounted companion costs nothing.
class CompanionFrameClock extends ChangeNotifier {
  CompanionFrameClock({this.displayHz = 60, double? cap}) : _cap = cap ?? 0 {
    _ticker = Ticker(_onTick, debugLabel: 'companion-frame-clock');
  }

  late final Ticker _ticker;

  /// The display's refresh rate, reported by the engine.
  double displayHz;

  double _cap;

  /// Frames per second the clock delivers; 0 or anything at or above the
  /// display rate means every vsync.
  double get cap => _cap;
  set cap(double fps) {
    if (fps == _cap) return;
    _cap = fps;
    _due = _seconds; // apply at once rather than after the old interval
    _wakeNow();
  }

  bool get pacing => _cap > 0 && _cap < displayHz - 0.5;

  double _seconds = 0;
  double _offset = 0;
  double _due = 0;
  Timer? _wake;
  bool _fineTimer = false;

  /// Seconds since the clock was created, continuous across stops.
  double get seconds => _seconds;

  /// Whether the clock is running (something is animating on it).
  bool get isRunning => _ticker.isActive;

  /// Deliveries in the current one-second window, and the last full window.
  int _windowCount = 0;
  double _windowStart = 0;
  double _deliveredFps = 0;
  double get deliveredFps => _deliveredFps;

  @override
  void addListener(VoidCallback listener) {
    super.addListener(listener);
    if (!_ticker.isActive) {
      _offset = _seconds;
      _due = _seconds;
      _ticker.start();
    }
  }

  @override
  void removeListener(VoidCallback listener) {
    super.removeListener(listener);
    if (!hasListeners) _stop();
  }

  void _stop() {
    _wake?.cancel();
    _wake = null;
    if (_ticker.isActive) _ticker.stop();
    _ticker.muted = false;
    _setFineTimer(false);
  }

  void _wakeNow() {
    _wake?.cancel();
    _wake = null;
    if (_ticker.isActive) _ticker.muted = false;
  }

  /// Vsync callbacks received (delivered or not); with pacing working, every
  /// tick is a delivery and no frame is requested in between.
  int get ticks => _ticks;
  int _ticks = 0;

  void _onTick(Duration elapsed) {
    _ticks++;
    final t = _offset + elapsed.inMicroseconds / 1e6;
    _seconds = t;
    if (!pacing) {
      _setFineTimer(false);
      _deliver(t);
      return;
    }
    final vsync = 1 / displayHz;
    final period = 1 / _cap;
    // Deliver on the first vsync at or after one frame before the due time:
    // the wake-up below lands within that frame, so no frame is wasted.
    if (t >= _due - vsync) {
      _due += period;
      // Fell behind (a long frame, a stall): restart the schedule from now
      // instead of delivering a burst to catch up.
      if (_due < t) _due = t + period;
      _deliver(t);
      if (!_ticker.isActive) return; // the last listener left
    }
    final wait = _due - t - 0.9 * vsync;
    if (wait > 0.0015) {
      _setFineTimer(true);
      _ticker.muted = true;
      _wake?.cancel();
      _wake = Timer(Duration(microseconds: (wait * 1e6).round()), () {
        _wake = null;
        if (_ticker.isActive) _ticker.muted = false;
      });
    }
  }

  void _deliver(double t) {
    _windowCount++;
    if (t - _windowStart >= 1) {
      _deliveredFps = _windowCount / (t - _windowStart);
      _windowCount = 0;
      _windowStart = t;
    }
    notifyListeners();
    // A listener that left during the notification (a companion that has
    // gone still) is only dropped once notification ends, so removeListener
    // could not see the clock become idle. Check again now.
    if (!hasListeners) _stop();
  }

  /// Windows timers tick at 15.6 ms by default, which would turn a 60 FPS cap
  /// into about 50. While the clock is pacing it asks for 1 ms resolution
  /// (process-local on Windows 10 2004 and later) and releases it when not.
  void _setFineTimer(bool on) {
    if (on == _fineTimer) return;
    _fineTimer = on;
    FineTimer.request(on);
  }

  @override
  void dispose() {
    _stop();
    _ticker.dispose();
    super.dispose();
  }

  static CompanionFrameClock? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<CompanionClockScope>()?.clock;
}

class CompanionClockScope extends InheritedWidget {
  const CompanionClockScope({
    super.key,
    required this.clock,
    required super.child,
  });

  final CompanionFrameClock clock;

  @override
  bool updateShouldNotify(CompanionClockScope old) => old.clock != clock;
}

/// Drives a living animation from the shared [CompanionFrameClock] when one is
/// installed, and from its own ticker otherwise (a bare widget in a test, the
/// capture harness). Either way the state receives `(seconds, dt)`.
mixin CompanionFrameDriver<T extends StatefulWidget>
    on SingleTickerProviderStateMixin<T> {
  CompanionFrameClock? _clock;
  Ticker? _own;
  bool _listening = false;
  bool _enabled = true;
  bool _paused = false;
  double _last = -1;

  void onCompanionFrame(double seconds, double dt);

  /// Whether the animation needs another frame. A state returns false when
  /// nothing on screen would change (reduced motion with every transition
  /// finished); the driver then stops listening, so a still companion
  /// schedules no frames at all, until [resumeFrames] or a dependency change.
  bool get wantsFrames => true;

  /// Restarts frames after [wantsFrames] paused them (a new state, a new
  /// identity, a preference change).
  void resumeFrames() {
    if (!_paused || !mounted) return;
    _paused = false;
    _bind(_clock, _enabled);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _paused = false; // e.g. reduced motion switched off
    _bind(
      CompanionFrameClock.maybeOf(context),
      TickerMode.valuesOf(context).enabled,
    );
  }

  void _pause() {
    _paused = true;
    if (_listening) {
      _clock?.removeListener(_onClock);
      _listening = false;
    }
    if (_own?.isActive ?? false) _own!.stop();
  }

  void _bind(CompanionFrameClock? clock, bool enabled) {
    _enabled = enabled;
    if (_paused) return;
    if (_listening && (_clock != clock || !enabled)) {
      _clock!.removeListener(_onClock);
      _listening = false;
    }
    _clock = clock;
    if (clock != null) {
      if (_own?.isActive ?? false) _own!.stop();
      if (enabled && !_listening) {
        _last = -1;
        clock.addListener(_onClock);
        _listening = true;
      }
    } else {
      _own ??= createTicker((elapsed) {
        final s = elapsed.inMicroseconds / 1e6;
        _emit(s);
      });
      if (!_own!.isActive) {
        _last = -1;
        _own!.start();
      }
    }
  }

  void _onClock() => _emit(_clock!.seconds);

  void _emit(double s) {
    final dt = _last < 0 ? 0.0 : math.max(0.0, s - _last);
    _last = s;
    onCompanionFrame(s, dt);
    if (!wantsFrames) _pause();
  }

  @override
  void dispose() {
    if (_listening) _clock?.removeListener(_onClock);
    _own?.dispose();
    super.dispose();
  }
}

/// Summary of one measurement window of real frames.
@immutable
class FrameWindowStats {
  const FrameWindowStats({
    required this.frames,
    required this.seconds,
    required this.buildP90Ms,
    required this.rasterP90Ms,
    required this.overBudget,
    required this.budgetMs,
  });

  final int frames;
  final double seconds;
  final double buildP90Ms;
  final double rasterP90Ms;

  /// Fraction of frames whose slower pipeline stage took longer than
  /// [budgetMs].
  final double overBudget;
  final double budgetMs;

  double get fps => seconds > 0 ? frames / seconds : 0;
  double get workP90Ms => math.max(buildP90Ms, rasterP90Ms);

  static FrameWindowStats of(
    List<double> buildMs,
    List<double> rasterMs,
    double seconds,
    double budgetMs,
  ) {
    double p90(List<double> v) {
      if (v.isEmpty) return 0;
      final s = [...v]..sort();
      return s[math.min(s.length - 1, (s.length * 0.9).floor())];
    }

    var over = 0;
    for (var i = 0; i < buildMs.length; i++) {
      if (math.max(buildMs[i], rasterMs[i]) > budgetMs) over++;
    }
    return FrameWindowStats(
      frames: buildMs.length,
      seconds: seconds,
      buildP90Ms: p90(buildMs),
      rasterP90Ms: p90(rasterMs),
      overBudget: buildMs.isEmpty ? 0 : over / buildMs.length,
      budgetMs: budgetMs,
    );
  }
}

/// The adaptive rate decision, kept pure so it can be tested exactly.
///
/// Tiers run from the display rate down to 30. A window in which more than 5 %
/// of frames overrun the current interval, or the 90th percentile uses more
/// than 85 % of it, steps down one tier. Stepping up needs [recoverWindows]
/// consecutive calm windows whose 90th percentile would fit comfortably in the
/// faster tier's interval, so a brief lull does not cause oscillation.
class AdaptiveRatePolicy {
  AdaptiveRatePolicy({required double displayHz, this.recoverWindows = 3})
    : tiers = tiersFor(displayHz) {
    _index = 0;
  }

  final List<double> tiers;
  final int recoverWindows;
  late int _index;
  int _calm = 0;

  double get cap => tiers[_index];
  int get tierIndex => _index;

  static List<double> tiersFor(double displayHz) {
    final top = displayHz.clamp(30.0, 144.0).roundToDouble();
    final out = <double>[top];
    for (final t in const <double>[90, 60, 45, 30]) {
      if (t < top - 1) out.add(t);
    }
    return out;
  }

  /// Returns true when the cap changed.
  bool observe(FrameWindowStats w) {
    if (w.frames < 10) return false; // too little to judge
    final budget = 1000 / cap;
    final stressed = w.overBudget > 0.05 || w.workP90Ms > 0.85 * budget;
    if (stressed) {
      _calm = 0;
      if (_index < tiers.length - 1) {
        _index++;
        return true;
      }
      return false;
    }
    if (_index == 0) return false;
    final faster = 1000 / tiers[_index - 1];
    if (w.overBudget < 0.01 && w.workP90Ms < 0.5 * faster) {
      _calm++;
      if (_calm >= recoverWindows) {
        _calm = 0;
        _index--;
        return true;
      }
    } else {
      _calm = 0;
    }
    return false;
  }
}

/// Connects the user's frame-rate preference, the display and measured frame
/// timings to the clock, and keeps the numbers the statistics overlay shows.
class CompanionFrameGovernor extends ChangeNotifier {
  CompanionFrameGovernor({
    required this.clock,
    required this.preferences,
    this.windowSeconds = 2,
  }) {
    preferences.addListener(_applyPreference);
    _applyPreference();
  }

  final CompanionFrameClock clock;
  final CompanionPreferences preferences;
  final double windowSeconds;

  AdaptiveRatePolicy? _policy;
  FrameWindowStats? _last;
  final List<double> _build = <double>[];
  final List<double> _raster = <double>[];
  double _windowStartUs = -1;
  bool _installed = false;

  FrameWindowStats? get lastWindow => _last;
  FrameRateMode get mode => preferences.frameRate;
  double get displayHz => clock.displayHz;

  /// The rate actually requested of the clock (the display rate when
  /// uncapped).
  double get effectiveCap => clock.cap > 0 ? clock.cap : clock.displayHz;

  /// Starts listening to the engine's frame timings. Separate from the
  /// constructor so widget tests can drive [observeTimings] by hand.
  void install() {
    if (_installed) return;
    _installed = true;
    SchedulerBinding.instance.addTimingsCallback(_onTimings);
  }

  void updateDisplay(double hz) {
    if (!hz.isFinite || hz < 20 || (hz - clock.displayHz).abs() < 0.5) return;
    clock.displayHz = hz;
    _policy = null;
    _applyPreference();
  }

  void _applyPreference() {
    final fixed = preferences.frameRate.fixedFps;
    if (fixed != null) {
      _policy = null;
      clock.cap = math.min(fixed, clock.displayHz);
    } else {
      _policy ??= AdaptiveRatePolicy(displayHz: clock.displayHz);
      clock.cap = _policy!.cap;
    }
    notifyListeners();
  }

  void _onTimings(List<FrameTiming> timings) {
    observeTimings([
      for (final t in timings)
        (
          t.buildDuration.inMicroseconds / 1000,
          t.rasterDuration.inMicroseconds / 1000,
          t.timestampInMicroseconds(FramePhase.rasterFinish),
        ),
    ]);
  }

  /// `(buildMs, rasterMs, rasterFinishMicros)` per frame.
  @visibleForTesting
  void observeTimings(List<(double, double, int)> frames) {
    for (final (b, r, at) in frames) {
      if (_windowStartUs < 0) _windowStartUs = at.toDouble();
      _build.add(b);
      _raster.add(r);
      final span = (at - _windowStartUs) / 1e6;
      if (span >= windowSeconds) {
        final stats = FrameWindowStats.of(
          _build,
          _raster,
          span,
          1000 / effectiveCap,
        );
        _build.clear();
        _raster.clear();
        _windowStartUs = at.toDouble();
        _last = stats;
        final p = _policy;
        if (p != null && p.observe(stats)) clock.cap = p.cap;
        notifyListeners();
      }
    }
  }

  @override
  void dispose() {
    preferences.removeListener(_applyPreference);
    if (_installed) SchedulerBinding.instance.removeTimingsCallback(_onTimings);
    super.dispose();
  }
}
