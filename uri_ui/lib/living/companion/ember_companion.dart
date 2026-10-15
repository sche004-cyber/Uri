import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:ui' as ui;

import 'package:flutter/foundation.dart';
import 'package:flutter/scheduler.dart' show SchedulerBinding;
import 'package:flutter/services.dart' show AssetBundle, rootBundle;
import 'package:flutter/widgets.dart';

import 'companion_preferences.dart' show CompanionLook;
import 'companion_state.dart';
import 'effects_settings.dart';
import 'frame_clock.dart';

/// The fire companion's animation clips, made from the reference painting
/// itself (`companion_art/fire_v2/`: the panels are cut into layers and
/// animated in 2.5D) and shipped as WebP sprite atlases.
///
/// A clip is an expression, not a state: several [CompanionState]s share one
/// (see [EmberClips.forState]). The reference sheet's "Fierce" is animated
/// and scored (`companion_art/fire_v2/expressions.json`) but not shipped: no
/// operational state may use it, because an angry face aimed at the user would
/// misreport what URI is doing. `focused` carries its energy for `working`.
enum EmberClip {
  idle,
  joyful,
  depleted,
  listening,
  thinking,
  speaking,
  focused,
  concerned,

  /// The Brain is starting: a calm, low, softly glowing flame with the eyes
  /// half lowered. It brightens into [idle] when URI is ready.
  kindling,
}

/// Pure mapping from authoritative state to expression. Kept free of widgets
/// so the whole table is asserted in a test.
class EmberClips {
  const EmberClips._();

  static EmberClip forState(CompanionState state) => switch (state) {
    CompanionState.unavailable => EmberClip.depleted,
    CompanionState.initializing => EmberClip.kindling,
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
    this.blink,
    this.eyeOffsets = const <Offset>[],
  });

  final String file;
  final int frames;
  final int cols;
  final int cell;

  /// Lid patches for the runtime blink, or null when this expression does not
  /// blink (smiling or already closed eyes).
  final EmberBlink? blink;

  /// Per frame, how far the eyes have moved from frame 0 (cell pixels): the
  /// head breathes, and the lid patch follows it.
  final List<Offset> eyeOffsets;

  Offset eyeOffset(int index) =>
      eyeOffsets.isEmpty ? Offset.zero : eyeOffsets[index % eyeOffsets.length];

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

/// [r] lies wholly inside [outer].
bool _inside(Rect outer, Rect r) =>
    r.left >= outer.left &&
    r.top >= outer.top &&
    r.right <= outer.right &&
    r.bottom <= outer.bottom;

/// Where a clip's lid patches are: [rect] is the patch's place in a cell at
/// frame 0, [sources] the top-left of each lid level (half closed .. closed)
/// in the blink atlas.
@immutable
class EmberBlink {
  const EmberBlink({required this.rect, required this.sources});

  final Rect rect;
  final List<Offset> sources;

  Rect sourceRect(int level) =>
      sources[level.clamp(0, sources.length - 1)] & rect.size;
}

@immutable
class EmberManifest {
  const EmberManifest({required this.fps, required this.clips, this.blinkFile});

  final double fps;
  final Map<EmberClip, EmberClipInfo> clips;

  /// The atlas holding every clip's lid patches (small), if any clip blinks.
  final String? blinkFile;

  static const String assetDir = 'assets/companions/ember';
  static const String assetPath = '$assetDir/manifest.json';

  /// A small still of the idle expression for the companion picker.
  static const String thumbnailPath = '$assetDir/thumbnail.webp';

  /// A clip's lid patches, or null when the entry is malformed or lies
  /// outside the cell: that clip then just does not blink, and the rest of
  /// Ember is unaffected (review R1-06).
  static EmberBlink? _parseBlink(Map<String, dynamic> b, double cell) {
    try {
      final r = (b['rect'] as List<dynamic>).cast<num>();
      final src = [
        for (final s in b['src'] as List<dynamic>)
          Offset(
            ((s as List<dynamic>)[0] as num).toDouble(),
            (s[1] as num).toDouble(),
          ),
      ];
      if (r.length != 4 || r[2] <= 0 || r[3] <= 0 || src.isEmpty) return null;
      final rect = Rect.fromLTWH(
        r[0].toDouble(),
        r[1].toDouble(),
        r[2].toDouble(),
        r[3].toDouble(),
      );
      if (!_inside(Offset.zero & Size(cell, cell), rect)) return null;
      if (src.any((o) => o.dx < 0 || o.dy < 0)) return null;
      return EmberBlink(rect: rect, sources: src);
    } on Object {
      return null;
    }
  }

  static EmberManifest parse(String text) {
    final j = jsonDecode(text) as Map<String, dynamic>;
    final clips = <EmberClip, EmberClipInfo>{};
    final raw = j['clips'] as Map<String, dynamic>;
    for (final c in EmberClip.values) {
      final m = raw[c.name] as Map<String, dynamic>?;
      if (m == null) continue;
      final frames = (m['frames'] as num).toInt();
      final offsets = <Offset>[
        for (final o in (m['eye_offsets'] as List<dynamic>? ?? const []))
          Offset(
            ((o as List<dynamic>)[0] as num).toDouble(),
            (o[1] as num).toDouble(),
          ),
      ];
      if (offsets.isNotEmpty && offsets.length != frames) {
        throw FormatException(
          'ember manifest: ${c.name} has ${offsets.length} eye offsets for '
          '$frames frames',
        );
      }
      final b = m['blink'] as Map<String, dynamic>?;
      EmberBlink? blink;
      if (b != null) blink = _parseBlink(b, (m['cell'] as num).toDouble());
      final info = EmberClipInfo(
        file: m['file'] as String,
        frames: frames,
        cols: (m['cols'] as num).toInt(),
        cell: (m['cell'] as num).toInt(),
        blink: blink,
        eyeOffsets: offsets,
      );
      if (info.frames <= 0 || info.cols <= 0 || info.cell <= 0) {
        throw FormatException('ember manifest: ${c.name} has an empty layout');
      }
      clips[c] = info;
    }
    final fps = (j['fps'] as num).toDouble();
    if (fps <= 0) {
      throw const FormatException('ember manifest: fps must be > 0');
    }
    final blinkAtlas = j['blink_atlas'] as Map<String, dynamic>?;
    final blinkFile = blinkAtlas?['file'] as String?;
    if (blinkFile == null) {
      // Lid patches without their atlas: Ember plays without blinks rather
      // than not at all (review R1-06).
      for (final e in clips.entries.toList()) {
        if (e.value.blink == null) continue;
        clips[e.key] = EmberClipInfo(
          file: e.value.file,
          frames: e.value.frames,
          cols: e.value.cols,
          cell: e.value.cell,
          eyeOffsets: e.value.eyeOffsets,
        );
      }
    }
    return EmberManifest(fps: fps, clips: clips, blinkFile: blinkFile);
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
  final Map<EmberClip, Duration> _failed = <EmberClip, Duration>{};
  String? lastFailure;
  ui.Image? _blinkImage;
  Future<void>? _blinkLoading;
  Duration? _blinkFailedAt;

  /// Monotonic time for the retry window (wall-clock changes cannot move it).
  /// Tests replace it to step past [retryAfter].
  @visibleForTesting
  Duration Function() now = _monotonic;
  static final Stopwatch _since = Stopwatch()..start();
  static Duration _monotonic() => _since.elapsed;

  /// How long a failed clip is not retried. A transient failure (e.g. memory
  /// pressure during decode) must not block the clip for the life of the app,
  /// and a permanent one must not be decoded again on every rebuild.
  static const Duration retryAfter = Duration(seconds: 30);

  /// The clip could not be loaded or decoded recently (missing, corrupt, no
  /// manifest). A widget never waits on it and does not fade to it.
  bool hasFailed(EmberClip clip) {
    final at = _failed[clip];
    return at != null && now() - at < retryAfter;
  }

  /// Time left before a failed clip may be tried again (zero if it may).
  Duration retryIn(EmberClip clip) {
    final at = _failed[clip];
    if (at == null) return Duration.zero;
    final left = retryAfter - (now() - at);
    return left.isNegative ? Duration.zero : left;
  }

  /// A decode for [clip] is in flight.
  bool isLoading(EmberClip clip) => _loading.containsKey(clip);

  /// Clips some widget has on screen. Never evicted.
  Set<EmberClip> get pinned => {for (final s in _pins.values) ...s};

  /// [owner] shows [clips] now (replacing what it showed before). Atlases no
  /// longer shown by anyone are evicted down to [capacity].
  void pin(Object owner, Set<EmberClip> clips) {
    _pins[owner] = Set<EmberClip>.of(clips);
    _evict();
  }

  /// When no widget shows Ember any more, every atlas is disposed: a hidden
  /// companion must not hold GPU memory next to the Brain.
  void release(Object owner) {
    _pins.remove(owner);
    if (_pins.isEmpty) {
      for (final i in _images.values) {
        i.dispose();
      }
      _images.clear();
      _recent.clear();
      _blinkImage?.dispose();
      _blinkImage = null;
      return;
    }
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
    final b = _blinkImage;
    if (b != null) n += b.width * b.height * 4;
    return n;
  }

  /// The lid-patch atlas, once decoded (small: a few eye-sized patches per
  /// clip). Null while loading, after a failure, or when nothing blinks.
  ui.Image? get blinkImageIfLoaded => _blinkImage;

  /// Starts decoding the lid-patch atlas if a widget shows Ember and it is not
  /// resident. A failure only means no blinks; it is retried after
  /// [retryAfter].
  void requestBlink() {
    if (_blinkImage != null || _blinkLoading != null || _pins.isEmpty) return;
    final failed = _blinkFailedAt;
    if (failed != null && now() - failed < retryAfter) return;
    _blinkLoading = _decodeBlink().whenComplete(() => _blinkLoading = null);
  }

  Future<void> _decodeBlink() async {
    final m = await manifest();
    final file = m?.blinkFile;
    if (file == null) return;
    try {
      final data = await _bundle.load('${EmberManifest.assetDir}/$file');
      final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
      final frame = await codec.getNextFrame();
      codec.dispose();
      _blinkFailedAt = null;
      if (_pins.isEmpty) {
        frame.image.dispose();
        return;
      }
      _blinkImage?.dispose();
      _blinkImage = frame.image;
    } catch (e) {
      lastFailure = 'blink: $e';
      _blinkFailedAt = now();
    }
  }

  Future<ui.Image?> load(EmberClip clip) {
    if (hasFailed(clip)) return Future<ui.Image?>.value(null);
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
    if (info == null) {
      _failed[clip] = now();
      return null;
    }
    try {
      final data = await _bundle.load('${EmberManifest.assetDir}/${info.file}');
      final codec = await ui.instantiateImageCodec(data.buffer.asUint8List());
      final frame = await codec.getNextFrame();
      codec.dispose();
      _failed.remove(clip);
      if (_pins.isEmpty) {
        // Everyone left while this decoded: keep nothing resident.
        frame.image.dispose();
        return null;
      }
      _images[clip] = frame.image;
      _touch(clip);
      _evict();
      return frame.image;
    } catch (e) {
      lastFailure = '${clip.name}: $e';
      _failed[clip] = now();
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
    _failed.clear();
    _blinkImage?.dispose();
    _blinkImage = null;
    _blinkLoading = null;
    _blinkFailedAt = null;
    _manifest = null;
    _manifestValue = null;
    lastFailure = null;
  }
}

/// When the companion blinks: at irregular intervals (2.5-7 s apart, now and
/// then twice in quick succession), each blink a short close-hold-open run of
/// lid levels, one level per sprite frame (about a quarter of a second).
///
/// Pure and driven by the caller's clock, so it never asks for frames itself:
/// a blink shows only on sprite frames the companion draws anyway.
class EmberBlinker {
  EmberBlinker({math.Random? random}) : _rng = random ?? math.Random();

  final math.Random _rng;

  /// Lid level per step (index into a clip's lid patches; 0 = half closed).
  static const List<int> sequence = <int>[0, 1, 2, 2, 1, 0];
  static const double step = 1 / 24;
  static const double minGap = 2.5;
  static const double maxGap = 7.0;
  static const double doubleChance = 0.15;
  static const double doubleGap = 0.2;

  double? _next;
  double? _start;
  bool _double = false;

  double get _gap => minGap + _rng.nextDouble() * (maxGap - minGap);

  /// The seconds (of the caller's clock) when the next blink starts.
  double? get nextBlinkAt => _next;

  /// Lid level at time [t] (seconds, never decreasing), or null when the eyes
  /// are open. Time jumps (a hidden window) skip a missed blink rather than
  /// replaying it late.
  int? levelAt(double t) {
    final start = _start;
    if (start != null) {
      final k = ((t - start) / step).floor();
      if (k >= 0 && k < sequence.length) return sequence[k];
      _start = null;
      if (_double) {
        _double = false;
        _next = t + doubleGap;
      } else {
        _next = t + _gap;
        _double = _rng.nextDouble() < doubleChance;
      }
      return null;
    }
    final next = _next ??= t + _gap;
    if (t < next) return null;
    if (t - next > step * sequence.length) {
      _next = t + _gap;
      return null;
    }
    _start = t;
    return sequence[0];
  }

  /// Forget any blink in progress and schedule the next from [t].
  void restart(double t) {
    _start = null;
    _double = false;
    _next = t + _gap;
  }
}

/// The fire companion. Plays the expression for [state], cross-fades between
/// expressions, and pulses gently while [attention] is on.
///
/// It asks the frame clock for frames only while something moves: between two
/// sprite frames (24 per second) it stops listening and a timer wakes it for
/// the next one, so a 144 Hz display is not asked for 144 frames a second.
class EmberCompanion extends StatefulWidget {
  const EmberCompanion({
    super.key,
    this.state = CompanionState.idle,
    this.clip,
    this.attention = false,
    this.look = CompanionLook.standard,
    this.fallback,
    this.library,
    this.still = false,
    this.blinkRandom,
  });

  final CompanionState state;

  /// Overrides the state mapping (companion picker, capture harness).
  final EmberClip? clip;
  final bool attention;
  final CompanionLook look;
  final Widget? fallback;
  final EmberLibrary? library;

  /// One representative frame and no animation (the companion picker tile).
  final bool still;

  /// Seeds the blink timing (tests); null = a fresh random source.
  final math.Random? blinkRandom;

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
  bool _drawable = false;
  bool _reducedMotion = false;
  late final EmberBlinker _blinker = EmberBlinker(random: widget.blinkRandom);
  double _blinkTime = 0; // never reset: blinks are independent of clip changes
  int? _lid;

  /// Time between deliveries, taken from the frame timestamp: the frame
  /// driver restarts its own `dt` at zero whenever this widget resumes after
  /// sleeping between sprite frames, and the shared clock does not count the
  /// time nobody listened. The vsync timestamp is continuous (and is the fake
  /// clock under test).
  Duration? _lastStamp;
  Timer? _wake;

  EmberClip get _target => widget.clip ?? EmberClips.forState(widget.state);
  bool get _frozen => _reducedMotion || widget.still;

  @override
  void initState() {
    super.initState();
    _current = _target;
    _lib.pin(this, {_current});
    _request(_current);
    // A still tile never blinks, so it never decodes the lid patches.
    if (!widget.still) _lib.requestBlink();
  }

  @override
  void dispose() {
    _wake?.cancel();
    _lib.release(this);
    super.dispose();
  }

  void _request(EmberClip clip) {
    if (_lib.imageIfLoaded(clip) != null) return;
    _lib.load(clip).then((_) {
      if (!mounted) return;
      setState(_settleFailure);
      resumeFrames();
    });
  }

  /// A clip that cannot be drawn ends its fade on what was on screen, rather
  /// than holding the fade open (and frames running) forever. Checked on the
  /// load callback and on every delivery, so it never depends on one path.
  /// Returns true when it changed something.
  bool _settleFailure() {
    if (!_lib.hasFailed(_current) || _previous == null) return false;
    _current = _previous!;
    _time = _prevTime;
    _previous = null;
    _fade = 1;
    _lib.pin(this, {_current});
    return true;
  }

  @override
  void didUpdateWidget(EmberCompanion old) {
    super.didUpdateWidget(old);
    _followTarget();
    resumeFrames();
  }

  /// Moves towards the clip the state asks for. A clip that failed recently is
  /// not faded to (the companion keeps what it shows); once its retry window
  /// has passed, the next delivery calls this again and tries it.
  void _followTarget() {
    final next = _target;
    if (next == _current || _lib.hasFailed(next)) return;
    if (next == _previous && _fade < 0.5) {
      // Going back before the new clip took over: cancel, no fade.
      _current = next;
      _time = _prevTime;
      _previous = null;
      _fade = 1;
      _lib.pin(this, {_current});
      return;
    }
    // Fade from what dominates the screen. If the clip that was fading in has
    // not decoded yet, or is still less than half in, the clip that is mostly
    // visible stays the outgoing one, so a quick run of changes never blanks
    // the companion or drops a clip in one frame.
    final currentShown = _lib.imageIfLoaded(_current) != null;
    if (_previous == null || (currentShown && _fade >= 0.5)) {
      _previous = _current;
      _prevTime = _time;
    }
    _fadeLength = EmberClips.fadeBetween(_previous!, next);
    _current = next;
    _time = 0;
    _fade = 0;
    _lib.pin(this, {_previous!, next});
    _request(next);
  }

  @override
  void didChangeDependencies() {
    _reducedMotion = EffectsSettings.of(context).reducedMotion;
    super.didChangeDependencies();
  }

  bool get _settling {
    final goal = widget.attention ? 1.0 : 0.0;
    final fading = _fade < 1 && !_lib.hasFailed(_current);
    return fading || (goal - _attention).abs() > 0.01;
  }

  @override
  bool get wantsFrames {
    if (_settling) return true;
    // Loading and retries come before the frozen check: a still or
    // reduced-motion companion must still recover from a failed clip
    // (review R5-01).
    if (_lib.imageIfLoaded(_current) == null) {
      if (_lib.hasFailed(_current)) {
        // Failed: the fallback shows; wake once when it may be retried.
        _wakeIn(_lib.retryIn(_current).inMicroseconds / 1e6 + 0.01);
      } else {
        // Not loaded and not failed: make sure a load is running (a retry
        // after the window, or a missed callback), then look again shortly.
        if (!_lib.isLoading(_current)) _request(_current);
        _wakeIn(0.05);
      }
      return false;
    }
    if (_target != _current && _lib.hasFailed(_target)) {
      // Showing a stand-in for a failed target: re-check when it may retry.
      _wakeIn(_lib.retryIn(_target).inMicroseconds / 1e6 + 0.01);
    }
    if (_frozen) return false;
    // The approval pulse is a slow brightness wave: 30 updates a second are
    // indistinguishable from more.
    if (_attention > 0.001) {
      _wakeIn(1 / 30);
      return false;
    }
    _scheduleNextSpriteFrame();
    return false;
  }

  /// Sleeps until the next sprite frame is due, then asks for frames again.
  void _scheduleNextSpriteFrame() {
    final m = _lib.manifestIfLoaded;
    if (m == null) return;
    final speed = widget.look.motion <= 0 ? 1.0 : widget.look.motion;
    // _time is already the companion's own (speed-scaled) time; the next
    // frame boundary is that far away in companion time, so divide by speed
    // for wall time. Wake about one 144 Hz vsync (8 ms; a vsync is 6.9 ms) after the boundary: the
    // delivery is stamped with the vsync time, which can lag the timer, and a
    // wake that lands just before the boundary costs a frame that shows
    // nothing new (measured: about 2 deliveries per sprite frame with 1 ms).
    final perFrame = 1 / m.fps;
    final remaining = (perFrame - _time % perFrame) / speed;
    _wakeIn(math.max(0.004, remaining + 0.008));
  }

  Duration? _wakeDue; // monotonic

  /// One pending wake at a time; a new, earlier reason replaces a later one
  /// (a 50 ms decode poll must not delay the next sprite frame or pulse step).
  void _wakeIn(double seconds) {
    final delay = Duration(microseconds: (seconds * 1e6).round());
    final due = _lib.now() + delay;
    if (_wake != null && _wakeDue != null && due >= _wakeDue!) return;
    _wake?.cancel();
    _wakeDue = due;
    _wake = Timer(delay, () {
      _wake = null;
      _wakeDue = null;
      if (mounted) resumeFrames();
    });
  }

  @visibleForTesting
  bool get sleepingBetweenFrames => _wake != null;

  @visibleForTesting
  int get shownFrame => _shownFrame;

  @visibleForTesting
  EmberClip get currentClip => _current;

  /// The lid level being shown (0 half closed .. 2 closed), null when open.
  @visibleForTesting
  int? get lidLevel => _lid;

  /// A blink may show: animating, one clip settled on screen, and that clip
  /// has lid patches that are decoded.
  bool get _canBlink {
    if (_frozen || _previous != null || _fade < 1) return false;
    final info = _lib.manifestIfLoaded?.clips[_current];
    if (info?.blink == null || _lib.imageIfLoaded(_current) == null) {
      return false;
    }
    if (_lib.blinkImageIfLoaded == null) {
      _lib.requestBlink();
      return false;
    }
    return true;
  }

  int _frameAt(EmberClip clip, double t) {
    final m = _lib.manifestIfLoaded;
    final info = m?.clips[clip];
    if (m == null || info == null) return 0;
    if (_frozen) return 0;
    return (t * m.fps).floor() % info.frames;
  }

  @override
  void onCompanionFrame(double seconds, double dt) {
    if (_settleFailure()) {
      setState(() {});
      return;
    }
    if (_target != _current && !_lib.hasFailed(_target)) {
      // A target that was refused (failed) may be tried now.
      setState(_followTarget);
    }
    final now = SchedulerBinding.instance.currentSystemFrameTimeStamp;
    final last = _lastStamp;
    _lastStamp = now;
    final realDt = last == null ? 0.0 : (now - last).inMicroseconds / 1e6;
    // After a long pause (a minimised window) do not jump through a fade.
    final step = realDt.clamp(0.0, 0.25);
    final speed = widget.look.motion;
    _time += step * speed;
    _prevTime += step * speed;
    _blinkTime += step * speed;
    var changed = false;
    final canBlink = _canBlink;
    final lid = canBlink ? _blinker.levelAt(_blinkTime) : null;
    if (!canBlink) {
      // Not blinking now (frozen, fading, no patches): the next blink is
      // scheduled from when blinking becomes possible again, never replayed.
      _blinker.restart(_blinkTime);
    }
    if (lid != _lid) {
      _lid = lid;
      changed = true;
    }
    if (_fade < 1) {
      // The fade starts only once the incoming clip can be drawn.
      if (_lib.imageIfLoaded(_current) != null) {
        final len = _fadeLength.inMicroseconds / 1e6;
        _fade = len <= 0 ? 1 : (_fade + step / len).clamp(0.0, 1.0);
        if (_fade >= 1) {
          _previous = null;
          _lib.pin(this, {_current});
        }
      } else {
        _time = 0;
      }
      changed = true;
    }
    final goal = widget.attention ? 1.0 : 0.0;
    if ((goal - _attention).abs() > 0.001) {
      _attention += (goal - _attention) * (1 - math.exp(-step / 0.35));
      if ((goal - _attention).abs() <= 0.01) _attention = goal;
      changed = true;
    }
    if (_attention > 0.001) changed = true; // the pulse moves every frame
    // A clip that has just become drawable must be painted even when no
    // sprite frame advances (still mode, reduced motion).
    final drawable = _lib.imageIfLoaded(_current) != null;
    if (drawable != _drawable) {
      _drawable = drawable;
      changed = true;
    }
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
    final pulse = _frozen
        ? 0.5
        : 0.5 - 0.5 * math.cos(2 * math.pi * ((_time / 2.8) % 1.0));
    final e = Curves.easeInOut.transform(_fade);
    final info = m.clips[_current];
    final blinkImage = _lib.blinkImageIfLoaded;
    final lid = _lid;
    EmberOverlay? overlay;
    final blink = info?.blink;
    // Never during a cross-fade (review R1-05), and only for a patch that lies
    // inside the decoded atlas (review R1-06).
    final settled = _previous == null && _fade >= 1;
    if (lid != null &&
        settled &&
        cur != null &&
        blink != null &&
        blinkImage != null &&
        _inside(
          Offset.zero &
              Size(blinkImage.width.toDouble(), blinkImage.height.toDouble()),
          blink.sourceRect(lid),
        )) {
      overlay = EmberOverlay(
        image: blinkImage,
        src: blink.sourceRect(lid),
        cellRect: blink.rect.shift(info!.eyeOffset(_frameAt(_current, _time))),
        cell: info.cell.toDouble(),
      );
    }
    final layers = <EmberLayer>[
      if (prev != null && (_fade < 1 || cur == null))
        EmberLayer(
          image: prev,
          src: m.clips[_previous!]!.frameRect(_frameAt(_previous!, _prevTime)),
          opacity: cur == null ? 1 : 1 - e,
        ),
      if (cur != null)
        EmberLayer(
          image: cur,
          src: m.clips[_current]!.frameRect(_frameAt(_current, _time)),
          opacity: prev == null || _fade >= 1 ? 1 : e,
        ),
    ];
    return CustomPaint(
      size: Size.infinite,
      painter: EmberPainter(
        layers: layers,
        overlay: overlay,
        // Glow preference (+-12 %) and the approval pulse both lift light.
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

/// A patch drawn over the shown frame (the lids of a blink), placed in the
/// cell's own pixels so it scales with the companion.
@immutable
class EmberOverlay {
  const EmberOverlay({
    required this.image,
    required this.src,
    required this.cellRect,
    required this.cell,
  });
  final ui.Image image;
  final Rect src;
  final Rect cellRect;
  final double cell;

  @override
  bool operator ==(Object other) =>
      other is EmberOverlay &&
      identical(other.image, image) &&
      other.src == src &&
      other.cellRect == cellRect &&
      other.cell == cell;

  @override
  int get hashCode => Object.hash(identityHashCode(image), src, cellRect, cell);
}

class EmberPainter extends CustomPainter {
  EmberPainter({required this.layers, this.overlay, this.brightness = 1});

  final List<EmberLayer> layers;
  final EmberOverlay? overlay;
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
    ColorFilter? filter;
    if ((brightness - 1).abs() > 0.002) {
      filter = ColorFilter.matrix(brightnessMatrix(brightness));
    }
    final visible = [
      for (final l in layers)
        if (l.opacity > 0.001) l,
    ];
    if (visible.length < 2) {
      for (final l in visible) {
        canvas.drawImageRect(l.image, l.src, dst, _paint(l.opacity, filter));
      }
      final o = overlay;
      if (o != null && visible.isNotEmpty) {
        final k = side / o.cell;
        final r = o.cellRect;
        canvas.drawImageRect(
          o.image,
          o.src,
          Rect.fromLTWH(
            dst.left + r.left * k,
            dst.top + r.top * k,
            r.width * k,
            r.height * k,
          ),
          _paint(visible.first.opacity, filter),
        );
      }
      return;
    }
    // Cross-fade: the two weighted frames are added in a layer of their own,
    // giving (1 - e) * outgoing + e * incoming in premultiplied colour. Drawn
    // over each other instead, the character would sit at about 75 % opacity
    // half-way through every change.
    canvas.saveLayer(dst, Paint());
    for (var i = 0; i < visible.length; i++) {
      final p = _paint(visible[i].opacity, filter);
      if (i > 0) p.blendMode = BlendMode.plus;
      canvas.drawImageRect(visible[i].image, visible[i].src, dst, p);
    }
    canvas.restore();
  }

  static Paint _paint(double opacity, ColorFilter? filter) {
    final p = Paint()
      ..filterQuality = FilterQuality.medium
      ..color = Color.fromRGBO(255, 255, 255, opacity.clamp(0.0, 1.0));
    if (filter != null) p.colorFilter = filter;
    return p;
  }

  @override
  bool shouldRepaint(EmberPainter old) =>
      old.brightness != brightness ||
      old.overlay != overlay ||
      !listEquals(old.layers, layers);
}
