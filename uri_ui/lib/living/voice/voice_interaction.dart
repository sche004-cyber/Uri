import 'dart:async';
import 'dart:math';

import '../../services/live_voice_service.dart';
import '../companion/companion_preferences.dart';
import '../companion/companion_sources.dart';
import '../companion/companion_state.dart';
import '../integration/oi_conversation.dart';
import '../presentation/presentation_controller.dart';
import 'voice_session.dart';

/// What the voice interaction is doing, as the user sees it.
enum VoiceStage {
  /// Nothing in progress.
  idle,

  /// Push-to-talk pressed; the microphone is opening.
  opening,

  /// The microphone is open (the user may be speaking).
  listening,

  /// The microphone is closed; the recogniser is producing the transcript.
  transcribing,

  /// The transcript was handed to URI; waiting for the answer.
  waiting,

  /// URI's reply audio is playing (or queued to play).
  speaking,
}

/// Sends a dictated transcript to the draft desk. Provided only when the
/// Text Intelligence draft desk is present in this build.
typedef DictationSink = Future<void> Function(
  String raw, {
  required String engine,
  List<String> uncertain,
});

/// Push-to-talk voice interaction over the live voice service.
///
/// Authority rules (plan section 2, item 4):
/// * A finished transcript is handled exactly like typed text: the local
///   presentation-command parser first, then [OiConversation.send]. Nothing
///   here calls `decide`, `confirm`, `abandon` or `selectBrain`; spoken words
///   can never approve, confirm or deny anything.
/// * When URI asks for approval, the spoken reply only points to the card.
/// * Drafting-mode words go only to the draft desk ([dictation]); without it
///   they are kept in the composer and nothing is sent.
class VoiceInteractionController extends CompanionStateSource {
  VoiceInteractionController({
    required this.service,
    required this.preferences,
    required this.presentation,
    this.oi,
    this.dictation,
    this.keepInComposer,
    this.maxSpokenChars = 900,
    this.noticeHold = const Duration(seconds: 6),
  }) {
    _subs.add(service.finals.listen(_onFinal));
    _subs.add(service.problems.listen(_onProblem));
    _subs.add(service.spokenEnds.listen(_onSpokenEnd));
    service.status.addListener(notifyListeners);
  }

  final LiveVoiceService service;
  final CompanionPreferences preferences;
  final UiPresentationController presentation;
  final OiConversation? oi;
  final DictationSink? dictation;

  /// Puts text back in the composer (drafting without a desk, or a turn that
  /// could not be sent), so spoken words are never silently lost.
  final void Function(String text)? keepInComposer;

  /// Replies longer than this are cut at a sentence end; the rest stays on
  /// screen and URI says so.
  final int maxSpokenChars;
  final Duration noticeHold;

  final List<StreamSubscription<Object?>> _subs = [];
  final Random _rng = Random();

  VoiceStage _stage = VoiceStage.idle;
  VoiceStage get stage => _stage;

  String? _captureId;
  String? _utteranceId;

  /// The last finished utterance, shown until the next one.
  VoiceFinal? lastFinal;

  /// A user-facing notice (failure, nothing heard, refused while busy).
  String? notice;
  String? noticeCode;
  Timer? _noticeTimer;

  // Reply tracking.
  OiMessage? _reply;
  int _spokenUpTo = 0;
  int _spokenChars = 0;
  bool _replyCut = false;
  bool _approvalSpoken = false;

  /// Measured per utterance: release -> final, final -> first reply audio.
  final List<Map<String, Object?>> timings = [];
  DateTime? _releasedAt;
  DateTime? _sentAt;

  bool get available => service.status.value.ready;
  bool get dictationAvailable => dictation != null;
  VoiceInputMode get mode => preferences.voice.inputMode;

  bool _disposed = false;

  // ---- push to talk ------------------------------------------------------

  /// Opens the microphone. Stops URI's speech first (barge-in).
  Future<void> pressTalk() async {
    if (_disposed) return;
    if (_stage == VoiceStage.listening || _stage == VoiceStage.opening) return;
    if (_stage == VoiceStage.transcribing) return;
    final conv = oi;
    if (mode == VoiceInputMode.conversation &&
        conv != null &&
        conv.busy &&
        _stage != VoiceStage.speaking) {
      _setNotice('BUSY', 'URI is still working on the last request.');
      return;
    }
    _stopReplyTracking();
    _setStage(VoiceStage.opening);
    if (!await service.ensureStarted()) {
      _setStage(VoiceStage.idle);
      _setNotice(
        service.status.value.problemCode ?? 'VOICE_UNAVAILABLE',
        service.status.value.problem ?? 'Voice input is not available.',
      );
      return;
    }
    final id =
        'cap-${DateTime.now().microsecondsSinceEpoch}-${_rng.nextInt(1 << 20)}';
    _captureId = id;
    _clearNotice();
    service.listenStart(
      id,
      device: preferences.voice.microphone,
      vocabulary: preferences.voice.vocabulary,
    );
    _setStage(VoiceStage.listening);
  }

  /// Closes the microphone and asks for the final transcript.
  void releaseTalk() {
    final id = _captureId;
    if (id == null || _stage != VoiceStage.listening) {
      if (_stage == VoiceStage.opening) cancel();
      return;
    }
    _releasedAt = DateTime.now();
    service.listenStop(id);
    _setStage(VoiceStage.transcribing);
  }

  /// Cancels a capture (nothing is transcribed or sent) or stops URI talking.
  void cancel() {
    final id = _captureId;
    if (id != null &&
        (_stage == VoiceStage.listening ||
            _stage == VoiceStage.opening ||
            _stage == VoiceStage.transcribing)) {
      service.listenCancel(id);
      _captureId = null;
      _setStage(VoiceStage.idle);
      return;
    }
    stopSpeaking();
  }

  /// Stops URI's reply audio and drops the rest of the reply.
  void stopSpeaking() {
    _stopReplyTracking();
    service.stopSpeaking();
    if (_stage == VoiceStage.speaking || _stage == VoiceStage.waiting) {
      _setStage(VoiceStage.idle);
    }
  }

  // ---- transcript routing --------------------------------------------------

  Future<void> _onFinal(VoiceFinal f) async {
    if (f.id != _captureId) return; // a cancelled or superseded capture
    _captureId = null;
    lastFinal = f;
    final released = _releasedAt;
    _releasedAt = null;
    timings.add({
      'audio_ms': f.audioMs,
      'transcribe_ms': f.transcribeMs,
      if (released != null)
        'release_to_final_ms': DateTime.now()
            .difference(released)
            .inMilliseconds,
    });
    if (timings.length > 50) timings.removeAt(0);
    final text = f.text.trim();
    // No letter or digit: noise the recogniser rendered as punctuation.
    if (f.reason == 'no_speech' || !RegExp(r'[A-Za-z0-9]').hasMatch(text)) {
      _setStage(VoiceStage.idle);
      _setNotice('NO_SPEECH', 'No speech was heard.');
      return;
    }
    if (mode == VoiceInputMode.drafting) {
      await _toDraft(f);
      return;
    }
    // Local presentation commands first, exactly as the composer does.
    final command = parseLocalUiCommand(_normaliseLeadingName(text));
    if (command != null) {
      presentation.apply(command);
      _setStage(VoiceStage.idle);
      return;
    }
    final conv = oi;
    if (conv == null) {
      keepInComposer?.call(text);
      _setStage(VoiceStage.idle);
      _setNotice(
        'NO_CONVERSATION',
        'URI is not connected. Your words are in the composer.',
      );
      return;
    }
    if (conv.busy) {
      keepInComposer?.call(text);
      _setStage(VoiceStage.idle);
      _setNotice(
        'BUSY',
        'URI is still answering. Your words are in the composer; nothing was sent.',
      );
      return;
    }
    _setStage(VoiceStage.waiting);
    _sentAt = DateTime.now();
    final before = conv.messages.length;
    await conv.send(text);
    if (_disposed) return;
    // `send` added the user's message and, when the worker accepted the
    // turn, URI's streaming message after it.
    OiMessage? reply;
    for (final m in conv.messages.skip(before)) {
      if (m.role == OiRole.uri && m.turnId != null) reply = m;
    }
    if (reply == null) {
      _setStage(VoiceStage.idle);
      return; // refused; the conversation shows why
    }
    _trackReply(conv, reply);
  }

  Future<void> _toDraft(VoiceFinal f) async {
    final sink = dictation;
    if (sink == null) {
      keepInComposer?.call(f.text);
      _setStage(VoiceStage.idle);
      _setNotice(
        'DRAFTING_UNAVAILABLE',
        'Drafting by voice needs the Text Intelligence draft desk, which is not in this build. '
            'Your words are in the composer; nothing was sent.',
      );
      return;
    }
    _setStage(VoiceStage.waiting);
    try {
      await sink(f.text, engine: f.engine, uncertain: f.uncertain);
    } finally {
      if (!_disposed) _setStage(VoiceStage.idle);
    }
  }

  /// "URI, dashboard." is how a recogniser writes the spoken command the
  /// composer accepts as "URI dashboard". Only the comma after the leading
  /// name is removed; nothing else is rewritten.
  static String _normaliseLeadingName(String text) => text.replaceFirst(
    RegExp(r'^\s*uri\s*[,:]\s*', caseSensitive: false),
    'URI ',
  );

  // ---- reply speech --------------------------------------------------------

  void _trackReply(OiConversation conv, OiMessage reply) {
    _reply = reply;
    _spokenUpTo = 0;
    _spokenChars = 0;
    _replyCut = false;
    _approvalSpoken = false;
    _utteranceId = 'utt-${DateTime.now().microsecondsSinceEpoch}';
    conv.addListener(_onConversation);
    _onConversation();
  }

  void _stopReplyTracking() {
    oi?.removeListener(_onConversation);
    _reply = null;
  }

  void _onConversation() {
    final conv = oi;
    final m = _reply;
    if (conv == null || m == null || _disposed) return;
    final speak = preferences.voice.speakReplies;
    final finished = !m.streaming;

    // An approval card: say where to look, never what to decide.
    if (!_approvalSpoken &&
        conv.pendingApproval?.turnId == m.turnId &&
        m.turnId != null) {
      _approvalSpoken = true;
      if (speak) {
        _say(
          'This needs your approval. Please review the card on screen.',
          last: false,
        );
      }
    }

    final spoken = speakableText(m.text);
    if (speak && !_replyCut) {
      final pieces = completeSentences(spoken, _spokenUpTo, finished: finished);
      for (final (end, sentence) in pieces) {
        _spokenUpTo = end;
        if (_spokenChars + sentence.length > maxSpokenChars &&
            _spokenChars > 0) {
          _replyCut = true;
          _say('The rest of the answer is on screen.', last: false);
          break;
        }
        _spokenChars += sentence.length;
        _say(sentence, last: false);
      }
    }

    if (finished) {
      conv.removeListener(_onConversation);
      _reply = null;
      if (!speak) {
        _setStage(VoiceStage.idle);
        return;
      }
      if (_spokenChars == 0 && !_approvalSpoken) {
        // No answer text: speak Core's message or the error, briefly.
        final fallback = m.coreMessage ?? m.errorMessage;
        if (fallback != null && fallback.trim().isNotEmpty) {
          _say(speakableText(fallback), last: true);
          return;
        }
        _say('', last: true);
        _setStage(VoiceStage.idle);
        return;
      }
      _say('', last: true); // closes the utterance after the queued sentences
    }
  }

  void _say(String text, {required bool last}) {
    final id = _utteranceId;
    if (id == null) return;
    if (text.isNotEmpty && _stage != VoiceStage.speaking) {
      if (_sentAt != null) {
        timings.add({
          'final_to_first_reply_sentence_ms': DateTime.now()
              .difference(_sentAt!)
              .inMilliseconds,
        });
        _sentAt = null;
      }
      _setStage(VoiceStage.speaking);
    }
    service.speak(id, text, preferences.voice, last: last);
  }

  void _onSpokenEnd((String, VoiceEndReason) e) {
    if (e.$1 != _utteranceId) return;
    if (_reply == null && _stage == VoiceStage.speaking) {
      _setStage(VoiceStage.idle);
    }
    if (e.$2 == VoiceEndReason.failed) {
      _setNotice(
        'TTS_FAILED',
        'URI could not speak the reply. It is shown on screen.',
      );
    }
  }

  // ---- problems and notices --------------------------------------------------

  void _onProblem(VoiceProblem p) {
    if (p.code == 'MIC_SILENT') {
      _setNotice(p.code, p.message);
      return;
    }
    if (p.warning) return;
    if (p.id != null && p.id == _captureId) {
      _captureId = null;
      _setStage(VoiceStage.idle);
    }
    final msg = switch (p.code) {
      'MIC_DENIED' =>
        '${p.message}. Allow microphone access for desktop apps in Settings > Privacy & security > Microphone.',
      _ => p.message,
    };
    _setNotice(p.code, msg);
  }

  void _setNotice(String code, String message) {
    noticeCode = code;
    notice = message;
    _noticeTimer?.cancel();
    _noticeTimer = Timer(noticeHold, _clearNotice);
    _emit();
  }

  void _clearNotice() {
    _noticeTimer?.cancel();
    if (notice == null) return;
    notice = null;
    noticeCode = null;
    _emit();
  }

  void _setStage(VoiceStage s) {
    if (_stage == s) return;
    _stage = s;
    _emit();
  }

  // ---- companion signal --------------------------------------------------------

  CompanionSignal _signal = const CompanionSignal.idle();

  @override
  String get name => 'Voice interaction';

  @override
  CompanionSignal get signal => _signal;

  void _emit() {
    if (_disposed) return;
    // Listening and speaking come from the voice session (real audio); this
    // source adds only what the session cannot see: transcription, and a
    // failure notice.
    final next = notice != null && !_isSoftNotice(noticeCode)
        ? CompanionSignal(
            state: CompanionState.error,
            detail: notice,
            sourceName: 'VoiceInteraction.notice',
          )
        : _stage == VoiceStage.transcribing
        ? const CompanionSignal(
            state: CompanionState.thinking,
            detail: 'Transcribing',
            sourceName: 'VoiceInteraction.transcribing',
          )
        : const CompanionSignal.idle();
    _signal = next;
    notifyListeners();
  }

  static bool _isSoftNotice(String? code) =>
      code == 'NO_SPEECH' || code == 'BUSY' || code == 'MIC_SILENT';

  @override
  void dispose() {
    _disposed = true;
    _noticeTimer?.cancel();
    _stopReplyTracking();
    for (final s in _subs) {
      s.cancel();
    }
    service.status.removeListener(notifyListeners);
    super.dispose();
  }
}

/// Text for speech from a Markdown answer: code blocks, tables, link targets
/// and formatting marks are not read aloud. The words themselves are kept.
String speakableText(String md) {
  var t = md.replaceAll('\r', '');
  t = t.replaceAll(
    RegExp(r'```[\s\S]*?(```|$)'),
    ' The code is shown on screen. ',
  );
  t = t.replaceAll(RegExp(r'!\[[^\]]*\]\([^)]*\)'), ' ');
  t = t.replaceAllMapped(RegExp(r'\[([^\]]+)\]\([^)]*\)'), (m) => m[1]!);
  t = t.replaceAll(RegExp(r'https?://\S+'), ' a link ');
  final lines = <String>[];
  for (final raw in t.split('\n')) {
    var l = raw.trim();
    if (l.isEmpty) {
      lines.add('');
      continue;
    }
    if (RegExp(r'^\|.*\|$').hasMatch(l) || RegExp(r'^[-:| ]+$').hasMatch(l)) {
      continue; // tables stay on screen
    }
    l = l.replaceFirst(RegExp(r'^#{1,6}\s+'), '');
    l = l.replaceFirst(RegExp(r'^([-*+]|\d+[.)])\s+'), '');
    l = l.replaceFirst(RegExp(r'^>\s*'), '');
    if (!RegExp(r'[.!?:;]$').hasMatch(l)) l = '$l.';
    lines.add(l);
  }
  t = lines.join('\n');
  t = t.replaceAll(RegExp(r'(\*\*|__|\*|_|`|~~)'), '');
  t = t.replaceAll(RegExp(r'[ \t]+'), ' ');
  return t.trim();
}

/// Sentences of [text] after character [from] that are complete: followed
/// by whitespace after `.`, `!` or `?`, or a paragraph break; at [finished],
/// the remainder too. Returns (end offset, sentence) pairs.
List<(int, String)> completeSentences(
  String text,
  int from, {
  required bool finished,
}) {
  final out = <(int, String)>[];
  var start = from;
  final re = RegExp(r'([.!?]["”)]*)\s+|\n\s*\n');
  for (final m in re.allMatches(text, from)) {
    final end = m.end;
    final s = text.substring(start, end).trim();
    if (s.isNotEmpty) out.add((end, s));
    start = end;
  }
  if (finished && start < text.length) {
    final s = text.substring(start).trim();
    if (s.isNotEmpty) out.add((text.length, s));
  }
  return out;
}
