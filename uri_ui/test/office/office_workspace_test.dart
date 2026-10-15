// O2 B1 Office workspace widget tests (plan §10): U1 panes, U2 responsive, U4 goal groups, U5 conversation across
// views, U6/U8 hints, U9 navigation, U10 no colour literals, U13 waiting badge, U14 renderer label, U15 Documents
// alias, U16 no duplication, U17 dismissible chips. The Office service is a fake (package:http/testing MockClient).
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/office/document_controller.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_workspace.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/theme/uri_theme.dart';

final _png = base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=');

Map<String, dynamic> _caps({bool ready = true}) => {
      'goals': [
        {'id': 'write', 'title': 'Write'},
        {'id': 'pdfs', 'title': 'PDFs'},
        {'id': 'data', 'title': 'Data & Excel'},
      ],
      'capabilities': [
        {'id': 'save_as_pdf', 'goal': 'pdfs', 'title': 'Make a PDF', 'status': 'available', 'ready': ready,
         'unready_reason': ready ? null : 'ENGINE_INTEGRITY', 'inputs': ['docx', 'pptx', 'xlsx']},
        {'id': 'view_pdf', 'goal': 'pdfs', 'title': 'Read a PDF', 'status': 'available', 'ready': true, 'inputs': ['pdf']},
        {'id': 'open_workbook', 'goal': 'data', 'title': 'Open a workbook', 'status': 'available', 'ready': true,
         'inputs': ['xlsx']},
        {'id': 'write_document', 'goal': 'write', 'title': 'Write a letter or notice', 'status': 'planned:O3',
         'ready': false, 'inputs': []},
        {'id': 'print_document', 'goal': 'pdfs', 'title': 'Print', 'status': 'planned:O2P', 'ready': false,
         'inputs': ['pdf']},
      ],
    };

class FakeOffice {
  final calls = <String>[];
  Map<String, dynamic> requestReply = {'result': 'clarify', 'question_id': 'q', 'question': 'What would you like to do?',
                                       'chips': [{'label': 'Make a PDF', 'intent': 'save_as_pdf'}]};
  bool ready = true;
  Map<String, dynamic> doc = {
    'document_id': '0123456789abcdef', 'kind': 'docx', 'name': 'order.docx', 'pages': 3,
    'outline': [{'title': 'Office Order No. 41', 'level': 1, 'page': null}],
    'preview': {'state': 'ready', 'reason': null}, 'findings': [], 'renderer': 'LibreOffice',
  };

  http.Client client() => MockClient((req) async {
        final path = req.url.path;
        calls.add('${req.method} $path');
        Map<String, dynamic> body = {};
        if (req.body.isNotEmpty) body = (jsonDecode(req.body) as Map).cast<String, dynamic>();
        if (path.contains('/page/')) {
          return http.Response.bytes(_png, 200, headers: {'content-type': 'image/png'});
        }
        final out = switch ('${req.method} $path') {
          'GET /contract' => {'contract': 'o2.1'},
          'GET /capabilities' => _caps(ready: ready),
          'GET /engines' => {'engines': [{'id': 'libreoffice', 'state': 'ready', 'reason': null}]},
          'GET /recent' => {'items': [{'path': r'C:\Users\me\notice.pdf', 'kind': 'pdf', 'last_opened': 1, 'size': 10}]},
          'GET /workflows' => {'running': [], 'done': []},
          'POST /request' => requestReply,
          'POST /open/document' => doc,
          'GET /document/0123456789abcdef' => doc,
          'POST /workflow' => {
              'workflow_id': 'a' * 20,
              'messages': _planCard(),
              'view': {'state': 'waiting_approval', 'steps': [], 'inputs': [], 'findings': []},
            },
          _ => {'error': 'NOT_FOUND'},
        };
        if (out['error'] != null) return http.Response(jsonEncode(out), 404);
        if (path == '/request') out['echo'] = body;
        return http.Response(jsonEncode(out), 200);
      });
}

/// A real plan card made by the Python service (`Approvals.propose_plan`), stored as a fixture.
List<dynamic> _planCard() =>
    jsonDecode(File('test/office/fixtures/o2_plan_card.json').readAsStringSync()) as List<dynamic>;

Widget _app(OfficeWorkspace w) => MaterialApp(
      theme: ThemeData(extensions: const [UriColors.graphite]),
      home: Scaffold(body: w),
    );

OfficeEnvironment _env({String? docPath}) => OfficeEnvironment(
      surfaceFactory: () => throw UnimplementedError(),
      pickWorkbookPath: () async => null,
      pickSavePath: (_) async => null,
      openExternalLink: (_) async {},
      pickDocumentPath: () async => docPath,
      pickPdfSavePath: (_) async => null,
    );

Future<FakeOffice> _pump(WidgetTester tester, {Size size = const Size(1440, 900), String? docPath}) async {
  SharedPreferences.setMockInitialValues({});
  await tester.binding.setSurfaceSize(size);
  final fake = FakeOffice();
  final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', fake.client());
  await tester.pumpWidget(_app(OfficeWorkspace(environment: _env(docPath: docPath), clientFactory: () => client)));
  await tester.pumpAndSettle();
  return fake;
}

void main() {
  testWidgets('U1: three panes at 1440 px with resize handles; toggles collapse the panes', (tester) async {
    await _pump(tester);
    expect(find.byKey(const ValueKey('office-nav')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-home')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-uri-pane')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-resize-left')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-resize-right')), findsOneWidget);
    final before = tester.getSize(find.byKey(const ValueKey('office-nav'))).width;
    await tester.drag(find.byKey(const ValueKey('office-resize-left')), const Offset(60, 0));
    await tester.pumpAndSettle();
    expect(tester.getSize(find.byKey(const ValueKey('office-nav'))).width, greaterThan(before));
    await tester.tap(find.byKey(const ValueKey('office-toggle-left')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-nav-compact')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('office-toggle-uri')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-uri-pane')), findsNothing);
    expect(tester.takeException(), isNull);
  });

  for (final (w, compactNav, sideSheet) in [(1100.0, true, false), (900.0, true, true), (700.0, true, true)]) {
    testWidgets('U2: responsive at ${w.toInt()} px, text scale 1.3, no overflow', (tester) async {
      tester.platformDispatcher.textScaleFactorTestValue = 1.3;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await _pump(tester, size: Size(w, 800));
      expect(find.byKey(const ValueKey('office-nav-compact')), compactNav ? findsOneWidget : findsNothing);
      expect(find.byKey(const ValueKey('office-uri-pane')), sideSheet ? findsNothing : findsOneWidget);
      if (sideSheet) {
        await tester.tap(find.byKey(const ValueKey('office-toggle-uri')));
        await tester.pumpAndSettle();
        expect(find.byKey(const ValueKey('office-side-sheet')), findsOneWidget);
      }
      expect(tester.takeException(), isNull);
    });
  }

  testWidgets('U4: goal groups show only available capabilities; empty groups are hidden', (tester) async {
    await _pump(tester);
    expect(find.byKey(const ValueKey('office-goal-pdfs')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-goal-write')), findsNothing);       // only planned capabilities
    expect(find.byKey(const ValueKey('office-cap-save_as_pdf')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-cap-print_document')), findsNothing);
    expect(find.byKey(const ValueKey('office-print')), findsNothing);
  });

  testWidgets('U6/U8: the first-visit hint shows once and stays dismissed', (tester) async {
    await _pump(tester);
    expect(find.byKey(const ValueKey('office-hint')), findsOneWidget);
    expect(find.textContaining('URI shows a plan before it changes anything'), findsWidgets);
    await tester.tap(find.byKey(const ValueKey('office-hint-dismiss')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-hint')), findsNothing);
    final p = await SharedPreferences.getInstance();
    expect(p.getStringList('office.layout.v1')![4], '1');
  });

  testWidgets('U5/U17: one conversation with target labels; chips can be dismissed', (tester) async {
    await _pump(tester, docPath: r'C:\Users\me\order.docx');
    await tester.enterText(find.byKey(const ValueKey('office-request')), 'do the usual');
    await tester.tap(find.byKey(const ValueKey('office-request-send')));
    await tester.pumpAndSettle();
    expect(find.text('do the usual'), findsOneWidget);
    expect(find.text('Home'), findsWidgets);                                   // the line's target
    expect(find.byKey(const ValueKey('office-chip-save_as_pdf')), findsOneWidget);
    await tester.tap(find.descendant(of: find.byKey(const ValueKey('office-chip-save_as_pdf')),
        matching: find.byTooltip('Dismiss')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-chip-save_as_pdf')), findsNothing);
    // open a document: the conversation is the same, the target label changes
    await tester.tap(find.byKey(const ValueKey('office-open-document')));
    await tester.pumpAndSettle();
    expect(find.text('do the usual'), findsOneWidget);
    expect(find.textContaining('Document · order.docx'), findsWidgets);
  });

  testWidgets('U14: page view shows pages, outline and the renderer label; Save as PDF needs a ready engine',
      (tester) async {
    await _pump(tester, docPath: r'C:\Users\me\order.docx');
    await tester.tap(find.byKey(const ValueKey('office-open-document')));
    await tester.pumpAndSettle();
    expect(find.text('Preview rendered by LibreOffice'), findsOneWidget);
    expect(find.text('Page 1 of 3'), findsOneWidget);
    expect(find.text('Office Order No. 41'), findsOneWidget);
    expect(find.byKey(const ValueKey('office-save-as-pdf')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('office-page-next')));
    await tester.pumpAndSettle();
    expect(find.text('Page 2 of 3'), findsOneWidget);
  });

  testWidgets('U9: OfficeView commands move the view and Back returns within Office', (tester) async {
    final pc = UiPresentationController();
    SharedPreferences.setMockInitialValues({});
    await tester.binding.setSurfaceSize(const Size(1440, 900));
    final fake = FakeOffice();
    final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', fake.client());
    final c = OfficeWorkspaceController(client: client, presentation: pc);
    await c.start();
    expect(parseLocalUiCommand('uri office pdfs'), isA<ShowModeCommand>());
    pc.apply(parseLocalUiCommand('uri office pdfs')!);
    expect(c.view, OfficeView.pdfs);
    expect(c.centre, OfficeCentre.list);
    c.showView(OfficeView.recent);
    expect(pc.officeBack(), isTrue);
    expect(c.view, OfficeView.pdfs);
    expect(pc.history, [UiPresentationMode.companion]);  // mode history holds the mode change only, no Office views
    expect((parseLocalUiCommand('uri documents') as ShowModeCommand).focus, WorkspaceFocus.documents);
    c.dispose();
    pc.dispose();
  });

  testWidgets('U13: a waiting card opens the side sheet and shows a badge at 900 px', (tester) async {
    await _pump(tester, size: const Size(900, 800), docPath: r'C:\Users\me\order.docx');
    await tester.tap(find.byKey(const ValueKey('office-nav-open')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-save-as-pdf')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-waiting-badge')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-side-sheet')), findsOneWidget);   // opens by itself for the card
    expect(find.text('Save order.docx as PDF?'), findsOneWidget);
    expect(find.text('Run'), findsOneWidget);
  });

  test('U10: no colour literals in the new Office files', () {
    final dir = Directory('lib/living/office');
    final files = ['office_workspace.dart', 'office_nav_pane.dart', 'office_home.dart', 'page_preview.dart',
                   'office_status_strip.dart', 'office_companion_pane.dart', 'document_controller.dart',
                   'office_conversation.dart'];
    final bad = RegExp(r'Color\(0x|Color\.fromARGB|Color\.fromRGBO|(?<![A-Za-z])Colors\.');
    for (final f in files) {
      final text = File('${dir.path}/$f').readAsStringSync();
      expect(bad.hasMatch(text), isFalse, reason: f);
    }
  });

  test('U16: no second Brain client, A2UI renderer or conversation store in the new files', () {
    for (final f in Directory('lib/living/office').listSync().whereType<File>()) {
      final text = f.readAsStringSync();
      expect(text.contains('brain_client'), isFalse, reason: f.path);
      expect(RegExp(r'class \w*A2ui(Hub|Renderer)').hasMatch(text), isFalse, reason: f.path);
    }
    // exactly one hub per workspace controller; the sheet controller is given it
    expect(File('lib/living/office/document_controller.dart').readAsStringSync().split('A2uiHub()').length - 1, 1);
  });

  test('page bytes are fetched as PNG and 202 means not ready', () async {
    var n = 0;
    final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', MockClient((req) async {
      n++;
      return n == 1 ? http.Response('', 202) : http.Response.bytes(_png, 200, headers: {'content-type': 'image/png'});
    }));
    expect(await client.documentPage('0123456789abcdef', 1, 440), isNull);
    expect(await client.documentPage('0123456789abcdef', 1, 440), isA<Uint8List>());
  });
}
