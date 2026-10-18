import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../models/uri_turn.dart';
import '../../services/app_state.dart';
import '../../services/paired_runtime.dart' show TurnResult;
import '../../services/supervised_runtime.dart';
import 'companion_state.dart';

/// Something that can say what URI is doing right now.
///
/// Sources are observed, never asked to act. The orb, the status strip
/// and the intelligence overview all read [signal]; nothing writes back.
abstract class CompanionStateSource extends ChangeNotifier {
  CompanionSignal get signal;
  String get name;
}

/// Derives a signal from the UI-side [AppState] only: the Hybrid `/ask`
/// conversation (the client that answers it decides what is true).
///
/// This is NOT the Phase 2 worker contract (that is
/// [SupervisedCompanionSource]); it is the mapping for the legacy chat
/// path, and every emitted detail names the fact it came from:
///
/// | fact on AppState | state |
/// |---|---|
/// | `connectionStatus == unreachable` | unavailable ("URI server unreachable") |
/// | `isSendingAsk` or last turn `understanding` | thinking |
/// | last turn `proposalReady` / `awaitingApproval` AND `proposedAction != null` | awaitingApproval |
/// | last turn `proposalReady` / `awaitingApproval` without a proposal | thinking (nothing to decide yet) |
/// | last turn `executing` | working |
/// | last turn `completed` AND `result != null`, within [successHold] | success ("Reply received": the fact is that a reply arrived; this path has no execution corroboration) |
/// | last turn `failed` / `needsConnection` | error |
/// | otherwise | idle |
///
/// There is no listening/speaking fact on AppState, so this source never
/// emits those states. When [dataIsMock] is true (the preview's
/// `MockUriClient`), every signal is flagged `simulated`.
class AppStateCompanionSource extends CompanionStateSource {
  AppStateCompanionSource(
    this._appState, {
    this.successHold = const Duration(seconds: 4),
    this.dataIsMock = false,
  }) {
    _appState.addListener(_recompute);
    _recompute();
  }

  final AppState _appState;
  final Duration successHold;
  final bool dataIsMock;
  CompanionSignal _signal = const CompanionSignal.idle();
  Timer? _successTimer;
  String? _lastCompletedTurnId;

  @override
  String get name => 'AppState';

  @override
  CompanionSignal get signal => _signal;

  void _recompute() {
    final next = _derive().copyWith(simulated: dataIsMock);
    if (next != _signal) {
      _signal = next;
      notifyListeners();
    }
  }

  CompanionSignal _derive() {
    final s = _appState;
    if (s.connectionStatus == BackendConnectionStatus.unreachable) {
      return const CompanionSignal(
        state: CompanionState.unavailable,
        detail: 'URI server unreachable',
        sourceName: 'AppState.connectionStatus',
      );
    }
    if (s.isSendingAsk) {
      return const CompanionSignal(
        state: CompanionState.thinking,
        detail: 'Understanding your request',
        sourceName: 'AppState.isSendingAsk',
      );
    }
    if (s.conversation.isEmpty) return const CompanionSignal.idle();
    final last = s.conversation.last;
    switch (last.stage) {
      case TurnStage.understanding:
        return const CompanionSignal(
          state: CompanionState.thinking,
          detail: 'Understanding your request',
          sourceName: 'UriTurn.stage',
        );
      case TurnStage.proposalReady:
      case TurnStage.awaitingApproval:
        final proposal = last.proposedAction;
        if (proposal == null) {
          return const CompanionSignal(
            state: CompanionState.thinking,
            detail: 'Waiting for a proposal',
            sourceName: 'UriTurn.stage (no proposedAction yet)',
          );
        }
        return CompanionSignal(
          state: CompanionState.awaitingApproval,
          detail: proposal.title,
          sourceName: 'UriTurn.proposedAction',
        );
      case TurnStage.executing:
        return const CompanionSignal(
          state: CompanionState.working,
          detail: 'Carrying out the approved action',
          sourceName: 'UriTurn.stage',
        );
      case TurnStage.completed:
        if (last.result == null) return const CompanionSignal.idle();
        if (_lastCompletedTurnId != last.id) {
          _lastCompletedTurnId = last.id;
          _successTimer?.cancel();
          _successTimer = Timer(successHold, _recompute);
        }
        if (_successTimer?.isActive ?? false) {
          return CompanionSignal(
            state: CompanionState.success,
            detail: 'Reply received: ${last.result!.summary}',
            sourceName:
                'UriTurn.result (server reply, not an execution receipt)',
          );
        }
        return const CompanionSignal.idle();
      case TurnStage.failed:
        return CompanionSignal(
          state: CompanionState.error,
          detail: last.failureReason ?? 'The last request failed',
          sourceName: 'UriTurn.failureReason',
        );
      case TurnStage.needsConnection:
        return CompanionSignal(
          state: CompanionState.error,
          detail: 'Needs ${last.requiredConnectionName ?? 'a connection'}',
          sourceName: 'UriTurn.requiredConnection',
        );
      case TurnStage.cancelled:
        return const CompanionSignal.idle();
    }
  }

  @override
  void dispose() {
    _successTimer?.cancel();
    _appState.removeListener(_recompute);
    super.dispose();
  }
}

/// The Phase 2 worker contract (`docs/architecture/PHASE2CLOSE_UI_READINESS.md`
/// section 3) over the accepted [SupervisedRuntime] interface. Polls
/// `preflight`, `listExecutions` and `executionStatus`; never begins,
/// decides or cancels anything.
///
/// | worker fact | state |
/// |---|---|
/// | runtime null (no opt-in) or `preflight` throws / reports `worker_profile != phase2d-supervised` | unavailable |
/// | pending turn with `INTENT_CLARIFICATION` / `INTENT_CONFIRMATION_REQUIRED` | awaitingApproval ("needs you: clarify/confirm") |
/// | pending turn `approval_required` with an `execution_proposal` | awaitingApproval |
/// | `executionStatus.state in {queued, approving, starting, running}` | working (no percentage: the worker reports none) |
/// | `completed` (the worker's `state`, which it corroborates against ledger/journal/server; `recordedState` alone never counts) within [successHold] | success |
/// | `uncertain`, `failed`, `quota_paused`, code `APPROVAL_REFUSED_NOT_APPLIED*` | error (reason verbatim) |
/// | `listExecutions().active == null`, no pending turn | idle |
///
/// Pending turns are reported by whoever starts them through
/// [noteTurn]; this source does not start turns. Not wired in this
/// phase (no worker in the preview); covered by tests with a fake
/// runtime.
class SupervisedCompanionSource extends CompanionStateSource {
  SupervisedCompanionSource(
    this._runtime, {
    this.pollInterval = const Duration(seconds: 1),
    this.successHold = const Duration(seconds: 4),
    bool autoStart = true,
  }) {
    if (autoStart) start();
  }

  final SupervisedRuntime? _runtime;
  final Duration pollInterval;
  final Duration successHold;
  Timer? _timer;
  Timer? _successTimer;
  TurnResult? _pendingTurn;
  String? _lastCompletedId;
  CompanionSignal _signal = const CompanionSignal(
    state: CompanionState.unavailable,
    detail: 'No supervised worker',
    sourceName: 'SupervisedRuntime (absent)',
  );

  @override
  String get name => 'SupervisedRuntime';

  @override
  CompanionSignal get signal => _signal;

  void start() {
    _timer?.cancel();
    if (_runtime == null) return;
    _timer = Timer.periodic(pollInterval, (_) => refresh());
    unawaited(refresh());
  }

  /// The caller that started or decided a turn reports the worker's
  /// reply here (a [TurnResult] / [SupervisedTurn]); `null` clears it.
  void noteTurn(TurnResult? turn) {
    _pendingTurn = turn;
    unawaited(refresh());
  }

  Future<void> refresh() async {
    final next = await _derive();
    if (next != _signal) {
      _signal = next;
      notifyListeners();
    }
  }

  Future<CompanionSignal> _derive() async {
    final rt = _runtime;
    if (rt == null) return _signal;
    Map<String, dynamic> pre;
    try {
      pre = await rt.preflight();
    } catch (e) {
      return CompanionSignal(
        state: CompanionState.unavailable,
        detail: 'preflight failed: $e',
        sourceName: 'SupervisedRuntime.preflight',
      );
    }
    if (pre['worker_profile'] != 'phase2d-supervised') {
      return CompanionSignal(
        state: CompanionState.unavailable,
        detail: 'worker_profile=${pre['worker_profile']}',
        sourceName: 'SupervisedRuntime.preflight',
      );
    }

    final turn = _pendingTurn;
    if (turn != null) {
      if (turn.needsClarification) {
        return const CompanionSignal(
          state: CompanionState.awaitingApproval,
          detail: 'Needs you: clarify',
          sourceName: 'turn.code=INTENT_CLARIFICATION',
        );
      }
      if (turn.needsConfirmation) {
        return const CompanionSignal(
          state: CompanionState.awaitingApproval,
          detail: 'Needs you: confirm',
          sourceName: 'turn.code=INTENT_CONFIRMATION_REQUIRED',
        );
      }
      if (turn.needsApproval &&
          turn is SupervisedTurn &&
          turn.proposal != null) {
        return CompanionSignal(
          state: CompanionState.awaitingApproval,
          detail:
              'Approve: ${turn.proposal!.provider} / ${turn.proposal!.model}',
          sourceName: 'turn.state=approval_required + execution_proposal',
        );
      }
    }

    ExecutionListing listing;
    try {
      listing = await rt.listExecutions();
    } catch (e) {
      return CompanionSignal(
        state: CompanionState.error,
        detail: 'execution_list failed: $e',
        sourceName: 'SupervisedRuntime.listExecutions',
      );
    }
    final activeId = listing.active;
    if (activeId != null) {
      try {
        final st = await rt.executionStatus(activeId);
        if (st.isActive) {
          return CompanionSignal(
            state: CompanionState.working,
            detail:
                '${st.state}: ${st.proposal?.provider ?? ''} ${st.proposal?.model ?? ''}'
                    .trim(),
            sourceName: 'execution_status.state',
          );
        }
        return _terminal(st.id, st.state, st.reason ?? st.code);
      } catch (e) {
        return CompanionSignal(
          state: CompanionState.error,
          detail: 'execution_status failed: $e',
          sourceName: 'SupervisedRuntime.executionStatus',
        );
      }
    }
    // No active execution: the newest terminal record may still be fresh.
    ExecutionSummary? newest;
    for (final e in listing.executions) {
      if (newest == null || (e.endedAt ?? 0) > (newest.endedAt ?? 0)) {
        newest = e;
      }
    }
    if (newest != null &&
        newest.id == _lastCompletedId &&
        (_successTimer?.isActive ?? false)) {
      return _terminal(newest.id, newest.state, newest.reason ?? newest.code);
    }
    if (newest != null &&
        newest.id != _lastCompletedId &&
        newest.state == 'completed') {
      _lastCompletedId = newest.id;
      _successTimer?.cancel();
      _successTimer = Timer(successHold, refresh);
      return _terminal(newest.id, newest.state, newest.reason ?? newest.code);
    }
    if (newest != null &&
        newest.state != 'completed' &&
        newest.state != 'cancelled') {
      return _terminal(newest.id, newest.state, newest.reason ?? newest.code);
    }
    return const CompanionSignal(
      state: CompanionState.idle,
      sourceName: 'execution_list.active == null',
    );
  }

  CompanionSignal _terminal(String id, String state, String? reason) {
    switch (state) {
      case 'completed':
        return CompanionSignal(
          state: CompanionState.success,
          detail: 'Completed (corroborated by the worker)',
          sourceName: 'execution_status.state=completed',
        );
      case 'cancelled':
        return const CompanionSignal(
          state: CompanionState.idle,
          sourceName: 'execution_status.state=cancelled',
        );
      default:
        return CompanionSignal(
          state: CompanionState.error,
          detail: '$state${reason != null ? ': $reason' : ''}',
          sourceName: 'execution_status.state=$state',
        );
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _successTimer?.cancel();
    super.dispose();
  }
}

/// A scripted / manually driven source. Everything it emits is flagged
/// `simulated: true`. Used by `main_living.dart`, the onboarding demo,
/// the state showcase and tests.
class MockCompanionSource extends CompanionStateSource {
  MockCompanionSource([CompanionSignal? initial])
    : _signal = initial ?? const CompanionSignal.idle();

  CompanionSignal _signal;

  @override
  String get name => 'Mock';

  @override
  CompanionSignal get signal => _signal;

  void emit(CompanionState state, {String? detail, double? progress}) {
    set(
      CompanionSignal(
        state: state,
        detail: detail,
        progress: progress,
        simulated: true,
        sourceName: 'mock',
      ),
    );
  }

  void set(CompanionSignal signal) {
    final flagged = signal.copyWith(simulated: true);
    if (flagged == _signal) return;
    _signal = flagged;
    notifyListeners();
  }

  void clear() => set(const CompanionSignal.idle().copyWith(simulated: true));
}

/// Merges several sources by priority. The user-blocking and failure
/// states win over activity, which wins over idle, so a mock "speaking"
/// never hides a real "awaiting approval".
class CompositeCompanionSource extends CompanionStateSource {
  CompositeCompanionSource(this.sources) {
    for (final s in sources) {
      s.addListener(notifyListeners);
    }
  }

  final List<CompanionStateSource> sources;

  /// Adds a source after construction (the voice session joins the merged
  /// signal this way, whichever services builder made the composite).
  void addSource(CompanionStateSource source) {
    if (sources.contains(source)) return;
    sources.add(source);
    source.addListener(notifyListeners);
    notifyListeners();
  }

  @override
  String get name => 'Composite';

  static const List<CompanionState> _priority = [
    CompanionState.error,
    CompanionState.awaitingApproval,
    CompanionState.working,
    CompanionState.thinking,
    CompanionState.speaking,
    CompanionState.listening,
    CompanionState.success,
    CompanionState.unavailable,
    CompanionState.initializing,
    CompanionState.idle,
  ];

  @override
  CompanionSignal get signal {
    CompanionSignal? best;
    var bestRank = _priority.length;
    for (final s in sources) {
      final rank = _priority.indexOf(s.signal.state);
      if (rank < bestRank) {
        bestRank = rank;
        best = s.signal;
      }
    }
    return best ?? const CompanionSignal.idle();
  }

  /// Every contributing signal, for the intelligence overview.
  List<CompanionSignal> get all => [for (final s in sources) s.signal];

  @override
  void dispose() {
    for (final s in sources) {
      s.removeListener(notifyListeners);
    }
    super.dispose();
  }
}
