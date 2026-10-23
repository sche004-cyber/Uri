// Writing Intelligence strip (plan 16, WI-7): suggestions after a pause, Accept / Dismiss / Accept all / Undo,
// Brain buttons only on request, rewrite-class items marked, refusals in words, the document untouched.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/integration/scheduler_client.dart' show SchedulerApiError;
import 'package:uri_ui/living/office/writing_assist.dart';

class FakeWriting implements WritingService {
  final checks = <String>[];
  final brainCalls = <String>[];
  Map<String, dynamic> Function(String) onCheck = (t) => {'suggestions': [], 'status': {'spelling': 'ok'}};
  Map<String, dynamic>? brainAnswer;
  String? brainError;

  @override
  Future<Map<String, dynamic>> writingCheck(String text, {List<String> ignore = const []}) async {
    checks.add(text);
    final r = onCheck(text);
    return {...r, 'suggestions': [for (final s in r['suggestions'] as List) if (!ignore.contains((s as Map)['id'])) s]};
  }

  @override
  Future<Map<String, dynamic>> writingApply(String text, List<Map<String, dynamic>> accepted) async {
    final items = [...accepted]..sort((a, b) => (b['start'] as int).compareTo(a['start'] as int));
    var out = text;
    for (final a in items) {
      if (out.substring(a['start'] as int, a['end'] as int) != a['original']) throw SchedulerApiError('STALE_SUGGESTION', null);
      out = out.replaceRange(a['start'] as int, a['end'] as int, a['replacement'] as String);
    }
    return {'text': out};
  }

  Future<Map<String, dynamic>> _brain(String what) async {
    brainCalls.add(what);
    if (brainError != null) throw SchedulerApiError(brainError!, null);
    return brainAnswer ?? {'suggestions': [], 'message': ''};
  }

  @override
  Future<Map<String, dynamic>> writingProofread(String text) => _brain('proofread');
  @override
  Future<Map<String, dynamic>> writingRewrite(String text, String tone) => _brain('rewrite:$tone');
  @override
  Future<Map<String, dynamic>> writingComplete(String text) => _brain('complete');
  @override
  Future<void> writingPrewarm() async {}
}

Map<String, dynamic> sugg(String id, int start, int end, String original, String rep,
        {String cls = 'correction', String message = 'Spelling.'}) =>
    {'id': id, 'start': start, 'end': end, 'original': original, 'replacements': [rep], 'class': cls,
     'kind': 'spelling', 'message': message};

Future<TextEditingController> pump(WidgetTester tester, FakeWriting w, String text) async {
  final c = TextEditingController(text: text);
  await tester.pumpWidget(MaterialApp(
    home: Scaffold(body: SingleChildScrollView(child: Column(children: [
      TextField(key: const ValueKey('field'), controller: c),
      WritingStrip(controller: c, service: w, debounce: const Duration(milliseconds: 50)),
    ]))),
  ));
  await tester.pump(const Duration(milliseconds: 60));
  await tester.pump();
  return c;
}

void main() {
  testWidgets('suggestions appear after a pause; accept changes only the field text; undo restores it',
      (tester) async {
    final w = FakeWriting()
      ..onCheck = (t) => t == 'i recieve it'
          ? {'suggestions': [sugg('a', 0, 1, 'i', 'I'), sugg('b', 2, 9, 'recieve', 'receive')],
             'status': {'spelling': 'ok'}}
          : {'suggestions': [], 'status': {'spelling': 'ok'}};
    final c = await pump(tester, w, 'i recieve it');
    expect(find.text('recieve  →  receive'), findsOneWidget);
    expect(find.text('Accept all corrections (2)'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('writing-item-1-accept-0')));
    await tester.pump();
    expect(c.text, 'i receive it');
    await tester.tap(find.byKey(const ValueKey('writing-undo')));
    await tester.pump();
    expect(c.text, 'i recieve it');
    expect(w.brainCalls, isEmpty);                   // typing never calls the Brain
    await tester.pump(const Duration(milliseconds: 60));
  });

  testWidgets('accept all takes corrections only; rewrite items are marked and need their own accept',
      (tester) async {
    final w = FakeWriting()
      ..onCheck = (t) => {'suggestions': [
            sugg('a', 0, 1, 'i', 'I'),
            sugg('b', 2, 9, 'recieve', 'receive'),
            sugg('c', 13, 15, '12', '14', cls: 'rewrite', message: 'A number changed.'),
          ], 'status': {'spelling': 'ok'}};
    final c = await pump(tester, w, 'i recieve it 12 May');
    expect(find.textContaining('May change meaning'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('writing-accept-all')));
    await tester.pump();
    expect(c.text, 'I receive it 12 May');
    await tester.pump(const Duration(milliseconds: 60));
  });

  testWidgets('dismiss hides a suggestion and it is not offered again', (tester) async {
    final w = FakeWriting()..onCheck = (t) => {'suggestions': [sugg('a', 0, 1, 'i', 'I')], 'status': {'spelling': 'ok'}};
    final c = await pump(tester, w, 'i go');
    await tester.tap(find.byKey(const ValueKey('writing-item-0-dismiss')));
    await tester.pump();
    expect(find.text('i  →  I'), findsNothing);
    c.text = 'i go now';
    await tester.pump(const Duration(milliseconds: 60));
    await tester.pump();
    expect(find.text('i  →  I'), findsNothing);
    expect(c.text, 'i go now');
  });

  testWidgets('Brain buttons run on request; refusals and spelling status are said in words', (tester) async {
    final w = FakeWriting()
      ..onCheck = ((t) => {'suggestions': [], 'status': {'spelling': 'SPELL_UNAVAILABLE'}})
      ..brainError = 'BRAIN_UNAVAILABLE';
    await pump(tester, w, 'text here');
    expect(find.textContaining('Windows spell checker is not available'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('writing-proofread')));
    await tester.pump();
    await tester.pump();
    expect(w.brainCalls, ['proofread']);
    expect(find.textContaining('local Brain is not running'), findsOneWidget);
    w
      ..brainError = null
      ..brainAnswer = {'suggestions': [sugg('f', 0, 9, 'text here', 'This is the text.', cls: 'rewrite', message: 'Formal version.')],
        'message': ''};
    await tester.tap(find.byKey(const ValueKey('writing-formal')));
    await tester.pump();
    await tester.pump();
    expect(w.brainCalls.last, 'rewrite:formal');
    expect(find.textContaining('May change meaning: Formal version.'), findsOneWidget);
    expect(find.text('Use this'), findsOneWidget);
  });

  testWidgets('results for older text are never shown', (tester) async {
    final w = FakeWriting()..onCheck = (t) => {'suggestions': [sugg('a', 0, 1, 'i', 'I')], 'status': {'spelling': 'ok'}};
    final c = await pump(tester, w, 'i go');
    expect(find.text('i  →  I'), findsOneWidget);
    c.text = 'We go';
    await tester.pump();
    expect(find.text('i  →  I'), findsNothing);
    await tester.pump(const Duration(milliseconds: 60));
  });
}
