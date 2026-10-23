import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../theme/uri_theme.dart';
import 'companion_orb.dart';
import 'companion_theme.dart';
import 'energy_orb.dart' show OrbVariant;

/// The companion the user chose: one of the living identities, or the
/// accepted classic Energy Orb (kept so no accepted functionality is lost).
@immutable
class CompanionChoice {
  const CompanionChoice.living(CompanionIdentity this.identity);
  const CompanionChoice.classic() : identity = null;

  /// Null for the classic Energy Orb.
  final CompanionIdentity? identity;

  bool get isClassic => identity == null;

  String get key => identity?.name ?? 'classic';

  String get label => identity?.label ?? 'Classic Energy Orb';

  String get tagline => identity?.tagline ?? 'The original orb, any palette';

  static const List<CompanionChoice> all = <CompanionChoice>[
    CompanionChoice.living(CompanionIdentity.solar),
    CompanionChoice.living(CompanionIdentity.sakura),
    CompanionChoice.living(CompanionIdentity.lunar),
    CompanionChoice.living(CompanionIdentity.moonlit),
    CompanionChoice.living(CompanionIdentity.ember),
    CompanionChoice.classic(),
  ];

  static CompanionChoice? fromKey(String? key) {
    for (final c in all) {
      if (c.key == key) return c;
    }
    return null;
  }

  @override
  bool operator ==(Object other) =>
      other is CompanionChoice && other.identity == identity;

  @override
  int get hashCode => identity.hashCode;
}

/// How often the companion and the voice waveform are redrawn.
enum FrameRateMode { adaptive, fps30, fps60, fps90, fps144 }

extension FrameRateModeInfo on FrameRateMode {
  /// The fixed cap, or null for adaptive.
  double? get fixedFps => switch (this) {
    FrameRateMode.adaptive => null,
    FrameRateMode.fps30 => 30,
    FrameRateMode.fps60 => 60,
    FrameRateMode.fps90 => 90,
    FrameRateMode.fps144 => 144,
  };

  String get label => switch (this) {
    FrameRateMode.adaptive => 'Adaptive',
    FrameRateMode.fps30 => '30 FPS',
    FrameRateMode.fps60 => '60 FPS',
    FrameRateMode.fps90 => '90 FPS',
    FrameRateMode.fps144 => '144 FPS',
  };

  /// A fixed rate the display cannot show is not offered as if it could be.
  /// A small tolerance keeps 59.94 Hz panels able to pick 60.
  bool supportedBy(double displayHz) {
    final f = fixedFps;
    return f == null || f <= displayHz + 1.5;
  }
}

/// Resolution the living companion's shader is evaluated at, relative to the
/// pixels it covers. Lower quality renders offscreen and scales up.
enum RenderQuality { full, balanced, performance }

extension RenderQualityInfo on RenderQuality {
  double get scale => switch (this) {
    RenderQuality.full => 1.0,
    RenderQuality.balanced => 0.75,
    RenderQuality.performance => 0.5,
  };

  String get label => switch (this) {
    RenderQuality.full => 'Full',
    RenderQuality.balanced => 'Balanced',
    RenderQuality.performance => 'Performance',
  };

  String get detail => switch (this) {
    RenderQuality.full => 'Every pixel computed',
    RenderQuality.balanced => '75 % resolution, smoothed',
    RenderQuality.performance => '50 % resolution, smoothed',
  };
}

/// Per-companion appearance. Each value scales that identity's own expression
/// parameters, so the controls never make two companions alike: "particles"
/// is embers for Solar, petals for Sakura, stars and mist for Lunar.
@immutable
class CompanionLook {
  const CompanionLook({
    this.size = 1,
    this.particles = 1,
    this.glow = 1,
    this.atmosphere = 1,
    this.motion = 1,
  });

  static const CompanionLook standard = CompanionLook();

  static const double sizeMin = 0.8, sizeMax = 1.25;
  static const double particlesMin = 0, particlesMax = 1.5;

  /// Glow scales exposure. Limited to ±12 %: beyond that the filmic tonemap
  /// starts to flatten the surface detail the companions are made of.
  static const double glowMin = 0.88, glowMax = 1.12;
  static const double atmosphereMin = 0, atmosphereMax = 1.5;
  static const double motionMin = 0.5, motionMax = 1.5;

  /// Size of the companion in its space (1 = the designed size).
  final double size;

  /// Multiplies the identity's `particles` parameter.
  final double particles;

  /// Multiplies `exposure`.
  final double glow;

  /// Multiplies `flare`: corona, energy ribbons or halo.
  final double atmosphere;

  /// Rate at which the companion's own time runs.
  final double motion;

  bool get isStandard => this == standard;

  CompanionLook copyWith({
    double? size,
    double? particles,
    double? glow,
    double? atmosphere,
    double? motion,
  }) => CompanionLook(
    size: size ?? this.size,
    particles: particles ?? this.particles,
    glow: glow ?? this.glow,
    atmosphere: atmosphere ?? this.atmosphere,
    motion: motion ?? this.motion,
  ).clamped();

  CompanionLook clamped() => CompanionLook(
    size: _c(size, sizeMin, sizeMax, 1),
    particles: _c(particles, particlesMin, particlesMax, 1),
    glow: _c(glow, glowMin, glowMax, 1),
    atmosphere: _c(atmosphere, atmosphereMin, atmosphereMax, 1),
    motion: _c(motion, motionMin, motionMax, 1),
  );

  /// The state's own parameters with this look applied.
  CompanionParams apply(CompanionParams p) {
    if (isStandard) return p;
    return CompanionParams(
      energy: p.energy,
      turbulence: p.turbulence,
      flare: (p.flare * atmosphere).clamp(0.0, 1.0),
      particles: (p.particles * particles).clamp(0.0, 1.0),
      focus: p.focus,
      exposure: (p.exposure * glow).clamp(0.5, 1.5),
    );
  }

  Map<String, double> toJson() => <String, double>{
    'size': size,
    'particles': particles,
    'glow': glow,
    'atmosphere': atmosphere,
    'motion': motion,
  };

  /// Unknown, missing or non-numeric fields fall back to the standard value;
  /// out-of-range ones are clamped. A corrupt preference never breaks the UI.
  static CompanionLook fromJson(Object? json) {
    if (json is! Map) return standard;
    double v(String k) {
      final x = json[k];
      return x is num && x.isFinite ? x.toDouble() : double.nan;
    }

    return CompanionLook(
      size: v('size'),
      particles: v('particles'),
      glow: v('glow'),
      atmosphere: v('atmosphere'),
      motion: v('motion'),
    ).clamped();
  }

  static double _c(double x, double lo, double hi, double fallback) =>
      x.isNaN ? fallback : x.clamp(lo, hi).toDouble();

  @override
  bool operator ==(Object other) =>
      other is CompanionLook &&
      other.size == size &&
      other.particles == particles &&
      other.glow == glow &&
      other.atmosphere == atmosphere &&
      other.motion == motion;

  @override
  int get hashCode => Object.hash(size, particles, glow, atmosphere, motion);
}

/// What each appearance control is called for one identity. The words are
/// the identity's own; a control that would do nothing is not offered.
@immutable
class CompanionLookVocabulary {
  const CompanionLookVocabulary({
    required this.particles,
    required this.atmosphere,
  });

  /// Null when the identity cannot vary it (Ember's embers and glow are
  /// rendered into its clips), so the control is not offered.
  final String? particles;
  final String? atmosphere;

  static CompanionLookVocabulary of(CompanionIdentity id) => switch (id) {
    CompanionIdentity.solar => const CompanionLookVocabulary(
      particles: 'Embers',
      atmosphere: 'Corona and prominences',
    ),
    CompanionIdentity.sakura => const CompanionLookVocabulary(
      particles: 'Petals and pollen',
      atmosphere: 'Energy ribbons',
    ),
    CompanionIdentity.lunar => const CompanionLookVocabulary(
      particles: 'Stars and mist',
      atmosphere: 'Halo and light shafts',
    ),
    CompanionIdentity.moonlit => const CompanionLookVocabulary(
      particles: 'Petals and mist',
      atmosphere: 'Moon halo',
    ),
    CompanionIdentity.ember => const CompanionLookVocabulary(
      particles: null,
      atmosphere: null,
    ),
  };
}

/// How a finished spoken utterance is used.
enum VoiceInputMode {
  /// The words are a turn in the conversation; URI answers aloud.
  conversation,

  /// The words are content for a draft (Text Intelligence draft desk); they
  /// never reach Core as a request.
  drafting,
}

/// User voice preferences: URI's reply voice (also used by the previews) and
/// the live voice input (microphone, reply speech, input mode).
@immutable
class VoicePreferences {
  const VoicePreferences({
    this.voiceId,
    this.volume = 100,
    this.rate = 0,
    this.pitch = 0,
    this.language,
    this.waveform = true,
    this.microphone,
    this.speakReplies = true,
    this.inputMode = VoiceInputMode.conversation,
    this.vocabulary = '',
    this.dictationScope = 'grammar',
  });

  /// `<engine>:<voice name>`, or null for the engine default.
  final String? voiceId;

  /// 0..100.
  final int volume;

  /// -10 (slowest) .. 10 (fastest); 0 is the voice's normal speed.
  final int rate;

  /// -10 .. 10; 0 is the voice's natural pitch.
  final int pitch;

  /// BCP-47 tag used to filter the voice list, or null for every language.
  final String? language;

  /// Whether the shared voice waveform is drawn while someone speaks. Off
  /// keeps the transcript and the state; it never changes the level mapping.
  final bool waveform;

  /// Input device name as the voice service lists it, or null for the
  /// Windows default microphone.
  final String? microphone;

  /// Whether URI speaks its replies to spoken questions.
  final bool speakReplies;

  final VoiceInputMode inputMode;

  /// Drafting mode (plan 16 WI-8): what URI does with dictated words. 'verbatim' keeps them as spoken (no Brain),
  /// 'grammar' corrects grammar and punctuation only, 'rewrite' polishes them into professional wording.
  final String dictationScope;
  static const dictationScopes = ['verbatim', 'grammar', 'rewrite'];

  /// Names and words the recogniser should expect (people, places, terms),
  /// space separated. Empty: only URI's own name is expected.
  final String vocabulary;

  VoicePreferences copyWith({
    Object? voiceId = _keep,
    int? volume,
    int? rate,
    int? pitch,
    Object? language = _keep,
    bool? waveform,
    Object? microphone = _keep,
    bool? speakReplies,
    VoiceInputMode? inputMode,
    String? vocabulary,
    String? dictationScope,
  }) => VoicePreferences(
    voiceId: identical(voiceId, _keep) ? this.voiceId : voiceId as String?,
    volume: (volume ?? this.volume).clamp(0, 100),
    rate: (rate ?? this.rate).clamp(-10, 10),
    pitch: (pitch ?? this.pitch).clamp(-10, 10),
    language: identical(language, _keep) ? this.language : language as String?,
    waveform: waveform ?? this.waveform,
    microphone: identical(microphone, _keep)
        ? this.microphone
        : microphone as String?,
    speakReplies: speakReplies ?? this.speakReplies,
    inputMode: inputMode ?? this.inputMode,
    vocabulary: vocabulary ?? this.vocabulary,
    dictationScope: dictationScopes.contains(dictationScope) ? dictationScope! : this.dictationScope,
  );

  static const Object _keep = Object();

  Map<String, Object?> toJson() => <String, Object?>{
    'voiceId': voiceId,
    'volume': volume,
    'rate': rate,
    'pitch': pitch,
    'language': language,
    'waveform': waveform,
    'microphone': microphone,
    'speakReplies': speakReplies,
    'inputMode': inputMode.name,
    'vocabulary': vocabulary,
    'dictationScope': dictationScope,
  };

  static VoicePreferences fromJson(Object? json) {
    if (json is! Map) return const VoicePreferences();
    int i(String k, int fallback, int lo, int hi) {
      final x = json[k];
      return x is num && x.isFinite ? x.round().clamp(lo, hi) : fallback;
    }

    final id = json['voiceId'];
    final lang = json['language'];
    final wf = json['waveform'];
    final mic = json['microphone'];
    final sr = json['speakReplies'];
    final mode = json['inputMode'];
    final vocab = json['vocabulary'];
    final scope = json['dictationScope'];
    return VoicePreferences(
      voiceId: id is String && id.contains(':') ? id : null,
      volume: i('volume', 100, 0, 100),
      rate: i('rate', 0, -10, 10),
      pitch: i('pitch', 0, -10, 10),
      language: lang is String && lang.isNotEmpty ? lang : null,
      waveform: wf is bool ? wf : true,
      microphone: mic is String && mic.isNotEmpty ? mic : null,
      speakReplies: sr is bool ? sr : true,
      inputMode: VoiceInputMode.values.firstWhere(
        (m) => m.name == mode,
        orElse: () => VoiceInputMode.conversation,
      ),
      vocabulary: vocab is String ? vocab : '',
      dictationScope: scope is String && dictationScopes.contains(scope) ? scope : 'grammar',
    );
  }

  @override
  bool operator ==(Object other) =>
      other is VoicePreferences &&
      other.voiceId == voiceId &&
      other.volume == volume &&
      other.rate == rate &&
      other.pitch == pitch &&
      other.language == language &&
      other.waveform == waveform &&
      other.microphone == microphone &&
      other.speakReplies == speakReplies &&
      other.inputMode == inputMode &&
      other.vocabulary == vocabulary &&
      other.dictationScope == dictationScope;

  @override
  int get hashCode => Object.hash(
    voiceId,
    volume,
    rate,
    pitch,
    language,
    waveform,
    microphone,
    speakReplies,
    inputMode,
    vocabulary,
    dictationScope,
  );
}

/// Companion preferences: one store, one source of truth.
///
/// Per-companion appearance is kept for every companion, so switching away
/// and back restores it. Performance and audio are global. Everything is
/// written under `uri.living.companion.*`, because every `uri_ui` build on a
/// PC shares one `shared_preferences.json` with the live Hybrid app.
///
/// The app theme is *derived* from the choice (see [themeFor]); it is not
/// stored here, so there is no second theme setting to disagree with.
class CompanionPreferences extends ChangeNotifier {
  CompanionPreferences({
    CompanionChoice choice = const CompanionChoice.living(
      CompanionIdentity.solar,
    ),
    FrameRateMode frameRate = FrameRateMode.adaptive,
    RenderQuality quality = RenderQuality.full,
    bool statsOverlay = false,
    Map<String, CompanionLook>? looks,
    VoicePreferences voice = const VoicePreferences(),
    this.persist = true,
  }) : _choice = choice,
       _frameRate = frameRate,
       _quality = quality,
       _stats = statsOverlay,
       _looks = <String, CompanionLook>{...?looks},
       _voice = voice;
  // ignore_for_file: prefer_initializing_formals

  static const String prefix = 'uri.living.companion.';
  static const String keyChoice = '${prefix}choice';
  static const String keyFrameRate = '${prefix}frameRate';
  static const String keyQuality = '${prefix}quality';
  static const String keyStats = '${prefix}statsOverlay';
  static const String keyLookPrefix = '${prefix}look.';
  static const String keyVoice = '${prefix}voice';
  static const String keyInterfaceTheme = '${prefix}interfaceTheme';
  static const String keyClassicVariant = '${prefix}classicVariant';
  UriThemeChoice? _interfaceTheme;
  OrbVariant _classicVariant = OrbVariant.nebula;
  UriThemeChoice? get interfaceTheme => _interfaceTheme;
  OrbVariant get classicVariant => _classicVariant;
  UriThemeChoice effectiveTheme([
    UriThemeChoice legacyClassic = UriThemeChoice.graphite,
  ]) => _interfaceTheme ?? themeFor(choice, legacyClassic);

  Future<void> setInterfaceTheme(UriThemeChoice? value) async {
    if (_interfaceTheme == value) return;
    _interfaceTheme = value;
    _changed(
      () => _write(
        (p) => p.setString(keyInterfaceTheme, value?.name ?? 'original'),
      ),
    );
    await pendingWrite;
  }

  void setClassicVariant(OrbVariant value) {
    if (_classicVariant == value) return;
    _classicVariant = value;
    _changed(() => _write((p) => p.setString(keyClassicVariant, value.name)));
  }

  /// False in harnesses and tests that must never write the shared file.
  final bool persist;

  CompanionChoice _choice;
  FrameRateMode _frameRate;
  RenderQuality _quality;
  bool _stats;
  final Map<String, CompanionLook> _looks;
  VoicePreferences _voice;

  CompanionChoice get choice => _choice;
  FrameRateMode get frameRate => _frameRate;
  RenderQuality get quality => _quality;
  bool get statsOverlay => _stats;
  VoicePreferences get voice => _voice;

  CompanionLook lookFor(CompanionChoice c) =>
      _looks[c.key] ?? CompanionLook.standard;

  CompanionLook get look => lookFor(_choice);

  /// The theme a choice implies. A living companion decides the theme; the
  /// classic orb keeps the user's free appearance choice.
  static UriThemeChoice themeFor(
    CompanionChoice c,
    UriThemeChoice classicTheme,
  ) =>
      c.identity == null ? classicTheme : CompanionTheme.choiceFor(c.identity!);

  void select(CompanionChoice c) {
    if (c == _choice) return;
    _choice = c;
    _changed(() => _write((p) => p.setString(keyChoice, c.key)));
  }

  void setFrameRate(FrameRateMode m) {
    if (m == _frameRate) return;
    _frameRate = m;
    _changed(() => _write((p) => p.setString(keyFrameRate, m.name)));
  }

  void setQuality(RenderQuality q) {
    if (q == _quality) return;
    _quality = q;
    _changed(() => _write((p) => p.setString(keyQuality, q.name)));
  }

  void setStatsOverlay(bool on) {
    if (on == _stats) return;
    _stats = on;
    _changed(() => _write((p) => p.setBool(keyStats, on)));
  }

  void setLook(CompanionChoice c, CompanionLook look) {
    final next = look.clamped();
    if (lookFor(c) == next) return;
    _looks[c.key] = next;
    _changed(
      () => _write(
        (p) => p.setString('$keyLookPrefix${c.key}', jsonEncode(next.toJson())),
      ),
    );
  }

  void setVoice(VoicePreferences v) {
    if (v == _voice) return;
    _voice = v;
    _changed(
      () => _write((p) => p.setString(keyVoice, jsonEncode(v.toJson()))),
    );
  }

  /// The most recent write, for tests and for a clean shutdown.
  Future<void> get pendingWrite => _pending;
  Future<void> _pending = Future<void>.value();

  void _changed(Future<void> Function() write) {
    notifyListeners();
    if (persist) _pending = _pending.then((_) => write());
  }

  Future<void> _write(Future<bool> Function(SharedPreferences) op) async {
    try {
      await op(await SharedPreferences.getInstance());
    } catch (_) {
      // A failed write loses a preference, never the session.
    }
  }

  /// Reads every key. Missing, unknown or corrupt values keep the default.
  static Future<CompanionPreferences> load({bool persist = true}) async {
    final prefs = await SharedPreferences.getInstance();
    return fromPrefs(prefs, persist: persist);
  }

  @visibleForTesting
  static CompanionPreferences fromPrefs(
    SharedPreferences prefs, {
    bool persist = true,
  }) => CompanionPreferences(persist: persist)..restoreFrom(prefs);

  /// Replaces every value with what [prefs] holds (defaults where a key is
  /// missing or unreadable) without writing anything back, then notifies
  /// once. The app restores into the instance its widgets already hold.
  void restoreFrom(SharedPreferences prefs) {
    T pick<T extends Enum>(List<T> values, String key, T fallback) {
      final raw = _safeString(prefs, key);
      for (final v in values) {
        if (v.name == raw) return v;
      }
      return fallback;
    }

    _looks.clear();
    final themeKey = _safeString(prefs, keyInterfaceTheme);
    _interfaceTheme = UriThemeChoice.values
        .where((t) => t.name == themeKey)
        .firstOrNull;
    if (themeKey == null && _safeString(prefs, keyChoice) == 'classic') {
      final legacy = _safeString(prefs, 'uri.living.themeChoice');
      _interfaceTheme = UriThemeChoice.values
          .where((t) => t.name == legacy)
          .firstOrNull;
    }
    _classicVariant = pick(
      OrbVariant.values,
      keyClassicVariant,
      OrbVariant.nebula,
    );
    for (final c in CompanionChoice.all) {
      final raw = _safeString(prefs, '$keyLookPrefix${c.key}');
      if (raw == null) continue;
      _looks[c.key] = CompanionLook.fromJson(_safeJson(raw));
    }
    final voiceRaw = _safeString(prefs, keyVoice);
    try {
      _stats = prefs.getBool(keyStats) ?? false;
    } catch (_) {
      _stats = false;
    }
    _choice =
        CompanionChoice.fromKey(_safeString(prefs, keyChoice)) ??
        const CompanionChoice.living(CompanionIdentity.solar);
    _frameRate = pick(
      FrameRateMode.values,
      keyFrameRate,
      FrameRateMode.adaptive,
    );
    _quality = pick(RenderQuality.values, keyQuality, RenderQuality.full);
    _voice = voiceRaw == null
        ? const VoicePreferences()
        : VoicePreferences.fromJson(_safeJson(voiceRaw));
    notifyListeners();
  }

  static String? _safeString(SharedPreferences p, String key) {
    try {
      return p.getString(key);
    } catch (_) {
      return null; // stored under another type
    }
  }

  static Object? _safeJson(String raw) {
    try {
      return jsonDecode(raw);
    } catch (_) {
      return null;
    }
  }

  static CompanionPreferences of(BuildContext context) =>
      context
          .dependOnInheritedWidgetOfExactType<CompanionPreferencesScope>()
          ?.notifier ??
      _fallback;

  static CompanionPreferences? maybeOf(BuildContext context) => context
      .dependOnInheritedWidgetOfExactType<CompanionPreferencesScope>()
      ?.notifier;

  static final CompanionPreferences _fallback = CompanionPreferences(
    persist: false,
  );
}

class CompanionPreferencesScope
    extends InheritedNotifier<CompanionPreferences> {
  const CompanionPreferencesScope({
    super.key,
    required CompanionPreferences preferences,
    required super.child,
  }) : super(notifier: preferences);
}
