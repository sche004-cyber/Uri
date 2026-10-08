import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/screens/onboarding/living_onboarding_flow.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/mock_uri_client.dart';

import 'living_shell_test.dart' show testServices;

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('first run shows onboarding; all eight steps walk; finishing persists and opens the shell',
      (tester) async {
    tester.view.physicalSize = const Size(1280, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final appState = AppState(MockUriClient());
    final services = testServices(appState);
    addTearDown(services.dispose);
    await tester.pumpWidget(LivingApp(appState: appState, services: services));
    await tester.pumpAndSettle();

    expect(find.byType(LivingOnboardingFlow), findsOneWidget);
    expect(find.byKey(const ValueKey('onboarding-orb')), findsOneWidget);
    for (var i = 0; i < LivingOnboardingFlow.stepTitles.length; i++) {
      expect(find.text(LivingOnboardingFlow.stepTitles[i]), findsOneWidget, reason: 'step $i');
      switch (i) {
        case 0:
          await tester.tap(find.byKey(const ValueKey('preview-awaitingApproval')));
          await tester.pumpAndSettle();
          expect(find.bySemanticsLabel('URI companion: Needs your approval'), findsOneWidget);
        case 1:
          await tester.tap(find.byKey(const ValueKey('onboarding-test-connection')));
          await tester.pumpAndSettle();
          expect(find.textContaining('Mock client answered'), findsOneWidget);
        case 2:
          expect(find.text('Codex (native CLI)'), findsOneWidget);
          expect(find.textContaining('Not installed'), findsOneWidget);
        case 4:
          await tester.tap(find.byKey(const ValueKey('autonomy-routineAutoApprove')));
          await tester.pumpAndSettle();
          expect(appState.preferences.autonomyLevel.name, 'routineAutoApprove');
        case 5:
          expect(find.textContaining('never signs in for you'), findsOneWidget);
        case 6:
          await tester.tap(find.byKey(const ValueKey('focus-Research')));
          await tester.pumpAndSettle();
        case 7:
          expect(find.text('URI server reachable'), findsOneWidget);
          expect(find.text('SIMULATED'), findsWidgets);
          expect(find.text('UNAVAILABLE'), findsOneWidget);
      }
      if (i < LivingOnboardingFlow.stepTitles.length - 1) {
        await tester.tap(find.byKey(const ValueKey('onboarding-next')));
        await tester.pumpAndSettle();
      }
    }
    await tester.tap(find.text('Start using URI'));
    await tester.pumpAndSettle();
    expect(find.byType(LivingShell), findsOneWidget);
    expect(appState.preferences.focusAreas, contains('Research'));
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getBool(LivingPrefs.onboardingDone), isTrue);
    expect(prefs.getBool('uri.completedOnboarding'), isTrue,
        reason: 'the real UserPreferences store is written (shared with the Hybrid app by design)');
    expect(tester.takeException(), isNull);
  });

  testWidgets('Skip setup works from the first step and Back is available after it', (tester) async {
    tester.view.physicalSize = const Size(1000, 760);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final appState = AppState(MockUriClient());
    final services = testServices(appState);
    addTearDown(services.dispose);
    await tester.pumpWidget(LivingApp(appState: appState, services: services));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('onboarding-back')), findsNothing);
    await tester.tap(find.byKey(const ValueKey('onboarding-next')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('onboarding-back')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('onboarding-skip')));
    await tester.pumpAndSettle();
    expect(find.byType(LivingShell), findsOneWidget);
  });
}
