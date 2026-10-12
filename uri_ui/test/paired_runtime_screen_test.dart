import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/screens/settings/paired_runtime_screen.dart';
import 'package:uri_ui/services/paired_runtime.dart';

/// Test double for the worker boundary ONLY. It records what the UI sends so
/// we can assert the UI never chooses an executor or approves on its own.
class _FakeRuntime implements PairedRuntime {
  final started = <ReasoningChoice>[];
  final decisions = <bool>[];

  @override
  Future<List<HarnessStatus>> discoverHarnesses() async => const [
    HarnessStatus(id: 'claude_code', installed: true, version: '2.1.287', authState: 'AUTH_UNVERIFIED',
        qualification: 'NATIVE_UNQUALIFIED', usable: false,
        requiredAction: 'Run `claude` in the URI client profile terminal and sign in with your subscription (native login).'),
  ];

  @override
  Future<TurnResult> startTurn(String sessionId, String text, ReasoningChoice choice) async {
    started.add(choice);
    return const TurnResult(state: 'approval_required', turnId: 't1',
        approval: {'capability_id': 'remember_fact', 'reversible': true});
  }

  @override
  Future<TurnResult> decide(String turnId, bool approve) async {
    decisions.add(approve);
    return TurnResult(state: approve ? 'reply' : 'cancelled', turnId: turnId,
        code: approve ? 'SETTLED_VERIFIED' : 'APPROVAL_DENIED', message: approve ? 'Done.' : 'You declined.');
  }

  final intentDecisions = <Map<String, dynamic>>[];
  bool intentMode = false;

  @override
  Future<TurnResult> intentDecision(String sessionId, ReasoningChoice choice, Map<String, dynamic> decision) async {
    intentDecisions.add(decision);
    if (decision['decision'] == 'select') {
      return const TurnResult(state: 'reply', code: 'INTENT_CONFIRMATION_REQUIRED',
          confirmation: {'intent_id': 'i1', 'revision': 2, 'digest': 'd2',
              'arguments': {'request_text': 'remember that Budget report Q4.pdf is due on Friday'}},
          intent: {'references': {'statement': {'expression': 'the budget report', 'title': 'Budget report Q4.pdf',
              'state': 'CONFIRMED'}}});
    }
    if (decision['decision'] == 'confirm') {
      return const TurnResult(state: 'approval_required', turnId: 't9',
          approval: {'capability_id': 'remember_fact', 'reversible': true});
    }
    return const TurnResult(state: 'reply', code: 'INTENT_ABANDONED', message: 'Dropped.');
  }

  @override
  Future<void> close() async {}
}

class _IntentRuntime extends _FakeRuntime {
  @override
  Future<TurnResult> startTurn(String sessionId, String text, ReasoningChoice choice) async {
    started.add(choice);
    return const TurnResult(state: 'reply', code: 'INTENT_CLARIFICATION',
        message: "Which one do you mean by 'the budget report'?",
        clarification: {'intent_id': 'i1', 'revision': 1, 'kind': 'reference',
            'question': "Which one do you mean by 'the budget report'?",
            'options': [{'candidate_id': 'f3', 'label': 'Budget report Q3.pdf', 'rank': 1},
                        {'candidate_id': 'f4', 'label': 'Budget report Q4.pdf', 'rank': 2}]});
  }
}

/// The selected Brain read which words fill the slot: the card must say so (third review).
class _InterpretedRuntime extends _FakeRuntime {
  @override
  Future<TurnResult> startTurn(String sessionId, String text, ReasoningChoice choice) async {
    started.add(choice);
    return const TurnResult(state: 'reply', code: 'INTENT_CONFIRMATION_REQUIRED',
        confirmation: {'intent_id': 'i1', 'revision': 1, 'digest': 'd1',
            'arguments': {'request_text': 'remember that the boiler service is booked for June'}},
        intent: {'references': {}, 'sources': {'statement': 'interpreted_from_request'}});
  }
}

Widget _host(PairedRuntime? runtime) => MaterialApp(
  home: Scaffold(body: PairedRuntimeScreen(runtimeOverride: runtime)),
);

void main() {
  testWidgets('unavailable harness is shown with the exact user action and cannot be chosen', (tester) async {
    final runtime = _FakeRuntime();
    await tester.pumpWidget(_host(runtime));
    await tester.pumpAndSettle();
    expect(find.textContaining('native login'), findsOneWidget);
    expect(find.textContaining('unavailable'), findsOneWidget);
    final tile = tester.widget<RadioListTile<ReasoningChoice>>(find.byKey(const Key('choice-claude_code')));
    expect(tile.enabled, isFalse);
  });

  testWidgets('no executor is preselected; send stays disabled until the user chooses', (tester) async {
    final runtime = _FakeRuntime();
    await tester.pumpWidget(_host(runtime));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('paired-input')), 'remember that a');
    await tester.pump();
    expect(tester.widget<FilledButton>(find.byKey(const Key('paired-send'))).onPressed, isNull);
    expect(runtime.started, isEmpty);
  });

  testWidgets('approval is explicit: nothing decided until the user presses Approve', (tester) async {
    final runtime = _FakeRuntime();
    await tester.pumpWidget(_host(runtime));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('choice-nobrain')));
    await tester.enterText(find.byKey(const Key('paired-input')), 'remember that a');
    await tester.pump();
    await tester.tap(find.byKey(const Key('paired-send')));
    await tester.pumpAndSettle();
    expect(runtime.started.single.provider, 'uri-deterministic');
    expect(runtime.decisions, isEmpty);
    expect(find.byKey(const Key('paired-approval')), findsOneWidget);
    await tester.tap(find.byKey(const Key('paired-approve')));
    await tester.pumpAndSettle();
    expect(runtime.decisions, [true]);
    expect(find.textContaining('SETTLED_VERIFIED'), findsOneWidget);
  });

  testWidgets('declining reports honestly and records a deny', (tester) async {
    final runtime = _FakeRuntime();
    await tester.pumpWidget(_host(runtime));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('choice-nobrain')));
    await tester.enterText(find.byKey(const Key('paired-input')), 'remember that b');
    await tester.pump();
    await tester.tap(find.byKey(const Key('paired-send')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('paired-deny')));
    await tester.pumpAndSettle();
    expect(runtime.decisions, [false]);
    expect(find.textContaining('APPROVAL_DENIED'), findsOneWidget);
  });

  testWidgets('intent: clarification choice, then explicit digest-bound confirmation, then approval', (tester) async {
    final runtime = _IntentRuntime();
    await tester.pumpWidget(_host(runtime));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('choice-nobrain')));
    await tester.enterText(find.byKey(const Key('paired-input')), 'remember that the budget report is due on Friday');
    await tester.pump();
    await tester.tap(find.byKey(const Key('paired-send')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('paired-clarification')), findsOneWidget);
    expect(find.byKey(const Key('paired-approval')), findsNothing);
    await tester.tap(find.byKey(const Key('paired-option-f4')));
    await tester.pumpAndSettle();
    expect(runtime.intentDecisions.single, {'intent_id': 'i1', 'revision': 1, 'decision': 'select', 'candidate_id': 'f4'});
    expect(find.byKey(const Key('paired-confirmation')), findsOneWidget);
    expect(find.textContaining('Budget report Q4.pdf is due on Friday'), findsOneWidget);
    expect(runtime.decisions, isEmpty); // nothing approved or run yet
    await tester.tap(find.byKey(const Key('paired-confirm')));
    await tester.pumpAndSettle();
    expect(runtime.intentDecisions.last, {'intent_id': 'i1', 'revision': 2, 'decision': 'confirm', 'digest': 'd2'});
    expect(find.byKey(const Key('paired-approval')), findsOneWidget);
    await tester.tap(find.byKey(const Key('paired-approve')));
    await tester.pumpAndSettle();
    expect(runtime.decisions, [true]);
  });

  testWidgets('intent: a slot read by the Brain is labelled on the confirmation card', (tester) async {
    final runtime = _InterpretedRuntime();
    await tester.pumpWidget(_host(runtime));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('choice-nobrain')));
    await tester.enterText(find.byKey(const Key('paired-input')), 'note for later: the boiler service is booked for June');
    await tester.pump();
    await tester.tap(find.byKey(const Key('paired-send')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('paired-confirmation')), findsOneWidget);
    expect(find.byKey(const Key('paired-confirm-interpreted')), findsOneWidget);
    expect(find.textContaining('Read from your words by the selected Brain: statement'), findsOneWidget);
    expect(runtime.decisions, isEmpty);
  });

  testWidgets('intent: cancelling a confirmation sends abandon and runs nothing', (tester) async {
    final runtime = _IntentRuntime();
    await tester.pumpWidget(_host(runtime));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('choice-nobrain')));
    await tester.enterText(find.byKey(const Key('paired-input')), 'remember that the budget report is due');
    await tester.pump();
    await tester.tap(find.byKey(const Key('paired-send')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('paired-option-f3')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('paired-abandon')));
    await tester.pumpAndSettle();
    expect(runtime.intentDecisions.last['decision'], 'abandon');
    expect(runtime.decisions, isEmpty);
    expect(find.textContaining('INTENT_ABANDONED'), findsOneWidget);
  });

  testWidgets('without a paired client installation the screen says so and fabricates nothing', (tester) async {
    await tester.pumpWidget(_host(null));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('paired-unavailable')), findsOneWidget);
    expect(find.byKey(const Key('paired-send')), findsNothing);
  });
}
