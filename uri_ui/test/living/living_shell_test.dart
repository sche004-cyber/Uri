import 'dart:io';

import 'package:flutter/gestures.dart' show PointerDeviceKind;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/companion/companion_orb.dart' show CompanionOrb;
import 'package:uri_ui/living/companion/companion_preferences.dart';
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
import 'package:uri_ui/living/widgets/glass_panel.dart';
import 'package:uri_ui/living/widgets/status_badge.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/theme/uri_theme.dart';

/// Test wiring: identical to [LivingApp.buildDefaultServices] except the
/// orb's continuous ticker is off (reduced motion) so `pumpAndSettle`
/// terminates, and the simulator steps fast.
LivingServices testServices(AppState appState, {MockWorkSimulator? work}) {
  final demo = MockCompanionSource();
  final sim =
      work ??
      MockWorkSimulator(stepInterval: const Duration(milliseconds: 100));
  return LivingServices(
    presentation: UiPresentationController(commandCooldown: Duration.zero),
    companion: CompositeCompanionSource([
      AppStateCompanionSource(appState, dataIsMock: true),
      sim.companion,
      demo,
    ]),
    work: sim,
    readiness: MockReadinessSource(),
    effects: EffectsSettings(reducedMotion: true),
    demo: demo,
  );
}

/// The classic orb inside the shell's companion slot.
Finder shellEnergyOrb() => find.descendant(
  of: find.byKey(LivingShell.orbKey),
  matching: find.byType(EnergyOrb),
);

/// The preview's AppState: mock client + namespaced preference store,
/// exactly as `main_living.dart` builds it.
AppState testAppState() =>
    AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());

Future<(AppState, LivingServices)> pumpLiving(
  WidgetTester tester, {
  Size size = const Size(1280, 900),
  MockWorkSimulator? work,
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final appState = testAppState();
  final services = testServices(appState, work: work);
  addTearDown(services.dispose);
  await tester.pumpWidget(
    LivingApp(appState: appState, services: services, skipOnboarding: true),
  );
  await tester.pumpAndSettle();
  return (appState, services);
}

void main() {
  test('Workspace orb is the centred heart of the rail', () {
    // Owner request 2026-10-10: the rail orb centred and prominent, not a
    // corner logo. Expanded rail (>= 1100 px wide) and collapsed rail.
    final wide = OrbDock.forMode(
      UiPresentationMode.workspace,
      const Size(1400, 900),
    ).rect;
    expect(wide.width, 132);
    expect(wide.center.dx, OrbDock.railWidth(1400) / 2);
    expect(wide.bottom + 12, OrbDock.railOrbSpace(1400));
    final narrow = OrbDock.forMode(
      UiPresentationMode.workspace,
      const Size(900, 700),
    ).rect;
    expect(narrow.width, 64);
    expect(narrow.center.dx, OrbDock.railWidth(900) / 2);
    expect(narrow.left, greaterThanOrEqualTo(0));
  });

  testWidgets('at the rail threshold the orb stays centred in the rail while both animate', (tester) async {
    // Codex review (2026-10-10): the rail, its reserved orb space and the orb must move together.
    final src = File('lib/living/screens/workspace_mode_view.dart').readAsStringSync();
    final rail = src.substring(src.indexOf('class _Rail extends'));
    expect(RegExp(r'AnimatedContainer\(\s*duration: UriMotion\.mode,\s*// Same curve[^)]*?curve: UriMotion\.move', dotAll: true)
        .hasMatch(rail), isTrue);
    expect(RegExp(r'AnimatedContainer\(\s*duration: UriMotion\.mode,\s*curve: UriMotion\.move,\s*height: orbSpace')
        .hasMatch(rail), isTrue);
    // Lerped with the same curve value t, the orb's left edge stays (railWidth(t) - size(t)) / 2.
    for (final t in [0.0, 0.25, 0.5, 0.75, 1.0]) {
      double lerp(double a, double b) => a + (b - a) * t;
      final w = lerp(OrbDock.railWidth(1099), OrbDock.railWidth(1100));
      final size = lerp(OrbDock.railOrbSize(1099), OrbDock.railOrbSize(1100));
      final left = lerp(
        OrbDock.forMode(UiPresentationMode.workspace, const Size(1099, 800)).rect.left,
        OrbDock.forMode(UiPresentationMode.workspace, const Size(1100, 800)).rect.left,
      );
      expect(left, closeTo((w - size) / 2, 1e-9));
      final space = lerp(OrbDock.railOrbSpace(1099), OrbDock.railOrbSpace(1100));
      expect(space, closeTo(OrbDock.railOrbTop + size + 12, 1e-9));
    }
  });

  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets(
    'opens in Companion mode with the orb, a status line and a composer',
    (tester) async {
      await pumpLiving(tester);
      expect(find.byKey(LivingShell.orbKey), findsOneWidget);
      expect(
        find.byKey(const ValueKey('companion-state-label')),
        findsOneWidget,
      );
      expect(find.text('Idle'), findsWidgets);
      expect(
        find.byKey(const ValueKey('living-composer-field')),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'A2: the same orb element travels through Companion -> Workspace -> Dashboard -> Companion',
    (tester) async {
      final (_, services) = await pumpLiving(tester);
      final before = tester.element(find.byKey(LivingShell.orbKey));
      final rectCompanion = tester.getRect(find.byKey(LivingShell.orbKey));

      await tester.tap(find.text('Workspace'));
      await tester.pump(const Duration(milliseconds: 100));
      expect(find.byKey(LivingShell.orbKey), findsOneWidget);
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.workspace);
      final rectWorkspace = tester.getRect(find.byKey(LivingShell.orbKey));
      expect(rectWorkspace.width, lessThan(rectCompanion.width));
      expect(rectWorkspace.left, lessThan(rectCompanion.left));
      expect(
        identical(before, tester.element(find.byKey(LivingShell.orbKey))),
        isTrue,
      );

      await tester.tap(find.text('Dashboard').last);
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.dashboard);
      expect(find.text('URI overview'), findsOneWidget);
      expect(
        identical(before, tester.element(find.byKey(LivingShell.orbKey))),
        isTrue,
      );

      await tester.tap(find.text('Companion').last);
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.companion);
      expect(
        identical(before, tester.element(find.byKey(LivingShell.orbKey))),
        isTrue,
      );
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'A3: "URI dashboard" typed in the composer is a command, not a chat message; Back undoes it',
    (tester) async {
      final (appState, services) = await pumpLiving(tester);
      await tester.enterText(
        find.byKey(const ValueKey('living-composer-field')),
        'URI dashboard',
      );
      await tester.tap(find.byKey(const ValueKey('living-composer-send')));
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.dashboard);
      expect(
        services.presentation.lastCommandOrigin,
        UiCommandOrigin.localCommand,
      );
      expect(
        appState.conversation,
        isEmpty,
        reason: 'a command is never sent as chat',
      );
      expect(find.text('URI opened Dashboard'), findsOneWidget);
      await tester.tap(find.text('Back'));
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.companion);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'a real question from Companion opens the Workspace conversation and the orb thinks (flagged simulated under the mock client)',
    (tester) async {
      final (appState, services) = await pumpLiving(tester);
      await tester.enterText(
        find.byKey(const ValueKey('living-composer-field')),
        'Summarise my unread email',
      );
      await tester.tap(find.byKey(const ValueKey('living-composer-send')));
      await tester.pump();
      expect(services.presentation.mode, UiPresentationMode.workspace);
      expect(services.presentation.focus, WorkspaceFocus.conversation);
      expect(appState.isSendingAsk, isTrue);
      expect(services.companion.signal.state, CompanionState.thinking);
      expect(services.companion.signal.sourceName, 'AppState.isSendingAsk');
      expect(
        services.companion.signal.simulated,
        isTrue,
        reason: 'the mock client answers, so the badge must show',
      );
      await tester.pumpAndSettle();
      expect(appState.conversation, hasLength(1));
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'R5-3: in Office the global context panel starts closed, so the Office URI pane has room (real-app run 2026-10-15)',
    (tester) async {
      final (_, services) = await pumpLiving(tester, size: const Size(1280, 800));
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.tasks);
      await tester.pumpAndSettle();
      expect(find.text('EXECUTOR'), findsOneWidget, reason: 'other regions keep the context panel at this width');
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.office);
      await tester.pumpAndSettle();
      expect(find.text('EXECUTOR'), findsNothing);
    },
  );

  testWidgets(
    'A4: office workflow: template -> in progress -> approval card -> approve -> Done',
    (tester) async {
      // O2 (plan §1.2, review F2): the simulated Documents region and its template tiles are retired; Documents is
      // now Office › Documents. The simulated work flow this test covers (companion states, approval card) is
      // started directly on the work simulator, which is what the retired "Letter" tile did.
      final (_, services) = await pumpLiving(tester);
      services.presentation.setMode(
        UiPresentationMode.workspace,
        focus: WorkspaceFocus.tasks,
      );
      await tester.pumpAndSettle();
      expect(find.byType(StatusBadge), findsWidgets);
      services.work.create(title: 'Draft a letter', kind: WorkItemKind.letter);
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
      final approve = find.byKey(
        ValueKey('approve-${services.work.items.first.id}'),
      );
      expect(approve, findsOneWidget);
      await tester.tap(approve);
      await tester.pump();
      expect(services.companion.signal.state, CompanionState.success);
      expect(find.text('Draft a letter.docx'), findsWidgets);
      await tester.pump(const Duration(seconds: 4));
      await tester.pumpAndSettle();
      expect(services.companion.signal.state, CompanionState.idle);
      expect(find.text('SIMULATED'), findsWidgets);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('A4: every Workspace region renders its own content', (
    tester,
  ) async {
    final (_, services) = await pumpLiving(
      tester,
      size: const Size(1400, 1000),
    );
    services.presentation.setMode(UiPresentationMode.workspace);
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('living-composer-field')), findsOneWidget);
    expect(find.text('CONTEXT & FILES'), findsOneWidget);
    for (final (focus, texts) in [
      (WorkspaceFocus.tasks, ['NEEDS YOUR DECISION', 'IN PROGRESS', 'HISTORY']),
      (
        WorkspaceFocus.intelligence,
        ['REQUEST PIPELINE', 'MEMORY GRAPH', 'SIGNAL SOURCES'],
      ),
      (
        WorkspaceFocus.settings,
        [
          'HARNESS',
          'BRAIN / PROVIDER',
          'REASONING MODE',
          'APPROVAL BOUNDARY',
          'PERMISSIONS',
          // The orb controls moved into Companion Settings (the default
          // companion is a living identity, Solar).
          'COMPANION',
          'PERFORMANCE',
          'VOICE AND AUDIO',
        ],
      ),
    ]) {
      services.presentation.setFocus(focus);
      await tester.pumpAndSettle();
      for (final t in texts) {
        // Regions are lazy lists; bring each eyebrow into view first.
        await tester.scrollUntilVisible(
          find.text(t),
          200,
          scrollable: find.byType(Scrollable).first,
        );
        expect(find.text(t), findsOneWidget, reason: '${focus.name}: $t');
      }
    }
    // Reconciliation with UI V2 (2026-10-16): Documents keeps its 'Start new work' tiles (real turns in the integrated
    // V2, BLK-INT-2); Office is its own region. With no Office service in this test it says so.
    services.presentation.setFocus(WorkspaceFocus.documents);
    await tester.pumpAndSettle();
    expect(find.text('START NEW WORK'), findsOneWidget);
    services.presentation.setFocus(WorkspaceFocus.office);
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-start-error')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets(
    'Companion mode offers "Review and decide" only while something waits',
    (tester) async {
      final (_, services) = await pumpLiving(tester);
      expect(find.byKey(const ValueKey('companion-review')), findsNothing);
      services.demo.emit(
        CompanionState.awaitingApproval,
        detail: 'Save the letter',
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('companion-review')), findsOneWidget);
      expect(find.text('Needs your approval'), findsWidgets);
      expect(find.text('SIMULATED'), findsWidgets);
      await tester.tap(find.byKey(const ValueKey('companion-review')));
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.workspace);
      expect(services.presentation.focus, WorkspaceFocus.tasks);
    },
  );

  testWidgets(
    'priority: a mock speaking never hides approval; error outranks both',
    (tester) async {
      final (_, services) = await pumpLiving(tester);
      services.demo.emit(CompanionState.speaking);
      expect(services.companion.signal.state, CompanionState.speaking);
      (services.work as MockWorkSimulator).companion.emit(
        CompanionState.awaitingApproval,
      );
      expect(services.companion.signal.state, CompanionState.awaitingApproval);
      services.demo.emit(CompanionState.error);
      expect(services.companion.signal.state, CompanionState.error);
    },
  );

  testWidgets(
    'A5: Dashboard: each mock-backed tile carries its own Simulated badge and names its source',
    (tester) async {
      final (_, services) = await pumpLiving(
        tester,
        size: const Size(1400, 1000),
      );
      services.presentation.setMode(UiPresentationMode.dashboard);
      await tester.pumpAndSettle();
      for (final title in [
        'Readiness',
        'Current tasks',
        'Brain & models',
        'Harnesses',
        'Connected clients',
        'Permissions',
        'Capabilities',
        'Selected harness',
      ]) {
        final tile = find.ancestor(
          of: find.text(title),
          matching: find.byType(GlassPanel),
        );
        expect(tile, findsOneWidget, reason: title);
        expect(
          find.descendant(of: tile, matching: find.text('SIMULATED')),
          findsWidgets,
          reason: '$title has no Simulated badge',
        );
      }
      expect(find.text('GET /tasks + WorkItemSource'), findsOneWidget);
      expect(find.text('GET /providers/active-brain'), findsOneWidget);
      expect(find.text('Upcoming Deadline'), findsNothing);
      expect(find.text('Halted Workflows'), findsNothing);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'A7: Intelligence: idle pipeline claims nothing; memory graph labelled PROTOTYPE; routing not inferred',
    (tester) async {
      final (_, services) = await pumpLiving(
        tester,
        size: const Size(1400, 1000),
        work: MockWorkSimulator(seed: false), // nothing has happened yet
      );
      services.presentation.setMode(
        UiPresentationMode.workspace,
        focus: WorkspaceFocus.intelligence,
      );
      await tester.pumpAndSettle();
      expect(find.text('PROTOTYPE'), findsOneWidget);
      expect(
        find.byKey(const ValueKey('memory-graph-disclaimer')),
        findsOneWidget,
      );
      expect(
        find.textContaining('not connected to a memory backend'),
        findsOneWidget,
      );
      expect(find.textContaining('reasoning trace'), findsNothing);
      expect(
        find.textContaining('Not reported by this client'),
        findsOneWidget,
      );
      for (final stage in [
        'Request',
        'Intent',
        'Route (Edge / Core)',
        'Harness',
        'Model',
        'Approval',
        'Execution',
        'Receipt',
      ]) {
        expect(
          find.bySemanticsLabel(RegExp('^${RegExp.escape(stage)}: idle')),
          findsOneWidget,
          reason: stage,
        );
      }
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'Settings: harness, Brain, reasoning, approval boundary, orb style, appearance, reduced effects',
    (tester) async {
      final (appState, services) = await pumpLiving(
        tester,
        size: const Size(1400, 1000),
      );
      // The orb style, palette and free theme controls belong to the classic
      // orb, which stays available as a companion choice.
      services.companionPrefs.select(const CompanionChoice.classic());
      services.presentation.setMode(
        UiPresentationMode.workspace,
        focus: WorkspaceFocus.settings,
      );
      await tester.pumpAndSettle();
      expect(find.text('Codex (native CLI)'), findsOneWidget);
      expect(find.text('Claude Code CLI'), findsOneWidget);
      expect(find.textContaining('Sign in to the CLI'), findsOneWidget);
      final scrollable = find.byType(Scrollable).first;
      await tester.scrollUntilVisible(
        find.text('Auto-approve routine actions, ask for the rest'),
        200,
        scrollable: scrollable,
      );
      await tester.tap(
        find.text('Auto-approve routine actions, ask for the rest'),
      );
      await tester.pumpAndSettle();
      expect(appState.preferences.autonomyLevel.name, 'routineAutoApprove');
      await tester.scrollUntilVisible(
        find.byKey(const ValueKey('orb-variant-mesh')),
        200,
        scrollable: scrollable,
      );
      await tester.tap(find.byKey(const ValueKey('orb-variant-mesh')));
      await tester.pumpAndSettle();
      expect(services.orbVariant.value, OrbVariant.mesh);
      expect(
        tester.widget<EnergyOrb>(shellEnergyOrb()).variant,
        OrbVariant.mesh,
      );
      await tester.scrollUntilVisible(
        find.byKey(const ValueKey('orb-palette-sunset')),
        200,
        scrollable: scrollable,
      );
      await tester.tap(find.byKey(const ValueKey('orb-palette-sunset')));
      await tester.pumpAndSettle();
      expect(services.orbPalette.value, OrbPalette.sunset);
      expect(
        tester.widget<EnergyOrb>(shellEnergyOrb()).palette,
        OrbPalette.sunset,
      );
      await tester.scrollUntilVisible(
        find.text('Obsidian Cyan'),
        200,
        scrollable: scrollable,
      );
      expect(find.text('Obsidian Cyan'), findsOneWidget);
      final sw = find.byKey(const ValueKey('reduced-effects-switch'));
      await tester.scrollUntilVisible(sw, 200, scrollable: scrollable);
      await tester.tap(sw);
      await tester.pumpAndSettle();
      expect(services.effects.reducedEffects, isTrue);
      expect(shellEnergyOrb(), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'A9: reduced effects removes every BackdropFilter and the shader path',
    (tester) async {
      final (_, services) = await pumpLiving(tester);
      expect(find.byType(BackdropFilter), findsOneWidget);
      services.effects.setReducedEffects(true);
      await tester.pumpAndSettle();
      expect(find.byType(BackdropFilter), findsNothing);
      // Reduced effects draws the companion with the effect-free classic
      // orb: no living shader is mounted and the classic one is off too.
      expect(find.byType(CompanionOrb), findsNothing);
      final orbState = tester.state(shellEnergyOrb()) as dynamic;
      expect(orbState.usesShader, isFalse);
      services.effects.setReducedEffects(false);
      services.presentation.setMode(UiPresentationMode.dashboard);
      await tester.pumpAndSettle();
      expect(find.byType(BackdropFilter), findsNothing);
    },
  );

  testWidgets(
    'click: the orb pokes, asks a question and hands focus to the composer',
    (tester) async {
      final (_, services) = await pumpLiving(tester);
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds: 400));
      expect(services.orbPokes.value, 1);
      expect(
        services.presentation.mode,
        UiPresentationMode.companion,
        reason: 'single click does not change mode',
      );
      expect(find.text("I'm here. What's next?"), findsOneWidget);
      expect(services.composerFocus.hasFocus, isTrue);
      await tester.pump(const Duration(seconds: 5));
      await tester.pumpAndSettle();
      final bubble = tester.widget<AnimatedOpacity>(
        find
            .ancestor(
              of: find.byKey(const ValueKey('orb-question-bubble')),
              matching: find.byType(AnimatedOpacity),
            )
            .first,
      );
      expect(bubble.opacity, 0);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('double-click opens the Workspace', (tester) async {
    final (_, services) = await pumpLiving(tester);
    final orb = find.byKey(LivingShell.orbKey);
    await tester.tap(orb);
    await tester.pump(const Duration(milliseconds: 80));
    await tester.tap(orb);
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.workspace);
  });

  testWidgets(
    'cursor gusts over the orb never throw (all variants, animating)',
    (tester) async {
      tester.view.physicalSize = const Size(600, 600);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      for (final v in OrbVariant.values) {
        await tester.pumpWidget(
          EffectsSettingsScope(
            settings: EffectsSettings(),
            child: MaterialApp(
              theme: buildUriTheme(UriColors.obsidianCyan),
              home: Scaffold(
                body: Center(
                  child: EnergyOrb(
                    state: CompanionState.idle,
                    size: 300,
                    variant: v,
                  ),
                ),
              ),
            ),
          ),
        );
        await tester.pump(const Duration(milliseconds: 50));
        final gesture = await tester.createGesture(
          kind: PointerDeviceKind.mouse,
        );
        await gesture.addPointer(location: const Offset(150, 300));
        for (var i = 0; i < 12; i++) {
          await gesture.moveTo(Offset(150.0 + i * 30, 300.0 + i * 4));
          await tester.pump(const Duration(milliseconds: 16));
        }
        for (var i = 0; i < 10; i++) {
          await tester.pump(const Duration(milliseconds: 100));
        }
        await gesture.removePointer();
        expect(tester.takeException(), isNull, reason: v.name);
      }
      await tester.pumpWidget(const SizedBox());
    },
  );

  testWidgets(
    'keyboard: Ctrl+2 opens Workspace, Ctrl+3 Dashboard, Esc returns to Companion',
    (tester) async {
      final (_, services) = await pumpLiving(tester);
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.digit2);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.workspace);
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.digit3);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.dashboard);
      await tester.sendKeyEvent(LogicalKeyboardKey.escape);
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.companion);
    },
  );

  testWidgets(
    'A11/isolation: the preview never writes a Hybrid preference key',
    (tester) async {
      final (appState, _) = await pumpLiving(tester);
      await appState.updatePreferences(
        appState.preferences.copyWith(
          focusAreas: ['Research'],
          completedOnboarding: true,
        ),
      );
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getBool('uri.completedOnboarding'), isNull);
      expect(prefs.getStringList('uri.focusAreas'), isNull);
      expect(prefs.getString('uri.autonomyLevel'), isNull);
      expect(prefs.getString('uri.themeChoice'), isNull);
      expect(
        prefs.getBool(LivingPreferencesStore.keyCompletedOnboarding),
        isTrue,
      );
      expect(prefs.getStringList(LivingPreferencesStore.keyFocusAreas), [
        'Research',
      ]);
      for (final k in prefs.getKeys()) {
        expect(k, startsWith('uri.living.'), reason: k);
      }
    },
  );

  testWidgets(
    'A8: the default wiring (as main_living.dart builds it) runs offline on the mock client',
    (tester) async {
      tester.view.physicalSize = const Size(1280, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final appState = testAppState();
      final services = LivingApp.buildDefaultServices(appState)
        ..effects.setReducedMotion(true);
      addTearDown(services.dispose);
      await tester.pumpWidget(
        LivingApp(appState: appState, services: services, skipOnboarding: true),
      );
      await tester.pumpAndSettle();
      expect(services.appDataIsMock, isTrue);
      expect(find.byKey(LivingShell.orbKey), findsOneWidget);
      await tester.enterText(
        find.byKey(const ValueKey('living-composer-field')),
        'hello',
      );
      await tester.tap(find.byKey(const ValueKey('living-composer-send')));
      await tester.pumpAndSettle();
      expect(appState.conversation, hasLength(1));
      expect(appState.lastConnectionErrorDetail, isNull);
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets(
    'fits a 440x680 companion window and a 1920x1080 desktop without overflow',
    (tester) async {
      final (_, services) = await pumpLiving(
        tester,
        size: const Size(440, 680),
      );
      expect(tester.takeException(), isNull);
      services.presentation.setMode(UiPresentationMode.workspace);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      services.presentation.setMode(UiPresentationMode.dashboard);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);

      tester.view.physicalSize = const Size(1920, 1080);
      await tester.pumpAndSettle();
      services.presentation.setMode(
        UiPresentationMode.workspace,
        focus: WorkspaceFocus.tasks,
      );
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      services.presentation.setMode(UiPresentationMode.companion);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
    },
  );

  testWidgets('works under the approved Hybrid themes too', (tester) async {
    for (final theme in [
      UriThemeChoice.graphite,
      UriThemeChoice.lightProfessional,
    ]) {
      tester.view.physicalSize = const Size(1280, 900);
      tester.view.devicePixelRatio = 1;
      final appState = testAppState();
      final services = testServices(appState);
      await tester.pumpWidget(
        LivingApp(
          appState: appState,
          services: services,
          skipOnboarding: true,
          initialTheme: theme,
        ),
      );
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
