import 'dart:async';

import '../companion/companion_sources.dart';
import '../companion/companion_state.dart';
import '../contracts/readiness_report.dart';
import '../widgets/status_badge.dart';
import 'oi_conversation.dart';

/// The calm Initializing look during a normal Brain startup (owner decision,
/// Ember V2.1 final). On canonical UI V2 the FCV-10 [brainNotReadyPresentation]
/// gives state, headline and detail; Initializing replaces its `working`
/// state only when [brainStartingDetail] accepts both snapshots. The detail
/// strings of [brainStartingDetail] and [brainUnavailableDetail] are not shown
/// on this path (EMBER-V21-INTEG review R1-07); they remain the tested
/// consistency rules.
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

/// Host states during a Brain Quick Controls profile switch that are not part of the requested reload: the user
/// needs to know (GPU wait, D-1) or the switch failed. Stopping, memory release, load and calibration are the reload.
const Set<String> brainSwitchNotProgressing = {'FAILED', 'WAITING_FOR_GPU', 'WAITING_FOR_LEASE'};

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
    // brain_health is read after brain_status: its readiness is the newer fact (live FCV-R restart run showed
    // "Brain unavailable | Brain ready." for one refresh when only the older status still said not ready).
    // Brain Quick Controls integration (review IC1-03): during a profile switch turns are refused, so the companion
    // never shows ready/idle - not from the old server before it stops, nor from the new one before calibration. A
    // reload in progress (old server stopping, memory release, load, calibration) is a genuine start (Initializing,
    // D-1); a host that waits for the GPU or fails keeps its FCV-10 presentation.
    final switching = (c.brainControls['switch'] as Map?)?['pending'] == true || c.brainStatus['switching'] == true;
    if (switching && c.selectedRowId == 'runtime-v1') {
      final h = c.brainHealth['host'];
      final hs = h is Map && h['running'] == true ? h['state'] : null;
      if (hs is String && brainSwitchNotProgressing.contains(hs)) {
        final p = brainNotReadyPresentation(hs, c.brainHealth);
        return CompanionSignal(
            state: p.state, headline: p.headline, detail: p.detail, sourceName: 'URI', simulated: false);
      }
      final target = ((c.brainControls['switch'] as Map?)?['target'] as Map?)?['label'];
      return CompanionSignal(
          state: CompanionState.initializing,
          headline: 'Switching Brain',
          detail: target is String ? 'Switching the Brain to $target.' : 'The Brain is switching.',
          sourceName: 'URI',
          simulated: false);
    }
    final state = c.brainHealth['readiness'] is String ? c.brainHealth['readiness'] : c.brainStatus['state'];
    if (state != null && state != 'READY' && c.selectedRowId == 'runtime-v1') {
      final p = brainNotReadyPresentation('$state', c.brainHealth);
      // Ember V2.1: a normal startup shows the calm Initializing look. It needs both the FCV-10 presentation
      // (a startup phase, `working`) and the Ember consistency check of the two snapshots to agree, so a stop,
      // failure, GPU wait or older snapshot never looks like Initializing. Headline and detail stay FCV-10's.
      final at = c.brainStatus['checked_at'];
      final statusAt = at is num ? at : null;
      final runtimeState = c.brainStatus['state'];
      // A host state that means the Brain is not coming up never gets the calm look, whatever the snapshot age
      // (review R1-04: a stale RELEASE_WAIT next to a fresh LOADING status).
      final host = c.brainHealth['host'];
      final hostState = host is Map && host['running'] == true ? host['state'] : null;
      final starting = p.state == CompanionState.working &&
          !brainHostNotStarting.contains(hostState) &&
          brainStartingDetail(runtimeState is String ? runtimeState : null, c.brainHealth,
                  statusCheckedAt: statusAt) !=
              null;
      return CompanionSignal(
          state: starting ? CompanionState.initializing : p.state,
          headline: p.headline,
          detail: p.detail,
          sourceName: 'URI',
          simulated: false);
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

/// What the companion says while the Brain is not ready (FCV-10).
///
/// Uses only the worker's readiness state, the Brain host's reported phase
/// and the host's own explanation from `brain_health`. Raw state codes stay
/// on the Dashboard; no progress or time estimate is invented.
({CompanionState state, String headline, String detail}) brainNotReadyPresentation(
    String readiness, Map<String, dynamic> health) {
  // brain_health is read after brain_status and carries its own readiness: prefer it, so the headline and the
  // host's explanation never describe two different moments (live FCV-R: "Brain not running | The Brain is starting").
  if (health['readiness'] is String) readiness = health['readiness'] as String;
  if (health['state'] == 'RECOVERING' && (readiness == 'STOPPED' || readiness == 'UNKNOWN')) readiness = 'STARTING';
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
