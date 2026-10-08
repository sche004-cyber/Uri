/// Real application entry point.
///
/// This file is deliberately thin, and is the ONLY place that touches a
/// platform plugin (`package:file_picker`, via platform_file_picker.dart).
/// The widget tree itself lives in app.dart so that widget tests can
/// import it without pulling the plugin in — which hangs `flutter test`.
library;

import 'dart:io' show Platform;

import 'package:flutter/material.dart';

import 'app.dart';
import 'services/app_state.dart';
import 'services/device_identity.dart';
import 'services/http_uri_client.dart';
import 'services/platform_attachment_opener.dart';
import 'services/platform_file_picker.dart';
import 'services/platform_window_controller.dart';
import 'services/integrated_runtime.dart';
import 'working_system_app.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ensurePlatformWindowManagerInitialized();

  // Prototype 2 (multi-client + runtime awareness): this install's own
  // durable device_id (see device_identity.dart), generated once and
  // reused across launches, distinct from whichever user_id ends up
  // logging in on it. Resolved before the client is built so it can be
  // sent at login/signup time.
  final deviceId = await DeviceIdentityStore().loadOrCreate();

  // Working-system integration (WS-D1/WS-D4): a paired installation with the
  // integrated opt-in starts in Living Companion over the integrated worker.
  // Nothing else changes for installations without the opt-in.
  final manifest = Platform.environment['URI_CLIENT_MANIFEST'];
  if (WorkerIntegratedRuntime.optInConfigured(manifest)) {
    runApp(
      WorkingSystemRoot(
        connect: () => WorkerIntegratedRuntime.fromManifest(manifest),
        classicBuilder: (back) => _ClassicLoader(deviceId: deviceId, back: back),
        filePicker: pickPlatformFile,
        attachmentOpener: openPlatformAttachment,
        skipOnboarding: Platform.environment['URI_LIVING_SKIP_ONBOARDING'] == '1',
      ),
    );
    return;
  }

  // Talks to the real uri_core backend (uvicorn uri_core.app.server:app).
  // As of M16 nothing in HttpUriClient falls back to mock data. Widget/
  // unit tests build their own AppState with MockUriClient directly and
  // are unaffected by this.
  final appState = AppState(HttpUriClient(deviceId: deviceId));
  // Resolve any previously persisted onboarding/preferences/server
  // address before the first frame, so a returning user never sees
  // onboarding flash by and a phone already pointed at its PC never
  // silently falls back to localhost.
  await appState.loadPersistedPreferences();
  await appState.loadPersistedServerAddress();
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
      filePicker: pickPlatformFile,
      attachmentOpener: openPlatformAttachment,
      onCompactModeChanged: setCompactWindowMode,
    ),
  );
}

/// The classic (Hybrid) interface inside the working system. Its server
/// address is read first (preferences only, no network); the legacy instance
/// on port 8000 is never contacted. A small control returns to Living.
class _ClassicLoader extends StatefulWidget {
  const _ClassicLoader({required this.deviceId, required this.back});
  final String deviceId;
  final VoidCallback back;

  @override
  State<_ClassicLoader> createState() => _ClassicLoaderState();
}

class _ClassicLoaderState extends State<_ClassicLoader> {
  late final Future<AppState?> _future = _load();

  Future<AppState?> _load() async {
    final appState = AppState(HttpUriClient(deviceId: widget.deviceId));
    await appState.loadPersistedServerAddress();
    if (isLegacyServerAddress(appState.baseUrl)) return null;
    await appState.loadPersistedPreferences();
    await appState.loadPersistedThemeMode();
    await appState.loadPersistedSession();
    return appState;
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<AppState?>(
      future: _future,
      builder: (context, snap) {
        if (snap.connectionState != ConnectionState.done) {
          return const MaterialApp(home: Scaffold(body: Center(child: CircularProgressIndicator())));
        }
        final appState = snap.data;
        if (appState == null) {
          return LegacyServerBlocked(baseUrl: 'http://localhost:8000', back: widget.back);
        }
        return Directionality(
          textDirection: TextDirection.ltr,
          child: Stack(
            children: [
              UriApp(
                appState: appState,
                filePicker: pickPlatformFile,
                attachmentOpener: openPlatformAttachment,
                onCompactModeChanged: setCompactWindowMode,
              ),
              Positioned(
                right: 12,
                bottom: 12,
                child: GestureDetector(
                  onTap: widget.back,
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
                    decoration: BoxDecoration(color: const Color(0xCC101820), borderRadius: BorderRadius.circular(8)),
                    child: const Text('Living Companion', style: TextStyle(color: Color(0xFFE6F7FF), fontSize: 12)),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
