import 'dart:async';

import 'package:flutter/foundation.dart';

import '../companion/companion_sources.dart';
import '../companion/companion_state.dart';
import 'voice_level.dart';

/// Who the voice waveform is currently carrying.
enum VoiceSpeaker { user, uri }

/// What the voice channel is doing. Only the two speaking phases replace the
/// companion with the waveform; listening keeps the companion on screen.
enum VoicePhase {
  /// No voice activity.
  off,

  /// A listener is open but no speech has been detected yet.
  listening,

  /// The user is speaking: the waveform follows the microphone.
  userSpeaking,

  /// URI is speaking: the waveform follows URI's speech audio.
  uriSpeaking,
}

/// Why a listening session or an utterance ended. Kept so the UI and the
/// tests can tell a clean finish from an interruption.
enum VoiceEndReason { completed, cancelled, interrupted, timedOut, failed }

/// One word of URI's reply with the moment it is heard, as reported by the
/// speech engine (System.Speech `SpeakProgress`, or any engine that reports
/// word boundaries). Without these the reply is shown whole.
@immutable
class WordTiming {
  const WordTiming({
    required this.char,
    required this.length,
    required this.ms,
  });
  final int char;
  final int length;
  final int ms;
}

/// Facts reported by whatever owns the audio devices. The voice layer only
/// observes them; nothing here opens a microphone or plays a sound.
sealed class VoiceSignal {
  const VoiceSignal();
}

class ListeningStarted extends VoiceSignal {
  const ListeningStarted(this.sessionId);
  final String sessionId;
}

/// Speech detected on the open listener (voice activity onset).
class UserSpeechStarted extends VoiceSignal {
  const UserSpeechStarted(this.sessionId);
  final String sessionId;
}

/// A partial or final transcript of the user's speech.
class UserTranscript extends VoiceSignal {
  const UserTranscript(this.sessionId, this.text, {this.isFinal = false});
  final String sessionId;
  final String text;
  final bool isFinal;
}

class ListeningEnded extends VoiceSignal {
  const ListeningEnded(this.sessionId, this.reason);
  final String sessionId;
  final VoiceEndReason reason;
}

/// URI's speech audio has started playing.
class UriSpeechStarted extends VoiceSignal {
  const UriSpeechStarted(this.utteranceId, this.text, {this.words});
  final String utteranceId;
  final String text;
  final List<WordTiming>? words;
}

/// Playback position of the current utterance.
class UriSpeechProgress extends VoiceSignal {
  const UriSpeechProgress(this.utteranceId, this.positionMs);
  final String utteranceId;
  final int positionMs;
}

class UriSpeechEnded extends VoiceSignal {
  const UriSpeechEnded(this.utteranceId, this.reason);
  final String utteranceId;
  final VoiceEndReason reason;
}

/// One measured audio block. [speaker] names the stream it was measured on:
/// the microphone for [VoiceSpeaker.user], URI's playback for
/// [VoiceSpeaker.uri]. Frames from the stream that is not currently speaking
/// are ignored, so the waveform can never follow the wrong source.
class AudioLevel extends VoiceSignal {
  const AudioLevel(this.speaker, this.rms, {this.blockMs = 20});
  final VoiceSpeaker speaker;
  final double rms;
  final double blockMs;
}

/// A microphone, playback or recogniser failure.
class VoiceFailure extends VoiceSignal {
  const VoiceFailure(this.message);
  final String message;
}

/// Everything stops: task cancelled, voice disabled, backend disconnected.
class VoiceReset extends VoiceSignal {
  const VoiceReset([this.notice]);
  final String? notice;
}

/// The voice channel at one instant. Immutable; produced only by
/// [reduceVoice].
@immutable
class VoiceSession {
  const VoiceSession({
    this.phase = VoicePhase.off,
    this.sessionId,
    this.utteranceId,
    this.interruptedUtteranceId,
    this.transcript = '',
    this.transcriptFinal = false,
    this.words,
    this.positionMs = 0,
    this.lastEnd,
    this.notice,
  });

  final VoicePhase phase;
  final String? sessionId;
  final String? utteranceId;

  /// The utterance a barge-in cut off. Late events for it are dropped.
  final String? interruptedUtteranceId;

  /// The user's transcript while listening, URI's reply while it speaks.
  final String transcript;
  final bool transcriptFinal;
  final List<WordTiming>? words;
  final int positionMs;
  final VoiceEndReason? lastEnd;

  /// A short, user-facing explanation when voice stopped for a reason the
  /// user did not choose (a failure or a lost signal).
  final String? notice;

  VoiceSpeaker? get speaker => switch (phase) {
    VoicePhase.userSpeaking => VoiceSpeaker.user,
    VoicePhase.uriSpeaking => VoiceSpeaker.uri,
    _ => null,
  };

  bool get showsWaveform => speaker != null;

  /// How many characters of URI's reply have been heard, from the reported
  /// word boundaries. Null when no timing exists: then the reply is shown
  /// whole and nothing pretends to follow the audio.
  int? get spokenChars {
    final w = words;
    // Not limited to the speaking phase: after the utterance ends the reply
    // fades out showing the same words it showed while playing.
    if (w == null || w.isEmpty) return null;
    var n = 0;
    for (final word in w) {
      if (word.ms > positionMs) break;
      n = word.char + word.length;
    }
    return n;
  }

  /// Whether audio measured on [s] may drive the waveform right now.
  bool accepts(VoiceSpeaker s) => switch (phase) {
    VoicePhase.listening || VoicePhase.userSpeaking => s == VoiceSpeaker.user,
    VoicePhase.uriSpeaking => s == VoiceSpeaker.uri,
    VoicePhase.off => false,
  };

  VoiceSession _with({
    VoicePhase? phase,
    String? transcript,
    bool? transcriptFinal,
    int? positionMs,
    VoiceEndReason? lastEnd,
    bool clearNotice = false,
  }) => VoiceSession(
    phase: phase ?? this.phase,
    sessionId: sessionId,
    utteranceId: utteranceId,
    interruptedUtteranceId: interruptedUtteranceId,
    transcript: transcript ?? this.transcript,
    transcriptFinal: transcriptFinal ?? this.transcriptFinal,
    words: words,
    positionMs: positionMs ?? this.positionMs,
    lastEnd: lastEnd ?? this.lastEnd,
    notice: clearNotice ? null : notice,
  );

  @override
  String toString() =>
      'VoiceSession(${phase.name}, session: $sessionId, utterance: '
      '$utteranceId, transcript: "$transcript", notice: $notice)';
}

/// The whole voice state machine. Pure: the same session and signal always
/// give the same result, so every interruption path is testable without
/// timers or audio.
///
/// Rules that keep the UI honest:
/// * Events carry the id of the session or utterance they belong to. An event
///   for anything but the current one is stale and changes nothing, so a late
///   "URI finished" after a barge-in cannot end the user's turn.
/// * The user wins. Speech detected while URI talks is a barge-in: URI's
///   utterance is marked interrupted and the waveform switches to the
///   microphone at once. URI audio that starts while the user is speaking is
///   ignored rather than drawn over them.
/// * A failure or reset always returns to [VoicePhase.off], from any phase.
VoiceSession reduceVoice(VoiceSession s, VoiceSignal e) {
  final cutOff = s.phase == VoicePhase.uriSpeaking
      ? s.utteranceId
      : s.interruptedUtteranceId;
  final listening =
      s.phase == VoicePhase.listening || s.phase == VoicePhase.userSpeaking;
  switch (e) {
    case ListeningStarted(:final sessionId):
      return VoiceSession(
        phase: VoicePhase.listening,
        sessionId: sessionId,
        interruptedUtteranceId: cutOff,
      );
    case UserSpeechStarted(:final sessionId):
      final bargeIn = s.phase == VoicePhase.uriSpeaking;
      // Speech on a listener other than the open one is stale.
      if (listening && s.sessionId != sessionId) return s;
      return VoiceSession(
        phase: VoicePhase.userSpeaking,
        sessionId: sessionId,
        transcript: listening ? s.transcript : '',
        interruptedUtteranceId: bargeIn ? s.utteranceId : cutOff,
      );
    case UserTranscript(:final sessionId, :final text, :final isFinal):
      if (!listening || s.sessionId != sessionId) return s;
      return s._with(
        // Words on a listener that had not yet reported speech prove speech.
        phase: text.trim().isEmpty ? s.phase : VoicePhase.userSpeaking,
        transcript: text,
        transcriptFinal: isFinal,
        clearNotice: true,
      );
    case ListeningEnded(:final sessionId, :final reason):
      if (!listening || s.sessionId != sessionId) return s;
      return s._with(phase: VoicePhase.off, lastEnd: reason);
    case UriSpeechStarted(:final utteranceId, :final text, :final words):
      if (s.phase == VoicePhase.userSpeaking) return s;
      if (utteranceId == s.interruptedUtteranceId) return s;
      return VoiceSession(
        phase: VoicePhase.uriSpeaking,
        utteranceId: utteranceId,
        transcript: text,
        transcriptFinal: true,
        words: words,
        interruptedUtteranceId: s.interruptedUtteranceId,
      );
    case UriSpeechProgress(:final utteranceId, :final positionMs):
      if (s.phase != VoicePhase.uriSpeaking || s.utteranceId != utteranceId) {
        return s;
      }
      // Playback never runs backwards; a reordered report is ignored.
      if (positionMs <= s.positionMs) return s;
      return s._with(positionMs: positionMs);
    case UriSpeechEnded(:final utteranceId, :final reason):
      if (s.phase != VoicePhase.uriSpeaking || s.utteranceId != utteranceId) {
        return s;
      }
      return s._with(phase: VoicePhase.off, lastEnd: reason);
    case AudioLevel():
      return s;
    case VoiceFailure(:final message):
      return VoiceSession(
        lastEnd: VoiceEndReason.failed,
        notice: message,
        interruptedUtteranceId: cutOff,
      );
    case VoiceReset(:final notice):
      return VoiceSession(
        lastEnd: s.phase == VoicePhase.off
            ? s.lastEnd
            : VoiceEndReason.cancelled,
        notice: notice,
        interruptedUtteranceId: cutOff,
      );
  }
}

/// Holds the live [VoiceSession], the shared display level, and a watchdog.
///
/// The watchdog is what makes "stuck" impossible: if a speaking phase stops
/// receiving any audio or progress for [speechStaleAfter] (or a listener
/// stays silent past [listenStaleAfter]), the controller ends the phase itself
/// with a notice. A crashed recogniser or a lost playback callback therefore
/// cannot leave a frozen waveform on screen.
class VoiceSessionController extends ChangeNotifier {
  VoiceSessionController({
    bool simulated = false,
    this.speechStaleAfter = const Duration(seconds: 4),
    this.listenStaleAfter = const Duration(seconds: 15),
  }) : _simulated = simulated; // ignore: prefer_initializing_formals

  /// True when the events come from a fixture or script, never a live device.
  /// Every surface that shows a simulated session must say so. Set by the
  /// [VoiceServiceBinding] from its adapter, so it always describes the
  /// source that is actually feeding the session.
  bool get simulated => _simulated;
  bool _simulated;
  set simulated(bool v) {
    if (v == _simulated) return;
    _simulated = v;
    notifyListeners();
  }

  final Duration speechStaleAfter;
  final Duration listenStaleAfter;

  VoiceSession _session = const VoiceSession();
  VoiceSession get session => _session;

  // One mapper per audio stream: two instances of the same class with the
  // same constants, so each stream keeps its own speech reference level and
  // neither is treated differently.
  final Map<VoiceSpeaker, VoiceLevelMapper> _mappers = {
    VoiceSpeaker.user: VoiceLevelMapper(),
    VoiceSpeaker.uri: VoiceLevelMapper(),
  };

  /// The display level and onset emphasis the waveform draws. Separate
  /// notifiers so fifty level updates a second do not rebuild the transcript.
  final ValueNotifier<double> level = ValueNotifier<double>(0);
  final ValueNotifier<double> flux = ValueNotifier<double>(0);

  Timer? _watchdog;
  bool _disposed = false;

  void add(VoiceSignal e) {
    if (_disposed) return;
    if (e is AudioLevel) {
      if (!_session.accepts(e.speaker)) return;
      final m = _mappers[e.speaker]!..addBlock(e.rms, e.blockMs);
      level.value = m.level;
      flux.value = m.flux;
      _arm();
      return;
    }
    final next = reduceVoice(_session, e);
    if (identical(next, _session)) return;
    final wasStream = _streamOf(_session.phase);
    _session = next;
    final stream = _streamOf(next.phase);
    if (stream != wasStream) {
      // A new audio stream starts from silence rather than inheriting the
      // other stream's loudness; the waveform's own smoothing makes this a
      // glide. Listening and user speech are one stream (the microphone), so
      // speech onset does not reset it.
      if (stream != null) _mappers[stream]!.reset();
      level.value = 0;
      flux.value = 0;
    }
    _arm();
    notifyListeners();
  }

  static VoiceSpeaker? _streamOf(VoicePhase p) => switch (p) {
    VoicePhase.listening || VoicePhase.userSpeaking => VoiceSpeaker.user,
    VoicePhase.uriSpeaking => VoiceSpeaker.uri,
    VoicePhase.off => null,
  };

  void _arm() {
    _watchdog?.cancel();
    final limit = switch (_session.phase) {
      VoicePhase.off => null,
      VoicePhase.listening => listenStaleAfter,
      VoicePhase.userSpeaking || VoicePhase.uriSpeaking => speechStaleAfter,
    };
    if (limit == null) return;
    _watchdog = Timer(limit, () {
      final message = _session.phase == VoicePhase.listening
          ? 'Stopped listening: no speech heard'
          : 'Voice signal lost';
      add(VoiceReset(message));
    });
  }

  @override
  void dispose() {
    _disposed = true;
    _watchdog?.cancel();
    level.dispose();
    flux.dispose();
    super.dispose();
  }
}

/// Exposes the voice channel to the existing companion contract, so the
/// [CompositeCompanionSource] priority rules apply to it like any other
/// source: listening and speaking never hide a real error or approval.
class VoiceCompanionSource extends CompanionStateSource {
  VoiceCompanionSource(this._voice) {
    _voice.addListener(_recompute);
    _recompute();
  }

  final VoiceSessionController _voice;
  CompanionSignal _signal = const CompanionSignal.idle();

  @override
  String get name => 'Voice';

  @override
  CompanionSignal get signal => _signal;

  void _recompute() {
    final s = _voice.session;
    final next = switch (s.phase) {
      VoicePhase.off => const CompanionSignal.idle(),
      VoicePhase.listening => const CompanionSignal(
        state: CompanionState.listening,
        detail: 'Listening',
        sourceName: 'VoiceSession.listening',
      ),
      VoicePhase.userSpeaking => const CompanionSignal(
        state: CompanionState.listening,
        detail: 'You are speaking',
        sourceName: 'VoiceSession.userSpeaking',
      ),
      VoicePhase.uriSpeaking => const CompanionSignal(
        state: CompanionState.speaking,
        detail: 'URI is speaking',
        sourceName: 'VoiceSession.uriSpeaking',
      ),
    }.copyWith(simulated: _voice.simulated);
    if (next != _signal) {
      _signal = next;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _voice.removeListener(_recompute);
    super.dispose();
  }
}
