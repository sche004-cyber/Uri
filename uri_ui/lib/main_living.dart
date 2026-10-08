/// Living Companion preview entry point: mock-data mode, no server.
///
///     flutter run -d windows -t lib/main_living.dart
///
/// Uses [MockUriClient] only. It never contacts port 8000, never reads
/// the Hybrid app's persisted session/server address, and writes only
/// `uri.living.*` preference keys. The Hybrid entry (`main.dart`) is
/// untouched. See `docs/ui_phase/UI_INTEGRATION_PLAN.md` for how this
/// would later mount inside `UriApp`.
///
/// Demo / evidence hooks (process environment, read once at start; all
/// optional, all local, none reachable from the Brain or the server):
///
/// | variable | effect |
/// |---|---|
/// | `URI_LIVING_SKIP_ONBOARDING=1` | open the shell directly |
/// | `URI_LIVING_START_MODE=companion|workspace|dashboard` | initial form |
/// | `URI_LIVING_START_FOCUS=conversation|tasks|documents|intelligence|settings` | initial Workspace region |
/// | `URI_LIVING_DEMO_STATE=<CompanionState name>` | feed one mock orb state (flagged Simulated) |
/// | `URI_LIVING_REDUCED_EFFECTS=1` | start with effects reduced |
/// | `URI_LIVING_PERF=1` | print frame-timing summaries to stdout |
library;

import 'dart:io' show Platform;

import 'package:flutter/material.dart';

import 'living/companion/companion_state.dart';
import 'living/living_app.dart';
import 'living/perf_logger.dart';
import 'living/presentation/presentation_controller.dart';
import 'services/app_state.dart';
import 'services/mock_uri_client.dart';
import 'services/platform_attachment_opener.dart';
import 'services/platform_file_picker.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final env = Platform.environment;
  bool flag(String k) => env[k] == '1' || env[k]?.toLowerCase() == 'true';

  final appState = AppState(MockUriClient());
  final services = LivingApp.buildDefaultServices(appState);

  final mode = UiPresentationMode.values
      .where((m) => m.name == env['URI_LIVING_START_MODE'])
      .firstOrNull;
  final focus = WorkspaceFocus.values
      .where((f) => f.name == env['URI_LIVING_START_FOCUS'])
      .firstOrNull;
  if (mode != null || focus != null) {
    services.presentation.setMode(mode ?? services.presentation.mode, focus: focus);
  }
  final demoState = CompanionState.values
      .where((s) => s.name == env['URI_LIVING_DEMO_STATE'])
      .firstOrNull;
  if (demoState != null) {
    services.demo.emit(demoState, detail: 'Demo state from URI_LIVING_DEMO_STATE');
  }
  if (flag('URI_LIVING_REDUCED_EFFECTS')) services.effects.setReducedEffects(true);
  if (flag('URI_LIVING_PERF')) PerfLogger().install();

  runApp(
    LivingApp(
      appState: appState,
      services: services,
      filePicker: pickPlatformFile,
      attachmentOpener: openPlatformAttachment,
      skipOnboarding: flag('URI_LIVING_SKIP_ONBOARDING'),
    ),
  );
}
