import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/assist/assist_controller.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/contracts/readiness_report.dart';
import 'package:uri_ui/living/contracts/work_items.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'package:uri_ui/services/mock_uri_client.dart';

/// A fake worker that answers the Assist commands the way `uri_assist.bridge`
/// does (state, separate permissions, screen confirmation, revoke), so the UI
/// is tested against the real command contract without a Python process.
class AssistRuntime implements IntegratedRuntime {
  AssistRuntime({this.tabAvailable = true});
  final bool tabAvailable;
  final commands = <Map<String, dynamic>>[];
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  bool _closed = false;
  String state = 'OFF';
  Map<String, dynamic>? scope;
  Set<String> perms = {};

  void emit(Map<String, dynamic> ev) => _events.add(ev);

  Map<String, dynamic> _status() => {
    'state': state,
    'generation': 1,
    'scope': scope,
    'permissions': {for (final p in ['observe', 'suggest', 'remember', 'insert', 'act']) p: perms.contains(p)},
    'adapters': [
      {'adapter': 'browser_extension', 'kind': 'browser_tab', 'state': tabAvailable ? 'AVAILABLE' : 'UNAVAILABLE',
        if (!tabAvailable) 'reason': 'channel not implemented in A0'},
      {'adapter': 'windows_uia', 'kind': 'desktop_window', 'state': 'UNAVAILABLE', 'reason': 'not implemented in A0'},
      {'adapter': 'screen_capture', 'kind': 'entire_screen', 'state': 'AVAILABLE'},
    ],
    'vision': {'model_level': 'QUALIFIED', 'application': 'NOT VERIFIED'},
    'last_refusal': null,
  };

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;
  @override
  bool get closed => _closed;

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> c) async {
    commands.add(c);
    switch (c['command']) {
      case 'assist_status':
        return _status();
      case 'assist_targets':
        if (c['kind'] == 'browser_tab') {
          return {'kind': 'browser_tab', 'targets': [{'target_id': 'tab-7', 'label': 'Fee form', 'origin': 'https://portal.example'}]};
        }
        return {'kind': c['kind'], 'targets': [{'target_id': 'screen-0', 'label': 'Display 1'}]};
      case 'assist_grant':
        if (c['kind'] == 'entire_screen' && c['confirm_screen'] != true) {
          throw IntegratedRuntimeException('SCREEN_CONFIRMATION_REQUIRED');
        }
        state = 'ACTIVE';
        perms = {...(c['permissions'] as List).cast<String>()};
        scope = {'kind': c['kind'], 'target_id': c['target_id'], 'label': c['kind'] == 'browser_tab' ? 'Fee form' : 'Display 1'};
        return _status();
      case 'assist_pause':
        state = 'PAUSED';
        return _status();
      case 'assist_resume':
        state = 'ACTIVE';
        return _status();
      case 'assist_revoke':
        state = 'OFF';
        scope = null;
        perms = {};
        return _status();
      case 'assist_check':
        if (!perms.contains('suggest')) throw IntegratedRuntimeException('PERMISSION_NOT_GRANTED_SUGGEST');
        return {
          'observation': {'title': 'Fee form', 'fields': 4, 'sensitive_fields': 1},
          'findings': [{'code': 'EMAIL_FORMAT', 'field': 'Parent e-mail', 'message': 'Incomplete e-mail address.'}],
          'changed_anything': false,
        };
      case 'web_research':
        return {'job_id': 'job-1'};
      default:
        return {'ok': true};
    }
  }

  @override
  Future<void> close() async => _closed = true;
  @override
  Future<void> kill() async => _closed = true;
}

Future<(LivingServices, AssistRuntime)> pumpAssist(WidgetTester tester, {bool tabAvailable = true}) async {
  SharedPreferences.setMockInitialValues({});
  tester.view.physicalSize = const Size(1280, 900);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final rt = AssistRuntime(tabAvailable: tabAvailable);
  final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
  final demo = MockCompanionSource();
  final sim = MockWorkSimulator(stepInterval: const Duration(milliseconds: 100));
  final services = LivingServices(
    presentation: UiPresentationController(commandCooldown: Duration.zero),
    companion: CompositeCompanionSource([AppStateCompanionSource(appState, dataIsMock: true), sim.companion, demo]),
    work: sim,
    readiness: MockReadinessSource(),
    effects: EffectsSettings(reducedMotion: true),
    demo: demo,
    assist: AssistController(runtime: () => rt, events: rt.events),
  );
  addTearDown(services.dispose);
  await tester.pumpWidget(LivingApp(appState: appState, services: services, skipOnboarding: true));
  await tester.pumpAndSettle();
  return (services, rt);
}

void main() {
  test('Assist is a fourth form with its own command and label', () {
    expect(UiPresentationMode.values, contains(UiPresentationMode.assist));
    expect(UiPresentationMode.assist.label, 'Assist');
    expect((parseLocalUiCommand('URI assist') as ShowModeCommand).mode, UiPresentationMode.assist);
    expect(parseLocalUiCommand('assist me with this form'), isNull);
  });

  testWidgets('Companion offers Workspace | Dashboard | Assist; opening Assist observes nothing', (tester) async {
    final (services, rt) = await pumpAssist(tester);
    expect(find.text('Workspace'), findsOneWidget);
    expect(find.text('Dashboard'), findsOneWidget);
    expect(find.text('Assist'), findsOneWidget);
    final orb = tester.element(find.byKey(LivingShell.orbKey));
    await tester.tap(find.text('Assist'));
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.assist);
    expect(identical(tester.element(find.byKey(LivingShell.orbKey)), orb), isTrue);
    // Only the status was read: no target listing, no capture, no grant.
    expect(rt.commands.map((c) => c['command']).toSet(), {'assist_status'});
    expect(find.byKey(const ValueKey('assist-picker')), findsOneWidget);
    expect(find.textContaining("URI can't see anything"), findsOneWidget);
    expect(find.byKey(const ValueKey('assist-kind-desktop_window-unavailable')), findsOneWidget);
  });

  testWidgets('Ctrl+4 opens Assist', (tester) async {
    final (services, _) = await pumpAssist(tester);
    await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
    await tester.sendKeyEvent(LogicalKeyboardKey.digit4);
    await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.assist);
  });

  testWidgets('grant a tab with Observe only, then Suggest stays off; Stop revokes in one tap', (tester) async {
    final (services, rt) = await pumpAssist(tester);
    services.presentation.setMode(UiPresentationMode.assist);
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: find.byKey(const ValueKey('assist-kind-browser_tab')), matching: find.text('Choose')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('assist-target-tab-7')));
    await tester.pumpAndSettle();
    final grant = rt.commands.lastWhere((c) => c['command'] == 'assist_grant');
    expect(grant['permissions'], ['observe']);
    expect(grant['confirm_screen'], isFalse);
    expect(find.byKey(const ValueKey('assist-scope-label')), findsOneWidget);
    expect(find.textContaining('browser tab "Fee form" only'), findsOneWidget);
    // Suggest was not granted: the check button is disabled.
    final check = tester.widget<FilledButton>(find.byKey(const ValueKey('assist-check')));
    expect(check.onPressed, isNull);
    await tester.tap(find.byKey(const ValueKey('assist-stop')));
    await tester.pumpAndSettle();
    expect(rt.commands.last['command'], 'assist_revoke');
    expect(services.assist!.off, isTrue);
    expect(find.byKey(const ValueKey('assist-picker')), findsOneWidget);
  });

  testWidgets('Suggest is a separate opt-in; Live Assist shows findings and changes nothing', (tester) async {
    final (services, rt) = await pumpAssist(tester);
    services.presentation.setMode(UiPresentationMode.assist);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('assist-suggest-toggle')));
    await tester.pump();
    await tester.tap(find.descendant(of: find.byKey(const ValueKey('assist-kind-browser_tab')), matching: find.text('Choose')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('assist-target-tab-7')));
    await tester.pumpAndSettle();
    expect(rt.commands.lastWhere((c) => c['command'] == 'assist_grant')['permissions'], ['observe', 'suggest']);
    await tester.tap(find.byKey(const ValueKey('assist-check')));
    await tester.pumpAndSettle();
    expect(find.text('Parent e-mail'), findsOneWidget);
    expect(find.textContaining('1 private (hidden)'), findsOneWidget);
    // Pause then resume through the header chip.
    await tester.tap(find.byKey(const ValueKey('assist-pause')));
    await tester.pumpAndSettle();
    expect(services.assist!.paused, isTrue);
    expect(find.textContaining('Paused'), findsWidgets);
    await tester.tap(find.byKey(const ValueKey('assist-resume')));
    await tester.pumpAndSettle();
    expect(services.assist!.active, isTrue);
  });

  testWidgets('entire screen needs a second explicit confirmation', (tester) async {
    final (services, rt) = await pumpAssist(tester);
    services.presentation.setMode(UiPresentationMode.assist);
    await tester.pumpAndSettle();
    await tester.tap(find.descendant(of: find.byKey(const ValueKey('assist-kind-entire_screen')), matching: find.text('Choose…')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('assist-target-screen-0')));
    await tester.pumpAndSettle();
    expect(rt.commands.where((c) => c['command'] == 'assist_grant'), isEmpty);
    expect(find.byKey(const ValueKey('assist-confirm-screen')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('assist-confirm-screen-allow')));
    await tester.pumpAndSettle();
    final g = rt.commands.lastWhere((c) => c['command'] == 'assist_grant');
    expect(g['kind'], 'entire_screen');
    expect(g['confirm_screen'], isTrue);
    expect(services.assist!.active, isTrue);
  });

  testWidgets('Companion shows the active scope with Stop', (tester) async {
    final (services, rt) = await pumpAssist(tester);
    await services.assist!.grant('browser_tab', 'tab-7', suggest: false);
    services.presentation.setMode(UiPresentationMode.companion);
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('assist-scope-line')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('assist-line-stop')));
    await tester.pumpAndSettle();
    expect(rt.commands.last['command'], 'assist_revoke');
    expect(find.byKey(const ValueKey('assist-scope-line')), findsNothing);
  });

  testWidgets('research result renders through the A2UI renderer; Teach and Smart Fill are not available', (tester) async {
    final (services, rt) = await pumpAssist(tester);
    services.presentation.setMode(UiPresentationMode.assist);
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('assist-tab-research')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('assist-research-query')), 'fee increase 2027');
    await tester.tap(find.byKey(const ValueKey('assist-research-go')));
    await tester.pumpAndSettle();
    expect(rt.commands.last['command'], 'web_research');
    rt.emit({'schema': 'uri.assist.event.v1', 'turn_id': 'job-1', 'type': 'research.progress', 'data': {'stage': 'retrieve'}});
    await tester.pumpAndSettle();
    expect(find.textContaining('retrieve'), findsOneWidget);
    rt.emit({
      'schema': 'uri.assist.event.v1', 'turn_id': 'job-1', 'type': 'research.finished',
      'data': {'status': 'COMPLETED_WITH_RESULT', 'a2ui': [
        {'version': 'v0.9', 'createSurface': {'surfaceId': 'web.research.job-1', 'catalogId': 'uri:a2ui/catalog/v1',
          'theme': {'agentDisplayName': 'URI', 'placement': 'workspace'}}},
        {'version': 'v0.9', 'updateComponents': {'surfaceId': 'web.research.job-1', 'components': [
          {'id': 'root', 'component': 'Column', 'children': ['t'], 'gap': 'medium'},
          {'id': 't', 'component': 'Text', 'text': 'Fees rise 4.5% [1]', 'variant': 'body'}]}},
        {'version': 'v0.9', 'updateDataModel': {'surfaceId': 'web.research.job-1', 'path': '/', 'value': {
          'bound': {'surface': {'digest': '${'a' * 64}', 'revision': 1, 'kind': 'web.research_result', 'title': 'Research'}}}}},
      ]},
    });
    await tester.pumpAndSettle();
    expect(find.text('Fees rise 4.5% [1]'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('assist-tab-fill')));
    await tester.pumpAndSettle();
    expect(find.textContaining('coming in A1'), findsOneWidget);
  });

  testWidgets('without a worker the Assist view says so and observes nothing', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
    final services = LivingApp.buildDefaultServices(appState);
    addTearDown(services.dispose);
    services.presentation.setMode(UiPresentationMode.assist);
    await tester.pumpWidget(LivingApp(appState: appState, services: services, skipOnboarding: true));
    await tester.pump(const Duration(milliseconds: 600));
    expect(find.byKey(const ValueKey('assist-unavailable')), findsOneWidget);
  });

  test('a replaced worker never shows the old grant', () async {
    var rt = AssistRuntime();
    final a = AssistController(runtime: () => rt);
    await a.grant('browser_tab', 'tab-7', suggest: true);
    expect(a.active, isTrue);
    rt = AssistRuntime();                 // worker restarted: the new one starts OFF
    await a.check();                      // any call notices the new worker first
    expect(a.off, isTrue);
    expect(a.lastError, 'PERMISSION_NOT_GRANTED_SUGGEST');
    expect(a.findings, isEmpty);
    a.dispose();
  });

  test('assist frames never touch OI turn or stall state', () async {
    final rt = AssistRuntime();
    final conv = OiConversation(rt);
    final got = <Map<String, dynamic>>[];
    final sub = conv.assistEvents.listen(got.add);
    conv.workerUnresponsive = true;
    rt.emit({'schema': 'uri.assist.event.v1', 'turn_id': 'job-1', 'type': 'research.progress', 'data': {'stage': 'x'}});
    await Future<void>.delayed(Duration.zero);
    expect(got, hasLength(1));
    expect(conv.workerUnresponsive, isTrue, reason: 'a research frame must not make a silent worker look alive');
    await sub.cancel();
    conv.dispose();
  });
}
