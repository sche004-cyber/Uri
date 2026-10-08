import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/services/desktop_harness_test_client.dart';
import 'package:uri_ui/app.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/models/user_preferences.dart';
import 'package:shared_preferences/shared_preferences.dart';
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
        home: Scaffold(
          body: Column(
            children: [
              const Text('Real application child'),
              Expanded(
                child: Builder(
                  builder: (context) =>
                      HarnessAccess.maybeOf(context)!.workspaceBuilder(context),
                ),
              ),
            ],
          ),
        ),
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

  testWidgets(
    'approval survives navigation and no harness footer appears on unrelated pages',
    (tester) async {
      SharedPreferences.setMockInitialValues({});
      tester.view.physicalSize = const Size(1280, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final uri = MockUriClient()
        ..restoreSession(token: 'unit-user', username: 'tester');
      uri.setBaseUrl('http://127.0.0.1:8021');
      final state = AppState(uri);
      await state.updatePreferences(
        const UserPreferences.initial().copyWith(completedOnboarding: true),
      );
      final calls = <http.Request>[];
      final client = DesktopHarnessTestClient(
        uri,
        httpClient: MockClient((request) async {
          calls.add(request);
          if (request.url.path.endsWith('/providers/refresh'))
            return http.Response(jsonEncode({'providers': providerRows}), 200);
          if (request.url.path.endsWith('/tasks'))
            return http.Response('{"tasks":[]}', 200);
          return http.Response(
            jsonEncode({
              'approval_id': 'pending-one-use',
              'workspace': 'disposable',
              'model': 'native default',
              'permissions': 'copy only',
            }),
            200,
          );
        }),
      );
      final navigatorKey = GlobalKey<NavigatorState>();
      await tester.pumpWidget(
        UriApp(
          appState: state,
          integrationNavigatorKey: navigatorKey,
          integrationTestBuilder: (context, child) => DesktopHarnessTest(
            client: client,
            navigatorKey: navigatorKey,
            child: child!,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('desktop-harness-prepare')),
        findsNothing,
      );
      await tester.tap(find.text('Chat'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('workspace-harness-tab')));
      await tester.pumpAndSettle();
      await tester.runAsync(() async {
        await tester.tap(find.text('Harness Management'));
        await Future<void>.delayed(const Duration(milliseconds: 30));
      });
      await tester.pumpAndSettle();
      await tester.ensureVisible(find.text('Select Claude Code'));
      await tester.tap(find.text('Select Claude Code'));
      await tester.pumpAndSettle();
      await tester.runAsync(() async {
        await tester.tap(find.text('Prepare disposable test'));
        await Future<void>.delayed(const Duration(milliseconds: 30));
      });
      await tester.pumpAndSettle();
      await tester.tap(find.text('Home'));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('desktop-harness-approve')),
        findsNothing,
      );
      await tester.tap(find.text('Settings'));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('desktop-harness-prepare')),
        findsNothing,
      );
      await tester.tap(find.text('Chat'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Workspace: disposable'), findsOneWidget);
      expect(
        tester
            .widget<TextButton>(
              find.byKey(const ValueKey('desktop-harness-approve')),
            )
            .onPressed,
        isNotNull,
      );
      expect(calls.where((r) => r.url.path.endsWith('/start')), isEmpty);
      client.close();
    },
  );

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
