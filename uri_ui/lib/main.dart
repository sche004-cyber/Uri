/// Real application entry point.
///
/// This file is deliberately thin, and is the ONLY place that touches a
/// platform plugin (`package:file_picker`, via platform_file_picker.dart).
/// The widget tree itself lives in app.dart so that widget tests can
/// import it without pulling the plugin in — which hangs `flutter test`.
library;

import 'package:flutter/material.dart';

import 'app.dart';
import 'services/app_state.dart';
import 'services/device_identity.dart';
import 'services/http_uri_client.dart';
import 'services/desktop_harness_test_client.dart';
import 'services/desktop_harness_test_session.dart';
import 'widgets/desktop_harness_test.dart';
import 'services/platform_attachment_opener.dart';
import 'services/platform_file_picker.dart';
import 'services/platform_window_controller.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ensurePlatformWindowManagerInitialized();

  // Prototype 2 (multi-client + runtime awareness): this install's own
  // durable device_id (see device_identity.dart), generated once and
  // reused across launches, distinct from whichever user_id ends up
  // logging in on it. Resolved before the client is built so it can be
  // sent at login/signup time.
  final deviceId = await DeviceIdentityStore().loadOrCreate();

  // Talks to the real uri_core backend (uvicorn uri_core.app.server:app).
  // As of M16 nothing in HttpUriClient falls back to mock data. Widget/
  // unit tests build their own AppState with MockUriClient directly and
  // are unaffected by this.
  final uriClient = HttpUriClient(deviceId: deviceId);
  const harnessTestEnabled = bool.fromEnvironment('URI_DESKTOP_HARNESS_TEST');
  final appState = AppState(
    uriClient,
    sessionStore: harnessTestEnabled ? DesktopHarnessTestSession(namespace: const String.fromEnvironment('URI_DESKTOP_HARNESS_CORE_URL', defaultValue: 'http://127.0.0.1:8021')) : null,
  );
  final harnessTestClient = harnessTestEnabled
      ? DesktopHarnessTestClient(uriClient)
      : null;
  final harnessNavigatorKey = harnessTestEnabled
      ? GlobalKey<NavigatorState>()
      : null;
  // Resolve any previously persisted onboarding/preferences/server
  // address before the first frame, so a returning user never sees
  // onboarding flash by and a phone already pointed at its PC never
  // silently falls back to localhost.
  await appState.loadPersistedPreferences();
  await appState.loadPersistedServerAddress();
  if (harnessTestEnabled) {
    uriClient.setBaseUrl(
      const String.fromEnvironment(
        'URI_DESKTOP_HARNESS_CORE_URL',
        defaultValue: 'http://127.0.0.1:8018',
      ),
    );
  }
  await appState.loadPersistedThemeMode();
  // M22.9 (§0.3): restores and proactively revalidates a still-valid
  // login from a previous launch, so closing/reopening the app does
  // not force a fresh sign-in every time. Depends on the server
  // address above already being applied to _client.
  await appState.loadPersistedSession();

  // M16: the real platform picker (and, likewise, the real platform
  // attachment opener) is injected here, at the entry point, and
  // nowhere else.
  runApp(
    UriApp(
      appState: appState,
      integrationNavigatorKey: harnessNavigatorKey,
      integrationTestBuilder: harnessTestClient == null
          ? null
          : (context, child) => DesktopHarnessTest(
              client: harnessTestClient,
              navigatorKey: harnessNavigatorKey,
              child: child!,
            ),
      filePicker: pickPlatformFile,
      attachmentOpener: openPlatformAttachment,
      onCompactModeChanged: setCompactWindowMode,
    ),
  );
}
