import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart' show PointerExitEvent;
import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import 'companion_state.dart';
import 'effects_settings.dart';
import 'orb_shader.dart';

/// Visual family of the orb. Every variant shares the same nine-state
/// engine ([OrbParams]), tints, rings, arcs and bloom; only the body
/// drawing differs, so the owner can choose a look without changing
/// what any state means. Compared in `docs/ui_phase/UI_ORB_OPTIONS.md`.
enum OrbVariant {
  /// Plasma core with a thin limb inside a loose particle shell (default).
  nebula,

  /// Small bright core with one wide luminous tilted ring; echoes the
  /// eclipse wordmark. Particles ride the ring.
  halo,

  /// No solid body: a dense swarm of particles that coheres into a
  /// sphere. State changes density and cohesion.
  swarm,

  /// Frosted glass sphere with a dim inner swirl, a specular highlight
  /// and a lit lower rim; few particles.
  glass,

  /// Plasma core that emits its particles: each one is born at the core,
  /// streams outward along a gentle spiral, fades and is reborn. State
  /// sets the emission rate and spread.
  flow,

  /// Neural mesh: nodes on the sphere surface joined by short edges, the
  /// whole lattice turning slowly. Thinking brightens edges and speeds
  /// the turn; error breaks edges.
  mesh,

  /// Liquid energy: a deep blue sphere with a tesla-coil network of
  /// veins crawling over it; bolts flicker faster the more URI works.
  energy,
}

extension OrbVariantLabel on OrbVariant {
  String get label => switch (this) {
    OrbVariant.nebula => 'Fluid Plasma',
    OrbVariant.swarm => 'Particle Intelligence',
    OrbVariant.mesh => 'Neural Filaments',
    OrbVariant.energy => 'Electric Core',
    OrbVariant.glass => 'Holographic Atmosphere',
    OrbVariant.halo => 'Aurora Vortex',
    OrbVariant.flow => 'Sun / Flow',
  };
}

/// URI's living form: a breathing core of light with a field of
/// orbiting particles.
///
/// One widget, one visual identity, nine states ([CompanionState]). The
/// state only changes the *parameters* of the same drawing ([OrbParams]),
/// and parameter changes are tweened over [UriMotion.orbState], so the
/// orb never "cuts" to a different object: it stays recognizably the
/// same entity while its behaviour changes.
///
/// Rendering: a `CustomPainter` driven by one `Ticker`. Particle
/// positions are pure functions of elapsed time and a fixed seed, so a
/// frame is one pass over the particle field with no mutable
/// per-particle state. Under `EffectsSettings.reducedEffects` the
/// runtime shader core and blur masks are skipped; the gradient core and
/// particles remain. Under `reducedMotion` the ticker stops and the orb
/// renders a still frame (state is still shown by colour, ring and
/// badge).
class EnergyOrb extends StatefulWidget {
  const EnergyOrb({
    super.key,
    required this.state,
    this.size = 220,
    this.progress,
    this.seed = 7,
    this.animate = true,
    this.semanticsLabel,
    this.variant = OrbVariant.nebula,
    this.pokes,
    this.interactive = true,
    this.palette,
  });

  final CompanionState state;

  /// Outer diameter in logical pixels (halo included).
  final double size;

  /// 0..1 progress ring while [CompanionState.working]; null = indeterminate.
  final double? progress;

  final int seed;

  /// Test hook to freeze time. `EffectsSettings.reducedMotion` does the
  /// same for users.
  final bool animate;

  final String? semanticsLabel;

  final OrbVariant variant;

  /// Increment to play the "poke" response (a short core bump, a burst
  /// ring and an outward kick of the particles). Driven by a click on
  /// the orb in [LivingShell]; the question bubble is drawn there.
  final ValueListenable<int>? pokes;

  /// Pointer "gusts": when the cursor sweeps across the orb, particles
  /// are pushed along the sweep like leaves in a gust and drift back.
  /// Pure presentation; no state change. Off in tests that assert
  /// deterministic frames.
  final bool interactive;

  /// Colour palette; null = the variant's default palette.
  final OrbPalette? palette;

  @override
  State<EnergyOrb> createState() => _EnergyOrbState();
}

class _EnergyOrbState extends State<EnergyOrb> with TickerProviderStateMixin {
  late final Ticker _ticker;
  late final AnimationController _stateTween;
  Duration _elapsed = Duration.zero;
  OrbParams _from = OrbParams.forState(CompanionState.idle);
  OrbParams _to = OrbParams.forState(CompanionState.idle);
  ui.FragmentProgram? _program;
  late final AnimationController _poke;
  final List<_Gust> _gusts = [];
  Offset? _lastPointer;
  double? _lastPointerAt;
  late _ParticleField _field = _ParticleField(
    seed: widget.seed,
    count: _particleCountFor(widget.variant),
  );

  /// Test hook (A9): whether the current frame paints with the shader.
  @visibleForTesting
  bool get usesShader =>
      _program != null && !EffectsSettings.of(context).reducedEffects;

  static int _particleCountFor(OrbVariant v) => switch (v) {
    OrbVariant.nebula => 0,
    OrbVariant.halo => 0,
    OrbVariant.swarm => 360,
    OrbVariant.glass => 0,
    OrbVariant.flow => 150,
    OrbVariant.mesh => 0,
    OrbVariant.energy => 0,
  };

  @override
  void initState() {
    super.initState();
    _from = _to = OrbParams.forState(widget.state);
    _stateTween = AnimationController(
      vsync: this,
      duration: UriMotion.orbState,
      value: 1,
    )..addListener(_onTweenTick);
    _ticker = createTicker(_onTick);
    _poke = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 720),
    )..addListener(_onTweenTick);
    widget.pokes?.addListener(_onPoke);
    OrbShaderCache.load().then((program) {
      if (!mounted) return;
      if (program != null) setState(() => _program = program);
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _syncTicker();
  }

  @override
  void didUpdateWidget(EnergyOrb oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.state != widget.state) {
      _from = _current;
      _to = OrbParams.forState(widget.state);
      _stateTween
        ..value = 0
        ..forward();
    }
    if (oldWidget.variant != widget.variant || oldWidget.seed != widget.seed) {
      _field = _ParticleField(
        seed: widget.seed,
        count: _particleCountFor(widget.variant),
      );
    }
    if (oldWidget.animate != widget.animate) _syncTicker();
    if (!identical(oldWidget.pokes, widget.pokes)) {
      oldWidget.pokes?.removeListener(_onPoke);
      widget.pokes?.addListener(_onPoke);
    }
  }

  /// Test/host hook: play the poke response now.
  void poke() {
    if (!mounted) return;
    _poke
      ..value = 0
      ..forward();
  }

  void _onPoke() => poke();

  double get _now => _elapsed.inMicroseconds / 1e6;

  void _onPointer(PointerEvent e) {
    if (!widget.interactive || !_ticker.isActive) return;
    final now = _now;
    final last = _lastPointer;
    final lastAt = _lastPointerAt;
    _lastPointer = e.localPosition;
    _lastPointerAt = now;
    if (last == null || lastAt == null) return;
    final dt = now - lastAt;
    if (dt <= 0 || dt > 0.25) return;
    final v = (e.localPosition - last) / dt; // px per second
    if (v.distance < 120) return;
    _gusts.add(
      _Gust(
        e.localPosition,
        v / v.distance,
        v.distance.clamp(0, 2500).toDouble(),
        now,
      ),
    );
    _gusts.removeWhere((g) => now - g.bornAt > _Gust.life);
    if (_gusts.length > 10) _gusts.removeAt(0);
  }

  void _onPointerExit(PointerExitEvent _) {
    _lastPointer = null;
    _lastPointerAt = null;
  }

  void _syncTicker() {
    final effects = EffectsSettings.of(context);
    final shouldRun = widget.animate && !effects.reducedMotion;
    if (shouldRun && !_ticker.isActive) {
      _ticker.start();
    } else if (!shouldRun && _ticker.isActive) {
      _ticker.stop();
    }
  }

  void _onTick(Duration elapsed) {
    setState(() => _elapsed = elapsed);
  }

  void _onTweenTick() {
    if (!_ticker.isActive) setState(() {});
  }

  OrbParams get _current => OrbParams.lerp(_from, _to, _stateTween.value);

  @override
  void dispose() {
    widget.pokes?.removeListener(_onPoke);
    _ticker.dispose();
    _stateTween.dispose();
    _poke.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = UriColors.of(context);
    final character = OrbCharacter.forVariant(widget.variant);
    final palette = widget.palette ?? character.defaultPalette;
    final effects = EffectsSettings.of(context);
    final params = _current;
    final tint = _tintFor(widget.state, colors);
    // Every palette hue leans toward the state tint by tintMix, so
    // approval/done/attention read the same on any palette.
    final hues = [
      for (final h in palette.hues) Color.lerp(h, tint, params.tintMix)!,
    ];
    final time = _now;
    _gusts.removeWhere((g) => time - g.bornAt > _Gust.life);

    return Semantics(
      label: widget.semanticsLabel ?? 'URI companion: ${widget.state.label}',
      liveRegion: true,
      child: RepaintBoundary(
        child: MouseRegion(
          opaque: false,
          onExit: _onPointerExit,
          child: Listener(
            behavior: HitTestBehavior.translucent,
            onPointerHover: _onPointer,
            onPointerMove: _onPointer,
            child: SizedBox(
              width: widget.size,
              height: widget.size,
              child: CustomPaint(
                painter: _OrbPainter(
                  time: time,
                  params: params,
                  hues: hues,
                  hot: Color.lerp(palette.hot, tint, params.tintMix * 0.7)!,
                  tint: tint,
                  tintMix: params.tintMix,
                  style: character.style,
                  ink: colors.ink,
                  canvas: colors.canvas,
                  progress: widget.state == CompanionState.working
                      ? widget.progress
                      : null,
                  reducedEffects: effects.reducedEffects,
                  program: effects.reducedEffects ? null : _program,
                  field: _field,
                  variant: widget.variant,
                  gusts: List<_Gust>.unmodifiable(_gusts),
                  poke: _poke.value,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }

  static Color _tintFor(CompanionState state, UriColors c) => switch (state) {
    CompanionState.awaitingApproval => c.warning,
    CompanionState.success => c.success,
    CompanionState.error => c.danger,
    CompanionState.unavailable => c.inkFaint,
    _ => c.accent,
  };
}

/// Everything that varies between states. Lerp-able so transitions are
/// continuous.
@immutable
class OrbParams {
  const OrbParams({
    required this.breathRate,
    required this.breathDepth,
    required this.particleSpeed,
    required this.particleSpread,
    required this.particleAlpha,
    required this.energy,
    required this.turbulence,
    required this.tintMix,
    required this.ringStrength,
    required this.orbitArc,
    required this.bloom,
    required this.rippleStrength,
    required this.coreScale,
  });

  /// Breathing cycles per second.
  final double breathRate;

  /// Scale amplitude of the breath (0.04 = +/-4%).
  final double breathDepth;

  /// Particle angular speed multiplier.
  final double particleSpeed;

  /// Particle orbit radius as a fraction of the core radius.
  final double particleSpread;

  final double particleAlpha;

  /// 0..1 activity (shader speed, core brightness).
  final double energy;

  /// 0..1 chaos (shader) and particle jitter.
  final double turbulence;

  /// 0..1 how much the state tint replaces the base glow colour.
  final double tintMix;

  /// Pulsing outer ring (approval).
  final double ringStrength;

  /// Rotating orbit arc (working).
  final double orbitArc;

  /// Expanding bloom ring (success).
  final double bloom;

  /// Concentric ripples (speaking) / inward pulses (listening).
  final double rippleStrength;

  final double coreScale;

  static OrbParams forState(CompanionState state) => switch (state) {
    CompanionState.unavailable => const OrbParams(
      breathRate: 0.12,
      breathDepth: 0.015,
      particleSpeed: 0.15,
      particleSpread: 1.05,
      particleAlpha: 0.25,
      energy: 0.05,
      turbulence: 0.0,
      tintMix: 0.85,
      ringStrength: 0,
      orbitArc: 0,
      bloom: 0,
      rippleStrength: 0,
      coreScale: 0.9,
    ),
    CompanionState.idle => const OrbParams(
      breathRate: 0.18,
      breathDepth: 0.035,
      particleSpeed: 0.35,
      particleSpread: 1.25,
      particleAlpha: 0.55,
      energy: 0.2,
      turbulence: 0.1,
      tintMix: 0,
      ringStrength: 0,
      orbitArc: 0,
      bloom: 0,
      rippleStrength: 0,
      coreScale: 1,
    ),
    CompanionState.listening => const OrbParams(
      breathRate: 0.5,
      breathDepth: 0.05,
      particleSpeed: 0.6,
      particleSpread: 1.5,
      particleAlpha: 0.7,
      energy: 0.45,
      turbulence: 0.1,
      tintMix: 0,
      ringStrength: 0.35,
      orbitArc: 0,
      bloom: 0,
      rippleStrength: -1,
      coreScale: 1.04,
    ),
    CompanionState.thinking => const OrbParams(
      breathRate: 0.9,
      breathDepth: 0.03,
      particleSpeed: 1.6,
      particleSpread: 1.1,
      particleAlpha: 0.9,
      energy: 0.85,
      turbulence: 0.35,
      tintMix: 0,
      ringStrength: 0,
      orbitArc: 0,
      bloom: 0,
      rippleStrength: 0,
      coreScale: 1.02,
    ),
    CompanionState.speaking => const OrbParams(
      breathRate: 2.2,
      breathDepth: 0.06,
      particleSpeed: 0.8,
      particleSpread: 1.35,
      particleAlpha: 0.8,
      energy: 0.6,
      turbulence: 0.15,
      tintMix: 0,
      ringStrength: 0,
      orbitArc: 0,
      bloom: 0,
      rippleStrength: 1,
      coreScale: 1.05,
    ),
    CompanionState.working => const OrbParams(
      breathRate: 0.6,
      breathDepth: 0.025,
      particleSpeed: 1.1,
      particleSpread: 1.4,
      particleAlpha: 0.85,
      energy: 0.7,
      turbulence: 0.2,
      tintMix: 0,
      ringStrength: 0,
      orbitArc: 1,
      bloom: 0,
      rippleStrength: 0,
      coreScale: 1,
    ),
    CompanionState.awaitingApproval => const OrbParams(
      breathRate: 0.45,
      breathDepth: 0.02,
      particleSpeed: 0.12,
      particleSpread: 1.3,
      particleAlpha: 0.6,
      energy: 0.3,
      turbulence: 0.0,
      tintMix: 0.8,
      ringStrength: 1,
      orbitArc: 0,
      bloom: 0,
      rippleStrength: 0,
      coreScale: 1,
    ),
    CompanionState.success => const OrbParams(
      breathRate: 0.3,
      breathDepth: 0.03,
      particleSpeed: 0.9,
      particleSpread: 1.6,
      particleAlpha: 0.9,
      energy: 0.75,
      turbulence: 0.05,
      tintMix: 0.9,
      ringStrength: 0,
      orbitArc: 0,
      bloom: 1,
      rippleStrength: 0,
      coreScale: 1.08,
    ),
    CompanionState.error => const OrbParams(
      breathRate: 0.25,
      breathDepth: 0.02,
      particleSpeed: 0.25,
      particleSpread: 0.95,
      particleAlpha: 0.5,
      energy: 0.35,
      turbulence: 0.9,
      tintMix: 0.9,
      ringStrength: 0.5,
      orbitArc: 0,
      bloom: 0,
      rippleStrength: 0,
      coreScale: 0.94,
    ),
  };

  static OrbParams lerp(OrbParams a, OrbParams b, double t) {
    double l(double x, double y) => x + (y - x) * t;
    return OrbParams(
      breathRate: l(a.breathRate, b.breathRate),
      breathDepth: l(a.breathDepth, b.breathDepth),
      particleSpeed: l(a.particleSpeed, b.particleSpeed),
      particleSpread: l(a.particleSpread, b.particleSpread),
      particleAlpha: l(a.particleAlpha, b.particleAlpha),
      energy: l(a.energy, b.energy),
      turbulence: l(a.turbulence, b.turbulence),
      tintMix: l(a.tintMix, b.tintMix),
      ringStrength: l(a.ringStrength, b.ringStrength),
      orbitArc: l(a.orbitArc, b.orbitArc),
      bloom: l(a.bloom, b.bloom),
      rippleStrength: l(a.rippleStrength, b.rippleStrength),
      coreScale: l(a.coreScale, b.coreScale),
    );
  }
}

/// One cursor sweep across the orb: where, which way, how fast, when.
@immutable
class _Gust {
  const _Gust(this.pos, this.dir, this.speed, this.bornAt);
  final Offset pos;
  final Offset dir; // unit vector
  final double speed; // px/s, clamped
  final double bornAt; // orb time, seconds
  static const double life = 1.4;
}

/// Fixed per-particle seeds. Positions are computed from time each
/// frame; nothing here changes after construction.
class _ParticleField {
  _ParticleField({required int seed, required this.count}) {
    final rnd = math.Random(seed);
    for (var i = 0; i < count; i++) {
      baseAngle.add(rnd.nextDouble() * math.pi * 2);
      tilt.add((rnd.nextDouble() - 0.5) * math.pi * 0.9);
      speed.add((0.5 + rnd.nextDouble()) * (rnd.nextBool() ? 1 : -1));
      radiusJitter.add(0.82 + rnd.nextDouble() * 0.36);
      // Volume radius for the swarm (0..1, cube-root for even fill).
      volume.add(math.pow(rnd.nextDouble(), 1 / 3).toDouble());
      size.add(0.6 + rnd.nextDouble() * 1.6);
      phase.add(rnd.nextDouble() * math.pi * 2);
    }
  }

  final int count;
  final List<double> baseAngle = [];
  final List<double> tilt = [];
  final List<double> speed = [];
  final List<double> radiusJitter = [];
  final List<double> volume = [];
  final List<double> size = [];
  final List<double> phase = [];
}

/// Colour palette for the orb, independent of its style (the owner's
/// board: "the same orb style expressed in different colour palettes").
/// Three to five hues per palette; `hot` is the brightest light.
/// The state tints (approval amber, done green, attention red,
/// unavailable grey) still override through `OrbParams.tintMix`.
enum OrbPalette {
  signature,
  deepOcean,
  aurora,
  nature,
  sunset,
  royal,
  passion,
  softPastel,
  monochrome,
  rainbow,
}

extension OrbPaletteData on OrbPalette {
  String get label => switch (this) {
    OrbPalette.signature => 'Signature (cyan / blue / violet)',
    OrbPalette.deepOcean => 'Deep Ocean (teal / blue)',
    OrbPalette.aurora => 'Aurora (cyan / violet / pink)',
    OrbPalette.nature => 'Nature (green / teal)',
    OrbPalette.sunset => 'Sunset (amber / orange / pink)',
    OrbPalette.royal => 'Royal (blue / purple)',
    OrbPalette.passion => 'Passion (red / orange)',
    OrbPalette.softPastel => 'Soft Pastel (ice / pink / lavender)',
    OrbPalette.monochrome => 'Monochrome (white / silver)',
    OrbPalette.rainbow => 'Rainbow',
  };

  List<Color> get hues => switch (this) {
    OrbPalette.signature => const [
      Color(0xFF38D1E8),
      Color(0xFF3B7BFF),
      Color(0xFF8A5CFF),
    ],
    OrbPalette.deepOcean => const [
      Color(0xFF1FD1C2),
      Color(0xFF2E7CFF),
      Color(0xFF123A8C),
    ],
    OrbPalette.aurora => const [
      Color(0xFF4FE3FF),
      Color(0xFF8A5CFF),
      Color(0xFFFF5FC8),
    ],
    OrbPalette.nature => const [
      Color(0xFF3DE07A),
      Color(0xFF1FC9A8),
      Color(0xFF0E6B5C),
    ],
    OrbPalette.sunset => const [
      Color(0xFFFFC24A),
      Color(0xFFFF6A2E),
      Color(0xFFFF4F8B),
    ],
    OrbPalette.royal => const [
      Color(0xFF3C5BFF),
      Color(0xFF7A3CFF),
      Color(0xFFB04CFF),
    ],
    OrbPalette.passion => const [
      Color(0xFFFF3B3B),
      Color(0xFFFF7A2E),
      Color(0xFFC81E4E),
    ],
    OrbPalette.softPastel => const [
      Color(0xFFBFEFFF),
      Color(0xFFFFB8DC),
      Color(0xFFC9B8FF),
    ],
    OrbPalette.monochrome => const [
      Color(0xFFF2F6FA),
      Color(0xFFB8C2CC),
      Color(0xFF7D8894),
    ],
    OrbPalette.rainbow => const [
      Color(0xFF38D1E8),
      Color(0xFF3DE07A),
      Color(0xFFFFC24A),
      Color(0xFFFF4F8B),
      Color(0xFF8A5CFF),
    ],
  };

  Color get hot => switch (this) {
    OrbPalette.sunset || OrbPalette.passion => const Color(0xFFFFF1D6),
    OrbPalette.monochrome => const Color(0xFFFFFFFF),
    _ => const Color(0xFFEAF8FF),
  };
}

/// Style-level character: shader style and the palette a variant opens
/// with. (Previously a fixed colour table; colours now come from
/// [OrbPalette] so any style can wear any palette.)
@immutable
class OrbCharacter {
  const OrbCharacter({required this.style, required this.defaultPalette});

  /// Shader style: 0 plasma swirl, 1 sun, 2 liquid veins.
  final double style;
  final OrbPalette defaultPalette;

  static OrbCharacter forVariant(OrbVariant v) => switch (v) {
    OrbVariant.nebula => const OrbCharacter(
      style: 2,
      defaultPalette: OrbPalette.signature,
    ),
    OrbVariant.swarm => const OrbCharacter(
      style: 0,
      defaultPalette: OrbPalette.aurora,
    ),
    OrbVariant.mesh => const OrbCharacter(
      style: 0,
      defaultPalette: OrbPalette.softPastel,
    ),
    OrbVariant.energy => const OrbCharacter(
      style: 0,
      defaultPalette: OrbPalette.royal,
    ),
    OrbVariant.glass => const OrbCharacter(
      style: 2,
      defaultPalette: OrbPalette.deepOcean,
    ),
    OrbVariant.halo => const OrbCharacter(
      style: 0,
      defaultPalette: OrbPalette.aurora,
    ),
    OrbVariant.flow => const OrbCharacter(
      style: 1,
      defaultPalette: OrbPalette.sunset,
    ),
  };
}

class _OrbPainter extends CustomPainter {
  _OrbPainter({
    required this.time,
    required this.params,
    required this.hues,
    required this.hot,
    required this.tint,
    required this.tintMix,
    required this.style,
    required this.ink,
    required this.canvas,
    required this.progress,
    required this.reducedEffects,
    required this.program,
    required this.field,
    required this.variant,
    required this.gusts,
    required this.poke,
  });

  final double time;
  final OrbParams params;

  /// Palette hues already blended toward the state tint.
  final List<Color> hues;

  /// Brightest light (palette token).
  final Color hot;
  final Color tint;
  final double tintMix;
  final double style;
  final Color ink;
  final Color canvas;
  final double? progress;
  final bool reducedEffects;
  final ui.FragmentProgram? program;
  final _ParticleField field;
  final OrbVariant variant;
  final List<_Gust> gusts;

  /// 0..1 poke animation progress (0 = none).
  final double poke;

  Color get glow => hues[0];
  Color get secondary => hues[1 % hues.length];
  Color hue(int i) => hues[i % hues.length];

  /// Where a particle actually lands: its base position plus the cursor
  /// gusts and the poke burst. Deterministic for the given inputs.
  Offset _place(Offset center, double x, double y, double coreR) {
    var p = center + Offset(x, y);
    if (poke > 0 && poke < 1) {
      final burst = math.sin(poke * math.pi);
      final d = p - center;
      final dist = d.distance;
      if (dist > 1) p += d / dist * coreR * 0.35 * burst;
    }
    for (final g in gusts) {
      final age = time - g.bornAt;
      if (age < 0 || age > _Gust.life) continue;
      final d = p - g.pos;
      final dist = d.distance;
      final reach = coreR * 1.2;
      final falloff = math.exp(-(dist * dist) / (reach * reach));
      if (falloff < 0.02) continue;
      final decay =
          math.sin(math.min(1.0, age / _Gust.life) * math.pi) *
          (1 - age / _Gust.life);
      final strength =
          coreR * 0.7 * (g.speed / 1200).clamp(0.25, 1.4) * falloff * decay;
      p += g.dir * strength;
      if (dist > 1) {
        p += d / dist * strength * 0.35;
      }
    }
    return p;
  }

  /// Gust displacement as a vector for a point (used to bend ribbons).
  Offset _gustAt(Offset p, double coreR) =>
      _place(Offset.zero, p.dx, p.dy, coreR) - p;

  static double _hash(int a, int b) {
    var h = a * 374761393 + b * 668265263;
    h = (h ^ (h >> 13)) * 1274126177;
    h = h ^ (h >> 16);
    return (h & 0xffffff) / 0xffffff;
  }

  Paint _blurred(Paint p, double sigma) {
    if (!reducedEffects && sigma > 0) {
      p.maskFilter = ui.MaskFilter.blur(ui.BlurStyle.normal, sigma);
    }
    return p;
  }

  @override
  void paint(Canvas c, Size size) {
    final center = size.center(Offset.zero);
    final outer = size.shortestSide / 2;
    final breath =
        1 +
        params.breathDepth * math.sin(time * params.breathRate * math.pi * 2);
    final bump = poke > 0 && poke < 1
        ? 1 + 0.10 * math.sin(poke * math.pi)
        : 1.0;
    final coreR = outer * 0.30 * params.coreScale * breath * bump;

    switch (variant) {
      case OrbVariant.nebula: // Fluid Plasma
        _paintHalo(c, center, coreR, 2.3, 1.0);
        _paintSphereBase(c, center, coreR, 0.9);
        _paintShaderCore(c, center, coreR, alpha: 0.55);
        _paintRibbons(
          c,
          center,
          coreR,
          count: 5,
          speed: 0.35,
          amp: 0.55,
          width: 0.16,
          reach: 0.92,
        );
        _paintSurface(c, center, coreR, 0.9);
      case OrbVariant.swarm: // Particle Intelligence
        _paintHalo(c, center, coreR, 2.3, 0.8);
        _paintSphereBase(c, center, coreR, 0.5);
        _paintRibbons(
          c,
          center,
          coreR,
          count: 4,
          speed: 0.5,
          amp: 0.7,
          width: 0.08,
          reach: 1.0,
          alpha: 0.5,
        );
        _paintStreamParticles(c, center, coreR);
        _paintSurface(c, center, coreR, 0.45);
      case OrbVariant.mesh: // Neural Filaments
        _paintHalo(c, center, coreR, 2.1, 0.6);
        _paintSphereBase(c, center, coreR, 1.0);
        _paintShaderCore(c, center, coreR * 0.95, alpha: 0.35);
        _paintThreads(c, center, coreR);
        _paintSurface(c, center, coreR, 1.0);
      case OrbVariant.energy: // Electric Core
        _paintHalo(c, center, coreR, 2.4, 1.0);
        _paintSphereBase(c, center, coreR, 0.7);
        _paintRibbons(
          c,
          center,
          coreR,
          count: 6,
          speed: 0.9,
          amp: 0.4,
          width: 0.07,
          reach: 0.95,
          alpha: 0.7,
        );
        _paintElectricCore(c, center, coreR);
        _paintSurface(c, center, coreR, 0.6);
      case OrbVariant.glass: // Holographic Atmosphere
        _paintHalo(c, center, coreR, 2.0, 0.6);
        _paintHolographic(c, center, coreR);
      case OrbVariant.halo: // Aurora Vortex
        _paintHalo(c, center, coreR, 2.2, 0.8);
        _paintSphereBase(c, center, coreR, 0.6);
        _paintRibbons(
          c,
          center,
          coreR,
          count: 9,
          speed: 0.45,
          amp: 0.85,
          width: 0.2,
          reach: 0.98,
          alpha: 0.8,
          vortex: true,
        );
        _paintSurface(c, center, coreR, 0.7);
      case OrbVariant.flow: // Sun
        _paintCorona(c, center, coreR);
        _paintFlowParticles(c, center, coreR, behind: true);
        _paintShaderCore(c, center, coreR, alpha: 1);
        _paintProminences(c, center, coreR);
        _paintLimb(c, center, coreR, 0.5);
        _paintFlowParticles(c, center, coreR, behind: false);
    }
    _paintStateOverlays(c, center, coreR, outer);
  }

  // ---------------------------------------------------------------- common

  void _paintHalo(
    Canvas c,
    Offset center,
    double coreR,
    double scale,
    double strength,
  ) {
    final haloR = coreR * scale;
    final a = (0.10 + params.energy * 0.22) * strength;
    c.drawCircle(
      center,
      haloR,
      Paint()
        ..shader = ui.Gradient.radial(
          center,
          haloR,
          [
            glow.withValues(alpha: a),
            secondary.withValues(alpha: a * 0.5),
            glow.withValues(alpha: 0),
          ],
          const [0.0, 0.5, 1.0],
        ),
    );
  }

  /// Dark translucent body the energy lives inside (every ribbon style).
  void _paintSphereBase(
    Canvas c,
    Offset center,
    double coreR,
    double strength,
  ) {
    c.drawCircle(
      center,
      coreR,
      Paint()
        ..shader = ui.Gradient.radial(
          center.translate(-coreR * 0.2, -coreR * 0.25),
          coreR * 1.25,
          [
            Color.lerp(
              canvas,
              secondary,
              0.30 * strength,
            )!.withValues(alpha: 0.9),
            Color.lerp(
              canvas,
              secondary,
              0.18 * strength,
            )!.withValues(alpha: 0.95),
            Color.lerp(canvas, glow, 0.35 * strength)!.withValues(alpha: 0.98),
          ],
          const [0.0, 0.6, 1.0],
        ),
    );
  }

  /// Translucent surface over the energy: rim light + a soft specular,
  /// so the ribbons read as "beneath a surface" (Fluid Plasma reference).
  void _paintSurface(Canvas c, Offset center, double coreR, double strength) {
    c.drawCircle(
      center,
      coreR * 0.985,
      _blurred(
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = coreR * 0.06
          ..shader = ui.Gradient.sweep(
            center,
            [
              glow.withValues(alpha: 0.05),
              hot.withValues(alpha: 0.55 * strength),
              hue(2).withValues(alpha: 0.35 * strength),
              glow.withValues(alpha: 0.05),
            ],
            const [0.05, 0.25, 0.4, 0.6],
          ),
        coreR * 0.04,
      ),
    );
    c.drawCircle(
      center,
      coreR,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = hot.withValues(
          alpha: (0.3 + params.energy * 0.25) * strength,
        ),
    );
    c.drawOval(
      Rect.fromCenter(
        center: center.translate(-coreR * 0.36, -coreR * 0.46),
        width: coreR * 0.62,
        height: coreR * 0.34,
      ),
      Paint()
        ..shader = ui.Gradient.radial(
          center.translate(-coreR * 0.36, -coreR * 0.46),
          coreR * 0.32,
          [hot.withValues(alpha: 0.45 * strength), hot.withValues(alpha: 0)],
        ),
    );
  }

  /// The body: runtime shader (two-tone, styled) or a gradient fallback.
  void _paintShaderCore(
    Canvas c,
    Offset center,
    double coreR, {
    required double alpha,
  }) {
    final rect = Rect.fromCircle(center: center, radius: coreR);
    final prog = program;
    if (prog != null) {
      final shader = prog.fragmentShader()
        ..setFloat(0, rect.width)
        ..setFloat(1, rect.height)
        ..setFloat(2, time)
        ..setFloat(3, params.energy)
        ..setFloat(4, params.turbulence)
        ..setFloat(5, glow.r)
        ..setFloat(6, glow.g)
        ..setFloat(7, glow.b)
        ..setFloat(8, alpha)
        ..setFloat(9, secondary.r)
        ..setFloat(10, secondary.g)
        ..setFloat(11, secondary.b)
        ..setFloat(12, style);
      c.save();
      c.translate(rect.left, rect.top);
      c.drawCircle(Offset(coreR, coreR), coreR, Paint()..shader = shader);
      c.restore();
    } else {
      final wobble = 0.5 + 0.5 * math.sin(time * (0.6 + params.energy * 2.5));
      final mid = Color.lerp(glow, secondary, 0.35 + 0.25 * wobble)!;
      c.drawCircle(
        center,
        coreR,
        Paint()
          ..shader = ui.Gradient.radial(
            center.translate(-coreR * 0.18, -coreR * 0.22),
            coreR * 1.15,
            [
              hot.withValues(alpha: 0.95 * alpha),
              glow.withValues(alpha: 0.9 * alpha),
              mid.withValues(alpha: 0.85 * alpha),
              Color.lerp(
                secondary,
                canvas,
                0.5,
              )!.withValues(alpha: 0.9 * alpha),
            ],
            const [0.0, 0.3, 0.65, 1.0],
          ),
      );
    }
    if (params.turbulence > 0.05) {
      final streak = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..color = hot.withValues(alpha: 0.3 * params.turbulence);
      for (var i = 0; i < 3; i++) {
        final a = time * (1.5 + i) * (i.isEven ? 1 : -1) + i;
        c.drawArc(
          rect.deflate(coreR * (0.15 + i * 0.18)),
          a,
          0.9,
          false,
          streak,
        );
      }
    }
  }

  void _paintLimb(Canvas c, Offset center, double r, double strength) {
    c.drawCircle(
      center,
      r,
      _blurred(
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.0
          ..color = Color.lerp(
            glow,
            hot,
            0.5,
          )!.withValues(alpha: (0.35 + params.energy * 0.3) * strength),
        1.2,
      ),
    );
  }

  // --------------------------------------------------------------- ribbons

  /// Path of ribbon k: a flowing curve inside the sphere, built from two
  /// phase-shifted sines on a slowly turning axis; bent by cursor gusts.
  Path _ribbonPath(
    Offset center,
    double coreR,
    int k,
    double speed,
    double amp,
    double reach,
    bool vortex,
  ) {
    final phase = time * speed * (0.6 + 0.5 * _hash(k, 1)) + k * 1.9;
    final tiltA = _hash(k, 2) * math.pi * 2 + time * 0.05 * (k.isEven ? 1 : -1);
    final ca = math.cos(tiltA), sa = math.sin(tiltA);
    final path = Path();
    const steps = 48;
    var prev = Offset.zero;
    for (var s = 0; s <= steps; s++) {
      final t = s / steps;
      double x, y;
      if (vortex) {
        // Orbit band: a tilted ring segment with undulation.
        final ang = phase + t * math.pi * 1.7;
        final rr =
            coreR *
            reach *
            (0.55 + 0.35 * _hash(k, 3)) *
            (1 + 0.08 * math.sin(phase * 2 + t * 6));
        x = math.cos(ang) * rr;
        y = math.sin(ang) * rr * (0.35 + 0.4 * _hash(k, 4));
      } else {
        // S-curve across the sphere.
        final u = (t - 0.5) * 2; // -1..1
        x = u * coreR * reach;
        y =
            (math.sin(u * math.pi * (1.0 + 0.5 * _hash(k, 5)) + phase) *
                    amp *
                    0.5 +
                math.sin(u * math.pi * 1.6 + phase * 1.3 + k) * amp * 0.10) *
            coreR;
        // Keep inside the disc.
        final maxY =
            math.sqrt(
              math.max(0.0, (coreR * reach) * (coreR * reach) - x * x),
            ) *
            0.95;
        y = y.clamp(-maxY, maxY);
      }
      final rx = x * ca - y * sa;
      final ry = x * sa + y * ca;
      final pt = center + Offset(rx, ry) + _gustAt(Offset(rx, ry), coreR);
      if (s == 0) {
        path.moveTo(pt.dx, pt.dy);
        prev = pt;
      } else {
        // Smooth: curve through the midpoint of the previous and this point.
        final mid = Offset((prev.dx + pt.dx) / 2, (prev.dy + pt.dy) / 2);
        path.quadraticBezierTo(prev.dx, prev.dy, mid.dx, mid.dy);
        prev = pt;
      }
    }
    path.lineTo(prev.dx, prev.dy);
    return path;
  }

  /// Glowing ribbons: wide soft pass (additive), medium pass, thin hot core.
  void _paintRibbons(
    Canvas c,
    Offset center,
    double coreR, {
    required int count,
    required double speed,
    required double amp,
    required double width,
    required double reach,
    double alpha = 0.85,
    bool vortex = false,
  }) {
    c.save();
    c.clipPath(
      Path()..addOval(Rect.fromCircle(center: center, radius: coreR * 0.985)),
    );
    final sp = speed * (0.6 + params.energy * 1.2);
    for (var k = 0; k < count; k++) {
      final path = _ribbonPath(
        center,
        coreR,
        k,
        sp,
        amp * (1 + params.turbulence * 0.6),
        reach,
        vortex,
      );
      final color = hue(k);
      final w = coreR * width * (0.7 + 0.6 * _hash(k, 6));
      if (!reducedEffects) {
        c.drawPath(
          path,
          _blurred(
            Paint()
              ..style = PaintingStyle.stroke
              ..strokeWidth = w * 2.6
              ..strokeCap = StrokeCap.round
              ..blendMode = BlendMode.plus
              ..color = color.withValues(alpha: 0.22 * alpha),
            w * 0.9,
          ),
        );
      }
      c.drawPath(
        path,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = w
          ..strokeCap = StrokeCap.round
          ..blendMode = reducedEffects ? BlendMode.srcOver : BlendMode.plus
          ..color = color.withValues(alpha: 0.55 * alpha),
      );
      c.drawPath(
        path,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = math.max(1.0, w * 0.28)
          ..strokeCap = StrokeCap.round
          ..color = Color.lerp(
            color,
            hot,
            0.6,
          )!.withValues(alpha: 0.65 * alpha),
      );
    }
    c.restore();
  }

  /// Particle Intelligence: particles ride the ribbon streams (sampled
  /// along the same curves) plus a loose mist around them.
  void _paintStreamParticles(Canvas c, Offset center, double coreR) {
    final paint = Paint();
    final sp = 0.5 * (0.6 + params.energy * 1.2);
    final gather = 0.5 + 0.5 * math.sin(time * params.breathRate * math.pi * 2);
    for (var i = 0; i < field.count; i++) {
      final k = i % 4;
      final life =
          (time *
                  (0.08 + params.particleSpeed * 0.1) *
                  (0.6 + field.radiusJitter[i]) +
              field.phase[i] / (math.pi * 2)) %
          1.0;
      // Position along ribbon k at parameter `life` (same maths as _ribbonPath).
      final phase = time * sp * (0.6 + 0.5 * _hash(k, 1)) + k * 1.9;
      final tiltA =
          _hash(k, 2) * math.pi * 2 + time * 0.05 * (k.isEven ? 1 : -1);
      final u = (life - 0.5) * 2;
      var x = u * coreR;
      var y =
          (math.sin(u * math.pi * (1.0 + 0.5 * _hash(k, 5)) + phase) * 0.35 +
              math.sin(u * math.pi * 2.3 + phase * 1.7 + k) * 0.12) *
          coreR;
      // Spread off the stream, more when dispersed.
      final off =
          (field.tilt[i] / (math.pi * 0.45)) *
          coreR *
          (0.08 + 0.22 * (1 - gather) + params.turbulence * 0.3);
      y += off;
      x += math.sin(field.phase[i] + time) * coreR * 0.03;
      final ca = math.cos(tiltA), sa = math.sin(tiltA);
      final rx = x * ca - y * sa;
      final ry = x * sa + y * ca;
      final inside = math.sqrt(rx * rx + ry * ry) < coreR * 1.05;
      if (!inside) continue;
      final fade = math.sin(life * math.pi);
      final alpha = (params.particleAlpha * (0.35 + 0.65 * fade)).clamp(
        0.0,
        1.0,
      );
      final color = i % 7 == 0 ? hot : hue(k);
      final pos = _place(center, rx, ry, coreR);
      final ps = field.size[i] * 0.6 * (coreR / 60).clamp(0.6, 2.2);
      paint.color = color.withValues(alpha: alpha * 0.18);
      c.drawCircle(pos, ps * 3, paint);
      paint.color = Color.lerp(color, hot, 0.35)!.withValues(alpha: alpha);
      c.drawCircle(pos, ps, paint);
    }
  }

  // ------------------------------------------------------------- electric

  Path _bolt(Offset a, Offset b, int seed, double jitter, int segments) {
    final path = Path()..moveTo(a.dx, a.dy);
    final d = b - a;
    final n = Offset(-d.dy, d.dx) / (d.distance == 0 ? 1 : d.distance);
    for (var i = 1; i < segments; i++) {
      final t = i / segments;
      final off = (_hash(seed, i) - 0.5) * 2 * jitter * math.sin(t * math.pi);
      final p = a + d * t + n * off;
      path.lineTo(p.dx, p.dy);
    }
    path.lineTo(b.dx, b.dy);
    return path;
  }

  void _strokeBolt(Canvas c, Path p, double width, double alpha, Color color) {
    if (!reducedEffects) {
      c.drawPath(
        p,
        _blurred(
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = width * 3.5
            ..strokeCap = StrokeCap.round
            ..blendMode = BlendMode.plus
            ..color = color.withValues(alpha: alpha * 0.45),
          width * 1.5,
        ),
      );
    }
    c.drawPath(
      p,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = width
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round
        ..color = Color.lerp(color, hot, 0.75)!.withValues(alpha: alpha),
    );
  }

  /// Electric Core: a hot concentrated centre with bolts passing outward
  /// to the surface, flickering faster the more URI works.
  void _paintElectricCore(Canvas c, Offset center, double coreR) {
    c.save();
    c.clipPath(Path()..addOval(Rect.fromCircle(center: center, radius: coreR)));
    final coreGlow =
        coreR * (0.42 + 0.12 * math.sin(time * 3 * (0.5 + params.energy)));
    c.drawCircle(
      center,
      coreGlow,
      Paint()
        ..blendMode = reducedEffects ? BlendMode.srcOver : BlendMode.plus
        ..shader = ui.Gradient.radial(
          center,
          coreGlow,
          [
            hot.withValues(alpha: 0.95),
            glow.withValues(alpha: 0.6),
            secondary.withValues(alpha: 0),
          ],
          const [0.0, 0.35, 1.0],
        ),
    );
    final frame = (time * (6 + params.energy * 10)).floor();
    final bolts = 6 + (params.energy * 8).round();
    for (var k = 0; k < bolts; k++) {
      final seed = frame * 23 + k * 97;
      if (_hash(seed, 9) > 0.5 + params.energy * 0.4) continue;
      final a = _hash(seed, 1) * math.pi * 2;
      final p1 =
          center +
          Offset(math.cos(a), math.sin(a)) *
              coreR *
              (0.05 + 0.15 * _hash(seed, 3));
      final p2 =
          center +
          Offset(
                math.cos(a + (_hash(seed, 2) - 0.5)),
                math.sin(a + (_hash(seed, 2) - 0.5)),
              ) *
              coreR *
              0.97;
      _strokeBolt(c, _bolt(p1, p2, seed, coreR * 0.3, 9), 1.2, 0.8, hue(k));
      c.drawCircle(p2, 1.8, Paint()..color = hot.withValues(alpha: 0.9));
    }
    c.restore();
  }

  // -------------------------------------------------------------- threads

  /// Neural Filaments: delicate threads of light leaving the sphere and
  /// drifting outward, bright at the tips.
  void _paintThreads(Canvas c, Offset center, double coreR) {
    const n = 14;
    for (var k = 0; k < n; k++) {
      final a =
          _hash(300 + k, 1) * math.pi * 2 + time * 0.04 * (k.isEven ? 1 : -1);
      final len =
          coreR * (0.9 + 0.9 * _hash(300 + k, 2)) * (0.8 + params.energy * 0.5);
      final bend = (_hash(300 + k, 3) - 0.5) * 1.6;
      final path = Path();
      const steps = 26;
      Offset? tip;
      for (var s = 0; s <= steps; s++) {
        final t = s / steps;
        final ang =
            a +
            bend * t * t +
            math.sin(time * 0.9 + k + t * 5) *
                0.08 *
                (1 + params.turbulence * 2);
        final rr = coreR * 0.55 + len * t;
        var pt = center + Offset(math.cos(ang), math.sin(ang)) * rr;
        pt += _gustAt(pt - center, coreR);
        if (s == 0) {
          path.moveTo(pt.dx, pt.dy);
        } else {
          path.lineTo(pt.dx, pt.dy);
        }
        tip = pt;
      }
      final color = hue(k);
      if (!reducedEffects) {
        c.drawPath(
          path,
          _blurred(
            Paint()
              ..style = PaintingStyle.stroke
              ..strokeWidth = 3.5
              ..strokeCap = StrokeCap.round
              ..blendMode = BlendMode.plus
              ..color = color.withValues(alpha: 0.25),
            2.0,
          ),
        );
      }
      c.drawPath(
        path,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.0
          ..strokeCap = StrokeCap.round
          ..color = Color.lerp(color, hot, 0.6)!.withValues(alpha: 0.75),
      );
      if (tip != null) {
        c.drawCircle(tip, 2.2, Paint()..color = hot.withValues(alpha: 0.9));
      }
    }
  }

  // ----------------------------------------------------------- holographic

  /// Holographic Atmosphere: translucent concentric layers with coloured
  /// rims, inner ribbons dimmer, a big specular.
  void _paintHolographic(Canvas c, Offset center, double coreR) {
    _paintSphereBase(c, center, coreR, 0.7);
    _paintRibbons(
      c,
      center,
      coreR * 0.82,
      count: 4,
      speed: 0.3,
      amp: 0.5,
      width: 0.14,
      reach: 0.9,
      alpha: 0.55,
    );
    for (var k = 0; k < 3; k++) {
      final rr = coreR * (0.62 + 0.19 * k);
      final sweepStart = time * (0.2 + 0.1 * k) * (k.isEven ? 1 : -1);
      c.drawCircle(
        center,
        rr,
        _blurred(
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = coreR * 0.05
            ..shader = ui.Gradient.sweep(
              center,
              [
                hue(k).withValues(alpha: 0.05),
                hue(k).withValues(alpha: 0.7),
                hue(k + 1).withValues(alpha: 0.5),
                hue(k).withValues(alpha: 0.05),
              ],
              const [0.0, 0.25, 0.45, 0.7],
              TileMode.repeated,
              sweepStart,
              sweepStart + math.pi * 2,
            ),
          coreR * 0.03,
        ),
      );
    }
    // Chromatic rim: cyan one side, pink the other.
    c.drawCircle(
      center,
      coreR * 0.985,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6
        ..shader = ui.Gradient.sweep(
          center,
          [
            hue(0).withValues(alpha: 0.8),
            hue(2).withValues(alpha: 0.8),
            hue(0).withValues(alpha: 0.8),
          ],
          const [0.0, 0.5, 1.0],
        ),
    );
    c.drawOval(
      Rect.fromCenter(
        center: center.translate(-coreR * 0.36, -coreR * 0.46),
        width: coreR * 0.75,
        height: coreR * 0.42,
      ),
      Paint()
        ..shader = ui.Gradient.radial(
          center.translate(-coreR * 0.36, -coreR * 0.46),
          coreR * 0.38,
          [
            hot.withValues(alpha: 0.8),
            hot.withValues(alpha: 0.12),
            hot.withValues(alpha: 0),
          ],
          const [0.0, 0.5, 1.0],
        ),
    );
    c.drawCircle(
      center.translate(coreR * 0.45, coreR * 0.5),
      coreR * 0.06,
      Paint()..color = hot.withValues(alpha: 0.5),
    );
  }

  // ------------------------------------------------------------------- sun

  void _paintCorona(Canvas c, Offset center, double coreR) {
    final outerR = coreR * 2.8;
    c.drawCircle(
      center,
      outerR,
      Paint()
        ..shader = ui.Gradient.radial(
          center,
          outerR,
          [
            glow.withValues(alpha: 0.30 + params.energy * 0.2),
            secondary.withValues(alpha: 0.16),
            secondary.withValues(alpha: 0),
          ],
          const [0.0, 0.45, 1.0],
        ),
    );
    final ray = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.2
      ..color = glow.withValues(alpha: 0.10 + params.energy * 0.1);
    for (var k = 0; k < 14; k++) {
      final a = k * (math.pi * 2 / 14) + time * 0.05;
      final len = coreR * (1.3 + 0.5 * _hash(k, 3) + 0.2 * math.sin(time + k));
      c.drawLine(
        center + Offset(math.cos(a), math.sin(a)) * coreR * 1.02,
        center + Offset(math.cos(a), math.sin(a)) * len,
        ray,
      );
    }
  }

  void _paintProminences(Canvas c, Offset center, double coreR) {
    final frame = (time * 0.6).floor();
    for (var k = 0; k < 3; k++) {
      final seed = frame * 31 + k * 71;
      final life = ((time * 0.6) + k / 3) % 1.0;
      final a = _hash(seed, 1) * math.pi * 2;
      final span = 0.35 + 0.4 * _hash(seed, 2);
      final height =
          coreR * (0.25 + 0.5 * _hash(seed, 3)) * math.sin(life * math.pi);
      final p1 = center + Offset(math.cos(a), math.sin(a)) * coreR;
      final p2 =
          center + Offset(math.cos(a + span), math.sin(a + span)) * coreR;
      final ctrl =
          center +
          Offset(math.cos(a + span / 2), math.sin(a + span / 2)) *
              (coreR + height);
      final path = Path()
        ..moveTo(p1.dx, p1.dy)
        ..quadraticBezierTo(ctrl.dx, ctrl.dy, p2.dx, p2.dy);
      c.drawPath(
        path,
        _blurred(
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2.2
            ..color = Color.lerp(
              glow,
              secondary,
              0.4,
            )!.withValues(alpha: 0.7 * math.sin(life * math.pi)),
          1.5,
        ),
      );
    }
  }

  void _paintFlowParticles(
    Canvas c,
    Offset center,
    double coreR, {
    required bool behind,
  }) {
    final paint = Paint();
    final rate = 0.08 + params.particleSpeed * 0.16;
    final reach = coreR * (1.0 + params.particleSpread * 0.9);
    for (var i = 0; i < field.count; i++) {
      final life =
          (time * rate * (0.7 + field.radiusJitter[i] * 0.6) +
              field.phase[i] / (math.pi * 2)) %
          1.0;
      final swirl =
          1.2 * (field.speed[i].sign) * (0.5 + params.turbulence * 1.5);
      final a = field.baseAngle[i] + life * swirl + time * 0.15;
      final r = coreR * 0.82 + life * reach;
      final tilt = field.tilt[i];
      final x = math.cos(a) * r;
      final y = math.sin(a) * r * math.cos(tilt);
      final depth = math.sin(a) * math.sin(tilt);
      final isBehind = depth < 0;
      if (isBehind != behind) continue;
      if (behind && math.sqrt(x * x + y * y) < coreR) continue;
      final fade = math.sin(life * math.pi);
      final near = (depth + 1) / 2;
      final alpha = (params.particleAlpha * fade * (0.45 + 0.55 * near)).clamp(
        0.0,
        1.0,
      );
      paint.color = Color.lerp(hot, secondary, life)!.withValues(alpha: alpha);
      final ps =
          field.size[i] *
          (1.3 - life * 0.9) *
          (0.7 + 0.5 * near) *
          (coreR / 60).clamp(0.6, 2.2);
      c.drawCircle(_place(center, x, y, coreR), ps, paint);
    }
  }

  // --------------------------------------------------------- state overlays

  void _paintStateOverlays(
    Canvas c,
    Offset center,
    double coreR,
    double outer,
  ) {
    final overlay = Color.lerp(glow, tint, math.max(tintMix, 0.6))!;
    if (params.ringStrength > 0.01) {
      final pulse = 0.5 + 0.5 * math.sin(time * math.pi * 1.6);
      final ringR = coreR * (1.55 + pulse * 0.08);
      c.drawCircle(
        center,
        ringR,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.6
          ..color = overlay.withValues(
            alpha: params.ringStrength * (0.35 + 0.45 * pulse),
          ),
      );
      final dots = Paint()
        ..color = overlay.withValues(alpha: params.ringStrength);
      for (var i = 0; i < 3; i++) {
        final a = -math.pi / 2 + i * (math.pi * 2 / 3) + time * 0.4;
        c.drawCircle(
          center + Offset(math.cos(a), math.sin(a)) * ringR,
          2.2,
          dots,
        );
      }
    }

    if (params.orbitArc > 0.01) {
      final arcRect = Rect.fromCircle(center: center, radius: coreR * 1.62);
      final arc = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2
        ..strokeCap = StrokeCap.round
        ..color = overlay.withValues(alpha: 0.85 * params.orbitArc);
      final p = progress;
      if (p == null) {
        final start = time * 2.4;
        c.drawArc(arcRect, start, math.pi * 0.55, false, arc);
        c.drawArc(
          arcRect,
          start + math.pi,
          math.pi * 0.25,
          false,
          arc..color = overlay.withValues(alpha: 0.4 * params.orbitArc),
        );
      } else {
        c.drawArc(
          arcRect,
          0,
          math.pi * 2,
          false,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2.2
            ..color = overlay.withValues(alpha: 0.18 * params.orbitArc),
        );
        c.drawArc(
          arcRect,
          -math.pi / 2,
          math.pi * 2 * p.clamp(0.0, 1.0),
          false,
          arc,
        );
      }
    }

    if (poke > 0 && poke < 1) {
      final burstR = coreR * (1.05 + poke * 1.3);
      c.drawCircle(
        center,
        burstR,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.0 * (1 - poke) + 0.5
          ..color = Color.lerp(
            glow,
            hot,
            0.4,
          )!.withValues(alpha: (1 - poke) * 0.8),
      );
    }

    if (params.bloom > 0.01) {
      final cycle = (time * 0.9) % 1.0;
      final bloomR = coreR * (1.1 + cycle * 1.4);
      c.drawCircle(
        center,
        bloomR,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.5 * (1 - cycle) + 0.5
          ..color = overlay.withValues(alpha: params.bloom * (1 - cycle) * 0.7),
      );
    }

    if (params.rippleStrength.abs() > 0.01) {
      final strength = params.rippleStrength.abs();
      final inward = params.rippleStrength < 0;
      for (var k = 0; k < 3; k++) {
        var cycle = ((time * 0.8) + k / 3) % 1.0;
        if (inward) cycle = 1 - cycle;
        final rr = coreR * (1.15 + cycle * 0.9);
        c.drawCircle(
          center,
          rr,
          Paint()
            ..style = PaintingStyle.stroke
            ..strokeWidth = 1.2
            ..color = overlay.withValues(
              alpha: strength * 0.5 * (inward ? cycle : (1 - cycle)),
            ),
        );
      }
    }
  }

  @override
  bool shouldRepaint(covariant _OrbPainter old) =>
      old.time != time ||
      old.params != params ||
      old.hues != hues ||
      old.hot != hot ||
      old.tint != tint ||
      old.progress != progress ||
      old.reducedEffects != reducedEffects ||
      old.program != program ||
      old.variant != variant ||
      old.field != field ||
      old.poke != poke ||
      old.gusts.length != gusts.length;
}
