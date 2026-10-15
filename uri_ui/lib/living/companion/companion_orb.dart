import 'dart:math' as math;
import 'dart:ui' as ui show FragmentProgram, FragmentShader, PictureRecorder;

import 'package:flutter/widgets.dart';

import 'companion_preferences.dart' show CompanionLook;
import 'companion_state.dart';
import 'effects_settings.dart';
import 'ember_companion.dart';
import 'frame_clock.dart';

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

  /// Warmth and character. A small fire spirit with a face, rendered in
  /// Blender (`companion_art/fire/`) and played as sprite clips by
  /// [EmberCompanion]; it has no shader of its own.
  ember,
}

extension CompanionIdentityInfo on CompanionIdentity {
  String get label => switch (this) {
    CompanionIdentity.solar => 'Solar',
    CompanionIdentity.sakura => 'Sakura',
    CompanionIdentity.lunar => 'Lunar',
    CompanionIdentity.moonlit => 'Moonlit Blossom',
    CompanionIdentity.ember => 'Ember',
  };

  /// One line for a picker.
  String get tagline => switch (this) {
    CompanionIdentity.solar => 'Power and energy',
    CompanionIdentity.sakura => 'Grace and life',
    CompanionIdentity.lunar => 'Calm and mystery',
    CompanionIdentity.moonlit => 'Moonlight and blossom',
    CompanionIdentity.ember => 'Warmth and character',
  };

  String get shaderAsset => switch (this) {
    CompanionIdentity.solar => 'shaders/companion_solar.frag',
    CompanionIdentity.sakura => 'shaders/companion_sakura.frag',
    CompanionIdentity.lunar => 'shaders/companion_lunar.frag',
    CompanionIdentity.moonlit => 'shaders/companion_moonlit.frag',
    // Not a shader identity; [CompanionOrb] hands it to [EmberCompanion]
    // before any program is loaded. Kept non-empty so a stray load fails
    // like any missing asset instead of asserting.
    CompanionIdentity.ember => 'shaders/companion_ember.unused',
  };

  /// Whether this identity is drawn by a fragment shader.
  bool get usesShader => this != CompanionIdentity.ember;

  /// How much of the shorter side the companion body occupies. The rest is
  /// deliberately left for the corona, the petals or the cloud, which is the
  /// whole point: a companion that stops at its own silhouette is a sticker.
  double get bodyRadius => switch (this) {
    CompanionIdentity.solar => 0.38,
    CompanionIdentity.sakura => 0.30,
    CompanionIdentity.lunar => 0.33,
    CompanionIdentity.moonlit => 0.32,
    // Half the width of the character's head and flame at its widest.
    CompanionIdentity.ember => 0.42,
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

  /// The approval attention pulse, applied on top of a state's own values.
  ///
  /// [s] is 0..1 through one pulse cycle. It lifts exposure, flare and energy
  /// together by a small amount, so the companion visibly "leans in" without
  /// changing shape, colour or motion vocabulary. The amplitudes are small on
  /// purpose: the pulse is a cue, the label "Needs your approval" is the
  /// message.
  CompanionParams withAttention(double s) {
    final k = s.clamp(0.0, 1.0);
    return CompanionParams(
      energy: (energy + 0.08 * k).clamp(0.0, 1.0),
      turbulence: turbulence,
      flare: (flare + 0.16 * k).clamp(0.0, 1.0),
      particles: particles,
      focus: focus,
      exposure: (exposure + 0.11 * k).clamp(0.5, 1.5),
    );
  }

  /// One attention pulse cycle: a smooth 0..1..0 over [period] seconds.
  static double attentionWave(double seconds, {double period = 2.8}) {
    final x = (seconds / period) % 1.0;
    return 0.5 - 0.5 * math.cos(2 * math.pi * x);
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
  /// It covers all ten, not the five in the visual brief: `CompanionState` is
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
    // Ember plays rendered clips and does not read these parameters; it
    // shares Solar's warm table so any caller that asks still gets a
    // complete, fire-like answer.
    CompanionIdentity.ember: _solar,
  };

  static const Map<CompanionState, CompanionParams> _solar =
      <CompanionState, CompanionParams>{
        CompanionState.unavailable: CompanionParams(
          energy: 0.06, turbulence: 0.05, flare: 0.00,
          particles: 0.05, focus: 0.95, exposure: 0.72,
        ),
        // Initializing: the idle look, calmer and dimmer (owner decision,
        // Ember V2.1 final: a normal startup must not look failed).
        CompanionState.initializing: CompanionParams(
          energy: 0.14, turbulence: 0.10, flare: 0.04,
          particles: 0.16, focus: 0.88, exposure: 0.88,
        ),
        CompanionState.idle: CompanionParams(
          energy: 0.22, turbulence: 0.16, flare: 0.10,
          particles: 0.28, focus: 0.85, exposure: 1.00,
        ),
        CompanionState.listening: CompanionParams(
          energy: 0.15, turbulence: 0.09, flare: 0.05,
          particles: 0.18, focus: 0.95, exposure: 0.97,
        ),
        CompanionState.thinking: CompanionParams(
          energy: 0.30, turbulence: 0.46, flare: 0.04,
          particles: 0.12, focus: 0.97, exposure: 0.84,
        ),
        CompanionState.speaking: CompanionParams(
          energy: 0.40, turbulence: 0.22, flare: 0.28,
          particles: 0.40, focus: 0.92, exposure: 1.02,
        ),
        CompanionState.working: CompanionParams(
          energy: 0.56, turbulence: 0.24, flare: 0.36,
          particles: 0.46, focus: 0.94, exposure: 1.05,
        ),
        CompanionState.awaitingApproval: CompanionParams(
          energy: 0.26, turbulence: 0.10, flare: 0.12,
          particles: 0.24, focus: 0.98, exposure: 1.00,
        ),
        CompanionState.success: CompanionParams(
          energy: 0.70, turbulence: 0.18, flare: 0.70,
          particles: 0.70, focus: 0.98, exposure: 1.12,
        ),
        CompanionState.error: CompanionParams(
          energy: 0.30, turbulence: 0.42, flare: 0.10,
          particles: 0.16, focus: 0.40, exposure: 0.90,
        ),
      };

  static const Map<CompanionState, CompanionParams> _sakura =
      <CompanionState, CompanionParams>{
        CompanionState.unavailable: CompanionParams(
          energy: 0.06, turbulence: 0.05, flare: 0.00,
          particles: 0.06, focus: 0.95, exposure: 0.74,
        ),
        // Initializing: the idle look, calmer and dimmer (owner decision,
        // Ember V2.1 final: a normal startup must not look failed).
        CompanionState.initializing: CompanionParams(
          energy: 0.15, turbulence: 0.11, flare: 0.04,
          particles: 0.20, focus: 0.84, exposure: 0.88,
        ),
        CompanionState.idle: CompanionParams(
          energy: 0.24, turbulence: 0.18, flare: 0.10,
          particles: 0.34, focus: 0.80, exposure: 1.00,
        ),
        CompanionState.listening: CompanionParams(
          energy: 0.16, turbulence: 0.10, flare: 0.05,
          particles: 0.26, focus: 0.94, exposure: 0.98,
        ),
        CompanionState.thinking: CompanionParams(
          energy: 0.30, turbulence: 0.42, flare: 0.05,
          particles: 0.24, focus: 0.97, exposure: 0.85,
        ),
        CompanionState.speaking: CompanionParams(
          energy: 0.42, turbulence: 0.22, flare: 0.28,
          particles: 0.44, focus: 0.90, exposure: 1.02,
        ),
        CompanionState.working: CompanionParams(
          energy: 0.56, turbulence: 0.26, flare: 0.36,
          particles: 0.56, focus: 0.93, exposure: 1.05,
        ),
        CompanionState.awaitingApproval: CompanionParams(
          energy: 0.28, turbulence: 0.10, flare: 0.12,
          particles: 0.32, focus: 0.98, exposure: 1.00,
        ),
        CompanionState.success: CompanionParams(
          energy: 0.72, turbulence: 0.18, flare: 0.70,
          particles: 0.80, focus: 0.96, exposure: 1.12,
        ),
        CompanionState.error: CompanionParams(
          energy: 0.30, turbulence: 0.40, flare: 0.10,
          particles: 0.24, focus: 0.40, exposure: 0.90,
        ),
      };

  static const Map<CompanionState, CompanionParams> _lunar =
      <CompanionState, CompanionParams>{
        CompanionState.unavailable: CompanionParams(
          energy: 0.05, turbulence: 0.10, flare: 0.00,
          particles: 0.06, focus: 0.30, exposure: 0.70,
        ),
        // Initializing: the idle look, calmer and dimmer (owner decision,
        // Ember V2.1 final: a normal startup must not look failed).
        CompanionState.initializing: CompanionParams(
          energy: 0.14, turbulence: 0.15, flare: 0.05,
          particles: 0.18, focus: 0.55, exposure: 0.86,
        ),
        CompanionState.idle: CompanionParams(
          energy: 0.22, turbulence: 0.24, flare: 0.12,
          particles: 0.30, focus: 0.55, exposure: 1.00,
        ),
        CompanionState.listening: CompanionParams(
          energy: 0.15, turbulence: 0.14, flare: 0.07,
          particles: 0.24, focus: 0.80, exposure: 0.98,
        ),
        CompanionState.thinking: CompanionParams(
          energy: 0.28, turbulence: 0.46, flare: 0.05,
          particles: 0.24, focus: 0.44, exposure: 0.85,
        ),
        CompanionState.speaking: CompanionParams(
          energy: 0.38, turbulence: 0.22, flare: 0.32,
          particles: 0.34, focus: 0.72, exposure: 1.02,
        ),
        CompanionState.working: CompanionParams(
          energy: 0.50, turbulence: 0.28, flare: 0.38,
          particles: 0.38, focus: 0.70, exposure: 1.05,
        ),
        CompanionState.awaitingApproval: CompanionParams(
          energy: 0.26, turbulence: 0.14, flare: 0.14,
          particles: 0.28, focus: 0.88, exposure: 1.00,
        ),
        CompanionState.success: CompanionParams(
          energy: 0.60, turbulence: 0.12, flare: 0.60,
          particles: 0.40, focus: 1.00, exposure: 1.10,
        ),
        CompanionState.error: CompanionParams(
          energy: 0.30, turbulence: 0.48, flare: 0.10,
          particles: 0.22, focus: 0.30, exposure: 0.88,
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
    if (!id.usesShader) {
      // Ember plays rendered clips; there is no program to load.
      _failures[id] = 'not a shader identity';
      return null;
    }
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
    this.renderScale = 1,
  });

  final CompanionIdentity identity;
  final CompanionParams params;
  final double seconds;

  /// Defaults to the identity's own body radius.
  final double? radius;

  /// Fraction of the covered pixels the shader is evaluated at (see
  /// [CompanionOrbPainter.renderScale]).
  final double renderScale;

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
        renderScale: widget.renderScale,
        devicePixelRatio: MediaQuery.maybeDevicePixelRatioOf(context) ?? 1,
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
    this.attention = false,
    this.look = CompanionLook.standard,
    this.renderScale = 1,
  });

  final CompanionIdentity identity;
  final CompanionState state;
  final double? radius;

  /// The user's appearance preferences for this companion. Applied on top of
  /// the state's own parameters; the motion setting scales the companion's
  /// own time, so changing it never jumps the animation.
  final CompanionLook look;

  /// See [CompanionOrbPainter.renderScale].
  final double renderScale;

  /// Adds the gentle attention pulse (see [CompanionParams.withAttention]).
  /// Used for `awaitingApproval`. Faded in and out, never switched.
  final bool attention;

  /// How long the companion takes to settle into a new state.
  final Duration transition;

  final Widget? fallback;

  @override
  State<CompanionOrb> createState() => _CompanionOrbState();
}

class _CompanionOrbState extends State<CompanionOrb>
    with SingleTickerProviderStateMixin, CompanionFrameDriver {
  double _seconds = 0;
  late CompanionParams _current;
  late CompanionParams _from;
  late CompanionParams _target;
  double _blend = 1;
  double _attention = 0;

  @override
  void initState() {
    super.initState();
    _from = _target = _current = CompanionParams.of(
      widget.identity,
      widget.state,
    );
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
    resumeFrames();
  }

  bool _reducedMotion = false;

  @override
  void didChangeDependencies() {
    _reducedMotion = EffectsSettings.of(context).reducedMotion;
    super.didChangeDependencies();
  }

  /// Under reduced motion the companion is a still image once its blend and
  /// attention have settled, so it stops asking for frames. Ember animates
  /// itself, so this state asks for none.
  @override
  bool get wantsFrames {
    if (!widget.identity.usesShader) return false;
    if (!_reducedMotion) return true;
    final goal = widget.attention ? 1.0 : 0.0;
    return _blend < 1 || (goal - _attention).abs() > 0.01;
  }

  @override
  void onCompanionFrame(double seconds, double dt) {
    final transition = widget.transition.inMicroseconds / 1e6;
    setState(() {
      // The companion's own time: integrated, so a change of the motion
      // preference changes the speed from here on instead of jumping.
      _seconds += dt * widget.look.motion;
      if (_blend < 1) {
        // Advance by real elapsed time rather than an assumed 1/60, so the
        // transition lasts the same wall-clock duration at any frame rate.
        _blend = transition <= 0 ? 1 : (_blend + dt / transition).clamp(0.0, 1.0);
      }
      final t = Curves.easeInOutCubic.transform(_blend);
      _current = _from.lerpTo(_target, t);
      // The pulse fades in and out over about a second rather than appearing
      // mid-cycle at full strength.
      final goal = widget.attention ? 1.0 : 0.0;
      _attention += (goal - _attention) * (1 - math.exp(-dt / 0.35));
      if ((goal - _attention).abs() <= 0.01) _attention = goal;
    });
  }

  @override
  Widget build(BuildContext context) {
    final effects = EffectsSettings.of(context);
    if (!widget.identity.usesShader) {
      if (effects.reducedEffects) {
        return widget.fallback ?? const SizedBox.expand();
      }
      return EmberCompanion(
        state: widget.state,
        attention: widget.attention,
        look: widget.look,
        fallback: widget.fallback,
      );
    }
    // Reduced motion freezes the clock at a representative moment instead of
    // stopping the widget: the state must still be readable, it just must not
    // move. Reduced effects drops the shader entirely.
    final seconds = effects.reducedMotion ? 7.0 : _seconds;
    if (effects.reducedEffects) {
      return widget.fallback ?? const SizedBox.expand();
    }
    // Reduced motion holds the pulse at its midpoint: the companion still
    // looks attentive, it just does not throb.
    final wave = effects.reducedMotion
        ? 0.5
        : CompanionParams.attentionWave(_seconds);
    final base = widget.look.apply(_current);
    final params = _attention > 0.001
        ? base.withAttention(wave * _attention)
        : base;
    return CompanionOrbFrame(
      identity: widget.identity,
      params: params,
      seconds: seconds,
      radius: widget.radius,
      fallback: widget.fallback,
      renderScale: widget.renderScale,
    );
  }
}

class CompanionOrbPainter extends CustomPainter {
  CompanionOrbPainter({
    required this.shader,
    required this.seconds,
    required this.params,
    required this.radius,
    this.renderScale = 1,
    this.devicePixelRatio = 1,
  });

  final ui.FragmentShader shader;
  final double seconds;
  final CompanionParams params;
  final double radius;

  /// Below 1 the shader is evaluated into an offscreen image of
  /// `renderScale` times the covered device pixels and drawn back scaled up
  /// with bilinear filtering. Fragment work falls with the pixel count (0.5
  /// computes a quarter of the pixels); the companions are soft-edged light,
  /// so the loss is mostly in the finest embers and petal edges.
  final double renderScale;
  final double devicePixelRatio;

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

  /// The offscreen size for [renderScale], or null when drawing directly.
  static Size? offscreenSize(Size size, double renderScale, double dpr) {
    if (renderScale >= 0.999) return null;
    final s = renderScale * dpr;
    return Size(
      math.max(1, (size.width * s).roundToDouble()),
      math.max(1, (size.height * s).roundToDouble()),
    );
  }

  void _setUniforms(Size size) {
    final values = uniformsFor(
      size: size,
      seconds: seconds,
      params: params,
      radius: radius,
    );
    for (var i = 0; i < values.length; i++) {
      shader.setFloat(i, values[i]);
    }
  }

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final low = offscreenSize(size, renderScale, devicePixelRatio);
    if (low == null) {
      _setUniforms(size);
      canvas.drawRect(Offset.zero & size, Paint()..shader = shader);
      return;
    }
    _setUniforms(low);
    final recorder = ui.PictureRecorder();
    Canvas(recorder).drawRect(Offset.zero & low, Paint()..shader = shader);
    final picture = recorder.endRecording();
    final image = picture.toImageSync(low.width.toInt(), low.height.toInt());
    picture.dispose();
    canvas.drawImageRect(
      image,
      Offset.zero & low,
      Offset.zero & size,
      Paint()..filterQuality = FilterQuality.medium,
    );
    // The display list holds its own reference; this releases ours.
    image.dispose();
  }

  @override
  bool shouldRepaint(CompanionOrbPainter old) =>
      old.seconds != seconds ||
      old.radius != radius ||
      old.params != params ||
      old.renderScale != renderScale ||
      old.devicePixelRatio != devicePixelRatio ||
      !identical(old.shader, shader);
}
