import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
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

/// A worker whose oi_turn reply waits until [release] completes.
class SlowRuntime extends FakeRuntime {
  final release = Completer<void>();

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    if (command['command'] == 'oi_turn') await release.future;
    return super.call(command);
  }
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

    test(
      'a loading model is reported as loading, then ready or failed',
      () async {
        await svc.ensureStarted();
        t.push({
          ...ready(),
          'model': {'state': 'loading'},
          'model_ok': false,
        });
        await pump();
        expect(svc.status.value.ready, isTrue);
        expect(svc.status.value.modelLoading, isTrue);
        t.push({'ev': 'model', 'state': 'ready', 'load_ms': 21000});
        await pump();
        expect(svc.status.value.modelLoading, isFalse);
        expect(svc.status.value.modelLoadMs, 21000);
        t.push({
          'ev': 'model',
          'state': 'failed',
          'code': 'MODEL_INTEGRITY',
          'message': 'hash mismatch',
        });
        await pump();
        expect(svc.status.value.state, VoiceServiceState.degraded);
        expect(svc.status.value.problemCode, 'MODEL_INTEGRITY');
      },
    );

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

    test('INT-3: real speech keeps its real provenance whatever the composer toggles say', () async {
      oi.setTranscriptMode(true); // the composer's SIMULATED-transcript toggle
      oi.setDictationMode(true); // and its typed Dictation toggle
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('What is the capital of Sikkim?');
      final turn = rt.commands.lastWhere((c) => c['command'] == 'oi_turn');
      final input = turn['input'] as Map;
      expect(input['source'], 'transcript');
      expect(input['transcript'], {
        'raw': 'What is the capital of Sikkim?',
        'engine': 'faster-whisper-base.en-int8',
        'simulated': false,
      });
      expect(input.containsKey('mode'), isFalse); // conversation mode: an ordinary turn, not dictation
      expect(turn['text'], 'What is the capital of Sikkim?');
    });

    test('INT-3: voice drafting sends the real transcript to the draft desk as dictation', () async {
      ctl.dispose();
      prefs.setVoice(prefs.voice.copyWith(inputMode: VoiceInputMode.drafting));
      ctl = VoiceInteractionController(
        service: svc,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
        keepInComposer: kept.add,
        noticeHold: const Duration(milliseconds: 50),
        dictation: (raw, {required engine, uncertain = const <String>[]}) => oi.sendTranscript(raw,
            engine: engine, simulated: false, uncertain: uncertain, dictation: true),
      );
      expect(ctl.dictationAvailable, isTrue);
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('Send the form to the office by Friday.');
      final turn = rt.commands.lastWhere((c) => c['command'] == 'oi_turn');
      final input = turn['input'] as Map;
      expect(input['mode'], 'dictation');
      expect((input['transcript'] as Map)['engine'], 'faster-whisper-base.en-int8');
      expect((input['transcript'] as Map)['simulated'], isFalse);
      expect(kept, isEmpty); // not left in the composer: it went to the desk
    });

    test('INT-3: a dictation while URI is busy stays in the composer, never dropped (Codex TIWS r13)', () async {
      ctl.dispose();
      prefs.setVoice(prefs.voice.copyWith(inputMode: VoiceInputMode.drafting));
      ctl = VoiceInteractionController(
        service: svc,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
        keepInComposer: kept.add,
        noticeHold: const Duration(milliseconds: 50),
        dictation: (raw, {required engine, uncertain = const <String>[]}) => oi.sendTranscript(raw,
            engine: engine, simulated: false, uncertain: uncertain, dictation: true),
      );
      await oi.send('a typed question'); // URI is now busy with this turn
      expect(oi.busy, isTrue);
      final turns = rt.commands.where((c) => c['command'] == 'oi_turn').length;
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('Send the form to the office by Friday.');
      expect(rt.commands.where((c) => c['command'] == 'oi_turn').length, turns); // nothing sent
      expect(kept, ['Send the form to the office by Friday.']); // and nothing lost
    });

    test('INT-3: a failing dictation sink keeps the words in the composer (Codex TIWS r14)', () async {
      ctl.dispose();
      prefs.setVoice(prefs.voice.copyWith(inputMode: VoiceInputMode.drafting));
      ctl = VoiceInteractionController(
        service: svc,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
        keepInComposer: kept.add,
        noticeHold: const Duration(milliseconds: 50),
        dictation: (raw, {required engine, uncertain = const <String>[]}) async => throw StateError('sink down'),
      );
      await ctl.pressTalk();
      ctl.releaseTalk();
      await finalText('Send the form to the office by Friday.');
      expect(kept, ['Send the form to the office by Friday.']);
      expect(ctl.stage, VoiceStage.idle);
    });

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

    // Office companion (owner request 2026-10-12): in Office focus with a workbook open, a spoken request goes to
    // the workbook like typed text in the Office pane. It only asks URI to suggest changes.
    test('in Office focus a spoken request goes to the open workbook, not the conversation', () async {
      final office = _FakeOffice();
      final c2 = VoiceInteractionController(
        service: svc,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
        keepInComposer: kept.add,
        officeTarget: () => office,
      );
      await c2.pressTalk();
      c2.releaseTalk();
      await finalText('Put checked by URI in C2');
      expect(office.asks, ['Put checked by URI in C2']);
      expect(rt.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
      expect(c2.stage, VoiceStage.idle);
      c2.dispose();
    });

    test('a busy workbook keeps the spoken request in the composer', () async {
      final office = _FakeOffice()..busy = true;
      final c2 = VoiceInteractionController(
        service: svc,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
        keepInComposer: kept.add,
        officeTarget: () => office,
      );
      await c2.pressTalk();
      c2.releaseTalk();
      await finalText('Sum column B');
      expect(office.asks, isEmpty);
      expect(kept, ['Sum column B']);
      expect(c2.noticeCode, 'BUSY');
      expect(rt.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
      c2.dispose();
    });

    test('in Office focus with no workbook open, speech is kept and nothing is sent (R1-01, M1-c2)', () async {
      final office = _FakeOffice()..acceptsRequests = false;
      final c2 = VoiceInteractionController(
        service: svc,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
        keepInComposer: kept.add,
        officeTarget: () => office,
      );
      await c2.pressTalk();
      c2.releaseTalk();
      await finalText('Sum column B');
      expect(office.asks, isEmpty);
      expect(kept, ['Sum column B']);
      expect(c2.noticeCode, 'NO_WORKBOOK');
      expect(rt.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
      c2.dispose();
    });

    test('with no Office target the spoken request is an ordinary turn', () async {
      final c2 = VoiceInteractionController(
        service: svc,
        preferences: prefs,
        presentation: presentation,
        oi: oi,
        officeTarget: () => null,
      );
      await c2.pressTalk();
      c2.releaseTalk();
      await finalText('What is the capital of Sikkim?');
      expect(rt.commands.where((c) => c['command'] == 'oi_turn'), hasLength(1));
      c2.dispose();
    });

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

    test('R2-1: the service dying while the turn is sent leaves nothing to speak', () async {
      final current = FakeVoiceTransport();
      final svc2 = LiveVoiceService(launch: () async => current);
      final slowRt = SlowRuntime();
      final oi2 = OiConversation(slowRt, sessionId: 's2');
      final c2 = VoiceInteractionController(
        service: svc2,
        preferences: prefs,
        presentation: presentation,
        oi: oi2,
      );
      await c2.pressTalk();
      c2.releaseTalk();
      final id =
          '${current.sent.lastWhere((c) => c['cmd'] == 'listen_start')['id']}';
      current.push({
        'ev': 'listen.final',
        'id': id,
        'text': 'Hello?',
        'reason': 'completed',
        'engine': 'e',
        'uncertain': <String>[],
      });
      await pump();
      expect(c2.stage, VoiceStage.waiting);
      current.die();
      await pump();
      slowRt.release.complete();
      await pump();
      await pump();
      slowRt.emit('t1', 'answer.delta', {'text': 'Hi there. '});
      slowRt.emit('t1', 'turn.finished', {'status': 'COMPLETE'});
      await pump();
      expect(current.cmds.where((c) => c == 'speak'), isEmpty);
      expect(c2.stage, VoiceStage.idle);
      c2.dispose();
      oi2.dispose();
    });

    test('R2-4: the spoken cap also holds for a long first sentence', () async {
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
        'text': 'This first sentence is very much longer than the forty character cap allows. Next. ',
      });
      rt.emit('t1', 'turn.finished', {'status': 'COMPLETE'});
      await pump();
      final speaks = t.sent
          .where((c) => c['cmd'] == 'speak')
          .map((c) => '${c['text']}')
          .toList();
      expect(speaks.first.length, lessThanOrEqualTo(40));
      expect(speaks.first, endsWith('…'));
      expect(speaks[1], 'The rest of the answer is on screen.');
      expect(speaks.join(' '), isNot(contains('Next.')));
      c2.dispose();
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

  group('Stop while URI speaks (live run 6 finding)', () {
    Future<VoiceInteractionController> speakingController(
      WidgetTester tester,
    ) async {
      // Built inside runAsync: stream subscriptions belong to the zone that
      // creates them, and the fake-async test zone would never deliver them.
      late FakeRuntime rt;
      late VoiceInteractionController ctl;
      await tester.runAsync(() async {
        rt = FakeRuntime();
        final oi = OiConversation(rt, sessionId: 's');
        ctl = VoiceInteractionController(
          service: svc,
          preferences: CompanionPreferences(),
          presentation: UiPresentationController(),
          oi: oi,
        );
        await svc.ensureStarted();
        t.push(ready());
        await pump();
        await ctl.pressTalk();
        ctl.releaseTalk();
        final id =
            '${t.sent.lastWhere((c) => c['cmd'] == 'listen_start')['id']}';
        t.push({
          'ev': 'listen.final',
          'id': id,
          'text': 'Tell me a story.',
          'reason': 'completed',
          'engine': 'e',
          'uncertain': <String>[],
        });
        await pump();
        await pump();
        await Future<void>.delayed(const Duration(milliseconds: 50));
        rt.emit('t1', 'answer.delta', {
          'text': 'Once upon a time. There was a king. ',
        });
        await Future<void>.delayed(const Duration(milliseconds: 50));
      });
      expect(ctl.stage, VoiceStage.speaking);
      await tester.pumpWidget(
        MaterialApp(
          theme: buildUriTheme(UriColors.graphite),
          home: Scaffold(
            body: Center(child: VoiceTalkButton(controller: ctl)),
          ),
        ),
      );
      return ctl;
    }

    testWidgets('a tap on Stop silences URI and captures nothing', (
      tester,
    ) async {
      final ctl = await speakingController(tester);
      final stop = find.byKey(const ValueKey('voice-stop-speaking'));
      expect(stop, findsOneWidget);
      final before = t.sent.length;
      await tester.runAsync(() async {
        final g = await tester.startGesture(tester.getCenter(stop));
        await Future<void>.delayed(const Duration(milliseconds: 30));
        await g.up();
        await pump();
      });
      final cmds = [for (final c in t.sent.skip(before)) '${c['cmd']}'];
      // The press opens the microphone (the process stops playback first),
      // the short release discards it: nothing is transcribed.
      expect(cmds, ['listen_start', 'listen_cancel']);
      expect(ctl.stage, VoiceStage.idle);
      ctl.dispose();
    });

    testWidgets('holding Stop interrupts URI and becomes the user turn', (
      tester,
    ) async {
      final ctl = await speakingController(tester);
      final stop = find.byKey(const ValueKey('voice-stop-speaking'));
      final before = t.sent.length;
      late TestGesture g;
      await tester.runAsync(() async {
        g = await tester.startGesture(tester.getCenter(stop));
        await pump();
      });
      await tester.pump(); // the disc becomes the talk button under the finger
      expect(ctl.stage, VoiceStage.listening);
      await tester.runAsync(() async {
        await Future<void>.delayed(const Duration(milliseconds: 400));
        await g.up();
        await pump();
      });
      final cmds = [for (final c in t.sent.skip(before)) '${c['cmd']}'];
      expect(cmds, ['listen_start', 'listen_stop']);
      expect(ctl.stage, VoiceStage.transcribing);
      ctl.cancel();
      ctl.dispose();
    });
  });

  test('R3-3: clipped text never exceeds the cap, with or without spaces', () {
    final long = 'x' * 700;
    expect(clipToWords(long, 600).length, 600);
    expect(clipToWords(long, 600), endsWith('…'));
    final words = List.filled(200, 'word').join(' ');
    expect(clipToWords(words, 600).length, lessThanOrEqualTo(600));
    expect(clipToWords('short', 600), 'short');
  });

  test('bold labels do not gain a stray full stop', () {
    expect(speakableText('1. **Implement DMS:**'), 'Implement DMS:');
  });

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

class _FakeOffice extends ChangeNotifier implements OfficeRequestTarget {
  final asks = <String>[];
  @override
  bool acceptsRequests = true;
  @override
  bool busy = false;
  @override
  Future<void> instruct(String text, {String? activeSheet}) async => asks.add(text);
}
