import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/services/paired_runtime.dart';
import 'package:uri_ui/services/supervised_runtime.dart';

/// A scriptable stand-in for the Phase 2 worker. Only the read-only
/// calls the source uses are implemented; everything else throws, which
/// proves the source never begins/decides/cancels.
class FakeSupervisedRuntime implements SupervisedRuntime {
  Map<String, dynamic> preflightReply = {
    'worker_profile': 'phase2d-supervised',
  };
  Object? preflightError;
  ExecutionListing listing = const ExecutionListing(
    executions: [],
    active: null,
    startup: null,
  );
  final Map<String, ExecutionStatus> statuses = {};
  int begins = 0;

  @override
  Future<Map<String, dynamic>> preflight() async {
    if (preflightError != null) throw preflightError!;
    return preflightReply;
  }

  @override
  Future<ExecutionListing> listExecutions() async => listing;

  @override
  Future<ExecutionStatus> executionStatus(String id) async => statuses[id]!;

  @override
  Future<ExecutionHandle> beginExecution(String t, String a, String p) {
    begins++;
    throw UnimplementedError('the companion source must never begin');
  }

  @override
  Future<Map<String, dynamic>> cancelExecution(String id) =>
      throw UnimplementedError();
  @override
  Future<List<HarnessStatus>> discoverHarnesses() => throw UnimplementedError();
  @override
  Future<TurnResult> startTurn(String s, String t, ReasoningChoice c) =>
      throw UnimplementedError();
  @override
  Future<TurnResult> decide(String t, bool a) => throw UnimplementedError();
  @override
  Future<TurnResult> intentDecision(
    String s,
    ReasoningChoice c,
    Map<String, dynamic> d,
  ) => throw UnimplementedError();
  @override
  Future<void> close() async {}
}

ExecutionStatus status(
  String id,
  String state, {
  String? reason,
  String? recorded,
}) => ExecutionStatus.fromJson({
  'execution_id': id,
  'state': state,
  'reason': reason,
  'recorded_state': recorded ?? state,
});

void main() {
  group('SupervisedCompanionSource (PHASE2CLOSE_UI_READINESS section 3)', () {
    test(
      'no runtime -> unavailable; preflight failure -> unavailable',
      () async {
        final none = SupervisedCompanionSource(null, autoStart: false);
        expect(none.signal.state, CompanionState.unavailable);

        final rt = FakeSupervisedRuntime()
          ..preflightError = StateError('worker died');
        final src = SupervisedCompanionSource(rt, autoStart: false);
        await src.refresh();
        expect(src.signal.state, CompanionState.unavailable);
        expect(src.signal.detail, contains('worker died'));
        rt.preflightError = null;
        rt.preflightReply = {'worker_profile': 'frozen-worker'};
        await src.refresh();
        expect(src.signal.state, CompanionState.unavailable);
        expect(src.signal.sourceName, 'SupervisedRuntime.preflight');
      },
    );

    test('idle when no active execution and no pending turn', () async {
      final rt = FakeSupervisedRuntime();
      final src = SupervisedCompanionSource(rt, autoStart: false);
      await src.refresh();
      expect(src.signal.state, CompanionState.idle);
      expect(src.signal.sourceName, 'execution_list.active == null');
      expect(rt.begins, 0);
    });

    test('pending turn: clarification / confirmation / approval with proposal need the user', () async {
      final rt = FakeSupervisedRuntime();
      final src = SupervisedCompanionSource(rt, autoStart: false);
      src.noteTurn(
        const TurnResult(
          state: 'intent',
          code: 'INTENT_CLARIFICATION',
          clarification: {'q': 'which file?'},
        ),
      );
      await src.refresh();
      expect(src.signal.state, CompanionState.awaitingApproval);
      expect(src.signal.detail, 'Needs you: clarify');

      src.noteTurn(
        const TurnResult(
          state: 'intent',
          code: 'INTENT_CONFIRMATION_REQUIRED',
          confirmation: {'x': 1},
        ),
      );
      await src.refresh();
      expect(src.signal.detail, 'Needs you: confirm');

      // approval_required WITHOUT an execution_proposal is not an approval state.
      src.noteTurn(const SupervisedTurn(state: 'approval_required'));
      await src.refresh();
      expect(src.signal.state, CompanionState.idle);

      src.noteTurn(
        SupervisedTurn.fromJson({
          'state': 'approval_required',
          'execution_proposal': {
            'proposal_digest': 'd',
            'approval_digest': 'a',
            'turn_id': 't',
            'session_id': 's',
            'kind': 'client_external_harness',
            'provider': 'codex',
            'model': 'gpt-5-codex',
            'capability_id': 'c',
            'argument_digest': 'g',
            'effect': 'write',
            'reversible': false,
            'instruction': 'i',
            'expected_file': 'f',
            'arguments': <String, dynamic>{},
          },
        }),
      );
      await src.refresh();
      expect(src.signal.state, CompanionState.awaitingApproval);
      expect(src.signal.detail, 'Approve: codex / gpt-5-codex');
      expect(rt.begins, 0, reason: 'observing never begins an execution');
    });

    test('active execution -> working; corroborated completed -> success; uncertain/failed/quota -> error', () async {
      final rt = FakeSupervisedRuntime();
      final src = SupervisedCompanionSource(
        rt,
        autoStart: false,
        successHold: const Duration(days: 1),
      );
      rt.listing = const ExecutionListing(
        executions: [],
        active: 'e1',
        startup: null,
      );
      rt.statuses['e1'] = status('e1', 'running');
      await src.refresh();
      expect(src.signal.state, CompanionState.working);
      expect(
        src.signal.progress,
        isNull,
        reason: 'the worker reports no percentage',
      );

      // Record says completed but the worker could not corroborate: state=uncertain.
      rt.statuses['e1'] = status(
        'e1',
        'uncertain',
        reason: 'UNCORROBORATED_COMPLETION:ledger',
        recorded: 'completed',
      );
      await src.refresh();
      expect(src.signal.state, CompanionState.error);
      expect(src.signal.detail, contains('UNCORROBORATED_COMPLETION'));

      rt.statuses['e1'] = status('e1', 'completed');
      await src.refresh();
      expect(src.signal.state, CompanionState.success);

      for (final s in ['failed', 'quota_paused']) {
        rt.statuses['e1'] = status('e1', s, reason: 'R');
        await src.refresh();
        expect(src.signal.state, CompanionState.error, reason: s);
      }
      src.dispose();
    });
  });

  group('AppStateCompanionSource', () {
    test('unreachable backend -> unavailable, not error', () async {
      final appState = AppState(MockUriClient());
      final src = AppStateCompanionSource(appState);
      appState.connectionStatus = BackendConnectionStatus.unreachable;
      appState.notifyListeners();
      expect(src.signal.state, CompanionState.unavailable);
      src.dispose();
    });

    test('a proposal is awaitingApproval only when a proposedAction exists; completed needs a result', () async {
      final appState = AppState(MockUriClient());
      final src = AppStateCompanionSource(
        appState,
        successHold: const Duration(days: 1),
      );
      appState.conversation.add(
        UriTurn(
          id: 't1',
          userText: 'x',
          timestamp: DateTime(2026),
          stage: TurnStage.proposalReady,
        ),
      );
      appState.notifyListeners();
      expect(src.signal.state, CompanionState.thinking);

      appState.conversation.last.proposedAction = const ProposedAction(
        title: 'Send reply',
        description: 'd',
        targetService: 'gmail',
        impact: ActionImpact.notable,
      );
      appState.conversation.last.stage = TurnStage.awaitingApproval;
      appState.notifyListeners();
      expect(src.signal.state, CompanionState.awaitingApproval);
      expect(src.signal.detail, 'Send reply');

      appState.conversation.last.stage = TurnStage.completed; // no result yet
      appState.notifyListeners();
      expect(src.signal.state, CompanionState.idle);

      appState.conversation.last.result = const ActionResult(summary: 'Sent');
      appState.notifyListeners();
      expect(src.signal.state, CompanionState.success);
      expect(src.signal.sourceName, contains('not an execution receipt'));
      src.dispose();
    });
  });
}
