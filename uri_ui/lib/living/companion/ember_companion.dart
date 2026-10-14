import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart' show AssetBundle, rootBundle;
import 'package:flutter/widgets.dart';

import 'companion_preferences.dart' show CompanionLook;
import 'companion_state.dart';
import 'effects_settings.dart';
import 'frame_clock.dart';

/// The fire companion's animation clips, rendered in Blender
/// (`companion_art/fire/`) and shipped as WebP sprite atlases.
///
/// A clip is an expression, not a state: several [CompanionState]s share one
/// (see [EmberClips.forState]). `fierce` is rendered and available to the
/// settings preview but no operational state uses it, because an angry face
/// aimed at the user would misreport what URI is doing.
enum EmberClip {
  idle,
  joyful,
  fierce,
  depleted,
  listening,
  thinking,
  speaking,
  focused,
  concerned,
}

/// Pure mapping from authoritative state to expression. Kept free of widgets
/// so the whole table is asserted in a test.
class EmberClips {
  const EmberClips._();

  static EmberClip forState(CompanionState state) => switch (state) {
    CompanionState.unavailable => EmberClip.depleted,
    CompanionState.idle => EmberClip.idle,
    CompanionState.listening => EmberClip.listening,
    CompanionState.thinking => EmberClip.thinking,
    CompanionState.speaking => EmberClip.speaking,
    CompanionState.working => EmberClip.focused,
    // Approval reuses the attentive pose; the attention pulse and the label
    // "Needs your approval" carry the request.
    CompanionState.awaitingApproval => EmberClip.listening,
    CompanionState.success => EmberClip.joyful,
    CompanionState.error => EmberClip.concerned,
  };

  /// How long two expressions cross-fade. Leaving or entering `depleted`
  /// is slower so the fire visibly dies down or rekindles.
  static Duration fadeBetween(EmberClip from, EmberClip to) =>
      from == EmberClip.depleted || to == EmberClip.depleted
      ? const Duration(milliseconds: 1100)
      : const Duration(milliseconds: 450);
}

/// One clip's placement in its atlas, from `manifest.json`.
@immutable
class EmberClipInfo {
  const EmberClipInfo({
    required this.file,
    required this.frames,
    required this.cols,
    required this.cell,
  });

  final String file;
  final int frames;
  final int cols;
  final int cell;

  Rect frameRect(int index) {
    final i = index % frames;
    return Rect.fromLTWH(
      ((i % cols) * cell).toDouble(),
      ((i ~/ cols) * cell).toDouble(),
      cell.toDouble(),
      cell.toDouble(),
    );
  }

  /// Decoded size in bytes (RGBA).
  int get decodedBytes {
    final rows = (frames + cols - 1) ~/ cols;
    return cols * cell * rows * cell * 4;
  }
}

@immutable
class EmberManifest {
  const EmberManifest({required this.fps, required this.clips});

  final double fps;
  final Map<EmberClip, EmberClipInfo> clips;

  static const String assetDir = 'assets/companions/ember';
  static const String assetPath = '$assetDir/manifest.json';

  static EmberManifest parse(String text) {
    final j = jsonDecode(text) as Map<String, dynamic>;
    final clips = <EmberClip, EmberClipInfo>{};
    final raw = j['clips'] as Map<String, dynamic>;
    for (final c in EmberClip.values) {
      final m = raw[c.name] as Map<String, dynamic>?;
      if (m == null) continue;
      clips[c] = EmberClipInfo(
        file: m['file'] as String,
        frames: (m['frames'] as num).toInt(),
        cols: (m['cols'] as num).toInt(),
        cell: (m['cell'] as num).toInt(),
      );
    }
    return EmberManifest(fps: (j['fps'] as num).toDouble(), clips: clips);
  }
}

/// Loads the manifest once and keeps a small number of decoded atlases.
///
/// Decoding happens off the UI thread (`instantiateImageCodec`). Only the
/// clips in use stay resident: [capacity] atlases, least recently used
/// evicted and disposed. A missing or broken asset degrades to `null` (the
/// widget then shows its fallback) and never throws.
class EmberLibrary {
  EmberLibrary({AssetBundle? bundle, this.capacity = 2})
    : _bundle = bundle ?? rootBundle;

  final AssetBundle _bundle;
  final int capacity;

  static EmberLibrary shared = EmberLibrary();

  Future<EmberManifest?>? _manifest;
  EmberManifest? _manifestValue;
  final Map<EmberClip, ui.Image> _images = <EmberClip, ui.Image>{};
  final Map<EmberClip, Future<ui.Image?>> _loading =
      <EmberClip, Future<ui.Image?>>{};
  final List<EmberClip> _recent = <EmberClip>[];
  final Map<Object, Set<EmberClip>> _pins = <Object, Set<EmberClip>>{};
  String? lastFailure;

  /// Clips some widget has on screen. Never evicted.
  Set<EmberClip> get pinned => {for (final s in _pins.values) ...s};

  /// [owner] shows [clips] now (replacing what it showed before). Atlases no
  /// longer shown by anyone are evicted down to [capacity].
  void pin(Object owner, Set<EmberClip> clips) {
    _pins[owner] = Set<EmberClip>.of(clips);
    _evict();
  }

  void release(Object owner) {
    _pins.remove(owner);
    _evict();
  }

  EmberManifest? get manifestIfLoaded => _manifestValue;

  Future<EmberManifest?> manifest() => _manifest ??= () async {
    try {
      final m = EmberManifest.parse(
        await _bundle.loadString(EmberManifest.assetPath),
      );
      _manifestValue = m;
      return m;
    } catch (e) {
      lastFailure = 'manifest: $e';
      return null;
    }
  }();

  ui.Image? imageIfLoaded(EmberClip clip) {
    final img = _images[clip];
    if (img != null) _touch(clip);
    return img;
  }

  /// Decoded atlases currently held (for diagnostics and tests).
  Iterable<EmberClip> get resident => _images.keys;

  int get residentBytes {
    final m = _manifestValue;
    if (m == null) return 0;
    var n = 0;
    for (final c in _images.keys) {
      n += m.clips[c]?.decodedBytes ?? 0;
    }
    return n;
  }

  Future<ui.Image?> load(EmberClip clip) {
    final ready = _images[clip];
    if (ready != null) {
      _touch(clip);
      return Future<ui.Image?>.value(ready);
    }
    return _loading[clip] ??= _decode(clip)
        .whenComplete(() => _loading.remove(clip));
  }

  Future<ui.Image?> _decode(EmberClip clip) async {
    final m = await manifest();
    final info = m?.clips[clip];
    if (info == null) return null;
    try {
      final data = await _bundle.load('${EmberManifest.assetDir}/${info.file}');
      final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
      final frame = await codec.getNextFrame();
      codec.dispose();
      _images[clip] = frame.image;
      _touch(clip);
      _evict();
      return frame.image;
    } catch (e) {
      lastFailure = '${clip.name}: $e';
      return null;
    }
  }

  void _touch(EmberClip clip) {
    _recent
      ..remove(clip)
      ..add(clip);
  }

  /// Keeps at most [capacity] atlases, never evicting a pinned one (a clip on
  /// screen, so a cross-fade never loses its outgoing frame). Pinned clips
  /// may exceed the capacity briefly; they are trimmed when released.
  void _evict() {
    final keep = pinned;
    while (_images.length > capacity) {
      EmberClip? victim;
      for (final c in _recent) {
        if (!keep.contains(c) && _images.containsKey(c)) {
          victim = c;
          break;
        }
      }
      if (victim == null) return;
      _recent.remove(victim);
      _images.remove(victim)?.dispose();
    }
  }

  @visibleForTesting
  void reset() {
    for (final i in _images.values) {
      i.dispose();
    }
    _images.clear();
    _loading.clear();
    _recent.clear();
    _pins.clear();
    _manifest = null;
    _manifestValue = null;
    lastFailure = null;
  }
}

/// The fire companion. Plays the expression for [state], cross-fades between
/// expressions, and pulses gently while [attention] is on.
///
/// It redraws only when the visible sprite frame changes (24 per second) or a
/// fade is in progress, so a 144 Hz display does not cost 144 blits.
class EmberCompanion extends StatefulWidget {
  const EmberCompanion({
    super.key,
    this.state = CompanionState.idle,
    this.clip,
    this.attention = false,
    this.look = CompanionLook.standard,
    this.fallback,
    this.library,
  });

  final CompanionState state;

  /// Overrides the state mapping (settings preview, capture harness).
  final EmberClip? clip;
  final bool attention;
  final CompanionLook look;
  final Widget? fallback;
  final EmberLibrary? library;

  @override
  State<EmberCompanion> createState() => _EmberCompanionState();
}

class _EmberCompanionState extends State<EmberCompanion>
    with SingleTickerProviderStateMixin, CompanionFrameDriver {
  EmberLibrary get _lib => widget.library ?? EmberLibrary.shared;

  late EmberClip _current;
  EmberClip? _previous;
  double _fade = 1; // 0..1 progress into _current
  Duration _fadeLength = Duration.zero;
  double _time = 0; // the companion's own seconds (scaled by look.motion)
  double _prevTime = 0;
  double _attention = 0;
  int _shownFrame = -1;
  bool _reducedMotion = false;

  EmberClip get _target => widget.clip ?? EmberClips.forState(widget.state);

  @override
  void initState() {
    super.initState();
    _current = _target;
    _lib.pin(this, {_current});
    _request(_current);
  }

  @override
  void dispose() {
    _lib.release(this);
    super.dispose();
  }

  void _request(EmberClip clip) {
    if (_lib.imageIfLoaded(clip) != null) return;
    _lib.load(clip).then((_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void didUpdateWidget(EmberCompanion old) {
    super.didUpdateWidget(old);
    final next = _target;
    if (next != _current) {
      _previous = _current;
      _prevTime = _time;
      _fadeLength = EmberClips.fadeBetween(_current, next);
      _current = next;
      _time = 0;
      _fade = 0;
      _lib.pin(this, {_previous!, next});
      _request(next);
    }
    resumeFrames();
  }

  @override
  void didChangeDependencies() {
    _reducedMotion = EffectsSettings.of(context).reducedMotion;
    super.didChangeDependencies();
  }

  @override
  bool get wantsFrames {
    if (!_reducedMotion) return true;
    final goal = widget.attention ? 1.0 : 0.0;
    return _fade < 1 || (goal - _attention).abs() > 0.01;
  }

  int _frameAt(EmberClip clip, double t) {
    final m = _lib.manifestIfLoaded;
    final info = m?.clips[clip];
    if (m == null || info == null) return 0;
    if (_reducedMotion) return 0;
    return (t * m.fps).floor() % info.frames;
  }

  @override
  void onCompanionFrame(double seconds, double dt) {
    final speed = widget.look.motion;
    _time += dt * speed;
    _prevTime += dt * speed;
    var changed = false;
    if (_fade < 1) {
      final len = _fadeLength.inMicroseconds / 1e6;
      _fade = len <= 0 ? 1 : (_fade + dt / len).clamp(0.0, 1.0);
      if (_fade >= 1) {
        _previous = null;
        _lib.pin(this, {_current});
      }
      changed = true;
    }
    final goal = widget.attention ? 1.0 : 0.0;
    if ((goal - _attention).abs() > 0.001) {
      _attention += (goal - _attention) * (1 - math.exp(-dt / 0.35));
      if ((goal - _attention).abs() <= 0.01) _attention = goal;
      changed = true;
    }
    if (_attention > 0.001) changed = true; // the pulse moves every frame
    final f = _frameAt(_current, _time);
    if (f != _shownFrame) {
      _shownFrame = f;
      changed = true;
    }
    if (changed) setState(() {});
  }

  @override
  Widget build(BuildContext context) {
    final cur = _lib.imageIfLoaded(_current);
    final prev = _previous == null ? null : _lib.imageIfLoaded(_previous!);
    final m = _lib.manifestIfLoaded;
    if (m == null || (cur == null && prev == null)) {
      return widget.fallback ?? const SizedBox.expand();
    }
    final pulse = _reducedMotion
        ? 0.5
        : 0.5 - 0.5 * math.cos(2 * math.pi * ((_time / 2.8) % 1.0));
    final layers = <EmberLayer>[
      if (prev != null && _fade < 1)
        EmberLayer(
          image: prev,
          src: m.clips[_previous!]!.frameRect(_frameAt(_previous!, _prevTime)),
          opacity: cur == null ? 1 : 1 - Curves.easeInOut.transform(_fade),
        ),
      if (cur != null)
        EmberLayer(
          image: cur,
          src: m.clips[_current]!.frameRect(_frameAt(_current, _time)),
          opacity: prev == null || _fade >= 1
              ? 1
              : Curves.easeInOut.transform(_fade),
        ),
    ];
    return CustomPaint(
      size: Size.infinite,
      painter: EmberPainter(
        layers: layers,
        // Glow preference (±12 %) and the approval pulse both lift light.
        brightness: widget.look.glow * (1 + 0.14 * pulse * _attention),
      ),
    );
  }
}

@immutable
class EmberLayer {
  const EmberLayer({
    required this.image,
    required this.src,
    required this.opacity,
  });
  final ui.Image image;
  final Rect src;
  final double opacity;

  @override
  bool operator ==(Object other) =>
      other is EmberLayer &&
      identical(other.image, image) &&
      other.src == src &&
      other.opacity == opacity;

  @override
  int get hashCode => Object.hash(identityHashCode(image), src, opacity);
}

class EmberPainter extends CustomPainter {
  EmberPainter({required this.layers, this.brightness = 1});

  final List<EmberLayer> layers;
  final double brightness;

  /// Colour matrix scaling RGB by [b] (alpha untouched).
  static List<double> brightnessMatrix(double b) => <double>[
    b, 0, 0, 0, 0, //
    0, b, 0, 0, 0, //
    0, 0, b, 0, 0, //
    0, 0, 0, 1, 0, //
  ];

  @override
  void paint(Canvas canvas, Size size) {
    if (size.isEmpty) return;
    final side = math.min(size.width, size.height);
    final dst = Rect.fromCenter(
      center: size.center(Offset.zero),
      width: side,
      height: side,
    );
    for (final l in layers) {
      if (l.opacity <= 0.001) continue;
      final p = Paint()
        ..filterQuality = FilterQuality.medium
        ..color = Color.fromRGBO(255, 255, 255, l.opacity.clamp(0.0, 1.0));
      if ((brightness - 1).abs() > 0.002) {
        p.colorFilter = ColorFilter.matrix(brightnessMatrix(brightness));
      }
      canvas.drawImageRect(l.image, l.src, dst, p);
    }
  }

  @override
  bool shouldRepaint(EmberPainter old) =>
      old.brightness != brightness || !listEquals(old.layers, layers);
}
