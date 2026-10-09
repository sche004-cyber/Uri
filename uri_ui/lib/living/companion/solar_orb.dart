import 'dart:ui' as ui show FragmentProgram, FragmentShader;

import 'package:flutter/scheduler.dart';
import 'package:flutter/widgets.dart';

/// Expressive states the solar orb can occupy.
///
/// These are the orb's posture, not its content: the same shader renders all of
/// them, and every state is a point in the same parameter space, so the orb can
/// move between any two without a cut.
enum SolarOrbState { idle, listening, thinking, speaking, acting }

/// The shader parameters for one state.
///
/// Field order here is the uniform order in `shaders/orb_solar.frag`; the two
/// must be changed together.
@immutable
class SolarOrbParams {
  const SolarOrbParams({
    required this.energy,
    required this.turbulence,
    required this.flare,
    required this.ember,
    required this.focus,
    required this.exposure,
  });

  /// Overall activity. Drives motion rate, brightness and how far the limb
  /// erupts.
  final double energy;

  /// Chaos in the surface flow.
  final double turbulence;

  /// Magnetic loop (prominence) activity.
  final double flare;

  /// Density of the drifting ember field.
  final double ember;

  /// How coherent the motion reads. Low focus thickens and loosens the arcs.
  final double focus;

  /// HDR exposure applied before the filmic tonemap.
  final double exposure;

  static const Map<SolarOrbState, SolarOrbParams> forState =
      <SolarOrbState, SolarOrbParams>{
    SolarOrbState.idle: SolarOrbParams(
      energy: 0.22, turbulence: 0.16, flare: 0.10,
      ember: 0.28, focus: 0.85, exposure: 1.00,
    ),
    SolarOrbState.listening: SolarOrbParams(
      energy: 0.36, turbulence: 0.14, flare: 0.14,
      ember: 0.44, focus: 0.95, exposure: 1.08,
    ),
    SolarOrbState.thinking: SolarOrbParams(
      energy: 0.62, turbulence: 0.48, flare: 0.30,
      ember: 0.52, focus: 0.70, exposure: 1.06,
    ),
    SolarOrbState.speaking: SolarOrbParams(
      energy: 0.74, turbulence: 0.34, flare: 0.62,
      ember: 0.60, focus: 0.88, exposure: 1.10,
    ),
    SolarOrbState.acting: SolarOrbParams(
      energy: 1.00, turbulence: 0.74, flare: 0.92,
      ember: 1.00, focus: 0.55, exposure: 1.16,
    ),
  };

  SolarOrbParams lerpTo(SolarOrbParams other, double t) {
    double m(double a, double b) => a + (b - a) * t;
    return SolarOrbParams(
      energy: m(energy, other.energy),
      turbulence: m(turbulence, other.turbulence),
      flare: m(flare, other.flare),
      ember: m(ember, other.ember),
      focus: m(focus, other.focus),
      exposure: m(exposure, other.exposure),
    );
  }
}

/// Loads the solar orb shader once per process and never throws.
///
/// The orb must render with or without the shader (reduced-effects mode, a
/// platform without runtime-shader support, a missing asset in a test harness),
/// so a failed load degrades to `null` and the caller draws a static fallback.
class SolarOrbShaderCache {
  SolarOrbShaderCache._();

  static const String assetKey = 'shaders/orb_solar.frag';

  static Future<ui.FragmentProgram?>? _loading;
  static ui.FragmentProgram? _program;
  static String? _failure;

  static ui.FragmentProgram? get programIfLoaded => _program;
  static String? get lastFailure => _failure;

  @visibleForTesting
  static void reset() {
    _loading = null;
    _program = null;
    _failure = null;
  }

  static Future<ui.FragmentProgram?> load() => _loading ??= _doLoad();

  static Future<ui.FragmentProgram?> _doLoad() async {
    try {
      final program = await ui.FragmentProgram.fromAsset(assetKey);
      _program = program;
      _failure = null;
      return program;
    } catch (error) {
      _program = null;
      _failure = error.toString();
      return null;
    }
  }
}

/// One deterministic frame of the solar orb.
///
/// Takes the parameters and the clock explicitly and owns no animation, so
/// the same pixels come out for the same inputs. [SolarOrb] drives it from a
/// ticker; the capture harness and widget tests drive it from a constant.
class SolarOrbFrame extends StatefulWidget {
  const SolarOrbFrame({
    super.key,
    required this.params,
    required this.seconds,
    this.radius = 0.38,
    this.fallback,
  });

  final SolarOrbParams params;
  final double seconds;
  final double radius;
  final Widget? fallback;

  @override
  State<SolarOrbFrame> createState() => _SolarOrbFrameState();
}

class _SolarOrbFrameState extends State<SolarOrbFrame> {
  ui.FragmentShader? _shader;

  @override
  void initState() {
    super.initState();
    final loaded = SolarOrbShaderCache.programIfLoaded;
    if (loaded != null) {
      _shader = loaded.fragmentShader();
      return;
    }
    SolarOrbShaderCache.load().then((program) {
      if (!mounted || program == null) return;
      setState(() => _shader = program.fragmentShader());
    });
  }

  @override
  void dispose() {
    _shader?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final shader = _shader;
    if (shader == null) {
      return widget.fallback ?? const SizedBox.expand();
    }
    return CustomPaint(
      size: Size.infinite,
      painter: SolarOrbPainter(
        shader: shader,
        seconds: widget.seconds,
        params: widget.params,
        radius: widget.radius,
      ),
    );
  }
}

/// A living solar orb: a star core with magnetic prominences, a structured
/// corona and a drifting ember field.
///
/// The widget sizes itself to its parent. The orb occupies [radius] of the
/// shorter side (0.38 leaves room for the corona, arcs and embers to extend
/// into the surrounding space, which is the point of the effect).
class SolarOrb extends StatefulWidget {
  const SolarOrb({
    super.key,
    this.state = SolarOrbState.idle,
    this.radius = 0.38,
    this.transition = const Duration(milliseconds: 900),
    this.fallback,
  });

  final SolarOrbState state;
  final double radius;

  /// How long the orb takes to settle into a new state.
  final Duration transition;

  /// Drawn instead of the shader when the program is unavailable.
  final Widget? fallback;

  @override
  State<SolarOrb> createState() => _SolarOrbState();
}

class _SolarOrbState extends State<SolarOrb>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker;
  ui.FragmentShader? _shader;

  double _seconds = 0;
  SolarOrbParams _current = SolarOrbParams.forState[SolarOrbState.idle]!;
  SolarOrbParams _from = SolarOrbParams.forState[SolarOrbState.idle]!;
  SolarOrbParams _target = SolarOrbParams.forState[SolarOrbState.idle]!;
  double _blend = 1;

  @override
  void initState() {
    super.initState();
    _from = _target = _current = SolarOrbParams.forState[widget.state]!;
    _ticker = createTicker(_onTick)..start();
    SolarOrbShaderCache.load().then((program) {
      if (!mounted || program == null) return;
      setState(() => _shader = program.fragmentShader());
    });
  }

  @override
  void didUpdateWidget(SolarOrb old) {
    super.didUpdateWidget(old);
    if (old.state != widget.state) {
      _from = _current;
      _target = SolarOrbParams.forState[widget.state]!;
      _blend = 0;
    }
  }

  void _onTick(Duration elapsed) {
    final seconds = elapsed.inMicroseconds / 1e6;
    final transition = widget.transition.inMicroseconds / 1e6;
    setState(() {
      _seconds = seconds;
      if (_blend < 1) {
        _blend = transition <= 0
            ? 1
            : (_blend + (1 / 60) / transition).clamp(0.0, 1.0);
      }
      // Ease so a state change reads as the orb changing posture rather than a
      // value snapping.
      final t = Curves.easeInOutCubic.transform(_blend);
      _current = _from.lerpTo(_target, t);
    });
  }

  @override
  void dispose() {
    _ticker.dispose();
    _shader?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final shader = _shader;
    if (shader == null) {
      return widget.fallback ?? const SizedBox.expand();
    }
    return CustomPaint(
      size: Size.infinite,
      painter: SolarOrbPainter(
        shader: shader,
        seconds: _seconds,
        params: _current,
        radius: widget.radius,
      ),
    );
  }
}

class SolarOrbPainter extends CustomPainter {
  SolarOrbPainter({
    required this.shader,
    required this.seconds,
    required this.params,
    required this.radius,
  });

  final ui.FragmentShader shader;
  final double seconds;
  final SolarOrbParams params;
  final double radius;

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    // Uniform order must match shaders/orb_solar.frag.
    shader
      ..setFloat(0, size.width)
      ..setFloat(1, size.height)
      ..setFloat(2, seconds)
      ..setFloat(3, params.energy)
      ..setFloat(4, params.turbulence)
      ..setFloat(5, params.flare)
      ..setFloat(6, params.ember)
      ..setFloat(7, params.focus)
      ..setFloat(8, radius)
      ..setFloat(9, params.exposure);
    canvas.drawRect(Offset.zero & size, Paint()..shader = shader);
  }

  @override
  bool shouldRepaint(SolarOrbPainter old) =>
      old.seconds != seconds ||
      old.radius != radius ||
      old.params != params ||
      !identical(old.shader, shader);
}
