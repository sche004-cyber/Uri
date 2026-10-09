/// LIVE (opt-in): the real Living Companion widgets driving the REAL
/// integrated worker (C1 gates) against the REAL integrated server, Core and,
/// when READY, Runtime v1. Journeys are typed into the real composer and
/// decided with the real buttons.
///
///   `set URI_WS_LIVE=1 & set URI_CLIENT_MANIFEST=<client manifest> & flutter test test/ws_live`
///
/// Evidence: a JSON receipt (`URI_WS_EVIDENCE` path, default build/ws_ui_live.json)
/// with every journey's observed state and the event types seen.
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_health_widgets.dart';
import 'package:uri_ui/living/integration/oi_markdown.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'package:uri_ui/services/mock_uri_client.dart';

final env = Platform.environment;
final live = env['URI_WS_LIVE'] == '1';
final receipt = <String, dynamic>{'journeys': <Map<String, dynamic>>[]};

Future<void> until(WidgetTester t, bool Function() ok, {int seconds = 240, String what = ''}) async {
  final end = DateTime.now().add(Duration(seconds: seconds));
  while (!ok()) {
    if (DateTime.now().isAfter(end)) throw StateError('timeout waiting for $what');
    await t.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 100)));
    await t.pump();
  }
}

Future<void> say(WidgetTester t, String text) async {
  await t.enterText(find.byKey(const ValueKey('living-composer-field')), text);
  await t.pump();
  await t.tap(find.byKey(const ValueKey('living-composer-send')));
  await t.pump();
}

void record(String name, OiConversation c, {Map<String, dynamic> extra = const {}}) {
  final m = c.messages.lastWhere((m) => m.role == OiRole.uri, orElse: () => OiMessage(role: OiRole.system, text: ''));
  (receipt['journeys'] as List).add({
    'journey': name,
    'route': m.route,
    'tier': m.tier,
    'answer_status': m.answerStatus,
    'core_code': m.coreCode,
    'finished': m.finishedStatus,
    'error': m.errorCode,
    'text_chars': m.text.length,
    'text_head': m.text.length > 160 ? m.text.substring(0, 160) : m.text,
    'metrics': m.metrics,
    'thinking_chars': m.thinkingChars,
    'brain': c.brainStatus['state'],
    'selected_row': c.selectedRowId,
    ...extra,
  });
}

void main() {
  testWidgets('working system journeys through the real Living UI', (t) async {
    SharedPreferences.setMockInitialValues({'uri.living.onboardingDone': true});
    await t.binding.setSurfaceSize(const Size(1400, 900));
    final manifest = env['URI_CLIENT_MANIFEST'];
    final rt = (await t.runAsync(() => WorkerIntegratedRuntime.fromManifest(manifest)))!;
    // Restart URI (WS hardening) starts a fresh real worker through the same manifest path.
    final conv = OiConversation(rt, respawn: () => WorkerIntegratedRuntime.fromManifest(manifest));
    final services = LivingApp.buildIntegratedServices(conv);
    services.effects.setReducedMotion(true);
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
    final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
    await t.runAsync(conv.refreshStatus);
    receipt['brain_status_start'] = conv.brainStatus;
    receipt['catalog_selected'] = conv.selectedRowId;
    await t.pumpWidget(LivingApp(appState: appState, services: services, skipOnboarding: true));
    await t.pump(const Duration(milliseconds: 200));
    final ready = conv.brainReady;

    try {
      // 1. Normal response (or honest unavailable-runtime handling when the Brain is not READY).
      await say(t, 'In one sentence, what is VRAM?');
      await until(t, () => !conv.busy && conv.messages.last.finishedStatus != null, what: 'question');
      if (ready) {
        expect(conv.messages.last.answerStatus, 'COMPLETE');
        expect(conv.messages.last.text, isNotEmpty);
      } else {
        expect(conv.messages.last.errorCode, 'BRAIN_UNAVAILABLE');
      }
      record(ready ? 'normal_response' : 'unavailable_runtime', conv);

      if (ready) {
        // 2. Reasoning: explicit Thinking depth.
        conv.setDepth(OiDepth.normal);
        await say(t, 'Compare paper records and a spreadsheet for a school office: two pros and two cons each.');
        await until(t, () => !conv.busy && conv.messages.last.finishedStatus != null, what: 'reasoning');
        expect(conv.messages.last.tier, 'NORMAL');
        record('reasoning', conv);
        conv.setDepth(OiDepth.auto);

        // 3. Cancellation mid-stream with the Stop button.
        await say(t, 'Write a long, detailed story about a lighthouse keeper, at least 800 words.');
        await until(t, () => conv.messages.last.role == OiRole.uri && (conv.messages.last.text.length > 40 || conv.messages.last.finishedStatus != null), what: 'stream start');
        receipt['cancel_probe'] = {
          'busy': conv.busy,
          'text_chars': conv.messages.last.text.length,
          'finished': conv.messages.last.finishedStatus,
          'route': conv.messages.last.route,
          'stop_buttons': find.byKey(const ValueKey('oi-cancel')).evaluate().length,
        };
        expect(conv.busy, isTrue, reason: 'Stop must be pressed while the turn is still streaming');
        expect(conv.messages.last.finishedStatus, isNull);
        await t.tap(find.byKey(const ValueKey('oi-cancel')));
        await t.pump();
        await until(t, () => !conv.busy, what: 'cancel');
        expect(conv.messages.last.answerStatus, 'CANCELLED');
        record('cancellation', conv);
      } else {
        // Without the Brain, actions run through the explicit deterministic row (an explicit user choice).
        await t.runAsync(() => conv.selectBrain('deterministic'));
        await t.pump();
      }

      // 4. Supervised action: typed "approve" is just text; the Approve button decides.
      final before = (await t.runAsync(() async {
        await conv.refreshMemory();
        return List<String>.from(conv.memory);
      }))!;
      await say(t, 'remember that the science lab is closed on Friday');
      await until(t, () => conv.pendingApproval != null || conv.pendingConfirmation != null || (!conv.busy && conv.messages.last.finishedStatus != null), what: 'action');
      if (conv.pendingConfirmation != null) {
        await t.tap(find.byKey(const ValueKey('oi-confirm')));
        await t.pump();
        await until(t, () => conv.pendingApproval != null, what: 'approval after confirm');
      }
      expect(find.byKey(const ValueKey('oi-approval-card')), findsOneWidget);
      await t.tap(find.byKey(const ValueKey('oi-approve')));
      await t.pump();
      await until(t, () => !conv.busy && conv.messages.last.coreCode == 'SETTLED_VERIFIED', what: 'verified');
      final after = (await t.runAsync(() async {
        await conv.refreshMemory();
        return List<String>.from(conv.memory);
      }))!;
      expect(after.length, before.length + 1);
      record('supervised_action_approved', conv, extra: {'memory_before': before.length, 'memory_after': after.length});

      // 5. Denial changes nothing.
      await say(t, 'remember that the staff meeting moved to 4 pm');
      await until(t, () => conv.pendingApproval != null || conv.pendingConfirmation != null, what: 'action 2');
      if (conv.pendingConfirmation != null) {
        await t.tap(find.byKey(const ValueKey('oi-confirm')));
        await t.pump();
        await until(t, () => conv.pendingApproval != null, what: 'approval 2');
      }
      await t.tap(find.byKey(const ValueKey('oi-deny')));
      await t.pump();
      await until(t, () => !conv.busy && conv.messages.last.coreCode == 'APPROVAL_DENIED', what: 'denied');
      final afterDeny = (await t.runAsync(() async {
        await conv.refreshMemory();
        return List<String>.from(conv.memory);
      }))!;
      expect(afterDeny, after);
      record('supervised_action_denied', conv);

      // 6. Refusal: a destructive request with no qualified capability never reaches an approval card.
      await say(t, 'delete every file on my D drive right now');
      await until(t, () => !conv.busy && conv.messages.last.finishedStatus != null, what: 'refusal');
      // In this UI session Core may first ask about the intent denied just before (INTENT_CONFIRMED_NOT_EXECUTED);
      // a fresh session gets REFUSED_UNSUPPORTED (worker-level journey). Either way: no card, nothing executed.
      expect(conv.pendingApproval, isNull);
      expect(conv.messages.last.finishedStatus, isNot('ok'));
      expect(conv.messages.last.coreCode, anyOf('REFUSED_UNSUPPORTED', 'INTENT_CONFIRMED_NOT_EXECUTED'));
      final afterRefusal = (await t.runAsync(() async {
        await conv.refreshMemory();
        return List<String>.from(conv.memory);
      }))!;
      expect(afterRefusal, afterDeny);
      record('refusal_no_execution', conv);

      // 7. Deterministic command with no model: presentation command is local.
      await say(t, 'URI dashboard');
      await t.pump(const Duration(milliseconds: 300));
      expect(services.presentation.mode, UiPresentationMode.dashboard);
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await t.pump(const Duration(milliseconds: 300));
      (receipt['journeys'] as List).add({'journey': 'presentation_command_local', 'mode_reached': 'dashboard'});

      // 9. WS hardening: real health, real Dashboard Brain card, markdown, worker exit + Restart URI.
      await t.runAsync(() => conv.refreshHealth());
      await t.pump();
      final speed = measuredSpeed(conv.brainHealth);
      if (ready) {
        expect(conv.healthState, anyOf('READY', 'DEGRADED'));
        expect(speed?.tps, isNotNull);
      } else {
        expect(conv.healthState, anyOf('UNAVAILABLE', 'RECOVERING'));
      }
      expect(find.byKey(const ValueKey('oi-health-chip')), findsOneWidget);
      (receipt['journeys'] as List).add({'journey': 'health', 'state': conv.healthState, 'tps': speed?.tps,
        'source': speed?.source, 'reasons': conv.brainHealth['reasons'], 'gpu': conv.brainHealth['gpu']});

      services.presentation.setMode(UiPresentationMode.dashboard);
      for (var i = 0; i < 10; i++) {
        await t.pump(const Duration(milliseconds: 60));
      }
      expect(find.byKey(const ValueKey('oi-brain-card')), findsOneWidget);
      expect(find.text('integrated worker · brain_health'), findsOneWidget);
      (receipt['journeys'] as List).add({'journey': 'dashboard_brain_card_real',
        'speed_line': (t.widget<Text>(find.byKey(const ValueKey('oi-brain-card-speed')))).data,
        'gpu_line': (t.widget<Text>(find.byKey(const ValueKey('oi-brain-card-gpu')))).data});
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await t.pump(const Duration(milliseconds: 300));

      if (ready) {
        await say(t, 'Give three benefits of regular backups as a markdown bullet list, with the key word of each in bold.');
        await until(t, () => !conv.busy && conv.messages.last.finishedStatus != null, what: 'markdown');
        final src = conv.messages.last.text;
        await t.pump();
        expect(find.byType(OiMarkdown), findsWidgets);
        final rawShown = find.byWidgetPredicate((w) =>
            (w is Text && (w.data ?? w.textSpan?.toPlainText() ?? '').contains('**')) ||
            (w is RichText && w.text.toPlainText().contains('**')));
        expect(rawShown, findsNothing, reason: 'raw ** markers must not be shown');
        record('markdown_rendered', conv, extra: {'source_has_markers': src.contains('**') || src.contains('- '),
          'blocks': parseMarkdownBlocks(src).map((b) => b.kind.name).toList()});
      }

      // Unexpected worker exit: the real worker process is ended; the UI offers Restart URI; a fresh worker serves.
      final nonce = List.filled(64, 'a').join();
      final ident = (await t.runAsync(() => conv.runtime.call({'command': 'identity', 'nonce': nonce})))!;
      final oldPid = ident['pid'] as int;
      await t.runAsync(() async {
        Process.killPid(oldPid, ProcessSignal.sigkill);
      });
      await until(t, () => conv.workerExited, seconds: 30, what: 'worker exit noticed');
      await t.pump();
      expect(find.byKey(const ValueKey('oi-restart-worker')), findsOneWidget);
      // The button calls conv.restartWorker (simulation widget test). Here the same call runs in a real async zone:
      // the widget tester's fake zone does not advance real process I/O and timers.
      await t.runAsync(conv.restartWorker);
      await t.pump();
      expect(conv.workerExited, isFalse, reason: conv.messages.last.text);
      final ident2 = (await t.runAsync(() => conv.runtime.call({'command': 'identity', 'nonce': nonce})))!;
      expect(ident2['pid'], isNot(oldPid));
      await say(t, 'In one short sentence, what is a backup?');
      await until(t, () => !conv.busy && conv.messages.last.finishedStatus != null, what: 'after restart');
      if (ready) expect(conv.messages.last.answerStatus, 'COMPLETE');
      record('worker_exit_restart_uri', conv, extra: {'old_pid': oldPid, 'new_pid': ident2['pid'],
        'system_messages': conv.messages.where((m) => m.role == OiRole.system).map((m) => m.text).toList()});
    } finally {
      receipt['memory_end'] = conv.memory;
      final partial = File(env['URI_WS_EVIDENCE'] ?? 'build/ws_ui_live.json');
      partial.parent.createSync(recursive: true);
      partial.writeAsStringSync(const JsonEncoder.withIndent(' ').convert(receipt));
      await t.runAsync(conv.runtime.close);
    }

    // 8. Restart: a fresh worker process over the same client root recovers and serves.
    final rt2 = (await t.runAsync(() => WorkerIntegratedRuntime.fromManifest(manifest)))!;
    final conv2 = OiConversation(rt2);
    await t.runAsync(() async {
      await conv2.refreshStatus();
      await conv2.refreshMemory();
    });
    expect(conv2.memory, receipt['memory_end']);
    (receipt['journeys'] as List).add({'journey': 'restart', 'memory_preserved': conv2.memory.length, 'brain': conv2.brainStatus['state']});
    await t.runAsync(rt2.close);

    final out = File(env['URI_WS_EVIDENCE'] ?? 'build/ws_ui_live.json');
    out.parent.createSync(recursive: true);
    out.writeAsStringSync(const JsonEncoder.withIndent(' ').convert(receipt));
    await t.pumpWidget(const SizedBox.shrink());
    await t.pump(const Duration(seconds: 5)); // let the mock Hybrid client's latency timers finish
  }, skip: !live, timeout: const Timeout(Duration(minutes: 20)));
}
