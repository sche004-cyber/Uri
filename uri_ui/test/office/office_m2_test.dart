// URI Office M2: a new workbook built from one or more source files (docs/office/M2_PLAN_AND_ACCEPTANCE_CRITERIA.md),
// against a fake sheet view and a fake Office service.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_controller.dart';
import 'package:uri_ui/living/office/office_panel.dart';
import 'package:uri_ui/theme/uri_theme.dart';

import 'office_panel_test.dart' show FakeSurface;

Map<String, dynamic> _sheet(String name) => {'name': name, 'index': 0, 'max_row': 0, 'max_col': 0, 'truncated': false,
      'merges': [], 'col_widths': {}, 'row_heights': {}, 'locked': [], 'cells': {}};

Map<String, dynamic> _wb(List<String> sheets) =>
    {'sheets': [for (final s in sheets) _sheet(s)], 'styles': {}, 'kept_not_shown': {'charts': 0, 'images': 0, 'pivot_tables': 0}};

Map<String, dynamic> _change(String cid, String cell, String sha) => {'cid': cid, 'by': 'uri', 'kind': 'cell',
      'state': 'proposed', 'sheet': 'Summary', 'cell': cell, 'before': {}, 'after': {'v': cell}, 'op': null,
      'change_sha256': sha};

Map<String, dynamic> _draft(List<Map<String, dynamic>> changes, {int version = 3, String engine = 'new'}) =>
    {'workbook_id': 'w1', 'engine': engine, 'version': version, 'can_undo': false, 'can_redo': false, 'changes': changes};

List<Map<String, dynamic>> _sources(List<String> labels, Map<String, String?> roles) => [
      for (final (i, l) in labels.indexed)
        {'id': 'S${i + 1}', 'label': l, 'role': roles['S${i + 1}'],
          'sheets': [{'name': 'Data', 'rows': 4, 'cols': 2, 'truncated': false}]},
    ];

class _Service {
  _Service({this.proposed = const [], this.reopenNeeded = false, String? role = 'reference'})
      : roles = {'S1': role, 'S2': role, 'S3': role};
  List<Map<String, dynamic>> proposed;
  final bool reopenNeeded;
  Map<String, String?> roles;
  String? get working => roles.entries.where((e) => e.value == 'check' || e.value == 'edit').map((e) => e.key).firstOrNull;
  dynamic findings;
  final calls = <String, List<Map<String, dynamic>>>{};
  var labels = <String>['north.xlsx', 'south.xlsx'];
  var created = false;

  OfficeClient client() => OfficeClient.forTest(Uri.parse('http://127.0.0.1:18530'), 'tok', MockClient((req) async {
        final body = req.body.isEmpty ? <String, dynamic>{} : jsonDecode(req.body) as Map<String, dynamic>;
        (calls[req.url.path] ??= []).add(body);
        Map<String, dynamic> view() => created
            ? {'workbook_id': 'w1', 'engine': 'local', 'label': 'summary.xlsx', 'workbook': _wb(['Summary']),
                'draft': _draft([], engine: 'local'), 'history_on': false}
            : {'workbook_id': 'w1', 'engine': working == null ? 'new' : 'local',
                'label': working == null ? 'New workbook' : labels[int.parse(working!.substring(1)) - 1],
                'workbook': _wb(['Summary']), 'draft': _draft(proposed), 'history_on': false,
                'sources': _sources(labels, roles), 'working': working,
                'task': working == null ? 'build' : roles[working]};
        switch (req.url.path) {
          case '/open/new':
            return http.Response(jsonEncode(view()), 200);
          case '/workbook/w1':
            return http.Response(jsonEncode(view()), 200);
          case '/workbook/w1/instruct':
            return http.Response(jsonEncode({'message': '', 'proposed': [], 'metrics': {}, 'draft': _draft(proposed),
              'refused': [{'index': 1, 'code': 'UNKNOWN_SOURCE', 'detail': 'None'},
                {'index': 2, 'code': 'OVERLAPS_EARLIER_OP', 'detail': 'Summary!A6 was already written'}],
              'notes': {'uncalculated': 2, 'not_copied': 0}, 'workbook': _wb(['Summary']), 'findings': ?findings}), 200);
          case '/workbook/w1/roles':
            roles = {...roles, ...(body['roles'] as Map).cast<String, String>()};
            return http.Response(jsonEncode(view()), 200);
          case '/workbook/w1/sources':
            labels = [...labels, 'east.xlsx'];
            return http.Response(jsonEncode(view()), 200);
          case '/workbook/w1/decide_all':
            final d = body['decision'] == 'accept' ? 'accepted' : 'rejected';
            proposed = [for (final c in proposed) {...c, 'state': d}];
            return http.Response(jsonEncode({'draft': _draft(proposed, version: 4)}), 200);
          case '/workbook/w1/propose_save':
            return http.Response(jsonEncode({'messages': [
              {'version': 'v0.9', 'createSurface': {'surfaceId': 'new-w1', 'catalogId': 'uri:a2ui/catalog/v1',
                'theme': {'agentDisplayName': 'URI', 'placement': 'workspace'}}},
              {'version': 'v0.9', 'updateComponents': {'surfaceId': 'new-w1', 'components': [
                {'id': 'root', 'component': 'Column', 'children': ['t']},
                {'id': 't', 'component': 'Text', 'text': 'Create this new file?'},
              ]}},
            ]}), 200);
          case '/a2ui/action':
            created = true;
            return http.Response(jsonEncode({'status': 'applied', 'workbook_id': 'w1', 'created': true,
              'saved_to': 'summary.xlsx', 'reopen_needed': reopenNeeded,
              'draft': reopenNeeded ? _draft(proposed) : _draft([], engine: 'local'),
              'workbook': _wb(['Summary'])}), 200);
        }
        return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
      }));
}

OfficeEnvironment _env(FakeSurface surface, {List<String> picked = const [r'C:\Users\me\north.xlsx']}) =>
    OfficeEnvironment(
      surfaceFactory: () => surface,
      pickWorkbookPath: () async => null,
      pickSavePath: (_) async => r'C:\Users\me\out\New workbook (URI).xlsx',
      openExternalLink: (_) async {},
      pickSourcePaths: () async => picked,
    );

Widget _app(Widget child) => MaterialApp(
      theme: ThemeData(extensions: const [UriColors.graphite]),
      home: Scaffold(body: SizedBox(width: 1400, height: 1600, child: child)),
    );

void main() {
  testWidgets('New from files: sources shown, add a file, save only as a new file', (tester) async {
    tester.view.physicalSize = const Size(1400, 1700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final svc = _Service();
    final surface = FakeSurface();
    await tester.pumpWidget(_app(OfficeRegion(
        environment: _env(surface, picked: [r'C:\Users\me\north.xlsx', r'C:\Users\me\south.xlsx']),
        clientFactory: svc.client)));
    await tester.pumpAndSettle();
    surface.ctl.add({'type': 'ready'});
    await tester.tap(find.byKey(const ValueKey('office-new-from-files')));
    await tester.pumpAndSettle();
    expect(svc.calls['/open/new']!.single, {'paths': [r'C:\Users\me\north.xlsx', r'C:\Users\me\south.xlsx']});
    expect(find.byKey(const ValueKey('office-source-S1')), findsOneWidget);
    expect(find.text('S2 south.xlsx'), findsOneWidget);
    expect(find.textContaining('Added north.xlsx, south.xlsx. Say what each file is for'), findsOneWidget);
    // A new workbook is saved only as a new file; no history (M2-D6), no share, no save-in-place.
    expect(find.byKey(const ValueKey('office-save-new')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-save')), findsNothing);
    expect(find.text('Share via Google'), findsNothing);
    expect(find.byKey(const ValueKey('office-history-consent')), findsNothing);
    // The grid got the new workbook.
    expect(surface.posted.lastWhere((m) => m['type'] == 'load')['workbook'], _wb(['Summary']));

    await tester.tap(find.byKey(const ValueKey('office-add-source')));
    await tester.pumpAndSettle();
    expect(svc.calls['/workbook/w1/sources']!.single, {'paths': [r'C:\Users\me\north.xlsx', r'C:\Users\me\south.xlsx']});
    expect(find.text('S3 east.xlsx'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('office-save-new')));
    await tester.pumpAndSettle();
    expect(svc.calls['/workbook/w1/propose_save']!.single, {'save_as_path': r'C:\Users\me\out\New workbook (URI).xlsx'});
    expect(find.text('Create this new file?'), findsOneWidget);
  });

  test('Accept all is bound to the draft version and the hash of the proposed set', () async {
    final svc = _Service(proposed: [_change('c2', 'B1', 'b' * 64), _change('c1', 'A1', 'a' * 64)]);
    final c = OfficeController(client: svc.client(), surface: FakeSurface());
    addTearDown(c.dispose);
    await c.openNew([r'C:\Users\me\north.xlsx']);
    // Reference value from the Python service: sha256(canonical(sorted([("c1","a"*64), ("c2","b"*64)]))).
    expect(c.proposedSetSha256(), '644c2b8dbade6ea4b2d2df26b22f75619c6398405c09fe83691e927a1845534d');
    await c.decideAll('accept');
    expect(svc.calls['/workbook/w1/decide_all']!.single, {'decision': 'accept', 'draft_version': 3,
      'set_sha256': '644c2b8dbade6ea4b2d2df26b22f75619c6398405c09fe83691e927a1845534d'});
    expect(c.proposed, isEmpty);
  });

  testWidgets('many proposed changes: at most 50 cards, Accept all and Reject all', (tester) async {
    tester.view.physicalSize = const Size(1400, 1700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final svc = _Service(proposed: [for (var i = 1; i <= 60; i++) _change('c$i', 'A$i', i.toRadixString(16).padLeft(64, '0'))]);
    final surface = FakeSurface();
    await tester.pumpWidget(_app(OfficeRegion(environment: _env(surface), clientFactory: svc.client)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-new-from-files')));
    await tester.pumpAndSettle();
    expect(find.text('Accept all 60'), findsOneWidget);
    expect(find.text('Reject all 60'), findsOneWidget);
    await tester.scrollUntilVisible(find.byKey(const ValueKey('office-more-changes')), 300,
        scrollable: find.descendant(of: find.byKey(const ValueKey('office-conversation')), matching: find.byType(Scrollable)));
    expect(find.text('and 10 more, marked in the sheet'), findsOneWidget);
    expect(find.byKey(const ValueKey('office-change-c51'), skipOffstage: false), findsNothing);
    await tester.scrollUntilVisible(find.byKey(const ValueKey('office-reject-all')), -300,
        scrollable: find.descendant(of: find.byKey(const ValueKey('office-conversation')), matching: find.byType(Scrollable)));
    await tester.ensureVisible(find.byKey(const ValueKey('office-reject-all')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-reject-all')));
    await tester.pumpAndSettle();
    expect(svc.calls['/workbook/w1/decide_all']!.single['decision'], 'reject');
    expect(find.byKey(const ValueKey('office-accept-all')), findsNothing);
  });

  test('creating the file turns the session into an ordinary local workbook', () async {
    final svc = _Service();
    final c = OfficeController(client: svc.client(), surface: FakeSurface());
    addTearDown(c.dispose);
    await c.openNew([r'C:\Users\me\north.xlsx']);
    expect(c.isNew, isTrue);
    await c.proposeSave(saveAsPath: r'C:\Users\me\out\summary.xlsx');
    // The action the card's "Create file" button sends (the hash-bound card itself is tested in Python).
    await c.hub.registry['office.apply_change']!({'name': 'office.apply_change', 'surfaceId': 'new-w1'});
    expect(c.isNew, isFalse);
    expect(c.sources, isEmpty);
    expect(c.view!['label'], 'summary.xlsx');
    expect(c.notice, 'Created summary.xlsx.');
  });

  test('created file that cannot be opened keeps the new workbook and explains how to open it', () async {
    final svc = _Service(reopenNeeded: true, proposed: [_change('c1', 'A1', 'a' * 64)]);
    final c = OfficeController(client: svc.client(), surface: FakeSurface());
    addTearDown(c.dispose);
    await c.openNew([r'C:\Users\me\north.xlsx']);
    await c.proposeSave(saveAsPath: r'C:\Users\me\out\summary.xlsx');
    await c.hub.registry['office.apply_change']!({'name': 'office.apply_change', 'surfaceId': 'new-w1'});
    expect(c.notice, 'Created summary.xlsx. It could not be opened here; open it with Open file.');
    expect(c.isNew, isTrue);
    expect(c.proposed, hasLength(1));
    expect(c.sources, hasLength(2));
    expect(svc.calls['/workbook/w1'], isNull);
  });

  test('refused ops and copy notes are explained to the owner', () async {
    final svc = _Service();
    final c = OfficeController(client: svc.client(), surface: FakeSurface());
    addTearDown(c.dispose);
    await c.openNew([r'C:\Users\me\north.xlsx']);
    await c.instruct('build it');
    final texts = [for (final t in c.conversation) t.text];
    expect(texts, contains('2 suggested change(s) were refused as unsafe or invalid '
        '(UNKNOWN_SOURCE: None; OVERLAPS_EARLIER_OP: Summary!A6 was already written).'));
    expect(texts, contains('2 source formula cell(s) had no calculated value and were copied as empty.'));
  });

  testWidgets('every added file needs a role: working file (check or edit) or reference', (tester) async {
    tester.view.physicalSize = const Size(1400, 1700);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final svc = _Service(role: null);
    final surface = FakeSurface();
    await tester.pumpWidget(_app(OfficeRegion(
        environment: _env(surface, picked: [r'C:\Users\me\north.xlsx', r'C:\Users\me\south.xlsx']),
        clientFactory: svc.client)));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('office-new-from-files')));
    await tester.pumpAndSettle();
    expect(find.text('What is each file for?'), findsOneWidget);

    // A request before the roles are set is not sent.
    await tester.enterText(find.byKey(const ValueKey('office-ask')), 'Check the totals');
    await tester.tap(find.byKey(const ValueKey('office-ask-send')));
    await tester.pumpAndSettle();
    expect(svc.calls['/workbook/w1/instruct'], isNull);
    expect(find.textContaining('First say what each file is for (working file or reference): north.xlsx, south.xlsx'),
        findsOneWidget);

    // S2 becomes the working file to check; S1 a reference.
    await tester.tap(find.descendant(of: find.byKey(const ValueKey('office-role-S2')), matching: find.text('Check')));
    await tester.pumpAndSettle();
    expect(svc.calls['/workbook/w1/roles']!.last, {'roles': {'S2': 'check'}});
    expect(find.byKey(const ValueKey('office-working-S2')), findsOneWidget);
    expect(find.text('Working file: south.xlsx'), findsOneWidget);
    expect(find.textContaining('Working file: south.xlsx (URI checks it and suggests fixes)'), findsOneWidget);
    await tester.tap(find.descendant(of: find.byKey(const ValueKey('office-role-S1')), matching: find.text('Reference')));
    await tester.pumpAndSettle();
    expect(svc.calls['/workbook/w1/roles']!.last, {'roles': {'S2': 'check', 'S1': 'reference'}});
    expect(find.text('What is each file for?'), findsNothing);

    // Making S1 the file to edit makes S2 a reference (one working file at a time).
    await tester.tap(find.descendant(of: find.byKey(const ValueKey('office-role-S1')), matching: find.text('Edit')));
    await tester.pumpAndSettle();
    expect(svc.calls['/workbook/w1/roles']!.last, {'roles': {'S2': 'reference', 'S1': 'edit'}});
    expect(find.byKey(const ValueKey('office-working-S1')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-working-S2')), findsNothing);
  });

  test('switching the working file removes its open approval surface', () async {
    final svc = _Service();
    final c = OfficeController(client: svc.client(), surface: FakeSurface());
    addTearDown(c.dispose);
    await c.openNew([r'C:\Users\me\north.xlsx', r'C:\Users\me\south.xlsx']);
    await c.proposeSave(saveAsPath: r'C:\Users\me\summary.xlsx');
    expect(c.hub.surfaces.map((s) => s.id), contains('new-w1'));

    await c.setRole('S1', 'reference');
    expect(c.hub.surfaces.map((s) => s.id), contains('new-w1'));
    await c.setRole('S2', 'check');
    expect(c.working, 'S2');
    expect(c.hub.surfaces, isEmpty);
  });

  test('a check lists its findings in the conversation', () async {
    final svc = _Service()
      ..roles = {'S1': 'check', 'S2': 'reference'}
      ..findings = [
        {'sheet': 'Data', 'cell': 'B4', 'issue': 'Total is 1200 but the rows add up to 1300.'},
        {'sheet': null, 'cell': null, 'issue': 'Dates use two formats.'},
      ];
    final c = OfficeController(client: svc.client(), surface: FakeSurface());
    addTearDown(c.dispose);
    await c.openNew([r'C:\Users\me\budget.xlsx']);
    await c.instruct('Check my budget');
    final texts = [for (final t in c.conversation) t.text];
    expect(texts, containsAllInOrder(['Check: 2 issue(s) found.', 'Data!B4: Total is 1200 but the rows add up to 1300.',
      'Dates use two formats.']));
  });
}
