/// Isolated real-service entry. Authentication/bootstrap are mandatory.
/// The candidate Windows VERSIONINFO uses a separate application-support
/// directory; it never reads the live installation's saved account/session.
library;

import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';

import 'app.dart';
import 'living/companion/companion_preferences.dart';
import 'living/companion/companion_sources.dart';
import 'living/companion/effects_settings.dart';
import 'living/contracts/work_items.dart';
import 'living/integration/http_readiness_source.dart';
import 'living/living_app.dart';
import 'living/living_scope.dart';
import 'living/presentation/presentation_controller.dart';
import 'living/presentation/companion_window_layout.dart';
import 'services/app_state.dart';
import 'services/companion_window_adapter.dart';
import 'services/device_identity.dart';
import 'services/http_uri_client.dart';
import 'services/live_voice_service.dart';
import 'services/platform_attachment_opener.dart';
import 'services/platform_file_picker.dart';
import 'services/platform_window_controller.dart';
import 'services/window_visibility.dart';
import 'services/windows_voice_catalog.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ensurePlatformWindowManagerInitialized();
  final companion = await CompanionPreferences.load();
  final deviceId = await DeviceIdentityStore().loadOrCreate();
  final app = AppState(HttpUriClient(deviceId: deviceId));
  await app.loadPersistedPreferences();
  await app.loadPersistedServerAddress();
  await app.loadPersistedThemeMode();
  await app.loadPersistedSession();
  runApp(
    UriApp(
      appState: app,
      filePicker: pickPlatformFile,
      attachmentOpener: openPlatformAttachment,
      companionPreferences: companion,
      authenticatedHome: _V2Home(app: app, companion: companion),
    ),
  );
}

class _V2Home extends StatefulWidget {
  const _V2Home({required this.app, required this.companion});
  final AppState app;
  final CompanionPreferences companion;
  @override
  State<_V2Home> createState() => _V2HomeState();
}

class _V2HomeState extends State<_V2Home> {
  late final LivingServices _services;
  final _window = CompanionWindowAdapter();
  @override
  void initState() {
    super.initState();
    final work = MockWorkSimulator(seed: false);
    final demo = MockCompanionSource();
    _services = LivingServices(
      presentation: UiPresentationController(
        initialMode: UiPresentationMode.dashboard,
      ),
      companion: CompositeCompanionSource([
        AppStateCompanionSource(widget.app),
      ]),
      work: work,
      readiness: HttpReadinessSource(widget.app),
      effects: EffectsSettings(),
      demo: demo,
      appDataIsMock: false,
      visualV2: true,
      companionPreferences: widget.companion,
    );
    _services.updateCompanionWindow = (layout) async {
      await _window.update(layout);
      if (mounted) _services.windowNotice.value = _window.lastError;
    };
    _services.moveCompanionWindow = _window.move;
    _services.readCompanionPointer = _window.cursorPosition;
    _services.classicInterfaceBuilder = (_) => const UriHome(
      filePicker: pickPlatformFile,
      attachmentOpener: openPlatformAttachment,
    );
    if (Platform.isWindows) {
      _services.voiceCatalog = WindowsVoiceCatalog();
      final voice = LiveVoiceService();
      _services.attachLiveVoice(voice);
      unawaited(voice.ensureStarted());
    }
    unawaited(bindWindowVisibility(_services.frameClock));
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      unawaited(widget.app.loadTasks());
      unawaited(widget.app.loadActiveBrain());
      unawaited(widget.app.loadConnections());
    });
  }

  @override
  void dispose() {
    unawaited(
      _window.update(
        const CompanionWindowLayout(active: false, orb: Rect.zero),
      ),
    );
    _services.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => LivingApp(
    appState: widget.app,
    services: _services,
    skipOnboarding: true,
    filePicker: pickPlatformFile,
    attachmentOpener: openPlatformAttachment,
  );
}
