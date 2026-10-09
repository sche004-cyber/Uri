/// LIVE (opt-in, TI-AC9/AC11): the owner's warden demonstration typed into the
/// REAL Living composer, driving the REAL integrated worker (C1 gates, paired
/// Core) and Runtime v1. Checks what the Draft panel shows after each step and
/// presses the real Undo/Redo buttons; then repeats step 1 as a SIMULATED
/// transcript (composer toggle) and checks the labels.
///
///   `set URI_WS_LIVE=1 & set URI_CLIENT_MANIFEST=<client manifest> & flutter test test/ws_live/ti_ui_live_test.dart`
///
/// Evidence: JSON receipt at `URI_TI_EVIDENCE` (default build/ti_ui_live.json).
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'package:uri_ui/services/mock_uri_client.dart';

final env = Platform.environment;
final live = env['URI_WS_LIVE'] == '1';
final receipt = <String, dynamic>{'steps': <Map<String, dynamic>>[]};

Future<void> until(WidgetTester t, bool Function() ok, {int seconds = 240, String what = ''}) async {
  final end = DateTime.now().add(Duration(seconds: seconds));
  while (!ok()) {
    if (DateTime.now().isAfter(end)) throw StateError('timeout waiting for $what');
    await t.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 100)));
    await t.pump();
  }
}

Future<void> say(WidgetTester t, OiConversation c, String text) async {
  final before = c.messages.length;
  await t.enterText(find.byKey(const ValueKey('living-composer-field')), text);
  await t.pump();
  await t.tap(find.byKey(const ValueKey('living-composer-send')));
  await t.pump();
  await until(t, () => c.messages.length > before + 1 && !c.busy && c.messages.last.finishedStatus != null,
      what: text);
  await t.pump();
}

void record(String step, OiConversation c, WidgetTester t) {
  final d = c.draft;
  (receipt['steps'] as List).add({
    'step': step,
    'route': c.messages.last.route,
    'finished': c.messages.last.finishedStatus,
    'error': c.messages.last.errorCode,
    'chat_line': c.messages.last.text,
    'version_label': find.byKey(const ValueKey('draft-version')).evaluate().isEmpty
        ? null
        : (t.widget<Text>(find.byKey(const ValueKey('draft-version'))).data),
    'source_label': d?.sourceLabel,
    'draft_text': d?.current.text,
    'changed': d?.current.changed.toList(),
    'flags': [for (final f in d?.current.flags ?? const []) '${f.code}/${f.severity}'],
    'can_undo': d?.canUndo,
    'can_redo': d?.canRedo,
  });
}

void main() {
  testWidgets('warden demonstration through the real Living UI and Draft panel', (t) async {
    SharedPreferences.setMockInitialValues({'uri.living.onboardingDone': true});
    await t.binding.setSurfaceSize(const Size(1400, 900));
    final rt = (await t.runAsync(() => WorkerIntegratedRuntime.fromManifest(env['URI_CLIENT_MANIFEST'])))!;
    final conv = OiConversation(rt);
    final services = LivingApp.buildIntegratedServices(conv);
    services.effects.setReducedMotion(true);
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
    final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
    await t.runAsync(conv.refreshStatus);
    receipt['brain_status'] = conv.brainStatus['state'];
    expect(conv.brainReady, isTrue, reason: 'Runtime v1 must be READY');
    await t.pumpWidget(LivingApp(appState: appState, services: services, skipOnboarding: true));
    await t.pump(const Duration(milliseconds: 200));

    try {
      await say(t, conv, 'URI draft a letter to the warden regarding five students, sorry seven students, who left '
          'the hostel on Monday without permission. Make it formal.');
      record('1_create', conv, t);
      expect(find.byKey(const ValueKey('draft-panel')), findsOneWidget);
      expect(find.text('Version 1 of 1'), findsOneWidget);
      expect(find.text('Typed'), findsOneWidget);
      final v1 = conv.draft!.current.text.toLowerCase();
      expect(v1.contains('seven'), isTrue);

      await say(t, conv, "Actually, don't say without permission. Say they left without recording their departure in "
          'the hostel register.');
      record('2_revise_allegation', conv, t);
      expect(find.text('Version 2 of 2'), findsOneWidget);
      final v2 = conv.draft!.current.text;
      expect(v2.toLowerCase().contains('without permission'), isFalse);
      expect(v2.toLowerCase().contains('hostel register'), isTrue);

      await say(t, conv, 'Make it more diplomatic and shorten the second paragraph.');
      record('3_diplomatic', conv, t);
      expect(find.text('Version 3 of 3'), findsOneWidget);
      await t.tap(find.text('Changes'));
      await t.pump();
      expect(find.byKey(const ValueKey('draft-diff')), findsOneWidget);
      await t.tap(find.text('Current'));
      await t.pump();

      await say(t, conv, 'Undo the last change.');
      record('4_undo_typed', conv, t);
      expect(find.text('Version 2 of 3'), findsOneWidget);
      expect(conv.draft!.current.text, v2);

      // The real buttons: Redo then Undo again (structured draft_op, no model).
      await t.tap(find.byKey(const ValueKey('draft-redo')));
      await until(t, () => conv.draft!.position == 3, what: 'redo');
      record('5_redo_button', conv, t);
      await t.tap(find.byKey(const ValueKey('draft-undo')));
      await until(t, () => conv.draft!.position == 2, what: 'undo button');
      record('6_undo_button', conv, t);

      // Simulated transcript: same words, toggled in the composer; labelled everywhere.
      await t.tap(find.byKey(const ValueKey('living-composer-transcript')));
      await t.pump();
      expect(conv.transcriptMode, isTrue);
      await say(t, conv, 'um URI write a letter to the warden about the students leaving hostel yesterday, no wait, '
          'on the 6th, and make it formal');
      record('7_simulated_transcript', conv, t);
      expect(conv.draft!.simulatedTranscript, isTrue);
      expect(find.text('Simulated transcript'), findsWidgets);
      final t7 = conv.draft!.current.text.toLowerCase();
      expect(t7.contains('6th') || t7.contains('sixth'), isTrue);
      expect(t7.contains('yesterday'), isFalse);
      await t.tap(find.text('Original'));
      await t.pump();
      expect(find.textContaining('SIMULATED input (no microphone)'), findsOneWidget);
      await t.tap(find.byKey(const ValueKey('living-composer-transcript')));
      await t.pump();
    } finally {
      final out = File(env['URI_TI_EVIDENCE'] ?? 'build/ti_ui_live.json');
      out.parent.createSync(recursive: true);
      out.writeAsStringSync(const JsonEncoder.withIndent(' ').convert(receipt));
      await t.runAsync(rt.close);
    }
  }, skip: !live, timeout: const Timeout(Duration(minutes: 20)));
}
