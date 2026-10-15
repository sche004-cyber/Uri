import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/contracts/readiness_report.dart';
import 'package:uri_ui/living/contracts/work_items.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_sources.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'package:uri_ui/services/mock_uri_client.dart';

/// FCV-10: with the real worker connected, the Workspace context rail showed
/// SIMULATED placeholder documents and results next to live state.
class _Runtime implements IntegratedRuntime {
  final _events = StreamController<Map<String, dynamic>>.broadcast();

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;

  @override
  bool get closed => false;

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    switch (command['command']) {
      case 'brain_status':
        return {'state': 'READY', 'model_id': 'qwen-test'};
      case 'brain_health':
        return {'state': 'READY'};
      case 'brain_catalog':
        return {
          'rows': [
            {'id': 'runtime-v1', 'display': 'Runtime v1 (local)', 'selectable': true, 'selected': true, 'state': 'READY'},
          ],
          'fallback': 'none',
        };
      default:
        return {'ok': true};
    }
  }

  @override
  Future<void> close() async => _events.close();

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Future<void> _pumpWorkspace(WidgetTester tester, OiConversation? conv) async {
  SharedPreferences.setMockInitialValues({});
  tester.view.physicalSize = const Size(1400, 1000);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
  final demo = MockCompanionSource();
  final work = MockWorkSimulator(stepInterval: const Duration(milliseconds: 100));
  final services = LivingServices(
    presentation: UiPresentationController(commandCooldown: Duration.zero),
    companion: CompositeCompanionSource([if (conv != null) OiCompanionSource(conv), work.companion, demo]),
    work: work,
    readiness: conv != null ? OiReadinessSource(conv) : MockReadinessSource(),
    effects: EffectsSettings(reducedMotion: true),
    demo: demo,
    appDataIsMock: true,
    oi: conv,
  );
  addTearDown(services.dispose);
  await tester.pumpWidget(LivingApp(appState: appState, services: services, skipOnboarding: true));
  services.presentation.setMode(UiPresentationMode.workspace);
  for (var i = 0; i < 20; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
}

void main() {
  testWidgets('live worker: the context rail carries no simulated placeholder rows', (tester) async {
    final conv = OiConversation(_Runtime());
    await tester.runAsync(conv.refreshStatus);
    await _pumpWorkspace(tester, conv);
    expect(find.text('CONTEXT & FILES'), findsOneWidget);
    expect(find.text('Tender reply, Gangtok office.docx'), findsNothing);
    expect(find.text('No attachments staged.'), findsOneWidget);
    expect(find.text('No results yet.'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('demo (no worker): placeholder rows stay, each badged SIMULATED', (tester) async {
    await _pumpWorkspace(tester, null);
    expect(find.text('Tender reply, Gangtok office.docx'), findsOneWidget);
    expect(find.text('SIMULATED'), findsWidgets);
  });
}
