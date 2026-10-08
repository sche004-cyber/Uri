import 'dart:async';
import 'dart:math';

import 'package:flutter/foundation.dart';

import '../../services/integrated_runtime.dart';

/// Working-system conversation model (WS blueprint W9): renders the real
/// `uri.oi.event.v1` stream from the integrated worker.
///
/// Rules carried over from the OI UI contract:
/// * Only `core.result` / `task.step` carry action outcomes; answer text
///   never does. An answer flagged `UNVERIFIED_ACTION_CLAIM` is marked.
/// * Approval happens only through [decide], from a button. It echoes the
///   digest of the card the user saw. [send] never decides anything.
/// * Reasoning text is never received; only the tier and a progress count.
/// * The Brain selection changes only through [selectBrain] (explicit).
/// * Health (WS hardening): [brainHealth] is the worker's READY / BUSY /
///   DEGRADED / UNAVAILABLE / RECOVERING report. A Brain restart is an
///   explicit request ([brainAction]) the worker refuses while a turn runs.
/// * Liveness (R-BUSY): while a turn runs and nothing arrives, the monitor
///   asks the worker for the job's state with a bound longer than the
///   worker's longest legitimate block. No answer = unresponsive; an answer
///   with a long-silent job = stalled. Both offer Restart worker. A restart
///   never retries the interrupted turn; its outcome is reported as unknown.

enum OiRole { user, uri, system }

class OiMessage {
  OiMessage({required this.role, required this.text, this.turnId});
  final OiRole role;
  String text;
  final String? turnId;

  /// Answer-channel status (COMPLETE, CANCELLED, ...) once done.
  String? answerStatus;

  /// Core's authoritative code for an action turn (SETTLED_VERIFIED, ...).
  String? coreCode;
  String? coreMessage;

  /// FAST / NORMAL tier actually used, and the route (answer, core, plan...).
  String? tier;
  String? route;
  int thinkingChars = 0;
  List<String> flags = const [];
  Map<String, dynamic> metrics = const {};
  String? errorCode;
  String? errorMessage;
  List<String> recoveryOptions = const [];
  bool streaming = false;
  String? finishedStatus;

  bool get unverifiedClaim => flags.contains('UNVERIFIED_ACTION_CLAIM');
}

class OiApproval {
  const OiApproval({
    required this.turnId,
    required this.capabilityId,
    required this.arguments,
    required this.approvalDigest,
    this.effect,
    this.reversible,
  });
  final String turnId;
  final String capabilityId;
  final Map<String, dynamic> arguments;
  final String approvalDigest;
  final String? effect;
  final bool? reversible;
}

class OiConfirmation {
  const OiConfirmation({required this.turnId, required this.message, required this.data});
  final String turnId;
  final String? message;
  final Map<String, dynamic> data;
}

/// Depth the user asks for on the next turn (`auto` lets the policy decide).
enum OiDepth { auto, fast, normal, deep }

class OiConversation extends ChangeNotifier {
  OiConversation(
    this.runtime, {
    String? sessionId,
    this.respawn,
    this.probeAfter = const Duration(seconds: 20),
    this.probeTimeout = const Duration(seconds: 40),
    this.stalledAfter = const Duration(seconds: 90),
  }) : sessionId = sessionId ?? _uuid4() {
    _sub = runtime.events.listen(_onEvent);
  }

  /// The current worker. Replaced only by [restartWorker].
  IntegratedRuntime runtime;
  final String sessionId;
  late StreamSubscription<Map<String, dynamic>> _sub;

  /// Starts a fresh worker for [restartWorker] (null: restart unavailable).
  final Future<IntegratedRuntime?> Function()? respawn;

  /// Silence before the monitor probes a running turn.
  final Duration probeAfter;

  /// Probe bound. Longer than the worker's longest legitimate block (a
  /// continuation joins its finishing job for up to 30 s, `JOIN_S`).
  final Duration probeTimeout;

  /// A job that is alive but has sent nothing for this long is "stalled".
  final Duration stalledAfter;

  Timer? _monitor;
  bool _probing = false;
  DateTime _lastFrame = DateTime.now();

  /// The worker did not answer a status probe within [probeTimeout].
  bool workerUnresponsive = false;

  /// The worker answers, but the running job has been silent for [stalledAfter].
  bool turnStalled = false;
  bool restarting = false;
  Map<String, dynamic> turnStatus = const {};
  Map<String, dynamic> brainHealth = const {};

  final List<OiMessage> messages = [];
  final Map<String, OiMessage> _byTurn = {};

  /// Events for a turn id this model has not registered yet (defensive: the
  /// worker writes the reply first, but stream and future callbacks may still
  /// interleave). Replayed by [_begin]; bounded.
  final Map<String, List<Map<String, dynamic>>> _early = {};

  /// Jobs started vs `turn.finished` received, per turn. A turn is active until every job it started (the turn
  /// itself, then each confirm/decide continuation) has finished, so the original job's late `turn.finished`
  /// cannot end a continuation that is still running (Codex WS round 2).
  final Map<String, int> _jobs = {};
  final Map<String, int> _finishes = {};

  String? activeTurnId;
  String companionState = 'idle';
  OiApproval? pendingApproval;
  OiConfirmation? pendingConfirmation;
  String? lastError;
  bool workerExited = false;
  OiDepth depth = OiDepth.auto;

  Map<String, dynamic> brainStatus = const {};
  Map<String, dynamic> catalog = const {};
  List<String> memory = const [];
  Map<String, dynamic> cloud = const {};

  /// When the `oi_turn` that is awaiting its reply was sent (Codex H-r1 F4).
  DateTime? _sendingSince;

  bool get busy => activeTurnId != null || _sendingSince != null;
  bool get brainReady => brainStatus['state'] == 'READY';

  /// READY / BUSY / DEGRADED / UNAVAILABLE / RECOVERING, or null before the
  /// first health report.
  String? get healthState => brainHealth['state'] as String?;

  /// The worker needs the user's attention (offer Restart worker).
  bool get workerTrouble => workerUnresponsive || turnStalled || workerExited;
  String get selectedRowId {
    final rows = (catalog['rows'] as List?) ?? const [];
    for (final r in rows) {
      if (r is Map && r['selected'] == true) return r['id'] as String;
    }
    return 'runtime-v1';
  }

  // ---- commands ---------------------------------------------------------

  Future<void> refreshStatus() async {
    try {
      brainStatus = await runtime.call({'command': 'brain_status'});
      catalog = await runtime.call({'command': 'brain_catalog'});
      lastError = null;
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
    }
    await refreshHealth(notify: false);
    notifyListeners();
  }

  Future<void> refreshHealth({bool notify = true}) async {
    try {
      brainHealth = await runtime.call({'command': 'brain_health'}).timeout(probeTimeout);
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
    } on TimeoutException {
      // The liveness probe decides about the worker; a slow health read alone does not.
    }
    if (notify) notifyListeners();
  }

  /// Explicit Brain host request: 'restart', 'stop' or 'start'.
  Future<void> brainAction(String action) async {
    if (busy) return;
    try {
      await runtime.call({'command': 'brain_restart', 'action': action});
      lastError = null;
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      messages.add(OiMessage(role: OiRole.system, text: 'Brain $action refused: ${e.code}'));
    }
    await refreshHealth();
  }

  /// Health polling and the liveness monitor (one timer).
  void startMonitor([Duration every = const Duration(seconds: 5)]) {
    _monitor?.cancel();
    _monitor = Timer.periodic(every, (_) => monitorTick());
  }

  /// One monitor step (public for tests).
  Future<void> monitorTick() async {
    if (_probing || restarting || workerExited) return;
    _probing = true;
    try {
      if (busy && DateTime.now().difference(_lastFrame) >= probeAfter) {
        await _probe();
      } else if (!busy) {
        turnStalled = false;
        await refreshHealth(notify: false);
        notifyListeners();
      }
    } finally {
      _probing = false;
    }
  }

  Future<void> _probe() async {
    final Map<String, dynamic> st;
    try {
      st = await runtime.call({'command': 'oi_turn_status'}).timeout(probeTimeout);
    } on TimeoutException {
      workerUnresponsive = true;
      notifyListeners();
      return;
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      notifyListeners();
      return;
    }
    workerUnresponsive = false;
    turnStatus = st;
    final t = activeTurnId;
    if (st['busy'] != true && t != null) {
      // The job ended but its turn.finished never arrived: stop waiting, claim nothing about the outcome.
      final m = _byTurn[t];
      m?.streaming = false;
      m?.finishedStatus ??= 'unknown';
      activeTurnId = null;
      turnStalled = false;
      messages.add(OiMessage(
          role: OiRole.system,
          text: 'URI finished this turn but its result did not arrive. Check before repeating any action.'));
    } else {
      final idle = (st['idle_s'] as num?)?.toDouble() ?? 0;
      turnStalled = idle >= stalledAfter.inSeconds;
    }
    notifyListeners();
  }

  /// Explicit user action: end the current worker and start a fresh one.
  /// The interrupted turn is never retried; pending cards lived in the old
  /// worker and are withdrawn (the server's expiry releases them).
  Future<void> restartWorker() async {
    final start = respawn;
    if (start == null || restarting) return;
    restarting = true;
    notifyListeners();
    final t = activeTurnId;
    if (t != null) {
      final m = _byTurn[t];
      m?.streaming = false;
      m?.finishedStatus = 'interrupted';
      final action = m?.route != null && m!.route != 'answer';
      messages.add(OiMessage(
          role: OiRole.system,
          text: action
              ? 'URI was restarted. The interrupted request was not retried and its outcome is unknown: '
                  'check whether the action happened before asking again.'
              : 'URI was restarted. The interrupted request was not retried.'));
    }
    if (pendingApproval != null || pendingConfirmation != null) {
      messages.add(OiMessage(role: OiRole.system, text: 'The open approval was withdrawn by the restart; nothing was approved.'));
    }
    if (_sendingSince != null) {
      messages.add(OiMessage(role: OiRole.system, text: 'A request was still being sent; it was not repeated and may not have started.'));
    }
    activeTurnId = null;
    _sendingSince = null;
    pendingApproval = null;
    pendingConfirmation = null;
    await _sub.cancel();
    final old = runtime;
    try {
      await old.kill();
    } catch (_) {}
    IntegratedRuntime? fresh;
    try {
      fresh = await start();
    } catch (_) {
      fresh = null;
    }
    if (fresh == null) {
      lastError = 'WORKER_RESTART_FAILED';
      workerExited = true;
      restarting = false;
      messages.add(OiMessage(role: OiRole.system, text: 'URI could not restart its worker. Close and reopen the app.'));
      notifyListeners();
      return;
    }
    runtime = fresh;
    _sub = runtime.events.listen(_onEvent);
    workerExited = false;
    workerUnresponsive = false;
    turnStalled = false;
    restarting = false;
    lastError = null;
    _lastFrame = DateTime.now();
    await refreshStatus();
  }

  Future<void> refreshMemory() async {
    try {
      final v = await runtime.call({'command': 'memory_list'});
      memory = [for (final f in (v['facts'] as List? ?? const [])) if (f is String) f];
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
    }
    notifyListeners();
  }

  Future<void> refreshCloud() async {
    try {
      cloud = await runtime.call({'command': 'cloud_policy'});
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
    }
    notifyListeners();
  }

  /// Sends the user's words as a turn. Never a decision, whatever it says.
  Future<void> send(String text) async {
    final t = text.trim();
    if (t.isEmpty || busy || restarting) return; // nothing goes to a worker that is being replaced
    messages.add(OiMessage(role: OiRole.user, text: t));
    lastError = null;
    _sendingSince = DateTime.now();
    _lastFrame = DateTime.now();
    notifyListeners();
    final rt = runtime;
    try {
      final r = await rt.call({
        'command': 'oi_turn',
        'session_id': sessionId,
        'text': t,
        'depth': depth.name,
      });
      // A late reply from a worker that was replaced by Restart URI changes nothing (Codex H-r2).
      if (!identical(rt, runtime)) return;
      _sendingSince = null;
      _begin(r['turn_id'] as String);
    } on IntegratedRuntimeException catch (e) {
      if (!identical(rt, runtime)) return;
      _sendingSince = null;
      lastError = e.code;
      if (e.code == 'WORKER_TIMEOUT') {
        // The worker said nothing for the whole bound: it may or may not have started the turn.
        workerUnresponsive = true;
        messages.add(OiMessage(
            role: OiRole.system,
            text: 'No reply from URI. The request may or may not have started; it was not repeated.'));
      } else {
        messages.add(OiMessage(role: OiRole.system, text: 'Not sent: ${e.code}'));
      }
      notifyListeners();
    }
  }

  void _begin(String turnId) {
    activeTurnId = turnId;
    _lastFrame = DateTime.now();
    _jobs[turnId] = (_jobs[turnId] ?? 0) + 1;
    final m = OiMessage(role: OiRole.uri, text: '', turnId: turnId)..streaming = true;
    messages.add(m);
    _byTurn[turnId] = m;
    for (final ev in _early.remove(turnId) ?? const <Map<String, dynamic>>[]) {
      _onEvent(ev);
    }
    notifyListeners();
  }

  Future<void> cancel() async {
    final t = activeTurnId;
    if (t == null) return;
    try {
      await runtime.call({'command': 'oi_cancel', 'turn_id': t});
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      notifyListeners();
    }
  }

  /// Button-only: approve or deny the card that is shown.
  Future<void> decide({required bool approve}) async {
    final a = pendingApproval;
    // The card's own turn may still be finishing (the worker waits for it); another turn blocks.
    if (a == null || (busy && activeTurnId != a.turnId)) return;
    pendingApproval = null;
    // Active BEFORE the command: the decision's events may arrive right after the reply.
    activeTurnId = a.turnId;
    _jobs[a.turnId] = (_jobs[a.turnId] ?? 0) + 1;
    _byTurn[a.turnId]?.streaming = true;
    notifyListeners();
    try {
      await runtime.call({
        'command': 'oi_decide',
        'turn_id': a.turnId,
        'approve': approve,
        'approval_digest': a.approvalDigest,
      });
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      if (e.code == 'WORKER_TIMEOUT') {
        // Unknown outcome: the worker may have accepted the decision. Stay busy with the job counted and offer no
        // retry; its turn.finished or a worker exit reconciles the state (Codex WS round 3).
        messages.add(OiMessage(role: OiRole.system, text: 'No reply yet from URI for this decision; waiting.'));
        notifyListeners();
        return;
      }
      _jobs[a.turnId] = (_jobs[a.turnId] ?? 1) - 1;
      if ((_finishes[a.turnId] ?? 0) >= (_jobs[a.turnId] ?? 0)) activeTurnId = null;
      _byTurn[a.turnId]?.streaming = false;
      // A definite transient refusal keeps the card; a digest mismatch or a released turn does not.
      if (e.code == 'TURN_IN_PROGRESS') pendingApproval = a;
      messages.add(OiMessage(role: OiRole.system, text: 'Decision refused: ${e.code}'));
    }
    notifyListeners();
  }

  Future<void> confirm() async {
    final c = pendingConfirmation;
    if (c == null || (busy && activeTurnId != c.turnId)) return;
    pendingConfirmation = null;
    activeTurnId = c.turnId;
    _jobs[c.turnId] = (_jobs[c.turnId] ?? 0) + 1;
    _byTurn[c.turnId]?.streaming = true;
    notifyListeners();
    try {
      await runtime.call({'command': 'oi_confirm', 'turn_id': c.turnId});
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      if (e.code == 'WORKER_TIMEOUT') {
        notifyListeners(); // unknown outcome: stay busy, no retry (see decide)
        return;
      }
      _jobs[c.turnId] = (_jobs[c.turnId] ?? 1) - 1;
      if ((_finishes[c.turnId] ?? 0) >= (_jobs[c.turnId] ?? 0)) activeTurnId = null;
      _byTurn[c.turnId]?.streaming = false;
      if (e.code == 'TURN_IN_PROGRESS') pendingConfirmation = c;
    }
    notifyListeners();
  }

  /// Withdraws a pending confirmation or approval (released as a denial).
  Future<void> abandon() async {
    final id = pendingApproval?.turnId ?? pendingConfirmation?.turnId;
    if (id == null) return;
    pendingApproval = null;
    pendingConfirmation = null;
    notifyListeners();
    try {
      await runtime.call({'command': 'oi_abandon', 'turn_id': id});
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
    }
    notifyListeners();
  }

  Future<void> selectBrain(String rowId) async {
    if (busy) return;
    try {
      await runtime.call({'command': 'brain_select', 'row_id': rowId});
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
    }
    await refreshStatus();
  }

  void setDepth(OiDepth d) {
    depth = d;
    notifyListeners();
  }

  // ---- events -----------------------------------------------------------

  void _onEvent(Map<String, dynamic> ev) {
    final type = ev['type'];
    _lastFrame = DateTime.now();
    if (workerUnresponsive || turnStalled) {
      workerUnresponsive = false;
      turnStalled = false;
    }
    if (type == 'worker.exited') {
      workerExited = true;
      activeTurnId = null;
      companionState = 'error';
      lastError = 'WORKER_EXITED';
      notifyListeners();
      return;
    }
    final turnId = ev['turn_id'] as String?;
    final data = (ev['data'] as Map?)?.cast<String, dynamic>() ?? const {};
    final m = turnId == null ? null : _byTurn[turnId];
    if (m == null && turnId != null && type != 'brain.status') {
      final q = _early.putIfAbsent(turnId, () => []);
      if (q.length < 2000) q.add(ev);
      while (_early.length > 8) {
        _early.remove(_early.keys.first);
      }
      return;
    }
    switch (type) {
      case 'companion.state':
        companionState = data['state'] as String? ?? 'idle';
      case 'turn.routed':
        m?.route = data['route'] as String?;
        m?.tier = ((data['tier'] as Map?)?['tier']) as String?;
      case 'thinking.progress':
        m?.thinkingChars = (data['chars'] as num?)?.toInt() ?? 0;
      case 'answer.delta':
        m?.text += data['text'] as String? ?? '';
      case 'answer.done':
        m?.answerStatus = data['status'] as String?;
        m?.flags = [for (final f in (data['flags'] as List? ?? const [])) '$f'];
        m?.metrics = (data['metrics'] as Map?)?.cast<String, dynamic>() ?? const {};
      case 'core.result':
        m?.coreCode = data['code'] as String?;
        m?.coreMessage = data['message'] as String?;
        if (data['needs'] == 'confirmation' && turnId != null) {
          pendingConfirmation = OiConfirmation(
            turnId: turnId,
            message: data['message'] as String?,
            data: (data['confirmation'] as Map?)?.cast<String, dynamic>() ?? const {},
          );
        }
      case 'approval.required':
        if (turnId != null) {
          pendingApproval = OiApproval(
            turnId: turnId,
            capabilityId: data['capability_id'] as String? ?? '?',
            arguments: (data['arguments'] as Map?)?.cast<String, dynamic>() ?? const {},
            approvalDigest: data['approval_digest'] as String? ?? '',
            effect: data['effect'] as String?,
            reversible: data['reversible'] as bool?,
          );
        }
      case 'error':
        m?.errorCode = data['code'] as String?;
        m?.errorMessage = data['message'] as String?;
        m?.recoveryOptions = [for (final o in (data['recovery_options'] as List? ?? const [])) '$o'];
      case 'brain.status':
        brainStatus = {...brainStatus, ...data};
      case 'turn.finished':
        m?.finishedStatus = data['status'] as String?;
        final done = (_finishes[turnId!] ?? 0) + 1;
        _finishes[turnId] = done;
        if (done >= (_jobs[turnId] ?? 0)) {
          m?.streaming = false;
          if (activeTurnId == turnId) activeTurnId = null;
        }
        // Memory may have changed after an approved action: re-read it (deterministic).
        if (m?.coreCode == 'SETTLED_VERIFIED') unawaited(refreshMemory());
      default:
        return; // unknown types are ignored (contract rule)
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _monitor?.cancel();
    _sub.cancel();
    super.dispose();
  }
}

String _uuid4() {
  final r = Random.secure();
  final b = List<int>.generate(16, (_) => r.nextInt(256));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  String h(int i) => b[i].toRadixString(16).padLeft(2, '0');
  final s = List.generate(16, h).join();
  return '${s.substring(0, 8)}-${s.substring(8, 12)}-${s.substring(12, 16)}-${s.substring(16, 20)}-${s.substring(20)}';
}
