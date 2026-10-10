import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/living/a2ui/a2ui_dock.dart';
import 'package:uri_ui/living/a2ui/a2ui_hub.dart';
import 'package:uri_ui/living/a2ui/a2ui_view.dart';
import 'package:uri_ui/living/integration/scheduler_client.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/theme/uri_theme.dart';

/// Renderer and hub behaviour with surfaces produced by the real scheduler
/// host (`tests/a2ui/make_surface_fixtures.py`), replayed through a fake HTTP
/// client that records every action message the renderer sends.
/// Evidence level: S (widget simulation).
http.Response _json(Object? body, [int code = 200]) => http.Response.bytes(
  utf8.encode(jsonEncode(body)),
  code,
  headers: {'content-type': 'application/json'},
);

void main() {
  final fx = jsonDecode(
    File('../tests/a2ui/fixtures/surfaces.json').readAsStringSync(),
  ) as Map<String, dynamic>;
  final proposal = fx['proposal'] as Map<String, dynamic>;
  final sid = proposal['surface_id'] as String;

  late List<Map<String, dynamic>> sent;
  late Map<String, dynamic> Function(Map<String, dynamic>) onAction;

  SchedulerClient client() => SchedulerClient(
    baseUrl: 'http://127.0.0.1:1',
    token: 't',
    principal: 'owner',
    client: MockClient((req) async {
      final body = req.body.isEmpty
          ? <String, dynamic>{}
          : jsonDecode(req.body) as Map<String, dynamic>;
      if (req.url.path == '/a2ui/propose') {
        return _json(proposal);
      }
      if (req.url.path == '/a2ui/action') {
        final a = (body['action'] as Map).cast<String, dynamic>();
        sent.add(a);
        final r = onAction(a);
        return _json(r, r.containsKey('error') ? 400 : 200);
      }
      if (req.url.path == '/a2ui/calendar') return _json(fx['calendar']);
      if (req.url.path == '/a2ui/surfaces') {
        return _json({'messages': proposal['messages']});
      }
      return http.Response('{"error":"NOT_FOUND"}', 404);
    }),
  );

  setUp(() {
    sent = [];
    onAction = (_) => fx['revised'] as Map<String, dynamic>;
  });

  Widget app(Widget child) => MaterialApp(
    theme: buildUriTheme(
      resolveUriColors(UriThemeChoice.obsidianCyan, Brightness.dark),
    ),
    home: Scaffold(body: SingleChildScrollView(child: child)),
  );

  // The stream wiring itself is covered by the "without a scheduler" test; real HTTP needs runAsync.
  Future<A2uiHub> handedOff(WidgetTester t) async {
    final hub = A2uiHub(scheduler: client());
    await t.runAsync(() => hub.handoff(fx['handoff'] as Map<String, dynamic>));
    return hub;
  }

  testWidgets(
    'a handoff renders the proposal; inputs stay local; revise sends the exact digest and draft',
    (t) async {
      t.view.physicalSize = const Size(1200, 2600);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.reset);
      final hub = await handedOff(t);
      expect(hub.notices, isEmpty);
      expect(hub.surfaces.map((s) => s.id), [sid]);
      final s = hub.surface(sid)!;
      expect(s.placement, 'companion');
      await t.pumpWidget(app(A2uiSurfaceView(hub: hub, surfaceId: sid)));
      expect(
        find.text('Festival greeting GIFs: proposed schedule'),
        findsOneWidget,
      );
      expect(find.textContaining('Dussehra'), findsWidgets);
      expect(
        find.textContaining('Nothing runs until you confirm'),
        findsOneWidget,
      );
      // Inputs: deselect everything except Diwali and Holi (Holi is in the default list).
      final draft = List<String>.from(s.read('/draft/selection') as List);
      for (final k in draft) {
        if (k != 'diwali' && k != 'holi') {
          await t.ensureVisible(find.byKey(ValueKey('a2ui.$sid.picker.$k')));
          await t.tap(find.byKey(ValueKey('a2ui.$sid.picker.$k')));
          await t.pump();
        }
      }
      expect(
        hub.surface(sid)!.read('/draft/selection'),
        unorderedEquals(['diwali', 'holi']),
      );
      expect(sent, isEmpty); // nothing left the renderer
      // An input can never write bound data.
      expect(hub.surface(sid)!.write('/bound/proposal_sha256', 'x'), isFalse);
      await t.ensureVisible(find.byKey(ValueKey('a2ui.$sid.revise')));
      await t.tap(find.byKey(ValueKey('a2ui.$sid.revise')));
      await t.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      await t.pump();
      expect(sent, hasLength(1));
      final a = sent.single;
      expect(a['name'], 'scheduler.revise_proposal');
      expect(a['sourceComponentId'], 'revise');
      final ctx = a['context'] as Map;
      expect(ctx['surface_digest'], s.digest);
      expect(ctx['selection'], unorderedEquals(['diwali', 'holi']));
      expect(ctx['time'], '09:00');
      expect(ctx['offset_days'], '2');
      // The reply (a new revision) was applied: new digest, new bound proposal hash.
      final s2 = hub.surface(sid)!;
      expect(s2.revision, 2);
      expect(s2.digest, isNot(s.digest));
      expect(
        s2.read('/bound/proposal_sha256'),
        isNot(s.read('/bound/proposal_sha256')),
      );
    },
  );

  testWidgets(
    'confirm sends the bound proposal hash; a refusal is shown, not hidden',
    (t) async {
      t.view.physicalSize = const Size(1200, 2600);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.reset);
      final hub = await handedOff(t);
      onAction = (_) => {'error': 'DRAFT_CHANGED', 'detail': 'update first'};
      await t.pumpWidget(app(A2uiSurfaceView(hub: hub, surfaceId: sid)));
      await t.ensureVisible(find.byKey(ValueKey('a2ui.$sid.confirm')));
      await t.tap(find.byKey(ValueKey('a2ui.$sid.confirm')));
      await t.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      await t.pump();
      final ctx = sent.single['context'] as Map;
      expect(
        ctx['proposal_sha256'],
        hub.surface(sid)!.read('/bound/proposal_sha256'),
      );
      expect(find.byKey(ValueKey('a2ui.$sid.error')), findsOneWidget);
      expect(find.textContaining('Update proposal'), findsWidgets);
    },
  );

  testWidgets(
    'a definition with a forbidden part is refused whole and the owner is told',
    (t) async {
      final hub = A2uiHub(scheduler: client());
      final bad = jsonDecode(jsonEncode(proposal['messages'])) as List;
      ((bad[1] as Map)['updateComponents']['components'] as List).add({
        'id': 'x',
        'component': 'WebView',
      });
      hub.apply(bad);
      expect(hub.surfaces, isEmpty);
      expect(hub.notices.single, contains('refused'));
      // valid messages still apply
      hub.apply(proposal['messages'] as List);
      expect(hub.surfaces, hasLength(1));
      // a later bad update leaves the shown version untouched
      final before = hub.surface(sid)!.digest;
      hub.apply([
        {
          'version': 'v0.9',
          'updateComponents': {
            'surfaceId': sid,
            'components': [
              {
                'id': 'root',
                'component': 'Text',
                'text': 'open https://evil.example',
              },
            ],
          },
        },
      ]);
      expect(hub.surface(sid)!.digest, before);
      expect(hub.surface(sid)!.byId.length, greaterThan(5));
    },
  );

  testWidgets('an unregistered action is never sent', (t) async {
    final hub = A2uiHub(scheduler: client());
    hub.apply(proposal['messages'] as List);
    hub.registry.remove('scheduler.revise_proposal');
    await hub.act(sid, 'revise');
    expect(sent, isEmpty);
    expect(hub.errors[sid], contains('not available'));
  });

  testWidgets('a proposal reply that renders nothing reviewable is a failed handoff (INT-F1)', (t) async {
    for (final body in <Object>[
      {'messages': <Object>[]},
      {'messages': [{'not': 'a valid message'}]},
    ]) {
      final failed = <Map<String, dynamic>>[];
      final hub = A2uiHub(
        scheduler: SchedulerClient(
          baseUrl: 'http://127.0.0.1:1',
          token: 't',
          principal: 'owner',
          client: MockClient((req) async => req.url.path == '/a2ui/propose'
              ? _json(body)
              : http.Response('{"error":"NOT_FOUND"}', 404)),
        ),
        onHandoffFailed: failed.add,
      );
      await t.runAsync(() => hub.handoff(fx['handoff'] as Map<String, dynamic>));
      expect(hub.surfaces, isEmpty);
      expect(failed, hasLength(1));
      expect(hub.notices.last, contains('nothing to review'));
    }
    // A real proposal is not reported as a failure.
    final failed = <Map<String, dynamic>>[];
    final ok = A2uiHub(scheduler: client(), onHandoffFailed: failed.add);
    await t.runAsync(() => ok.handoff(fx['handoff'] as Map<String, dynamic>));
    expect(ok.surfaces, isNotEmpty);
    expect(failed, isEmpty);
  });

  testWidgets('without a scheduler a handoff gives an honest notice', (
    t,
  ) async {
    final handoffs = StreamController<Map<String, dynamic>>();
    final failed = <Map<String, dynamic>>[];
    final hub = A2uiHub(handoffs: handoffs.stream, onHandoffFailed: failed.add);
    handoffs.add(fx['handoff'] as Map<String, dynamic>);
    await t.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 20)),
    );
    expect(hub.surfaces, isEmpty);
    expect(hub.notices.single, contains('scheduler is not running'));
    expect(failed, hasLength(1)); // INT-F1: whoever showed "waiting for you" is told
    await handoffs.close();
  });

  testWidgets(
    'companion slot shows companion surfaces; workspace surfaces get one chip that opens the Workspace',
    (t) async {
      t.view.physicalSize = const Size(900, 1800);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.reset);
      final hub = A2uiHub(scheduler: client());
      hub.apply(proposal['messages'] as List);
      hub.apply((fx['calendar'] as Map)['messages'] as List);
      final presentation = UiPresentationController();
      await t.pumpWidget(
        app(
          A2uiCompanionSlot(hub: hub, presentation: presentation, width: 560),
        ),
      );
      expect(find.byKey(ValueKey('a2ui.$sid')), findsOneWidget);
      expect(find.byKey(const ValueKey('a2ui.calendar-review')), findsNothing);
      await t.tap(find.byKey(const ValueKey('a2ui.open-workspace')));
      expect(presentation.mode, UiPresentationMode.workspace);
      expect(presentation.focus, WorkspaceFocus.tasks);
    },
  );

  testWidgets(
    'calendar review: correct-date sends record, date, note and the literal correction',
    (t) async {
      t.view.physicalSize = const Size(1200, 2400);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.reset);
      final hub = A2uiHub(scheduler: client());
      await t.runAsync(hub.openCalendar);
      onAction = (_) => {'result': 'CORRECTED', 'messages': []};
      await t.pumpWidget(
        app(A2uiDock(hub: hub, placements: const ['workspace'])),
      );
      hub.input('calendar-review', '/draft/record', 'diwali:2026');
      hub.input('calendar-review', '/draft/start', '2026-11-09');
      await t.pump();
      await t.ensureVisible(
        find.byKey(const ValueKey('a2ui.calendar-review.note')),
      );
      await t.enterText(
        find.byKey(const ValueKey('a2ui.calendar-review.note')),
        'local practice',
      );
      await t.tap(find.byKey(const ValueKey('a2ui.calendar-review.set_date')));
      await t.runAsync(
        () => Future<void>.delayed(const Duration(milliseconds: 50)),
      );
      final ctx = sent.single['context'] as Map;
      expect(ctx['record'], 'diwali:2026');
      expect(ctx['start'], '2026-11-09');
      expect(ctx['note'], 'local practice');
      expect(ctx['correction'], 'set_date');
      // a correct-date without a date is stopped before sending
      sent.clear();
      hub.input('calendar-review', '/draft/start', '2026-13-99x');
      await hub.act('calendar-review', 'set_date');
      expect(sent, isEmpty);
    },
  );

  test('A2UI audit r1 F4: template inputs write list items in place; /bound stays read-only', () {
    final s = A2uiSurface('t', 'inline')
      ..data = {
        'draft': {
          'items': [
            {'name': 'a'},
            {'name': 'b'},
          ],
        },
        'bound': {'x': 1},
      };
    expect(s.write('name', 'z', scope: '/draft/items/1'), isTrue);
    expect(s.read('/draft/items'), [
      {'name': 'a'},
      {'name': 'z'},
    ]);
    expect(
      s.write('/draft/items/5/name', 'q'),
      isFalse,
    ); // no new list slot invented
    expect(s.write('/bound/x', 2), isFalse);
    expect(
      s.write('x', 2, scope: '/bound'),
      isFalse,
    ); // relative path into /bound
    expect(s.read('/bound/x'), 1);
  });

  test('A2UI audit r1 F1/F5: bound patches and deep nesting are refused by the renderer', () {
    final hub = A2uiHub();
    hub.apply(proposal['messages'] as List);
    final before = hub.surface(sid)!.digest;
    hub.apply([
      {
        'version': 'v0.9',
        'updateDataModel': {
          'surfaceId': sid,
          'path': '/bound/surface/digest',
          'value': 'f' * 64,
        },
      },
    ]);
    expect(hub.surface(sid)!.digest, before);
    expect(hub.notices.last, contains('READ_ONLY_PATH'));
  });
}
