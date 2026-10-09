import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/foundation.dart';

import '../living/companion/companion_preferences.dart';
import '../living/voice/voice_catalog.dart';
import '../living/voice/voice_session.dart';

/// URI's live voice service seen from the client: the bundled
/// `assets/voice/uri_voice_service.py` in its own process, one JSON object per
/// line each way.
///
/// The process owns the microphone and the speakers and enforces half duplex
/// itself (the microphone never opens while URI's audio plays). This class
/// turns its events into the presentation's [VoiceSignal]s, so the existing
/// [VoiceSessionController] (stale-event rejection, watchdog) and the
/// companion apply unchanged. Finished transcripts and service status go out
/// on separate streams: a transcript is data for the interaction controller,
/// never a presentation event and never a decision.

/// A finished utterance from the recogniser.
@immutable
class VoiceFinal {
  const VoiceFinal({
    required this.id,
    required this.text,
    required this.engine,
    required this.reason,
    this.uncertain = const <String>[],
    this.audioMs = 0,
    this.transcribeMs = 0,
  });
  final String id;

  /// The recogniser's text exactly as produced (never cleaned here).
  final String text;
  final String engine;

  /// `completed` or `no_speech`.
  final String reason;
  final List<String> uncertain;
  final int audioMs;
  final int transcribeMs;
}

/// A microphone the service can open.
@immutable
class VoiceInputDevice {
  const VoiceInputDevice({
    required this.name,
    required this.api,
    this.isDefault = false,
  });
  final String name;
  final String api;
  final bool isDefault;
}

/// What the client knows about the voice service right now.
@immutable
class VoiceServiceStatus {
  const VoiceServiceStatus({
    this.state = VoiceServiceState.stopped,
    this.engine,
    this.inputs = const <VoiceInputDevice>[],
    this.privacy,
    this.problemCode,
    this.problem,
    this.modelLoadMs,
  });
  final VoiceServiceState state;
  final String? engine;
  final List<VoiceInputDevice> inputs;

  /// `allowed`, `denied` or `unknown` (Windows microphone privacy switches).
  final String? privacy;

  /// A specific, user-facing reason when voice input cannot work.
  final String? problemCode;
  final String? problem;
  final int? modelLoadMs;

  bool get ready => state == VoiceServiceState.ready;

  VoiceServiceStatus copyWith({
    VoiceServiceState? state,
    String? engine,
    List<VoiceInputDevice>? inputs,
    String? privacy,
    Object? problemCode = _keep,
    Object? problem = _keep,
    int? modelLoadMs,
  }) => VoiceServiceStatus(
    state: state ?? this.state,
    engine: engine ?? this.engine,
    inputs: inputs ?? this.inputs,
    privacy: privacy ?? this.privacy,
    problemCode: identical(problemCode, _keep)
        ? this.problemCode
        : problemCode as String?,
    problem: identical(problem, _keep) ? this.problem : problem as String?,
    modelLoadMs: modelLoadMs ?? this.modelLoadMs,
  );
  static const Object _keep = Object();
}

enum VoiceServiceState {
  /// Not started yet, or shut down.
  stopped,

  /// Process started; waiting for its readiness report.
  starting,

  /// Microphone and recogniser usable.
  ready,

  /// Running, but voice input cannot work ([VoiceServiceStatus.problem]).
  degraded,

  /// Cannot run at all (no runtime, no script, process died).
  unavailable,
}

/// A recoverable problem reported during a capture or a reply.
@immutable
class VoiceProblem {
  const VoiceProblem(this.code, this.message, {this.id, this.warning = false});
  final String code;
  final String message;
  final String? id;
  final bool warning;
}

/// The line transport to the voice process. Tests provide a fake.
abstract class VoiceTransport {
  Stream<Map<String, dynamic>> get events;
  void send(Map<String, Object?> command);
  Future<int> get exitCode;
  Future<void> close();
}

class ProcessVoiceTransport implements VoiceTransport {
  ProcessVoiceTransport._(this._process) {
    _process.stdout
        .transform(utf8.decoder)
        .transform(const LineSplitter())
        .listen((line) {
          try {
            final v = jsonDecode(line);
            if (v is Map<String, dynamic>) _events.add(v);
          } catch (_) {
            // Unreadable lines are dropped, never guessed at.
          }
        }, onDone: () => _events.close());
    _process.stderr.transform(utf8.decoder).listen((t) {
      if (kDebugMode) debugPrint('[voice] $t');
    });
  }

  final Process _process;
  final _events = StreamController<Map<String, dynamic>>.broadcast();

  /// Starts `python -I <script>`. [python] and [script] are resolved by
  /// [VoiceRuntimeLocator]; nothing comes from user input.
  static Future<ProcessVoiceTransport> start(
    String python,
    String script,
  ) async {
    final p = await Process.start(python, <String>[
      '-I',
      script,
    ], runInShell: false);
    return ProcessVoiceTransport._(p);
  }

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;

  @override
  void send(Map<String, Object?> command) {
    try {
      _process.stdin.writeln(jsonEncode(command));
    } catch (_) {
      // The process is gone; [exitCode] reports it.
    }
  }

  @override
  Future<int> get exitCode => _process.exitCode;

  @override
  Future<void> close() async {
    send(const {'cmd': 'shutdown'});
    final code = await _process.exitCode.timeout(
      const Duration(seconds: 3),
      onTimeout: () => -1,
    );
    if (code == -1) _process.kill();
  }
}

/// Finds the interpreter and the service script. Never searches PATH: the
/// interpreter is the provisioned voice environment or an explicit override.
class VoiceRuntimeLocator {
  const VoiceRuntimeLocator();

  static const String setupHint =
      'Install the voice runtime with uri_ui\\tool\\voice\\provision_voice_env.ps1.';

  String? python() {
    final env = Platform.environment;
    final override = env['URI_VOICE_PYTHON'];
    if (override != null && override.isNotEmpty) {
      return File(override).existsSync() ? override : null;
    }
    final base = env['LOCALAPPDATA'];
    if (base == null) return null;
    final p = '$base\\URI\\voice\\venv\\Scripts\\python.exe';
    return File(p).existsSync() ? p : null;
  }

  /// The bundled asset next to the executable (`data/flutter_assets`).
  String? script() {
    final override = Platform.environment['URI_VOICE_SERVICE_SCRIPT'];
    if (override != null && override.isNotEmpty) {
      return File(override).existsSync() ? override : null;
    }
    final exeDir = File(Platform.resolvedExecutable).parent.path;
    final p =
        '$exeDir\\data\\flutter_assets\\assets\\voice\\uri_voice_service.py';
    return File(p).existsSync() ? p : null;
  }
}

/// [VoiceServiceAdapter] over the live voice process.
class LiveVoiceService implements VoiceServiceAdapter {
  LiveVoiceService({
    Future<VoiceTransport> Function()? launch,
    this.locator = const VoiceRuntimeLocator(),
  }) : _launch = launch; // ignore: prefer_initializing_formals

  final Future<VoiceTransport> Function()? _launch;
  final VoiceRuntimeLocator locator;

  VoiceTransport? _transport;
  StreamSubscription<Map<String, dynamic>>? _sub;
  Future<bool>? _starting;
  bool _disposed = false;

  final _signals = StreamController<VoiceSignal>.broadcast();
  final _finals = StreamController<VoiceFinal>.broadcast();
  final _problems = StreamController<VoiceProblem>.broadcast();
  final _spoken = StreamController<(String, VoiceEndReason)>.broadcast();
  final _spokenStarts = StreamController<String>.broadcast();

  /// Service readiness, devices and the current problem, if any.
  final ValueNotifier<VoiceServiceStatus> status =
      ValueNotifier<VoiceServiceStatus>(const VoiceServiceStatus());

  @override
  String get name => status.value.engine == null
      ? 'Local speech recognition'
      : 'Local speech recognition (${status.value.engine})';

  @override
  bool get simulated => false;

  @override
  Stream<VoiceSignal> get signals => _signals.stream;

  Stream<VoiceFinal> get finals => _finals.stream;
  Stream<VoiceProblem> get problems => _problems.stream;

  /// Every reply utterance that ended, with how it ended.
  Stream<(String, VoiceEndReason)> get spokenEnds => _spoken.stream;

  /// The id of each reply utterance when its first audio starts playing.
  Stream<String> get spokenStarts => _spokenStarts.stream;

  /// Starts the process if it is not running. True when it is running.
  Future<bool> ensureStarted() {
    if (_disposed) return Future.value(false);
    if (_transport != null) return Future.value(true);
    return _starting ??= _start().whenComplete(() => _starting = null);
  }

  Future<bool> _start() async {
    status.value = status.value.copyWith(
      state: VoiceServiceState.starting,
      problemCode: null,
      problem: null,
    );
    VoiceTransport t;
    try {
      if (_launch != null) {
        t = await _launch();
      } else {
        if (!Platform.isWindows) {
          return _unavailable('NOT_WINDOWS', 'Live voice needs Windows.');
        }
        final py = locator.python();
        if (py == null) {
          return _unavailable(
            'VOICE_RUNTIME_MISSING',
            'The voice runtime is not installed. ${VoiceRuntimeLocator.setupHint}',
          );
        }
        final script = locator.script();
        if (script == null) {
          return _unavailable(
            'VOICE_SERVICE_MISSING',
            'The voice service file is missing from this build.',
          );
        }
        t = await ProcessVoiceTransport.start(py, script);
      }
    } catch (e) {
      return _unavailable(
        'VOICE_START_FAILED',
        'The voice service did not start: $e',
      );
    }
    if (_disposed) {
      unawaited(t.close());
      return false;
    }
    _transport = t;
    _sub = t.events.listen(_onEvent, onDone: () => _lost(t));
    unawaited(t.exitCode.then((_) => _lost(t)));
    t.send(const {'cmd': 'hello'});
    return true;
  }

  bool _unavailable(String code, String message) {
    status.value = status.value.copyWith(
      state: VoiceServiceState.unavailable,
      problemCode: code,
      problem: message,
    );
    return false;
  }

  void _lost(VoiceTransport t) {
    if (!identical(_transport, t)) return;
    _transport = null;
    _sub?.cancel();
    _sub = null;
    if (_disposed) return;
    _unavailable(
      'VOICE_SERVICE_STOPPED',
      'The voice service stopped. Press talk to start it again.',
    );
    _signals.add(const VoiceReset('Voice service stopped'));
  }

  // ---- commands --------------------------------------------------------

  void listenStart(
    String id, {
    String? device,
    double maxSeconds = 60,
    String vocabulary = '',
  }) => _transport?.send({
    'cmd': 'listen_start',
    'id': id,
    'device': device,
    'max_s': maxSeconds,
    'vocabulary': vocabulary,
  });

  void listenStop(String id) =>
      _transport?.send({'cmd': 'listen_stop', 'id': id});

  void listenCancel(String id) =>
      _transport?.send({'cmd': 'listen_cancel', 'id': id});

  /// Queues one piece of a reply. Pieces of one [id] play in order; [last]
  /// ends the utterance after it has played.
  void speak(
    String id,
    String text,
    VoicePreferences voice, {
    bool last = true,
  }) {
    final vid = voice.voiceId;
    final sep = vid?.indexOf(':') ?? -1;
    _transport?.send({
      'cmd': 'speak',
      'id': id,
      'text': text,
      'final': last,
      'voice': {
        'engine': sep > 0 ? vid!.substring(0, sep) : 'sapi',
        'name': sep > 0 ? vid!.substring(sep + 1) : '',
        'rate': voice.rate,
        'pitch': voice.pitch,
        'volume': voice.volume,
      },
    });
  }

  void stopSpeaking() => _transport?.send(const {'cmd': 'speak_stop'});

  void refreshDevices() => _transport?.send(const {'cmd': 'devices'});

  // ---- events ----------------------------------------------------------

  static VoiceEndReason _listenEnd(String? r) => switch (r) {
    'released' || 'max_length' => VoiceEndReason.completed,
    'cancelled' => VoiceEndReason.cancelled,
    _ => VoiceEndReason.failed,
  };

  static VoiceEndReason _speakEnd(String? r) => switch (r) {
    'completed' => VoiceEndReason.completed,
    'interrupted' => VoiceEndReason.interrupted,
    'stopped' || 'refused_listening' => VoiceEndReason.cancelled,
    _ => VoiceEndReason.failed,
  };

  static List<VoiceInputDevice> _inputs(Object? rows) => [
    for (final r in (rows is List ? rows : const []))
      if (r is Map && r['name'] is String)
        VoiceInputDevice(
          name: r['name'] as String,
          api: '${r['api'] ?? ''}',
          isDefault: r['default'] == true,
        ),
  ];

  void _onEvent(Map<String, dynamic> e) {
    final id = '${e['id'] ?? ''}';
    switch (e['ev']) {
      case 'ready':
        final err = e['model_error'];
        final privacy = (e['privacy'] as Map?)?['state'] as String?;
        final inputs = _inputs(e['inputs']);
        String? code;
        String? msg;
        if (err is Map) {
          code = '${err['code']}';
          msg = '${err['message']}';
        } else if (privacy == 'denied') {
          code = 'MIC_DENIED';
          msg =
              '${(e['privacy'] as Map?)?['detail'] ?? 'Windows blocks the microphone'}. '
              'Allow it in Settings > Privacy & security > Microphone.';
        } else if (inputs.isEmpty) {
          code = 'MIC_NOT_FOUND';
          msg = 'No microphone is connected or enabled.';
        }
        status.value = VoiceServiceStatus(
          state: code == null
              ? VoiceServiceState.ready
              : VoiceServiceState.degraded,
          engine: e['engine'] as String?,
          inputs: inputs,
          privacy: privacy,
          problemCode: code,
          problem: msg,
          modelLoadMs: (e['model_load_ms'] as num?)?.toInt(),
        );
      case 'devices':
        status.value = status.value.copyWith(
          inputs: _inputs(e['inputs']),
          privacy: (e['privacy'] as Map?)?['state'] as String?,
        );
      case 'listen.started':
        _signals.add(ListeningStarted(id));
      case 'listen.speech':
        _signals.add(UserSpeechStarted(id));
      case 'listen.level':
        _signals.add(
          AudioLevel(
            VoiceSpeaker.user,
            (e['rms'] as num?)?.toDouble() ?? 0,
            blockMs: (e['block_ms'] as num?)?.toDouble() ?? 20,
          ),
        );
      case 'listen.partial':
        _signals.add(UserTranscript(id, '${e['text'] ?? ''}'));
      case 'listen.closed':
        _signals.add(ListeningEnded(id, _listenEnd(e['reason'] as String?)));
        if (e['reason'] == 'max_length') {
          _problems.add(
            VoiceProblem(
              'MAX_LENGTH',
              'Stopped listening at the length limit; what was heard is being transcribed.',
              id: id,
              warning: true,
            ),
          );
        }
      case 'listen.final':
        _finals.add(
          VoiceFinal(
            id: id,
            text: '${e['text'] ?? ''}',
            engine: '${e['engine'] ?? 'unknown'}',
            reason: '${e['reason'] ?? 'completed'}',
            uncertain: [
              for (final u in (e['uncertain'] as List? ?? const [])) '$u',
            ],
            audioMs: (e['audio_ms'] as num?)?.toInt() ?? 0,
            transcribeMs: (e['transcribe_ms'] as num?)?.toInt() ?? 0,
          ),
        );
      case 'listen.warning':
        _problems.add(
          VoiceProblem(
            '${e['code']}',
            '${e['message']}',
            id: id,
            warning: true,
          ),
        );
      case 'listen.error':
        final p = VoiceProblem('${e['code']}', '${e['message']}', id: id);
        _problems.add(p);
        _signals.add(VoiceFailure(p.message));
      case 'speak.started' || 'speak.chunk':
        _signals.add(UriSpeechStarted(id, '${e['text'] ?? ''}'));
        if (e['ev'] == 'speak.started') _spokenStarts.add(id);
      case 'speak.level':
        _signals.add(
          AudioLevel(
            VoiceSpeaker.uri,
            (e['rms'] as num?)?.toDouble() ?? 0,
            blockMs: (e['block_ms'] as num?)?.toDouble() ?? 20,
          ),
        );
      case 'speak.progress':
        _signals.add(UriSpeechProgress(id, (e['ms'] as num?)?.toInt() ?? 0));
      case 'speak.ended':
        final reason = _speakEnd(e['reason'] as String?);
        _signals.add(UriSpeechEnded(id, reason));
        _spoken.add((id, reason));
      case 'speak.error':
        _problems.add(VoiceProblem('${e['code']}', '${e['message']}', id: id));
      case 'fatal':
        _unavailable('${e['code']}', '${e['message']}');
      case 'error':
        _problems.add(
          VoiceProblem('${e['code']}', '${e['message']}', warning: true),
        );
      default:
        break; // unknown events are ignored
    }
  }

  Future<void> dispose() async {
    _disposed = true;
    final t = _transport;
    _transport = null;
    await _sub?.cancel();
    if (t != null) await t.close();
    await _signals.close();
    await _finals.close();
    await _problems.close();
    await _spoken.close();
    await _spokenStarts.close();
    status.dispose();
  }
}
