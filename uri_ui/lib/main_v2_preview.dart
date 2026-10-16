/// Explicit offline visual-review fixture. Authentication is not demonstrated
/// here; main_v2.dart is the real-service entry with mandatory auth gates.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'living/companion/companion_preferences.dart';
import 'living/companion/companion_sources.dart';
import 'living/companion/effects_settings.dart';
import 'living/contracts/readiness_report.dart';
import 'living/contracts/work_items.dart';
import 'living/living_app.dart';
import 'living/living_scope.dart';
import 'living/presentation/presentation_controller.dart';
import 'services/app_state.dart';
import 'services/companion_window_adapter.dart';
import 'services/mock_uri_client.dart';
import 'services/platform_window_controller.dart';
import 'services/window_visibility.dart';
import 'theme/uri_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ensurePlatformWindowManagerInitialized();
  // ignore: invalid_use_of_visible_for_testing_member
  SharedPreferences.setMockInitialValues({
    CompanionPreferences.keyInterfaceTheme: UriThemeChoice.ivoryFoundry.name,
  });
  final app = AppState(
    MockUriClient(),
    preferencesStore: LivingPreferencesStore(),
  );
  final work = MockWorkSimulator(seed: false);
  final demo = MockCompanionSource();
  final services = LivingServices(
    presentation: UiPresentationController(
      initialMode: UiPresentationMode.dashboard,
    ),
    companion: CompositeCompanionSource([
      AppStateCompanionSource(app, dataIsMock: true),
      work.companion,
      demo,
    ]),
    work: work,
    readiness: MockReadinessSource(),
    effects: EffectsSettings(),
    demo: demo,
    visualV2: true,
  );
  final native = CompanionWindowAdapter();
  services.updateCompanionWindow = (layout) async {
    await native.update(layout);
    services.windowNotice.value = native.lastError;
  };
  services.moveCompanionWindow = native.move;
  services.readCompanionPointer = native.cursorPosition;
  unawaited(bindWindowVisibility(services.frameClock));
  runApp(LivingApp(appState: app, services: services, skipOnboarding: true));
}
