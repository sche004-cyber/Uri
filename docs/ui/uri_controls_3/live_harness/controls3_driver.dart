// URI-CONTROLS-3 live driver (temporary, external; copied into uri_ui/integration_test by run_qc_ui.py and removed
// afterwards). Based on the UI-CONTROLS-TYPO driver (docs/ui/controls_typography_20261018/evidence/live_harness).
// Calls the ORIGINAL production main() of the candidate with the real integrated worker, paired Core and the real
// Runtime v1 Brain started by the production Brain host. Input: flutter_test taps, synthesized key events
// (sendKeyEvent), a synthesized mouse for hover, semantics actions, and TestTextInput: automation only, never a
// physical keyboard, mouse or screen reader.
//
// Journey: ready (exactly Thinking / Vision / URI Assist; Vision glows; Thinking Off; Assist off) -> semantics of the
// three toggles -> Thinking On by keyboard (Space) and a turn -> Thinking Off by click and a fact turn -> Vision off
// (Long context; the session host fails that start once on purpose) -> URI goes back by itself -> Vision off by
// keyboard (Enter) -> real switch to Long -> recall -> Vision on by a screen-reader tap action -> Standard -> recall ->
// URI Assist on (opens the consent view; a grant only through the worker's own targets) and off -> worker restart:
// controls consistent and responsive -> recall after the restart.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path_provider_windows/path_provider_windows.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';
import 'package:shared_preferences_windows/shared_preferences_windows.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/qc_toggle.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/main.dart' as app;
import 'package:uri_ui/working_system_app.dart';

class QualificationPaths extends PathProviderWindows {
  @override
  Future<String?> getApplicationSupportPath() async => Platform.environment['URI_QUAL_PREFS'];
}

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  binding.framePolicy = LiveTestWidgetsFlutterBindingFramePolicy.fullyLive;
  testWidgets('URI-CONTROLS-3: Thinking / Vision / URI Assist on the production main with the real Brain', (t) async {
    final out = Directory(Platform.environment['URI_QUAL_UI_OUT']!)..createSync(recursive: true);
    final rows = <Map<String, Object?>>[];
    final failures = <String>[];
    final oldOnError = FlutterError.onError;
    FlutterError.onError = (d) {
      rows.add({'utc': DateTime.now().toUtc().toIso8601String(), 'label': 'flutter-error', 'error': d.exceptionAsString()});
    };
    void record(String label, Map<String, Object?> fields) {
      rows.add({'utc': DateTime.now().toUtc().toIso8601String(), 't': DateTime.now().millisecondsSinceEpoch / 1000,
        'label': label, ...fields});
      File('${out.path}/observations.json').writeAsStringSync(const JsonEncoder.withIndent('  ').convert(rows));
    }
    void check(String id, bool ok, [Map<String, Object?> detail = const {}]) {
      record('check', {'id': id, 'result': ok ? 'PASS' : 'FAIL', ...detail});
      if (!ok) failures.add(id);
    }
    Future<void> settle([int ms = 800]) async {
      for (var i = 0; i < ms ~/ 100; i++) {
        await t.pump(const Duration(milliseconds: 100));
      }
    }
    Future<void> until(bool Function() ok, String label, {int seconds = 240}) async {
      final end = DateTime.now().add(Duration(seconds: seconds));
      while (!ok()) {
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: $label');
        await t.pump(const Duration(milliseconds: 100));
      }
    }
    Future<void> shot(String name) async {
      await settle(400);
      final view = t.binding.renderViews.first;
      final im = await (view.debugLayer! as OffsetLayer).toImage(Offset.zero & view.size, pixelRatio: 1);
      final bytes = await im.toByteData(format: ui.ImageByteFormat.png);
      File('${out.path}/$name.png').writeAsBytesSync(bytes!.buffer.asUint8List());
    }
    Future<void> step(String id, Future<void> Function() body) async {
      try {
        await body();
      } catch (e, s) {
        check(id, false, {'exception': '$e', 'stack': '$s'.split('\n').take(6).join(' | ')});
      }
    }
    QcToggle? toggle(String key) {
      final f = find.byKey(ValueKey(key));
      return f.evaluate().isEmpty ? null : t.widget<QcToggle>(f.first);
    }
    List<String> toggleKeys() => [
          for (final w in t.widgetList<QcToggle>(find.byType(QcToggle))) '${(w.key as ValueKey).value}'
        ];
    String? textOf(String key) {
      final own = find.byKey(ValueKey(key));
      if (own.evaluate().isNotEmpty && own.evaluate().first.widget is Text) {
        return (own.evaluate().first.widget as Text).data;
      }
      final f = find.descendant(of: own, matching: find.byType(Text));
      if (f.evaluate().isEmpty) return null;
      return [for (final e in f.evaluate()) (e.widget as Text).data ?? ''].join(' | ');
    }
    List<String?> dialogTexts() => [
          for (final e in find.descendant(of: find.byKey(const ValueKey('qc-confirm-switch')),
              matching: find.byType(Text)).evaluate()) (e.widget as Text).data
        ];
    // Keyboard: focus the toggle's own focus node (as Tab would), then a synthesized key event.
    Future<bool> keyOn(String key, LogicalKeyboardKey k) async {
      final inner = find.descendant(of: find.byKey(ValueKey(key)), matching: find.byType(AnimatedContainer)).first;
      final node = Focus.of(t.element(inner));
      node.requestFocus();
      await settle(300);
      final focused = node.hasPrimaryFocus;
      final ring = t.widget<AnimatedContainer>(inner).foregroundDecoration != null;
      await t.sendKeyEvent(k);
      await settle(600);
      record('keyboard', {'toggle': key, 'key': k.keyLabel, 'focused': focused, 'focus_ring': ring});
      return focused && ring;
    }

    t.testTextInput.register();
    addTearDown(t.testTextInput.unregister);
    final semantics = t.ensureSemantics();
    record('automation input transport', {
      'keyboard': 'Flutter sendKeyEvent + TestTextInput', 'pointer': 'flutter_test tap and synthesized mouse hover',
      'screen_reader': 'semantics tree + SemanticsAction.tap (no Narrator)',
      'physical_keyboard_qualified': false, 'physical_mouse_qualified': false, 'narrator_qualified': false,
      'Brain_Core_worker_mocked': false,
    });
    SharedPreferencesStorePlatform.instance = SharedPreferencesWindows()..pathProvider = QualificationPaths();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('uri.living.onboardingDone', true);
    app.main();
    await until(() => find.byType(WorkingSystemRoot).evaluate().isNotEmpty, 'production manifest opt-in');
    await until(() => find.byType(LivingScope).evaluate().isNotEmpty, 'real integrated worker bootstrap');
    final services = t.widget<LivingScope>(find.byType(LivingScope).first).services;
    final conv = services.oi!;
    final session0 = conv.sessionId;
    await until(() => find.byKey(LivingShell.orbKey).evaluate().isNotEmpty, 'living shell');
    await settle(1500);
    final onboarding = find.byKey(const ValueKey('onboarding-skip'));
    if (onboarding.evaluate().isNotEmpty) {
      await t.tap(onboarding);
      await settle(1200);
    }
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
    await settle(1500);
    record('window', {'logical_size': '${t.binding.renderViews.first.size}', 'mode': services.presentation.mode.name});

    Future<Map<String, dynamic>> health() async {
      await t.runAsync(() => conv.refreshHealth());
      await t.pump();
      return conv.brainHealth;
    }
    String? activeId() => (conv.brainControls['active'] as Map?)?['id'] as String?;
    bool pending() => (conv.brainControls['switch'] as Map?)?['pending'] == true;
    Map<String, Object?> uiRow(Map<String, dynamic> h) => {
          't': DateTime.now().millisecondsSinceEpoch / 1000, 'state': h['state'], 'active': activeId(),
          'pending': pending(), 'configured': (conv.brainControls['configured'] as Map?)?['id'],
          'last': (conv.brainControls['switch'] as Map?)?['last'],
          'vision_visual': toggle('qc-vision')?.visual.name, 'vision_status': toggle('qc-vision')?.status,
          'thinking_visual': toggle('qc-thinking')?.visual.name, 'assist_visual': toggle('qc-assist')?.visual.name,
          'assist_status': toggle('qc-assist')?.status, 'worker_assist': conv.brainControls['assist'],
          'switching_text': textOf('qc-switching'), 'notice': textOf('qc-notice'), 'mismatch': textOf('qc-mismatch'),
          'header_brain': conv.brainStatus['state'],
        };
    // Glow honesty over a timeline: Vision glows only when the verified active profile has vision on; while a switch
    // is pending it shows loading.
    Map<String, Object?> honesty(List<Map<String, Object?>> rowsT) {
      final bad = <Map<String, Object?>>[];
      for (final r in rowsT) {
        final a = r['active'];
        final std = a == 'standard' || a == 'standard-nodraft';
        final visOk = r['vision_visual'] != 'on' || (std && r['pending'] != true);
        final pendOk = r['pending'] != true || r['vision_visual'] == 'loading';
        if (!(visOk && pendOk)) bad.add(r);
      }
      return {'rows': rowsT.length, 'violations': bad.length, 'first_violation': bad.isEmpty ? null : bad.first};
    }

    Future<OiMessage> send(String scenario, String text) async {
      final count = conv.messages.length;
      final timer = Stopwatch()..start();
      await t.enterText(find.byKey(const ValueKey('living-composer-field')).first, text);
      await t.pump();
      await t.tap(find.byKey(const ValueKey('living-composer-send')).first);
      await t.pump(const Duration(milliseconds: 100));
      await until(() => conv.messages.length > count, 'submitted');
      await until(() => !conv.busy, 'terminal', seconds: 300);
      await settle(600);
      final m = conv.messages.skip(count).lastWhere((x) => x.role == OiRole.uri, orElse: () => conv.messages.last);
      record('turn', {
        'scenario': scenario, 'request': text, 'text': m.text, 'route': m.route, 'tier': m.tier,
        'status': m.finishedStatus, 'answer_status': m.answerStatus, 'metrics': m.metrics,
        'depth_sent': conv.depth.name, 'seconds': timer.elapsedMilliseconds / 1000, 'error': m.errorCode,
      });
      return m;
    }

    var startId = 'standard';
    String startLabel() => startId == 'standard' ? 'Standard' : 'Standard, draft off';
    Future<void> waitServing(String label, {int seconds = 600}) async {
      final end = DateTime.now().add(Duration(seconds: seconds));
      while (!(activeId() != null && !pending() && (conv.healthState == 'READY' || conv.healthState == 'DEGRADED'))) {
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: $label');
        await health();
        await t.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 700)));
      }
    }
    await step('C3-ready', () async {
      await waitServing('start profile ready');
      startId = activeId()!;
      await settle(800);
      record('start-profile', {'id': startId});
      check('C3-exactly-three-controls', toggleKeys().join(',') == 'qc-thinking,qc-vision,qc-assist' &&
          find.byKey(const ValueKey('qc-context')).evaluate().isEmpty &&
          find.byKey(const ValueKey('qc-draft')).evaluate().isEmpty, {'toggles': toggleKeys()});
      check('C3-ready-visuals', toggle('qc-vision')?.visual == QcVisual.on &&
          toggle('qc-thinking')?.visual == QcVisual.off && toggle('qc-thinking')?.status == null &&
          toggle('qc-assist')?.visual == QcVisual.off && toggle('qc-assist')?.onPressed != null &&
          conv.depth == OiDepth.fast, uiRow(conv.brainHealth));
      await shot('01-ready-three-controls');
    });

    await step('C3-semantics', () async {
      final res = <String, Object?>{};
      var ok = true;
      for (final e in {'qc-thinking': 'Thinking', 'qc-vision': 'Vision', 'qc-assist': 'URI Assist'}.entries) {
        final n = t.getSemantics(find.byKey(ValueKey(e.key)));
        final d = n.getSemanticsData();
        final good = d.label == e.value && d.hasFlag(SemanticsFlag.isButton) &&
            d.hasFlag(SemanticsFlag.hasToggledState) && d.hasFlag(SemanticsFlag.isFocusable) &&
            d.hasAction(SemanticsAction.tap);
        res[e.key] = {'label': d.label, 'value': d.value, 'toggled': d.hasFlag(SemanticsFlag.isToggled),
          'tap': d.hasAction(SemanticsAction.tap), 'focusable': d.hasFlag(SemanticsFlag.isFocusable)};
        ok &= good;
      }
      check('C3-semantics-toggle-buttons', ok, res);
    });

    const secret = '4817';
    await step('C3-thinking', () async {
      final kb = await keyOn('qc-thinking', LogicalKeyboardKey.space);
      check('C3-thinking-on-by-keyboard', kb && conv.depth == OiDepth.normal &&
          toggle('qc-thinking')?.visual == QcVisual.on, {'depth': conv.depth.name});
      await shot('02-thinking-on-focus');
      final b = await send('thinking-on', 'Compare a bicycle and an electric scooter for a 3 km city commute in two short sentences.');
      check('C3-thinking-on-tier', b.tier == 'NORMAL', {'tier': b.tier, 'route': b.route});
      await t.tap(find.byKey(const ValueKey('qc-thinking')));
      await settle(600);
      check('C3-thinking-off-click', conv.depth == OiDepth.fast && toggle('qc-thinking')?.visual == QcVisual.off);
      final a = await send('tell-fact', 'Quick arithmetic game. The secret number is $secret. Reply with just OK.');
      check('C3-thinking-off-tier', a.tier == 'FAST', {'tier': a.tier, 'route': a.route});
      check('C3-thinking-persisted', prefs.getString('uri.living.thinking') == 'fast' ||
          (await t.runAsync(() async => (await SharedPreferences.getInstance()).getString('uri.living.thinking'))) ==
              'fast');
    });

    Future<List<Map<String, Object?>>> waitDone(String label, {int seconds = 900}) async {
      final rowsT = <Map<String, Object?>>[];
      final end = DateTime.now().add(Duration(seconds: seconds));
      var seenPending = false;
      while (true) {
        final h = await health();
        rowsT.add(uiRow(h));
        seenPending |= pending();
        final last = (conv.brainControls['switch'] as Map?)?['last'] as Map?;
        final mine = last != null && last['id'] == conv.profileRequestId;
        final refused = mine && '${last['result']}'.startsWith('REFUSED_');
        if (!pending() && (refused || (seenPending && activeId() != null &&
            (h['state'] == 'READY' || h['state'] == 'DEGRADED')))) {
          break;
        }
        if (conv.profileNotice != null && !pending()) break;
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: $label ${jsonEncode(rowsT.last)}');
        await t.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 700)));
        await t.pump();
      }
      await settle(600);
      return rowsT;
    }
    Future<List<Map<String, Object?>>> confirmAndWait(String label, String shotName) async {
      await shot(shotName);
      await t.tap(find.byKey(const ValueKey('qc-confirm-switch-go')));
      await settle(300);
      final tl = await waitDone(label);
      record('switch-timeline', {'label': label, 'rows': tl, 'last': (conv.brainControls['switch'] as Map?)?['last'],
        'active': activeId(), 'notice': textOf('qc-notice')});
      check('C3-glow-honest-$label', (honesty(tl)['violations'] as int) == 0, honesty(tl));
      return tl;
    }

    await step('C3-vision-off-failed-start-restored', () async {
      await t.tap(find.byKey(const ValueKey('qc-vision')));
      await settle(800);
      final texts = dialogTexts();
      check('C3-confirm-coupled-change', texts.contains('Switch the Brain to Long context?') &&
          texts.contains('64K') && texts.contains('Off'), {'texts': texts});
      final tl = await confirmAndWait('restore', '03-confirm-vision-off-long');
      final last = (conv.brainControls['switch'] as Map?)?['last'] as Map?;
      check('C3-failed-start-restored', last?['result'] == 'FAILED' && last?['restored'] == true &&
          (last?['fallback'] as Map?)?['result'] == 'READY' && activeId() == startId, {'last': last});
      check('C3-switching-indicated', tl.any((r) => r['vision_visual'] == 'loading'));
      check('C3-restored-notice', (textOf('qc-notice') ?? '').contains('went back to ${startLabel()}'),
          {'notice': textOf('qc-notice')});
      check('C3-restored-visuals', toggle('qc-vision')?.visual == QcVisual.on);
      await shot('04-restored');
    });

    await step('C3-vision-off-by-keyboard', () async {
      final kb = await keyOn('qc-vision', LogicalKeyboardKey.enter);
      check('C3-vision-enter-opens-confirm', kb && find.byKey(const ValueKey('qc-confirm-switch')).evaluate().isNotEmpty,
          {'texts': dialogTexts()});
      await confirmAndWait('long', '05-confirm-vision-off-keyboard');
      check('C3-long-visuals', activeId() == 'long' && toggle('qc-vision')?.visual == QcVisual.off,
          uiRow(conv.brainHealth));
      await shot('06-long-ready');
      final r = await send('recall-long', 'What was the secret number I gave you at the start of this conversation? Reply with the number only.');
      check('C3-continuity-long', r.text.contains(secret) && r.route == 'answer', {'answer': r.text, 'route': r.route});
    });

    await step('C3-vision-on-by-screen-reader', () async {
      final node = t.getSemantics(find.byKey(const ValueKey('qc-vision')));
      t.binding.renderViews.first.owner!.semanticsOwner!.performAction(node.id, SemanticsAction.tap);
      await settle(800);
      check('C3-semantics-tap-opens-confirm', dialogTexts().contains('Switch the Brain to Standard?'),
          {'texts': dialogTexts()});
      await confirmAndWait('vision-on', '07-confirm-vision-on');
      final last = (conv.brainControls['switch'] as Map?)?['last'] as Map?;
      final refused = '${last?['result']}'.startsWith('REFUSED_');
      record('vision-on-outcome', {'result': last?['result'], 'active': activeId(), 'notice': textOf('qc-notice')});
      if (refused) {
        check('C3-refusal-keeps-long', activeId() == 'long' && toggle('qc-vision')?.visual == QcVisual.off,
            {'notice': textOf('qc-notice'), 'last': last});
      } else {
        check('C3-standard-visuals', activeId() == 'standard' && toggle('qc-vision')?.visual == QcVisual.on);
      }
      final r = await send('recall-2', 'Once more: what was the secret number I gave you at the start of this conversation? Reply with the number only.');
      check('C3-continuity-2', r.text.contains(secret) && r.route == 'answer', {'answer': r.text, 'route': r.route});
    });

    await step('C3-assist', () async {
      final assist = services.assist!;
      await t.tap(find.byKey(const ValueKey('qc-assist')));
      await settle(1500);
      await until(() => !assist.busy, 'assist status', seconds: 30);
      check('C3-assist-on-opens-consent', services.presentation.mode == UiPresentationMode.assist && assist.loaded &&
          assist.off, {'mode': services.presentation.mode.name, 'state': assist.state, 'error': assist.lastError});
      await shot('08-assist-consent-view');
      // The user's choice in the consent view = a grant on a target the worker itself lists (same calls as the view).
      String? granted;
      final listed = <String, Object?>{};
      for (final kind in ['desktop_window', 'browser_tab']) {
        await t.runAsync(() => assist.listTargets(kind));
        await t.pump();
        listed[kind] = {'n': assist.targets.length, 'error': assist.lastError};
        if (assist.targets.isNotEmpty) {
          final id = '${assist.targets.first['id'] ?? assist.targets.first['target_id']}';
          await t.runAsync(() => assist.grant(kind, id, suggest: false));
          await t.pump();
          if (assist.active) {
            granted = kind;
            break;
          }
          listed['${kind}_grant_error'] = assist.lastError;
        }
      }
      record('assist-targets', {'listed': listed, 'granted': granted, 'state': assist.state});
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await settle(1500);
      await health();
      if (granted != null) {
        check('C3-assist-on-glow-from-worker', toggle('qc-assist')?.visual == QcVisual.on &&
            conv.brainControls['vision_locked'] == true && toggle('qc-vision')?.onPressed == null,
            uiRow(conv.brainHealth));
        await shot('09-assist-on');
        await t.tap(find.byKey(const ValueKey('qc-assist')));
        await settle(1200);
        await health();
        check('C3-assist-off-revokes', assist.off && toggle('qc-assist')?.visual == QcVisual.off &&
            conv.brainControls['vision_locked'] != true, uiRow(conv.brainHealth));
      } else {
        // No target to grant (perception adapters unavailable on this build, finding D14): the toggle stays off,
        // never glows without a grant.
        check('C3-assist-no-grant-stays-off', toggle('qc-assist')?.visual == QcVisual.off &&
            conv.brainControls['vision_locked'] != true, {'listed': listed, ...uiRow(conv.brainHealth)});
      }
      await shot('10-assist-off');
    });

    await step('C3-worker-restart', () async {
      final runtimeBefore = conv.runtime;
      await t.tap(find.byKey(const ValueKey('qc-thinking')));          // On before the restart
      await settle(600);
      await t.runAsync(() => conv.restartWorker());
      await until(() => !conv.restarting && !identical(conv.runtime, runtimeBefore), 'worker restarted', seconds: 180);
      await waitServing('serving after the restart');
      await settle(1500);
      check('C3-restart-consistent', !identical(conv.runtime, runtimeBefore) && conv.depth == OiDepth.normal &&
          toggle('qc-thinking')?.visual == QcVisual.on && toggle('qc-assist')?.visual == QcVisual.off &&
          toggle('qc-vision')?.visual == ((activeId() == 'long') ? QcVisual.off : QcVisual.on) &&
          toggleKeys().join(',') == 'qc-thinking,qc-vision,qc-assist', uiRow(conv.brainHealth));
      check('C3-restart-responsive', toggle('qc-thinking')?.onPressed != null &&
          toggle('qc-vision')?.onPressed != null && toggle('qc-assist')?.onPressed != null);
      await t.tap(find.byKey(const ValueKey('qc-thinking')));
      await settle(600);
      check('C3-restart-thinking-toggles', conv.depth == OiDepth.fast);
      final r = await send('after-restart', 'Reply with exactly the word ready.');
      check('C3-turn-after-restart', r.text.toLowerCase().contains('ready'), {'text': r.text});
      await shot('11-after-restart');
    });

    check('C3-no-mismatch-line', find.byKey(const ValueKey('qc-mismatch')).evaluate().isEmpty,
        {'mismatch': textOf('qc-mismatch')});
    final errors = rows.where((r) => r['label'] == 'flutter-error').toList();
    check('C3-no-flutter-errors', errors.isEmpty, {'count': errors.length, 'first': errors.isEmpty ? null : errors.first});
    record('final', {'failures': failures, 'controls': conv.brainControls, 'health_state': conv.healthState,
      'session_before': session0, 'session_after': conv.sessionId});
    File('${out.path}/ui-finished.json').writeAsStringSync(jsonEncode({'by': 'driver', 'failures': failures,
      'utc': DateTime.now().toUtc().toIso8601String()}));
    semantics.dispose();
    FlutterError.onError = oldOnError;
    expect(failures, isEmpty);
  }, timeout: const Timeout(Duration(minutes: 45)));
}
