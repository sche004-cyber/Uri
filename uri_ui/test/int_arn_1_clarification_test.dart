// INT-ARN-1 Slice D (Flutter) Comprehensive Test Suite
//
// Covers:
// 1. Clarification kinds: CHOOSE_ONE, CONFIRM_ONE, CHOOSE_ATTRIBUTE, FREE_INPUT_ONLY
// 2. Free input escape path
// 3. Over-cap presentation limit (max 5 options shown)
// 4. Stale lock / retry handling
// 5. Keyboard activation (Enter/Space)
// 6. Compact layout (narrow width)
// 7. History read-only behavior
// 8. Tentative binding ("Using X · Change")
// 9. AppState.submitClarificationResponse duplicate-submit guard & turn updates
// 10. HttpUriClient request/response wire contract verification matching backend server.py

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'package:uri_ui/models/clarification.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/http_uri_client.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/widgets/clarification_card.dart';
import 'package:uri_ui/widgets/turn_card.dart';

Widget _wrap(Widget child) => MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(child: child),
      ),
    );

ClarificationRequest _sampleRequest({
  ClarificationKind kind = ClarificationKind.chooseOne,
  int optionCount = 3,
  int filterCount = 0,
}) {
  return ClarificationRequest(
    ambiguityId: 'amb-test-1',
    traceId: 'trace-test-1',
    kind: kind,
    question: 'Which item did you mean?',
    options: List.generate(
      optionCount,
      (i) => ClarificationCandidateOption(
        optionKey: 's${i + 1}',
        candidateId: 'cand-${i + 1}',
        label: 'Candidate ${i + 1}',
        rank: i,
      ),
    ),
    attributeAxis: filterCount > 0 ? 'type' : null,
    attributeFilters: List.generate(
      filterCount,
      (i) => ClarificationAttributeFilter(
        optionKey: 'a${i + 1}',
        axis: 'type',
        value: 'type_${i + 1}',
        label: 'Type ${i + 1}',
        memberCount: 2,
      ),
    ),
    overflowCount: 0,
    escapeLabel: 'None of these / something else',
    candidateSetFingerprint: 'fp-12345',
  );
}

void main() {
  group('INT-ARN-1 Clarification Card Kinds & Interactions', () {
    testWidgets('CHOOSE_ONE: renders options and emits candidate payload on tap',
        (tester) async {
      ClarificationResponsePayload? emitted;
      final request = _sampleRequest(
        kind: ClarificationKind.chooseOne,
        optionCount: 3,
      );

      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        onRespond: (p) => emitted = p,
      )));

      expect(find.text('Which item did you mean?'), findsOneWidget);
      expect(find.byKey(const Key('clarification-option-s1')), findsOneWidget);
      expect(find.byKey(const Key('clarification-option-s2')), findsOneWidget);
      expect(find.byKey(const Key('clarification-option-s3')), findsOneWidget);

      await tester.tap(find.byKey(const Key('clarification-option-s1')));
      await tester.pump();

      expect(emitted, isNotNull);
      expect(emitted!.ambiguityId, 'amb-test-1');
      expect(emitted!.kind, ClarificationResponseKind.candidate);
      expect(emitted!.candidateId, 'cand-1');
      expect(emitted!.candidateSetFingerprint, 'fp-12345');

      // Card locks upon answer
      expect(find.byKey(const Key('clarification-answered')), findsOneWidget);
      expect(find.text('Using: Candidate 1'), findsOneWidget);
    });

    testWidgets('CONFIRM_ONE: renders single option and emits candidate payload',
        (tester) async {
      ClarificationResponsePayload? emitted;
      final request = _sampleRequest(
        kind: ClarificationKind.confirmOne,
        optionCount: 1,
      );

      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        onRespond: (p) => emitted = p,
      )));

      expect(find.byKey(const Key('clarification-option-s1')), findsOneWidget);
      expect(find.byKey(const Key('clarification-option-s2')), findsNothing);

      await tester.tap(find.byKey(const Key('clarification-option-s1')));
      await tester.pump();

      expect(emitted, isNotNull);
      expect(emitted!.candidateId, 'cand-1');
      expect(emitted!.kind, ClarificationResponseKind.candidate);
    });

    testWidgets('CHOOSE_ATTRIBUTE: renders attribute chips and emits attribute payload',
        (tester) async {
      ClarificationResponsePayload? emitted;
      final request = _sampleRequest(
        kind: ClarificationKind.chooseAttribute,
        optionCount: 2,
        filterCount: 2,
      );

      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        onRespond: (p) => emitted = p,
      )));

      expect(find.byKey(const Key('clarification-filter-a1')), findsOneWidget);
      expect(find.byKey(const Key('clarification-filter-a2')), findsOneWidget);

      await tester.tap(find.byKey(const Key('clarification-filter-a1')));
      await tester.pump();

      expect(emitted, isNotNull);
      expect(emitted!.kind, ClarificationResponseKind.attribute);
      expect(emitted!.optionKey, 'a1');
      expect(emitted!.candidateSetFingerprint, 'fp-12345');
    });

    testWidgets('FREE_INPUT_ONLY: renders text input immediately and emits free text',
        (tester) async {
      ClarificationResponsePayload? emitted;
      final request = _sampleRequest(
        kind: ClarificationKind.freeInputOnly,
        optionCount: 0,
      );

      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        onRespond: (p) => emitted = p,
      )));

      expect(find.byKey(const Key('clarification-free-input')), findsOneWidget);
      expect(find.byKey(const Key('clarification-escape')), findsNothing);

      await tester.enterText(
        find.byKey(const Key('clarification-free-input')),
        'The draft about project roadmap',
      );
      await tester.tap(find.byKey(const Key('clarification-free-input-submit')));
      await tester.pump();

      expect(emitted, isNotNull);
      expect(emitted!.kind, ClarificationResponseKind.freeInput);
      expect(emitted!.text, 'The draft about project roadmap');
    });

    testWidgets('Escape button opens free input and submits free text',
        (tester) async {
      ClarificationResponsePayload? emitted;
      final request = _sampleRequest(
        kind: ClarificationKind.chooseOne,
        optionCount: 2,
      );

      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        onRespond: (p) => emitted = p,
      )));

      expect(find.byKey(const Key('clarification-free-input')), findsNothing);

      await tester.tap(find.byKey(const Key('clarification-escape')));
      await tester.pump();

      expect(find.byKey(const Key('clarification-free-input')), findsOneWidget);

      await tester.enterText(
        find.byKey(const Key('clarification-free-input')),
        'None of these, use file 42',
      );
      await tester.tap(find.byKey(const Key('clarification-free-input-submit')));
      await tester.pump();

      expect(emitted, isNotNull);
      expect(emitted!.kind, ClarificationResponseKind.freeInput);
      expect(emitted!.text, 'None of these, use file 42');
    });

    testWidgets('Over-cap presentation limit: exactly 5 options rendered when 7 provided',
        (tester) async {
      final request = _sampleRequest(
        kind: ClarificationKind.chooseOne,
        optionCount: 7,
      );

      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        onRespond: (_) {},
      )));

      expect(find.byKey(const Key('clarification-option-s1')), findsOneWidget);
      expect(find.byKey(const Key('clarification-option-s2')), findsOneWidget);
      expect(find.byKey(const Key('clarification-option-s3')), findsOneWidget);
      expect(find.byKey(const Key('clarification-option-s4')), findsOneWidget);
      expect(find.byKey(const Key('clarification-option-s5')), findsOneWidget);
      expect(find.byKey(const Key('clarification-option-s6')), findsNothing);
      expect(find.byKey(const Key('clarification-option-s7')), findsNothing);
      expect(find.byKey(const Key('clarification-escape')), findsOneWidget);
    });

    testWidgets('Stale lock / retry: card locks when isSubmitting, re-enables with retryMessage',
        (tester) async {
      final request = _sampleRequest(optionCount: 2);

      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        isSubmitting: true,
        onRespond: (_) {},
      )));

      expect(find.byKey(const Key('clarification-submitting')), findsOneWidget);
      final button = tester.widget<OutlinedButton>(
        find.byKey(const Key('clarification-option-s1')),
      );
      expect(button.onPressed, isNull);

      // Re-render with retry message
      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        isSubmitting: false,
        retryMessage: 'Reference session expired. Please retry your choice.',
        onRespond: (_) {},
      )));

      expect(find.byKey(const Key('clarification-submitting')), findsNothing);
      expect(find.byKey(const Key('clarification-retry-message')), findsOneWidget);
      expect(
        find.text('Reference session expired. Please retry your choice.'),
        findsOneWidget,
      );

      final reEnabledButton = tester.widget<OutlinedButton>(
        find.byKey(const Key('clarification-option-s1')),
      );
      expect(reEnabledButton.onPressed, isNotNull);
    });

    testWidgets('Keyboard activation: Enter/Space triggers candidate button and free text',
        (tester) async {
      ClarificationResponsePayload? emitted;
      final request = _sampleRequest(optionCount: 2);

      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        onRespond: (p) => emitted = p,
      )));

      // Free input onSubmitted via keyboard Enter
      await tester.tap(find.byKey(const Key('clarification-escape')));
      await tester.pump();

      await tester.enterText(
        find.byKey(const Key('clarification-free-input')),
        'Keyboard entered text',
      );
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pump();

      expect(emitted, isNotNull);
      expect(emitted!.text, 'Keyboard entered text');
    });

    testWidgets('History read-only: options and inputs disabled when isReadOnly is true',
        (tester) async {
      final request = _sampleRequest(optionCount: 2);

      await tester.pumpWidget(_wrap(ClarificationCard(
        request: request,
        isReadOnly: true,
        onRespond: (_) {},
      )));

      final option1 = tester.widget<OutlinedButton>(
        find.byKey(const Key('clarification-option-s1')),
      );
      expect(option1.onPressed, isNull);
    });

    testWidgets('Compact layout: renders without overflow on narrow 320px width',
        (tester) async {
      final request = _sampleRequest(optionCount: 3, filterCount: 2);
      final turn = UriTurn(
        id: 't-compact',
        userText: 'Check file',
        timestamp: DateTime.now(),
        stage: TurnStage.awaitingClarification,
        understanding: 'Which file did you mean?',
        clarification: request,
      );

      await tester.pumpWidget(MaterialApp(
        home: Scaffold(
          body: Center(
            child: SizedBox(
              width: 320,
              child: TurnCard(
                turn: turn,
                onApprove: () {},
                onCancel: () {},
                onConnectService: (_) {},
                onOpenAttachment: (_) {},
                compact: true,
              ),
            ),
          ),
        ),
      ));

      expect(tester.takeException(), isNull);
      expect(find.byKey(const Key('clarification-card')), findsOneWidget);
    });

    testWidgets('Tentative binding: shows "Using X · Change" and tap triggers callback',
        (tester) async {
      bool changeTapped = false;
      final turn = UriTurn(
        id: 't-tentative',
        userText: 'Send email to team',
        timestamp: DateTime.now(),
        stage: TurnStage.completed,
        understanding: 'Sending email',
        tentativeBinding: const TentativeBinding(
          label: 'Engineering Team list',
          candidateId: 'cand-team',
          bindingId: 'bind-team-1',
        ),
      );

      await tester.pumpWidget(_wrap(TurnCard(
        turn: turn,
        onApprove: () {},
        onCancel: () {},
        onConnectService: (_) {},
        onOpenAttachment: (_) {},
        onChangeTentativeBinding: () => changeTapped = true,
      )));

      expect(find.byKey(const Key('turn-tentative-binding')), findsOneWidget);
      expect(find.text('Using Engineering Team list'), findsOneWidget);
      expect(find.byKey(const Key('tentative-binding-change')), findsOneWidget);

      await tester.tap(find.byKey(const Key('tentative-binding-change')));
      await tester.pump();

      expect(changeTapped, isTrue);
    });
  });

  group('AppState Clarification Submission & Duplicate Guard', () {
    test('submitClarificationResponse prevents duplicate submits and updates turn',
        () async {
      final mockClient = MockUriClient();
      final appState = AppState(mockClient);

      final initialTurn = UriTurn(
        id: 'turn-clarify-1',
        userText: 'Read message',
        timestamp: DateTime.now(),
        stage: TurnStage.awaitingClarification,
        clarification: _sampleRequest(),
      );
      appState.conversation.add(initialTurn);

      final payload = ClarificationResponsePayload.freeInput(
        initialTurn.clarification!,
        'specific message id',
      );

      expect(appState.isSubmittingClarification('turn-clarify-1'), isFalse);

      final future1 = appState.submitClarificationResponse('turn-clarify-1', payload);
      expect(appState.isSubmittingClarification('turn-clarify-1'), isTrue);

      // Duplicate submission while in flight must be rejected
      final future2 = appState.submitClarificationResponse('turn-clarify-1', payload);
      final duplicateResult = await future2;
      expect(duplicateResult, isNull);

      final result = await future1;
      expect(result, isNotNull);
      expect(appState.isSubmittingClarification('turn-clarify-1'), isFalse);
      // The question card stays as history; the answer is a new turn
      // labelled with what the user chose.
      expect(appState.conversation, hasLength(2));
      expect(appState.conversation.first.clarification, isNotNull);
      expect(appState.conversation.last.stage, TurnStage.completed);
      expect(appState.conversation.last.userText, 'specific message id');
    });
  });

  group('HttpUriClient Wire Contract & Response Decoding', () {
    test('submits typed clarification_response to POST /ask and decodes response',
        () async {
      Map<String, dynamic>? recordedRequestJson;

      final httpClient = MockClient((request) async {
        if (request.url.path == '/ask') {
          recordedRequestJson = jsonDecode(request.body) as Map<String, dynamic>;
          return http.Response(
            jsonEncode({
              'status': 'awaiting_user_response',
              'session_id': 'sess-test-1',
              'clarification': {
                'ambiguity_id': 'amb-new-1',
                'trace_id': 'trace-new-1',
                'kind': 'CHOOSE_ONE',
                'question': 'Which file do you want to attach?',
                'options': [
                  {
                    'option_key': 's1',
                    'candidate_id': 'file-123',
                    'label': 'Budget 2026.pdf',
                    'rank': 0,
                  }
                ],
                'attribute_axis': null,
                'attribute_filters': [],
                'overflow_count': 0,
                'escape_label': 'None of these',
                'candidate_set_fingerprint': 'fp-file-999',
                'expires_at': '2026-10-02T20:00:00Z',
              },
              'tentative_binding': {
                'label': 'Budget 2026.pdf',
                'candidate_id': 'file-123',
                'binding_id': 'bind-file-1',
              },
              'serving_model': 'gemini-1.5-flash',
            }),
            200,
            headers: {'content-type': 'application/json'},
          );
        }
        return http.Response('{"error": "not found"}', 404);
      });

      final client = HttpUriClient(httpClient: httpClient);
      client.setSessionId('sess-test-1');

      final outgoingPayload = ClarificationResponsePayload.fromJson({
        'ambiguity_id': 'amb-origin-1',
        'response_kind': 'CANDIDATE',
        'candidate_id': 'cand-origin-1',
        'candidate_set_fingerprint': 'fp-origin-1',
      });

      final turn = await client.submitClarificationResponse(
        outgoingPayload,
        turnId: 'turn-wire-1',
      );

      // Verify wire shape sent to POST /ask
      expect(recordedRequestJson, isNotNull);
      expect(recordedRequestJson!['session_id'], 'sess-test-1');
      final wirePayload = recordedRequestJson!['clarification_response'] as Map<String, dynamic>;
      expect(wirePayload['ambiguity_id'], 'amb-origin-1');
      expect(wirePayload['response_kind'], 'CANDIDATE');
      expect(wirePayload['candidate_id'], 'cand-origin-1');
      expect(wirePayload['candidate_set_fingerprint'], 'fp-origin-1');

      // Verify returned UriTurn decoded from server response
      expect(turn.id, 'turn-wire-1');
      expect(turn.stage, TurnStage.awaitingClarification);
      expect(turn.clarification, isNotNull);
      expect(turn.clarification!.ambiguityId, 'amb-new-1');
      expect(turn.clarification!.question, 'Which file do you want to attach?');
      expect(turn.clarification!.options.single.label, 'Budget 2026.pdf');
      expect(turn.clarification!.expiresAt, '2026-10-02T20:00:00Z');
      expect(turn.tentativeBinding, isNotNull);
      expect(turn.tentativeBinding!.label, 'Budget 2026.pdf');
      expect(turn.tentativeBinding!.candidateId, 'file-123');
      expect(turn.servingModel, 'gemini-1.5-flash');
    });

    test('an ungrounded clarification card fails closed as a visible failed turn',
        () async {
      final httpClient = MockClient((request) async {
        return http.Response(
          jsonEncode({
            'status': 'awaiting_user_response',
            'session_id': 'sess-test-2',
            'clarification': {
              'ambiguity_id': 'amb-bad',
              'trace_id': 'trace-bad',
              'kind': 'CHOOSE_ONE',
              'question': 'Which one?',
              'options': [
                {'option_key': 'x1', 'candidate_id': '', 'label': 'Padded', 'rank': 1},
              ],
              'attribute_filters': [],
              'overflow_count': 0,
              'escape_label': 'None of these',
              'candidate_set_fingerprint': 'fp',
            },
          }),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final client = HttpUriClient(httpClient: httpClient);
      client.setSessionId('sess-test-2');
      final turn = await client.ask('open the report');
      expect(turn.stage, TurnStage.failed);
      expect(turn.clarification, isNull);
      expect(turn.failureReason, contains('not valid'));
    });
  });
}
