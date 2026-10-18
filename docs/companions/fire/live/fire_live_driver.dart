// FIRE-COMPANION live qualification driver (copied into uri_ui/integration_test/ by run_fire_live.py and
// removed afterwards). Runs the ORIGINAL production main() in a real Windows window against the real integrated
// worker, paired Core server and Runtime v1 Brain. Only the input transport is automated (Flutter taps and
// TestTextInput); nothing in URI is mocked. Preferences are redirected to a fixture directory, so the owner's own
// shared_preferences are never read or written.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/gestures.dart' show kDoubleTapMinTime;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path_provider_windows/path_provider_windows.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';
import 'package:shared_preferences_windows/shared_preferences_windows.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/ember_companion.dart';
import 'package:uri_ui/living/companion/living_companion.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/main.dart' as app;
import 'package:uri_ui/working_system_app.dart';

class QualificationPaths extends PathProviderWindows {
  @override
  Future<String?> getApplicationSupportPath() async =>
      Platform.environment['URI_QUAL_PREFS'];
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Ember live journeys on the production main()', (t) async {
    final out = Directory(Platform.environment['URI_QUAL_UI_OUT']!)
      ..createSync(recursive: true);
    final rows = <Map<String, Object?>>[];
    void record(String label, Map<String, Object?> fields) {
      rows.add({
        'utc': DateTime.now().toUtc().toIso8601String(),
        'label': label,
        ...fields,
      });
      File('${out.path}/observations.json').writeAsStringSync(
        const JsonEncoder.withIndent('  ').convert(rows),
      );
    }

    Future<void> until(bool Function() ok, String label, {int seconds = 180}) async {
      final end = DateTime.now().add(Duration(seconds: seconds));
      while (!ok()) {
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: $label');
        await t.pump(const Duration(milliseconds: 100));
      }
    }

    Future<void> pumpFor(Duration d) async {
      final end = DateTime.now().add(d);
      while (DateTime.now().isBefore(end)) {
        await t.pump(const Duration(milliseconds: 50));
      }
    }

    var shots = 0;
    Future<void> shot(String name) async {
      await t.pump(const Duration(milliseconds: 200));
      final view = t.binding.renderViews.first;
      final im = await (view.debugLayer! as OffsetLayer).toImage(
        Offset.zero & view.size,
        pixelRatio: 1,
      );
      final bytes = await im.toByteData(format: ui.ImageByteFormat.png);
      shots++;
      File('${out.path}/${shots.toString().padLeft(2, '0')}-$name.png')
          .writeAsBytesSync(bytes!.buffer.asUint8List());
    }

    // Frame timings of the real window for the whole run.
    final frames = <Map<String, Object>>[];
    var phase = 'start';
    SchedulerBinding.instance.addTimingsCallback((list) {
      for (final f in list) {
        frames.add({
          'phase': phase,
          'build_ms': f.buildDuration.inMicroseconds / 1000,
          'raster_ms': f.rasterDuration.inMicroseconds / 1000,
        });
      }
    });

    t.testTextInput.register();
    addTearDown(t.testTextInput.unregister);
    record('automation input transport', {
      'keyboard': 'Flutter TestTextInput',
      'pointer': 'Flutter tester taps on the real window',
      'physical_input_qualified': false,
      'Brain_Core_worker_mocked': false,
    });
    SharedPreferencesStorePlatform.instance = SharedPreferencesWindows()
      ..pathProvider = QualificationPaths();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(wsShellPref, 'living');
    await prefs.setBool('uri.living.onboardingDone', true);

    // 1. Starting URI.
    final sw = Stopwatch()..start();
    app.main();
    await until(() => find.byType(WorkingSystemRoot).evaluate().isNotEmpty, 'production manifest opt-in');
    await until(() => find.byType(LivingScope).evaluate().isNotEmpty, 'integrated worker bootstrap');
    final services = t.widget<LivingScope>(find.byType(LivingScope).first).services;
    final conv = services.oi!;
    CompanionState? orbStateOrNull() {
      final f = find.byKey(LivingShell.orbKey);
      return f.evaluate().isEmpty ? null : t.widget<LivingCompanion>(f).state;
    }
    await until(() => orbStateOrNull() != null, 'living shell with companion', seconds: 60);
    CompanionState orbState() => orbStateOrNull() ?? CompanionState.idle;
    record('1 start', {
      'seconds_to_shell': sw.elapsedMilliseconds / 1000,
      'manifest': Platform.environment['URI_CLIENT_MANIFEST'],
      'default_companion': services.companionPrefs.choice.key,
      'orb_state': orbState().name,
      'brain_status': conv.brainStatus,
    });
    await shot('start-default-companion');

    // 2. Selecting the new fire companion through the real settings picker.
    phase = 'select';
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.settings);
    await pumpFor(const Duration(milliseconds: 900));
    final choice = find.byKey(const ValueKey('companion-choice-ember'));
    // The companion section is at the end of a lazily built settings list:
    // scroll it like a user would until the picker is built.
    final view = t.binding.renderViews.first.size;
    for (var i = 0; i < 40 && choice.evaluate().isEmpty; i++) {
      await t.dragFrom(Offset(view.width * 0.62, view.height * 0.7), const Offset(0, -320));
      await pumpFor(const Duration(milliseconds: 250));
    }
    await until(() => choice.evaluate().isNotEmpty, 'Ember in the companion picker', seconds: 20);
    await t.ensureVisible(choice);
    await pumpFor(const Duration(milliseconds: 300));
    await shot('settings-picker-before');
    await t.tap(choice);
    await pumpFor(const Duration(milliseconds: 900));
    await shot('settings-ember-selected');
    record('2 select ember', {
      'choice': services.companionPrefs.choice.key,
      'ember_widgets': find.byType(EmberCompanion).evaluate().length,
      'stored_choice': (await SharedPreferences.getInstance()).getString(CompanionPreferences.keyChoice),
    });

    // 3. Idle in Companion mode (the Brain is still loading or waiting here).
    phase = 'idle';
    services.presentation.setMode(UiPresentationMode.companion);
    await pumpFor(const Duration(seconds: 2));
    record('3 companion mode before brain', {'orb_state': orbState().name, 'brain_status': conv.brainStatus});
    await shot('companion-before-brain');
    File('${out.path}/ui-ready.json').writeAsStringSync('{"ready":true}');

    // 4. Wake phrase: not available in canonical URI (no wake-word recogniser).
    record('4 wake phrase', {'result': 'NOT AVAILABLE', 'reason': 'no wake-word recogniser in canonical URI; HOTWORDS only biases push-to-talk'});

    final states = <String>[];
    void sample() {
      final s = orbState().name;
      if (states.isEmpty || states.last != s) states.add(s);
    }

    final end = DateTime.now().add(const Duration(minutes: 9));
    while (true) {
      await t.runAsync(conv.refreshStatus);
      sample();
      if (conv.brainReady) break;
      if (DateTime.now().isAfter(end)) throw StateError('Timeout: Brain ready');
      await pumpFor(const Duration(seconds: 2));
    }
    record('brain ready', {'state_sequence_while_loading': List.of(states), 'brain_status': conv.brainStatus});
    await pumpFor(const Duration(seconds: 2));
    phase = 'idle';
    await shot('idle-brain-ready');

    Future<OiMessage> send(String scenario, String text, {String? shotWhileBusy}) async {
      states.clear();
      final count = conv.messages.length;
      final timer = Stopwatch()..start();
      await t.enterText(find.byKey(const ValueKey('living-composer-field')), text);
      await t.tap(find.byKey(const ValueKey('living-composer-send')));
      await t.pump(const Duration(milliseconds: 100));
      var shotTaken = shotWhileBusy == null;
      await until(() {
        sample();
        return conv.messages.length > count;
      }, 'submitted');
      final end = DateTime.now().add(const Duration(seconds: 240));
      while (conv.busy) {
        sample();
        if (!shotTaken && timer.elapsedMilliseconds > 700) {
          shotTaken = true;
          await shot(shotWhileBusy!);
        }
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: $scenario');
        await t.pump(const Duration(milliseconds: 50));
      }
      await pumpFor(const Duration(milliseconds: 600));
      sample();
      final m = conv.messages.skip(count).lastWhere((x) => x.role == OiRole.uri);
      record('turn', {
        'scenario': scenario,
        'request': text,
        'text': m.text,
        'answer_status': m.answerStatus,
        'core_code': m.coreCode,
        'metrics': m.metrics,
        'application_seconds': timer.elapsedMilliseconds / 1000,
        'companion_states': List.of(states),
        'identity': services.companionPrefs.choice.key,
      });
      return m;
    }

    Future<void> press(String label) async {
      await until(() => find.text(label).evaluate().isNotEmpty, 'button $label');
      await t.tap(find.text(label).first);
      await t.pump(const Duration(milliseconds: 100));
      await until(() => !conv.busy, 'decision terminal');
    }

    // 5. Single click on the companion opens the conversation; listening and responding.
    phase = 'conversation';
    await t.tap(find.byKey(LivingShell.orbKey));
    await pumpFor(const Duration(milliseconds: 900));
    await shot('single-click-conversation');
    record('5 single click', {'mode': services.presentation.mode.name});
    if (find.byKey(const ValueKey('living-composer-field')).evaluate().isEmpty) {
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await pumpFor(const Duration(milliseconds: 900));
      record('composer not on the companion panel; opened Workspace conversation', {});
    }
    phase = 'turn-greeting';
    await send('greeting', 'Hello URI', shotWhileBusy: 'thinking-during-greeting');
    await shot('reply-greeting');

    // 6. Switching between conversation and dashboard (double-click and the mode controls).
    phase = 'modes';
    services.presentation.setMode(UiPresentationMode.companion);
    await pumpFor(const Duration(milliseconds: 900));
    await t.tap(find.byKey(LivingShell.orbKey));
    await t.pump(kDoubleTapMinTime);
    await t.tap(find.byKey(LivingShell.orbKey));
    await pumpFor(const Duration(milliseconds: 900));
    record('6 double click', {'mode': services.presentation.mode.name});
    await shot('double-click-workspace');
    services.presentation.setMode(UiPresentationMode.dashboard);
    await pumpFor(const Duration(milliseconds: 900));
    await shot('dashboard');
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
    await pumpFor(const Duration(milliseconds: 900));

    // 7-8. A real task with approval, completed.
    phase = 'task';
    await send('task request', 'remember that the science lab is closed on Friday', shotWhileBusy: 'thinking-task');
    if (conv.pendingConfirmation != null) {
      await pumpFor(const Duration(milliseconds: 600));
      await shot('awaiting-confirmation');
      record('confirmation', {'orb_state': orbState().name});
      await press('Yes, continue');
    }
    await until(() => conv.pendingApproval != null, 'approval card', seconds: 120);
    await pumpFor(const Duration(seconds: 2));
    record('7 approval shown', {'orb_state': orbState().name, 'arguments': conv.pendingApproval!.arguments});
    await shot('awaiting-approval');
    states.clear();
    await press('Approve');
    for (var i = 0; i < 40; i++) {
      sample();
      await t.pump(const Duration(milliseconds: 100));
    }
    final settled = conv.messages.lastWhere((x) => x.role == OiRole.uri);
    record('8 task completed', {
      'core_code': settled.coreCode,
      'text': settled.text,
      'companion_states_after_approve': List.of(states),
    });
    await shot('task-completed');

    // Brain coexistence: the same generation with Ember and with Solar on screen.
    const probe = 'Write four sentences about how lanterns were used in old villages.';
    phase = 'gen-ember';
    services.presentation.setMode(UiPresentationMode.companion);
    await pumpFor(const Duration(milliseconds: 900));
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
    await pumpFor(const Duration(milliseconds: 600));
    for (var i = 0; i < 2; i++) {
      await send('coexistence ember $i', probe);
    }
    phase = 'gen-solar';
    services.companionPrefs.select(const CompanionChoice.living(CompanionIdentity.solar));
    await pumpFor(const Duration(seconds: 2));
    for (var i = 0; i < 2; i++) {
      await send('coexistence solar $i', probe);
    }
    services.companionPrefs.select(const CompanionChoice.living(CompanionIdentity.ember));
    await pumpFor(const Duration(seconds: 2));

    // 9-10. A recoverable error: the run script stops the Brain host; URI must show it and return.
    phase = 'error';
    services.presentation.setMode(UiPresentationMode.companion);
    await pumpFor(const Duration(seconds: 1));
    File('${out.path}/stop-brain.json').writeAsStringSync('{"stop":true}');
    states.clear();
    final stopEnd = DateTime.now().add(const Duration(minutes: 3));
    while (conv.brainReady) {
      await t.runAsync(conv.refreshStatus);
      sample();
      if (DateTime.now().isAfter(stopEnd)) break;
      await pumpFor(const Duration(seconds: 2));
    }
    await pumpFor(const Duration(seconds: 3));
    sample();
    record('9 brain stopped', {'orb_state': orbState().name, 'brain_status': conv.brainStatus, 'states': List.of(states)});
    await shot('brain-unavailable');
    final failed = await send('request while Brain unavailable', 'What is 2 plus 3?');
    record('9b request outcome', {'answer_status': failed.answerStatus, 'core_code': failed.coreCode});
    await shot('error-visible');
    File('${out.path}/restart-brain.json').writeAsStringSync('{"restart":true}');
    final backEnd = DateTime.now().add(const Duration(minutes: 9));
    while (!conv.brainReady) {
      await t.runAsync(conv.refreshStatus);
      sample();
      if (DateTime.now().isAfter(backEnd)) throw StateError('Timeout: Brain back');
      await pumpFor(const Duration(seconds: 2));
    }
    phase = 'recovered';
    final back = await send('after recovery', 'What is 9 plus 6? Reply only with the number.');
    services.presentation.setMode(UiPresentationMode.companion);
    await pumpFor(const Duration(seconds: 3));
    record('10 recovered to idle', {
      'reply': back.text,
      'orb_state': orbState().name,
      'states_through_recovery': List.of(states),
    });
    await shot('recovered-idle');

    File('${out.path}/frames.json').writeAsStringSync(jsonEncode(frames));
    File('${out.path}/ui-finished.json').writeAsStringSync('{"finished":true}');
    await t.pumpWidget(const SizedBox.shrink());
    await t.runAsync(() => conv.runtime.close());
  }, timeout: const Timeout(Duration(minutes: 45)));
}
