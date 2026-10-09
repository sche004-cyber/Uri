import 'dart:async';

import 'package:flutter/foundation.dart';

import '../companion/companion_preferences.dart';
import 'voice_session.dart';

/// A local speech engine URI can speak through.
enum VoiceEngine {
  /// System.Speech (SAPI 5): the engine URI's voice architecture designates.
  systemSpeech,

  /// Windows OneCore (Windows.Media.SpeechSynthesis, WinRT).
  oneCore,
}

extension VoiceEngineInfo on VoiceEngine {
  String get key => switch (this) {
    VoiceEngine.systemSpeech => 'sapi',
    VoiceEngine.oneCore => 'onecore',
  };

  String get label => switch (this) {
    VoiceEngine.systemSpeech => 'Windows desktop voices (System.Speech)',
    VoiceEngine.oneCore => 'Windows OneCore voices',
  };

  static VoiceEngine? fromKey(String? k) {
    for (final e in VoiceEngine.values) {
      if (e.key == k) return e;
    }
    return null;
  }
}

/// What an engine can change about a voice. Each flag is set from
/// measurement (rnd/companions/settings/measure_voice_params.py renders the
/// same sentence at each extreme and checks duration, f0 and level), never
/// from documentation alone. A setting whose flag is false is shown as
/// unavailable rather than as a slider that does nothing.
@immutable
class VoiceCapabilities {
  const VoiceCapabilities({
    this.rate = false,
    this.pitch = false,
    this.volume = false,
    this.style = false,
  });

  final bool rate;
  final bool pitch;
  final bool volume;

  /// Speaking styles (e.g. "cheerful"). No installed engine offers them.
  final bool style;

  /// Measured 2026-10-09 on both engines with Zira Desktop and Mark: rate
  /// changed duration 7.1 s to 21.3 / 2.6 s (SAPI) and 6.0 to 12.1 / 3.1 s
  /// (OneCore); pitch moved median f0 175 to 131 / 232 Hz and 148 to 87 /
  /// 216 Hz; volume 30 % lowered level by 17.5 dB. Evidence:
  /// docs/companions/settings/evidence/voice/voice_params.json.
  static const VoiceCapabilities measuredWindows = VoiceCapabilities(
    rate: true,
    pitch: true,
    volume: true,
  );
}

/// One installed voice.
@immutable
class VoiceInfo {
  const VoiceInfo({
    required this.engine,
    required this.name,
    required this.culture,
    this.gender,
    this.usable = true,
    this.reason,
    this.capabilities = const VoiceCapabilities(),
  });

  final VoiceEngine engine;
  final String name;

  /// BCP-47 tag, e.g. `en-US`.
  final String culture;
  final String? gender;

  /// False for a voice that is installed but cannot be used (disabled by
  /// the system); [reason] says why.
  final bool usable;
  final String? reason;
  final VoiceCapabilities capabilities;

  /// The identifier stored in [VoicePreferences.voiceId].
  String get id => '${engine.key}:$name';

  @override
  bool operator ==(Object other) =>
      other is VoiceInfo &&
      other.engine == engine &&
      other.name == name &&
      other.culture == culture &&
      other.usable == usable;

  @override
  int get hashCode => Object.hash(engine, name, culture, usable);
}

/// Result of a voice listing.
@immutable
class VoiceListing {
  const VoiceListing({
    required this.voices,
    this.unavailableReason,
    this.engineErrors = const <String>[],
  });

  /// Every installed voice found, usable or not.
  final List<VoiceInfo> voices;

  /// Set when no speech engine can be reached at all on this platform.
  final String? unavailableReason;

  /// An engine that failed to enumerate, in words (the other may still work).
  final List<String> engineErrors;

  List<String> get languages =>
      ({for (final v in voices) v.culture}.toList()..sort());
}

/// Enumerates the voices installed on this device and plays previews.
///
/// The interface is engine-neutral: a future engine (a local neural voice,
/// for instance) is one more implementation, not a change to the settings
/// page. Implementations run speech outside the renderer; nothing here draws.
abstract class VoiceCatalog {
  Future<VoiceListing> list();

  /// Speaks a short sample with [voice] and the user's parameters. Completes
  /// when playback ends; throws [VoicePreviewError] on failure.
  Future<void> preview(VoiceInfo voice, VoicePreferences prefs);

  /// Stops a preview in progress, if any.
  Future<void> stopPreview();
}

class VoicePreviewError implements Exception {
  const VoicePreviewError(this.message);
  final String message;
  @override
  String toString() => message;
}

/// The catalog on a platform without a local speech engine (and the default
/// in widget tests). It says so instead of inventing voices.
class UnavailableVoiceCatalog implements VoiceCatalog {
  const UnavailableVoiceCatalog([
    this.reason = 'No local speech engine is available on this platform.',
  ]);

  final String reason;

  @override
  Future<VoiceListing> list() async =>
      VoiceListing(voices: const <VoiceInfo>[], unavailableReason: reason);

  @override
  Future<void> preview(VoiceInfo voice, VoicePreferences prefs) async =>
      throw VoicePreviewError(reason);

  @override
  Future<void> stopPreview() async {}
}

/// Where URI's live voice events come from.
///
/// URI's voice service owns microphone capture, recognition, synthesis,
/// playback and interruption. It reports what is happening as
/// [VoiceSignal]s (speech started, transcript, audio level per block,
/// speech progress with word timings, ended, failure); the companion
/// presentation only consumes them through a [VoiceSessionController], which
/// already rejects stale and out-of-order events. No adapter is connected in
/// this build: there is no voice service on this line yet (see the voice
/// section of the companion settings report).
abstract class VoiceServiceAdapter {
  /// Shown in Settings (`Voice input: <name>`).
  String get name;

  /// True when the signals are scripted rather than from a live device.
  bool get simulated;

  Stream<VoiceSignal> get signals;
}

/// Feeds one adapter into one controller. An adapter error ends any turn in
/// progress with a visible notice; the adapter closing resets the session,
/// so a crashed voice service can never leave a waveform on screen.
class VoiceServiceBinding {
  VoiceServiceBinding(this.adapter, this.controller) {
    _sub = adapter.signals.listen(
      controller.add,
      onError: (Object error, StackTrace _) =>
          controller.add(VoiceFailure('Voice service error: $error')),
      onDone: () => controller.add(const VoiceReset()),
    );
  }

  final VoiceServiceAdapter adapter;
  final VoiceSessionController controller;
  late final StreamSubscription<VoiceSignal> _sub;

  Future<void> dispose() => _sub.cancel();
}
