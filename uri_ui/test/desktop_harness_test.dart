import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/services/desktop_harness_test_client.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/widgets/desktop_harness_test.dart';

void main() {
  final providerRows = [
    for (final id in ['claude_code', 'antigravity'])
      {
        'id': id,
        'label': id == 'claude_code' ? 'Claude Code' : 'Antigravity',
        'installed': true,
        'version': 'test',
        'authentication': 'test',
        'authentication_evidence': 'test evidence',
        'quota': 'unknown',
        'qualification': 'provisional',
        'models': [],
        'native_tools': [],
        'inventory_status': 'unknown',
        'running_sessions': 0,
        'eligible': id == 'claude_code',
        'blocked_reason': 'Containment unqualified',
        'permissions': 'copy only',
        'capabilities': [],
        'onboarding': 'Native sign-in',
        'configuration': 'No native integrations',
      },
  ];
  testWidgets('requires a separate click to approve and renders the receipt', (
    tester,
  ) async {
    final uri = MockUriClient();
    uri.restoreSession(token: 'uri-test-token', username: 'tester');
    uri.setBaseUrl('http://127.0.0.1:8000');
    final calls = <http.Request>[];
    final client = DesktopHarnessTestClient(
      uri,
      httpClient: MockClient((request) async {
        calls.add(request);
        expect(request.headers['Authorization'], 'Bearer ${uri.authToken}');
        if (request.url.path.endsWith('/providers/refresh')) {
          return http.Response(jsonEncode({'providers': providerRows}), 200);
        }
        if (request.url.path.endsWith('/tasks')) {
          return http.Response('{"tasks":[]}', 200);
        }
        if (request.url.path.endsWith('/prepare')) {
          expect(jsonDecode(request.body), {'provider': 'claude_code'});
          return http.Response(
            jsonEncode({
              'approval_id': 'one-use',
              'state': 'PROVISIONAL',
              'workspace': 'disposable',
              'model': 'native default',
              'permissions': 'copy only',
            }),
            200,
          );
        }
        if (request.url.path.endsWith('/start')) {
          expect(jsonDecode(request.body), {'authorized': true});
          return http.Response(
            jsonEncode({
              'task_id': 'task1',
              'status': 'RUNNING',
              'progress': 'Running',
              'result': 'Running',
              'recovery_choices': [],
            }),
            200,
          );
        }
        return http.Response(
          jsonEncode({
            'task_id': 'task1',
            'status': 'SUCCEEDED',
            'progress': 'Settled',
            'recovery_choices': [],
            'receipt': {
              'verified': true,
              'execution_ok': true,
              'verification_status': 'VERIFIED',
              'core_duration_ms': 395,
              'harness_duration_ms': 300,
            },
            'result': 'Amount column reference repaired',
            'core_duration_ms': 395,
            'state': 'PROVISIONAL',
          }),
          200,
        );
      }),
    );
    final navigatorKey = GlobalKey<NavigatorState>();
    await tester.pumpWidget(
      MaterialApp(
        navigatorKey: navigatorKey,
        builder: (context, child) => DesktopHarnessTest(
          client: client,
          navigatorKey: navigatorKey,
          child: child!,
        ),
        home: const Scaffold(body: Text('Real application child')),
      ),
    );
    expect(
      tester
          .widget<TextButton>(
            find.byKey(const ValueKey('desktop-harness-prepare')),
          )
          .onPressed,
      isNull,
    );
    expect(calls, isEmpty);
    await tester.runAsync(() async {
      await tester.tap(find.text('Harness Management'));
      await Future<void>.delayed(const Duration(milliseconds: 20));
    });
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<TextButton>(find.byKey(const ValueKey('select-antigravity')))
          .onPressed,
      isNull,
    );
    await tester.ensureVisible(find.text('Select Claude Code'));
    await tester.tap(find.text('Select Claude Code'));
    await tester.pumpAndSettle();
    expect(calls.where((r) => r.url.path.endsWith('/start')), isEmpty);
    await tester.runAsync(() async {
      await tester.tap(find.text('Prepare disposable test'));
      await Future<void>.delayed(const Duration(milliseconds: 20));
    });
    await tester.pumpAndSettle();
    expect(calls.length, 3);
    expect(
      find.textContaining('Workspace: disposable'),
      findsOneWidget,
      reason: tester
          .widgetList<Text>(find.byType(Text))
          .map((w) => w.data)
          .join('\n'),
    );
    await tester.runAsync(() async {
      await tester.tap(find.text('Authorize this Claude Code run'));
      await Future<void>.delayed(const Duration(milliseconds: 20));
    });
    await tester.pump(const Duration(seconds: 2));
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 1200));
    });
    await tester.pumpAndSettle();
    expect(calls.where((r) => r.url.path.endsWith('/start')).length, 1);
    expect(
      find.textContaining('Amount column reference repaired'),
      findsOneWidget,
    );
    expect(find.text('Real application child'), findsOneWidget);
    client.close();
  });

  test(
    'unauthenticated and non-loopback requests never leave client',
    () async {
      final uri = MockUriClient();
      var calls = 0;
      final client = DesktopHarnessTestClient(
        uri,
        httpClient: MockClient((_) async {
          calls++;
          return http.Response('{}', 200);
        }),
      );
      await expectLater(client.prepare(), throwsStateError);
      uri.restoreSession(token: 'uri-test-token', username: 'tester');
      uri.setBaseUrl('http://remote.example:8000');
      await expectLater(client.prepare(), throwsStateError);
      expect(calls, 0);
      client.close();
    },
  );

  test('errors never retry a side effect', () async {
    final uri = MockUriClient()
      ..restoreSession(token: 'uri-test-token', username: 'tester');
    uri.setBaseUrl('http://127.0.0.1:8000');
    var calls = 0;
    final client = DesktopHarnessTestClient(
      uri,
      httpClient: MockClient((_) async {
        calls++;
        return http.Response('{"detail":"private stderr"}', 503);
      }),
    );
    await expectLater(client.approve('one-use'), throwsStateError);
    expect(calls, 1);
    client.close();
  });
}
