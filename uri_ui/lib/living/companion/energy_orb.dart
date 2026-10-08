import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';

import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import 'companion_state.dart';
import 'effects_settings.dart';
import 'orb_shader.dart';

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
/// frame is one pass over [_particleCount] points with no mutable
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
  late final _ParticleField _field = _ParticleField(seed: widget.seed);

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
    if (oldWidget.animate != widget.animate) _syncTicker();
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
    _ticker.dispose();
    _stateTween.dispose();
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
    final time = _elapsed.inMicroseconds / 1e6;

    return Semantics(
      label: widget.semanticsLabel ?? 'URI companion: ${widget.state.label}',
      liveRegion: true,
      child: RepaintBoundary(
        child: SizedBox(
          width: widget.size,
          height: widget.size,
          child: CustomPaint(
            painter: _OrbPainter(
              time: time,
              params: params,
              glow: glow,
              ink: colors.ink,
              canvas: colors.canvas,
              progress:
                  widget.state == CompanionState.working ? widget.progress : null,
              reducedEffects: effects.reducedEffects,
              program: effects.reducedEffects ? null : _program,
              field: _field,
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

const int _particleCount = 88;

/// Fixed per-particle seeds. Positions are computed from time each
/// frame; nothing here changes after construction.
class _ParticleField {
  _ParticleField({required int seed}) {
    final rnd = math.Random(seed);
    for (var i = 0; i < _particleCount; i++) {
      baseAngle.add(rnd.nextDouble() * math.pi * 2);
      tilt.add((rnd.nextDouble() - 0.5) * math.pi * 0.9);
      speed.add((0.5 + rnd.nextDouble()) * (rnd.nextBool() ? 1 : -1));
      radiusJitter.add(0.82 + rnd.nextDouble() * 0.36);
      size.add(0.6 + rnd.nextDouble() * 1.6);
      phase.add(rnd.nextDouble() * math.pi * 2);
    }
  }

  final List<double> baseAngle = [];
  final List<double> tilt = [];
  final List<double> speed = [];
  final List<double> radiusJitter = [];
  final List<double> size = [];
  final List<double> phase = [];
}

class _OrbPainter extends CustomPainter {
  _OrbPainter({
    required this.time,
    required this.params,
    required this.glow,
    required this.ink,
    required this.canvas,
    required this.progress,
    required this.reducedEffects,
    required this.program,
    required this.field,
  });

  final double time;
  final OrbParams params;
  final Color glow;
  final Color ink;
  final Color canvas;
  final double? progress;
  final bool reducedEffects;
  final ui.FragmentProgram? program;
  final _ParticleField field;

  @override
  void paint(Canvas c, Size size) {
    final center = size.center(Offset.zero);
    final outer = size.shortestSide / 2;
    final breath = 1 +
        params.breathDepth * math.sin(time * params.breathRate * math.pi * 2);
    final coreR = outer * 0.30 * params.coreScale * breath;

    _paintHalo(c, center, outer, coreR);
    _paintParticles(c, center, coreR, behind: true);
    _paintCore(c, center, coreR);
    _paintParticles(c, center, coreR, behind: false);
    _paintStateOverlays(c, center, coreR, outer);
  }

  void _paintHalo(Canvas c, Offset center, double outer, double coreR) {
    final haloR = coreR * 2.4;
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

  void _paintCore(Canvas c, Offset center, double coreR) {
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
        ..setFloat(8, 1.0);
      // The shader samples FlutterFragCoord in canvas space; translate
      // so the sphere's uv origin is the rect's top-left.
      c.save();
      c.translate(rect.left, rect.top);
      c.drawCircle(
        Offset(coreR, coreR),
        coreR,
        Paint()..shader = shader,
      );
      c.restore();
    } else {
      final bright = Color.lerp(glow, Colors.white, 0.7)!;
      final wobble = 0.5 + 0.5 * math.sin(time * (0.6 + params.energy * 2.5));
      final core = Paint()
        ..shader = ui.Gradient.radial(
          center.translate(-coreR * 0.18, -coreR * 0.22),
          coreR * 1.15,
          [
            bright.withValues(alpha: 0.95),
            Color.lerp(glow, bright, 0.25 + 0.25 * wobble)!
                .withValues(alpha: 0.9),
            glow.withValues(alpha: 0.75),
            Color.lerp(glow, canvas, 0.55)!.withValues(alpha: 0.9),
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
        ..color = Colors.white.withValues(alpha: 0.25 * params.turbulence);
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

    // Limb: thin rim so the sphere reads as a solid.
    final rim = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0
      ..color = Color.lerp(glow, Colors.white, 0.4)!
          .withValues(alpha: 0.35 + params.energy * 0.3);
    if (!reducedEffects) {
      rim.maskFilter = const ui.MaskFilter.blur(ui.BlurStyle.normal, 1.2);
    }
    c.drawCircle(center, coreR, rim);
  }

  void _paintParticles(Canvas c, Offset center, double coreR,
      {required bool behind}) {
    final paint = Paint();
    for (var i = 0; i < _particleCount; i++) {
      final a = field.baseAngle[i] +
          time * field.speed[i] * params.particleSpeed * 0.8;
      final spread = params.particleSpread * field.radiusJitter[i];
      final wob = math.sin(time * 1.3 + field.phase[i]) *
          (0.03 + params.turbulence * 0.12);
      final r = coreR * (spread + wob);
      // Tilted elliptical orbit: y is foreshortened by the tilt.
      final tilt = field.tilt[i];
      final x = math.cos(a) * r;
      final y = math.sin(a) * r * math.cos(tilt);
      final depth = math.sin(a) * math.sin(tilt); // -1 behind .. 1 front
      final isBehind = depth < 0;
      if (isBehind != behind) continue;
      final inside = math.sqrt(x * x + y * y) < coreR;
      if (behind && inside) continue; // occluded by the core
      final dAlpha = 0.45 + 0.55 * (depth + 1) / 2;
      final alpha = (params.particleAlpha * dAlpha).clamp(0.0, 1.0);
      paint.color = Color.lerp(glow, Colors.white, 0.35 * dAlpha)!
          .withValues(alpha: alpha);
      final ps = field.size[i] * (0.7 + 0.5 * (depth + 1) / 2) *
          (coreR / 60).clamp(0.6, 2.2);
      c.drawCircle(center + Offset(x, y), ps, paint);
    }
  }

  void _paintStateOverlays(
      Canvas c, Offset center, double coreR, double outer) {
    // Approval / error: pulsing attention ring just outside the halo core.
    if (params.ringStrength > 0.01) {
      final pulse = 0.5 + 0.5 * math.sin(time * math.pi * 1.6);
      final ringR = coreR * (1.55 + pulse * 0.08);
      final ring = Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.6
        ..color = glow.withValues(
            alpha: params.ringStrength * (0.35 + 0.45 * pulse));
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
        c.drawArc(arcRect, start + math.pi, math.pi * 0.25, false,
            arc..color = glow.withValues(alpha: 0.4 * params.orbitArc));
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
              alpha: strength * 0.5 * (inward ? cycle : (1 - cycle)));
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
      old.program != program;
}
