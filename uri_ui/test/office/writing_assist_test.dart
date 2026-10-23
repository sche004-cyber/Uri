// Writing Intelligence strip (plan 16, WI-7): suggestions after a pause, Accept / Dismiss / Accept all / Undo,
// Brain buttons only on request, rewrite-class items marked, refusals in words, the document untouched.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/living/integration/scheduler_client.dart' show SchedulerApiError;
import 'package:uri_ui/living/office/document_controller.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/presentation_editor.dart';
import 'package:uri_ui/living/office/word_editor.dart';
import 'package:uri_ui/living/office/writing_assist.dart';
import 'package:uri_ui/theme/uri_theme.dart';

class FakeWriting implements WritingService {
  final checks = <String>[];
  final brainCalls = <String>[];
  List<String> lastIgnore = const [];
  Map<String, dynamic> Function(String) onCheck = (t) => {'suggestions': [], 'status': {'spelling': 'ok'}};
  Map<String, dynamic>? brainAnswer;
  String? brainError;

  @override
  Future<Map<String, dynamic>> writingCheck(String text, {List<String> ignore = const []}) async {
    checks.add(text);
    lastIgnore = ignore;
    final r = onCheck(text);
    // like the engine: ignore by id or by the (lower-case) original word
    return {...r, 'suggestions': [
      for (final s in r['suggestions'] as List)
        if (!ignore.contains((s as Map)['id']) && !ignore.contains('${s['original']}'.toLowerCase())) s
    ]};
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
  testWidgets('Word and PowerPoint authoring fields expose writing help', (tester) async {
    await tester.binding.setSurfaceSize(const Size(1600, 1400));
    addTearDown(() => tester.binding.setSurfaceSize(null));
    final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't',
        MockClient((_) async => http.Response('{}', 404)));
    final workspace = OfficeWorkspaceController(client: client);
    final slide = PresentationEditController(client, {
      'authoring_id': 'test', 'kind': 'pptx', 'name': 'Test',
      'deck': {'slides': [
        {'id': 1, 'title_id': 2, 'title': 'Draft title', 'notes': '', 'items': [
          {'id': 2, 'kind': 'text', 'paragraphs': ['Draft title']},
          {'id': 3, 'kind': 'table', 'cells': [['Draft cell']]},
        ]}
      ]},
    });
    await tester.pumpWidget(MaterialApp(theme: ThemeData(extensions: const [UriColors.graphite]),
        home: Scaffold(body: PresentationEditor(workspace: workspace, editor: slide))));
    expect(find.byKey(const ValueKey('authoring-title-writing')), findsOneWidget);
    expect(find.byKey(const ValueKey('authoring-cell-3-0-0-writing')), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    slide.dispose();

    final word = PresentationEditController(client, {
      'authoring_id': 'test', 'kind': 'docx', 'name': 'Test',
      'doc': {'blocks': [
        {'index': 0, 'expect': 'test', 'kind': 'table', 'cells': [['Draft cell']]}
      ], 'header': 'Draft header', 'footer': 'Draft footer'},
    });
    await tester.pumpWidget(MaterialApp(theme: ThemeData(extensions: const [UriColors.graphite]),
        home: Scaffold(body: WordEditor(workspace: workspace, editor: word))));
    expect(find.byKey(const ValueKey('authoring-header-writing')), findsOneWidget);
    expect(find.byKey(const ValueKey('authoring-footer-writing')), findsOneWidget);
    expect(find.byKey(const ValueKey('authoring-wcell-0-0-writing')), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    word.dispose();
    workspace.dispose();
  });

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

  testWidgets('Accept all preserves reference separators and clause parentheses', (tester) async {
    const text = 'i recieve Ref. 12/3/2026 and Clause (a).';
    final firstSlash = text.indexOf('/');
    final secondSlash = text.indexOf('/', firstSlash + 1);
    final open = text.indexOf('(');
    final close = text.indexOf(')');
    final w = FakeWriting()..onCheck = (_) => {'suggestions': [
      sugg('capital', 0, 1, 'i', 'I'),
      sugg('spelling', 2, 9, 'recieve', 'receive'),
      sugg('sep1', firstSlash, firstSlash + 1, '/', '-', cls: 'rewrite'),
      sugg('sep2', secondSlash, secondSlash + 1, '/', '-', cls: 'rewrite'),
      sugg('paren1', open, open + 1, '(', '', cls: 'rewrite'),
      sugg('paren2', close, close + 1, ')', '', cls: 'rewrite'),
    ], 'status': {'spelling': 'ok'}};
    final c = await pump(tester, w, text);
    expect(find.text('Accept all corrections (2)'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('writing-accept-all')));
    await tester.pump();
    expect(c.text, 'I receive Ref. 12/3/2026 and Clause (a).');
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

  // ---- review FB1 regressions ----
  testWidgets('R2-05: typing after an accept (or clearing the field) ends Undo', (tester) async {
    final w = FakeWriting()
      ..onCheck = (t) => t == 'i go'
          ? {'suggestions': [sugg('a', 0, 1, 'i', 'I')], 'status': {'spelling': 'ok'}}
          : {'suggestions': [], 'status': {'spelling': 'ok'}};
    final c = await pump(tester, w, 'i go');
    await tester.tap(find.byKey(const ValueKey('writing-item-0-accept-0')));
    await tester.pump();
    expect(c.text, 'I go');
    expect(find.byKey(const ValueKey('writing-undo')), findsOneWidget);
    c.text = 'I go home';                       // the owner keeps typing
    await tester.pump();
    expect(find.byKey(const ValueKey('writing-undo')), findsNothing);
    expect(c.text, 'I go home');
    await tester.pump(const Duration(milliseconds: 60));
  });

  testWidgets('R2-06: a dismissed word stays dismissed when its position changes', (tester) async {
    final w = FakeWriting()
      ..onCheck = (t) {
        final i = t.indexOf('recieve');
        return {'suggestions': [if (i >= 0) sugg('id$i', i, i + 7, 'recieve', 'receive')], 'status': {'spelling': 'ok'}};
      };
    final c = await pump(tester, w, 'I recieve it');
    await tester.tap(find.byKey(const ValueKey('writing-item-0-dismiss')));
    await tester.pump();
    c.text = 'Yes, I recieve it';               // an earlier edit moves the word
    await tester.pump(const Duration(milliseconds: 60));
    await tester.pump();
    expect(find.text('recieve  →  receive'), findsNothing);
    expect(w.lastIgnore, contains('recieve'));
  });

  testWidgets('R2-03 / R2-01: guesses stay out of Accept all; meaning flags are shown', (tester) async {
    final w = FakeWriting()
      ..onCheck = ((t) => {'suggestions': [
            sugg('a', 0, 1, 'i', 'I'),
            {...sugg('g', 2, 14, 'mukhyamantri', 'mahamari'), 'confidence': 'guess'},
            sugg('b', 15, 22, 'recieve', 'receive'),
          ], 'status': {'spelling': 'ok'}})
      ..brainAnswer = {'suggestions': [sugg('n', 0, 1, 'i', 'I', cls: 'rewrite')],
        'flags': [{'code': 'MEANING_CHANGED', 'severity': 'error', 'detail': 'missing after correction: 3, january'}],
        'message': ''};
    final c = await pump(tester, w, 'i mukhyamantri recieve');
    expect(find.text('Accept all corrections (2)'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('writing-accept-all')));
    await tester.pump();
    expect(c.text, 'I mukhyamantri receive');   // the guess was not applied
    await tester.tap(find.byKey(const ValueKey('writing-proofread')));
    await tester.pump();
    await tester.pump();
    expect(find.textContaining('missing after correction: 3, january'), findsOneWidget);
    await tester.pump(const Duration(milliseconds: 60));
  });

  // ---- review FB2 regressions ----
  testWidgets('R3-04: after accepting one Brain item the others stay, moved by the change', (tester) async {
    final w = FakeWriting()
      ..brainAnswer = {'suggestions': [
            sugg('x', 0, 3, 'pls', 'please', cls: 'rewrite', message: 'Wording.'),
            sugg('y', 9, 12, 'abt', 'about', cls: 'rewrite', message: 'Wording.'),
          ], 'message': ''};
    final c = await pump(tester, w, 'pls send abt it');
    await tester.tap(find.byKey(const ValueKey('writing-proofread')));
    await tester.pump();
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('writing-item-0-accept-0')));
    await tester.pump();
    expect(c.text, 'please send abt it');
    expect(find.text('abt  →  about'), findsOneWidget);       // still offered
    await tester.tap(find.byKey(const ValueKey('writing-item-0-accept-0')));
    await tester.pump();
    expect(c.text, 'please send about it');                    // applied at its moved position
    expect(w.brainCalls, ['proofread']);                       // no second Brain call was needed
    await tester.pump(const Duration(milliseconds: 60));
  });

  testWidgets('R5-02: retained offsets use original spans across multiple accepted edits', (tester) async {
    const text = 'abcdefghijklmnopqrstu';
    final w = FakeWriting()..onCheck = (_) => {'suggestions': [
      sugg('insert', 0, 0, '', '01234567890123456789'),
      sugg('retained', 10, 11, 'k', 'K', cls: 'rewrite'),
      sugg('later', 20, 21, 'u', 'UU'),
    ], 'status': {'spelling': 'ok'}};
    final c = await pump(tester, w, text);
    await tester.tap(find.byKey(const ValueKey('writing-accept-all')));
    await tester.pump();
    expect(c.text, '01234567890123456789abcdefghijklmnopqrstUU');
    expect(find.text('k  →  K'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('writing-item-0-accept-0')));
    await tester.pump();
    expect(c.text, '01234567890123456789abcdefghijKlmnopqrstUU');
  });

  testWidgets('R3-03: dismissing a capital or a/an item does not hide every other one', (tester) async {
    final w = FakeWriting()
      ..onCheck = ((t) => {'suggestions': [
            {...sugg('c1', 0, 1, 't', 'T'), 'kind': 'capital'},
          ], 'status': {'spelling': 'ok'}});
    final c = await pump(tester, w, 'the end.');
    await tester.tap(find.byKey(const ValueKey('writing-item-0-dismiss')));
    await tester.pump();
    c.text = 'the end. ok';
    await tester.pump(const Duration(milliseconds: 60));
    await tester.pump();
    expect(w.lastIgnore, isNot(contains('t')));
    expect(w.lastIgnore, contains('c1'));
  });
}
