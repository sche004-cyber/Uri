import 'dart:convert';
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/voice/companion_presence.dart';
import 'package:uri_ui/living/voice/voice_level.dart';
import 'package:uri_ui/living/voice/voice_script.dart';
import 'package:uri_ui/living/voice/voice_session.dart';
import 'package:uri_ui/living/voice/voice_transcript.dart';
import 'package:uri_ui/living/voice/voice_waveform.dart';
import 'package:uri_ui/theme/uri_theme.dart';

const _fixtures = 'test/fixtures/voice';

PcmClip _clip(String name) =>
    decodeWavPcm16(File('$_fixtures/$name.wav').readAsBytesSync());

Map<String, dynamic> _timing(String name) =>
    jsonDecode(File('$_fixtures/$name.timing.json').readAsStringSync())
        as Map<String, dynamic>;

VoiceSession _run(List<VoiceSignal> events) =>
    events.fold(const VoiceSession(), reduceVoice);

void main() {
  group('level mapping (one mapping, no speaker)', () {
    test('silence maps to zero and full-scale speech to the top', () {
      expect(VoiceLevelMapper.target(0), 0);
      expect(VoiceLevelMapper.target(1e-4), 0); // -80 dBFS, below the floor
      expect(VoiceLevelMapper.target(1.0), 1.0);
    });

    test('target is monotonic in loudness', () {
      var last = -1.0;
      for (var db = -70.0; db <= 0; db += 1) {
        final v = VoiceLevelMapper.target(math.pow(10, db / 20).toDouble());
        expect(v, greaterThanOrEqualTo(last));
        last = v;
      }
    });

    test('two mappers fed the same blocks agree exactly', () {
      final a = VoiceLevelMapper();
      final b = VoiceLevelMapper();
      final env = levelEnvelope(_clip('uri_reply').samples, 16000);
      for (final f in env) {
        a.addBlock(f.rms, 20);
        b.addBlock(f.rms, 20);
        expect(a.level, b.level);
        expect(a.flux, b.flux);
      }
    });

    test('a quieter stream with the same speech converges to the same '
        'display level (equal effort is drawn equally)', () {
      final env = levelEnvelope(_clip('user_request').samples, 16000);
      final loud = VoiceLevelMapper();
      final quiet = VoiceLevelMapper();
      final quietGain = math.pow(10, -9 / 20).toDouble(); // 9 dB quieter mic
      // Let both references settle on a first pass, then compare a second.
      for (final f in env) {
        loud.addBlock(f.rms, 20);
        quiet.addBlock(f.rms * quietGain, 20);
      }
      var maxDiff = 0.0;
      for (final f in env) {
        loud.addBlock(f.rms, 20);
        quiet.addBlock(f.rms * quietGain, 20);
        maxDiff = math.max(maxDiff, (loud.level - quiet.level).abs());
      }
      expect(maxDiff, lessThan(0.12));
    });

    test('the reference never moves more than maxGainDb', () {
      final m = VoiceLevelMapper();
      for (var i = 0; i < 2000; i++) {
        m.addBlock(0.9, 20);
      }
      expect(
        m.referenceDb,
        lessThanOrEqualTo(
          VoiceLevelMapper.nominalDb + VoiceLevelMapper.maxGainDb,
        ),
      );
      for (var i = 0; i < 4000; i++) {
        m.addBlock(0.002, 20);
      }
      expect(
        m.referenceDb,
        greaterThanOrEqualTo(
          VoiceLevelMapper.nominalDb - VoiceLevelMapper.maxGainDb,
        ),
      );
    });

    test('reset clears the level but keeps the stream reference', () {
      final m = VoiceLevelMapper();
      for (var i = 0; i < 300; i++) {
        m.addBlock(0.02, 20);
      }
      final ref = m.referenceDb;
      m.reset();
      expect(m.level, 0);
      expect(m.flux, 0);
      expect(m.referenceDb, ref);
    });
  });

  group('PCM fixtures', () {
    test('decodes the fixtures as 16 kHz mono with real speech energy', () {
      for (final n in ['user_request', 'uri_reply']) {
        final c = _clip(n);
        expect(c.sampleRate, 16000);
        expect(c.durationMs, greaterThan(4000));
        final env = levelEnvelope(c.samples, c.sampleRate);
        final speech = env.where((f) => VoiceLevelMapper.dbfs(f.rms) > -45);
        expect(speech.length, greaterThan(env.length ~/ 3), reason: n);
      }
    });

    test('rejects non-WAVE input', () {
      expect(
        () => decodeWavPcm16(Uint8List.fromList(utf8.encode('not audio'))),
        throwsFormatException,
      );
    });

    test('the timing files carry one entry per spoken word', () {
      for (final n in ['user_request', 'uri_reply']) {
        final t = _timing(n);
        final words = VoiceScript.wordsFromJson(t);
        final text = t['text'] as String;
        expect(words, isNotEmpty);
        for (var i = 1; i < words.length; i++) {
          expect(words[i].ms, greaterThanOrEqualTo(words[i - 1].ms));
          expect(words[i].char, greaterThan(words[i - 1].char));
        }
        expect(
          words.last.char + words.last.length,
          lessThanOrEqualTo(text.length),
        );
      }
    });
  });

  group('voice state machine', () {
    test('a user turn: listening, speech, partials, final, end', () {
      var s = _run([const ListeningStarted('a')]);
      expect(s.phase, VoicePhase.listening);
      expect(s.showsWaveform, isFalse);
      s = reduceVoice(s, const UserSpeechStarted('a'));
      expect(s.phase, VoicePhase.userSpeaking);
      expect(s.speaker, VoiceSpeaker.user);
      s = reduceVoice(s, const UserTranscript('a', 'draft a'));
      s = reduceVoice(s, const UserTranscript('a', 'draft a reply'));
      expect(s.transcript, 'draft a reply');
      s = reduceVoice(
        s,
        const UserTranscript('a', 'Draft a reply.', isFinal: true),
      );
      expect(s.transcriptFinal, isTrue);
      s = reduceVoice(s, const ListeningEnded('a', VoiceEndReason.completed));
      expect(s.phase, VoicePhase.off);
      expect(s.lastEnd, VoiceEndReason.completed);
    });

    test('a transcript on a silent listener proves speech', () {
      final s = _run([
        const ListeningStarted('a'),
        const UserTranscript('a', 'hello'),
      ]);
      expect(s.phase, VoicePhase.userSpeaking);
    });

    test('events for another session or utterance change nothing', () {
      final open = _run([const ListeningStarted('a')]);
      expect(reduceVoice(open, const UserSpeechStarted('b')), same(open));
      expect(reduceVoice(open, const UserTranscript('b', 'x')), same(open));
      expect(
        reduceVoice(open, const ListeningEnded('b', VoiceEndReason.completed)),
        same(open),
      );
      final talking = _run([const UriSpeechStarted('r1', 'Hello.')]);
      expect(
        reduceVoice(talking, const UriSpeechProgress('r2', 900)),
        same(talking),
      );
      expect(
        reduceVoice(
          talking,
          const UriSpeechEnded('r2', VoiceEndReason.completed),
        ),
        same(talking),
      );
    });

    test('barge-in: the user wins and late events for the cut-off reply '
        'are dropped', () {
      var s = _run([
        const UriSpeechStarted('r1', 'A long reply.'),
        const UriSpeechProgress('r1', 400),
        const UserSpeechStarted('u1'),
      ]);
      expect(s.phase, VoicePhase.userSpeaking);
      expect(s.interruptedUtteranceId, 'r1');
      expect(s.transcript, '');
      final before = s;
      s = reduceVoice(s, const UriSpeechProgress('r1', 800));
      s = reduceVoice(
        s,
        const UriSpeechEnded('r1', VoiceEndReason.interrupted),
      );
      s = reduceVoice(s, const UriSpeechStarted('r1', 'A long reply.'));
      expect(s, same(before));
    });

    test(
      'URI audio that starts while the user speaks is not drawn over them',
      () {
        final s = _run([
          const ListeningStarted('u1'),
          const UserSpeechStarted('u1'),
          const UriSpeechStarted('r1', 'Interrupting.'),
        ]);
        expect(s.phase, VoicePhase.userSpeaking);
      },
    );

    test('opening a listener while URI speaks cuts the reply off', () {
      final s = _run([
        const UriSpeechStarted('r1', 'Reply.'),
        const ListeningStarted('u1'),
        const UriSpeechEnded('r1', VoiceEndReason.completed),
      ]);
      expect(s.phase, VoicePhase.listening);
      expect(s.interruptedUtteranceId, 'r1');
    });

    test('playback progress never runs backwards', () {
      var s = _run([
        const UriSpeechStarted('r1', 'Reply.'),
        const UriSpeechProgress('r1', 900),
      ]);
      s = reduceVoice(s, const UriSpeechProgress('r1', 300));
      expect(s.positionMs, 900);
    });

    test('a failure or reset ends every phase with a notice', () {
      final phases = <List<VoiceSignal>>[
        [const ListeningStarted('a')],
        [const ListeningStarted('a'), const UserSpeechStarted('a')],
        [const UriSpeechStarted('r', 'x')],
        [],
      ];
      for (final p in phases) {
        final failed = reduceVoice(
          _run(p),
          const VoiceFailure('Microphone unavailable'),
        );
        expect(failed.phase, VoicePhase.off);
        expect(failed.notice, 'Microphone unavailable');
        final reset = reduceVoice(_run(p), const VoiceReset('Task cancelled'));
        expect(reset.phase, VoicePhase.off);
        expect(reset.notice, 'Task cancelled');
      }
    });

    test('spoken position follows the engine word timing', () {
      final t = _timing('uri_reply');
      final words = VoiceScript.wordsFromJson(t);
      final text = t['text'] as String;
      var s = _run([UriSpeechStarted('r', text, words: words)]);
      expect(s.spokenChars, 0);
      s = reduceVoice(s, UriSpeechProgress('r', words[3].ms));
      expect(s.spokenChars, words[3].char + words[3].length);
      final none = _run([UriSpeechStarted('r', text)]);
      expect(none.spokenChars, isNull);
    });

    test('random event storms never leave an inconsistent session', () {
      final rnd = math.Random(20261009);
      const ids = ['a', 'b'];
      const utt = ['r1', 'r2'];
      VoiceSignal pick() {
        final id = ids[rnd.nextInt(2)];
        final u = utt[rnd.nextInt(2)];
        return switch (rnd.nextInt(10)) {
          0 => ListeningStarted(id),
          1 => UserSpeechStarted(id),
          2 => UserTranscript(
            id,
            'w${rnd.nextInt(9)}',
            isFinal: rnd.nextBool(),
          ),
          3 => ListeningEnded(id, VoiceEndReason.values[rnd.nextInt(5)]),
          4 => UriSpeechStarted(u, 'Reply $u.'),
          5 => UriSpeechProgress(u, rnd.nextInt(5000)),
          6 => UriSpeechEnded(u, VoiceEndReason.values[rnd.nextInt(5)]),
          7 => AudioLevel(
            VoiceSpeaker.values[rnd.nextInt(2)],
            rnd.nextDouble(),
          ),
          8 => const VoiceFailure('failure'),
          _ => const VoiceReset(),
        };
      }

      for (var run = 0; run < 300; run++) {
        var s = const VoiceSession();
        for (var i = 0; i < 60; i++) {
          s = reduceVoice(s, pick());
          if (s.phase == VoicePhase.off) expect(s.speaker, isNull);
          if (s.phase == VoicePhase.uriSpeaking) {
            expect(s.utteranceId, isNotNull);
            expect(s.utteranceId, isNot(s.interruptedUtteranceId));
          }
          if (s.phase == VoicePhase.listening ||
              s.phase == VoicePhase.userSpeaking) {
            expect(s.sessionId, isNotNull);
          }
        }
        expect(reduceVoice(s, const VoiceReset()).phase, VoicePhase.off);
      }
    });
  });

  group('controller', () {
    test('audio from the stream that is not speaking is ignored', () {
      final c = VoiceSessionController();
      addTearDown(c.dispose);
      c.add(const UriSpeechStarted('r', 'Reply.'));
      c.add(const AudioLevel(VoiceSpeaker.user, 0.5));
      expect(c.level.value, 0);
      c.add(const AudioLevel(VoiceSpeaker.uri, 0.1));
      expect(c.level.value, greaterThan(0));
    });

    test('nothing drives the waveform when voice is off', () {
      final c = VoiceSessionController();
      addTearDown(c.dispose);
      c.add(const AudioLevel(VoiceSpeaker.user, 0.5));
      c.add(const AudioLevel(VoiceSpeaker.uri, 0.5));
      expect(c.level.value, 0);
    });

    test('the same audio as the user and as URI gives identical levels', () {
      final clip = _clip('uri_reply');
      final env = levelEnvelope(clip.samples, clip.sampleRate);
      final asUser = VoiceSessionController();
      final asUri = VoiceSessionController();
      addTearDown(asUser.dispose);
      addTearDown(asUri.dispose);
      asUser.add(const ListeningStarted('u'));
      asUser.add(const UserSpeechStarted('u'));
      asUri.add(const UriSpeechStarted('r', 'x'));
      for (final f in env) {
        asUser.add(AudioLevel(VoiceSpeaker.user, f.rms));
        asUri.add(AudioLevel(VoiceSpeaker.uri, f.rms));
        expect(asUser.level.value, asUri.level.value);
        expect(asUser.flux.value, asUri.flux.value);
      }
    });

    test('speech onset on an open listener does not reset the level', () {
      final c = VoiceSessionController();
      addTearDown(c.dispose);
      c.add(const ListeningStarted('u'));
      for (var i = 0; i < 20; i++) {
        c.add(const AudioLevel(VoiceSpeaker.user, 0.05));
      }
      final before = c.level.value;
      expect(before, greaterThan(0));
      c.add(const UserSpeechStarted('u'));
      expect(c.level.value, before);
    });

    testWidgets('the watchdog ends a speaking phase that stops reporting', (
      tester,
    ) async {
      final c = VoiceSessionController(
        speechStaleAfter: const Duration(seconds: 2),
      );
      c.add(const UriSpeechStarted('r', 'Reply.'));
      c.add(const AudioLevel(VoiceSpeaker.uri, 0.1));
      await tester.pump(const Duration(milliseconds: 1500));
      expect(c.session.phase, VoicePhase.uriSpeaking);
      c.add(const AudioLevel(VoiceSpeaker.uri, 0.1)); // re-arms
      await tester.pump(const Duration(milliseconds: 1500));
      expect(c.session.phase, VoicePhase.uriSpeaking);
      await tester.pump(const Duration(milliseconds: 600));
      expect(c.session.phase, VoicePhase.off);
      expect(c.session.notice, 'Voice signal lost');
      expect(c.level.value, 0);
      c.dispose();
    });

    testWidgets('the watchdog closes a listener that hears nothing', (
      tester,
    ) async {
      final c = VoiceSessionController(
        listenStaleAfter: const Duration(seconds: 3),
      );
      c.add(const ListeningStarted('u'));
      await tester.pump(const Duration(seconds: 4));
      expect(c.session.phase, VoicePhase.off);
      expect(c.session.notice, contains('no speech'));
      c.dispose();
    });

    test('a full scripted exchange from the real fixtures ends off', () {
      final user = _timing('user_request');
      final reply = _timing('uri_reply');
      final script = VoiceScript([
        ...VoiceScript.userTurn(
          clip: _clip('user_request'),
          words: VoiceScript.wordsFromJson(user),
          text: user['text'] as String,
          sessionId: 'u1',
        ),
        ...VoiceScript.uriTurn(
          clip: _clip('uri_reply'),
          words: VoiceScript.wordsFromJson(reply),
          text: reply['text'] as String,
          utteranceId: 'r1',
          startMs: 8000,
        ),
      ]);
      final c = VoiceSessionController(simulated: true);
      addTearDown(c.dispose);
      final seen = <VoicePhase>{};
      for (final e in script.until(script.durationMs)) {
        c.add(e);
        seen.add(c.session.phase);
      }
      expect(seen, containsAll(VoicePhase.values));
      expect(c.session.phase, VoicePhase.off);
      expect(c.session.lastEnd, VoiceEndReason.completed);
    });
  });

  group('presence resolution', () {
    const idle = CompanionSignal.idle();
    const approval = CompanionSignal(
      state: CompanionState.awaitingApproval,
      detail: 'Send it?',
    );
    const error = CompanionSignal(state: CompanionState.error, detail: 'x');

    test('only real speech shows the waveform', () {
      expect(
        resolvePresence(idle, _run([const UriSpeechStarted('r', 'x')])).mode,
        PresenceMode.voice,
      );
      expect(
        resolvePresence(
          idle,
          _run([const ListeningStarted('a'), const UserSpeechStarted('a')]),
        ).mode,
        PresenceMode.voice,
      );
      // A source that merely claims speaking, with no voice session, keeps
      // the companion.
      expect(
        resolvePresence(
          const CompanionSignal(state: CompanionState.speaking),
          const VoiceSession(),
        ).mode,
        PresenceMode.companion,
      );
    });

    test('listening shows the companion, softened', () {
      final v = resolvePresence(idle, _run([const ListeningStarted('a')]));
      expect(v.mode, PresenceMode.companion);
      expect(v.orbState, CompanionState.listening);
    });

    test('an approval or error stays named while the waveform is up', () {
      final speaking = _run([const UriSpeechStarted('r', 'x')]);
      final a = resolvePresence(approval, speaking);
      expect(a.mode, PresenceMode.voice);
      expect(a.status, CompanionState.awaitingApproval.label);
      expect(a.statusState, CompanionState.awaitingApproval);
      expect(a.detail, 'Send it?');
      final e = resolvePresence(error, speaking);
      expect(e.statusState, CompanionState.error);
    });

    test('blocking states win over an open listener', () {
      final open = _run([const ListeningStarted('a')]);
      expect(
        resolvePresence(approval, open).orbState,
        CompanionState.awaitingApproval,
      );
      expect(resolvePresence(approval, open).attention, isTrue);
      expect(resolvePresence(error, open).orbState, CompanionState.error);
    });

    test('a voice failure is shown as a notice, not as a URI error', () {
      final v = resolvePresence(
        idle,
        reduceVoice(
          _run([const ListeningStarted('a')]),
          const VoiceFailure('Microphone unavailable'),
        ),
      );
      expect(v.orbState, CompanionState.idle);
      expect(v.notice, 'Microphone unavailable');
    });

    test('the layout only moves the companion; it never leaves the box', () {
      for (final size in const [
        Size(280, 380),
        Size(480, 560),
        Size(720, 460),
      ]) {
        for (var v = 0.0; v <= 1.0001; v += 0.1) {
          final l = PresenceLayout.of(size, v);
          final box = Offset.zero & size;
          for (final r in [l.orb, l.wave, l.transcript, l.status]) {
            expect(
              box.inflate(0.5).contains(r.topLeft),
              isTrue,
              reason: '$size $v',
            );
            expect(
              box.inflate(0.5).contains(r.bottomRight),
              isTrue,
              reason: '$size $v',
            );
          }
          expect(l.orb.width, closeTo(l.orb.height, 1e-6));
        }
        final voice = PresenceLayout.of(size, 1);
        expect(voice.orb.bottom, lessThanOrEqualTo(voice.wave.top));
        expect(voice.wave.bottom, lessThanOrEqualTo(voice.transcript.top));
      }
      expect(PresenceLayout.voiceOpacity(0), 0);
      // The companion body spans about half its box, whatever the identity,
      // and the enlargement stays bounded.
      for (final id in CompanionIdentity.values) {
        final k = presenceScale(id);
        expect(k, inInclusiveRange(1.0, 1.4));
        expect(
          id.bodyRadius * k,
          inInclusiveRange(0.40, 0.52),
          reason: id.name,
        );
      }
      expect(PresenceLayout.voiceOpacity(1), 1);
    });
  });

  group('transcript windowing', () {
    test('the newest user words stay visible', () {
      final long = List.generate(60, (i) => 'word$i').join(' ');
      final w = TranscriptWindow.tail(long, 300, 15, 2);
      expect(w.leadingEllipsis, isTrue);
      expect(w.heard.endsWith('word59'), isTrue);
      expect(w.heard.startsWith('word'), isTrue); // cut at a word boundary
      final short = TranscriptWindow.tail('hello there', 300, 15, 2);
      expect(short.heard, 'hello there');
      expect(short.leadingEllipsis, isFalse);
    });

    test(
      "URI's reply is shown a sentence at a time, split at the heard word",
      () {
        final t = _timing('uri_reply');
        final text = t['text'] as String;
        final words = VoiceScript.wordsFromJson(t);
        final sentences = TranscriptWindow.splitSentences(text);
        expect(sentences.length, 3);
        final first = TranscriptWindow.spoken(
          text,
          words[2].char + words[2].length,
        );
        expect(first.heard, 'I have drafted');
        expect(first.ahead, ' the reply to Mr Rai.');
        // After the first sentence ends but before the second starts, it stays.
        final pause = TranscriptWindow.spoken(text, sentences[0].$2 - 1);
        expect(pause.key, 'uri-0');
        final second = TranscriptWindow.spoken(text, sentences[1].$1 + 2);
        expect(second.key, 'uri-1');
        expect(TranscriptWindow.spoken(text, null).heard, text.trim());
      },
    );
  });

  group('waveform contract', () {
    test('the uniform vector has no speaker slot and fixed order', () {
      final u = VoiceWaveformPainter.uniformsFor(
        size: const Size(340, 100),
        seconds: 2,
        level: 0.4,
        flux: 0.1,
        presence: 1,
        motion: 1,
        colA: const Color(0xFFFF0000),
        colB: const Color(0xFF00FF00),
        colC: const Color(0xFF0000FF),
      );
      expect(u.length, 16);
      expect(u.sublist(0, 7), [340, 100, 2, 0.4, 0.1, 1, 1]);
      expect(u.sublist(7), [1, 0, 0, 0, 1, 0, 0, 0, 1]);
    });

    test('glide converges by elapsed time and reduced motion is slower', () {
      var a = 0.0;
      var b = 0.0;
      for (var i = 0; i < 6; i++) {
        a = voiceGlide(a, 1, 1 / 60);
        b = voiceGlide(b, 1, 1 / 60, reduced: true);
      }
      expect(a, greaterThan(0.7));
      expect(b, lessThan(0.25));
    });

    test('the shader asset is registered', () {
      final pubspec = File('pubspec.yaml').readAsStringSync();
      expect(pubspec, contains(kVoiceWaveformAsset));
    });
  });

  group('companion expression tables', () {
    test('match rnd/companions/state_tables.json exactly', () {
      final json = jsonDecode(
        File('../rnd/companions/state_tables.json').readAsStringSync(),
      ) as Map<String, dynamic>;
      final tables = json['tables'] as Map<String, dynamic>;
      for (final id in CompanionIdentity.values) {
        // Moonlit reads the lunar table; Ember (sprite clips, no shader)
        // shares Solar's so any caller still gets fire-like values.
        final fam = switch (id) {
          CompanionIdentity.moonlit => 'lunar',
          CompanionIdentity.ember => 'solar',
          _ => id.name,
        };
        final t = tables[fam] as Map<String, dynamic>;
        for (final st in CompanionState.values) {
          final row = (t[st.name] as List).cast<num>();
          final p = CompanionParams.of(id, st);
          expect(
            [p.energy, p.turbulence, p.flare, p.particles, p.focus, p.exposure],
            [for (final v in row) v.toDouble()],
            reason: '${id.name}/${st.name}',
          );
        }
      }
    });

    test('ordinary states keep the brief ordering', () {
      for (final id in CompanionIdentity.values) {
        CompanionParams p(CompanionState s) => CompanionParams.of(id, s);
        final idle = p(CompanionState.idle);
        final listening = p(CompanionState.listening);
        final thinking = p(CompanionState.thinking);
        final working = p(CompanionState.working);
        // Listening is softer than idle; thinking is the deepest shade.
        expect(listening.energy, lessThan(idle.energy), reason: id.name);
        expect(listening.exposure, lessThan(idle.exposure), reason: id.name);
        expect(
          thinking.exposure,
          lessThan(listening.exposure),
          reason: id.name,
        );
        expect(thinking.flare, lessThan(idle.flare), reason: id.name);
        expect(
          thinking.turbulence,
          greaterThan(idle.turbulence),
          reason: id.name,
        );
        // Working is steady: more energy, but calmer than thinking.
        expect(working.energy, greaterThan(idle.energy), reason: id.name);
        expect(
          working.turbulence,
          lessThan(thinking.turbulence),
          reason: id.name,
        );
        // No ordinary state darkens below the detail-preserving floor.
        for (final s in CompanionState.values) {
          if (s == CompanionState.unavailable) continue;
          expect(
            p(s).exposure,
            greaterThanOrEqualTo(0.84),
            reason: '${id.name} $s',
          );
        }
      }
    });

    test('the attention pulse is gentle and returns to the base', () {
      final base = CompanionParams.of(
        CompanionIdentity.solar,
        CompanionState.awaitingApproval,
      );
      expect(base.withAttention(0), base);
      final peak = base.withAttention(1);
      expect(peak.exposure - base.exposure, closeTo(0.11, 1e-9));
      expect(peak.turbulence, base.turbulence);
      expect(peak.focus, base.focus);
      expect(CompanionParams.attentionWave(0), closeTo(0, 1e-9));
      expect(CompanionParams.attentionWave(1.4), closeTo(1, 1e-9));
    });
  });

  group('composite priority with voice', () {
    test('voice never hides a real approval', () {
      final voice = VoiceSessionController();
      final mock = MockCompanionSource();
      final vs = VoiceCompanionSource(voice);
      final composite = CompositeCompanionSource([mock, vs]);
      addTearDown(() {
        composite.dispose();
        vs.dispose();
        voice.dispose();
      });
      voice.add(const UriSpeechStarted('r', 'x'));
      expect(composite.signal.state, CompanionState.speaking);
      mock.emit(CompanionState.awaitingApproval, detail: 'Approve?');
      expect(composite.signal.state, CompanionState.awaitingApproval);
    });
  });

  group('presence widget', () {
    Widget host(
      VoiceSessionController voice,
      CompanionSignal signal, {
      EffectsSettings? effects,
    }) {
      return MaterialApp(
        theme: buildUriTheme(UriColors.lunarSilver),
        home: EffectsSettingsScope(
          settings: effects ?? EffectsSettings(),
          child: Scaffold(
            body: SizedBox(
              width: 480,
              height: 560,
              child: CompanionPresence(
                identity: CompanionIdentity.lunar,
                signal: signal,
                voice: voice,
              ),
            ),
          ),
        ),
      );
    }

    testWidgets('rapid barge-in, cancellation and failure leave no stuck '
        'waveform and never remount the companion', (tester) async {
      final voice = VoiceSessionController(simulated: true);
      await tester.pumpWidget(host(voice, const CompanionSignal.idle()));
      await tester.pump();
      final orb = tester.element(find.byKey(const ValueKey('presence-orb')));

      final steps = <VoiceSignal>[
        const ListeningStarted('u1'),
        const UserSpeechStarted('u1'),
        const UriSpeechStarted('r1', 'Reply one.'),
        const ListeningEnded('u1', VoiceEndReason.completed),
        const UriSpeechStarted('r1', 'Reply one.'),
        const UserSpeechStarted('u2'), // barge-in
        const UriSpeechEnded('r1', VoiceEndReason.interrupted), // late
        const VoiceFailure('Microphone unavailable'),
        const UriSpeechStarted('r2', 'Reply two.'),
        const VoiceReset('Task cancelled'),
      ];
      for (final e in steps) {
        voice.add(e);
        await tester.pump(const Duration(milliseconds: 90));
        expect(tester.takeException(), isNull);
        expect(
          tester.element(find.byKey(const ValueKey('presence-orb'))),
          same(orb),
        );
      }
      await tester.pump(const Duration(seconds: 1));
      expect(voice.session.phase, VoicePhase.off);
      expect(find.byKey(const ValueKey('presence-waveform')), findsNothing);
      expect(find.text('Task cancelled'), findsOneWidget);
      voice.dispose();
    });

    testWidgets('user speech shows the shared waveform and the transcript', (
      tester,
    ) async {
      final voice = VoiceSessionController(simulated: true);
      await tester.pumpWidget(host(voice, const CompanionSignal.idle()));
      voice
        ..add(const ListeningStarted('u'))
        ..add(const UserSpeechStarted('u'))
        ..add(const UserTranscript('u', 'draft a reply'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 700));
      expect(find.byKey(const ValueKey('presence-waveform')), findsOneWidget);
      expect(find.text('You'), findsOneWidget);
      expect(
        find.textContaining('draft a reply', findRichText: true),
        findsOneWidget,
      );
      expect(find.text('SIMULATED'), findsWidgets); // transcript and status
      voice.add(const ListeningEnded('u', VoiceEndReason.completed));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 700));
      expect(find.byKey(const ValueKey('presence-waveform')), findsNothing);
      voice.dispose();
    });

    testWidgets('reduced motion and reduced effects still build', (
      tester,
    ) async {
      for (final e in [
        EffectsSettings(reducedMotion: true),
        EffectsSettings(reducedEffects: true),
      ]) {
        final voice = VoiceSessionController();
        await tester.pumpWidget(
          host(voice, const CompanionSignal.idle(), effects: e),
        );
        voice.add(const UriSpeechStarted('r', 'Reply.'));
        voice.add(const AudioLevel(VoiceSpeaker.uri, 0.1));
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 400));
        expect(tester.takeException(), isNull);
        expect(find.byKey(const ValueKey('presence-waveform')), findsOneWidget);
        voice.add(const VoiceReset());
        await tester.pump(const Duration(milliseconds: 400));
        await tester.pumpWidget(const SizedBox());
        voice.dispose();
      }
    });
  });
}
