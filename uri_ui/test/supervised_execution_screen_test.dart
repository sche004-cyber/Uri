import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/screens/tasks/supervised_execution_screen.dart';
import 'package:uri_ui/services/paired_runtime.dart';
import 'package:uri_ui/services/supervised_runtime.dart';
import 'package:uri_ui/services/task_handoff.dart';
import 'package:uri_ui/widgets/supervised_handoff_action.dart';

/// Test double for the worker boundary ONLY. It records every frame the UI
/// sends so the tests can assert the UI never approves, chooses or cancels on
/// its own, and it plays back worker-shaped statuses so the UI's rendering of
/// authoritative state (never UI memory) can be checked.
class _FakeSupervised implements SupervisedRuntime {
  final started = <ReasoningChoice>[];
  final sessions = <String>[];
  final begun = <List<String>>[];
  final decided = <bool>[];
  final cancelled = <String>[];
  final statusCalls = <String>[];
  bool closed = false;
  String? activeOnList;
  List<Map<String, dynamic>> listed = const [];
  Map<String, dynamic>? startup;
  // execution id -> queue of statuses to play back (last one repeats)
  final script = <String, List<Map<String, dynamic>>>{};
  String turnState = 'approval_required';
  Map<String, dynamic>? harness; // OQ-1: live usability the worker attaches to a proposal

  static const approvalDigest = 'a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1';
  static const proposalDigest = 'b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2b2';

  Map<String, dynamic> proposal({String provider = 'codex_cli', String? model = 'gpt-6-sol'}) => {
        'proposal_digest': proposalDigest,
        'approval_digest': approvalDigest,
        'turn_id': 't1',
        'session_id': 's1',
        'kind': 'client_external_harness',
        'provider': provider,
        'model': model,
        'capability_id': 'external_harness_task',
        'argument_digest': 'c3c3',
        'effect': 'local_write',
        'reversible': true,
        'instruction': 'write a greeting into out.txt',
        'expected_file': 'out.txt',
        'arguments': {'action': 'run', 'inputs': {'instruction': 'write a greeting into out.txt', 'expected_file': 'out.txt'}},
        'qualification': {'level': 'FIXTURE_ONLY', 'status': 'QUALIFIED', 'expires_at': 1800000000},
        if (harness != null) 'harness': harness,
      };

  Map<String, dynamic> status(String id, String state, {String? reason, String? code, String? ledgerState,
      String? endReason, bool cancel = false, bool evidence = false, String? journal, String? server}) => {
        'execution_id': id,
        'turn_id': 't1',
        'session_id': 's1',
        'state': state,
        'reason': reason,
        'code': code,
        'message': null,
        'request_text': 'use the harness to write a greeting into out.txt',
        'proposal': proposal(),
        'task_id': ledgerState == null ? null : '11111111-1111-4111-8111-111111111111',
        'cancel_requested': cancel,
        'bridge_outcome': null,
        'failure_category': null,
        'evidence': evidence ? [{'matched': true, 'output_sha256': 'd' * 64, 'output_bytes': 24}] : [],
        'queued_at': 1700000000.0,
        'approving_at': 1700000001.0,
        'starting_at': null,
        'running_at': null,
        'ended_at': null,
        'ledger': ledgerState == null
            ? null
            : {'task': {'state': ledgerState, 'reason_code': null},
                'attempts': [{'attempt_id': 1, 'status': endReason == null ? 'RUNNING' : 'ENDED', 'pid': 4242, 'end_reason': endReason}],
                'open_authorizations': 0},
        'journal': journal == null ? null : {'state': journal, 'receipted': true},
        'server_turn': server == null ? null : {'state': server, 'version': 5},
      };

  @override
  Future<List<HarnessStatus>> discoverHarnesses() async => const [
        HarnessStatus(id: 'codex_cli', installed: true, version: '0.158.0', authState: 'AUTHENTICATED',
            qualification: 'FIXTURE_ONLY', usable: true, requiredAction: null),
        HarnessStatus(id: 'claude_code', installed: true, version: '2.1.287', authState: 'NOT_AUTHENTICATED',
            qualification: 'NATIVE_UNQUALIFIED', usable: false, requiredAction: 'Sign in natively in the URI client profile.'),
      ];

  @override
  Future<Map<String, dynamic>> preflight() async =>
      {'worker_profile': 'phase2d-supervised', 'production_cutover': false, 'mid_run_cancel': true,
       'execution_lifecycle': ['execution_begin', 'execution_cancel', 'execution_list', 'execution_status']};

  @override
  Future<TurnResult> startTurn(String sessionId, String text, ReasoningChoice choice) async {
    started.add(choice);
    sessions.add(sessionId);
    if (turnState != 'approval_required') {
      return SupervisedTurn(state: 'reply', code: turnState, message: 'held');
    }
    return SupervisedTurn(state: 'approval_required', turnId: 't1',
        approval: {'capability_id': 'external_harness_task', 'reversible': true, 'effect': 'local_write',
            'approval_digest': approvalDigest, 'argument_digest': 'c3c3'},
        proposal: ExecutionProposal.fromJson(proposal(provider: choice.provider)));
  }

  @override
  Future<TurnResult> decide(String turnId, bool approve) async {
    decided.add(approve);
    return SupervisedTurn(state: approve ? 'reply' : 'cancelled', turnId: turnId,
        code: approve ? 'SETTLED_VERIFIED' : 'APPROVAL_DENIED', message: approve ? 'Done.' : 'You declined.');
  }

  @override
  Future<TurnResult> intentDecision(String sessionId, ReasoningChoice choice, Map<String, dynamic> decision) async =>
      const SupervisedTurn(state: 'reply', code: 'INTENT_ABANDONED', message: 'Dropped.');

  @override
  Future<ExecutionHandle> beginExecution(String turnId, String approvalDigest, String proposalDigest) async {
    begun.add([turnId, approvalDigest, proposalDigest]);
    if (approvalDigest != _FakeSupervised.approvalDigest || proposalDigest != _FakeSupervised.proposalDigest) {
      throw PairedRuntimeException('PROPOSAL_DIGEST_MISMATCH');
    }
    script.putIfAbsent('e1', () => [status('e1', 'queued')]);
    return ExecutionHandle(id: 'e1', turnId: 't1', state: 'queued', proposalDigest: proposalDigest);
  }

  @override
  Future<ExecutionStatus> executionStatus(String executionId) async {
    statusCalls.add(executionId);
    final q = script[executionId];
    if (q == null || q.isEmpty) throw PairedRuntimeException('EXECUTION_UNKNOWN');
    final next = q.length > 1 ? q.removeAt(0) : q.first;
    return ExecutionStatus.fromJson(next);
  }

  @override
  Future<Map<String, dynamic>> cancelExecution(String executionId) async {
    cancelled.add(executionId);
    final q = script[executionId];
    if (q != null && q.isNotEmpty && terminalExecutionStates.contains(q.first['state'])) {
      throw PairedRuntimeException('EXECUTION_TERMINAL');
    }
    return {'execution_id': executionId, 'cancel': 'requested', 'kill': {'granted': true, 'reason': 'CANCEL_REQUESTED'}};
  }

  @override
  Future<ExecutionListing> listExecutions() async => ExecutionListing(
      executions: listed.map(ExecutionSummary.fromJson).toList(), active: activeOnList, startup: startup);

  @override
  Future<void> close() async {
    closed = true;
  }
}

Widget _host(SupervisedRuntime? runtime) => MaterialApp(
      home: Scaffold(
          body: SupervisedExecutionScreen(
              runtimeOverride: runtime, sessionId: 's1', pollInterval: const Duration(seconds: 1))),
    );

/// The screen is a long ListView: give the test surface room so every card is on screen for tap().
void _tall(WidgetTester tester) {
  tester.view.physicalSize = const Size(1000, 3000);
  tester.view.devicePixelRatio = 1.0;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
}

/// One poll tick: advance fake time by the poll interval, then let the status future rebuild the card.
Future<void> _tick(WidgetTester tester) async {
  await tester.pump(const Duration(seconds: 1));
  await tester.pump();
}

Future<void> _sendWithCodex(WidgetTester tester, _FakeSupervised rt) async {
  _tall(tester);
  await tester.pumpWidget(_host(rt));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const Key('sx-choice-codex_cli')));
  await tester.enterText(find.byKey(const Key('sx-input')), 'use the harness to write a greeting into out.txt');
  await tester.pump();
  await tester.tap(find.byKey(const Key('sx-send')));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('without an opted-in installation the screen says so and fabricates nothing', (tester) async {
    await tester.pumpWidget(_host(null));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sx-unavailable')), findsOneWidget);
    expect(find.byKey(const Key('sx-send')), findsNothing);
  });

  testWidgets('the entry on Tasks renders nothing unless the installation opted in', (tester) async {
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: SupervisedExecutionEntry(configured: false))));
    expect(find.byKey(const Key('sx-entry-absent')), findsOneWidget);
    expect(find.byKey(const Key('sx-entry')), findsNothing);
    await tester.pumpWidget(const MaterialApp(home: Scaffold(body: SupervisedExecutionEntry(configured: true))));
    expect(find.byKey(const Key('sx-entry')), findsOneWidget);
  });

  testWidgets('no executor is preselected; unusable harness cannot be chosen; preflight is shown honestly', (tester) async {
    final rt = _FakeSupervised();
    await tester.pumpWidget(_host(rt));
    await tester.pumpAndSettle();
    expect(find.textContaining('production cutover: false'), findsOneWidget);
    expect(tester.widget<FilledButton>(find.byKey(const Key('sx-send'))).onPressed, isNull);
    expect(tester.widget<RadioListTile<ReasoningChoice>>(find.byKey(const Key('sx-choice-claude_code'))).enabled, isFalse);
    expect(rt.started, isEmpty);
  });

  testWidgets('approval card shows the full proposal and nothing is sent until Approve and run', (tester) async {
    final rt = _FakeSupervised();
    await _sendWithCodex(tester, rt);
    expect(rt.started.single.provider, 'codex_cli');
    expect(find.byKey(const Key('sx-approval')), findsOneWidget);
    expect(find.textContaining('write a greeting into out.txt'), findsWidgets);
    expect(find.byKey(const Key('sx-proposal-file')), findsOneWidget);
    expect(find.textContaining('Executor: codex_cli · model gpt-6-sol'), findsOneWidget);
    expect(find.textContaining('Effect: local_write · reversible: true'), findsOneWidget);
    expect(find.textContaining('Qualification: FIXTURE_ONLY · QUALIFIED'), findsOneWidget);
    expect(find.textContaining('Approval digest a1a1a1a1a1a1a1a1'), findsOneWidget);
    expect(rt.begun, isEmpty);
    expect(rt.decided, isEmpty);
    // the executor choice is locked while the proposal is pending (changing it would change an authority field)
    expect(tester.widget<RadioListTile<ReasoningChoice>>(find.byKey(const Key('sx-choice-codex_cli'))).enabled, isFalse);
    expect(tester.widget<RadioListTile<ReasoningChoice>>(find.byKey(const Key('sx-choice-nobrain'))).enabled, isFalse);
    expect(tester.widget<FilledButton>(find.byKey(const Key('sx-send'))).onPressed, isNull);
  });

  testWidgets('Approve and run echoes exactly the displayed digests, then follows the lifecycle to a receipt', (tester) async {
    final rt = _FakeSupervised();
    rt.script['e1'] = [
      rt.status('e1', 'queued'),
      rt.status('e1', 'starting'),
      rt.status('e1', 'running', ledgerState: 'RUNNING'),
      rt.status('e1', 'completed', code: 'SETTLED_VERIFIED', ledgerState: 'COMPLETE', endReason: 'exited_after_terminal_success_claim',
          evidence: true, journal: 'verified', server: 'reply'),
    ];
    await _sendWithCodex(tester, rt);
    await tester.tap(find.byKey(const Key('sx-approve')));
    await tester.pump();
    await tester.pump();
    expect(rt.begun.single, ['t1', _FakeSupervised.approvalDigest, _FakeSupervised.proposalDigest]);
    expect(rt.decided, isEmpty); // the frozen blocking decide was never used
    expect(find.byKey(const Key('sx-approval')), findsNothing);
    expect(find.byKey(const Key('sx-execution')), findsOneWidget);
    expect(find.textContaining('· QUEUED'), findsOneWidget);
    await _tick(tester);
    expect(find.textContaining('· STARTING'), findsOneWidget);
    await _tick(tester);
    expect(find.textContaining('· RUNNING'), findsOneWidget);
    expect(tester.widget<OutlinedButton>(find.byKey(const Key('sx-cancel'))).onPressed, isNotNull);
    await _tick(tester);
    await tester.pumpAndSettle();
    expect(find.textContaining('· COMPLETED'), findsOneWidget);
    expect(find.textContaining('SETTLED_VERIFIED'), findsOneWidget);
    expect(find.byKey(const Key('sx-receipt')), findsOneWidget);
    expect(find.textContaining('24 bytes'), findsOneWidget);
    expect(find.textContaining('ledger COMPLETE'), findsOneWidget);
    expect(find.textContaining('Client journal: verified · server turn: reply'), findsOneWidget);
    expect(tester.widget<OutlinedButton>(find.byKey(const Key('sx-cancel'))).onPressed, isNull);
    expect(rt.cancelled, isEmpty);
  });

  testWidgets('approval card renders the exact arguments object verbatim (C6; review round 1 OPS-3)', (tester) async {
    final rt = _FakeSupervised();
    await _sendWithCodex(tester, rt);
    final shown = tester.widget<Text>(find.byKey(const Key('sx-proposal-arguments'))).data!;
    expect(shown, contains('"action": "run"'));
    expect(shown, contains('"instruction": "write a greeting into out.txt"'));
    expect(shown, contains('"expected_file": "out.txt"'));
    expect(find.textContaining('Argument digest c3c3'), findsOneWidget);
  });

  testWidgets('an uncorroborated record is shown as UNCERTAIN with the record own claim beside it (OPS-1)', (tester) async {
    final rt = _FakeSupervised();
    final forged = rt.status('e1', 'uncertain', reason: 'UNCORROBORATED_COMPLETION:LEDGER_NOT_COMPLETE,JOURNAL_NOT_VERIFIED', code: 'SETTLED_VERIFIED');
    forged['recorded_state'] = 'completed';
    rt.script['e1'] = [forged];
    await _sendWithCodex(tester, rt);
    await tester.tap(find.byKey(const Key('sx-approve')));
    await tester.pumpAndSettle();
    expect(find.textContaining('· UNCERTAIN'), findsOneWidget);
    expect(find.byKey(const Key('sx-uncorroborated')), findsOneWidget);
    expect(find.byKey(const Key('sx-receipt')), findsNothing);
  });

  testWidgets('typing approve never begins an execution', (tester) async {
    final rt = _FakeSupervised();
    await _sendWithCodex(tester, rt);
    await tester.enterText(find.byKey(const Key('sx-input')), 'approve');
    await tester.pump();
    expect(tester.widget<FilledButton>(find.byKey(const Key('sx-send'))).onPressed, isNull); // locked while pending
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();
    expect(rt.begun, isEmpty);
    expect(rt.decided, isEmpty);
    expect(rt.started.length, 1);
  });

  testWidgets('a refused begin drops the card and shows the refusal; nothing runs', (tester) async {
    final rt = _FakeSupervised();
    await _sendWithCodex(tester, rt);
    // simulate the worker refusing (e.g. the card the UI holds no longer matches): the fake refuses other digests
    rt.script['e1'] = [];
    final state = tester.state(find.byType(SupervisedExecutionScreen)) as dynamic;
    expect(state, isNotNull);
    await tester.tap(find.byKey(const Key('sx-approve')));
    await tester.pumpAndSettle();
    // begin succeeded in the fake (digests matched); the status queue was emptied -> EXECUTION_UNKNOWN surfaces honestly
    expect(find.byKey(const Key('sx-approval')), findsNothing);
    expect(find.textContaining('EXECUTION_UNKNOWN'), findsOneWidget);
  });

  testWidgets('Decline sends a deny and records nothing else', (tester) async {
    final rt = _FakeSupervised();
    await _sendWithCodex(tester, rt);
    await tester.tap(find.byKey(const Key('sx-decline')));
    await tester.pumpAndSettle();
    expect(rt.decided, [false]);
    expect(rt.begun, isEmpty);
    expect(find.textContaining('APPROVAL_DENIED'), findsOneWidget);
  });

  testWidgets('mid-run Cancel sends execution_cancel and the card shows the worker outcome (uncertain), not a label', (tester) async {
    final rt = _FakeSupervised();
    rt.script['e1'] = [
      rt.status('e1', 'running', ledgerState: 'RUNNING'),
      rt.status('e1', 'running', ledgerState: 'RUNNING'),
      rt.status('e1', 'uncertain', reason: 'CANCELLED_AFTER_DISPATCH', code: 'SETTLED_EXECUTION_UNCERTAIN',
          ledgerState: 'FAILED', endReason: 'cancelled_killed', cancel: true, journal: 'execution_uncertain',
          server: 'execution_uncertain'),
    ];
    await _sendWithCodex(tester, rt);
    await tester.tap(find.byKey(const Key('sx-approve')));
    await tester.pump();
    await tester.pump();
    expect(find.textContaining('· RUNNING'), findsOneWidget);
    await tester.tap(find.byKey(const Key('sx-cancel')));
    await tester.pump();
    expect(rt.cancelled, ['e1']);
    await _tick(tester); // the worker reports the kill outcome on the next poll
    await tester.pumpAndSettle();
    expect(find.textContaining('· UNCERTAIN'), findsOneWidget);
    expect(find.byKey(const Key('sx-uncertain')), findsOneWidget);
    expect(find.byKey(const Key('sx-cancel-flag')), findsOneWidget);
    expect(find.textContaining('cancelled_killed'), findsOneWidget);
    expect(tester.widget<OutlinedButton>(find.byKey(const Key('sx-cancel'))).onPressed, isNull);
  });

  testWidgets('reconnect: the worker lists earlier executions and the active one is followed', (tester) async {
    final rt = _FakeSupervised();
    rt.listed = [
      {'execution_id': 'e9', 'turn_id': 't9', 'state': 'uncertain', 'reason': 'WORKER_RESTARTED', 'code': null,
        'provider': 'codex_cli', 'model': 'gpt-6-sol', 'queued_at': 1700000000.0, 'ended_at': 1700000100.0, 'cancel_requested': false},
      {'execution_id': 'e8', 'turn_id': 't8', 'state': 'running', 'reason': null, 'code': null,
        'provider': 'codex_cli', 'model': 'gpt-6-sol', 'queued_at': 1700000200.0, 'ended_at': null, 'cancel_requested': false},
    ];
    rt.startup = {'journal': [], 'executions': [{'execution_id': 'e9', 'was': 'running', 'state': 'uncertain', 'reason': 'WORKER_RESTARTED'}]};
    rt.activeOnList = 'e8';
    rt.script['e8'] = [rt.status('e8', 'running', ledgerState: 'RUNNING'), rt.status('e8', 'completed', code: 'SETTLED_VERIFIED', ledgerState: 'COMPLETE', endReason: 'x', evidence: true)];
    rt.script['e9'] = [rt.status('e9', 'uncertain', reason: 'WORKER_RESTARTED', ledgerState: 'FAILED', endReason: 'orphan_killed')];
    _tall(tester);
    await tester.pumpWidget(_host(rt));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sx-exec-e9')), findsOneWidget);
    expect(find.byKey(const Key('sx-exec-e8')), findsOneWidget);
    expect(find.byKey(const Key('sx-restart-note')), findsOneWidget);
    expect(find.textContaining('· RUNNING'), findsOneWidget); // the active execution is followed, not re-begun
    await _tick(tester);
    await tester.pumpAndSettle();
    expect(find.textContaining('· COMPLETED'), findsOneWidget); // e8 followed to its worker-reported end
    await tester.tap(find.byKey(const Key('sx-exec-e9')));
    await tester.pumpAndSettle();
    expect(find.textContaining('· UNCERTAIN'), findsOneWidget);
    expect(find.textContaining('WORKER_RESTARTED'), findsWidgets);
    expect(rt.begun, isEmpty);
    expect(rt.cancelled, isEmpty);
  });

  testWidgets('stale UI state yields to the worker: a run the UI believed active is shown terminal, cancel refused', (tester) async {
    final rt = _FakeSupervised();
    rt.script['e1'] = [
      rt.status('e1', 'running', ledgerState: 'RUNNING'),
      rt.status('e1', 'failed', reason: 'NOT_STARTED:HARNESS_HARNESS_NOT_USABLE', code: 'SETTLED_FAILED'),
    ];
    await _sendWithCodex(tester, rt);
    await tester.tap(find.byKey(const Key('sx-approve')));
    await tester.pump();
    await tester.pump();
    expect(find.textContaining('· RUNNING'), findsOneWidget);
    await _tick(tester);
    await tester.pumpAndSettle();
    expect(find.textContaining('· FAILED'), findsOneWidget);
    expect(find.textContaining('NOT_STARTED:HARNESS_HARNESS_NOT_USABLE'), findsOneWidget);
    expect(tester.widget<OutlinedButton>(find.byKey(const Key('sx-cancel'))).onPressed, isNull);
    // Refresh keeps asking the worker; the state cannot be moved by the UI
    await tester.tap(find.byKey(const Key('sx-refresh')));
    await tester.pumpAndSettle();
    expect(find.textContaining('· FAILED'), findsOneWidget);
    expect(rt.cancelled, isEmpty);
  });

  testWidgets('quota pause is shown as a user choice, never a silent switch', (tester) async {
    final rt = _FakeSupervised();
    rt.script['e1'] = [rt.status('e1', 'quota_paused', reason: 'PROVIDER_QUOTA_EXHAUSTED', code: 'WAITING_FOR_MODEL')];
    await _sendWithCodex(tester, rt);
    await tester.tap(find.byKey(const Key('sx-approve')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sx-quota')), findsOneWidget);
    expect(rt.started.length, 1); // no automatic retry with another executor
  });

  testWidgets('closing the screen closes the worker (which withdraws any run)', (tester) async {
    final rt = _FakeSupervised();
    await tester.pumpWidget(_host(rt));
    await tester.pumpAndSettle();
    await tester.pumpWidget(const MaterialApp(home: SizedBox()));
    await tester.pumpAndSettle();
    expect(rt.closed, isTrue);
  });

  // ---- Phase 2 closure: conversation-to-task handoff (C6 decision 2, the no-decision part) and VAL-1 display ----

  testWidgets('a conversation handoff pre-fills the composer only: no frame, no executor, no approval', (tester) async {
    _tall(tester);
    final rt = _FakeSupervised();
    final draft = TaskHandoff(text: '  please write a greeting into out.txt  ', conversationSessionId: 'chat-1', messageId: 'm7');
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(
            body: SupervisedExecutionScreen(
                runtimeOverride: rt, sessionId: 's1', pollInterval: const Duration(seconds: 1), draft: draft))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sx-draft-banner')), findsOneWidget);
    expect(tester.widget<TextField>(find.byKey(const Key('sx-input'))).controller!.text, 'please write a greeting into out.txt');
    // Nothing was sent or decided because of the draft, and no executor was chosen for the user.
    expect(rt.started, isEmpty);
    expect(rt.begun, isEmpty);
    expect(rt.decided, isEmpty);
    expect(tester.widget<FilledButton>(find.byKey(const Key('sx-send'))).onPressed, isNull);
    expect(find.text('Choose an executor first'), findsOneWidget);
    // The conversation's session id is never reused as the supervised session.
    await tester.tap(find.byKey(const Key('sx-choice-codex_cli')));
    await tester.pump();
    await tester.tap(find.byKey(const Key('sx-send')));
    await tester.pumpAndSettle();
    expect(rt.started.length, 1);
    expect(rt.sessions, ['s1']);
    expect(find.byKey(const Key('sx-approval')), findsOneWidget);
    expect(rt.begun, isEmpty); // the approval is still the user's to give
  });

  test('a handoff is trimmed, never truncated (too long = refused whole), and carries no authority fields', () {
    // Closure version cut the text at maxChars; operational qualification (C6 Option B) refuses it whole instead,
    // because the user's words must never be silently altered.
    final h = TaskHandoff(text: 'x' * (TaskHandoff.maxChars + 10));
    expect(h.text.length, TaskHandoff.maxChars + 10);
    expect(h.tooLong, isTrue);
    expect(h.usable, isFalse);
    expect(TaskHandoff(text: '   ').isEmpty, isTrue);
    expect(TaskHandoff(text: '  keep my words  ').original, '  keep my words  ');
    expect(TaskHandoff(text: 'a', source: 'voice').banner, contains('voice'));
  });

  testWidgets('an empty handoff shows no banner and leaves the composer empty', (tester) async {
    final rt = _FakeSupervised();
    await tester.pumpWidget(MaterialApp(
        home: Scaffold(body: SupervisedExecutionScreen(runtimeOverride: rt, sessionId: 's1', draft: TaskHandoff(text: ' ')))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sx-draft-banner')), findsNothing);
    expect(tester.widget<TextField>(find.byKey(const Key('sx-input'))).controller!.text, '');
  });

  testWidgets('VAL-1: an approval refused before anything ran is explained as not executed', (tester) async {
    final rt = _FakeSupervised();
    rt.script['e1'] = [rt.status('e1', 'queued'),
      rt.status('e1', 'failed', reason: 'APPROVAL_REFUSED_NOT_APPLIED:SERVER_REFUSED:HTTP_403', server: 'approval_required')];
    await _sendWithCodex(tester, rt);
    await tester.tap(find.byKey(const Key('sx-approve')));
    await tester.pump();
    await _tick(tester);
    await _tick(tester);
    expect(find.textContaining('FAILED'), findsWidgets);
    expect(find.byKey(const Key('sx-approval-not-applied')), findsOneWidget);
    expect(find.byKey(const Key('sx-uncertain')), findsNothing);
  });

  // ---- Operational qualification: OQ-1 and C6 Option B ----------------------------------------------------------

  testWidgets('OQ-1: a proposal for an executor that cannot run now disables Approve and says why', (tester) async {
    final rt = _FakeSupervised()
      ..harness = {'usable': false, 'auth_state': 'NOT_AUTHENTICATED', 'reason': 'HARNESS_NOT_USABLE',
        'required_user_action': 'Run `codex login` in the URI client profile terminal (native login).'};
    await _sendWithCodex(tester, rt);
    expect(find.byKey(const Key('sx-proposal-harness-blocked')), findsOneWidget);
    expect(find.textContaining('codex login'), findsWidgets);
    expect(tester.widget<FilledButton>(find.byKey(const Key('sx-approve'))).onPressed, isNull);
    expect(find.textContaining('cannot run now'), findsWidgets);
    await tester.tap(find.byKey(const Key('sx-approve')), warnIfMissed: false);
    await tester.pump();
    expect(rt.begun, isEmpty);
  });

  testWidgets('OQ-1: a usable executor is shown as ready and Approve stays the user\'s choice', (tester) async {
    final rt = _FakeSupervised()..harness = {'usable': true, 'auth_state': 'AUTHENTICATED', 'reason': null};
    await _sendWithCodex(tester, rt);
    expect(find.byKey(const Key('sx-proposal-harness')), findsOneWidget);
    expect(tester.widget<FilledButton>(find.byKey(const Key('sx-approve'))).onPressed, isNotNull);
    expect(rt.begun, isEmpty);
  });

  testWidgets('C6 B: the screen states the intended next action at every step', (tester) async {
    _tall(tester);
    final rt = _FakeSupervised();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SupervisedExecutionScreen(runtimeOverride: rt, sessionId: 's1',
        pollInterval: const Duration(seconds: 1), draft: TaskHandoff(text: 'write a greeting into out.txt')))));
    await tester.pumpAndSettle();
    String next() => tester.widget<Text>(find.byKey(const Key('sx-next-action'))).data!;
    expect(next(), 'Next: choose an executor.');
    await tester.tap(find.byKey(const Key('sx-choice-codex_cli')));
    await tester.pump();
    expect(next(), contains('press Send'));
    expect(next(), contains('nothing runs until you approve'));
    await tester.tap(find.byKey(const Key('sx-send')));
    await tester.pumpAndSettle();
    expect(next(), contains('approve or decline'));
    expect(rt.begun, isEmpty);
  });

  testWidgets('C6 B: an edited draft is marked as edited; editing sends nothing', (tester) async {
    _tall(tester);
    final rt = _FakeSupervised();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SupervisedExecutionScreen(runtimeOverride: rt, sessionId: 's1',
        draft: TaskHandoff(text: 'write a greeting into out.txt')))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sx-draft-edited')), findsNothing);
    await tester.enterText(find.byKey(const Key('sx-input')), 'write a farewell into out.txt');
    await tester.pump();
    expect(find.byKey(const Key('sx-draft-edited')), findsOneWidget);
    expect(find.byKey(const Key('sx-draft-banner')), findsOneWidget);
    expect(rt.started, isEmpty);
  });

  testWidgets('C6 B: a draft that arrives while a run is in flight is kept; the worker state wins', (tester) async {
    _tall(tester);
    final rt = _FakeSupervised()..activeOnList = 'e1';
    rt.script['e1'] = [rt.status('e1', 'running', ledgerState: 'RUNNING')];
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SupervisedExecutionScreen(runtimeOverride: rt, sessionId: 's1',
        pollInterval: const Duration(seconds: 1), draft: TaskHandoff(text: 'write a greeting into out.txt')))));
    await tester.pump();
    await tester.pump();
    await tester.pump();
    expect(find.byKey(const Key('sx-execution')), findsOneWidget);
    expect(find.byKey(const Key('sx-draft-busy')), findsOneWidget);
    expect(tester.widget<TextField>(find.byKey(const Key('sx-input'))).controller!.text, 'write a greeting into out.txt');
    expect(tester.widget<Text>(find.byKey(const Key('sx-next-action'))).data, contains('running execution'));
    expect(rt.started, isEmpty);
    expect(rt.begun, isEmpty);
    await tester.pumpWidget(const SizedBox());       // dispose the screen: stops the poll timer
  });

  testWidgets('C6 B: a message over the ceiling is refused whole: nothing copied, nothing cut', (tester) async {
    final rt = _FakeSupervised();
    await tester.pumpWidget(MaterialApp(home: Scaffold(body: SupervisedExecutionScreen(runtimeOverride: rt, sessionId: 's1',
        draft: TaskHandoff(text: 'y' * (TaskHandoff.maxChars + 1))))));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sx-draft-refused')), findsOneWidget);
    expect(find.byKey(const Key('sx-draft-banner')), findsNothing);
    expect(tester.widget<TextField>(find.byKey(const Key('sx-input'))).controller!.text, '');
  });

  UriTurn turnOf(String text, TurnStage stage, {String id = 'm1'}) =>
      UriTurn(id: id, userText: text, timestamp: DateTime(2026, 10, 8), stage: stage);

  Widget chatHost(UriTurn turn, {bool configured = true, SupervisedRuntime? rt}) => MaterialApp(
        home: Scaffold(
          body: Column(children: [
            Text('conversation: ${turn.userText.length > 200 ? '<${turn.userText.length} chars>' : turn.userText}', key: const Key('chat-message')),
            SupervisedHandoffAction(turn: turn, configured: configured, runtimeOverride: rt),
          ]),
        ),
      );

  testWidgets('C6 B Chat: no action without the supervised opt-in, for an empty message, or while the turn is in flight',
      (tester) async {
    await tester.pumpWidget(chatHost(turnOf('write a greeting', TurnStage.completed), configured: false));
    expect(find.byKey(const Key('chat-handoff-m1')), findsNothing);
    expect(find.byKey(const Key('chat-handoff-absent-m1')), findsOneWidget);
    await tester.pumpWidget(chatHost(turnOf('   ', TurnStage.completed)));
    expect(find.byKey(const Key('chat-handoff-m1')), findsNothing);
    for (final stage in [TurnStage.understanding, TurnStage.proposalReady, TurnStage.awaitingApproval, TurnStage.executing]) {
      await tester.pumpWidget(chatHost(turnOf('write a greeting', stage)));
      expect(find.byKey(const Key('chat-handoff-m1')), findsNothing, reason: '$stage');
    }
    for (final stage in [TurnStage.completed, TurnStage.failed, TurnStage.cancelled, TurnStage.needsConnection]) {
      await tester.pumpWidget(chatHost(turnOf('write a greeting', stage)));
      expect(find.byKey(const Key('chat-handoff-m1')), findsOneWidget, reason: '$stage');
    }
  });

  testWidgets('C6 B Chat: the action opens an unsent draft of the user\'s own words; Back returns to the conversation',
      (tester) async {
    _tall(tester);
    final rt = _FakeSupervised();
    await tester.pumpWidget(chatHost(turnOf('  please write a greeting into out.txt ', TurnStage.completed), rt: rt));
    await tester.tap(find.byKey(const Key('chat-handoff-m1')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sx-draft-banner')), findsOneWidget);
    expect(tester.widget<TextField>(find.byKey(const Key('sx-input'))).controller!.text, 'please write a greeting into out.txt');
    expect(rt.started, isEmpty);
    expect(rt.begun, isEmpty);
    expect(rt.decided, isEmpty);
    expect(rt.cancelled, isEmpty);
    expect(tester.widget<FilledButton>(find.byKey(const Key('sx-send'))).onPressed, isNull); // no executor chosen for the user
    // Abandon: Back with the draft unsent.
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('chat-message')), findsOneWidget);
    expect(find.text('conversation:   please write a greeting into out.txt '), findsOneWidget); // the original is untouched
    expect(rt.started, isEmpty);
    expect(rt.begun, isEmpty);
    expect(rt.closed, isTrue); // leaving the screen closes the worker session; nothing was in flight
    // Restart = a fresh screen without a handoff: no draft is resurrected.
    await tester.pumpWidget(_host(_FakeSupervised()));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('sx-draft-banner')), findsNothing);
    expect(tester.widget<TextField>(find.byKey(const Key('sx-input'))).controller!.text, '');
  });

  testWidgets('C6 B Chat: a message too long to hand off whole offers no handoff', (tester) async {
    await tester.pumpWidget(chatHost(turnOf('z' * (TaskHandoff.maxChars + 1), TurnStage.completed)));
    final button = tester.widget<TextButton>(find.byKey(const Key('chat-handoff-m1')));
    expect(button.onPressed, isNull);
    expect(find.text('Too long to make a supervised task'), findsOneWidget);
  });
}
