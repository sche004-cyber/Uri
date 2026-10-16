import 'dart:math' as math;
import 'dart:ui' as ui show FragmentProgram, FragmentShader;

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import '../../theme/uri_theme.dart';
import '../companion/effects_settings.dart';
import '../companion/frame_clock.dart';

/// The shared voice waveform: one horizontal oval of soft flowing bands.
///
/// It is used for the user speaking and for URI speaking, and it is the same
/// widget both times. It takes no speaker argument on purpose: there is
/// nothing it could do differently with one. What changes between the two is
/// only the level it is given and the transcript shown under it.
///
/// Colours come from the active theme's [UriColors] tokens (accent,
/// accentInk, ink), so the waveform follows the selected companion's palette
/// and never introduces colours of its own.

/// Width to height of the oval.
const double kVoiceWaveformAspect = 3.4;

const String kVoiceWaveformAsset = 'shaders/voice_waveform.frag';

/// Loads the waveform program once. A failure degrades to `null` and the
/// widget draws its static fallback; it never throws into the UI.
class VoiceWaveformShader {
  VoiceWaveformShader._();

  static Future<ui.FragmentProgram?>? _loading;
  static ui.FragmentProgram? _program;
  static String? failure;

  static ui.FragmentProgram? get programIfLoaded => _program;

  static Future<ui.FragmentProgram?> load() => _loading ??= () async {
    try {
      return _program = await ui.FragmentProgram.fromAsset(kVoiceWaveformAsset);
    } catch (error) {
      failure = error.toString();
      return null;
    }
  }();

  @visibleForTesting
  static void reset() {
    _loading = null;
    _program = null;
    failure = null;
  }
}

/// One deterministic frame. The same inputs produce the same pixels, which is
/// what lets the capture harness compare the user's and URI's waveforms.
class VoiceWaveformFrame extends StatefulWidget {
  const VoiceWaveformFrame({
    super.key,
    required this.seconds,
    required this.level,
    required this.flux,
    this.presence = 1,
    this.motion = 1,
    this.bars = false,
  });

  final double seconds;
  final double level;
  final double flux;
  final double presence;
  final double motion;
  final bool bars;

  @override
  State<VoiceWaveformFrame> createState() => _VoiceWaveformFrameState();
}

class _VoiceWaveformFrameState extends State<VoiceWaveformFrame> {
  ui.FragmentShader? _shader;

  @override
  void initState() {
    super.initState();
    final loaded = VoiceWaveformShader.programIfLoaded;
    if (loaded != null) {
      _shader = loaded.fragmentShader();
    } else {
      VoiceWaveformShader.load().then((p) {
        if (!mounted || p == null) return;
        setState(() => _shader = p.fragmentShader());
      });
    }
  }

  @override
  void dispose() {
    _shader?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    if (widget.bars) {
      return CustomPaint(
        size: Size.infinite,
        painter: VoiceBarsPainter(widget.level, c.accentSoft, widget.presence),
      );
    }
    final shader = _shader;
    if (shader == null || EffectsSettings.of(context).reducedEffects) {
      return CustomPaint(
        size: Size.infinite,
        painter: VoiceWaveformFallbackPainter(
          level: widget.level,
          presence: widget.presence,
          line: c.accentInk,
          rim: c.accent,
        ),
      );
    }
    return CustomPaint(
      size: Size.infinite,
      painter: VoiceWaveformPainter(
        shader: shader,
        seconds: widget.seconds,
        level: widget.level,
        flux: widget.flux,
        presence: widget.presence,
        motion: widget.motion,
        colA: c.accent,
        colB: c.accentInk,
        colC: c.ink,
      ),
    );
  }
}

/// The live waveform. Reads a level and a flux that a [VoiceSessionController]
/// keeps current and glides towards them every frame, so 50 Hz audio blocks
/// render as continuous motion at any display rate.
class VoiceWaveform extends StatefulWidget {
  const VoiceWaveform({
    super.key,
    required this.level,
    required this.flux,
    this.presence = 1,
    this.bars = false,
  });

  final ValueListenable<double> level;
  final ValueListenable<double> flux;
  final double presence;
  final bool bars;

  @override
  State<VoiceWaveform> createState() => _VoiceWaveformState();
}

class _VoiceWaveformState extends State<VoiceWaveform>
    with SingleTickerProviderStateMixin, CompanionFrameDriver {
  double _seconds = 0;
  double _level = 0;
  double _flux = 0;
  bool _reduced = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _reduced = EffectsSettings.of(context).reducedMotion;
  }

  // Runs on the same clock as the companion, so a frame-rate cap applies to
  // both and their frames coincide.
  @override
  void onCompanionFrame(double seconds, double dt) {
    final reduced = _reduced;
    setState(() {
      _seconds = seconds;
      _level = voiceGlide(_level, widget.level.value, dt, reduced: reduced);
      _flux = voiceGlide(
        _flux,
        reduced ? 0 : widget.flux.value,
        dt,
        reduced: reduced,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final reduced = EffectsSettings.of(context).reducedMotion;
    return VoiceWaveformFrame(
      seconds: _seconds,
      level: _level,
      flux: _flux,
      presence: widget.presence,
      motion: reduced ? 0 : 1,
      bars: widget.bars,
    );
  }
}

/// Per-frame smoothing toward the controller's value, by real elapsed time.
/// Reduced motion uses a much slower follower: the waveform still shows that
/// someone is speaking and how loudly, without rapid movement.
double voiceGlide(
  double current,
  double target,
  double dt, {
  bool reduced = false,
}) {
  final tau = reduced ? 0.45 : 0.06;
  return current + (target - current) * (1 - math.exp(-dt / tau));
}

class VoiceWaveformPainter extends CustomPainter {
  VoiceWaveformPainter({
    required this.shader,
    required this.seconds,
    required this.level,
    required this.flux,
    required this.presence,
    required this.motion,
    required this.colA,
    required this.colB,
    required this.colC,
  });

  final ui.FragmentShader shader;
  final double seconds;
  final double level;
  final double flux;
  final double presence;
  final double motion;
  final Color colA;
  final Color colB;
  final Color colC;

  /// The uniform vector, in the order `voice_waveform.frag` declares. There is
  /// no speaker in it: that absence is what guarantees identical treatment.
  static List<double> uniformsFor({
    required Size size,
    required double seconds,
    required double level,
    required double flux,
    required double presence,
    required double motion,
    required Color colA,
    required Color colB,
    required Color colC,
  }) => <double>[
    size.width,
    size.height,
    seconds,
    level,
    flux,
    presence,
    motion,
    colA.r,
    colA.g,
    colA.b,
    colB.r,
    colB.g,
    colB.b,
    colC.r,
    colC.g,
    colC.b,
  ];

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final v = uniformsFor(
      size: size,
      seconds: seconds,
      level: level,
      flux: flux,
      presence: presence,
      motion: motion,
      colA: colA,
      colB: colB,
      colC: colC,
    );
    for (var i = 0; i < v.length; i++) {
      shader.setFloat(i, v[i]);
    }
    canvas.drawRect(Offset.zero & size, Paint()..shader = shader);
  }

  @override
  bool shouldRepaint(VoiceWaveformPainter old) =>
      old.seconds != seconds ||
      old.level != level ||
      old.flux != flux ||
      old.presence != presence ||
      old.motion != motion ||
      old.colA != colA ||
      old.colB != colB ||
      old.colC != colC ||
      !identical(old.shader, shader);
}

/// Reduced effects (or no shader support): the same oval and a centre line
/// whose thickness follows the level. Still speaker-agnostic, still driven by
/// the real level, just without the shader.
class VoiceWaveformFallbackPainter extends CustomPainter {
  VoiceWaveformFallbackPainter({
    required this.level,
    required this.presence,
    required this.line,
    required this.rim,
  });

  final double level;
  final double presence;
  final Color line;
  final Color rim;

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty || presence <= 0) return;
    final r = Offset.zero & size;
    canvas.drawOval(
      r.deflate(1),
      Paint()
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1
        ..color = rim.withValues(alpha: 0.22 * presence),
    );
    // A single line whose thickness and length follow the level: the same
    // information as the shader bands, with no movement beyond the level.
    final l = level.clamp(0.0, 1.0);
    final h = 1.5 + l * size.height * 0.06;
    canvas.drawRRect(
      RRect.fromRectAndRadius(
        Rect.fromCenter(
          center: r.center,
          width: size.width * (0.40 + 0.40 * l),
          height: h,
        ),
        Radius.circular(h / 2),
      ),
      Paint()..color = line.withValues(alpha: 0.6 * presence),
    );
  }

  @override
  bool shouldRepaint(VoiceWaveformFallbackPainter old) =>
      old.level != level ||
      old.presence != presence ||
      old.line != line ||
      old.rim != rim;
}

/// RMS-level display, not a frequency spectrum or fabricated audio recording.
/// Silent listening stays at short marks; only the real controller level grows
/// the bars. It uses the existing paced/hidden-window waveform driver.
class VoiceBarsPainter extends CustomPainter {
  const VoiceBarsPainter(this.level, this.color, this.presence);
  final double level, presence;
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    final amplitude = math.sqrt(level.clamp(0, 1));
    final paint = Paint()
      ..color = color.withValues(alpha: presence.clamp(0, 1))
      ..strokeWidth = 2
      ..strokeCap = StrokeCap.round;
    for (var i = 0; i < 33; i++) {
      final x = (i + .5) * size.width / 33;
      final envelope = math
          .pow(math.sin((i + 1) * math.pi / 34), 1.4)
          .toDouble();
      final shape = .55 + .45 * math.cos(i * 1.73).abs();
      final h = 2 + amplitude * (size.height - 2) * envelope * shape;
      canvas.drawLine(
        Offset(x, (size.height - h) / 2),
        Offset(x, (size.height + h) / 2),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(VoiceBarsPainter old) =>
      old.level != level || old.color != color || old.presence != presence;
}
