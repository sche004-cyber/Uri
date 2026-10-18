/// UI-NOTIFY-1 (real-app runs r7 and r1b, 2026-10-15): the Office workspace changed the living scope's Office target
/// from didChangeDependencies (during build) and from dispose (tree locked). A widget listening to the target (as the
/// companion composer does) was then marked dirty at a forbidden time and Flutter raised assertions.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/contracts/readiness_report.dart';
import 'package:uri_ui/living/contracts/work_items.dart';
import 'package:uri_ui/living/living_app.dart' show LivingPreferencesStore;
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_workspace.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/app_state_scope.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/theme/uri_theme.dart';

import 'office_workspace_test.dart' show FakeOffice;

LivingServices _services() {
  final demo = MockCompanionSource();
  final work = MockWorkSimulator(stepInterval: const Duration(milliseconds: 100));
  return LivingServices(
    presentation: UiPresentationController(commandCooldown: Duration.zero),
    companion: CompositeCompanionSource([work.companion, demo]),
    work: work,
    readiness: MockReadinessSource(),
    effects: EffectsSettings(reducedMotion: true),
    demo: demo,
  );
}

OfficeEnvironment _env() => OfficeEnvironment(
      surfaceFactory: () => throw UnimplementedError(),
      pickWorkbookPath: () async => null,
      pickSavePath: (_) async => null,
      openExternalLink: (_) async {},
    );

void main() {
  testWidgets('entering and leaving Office changes the target without framework assertions', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.binding.setSurfaceSize(const Size(1440, 900));
    final services = _services();
    final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client());
    final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
    var showOffice = true;
    var showSecond = false;
    late StateSetter set;
    await tester.pumpWidget(MaterialApp(
      theme: ThemeData(extensions: const [UriColors.graphite]),
      home: AppStateScope(
        state: appState,
        child: LivingScope(
        services: services,
        child: Scaffold(
          body: StatefulBuilder(builder: (context, setState) {
            set = setState;
            return Column(children: [
              // A listener of the target, as the companion composer is in the app.
              ListenableBuilder(
                listenable: services.officeTarget,
                builder: (_, _) => Text(services.officeTarget.value == null ? 'target: none' : 'target: office'),
              ),
              Expanded(
                child: Row(children: [
                  if (showOffice)
                    Expanded(child: OfficeWorkspace(key: const ValueKey('first'), environment: _env(),
                        clientFactory: () => client)),
                  if (showSecond)
                    Expanded(child: OfficeWorkspace(key: const ValueKey('second'), environment: _env(),
                        clientFactory: () => client)),
                ]),
              ),
            ]);
          }),
        ),
      ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('target: office'), findsOneWidget);

    set(() => showOffice = false);          // leave Office: the workspace is disposed
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('target: none'), findsOneWidget);

    set(() => showOffice = true);           // come back: a new workspace claims the target again
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('target: office'), findsOneWidget);

    // Codex review R1-2: two workspaces share the scope's controller; closing one keeps the target.
    set(() => showSecond = true);
    await tester.pumpAndSettle();
    set(() => showOffice = false);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('target: office'), findsOneWidget);
    set(() => showSecond = false);
    await tester.pumpAndSettle();
    expect(find.text('target: none'), findsOneWidget);
    // The controller keeps polling while Office is shown; end the tree and let its timers run out.
    set(() => showOffice = false);
    await tester.pumpAndSettle();
    await tester.pumpWidget(const SizedBox());
    services.dispose();
    await tester.pump(const Duration(seconds: 10));
  });

  testWidgets('Codex R2-2: a workspace that moves to another scope clears the old target and claims the new one',
      (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.binding.setSurfaceSize(const Size(1440, 900));
    final a = _services(), b = _services();
    final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client());
    final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
    var useB = false;
    late StateSetter set;
    final workspace = GlobalKey();
    await tester.pumpWidget(MaterialApp(
      theme: ThemeData(extensions: const [UriColors.graphite]),
      home: AppStateScope(
        state: appState,
        child: StatefulBuilder(builder: (context, setState) {
          set = setState;
          return LivingScope(
            services: useB ? b : a,
            child: Scaffold(
              body: Column(children: [
                ListenableBuilder(listenable: a.officeTarget,
                    builder: (_, _) => Text('a: ${a.officeTarget.value == null ? 'none' : 'office'}')),
                ListenableBuilder(listenable: b.officeTarget,
                    builder: (_, _) => Text('b: ${b.officeTarget.value == null ? 'none' : 'office'}')),
                Expanded(child: OfficeWorkspace(key: workspace, environment: _env(), clientFactory: () => client)),
              ]),
            ),
          );
        }),
      ),
    ));
    await tester.pumpAndSettle();
    expect(find.text('a: office'), findsOneWidget);
    expect(find.text('b: none'), findsOneWidget);
    set(() => useB = true);                  // same workspace element, new scope
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.text('a: none'), findsOneWidget);
    expect(find.text('b: office'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    a.dispose();
    b.dispose();
    await tester.pump(const Duration(seconds: 10));
  });

  // Smoke test only: this ordering does not reproduce the live run a7 assertion (it passes without the fix too);
  // the fix is evidenced by the live log and qualified by the next live run.
  testWidgets('live run a7: closing the app with Office open does not touch a disposed target', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.binding.setSurfaceSize(const Size(1440, 900));
    final services = _services();
    final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client());
    final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
    await tester.pumpWidget(MaterialApp(
      theme: ThemeData(extensions: const [UriColors.graphite]),
      home: AppStateScope(
        state: appState,
        child: LivingScope(
          services: services,
          child: Scaffold(body: OfficeWorkspace(environment: _env(), clientFactory: () => client)),
        ),
      ),
    ));
    await tester.pumpAndSettle();
    expect(services.officeTarget.value, isNotNull);
    // The app closes: the tree goes (the workspace's release is deferred to the end of the frame) and the living
    // scope's services are disposed before that frame ends.
    await tester.pumpWidget(const SizedBox(), duration: Duration.zero, phase: EnginePhase.build);
    services.dispose();
    await tester.pump();
    expect(tester.takeException(), isNull);
  });
}
