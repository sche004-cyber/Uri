// O2P print panel (A1 §A4, §A6): PR-3 preview of the chosen pages, PR-10 "Connect a printer" (Settings hand-off only
// on a click, Check again), PR-11 nothing printed without the card, and "No physical printer found".
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/office/document_controller.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_workspace.dart';
import 'package:uri_ui/theme/uri_theme.dart';

final _png = base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=');

void main() {
  testWidgets('print panel: virtual printers only, preview, card, Settings hand-off on click', (tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.binding.setSurfaceSize(const Size(1440, 1000));
    final calls = <String>[];
    var settingsOpened = 0;
    final printer = {
      'id': '1234567890abcdef', 'kind': 'printer', 'name': 'Microsoft Print to PDF', 'connection': 'virtual',
      'is_default': true, 'status': 'ready', 'status_detail': '', 'port': 'PORTPROMPT:', 'new': false,
      'capabilities': {'duplex': false, 'color': true, 'max_copies': 1, 'collate': false,
                       'papers': [{'id': 9, 'name': 'A4'}, {'id': 1, 'name': 'Letter'}]},
    };
    final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', MockClient((req) async {
      final key = '${req.method} ${req.url.path}';
      calls.add(key);
      if (req.url.path.contains('/page/')) {
        return http.Response.bytes(_png, 200, headers: {'content-type': 'image/png'});
      }
      final Object out = switch (key) {
        'GET /contract' => {'contract': 'o2.1'},
        'GET /capabilities' => {
            'goals': [{'id': 'pdfs', 'title': 'PDFs'}],
            'capabilities': [
              {'id': 'print_document', 'goal': 'pdfs', 'title': 'Print', 'status': 'available', 'ready': true,
               'inputs': ['pdf']},
              {'id': 'view_pdf', 'goal': 'pdfs', 'title': 'Read a PDF', 'status': 'available', 'ready': true,
               'inputs': ['pdf']},
            ],
          },
        'GET /engines' => {'engines': []},
        'GET /recent' => {'items': []},
        'GET /workflows' => {'running': [], 'done': []},
        'POST /open/document' || 'GET /document/0123456789abcdef' => {
            'document_id': '0123456789abcdef', 'kind': 'pdf', 'name': 'notice.pdf', 'pages': 3, 'outline': [],
            'preview': {'state': 'ready'}, 'findings': [], 'renderer': 'Windows'},
        'GET /devices/printers' || 'POST /devices/refresh' => {'printers': [printer], 'physical': false},
        'GET /devices/printers/1234567890abcdef' => printer,
        'POST /print/preview' => {'pages': [2, 3], 'printable_area': {'ok': true, 'printable_mm': [0, 0, 210, 297],
                                                                      'paper_mm': [210, 297]}, 'warnings': []},
        'POST /print/propose' => {
            'job': 'c' * 16,
            'messages': jsonDecode(File('test/office/fixtures/o2p_print_card.json').readAsStringSync()),
            'preview': {'pages': [2, 3]},
          },
        'GET /print/cccccccccccccccc' => {'state': 'waiting_approval'},
        _ => {'error': 'NOT_FOUND'},
      };
      return http.Response(jsonEncode(out), (out as Map).containsKey('error') ? 404 : 200);
    }));
    final env = OfficeEnvironment(
      surfaceFactory: () => throw UnimplementedError(),
      pickWorkbookPath: () async => null,
      pickSavePath: (_) async => null,
      openExternalLink: (_) async {},
      pickDocumentPath: () async => r'C:\Users\me\notice.pdf',
      pickPdfSavePath: (_) async => r'C:\Users\me\notice (printed).pdf',
      openPrinterSettings: () async => settingsOpened++,
    );
    await tester.pumpWidget(MaterialApp(theme: ThemeData(extensions: const [UriColors.graphite]),
        home: Scaffold(body: OfficeWorkspace(environment: env, clientFactory: () => client))));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-open-document')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-print')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('office-print')), findsWidgets);
    expect(find.byKey(const ValueKey('office-no-physical')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-print-duplex')), findsNothing);       // not offered: no duplex
    expect(find.byKey(const ValueKey('office-print-copies')), findsNothing);       // max 1 copy
    expect(settingsOpened, 0);                                                     // never opened by itself
    await tester.enterText(find.byKey(const ValueKey('office-print-pages')), '2-3');
    await tester.tap(find.byKey(const ValueKey('office-print-preview')));
    await tester.pumpAndSettle();
    expect(find.text('PREVIEW: 2 PAGE(S)'), findsOneWidget);  // Eyebrow shows upper case
    expect(calls.where((x) => x == 'POST /print/propose'), isEmpty);
    await tester.tap(find.byKey(const ValueKey('office-print-propose')));
    await tester.pumpAndSettle();
    expect(find.text('Print this?'), findsOneWidget);                            // the card, in the URI pane
    expect(find.text('Print'), findsWidgets);
    await tester.scrollUntilVisible(find.byKey(const ValueKey('office-open-printer-settings')), 200,
        scrollable: find.descendant(of: find.byKey(const ValueKey('office-print')), matching: find.byType(Scrollable))
            .first);
    await tester.tap(find.byKey(const ValueKey('office-open-printer-settings')));
    await tester.pumpAndSettle();
    expect(settingsOpened, 1);
    await tester.tap(find.byKey(const ValueKey('office-printers-check-again')));
    await tester.pumpAndSettle();
    expect(calls, contains('POST /devices/refresh'));
    expect(tester.takeException(), isNull);
  });

  test('page ranges parse within the document only', () {
    expect(OfficeWorkspaceController.parsePages('all', 3), [1, 2, 3]);
    expect(OfficeWorkspaceController.parsePages('1-2, 3', 3), [1, 2, 3]);
    expect(OfficeWorkspaceController.parsePages('3,1', 3), [1, 3]);
    expect(OfficeWorkspaceController.parsePages('0-2', 3), isNull);
    expect(OfficeWorkspaceController.parsePages('2-9', 3), isNull);
    expect(OfficeWorkspaceController.parsePages('x', 3), isNull);
  });
}
