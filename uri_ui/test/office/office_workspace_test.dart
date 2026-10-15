// O2 B1 Office workspace widget tests (plan §10): U1 panes, U2 responsive, U4 goal groups, U5 conversation across
// views, U6/U8 hints, U9 navigation, U10 no colour literals, U13 waiting badge, U14 renderer label, U15 Documents
// alias, U16 no duplication, U17 dismissible chips. The Office service is a fake (package:http/testing MockClient).
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/office/document_controller.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_nav_pane.dart';
import 'package:uri_ui/living/office/office_workspace.dart';
import 'package:uri_ui/living/office/page_preview.dart';
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
  Map<String, dynamic>? openError;           // POST /open/document answers this error (400) when set
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
          'GET /status' => {'ok': true},
          'GET /contract' => {'contract': 'o2.1'},
          'GET /capabilities' => _caps(ready: ready),
          'GET /engines' => {'engines': [{'id': 'libreoffice', 'state': 'ready', 'reason': null}]},
          'GET /recent' => {'items': [{'path': r'C:\Users\me\notice.pdf', 'kind': 'pdf', 'last_opened': 1, 'size': 10}]},
          'GET /workflows' => {'running': [], 'done': []},
          'POST /request' => requestReply,
          'POST /open/document' => doc,
          'GET /document/0123456789abcdef' => doc,
          'POST /document/0123456789abcdef/retry' => (doc = {...doc, 'preview': {'state': 'ready', 'reason': null}}),
          'POST /engines/verify' => {'ok': true},
          'POST /workflow' => {
              'workflow_id': 'a' * 20,
              'messages': _planCard(),
              'view': {'state': 'waiting_approval', 'steps': [], 'inputs': [], 'findings': []},
            },
          _ => {'error': 'NOT_FOUND'},
        };
        if (path == '/open/document' && openError != null) return http.Response(jsonEncode(openError), 400);
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
    final pc = UiPresentationController(commandCooldown: Duration.zero);
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
    // review round 3, m4: a command moves the centre from a document view too
    await c.openDocumentPath(r'C:\Users\me\order.docx');
    expect(c.centre, OfficeCentre.document);
    expect(pc.apply(parseLocalUiCommand('uri office presentations')!), isTrue);
    expect(c.view, OfficeView.presentations);
    expect(c.centre, OfficeCentre.list);
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

  testWidgets('U1-persist: pane widths and collapsed panes survive a restart (new controller, same settings)',
      (tester) async {
    await _pump(tester);
    double navWidth() => tester.getSize(find.byType(OfficeNavPane)).width;
    expect(navWidth(), 260);
    await tester.drag(find.byKey(const ValueKey('office-resize-left')), const Offset(60, 0));
    await tester.pumpAndSettle();
    expect(navWidth(), 320);
    expect(find.byKey(const ValueKey('office-region-conversation')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('office-toggle-uri')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-region-conversation')), findsNothing);
    // "restart": the workspace and its controller are gone; a new one reads the same settings store
    await tester.pumpWidget(const SizedBox());
    await tester.pumpAndSettle();
    final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client());
    await tester.pumpWidget(_app(OfficeWorkspace(environment: _env(), clientFactory: () => client)));
    await tester.pumpAndSettle();
    expect(navWidth(), 320);
    expect(find.byKey(const ValueKey('office-region-conversation')), findsNothing);
  });

  testWidgets('U11: keyboard - Ctrl+Shift+B and Ctrl+Shift+J toggle the panes, Ctrl+K focuses the request box',
      (tester) async {
    await _pump(tester);
    Future<void> chord(LogicalKeyboardKey k, {bool shift = true}) async {
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      if (shift) await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
      await tester.sendKeyEvent(k);
      if (shift) await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
    }
    // focus somewhere inside the workspace first, as a user's click would
    await tester.tap(find.byKey(const ValueKey('office-view-title')));
    await tester.pumpAndSettle();
    final before = tester.getSize(find.byType(OfficeNavPane)).width;
    await chord(LogicalKeyboardKey.keyB);
    expect(tester.getSize(find.byType(OfficeNavPane)).width, lessThan(before));
    await chord(LogicalKeyboardKey.keyB);
    expect(tester.getSize(find.byType(OfficeNavPane)).width, before);
    await chord(LogicalKeyboardKey.keyJ);
    expect(find.byKey(const ValueKey('office-region-conversation')), findsNothing);
    await chord(LogicalKeyboardKey.keyJ);
    expect(find.byKey(const ValueKey('office-region-conversation')), findsOneWidget);
    await chord(LogicalKeyboardKey.keyK, shift: false);
    final focused = FocusManager.instance.primaryFocus?.context;
    expect(focused, isNotNull);
    var insideRequestBox = false;
    focused!.visitAncestorElements((e) {
      if (e.widget.key == const ValueKey('office-request')) insideRequestBox = true;
      return !insideRequestBox;
    });
    expect(insideRequestBox, isTrue, reason: 'Ctrl+K should put the cursor in the request box');
  });

  group('R6 task view (real-app run r2)', () {
    OfficeWorkspaceController ctl() => OfficeWorkspaceController(
        client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client()));
    final findings = [
      for (var i = 0; i < 6; i++) {'id': 'f$i', 'severity': 'warning', 'message': 'Warning $i.', 'check': 'x'}
    ];

    testWidgets('the task actions come before the findings and page images', (tester) async {
      await tester.binding.setSurfaceSize(const Size(900, 600));
      final c = ctl()
        ..activeWorkflow = 'a' * 20
        ..workflowView = {'state': 'ready_to_save', 'steps': [], 'findings': findings, 'warnings_accepted': true,
          'outputs': [{'name': 'report.pdf', 'pages': 20}]};
      await tester.pumpWidget(MaterialApp(theme: ThemeData(extensions: const [UriColors.graphite]),
          home: Scaffold(body: OfficeWorkflowView(controller: c))));
      await tester.pump();
      final save = find.byKey(const ValueKey('office-save-output'));
      expect(save, findsOneWidget, reason: 'Save is built without scrolling');
      expect(tester.getTopLeft(save).dy, lessThan(tester.getTopLeft(find.text('Warning 0.')).dy));
      expect(tester.getBottomLeft(save).dy, lessThan(600));
    });

    testWidgets('a saved task names the file and offers to open it', (tester) async {
      await tester.binding.setSurfaceSize(const Size(900, 600));
      final c = OfficeWorkspaceController(
          client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client()),
          environment: _env(docPath: r'C:\Users\me\Saved\report.pdf'))
        ..activeWorkflow = 'a' * 20
        ..workflowView = {'state': 'saved', 'steps': [], 'findings': [], 'saved': {'name': 'report.pdf'},
          'outputs': [{'name': 'report.pdf', 'pages': 2}]};
      await tester.pumpWidget(MaterialApp(theme: ThemeData(extensions: const [UriColors.graphite]),
          home: Scaffold(body: OfficeWorkflowView(controller: c))));
      await tester.pump();
      expect(find.textContaining('Saved as report.pdf'), findsOneWidget);
      expect(find.byKey(const ValueKey('office-open-saved')), findsOneWidget);
      expect(find.text('Open it…'), findsOneWidget, reason: 'opening goes through the picker');
    });
  });

  group('CX-1 cancel (readiness run r2)', () {
    testWidgets('a cancelled task says so and draws no output pages', (tester) async {
      await tester.binding.setSurfaceSize(const Size(900, 600));
      final c = OfficeWorkspaceController(
          client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client()))
        ..activeWorkflow = 'a' * 20
        ..workflowView = {'state': 'cancelled', 'steps': [], 'findings': [],
          'outputs': [{'name': 'deck.pdf', 'pages': 11}]};
      await tester.pumpWidget(MaterialApp(theme: ThemeData(extensions: const [UriColors.graphite]),
          home: Scaffold(body: OfficeWorkflowView(controller: c))));
      await tester.pump();
      expect(find.byKey(const ValueKey('office-workflow-cancelled')), findsOneWidget);
      expect(find.textContaining('Nothing was saved'), findsOneWidget);
      expect(find.byType(CircularProgressIndicator), findsNothing, reason: 'no page that can never load');
      expect(find.byKey(const ValueKey('office-cancel')), findsNothing);
    });

    test('an output page that is not drawn yet is fetched again, not cached as empty', () async {
      var n = 0;
      final mock = MockClient((req) async {
        if (req.url.path.contains('/page/')) {
          n++;
          return n == 1 ? http.Response('', 202) : http.Response.bytes(_png, 200, headers: {'content-type': 'image/png'});
        }
        return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
      });
      final c = OfficeWorkspaceController(client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', mock));
      final first = await c.outputPage('a' * 20, 1, 160);
      expect(first == null || first.isEmpty, isTrue);
      final second = await c.outputPage('a' * 20, 1, 160);
      expect(second, isNotNull);
      expect(second!.isNotEmpty, isTrue);
    });

    test('cancelling says so in the Office conversation', () async {
      final mock = MockClient((req) async => http.Response(
          jsonEncode({'state': 'cancelled', 'steps': [], 'findings': []}), 200));
      final c = OfficeWorkspaceController(client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', mock))
        ..activeWorkflow = 'a' * 20;
      await c.cancelWorkflow();
      expect(c.workflowView?['state'], 'cancelled');
      expect(c.conversation.lines.last.text, contains('Cancelled. Nothing was saved'));
    });

    test('Codex R4-3: a task still stopping is not announced as cancelled', () async {
      final mock = MockClient((req) async => http.Response(
          jsonEncode({'state': 'running', 'steps': [], 'findings': []}), 200));
      final c = OfficeWorkspaceController(client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', mock))
        ..activeWorkflow = 'a' * 20;
      await c.cancelWorkflow();
      expect(c.conversation.lines.last.text, 'Stopping the task…');
      expect(c.conversation.lines.any((l) => l.text.startsWith('Cancelled')), isFalse);
    });

    testWidgets('Codex R4-1: a saved task requests no output pages (its work files are gone)', (tester) async {
      await tester.binding.setSurfaceSize(const Size(900, 600));
      var pages = 0;
      final mock = MockClient((req) async {
        if (req.url.path.contains('/page/')) pages++;
        return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
      });
      final c = OfficeWorkspaceController(client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', mock))
        ..activeWorkflow = 'a' * 20
        ..workflowView = {'state': 'saved', 'steps': [], 'findings': [], 'saved': {'name': 'report.pdf'},
          'outputs': [{'name': 'report.pdf', 'pages': 12}]};
      await tester.pumpWidget(MaterialApp(theme: ThemeData(extensions: const [UriColors.graphite]),
          home: Scaffold(body: OfficeWorkflowView(controller: c))));
      await tester.pump(const Duration(seconds: 5));
      expect(pages, 0);
      expect(find.textContaining('Saved as report.pdf'), findsOneWidget);
    });

    testWidgets('Codex R4-2: a page that takes long to draw still appears (no 8-second cut-off)', (tester) async {
      await tester.binding.setSurfaceSize(const Size(900, 600));
      var n = 0;
      final mock = MockClient((req) async {
        if (req.url.path.contains('/page/')) {
          n++;
          return n <= 25 ? http.Response('', 202) : http.Response.bytes(_png, 200, headers: {'content-type': 'image/png'});
        }
        return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
      });
      final c = OfficeWorkspaceController(client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', mock))
        ..activeWorkflow = 'a' * 20
        ..workflowView = {'state': 'ready_to_save', 'steps': [], 'findings': [], 'outputs': [{'name': 'r.pdf', 'pages': 1}]};
      await tester.pumpWidget(MaterialApp(theme: ThemeData(extensions: const [UriColors.graphite]),
          home: Scaffold(body: OfficeWorkflowView(controller: c))));
      for (var i = 0; i < 120; i++) {
        await tester.runAsync(() => Future<void>.delayed(Duration.zero));
        await tester.pump(const Duration(seconds: 1));
      }
      // The fake PNG cannot be decoded by the test engine; the widget tree is what matters here.
      final e = tester.takeException();
      expect(e == null || '$e'.contains('Codec failed'), isTrue);
      expect(n, greaterThan(25));
      expect(find.byType(Image), findsOneWidget);
      expect(find.textContaining('not ready yet'), findsNothing);
    });
  });

  group('R5 real-app repairs (2026-10-15)', () {
    Future<void> openDoc(WidgetTester tester) async {
      await tester.tap(find.byKey(const ValueKey('office-home-open')));
      await tester.pumpAndSettle();
    }

    testWidgets('R5-6: Ctrl+Shift+B works while the keyboard focus is outside the workspace', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.binding.setSurfaceSize(const Size(1440, 900));
      final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client());
      await tester.pumpWidget(MaterialApp(
        theme: ThemeData(extensions: const [UriColors.graphite]),
        home: Scaffold(body: Column(children: [
          const TextField(key: ValueKey('outside-field')),
          Expanded(child: OfficeWorkspace(environment: _env(), clientFactory: () => client)),
        ])),
      ));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('outside-field')));
      await tester.pumpAndSettle();
      final before = tester.getSize(find.byType(OfficeNavPane)).width;
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
      await tester.sendKeyEvent(LogicalKeyboardKey.keyB);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
      expect(tester.getSize(find.byType(OfficeNavPane)).width, lessThan(before));
    });

    testWidgets('R5-4: in the icon strip (1100 px) the open document can be reached again', (tester) async {
      final fake = await _pump(tester, size: const Size(1100, 800), docPath: r'C:\Users\me\order.docx');
      await tester.tap(find.byKey(const ValueKey('office-nav-open')));
      await tester.pumpAndSettle();
      expect(fake.calls, contains('POST /open/document'));
      await tester.tap(find.byKey(const ValueKey('office-nav-home')));
      await tester.pumpAndSettle();
      final docIcon = find.byKey(const ValueKey('office-open-doc-0123456789abcdef'));
      expect(docIcon, findsOneWidget);
      expect(find.byTooltip('order.docx'), findsOneWidget);
      await tester.tap(docIcon);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('office-page-label')), findsOneWidget);
    });

    testWidgets('R5-2: an unavailable preview offers a way back (engine check, then the preview again)', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.binding.setSurfaceSize(const Size(1440, 900));
      final fake = FakeOffice();
      fake.doc = {...fake.doc, 'preview': {'state': 'unavailable', 'reason': 'ENGINE_UNAVAILABLE'}};
      final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', fake.client());
      await tester.pumpWidget(_app(OfficeWorkspace(environment: _env(docPath: r'C:\Users\me\order.docx'),
          clientFactory: () => client)));
      await tester.pumpAndSettle();
      await openDoc(tester);
      expect(find.byKey(const ValueKey('office-preview-unavailable')), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('office-preview-retry')));
      await tester.pumpAndSettle();
      expect(fake.calls, contains('POST /document/0123456789abcdef/retry'));
      expect(find.byKey(const ValueKey('office-preview-unavailable')), findsNothing);
      expect(find.byKey(const ValueKey('office-page-label')), findsOneWidget);
    });

    testWidgets('R5-5: a message about an earlier action is cleared when the owner moves to another view',
        (tester) async {
      final fake = await _pump(tester, docPath: r'C:\Users\me\bad.docx');
      fake.openError = {'error': 'ARCHIVE_REFUSED'};
      await openDoc(tester);
      expect(find.text('This file looks damaged or unsafe and was not opened.'), findsWidgets);
      await tester.tap(find.byKey(const ValueKey('office-nav-recent')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('office-status-error')), findsNothing);
    });
  });

  group('R5-1: the app starts the Office service on first use (real-app run 2026-10-15)', () {
    OfficeEnvironment env(Future<String?> Function() start) => OfficeEnvironment(
          surfaceFactory: () => throw UnimplementedError(),
          pickWorkbookPath: () async => null,
          pickSavePath: (_) async => null,
          openExternalLink: (_) async {},
          pickDocumentPath: () async => null,
          startService: start,
        );

    testWidgets('no service: starts it, shows progress, then the workspace', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.binding.setSurfaceSize(const Size(1440, 900));
      final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client());
      var started = 0;
      final gate = Completer<String?>();
      await tester.pumpWidget(_app(OfficeWorkspace(
          environment: env(() {
            started++;
            return gate.future;
          }),
          clientFactory: () => gate.isCompleted ? client : null)));
      await tester.pump();
      expect(started, 1);
      expect(find.text('Starting URI Office…'), findsOneWidget);
      gate.complete(null);
      await tester.pump(const Duration(milliseconds: 600));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('office-start-error')), findsNothing);
      expect(find.byKey(const ValueKey('office-home')), findsOneWidget);
    });

    testWidgets('a start problem is shown in words with Try again, which tries again', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.binding.setSurfaceSize(const Size(1440, 900));
      var started = 0;
      await tester.pumpWidget(_app(OfficeWorkspace(
          environment: env(() async {
            started++;
            return 'URI Office is not installed with this copy of URI.';
          }),
          clientFactory: () => null)));
      await tester.pumpAndSettle();
      expect(find.text('URI Office is not installed with this copy of URI.'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('office-start-retry')));
      await tester.pumpAndSettle();
      expect(started, 2);
    });

    testWidgets('another program that answers 200 without the Office contract is not taken for URI Office',
        (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.binding.setSurfaceSize(const Size(1440, 900));
      final foreign = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't',
          MockClient((_) async => http.Response('<html>hello</html>', 200)));
      final live = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client());
      var started = 0;
      await tester.pumpWidget(_app(OfficeWorkspace(
          environment: env(() async {
            started++;
            return null;
          }),
          clientFactory: () => started > 0 ? live : foreign)));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 600));
      await tester.pumpAndSettle();
      expect(started, 1);
    });

    testWidgets('another program on the recorded port (token refused) is not taken for URI Office', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.binding.setSurfaceSize(const Size(1440, 900));
      final foreign = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't',
          MockClient((_) async => http.Response('{"error":"UNAUTHORIZED"}', 401)));
      final live = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client());
      var started = 0;
      await tester.pumpWidget(_app(OfficeWorkspace(
          environment: env(() async {
            started++;
            return null;
          }),
          clientFactory: () => started > 0 ? live : foreign)));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 600));
      await tester.pumpAndSettle();
      expect(started, 1);
      expect(find.byKey(const ValueKey('office-home')), findsOneWidget);
    });

    testWidgets('a service.json left by an ended service is not trusted: a new service is started', (tester) async {
      SharedPreferences.setMockInitialValues({});
      await tester.binding.setSurfaceSize(const Size(1440, 900));
      final dead = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't',
          MockClient((_) async => throw const SocketException('refused')));
      final live = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', FakeOffice().client());
      var started = 0;
      await tester.pumpWidget(_app(OfficeWorkspace(
          environment: env(() async {
            started++;
            return null;
          }),
          clientFactory: () => started > 0 ? live : dead)));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 600));
      await tester.pumpAndSettle();
      expect(started, 1);
      expect(find.byKey(const ValueKey('office-home')), findsOneWidget);
    });
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
