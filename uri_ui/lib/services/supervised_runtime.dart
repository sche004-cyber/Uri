import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'paired_runtime.dart';

/// Phase 2 UI/operations: the supervised worker profile seen from the Flutter UI.
///
/// The frozen `WorkerPairedRuntime` (paired_runtime.dart, byte-identical to
/// the Phase 1 checkpoint) spawns the frozen worker named by the manifest. This
/// runtime spawns the Phase 2 COMPOSITION PROFILE (`scripts/run_uri_supervised_worker.py`)
/// instead, speaks the same framed stdio protocol, and adds the execution
/// lifecycle frames. It is an explicit, per-installation OPT-IN: the client
/// root must hold `control/ui-supervised-profile.json`; nothing in a manifest
/// or launcher is changed (no cutover). The UI never passes
/// `--allow-fixture-qualification`, never sees tickets or credentials, and
/// holds only execution ids: every state shown is re-read from the worker.
const supervisedProfileFile = 'control/ui-supervised-profile.json';
const supervisedProfileSchema = 'uri.phase2ops.ui_profile.v1';
const supervisedWorkerProfile = 'phase2d-supervised';
const supervisedWorkerEntrypoint = 'scripts/run_uri_supervised_worker.py';

const activeExecutionStates = {'queued', 'approving', 'starting', 'running'};

// Tolerant readers: a damaged field in one worker record must never throw and hide the whole history/status
// (review round 3, OPS-2R end to end). Anything of the wrong shape reads as null / empty.
String? _str(dynamic v) => v is String ? v : null;
bool? _bool(dynamic v) => v is bool ? v : null;
double? _num(dynamic v) => v is num ? v.toDouble() : null;
Map<String, dynamic>? _map(dynamic v) => v is Map ? v.cast<String, dynamic>() : null;
List<Map<String, dynamic>> _maps(dynamic v) =>
    v is List ? v.whereType<Map>().map((m) => m.cast<String, dynamic>()).toList() : const [];
const terminalExecutionStates = {'completed', 'failed', 'cancelled', 'uncertain', 'quota_paused'};

/// What the approval is bound to. Shown verbatim; `proposalDigest` and
/// `approvalDigest` are echoed on `execution_begin` so the worker can refuse an
/// approval whose provider/model/arguments/turn differ from the card displayed.
class ExecutionProposal {
  const ExecutionProposal({
    required this.proposalDigest,
    required this.approvalDigest,
    required this.turnId,
    required this.sessionId,
    required this.kind,
    required this.provider,
    required this.model,
    required this.capabilityId,
    required this.argumentDigest,
    required this.effect,
    required this.reversible,
    required this.instruction,
    required this.expectedFile,
    required this.arguments,
    required this.qualification,
  });

  factory ExecutionProposal.fromJson(Map<String, dynamic> j) => ExecutionProposal(
        proposalDigest: _str(j['proposal_digest']) ?? '',
        approvalDigest: _str(j['approval_digest']),
        turnId: _str(j['turn_id']),
        sessionId: _str(j['session_id']),
        kind: _str(j['kind']),
        provider: _str(j['provider']),
        model: _str(j['model']),
        capabilityId: _str(j['capability_id']),
        argumentDigest: _str(j['argument_digest']),
        effect: _str(j['effect']),
        reversible: _bool(j['reversible']),
        instruction: _str(j['instruction']),
        expectedFile: _str(j['expected_file']),
        arguments: _map(j['arguments']) ?? const {},
        qualification: _map(j['qualification']),
      );

  final String proposalDigest;
  final String? approvalDigest;
  final String? turnId;
  final String? sessionId;
  final String? kind;
  final String? provider;
  final String? model;
  final String? capabilityId;
  final String? argumentDigest;
  final String? effect;
  final bool? reversible;
  final String? instruction;
  final String? expectedFile;
  final Map<String, dynamic> arguments;
  final Map<String, dynamic>? qualification;
}

/// A turn result from the supervised worker: the frozen envelope plus the
/// execution proposal when approval is required.
class SupervisedTurn extends TurnResult {
  const SupervisedTurn({
    required super.state,
    super.turnId,
    super.code,
    super.message,
    super.approval,
    super.clarification,
    super.confirmation,
    super.intent,
    this.proposal,
  });

  factory SupervisedTurn.fromJson(Map<String, dynamic> v) => SupervisedTurn(
        state: _str(v['state']) ?? 'unknown',
        turnId: _str(v['turn_id']),
        code: _str(v['code']),
        message: _str(v['message']),
        approval: _map(v['approval_request']),
        clarification: _map(v['clarification']),
        confirmation: _map(v['confirmation']),
        intent: _map(v['intent']),
        proposal: _map(v['execution_proposal']) == null ? null : ExecutionProposal.fromJson(_map(v['execution_proposal'])!),
      );

  final ExecutionProposal? proposal;
}

class ExecutionHandle {
  const ExecutionHandle({required this.id, required this.turnId, required this.state, required this.proposalDigest});
  factory ExecutionHandle.fromJson(Map<String, dynamic> j) => ExecutionHandle(
      id: _str(j['execution_id']) ?? '',
      turnId: _str(j['turn_id']) ?? '',
      state: _str(j['state']) ?? 'uncertain',
      proposalDigest: _str(j['proposal_digest']) ?? '');
  final String id;
  final String turnId;
  final String state;
  final String proposalDigest;
}

/// One execution as the worker reports it: its durable record plus the live
/// ledger, journal and server views. Never UI-derived.
class ExecutionStatus {
  const ExecutionStatus({
    required this.id,
    required this.turnId,
    required this.sessionId,
    required this.state,
    required this.reason,
    required this.code,
    required this.message,
    required this.requestText,
    required this.proposal,
    required this.taskId,
    required this.cancelRequested,
    required this.bridgeOutcome,
    required this.failureCategory,
    required this.evidence,
    required this.queuedAt,
    required this.approvingAt,
    required this.startingAt,
    required this.runningAt,
    required this.endedAt,
    required this.ledger,
    required this.journal,
    required this.serverTurn,
    required this.decision,
    required this.recordedState,
    required this.corroboration,
  });

  factory ExecutionStatus.fromJson(Map<String, dynamic> j) => ExecutionStatus(
        id: _str(j['execution_id']) ?? '',
        turnId: _str(j['turn_id']),
        sessionId: _str(j['session_id']),
        state: _str(j['state']) ?? 'uncertain',
        reason: _str(j['reason']),
        code: _str(j['code']),
        message: _str(j['message']),
        requestText: _str(j['request_text']),
        proposal: _map(j['proposal']) == null ? null : ExecutionProposal.fromJson(_map(j['proposal'])!),
        taskId: _str(j['task_id']),
        cancelRequested: j['cancel_requested'] == true,
        bridgeOutcome: _str(j['bridge_outcome']),
        failureCategory: _str(j['failure_category']),
        evidence: _maps(j['evidence']),
        queuedAt: _num(j['queued_at']),
        approvingAt: _num(j['approving_at']),
        startingAt: _num(j['starting_at']),
        runningAt: _num(j['running_at']),
        endedAt: _num(j['ended_at']),
        ledger: _map(j['ledger']),
        journal: _map(j['journal']),
        serverTurn: _map(j['server_turn']),
        decision: _str(j['decision']),
        recordedState: _str(j['recorded_state']),
        corroboration: _map(j['corroboration']),
      );

  final String id;
  final String? turnId;
  final String? sessionId;
  final String state;
  final String? reason;
  final String? code;
  final String? message;
  final String? requestText;
  final ExecutionProposal? proposal;
  final String? taskId;
  final bool cancelRequested;
  final String? bridgeOutcome;
  final String? failureCategory;
  final List<Map<String, dynamic>> evidence;
  final double? queuedAt;
  final double? approvingAt;
  final double? startingAt;
  final double? runningAt;
  final double? endedAt;
  final Map<String, dynamic>? ledger;
  final Map<String, dynamic>? journal;
  final Map<String, dynamic>? serverTurn;
  final String? decision;
  /// What the durable record itself says; [state] is what the worker could corroborate against ledger/journal/server.
  final String? recordedState;
  final Map<String, dynamic>? corroboration;

  bool get isTerminal => terminalExecutionStates.contains(state);
  bool get isActive => activeExecutionStates.contains(state);

  /// The ledger's task state, when the execution reached the supervisor.
  String? get ledgerTaskState => _str(_map(ledger?['task'])?['state']);
  String? get journalState => _str(journal?['state']);
  String? get serverTurnState => _str(serverTurn?['state']);
}

class ExecutionSummary {
  const ExecutionSummary({
    required this.id,
    required this.turnId,
    required this.state,
    required this.reason,
    required this.code,
    required this.provider,
    required this.model,
    required this.queuedAt,
    required this.endedAt,
    required this.cancelRequested,
  });
  factory ExecutionSummary.fromJson(Map<String, dynamic> j) => ExecutionSummary(
        id: _str(j['execution_id']) ?? '',
        turnId: _str(j['turn_id']),
        state: _str(j['state']) ?? 'uncertain',
        reason: _str(j['reason']),
        code: _str(j['code']),
        provider: _str(j['provider']),
        model: _str(j['model']),
        queuedAt: _num(j['queued_at']),
        endedAt: _num(j['ended_at']),
        cancelRequested: j['cancel_requested'] == true,
      );
  final String id;
  final String? turnId;
  final String state;
  final String? reason;
  final String? code;
  final String? provider;
  final String? model;
  final double? queuedAt;
  final double? endedAt;
  final bool cancelRequested;
  bool get isActive => activeExecutionStates.contains(state);
}

class ExecutionListing {
  const ExecutionListing({required this.executions, required this.active, required this.startup});
  final List<ExecutionSummary> executions;
  final String? active;
  final Map<String, dynamic>? startup;
}

/// Boundary to the supervised worker. Everything here comes from the real
/// worker; the UI is never the authority for any of it.
abstract class SupervisedRuntime implements PairedRuntime {
  Future<Map<String, dynamic>> preflight();
  Future<ExecutionHandle> beginExecution(String turnId, String approvalDigest, String proposalDigest);
  Future<ExecutionStatus> executionStatus(String executionId);
  Future<Map<String, dynamic>> cancelExecution(String executionId);
  Future<ExecutionListing> listExecutions();
}

/// Real implementation over the Phase 2 worker profile.
class SupervisedWorkerRuntime implements SupervisedRuntime {
  SupervisedWorkerRuntime._(this._process);

  final Process _process;
  final _pending = <Completer<Map<String, dynamic>>>[];
  bool _listening = false;
  bool _closed = false;

  /// True only when a paired client installation is configured AND its client
  /// root carries the explicit supervised-profile opt-in file. Synchronous and
  /// read-only; never creates anything.
  static bool optInConfigured(String? manifestPath) {
    final manifest = _readManifest(manifestPath);
    if (manifest == null) return false;
    return _readOptIn(manifest) != null;
  }

  static Map<String, dynamic>? _readManifest(String? manifestPath) {
    if (manifestPath == null || manifestPath.isEmpty) return null;
    try {
      final file = File(manifestPath);
      if (!file.existsSync()) return null;
      final json = jsonDecode(file.readAsStringSync());
      return json is Map<String, dynamic> ? json : null;
    } catch (_) {
      return null;
    }
  }

  static Map<String, dynamic>? _readOptIn(Map<String, dynamic> manifest) {
    final root = manifest['client_root'];
    if (root is! String || root.isEmpty) return null;
    try {
      final file = File('$root${Platform.pathSeparator}${supervisedProfileFile.replaceAll('/', Platform.pathSeparator)}');
      if (!file.existsSync()) return null;
      final json = jsonDecode(file.readAsStringSync());
      if (json is! Map<String, dynamic>) return null;
      if (json['schema'] != supervisedProfileSchema || json['worker_profile'] != supervisedWorkerProfile) return null;
      return json;
    } catch (_) {
      return null;
    }
  }

  /// Returns null when the installation has not opted in. Spawns the Phase 2
  /// worker profile from the manifest's pinned `source_root` with the same
  /// interpreter and client root the frozen worker uses, then verifies through
  /// `preflight` that the worker really is the supervised profile.
  static Future<SupervisedWorkerRuntime?> fromManifest(String? manifestPath) async {
    final manifest = _readManifest(manifestPath);
    if (manifest == null || _readOptIn(manifest) == null) return null;
    final sourceRoot = manifest['source_root'] as String;
    final entrypoint = '$sourceRoot${Platform.pathSeparator}${supervisedWorkerEntrypoint.replaceAll('/', Platform.pathSeparator)}';
    return spawn(
      interpreter: manifest['interpreter'] as String,
      entrypoint: entrypoint,
      manifestPath: manifestPath!,
      workingDirectory: manifest['client_root'] as String,
    );
  }

  /// Spawns the worker and checks its profile. `extraArgs` exists for the live
  /// test harness only (fixture qualification); `fromManifest` never passes any.
  static Future<SupervisedWorkerRuntime> spawn({
    required String interpreter,
    required String entrypoint,
    required String manifestPath,
    required String workingDirectory,
    List<String> extraArgs = const [],
  }) async {
    final process = await Process.start(
      interpreter,
      ['-B', '-I', entrypoint, '--manifest', manifestPath, ...extraArgs],
      workingDirectory: workingDirectory,
    );
    final runtime = SupervisedWorkerRuntime._(process).._listen();
    try {
      final pre = await runtime.preflight();
      if (pre['worker_profile'] != supervisedWorkerProfile || pre['production_cutover'] != false) {
        throw PairedRuntimeException('WORKER_PROFILE_MISMATCH');
      }
      final lifecycle = pre['execution_lifecycle'];
      if (lifecycle is! List || !lifecycle.contains('execution_begin') || !lifecycle.contains('execution_cancel')) {
        throw PairedRuntimeException('EXECUTION_LIFECYCLE_UNAVAILABLE');
      }
    } catch (_) {
      await runtime.close();
      rethrow;
    }
    return runtime;
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

  Future<Map<String, dynamic>> _raw(Map<String, dynamic> command) {
    if (_closed) return Future.error(PairedRuntimeException('WORKER_CLOSED'));
    final completer = Completer<Map<String, dynamic>>();
    _pending.add(completer);
    final payload = utf8.encode(jsonEncode(command));
    final header = ByteData(4)..setUint32(0, payload.length, Endian.big);
    _process.stdin.add(header.buffer.asUint8List());
    _process.stdin.add(payload);
    return completer.future.timeout(const Duration(minutes: 5), onTimeout: () {
      throw PairedRuntimeException('WORKER_TIMEOUT');
    });
  }

  Future<Map<String, dynamic>> _call(Map<String, dynamic> command) async {
    final reply = await _raw(command);
    if (reply['result'] != 'OK') {
      throw PairedRuntimeException((reply['code'] as String?) ?? 'CLIENT_COMMAND_REFUSED');
    }
    return reply['value'] as Map<String, dynamic>;
  }

  @override
  Future<Map<String, dynamic>> preflight() => _call({'command': 'preflight'});

  @override
  Future<List<HarnessStatus>> discoverHarnesses() async {
    final value = await _call({'command': 'harness_discover'});
    return _maps(value['harnesses']).map(HarnessStatus.fromJson).toList();
  }

  @override
  Future<TurnResult> startTurn(String sessionId, String text, ReasoningChoice choice) async =>
      SupervisedTurn.fromJson(await _call({
        'command': 'turn_start',
        'session_id': sessionId,
        'text': text,
        'reasoning': choice.toJson(),
      }));

  /// Frozen blocking decision (no lifecycle, no mid-run cancel). The screen
  /// uses [beginExecution]; this stays for protocol parity with the frozen UI.
  @override
  Future<TurnResult> decide(String turnId, bool approve) async =>
      SupervisedTurn.fromJson(await _call({'command': 'turn_decide', 'turn_id': turnId, 'approve': approve}));

  static const _decisionText = {'confirm': 'Confirm', 'abandon': 'Cancel that request', 'select': 'Selected option'};

  @override
  Future<TurnResult> intentDecision(String sessionId, ReasoningChoice choice, Map<String, dynamic> decision) async =>
      SupervisedTurn.fromJson(await _call({
        'command': 'turn_intent',
        'session_id': sessionId,
        'text': _decisionText[decision['decision']] ?? 'Decision',
        'reasoning': choice.toJson(),
        'intent_decision': decision,
      }));

  @override
  Future<ExecutionHandle> beginExecution(String turnId, String approvalDigest, String proposalDigest) async =>
      ExecutionHandle.fromJson(await _call({
        'command': 'execution_begin',
        'turn_id': turnId,
        'approval_digest': approvalDigest,
        'proposal_digest': proposalDigest,
      }));

  @override
  Future<ExecutionStatus> executionStatus(String executionId) async =>
      ExecutionStatus.fromJson(await _call({'command': 'execution_status', 'execution_id': executionId}));

  @override
  Future<Map<String, dynamic>> cancelExecution(String executionId) =>
      _call({'command': 'execution_cancel', 'execution_id': executionId});

  @override
  Future<ExecutionListing> listExecutions() async {
    final v = await _call({'command': 'execution_list'});
    return ExecutionListing(
      executions: _maps(v['executions']).map(ExecutionSummary.fromJson).toList(),
      active: _str(v['active']),
      startup: _map(v['startup']),
    );
  }

  @override
  Future<void> close() async {
    if (_closed) return;
    try {
      // The worker withdraws any execution still in flight (job kill) before
      // it answers CLOSED, so a closing UI never leaves a harness running.
      await _raw({'command': 'close'}).catchError((_) => <String, dynamic>{});
    } finally {
      _closed = true;
      await _process.stdin.close();
    }
  }
}
