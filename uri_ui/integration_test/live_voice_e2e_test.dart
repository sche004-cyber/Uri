// Live voice end-to-end run on the real Windows app (live voice phase, AC-2,
// AC-5..AC-9, AC-11). Opt-in: runs only with URI_VOICE_E2E=1 and a provisioned
// working-system installation in URI_CLIENT_MANIFEST.
//
//   set URI_VOICE_E2E=1
//   set URI_VOICE_E2E_OUT=<evidence dir>
//   set URI_VOICE_E2E_SCENARIOS=deterministic,brain   (default: deterministic)
//   set URI_CLIENT_MANIFEST=<client-manifest.json>
//   flutter test integration_test/live_voice_e2e_test.dart -d windows
//
// Everything is real except the talker: the app, the integrated worker (Core +
// Operational Intelligence + Runtime v1 when it is running), the voice process,
// the microphone and the speakers. The user's speech is a Windows voice played
// through the speakers and picked up by the microphone (labelled
// "talker: synthetic voice through the speakers" in the evidence). Gestures
// press the real talk button; nothing calls the controller directly except the
// minimised-window case, where no input can reach a minimised window.
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/voice/voice_interaction.dart';
import 'package:uri_ui/living/voice/voice_session.dart';
import 'package:uri_ui/living/widgets/living_composer.dart';
import 'package:uri_ui/main.dart' as app;
import 'package:window_manager/window_manager.dart';

final env = Platform.environment;
final bool enabled = env['URI_VOICE_E2E'] == '1';
final Directory out = Directory(
  env['URI_VOICE_E2E_OUT'] ?? '${Directory.systemTemp.path}\\uri_voice_e2e',
);
final Set<String> scenarios =
    (env['URI_VOICE_E2E_SCENARIOS'] ?? 'deterministic').split(',').toSet();

final List<Map<String, Object?>> log = [];
final Stopwatch clock = Stopwatch()..start();

void record(String kind, [Map<String, Object?> data = const {}]) =>
    log.add({'t_ms': clock.elapsedMilliseconds, 'kind': kind, ...data});

/// Plays [text] through the speakers with a Windows voice (the synthetic talker).
Future<void> talk(String text) async {
  record('talker.start', {'text': text});
  await Process.run(
    'powershell.exe',
    [
      '-NoProfile',
      '-NonInteractive',
      '-Command',
      r'Add-Type -AssemblyName System.Speech; $s=New-Object System.Speech.Synthesis.SpeechSynthesizer; '
          r"$s.SelectVoice('Microsoft Zira Desktop'); $s.Speak($env:URI_TALK); $s.Dispose()",
    ],
    environment: {'URI_TALK': text},
  );
  record('talker.end');
}

Future<void> until(
  WidgetTester tester,
  bool Function() cond, {
  Duration timeout = const Duration(seconds: 60),
  String what = '',
}) async {
  final end = DateTime.now().add(timeout);
  while (!cond()) {
    if (DateTime.now().isAfter(end)) {
      record('timeout', {'waiting_for': what});
      throw TimeoutException('waiting for $what');
    }
    await tester.pump(const Duration(milliseconds: 50));
  }
}

Future<void> shot(WidgetTester tester, String name) async {
  try {
    final view = tester.binding.renderViews.first;
    final layer = view.debugLayer! as OffsetLayer;
    final size = view.size;
    final img = await layer.toImage(Offset.zero & size, pixelRatio: 1.0);
    final bytes = await img.toByteData(format: ui.ImageByteFormat.png);
    await File('${out.path}\\$name.png')
        .writeAsBytes(bytes!.buffer.asUint8List());
    record('screenshot', {'name': name});
  } catch (e) {
    record('screenshot.failed', {'name': name, 'error': '$e'});
  }
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('live voice end to end', (tester) async {
    if (!enabled) {
      markTestSkipped('URI_VOICE_E2E is not 1');
      return;
    }
    out.createSync(recursive: true);
    record('run.start', {
      'scenarios': scenarios.toList(),
      'manifest_set': env['URI_CLIENT_MANIFEST'] != null,
    });
    app.main();
    await until(
      tester,
      () => find.byType(LivingComposer).evaluate().isNotEmpty,
      what: 'composer',
      timeout: const Duration(seconds: 90),
    );
    final services = LivingScope.of(
      tester.element(find.byType(LivingComposer).first),
    );
    final voice = services.voiceInteraction!;
    final svc = services.liveVoice!;
    final OiConversation oi = services.oi!;

    // Observers: every voice signal, final, problem, companion state and stage.
    final subs = <StreamSubscription<Object?>>[
      svc.signals.listen(
        (s) => record('signal', {
          'type': s.runtimeType.toString(),
          if (s is AudioLevel) 'speaker': s.speaker.name,
          if (s is AudioLevel) 'rms': s.rms,
          if (s is UserTranscript) 'text': s.text,
          if (s is UserTranscript) 'final': s.isFinal,
          if (s is UriSpeechStarted) 'text': s.text,
          if (s is UriSpeechEnded) 'reason': s.reason.name,
          if (s is ListeningEnded) 'reason': s.reason.name,
          if (s is VoiceFailure) 'message': s.message,
        }),
      ),
      svc.finals.listen(
        (f) => record('final', {
          'text': f.text,
          'reason': f.reason,
          'engine': f.engine,
          'audio_ms': f.audioMs,
          'transcribe_ms': f.transcribeMs,
          'uncertain': f.uncertain,
        }),
      ),
      svc.problems.listen(
        (p) => record('problem', {
          'code': p.code,
          'message': p.message,
          'warning': p.warning,
        }),
      ),
    ];
    String? lastCompanion;
    void onCompanion() {
      final s = services.companion.signal;
      final key = '${s.state.name}|${s.detail}';
      if (key != lastCompanion) {
        lastCompanion = key;
        record('companion', {
          'state': s.state.name,
          'detail': s.detail,
          'source': s.sourceName,
        });
      }
    }

    VoiceStage? lastStage;
    void onStage() {
      if (voice.stage != lastStage) {
        lastStage = voice.stage;
        record('stage', {'stage': voice.stage.name, 'notice': voice.notice});
      }
    }

    services.companion.addListener(onCompanion);
    voice.addListener(onStage);
    final sw = Stopwatch()..start();
    await svc.ensureStarted();
    await until(
      tester,
      () => svc.status.value.ready || svc.status.value.problem != null,
      what: 'voice service ready',
      timeout: const Duration(seconds: 60),
    );
    record('voice.status', {
      'state': svc.status.value.state.name,
      'engine': svc.status.value.engine,
      'inputs': [for (final d in svc.status.value.inputs) d.name],
      'privacy': svc.status.value.privacy,
      'problem': svc.status.value.problem,
      'model_load_ms': svc.status.value.modelLoadMs,
      'ready_after_ms': sw.elapsedMilliseconds,
    });
    expect(svc.status.value.ready, isTrue, reason: svc.status.value.problem);
    await oi.refreshStatus();
    record('brain.status', {'brain': oi.brainStatus});
    await shot(tester, '00_ready');

    final talkButton = find
        .byKey(const ValueKey('voice-talk'))
        .hitTestable()
        .first;

    /// Holds the real talk button while the talker speaks [text].
    Future<void> holdAndSay(String text, {String? shotName}) async {
      await until(
        tester,
        () => talkButton.evaluate().isNotEmpty,
        what: 'talk button',
      );
      final g = await tester.startGesture(tester.getCenter(talkButton));
      record('ptt.down');
      await until(
        tester,
        () => voice.stage == VoiceStage.listening,
        what: 'listening',
      );
      await tester.pump(const Duration(milliseconds: 400));
      var done = false;
      unawaited(talk(text).then((_) => done = true));
      await until(
        tester,
        () => done,
        what: 'talker',
        timeout: const Duration(seconds: 30),
      );
      if (shotName != null) await shot(tester, shotName);
      await tester.pump(const Duration(milliseconds: 400));
      await g.up();
      record('ptt.up');
    }

    Future<void> waitTurnSpoken({required String label}) async {
      await until(
        tester,
        () => voice.stage != VoiceStage.transcribing,
        what: '$label transcript',
        timeout: const Duration(seconds: 30),
      );
      await until(
        tester,
        () =>
            voice.stage == VoiceStage.speaking ||
            voice.stage == VoiceStage.idle,
        what: '$label reply',
        timeout: const Duration(seconds: 120),
      );
      if (voice.stage == VoiceStage.speaking) {
        await shot(tester, '${label}_speaking');
      }
      await until(
        tester,
        () => voice.stage == VoiceStage.idle,
        what: '$label speech end',
        timeout: const Duration(seconds: 180),
      );
      record('turn.done', {
        'label': label,
        'last_message': oi.messages.isEmpty ? null : oi.messages.last.text,
        'core_code': oi.messages.isEmpty ? null : oi.messages.last.coreCode,
        'metrics': oi.messages.isEmpty ? null : oi.messages.last.metrics,
        'timings': voice.timings.isEmpty ? null : voice.timings.last,
      });
    }

    try {
      if (scenarios.contains('brain')) {
        // UI first: the Brain host is started after this window opened. The
        // run waits for it before any scenario, so an action reaches Core with
        // a Brain to interpret it (approval card scenario D4).
        record('brain.wait');
        final until20 = DateTime.now().add(const Duration(minutes: 40));
        while (oi.brainStatus['state'] != 'READY' &&
            DateTime.now().isBefore(until20)) {
          await oi.refreshStatus();
          await tester.pump(const Duration(seconds: 3));
        }
        await oi.refreshHealth();
        record('brain.ready', {
          'brain': oi.brainStatus,
          'health': oi.brainHealth,
        });
        await shot(tester, '01_brain_ready');
      }

      if (scenarios.contains('deterministic')) {
        // D1: a local presentation command by voice. A recognition miss is
        // recorded, not fatal: the words then reach URI as an ordinary turn.
        record('scenario', {'id': 'D1 presentation command'});
        final before1 = oi.messages.length;
        await holdAndSay('URI, dashboard.');
        await until(
          tester,
          () =>
              services.presentation.mode == UiPresentationMode.dashboard ||
              (voice.stage == VoiceStage.idle && voice.lastFinal != null),
          what: 'dashboard or turn end',
          timeout: const Duration(seconds: 60),
        );
        await until(
          tester,
          () => voice.stage == VoiceStage.idle,
          what: 'D1 idle',
          timeout: const Duration(seconds: 60),
        );
        record('result', {
          'id': 'D1',
          'mode': services.presentation.mode.name,
          'final': voice.lastFinal?.text,
          'sent_as_turn': oi.messages.length > before1,
        });
        await shot(tester, 'D1_dashboard');
        services.presentation.setMode(
          UiPresentationMode.workspace,
          focus: WorkspaceFocus.conversation,
        );
        await tester.pump(const Duration(seconds: 1));

        // D2: nothing said.
        record('scenario', {'id': 'D2 silence'});
        final g = await tester.startGesture(tester.getCenter(talkButton));
        await until(
          tester,
          () => voice.stage == VoiceStage.listening,
          what: 'listening',
        );
        await tester.pump(const Duration(milliseconds: 1500));
        await g.up();
        await until(
          tester,
          () => voice.stage == VoiceStage.idle,
          what: 'D2 idle',
        );
        record('result', {
          'id': 'D2',
          'notice': voice.noticeCode,
          'final': voice.lastFinal?.reason,
        });
        await shot(tester, 'D2_no_speech');

        // D3: cancel with Esc while speaking into the microphone.
        record('scenario', {'id': 'D3 cancel'});
        final turnsBefore = oi.messages.length;
        final g3 = await tester.startGesture(tester.getCenter(talkButton));
        await until(
          tester,
          () => voice.stage == VoiceStage.listening,
          what: 'listening',
        );
        final t3 = talk('Send the monthly report to the director.');
        await tester.pump(const Duration(milliseconds: 1500));
        await tester.sendKeyEvent(LogicalKeyboardKey.escape);
        record('esc');
        await g3.up();
        var done3 = false;
        unawaited(t3.then((_) => done3 = true));
        await until(tester, () => done3, what: 'talker');
        await tester.pump(const Duration(seconds: 3));
        record('result', {
          'id': 'D3',
          'stage': voice.stage.name,
          'new_messages': oi.messages.length - turnsBefore,
        });

        // D4: an action goes to Core and stops at approval; a spoken "yes" does not approve.
        record('scenario', {'id': 'D4 approval by voice is refused'});
        await holdAndSay(
          'Remember that the laboratory is closed on Friday afternoon.',
        );
        await until(
          tester,
          () =>
              oi.pendingApproval != null ||
              (!oi.busy && voice.stage == VoiceStage.idle),
          what: 'approval card',
          timeout: const Duration(seconds: 120),
        );
        await tester.pump(const Duration(seconds: 1));
        await shot(tester, 'D4_approval_card');
        await until(
          tester,
          () => voice.stage == VoiceStage.idle,
          what: 'pointer spoken',
          timeout: const Duration(seconds: 60),
        );
        final approval = oi.pendingApproval;
        record('result', {
          'id': 'D4a',
          'approval_capability': approval?.capabilityId,
          'approval_args': approval?.arguments,
        });
        await holdAndSay('Yes, approve it.');
        await until(
          tester,
          () => voice.stage == VoiceStage.idle && !oi.busy,
          what: 'yes handled',
          timeout: const Duration(seconds: 120),
        );
        record('result', {
          'id': 'D4b',
          'approval_still_pending_or_not_executed': oi.pendingApproval != null,
          'settled_by_voice': oi.messages.any(
            (m) => m.coreCode == 'SETTLED_VERIFIED',
          ),
        });
        await shot(tester, 'D4_after_spoken_yes');
        if (oi.pendingApproval != null) {
          // Clean up through the card's own Deny button (a real click).
          final deny = find.textContaining('Deny');
          if (deny.evaluate().isNotEmpty) {
            await tester.tap(deny.first);
            record('deny.clicked');
            await tester.pump(const Duration(seconds: 2));
          }
        }
      }

      if (scenarios.contains('brain')) {
        services.presentation.setMode(UiPresentationMode.companion);
        await tester.pump(const Duration(seconds: 1));
        // B1: a conversational question answered by the Brain and spoken.
        record('scenario', {'id': 'B1 conversation'});
        await holdAndSay(
          'What is the capital of Sikkim, and what is it known for?',
          shotName: 'B1_listening',
        );
        await waitTurnSpoken(label: 'B1');

        // B2: barge-in while URI speaks.
        record('scenario', {'id': 'B2 barge-in'});
        await holdAndSay(
          'Tell me five ways to reduce paper use in a government office.',
        );
        await until(
          tester,
          () => voice.stage == VoiceStage.speaking,
          what: 'B2 speaking',
          timeout: const Duration(seconds: 120),
        );
        await tester.pump(const Duration(milliseconds: 2500));
        record('bargein.press');
        final gb = await tester.startGesture(
          tester.getCenter(
            find
                .byKey(const ValueKey('voice-stop-speaking'))
                .hitTestable()
                .first,
          ),
        );
        await tester.pump(const Duration(milliseconds: 120)); // a tap on Stop
        await gb.up();
        record('bargein.release');
        await until(
          tester,
          () =>
              voice.stage == VoiceStage.idle ||
              voice.stage == VoiceStage.listening,
          what: 'B2 stopped',
          timeout: const Duration(seconds: 10),
        );
        await tester.pump(const Duration(seconds: 2));
        if (voice.stage != VoiceStage.idle) voice.cancel();
        await until(
          tester,
          () => !oi.busy,
          what: 'B2 turn end',
          timeout: const Duration(seconds: 120),
        );

        // B3: minimised window while URI speaks (no input reaches a minimised window,
        // so the press is the controller's own call; the audio path is unchanged).
        record('scenario', {'id': 'B3 minimised'});
        await holdAndSay(
          'Give me a two sentence tip for writing a clear office note.',
        );
        await until(
          tester,
          () => voice.stage == VoiceStage.speaking,
          what: 'B3 speaking',
          timeout: const Duration(seconds: 120),
        );
        await windowManager.minimize();
        record('window.minimized');
        await tester.pump(const Duration(milliseconds: 800));
        record('minimised.state', {
          'frame_clock_hidden': services.frameClock.hidden,
          'stage': voice.stage.name,
        });
        await until(
          tester,
          () => voice.stage == VoiceStage.idle,
          what: 'B3 speech end',
          timeout: const Duration(seconds: 120),
        );
        record('result', {
          'id': 'B3',
          'frame_clock_suspended_while_minimised': services.frameClock.hidden,
        });
        await windowManager.restore();
        record('window.restored');
        await tester.pump(const Duration(seconds: 1));
      }

      if (scenarios.contains('manual')) {
        // A person drives the real app (talk button, Ctrl+Space, Esc, Stop).
        // Nothing is pressed by the test; it only records what happens and
        // takes a screenshot whenever the voice stage changes.
        final seconds =
            int.tryParse(env['URI_VOICE_E2E_MANUAL_S'] ?? '') ?? 600;
        record('scenario', {'id': 'M manual session', 'seconds': seconds});
        final end = DateTime.now().add(Duration(seconds: seconds));
        var lastShot = voice.stage;
        var n = 0;
        while (DateTime.now().isBefore(end)) {
          await tester.pump(const Duration(milliseconds: 100));
          if (voice.stage != lastShot) {
            lastShot = voice.stage;
            if (lastShot != VoiceStage.idle && n < 60) {
              n++;
              await shot(
                tester,
                'M_${n.toString().padLeft(2, '0')}_${lastShot.name}',
              );
            }
          }
        }
        record('result', {
          'id': 'M',
          'messages': [
            for (final m in oi.messages)
              {
                'role': m.role.name,
                'text': m.text.length > 400
                    ? '${m.text.substring(0, 400)}...'
                    : m.text,
                'core': m.coreCode,
                'metrics': m.metrics,
              },
          ],
          'timings': voice.timings,
        });
      }

      if (scenarios.contains('drafting')) {
        record('scenario', {'id': 'R1 drafting mode'});
        services.companionPrefs.setVoice(
          services.companionPrefs.voice.copyWith(
            inputMode: VoiceInputMode.drafting,
          ),
        );
        await holdAndSay(
          'dear sir i need leave on monday and tuesday because my mother is unwell please approve thanks ramesh',
        );
        await until(
          tester,
          () => voice.stage == VoiceStage.idle,
          what: 'R1 done',
          timeout: const Duration(seconds: 120),
        );
        record('result', {
          'id': 'R1',
          'notice': voice.noticeCode,
          'dictation_available': voice.dictationAvailable,
        });
        await shot(tester, 'R1_drafting');
        services.companionPrefs.setVoice(
          services.companionPrefs.voice.copyWith(
            inputMode: VoiceInputMode.conversation,
          ),
        );
      }
    } finally {
      services.companion.removeListener(onCompanion);
      voice.removeListener(onStage);
      for (final s in subs) {
        await s.cancel();
      }
      record('run.end');
      final levels = log
          .where((e) => e['kind'] == 'signal' && e['type'] == 'AudioLevel')
          .length;
      final compact = [
        for (final e in log)
          if (!(e['kind'] == 'signal' && e['type'] == 'AudioLevel') &&
              !(e['kind'] == 'signal' && e['type'] == 'UriSpeechProgress'))
            e,
      ];
      final levelSeries = [
        for (final e in log)
          if (e['kind'] == 'signal' && e['type'] == 'AudioLevel')
            [e['t_ms'], e['speaker'], e['rms']],
      ];
      await File('${out.path}\\e2e_events.json').writeAsString(
        const JsonEncoder.withIndent(' ')
            .convert({'audio_level_events': levels, 'events': compact}),
      );
      await File('${out.path}\\e2e_levels.json')
          .writeAsString(jsonEncode(levelSeries));
    }
  }, timeout: const Timeout(Duration(minutes: 60)));
}
