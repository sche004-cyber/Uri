// URI Office panel: the page-message contract, the recorded page hash, and the panel against a fake sheet view
// and a fake Office service. No platform plugin is loaded (the WebView2 surface is injected in the app).
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_controller.dart';
import 'package:uri_ui/living/office/office_page_hash.dart';
import 'package:uri_ui/living/office/office_panel.dart';
import 'package:uri_ui/theme/uri_theme.dart';

class FakeSurface implements OfficeSurface {
  final posted = <Map<String, dynamic>>[];
  final StreamController<Map<String, dynamic>> ctl = StreamController.broadcast();
  bool started = false;
  bool failStart = false;

  @override
  Stream<Map<String, dynamic>> get messages => ctl.stream;
  @override
  Future<void> start() async {
    if (failStart) throw OfficeSurfaceError('PAGE_HASH_MISMATCH');
    started = true;
  }

  @override
  Future<void> post(Map<String, dynamic> m) async => posted.add(m);
  @override
  Future<Map<String, dynamic>> securityReport() async => {};
  @override
  Widget build(BuildContext context) => const SizedBox(key: ValueKey('fake-sheet'));
  @override
  Future<void> dispose() async => ctl.close();
}

const _workbook = {
  'sheets': [
    {'name': 'Sales', 'index': 0, 'max_row': 3, 'max_col': 2, 'truncated': false, 'merges': [], 'col_widths': {},
      'row_heights': {}, 'locked': [], 'cells': {'A1': {'v': 'Region'}, 'B2': {'v': 10}}},
  ],
  'styles': {},
  'kept_not_shown': {'charts': 0, 'images': 0, 'pivot_tables': 0},
};

Map<String, dynamic> _draft(List<Map<String, dynamic>> changes) =>
    {'workbook_id': 'w1', 'engine': 'local', 'version': 2, 'can_undo': true, 'can_redo': false, 'changes': changes};

final _uriChange = {
  'cid': 'c1', 'by': 'uri', 'kind': 'cell', 'state': 'proposed', 'sheet': 'Sales', 'cell': 'B2',
  'before': {'v': 10}, 'after': {'v': 12}, 'op': null, 'change_sha256': 'a' * 64,
};

Widget _app(Widget child) => MaterialApp(
      theme: ThemeData(extensions: const [UriColors.graphite]),
      home: Scaffold(body: SizedBox(width: 1400, height: 900, child: child)),
    );

void main() {
  group('page messages', () {
    test('accepted shapes', () {
      expect(parsePageMessage({'type': 'ready'}), {'type': 'ready'});
      expect(parsePageMessage({'type': 'edit', 'sheet': 'Sales', 'cell': 'B2', 'value': 3}),
          {'type': 'edit', 'sheet': 'Sales', 'cell': 'B2', 'value': 3});
      expect(parsePageMessage({'type': 'edit', 'sheet': 'Sales', 'cell': 'B2', 'formula': '=A1*2'})!['formula'], '=A1*2');
      expect(parsePageMessage({'type': 'edit', 'sheet': 'Sales', 'cell': 'B2', 'value': null})!['value'], isNull);
    });

    test('everything else is dropped', () {
      for (final bad in <Object?>[
        null, 'ready', 42, {'type': 'evil'}, {'type': 'ready', 'x': 1},
        {'type': 'edit', 'sheet': 'Sales', 'cell': '1A', 'value': 1},
        {'type': 'edit', 'sheet': '', 'cell': 'A1', 'value': 1},
        {'type': 'edit', 'sheet': 'x' * 32, 'cell': 'A1', 'value': 1},
        {'type': 'edit', 'sheet': 'S', 'cell': 'A1', 'value': {'nested': 1}},
        {'type': 'edit', 'sheet': 'S', 'cell': 'A1', 'value': 1, 'formula': '=1'},
        {'type': 'edit', 'sheet': 'S', 'cell': 'A1', 'formula': 'SUM(1)'},
        {'type': 'edit', 'sheet': 'S', 'cell': 'A1', 'value': 1, 'path': 'C:/x'},
        {'type': 'edit', 'sheet': 'S', 'cell': 'A1'},
        {'type': 'save'}, {'type': 'open', 'path': 'C:/x.xlsx'},
      ]) {
        expect(parsePageMessage(bad), isNull, reason: '$bad');
      }
    });
  });

  group('page hash', () {
    test('Dart constant equals the committed BUNDLE_SHA256', () {
      final recorded = File('office_web/BUNDLE_SHA256').readAsStringSync().trim();
      expect(kOfficeBundleSha256, recorded);
    });

    test('Dart bundle hash uses the same algorithm as uri_office.page_build', () async {
      final d = await Directory.systemTemp.createTemp('office-hash');
      await File('${d.path}/a.txt').writeAsString('alpha');
      await Directory('${d.path}/sub').create();
      await File('${d.path}/sub/b.js').writeAsString('beta');
      // Reference value computed with the Python implementation for the same two files.
      expect(await officeBundleHash(d), '59e68f96ef6b83ba09543361bd1f8cd0248bfe187611632f24288bbf6aaafc2c');
      await d.delete(recursive: true);
    });
  });

  group('panel', () {
    testWidgets('no WebView2 environment: says so and starts nothing', (tester) async {
      await tester.pumpWidget(_app(OfficeRegion(environment: null, clientFactory: () => null)));
      await tester.pump();
      expect(find.byKey(const ValueKey('office-start-error')), findsOneWidget);
      expect(find.textContaining('WebView2'), findsOneWidget);
    });

    testWidgets('service not running: says so', (tester) async {
      final env = OfficeEnvironment(
        surfaceFactory: FakeSurface.new,
        pickWorkbookPath: () async => null,
        pickSavePath: (_) async => null,
        openExternalLink: (_) async {},
      );
      await tester.pumpWidget(_app(OfficeRegion(environment: env, clientFactory: () => null)));
      await tester.pump();
      expect(find.textContaining('service is not running'), findsOneWidget);
    });

    testWidgets('a page that fails verification is not shown', (tester) async {
      final surface = FakeSurface()..failStart = true;
      final env = OfficeEnvironment(
        surfaceFactory: () => surface,
        pickWorkbookPath: () async => null,
        pickSavePath: (_) async => null,
        openExternalLink: (_) async {},
      );
      final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't',
          MockClient((_) async => http.Response('{}', 200)));
      await tester.pumpWidget(_app(OfficeRegion(environment: env, clientFactory: () => client)));
      await tester.pumpAndSettle();
      expect(find.textContaining('could not start safely'), findsOneWidget);
      expect(find.byKey(const ValueKey('fake-sheet')), findsNothing);
    });

    testWidgets('open, show URI change marked, edits go to the service, accept is hash-bound', (tester) async {
      final surface = FakeSurface();
      final calls = <String, Map<String, dynamic>>{};
      final mock = MockClient((req) async {
        final body = req.body.isEmpty ? <String, dynamic>{} : jsonDecode(req.body) as Map<String, dynamic>;
        calls[req.url.path] = body;
        expect(req.headers['Authorization'], 'Bearer tok');
        expect(req.url.host, '127.0.0.1');
        switch (req.url.path) {
          case '/open/local':
            return http.Response(jsonEncode({'workbook_id': 'w1', 'engine': 'local', 'label': 'book.xlsx',
              'workbook': _workbook, 'draft': _draft([_uriChange]), 'history_on': false}), 200);
          case '/workbook/w1/edit':
            return http.Response(jsonEncode({'draft': _draft([_uriChange])}), 200);
          case '/workbook/w1/decide':
            return http.Response(jsonEncode({'draft': _draft([{..._uriChange, 'state': 'accepted'}])}), 200);
        }
        return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
      });
      final env = OfficeEnvironment(
        surfaceFactory: () => surface,
        pickWorkbookPath: () async => r'C:\Users\me\book.xlsx',
        pickSavePath: (_) async => null,
        openExternalLink: (_) async {},
      );
      final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:18530'), 'tok', mock);
      await tester.pumpWidget(_app(OfficeRegion(environment: env, clientFactory: () => client)));
      await tester.pumpAndSettle();
      expect(surface.started, isTrue);

      surface.ctl.add({'type': 'ready'});
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('office-open-file')));
      await tester.pumpAndSettle();
      expect(calls['/open/local'], {'path': r'C:\Users\me\book.xlsx'});

      // The page got the workbook with URI's change marked as proposed.
      final load = surface.posted.lastWhere((m) => m['type'] == 'load');
      expect(load['marks'], [
        {'sheet': 'Sales', 'cell': 'B2', 'state': 'proposed', 'after': {'v': 12}},
      ]);
      // The side panel marks it as URI's.
      expect(find.byKey(const ValueKey('office-change-c1')), findsOneWidget);
      expect(find.byKey(const ValueKey('office-uri-mark')), findsOneWidget);

      // An owner edit from the page goes to the service, not to the file.
      surface.ctl.add({'type': 'edit', 'sheet': 'Sales', 'cell': 'A1', 'value': 'Area'});
      await tester.pumpAndSettle();
      expect(calls['/workbook/w1/edit'], {'sheet': 'Sales', 'cell': 'A1', 'value': 'Area'});

      // Accept carries the hash of the exact change shown.
      await tester.tap(find.text('Accept'));
      await tester.pumpAndSettle();
      expect(calls['/workbook/w1/decide'], {'change_id': 'c1', 'decision': 'accept', 'change_sha256': 'a' * 64});
      expect(find.byKey(const ValueKey('office-change-c1')), findsNothing);
    });
  });

  // R1-10: page edits were dropped while the controller was busy (the first cell of a paste made it busy, so the other
  // cells were discarded; typing during a Brain turn was discarded too).
  group('page edits are queued, never dropped', () {
    Future<void> until(bool Function() done) async {
      for (var i = 0; i < 500 && !done(); i++) {
        await Future<void>.delayed(const Duration(milliseconds: 2));
      }
    }

    late List<Map<String, dynamic>> edits;
    late Completer<void> brainGate;

    OfficeController make(FakeSurface surface) {
      edits = [];
      brainGate = Completer<void>()..complete();
      final mock = MockClient((req) async {
        final body = req.body.isEmpty ? <String, dynamic>{} : jsonDecode(req.body) as Map<String, dynamic>;
        switch (req.url.path) {
          case '/open/local':
            return http.Response(jsonEncode({'workbook_id': 'w1', 'engine': 'local', 'label': 'book.xlsx',
              'workbook': _workbook, 'draft': _draft([]), 'history_on': false}), 200);
          case '/workbook/w1/edit':
            await Future<void>.delayed(const Duration(milliseconds: 5));   // a real round trip
            edits.add(body);
            return http.Response(jsonEncode({'draft': _draft([])}), 200);
          case '/workbook/w1/instruct':
            await brainGate.future;
            return http.Response(jsonEncode({'message': 'ok', 'proposed': [], 'refused': [], 'metrics': {},
              'draft': _draft([])}), 200);
        }
        return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
      });
      return OfficeController(
          client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:18530'), 'tok', mock), surface: surface);
    }

    test('a multi-cell paste sends every cell, in order', () async {
      final surface = FakeSurface();
      final c = make(surface);
      await c.openLocal(r'C:\Users\me\book.xlsx');
      surface.ctl.add({'type': 'ready'});
      for (final cell in ['A2', 'A3', 'A4', 'A5']) {
        surface.ctl.add({'type': 'edit', 'sheet': 'Sales', 'cell': cell, 'value': cell.toLowerCase()});
      }
      await until(() => edits.length == 4 && !c.busy);
      expect([for (final e in edits) e['cell']], ['A2', 'A3', 'A4', 'A5']);
      expect(c.notice, isNull);
      // The page is reloaded from the service once, after the last cell was accepted.
      await until(() => surface.posted.where((m) => m['type'] == 'load').length >= 2);
      expect(surface.posted.last['type'], 'load');
    });

    test('XF-1: formatting the page did not apply is explained, and nothing is sent', () async {
      final surface = FakeSurface();
      final c = make(surface);
      await c.openLocal(r'C:\Users\me\book.xlsx');
      surface.ctl.add({'type': 'ready'});
      surface.ctl.add({'type': 'error', 'code': 'FORMAT_CHANGE_NOT_SAVED'});
      await until(() => c.notice != null);
      expect(c.notice, contains('Formatting'));
      expect(c.notice, contains('not applied'));
      expect(c.notice, contains('column widths'));
      expect(edits, isEmpty);
    });

    test('typing during a Brain turn is sent, not discarded', () async {
      final surface = FakeSurface();
      final c = make(surface);
      await c.openLocal(r'C:\Users\me\book.xlsx');
      surface.ctl.add({'type': 'ready'});
      brainGate = Completer<void>();
      final turn = c.instruct('fill the totals');
      await until(() => c.busy);
      expect(c.busy, isTrue);
      surface.ctl.add({'type': 'edit', 'sheet': 'Sales', 'cell': 'B2', 'value': 11});
      surface.ctl.add({'type': 'edit', 'sheet': 'Sales', 'cell': 'B3', 'formula': '=B2*2'});
      await until(() => edits.length == 2);
      brainGate.complete();
      await turn;
      expect(edits, [
        {'sheet': 'Sales', 'cell': 'B2', 'value': 11},
        {'sheet': 'Sales', 'cell': 'B3', 'formula': '=B2*2'},
      ]);
    });
  });

  // R5-02: after an approved save the grid was reloaded from the workbook as opened, so saved edits vanished from it.
  test('after an approved save the grid reloads the workbook the service returns', () async {
    final surface = FakeSurface();
    final saved = {
      ..._workbook,
      'sheets': [
        {...(_workbook['sheets'] as List).first as Map<String, dynamic>,
          'cells': {'A1': {'v': 'Region'}, 'B2': {'v': 99}}},
      ],
    };
    final mock = MockClient((req) async {
      switch (req.url.path) {
        case '/open/local':
          return http.Response(jsonEncode({'workbook_id': 'w1', 'engine': 'local', 'label': 'book.xlsx',
            'workbook': _workbook, 'draft': _draft([]), 'history_on': false}), 200);
        case '/a2ui/action':
          return http.Response(jsonEncode({'status': 'applied', 'workbook_id': 'w1', 'saved_to': 'book.xlsx',
            'changed_parts': [], 'draft': _draft([]), 'workbook': saved}), 200);
      }
      return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
    });
    final c = OfficeController(
        client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:18530'), 'tok', mock), surface: surface);
    await c.openLocal(r'C:\Users\me\book.xlsx');
    surface.ctl.add({'type': 'ready'});
    await Future<void>.delayed(const Duration(milliseconds: 10));
    await c.hub.registry['office.apply_change']!({'name': 'office.apply_change', 'surfaceId': 's1', 'context': {}});
    final load = surface.posted.lastWhere((m) => m['type'] == 'load');
    expect(((load['workbook'] as Map)['sheets'] as List).first['cells']['B2'], {'v': 99});
    expect(c.view!['workbook'], saved);
    expect(c.notice, 'Saved to book.xlsx.');
  });
}
