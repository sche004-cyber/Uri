/// Real Windows Flutter-engine capture, fixture services only. No network,
/// account, microphone, private transcript or persisted preference access.
library;

import 'dart:io';
import 'dart:async';
import 'dart:convert';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/companion/companion_design.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/contracts/readiness_report.dart';
import 'package:uri_ui/living/contracts/work_items.dart';
import 'package:uri_ui/living/voice/voice_session.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/presentation/companion_window_layout.dart';
import 'package:uri_ui/living/screens/companion_mode_view.dart';
import 'package:uri_ui/living/screens/settings/companion_gallery.dart';
import 'package:uri_ui/screens/auth/login_screen.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/live_voice_service.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/services/uri_client.dart';
import 'package:uri_ui/services/platform_window_controller.dart';
import 'package:uri_ui/services/companion_window_adapter.dart';
import 'package:uri_ui/theme/uri_theme.dart';

const output = String.fromEnvironment(
  'OUT',
  defaultValue: '../docs/ui_v2/evidence/flutter',
);
final _key = GlobalKey();
final _scene = ValueNotifier<Widget>(const SizedBox.shrink());
final _size = ValueNotifier<Size>(const Size(1440, 1000));
final _log = StringBuffer(
  'Fixture-only Flutter engine capture. Native desktop compositing/hit testing is not captured by toImage.\n',
);
Future<void> settle() async {
  for (var i = 0; i < 3; i++) {
    WidgetsBinding.instance.scheduleFrame();
    await WidgetsBinding.instance.endOfFrame;
  }
  await Future<void>.delayed(const Duration(milliseconds: 700));
  WidgetsBinding.instance.scheduleFrame();
  await WidgetsBinding.instance.endOfFrame;
}

Future<void> shot(String name) async {
  await settle();
  final boundary =
      _key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
  final image = await boundary.toImage(pixelRatio: 1);
  final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
  image.dispose();
  File('$output/$name.png').writeAsBytesSync(bytes!.buffer.asUint8List());
  _log.writeln('CAPTURED $name ${boundary.size}');
}

void press(String key) {
  void visit(Element element) {
    final widget = element.widget;
    if (widget is ButtonStyleButton && widget.key == ValueKey(key)) {
      widget.onPressed!();
      return;
    }
    element.visitChildElements(visit);
  }

  _key.currentContext!.visitChildElements(visit);
}

class FixtureVoiceTransport implements VoiceTransport {
  final eventsController = StreamController<Map<String, dynamic>>.broadcast();
  @override
  Stream<Map<String, dynamic>> get events => eventsController.stream;
  @override
  Future<int> get exitCode => Completer<int>().future;
  @override
  void send(Map<String, Object?> command) {}
  @override
  Future<void> close() => eventsController.close();
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ensurePlatformWindowManagerInitialized();
  // ignore: invalid_use_of_visible_for_testing_member
  SharedPreferences.setMockInitialValues({});
  Directory(output).createSync(recursive: true);
  runApp(
    Directionality(
      textDirection: TextDirection.ltr,
      child: Stack(
        children: [
          ValueListenableBuilder<Size>(
            valueListenable: _size,
            builder: (context, size, _) => Positioned(
              left: 0,
              top: 0,
              width: size.width,
              height: size.height,
              child: RepaintBoundary(
                key: _key,
                child: ValueListenableBuilder<Widget>(
                  valueListenable: _scene,
                  builder: (_, scene, _) => scene,
                ),
              ),
            ),
          ),
        ],
      ),
    ),
  );
  var failed = false;
  FlutterError.onError = (details) {
    failed = true;
    _log.writeln(details.toString());
  };
  for (final id in CompanionIdentity.values) {
    await CompanionShaderCache.load(id);
    _log.writeln(
      'SHADER ${id.name}: ${CompanionShaderCache.failureFor(id) ?? 'loaded'}',
    );
    if (CompanionShaderCache.failureFor(id) != null) failed = true;
  }
  for (final theme in [
    UriThemeChoice.ivoryFoundry,
    UriThemeChoice.snowArchive,
    UriThemeChoice.ashLimestone,
  ]) {
    // ignore: invalid_use_of_visible_for_testing_member
    SharedPreferences.setMockInitialValues({
      CompanionPreferences.keyInterfaceTheme: theme.name,
    });
    final app = AppState(
      MockUriClient(),
      preferencesStore: LivingPreferencesStore(),
    );
    final demo = MockCompanionSource();
    final work = MockWorkSimulator();
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
      effects: EffectsSettings(reducedMotion: true),
      demo: demo,
      visualV2: true,
    );
    services.companionPrefs.restoreFrom(await SharedPreferences.getInstance());
    _scene.value = LivingApp(
      key: UniqueKey(),
      appState: app,
      services: services,
      skipOnboarding: true,
    );
    _size.value = const Size(1440, 1000);
    await shot('dashboard-${theme.name}-1440');
    if (theme == UriThemeChoice.ivoryFoundry) {
      for (final size in [
        const Size(1920, 1080),
        const Size(1024, 768),
        const Size(390, 844),
      ]) {
        _size.value = size;
        await shot('dashboard-${size.width.toInt()}x${size.height.toInt()}');
      }
      _size.value = const Size(440, 680);
      services.presentation.setMode(UiPresentationMode.companion);
      await shot('companion-borderless-canvas');
      final native = CompanionWindowAdapter();
      final closedOrb = OrbDock.forMode(
        UiPresentationMode.companion,
        const Size(440, 680),
        visualV2: true,
      ).rect;
      GestureDetector? gesture;
      LivingShell.orbKey.currentContext!.visitAncestorElements((e) {
        if (e.widget is GestureDetector &&
            (e.widget as GestureDetector).onDoubleTap != null) {
          gesture = e.widget as GestureDetector;
          return false;
        }
        return true;
      });
      final fixtureVoice = LiveVoiceService(
        launch: () async => FixtureVoiceTransport(),
      );
      services.attachLiveVoice(fixtureVoice);
      await fixtureVoice.ensureStarted();
      fixtureVoice.status.value = const VoiceServiceStatus(
        state: VoiceServiceState.ready,
      );
      gesture!.onTap!();
      await shot('companion-action-launcher');
      app.conversation.add(
        UriTurn(
          id: 'visual-fixture',
          userText: 'Can you help with my draft?',
          timestamp: DateTime(2026, 10, 13),
          stage: TurnStage.completed,
          result: const ActionResult(summary: 'What would you like to change?'),
        ),
      );
      press('a2ui.companion-controls.chat');
      await shot('companion-detached-chat');
      services.voice.add(const ListeningStarted('capture-fixture'));
      services.voice.add(const AudioLevel(VoiceSpeaker.user, 0.18));
      await shot('companion-listening');
      services.voice.add(const UserSpeechStarted('capture-fixture'));
      services.voice.add(
        const UserTranscript('capture-fixture', 'Show the workspace'),
      );
      services.voice.add(const AudioLevel(VoiceSpeaker.user, 0.18));
      await shot('companion-user-speaking');
      services.voice.add(
        const ListeningEnded('capture-fixture', VoiceEndReason.completed),
      );
      services.voice.add(
        const UriSpeechStarted(
          'capture-reply',
          'The workspace is ready to open.',
        ),
      );
      services.voice.add(const AudioLevel(VoiceSpeaker.uri, 0.15));
      await shot('companion-uri-speaking');
      services.voice.add(const VoiceReset());
      _size.value = const Size(360, 560);
      await shot('companion-floating-360');
      _size.value = const Size(828, 1280);
      services.voice.add(const ListeningStarted('capture-reference-fixture'));
      // Fixture-only settled input: exercise the real stream mapper's attack
      // rather than showing only its first 20ms block. No audio is recorded.
      for (var block = 0; block < 20; block++) {
        services.voice.add(const AudioLevel(VoiceSpeaker.user, 0.75));
      }
      await shot('companion-approved-828');
      services.voice.add(const VoiceReset());
      _size.value = const Size(440, 680);
      await settle();
      final openOrb = OrbDock.forMode(
        UiPresentationMode.companion,
        const Size(440, 680),
        visualV2: true,
        expanded: true,
      ).rect;
      await native.update(CompanionWindowLayout(active: true, orb: closedOrb));
      final closedFacts = await const MethodChannel('uri/companion_window')
          .invokeMapMethod<String, dynamic>('facts');
      _log.writeln(
        'NATIVE_COLLAPSED ${jsonEncode(closedFacts)} error=${native.lastError}',
      );
      await native.update(
        CompanionWindowLayout(
          active: true,
          orb: openOrb,
          orbit: Rect.fromCircle(
            center: openOrb.center,
            radius: CompanionModeView.orbitRadius(const Size(440, 680)),
          ),
          panel: CompanionModeView.chatRect(const Size(440, 680), openOrb),
          buttons: CompanionModeView.buttonRects(
            const Size(440, 680),
            openOrb,
            CompanionModeView.actions(
              services,
              CompanionModeView.reviewCount(
                services,
                LivingShell.orbKey.currentContext!,
              ),
            ),
          ).values.toList(),
        ),
      );
      final openFacts = await const MethodChannel('uri/companion_window')
          .invokeMapMethod<String, dynamic>('facts');
      _log.writeln(
        'NATIVE_FLOATING ${jsonEncode(openFacts)} error=${native.lastError}',
      );
      if (native.lastError != null ||
          closedFacts?['cornerHit'] != false ||
          openFacts?['cornerHit'] != false) {
        failed = true;
      }
      await native.update(
        const CompanionWindowLayout(active: false, orb: Rect.zero),
      );
      services.presentation.setMode(
        UiPresentationMode.workspace,
        focus: WorkspaceFocus.conversation,
      );
      await shot('chat-workspace');
      _size.value = const Size(1440, 1000);
      services.presentation.setMode(
        UiPresentationMode.workspace,
        focus: WorkspaceFocus.settings,
      );
      await settle();
      Navigator.of(LivingShell.orbKey.currentContext!).push(
        MaterialPageRoute<void>(
          builder: (_) => CompanionGallery(
            active: services.companionPrefs,
            services: services,
          ),
        ),
      );
      await shot('companions-gallery');
      Navigator.of(LivingShell.orbKey.currentContext!).pop();
      await settle();
      for (final d in CompanionDesign.installed) {
        final navigator = Navigator.of(LivingShell.orbKey.currentContext!);
        navigator.push(
          MaterialPageRoute<void>(
            builder: (_) => CompanionGallery(
              active: services.companionPrefs,
              services: services,
              initialDesign: d,
            ),
          ),
        );
        await shot('viewer-${d.id}');
        navigator.pop();
        await settle();
      }
    }
    _scene.value = const SizedBox.shrink();
    await settle();
    services.dispose();
    app.dispose();
    _size.value = const Size(1440, 1000);
    _scene.value = MaterialApp(
      debugShowCheckedModeBanner: false,
      theme: buildUriTheme(resolveUriColors(theme, Brightness.light)),
      home: LoginScreen(
        onLogin: (_, _) async => const AuthOutcome.failure('Fixture only'),
        onSignup: (_, _) async => const AuthOutcome.failure('Fixture only'),
      ),
    );
    await shot('login-${theme.name}');
    _scene.value = const SizedBox.shrink();
    await settle();
  }
  File('$output/capture_log.txt').writeAsStringSync(_log.toString());
  File('$output/result.json').writeAsStringSync(
    jsonEncode({
      'success': !failed,
      'capture': 'real Windows Flutter engine',
      'data': 'fixtures only',
      'desktop_compositing_verified': false,
    }),
  );
  exit(failed ? 1 : 0);
}
