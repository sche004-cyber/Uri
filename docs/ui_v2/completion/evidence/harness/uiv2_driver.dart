// UI V2 completion qualification driver (temporary, external): calls the ORIGINAL production main() of the
// candidate with the real integrated worker, paired Core and Runtime v1 Brain. Input is Flutter TestTextInput and
// synthesized key events (automation), never a physical keyboard or mouse. Modes: main (first-time user, all
// journeys) and returning (restart with the same preferences).
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path_provider_windows/path_provider_windows.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';
import 'package:shared_preferences_windows/shared_preferences_windows.dart';
import 'package:uri_ui/living/companion/companion_orb.dart' show CompanionIdentity;
import 'package:uri_ui/living/companion/companion_preferences.dart' show CompanionChoice;
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/screens/workspace_mode_view.dart' show WorkspaceSettingsRegion;
import 'package:uri_ui/main.dart' as app;
import 'package:uri_ui/working_system_app.dart';
import 'package:window_manager/window_manager.dart';

class QualificationPaths extends PathProviderWindows {
  @override
  Future<String?> getApplicationSupportPath() async => Platform.environment['URI_QUAL_PREFS'];
}

final _rawCode = RegExp(r'\b[A-Z]{2,}_[A-Z_]{2,}\b');
const _companionWindow = MethodChannel('uri/companion_window');

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  binding.framePolicy = LiveTestWidgetsFlutterBindingFramePolicy.fullyLive;
  testWidgets('UI V2 completion: production main, real worker, Core and Brain', (t) async {
    final out = Directory(Platform.environment['URI_QUAL_UI_OUT']!)..createSync(recursive: true);
    final mode = Platform.environment['URI_QUAL_MODE'] ?? 'main';
    final rows = <Map<String, Object?>>[];
    final failures = <String>[];
    final flutterErrors = <String>[];
    final oldOnError = FlutterError.onError;
    FlutterError.onError = (d) {
      flutterErrors.add(d.exceptionAsString());
      final full = d.toString();
      rows.add({'utc': DateTime.now().toUtc().toIso8601String(), 'label': 'flutter-error', 'error': d.exceptionAsString(),
        'detail': full.length > 6000 ? full.substring(0, 6000) : full,
        'stack': '${d.stack}'.split(String.fromCharCode(10)).take(30).join(String.fromCharCode(10))});
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
    List<String> visibleTexts() => [
          for (final e in find.byType(Text).evaluate())
            ((e.widget as Text).data ?? (e.widget as Text).textSpan?.toPlainText() ?? ''),
          for (final e in find.byType(SelectableText).evaluate()) ((e.widget as SelectableText).data ?? ''),
        ];
    void rawCodeCheck(String where) {
      final codes = {for (final s in visibleTexts()) ..._rawCode.allMatches(s).map((m) => m.group(0)!)};
      record('raw-codes-on-screen', {'where': where, 'codes': codes.toList()});
    }
    // Frame timings (engine-reported build and raster time per frame), grouped by labelled windows.
    final timings = <FrameTiming>[];
    SchedulerBinding.instance.addTimingsCallback(timings.addAll);
    Map<String, Object?> frameStats(int from) {
      final f = timings.skip(from).toList();
      if (f.isEmpty) return {'frames': 0};
      List<double> ms(Duration Function(FrameTiming) d) => (f.map((x) => d(x).inMicroseconds / 1000).toList()..sort());
      double pct(List<double> v, double p) => v[((v.length - 1) * p).round()];
      final build = ms((x) => x.buildDuration), raster = ms((x) => x.rasterDuration), total = ms((x) => x.totalSpan);
      return {
        'frames': f.length,
        'build_ms_p50': pct(build, .5), 'build_ms_p95': pct(build, .95), 'build_ms_max': build.last,
        'raster_ms_p50': pct(raster, .5), 'raster_ms_p95': pct(raster, .95), 'raster_ms_max': raster.last,
        'total_ms_p95': pct(total, .95), 'over_16ms': total.where((x) => x > 16.7).length,
      };
    }
    Future<void> perfWindow(String label, Duration d) async {
      final from = timings.length;
      final sw = Stopwatch()..start();
      while (sw.elapsed < d) {
        await t.pump(const Duration(milliseconds: 16));
      }
      record('perf-window', {'window': label, 'seconds': d.inSeconds, ...frameStats(from)});
    }
    Future<void> key(LogicalKeyboardKey k, {bool control = false}) async {
      final before = FocusManager.instance.primaryFocus?.toString();
      if (control) await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await t.sendKeyEvent(k);
      if (control) await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await settle(600);
      record('key', {'key': '${control ? 'ctrl+' : ''}${k.keyLabel}', 'focus_before': before,
        'mode_after': LivingScope.of(t.element(find.byType(LivingShell))).presentation.mode.name,
        'can_pop': Navigator.of(t.element(find.byType(LivingShell))).canPop()});
    }
    Future<void> step(String id, Future<void> Function() body) async {
      try {
        await body();
      } catch (e, s) {
        check(id, false, {'exception': '$e', 'stack': '$s'.split('\n').take(6).join(' | ')});
      }
    }

    t.testTextInput.register();
    addTearDown(t.testTextInput.unregister);
    record('automation input transport', {
      'keyboard': 'Flutter TestTextInput + synthesized key events', 'pointer': 'flutter_test tap (synthesized)',
      'physical_keyboard_qualified': false, 'physical_mouse_qualified': false, 'microphone_qualified': false,
      'Brain_Core_worker_mocked': false, 'first_run': Platform.environment['URI_QUAL_FIRST_RUN'],
      'visual': Platform.environment['URI_UI_VISUAL'],
    });
    SharedPreferencesStorePlatform.instance = SharedPreferencesWindows()..pathProvider = QualificationPaths();
    final prefs = await SharedPreferences.getInstance();
    record('preferences at start', {'keys': prefs.getKeys().toList()..sort()});
    final sw = Stopwatch()..start();
    app.main();
    await until(() => find.byType(WorkingSystemRoot).evaluate().isNotEmpty, 'production manifest opt-in');
    await until(() => find.byType(LivingScope).evaluate().isNotEmpty, 'real integrated worker bootstrap');
    final services = t.widget<LivingScope>(find.byType(LivingScope).first).services;
    final conv = services.oi!;
    record('production main connected', {
      'seconds_to_living_scope': sw.elapsedMilliseconds / 1000, 'visualV2': services.visualV2,
      'mode': services.presentation.mode.name, 'brain_status': conv.brainStatus,
    });
    final v2 = services.visualV2;
    // A fact unique to this run: the paired client store keeps facts between runs.
    final code = 'K${DateTime.now().millisecondsSinceEpoch % 100000}';
    final fact = 'the project room code is $code';
    await t.runAsync(conv.refreshMemory);
    record('memory at start', {'facts': conv.memory, 'run_fact': fact});

    // J1. First-time start: onboarding (if shown), then the default presentation.
    await step('J1-start', () async {
      await settle(1500);
      final onboarding = find.byKey(const ValueKey('onboarding-step-title'));
      record('onboarding shown', {'shown': onboarding.evaluate().isNotEmpty});
      if (onboarding.evaluate().isNotEmpty) {
        await shot('j1-onboarding-first');
        final titles = <String>[];
        for (var i = 0; i < 10 && find.byKey(const ValueKey('onboarding-step-title')).evaluate().isNotEmpty; i++) {
          titles.add((t.widget<Text>(find.byKey(const ValueKey('onboarding-step-title'))).data ?? ''));
          final next = find.byKey(const ValueKey('onboarding-next'));
          if (next.evaluate().isEmpty) break;
          await t.tap(next);
          await settle(1200);
        }
        if (find.byKey(const ValueKey('onboarding-skip')).evaluate().isNotEmpty) {
          await t.tap(find.byKey(const ValueKey('onboarding-skip')));
          await settle(1200);
          record('onboarding finished by', {'control': 'Skip setup'});
        }
        record('onboarding steps', {'titles': titles});
      }
      await until(() => find.byKey(LivingShell.orbKey).evaluate().isNotEmpty, 'living shell');
      check('J1-v2-is-default', v2 == (Platform.environment['URI_UI_VISUAL'] != 'living'),
          {'visualV2': v2, 'mode': services.presentation.mode.name});
      if (v2) check('J1-dashboard-first', services.presentation.mode == UiPresentationMode.dashboard);
      await shot('j1-start');
      rawCodeCheck('start');
    });
    // Brain readiness as the UI reports it.
    await step('J1-brain-ready', () async {
      for (var i = 0; i < 120 && !conv.brainReady; i++) {
        await t.runAsync(() async {
          await conv.refreshStatus();
          await Future<void>.delayed(const Duration(milliseconds: 500));
        });
        await t.pump();
      }
      check('J1-brain-ready', conv.brainReady, {'brain': conv.brainStatus});
      await shot('j1-ready');
    });
    await perfWindow('idle-${services.presentation.mode.name}', const Duration(seconds: 10));

    Future<OiMessage> send(String scenario, String text, {Finder? field, Finder? sendButton}) async {
      final count = conv.messages.length;
      final timer = Stopwatch()..start();
      final from = timings.length;
      await t.enterText(field ?? find.byKey(const ValueKey('living-composer-field')).first, text);
      await t.pump();
      await t.tap(sendButton ?? find.byKey(const ValueKey('living-composer-send')).first);
      await t.pump(const Duration(milliseconds: 100));
      await until(() => conv.messages.length > count, 'submitted');
      await until(() => !conv.busy, 'terminal');
      final m = conv.messages.skip(count).lastWhere((x) => x.role == OiRole.uri, orElse: () => conv.messages.last);
      record('turn', {
        'scenario': scenario, 'request': text, 'text': m.text, 'core_message': m.coreMessage, 'route': m.route,
        'answer_status': m.answerStatus, 'core_code': m.coreCode, 'error_code': m.errorCode,
        'error_message': m.errorMessage, 'metrics': m.metrics, 'application_seconds': timer.elapsedMilliseconds / 1000,
        'frames_during_turn': frameStats(from), 'mode': services.presentation.mode.name,
      });
      return m;
    }
    Future<void> press(String label) async {
      await until(() => find.text(label).evaluate().isNotEmpty, 'button $label', seconds: 60);
      await t.ensureVisible(find.text(label).first);
      await t.tap(find.text(label).first);
      await t.pump(const Duration(milliseconds: 100));
      await until(() => !conv.busy, 'decision terminal');
      await settle();
    }

    if (mode == 'perf') {
      // Controlled comparison: same view (Workspace conversation), same prompt, five times; then idle windows.
      await step('P-brain-speed', () async {
        await key(LogicalKeyboardKey.digit2, control: true);
        services.presentation.setFocus(WorkspaceFocus.conversation);
        await settle(1500);
        for (var i = 0; i < 5; i++) {
          final m = await send('perf sky $i', 'Write four short sentences about why the sky looks blue.');
          record('perf-turn', {'i': i, 'tps': m.metrics['predicted_per_second'], 'n': m.metrics['predicted_n'],
            'ttft_s': m.metrics['ttft_s'], 'mode': services.presentation.mode.name});
          await settle(1500);
        }
        await perfWindow('idle-workspace-30s', const Duration(seconds: 30));
        await key(LogicalKeyboardKey.digit3, control: true);
        await perfWindow('idle-dashboard-30s', const Duration(seconds: 30));
        await key(LogicalKeyboardKey.digit1, control: true);
        await perfWindow('idle-companion-30s', const Duration(seconds: 30));
      });
    } else if (mode == 'returning') {
      await step('R-no-onboarding-and-persisted', () async {
        check('R-no-onboarding', find.byKey(const ValueKey('onboarding-step-title')).evaluate().isEmpty);
        check('R-companion-persisted', services.companionPrefs.choice.identity == CompanionIdentity.lunar,
            {'choice': services.companionPrefs.choice.key});
        check('R-theme-persisted', services.companionPrefs.interfaceTheme?.name == 'snowArchive',
            {'theme': services.companionPrefs.interfaceTheme?.name});
        await shot('r-start');
      });
      await step('R-conversation', () async {
        await key(LogicalKeyboardKey.digit2, control: true);
        final m = await send('returning conversation', 'Reply with exactly the word ready.');
        check('R-conversation', m.text.toLowerCase().contains('ready'), {'text': m.text});
      });
      await step('R-connections-honest', () async {
        await key(LogicalKeyboardKey.digit3, control: true);
        final card = find.text('Not managed here yet');
        check('R-connections-card-plain', card.evaluate().isNotEmpty);
        await t.tap(card.first);
        await settle(1500);
        check('R-connections-page-plain', find.byKey(const ValueKey('connections-unavailable')).evaluate().isNotEmpty &&
            find.text('Connected').evaluate().isEmpty);
        await shot('r-connections');
        await t.tap(find.text('Open Settings'));
        await settle(1500);
        check('R-connections-open-settings', services.presentation.focus == WorkspaceFocus.settings);
      });
      await step('R-restore-defaults', () async {
        services.companionPrefs.select(const CompanionChoice.living(CompanionIdentity.solar));
        await services.companionPrefs.setInterfaceTheme(null);
        await settle();
        check('R-restored', services.companionPrefs.choice.identity == CompanionIdentity.solar);
      });
    } else {
      // J2. Navigation by keyboard and by the visible navigation.
      await step('J2-navigation', () async {
        final seen = <String>[];
        for (final (k, m) in [
          (LogicalKeyboardKey.digit2, UiPresentationMode.workspace),
          (LogicalKeyboardKey.digit3, UiPresentationMode.dashboard),
          (LogicalKeyboardKey.digit4, UiPresentationMode.assist),
          (LogicalKeyboardKey.digit3, UiPresentationMode.dashboard),
        ]) {
          await key(k, control: true);
          seen.add(services.presentation.mode.name);
          check('J2-ctrl-${m.name}', services.presentation.mode == m, {'mode': services.presentation.mode.name});
          await shot('j2-${m.name}');
          rawCodeCheck('mode ${m.name}');
        }
        if (v2) {
          for (final (label, focus) in [
            ('Conversation', WorkspaceFocus.conversation),
            ('Tasks', WorkspaceFocus.tasks),
            ('Documents', WorkspaceFocus.documents),
            ('Settings', WorkspaceFocus.settings),
          ]) {
            await key(LogicalKeyboardKey.digit3, control: true);
            final item = find.widgetWithText(ListTile, label);
            if (item.evaluate().isEmpty) {
              // Medium/narrow window: the navigation is in the drawer.
              await t.tap(find.byTooltip('Navigation'));
              await settle();
            }
            await t.tap(find.widgetWithText(ListTile, label).first);
            await settle(1000);
            check('J2-nav-$label', services.presentation.mode == UiPresentationMode.workspace &&
                services.presentation.focus == focus, {'mode': services.presentation.mode.name, 'focus': services.presentation.focus.name});
            await shot('j2-nav-${label.toLowerCase()}');
          }
        }
      });
      // J3. Real conversation with the Brain from the V2 Workspace.
      await step('J3-conversation', () async {
        await key(LogicalKeyboardKey.digit2, control: true);
        services.presentation.setFocus(WorkspaceFocus.conversation);
        await settle();
        final hello = await send('greeting', 'Hello URI');
        check('J3-greeting-replied', hello.text.trim().isNotEmpty && hello.errorCode == null,
            {'text': hello.text, 'code': hello.coreCode});
        final fact = await send('fact question', 'In one short sentence: what is the capital of France?');
        check('J3-fact', fact.text.toLowerCase().contains('paris'), {'text': fact.text});
        await shot('j3-conversation');
        rawCodeCheck('conversation');
      });
      // J4 + J5 + J9. Clarification, confirmation, approval card, decline, then approve (remember_fact tool).
      await step('J4-clarify-confirm-decline', () async {
        var m = await send('missing fact clarification', 'remember that');
        check('J4-clarification-asked', m.coreCode == 'INTENT_CLARIFICATION', {'code': m.coreCode, 'text': m.text});
        m = await send('clarification answer', fact);
        check('J4-confirmation-asked', conv.pendingConfirmation != null, {'code': m.coreCode, 'text': m.text});
        await shot('j4-confirmation');
        if (v2) {
          await key(LogicalKeyboardKey.digit3, control: true);
          check('J9-dashboard-counts-decision', find.text('1 review needed').evaluate().isNotEmpty,
              {'texts': visibleTexts().where((s) => s.contains('review') || s.contains('decision')).toList()});
          await shot('j9-dashboard-review-count');
          await t.tap(find.text('1 review needed'));
          await settle(1000);
          check('J9-review-opens-tasks', services.presentation.focus == WorkspaceFocus.tasks);
          await shot('j9-tasks-review');
          await key(LogicalKeyboardKey.digit2, control: true);
          services.presentation.setFocus(WorkspaceFocus.conversation);
          await settle();
        }
        await press('Yes, continue');
        await until(() => conv.pendingApproval != null, 'memory approval', seconds: 120);
        record('approval card', {'capability': conv.pendingApproval!.capabilityId, 'arguments': conv.pendingApproval!.arguments});
        await shot('j5-approval-card');
        rawCodeCheck('approval card');
        await press('Deny');
        await t.runAsync(conv.refreshMemory);
        check('J9-deny-honoured', conv.pendingApproval == null && !conv.memory.any((f) => f.contains(code)),
            {'memory': conv.memory, 'last_code': conv.messages.last.coreCode});
        await shot('j9-after-deny');
      });
      await step('J5-approve-tool', () async {
        // Same path as J4 (the one-shot phrasing is sometimes refused by Core as INTENT_UNGROUNDED_VALUE, OUT-CORE-3).
        var m = await send('remember again', 'remember that');
        m = await send('remember again: the fact', fact);
        if (conv.pendingConfirmation != null) await press('Yes, continue');
        await until(() => conv.pendingApproval != null, 'memory approval', seconds: 120);
        await press('Approve');
        m = conv.messages.lastWhere((x) => x.role == OiRole.uri);
        await t.runAsync(conv.refreshMemory);
        check('J5-tool-settled', m.coreCode == 'SETTLED_VERIFIED', {'code': m.coreCode, 'text': m.text});
        check('J5-memory-written', conv.memory.any((f) => f.contains(code)), {'memory': conv.memory});
        final recall = await send('recall', 'What is the project room code? Answer from what I asked you to remember.');
        check('J5-recall', recall.text.contains(code), {'text': recall.text, 'semantic_review_required': true});
        await shot('j5-after-approve');
      });
      // J6. Documents entry point (existing): Start new work sends a real turn.
      if (v2) {
        await step('J6-documents-start-work', () async {
          await key(LogicalKeyboardKey.digit2, control: true);
          services.presentation.setFocus(WorkspaceFocus.documents);
          await settle(1000);
          await shot('j6-documents');
          final count = conv.messages.length;
          await t.tap(find.byKey(const ValueKey('template-Letter')));
          await settle(500);
          check('J6-letter-opens-conversation', services.presentation.focus == WorkspaceFocus.conversation);
          await until(() => conv.messages.length > count, 'letter submitted');
          await until(() => !conv.busy, 'letter terminal');
          final m = conv.messages.lastWhere((x) => x.role == OiRole.uri);
          record('turn', {'scenario': 'start new work: letter', 'request': 'Draft a letter', 'text': m.text, 'core_code': m.coreCode,
            'route': m.route, 'metrics': m.metrics});
          check('J6-letter-real-turn', services.work.items.isEmpty && conv.messages.length > count,
              {'simulated_items': services.work.items.length});
          await shot('j6-letter-reply');
          if (conv.pendingConfirmation != null) await press('No');
          if (conv.pendingApproval != null) await press('Deny');
          // Leave the draft desk so later turns are ordinary turns (an open draft takes follow-up text as edits).
          final close = find.text('Close draft');
          record('draft open after letter', {'open': close.evaluate().isNotEmpty});
          if (close.evaluate().isNotEmpty) {
            await t.ensureVisible(close.first);
            await t.tap(close.first);
            await settle(1000);
          }
        });
      }
      // J10. Responsiveness while the Brain works: navigate during a turn.
      await step('J10-responsive-during-turn', () async {
        await key(LogicalKeyboardKey.digit2, control: true);
        services.presentation.setFocus(WorkspaceFocus.conversation);
        await settle();
        final count = conv.messages.length;
        await t.enterText(find.byKey(const ValueKey('living-composer-field')).first,
            'Write four short sentences about why the sky looks blue.');
        await t.tap(find.byKey(const ValueKey('living-composer-send')).first);
        await t.pump(const Duration(milliseconds: 200));
        await until(() => conv.messages.length > count && conv.busy, 'busy');
        final from = timings.length;
        final navs = <String, double>{};
        for (final k in [LogicalKeyboardKey.digit3, LogicalKeyboardKey.digit2]) {
          final s = Stopwatch()..start();
          await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
          await t.sendKeyEvent(k);
          await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
          await t.pump();
          navs[k.keyLabel] = s.elapsedMicroseconds / 1000;
          await settle(1500);
        }
        check('J10-navigation-while-busy', services.presentation.mode == UiPresentationMode.workspace,
            {'nav_ms': navs, 'busy_seen': true});
        await until(() => !conv.busy, 'terminal');
        final m = conv.messages.lastWhere((x) => x.role == OiRole.uri);
        record('perf-window', {'window': 'brain-turn-with-navigation', ...frameStats(from), 'metrics': m.metrics,
          'answer_chars': m.text.length});
      });
      // J7. Companion: frameless shaped window, single/double click, detached chat, Escape.
      if (v2) {
        await step('J7-companion', () async {
          final before = await windowManager.getSize();
          await key(LogicalKeyboardKey.digit1, control: true);
          await settle(1500);
          final size = await windowManager.getSize();
          final facts = await _companionWindow.invokeMapMethod<String, Object?>('facts');
          check('J7-window-440x680', (size.width - 440).abs() < 2 && (size.height - 680).abs() < 2, {'size': '$size'});
          check('J7-shaped-region', facts?['regionKind'] != 1 && facts?['cornerHit'] == false, {'facts': facts});
          await shot('j7-companion-idle');
          // R1-03: the native region channel rejects malformed layouts and keeps the current region.
          for (final (name, orb) in [
            ('nan', [double.nan, 0.0, 10.0, 10.0]),
            ('infinite', [0.0, 0.0, double.infinity, 10.0]),
            ('inverted', [50.0, 50.0, 10.0, 10.0]),
          ]) {
            String? code;
            try {
              await _companionWindow.invokeMethod<void>('regions', {'active': true, 'orb': orb});
            } on PlatformException catch (e) {
              code = e.code;
            }
            check('J7-native-rejects-$name', code == 'INVALID_LAYOUT', {'code': code});
          }
          final factsAfterReject = await _companionWindow.invokeMapMethod<String, Object?>('facts');
          check('J7-region-kept-after-reject', factsAfterReject?['regionKind'] == facts?['regionKind'] &&
              factsAfterReject?['regionWidth'] == facts?['regionWidth'], {'before': facts, 'after': factsAfterReject});
          await perfWindow('idle-companion', const Duration(seconds: 10));
          await t.tap(find.byKey(LivingShell.orbKey));
          await settle(900);
          final chat = find.byKey(const ValueKey('a2ui.companion-controls.chat'));
          check('J7-single-click-controls', chat.evaluate().isNotEmpty && conv.messages.isNotEmpty);
          final factsOpen = await _companionWindow.invokeMapMethod<String, Object?>('facts');
          record('companion region with controls', {'facts': factsOpen});
          await shot('j7-companion-controls');
          await t.tap(chat);
          await settle(900);
          check('J7-detached-chat', find.byKey(const ValueKey('companion-detached-chat')).evaluate().isNotEmpty);
          final m = await send('companion chat', 'Say hello in three words.',
              field: find.descendant(of: find.byKey(const ValueKey('companion-detached-chat')),
                  matching: find.byKey(const ValueKey('living-composer-field'))),
              sendButton: find.descendant(of: find.byKey(const ValueKey('companion-detached-chat')),
                  matching: find.byKey(const ValueKey('living-composer-send'))));
          check('J7-chat-reply', m.text.trim().isNotEmpty, {'text': m.text});
          check('J7-stays-companion', services.presentation.mode == UiPresentationMode.companion);
          await shot('j7-companion-chat');
          await key(LogicalKeyboardKey.escape);
          check('J7-escape-closes-chat', find.byKey(const ValueKey('companion-detached-chat')).evaluate().isEmpty);
          await shot('j7-after-escape');
          final orb = find.byKey(LivingShell.orbKey);
          await t.tap(orb);
          await t.pump(const Duration(milliseconds: 60));
          await t.tap(orb);
          await settle(1500);
          final after = await windowManager.getSize();
          check('J7-double-click-dashboard', services.presentation.mode == UiPresentationMode.dashboard,
              {'mode': services.presentation.mode.name});
          check('J7-window-restored', (after.width - before.width).abs() < 2 && (after.height - before.height).abs() < 2,
              {'before': '$before', 'after': '$after'});
          await shot('j7-back-dashboard');
        });
      }
      // J8. Settings: companion gallery (Apply) and interface theme; persisted for the returning run.
      if (v2) {
        await step('J8-settings', () async {
          await key(LogicalKeyboardKey.digit2, control: true);
          services.presentation.setFocus(WorkspaceFocus.settings);
          await settle(1000);
          await t.scrollUntilVisible(find.text('Companion Design'), 200, scrollable: find.byType(Scrollable).first);
          var attempts = 0;
          while (attempts < 3 && find.byKey(const ValueKey('gallery-live-renderer')).evaluate().isEmpty) {
            attempts++;
            await settle(800);
            await t.ensureVisible(find.widgetWithText(ListTile, 'Companion Design').first);
            await settle(400);
            await t.tap(find.widgetWithText(ListTile, 'Companion Design').first);
            for (var i = 0; i < 20 && find.byKey(const ValueKey('gallery-live-renderer')).evaluate().isEmpty; i++) {
              await settle(200);
            }
          }
          record('gallery open attempts', {'attempts': attempts});
          check('J8-gallery-opens', find.byKey(const ValueKey('gallery-live-renderer')).evaluate().isNotEmpty);
          await shot('j8-gallery');
          await t.scrollUntilVisible(find.byKey(const ValueKey('gallery-design-lunar')), 150,
              scrollable: find.descendant(of: find.byType(ListView), matching: find.byType(Scrollable)).first);
          await t.tap(find.byKey(const ValueKey('gallery-design-lunar')));
          await settle(800);
          check('J8-preview-isolated', services.companionPrefs.choice.identity == CompanionIdentity.solar);
          await t.tap(find.byKey(const ValueKey('gallery-apply')));
          await settle(1200);
          check('J8-apply', services.companionPrefs.choice.identity == CompanionIdentity.lunar);
          final theme = find.byType(DropdownButtonFormField<String>);
          if (theme.evaluate().isNotEmpty) {
            await t.ensureVisible(theme.first);
            await t.tap(theme.first);
            await settle(800);
            await t.tap(find.text('Snow Archive').last);
            await settle(1200);
          }
          check('J8-theme', services.companionPrefs.interfaceTheme?.name == 'snowArchive',
              {'theme': services.companionPrefs.interfaceTheme?.name});
          await shot('j8-after-theme');
          await key(LogicalKeyboardKey.digit3, control: true);
          await shot('j8-dashboard-snow-lunar');
          check('J13-classic-reachable', true, {'note': 'checked below'});
        });
        await step('J13-classic-entry-present', () async {
          await key(LogicalKeyboardKey.digit2, control: true);
          services.presentation.setFocus(WorkspaceFocus.settings);
          await settle(1000);
          final classic = find.byKey(const ValueKey('ws-open-classic'));
          if (classic.evaluate().isEmpty) {
            await t.scrollUntilVisible(classic, 300,
                scrollable: find.ancestor(of: find.text('Companion Design'), matching: find.byType(Scrollable)).first);
          }
          check('J13-classic-entry-present', classic.evaluate().isNotEmpty);
        });
      }
      // J11. Window sizes: dashboard and workspace at common window sizes.
      if (v2) {
        await step('J11-resize', () async {
          final original = await windowManager.getSize();
          for (final s in const [Size(1366, 768), Size(1280, 800), Size(1024, 768), Size(900, 640), Size(800, 600)]) {
            final errors = flutterErrors.length;
            await windowManager.setSize(s);
            await settle(1200);
            await key(LogicalKeyboardKey.digit3, control: true);
            await shot('j11-dashboard-${s.width.toInt()}x${s.height.toInt()}');
            final view = t.binding.renderViews.first.size;
            final composer = find.byKey(const ValueKey('living-composer-field'));
            final visible = composer.evaluate().isNotEmpty &&
                (Offset.zero & view).contains(t.getRect(composer.first).bottomRight);
            final medium = view.width >= 900 && view.height >= 640;
            record('resize', {'requested': '$s', 'view': '$view', 'composer_visible_without_scroll': visible,
              'expected_layout': medium ? 'medium (composer in view)' : 'scrolling column', 'new_flutter_errors': flutterErrors.length - errors});
            if (medium) check('J11-composer-in-view-${s.width.toInt()}', visible, {'view': '$view'});
            check('J11-no-layout-error-${s.width.toInt()}', flutterErrors.length == errors);
            await key(LogicalKeyboardKey.digit2, control: true);
            await shot('j11-workspace-${s.width.toInt()}x${s.height.toInt()}');
          }
          await windowManager.setSize(original);
          await settle(1000);
        });
      }
      // J12. Failure and recovery: the Brain stops; the UI says so in plain words and a turn fails honestly.
      await step('J12-brain-stopped', () async {
        File('${out.path}/stop-brain.json').writeAsStringSync('{"by":"driver"}');
        for (var i = 0; i < 120 && conv.brainReady; i++) {
          await t.runAsync(() async {
            await conv.refreshStatus();
            await Future<void>.delayed(const Duration(milliseconds: 500));
          });
          await t.pump();
        }
        check('J12-brain-not-ready-seen', !conv.brainReady, {'brain': conv.brainStatus});
        await key(LogicalKeyboardKey.digit3, control: true);
        await shot('j12-dashboard-brain-stopped');
        await key(LogicalKeyboardKey.digit2, control: true);
        services.presentation.setFocus(WorkspaceFocus.conversation);
        await settle();
        final m = await send('turn without Brain', 'Hello again URI');
        record('turn without brain', {'text': m.text, 'error_code': m.errorCode, 'error_message': m.errorMessage,
          'recovery': m.recoveryOptions});
        await shot('j12-turn-without-brain');
        rawCodeCheck('brain stopped');
      });
    }
    record('summary', {'failures': failures, 'flutter_errors': flutterErrors.length, 'elapsed_s': sw.elapsedMilliseconds / 1000});
    File('${out.path}/ui-finished.json').writeAsStringSync(jsonEncode({'failures': failures, 'mode': mode}));
    FlutterError.onError = oldOnError;
  }, timeout: const Timeout(Duration(minutes: 40)));
}
