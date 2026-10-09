// Capture harness for the companion settings phase: the real living app (the
// shell, the selected companion, Companion Settings) rendered by the Windows
// engine, plus deterministic close-ups of each render quality.
//
// It runs `LivingApp` itself, with the mock AppState used by the preview and
// the real Windows voice catalog (read-only listing of installed voices). The
// live companions animate, so those frames are a moment of a running app, not
// a fixed seed; the quality close-ups use fixed frames so they compare
// exactly. Preferences are held in memory: nothing is written to the
// `shared_preferences.json` every uri_ui build on this PC shares.
//
// The one voice frame is driven by a scripted adapter playing a real
// System.Speech recording through the same VoiceServiceBinding the app uses,
// and is labelled SIMULATED on screen.
//
// Usage (from uri_ui/):
//   flutter run -d windows -t tool/capture/settings_capture_app.dart \
//     --dart-define=OUT=<absolute dir>
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/voice/companion_presence.dart';
import 'package:uri_ui/living/voice/voice_catalog.dart';
import 'package:uri_ui/living/voice/voice_level.dart';
import 'package:uri_ui/living/voice/voice_script.dart';
import 'package:uri_ui/living/voice/voice_session.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/services/windows_voice_catalog.dart';
import 'package:uri_ui/theme/uri_theme.dart';

const String outDir = String.fromEnvironment('OUT', defaultValue: 'captures');
const String fixtures = String.fromEnvironment(
  'FIXTURES',
  defaultValue: 'test/fixtures/voice',
);
const Size appSize = Size(1280, 860);

final GlobalKey _appKey = GlobalKey();
final GlobalKey _closeKey = GlobalKey();
final ValueNotifier<Widget?> _closeup = ValueNotifier<Widget?>(null);
final StringBuffer _log = StringBuffer();

void log(String s) {
  _log.writeln(s);
  // ignore: avoid_print
  print(s);
}

/// Plays a scripted voice turn as if it came from a voice service.
class ScriptedVoiceAdapter implements VoiceServiceAdapter {
  ScriptedVoiceAdapter(this.events);
  final List<(int, VoiceSignal)> events;
  final StreamController<VoiceSignal> _ctl = StreamController<VoiceSignal>();
  final List<Timer> _timers = [];

  @override
  String get name => 'Scripted System.Speech recording (simulated)';
  @override
  bool get simulated => true;
  @override
  Stream<VoiceSignal> get signals => _ctl.stream;

  void play() {
    for (final (ms, e) in events) {
      _timers.add(Timer(Duration(milliseconds: ms), () => _ctl.add(e)));
    }
  }

  void stop() {
    for (final t in _timers) {
      t.cancel();
    }
    _ctl.close();
  }
}

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // In-memory preferences: the harness never touches the shared file.
  // ignore: invalid_use_of_visible_for_testing_member
  SharedPreferences.setMockInitialValues({});
  Directory(outDir).createSync(recursive: true);
  final appState = AppState(
    MockUriClient(),
    preferencesStore: LivingPreferencesStore(),
  );
  final services = LivingApp.buildDefaultServices(appState);
  services.voiceCatalog = WindowsVoiceCatalog();
  runApp(
    Directionality(
      textDirection: TextDirection.ltr,
      child: Stack(
        children: [
          Positioned(
            left: 0,
            top: 0,
            width: appSize.width,
            height: appSize.height,
            child: RepaintBoundary(
              key: _appKey,
              child: LivingApp(
                appState: appState,
                services: services,
                skipOnboarding: true,
              ),
            ),
          ),
          Positioned(
            left: 0,
            top: 0,
            child: ValueListenableBuilder<Widget?>(
              valueListenable: _closeup,
              builder: (context, w, _) => w == null
                  ? const SizedBox.shrink()
                  : RepaintBoundary(key: _closeKey, child: w),
            ),
          ),
        ],
      ),
    ),
  );
  await Future<void>.delayed(const Duration(seconds: 2));
  var failures = 0;
  try {
    await _run(services);
  } catch (e, st) {
    failures++;
    log('FAILED $e\n$st');
  }
  log('DONE failures=$failures');
  File('$outDir/capture_log.txt').writeAsStringSync(_log.toString());
  exit(failures == 0 ? 0 : 1);
}

Future<void> _settle([int ms = 1400]) async {
  await Future<void>.delayed(Duration(milliseconds: ms));
  await WidgetsBinding.instance.endOfFrame;
}

Future<void> _shot(String name, {GlobalKey? key, double ratio = 1}) async {
  await WidgetsBinding.instance.endOfFrame;
  final obj =
      (key ?? _appKey).currentContext!.findRenderObject()!
          as RenderRepaintBoundary;
  final img = await obj.toImage(pixelRatio: ratio);
  final data = await img.toByteData(format: ui.ImageByteFormat.png);
  img.dispose();
  File('$outDir/$name.png').writeAsBytesSync(data!.buffer.asUint8List());
  log('SHOT $name ${obj.size.width.round()}x${obj.size.height.round()}');
}

Element? _find(String key) {
  Element? hit;
  void visit(Element e) {
    if (hit != null) return;
    final k = e.widget.key;
    if (k is ValueKey<String> && k.value == key) {
      hit = e;
      return;
    }
    e.visitChildren(visit);
  }

  WidgetsBinding.instance.rootElement?.visitChildren(visit);
  return hit;
}

Future<void> _scrollTo(String key) async {
  final e = _find(key);
  if (e == null) {
    log('MISSING $key');
    return;
  }
  await Scrollable.ensureVisible(e, alignment: 0.04);
  await _settle(500);
}

Future<void> _run(LivingServices s) async {
  final prefs = s.companionPrefs;
  final hz = s.frameGovernor.displayHz;
  log('display_hz=$hz');

  // 1. Every companion: Companion mode, its settings, Dashboard.
  for (final choice in CompanionChoice.all) {
    final k = choice.key;
    prefs.select(choice);
    s.presentation.setMode(UiPresentationMode.companion);
    await _settle(1800);
    await _shot('companion_$k');
    s.presentation.setMode(
      UiPresentationMode.workspace,
      focus: WorkspaceFocus.settings,
    );
    await _settle(1200);
    await _scrollTo('companion-settings');
    await _shot('settings_${k}_picker');
    await _scrollTo('fps-note');
    await _shot('settings_${k}_performance');
    await _scrollTo('voice-service-line');
    await _settle(2500); // the voice listing runs PowerShell once
    await _shot('settings_${k}_voice');
    s.presentation.setMode(UiPresentationMode.dashboard);
    await _settle(1500);
    await _shot('dashboard_$k');
  }

  // 2. Statistics overlay on the default companion, after a few windows.
  prefs.select(const CompanionChoice.living(CompanionIdentity.solar));
  prefs.setStatsOverlay(true);
  s.presentation.setMode(UiPresentationMode.companion);
  await _settle(6500);
  await _shot('stats_overlay_solar');
  final w = s.frameGovernor.lastWindow;
  log(
    'stats delivered_fps=${s.frameClock.deliveredFps.toStringAsFixed(1)} '
    'app_fps=${w?.fps.toStringAsFixed(1)} raster_p90=${w?.rasterP90Ms.toStringAsFixed(2)}',
  );
  prefs.setStatsOverlay(false);

  // 3. A voice turn through the adapter interface (simulated recording).
  final clip = decodeWavPcm16(
    File('$fixtures/user_request.wav').readAsBytesSync(),
  );
  final timing = jsonDecode(
    File('$fixtures/user_request.timing.json').readAsStringSync(),
  ) as Map<String, dynamic>;
  final adapter = ScriptedVoiceAdapter(
    VoiceScript.userTurn(
      clip: clip,
      words: VoiceScript.wordsFromJson(timing),
      text: timing['text'] as String,
      sessionId: 'capture-1',
    ),
  );
  s.bindVoice(adapter);
  for (final (name, mode) in [
    ('voice_companion_mode', UiPresentationMode.companion),
    ('voice_workspace_mode', UiPresentationMode.workspace),
  ]) {
    s.presentation.setMode(mode, focus: WorkspaceFocus.conversation);
    await _settle(900);
    adapter.play();
    await Future<void>.delayed(const Duration(milliseconds: 3600));
    await _shot(name);
    await Future<void>.delayed(const Duration(milliseconds: 4500));
  }
  adapter.stop();
  await _settle(800);

  // 4. Reduced effects keeps the state readable without a shader.
  s.effects.setReducedEffects(true);
  s.presentation.setMode(UiPresentationMode.companion);
  await _settle(1200);
  await _shot('reduced_effects_solar');
  s.effects.setReducedEffects(false);

  // 5. Render quality close-ups: fixed frames, identical except the scale.
  for (final id in CompanionIdentity.values) {
    for (final q in RenderQuality.values) {
      final scale = presenceScale(id);
      _closeup.value = Theme(
        data: buildUriTheme(UriColors.lunarSilver),
        child: EffectsSettingsScope(
          settings: EffectsSettings(),
          child: Container(
            width: 420,
            height: 420,
            color: const Color(0xFF000000),
            child: OverflowBox(
              maxWidth: 420 * scale,
              maxHeight: 420 * scale,
              child: SizedBox(
                width: 420 * scale,
                height: 420 * scale,
                child: SoftDisc(
                  outer: 1 / scale,
                  child: CompanionOrbFrame(
                    identity: id,
                    params: CompanionParams.of(id, CompanionState.idle),
                    seconds: 17,
                    renderScale: q.scale,
                  ),
                ),
              ),
            ),
          ),
        ),
      );
      await _settle(700);
      await _shot('quality_${id.name}_${q.name}', key: _closeKey);
    }
  }
  _closeup.value = null;
}
