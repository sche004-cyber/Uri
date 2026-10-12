/// Working-system root (WS blueprint W10, owner decision WS-D4).
///
/// Active only when the paired installation named by `URI_CLIENT_MANIFEST`
/// carries the integrated opt-in (`control/ui-integrated-profile.json`).
/// Living Companion is the default shell, over the real integrated worker
/// (Core + Operational Intelligence + Runtime v1). Living Settings can open
/// the classic (Hybrid) interface instead. That closes the integrated worker
/// first (one worker per client root), and it never contacts the legacy
/// instance on port 8000.
///
/// Plugin-free like `app.dart`; `main.dart` injects the plugin-backed pieces.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'living/integration/oi_conversation.dart';
import 'living/integration/ws_settings.dart';
import 'living/living_app.dart';
import 'living/living_scope.dart';
import 'services/app_state.dart';
import 'services/file_picker_service.dart';
import 'services/attachment_opener_service.dart';
import 'services/integrated_runtime.dart';
import 'services/mock_uri_client.dart';
import 'theme/uri_theme.dart';

const wsShellPref = 'uri.ws.shell';

/// True when [baseUrl] points at the known legacy instance (port 8000 on this
/// machine). The working system never contacts it.
bool isLegacyServerAddress(String baseUrl) {
  final u = Uri.tryParse(baseUrl);
  if (u == null) return false;
  final local =
      u.host == 'localhost' ||
      u.host == '127.0.0.1' ||
      u.host == '::1' ||
      u.host == '[::1]';
  return local && u.port == 8000;
}

class WorkingSystemRoot extends StatefulWidget {
  const WorkingSystemRoot({
    super.key,
    required this.connect,
    required this.classicBuilder,
    this.filePicker,
    this.attachmentOpener,
    this.statusInterval = const Duration(seconds: 15),
    this.healthInterval = const Duration(seconds: 5),
    this.skipOnboarding = false,
    this.configureServices,
    this.visualV2 = false,
  });

  /// Called once for each set of living services the root builds (after a
  /// connect). The entry point uses it for platform wiring that widget tests
  /// must not run: the installed-voice catalog and the window minimise
  /// binding that stops the companion's frames while the window is hidden.
  final void Function(LivingServices services)? configureServices;

  /// Spawns the integrated worker (null = not configured).
  final Future<IntegratedRuntime?> Function() connect;

  /// Builds the classic interface; `back` returns to Living Companion.
  final Widget Function(VoidCallback back) classicBuilder;
  final FilePickerFn? filePicker;
  final AttachmentOpenerFn? attachmentOpener;
  final Duration statusInterval;

  /// Health polling and liveness monitor period (WS hardening).
  final Duration healthInterval;
  final bool skipOnboarding;

  /// Candidate composition only; worker authority and lifecycle stay unchanged.
  final bool visualV2;

  @override
  State<WorkingSystemRoot> createState() => _WorkingSystemRootState();
}

class _WorkingSystemRootState extends State<WorkingSystemRoot> {
  bool? _classic;
  IntegratedRuntime? _runtime;
  OiConversation? _conv;
  LivingServices? _services;
  AppState? _appState;
  String? _error;
  bool _connecting = false;
  Timer? _status;

  @override
  void initState() {
    super.initState();
    _start();
  }

  Future<void> _start() async {
    final prefs = await SharedPreferences.getInstance();
    final classic = prefs.getString(wsShellPref) == 'classic';
    if (!mounted) return;
    setState(() => _classic = classic);
    if (!classic) await _connect();
  }

  Future<void> _connect() async {
    if (_connecting) return;
    setState(() {
      _connecting = true;
      _error = null;
    });
    try {
      final rt = await widget.connect();
      if (rt == null) {
        throw IntegratedRuntimeException('INTEGRATED_PROFILE_NOT_CONFIGURED');
      }
      // Restart URI (R-BUSY) starts a fresh worker through the same connect path.
      final conv = OiConversation(rt, respawn: widget.connect);
      _runtime = rt;
      _conv = conv;
      _appState = AppState(
        MockUriClient(),
        preferencesStore: LivingPreferencesStore(),
      );
      _services = LivingApp.buildIntegratedServices(
        conv,
        visualV2: widget.visualV2,
      );
      widget.configureServices?.call(_services!);
      await conv.refreshStatus();
      unawaited(
        _services!.readiness.refresh(),
      ); // harness discovery for the readiness views (read-only)
      _status = Timer.periodic(
        widget.statusInterval,
        (_) => conv.refreshStatus(),
      );
      conv.startMonitor(widget.healthInterval);
    } on IntegratedRuntimeException catch (e) {
      _error = e.code;
    } catch (e) {
      _error = 'WORKER_START_FAILED';
    }
    if (mounted) setState(() => _connecting = false);
  }

  Future<void> _disconnect() async {
    _status?.cancel();
    _status = null;
    final rt =
        _conv?.runtime ?? _runtime; // a restarted worker replaces the first one
    _runtime = null;
    _services?.dispose();
    _services = null;
    _conv?.dispose();
    _conv = null;
    await rt?.close();
  }

  Future<void> _setClassic(bool classic) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(wsShellPref, classic ? 'classic' : 'living');
    if (classic) await _disconnect();
    if (!mounted) return;
    setState(() => _classic = classic);
    if (!classic) await _connect();
  }

  @override
  void dispose() {
    _disconnect();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_classic == null) return const SizedBox.shrink();
    if (_classic!) return widget.classicBuilder(() => _setClassic(false));
    final conv = _conv;
    if (conv == null || _services == null) {
      return _StatusApp(
        connecting: _connecting,
        error: _error,
        onRetry: _connect,
        onClassic: () => _setClassic(true),
      );
    }
    return WorkingSystemShellSwitch(
      openClassic: () => _setClassic(true),
      child: LivingApp(
        appState: _appState!,
        services: _services,
        filePicker: widget.filePicker,
        attachmentOpener: widget.attachmentOpener,
        skipOnboarding: widget.skipOnboarding,
      ),
    );
  }
}

class _StatusApp extends StatelessWidget {
  const _StatusApp({
    required this.connecting,
    required this.error,
    required this.onRetry,
    required this.onClassic,
  });
  final bool connecting;
  final String? error;
  final VoidCallback onRetry;
  final VoidCallback onClassic;

  @override
  Widget build(BuildContext context) {
    final palette = resolveUriColors(
      UriThemeChoice.obsidianCyan,
      Brightness.dark,
    );
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: buildUriTheme(palette),
      home: Scaffold(
        body: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (connecting) const CircularProgressIndicator(),
              const SizedBox(height: 16),
              Text(
                connecting
                    ? 'Starting URI…'
                    : 'URI could not start: ${error ?? 'unknown'}',
                key: const ValueKey('ws-status'),
              ),
              if (!connecting) ...[
                const SizedBox(height: 16),
                FilledButton(onPressed: onRetry, child: const Text('Retry')),
                TextButton(
                  onPressed: onClassic,
                  child: const Text('Open the classic interface'),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

/// Shown instead of the classic interface when its saved server address is
/// the legacy instance. The working system never contacts it.
class LegacyServerBlocked extends StatelessWidget {
  const LegacyServerBlocked({
    super.key,
    required this.baseUrl,
    required this.back,
  });
  final String baseUrl;
  final VoidCallback back;

  @override
  Widget build(BuildContext context) {
    final palette = resolveUriColors(
      UriThemeChoice.obsidianCyan,
      Brightness.dark,
    );
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: buildUriTheme(palette),
      home: Scaffold(
        body: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  'The classic interface is set to $baseUrl, which is the legacy URI instance. '
                  'The working system does not connect to it.',
                  key: const ValueKey('ws-legacy-blocked'),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: back,
                  child: const Text('Back to Living Companion'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
