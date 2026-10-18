// BRAIN-QC-20261018 live driver (temporary, external; copied into uri_ui/integration_test by run_qc_ui.py and removed
// afterwards). Calls the ORIGINAL production main() of the candidate with the real integrated worker, paired Core and
// the real Runtime v1 Brain started by the production Brain host. Input: flutter_test taps and TestTextInput
// (automation), never a physical keyboard or mouse.
//
// Journey: Standard ready -> Thinking Off turn (tell a fact) -> Thinking On turn -> menus (disabled 64K + vision) ->
// Context 64K (Long context) with confirmation, timeline sampled through the switch, a send attempt during it ->
// recall -> Vision On (back to Standard) -> recall -> Thinking back to Auto.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path_provider_windows/path_provider_windows.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';
import 'package:shared_preferences_windows/shared_preferences_windows.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
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
  testWidgets('BRAIN-QC: quick controls on the production main with the real worker, Core and Brain', (t) async {
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
    String? textOf(String key) {
      final f = find.descendant(of: find.byKey(ValueKey(key)), matching: find.byType(Text));
      if (f.evaluate().isEmpty) return null;
      return [for (final e in f.evaluate()) (e.widget as Text).data ?? ''].join(' | ');
    }

    t.testTextInput.register();
    addTearDown(t.testTextInput.unregister);
    record('automation input transport', {
      'keyboard': 'Flutter TestTextInput', 'pointer': 'flutter_test tap (synthesized)',
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
    final size = t.binding.renderViews.first.size;
    record('window', {'logical_size': '$size', 'mode': services.presentation.mode.name});

    Future<Map<String, dynamic>> health() async {
      await t.runAsync(() => conv.refreshHealth());
      await t.pump();
      return conv.brainHealth;
    }
    String? activeId() => (conv.brainControls['active'] as Map?)?['id'] as String?;

    Future<void> waitActive(String id, String label, {int seconds = 420, List<Map<String, Object?>>? timeline}) async {
      final end = DateTime.now().add(Duration(seconds: seconds));
      while (true) {
        final h = await health();
        final c = conv.brainControls;
        final row = <String, Object?>{
          't': DateTime.now().millisecondsSinceEpoch / 1000, 'state': h['state'], 'reasons': h['reasons'],
          'active': activeId(), 'pending': (c['switch'] as Map?)?['pending'],
          'configured': (c['configured'] as Map?)?['id'], 'chip_vision': textOf('qc-vision'),
          'chip_context': textOf('qc-context'), 'chip_switching': textOf('qc-switching'),
          'header_brain': conv.brainStatus['state'],
          'header_text': find.byKey(const ValueKey('oi-brain-state')).evaluate().isEmpty ? null
              : (find.byKey(const ValueKey('oi-brain-state')).evaluate().first.widget as Text).data,
        };
        timeline?.add(row);
        if (activeId() == id && h['state'] == 'READY') break;
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: $label ${jsonEncode(row)}');
        await t.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 700)));
        await t.pump();
      }
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
        'new_messages': [for (final x in conv.messages.skip(count)) {'role': x.role.name, 'text': x.text}],
      });
      return m;
    }

    // Decode speed on a real answer of a few hundred tokens (Thinking Off), right after a profile became ready.
    Future<void> perfTurn(String label) async {
      final keep = conv.depth;
      conv.setDepth(OiDepth.fast);
      final m = await send('perf-$label', 'List thirty common fruits, one per line, nothing else.');
      record('perf', {'profile': label, 'predicted_n': m.metrics['predicted_n'],
        'decode_tps': m.metrics['predicted_per_second'], 'tier': m.tier});
      conv.setDepth(keep);
    }

    Future<void> chooseThinking(String title) async {
      await t.tap(find.byKey(const ValueKey('qc-thinking')));
      await settle(600);
      await t.tap(find.byKey(ValueKey('qc-thinking-$title')));
      await settle(600);
    }

    if (Platform.environment['URI_QC_DRY'] == '1') {
      // Dry run (no Brain host by design): the real worker's controls must not claim any profile is running.
      final h = await health();
      await settle(1500);
      record('dry-health', {'state': h['state'], 'reasons': h['reasons'], 'controls': conv.brainControls});
      check('QC-dry-nothing-active', activeId() == null, {'active': activeId()});
      check('QC-dry-not-switchable', conv.brainControls['can_switch'] == false,
          {'reason': conv.brainControls['cannot_switch_reason']});
      check('QC-dry-chips-unconfirmed', (textOf('qc-vision') ?? '').contains('(not running)') &&
          (textOf('qc-context') ?? '').contains('(not running)'),
          {'vision': textOf('qc-vision'), 'context': textOf('qc-context'), 'thinking': textOf('qc-thinking')});
      await shot('00-dry-no-brain');
      File('${out.path}/ui-finished.json').writeAsStringSync(jsonEncode({'by': 'driver', 'failures': failures}));
      FlutterError.onError = oldOnError;
      expect(failures, isEmpty);
      return;
    }
    await step('QC-ready-standard', () async {
      final timeline = <Map<String, Object?>>[];
      await waitActive('standard', 'Standard ready', seconds: 600, timeline: timeline);
      record('ready-timeline', {'rows': timeline});
      check('QC-ready-standard', activeId() == 'standard', {'controls': conv.brainControls});
      check('QC-chips-standard', textOf('qc-vision') == 'Vision: On' && textOf('qc-context') == 'Context: 32K',
          {'vision': textOf('qc-vision'), 'context': textOf('qc-context'), 'thinking': textOf('qc-thinking')});
      await shot('01-standard-ready');
      await perfTurn('standard-start');
    });

    const secret = '4817';
    await step('QC-thinking', () async {
      await chooseThinking('Off');
      check('QC-thinking-off-depth', conv.depth == OiDepth.fast);
      final a = await send('tell-fact', 'Quick arithmetic game. The secret number is $secret. Reply with just OK.');
      check('QC-thinking-off-tier', a.tier == 'FAST', {'tier': a.tier, 'route': a.route});
      await chooseThinking('On');
      check('QC-thinking-on-depth', conv.depth == OiDepth.normal);
      final b = await send('thinking-on', 'Compare a bicycle and an electric scooter for a 3 km city commute in two short sentences.');
      check('QC-thinking-on-tier', b.tier == 'NORMAL', {'tier': b.tier, 'route': b.route});
      await t.tap(find.byKey(const ValueKey('qc-thinking')));
      await settle(600);
      await shot('02-thinking-menu-last-answer');
      check('QC-thinking-last-answer-shown', find.byKey(const ValueKey('qc-thinking-last')).evaluate().isNotEmpty,
          {'text': textOf('qc-thinking-last')});
      await t.tapAt(const Offset(5, 5));
      await settle(600);
      await chooseThinking('Off');
    });

    await step('QC-menus', () async {
      await t.tap(find.byKey(const ValueKey('qc-context')));
      await settle(800);
      await shot('03-context-menu-standard');
      final blocked = find.text('64K with vision on');
      check('QC-unqualified-listed-disabled', blocked.evaluate().isNotEmpty &&
          find.textContaining('CRASH-1').evaluate().isNotEmpty);
      await t.tap(blocked.first);              // disabled: nothing may happen
      await settle(800);
      check('QC-unqualified-not-requested', find.byKey(const ValueKey('qc-confirm-switch')).evaluate().isEmpty);
      if (find.byKey(const ValueKey('qc-context-64K')).evaluate().isNotEmpty) {
        await t.tapAt(const Offset(5, 5));
        await settle(600);
      }
      await t.tap(find.byKey(const ValueKey('qc-vision')));
      await settle(800);
      await shot('04-vision-menu-standard');
      await t.tapAt(const Offset(5, 5));
      await settle(600);
    });

    final pidsBefore = <String, Object?>{'runtime_identical': identical(conv.runtime, runtime0), 'session': conv.sessionId};
    await step('QC-switch-to-long', () async {
      await t.tap(find.byKey(const ValueKey('qc-context')));
      await settle(800);
      await t.tap(find.byKey(const ValueKey('qc-context-64K')));
      await settle(800);
      await shot('05-confirm-long');
      check('QC-confirm-dialog', find.byKey(const ValueKey('qc-confirm-switch')).evaluate().isNotEmpty,
          {'texts': [for (final e in find.descendant(of: find.byKey(const ValueKey('qc-confirm-switch')),
              matching: find.byType(Text)).evaluate()) (e.widget as Text).data]});
      final tSwitch = DateTime.now().millisecondsSinceEpoch / 1000;
      await t.tap(find.byKey(const ValueKey('qc-confirm-switch-go')));
      await settle(300);
      record('switch-requested', {'to': 'long', 't': tSwitch, 'request_id': conv.profileRequestId,
        'notice': conv.profileNotice});
      final timeline = <Map<String, Object?>>[];
      // a message during the switch must not start a turn
      await settle(1500);
      final h0 = await health();
      await shot('06-switching');
      final before = conv.messages.length;
      await t.runAsync(() => conv.send('Are you there?'));
      await settle(800);
      final refused = conv.messages.skip(before).map((m) => m.text).toList();
      record('send-during-switch', {'health': h0['state'], 'reasons': h0['reasons'], 'messages': refused,
        'last_error': conv.lastError});
      check('QC-turn-refused-during-switch', conv.lastError == 'BRAIN_RESTARTING' ||
          refused.any((x) => x.contains('restarting')), {'last_error': conv.lastError, 'messages': refused});
      await waitActive('long', 'Long context ready', timeline: timeline);
      final tReady = DateTime.now().millisecondsSinceEpoch / 1000;
      record('switch-timeline', {'to': 'long', 'rows': timeline, 'ui_seconds': tReady - tSwitch});
      // review R1-01: the header never reads "ready" while the switch is pending
      final headerReady = timeline.where((r) => r['pending'] == true &&
          (r['header_brain'] == 'READY' || '${r['header_text']}'.endsWith('ready')));
      check('QC-header-truthful-long', headerReady.isEmpty, {'rows_ready_while_pending': headerReady.length,
        'states': {for (final r in timeline) '${r['header_brain']}'}.toList()});
      final early = timeline.where((r) => r['active'] == 'long' && r['state'] != 'READY' && r['state'] != 'BUSY');
      final shownEarly = timeline.where((r) => r['state'] != 'READY' && r['chip_context'] == 'Context: 64K');
      check('QC-truthful-switch-long', early.isEmpty && shownEarly.isEmpty &&
          timeline.any((r) => r['chip_switching'] != null || r['state'] == 'RECOVERING'),
          {'rows': timeline.length, 'early': early.length, 'shown_early': shownEarly.length});
      check('QC-chips-long', textOf('qc-vision') == 'Vision: Off' && textOf('qc-context') == 'Context: 64K',
          {'vision': textOf('qc-vision'), 'context': textOf('qc-context'), 'notice': textOf('qc-notice')});
      await shot('07-long-ready');
      await perfTurn('long');
      final r = await send('recall-long', 'What was the secret number I gave you at the start of this conversation? Reply with the number only.');
      check('QC-continuity-long', r.text.contains(secret) && r.route == 'answer', {'answer': r.text, 'route': r.route});
      await t.tap(find.byKey(const ValueKey('qc-vision')));
      await settle(800);
      await shot('08-vision-menu-long');
      check('QC-unqualified-listed-at-64k', find.text('On at 64K').evaluate().isNotEmpty);
      await t.tapAt(const Offset(5, 5));
      await settle(600);
    });

    await step('QC-switch-to-standard', () async {
      await t.tap(find.byKey(const ValueKey('qc-vision')));
      await settle(800);
      await t.tap(find.byKey(const ValueKey('qc-vision-On')));
      await settle(800);
      await shot('09-confirm-standard');
      final tSwitch = DateTime.now().millisecondsSinceEpoch / 1000;
      await t.tap(find.byKey(const ValueKey('qc-confirm-switch-go')));
      await settle(300);
      final timeline = <Map<String, Object?>>[];
      await waitActive('standard', 'Standard ready again', timeline: timeline);
      final tReady = DateTime.now().millisecondsSinceEpoch / 1000;
      record('switch-timeline', {'to': 'standard', 'rows': timeline, 'ui_seconds': tReady - tSwitch});
      // review R1-01: the header never reads "ready" while the switch is pending
      final headerReady = timeline.where((r) => r['pending'] == true &&
          (r['header_brain'] == 'READY' || '${r['header_text']}'.endsWith('ready')));
      check('QC-header-truthful-standard', headerReady.isEmpty, {'rows_ready_while_pending': headerReady.length,
        'states': {for (final r in timeline) '${r['header_brain']}'}.toList()});
      final early = timeline.where((r) => r['active'] == 'standard' && r['state'] != 'READY' && r['state'] != 'BUSY');
      check('QC-truthful-switch-standard', early.isEmpty, {'rows': timeline.length});
      check('QC-chips-standard-again', textOf('qc-vision') == 'Vision: On' && textOf('qc-context') == 'Context: 32K',
          {'vision': textOf('qc-vision'), 'context': textOf('qc-context'), 'notice': textOf('qc-notice')});
      await shot('10-standard-again');
      await perfTurn('standard-after-switch');
      final r = await send('recall-standard', 'Once more: what was the secret number I gave you at the start of this conversation? Reply with the number only.');
      check('QC-continuity-standard', r.text.contains(secret) && r.route == 'answer', {'answer': r.text, 'route': r.route});
      await chooseThinking('Auto');
      check('QC-thinking-auto-restored', conv.depth == OiDepth.auto);
    });

    check('QC-same-worker-and-session', identical(conv.runtime, runtime0) && conv.sessionId == session0 &&
        !conv.workerExited, {'before': pidsBefore, 'session_after': conv.sessionId});
    record('final', {'failures': failures, 'controls': conv.brainControls, 'health_state': conv.healthState});
    File('${out.path}/ui-finished.json').writeAsStringSync(jsonEncode({'by': 'driver', 'failures': failures,
      'utc': DateTime.now().toUtc().toIso8601String()}));
    FlutterError.onError = oldOnError;
    expect(failures, isEmpty);
  }, timeout: const Timeout(Duration(minutes: 40)));
}
