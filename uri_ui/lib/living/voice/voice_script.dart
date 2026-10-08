import 'dart:async';

import 'voice_level.dart';
import 'voice_session.dart';

/// A timed sequence of [VoiceSignal]s built from recorded audio.
///
/// This is how the voice layer is exercised without live devices: real speech
/// audio is measured block by block exactly as a live microphone or playback
/// tap would measure it, and the resulting level frames, transcripts and
/// progress reports are delivered on the clock they would have arrived on.
/// Everything produced here is SIMULATED as a session (scripted words, no
/// live device), even though the audio signal itself is genuine speech.
class VoiceScript {
  VoiceScript(List<(int, VoiceSignal)> events) : events = _stableByTime(events);

  // List.sort is not guaranteed stable, and order within one millisecond
  // matters (speech onset must precede the block that triggered it).
  static List<(int, VoiceSignal)> _stableByTime(List<(int, VoiceSignal)> e) {
    final idx = List<int>.generate(e.length, (i) => i)
      ..sort((a, b) {
        final c = e[a].$1.compareTo(e[b].$1);
        return c != 0 ? c : a.compareTo(b);
      });
    return [for (final i in idx) e[i]];
  }

  /// `(atMs, signal)`, sorted by time.
  final List<(int, VoiceSignal)> events;

  int get durationMs => events.isEmpty ? 0 : events.last.$1;

  /// Every event at or before [ms], in order.
  Iterable<VoiceSignal> until(int ms) sync* {
    for (final e in events) {
      if (e.$1 > ms) break;
      yield e.$2;
    }
  }

  /// A user's spoken request: listener opens, speech is detected at the first
  /// block above the noise floor, partial transcripts follow the words with a
  /// recogniser-like delay, a final transcript closes the turn.
  static List<(int, VoiceSignal)> userTurn({
    required PcmClip clip,
    required List<WordTiming> words,
    required String text,
    required String sessionId,
    int startMs = 0,
    int leadInMs = 600,
    int partialDelayMs = 280,
    int blockMs = 20,
  }) {
    final out = <(int, VoiceSignal)>[(startMs, ListeningStarted(sessionId))];
    final speechAt = startMs + leadInMs;
    // Room tone before speech: a quiet but non-zero signal, as a real
    // microphone delivers.
    for (var t = 0; t < leadInMs; t += blockMs) {
      out.add((
        startMs + t,
        AudioLevel(VoiceSpeaker.user, 0.0012, blockMs: blockMs.toDouble()),
      ));
    }
    final env = levelEnvelope(clip.samples, clip.sampleRate, blockMs: blockMs);
    var onset = false;
    for (final f in env) {
      final at = speechAt + f.tMs;
      if (!onset && VoiceLevelMapper.dbfs(f.rms) > -45) {
        onset = true;
        out.add((at, UserSpeechStarted(sessionId)));
      }
      out.add((
        at,
        AudioLevel(VoiceSpeaker.user, f.rms, blockMs: blockMs.toDouble()),
      ));
    }
    for (var i = 0; i < words.length; i++) {
      final w = words[i];
      final upto = (w.char + w.length).clamp(0, text.length);
      out.add((
        speechAt + w.ms + partialDelayMs,
        UserTranscript(sessionId, text.substring(0, upto)),
      ));
    }
    final end = speechAt + clip.durationMs;
    for (var t = 0; t < 500; t += blockMs) {
      out.add((
        end + t,
        AudioLevel(VoiceSpeaker.user, 0.0012, blockMs: blockMs.toDouble()),
      ));
    }
    out.add((end + 450, UserTranscript(sessionId, text, isFinal: true)));
    out.add((end + 600, ListeningEnded(sessionId, VoiceEndReason.completed)));
    return out;
  }

  /// URI speaking a reply: playback starts, level frames are measured on the
  /// playback stream, the position is reported ten times a second, and the
  /// utterance ends with the audio.
  static List<(int, VoiceSignal)> uriTurn({
    required PcmClip clip,
    required List<WordTiming>? words,
    required String text,
    required String utteranceId,
    int startMs = 0,
    int blockMs = 20,
    int progressEveryMs = 100,
  }) {
    final out = <(int, VoiceSignal)>[
      (startMs, UriSpeechStarted(utteranceId, text, words: words)),
    ];
    for (final f in levelEnvelope(
      clip.samples,
      clip.sampleRate,
      blockMs: blockMs,
    )) {
      out.add((
        startMs + f.tMs,
        AudioLevel(VoiceSpeaker.uri, f.rms, blockMs: blockMs.toDouble()),
      ));
    }
    for (var t = progressEveryMs; t < clip.durationMs; t += progressEveryMs) {
      out.add((startMs + t, UriSpeechProgress(utteranceId, t)));
    }
    out.add((
      startMs + clip.durationMs,
      UriSpeechEnded(utteranceId, VoiceEndReason.completed),
    ));
    return out;
  }

  /// Parses the `words` list written by `rnd/voice/make_fixtures.ps1`,
  /// in spoken (character) order. Engines can report boundaries out of order
  /// through an event queue; each entry carries its own offsets, so sorting
  /// restores the order without losing information.
  static List<WordTiming> wordsFromJson(Map<String, dynamic> json) => [
    for (final w in (json['words'] as List).cast<Map<String, dynamic>>())
      WordTiming(
        char: w['char'] as int,
        length: w['len'] as int,
        ms: w['ms'] as int,
      ),
  ]..sort((a, b) => a.char.compareTo(b.char));
}

/// Plays a [VoiceScript] into a controller on the wall clock. Used by the
/// interactive demo and the performance run; the tests and the capture
/// harness replay deterministically with [VoiceScript.until] instead.
class VoiceScriptPlayer {
  VoiceScriptPlayer(this.script, this.target);

  final VoiceScript script;
  final VoiceSessionController target;
  final Stopwatch _clock = Stopwatch();
  Timer? _timer;
  int _next = 0;

  bool get isPlaying => _timer?.isActive ?? false;

  void play() {
    stop();
    _next = 0;
    _clock
      ..reset()
      ..start();
    _timer = Timer.periodic(const Duration(milliseconds: 10), (_) => _pump());
  }

  void _pump() {
    final now = _clock.elapsedMilliseconds;
    final events = script.events;
    while (_next < events.length && events[_next].$1 <= now) {
      target.add(events[_next].$2);
      _next++;
    }
    if (_next >= events.length) stop();
  }

  /// Stops delivering events. What the controller shows next is decided by
  /// the events already delivered and by its watchdog, never by this player.
  void stop() {
    _timer?.cancel();
    _timer = null;
    _clock.stop();
  }
}
