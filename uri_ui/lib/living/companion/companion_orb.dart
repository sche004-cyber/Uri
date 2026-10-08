import 'dart:ui' as ui show FragmentProgram, FragmentShader;

import 'package:flutter/scheduler.dart';
import 'package:flutter/widgets.dart';

import 'companion_state.dart';
import 'effects_settings.dart';

/// Which living companion is active.
///
/// The identity decides three things together, and they are never chosen
/// separately: the shader that draws the companion, the colour palette the
/// rest of the UI adopts, and the vocabulary the expression parameters are
/// written in. Picking "Sakura" is not a recolour of Solar; it is a different
/// program with a different idea of what motion means.
enum CompanionIdentity {
  /// Power and energy. A living star: plasma, magnetic arcs, embers.
  solar,

  /// Grace and life. A luminous spring core in a vortex of cherry petals.
  sakura,

  /// Calm and mystery. A moon with circulating night cloud and moonlight.
  lunar,

  /// Lunar and Sakura together: moonlit petals on a night breeze. Offered
  /// because the owner asked whether the two could be one companion; it is a
  /// separate identity rather than a mode of either.
  moonlit,
}

extension CompanionIdentityInfo on CompanionIdentity {
  String get label => switch (this) {
    CompanionIdentity.solar => 'Solar',
    CompanionIdentity.sakura => 'Sakura',
    CompanionIdentity.lunar => 'Lunar',
    CompanionIdentity.moonlit => 'Moonlit Blossom',
  };

  /// One line for a picker.
  String get tagline => switch (this) {
    CompanionIdentity.solar => 'Power and energy',
    CompanionIdentity.sakura => 'Grace and life',
    CompanionIdentity.lunar => 'Calm and mystery',
    CompanionIdentity.moonlit => 'Moonlight and blossom',
  };

  String get shaderAsset => switch (this) {
    CompanionIdentity.solar => 'shaders/companion_solar.frag',
    CompanionIdentity.sakura => 'shaders/companion_sakura.frag',
    CompanionIdentity.lunar => 'shaders/companion_lunar.frag',
    CompanionIdentity.moonlit => 'shaders/companion_moonlit.frag',
  };

  /// How much of the shorter side the companion body occupies. The rest is
  /// deliberately left for the corona, the petals or the cloud, which is the
  /// whole point: a companion that stops at its own silhouette is a sticker.
  double get bodyRadius => switch (this) {
    CompanionIdentity.solar => 0.38,
    CompanionIdentity.sakura => 0.30,
    CompanionIdentity.lunar => 0.33,
    CompanionIdentity.moonlit => 0.32,
  };
}

/// The six expression parameters, in the uniform order the shaders declare.
///
/// The names are shared across every identity; the meanings are not. Each
/// shader documents its own reading in its generated header, and the mapping
/// is summarised on [CompanionParams.forState].
@immutable
class CompanionParams {
  const CompanionParams({
    required this.energy,
    required this.turbulence,
    required this.flare,
    required this.particles,
    required this.focus,
    required this.exposure,
  });

  /// Overall activity. Every identity reads this the same way.
  final double energy;

  /// Chaos in the flow.
  final double turbulence;

  /// Solar: prominence activity. Sakura: energy ribbons. Lunar: halo and
  /// light shafts.
  final double flare;

  /// Solar: embers. Sakura: petals and pollen. Lunar: stars and mist.
  final double particles;

  /// How ordered the motion reads. Solar: arc coherence. Sakura: how tightly
  /// the petals hold their arms. Lunar: how far the cloud parts, so a low
  /// value obscures the moon.
  final double focus;

  /// HDR exposure applied before the filmic tonemap.
  final double exposure;

  CompanionParams lerpTo(CompanionParams other, double t) {
    double m(double a, double b) => a + (b - a) * t;
    return CompanionParams(
      energy: m(energy, other.energy),
      turbulence: m(turbulence, other.turbulence),
      flare: m(flare, other.flare),
      particles: m(particles, other.particles),
      focus: m(focus, other.focus),
      exposure: m(exposure, other.exposure),
    );
  }

  @override
  bool operator ==(Object other) =>
      other is CompanionParams &&
      other.energy == energy &&
      other.turbulence == turbulence &&
      other.flare == flare &&
      other.particles == particles &&
      other.focus == focus &&
      other.exposure == exposure;

  @override
  int get hashCode =>
      Object.hash(energy, turbulence, flare, particles, focus, exposure);

  /// The parameter table for one identity, covering every [CompanionState].
  ///
  /// It covers all nine, not the five in the visual brief: `CompanionState` is
  /// an existing contract driven by authoritative facts, and a companion that
  /// cannot express `awaitingApproval` or `unavailable` would silently fall
  /// back to some other state's appearance and misreport what URI is doing.
  static CompanionParams of(CompanionIdentity id, CompanionState state) =>
      _tables[id]![state]!;

  static const Map<CompanionIdentity, Map<CompanionState, CompanionParams>>
  _tables = <CompanionIdentity, Map<CompanionState, CompanionParams>>{
    CompanionIdentity.solar: _solar,
    CompanionIdentity.sakura: _sakura,
    CompanionIdentity.lunar: _lunar,
    // The hybrid is a lunar scene carrying petals, so it reads the lunar
    // table. Its own shader interprets `particles` as petals as well as mist.
    CompanionIdentity.moonlit: _lunar,
  };

  static const Map<CompanionState, CompanionParams> _solar =
      <CompanionState, CompanionParams>{
        CompanionState.unavailable: CompanionParams(
          energy: 0.06, turbulence: 0.05, flare: 0.00,
          particles: 0.05, focus: 0.95, exposure: 0.72,
        ),
        CompanionState.idle: CompanionParams(
          energy: 0.22, turbulence: 0.16, flare: 0.10,
          particles: 0.28, focus: 0.85, exposure: 1.00,
        ),
        CompanionState.listening: CompanionParams(
          energy: 0.36, turbulence: 0.14, flare: 0.14,
          particles: 0.44, focus: 0.95, exposure: 1.08,
        ),
        CompanionState.thinking: CompanionParams(
          energy: 0.62, turbulence: 0.48, flare: 0.30,
          particles: 0.52, focus: 0.70, exposure: 1.06,
        ),
        CompanionState.speaking: CompanionParams(
          energy: 0.74, turbulence: 0.34, flare: 0.62,
          particles: 0.60, focus: 0.88, exposure: 1.10,
        ),
        CompanionState.working: CompanionParams(
          energy: 1.00, turbulence: 0.74, flare: 0.92,
          particles: 1.00, focus: 0.55, exposure: 1.16,
        ),
        CompanionState.awaitingApproval: CompanionParams(
          energy: 0.44, turbulence: 0.10, flare: 0.20,
          particles: 0.34, focus: 1.00, exposure: 1.04,
        ),
        CompanionState.success: CompanionParams(
          energy: 0.86, turbulence: 0.22, flare: 1.00,
          particles: 0.86, focus: 0.98, exposure: 1.22,
        ),
        CompanionState.error: CompanionParams(
          energy: 0.58, turbulence: 0.95, flare: 0.44,
          particles: 0.42, focus: 0.22, exposure: 0.92,
        ),
      };

  static const Map<CompanionState, CompanionParams> _sakura =
      <CompanionState, CompanionParams>{
        CompanionState.unavailable: CompanionParams(
          energy: 0.06, turbulence: 0.05, flare: 0.00,
          particles: 0.06, focus: 0.95, exposure: 0.74,
        ),
        CompanionState.idle: CompanionParams(
          energy: 0.24, turbulence: 0.18, flare: 0.10,
          particles: 0.34, focus: 0.80, exposure: 1.00,
        ),
        CompanionState.listening: CompanionParams(
          energy: 0.38, turbulence: 0.12, flare: 0.16,
          particles: 0.46, focus: 0.96, exposure: 1.06,
        ),
        CompanionState.thinking: CompanionParams(
          energy: 0.60, turbulence: 0.42, flare: 0.34,
          particles: 0.62, focus: 0.72, exposure: 1.05,
        ),
        CompanionState.speaking: CompanionParams(
          energy: 0.72, turbulence: 0.28, flare: 0.58,
          particles: 0.58, focus: 0.90, exposure: 1.08,
        ),
        CompanionState.working: CompanionParams(
          energy: 0.95, turbulence: 0.66, flare: 0.86,
          particles: 1.00, focus: 0.58, exposure: 1.14,
        ),
        CompanionState.awaitingApproval: CompanionParams(
          energy: 0.44, turbulence: 0.10, flare: 0.22,
          particles: 0.38, focus: 1.00, exposure: 1.03,
        ),
        CompanionState.success: CompanionParams(
          energy: 0.88, turbulence: 0.20, flare: 1.00,
          particles: 0.95, focus: 0.96, exposure: 1.20,
        ),
        CompanionState.error: CompanionParams(
          energy: 0.55, turbulence: 0.92, flare: 0.40,
          particles: 0.40, focus: 0.20, exposure: 0.90,
        ),
      };

  static const Map<CompanionState, CompanionParams> _lunar =
      <CompanionState, CompanionParams>{
        CompanionState.unavailable: CompanionParams(
          energy: 0.05, turbulence: 0.10, flare: 0.00,
          particles: 0.06, focus: 0.30, exposure: 0.70,
        ),
        CompanionState.idle: CompanionParams(
          energy: 0.22, turbulence: 0.24, flare: 0.12,
          particles: 0.30, focus: 0.55, exposure: 1.00,
        ),
        CompanionState.listening: CompanionParams(
          energy: 0.32, turbulence: 0.16, flare: 0.18,
          particles: 0.34, focus: 0.88, exposure: 1.05,
        ),
        CompanionState.thinking: CompanionParams(
          energy: 0.55, turbulence: 0.52, flare: 0.26,
          particles: 0.42, focus: 0.45, exposure: 1.02,
        ),
        CompanionState.speaking: CompanionParams(
          energy: 0.62, turbulence: 0.26, flare: 0.60,
          particles: 0.40, focus: 0.70, exposure: 1.08,
        ),
        CompanionState.working: CompanionParams(
          energy: 0.92, turbulence: 0.70, flare: 0.80,
          particles: 0.60, focus: 0.40, exposure: 1.12,
        ),
        CompanionState.awaitingApproval: CompanionParams(
          energy: 0.40, turbulence: 0.14, flare: 0.22,
          particles: 0.32, focus: 0.92, exposure: 1.04,
        ),
        CompanionState.success: CompanionParams(
          energy: 0.72, turbulence: 0.12, flare: 0.75,
          particles: 0.45, focus: 1.00, exposure: 1.16,
        ),
        CompanionState.error: CompanionParams(
          energy: 0.50, turbulence: 0.88, flare: 0.30,
          particles: 0.30, focus: 0.12, exposure: 0.88,
        ),
      };
}

/// Loads a companion shader once per identity and never throws.
///
/// The companion must render with or without a shader (reduced effects, a
/// platform without runtime-shader support, a missing asset in a test
/// harness), so a failed load degrades to `null` and the caller draws a static
/// fallback instead of taking the app down.
class CompanionShaderCache {
  CompanionShaderCache._();

  static final Map<CompanionIdentity, Future<ui.FragmentProgram?>> _loading =
      <CompanionIdentity, Future<ui.FragmentProgram?>>{};
  static final Map<CompanionIdentity, ui.FragmentProgram> _programs =
      <CompanionIdentity, ui.FragmentProgram>{};
  static final Map<CompanionIdentity, String> _failures =
      <CompanionIdentity, String>{};

  static ui.FragmentProgram? programIfLoaded(CompanionIdentity id) =>
      _programs[id];

  static String? failureFor(CompanionIdentity id) => _failures[id];

  @visibleForTesting
  static void reset() {
    _loading.clear();
    _programs.clear();
    _failures.clear();
  }

  static Future<ui.FragmentProgram?> load(CompanionIdentity id) =>
      _loading[id] ??= _doLoad(id);

  static Future<ui.FragmentProgram?> _doLoad(CompanionIdentity id) async {
    try {
      final program = await ui.FragmentProgram.fromAsset(id.shaderAsset);
      _programs[id] = program;
      _failures.remove(id);
      return program;
    } catch (error) {
      _programs.remove(id);
      _failures[id] = error.toString();
      return null;
    }
  }
}

/// One deterministic frame of a companion.
///
/// Owns no animation: the same inputs produce the same pixels. [CompanionOrb]
/// drives it from a ticker; the capture harness and the widget tests drive it
/// from constants, which is the only way to get a reproducible image out of a
/// continuously moving effect.
class CompanionOrbFrame extends StatefulWidget {
  const CompanionOrbFrame({
    super.key,
    required this.identity,
    required this.params,
    required this.seconds,
    this.radius,
    this.fallback,
  });

  final CompanionIdentity identity;
  final CompanionParams params;
  final double seconds;

  /// Defaults to the identity's own body radius.
  final double? radius;

  /// Drawn instead of the shader when the program is unavailable.
  final Widget? fallback;

  @override
  State<CompanionOrbFrame> createState() => _CompanionOrbFrameState();
}

class _CompanionOrbFrameState extends State<CompanionOrbFrame> {
  ui.FragmentShader? _shader;
  CompanionIdentity? _shaderFor;

  @override
  void initState() {
    super.initState();
    _ensureShader();
  }

  @override
  void didUpdateWidget(CompanionOrbFrame old) {
    super.didUpdateWidget(old);
    if (old.identity != widget.identity) _ensureShader();
  }

  void _ensureShader() {
    final id = widget.identity;
    final loaded = CompanionShaderCache.programIfLoaded(id);
    if (loaded != null) {
      _swap(loaded.fragmentShader(), id);
      return;
    }
    CompanionShaderCache.load(id).then((program) {
      if (!mounted || program == null || widget.identity != id) return;
      setState(() => _swap(program.fragmentShader(), id));
    });
  }

  void _swap(ui.FragmentShader next, CompanionIdentity id) {
    _shader?.dispose();
    _shader = next;
    _shaderFor = id;
  }

  @override
  void dispose() {
    _shader?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final shader = _shader;
    if (shader == null || _shaderFor != widget.identity) {
      return widget.fallback ?? const SizedBox.expand();
    }
    return CustomPaint(
      size: Size.infinite,
      painter: CompanionOrbPainter(
        shader: shader,
        seconds: widget.seconds,
        params: widget.params,
        radius: widget.radius ?? widget.identity.bodyRadius,
      ),
    );
  }
}

/// A living companion that expresses [state] and settles between states
/// without a cut.
class CompanionOrb extends StatefulWidget {
  const CompanionOrb({
    super.key,
    required this.identity,
    this.state = CompanionState.idle,
    this.radius,
    this.transition = const Duration(milliseconds: 900),
    this.fallback,
  });

  final CompanionIdentity identity;
  final CompanionState state;
  final double? radius;

  /// How long the companion takes to settle into a new state.
  final Duration transition;

  final Widget? fallback;

  @override
  State<CompanionOrb> createState() => _CompanionOrbState();
}

class _CompanionOrbState extends State<CompanionOrb>
    with SingleTickerProviderStateMixin {
  late final Ticker _ticker;

  double _seconds = 0;
  late CompanionParams _current;
  late CompanionParams _from;
  late CompanionParams _target;
  double _blend = 1;
  Duration _lastTick = Duration.zero;

  @override
  void initState() {
    super.initState();
    _from = _target = _current = CompanionParams.of(
      widget.identity,
      widget.state,
    );
    _ticker = createTicker(_onTick)..start();
  }

  @override
  void didUpdateWidget(CompanionOrb old) {
    super.didUpdateWidget(old);
    if (old.state != widget.state || old.identity != widget.identity) {
      // Blend from where the companion actually is, not from the old state's
      // table entry: switching identity mid-transition must not snap.
      _from = _current;
      _target = CompanionParams.of(widget.identity, widget.state);
      _blend = 0;
    }
  }

  void _onTick(Duration elapsed) {
    final dt = (elapsed - _lastTick).inMicroseconds / 1e6;
    _lastTick = elapsed;
    final transition = widget.transition.inMicroseconds / 1e6;
    setState(() {
      _seconds = elapsed.inMicroseconds / 1e6;
      if (_blend < 1) {
        // Advance by real elapsed time rather than an assumed 1/60, so the
        // transition lasts the same wall-clock duration at any frame rate.
        _blend = transition <= 0 ? 1 : (_blend + dt / transition).clamp(0.0, 1.0);
      }
      final t = Curves.easeInOutCubic.transform(_blend);
      _current = _from.lerpTo(_target, t);
    });
  }

  @override
  void dispose() {
    _ticker.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final effects = EffectsSettings.of(context);
    // Reduced motion freezes the clock at a representative moment instead of
    // stopping the widget: the state must still be readable, it just must not
    // move. Reduced effects drops the shader entirely.
    final seconds = effects.reducedMotion ? 7.0 : _seconds;
    if (effects.reducedEffects) {
      return widget.fallback ?? const SizedBox.expand();
    }
    return CompanionOrbFrame(
      identity: widget.identity,
      params: _current,
      seconds: seconds,
      radius: widget.radius,
      fallback: widget.fallback,
    );
  }
}

class CompanionOrbPainter extends CustomPainter {
  CompanionOrbPainter({
    required this.shader,
    required this.seconds,
    required this.params,
    required this.radius,
  });

  final ui.FragmentShader shader;
  final double seconds;
  final CompanionParams params;
  final double radius;

  /// The uniform vector, in the order the generated `.frag` headers declare.
  ///
  /// Built as a list rather than written straight into the shader so the order
  /// can be asserted in a test: a silently reordered uniform is invisible in
  /// code review and produces a plausible-looking but wrong image.
  static List<double> uniformsFor({
    required Size size,
    required double seconds,
    required CompanionParams params,
    required double radius,
  }) => <double>[
    size.width,
    size.height,
    seconds,
    params.energy,
    params.turbulence,
    params.flare,
    params.particles,
    params.focus,
    radius,
    params.exposure,
  ];

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final values = uniformsFor(
      size: size,
      seconds: seconds,
      params: params,
      radius: radius,
    );
    for (var i = 0; i < values.length; i++) {
      shader.setFloat(i, values[i]);
    }
    canvas.drawRect(Offset.zero & size, Paint()..shader = shader);
  }

  @override
  bool shouldRepaint(CompanionOrbPainter old) =>
      old.seconds != seconds ||
      old.radius != radius ||
      old.params != params ||
      !identical(old.shader, shader);
}
