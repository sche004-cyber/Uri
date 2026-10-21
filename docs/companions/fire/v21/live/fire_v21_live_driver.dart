// EMBER V2.1 live qualification driver (copied into uri_ui/integration_test/ by run_fire_v21_live.py and
// removed afterwards). V2's driver with interleaved coexistence turns; derived from the V1 driver (docs/companions/fire/live/). URI_QUAL_MODE selects the journey:
//   first     - a first-time user: fresh preferences, default companion, select Ember in Settings (voice section
//               included, PRE-1), startup presentation, then the full state journeys with the real Brain;
//   returning - the same preferences again: Ember must come back without any choice, blink, and Settings must open
//               cleanly. Runs the ORIGINAL production main() in a real Windows window against the real integrated
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
  testWidgets('Ember V2.1 live journeys on the production main()', (t) async {
    final mode = Platform.environment['URI_QUAL_MODE'] ?? 'first';
    final brainWaitMin = int.tryParse(Platform.environment['URI_QUAL_BRAIN_WAIT_MIN'] ?? '') ?? 30;
    final out = Directory(Platform.environment['URI_QUAL_UI_OUT']!)
      ..createSync(recursive: true);
    final rows = <Map<String, Object?>>[];
    void record(String label, Map<String, Object?> fields) {
      rows.add({
        'utc': DateTime.now().toUtc().toIso8601String(),
        'label': label,
        ...fields,
      });
      File('${out.path}/observations-$mode.json').writeAsStringSync(
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
      File('${out.path}/$mode-${shots.toString().padLeft(2, '0')}-$name.png')
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
    final storedBefore = prefs.getString(CompanionPreferences.keyChoice);
    if (mode == 'first') {
      // A first-time user: nothing chosen yet (the fixture folder is new).
      if (storedBefore != null) throw StateError('first-time run found a stored companion: $storedBefore');
      await prefs.setString(wsShellPref, 'living');
      await prefs.setBool('uri.living.onboardingDone', true);
    }
    record('0 preferences before start', {'mode': mode, 'stored_choice': storedBefore});

    // Blinks of the Ember on screen: lid levels sampled from the real widget.
    Future<Map<String, Object?>> watchBlinks(Duration d) async {
      final starts = <double>[];
      final sw2 = Stopwatch()..start();
      int? last;
      var closed = 0;
      while (sw2.elapsed < d) {
        await t.pump(const Duration(milliseconds: 20));
        final f = find.byType(EmberCompanion);
        if (f.evaluate().isEmpty) continue;
        final lid = (t.state(f.first) as dynamic).lidLevel as int?;
        if (lid != null && last == null) starts.add(sw2.elapsedMilliseconds / 1000);
        if (lid == 2) closed++;
        last = lid;
      }
      final gaps = [for (var i = 1; i < starts.length; i++) double.parse((starts[i] - starts[i - 1]).toStringAsFixed(2))];
      return {'seconds': d.inSeconds, 'blink_starts_s': starts, 'gaps_s': gaps, 'fully_closed_samples': closed};
    }

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

    if (mode == 'returning') {
      phase = 'returning';
      await pumpFor(const Duration(seconds: 2));
      record('R1 returning user', {
        'choice': services.companionPrefs.choice.key,
        'ember_widgets': find.byType(EmberCompanion).evaluate().length,
        'orb_state': orbState().name,
        'brain_status': conv.brainStatus,
      });
      await shot('returning-start');
      record('R2 blinks while shown (25 s)', await watchBlinks(const Duration(seconds: 25)));
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.settings);
      await pumpFor(const Duration(milliseconds: 900));
      final view = t.binding.renderViews.first.size;
      final choice = find.byKey(const ValueKey('companion-choice-ember'));
      for (var i = 0; i < 40 && choice.evaluate().isEmpty; i++) {
        await t.dragFrom(Offset(view.width * 0.62, view.height * 0.7), const Offset(0, -320));
        await pumpFor(const Duration(milliseconds: 250));
      }
      await pumpFor(const Duration(milliseconds: 600));
      await shot('returning-settings');
      record('R3 settings opened (voice section built; PRE-1 would raise framework errors here)', {
        'ember_choice_visible': choice.evaluate().isNotEmpty,
      });
      services.presentation.setMode(UiPresentationMode.companion);
      await pumpFor(const Duration(seconds: 2));
      await shot('returning-companion');
      File('${out.path}/ui-finished-$mode.json').writeAsStringSync('{"finished":true}');
      await t.pumpWidget(const SizedBox.shrink());
      await t.runAsync(() => conv.runtime.close());
      return;
    }

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
    record('3b blinks before the Brain (15 s)', await watchBlinks(const Duration(seconds: 15)));
    File('${out.path}/ui-ready.json').writeAsStringSync('{"ready":true}');

    // 4. Wake phrase: not available in canonical URI (no wake-word recogniser).
    record('4 wake phrase', {'result': 'NOT AVAILABLE', 'reason': 'no wake-word recogniser in canonical URI; HOTWORDS only biases push-to-talk'});

    final states = <String>[];
    // Ember V2.1 final: state changes carry seconds since the UI signalled ready (the Brain host starts then), so
    // the Initializing journey shows how long each look lasted.
    final sinceReady = Stopwatch()..start();
    var lastState = '';
    var initializingShot = false;
    void sample() {
      final s = orbState().name;
      if (s != lastState) {
        states.add('$s@${sinceReady.elapsed.inSeconds}s');
        lastState = s;
      }
    }

    bool ourBrain() {
      final path = Platform.environment['URI_QUAL_BRAIN_HOST'];
      if (path == null || !File(path).existsSync()) return false;
      try {
        final host = jsonDecode(File(path).readAsStringSync()) as Map<String, dynamic>;
        final server = host['server'] as Map<String, dynamic>?;
        return server != null &&
            server['owned'] == true &&
            server['pid'] != null &&
            '${server['pid']}' == '${conv.brainStatus['pid']}';
      } on Object {
        return false;
      }
    }

    // The Brain host waits for the GPU lease (OD-8: never taken from another session). If it does not become
    // ready in time, the Brain journeys are recorded BLOCKED, not simulated.
    final end = DateTime.now().add(Duration(minutes: brainWaitMin));
    var brainBlocked = false;
    while (true) {
      await t.runAsync(conv.refreshStatus);
      sample();
      if (!initializingShot && orbState() == CompanionState.initializing) {
        initializingShot = true;
        record('3c brain initializing', {'brain_status': conv.brainStatus, 'host': conv.brainHealth['host'],
          'detail': services.companion.signal.detail});
        await shot('brain-initializing');
      }
      // Only a Brain started by this run's own Brain host counts (OD-8). The worker's 'owned' flag is about the
      // worker, not the run (live run 3: it reads false for our own host too), so the server pid the worker
      // reports must equal the pid this runtime's host records in its brain_host.json.
      if (conv.brainReady && ourBrain()) break;
      if (DateTime.now().isAfter(end)) {
        brainBlocked = true;
        break;
      }
      await pumpFor(const Duration(seconds: 2));
    }
    if (brainBlocked) {
      record('BRAIN BLOCKED', {
        'waited_minutes': brainWaitMin,
        'brain_status': conv.brainStatus,
        'state_sequence_while_waiting': List.of(states),
        'journeys_not_run': ['5 conversation', '7-8 task', 'coexistence', '9-10 error and recovery'],
      });
      await shot('brain-blocked');
      File('${out.path}/frames-$mode.json').writeAsStringSync(jsonEncode(frames));
      File('${out.path}/ui-finished-$mode.json').writeAsStringSync('{"finished":true,"brain":"blocked"}');
      await t.pumpWidget(const SizedBox.shrink());
      await t.runAsync(() => conv.runtime.close());
      return;
    }
    record('brain ready', {
      'state_sequence_while_loading': List.of(states),
      'brain_status': conv.brainStatus,
      // OD-8 proof (review R1-07): the Brain the turns go to is this run's own.
      'our_brain': ourBrain(),
      'host_record': File(Platform.environment['URI_QUAL_BRAIN_HOST'] ?? '').existsSync()
          ? jsonDecode(File(Platform.environment['URI_QUAL_BRAIN_HOST']!).readAsStringSync())['server']
          : null,
    });
    await pumpFor(const Duration(seconds: 2));
    phase = 'idle';
    await shot('idle-brain-ready');

    Future<OiMessage> send(String scenario, String text, {String? shotWhileBusy}) async {
      states.clear();
      lastState = ''; // review R3-06: the first state after a reset is recorded
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
    // F-SUCCESS (V2): a turn that finished ok shows success (joyful) for 4 s.
    record('5b after greeting', {'orb_state': orbState().name});
    await shot('reply-greeting-success');

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
    lastState = ''; // review R3-06: the first state after a reset is recorded
    await press('Approve');
    for (var i = 0; i < 40; i++) {
      sample();
      await t.pump(const Duration(milliseconds: 100));
    }
    final settled = conv.messages.lastWhere((x) => x.role == OiRole.uri);
    await shot('task-completed-success');
    record('8 task completed', {
      'core_code': settled.coreCode,
      'text': settled.text,
      'companion_states_after_approve': List.of(states),
    });
    await pumpFor(const Duration(seconds: 5));
    record('8b after the success hold', {'orb_state': orbState().name});
    await shot('task-completed-idle');
    record('8c blinks in idle (20 s)', await watchBlinks(const Duration(seconds: 20)));

    // Brain coexistence (V2.1): the same generation, alternating Ember and Solar on screen (E S E S E S), so a drift
    // in the Brain (demotion, other GPU users) does not fall on one companion only.
    const probe = 'Write four sentences about how lanterns were used in old villages.';
    for (var i = 0; i < 3; i++) {
      phase = 'gen-ember';
      services.companionPrefs.select(const CompanionChoice.living(CompanionIdentity.ember));
      services.presentation.setMode(UiPresentationMode.companion);
      await pumpFor(const Duration(seconds: 2));
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await pumpFor(const Duration(milliseconds: 600));
      await send('coexistence ember $i', probe);
      phase = 'gen-solar';
      services.companionPrefs.select(const CompanionChoice.living(CompanionIdentity.solar));
      services.presentation.setMode(UiPresentationMode.companion);
      await pumpFor(const Duration(seconds: 2));
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await pumpFor(const Duration(milliseconds: 600));
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
    lastState = ''; // review R3-06: the first state after a reset is recorded
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

    File('${out.path}/frames-$mode.json').writeAsStringSync(jsonEncode(frames));
    File('${out.path}/ui-finished-$mode.json').writeAsStringSync('{"finished":true}');
    await t.pumpWidget(const SizedBox.shrink());
    await t.runAsync(() => conv.runtime.close());
  }, timeout: const Timeout(Duration(minutes: 45)));
}
