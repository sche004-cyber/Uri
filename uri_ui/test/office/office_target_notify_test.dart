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
}
