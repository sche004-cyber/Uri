// Plan 16 increment 1, OD-A in the app: "Draft with URI…" on Office Home (instruction + optional kind of document)
// opens the Word editor on the draft and lists missing facts in words; clarify / cannot / a missing Brain are said in
// words and open nothing; a request routed to write_document drafts from the request's words; a PDF's text goes to
// the clipboard ("Copy text"), scanned pages only on request, and into a new Word document ("To Word"). The Office
// service is a fake (package:http/testing MockClient).
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_workspace.dart';
import 'package:uri_ui/theme/uri_theme.dart';

final _png = base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=');

const _aid = '00112233445566778899aabbccddeeff';
const _fact = "The draft does not contain the amount '25,000' from your instruction. Check it before saving.";

Map<String, dynamic> _view(String name) => {
      'authoring_id': _aid, 'kind': 'docx', 'name': name, 'new': true, 'path': null,
      'doc': {'blocks': [
        {'index': 0, 'expect': 'a00000000000', 'kind': 'paragraph', 'style': 'Title', 'level': 0,
         'text': 'Office Order', 'picture': false, 'page_break': false, 'section_break': false, 'locked': null},
        {'index': 1, 'expect': 'a11111111111', 'kind': 'paragraph', 'style': 'List Number', 'level': null,
         'text': 'Shri Ramesh Kumar is transferred.', 'picture': false, 'page_break': false, 'section_break': false,
         'locked': null},
      ], 'styles': ['Normal', 'Title', 'Heading 1', 'List Number'],
              'page': {'orientation': 'portrait', 'margins_cm': {}, 'sections': 1}, 'header': '', 'footer': ''},
      'changes': [], 'can_undo': false, 'can_redo': false, 'preview_document_id': 'p0', 'sha256_prefix': 'abc',
    };

class FakeDailyOffice {
  final calls = <String>[];
  final bodies = <String, List<Map<String, dynamic>>>{};
  Map<String, dynamic>? draftReply;
  int draftStatus = 200;
  bool brain = true;
  Map<String, dynamic> requestReply = {'result': 'clarify', 'chips': []};
  String docKind = 'pdf';
  Map<String, dynamic> textReply = {
    'pages': [{'page': 1, 'text': 'Notice of meeting', 'source': 'text'}, {'page': 2, 'text': '', 'source': 'none'}],
    'text': '--- Page 1 ---\nNotice of meeting\n\n--- Page 2 ---\n', 'truncated': false, 'pages_without_text': [2],
  };

  Map<String, dynamic> ocrReply = {
    'pages': [{'page': 1, 'text': 'Notice of meeting', 'source': 'text'}, {'page': 2, 'text': '', 'source': 'none'}],
    'text': '--- Page 1 ---\nNotice of meeting\n\n--- Page 2 ---\n', 'truncated': false, 'pages_without_text': [2],
    'ocr_skipped': [2], 'ocr_skipped_reasons': {'page_limit': [], 'size_limit': [], 'time_limit': [2]},
  };

  Map<String, dynamic> get doc => {
        'document_id': '0123456789abcdef', 'kind': docKind, 'name': 'notice.$docKind', 'pages': 2, 'outline': [],
        'preview': {'state': 'ready', 'reason': null}, 'findings': [], 'renderer': 'Windows',
      };

  http.Client client() => MockClient((req) async {
        final path = req.url.path;
        calls.add('${req.method} $path');
        Map<String, dynamic> body = {};
        if (req.body.isNotEmpty) body = (jsonDecode(req.body) as Map).cast<String, dynamic>();
        bodies.putIfAbsent(path, () => []).add(body);
        if (path.contains('/page/')) return http.Response.bytes(_png, 200, headers: {'content-type': 'image/png'});
        if (path == '/authoring/draft') {
          return http.Response(jsonEncode(draftReply), draftStatus);
        }
        final Map<String, dynamic> out = switch ('${req.method} $path') {
          'GET /status' => {'ok': true},
          'GET /contract' => {'contract': 'o2.1'},
          'GET /capabilities' => {
              'goals': [{'id': 'write', 'title': 'Write'}],
              'capabilities': [
                {'id': 'write_document', 'goal': 'write', 'title': 'Write a letter or notice', 'status': 'available',
                 'ready': brain, 'unready_reason': brain ? null : 'BRAIN_UNAVAILABLE', 'inputs': []},
              ]},
          'GET /engines' => {'engines': [{'id': 'libreoffice', 'state': 'ready'}]},
          'GET /recent' => {'items': []},
          'GET /workflows' => {'running': [], 'done': []},
          'GET /authoring/layouts' => {'docx': [
              {'id': 'blank', 'title': 'Blank document'}, {'id': 'office_order', 'title': 'Office order'},
              {'id': 'notesheet', 'title': 'Note sheet'}, {'id': 'circular', 'title': 'Circular'}]},
          'POST /request' => requestReply,
          'POST /open/document' => doc,
          'GET /document/0123456789abcdef' => doc,
          'POST /document/0123456789abcdef/text' => body['ocr'] == true ? ocrReply : textReply,
          'POST /document/0123456789abcdef/to_word' => {..._view('notice (text).docx'), 'pages_without_text': [2],
              'truncated': false,
              if (body['ocr'] == true) 'ocr_skipped_reasons': {'page_limit': [], 'size_limit': [], 'time_limit': [2]}},
          'POST /authoring/$_aid/close' => {'closed': true, 'unsaved_changes': 0},
          _ => path.startsWith('/document/p')
              ? {'document_id': 'p0', 'kind': 'docx', 'name': 'x', 'pages': 1, 'preview': {'state': 'ready'},
                 'outline': [], 'findings': []}
              : {'error': 'NOT_FOUND'},
        };
        if (out['error'] != null) return http.Response(jsonEncode(out), 404);
        return http.Response(jsonEncode(out), 200);
      });
}

OfficeEnvironment _env(String docKind) => OfficeEnvironment(
      surfaceFactory: () => throw UnimplementedError(),
      pickWorkbookPath: () async => null,
      pickSavePath: (_) async => null,
      openExternalLink: (_) async {},
      pickDocumentPath: () async => 'C:\\Users\\me\\notice.$docKind',
      pickPdfSavePath: (_) async => null,
      pickDocumentSavePath: (_) async => null,
    );

Future<FakeDailyOffice> _pump(WidgetTester tester, {String docKind = 'pdf', bool brain = true}) async {
  SharedPreferences.setMockInitialValues({});
  await tester.binding.setSurfaceSize(const Size(1600, 1000));
  addTearDown(() => tester.binding.setSurfaceSize(null));
  final fake = FakeDailyOffice()
    ..docKind = docKind
    ..brain = brain;
  final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', fake.client());
  await tester.pumpWidget(MaterialApp(
    theme: ThemeData(extensions: const [UriColors.graphite]),
    home: Scaffold(body: OfficeWorkspace(environment: _env(docKind), clientFactory: () => client)),
  ));
  await tester.pumpAndSettle();
  return fake;
}

Future<void> _settle(WidgetTester tester) async {
  await tester.pump(const Duration(milliseconds: 800));
  await tester.pumpAndSettle();
}

Future<void> _unmount(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox());
  await tester.pump(const Duration(seconds: 1));
}

Future<void> _draft(WidgetTester tester, String text, {String? layoutTitle}) async {
  await tester.tap(find.byKey(const ValueKey('office-home-draft')));
  await tester.pumpAndSettle();
  expect(find.byKey(const ValueKey('office-draft-dialog')), findsOneWidget);
  await tester.enterText(find.byKey(const ValueKey('office-draft-instruction')), text);
  if (layoutTitle != null) {
    await tester.tap(find.byKey(const ValueKey('office-draft-layout')));
    await tester.pumpAndSettle();
    await tester.tap(find.text(layoutTitle).last);
    await tester.pumpAndSettle();
  }
  await tester.tap(find.byKey(const ValueKey('office-draft-go')));
  await _settle(tester);
}

void main() {
  testWidgets('OD-2: Draft with URI opens the Word editor on the draft and lists missing facts in words',
      (tester) async {
    final fake = await _pump(tester);
    fake.draftReply = {..._view('Note sheet (draft).docx'), 'status': 'propose', 'message': 'Drafted.',
      'layout': 'notesheet', 'layout_title': 'Note sheet', 'missing': ['file number'],
      'warnings': [{'code': 'FACT_MISSING', 'kind': 'amount', 'text': '25,000', 'message': _fact}]};
    expect(find.byKey(const ValueKey('office-home-cap-write_document')), findsNothing);   // one entry: the chip below
    await _draft(tester, 'Put up a note for buying laptops worth Rs. 25,000', layoutTitle: 'Note sheet');
    expect(fake.bodies['/authoring/draft']!.single,
        {'instruction': 'Put up a note for buying laptops worth Rs. 25,000', 'layout': 'notesheet'});
    expect(find.byKey(const ValueKey('authoring-block-1')), findsOneWidget);             // the Word editor
    expect(find.text('Editing Note sheet (draft).docx'), findsOneWidget);
    expect(find.byKey(const ValueKey('office-draft-warnings')), findsOneWidget);
    expect(find.text(_fact), findsOneWidget);
    expect(find.byKey(const ValueKey('office-draft-scope-note')), findsOneWidget);    // OD-OD-4: scope shown too
    expect(tester.takeException(), isNull);
    await _unmount(tester);
  });

  testWidgets('OD-2: clarify without a kind offers the kinds; picking one drafts in that kind', (tester) async {
    final fake = await _pump(tester);
    fake.draftReply = {'status': 'clarify', 'layout': null, 'missing': [], 'warnings': [],
      'message': 'Which kind of document should URI write?',
      'layouts': [{'id': 'circular', 'title': 'Circular'}, {'id': 'notice', 'title': 'Notice'}]};
    await _draft(tester, 'write about the holiday');
    expect(find.textContaining('Which kind of document should URI write? Nothing was drafted.'), findsOneWidget);
    expect(find.byKey(const ValueKey('authoring-block-0')), findsNothing);
    fake.draftReply = {'status': 'cannot', 'message': 'That is not a document.', 'missing': [], 'warnings': [],
      'layout': 'circular'};
    await tester.tap(find.widgetWithText(InputChip, 'Circular'));
    await _settle(tester);
    expect(fake.bodies['/authoring/draft']!.last, {'instruction': 'write about the holiday', 'layout': 'circular'});
    expect(find.textContaining('That is not a document. Nothing was drafted.'), findsOneWidget);
    expect(find.byKey(const ValueKey('authoring-block-0')), findsNothing);
    expect(tester.takeException(), isNull);
    await _unmount(tester);
  });

  testWidgets('OD-2: no Brain is said in words', (tester) async {
    final fake = await _pump(tester);
    fake
      ..draftStatus = 503
      ..draftReply = {'error': 'BRAIN_UNAVAILABLE', 'detail': ''};
    await _draft(tester, 'write a letter to the collector');
    // in the conversation and in the status strip
    expect(find.text('The local Brain is not running, so URI cannot draft or decide this now.'), findsWidgets);
    expect(find.byKey(const ValueKey('authoring-block-0')), findsNothing);
    await _unmount(tester);
  });

  testWidgets('OD-2: without a Brain the Draft chip is off and says why', (tester) async {
    await _pump(tester, brain: false);
    final chip = tester.widget<ActionChip>(find.byKey(const ValueKey('office-home-draft')));
    expect(chip.onPressed, isNull);
    expect(find.byTooltip('The local Brain is not running, so URI cannot draft or decide this now.'), findsOneWidget);
    await _unmount(tester);
  });

  testWidgets('OD-2: a request routed to write_document drafts from the request words', (tester) async {
    final fake = await _pump(tester);
    fake
      ..requestReply = {'result': 'matched', 'intent': 'write_document', 'capability': 'write_document', 'stage': 1,
                        'inputs_needed': [], 'route': '/authoring/draft'}
      ..draftReply = {..._view('Office order (draft).docx'), 'status': 'propose', 'message': '',
                      'layout': 'office_order', 'layout_title': 'Office order', 'missing': [], 'warnings': []};
    await tester.enterText(find.byKey(const ValueKey('office-request')), 'write an office order for the transfer');
    await tester.tap(find.byKey(const ValueKey('office-request-send')));
    await _settle(tester);
    expect(fake.bodies['/authoring/draft']!.single, {'instruction': 'write an office order for the transfer'});
    expect(find.text('Editing Office order (draft).docx'), findsOneWidget);
    expect(find.byKey(const ValueKey('office-draft-warnings')), findsNothing);
    // OD-OD-4: a draft with no warnings still says what URI checked and that the owner reads the whole draft
    expect(find.byKey(const ValueKey('office-draft-scope')), findsOneWidget);
    expect(find.textContaining('read the whole draft before saving'), findsOneWidget);
    await _unmount(tester);
  });

  testWidgets('OD-3: Copy text puts the page-labelled text on the clipboard; scanned pages only on request',
      (tester) async {
    final fake = await _pump(tester);
    String? clip;
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
      if (call.method == 'Clipboard.setData') clip = (call.arguments as Map)['text'] as String?;
      return null;
    });
    addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
    await tester.tap(find.byKey(const ValueKey('office-open-document')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-pdf-copy-text')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('office-pdf-copy-text')));
    await _settle(tester);
    expect(fake.bodies['/document/0123456789abcdef/text']!.single, isEmpty);           // no OCR unless asked
    expect(clip, '--- Page 1 ---\nNotice of meeting\n\n--- Page 2 ---\n');
    expect(find.textContaining('Copied the text of 2 pages to the clipboard. 1 page has no text'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('office-chip-pdf:ocr_copy')));
    await _settle(tester);
    expect(fake.bodies['/document/0123456789abcdef/text']!.last, {'ocr': true});
    // FB1 R2-05: a page left out at the time limit is named so, not as unreadable
    expect(find.textContaining('1 page not read: the time limit was reached.'), findsOneWidget);
    expect(find.textContaining('could not be read'), findsNothing);
    expect(tester.takeException(), isNull);
    await _unmount(tester);
  });

  testWidgets('OD-3: To Word opens a new Word document made from the PDF text', (tester) async {
    final fake = await _pump(tester);
    await tester.tap(find.byKey(const ValueKey('office-open-document')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-pdf-to-word')));
    await _settle(tester);
    expect(fake.calls, contains('POST /document/0123456789abcdef/to_word'));
    expect(find.text('Editing notice (text).docx'), findsOneWidget);
    expect(find.byKey(const ValueKey('authoring-block-0')), findsOneWidget);
    await _unmount(tester);
  });

  testWidgets('OD-3 (live-driver finding): the toolbar Read scans switch sends OCR for Copy text and To Word',
      (tester) async {
    final fake = await _pump(tester);
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async => null);
    addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
    await tester.tap(find.byKey(const ValueKey('office-open-document')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-pdf-ocr')));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('office-pdf-copy-text')));
    await _settle(tester);
    expect(fake.bodies['/document/0123456789abcdef/text']!.last, {'ocr': true});
    await tester.tap(find.byKey(const ValueKey('office-pdf-to-word')));
    await _settle(tester);
    expect(fake.bodies['/document/0123456789abcdef/to_word']!.last, {'ocr': true});
    await _unmount(tester);
  });

  testWidgets('FB2 R3-05: To Word with Read scans names the limit that left a page out', (tester) async {
    await _pump(tester);
    await tester.tap(find.byKey(const ValueKey('office-open-document')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-pdf-ocr')));
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('office-pdf-to-word')));
    await _settle(tester);
    await tester.tap(find.byKey(const ValueKey('office-toggle-uri')));        // the URI pane beside the editor
    await _settle(tester);
    expect(find.textContaining('1 page not read: the time limit was reached.'), findsOneWidget);
    expect(find.textContaining('no text (they may be scans)'), findsNothing);
    await _unmount(tester);
  });

  testWidgets('OD-3: a Word document view has no PDF text buttons', (tester) async {
    await _pump(tester, docKind: 'docx');
    await tester.tap(find.byKey(const ValueKey('office-open-document')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-pdf-copy-text')), findsNothing);
    expect(find.byKey(const ValueKey('office-pdf-to-word')), findsNothing);
    await _unmount(tester);
  });
}
