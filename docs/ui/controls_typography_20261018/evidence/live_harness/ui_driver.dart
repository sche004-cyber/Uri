// UI-CONTROLS-TYPO-20261018 live driver (temporary, external; copied into uri_ui/integration_test by run_qc_ui.py and
// removed afterwards). Based on the BRAIN-QC live driver. Calls the ORIGINAL production main() of the candidate with
// the real integrated worker, paired Core and the real Runtime v1 Brain started by the production Brain host. Input:
// flutter_test taps, a synthesized mouse for hover, and TestTextInput (automation), never a physical keyboard/mouse.
//
// Journey: Standard ready (Vision glows, 32K selected) -> Thinking toggle On (glow) turn -> Thinking toggle Off turn
// (tell a fact) -> tooltip on hover -> Vision toggle off (=> Long context, confirmation states the coupled change) ->
// the session host fails that start on purpose (--inject-fail-once) -> URI goes back to Standard by itself (glow only
// after it is verified again) -> Context 64K selection (real switch) -> recall -> Vision toggle on (=> Standard, the
// unqualified 64K + vision is explained) -> recall -> Thinking Auto -> typography tour of the surfaces.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
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
  testWidgets('UI-TYPO: push-to-enable controls and typography on the production main with the real Brain', (t) async {
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
    QcSegmented? ctxGroup() {
      final f = find.byKey(const ValueKey('qc-context'));
      return f.evaluate().isEmpty ? null : t.widget<QcSegmented>(f.first);
    }
    String? selectedCtx() {
      final g = ctxGroup();
      if (g == null) return null;
      final s = g.segments.where((x) => x.selected);
      return s.isEmpty ? null : s.first.label;
    }
    String? textOf(String key) {
      // ui-1 finding: the notice, mismatch and switching keys sit ON a Text; a descendant search misses it.
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

    t.testTextInput.register();
    addTearDown(t.testTextInput.unregister);
    record('automation input transport', {
      'keyboard': 'Flutter TestTextInput', 'pointer': 'flutter_test tap and synthesized mouse hover',
      'physical_keyboard_qualified': false, 'physical_mouse_qualified': false, 'Brain_Core_worker_mocked': false,
    });
    SharedPreferencesStorePlatform.instance = SharedPreferencesWindows()..pathProvider = QualificationPaths();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('uri.living.onboardingDone', true);
    app.main();
    await until(() => find.byType(WorkingSystemRoot).evaluate().isNotEmpty, 'production manifest opt-in');
    await until(() => find.byType(LivingScope).evaluate().isNotEmpty, 'real integrated worker bootstrap');
    final services = t.widget<LivingScope>(find.byType(LivingScope).first).services;
    final conv = services.oi!;
    final runtime0 = conv.runtime;
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
          't': DateTime.now().millisecondsSinceEpoch / 1000, 'state': h['state'], 'reasons': h['reasons'],
          'explain': h['explain'], 'active': activeId(), 'pending': pending(),
          'configured': (conv.brainControls['configured'] as Map?)?['id'],
          'last': (conv.brainControls['switch'] as Map?)?['last'],
          'vision_visual': toggle('qc-vision')?.visual.name, 'vision_status': toggle('qc-vision')?.status,
          'draft_visual': toggle('qc-draft')?.visual.name, 'mismatch': textOf('qc-mismatch'),
          'context_selected': selectedCtx(), 'context_loading': ctxGroup()?.loading,
          'context_status': ctxGroup()?.status, 'switching_text': textOf('qc-switching'),
          'notice': textOf('qc-notice'), 'header_brain': conv.brainStatus['state'],
        };

    // Glow honesty over a timeline: Vision glows only when the verified active profile has vision on; a context
    // segment is selected only when it is the verified active context; while pending nothing glows.
    Map<String, Object?> honesty(List<Map<String, Object?>> rowsT) {
      final bad = <Map<String, Object?>>[];
      for (final r in rowsT) {
        final a = r['active'];
        final std = a == 'standard' || a == 'standard-nodraft';
        final visOk = r['vision_visual'] != 'on' || (std && r['pending'] != true);
        final draftOk = r['draft_visual'] != 'on' || (a == 'standard' && r['pending'] != true);
        final ctxOk = r['context_selected'] == null ||
            (r['pending'] != true && ((std && r['context_selected'] == '32K') ||
                (a == 'long' && r['context_selected'] == '64K')));
        final pendOk = r['pending'] != true || r['vision_visual'] == 'loading';
        if (!(visOk && ctxOk && pendOk && draftOk)) bad.add(r);
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

    // The start profile S: Standard, or Standard draft off (P3) when the owner's desktop leaves too little GPU memory
    // for Standard (owner instruction 2026-10-18: "try with no mtp and 32k context size"; the session then starts
    // the production host with --profile 32768,gpu,0).
    var startId = 'standard';
    String startLabel() => startId == 'standard' ? 'Standard' : 'Standard, draft off';
    await step('UT-ready-start-profile', () async {
      final end = DateTime.now().add(const Duration(seconds: 600));
      while (!((activeId() == 'standard' || activeId() == 'standard-nodraft') &&
          (conv.healthState == 'READY' || conv.healthState == 'DEGRADED'))) {
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: start profile ready');
        await health();
        await t.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 700)));
      }
      startId = activeId()!;
      await settle(800);
      record('start-profile', {'id': startId});
      check('UT-ready-visuals', toggle('qc-vision')?.visual == QcVisual.on && selectedCtx() == '32K' &&
          toggle('qc-thinking')?.status == 'Auto' &&
          toggle('qc-draft')?.visual == (startId == 'standard' ? QcVisual.on : QcVisual.off), uiRow(conv.brainHealth));
      await shot('01-ready-controls');
    });

    // Waits until this UI's request is over: accepted (pending) and then finished with a verified Brain, or refused.
    Future<List<Map<String, Object?>>> waitDone(String label, {int seconds = 900}) async {
      final rowsT = <Map<String, Object?>>[];
      final end = DateTime.now().add(Duration(seconds: seconds));
      var seenPending = false;
      while (true) {
        final h = await health();
        final row = uiRow(h);
        rowsT.add(row);
        seenPending |= pending();
        final last = (conv.brainControls['switch'] as Map?)?['last'] as Map?;
        final mine = last != null && last['id'] == conv.profileRequestId;
        final refused = mine && '${last['result']}'.startsWith('REFUSED_');
        // DEGRADED = the Brain serves but slowly (GPU memory short next to the owner's applications): a finished
        // switch whose outcome is recorded, not a reason to wait.
        if (!pending() && (refused || (seenPending && activeId() != null &&
            (h['state'] == 'READY' || h['state'] == 'DEGRADED')))) {
          break;
        }
        if (conv.profileNotice != null && !pending()) break;            // refused by the worker before any request
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: $label ${jsonEncode(row)}');
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
      final last = (conv.brainControls['switch'] as Map?)?['last'];
      record('switch-timeline', {'label': label, 'rows': tl, 'last': last, 'active': activeId(),
        'notice': textOf('qc-notice')});
      check('UT-glow-honest-$label', (honesty(tl)['violations'] as int) == 0, honesty(tl));
      return tl;
    }

    const secret = '4817';
    await step('UT-thinking', () async {
      await t.tap(find.byKey(const ValueKey('qc-thinking')));
      await settle(600);
      check('UT-thinking-on-click', conv.depth == OiDepth.normal && toggle('qc-thinking')?.visual == QcVisual.on);
      await shot('02-thinking-on-glow');
      final b = await send('thinking-on', 'Compare a bicycle and an electric scooter for a 3 km city commute in two short sentences.');
      check('UT-thinking-on-tier', b.tier == 'NORMAL', {'tier': b.tier, 'route': b.route});
      await t.tap(find.byKey(const ValueKey('qc-thinking')));
      await settle(600);
      check('UT-thinking-off-click', conv.depth == OiDepth.fast && toggle('qc-thinking')?.visual == QcVisual.off);
      final a = await send('tell-fact', 'Quick arithmetic game. The secret number is $secret. Reply with just OK.');
      check('UT-thinking-off-tier', a.tier == 'FAST', {'tier': a.tier, 'route': a.route});
    });

    await step('UT-tooltip', () async {
      final mouse = await t.createGesture(kind: PointerDeviceKind.mouse);
      await mouse.addPointer(location: Offset.zero);
      await mouse.moveTo(t.getCenter(find.byKey(const ValueKey('qc-vision'))));
      await settle(1600);
      check('UT-tooltip-shown', find.textContaining('Also changes context to 64K').evaluate().isNotEmpty);
      await shot('03-vision-hover-tooltip');
      await mouse.moveTo(const Offset(5, 5));
      await mouse.removePointer();
      await settle(800);
    });

    await step('UT-vision-off-failed-start-restored', () async {
      await t.tap(find.byKey(const ValueKey('qc-vision')));
      await settle(800);
      final texts = dialogTexts();
      check('UT-confirm-coupled-change', texts.contains('Switch the Brain to Long context?') &&
          texts.contains('64K') && texts.contains('Off'), {'texts': texts});
      final tl = await confirmAndWait('restore', '04-confirm-vision-off-long');
      final last = (conv.brainControls['switch'] as Map?)?['last'] as Map?;
      check('UT-failed-start-recorded', last?['result'] == 'FAILED' && last?['restored'] == true &&
          (last?['fallback'] as Map?)?['result'] == 'READY', {'last': last});
      check('UT-restored-to-start-profile', activeId() == startId, {'active': activeId()});
      check('UT-switching-indicated', tl.any((r) => r['vision_visual'] == 'loading'),
          {'saw_going_back_text': tl.any((r) => '${r['switching_text']}'.contains('going back to'))});
      check('UT-restored-notice', (textOf('qc-notice') ?? '').contains('went back to ${startLabel()}'),
          {'notice': textOf('qc-notice')});
      check('UT-restored-visuals', toggle('qc-vision')?.visual == QcVisual.on && selectedCtx() == '32K');
      await shot('05-restored-after-failed-start');
    });

    await step('UT-context-64k', () async {
      await t.tap(find.byKey(const ValueKey('qc-context-64K')));
      await settle(800);
      check('UT-confirm-dialog', find.byKey(const ValueKey('qc-confirm-switch')).evaluate().isNotEmpty,
          {'texts': dialogTexts()});
      await shot('06-confirm-context-64k');
      await t.tap(find.byKey(const ValueKey('qc-confirm-switch-go')));
      await settle(1500);
      await shot('07-switching-loading');
      final tl = await waitDone('long');
      record('switch-timeline', {'label': 'long', 'rows': tl, 'active': activeId()});
      check('UT-glow-honest-long', (honesty(tl)['violations'] as int) == 0, honesty(tl));
      check('UT-long-visuals', activeId() == 'long' && toggle('qc-vision')?.visual == QcVisual.off &&
          selectedCtx() == '64K' && find.byKey(const ValueKey('qc-draft')).evaluate().isEmpty, uiRow(conv.brainHealth));
      await shot('08-long-ready');
      final r = await send('recall-long', 'What was the secret number I gave you at the start of this conversation? Reply with the number only.');
      check('UT-continuity-long', r.text.contains(secret) && r.route == 'answer', {'answer': r.text, 'route': r.route});
    });

    await step('UT-vision-on-from-long', () async {
      await t.tap(find.byKey(const ValueKey('qc-vision')));
      await settle(800);
      final texts = dialogTexts();
      check('UT-confirm-explains-unqualified', texts.any((x) => (x ?? '').startsWith('On at 64K:')) &&
          texts.contains('Switch the Brain to Standard?'), {'texts': texts});
      await confirmAndWait('vision-on', '09-confirm-vision-on-standard');
      final last = (conv.brainControls['switch'] as Map?)?['last'] as Map?;
      final refused = '${last?['result']}'.startsWith('REFUSED_');
      record('vision-on-outcome', {'result': last?['result'], 'active': activeId(), 'notice': textOf('qc-notice')});
      if (refused) {
        // Standard does not fit next to the owner's applications: refused BEFORE anything was stopped.
        check('UT-refusal-keeps-long', activeId() == 'long' && toggle('qc-vision')?.visual == QcVisual.off &&
            (textOf('qc-notice') ?? '').contains('not switched'), {'notice': textOf('qc-notice'), 'last': last});
      } else {
        check('UT-standard-visuals', activeId() == 'standard' && toggle('qc-vision')?.visual == QcVisual.on &&
            selectedCtx() == '32K' && toggle('qc-draft')?.visual == QcVisual.on);
      }
      await shot('10-after-vision-on');
      final r = await send('recall-2', 'Once more: what was the secret number I gave you at the start of this conversation? Reply with the number only.');
      check('UT-continuity-2', r.text.contains(secret) && r.route == 'answer', {'answer': r.text, 'route': r.route});
    });

    await step('UT-draft', () async {
      if (find.byKey(const ValueKey('qc-draft')).evaluate().isEmpty) {
        record('draft-skipped', {'reason': 'no Draft toggle at ${activeId()} (only at 32K + vision)'});
        return;
      }
      final on = toggle('qc-draft')!.visual == QcVisual.on;
      await t.tap(find.byKey(const ValueKey('qc-draft')));
      await settle(800);
      check('UT-confirm-draft', dialogTexts().contains('32K (unchanged)'), {'texts': dialogTexts()});
      await confirmAndWait('draft', '10b-confirm-draft');
      record('draft-outcome', {'from_on': on, 'active': activeId(), 'last': (conv.brainControls['switch'] as Map?)?['last']});
      check('UT-draft-visual-matches-active', toggle('qc-draft')?.visual ==
          (activeId() == 'standard' ? QcVisual.on : QcVisual.off) && toggle('qc-vision')?.visual == QcVisual.on);
      await shot('10c-after-draft');
    });

    await step('UT-finish', () async {
      check('UT-no-mismatch-line', find.byKey(const ValueKey('qc-mismatch')).evaluate().isEmpty,
          {'mismatch': textOf('qc-mismatch')});
      await t.tap(find.byKey(const ValueKey('qc-thinking-menu')));
      await settle(600);
      await shot('11-thinking-menu');
      await t.tap(find.byKey(const ValueKey('qc-thinking-Auto')));
      await settle(600);
      check('UT-thinking-auto-restored', conv.depth == OiDepth.auto);
    });

    check('UT-same-worker-and-session', identical(conv.runtime, runtime0) && conv.sessionId == session0 &&
        !conv.workerExited, {'session_after': conv.sessionId});

    // Typography tour: the same running app, each surface once.
    await step('UT-typography-tour', () async {
      final surfaces = <String, void Function()>{
        '20-workspace-conversation': () =>
            services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation),
        '21-workspace-tasks': () => services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.tasks),
        '22-workspace-intelligence-diagnostics': () =>
            services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.intelligence),
        '23-workspace-settings': () =>
            services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.settings),
        '24-dashboard': () => services.presentation.setMode(UiPresentationMode.dashboard),
        '25-assist': () => services.presentation.setMode(UiPresentationMode.assist),
        '26-companion': () => services.presentation.setMode(UiPresentationMode.companion),
      };
      for (final e in surfaces.entries) {
        e.value();
        await settle(2500);
        await shot(e.key);
        record('surface', {'name': e.key, 'mode': services.presentation.mode.name});
      }
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await settle(2000);
      check('UT-typography-tour', true);
    });

    final errors = rows.where((r) => r['label'] == 'flutter-error').toList();
    check('UT-no-flutter-errors', errors.isEmpty, {'count': errors.length, 'first': errors.isEmpty ? null : errors.first});
    record('final', {'failures': failures, 'controls': conv.brainControls, 'health_state': conv.healthState});
    File('${out.path}/ui-finished.json').writeAsStringSync(jsonEncode({'by': 'driver', 'failures': failures,
      'utc': DateTime.now().toUtc().toIso8601String()}));
    FlutterError.onError = oldOnError;
    expect(failures, isEmpty);
  }, timeout: const Timeout(Duration(minutes: 45)));
}
