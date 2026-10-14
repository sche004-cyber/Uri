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
class OiCompanionSource extends CompanionStateSource {
  OiCompanionSource(this.conversation) {
    conversation.addListener(_update);
    _update();
  }

  final OiConversation conversation;
  CompanionSignal _signal = const CompanionSignal(state: CompanionState.idle, sourceName: 'URI');

  @override
  String get name => 'Operational Intelligence';

  @override
  CompanionSignal get signal => _signal;

  void _update() {
    final c = conversation;
    final next = _derive(c);
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
      final p = brainNotReadyPresentation('$state', c.brainHealth);
      return CompanionSignal(
          state: p.state, headline: p.headline, detail: p.detail, sourceName: 'URI', simulated: false);
    }
    return s(CompanionState.idle);
  }

  @override
  void dispose() {
    conversation.removeListener(_update);
    super.dispose();
  }
}

/// What the companion says while the Brain is not ready (FCV-10).
///
/// Uses only the worker's readiness state, the Brain host's reported phase
/// and the host's own explanation from `brain_health`. Raw state codes stay
/// on the Dashboard; no progress or time estimate is invented.
({CompanionState state, String headline, String detail}) brainNotReadyPresentation(
    String readiness, Map<String, dynamic> health) {
  final host = health['host'] is Map ? health['host'] as Map : const {};
  final hostState = host['running'] == true ? host['state'] as String? : null;
  final explain = health['explain'];
  String say(String fallback) => explain is String && explain.trim().isNotEmpty ? explain.trim() : fallback;
  ({CompanionState state, String headline, String detail}) p(CompanionState st, String h, String d) =>
      (state: st, headline: h, detail: d);
  switch (hostState) {
    case 'CALIBRATING':
      return p(CompanionState.working, 'Checking Brain speed',
          say('The model is loaded. URI is measuring its speed before first use.'));
    case 'LOADING':
      return p(CompanionState.working, 'Loading model',
          say('The Brain is loading its model into memory. URI can answer when it is ready.'));
    case 'STARTING':
    case 'STARTING_HOST':
      return p(CompanionState.working, 'Starting Brain', say('The Brain is starting.'));
    case 'RELEASE_WAIT':
      return p(CompanionState.working, 'Waiting for GPU memory', say('Waiting for GPU memory to be released.'));
    case 'WAITING_FOR_GPU':
    case 'WAITING_FOR_LEASE':
      return p(CompanionState.unavailable, 'Waiting for GPU',
          say('Another program is using the GPU memory the Brain needs. URI waits; it does not close other apps.'));
    case 'STOPPING':
      return p(CompanionState.unavailable, 'Brain stopping', say('The Brain is stopping.'));
  }
  switch (readiness) {
    case 'LOADING':
      return p(CompanionState.working, 'Loading model',
          'The Brain is loading its model into memory. URI can answer when it is ready.');
    case 'STARTING':
      return p(CompanionState.working, 'Starting Brain', 'The Brain is starting.');
    case 'NOT_CONFIGURED':
      return p(CompanionState.unavailable, 'Brain not set up', 'No local Brain is configured on this computer.');
    case 'ARTIFACT_MISSING':
      return p(CompanionState.unavailable, 'Brain files missing',
          'The Brain model files were not found, so URI cannot load it.');
    case 'IDENTITY_MISMATCH':
    case 'FOREIGN_INSTANCE':
      return p(CompanionState.error, 'Brain check failed',
          'The running Brain does not match the approved model, so URI will not use it. Details are on the Dashboard.');
    case 'FAILED':
      return p(CompanionState.error, 'Brain failed to start',
          say('The Brain did not start correctly. Details and recovery options are on the Dashboard.'));
    case 'STOPPED':
      return p(CompanionState.unavailable, 'Brain not running', say('The Brain is not running.'));
  }
  return p(CompanionState.unavailable, 'Brain unavailable', say('URI cannot use the Brain right now.'));
}

/// Readiness from the integrated worker: Brain status, the catalog and
/// harness discovery. Read-only. It never selects, qualifies or logs in.
class OiReadinessSource extends ReadinessSource {
  OiReadinessSource(this.conversation) {
    conversation.addListener(notifyListeners);
  }

  final OiConversation conversation;
  List<HarnessFact> _harnesses = const [];
  bool _disposed = false;

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
    if (_disposed) return;
    final rt = conversation.runtime;
    await conversation.refreshStatus();
    if (_disposed || !identical(rt, conversation.runtime)) return;
    try {
      final v = await rt.call({'command': 'harness_discover'});
      if (_disposed || !identical(rt, conversation.runtime)) return;
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
    if (!_disposed && identical(rt, conversation.runtime)) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    conversation.removeListener(notifyListeners);
    super.dispose();
  }
}
