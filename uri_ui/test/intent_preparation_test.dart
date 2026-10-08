import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/services/desktop_harness_test_client.dart';
import 'package:uri_ui/services/uri_client.dart';
import 'package:uri_ui/widgets/intent_preparation.dart';

class IntentUri extends Fake implements UriClient {
  @override
  String? get authToken => 'account-one';
  @override
  String get baseUrl => 'http://127.0.0.1:8022';
  @override
  String get sessionId => 'existing-chat';
}

Map<String, dynamic> state({bool accepted = false, String? executor}) => {
  'cycle_id': 'cycle-one',
  'revision': 1,
  'questions_asked': 0,
  'status': accepted ? 'PREPARED' : 'AUDIT',
  'executor': executor,
  'audit': {
    'objective': 'Complete the existing console',
    'scope_in': ['Task preparation'],
    'scope_out': ['Production promotion'],
    'constraints': ['Frozen sources unchanged'],
    'assumptions': ['Previously discussed console identity'],
    'expected_outcome': 'A reviewable result',
    'acceptance_checks': ['Visible controls work'],
    'uncertainty': [],
    'relevant_context': [
      {
        'source': 'decision.md:7',
        'status': 'HISTORICAL',
        'content': 'Reuse DesktopHarnessTest',
      },
    ],
  },
  'package': accepted ? {'execution_authorized': false} : null,
};

void main() {
  testWidgets(
    'accept and executor selection prepare only; source and assumptions stay visible',
    (tester) async {
      final calls = <String>[];
      final transport = MockClient((request) async {
        calls.add(request.url.path);
        final body = jsonDecode(request.body) as Map;
        expect(body.containsKey('authorized'), isFalse);
        if (request.url.path.endsWith('/begin')) {
          expect(body['session_id'], 'existing-chat');
          return http.Response(jsonEncode(state()), 200);
        }
        if (request.url.path.endsWith('/accept')) {
          expect(body, {'revision': 1});
          return http.Response(jsonEncode(state(accepted: true)), 200);
        }
        if (request.url.path.endsWith('/executor')) {
          expect(body['executor'], 'codex');
          return http.Response(
            jsonEncode(state(accepted: true, executor: 'codex')),
            200,
          );
        }
        throw StateError('Unexpected execution route');
      });
      final client = DesktopHarnessTestClient(
        IntentUri(),
        httpClient: transport,
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: IntentPreparation(
                client: client,
                providers: const [
                  {'id': 'codex', 'label': 'Codex', 'installed': true},
                ],
                initialData: null,
                onChanged: (_) {},
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Understand and prepare a task'));
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('intent-request')),
        'Complete the console',
      );
      await tester.tap(find.byKey(const ValueKey('intent-understand')));
      await tester.pumpAndSettle();
      expect(find.textContaining('decision.md:7'), findsOneWidget);
      expect(
        find.textContaining('Previously discussed console identity'),
        findsOneWidget,
      );
      await tester.ensureVisible(find.byKey(const ValueKey('intent-accept')));
      await tester.tap(find.byKey(const ValueKey('intent-accept')));
      await tester.pumpAndSettle();
      await tester.ensureVisible(
        find.byKey(const ValueKey('intent-executor-codex')),
      );
      await tester.tap(find.byKey(const ValueKey('intent-executor-codex')));
      await tester.pumpAndSettle();
      expect(
        calls.every((path) => path.startsWith('/desktop/intent/')),
        isTrue,
      );
      expect(calls, hasLength(3));
      expect(find.text('Executor choice: codex'), findsOneWidget);
      await tester.ensureVisible(find.byKey(const ValueKey('intent-new-task')));
      await tester.tap(find.byKey(const ValueKey('intent-new-task')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('intent-request')), findsOneWidget);
      expect(find.textContaining('Clarification questions:'), findsNothing);
      expect(calls, hasLength(3));
      client.close();
    },
  );

  testWidgets('correction sends the existing cycle and revision', (
    tester,
  ) async {
    Map? posted;
    final client = DesktopHarnessTestClient(
      IntentUri(),
      httpClient: MockClient((request) async {
        expect(request.url.path, '/desktop/intent/cycle-one/respond');
        posted = jsonDecode(request.body) as Map;
        return http.Response(
          jsonEncode({...state(), 'revision': 2, 'questions_asked': 4}),
          200,
        );
      }),
    );
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: IntentPreparation(
              client: client,
              providers: const [],
              initialData: {...state(), 'questions_asked': 4},
              onChanged: (_) {},
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('Understand and prepare a task'));
    await tester.pumpAndSettle();
    await tester.ensureVisible(find.byKey(const ValueKey('intent-correct')));
    await tester.tap(find.byKey(const ValueKey('intent-correct')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const ValueKey('intent-correction')),
      'Only the existing console',
    );
    await tester.ensureVisible(find.text('Update existing intent'));
    await tester.tap(find.text('Update existing intent'));
    await tester.pumpAndSettle();
    expect(posted, {'revision': 1, 'correction': 'Only the existing console'});
    expect(find.text('Clarification questions: 4 / 5'), findsOneWidget);
    client.close();
  });
  testWidgets(
    'rejected output has safe recovery and no interpretation correction',
    (tester) async {
      final client = DesktopHarnessTestClient(
        IntentUri(),
        httpClient: MockClient((_) async => http.Response('{}', 200)),
      );
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: IntentPreparation(
                client: client,
                providers: const [],
                initialData: {
                  'cycle_id': 'one',
                  'revision': 1,
                  'questions_asked': 0,
                  'status': 'AUDIT_REJECTED',
                  'error_explanation': 'Required boolean field higher_reasoning is invalid. Retry explicitly.',
                  'reasoning_route': {
                    'provider': 'ollama',
                    'model': 'qwen3.5:9b',
                  },
                },
                onChanged: (_) {},
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Understand and prepare a task'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Intent audit rejected:'), findsOneWidget);
      expect(find.textContaining('higher_reasoning'), findsOneWidget);
      expect(
        find.textContaining('Configured reasoning: ollama / qwen3.5:9b'),
        findsOneWidget,
      );
      expect(find.text('Clarify / Correct'), findsNothing);
      expect(find.byKey(const ValueKey('intent-accept')), findsNothing);
      expect(find.text('Edit request / Retry'), findsOneWidget);
      client.close();
    },
  );
}
