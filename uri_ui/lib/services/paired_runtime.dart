import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

/// One harness row exactly as the paired client worker reports it.
class HarnessStatus {
  const HarnessStatus({
    required this.id,
    required this.installed,
    required this.version,
    required this.authState,
    required this.qualification,
    required this.usable,
    required this.requiredAction,
  });

  factory HarnessStatus.fromJson(Map<String, dynamic> json) => HarnessStatus(
    id: json['harness_id'] as String,
    installed: json['installed'] as bool,
    version: json['version'] as String?,
    authState: json['auth_state'] as String,
    qualification: json['qualification'] as String,
    usable: json['usable'] as bool,
    requiredAction: json['required_user_action'] as String?,
  );

  final String id;
  final bool installed;
  final String? version;
  final String authState;
  final String qualification;
  final bool usable;
  final String? requiredAction;
}

/// The user's explicit executor choice. There is no default and no fallback.
class ReasoningChoice {
  const ReasoningChoice(this.kind, this.provider);
  final String kind;
  final String provider;

  static const noBrain = ReasoningChoice('server_local_model', 'uri-deterministic');

  Map<String, dynamic> toJson() => {'kind': kind, 'provider': provider, 'model': null};
}

class TurnResult {
  const TurnResult({required this.state, this.turnId, this.code, this.message, this.approval,
      this.clarification, this.confirmation, this.intent});
  final String state;
  final String? turnId;
  final String? code;
  final String? message;
  final Map<String, dynamic>? approval;
  /// Intent discovery: a question URI needs answered (reference choice or missing detail).
  final Map<String, dynamic>? clarification;
  /// Intent discovery: the exact request URI will carry out, awaiting explicit confirmation.
  final Map<String, dynamic>? confirmation;
  final Map<String, dynamic>? intent;
  bool get needsApproval => state == 'approval_required';
  bool get needsClarification => clarification != null && code == 'INTENT_CLARIFICATION';
  bool get needsConfirmation => confirmation != null &&
      (code == 'INTENT_CONFIRMATION_REQUIRED' || code == 'INTENT_CONFIRMED_NOT_EXECUTED');
}

class PairedRuntimeException implements Exception {
  PairedRuntimeException(this.code);
  final String code;
  @override
  String toString() => 'PairedRuntimeException($code)';
}

/// Boundary to the paired client worker. The UI never sees credentials,
/// tickets or private state; every outcome here comes from the real worker.
abstract class PairedRuntime {
  Future<List<HarnessStatus>> discoverHarnesses();
  Future<TurnResult> startTurn(String sessionId, String text, ReasoningChoice choice);
  Future<TurnResult> decide(String turnId, bool approve);
  /// Explicit structured decision on a pending intent: confirm (digest-bound), abandon, or select.
  Future<TurnResult> intentDecision(String sessionId, ReasoningChoice choice, Map<String, dynamic> decision);
  Future<void> close();
}

/// Real implementation: spawns the exact worker named by a client manifest
/// and speaks its length-prefixed JSON frame protocol.
class WorkerPairedRuntime implements PairedRuntime {
  WorkerPairedRuntime._(this._process);

  final Process _process;
  final _pending = <Completer<Map<String, dynamic>>>[];
  bool _listening = false;

  /// Returns null when no paired client installation is configured.
  static Future<WorkerPairedRuntime?> fromManifest(String? manifestPath) async {
    if (manifestPath == null || manifestPath.isEmpty) return null;
    final manifest = jsonDecode(await File(manifestPath).readAsString()) as Map<String, dynamic>;
    final process = await Process.start(
      manifest['interpreter'] as String,
      ['-B', '-I', manifest['worker_entrypoint'] as String, '--manifest', manifestPath],
      workingDirectory: manifest['client_root'] as String,
    );
    return WorkerPairedRuntime._(process).._listen();
  }

  void _listen() {
    if (_listening) return;
    _listening = true;
    final bytes = <int>[];
    _process.stdout.listen((chunk) {
      bytes.addAll(chunk);
      while (bytes.length >= 4) {
        final size = ByteData.sublistView(Uint8List.fromList(bytes.sublist(0, 4))).getUint32(0, Endian.big);
        if (bytes.length < 4 + size) return;
        final body = utf8.decode(bytes.sublist(4, 4 + size));
        bytes.removeRange(0, 4 + size);
        if (_pending.isNotEmpty) {
          _pending.removeAt(0).complete(jsonDecode(body) as Map<String, dynamic>);
        }
      }
    }, onDone: () {
      for (final waiter in _pending) {
        waiter.completeError(PairedRuntimeException('WORKER_EXITED'));
      }
      _pending.clear();
    });
    _process.stderr.drain<void>();
  }

  Future<Map<String, dynamic>> _call(Map<String, dynamic> command) {
    final completer = Completer<Map<String, dynamic>>();
    _pending.add(completer);
    final payload = utf8.encode(jsonEncode(command));
    final header = ByteData(4)..setUint32(0, payload.length, Endian.big);
    _process.stdin.add(header.buffer.asUint8List());
    _process.stdin.add(payload);
    return completer.future.timeout(const Duration(minutes: 5), onTimeout: () {
      throw PairedRuntimeException('WORKER_TIMEOUT');
    }).then((reply) {
      if (reply['result'] != 'OK') {
        throw PairedRuntimeException((reply['code'] as String?) ?? 'CLIENT_COMMAND_REFUSED');
      }
      return reply['value'] as Map<String, dynamic>;
    });
  }

  @override
  Future<List<HarnessStatus>> discoverHarnesses() async {
    final value = await _call({'command': 'harness_discover'});
    return (value['harnesses'] as List)
        .map((h) => HarnessStatus.fromJson(h as Map<String, dynamic>))
        .toList();
  }

  TurnResult _turn(Map<String, dynamic> v) => TurnResult(
    state: v['state'] as String,
    turnId: v['turn_id'] as String?,
    code: v['code'] as String?,
    message: v['message'] as String?,
    approval: v['approval_request'] as Map<String, dynamic>?,
    clarification: v['clarification'] as Map<String, dynamic>?,
    confirmation: v['confirmation'] as Map<String, dynamic>?,
    intent: v['intent'] as Map<String, dynamic>?,
  );

  @override
  Future<TurnResult> startTurn(String sessionId, String text, ReasoningChoice choice) async =>
      _turn(await _call({
        'command': 'turn_start',
        'session_id': sessionId,
        'text': text,
        'reasoning': choice.toJson(),
      }));

  @override
  Future<TurnResult> decide(String turnId, bool approve) async =>
      _turn(await _call({'command': 'turn_decide', 'turn_id': turnId, 'approve': approve}));

  static const _decisionText = {'confirm': 'Confirm', 'abandon': 'Cancel that request', 'select': 'Selected option'};

  @override
  Future<TurnResult> intentDecision(String sessionId, ReasoningChoice choice, Map<String, dynamic> decision) async =>
      _turn(await _call({
        'command': 'turn_intent',
        'session_id': sessionId,
        'text': _decisionText[decision['decision']] ?? 'Decision',
        'reasoning': choice.toJson(),
        'intent_decision': decision,
      }));

  @override
  Future<void> close() async {
    try {
      await _call({'command': 'close'}).catchError((_) => <String, dynamic>{});
    } finally {
      await _process.stdin.close();
    }
  }
}
