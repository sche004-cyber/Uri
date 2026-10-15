import 'dart:async';

import '../companion/companion_sources.dart';
import '../companion/companion_state.dart';
import '../contracts/readiness_report.dart';
import '../widgets/status_badge.dart';
import 'oi_conversation.dart';

/// The calm Initializing look during a normal Brain startup (owner decision,
/// Ember V2.1 final). [brainStartingDetail] decides; everything it does not
/// accept stays `unavailable` with the real state named.
///
/// Runtime v1 readiness states of a normal startup.
const Set<String> brainRuntimeStarting = {'STARTING', 'LOADING'};

/// Brain host states (`brain_health.py`, host report) of a normal startup,
/// while the runtime itself still reads `STOPPED`. `WAITING_FOR_GPU` is not
/// one: the host uses it for contention that needs the user (close GPU apps),
/// and `brain_health` reports it as UNAVAILABLE (review R3-02).
const Set<String> brainHostStarting = {'STARTING_HOST', 'STARTING', 'LOADING', 'CALIBRATING', 'WAITING_FOR_LEASE'};

/// Host states that mean the Brain is not coming up: they always win over a
/// runtime snapshot that still says it is starting (review R3-01).
const Set<String> brainHostNotStarting = {'FAILED', 'STOPPED', 'STOPPING', 'RELEASE_WAIT', 'WAITING_FOR_GPU'};

/// The detail for the unavailable look: the polled runtime state, unless the
/// newer health report or the running host already names a different one
/// (review R4-N2). An older or unstamped health report never overrides it,
/// and `UNKNOWN` never replaces a known state (review R5-N2).
String brainUnavailableDetail(String runtimeState, Map<String, dynamic> health, {num? statusCheckedAt}) {
  if (brainHealthIsNewer(health, statusCheckedAt) != true) return 'Brain $runtimeState';
  final host = health['host'];
  final hostState = host is Map && host['running'] == true ? host['state'] as String? : null;
  if (brainHostNotStarting.contains(hostState)) return 'Brain $hostState';
  final readiness = health['readiness'] as String?;
  if (readiness != null && readiness != runtimeState && readiness != 'READY' && readiness != 'UNKNOWN') {
    return 'Brain $readiness';
  }
  return 'Brain $runtimeState';
}

/// Whether the `brain_health` report was taken after the `brain_status`
/// read: true or false when both carry `checked_at` (the worker stamps both),
/// null when either is missing. A failed health refresh keeps the previous
/// report, so it can be the older one (reviews R4-N1, R5-N2).
bool? brainHealthIsNewer(Map<String, dynamic> health, num? statusCheckedAt) {
  final h = health['checked_at'];
  if (h is! num || statusCheckedAt == null) return null;
  return h >= statusCheckedAt;
}

/// The detail to show while the Brain starts normally, or null.
///
/// [runtimeState] is the polled `brain_status` state (refreshed every 15 s,
/// and by `brain.status` events); [health] is the `brain_health` report
/// (refreshed every 5 s, so usually newer). The two may disagree for a few
/// seconds, so Initializing needs both to be consistent with a startup: the
/// runtime is starting or not yet up, the newer readiness is starting (or has
/// just become READY), and the running host reports nothing that means
/// failure or stop. A failure in either snapshot is never shown as
/// Initializing.
String? brainStartingDetail(String? runtimeState, Map<String, dynamic> health, {num? statusCheckedAt}) {
  if (runtimeState != 'STOPPED' && !brainRuntimeStarting.contains(runtimeState)) return null;
  final newer = brainHealthIsNewer(health, statusCheckedAt);
  // A health report older than the status read says nothing current: the
  // runtime state decides alone (review R5-N2/N3).
  if (newer == false) return brainRuntimeStarting.contains(runtimeState) ? 'Brain loading' : null;
  final host = health['host'];
  final hostState = host is Map && host['running'] == true ? host['state'] as String? : null;
  if (brainHostNotStarting.contains(hostState)) return null;
  // Without timestamps the age is unknown: a STOPPED runtime is a startup
  // only while a Brain host is running (review R4-N1).
  if (newer == null && runtimeState == 'STOPPED' && hostState == null) return null;
  final readiness = health['readiness'] as String? ?? runtimeState;
  // READY here means the newer snapshot has just seen the Brain come up while
  // the older one still says starting or stopped: stay calm, not depleted.
  final starting = readiness == 'READY' ||
      brainRuntimeStarting.contains(readiness) ||
      (readiness == 'STOPPED' && brainHostStarting.contains(hostState));
  if (!starting) return null;
  return hostState == 'WAITING_FOR_LEASE' ? 'Waiting for the GPU' : 'Brain loading';
}

/// Companion signal from the real OI event stream (WS blueprint W9).
///
/// `companion.state` comes from the orchestrator. A pending approval card or
/// confirmation, Brain unavailability, and a worker exit are derived from
/// the same authoritative stream. Listening stays without a source: there is
/// no voice layer in this integration.
///
/// Success: a turn whose `turn.finished` status is `ok` shows `success` for
/// [successHold], then idle. The orchestrator allowlists `ok` (a complete
/// Brain answer, or Core's `SETTLED_VERIFIED` reply; `core_turn_status`), so
/// the UI adds no judgement of its own. Turns that finished before this
/// source existed never celebrate (finding F-SUCCESS, Ember V2).
class OiCompanionSource extends CompanionStateSource {
  OiCompanionSource(
    this.conversation, {
    this.successHold = const Duration(seconds: 4),
  }) {
    _seenFinish = _lastFinish(conversation);
    conversation.addListener(_update);
    _update();
  }

  final OiConversation conversation;
  final Duration successHold;
  Timer? _successTimer;

  /// The latest finished URI turn already accounted for (and its status), so
  /// one finish is celebrated once.
  (String?, String?)? _seenFinish;
  CompanionSignal _signal = const CompanionSignal(state: CompanionState.idle, sourceName: 'URI');

  @override
  String get name => 'Operational Intelligence';

  @override
  CompanionSignal get signal => _signal;

  static (String?, String?)? _lastFinish(OiConversation c) {
    for (final m in c.messages.reversed) {
      if (m.role == OiRole.uri && m.turnId != null && m.finishedStatus != null) return (m.turnId, m.finishedStatus);
    }
    return null;
  }

  void _update() {
    final c = conversation;
    final finish = _lastFinish(c);
    if (finish != null && finish != _seenFinish) {
      _seenFinish = finish;
      _successTimer?.cancel();
      // A later finish that is not ok ends any celebration still running (review R1-01).
      if (finish.$2 == 'ok') _successTimer = Timer(successHold, _update);
    }
    // A new turn in flight is not the one that succeeded: stop celebrating it (review R1-01).
    final active = c.activeTurnId;
    if (active != null && active != _seenFinish?.$1) _successTimer?.cancel();
    var next = _derive(c);
    if (next.state == CompanionState.idle && (_successTimer?.isActive ?? false)) {
      next = const CompanionSignal(
        state: CompanionState.success,
        detail: 'Done',
        sourceName: 'URI',
        simulated: false,
      );
    }
    if (next.state != _signal.state || next.detail != _signal.detail) {
      _signal = next;
      notifyListeners();
    }
  }

  static CompanionSignal _derive(OiConversation c) {
    CompanionSignal s(CompanionState st, [String? d]) =>
        CompanionSignal(state: st, detail: d, sourceName: 'URI', simulated: false);
    if (c.workerExited) return s(CompanionState.error, 'URI worker stopped');
    if (c.pendingApproval != null) return s(CompanionState.awaitingApproval, 'Approval needed');
    if (c.pendingConfirmation != null) return s(CompanionState.awaitingApproval, 'Please confirm');
    switch (c.companionState) {
      case 'thinking':
        return s(CompanionState.thinking);
      case 'speaking':
        return s(CompanionState.speaking);
      case 'waiting_user':
        return s(CompanionState.awaitingApproval);
      case 'error':
        return s(CompanionState.error, c.lastError);
    }
    final state = c.brainStatus['state'];
    if (state != null && state != 'READY' && c.selectedRowId == 'runtime-v1') {
      // A normal startup is not a failure: the calm Initializing look.
      // Stopped, failed and unknown states stay unavailable, and the detail
      // keeps naming the real state.
      final at = c.brainStatus['checked_at'];
      final statusAt = at is num ? at : null;
      final starting = brainStartingDetail(state as String?, c.brainHealth, statusCheckedAt: statusAt);
      if (starting != null) return s(CompanionState.initializing, starting);
      return s(CompanionState.unavailable, brainUnavailableDetail('$state', c.brainHealth, statusCheckedAt: statusAt));
    }
    return s(CompanionState.idle);
  }

  @override
  void dispose() {
    _successTimer?.cancel();
    conversation.removeListener(_update);
    super.dispose();
  }
}

/// Readiness from the integrated worker: Brain status, the catalog and
/// harness discovery. Read-only. It never selects, qualifies or logs in.
class OiReadinessSource extends ReadinessSource {
  OiReadinessSource(this.conversation) {
    conversation.addListener(notifyListeners);
  }

  final OiConversation conversation;
  List<HarnessFact> _harnesses = const [];

  @override
  bool get isSimulated => false;

  @override
  List<HarnessFact> get harnesses => _harnesses;

  @override
  List<ClientFact> get clients => const [];

  @override
  List<PermissionFact> get permissions => const [];

  @override
  List<ReadinessCheck> get checks {
    final b = conversation.brainStatus;
    final st = b['state'] as String?;
    final rows = (conversation.catalog['rows'] as List?) ?? const [];
    return [
      ReadinessCheck(
        id: 'worker',
        label: 'URI worker (integrated profile)',
        status: conversation.workerExited ? TruthStatus.unavailable : TruthStatus.qualified,
        detail: conversation.workerExited ? 'stopped' : 'connected',
      ),
      ReadinessCheck(
        id: 'brain',
        label: 'Runtime v1 Brain',
        status: st == 'READY'
            ? TruthStatus.qualified
            : (st == null ? TruthStatus.unavailable : TruthStatus.configured),
        detail: [st ?? 'unknown', if (b['model_id'] != null) '${b['model_id']}', if (b['artifacts'] != null) 'artifacts ${b['artifacts']}'].join(' · '),
      ),
      for (final r in rows)
        if (r is Map && r['id'] != 'runtime-v1')
          ReadinessCheck(
            id: 'brain-row-${r['id']}',
            label: '${r['display']}',
            status: r['selectable'] == true ? TruthStatus.qualified : TruthStatus.unavailable,
            detail: (r['why_not'] ?? r['note'] ?? r['qualification'])?.toString(),
          ),
    ];
  }

  @override
  Future<void> refresh() async {
    await conversation.refreshStatus();
    try {
      final v = await conversation.runtime.call({'command': 'harness_discover'});
      final list = v['harnesses'];
      _harnesses = [
        if (list is List)
          for (final h in list)
            if (h is Map)
              HarnessFact(
                id: '${h['harness_id'] ?? '?'}',
                displayName: '${h['harness_id'] ?? '?'}',
                installed: h['installed'] == true,
                authState: '${h['auth_state'] ?? 'unknown'}',
                qualification: '${h['qualification'] ?? 'not_qualified'}',
                usable: h['usable'] == true,
                requiredAction: h['required_user_action'] as String?,
                simulated: false,
              ),
      ];
    } catch (_) {
      // Discovery refused (e.g. while a turn runs): keep the previous facts.
    }
    notifyListeners();
  }

  @override
  void dispose() {
    conversation.removeListener(notifyListeners);
    super.dispose();
  }
}
