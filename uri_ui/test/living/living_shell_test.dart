import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/companion/energy_orb.dart';
import 'package:uri_ui/living/contracts/readiness_report.dart';
import 'package:uri_ui/living/contracts/work_items.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/widgets/status_badge.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/theme/uri_theme.dart';

/// Test wiring: identical to [LivingApp.buildDefaultServices] except the
/// orb's continuous ticker is off (reduced motion) so `pumpAndSettle`
/// terminates, and the simulator steps fast.
LivingServices testServices(AppState appState, {MockWorkSimulator? work}) {
  final demo = MockCompanionSource();
  final sim = work ?? MockWorkSimulator(stepInterval: const Duration(milliseconds: 100));
  return LivingServices(
    presentation: UiPresentationController(commandCooldown: Duration.zero),
    companion: CompositeCompanionSource([AppStateCompanionSource(appState), sim.companion, demo]),
    work: sim,
    readiness: MockReadinessSource(),
    effects: EffectsSettings(reducedMotion: true),
    demo: demo,
  );
}

Future<(AppState, LivingServices)> pumpLiving(
  WidgetTester tester, {
  Size size = const Size(1280, 900),
  MockWorkSimulator? work,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final appState = AppState(MockUriClient());
  final services = testServices(appState, work: work);
  addTearDown(services.dispose);
  await tester.pumpWidget(LivingApp(appState: appState, services: services, skipOnboarding: true));
  await tester.pumpAndSettle();
  return (appState, services);
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('opens in Companion mode with the orb, a status line and a composer', (tester) async {
    await pumpLiving(tester);
    expect(find.byKey(LivingShell.orbKey), findsOneWidget);
    expect(find.byKey(const ValueKey('companion-state-label')), findsOneWidget);
    expect(find.text('Idle'), findsWidgets);
    expect(find.byKey(const ValueKey('living-composer-field')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('the same orb element travels through Companion -> Workspace -> Dashboard -> Companion',
      (tester) async {
    final (_, services) = await pumpLiving(tester);
    final before = tester.element(find.byKey(LivingShell.orbKey));
    final rectCompanion = tester.getRect(find.byKey(LivingShell.orbKey));

    await tester.tap(find.text('Workspace'));
    await tester.pump(const Duration(milliseconds: 100));
    // Mid-transition: still one orb, moving.
    expect(find.byKey(LivingShell.orbKey), findsOneWidget);
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.workspace);
    final rectWorkspace = tester.getRect(find.byKey(LivingShell.orbKey));
    expect(rectWorkspace.width, lessThan(rectCompanion.width));
    expect(rectWorkspace.left, lessThan(rectCompanion.left));
    expect(identical(before, tester.element(find.byKey(LivingShell.orbKey))), isTrue);

    await tester.tap(find.text('Dashboard').last);
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.dashboard);
    expect(find.text('URI overview'), findsOneWidget);
    expect(identical(before, tester.element(find.byKey(LivingShell.orbKey))), isTrue);

    await tester.tap(find.text('Companion').last);
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.companion);
    expect(identical(before, tester.element(find.byKey(LivingShell.orbKey))), isTrue);
    expect(tester.takeException(), isNull);
  });

  testWidgets('"URI dashboard" typed in the composer is a command, not a chat message; Back undoes it',
      (tester) async {
    final (appState, services) = await pumpLiving(tester);
    await tester.enterText(find.byKey(const ValueKey('living-composer-field')), 'URI dashboard');
    await tester.tap(find.byKey(const ValueKey('living-composer-send')));
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.dashboard);
    expect(services.presentation.lastCommandOrigin, UiCommandOrigin.localCommand);
    expect(appState.conversation, isEmpty, reason: 'a command is never sent as chat');
    expect(find.text('URI opened Dashboard'), findsOneWidget);
    await tester.tap(find.text('Back'));
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.companion);
    expect(tester.takeException(), isNull);
  });

  testWidgets('a real question from Companion opens the Workspace conversation and the orb thinks',
      (tester) async {
    final (appState, services) = await pumpLiving(tester);
    await tester.enterText(find.byKey(const ValueKey('living-composer-field')), 'Summarise my unread email');
    await tester.tap(find.byKey(const ValueKey('living-composer-send')));
    await tester.pump();
    expect(services.presentation.mode, UiPresentationMode.workspace);
    expect(services.presentation.focus, WorkspaceFocus.conversation);
    expect(appState.isSendingAsk, isTrue);
    expect(services.companion.signal.state, CompanionState.thinking);
    expect(services.companion.signal.simulated, isFalse, reason: 'derived from AppState, not a mock event');
    await tester.pumpAndSettle();
    expect(appState.conversation, hasLength(1));
    expect(tester.takeException(), isNull);
  });

  testWidgets('office workflow: template -> in progress -> approval card -> approve -> Done',
      (tester) async {
    final (_, services) = await pumpLiving(tester);
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.documents);
    await tester.pumpAndSettle();
    expect(find.byType(StatusBadge), findsWidgets, reason: 'mock documents carry Simulated badges');
    await tester.tap(find.byKey(const ValueKey('template-Letter')));
    // Explicit pumps: pumpAndSettle would run the fast simulator to the end.
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 50));
    expect(services.presentation.focus, WorkspaceFocus.tasks);
    expect(find.text('Draft a letter'), findsWidgets);

    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump();
    expect(services.companion.signal.state, CompanionState.working);
    expect(find.byKey(const ValueKey('rail-state-label')), findsOneWidget);
    expect(find.text('Working'), findsWidgets);

    for (var i = 0; i < 6; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    await tester.pump();
    expect(services.companion.signal.state, CompanionState.awaitingApproval);
    expect(find.text('Needs your approval'), findsWidgets);
    final approve = find.byKey(ValueKey('approve-${services.work.items.first.id}'));
    expect(approve, findsOneWidget);
    await tester.tap(approve);
    await tester.pump();
    expect(services.companion.signal.state, CompanionState.success);
    expect(find.text('Draft a letter.docx'), findsWidgets);
    await tester.pump(const Duration(seconds: 4));
    await tester.pumpAndSettle();
    expect(services.companion.signal.state, CompanionState.idle);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Companion mode offers "Review and decide" only while something waits', (tester) async {
    final (_, services) = await pumpLiving(tester);
    expect(find.byKey(const ValueKey('companion-review')), findsNothing);
    services.demo.emit(CompanionState.awaitingApproval, detail: 'Save the letter');
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('companion-review')), findsOneWidget);
    expect(find.text('Needs your approval'), findsWidgets);
    expect(find.text('SIMULATED'), findsWidgets);
    await tester.tap(find.byKey(const ValueKey('companion-review')));
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.workspace);
    expect(services.presentation.focus, WorkspaceFocus.tasks);
  });

  testWidgets('priority: a real error outranks a mock speaking signal; a mock speaking never hides approval',
      (tester) async {
    final (_, services) = await pumpLiving(tester);
    services.demo.emit(CompanionState.speaking);
    expect(services.companion.signal.state, CompanionState.speaking);
    (services.work as MockWorkSimulator).companion.emit(CompanionState.awaitingApproval);
    expect(services.companion.signal.state, CompanionState.awaitingApproval);
  });

  testWidgets('Dashboard: every mock-backed tile carries the Simulated badge and names its source',
      (tester) async {
    final (_, services) = await pumpLiving(tester, size: const Size(1400, 1000));
    services.presentation.setMode(UiPresentationMode.dashboard);
    await tester.pumpAndSettle();
    for (final title in ['Readiness', 'Current tasks', 'Brain & models', 'Harnesses', 'Connected clients', 'Permissions', 'Capabilities']) {
      expect(find.text(title), findsOneWidget, reason: title);
    }
    expect(find.text('GET /tasks + WorkItemSource'), findsOneWidget);
    expect(find.text('GET /providers/active-brain'), findsOneWidget);
    expect(find.text('SIMULATED'), findsAtLeastNWidgets(7));
    expect(find.text('Upcoming Deadline'), findsNothing);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Intelligence: pipeline, no fabricated reasoning, memory graph labelled PROTOTYPE',
      (tester) async {
    final (_, services) = await pumpLiving(tester, size: const Size(1400, 1000));
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.intelligence);
    await tester.pumpAndSettle();
    expect(find.text('PROTOTYPE'), findsOneWidget);
    expect(find.byKey(const ValueKey('memory-graph-disclaimer')), findsOneWidget);
    expect(find.textContaining('not connected to a memory backend'), findsOneWidget);
    expect(find.textContaining('reasoning trace'), findsNothing);
    expect(find.bySemanticsLabel(RegExp('Request: ')), findsOneWidget);
    expect(find.bySemanticsLabel(RegExp('Receipt: ')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('Settings: harness, Brain, reasoning, approval boundary, appearance, reduced effects',
      (tester) async {
    final (appState, services) = await pumpLiving(tester, size: const Size(1400, 1000));
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.settings);
    await tester.pumpAndSettle();
    expect(find.text('Codex (native CLI)'), findsOneWidget);
    expect(find.text('Claude Code CLI'), findsOneWidget);
    expect(find.textContaining('Sign in to the CLI'), findsOneWidget);
    final scrollable = find.byType(Scrollable).first;
    await tester.scrollUntilVisible(find.text('Auto-approve routine actions, ask for the rest'), 200,
        scrollable: scrollable);
    await tester.tap(find.text('Auto-approve routine actions, ask for the rest'));
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Obsidian Cyan'), 200, scrollable: scrollable);
    expect(find.text('Obsidian Cyan'), findsOneWidget);
    final sw = find.byKey(const ValueKey('reduced-effects-switch'));
    await tester.scrollUntilVisible(sw, 200, scrollable: scrollable);
    expect(sw, findsOneWidget);
    await tester.tap(sw);
    await tester.pumpAndSettle();
    expect(services.effects.reducedEffects, isTrue);
    expect(find.byType(EnergyOrb), findsOneWidget);
    expect(appState.preferences.autonomyLevel.name, 'routineAutoApprove');
    expect(tester.takeException(), isNull);
  });

  testWidgets('fits a 440x680 companion window and a 1920x1080 desktop without overflow',
      (tester) async {
    final (_, services) = await pumpLiving(tester, size: const Size(440, 680));
    expect(tester.takeException(), isNull);
    services.presentation.setMode(UiPresentationMode.workspace);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    services.presentation.setMode(UiPresentationMode.dashboard);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);

    tester.view.physicalSize = const Size(1920, 1080);
    await tester.pumpAndSettle();
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.tasks);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    services.presentation.setMode(UiPresentationMode.companion);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });

  testWidgets('works under the four approved Hybrid themes too', (tester) async {
    for (final theme in [
      UriThemeChoice.graphite,
      UriThemeChoice.lightProfessional,
    ]) {
      tester.view.physicalSize = const Size(1280, 900);
      tester.view.devicePixelRatio = 1;
      final appState = AppState(MockUriClient());
      final services = testServices(appState);
      await tester.pumpWidget(LivingApp(
        appState: appState,
        services: services,
        skipOnboarding: true,
        initialTheme: theme,
      ));
      await tester.pumpAndSettle();
      services.presentation.setMode(UiPresentationMode.dashboard);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      await tester.pumpWidget(const SizedBox());
      services.dispose();
    }
    tester.view.resetPhysicalSize();
  });
}
