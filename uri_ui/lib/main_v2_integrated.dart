/// Optional isolated-worker qualification entry. Never reads the owner's
/// URI_CLIENT_MANIFEST. No worker is started without an explicit candidate
/// manifest whose source and client directories are inside this worktree.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import 'app.dart';
import 'living/presentation/companion_window_layout.dart';
import 'services/app_state.dart';
import 'services/companion_window_adapter.dart';
import 'services/device_identity.dart';
import 'services/http_uri_client.dart';
import 'services/integrated_runtime.dart';
import 'services/live_voice_service.dart';
import 'services/platform_attachment_opener.dart';
import 'services/platform_file_picker.dart';
import 'services/platform_window_controller.dart';
import 'services/window_visibility.dart';
import 'services/windows_voice_catalog.dart';
import 'theme/uri_theme.dart';
import 'working_system_app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ensurePlatformWindowManagerInitialized();
  final manifest = Platform.environment['URI_V2_CLIENT_MANIFEST'];
  bool isolated = false;
  try {
    final candidate = Directory.current.parent
        .resolveSymbolicLinksSync()
        .toLowerCase();
    final data =
        jsonDecode(File(manifest!).readAsStringSync()) as Map<String, dynamic>;
    final source = Directory(data['source_root'] as String)
        .resolveSymbolicLinksSync()
        .toLowerCase();
    final client = Directory(data['client_root'] as String)
        .resolveSymbolicLinksSync()
        .toLowerCase();
    isolated =
        source == candidate &&
        client.startsWith(
          '$candidate${Platform.pathSeparator}work${Platform.pathSeparator}ui_v2${Platform.pathSeparator}',
        );
  } catch (_) {
    /* Missing/invalid manifests stay unavailable, with no spawn. */
  }
  if (!isolated || !WorkerIntegratedRuntime.optInConfigured(manifest)) {
    runApp(
      MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: buildUriTheme(
          resolveUriColors(UriThemeChoice.ivoryFoundry, Brightness.light),
        ),
        home: const Scaffold(
          body: Center(
            child: Padding(
              padding: EdgeInsets.all(32),
              child: Text(
                'URI\nIntegrated preview unavailable. Set URI_V2_CLIENT_MANIFEST to an explicitly prepared isolated client under this worktree/work/ui_v2/. No worker was started.',
              ),
            ),
          ),
        ),
      ),
    );
    return;
  }
  final window = CompanionWindowAdapter();
  final device = await DeviceIdentityStore().loadOrCreate();
  runApp(
    WorkingSystemRoot(
      visualV2: true,
      connect: () => WorkerIntegratedRuntime.fromManifest(manifest),
      filePicker: pickPlatformFile,
      attachmentOpener: openPlatformAttachment,
      classicBuilder: (back) {
        unawaited(
          window.update(
            const CompanionWindowLayout(active: false, orb: Rect.zero),
          ),
        );
        return _Classic(device: device, back: back);
      },
      configureServices: (services) {
        services.updateCompanionWindow = (layout) async {
          await window.update(layout);
          services.windowNotice.value = window.lastError;
        };
        services.moveCompanionWindow = window.move;
        if (Platform.isWindows) {
          services.voiceCatalog = WindowsVoiceCatalog();
          final live = LiveVoiceService();
          services.attachLiveVoice(
            live,
            dictation:
                (raw, {required engine, uncertain = const <String>[]}) async {
                  await services.oi?.sendTranscript(
                    raw,
                    engine: engine,
                    simulated: false,
                    uncertain: uncertain,
                    dictation: true,
                  );
                },
          );
          unawaited(live.ensureStarted());
        }
        unawaited(bindWindowVisibility(services.frameClock));
      },
    ),
  );
}

class _Classic extends StatefulWidget {
  const _Classic({required this.device, required this.back});
  final String device;
  final VoidCallback back;
  @override
  State<_Classic> createState() => _ClassicState();
}

class _ClassicState extends State<_Classic> {
  AppState? _app;
  late final Future<AppState?> _loaded = _load();
  Future<AppState?> _load() async {
    final app = AppState(HttpUriClient(deviceId: widget.device));
    _app = app;
    await app.loadPersistedServerAddress();
    if (isLegacyServerAddress(app.baseUrl)) return null;
    await app.loadPersistedPreferences();
    await app.loadPersistedThemeMode();
    await app.loadPersistedSession();
    return app;
  }

  @override
  void dispose() {
    _app?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => FutureBuilder<AppState?>(
    future: _loaded,
    builder: (_, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const MaterialApp(
          home: Scaffold(body: Center(child: CircularProgressIndicator())),
        );
      }
      if (snapshot.data == null) {
        return LegacyServerBlocked(
          baseUrl: _app?.baseUrl ?? 'unavailable',
          back: widget.back,
        );
      }
      return Directionality(
        textDirection: TextDirection.ltr,
        child: Stack(
          children: [
            UriApp(
              appState: snapshot.data!,
              filePicker: pickPlatformFile,
              attachmentOpener: openPlatformAttachment,
            ),
            Positioned(
              right: 16,
              bottom: 16,
              child: Material(
                child: TextButton(
                  onPressed: widget.back,
                  child: const Text('Return to Living Companion'),
                ),
              ),
            ),
          ],
        ),
      );
    },
  );
}
