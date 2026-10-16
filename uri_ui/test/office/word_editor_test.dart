// Authoring milestone C (plan 12 §5): the Word editor. Edit from a .docx view, block list and page preview, change a
// paragraph against its address, style menu, insert a table after a block, header and page numbers, find and replace
// with its counts in words, the real save card ("Save this document?", made by the Python service), and New document
// from a built-in layout with Save as. The Office service is a fake (package:http/testing MockClient).
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
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

List<dynamic> _card() =>
    jsonDecode(File('test/office/fixtures/authoring_save_card_docx.json').readAsStringSync()) as List<dynamic>;

String _cardAid() => RegExp(r'office\.authoring_save\.([0-9a-f]{16})\.')
    .firstMatch('${(_card().first as Map)['createSurface']['surfaceId']}')!
    .group(1)!;

class FakeWordOffice {
  FakeWordOffice() : aid = _cardAid();
  final String aid;
  final calls = <String>[];
  final ops = <Map<String, dynamic>>[];
  final bodies = <String, List<Map<String, dynamic>>>{};
  bool isNew = false;
  Object? result;
  List<Map<String, dynamic>> blocks = [
    {'index': 0, 'expect': 'a00000000000', 'kind': 'paragraph', 'style': 'Title', 'level': 0, 'text': 'Annual Report',
     'picture': false, 'page_break': false, 'section_break': false, 'locked': null},
    {'index': 1, 'expect': 'a11111111111', 'kind': 'paragraph', 'style': 'Heading 1', 'level': 1, 'text': 'Summary',
     'picture': false, 'page_break': false, 'section_break': false, 'locked': null},
    {'index': 2, 'expect': 'a22222222222', 'kind': 'paragraph', 'style': 'Normal', 'level': null,
     'text': 'Costs were flat across the year.', 'picture': false, 'page_break': false, 'section_break': false,
     'locked': null},
    {'index': 3, 'expect': 'a33333333333', 'kind': 'table', 'rows': 2, 'cols': 2,
     'cells': [['Item', 'Cost'], ['Paper', '100']]},
    {'index': 4, 'expect': 'a44444444444', 'kind': 'paragraph', 'style': 'Normal', 'level': null,
     'text': 'Reviewed by the committee.', 'picture': false, 'page_break': false, 'section_break': false,
     'locked': 'a comment'},
  ];
  List<String> changes = [];
  String header = 'Department of Records';

  Map<String, dynamic> view() => {
        'authoring_id': aid, 'kind': 'docx', 'name': isNew ? 'Letter.docx' : 'Annual Report.docx', 'new': isNew,
        'path': isNew ? null : r'C:\Users\me\Documents\Annual Report.docx',
        'doc': {'blocks': blocks, 'styles': ['Normal', 'Title', 'Heading 1', 'Heading 2', 'Quote'],
                'page': {'orientation': 'portrait', 'margins_cm': {}, 'sections': 1}, 'header': header, 'footer': ''},
        'changes': [for (final c in changes) {'text': c}], 'can_undo': changes.isNotEmpty, 'can_redo': false,
        'preview_document_id': 'p${changes.length}', 'sha256_prefix': 'abc', 'result': ?result,
      };

  Map<String, dynamic> doc = {
    'document_id': '0123456789abcdef', 'kind': 'docx', 'name': 'Annual Report.docx', 'pages': 2,
    'outline': [], 'preview': {'state': 'ready', 'reason': null}, 'findings': [], 'renderer': 'LibreOffice',
  };

  http.Client client() => MockClient((req) async {
        final path = req.url.path;
        calls.add('${req.method} $path');
        Map<String, dynamic> body = {};
        if (req.body.isNotEmpty) body = (jsonDecode(req.body) as Map).cast<String, dynamic>();
        bodies.putIfAbsent(path, () => []).add(body);
        if (path.contains('/page/')) return http.Response.bytes(_png, 200, headers: {'content-type': 'image/png'});
        Map<String, dynamic> out;
        result = null;
        if (path.startsWith('/document/p')) {
          out = {'document_id': path.split('/')[2], 'kind': 'docx', 'name': 'x', 'pages': 2,
                 'preview': {'state': 'ready'}, 'outline': [], 'findings': []};
        } else if (path == '/authoring/edit' || path == '/authoring/new') {
          isNew = path == '/authoring/new';
          out = view();
        } else if (path == '/authoring/layouts') {
          out = {'docx': [{'id': 'blank', 'title': 'Blank document'}, {'id': 'letter', 'title': 'Letter'}]};
        } else if (path == '/authoring/$aid/op') {
          final op = (body['op'] as Map).cast<String, dynamic>();
          ops.add(op);
          switch (op['op']) {
            case 'set_paragraph_text':
              blocks = [for (final b in blocks) b['index'] == op['block'] ? {...b, 'text': op['text'],
                  'expect': 'b22222222222'} : b];
            case 'insert_table':
              result = (op['after'] as int) + 1;
            case 'replace_text':
              result = {'replaced': 2, 'split_across_formatting': 1, 'skipped': 0};
            case 'set_header_text':
              header = '${op['text']}';
          }
          changes = [...changes, '${op['op']}'];
          out = view();
        } else if (path == '/authoring/$aid/save') {
          out = {'messages': _card(), 'surface_id': 'x'};
        } else if (path == '/authoring/$aid/close') {
          out = {'closed': true, 'unsaved_changes': changes.length};
        } else if (path == '/a2ui/action') {
          changes = [];
          out = {'status': 'applied', 'subject_kind': 'authoring_save', 'subject_id': aid,
                 'saved_to': 'Annual Report.docx', 'authoring_id': aid};
        } else {
          out = switch ('${req.method} $path') {
            'GET /status' => {'ok': true},
            'GET /contract' => {'contract': 'o2.1'},
            'GET /capabilities' => {'goals': [], 'capabilities': []},
            'GET /engines' => {'engines': [{'id': 'libreoffice', 'state': 'ready'}]},
            'GET /recent' => {'items': []},
            'GET /workflows' => {'running': [], 'done': []},
            'POST /open/document' => doc,
            'GET /document/0123456789abcdef' => doc,
            _ => {'error': 'NOT_FOUND'},
          };
        }
        if (out['error'] != null) return http.Response(jsonEncode(out), 404);
        return http.Response(jsonEncode(out), 200);
      });
}

OfficeEnvironment _env({String? saveAs}) => OfficeEnvironment(
      surfaceFactory: () => throw UnimplementedError(),
      pickWorkbookPath: () async => null,
      pickSavePath: (_) async => null,
      openExternalLink: (_) async {},
      pickDocumentPath: () async => r'C:\Users\me\Documents\Annual Report.docx',
      pickPdfSavePath: (_) async => null,
      pickPresentationSavePath: (_) async => null,
      pickDocumentSavePath: (_) async => saveAs,
      pickWordTemplatePath: () async => null,
    );

Future<FakeWordOffice> _pump(WidgetTester tester, {String? saveAs, Size size = const Size(1600, 1000)}) async {
  SharedPreferences.setMockInitialValues({});
  await tester.binding.setSurfaceSize(size);
  addTearDown(() => tester.binding.setSurfaceSize(null));
  final fake = FakeWordOffice();
  final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', fake.client());
  await tester.pumpWidget(MaterialApp(
    theme: ThemeData(extensions: const [UriColors.graphite]),
    home: Scaffold(body: OfficeWorkspace(environment: _env(saveAs: saveAs), clientFactory: () => client)),
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

void main() {
  testWidgets('C-8: edit a Word document by block, page section, find and replace, save through the card',
      (tester) async {
    final fake = await _pump(tester);
    await tester.tap(find.byKey(const ValueKey('office-open-document')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-edit')));
    await _settle(tester);
    expect(fake.calls, contains('POST /authoring/edit'));
    expect(find.byKey(const ValueKey('authoring-block-4')), findsOneWidget);
    expect(find.text('Page 1 of 2 · preview drawn by LibreOffice'), findsOneWidget);

    // a commented paragraph is kept as it is: no text field
    await tester.tap(find.byKey(const ValueKey('authoring-block-4')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('authoring-block-locked')), findsOneWidget);
    expect(find.byKey(const ValueKey('authoring-para-text')), findsNothing);

    // change paragraph 3 against its address
    await tester.tap(find.byKey(const ValueKey('authoring-block-2')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('authoring-para-text')), 'Costs fell.');
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('authoring-para-text-apply')));
    await _settle(tester);
    expect(fake.ops.last, {'op': 'set_paragraph_text', 'block': 2, 'expect': 'a22222222222', 'text': 'Costs fell.'});

    // the style menu uses the new address
    await tester.tap(find.byKey(const ValueKey('authoring-style')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('authoring-style-Quote')));
    await _settle(tester);
    expect(fake.ops.last, {'op': 'set_style', 'block': 2, 'expect': 'b22222222222', 'style': 'Quote'});

    // insert a table after it; the new block is selected
    await tester.tap(find.byKey(const ValueKey('authoring-insert-table')));
    await _settle(tester);
    expect(fake.ops.last['op'], 'insert_table');
    expect(find.text('BLOCK 4'), findsOneWidget);

    // page section
    await tester.enterText(find.byKey(const ValueKey('authoring-header')), 'Records Division');
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('authoring-header-apply')));
    await _settle(tester);
    expect(fake.ops.last, {'op': 'set_header_text', 'text': 'Records Division'});
    await tester.ensureVisible(find.byKey(const ValueKey('authoring-page-numbers')));
    await tester.tap(find.byKey(const ValueKey('authoring-page-numbers')));
    await _settle(tester);
    expect(fake.ops.last['op'], 'insert_page_number');

    // find and replace reports what it did and what it left
    await tester.ensureVisible(find.byKey(const ValueKey('authoring-find')));
    await tester.enterText(find.byKey(const ValueKey('authoring-find')), 'percent');
    await tester.enterText(find.byKey(const ValueKey('authoring-replace')), '%');
    await tester.ensureVisible(find.byKey(const ValueKey('authoring-replace-all')));
    await tester.tap(find.byKey(const ValueKey('authoring-replace-all')));
    await _settle(tester);
    expect(find.text('Replaced 2. 1 more cross formatting changes and were left as they are.'), findsOneWidget);

    // save through the real card
    await tester.tap(find.byKey(const ValueKey('authoring-save')));
    await _settle(tester);
    expect(find.text('Save this document?'), findsOneWidget);
    expect(find.textContaining("to 'Costs fell.'"), findsOneWidget);
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await _settle(tester);
    expect(find.text('Saved as Annual Report.docx'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await _unmount(tester);
  });

  testWidgets('C-8/AB-10: New document from a layout on Home, then Save as to the picked new file', (tester) async {
    final fake = await _pump(tester, saveAs: r'C:\Users\me\Documents\Letter to the bank.docx');
    expect(find.byKey(const ValueKey('office-home-new-document')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('office-home-new-document')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-layout-letter')));
    await _settle(tester);
    expect(fake.bodies['/authoring/new']!.last, {'kind': 'docx', 'layout': 'letter'});
    expect(find.byKey(const ValueKey('authoring-save')), findsNothing);
    await tester.tap(find.byKey(const ValueKey('authoring-save-as')));
    await _settle(tester);
    expect(fake.bodies['/authoring/${fake.aid}/save']!.last,
        {'save_as_path': r'C:\Users\me\Documents\Letter to the bank.docx'});
    expect(find.text('Save this document?'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await _unmount(tester);
  });

  for (final size in const [Size(1064, 640), Size(900, 640), Size(760, 600)]) {
    testWidgets('the Word editor fits a ${size.width.toInt()}x${size.height.toInt()} Office region', (tester) async {
      await _pump(tester, size: size);
      await tester.tap(find.byKey(const ValueKey('office-home-open')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('office-edit')));
      await _settle(tester);
      expect(find.byKey(const ValueKey('authoring-blocks')), findsOneWidget);
      expect(tester.takeException(), isNull);
      await _unmount(tester);
    });
  }
}
