// EMBER-V21-INTEG live driver (temporary, external; adapted from the UI V2 freeze driver). Calls the ORIGINAL
// production main() of the candidate with the real integrated worker, paired Core and Runtime v1 Brain. Preferences
// are redirected (URI_QUAL_PREFS). The outer probe (tools/win_probe.py) checks the native window with Win32 and
// real OS input: borderless styles, per-pixel transparency over known backdrops, click-through, drag.
// Driver -> probe handshake: probe-<step>.json, probe answers probe-<step>.done.json.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path_provider_windows/path_provider_windows.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';
import 'package:shared_preferences_windows/shared_preferences_windows.dart';
import 'package:uri_ui/living/companion/companion_design.dart';
import 'package:uri_ui/living/companion/companion_orb.dart' show CompanionIdentity;
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/main.dart' as app;
import 'package:uri_ui/working_system_app.dart';

class QualificationPaths extends PathProviderWindows {
  @override
  Future<String?> getApplicationSupportPath() async => Platform.environment['URI_QUAL_PREFS'];
}

const _companionWindow = MethodChannel('uri/companion_window');

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  binding.framePolicy = LiveTestWidgetsFlutterBindingFramePolicy.fullyLive;
  // Real OS input (the Win32 probe's SendInput clicks and drags) must reach the app; the live test binding drops
  // device pointer events by default (run l3-input: 0 events received).
  binding.shouldPropagateDevicePointerEvents = true;
  testWidgets('EMBER-V21-INTEG: production main, real worker, Core and Brain', (t) async {
    final out = Directory(Platform.environment['URI_QUAL_UI_OUT']!)..createSync(recursive: true);
    final mode = Platform.environment['URI_QUAL_MODE'] ?? 'first';
    final rows = <Map<String, Object?>>[];
    final failures = <String>[];
    final oldOnError = FlutterError.onError;
    FlutterError.onError = (d) {
      final full = d.toString();
      rows.add({'utc': DateTime.now().toUtc().toIso8601String(), 'label': 'flutter-error', 'error': d.exceptionAsString(),
        'detail': full.length > 4000 ? full.substring(0, 4000) : full});
    };
    void record(String label, Map<String, Object?> fields) {
      rows.add({'utc': DateTime.now().toUtc().toIso8601String(), 'label': label, ...fields});
      File('${out.path}/observations-$mode.json').writeAsStringSync(const JsonEncoder.withIndent('  ').convert(rows));
    }
    void check(String id, bool ok, [Map<String, Object?> detail = const {}]) {
      record('check', {'id': id, 'result': ok ? 'PASS' : 'FAIL', ...detail});
      if (!ok) failures.add(id);
    }
    Future<void> until(bool Function() ok, String label, {int seconds = 240}) async {
      final end = DateTime.now().add(Duration(seconds: seconds));
      while (!ok()) {
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: $label');
        await t.pump(const Duration(milliseconds: 100));
      }
    }
    Future<void> settle([int ms = 800]) async {
      for (var i = 0; i < ms ~/ 100; i++) {
        await t.pump(const Duration(milliseconds: 100));
      }
    }
    Future<void> shot(String name) async {
      await settle(400);
      final view = t.binding.renderViews.first;
      final im = await (view.debugLayer! as OffsetLayer).toImage(Offset.zero & view.size, pixelRatio: 1);
      final bytes = await im.toByteData(format: ui.ImageByteFormat.png);
      File('${out.path}/$mode-$name.png').writeAsBytesSync(bytes!.buffer.asUint8List());
    }
    Future<void> step(String id, Future<void> Function() body) async {
      try {
        await body();
      } catch (e, s) {
        check(id, false, {'exception': '$e', 'stack': '$s'.split('\n').take(6).join(' | ')});
      }
    }
    Future<Map<String, Object?>> facts() async {
      try {
        final f = await _companionWindow.invokeMethod<Map<Object?, Object?>>('facts');
        return {for (final e in (f ?? const {}).entries) '${e.key}': e.value};
      } catch (e) {
        return {'error': '$e'};
      }
    }
    // Handshake with the outer Win32 probe.
    Future<Map<String, Object?>> probe(String name, Map<String, Object?> info, {int seconds = 180}) async {
      final done = File('${out.path}/probe-$name.done.json');
      if (done.existsSync()) done.deleteSync();
      File('${out.path}/probe-$name.json').writeAsStringSync(jsonEncode({'step': name, 'pid': pid, ...info,
        'facts': await facts(), 'utc': DateTime.now().toUtc().toIso8601String()}));
      await until(() => done.existsSync(), 'probe $name', seconds: seconds);
      await settle(300);
      final r = jsonDecode(done.readAsStringSync()) as Map<String, Object?>;
      record('probe', {'step': name, 'result': r});
      return r;
    }

    record('automation input transport', {
      'driver': 'Flutter integration_test on production main()', 'window_checks': 'tools/win_probe.py (Win32 + SendInput)',
      'physical_keyboard_qualified': false, 'physical_mouse_qualified': false, 'microphone_qualified': false,
      'Brain_Core_worker_mocked': false, 'mode': mode,
    });
    SharedPreferencesStorePlatform.instance = SharedPreferencesWindows()..pathProvider = QualificationPaths();
    final prefs = await SharedPreferences.getInstance();
    record('preferences at start', {'keys': prefs.getKeys().toList()..sort(),
      'choice': prefs.getString(CompanionPreferences.keyChoice)});
    final sw = Stopwatch()..start();
    app.main();
    await until(() => find.byType(WorkingSystemRoot).evaluate().isNotEmpty, 'production manifest opt-in');
    await until(() => find.byType(LivingScope).evaluate().isNotEmpty, 'real integrated worker bootstrap');
    final services = t.widget<LivingScope>(find.byType(LivingScope).first).services;
    final OiConversation conv = services.oi!;
    record('production main connected', {
      'seconds_to_living_scope': sw.elapsedMilliseconds / 1000, 'visualV2': services.visualV2,
      'mode': services.presentation.mode.name, 'brain_status': conv.brainStatus,
      'restored_choice': services.companionPrefs.choice.identity?.name,
    });
    // Companion signal timeline (every change of state, headline or detail).
    final timeline = <Map<String, Object?>>[];
    CompanionSignal? last;
    void sample() {
      final s = services.companion.signal;
      if (last == null || last!.state != s.state || last!.headline != s.headline || last!.detail != s.detail) {
        last = s;
        timeline.add({'utc': DateTime.now().toUtc().toIso8601String(), 't_s': sw.elapsedMilliseconds / 1000,
          'state': s.state.name, 'headline': s.headline, 'detail': s.detail, 'source': s.sourceName,
          'simulated': s.simulated, 'brain_status': conv.brainStatus['state'], 'readiness': conv.brainHealth['readiness'],
          'host': (conv.brainHealth['host'] is Map) ? (conv.brainHealth['host'] as Map)['state'] : null});
        File('${out.path}/companion-timeline-$mode.json').writeAsStringSync(const JsonEncoder.withIndent('  ').convert(timeline));
      }
    }
    services.companion.addListener(sample);
    conv.addListener(sample);
    sample();
    bool seen(CompanionState st, {int from = 0}) => timeline.skip(from).any((r) => r['state'] == st.name);
    final ember = const CompanionChoice.living(CompanionIdentity.ember);

    await step('G-installed', () async {
      final ids = CompanionDesign.installed.map((d) => d.id).toList();
      check('G-installed-12-with-ember', CompanionDesign.installed.length == 12 &&
          CompanionDesign.installed.any((d) => '${d.id}'.toLowerCase().contains('ember')), {'ids': '$ids'});
    });

    Future<void> windowChecks() async {
      await step('W-window', () async {
        // Still frames for the alpha recovery (two captures over different backdrops must show the same frame).
        services.effects.setReducedMotion(true);
        await settle(3000);
        final r = await probe('transparent-1.0', {'scale': 1.0}, seconds: 300);
        check('W-borderless', r['borderless'] == true, {'probe': r['borderless_detail']});
        check('W-per-pixel-transparency', r['per_pixel_transparent'] == true, {'probe': r['alpha_summary']});
        final c = await probe('click-through', {}, seconds: 300);
        check('W-click-through-outside', c['outside_reached_backdrop'] == true, {'probe': c});
        check('W-click-on-ember-reaches-uri', c['ember_click_reached_uri'] == true, {'probe': c});
        await settle(1500);
        record('controls after Ember click', {
          'chat_control_visible': find.byKey(const ValueKey('a2ui.companion-controls.chat')).evaluate().isNotEmpty,
          'facts': await facts()});
        await shot('w-after-ember-click');
        final d = await probe('drag', {}, seconds: 300);
        check('W-drag-moves-window', d['moved'] == true, {'probe': d});
      });
      await step('W-scale-1.25', () async {
        services.companionPrefs.setLook(ember, services.companionPrefs.lookFor(ember).copyWith(size: 1.25));
        await settle(2500);
        final r = await probe('transparent-1.25', {'scale': 1.25}, seconds: 300);
        check('W-scale-1.25-transparent', r['per_pixel_transparent'] == true, {'probe': r['alpha_summary']});
        record('F-SIZE-1 measurement', {'crop': r['crop']});
        services.companionPrefs.setLook(ember, services.companionPrefs.lookFor(ember).copyWith(size: 1));
        services.effects.setReducedMotion(false);
        await settle(1500);
      });
    }

    if (mode == 'input') {
      // Input diagnosis: every pointer event Flutter receives, while the probe sends real OS input.
      final events = <Map<String, Object?>>[];
      void route(PointerEvent e) => events.add({'utc': DateTime.now().toUtc().toIso8601String(),
        'type': e.runtimeType.toString(), 'pos': [e.position.dx, e.position.dy], 'kind': e.kind.name, 'buttons': e.buttons});
      GestureBinding.instance.pointerRouter.addGlobalRoute(route);
      services.presentation.setMode(UiPresentationMode.companion);
      services.effects.setReducedMotion(true);
      await settle(3000);
      final layout = await facts();
      final r = await probe('input-diag', {'note': 'click and drag on Ember with pointer logging'}, seconds: 300);
      await settle(1500);
      record('input diagnosis', {'probe': r, 'flutter_pointer_events': events, 'facts_before': layout,
        'chat_control_visible': find.byKey(const ValueKey('a2ui.companion-controls.chat')).evaluate().isNotEmpty});
      await shot('input-after');
      GestureBinding.instance.pointerRouter.removeGlobalRoute(route);
    } else if (mode == 'returning') {
      await step('R-restored', () async {
        check('R-ember-restored', services.companionPrefs.choice.identity == CompanionIdentity.ember,
            {'choice': services.companionPrefs.choice.identity?.name});
        services.presentation.setMode(UiPresentationMode.companion);
        await settle(2500);
        await shot('returning-companion');
        await probe('returning', {'scale': services.companionPrefs.look.size});
      });
      // Window checks again, in the idle state with our Brain READY (run 1 probe attempt 1 was invalid: occluded).
      File('${out.path}/ui-ready.json').writeAsStringSync(jsonEncode({'utc': DateTime.now().toUtc().toIso8601String(), 'pid': pid}));
      await step('R-brain-idle', () async {
        await until(() => File('${out.path}/brain-ready.json').existsSync(), 'brain-ready', seconds: 1500);
        await until(() => services.companion.signal.state == CompanionState.idle, 'companion idle', seconds: 300);
        check('R-idle-after-ready', services.companion.signal.state == CompanionState.idle);
        check('R-initializing-seen', seen(CompanionState.initializing));
      });
      await windowChecks();
    } else {
      await step('J0-select-ember', () async {
        services.companionPrefs.select(ember);
        services.companionPrefs.setLook(ember, services.companionPrefs.lookFor(ember).copyWith(size: 1));
        await services.companionPrefs.pendingWrite;
        services.presentation.setMode(UiPresentationMode.companion);
        await settle(2500);
        check('J0-ember-selected', services.companionPrefs.choice.identity == CompanionIdentity.ember);
        check('J0-companion-mode', services.presentation.mode == UiPresentationMode.companion);
        record('companion window facts', await facts());
        await shot('j0-companion-before-brain');
      });
      File('${out.path}/ui-ready.json').writeAsStringSync(jsonEncode({'utc': DateTime.now().toUtc().toIso8601String(), 'pid': pid}));
      await step('J1-brain-start', () async {
        final brainReady = File('${out.path}/brain-ready.json');
        await until(() => brainReady.existsSync(), 'brain-ready', seconds: 1500);
        await until(() => services.companion.signal.state == CompanionState.idle, 'companion idle', seconds: 300);
        check('J1-initializing-seen', seen(CompanionState.initializing));
        check('J1-idle-after-ready', services.companion.signal.state == CompanionState.idle);
        record('brain ready', {'file': jsonDecode(brainReady.readAsStringSync())});
        await shot('j1-idle');
      });
      await windowChecks();
      Future<Map<String, Object?>> turn(String id, String text) async {
        final from = timeline.length;
        final before = conv.messages.length;
        await conv.send(text);
        await until(() => conv.messages.length > before && conv.activeTurnId == null &&
            conv.messages.last.role == OiRole.uri && conv.messages.last.finishedStatus != null, 'turn $id', seconds: 300);
        await settle(1500);
        final m = conv.messages.last;
        final states = timeline.skip(from).map((r) => r['state']).toList();
        record('turn', {'id': id, 'text': text, 'status': m.finishedStatus, 'reply': m.text, 'states': states});
        return {'status': m.finishedStatus, 'states': states};
      }
      await step('J2-conversation', () async {
        final r = await turn('hello', 'Say hello in three words.');
        final states = r['states'] as List;
        check('J2-turn-ok', r['status'] == 'ok', r);
        check('J2-thinking-seen', states.contains('thinking'), r);
        check('J2-success-seen', states.contains('success'), r);
        record('speaking seen (not gated: short replies may skip it)', {'speaking': states.contains('speaking')});
        await settle(5000);
        check('J2-back-to-idle', services.companion.signal.state == CompanionState.idle);
      });
      await step('J3-brain-stopped', () async {
        final from = timeline.length;
        File('${out.path}/stop-brain.json').writeAsStringSync(jsonEncode({'utc': DateTime.now().toUtc().toIso8601String()}));
        await until(() => [CompanionState.unavailable, CompanionState.error].contains(services.companion.signal.state),
            'unavailable after stop', seconds: 300);
        await settle(2000);
        check('J3-unavailable-or-error', [CompanionState.unavailable, CompanionState.error].contains(services.companion.signal.state),
            {'signal': services.companion.signal.state.name, 'detail': services.companion.signal.detail});
        check('J3-never-initializing-while-stopping', !seen(CompanionState.initializing, from: from) ||
            timeline.skip(from).takeWhile((r) => r['state'] != 'unavailable' && r['state'] != 'error').every((r) => r['state'] != 'initializing'));
        await shot('j3-unavailable');
        await probe('unavailable', {'scale': 1.0});
      });
      await step('J4-recovery', () async {
        final from = timeline.length;
        File('${out.path}/restart-brain.json').writeAsStringSync(jsonEncode({'utc': DateTime.now().toUtc().toIso8601String()}));
        await until(() => File('${out.path}/brain-ready-1.json').existsSync(), 'brain-ready-1', seconds: 1500);
        await until(() => services.companion.signal.state == CompanionState.idle, 'idle after recovery', seconds: 300);
        check('J4-initializing-during-restart', seen(CompanionState.initializing, from: from));
        final r = await turn('recovery', 'What is 7 plus 8? Answer with the number only.');
        check('J4-turn-ok-after-recovery', r['status'] == 'ok', r);
      });
      await step('J5-persisted', () async {
        await services.companionPrefs.pendingWrite;
        final p = await SharedPreferences.getInstance();
        await p.reload();
        check('J5-choice-persisted', (p.getString(CompanionPreferences.keyChoice) ?? '').contains('ember'),
            {'stored': p.getString(CompanionPreferences.keyChoice)});
      });
    }
    record('final', {'failures': failures, 'timeline_rows': timeline.length});
    File('${out.path}/ui-finished.json').writeAsStringSync(jsonEncode({'utc': DateTime.now().toUtc().toIso8601String(),
      'failures': failures}));
    services.companion.removeListener(sample);
    conv.removeListener(sample);
    FlutterError.onError = oldOnError;
    await settle(2000);
  }, timeout: const Timeout(Duration(minutes: 90)));
}
