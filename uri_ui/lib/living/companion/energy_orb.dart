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
}

extension OrbVariantLabel on OrbVariant {
  String get label => switch (this) {
    OrbVariant.nebula => 'Nebula',
    OrbVariant.halo => 'Halo',
    OrbVariant.swarm => 'Swarm',
    OrbVariant.glass => 'Glass',
    OrbVariant.flow => 'Flow',
    OrbVariant.mesh => 'Mesh',
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
    OrbVariant.nebula => 88,
    OrbVariant.halo => 96,
    OrbVariant.swarm => 420,
    OrbVariant.glass => 40,
    OrbVariant.flow => 150,
    OrbVariant.mesh => 72,
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
    final glass = UriGlass.of(context);
    final effects = EffectsSettings.of(context);
    final params = _current;
    final tint = _tintFor(widget.state, colors);
    final glow = Color.lerp(glass.glow, tint, params.tintMix)!;
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
                  glow: glow,
                  specular: glass.specular,
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

class _OrbPainter extends CustomPainter {
  _OrbPainter({
    required this.time,
    required this.params,
    required this.glow,
    required this.specular,
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
  final Color glow;

  /// Brightest light (theme token), used for highlights instead of a literal.
  final Color specular;
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
        p += d / dist * strength * 0.35; // scatter away from the path
      }
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
      case OrbVariant.nebula:
        _paintHalo(c, center, coreR, 2.4);
        _paintShellParticles(c, center, coreR, behind: true);
        _paintPlasmaCore(c, center, coreR, alpha: 1);
        _paintLimb(c, center, coreR);
        _paintShellParticles(c, center, coreR, behind: false);
      case OrbVariant.halo:
        final r = coreR * 0.72;
        _paintHalo(c, center, coreR, 2.2);
        _paintRingBand(c, center, coreR, behind: true);
        _paintPlasmaCore(c, center, r, alpha: 1);
        _paintLimb(c, center, r);
        _paintRingBand(c, center, coreR, behind: false);
      case OrbVariant.swarm:
        _paintHalo(c, center, coreR, 2.0);
        _paintSwarm(c, center, coreR);
      case OrbVariant.glass:
        _paintHalo(c, center, coreR, 2.2);
        _paintShellParticles(c, center, coreR, behind: true, alphaScale: 0.45);
        _paintGlassSphere(c, center, coreR);
        _paintShellParticles(c, center, coreR, behind: false, alphaScale: 0.45);
      case OrbVariant.flow:
        _paintHalo(c, center, coreR, 2.6);
        _paintFlowParticles(c, center, coreR, behind: true);
        _paintPlasmaCore(c, center, coreR, alpha: 1);
        _paintLimb(c, center, coreR);
        _paintFlowParticles(c, center, coreR, behind: false);
      case OrbVariant.mesh:
        _paintHalo(c, center, coreR, 2.0);
        _paintMesh(c, center, coreR);
    }
    _paintStateOverlays(c, center, coreR, outer);
  }

  // ---------------------------------------------------------------- common

  void _paintHalo(Canvas c, Offset center, double coreR, double scale) {
    final haloR = coreR * scale;
    final haloAlpha = 0.10 + params.energy * 0.22;
    final halo = Paint()
      ..shader = ui.Gradient.radial(
        center,
        haloR,
        [
          glow.withValues(alpha: haloAlpha),
          glow.withValues(alpha: haloAlpha * 0.35),
          glow.withValues(alpha: 0),
        ],
        const [0.0, 0.45, 1.0],
      );
    c.drawCircle(center, haloR, halo);
  }

  /// The plasma body: runtime shader when available, gradient otherwise.
  void _paintPlasmaCore(
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
        ..setFloat(8, alpha);
      // The shader samples FlutterFragCoord in canvas space; translate
      // so the sphere's uv origin is the rect's top-left.
      c.save();
      c.translate(rect.left, rect.top);
      c.drawCircle(Offset(coreR, coreR), coreR, Paint()..shader = shader);
      c.restore();
    } else {
      final bright = Color.lerp(glow, specular, 0.7)!;
      final wobble = 0.5 + 0.5 * math.sin(time * (0.6 + params.energy * 2.5));
      final core = Paint()
        ..shader = ui.Gradient.radial(
          center.translate(-coreR * 0.18, -coreR * 0.22),
          coreR * 1.15,
          [
            bright.withValues(alpha: 0.95 * alpha),
            Color.lerp(
              glow,
              bright,
              0.25 + 0.25 * wobble,
            )!.withValues(alpha: 0.9 * alpha),
            glow.withValues(alpha: 0.75 * alpha),
            Color.lerp(glow, canvas, 0.55)!.withValues(alpha: 0.9 * alpha),
          ],
          const [0.0, 0.28, 0.62, 1.0],
        );
      c.drawCircle(center, coreR, core);
    }

    // Inner turbulence streaks (error) / calm sheen: a few arcs.
    if (params.turbulence > 0.05) {
      final streak = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.2
        ..color = specular.withValues(alpha: 0.25 * params.turbulence);
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

  void _paintLimb(Canvas c, Offset center, double r) {
    final rim = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0
      ..color = Color.lerp(
        glow,
        specular,
        0.4,
      )!.withValues(alpha: 0.35 + params.energy * 0.3);
    if (!reducedEffects) {
      rim.maskFilter = const ui.MaskFilter.blur(ui.BlurStyle.normal, 1.2);
    }
    c.drawCircle(center, r, rim);
  }

  /// Tilted elliptical orbits around the body (nebula, glass).
  void _paintShellParticles(
    Canvas c,
    Offset center,
    double coreR, {
    required bool behind,
    double alphaScale = 1,
  }) {
    final paint = Paint();
    for (var i = 0; i < field.count; i++) {
      final a =
          field.baseAngle[i] +
          time * field.speed[i] * params.particleSpeed * 0.8;
      final spread = params.particleSpread * field.radiusJitter[i];
      final wob =
          math.sin(time * 1.3 + field.phase[i]) *
          (0.03 + params.turbulence * 0.12);
      final r = coreR * (spread + wob);
      final tilt = field.tilt[i];
      final x = math.cos(a) * r;
      final y = math.sin(a) * r * math.cos(tilt);
      final depth = math.sin(a) * math.sin(tilt); // -1 behind .. 1 front
      final isBehind = depth < 0;
      if (isBehind != behind) continue;
      final inside = math.sqrt(x * x + y * y) < coreR;
      if (behind && inside) continue; // occluded by the core
      final dAlpha = 0.45 + 0.55 * (depth + 1) / 2;
      final alpha = (params.particleAlpha * dAlpha * alphaScale).clamp(
        0.0,
        1.0,
      );
      paint.color = Color.lerp(
        glow,
        specular,
        0.35 * dAlpha,
      )!.withValues(alpha: alpha);
      final ps =
          field.size[i] *
          (0.7 + 0.5 * (depth + 1) / 2) *
          (coreR / 60).clamp(0.6, 2.2);
      c.drawCircle(_place(center, x, y, coreR), ps, paint);
    }
  }

  // ------------------------------------------------------------------ flow

  /// Emission: a particle's life is a phase p in 0..1 that advances with
  /// time; it is born just inside the limb, travels outward along a
  /// tilted spiral, fades in then out, shrinks, and is reborn. Thinking
  /// and working raise the emission rate; approval holds the stream
  /// nearly still; error scatters it.
  void _paintFlowParticles(
    Canvas c,
    Offset center,
    double coreR, {
    required bool behind,
  }) {
    final paint = Paint();
    final rate = 0.08 + params.particleSpeed * 0.16; // lives per second
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
      final fade = math.sin(life * math.pi); // in then out
      final near = (depth + 1) / 2;
      final alpha = (params.particleAlpha * fade * (0.45 + 0.55 * near)).clamp(
        0.0,
        1.0,
      );
      paint.color = Color.lerp(
        Color.lerp(glow, specular, 0.6)!,
        glow,
        life,
      )!.withValues(alpha: alpha);
      final ps =
          field.size[i] *
          (1.3 - life * 0.9) *
          (0.7 + 0.5 * near) *
          (coreR / 60).clamp(0.6, 2.2);
      c.drawCircle(_place(center, x, y, coreR), ps, paint);
    }
  }

  // ------------------------------------------------------------------ mesh

  /// Nodes on a sphere (Fibonacci lattice, so they are evenly spread),
  /// rotated about a tilted axis; edges join nodes closer than a
  /// threshold. Depth sorts brightness; edges behind the sphere are dim.
  void _paintMesh(Canvas c, Offset center, double coreR) {
    final n = field.count;
    final r = coreR * 1.25 * (0.85 + params.particleSpread * 0.15);
    final rot = time * (0.12 + params.particleSpeed * 0.18);
    const tiltX = 0.42; // axis tilt
    final pts = List<Offset>.filled(n, Offset.zero);
    final depth = List<double>.filled(n, 0);
    const golden = 2.399963229728653; // golden angle
    for (var i = 0; i < n; i++) {
      final yUnit = 1 - (i + 0.5) * 2 / n; // -1..1
      final ring = math.sqrt(1 - yUnit * yUnit);
      final theta = i * golden + rot;
      var x = math.cos(theta) * ring;
      var z = math.sin(theta) * ring;
      var y = yUnit;
      // tilt about x axis
      final y2 = y * math.cos(tiltX) - z * math.sin(tiltX);
      final z2 = y * math.sin(tiltX) + z * math.cos(tiltX);
      y = y2;
      z = z2;
      final jitter =
          math.sin(time * 1.1 + field.phase[i]) *
          (0.01 + params.turbulence * 0.08);
      pts[i] = _place(
        center,
        x * r * (1 + jitter),
        y * r * (1 + jitter),
        coreR,
      );
      depth[i] = z; // -1 back .. 1 front
    }
    // Faint inner glow so the lattice reads as a body.
    c.drawCircle(
      center,
      r,
      Paint()
        ..shader = ui.Gradient.radial(center, r, [
          glow.withValues(alpha: 0.12 + params.energy * 0.18),
          glow.withValues(alpha: 0.02),
        ]),
    );
    // Edges: nearest neighbours under a threshold (O(n^2), n=72).
    final maxD = r * 0.62;
    final broken = params.turbulence; // error breaks some edges
    final edge = Paint()..strokeWidth = 1;
    for (var i = 0; i < n; i++) {
      for (var j = i + 1; j < n; j++) {
        final d = (pts[i] - pts[j]).distance;
        if (d > maxD) continue;
        if (broken > 0.3 && ((i * 31 + j * 17) % 7) < broken * 7) continue;
        final front = (depth[i] + depth[j]) / 2;
        final near = (front + 1) / 2;
        final w = 1 - d / maxD;
        edge.color = glow.withValues(
          alpha: (0.08 + 0.55 * near * w) * (0.5 + params.energy * 0.5),
        );
        c.drawLine(pts[i], pts[j], edge);
      }
    }
    // Nodes.
    final node = Paint();
    for (var i = 0; i < n; i++) {
      final near = (depth[i] + 1) / 2;
      node.color = Color.lerp(glow, specular, 0.5 * near)!.withValues(
        alpha: (0.25 + 0.75 * near) * params.particleAlpha.clamp(0.4, 1.0),
      );
      final pulse = 0.5 + 0.5 * math.sin(time * 2.0 + field.phase[i]);
      c.drawCircle(
        pts[i],
        (1.2 + 1.8 * near + pulse * params.energy) *
            (coreR / 60).clamp(0.6, 2.2),
        node,
      );
    }
  }

  // ------------------------------------------------------------------ halo

  /// One wide luminous ring, tilted like the wordmark's orbit, with the
  /// particles riding in its band. Drawn in two halves so the core
  /// occludes the far side.
  void _paintRingBand(
    Canvas c,
    Offset center,
    double coreR, {
    required bool behind,
  }) {
    final ringR = coreR * 1.45 * (0.9 + params.particleSpread * 0.1);
    const tiltY = 0.38;
    final rect = Rect.fromCenter(
      center: center,
      width: ringR * 2,
      height: ringR * 2 * tiltY,
    );
    // Far half: angles with sin(a) < 0 (upper arc), near half: lower arc.
    final start = behind ? math.pi : 0.0;
    final band = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = coreR * 0.16
      ..shader = ui.Gradient.sweep(
        center,
        [
          glow.withValues(alpha: 0.05),
          glow.withValues(alpha: 0.55 + params.energy * 0.3),
          Color.lerp(glow, specular, 0.5)!.withValues(alpha: 0.9),
          glow.withValues(alpha: 0.55 + params.energy * 0.3),
          glow.withValues(alpha: 0.05),
        ],
        const [0.0, 0.3, 0.5, 0.7, 1.0],
        TileMode.repeated,
        time * (0.3 + params.particleSpeed * 0.5),
        time * (0.3 + params.particleSpeed * 0.5) + math.pi * 2,
      );
    if (!reducedEffects) {
      band.maskFilter = ui.MaskFilter.blur(ui.BlurStyle.normal, coreR * 0.05);
    }
    c.drawArc(rect, start, math.pi, false, band..color = specular);
    final thin = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0
      ..color = Color.lerp(glow, specular, 0.6)!.withValues(alpha: 0.7);
    c.drawArc(rect, start, math.pi, false, thin);

    // Particles in the band.
    final paint = Paint();
    for (var i = 0; i < field.count; i++) {
      final a =
          field.baseAngle[i] +
          time * field.speed[i] * params.particleSpeed * 0.6;
      final isBehind = math.sin(a) < 0;
      if (isBehind != behind) continue;
      final r = ringR * (0.92 + 0.16 * (field.radiusJitter[i] - 0.82) / 0.36);
      final jitter =
          math.sin(time * 1.7 + field.phase[i]) *
          coreR *
          0.04 *
          (1 + params.turbulence * 3);
      final p = _place(
        center,
        math.cos(a) * r,
        math.sin(a) * r * tiltY + jitter,
        coreR,
      );
      final near = (math.sin(a) + 1) / 2;
      paint.color = Color.lerp(glow, specular, 0.4 * near)!.withValues(
        alpha: (params.particleAlpha * (0.4 + 0.6 * near)).clamp(0.0, 1.0),
      );
      c.drawCircle(
        p,
        field.size[i] * 0.9 * (coreR / 60).clamp(0.6, 2.2),
        paint,
      );
    }
  }

  // ----------------------------------------------------------------- swarm

  /// A sphere made only of particles; cohesion comes from energy and a
  /// faint central glow. Thinking tightens it, error scatters it.
  void _paintSwarm(Canvas c, Offset center, double coreR) {
    final glowPaint = Paint()
      ..shader = ui.Gradient.radial(
        center,
        coreR * 1.1,
        [
          Color.lerp(
            glow,
            specular,
            0.5,
          )!.withValues(alpha: 0.22 + params.energy * 0.25),
          glow.withValues(alpha: 0.10),
          glow.withValues(alpha: 0),
        ],
        const [0.0, 0.5, 1.0],
      );
    c.drawCircle(center, coreR * 1.1, glowPaint);

    final paint = Paint();
    // Gather / disperse: the swarm breathes with the state's breath rate,
    // tightening on thinking (small spread) and loosening on error.
    final gather = 0.5 + 0.5 * math.sin(time * params.breathRate * math.pi * 2);
    final cohesion = (1.0 - params.turbulence * 0.5) * (0.9 + 0.2 * gather);
    final bodyR = coreR * 1.25 * (0.75 + params.particleSpread * 0.25);
    for (var i = 0; i < field.count; i++) {
      final a =
          field.baseAngle[i] +
          time * field.speed[i] * params.particleSpeed * 0.5;
      final tilt = field.tilt[i];
      final vr =
          field.volume[i] * bodyR * cohesion +
          math.sin(time * 0.9 + field.phase[i]) * coreR * 0.05;
      final x = math.cos(a) * vr;
      final y = math.sin(a) * vr * math.cos(tilt);
      final depth = math.sin(a) * math.sin(tilt);
      final near = (depth + 1) / 2;
      final alpha = (params.particleAlpha * (0.35 + 0.65 * near)).clamp(
        0.0,
        1.0,
      );
      paint.color = Color.lerp(
        glow,
        specular,
        0.45 * near,
      )!.withValues(alpha: alpha);
      final pos = _place(center, x, y, coreR);
      final ps =
          field.size[i] * (0.55 + 0.6 * near) * (coreR / 60).clamp(0.6, 2.2);
      // Soft body: a faint wide disc under a small bright one.
      c.drawCircle(
        pos,
        ps * 3.4,
        paint..color = paint.color.withValues(alpha: alpha * 0.14),
      );
      c.drawCircle(
        pos,
        ps,
        paint..color = paint.color.withValues(alpha: alpha),
      );
    }
  }

  // ----------------------------------------------------------------- glass

  /// Frosted sphere: dark glass body, dim inner swirl, specular highlight,
  /// lit lower rim.
  void _paintGlassSphere(Canvas c, Offset center, double coreR) {
    final rect = Rect.fromCircle(center: center, radius: coreR);
    // Body.
    c.drawCircle(
      center,
      coreR,
      Paint()
        ..shader = ui.Gradient.radial(
          center.translate(-coreR * 0.25, -coreR * 0.3),
          coreR * 1.4,
          [
            Color.lerp(glow, canvas, 0.55)!.withValues(alpha: 0.95),
            Color.lerp(glow, canvas, 0.78)!.withValues(alpha: 0.95),
            Color.lerp(glow, canvas, 0.9)!.withValues(alpha: 0.98),
          ],
          const [0.0, 0.6, 1.0],
        ),
    );
    // Inner swirl, dim, clipped to the sphere.
    c.save();
    c.clipPath(Path()..addOval(rect.deflate(coreR * 0.08)));
    _paintPlasmaCore(c, center, coreR * 0.92, alpha: 0.42);
    c.restore();
    // Lower rim light.
    final rimLight = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = coreR * 0.08
      ..shader = ui.Gradient.sweep(
        center,
        [
          glow.withValues(alpha: 0),
          glow.withValues(alpha: 0.75),
          glow.withValues(alpha: 0),
        ],
        const [0.15, 0.3, 0.45],
      );
    if (!reducedEffects) {
      rimLight.maskFilter = ui.MaskFilter.blur(
        ui.BlurStyle.normal,
        coreR * 0.06,
      );
    }
    c.drawCircle(center, coreR * 0.96, rimLight);
    // Specular highlight.
    final spec = Paint()
      ..shader = ui.Gradient.radial(
        center.translate(-coreR * 0.38, -coreR * 0.42),
        coreR * 0.38,
        [
          specular.withValues(alpha: 0.55),
          specular.withValues(alpha: 0.12),
          specular.withValues(alpha: 0),
        ],
        const [0.0, 0.45, 1.0],
      );
    c.drawOval(
      Rect.fromCenter(
        center: center.translate(-coreR * 0.38, -coreR * 0.42),
        width: coreR * 0.75,
        height: coreR * 0.5,
      ),
      spec,
    );
    // Thin edge.
    c.drawCircle(
      center,
      coreR,
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = specular.withValues(alpha: 0.22 + params.energy * 0.2),
    );
  }

  // --------------------------------------------------------- state overlays

  void _paintStateOverlays(
    Canvas c,
    Offset center,
    double coreR,
    double outer,
  ) {
    // Approval / error: pulsing attention ring just outside the halo core.
    if (params.ringStrength > 0.01) {
      final pulse = 0.5 + 0.5 * math.sin(time * math.pi * 1.6);
      final ringR = coreR * (1.55 + pulse * 0.08);
      final ring = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6
        ..color = glow.withValues(
          alpha: params.ringStrength * (0.35 + 0.45 * pulse),
        );
      c.drawCircle(center, ringR, ring);
      final dots = Paint()..color = glow.withValues(alpha: params.ringStrength);
      for (var i = 0; i < 3; i++) {
        final a = -math.pi / 2 + i * (math.pi * 2 / 3) + time * 0.4;
        c.drawCircle(
          center + Offset(math.cos(a), math.sin(a)) * ringR,
          2.2,
          dots,
        );
      }
    }

    // Working: rotating orbit arc + optional progress arc.
    if (params.orbitArc > 0.01) {
      final arcRect = Rect.fromCircle(center: center, radius: coreR * 1.62);
      final arc = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.2
        ..strokeCap = StrokeCap.round
        ..color = glow.withValues(alpha: 0.85 * params.orbitArc);
      final p = progress;
      if (p == null) {
        final start = time * 2.4;
        c.drawArc(arcRect, start, math.pi * 0.55, false, arc);
        c.drawArc(
          arcRect,
          start + math.pi,
          math.pi * 0.25,
          false,
          arc..color = glow.withValues(alpha: 0.4 * params.orbitArc),
        );
      } else {
        final track = Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2.2
          ..color = glow.withValues(alpha: 0.18 * params.orbitArc);
        c.drawArc(arcRect, 0, math.pi * 2, false, track);
        c.drawArc(
          arcRect,
          -math.pi / 2,
          math.pi * 2 * p.clamp(0.0, 1.0),
          false,
          arc,
        );
      }
    }

    // Poke: a quick burst ring (click response).
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
            specular,
            0.4,
          )!.withValues(alpha: (1 - poke) * 0.8),
      );
    }

    // Success: a bloom ring expanding outward and fading.
    if (params.bloom > 0.01) {
      final cycle = (time * 0.9) % 1.0;
      final bloomR = coreR * (1.1 + cycle * 1.4);
      final bloom = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 2.5 * (1 - cycle) + 0.5
        ..color = glow.withValues(alpha: params.bloom * (1 - cycle) * 0.7);
      c.drawCircle(center, bloomR, bloom);
    }

    // Speaking (outward ripples) / listening (inward ripples).
    if (params.rippleStrength.abs() > 0.01) {
      final strength = params.rippleStrength.abs();
      final inward = params.rippleStrength < 0;
      for (var k = 0; k < 3; k++) {
        var cycle = ((time * 0.8) + k / 3) % 1.0;
        if (inward) cycle = 1 - cycle;
        final rr = coreR * (1.15 + cycle * 0.9);
        final rp = Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.2
          ..color = glow.withValues(
            alpha: strength * 0.5 * (inward ? cycle : (1 - cycle)),
          );
        c.drawCircle(center, rr, rp);
      }
    }
  }

  @override
  bool shouldRepaint(covariant _OrbPainter old) =>
      old.time != time ||
      old.params != params ||
      old.glow != glow ||
      old.progress != progress ||
      old.reducedEffects != reducedEffects ||
      old.program != program ||
      old.variant != variant ||
      old.field != field ||
      old.specular != specular ||
      old.poke != poke ||
      old.gusts.length != gusts.length;
}
