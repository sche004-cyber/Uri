import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../models/uri_turn.dart';
import '../../services/app_state.dart';
import 'companion_state.dart';

/// Something that can say what URI is doing right now.
///
/// Sources are observed, never asked to act. The orb, the status strip
/// and the intelligence overview all read [signal]; nothing writes back.
abstract class CompanionStateSource extends ChangeNotifier {
  CompanionSignal get signal;
  String get name;
}

/// Derives a signal from the real UI-side [AppState] only (the mock or
/// HTTP client behind it decides what is true). Mapping follows
/// `docs/architecture/PHASE2CLOSE_UI_READINESS.md` section 3:
///
/// | fact on AppState | state |
/// |---|---|
/// | `connectionStatus == unreachable` | error ("URI server unreachable") |
/// | `isSendingAsk` or last turn `understanding` | thinking |
/// | last turn `awaitingApproval` / `proposalReady` | awaitingApproval |
/// | last turn `executing` | working |
/// | last turn `completed` within [successHold] | success |
/// | last turn `failed` / `needsConnection` | error |
/// | otherwise | idle |
///
/// There is no listening/speaking fact on AppState, so this source never
/// emits those states.
class AppStateCompanionSource extends CompanionStateSource {
  AppStateCompanionSource(
    this._appState, {
    this.successHold = const Duration(seconds: 4),
  }) {
    _appState.addListener(_recompute);
    _recompute();
  }

  final AppState _appState;
  final Duration successHold;
  CompanionSignal _signal = const CompanionSignal.idle();
  Timer? _successTimer;
  String? _lastCompletedTurnId;

  @override
  String get name => 'AppState';

  @override
  CompanionSignal get signal => _signal;

  void _recompute() {
    final next = _derive();
    if (next != _signal) {
      _signal = next;
      notifyListeners();
    }
  }

  CompanionSignal _derive() {
    final s = _appState;
    if (s.connectionStatus == BackendConnectionStatus.unreachable) {
      return const CompanionSignal(
        state: CompanionState.error,
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
        return CompanionSignal(
          state: CompanionState.awaitingApproval,
          detail:
              last.proposedAction?.title ?? 'A proposal needs your decision',
          sourceName: 'UriTurn.stage',
        );
      case TurnStage.executing:
        return const CompanionSignal(
          state: CompanionState.working,
          detail: 'Carrying out the approved action',
          sourceName: 'UriTurn.stage',
        );
      case TurnStage.completed:
        if (_lastCompletedTurnId != last.id) {
          _lastCompletedTurnId = last.id;
          _successTimer?.cancel();
          _successTimer = Timer(successHold, _recompute);
          return CompanionSignal(
            state: CompanionState.success,
            detail: last.result?.summary ?? 'Done',
            sourceName: 'UriTurn.stage',
          );
        }
        if (_successTimer?.isActive ?? false) {
          return CompanionSignal(
            state: CompanionState.success,
            detail: last.result?.summary ?? 'Done',
            sourceName: 'UriTurn.stage',
          );
        }
        return const CompanionSignal.idle();
      case TurnStage.failed:
        return CompanionSignal(
          state: CompanionState.error,
          detail: last.failureReason ?? 'The last request failed',
          sourceName: 'UriTurn.stage',
        );
      case TurnStage.needsConnection:
        return CompanionSignal(
          state: CompanionState.error,
          detail: 'Needs ${last.requiredConnectionName ?? 'a connection'}',
          sourceName: 'UriTurn.stage',
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
