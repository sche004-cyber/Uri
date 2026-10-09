import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/voice/voice_controls.dart';
import 'package:uri_ui/living/voice/voice_interaction.dart';
import 'package:uri_ui/living/voice/voice_session.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'package:uri_ui/services/live_voice_service.dart';
import 'package:uri_ui/theme/uri_theme.dart';

/// The voice process seen through its line protocol; tests push its events.
class FakeVoiceTransport implements VoiceTransport {
  final sent = <Map<String, Object?>>[];
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  final _exit = Completer<int>();

  void push(Map<String, dynamic> e) => _events.add(e);

  List<String> get cmds => [for (final c in sent) '${c['cmd']}'];

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;

  @override
  void send(Map<String, Object?> command) => sent.add(command);

  @override
  Future<int> get exitCode => _exit.future;

  void die() {
    if (!_exit.isCompleted) _exit.complete(1);
  }

  @override
  Future<void> close() async {
    sent.add(const {'cmd': 'shutdown'});
    die();
  }
}

class FakeRuntime implements IntegratedRuntime {
  final commands = <Map<String, dynamic>>[];
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  int _turn = 0;

  void emit(
    String turnId,
    String type, [
    Map<String, dynamic> data = const {},
  ]) => _events.add({
    'schema': 'uri.oi.event.v1',
    'turn_id': turnId,
    'type': type,
    'data': data,
  });

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;

  @override
  bool get closed => false;

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    commands.add(command);
    if (command['command'] == 'oi_turn') {
      return {'turn_id': 't${++_turn}', 'accepted': true};
    }
    return {'ok': true};
  }

  @override
  Future<void> close() async {}

  @override
  Future<void> kill() async {}
}

Map<String, dynamic> ready({
  String privacy = 'allowed',
  Map<String, dynamic>? modelError,
}) => {
  'ev': 'ready',
  'engine': 'faster-whisper-base.en-int8',
  'model_ok': modelError == null,
  'model_error': modelError,
  'model_load_ms': 900,
  'privacy': {
    'state': privacy,
    'detail': 'Windows blocks microphone access for desktop apps',
  },
  'inputs': [
    {
      'name': 'Microphone (Test)',
      'index': 1,
      'api': 'Windows WASAPI',
      'default': true,
    },
    {'name': 'USB Mic', 'index': 2, 'api': 'Windows WASAPI', 'default': false},
  ],
};

Future<void> pump() => Future<void>.delayed(Duration.zero);

void main() {
  late FakeVoiceTransport t;
  late LiveVoiceService svc;
  late List<VoiceSignal> signals;

  setUp(() async {
    t = FakeVoiceTransport();
    svc = LiveVoiceService(launch: () async => t);
    signals = [];
    svc.signals.listen(signals.add);
  });

  group('LiveVoiceService', () {
    test(
      'starts once, says hello, and reports readiness and devices',
      () async {
        expect(await svc.ensureStarted(), isTrue);
        expect(await svc.ensureStarted(), isTrue);
        expect(t.cmds, ['hello']);
        t.push(ready());
        await pump();
        final st = svc.status.value;
        expect(st.state, VoiceServiceState.ready);
        expect(st.inputs.map((d) => d.name), ['Microphone (Test)', 'USB Mic']);
        expect(st.inputs.first.isDefault, isTrue);
        expect(svc.simulated, isFalse);
      },
    );

    test('a denied microphone is a specific, recoverable problem', () async {
      await svc.ensureStarted();
      t.push(ready(privacy: 'denied'));
      await pump();
      expect(svc.status.value.state, VoiceServiceState.degraded);
      expect(svc.status.value.problemCode, 'MIC_DENIED');
      expect(
        svc.status.value.problem,
        contains('Privacy & security > Microphone'),
      );
    });

    test(
      'a model that fails its integrity check is reported, not hidden',
      () async {
        await svc.ensureStarted();
        t.push(
          ready(
            modelError: {
              'code': 'MODEL_INTEGRITY',
              'message': 'hash mismatch: model.bin',
            },
          ),
        );
        await pump();
        expect(svc.status.value.problemCode, 'MODEL_INTEGRITY');
      },
    );

    test('events become presentation signals; the final transcript is separate data', () async {
      await svc.ensureStarted();
      final finals = <VoiceFinal>[];
      svc.finals.listen(finals.add);
      for (final e in [
        {'ev': 'listen.started', 'id': 'c1'},
        {'ev': 'listen.speech', 'id': 'c1'},
        {'ev': 'listen.level', 'id': 'c1', 'rms': 0.05, 'block_ms': 20},
        {'ev': 'listen.partial', 'id': 'c1', 'text': 'what is'},
        {'ev': 'listen.closed', 'id': 'c1', 'reason': 'released'},
        {
          'ev': 'listen.final',
          'id': 'c1',
          'text': 'What is the time?',
          'reason': 'completed',
          'engine': 'faster-whisper-base.en-int8',
          'audio_ms': 1500,
          'transcribe_ms': 300,
          'uncertain': ['time'],
        },
        {'ev': 'speak.started', 'id': 'u1', 'text': 'It is noon.'},
        {'ev': 'speak.level', 'id': 'u1', 'rms': 0.1, 'block_ms': 20},
        {'ev': 'speak.progress', 'id': 'u1', 'ms': 200},
        {'ev': 'speak.ended', 'id': 'u1', 'reason': 'interrupted'},
      ]) {
        t.push(e);
      }
      await pump();
      expect(signals.map((s) => s.runtimeType.toString()), [
        'ListeningStarted',
        'UserSpeechStarted',
        'AudioLevel',
        'UserTranscript',
        'ListeningEnded',
        'UriSpeechStarted',
        'AudioLevel',
        'UriSpeechProgress',
        'UriSpeechEnded',
      ]);
      expect((signals[2] as AudioLevel).speaker, VoiceSpeaker.user);
      expect((signals[6] as AudioLevel).speaker, VoiceSpeaker.uri);
      expect((signals[8] as UriSpeechEnded).reason, VoiceEndReason.interrupted);
      expect(finals.single.text, 'What is the time?');
      expect(finals.single.uncertain, ['time']);
    });

    test('a capture error becomes a visible failure', () async {
      await svc.ensureStarted();
      final problems = <VoiceProblem>[];
      svc.problems.listen(problems.add);
      t.push({
        'ev': 'listen.error',
        'id': 'c1',
        'code': 'MIC_OPEN_FAILED',
        'message': 'busy device',
      });
      await pump();
      expect(signals.single, isA<VoiceFailure>());
      expect(problems.single.code, 'MIC_OPEN_FAILED');
    });

    test(
      'the process dying resets the presentation and marks voice unavailable',
      () async {
        await svc.ensureStarted();
        t.die();
        await pump();
        expect(svc.status.value.state, VoiceServiceState.unavailable);
        expect(svc.status.value.problemCode, 'VOICE_SERVICE_STOPPED');
        expect(signals.last, isA<VoiceReset>());
      },
    );

    test('speak sends the user voice, rate, pitch and volume', () async {
      await svc.ensureStarted();
      svc.speak(
        'u1',
        'Hello.',
        const VoicePreferences(
          voiceId: 'onecore:Microsoft Mark',
          rate: 3,
          pitch: -2,
          volume: 70,
        ),
        last: false,
      );
      final c = t.sent.last;
      expect(c['cmd'], 'speak');
      expect(c['final'], false);
      expect(c['voice'], {
        'engine': 'onecore',
        'name': 'Microsoft Mark',
        'rate': 3,
        'pitch': -2,
        'volume': 70,
      });
    });

    test('dispose shuts the process down', () async {
      await svc.ensureStarted();
      await svc.dispose();
      expect(t.cmds.last, 'shutdown');
    });
  });

  group('VoiceInteractionController', () {
    late FakeRuntime rt;
    late OiConversation oi;
    late CompanionPreferences prefs;
    late UiPresentationController presentation;
    late VoiceInteractionController ctl;
    late List<String> kept;

    setUp(() async {
      rt = FakeRuntime();
      oi = OiConversation(rt, sessionId: 's');
      prefs = CompanionPreferences();
      presentation = UiPresentationController();
      kept = [];
      ctl = VoiceInteractionController(
        service: svc,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
        keepInComposer: kept.add,
        noticeHold: const Duration(milliseconds: 50),
      );
      await svc.ensureStarted();
      t.push(ready());
      await pump();
    });

    tearDown(() {
      ctl.dispose();
      oi.dispose();
    });

    String captureId() =>
        '${t.sent.lastWhere((c) => c['cmd'] == 'listen_start')['id']}';

    Future<void> finalText(String text, {String reason = 'completed'}) async {
      t.push({
        'ev': 'listen.final',
        'id': captureId(),
        'text': text,
        'reason': reason,
        'engine': 'faster-whisper-base.en-int8',
        'audio_ms': 1000,
        'transcribe_ms': 200,
        'uncertain': <String>[],
      });
      await pump();
      await pump();
    }

    test('push to talk opens the chosen microphone and release asks for the transcript', () async {
      prefs.setVoice(
        prefs.voice.copyWith(
          microphone: 'USB Mic',
          vocabulary: 'Gangtok Tshering',
        ),
      );
      await ctl.pressTalk();
      expect(ctl.stage, VoiceStage.listening);
      final start = t.sent.lastWhere((c) => c['cmd'] == 'listen_start');
      expect(start['device'], 'USB Mic');
      expect(start['vocabulary'], 'Gangtok Tshering');
      ctl.releaseTalk();
      expect(t.cmds.last, 'listen_stop');
      expect(ctl.stage, VoiceStage.transcribing);
      expect(ctl.signal.state, CompanionState.thinking);
      expect(ctl.signal.detail, 'Transcribing');
    });

    test('a spoken question becomes an ordinary turn and the reply is spoken by sentence', () async {
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('What is the capital of Sikkim?');
      final turn = rt.commands.lastWhere((c) => c['command'] == 'oi_turn');
      expect(turn['text'], 'What is the capital of Sikkim?');
      expect(ctl.stage, VoiceStage.waiting);
      rt.emit('t1', 'answer.delta', {
        'text': 'The capital is Gangtok. It is in the ',
      });
      await pump();
      var speaks = t.sent.where((c) => c['cmd'] == 'speak').toList();
      expect(speaks.map((c) => c['text']), ['The capital is Gangtok.']);
      expect(ctl.stage, VoiceStage.speaking);
      rt.emit('t1', 'answer.delta', {'text': 'east of India.'});
      rt.emit('t1', 'answer.done', {'status': 'COMPLETE'});
      rt.emit('t1', 'turn.finished', {'status': 'COMPLETE'});
      await pump();
      speaks = t.sent.where((c) => c['cmd'] == 'speak').toList();
      expect(speaks.map((c) => c['text']), [
        'The capital is Gangtok.',
        'It is in the east of India.',
        '',
      ]);
      expect(speaks.last['final'], true);
      final utt = '${speaks.first['id']}';
      t.push({'ev': 'speak.ended', 'id': utt, 'reason': 'completed'});
      await pump();
      expect(ctl.stage, VoiceStage.idle);
    });

    test(
      'speech never decides: an approval is pointed to, never answered',
      () async {
        await ctl.pressTalk();
        ctl.releaseTalk();
        await finalText('Remember that the lab is closed on Friday.');
        rt.emit('t1', 'approval.required', {
          'capability_id': 'remember_fact',
          'arguments': {'fact': 'the lab is closed on Friday'},
          'approval_digest': 'd1',
        });
        rt.emit('t1', 'turn.finished', {'status': 'WAITING'});
        await pump();
        final speaks = t.sent
            .where((c) => c['cmd'] == 'speak')
            .map((c) => c['text'])
            .toList();
        expect(speaks.first, contains('review the card on screen'));
        // The user then says "yes, approve it": it is only ever a turn text.
        await ctl.pressTalk();
        ctl.releaseTalk();
        await finalText('Yes, approve it.');
        expect(rt.commands.where((c) => c['command'] == 'oi_decide'), isEmpty);
        expect(rt.commands.where((c) => c['command'] == 'oi_confirm'), isEmpty);
        expect(oi.pendingApproval, isNotNull);
      },
    );

    test('a local presentation command is applied, not sent', () async {
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('URI, dashboard.');
      expect(rt.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
      expect(presentation.mode, UiPresentationMode.dashboard);
    });

    test('nothing heard: a notice, nothing sent', () async {
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('', reason: 'no_speech');
      expect(rt.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
      expect(ctl.noticeCode, 'NO_SPEECH');
      expect(ctl.stage, VoiceStage.idle);
    });

    test(
      'a punctuation-only transcript is not sent (noise, live run 3)',
      () async {
        await ctl.pressTalk();
        ctl.releaseTalk();
        await finalText('.');
        expect(rt.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
        expect(ctl.noticeCode, 'NO_SPEECH');
      },
    );

    test('cancel discards the capture: a late transcript is ignored', () async {
      await ctl.pressTalk();
      final id = captureId();
      ctl.cancel();
      expect(t.cmds.last, 'listen_cancel');
      t.push({
        'ev': 'listen.final',
        'id': id,
        'text': 'Send the report',
        'reason': 'completed',
        'engine': 'e',
        'uncertain': <String>[],
      });
      await pump();
      expect(rt.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
    });

    test(
      'drafting without a draft desk keeps the words and sends nothing',
      () async {
        prefs.setVoice(
          prefs.voice.copyWith(inputMode: VoiceInputMode.drafting),
        );
        await ctl.pressTalk();
        ctl.releaseTalk();
        await finalText('dear sir i need leave on monday');
        expect(rt.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
        expect(kept, ['dear sir i need leave on monday']);
        expect(ctl.noticeCode, 'DRAFTING_UNAVAILABLE');
      },
    );

    test(
      'drafting with a draft desk hands over the raw transcript and engine',
      () async {
        final got = <(String, String)>[];
        final c2 = VoiceInteractionController(
          service: svc,
          preferences: prefs,
          presentation: presentation,
          oi: oi,
          dictation: (raw, {required engine, uncertain = const []}) async =>
              got.add((raw, engine)),
        );
        prefs.setVoice(
          prefs.voice.copyWith(inputMode: VoiceInputMode.drafting),
        );
        await c2.pressTalk();
        c2.releaseTalk();
        await finalText('dear sir i need leave on monday');
        expect(got, [
          ('dear sir i need leave on monday', 'faster-whisper-base.en-int8'),
        ]);
        expect(rt.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
        c2.dispose();
      },
    );

    test('talking while URI speaks interrupts the reply (barge-in)', () async {
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('Tell me a story.');
      rt.emit('t1', 'answer.delta', {'text': 'Once upon a time. '});
      rt.emit('t1', 'answer.done', {'status': 'COMPLETE'});
      rt.emit('t1', 'turn.finished', {'status': 'COMPLETE'});
      await pump();
      expect(ctl.stage, VoiceStage.speaking);
      await ctl.pressTalk();
      expect(ctl.stage, VoiceStage.listening);
      expect(
        t.cmds.last,
        'listen_start',
      ); // the service stops speech first (half duplex)
    });

    test('a refused press while URI is still answering says why', () async {
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('Long question?');
      expect(oi.busy, isTrue);
      expect(ctl.stage, VoiceStage.waiting);
      await ctl.pressTalk();
      expect(ctl.noticeCode, 'BUSY');
    });

    test('speak replies off: nothing is spoken', () async {
      prefs.setVoice(prefs.voice.copyWith(speakReplies: false));
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('Hello?');
      rt.emit('t1', 'answer.delta', {'text': 'Hi there. '});
      rt.emit('t1', 'turn.finished', {'status': 'COMPLETE'});
      await pump();
      expect(t.cmds.where((c) => c == 'speak'), isEmpty);
      expect(ctl.stage, VoiceStage.idle);
    });

    test(
      'long replies are cut at a sentence end and say the rest is on screen',
      () async {
        final c2 = VoiceInteractionController(
          service: svc,
          preferences: prefs,
          presentation: presentation,
          oi: oi,
          maxSpokenChars: 40,
        );
        await c2.pressTalk();
        c2.releaseTalk();
        await finalText('Explain.');
        rt.emit('t1', 'answer.delta', {
          'text': 'First sentence is here. Second sentence is longer than that. Third. ',
        });
        rt.emit('t1', 'turn.finished', {'status': 'COMPLETE'});
        await pump();
        final speaks = t.sent
            .where((c) => c['cmd'] == 'speak')
            .map((c) => c['text'])
            .toList();
        expect(speaks, [
          'First sentence is here.',
          'The rest of the answer is on screen.',
          '',
        ]);
        c2.dispose();
      },
    );

    test('R1-1: a press released while the service starts never opens the microphone', () async {
      final slow = Completer<VoiceTransport>();
      final t2 = FakeVoiceTransport();
      final svc2 = LiveVoiceService(launch: () => slow.future);
      final c2 = VoiceInteractionController(
        service: svc2,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
      );
      final press = c2.pressTalk();
      expect(c2.stage, VoiceStage.opening);
      c2.releaseTalk(); // key up during start-up
      expect(c2.stage, VoiceStage.idle);
      slow.complete(t2);
      await press;
      await pump();
      expect(t2.cmds.where((c) => c == 'listen_start'), isEmpty);
      expect(c2.stage, VoiceStage.idle);
      c2.dispose();
    });

    test('R1-2: the service dying mid-capture resets the interaction; the next press restarts it', () async {
      var launches = 0;
      var current = FakeVoiceTransport();
      final svc2 = LiveVoiceService(
        launch: () async {
          launches++;
          return current;
        },
      );
      final c2 = VoiceInteractionController(
        service: svc2,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
      );
      await c2.pressTalk();
      expect(c2.stage, VoiceStage.listening);
      current.die();
      await pump();
      expect(c2.stage, VoiceStage.idle);
      expect(c2.noticeCode, 'VOICE_SERVICE_STOPPED');
      current = FakeVoiceTransport();
      await c2.pressTalk();
      expect(launches, 2);
      expect(current.cmds, ['hello', 'listen_start']);
      expect(c2.stage, VoiceStage.listening);
      c2.dispose();
    });

    test(
      'R1-6: the length bound ends the capture with a notice and transcribes',
      () async {
        await ctl.pressTalk();
        t.push({
          'ev': 'listen.closed',
          'id': captureId(),
          'reason': 'max_length',
        });
        await pump();
        expect(ctl.noticeCode, 'MAX_LENGTH');
        expect(ctl.stage, VoiceStage.transcribing);
        await finalText('A very long dictation.');
        expect(rt.commands.where((c) => c['command'] == 'oi_turn').length, 1);
      },
    );

    test(
      'R1-7: latency is measured to the first reply audio, not to queueing',
      () async {
        await ctl.pressTalk();
        ctl.releaseTalk();
        await finalText('Hello there?');
        rt.emit('t1', 'answer.delta', {'text': 'Hi. '});
        rt.emit('t1', 'turn.finished', {'status': 'COMPLETE'});
        await pump();
        expect(
          ctl.timings.where(
            (m) => m.containsKey('final_to_first_reply_audio_ms'),
          ),
          isEmpty,
        );
        final utt = '${t.sent.firstWhere((c) => c['cmd'] == 'speak')['id']}';
        t.push({'ev': 'speak.started', 'id': utt, 'text': 'Hi.'});
        await pump();
        expect(
          ctl.timings
              .where((m) => m.containsKey('final_to_first_reply_audio_ms'))
              .length,
          1,
        );
      },
    );

    test('R1-5: a fallback microphone is a soft notice', () async {
      t.push({
        'ev': 'listen.warning',
        'id': 'x',
        'code': 'MIC_FALLBACK',
        'message': 'using Microphone (Test)',
      });
      await pump();
      expect(ctl.noticeCode, 'MIC_FALLBACK');
      expect(ctl.signal.state, isNot(CompanionState.error));
    });

    test(
      'microphone denied: a press shows the reason and opens nothing',
      () async {
        t.push({
          'ev': 'listen.error',
          'id': 'x',
          'code': 'MIC_DENIED',
          'message': 'Windows blocks microphone access for desktop apps',
        });
        await pump();
        expect(ctl.notice, contains('Privacy & security > Microphone'));
        expect(ctl.signal.state, CompanionState.error);
      },
    );
  });

  group('VoiceTalkButton', () {
    testWidgets(
      'two mounted buttons: one Ctrl+Space press opens one capture; Esc cancels it',
      (tester) async {
        final ctl = VoiceInteractionController(
          service: svc,
          preferences: CompanionPreferences(),
          presentation: UiPresentationController(),
        );
        await tester.pumpWidget(
          MaterialApp(
            theme: buildUriTheme(UriColors.graphite),
            home: Scaffold(
              body: Row(
                children: [
                  VoiceTalkButton(controller: ctl),
                  VoiceTalkButton(controller: ctl),
                ],
              ),
            ),
          ),
        );
        await tester.runAsync(() async {
          await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
          await tester.sendKeyDownEvent(LogicalKeyboardKey.space);
          await Future<void>.delayed(const Duration(milliseconds: 20));
        });
        expect(t.cmds.where((c) => c == 'listen_start').length, 1);
        expect(ctl.stage, VoiceStage.listening);
        await tester.sendKeyUpEvent(LogicalKeyboardKey.space);
        await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
        expect(t.cmds.where((c) => c == 'listen_stop').length, 1);
        ctl.cancel();
        await tester.pumpWidget(const SizedBox());
        ctl.dispose();
      },
    );
  });

  test(
    'voice preferences keep microphone, mode, reply speech and vocabulary',
    () {
      const p = VoicePreferences(
        microphone: 'USB Mic',
        speakReplies: false,
        inputMode: VoiceInputMode.drafting,
        vocabulary: 'Gangtok',
      );
      expect(VoicePreferences.fromJson(p.toJson()), p);
      expect(
        VoicePreferences.fromJson({'inputMode': 'bogus'}).inputMode,
        VoiceInputMode.conversation,
      );
      expect(VoicePreferences.fromJson({}).speakReplies, isTrue);
    },
  );

  group('speakableText and completeSentences', () {
    test('markdown marks, code and tables are not read aloud', () {
      final s = speakableText(
        '## Plan\n\n- **First** step\n- see [docs](http://x.y)\n\n```dart\nvoid main() {}\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |\n',
      );
      expect(s, isNot(contains('**')));
      expect(s, isNot(contains('void main')));
      expect(s, isNot(contains('|')));
      expect(s, contains('First step.'));
      expect(s, contains('see docs.'));
      expect(s, contains('The code is shown on screen.'));
    });

    test('only finished sentences are returned until the reply ends', () {
      const text = 'One. Two is here. Three without end';
      final a = completeSentences(text, 0, finished: false);
      expect(a.map((e) => e.$2), ['One.', 'Two is here.']);
      final b = completeSentences(text, a.last.$1, finished: true);
      expect(b.map((e) => e.$2), ['Three without end']);
    });
  });
}
