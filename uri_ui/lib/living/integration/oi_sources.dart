import 'dart:async';

import '../companion/companion_sources.dart';
import '../companion/companion_state.dart';
import '../contracts/readiness_report.dart';
import '../widgets/status_badge.dart';
import 'oi_conversation.dart';

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
      return s(CompanionState.unavailable, 'Brain $state');
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
