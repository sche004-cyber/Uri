import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:uri_ui/living/integration/draft_panel.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_draft.dart';

import 'ws_integration_test.dart' show FakeRuntime, host;

/// Text intelligence in the Living UI (TI-AC6, TI-AC9).

Map<String, dynamic> version(int n, List<List<String>> blocks,
        {String op = 'revised', List<String> changed = const [], List<Map<String, String>> flags = const [],
        List<String> missing = const []}) =>
    {
      'n': n,
      'blocks': [
        for (final b in blocks) {'id': b[0], 'role': b[1], 'text': b[2]},
      ],
      'text': [for (final b in blocks) b[2]].join('\n\n'),
      'op': op,
      'summary': 'summary $n',
      'instruction': 'instruction $n',
      'changed': changed,
      'removed': <String>[],
      'flags': flags,
      'missing': missing,
    };

final v1 = version(1, [
  ['b1', 'subject', 'Subject: Students leaving the hostel'],
  ['b2', 'body', 'Seven students left the hostel on Monday without permission.'],
  ['b3', 'body', 'Thanking you.'],
], op: 'created', changed: ['b1', 'b2', 'b3'], missing: ['[Your Name]']);
final v2 = version(2, [
  ['b1', 'subject', 'Subject: Students leaving the hostel'],
  ['b2', 'body', 'Seven students left the hostel on Monday without recording their departure in the hostel register.'],
  ['b3', 'body', 'Thanking you.'],
], changed: ['b2'], flags: [
  {'code': 'NEW_DETAIL', 'severity': 'review', 'detail': 'not in your words: 204'},
  {'code': 'DETAIL_DROPPED', 'severity': 'info', 'detail': 'not in the draft because of your correction or instruction: 5'},
]);

Map<String, dynamic> snapshot({required Map<String, dynamic> current, Map<String, dynamic>? previous,
        int position = 2, int count = 2, bool simulated = true}) =>
    {
      'draft_id': 'd1',
      'doc_type': 'letter',
      'tone': 'formal',
      'source': simulated
          ? {'source': 'transcript', 'raw': 'um five sorry seven students', 'engine': 'simulated', 'simulated': true}
          : {'source': 'typed'},
      'original_text': simulated ? 'um five sorry seven students' : 'draft a letter',
      'version': current['n'],
      'position': position,
      'count': count,
      'can_undo': position > 1,
      'can_redo': position < count,
      'current': current,
      'first': v1,
      'previous': previous,
      'pending_question': null,
    };

void main() {
  test('transcript mode sends the uri.text_input.v1 envelope, labelled simulated', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt)..setTranscriptMode(true);
    await conv.send('  um write a letter, no wait, an email  ');
    final c = rt.commands.last;
    expect(c['command'], 'oi_turn');
    // The raw transcript is kept byte for byte, spaces included (Codex TI round 2, C1).
    expect(c['text'], '  um write a letter, no wait, an email  ');
    expect(c['input'], {
      'schema': 'uri.text_input.v1',
      'source': 'transcript',
      'transcript': {'raw': '  um write a letter, no wait, an email  ', 'engine': 'simulated', 'simulated': true},
    });
    expect(conv.messages.lastWhere((m) => m.role == OiRole.user).inputLabel, 'Simulated transcript');

    conv.setTranscriptMode(false);
    rt.emit('t1', 'turn.finished', {'status': 'ok'});
    await pumpEventQueue();
    await conv.send('typed text');
    expect(rt.commands.last.containsKey('input'), isFalse);
    expect(conv.messages.lastWhere((m) => m.role == OiRole.user).inputLabel, isNull);
  });

  test('draft events update the draft; buttons send draft_op, never a turn', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await conv.send('draft a letter');
    rt.emit('t1', 'turn.routed', {'route': 'draft', 'tier': {'tier': 'FAST'}});
    rt.emit('t1', 'draft.progress', {'chars': 240});
    await pumpEventQueue();
    expect(conv.messages.last.draftChars, 240);
    rt.emit('t1', 'draft.updated', {'op': 'revised', 'draft': snapshot(current: v2, previous: v1)});
    rt.emit('t1', 'turn.finished', {'status': 'ok'});
    await pumpEventQueue();
    expect(conv.draft!.current.n, 2);
    expect(conv.draft!.simulatedTranscript, isTrue);
    expect(conv.draft!.sourceLabel, 'Simulated transcript');

    await conv.draftOp('undo');
    expect(rt.commands.last, {'command': 'draft_op', 'session_id': conv.sessionId, 'op': 'undo'});
    await conv.draftOp('restore', version: 1);
    expect(rt.commands.last['version'], 1);
    expect(rt.commands.where((c) => c['command'] == 'oi_turn').length, 1);

    await conv.send('change the date');
    rt.emit('t2', 'draft.clarify', {'question': 'Which date?', 'draft': null});
    await pumpEventQueue();
    expect(conv.draftQuestion, 'Which date?');
  });

  test('a real recogniser must be named; the label says so', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await conv.sendTranscript('hello there', engine: 'faster-whisper-large-v3-turbo', simulated: false, language: 'en-IN');
    final t = rt.commands.last['input']['transcript'] as Map;
    expect(t['simulated'], isFalse);
    expect(t['language'], 'en-IN');
    expect(conv.messages.lastWhere((m) => m.role == OiRole.user).inputLabel, 'Transcript · faster-whisper-large-v3-turbo');
  });

  test('word diff marks only what changed', () {
    final d = wordDiff('Seven students left without permission.', 'Seven students left without recording it.');
    expect(d.where((s) => s.kind == DiffKind.removed).map((s) => s.text.trim()), ['permission.']);
    expect(d.where((s) => s.kind == DiffKind.added).map((s) => s.text.trim()), ['recording it.']);
    expect(d.where((s) => s.kind == DiffKind.same).map((s) => s.text).join(), 'Seven students left without ');
    // A removed word at a line end does not carry the line break into the comparison.
    final nl = wordDiff('Leaving without permission\n\nRespected Sir', 'Leaving without recording it\n\nRespected Sir');
    final removed = nl.where((s) => s.kind == DiffKind.removed).map((s) => s.text).join();
    expect(removed.contains('\n'), isFalse);
    expect(nl.map((s) => s.kind == DiffKind.removed ? '' : s.text).join(), 'Leaving without recording it\n\nRespected Sir');
    final big = List.filled(2000, 'w').join(' ');
    expect(wordDiff(big, '$big x').length, 2); // bounded fallback
  });

  testWidgets('panel: version, simulated label, flags, missing, changes and original views, undo button',
      (tester) async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    conv.draft = OiDraft.parse(snapshot(current: v2, previous: v1));
    await tester.pumpWidget(host(SizedBox(width: 520, height: 900, child: DraftPanel(conversation: conv))));
    await tester.pumpAndSettle();

    expect(find.text('Version 2 of 2'), findsOneWidget);
    expect(find.text('Simulated transcript'), findsOneWidget);
    expect(find.text('Not sent · not saved'), findsOneWidget);
    expect(find.textContaining('Please check: not in your words: 204'), findsOneWidget);
    // Info lines are always shown: nothing is excused silently.
    expect(find.textContaining('Left out: not in the draft because of your correction or instruction: 5'), findsOneWidget);
    expect(find.textContaining('register'), findsOneWidget);

    // Changes: word diff against the previous version.
    await tester.tap(find.text('Changes'));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('draft-diff')), findsOneWidget);

    // Original: the raw transcript, labelled as simulated, apart from URI's interpretation.
    await tester.tap(find.text('Original'));
    await tester.pumpAndSettle();
    expect(find.textContaining('SIMULATED input (no microphone)'), findsOneWidget);
    expect(find.text('um five sorry seven students'), findsOneWidget);
    expect(find.textContaining("URI's interpretation"), findsOneWidget);

    expect(tester.widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Redo')).onPressed, isNull);
    await tester.tap(find.text('Undo'));
    await tester.pump();
    expect(rt.commands.last['command'], 'draft_op');
    expect(rt.commands.last['op'], 'undo');
  });

  testWidgets('a short panel with many checks scrolls instead of overflowing (live UI finding)', (tester) async {
    final conv = OiConversation(FakeRuntime());
    final many = version(2, [
      ['b1', 'body', List.filled(40, 'A long paragraph of text.').join(' ')],
    ], flags: [
      for (var i = 0; i < 8; i++) {'code': 'NEW_DETAIL', 'severity': 'review', 'detail': 'detail $i'},
    ], missing: [for (var i = 0; i < 12; i++) '[Missing item $i]']);
    conv.draft = OiDraft.parse(snapshot(current: many, previous: v1));
    await tester.pumpWidget(host(SizedBox(width: 400, height: 420, child: DraftPanel(conversation: conv))));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(find.byKey(const ValueKey('draft-scroll')), findsOneWidget);
    expect(find.byKey(const ValueKey('draft-undo')), findsOneWidget);
  });

  testWidgets('typed draft is labelled Typed and missing items are shown', (tester) async {
    final conv = OiConversation(FakeRuntime());
    conv.draft = OiDraft.parse(snapshot(current: v1, position: 1, count: 1, simulated: false));
    await tester.pumpWidget(host(SizedBox(width: 520, height: 900, child: DraftPanel(conversation: conv))));
    await tester.pumpAndSettle();
    expect(find.text('Typed'), findsOneWidget);
    expect(find.text('[Your Name]'), findsOneWidget);
    expect(tester.widget<OutlinedButton>(find.widgetWithText(OutlinedButton, 'Undo')).onPressed, isNull);
  });
}
