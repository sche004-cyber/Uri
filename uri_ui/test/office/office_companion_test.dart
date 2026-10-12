// URI Office companion pane (owner request 2026-10-12): the URI companion sits in the Office region's right pane.
// While a workbook is open in Office focus, the companion composer (and push-to-talk, see live_voice_test) sends the
// owner's request to the open workbook; URI's reply and suggested changes appear in that pane. Elsewhere the
// composer keeps its ordinary conversation behaviour.
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/contracts/readiness_report.dart';
import 'package:uri_ui/living/contracts/work_items.dart';
import 'package:uri_ui/living/living_app.dart' show LivingPreferencesStore;
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_controller.dart';
import 'package:uri_ui/living/office/office_panel.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/widgets/living_composer.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/app_state_scope.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/theme/uri_theme.dart';

import 'office_panel_test.dart' show FakeSurface;

const _workbook = {
  'sheets': [
    {'name': 'Sales', 'index': 0, 'max_row': 3, 'max_col': 2, 'truncated': false, 'merges': [], 'col_widths': {},
      'row_heights': {}, 'locked': [], 'cells': {'A1': {'v': 'Region'}, 'B2': {'v': 10}}},
  ],
  'styles': {},
  'kept_not_shown': {'charts': 0, 'images': 0, 'pivot_tables': 0},
};

Map<String, dynamic> _draft(List<Map<String, dynamic>> changes) =>
    {'workbook_id': 'w1', 'engine': 'local', 'version': 2, 'can_undo': false, 'can_redo': false, 'changes': changes};

final _uriChange = {
  'cid': 'c1', 'by': 'uri', 'kind': 'cell', 'state': 'proposed', 'sheet': 'Sales', 'cell': 'C2',
  'before': null, 'after': {'v': 'Checked by URI'}, 'op': null, 'change_sha256': 'b' * 64,
};

/// A fake Office service: records each request; `instruct` proposes one change with a reply.
(OfficeClient, Map<String, List<Map<String, dynamic>>>) _service({String message = 'I will write it in C2.'}) {
  final calls = <String, List<Map<String, dynamic>>>{};
  final mock = MockClient((req) async {
    final body = req.body.isEmpty ? <String, dynamic>{} : jsonDecode(req.body) as Map<String, dynamic>;
    (calls[req.url.path] ??= []).add(body);
    switch (req.url.path) {
      case '/open/local':
        return http.Response(jsonEncode({'workbook_id': 'w1', 'engine': 'local', 'label': 'book.xlsx',
          'workbook': _workbook, 'draft': _draft([]), 'history_on': false}), 200);
      case '/workbook/w1/instruct':
        return http.Response(jsonEncode({'message': message, 'proposed': [_uriChange], 'refused': [], 'metrics': {},
          'draft': _draft([_uriChange])}), 200);
    }
    return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
  });
  return (OfficeClient.forTest(Uri.parse('http://127.0.0.1:18530'), 'tok', mock), calls);
}

OfficeEnvironment _env(FakeSurface surface) => OfficeEnvironment(
      surfaceFactory: () => surface,
      pickWorkbookPath: () async => r'C:\Users\me\book.xlsx',
      pickSavePath: (_) async => null,
      openExternalLink: (_) async {},
    );

LivingServices _services() {
  final demo = MockCompanionSource();
  final work = MockWorkSimulator(stepInterval: const Duration(milliseconds: 100));
  return LivingServices(
    presentation: UiPresentationController(commandCooldown: Duration.zero),
    companion: CompositeCompanionSource([work.companion, demo]),
    work: work,
    readiness: MockReadinessSource(),
    effects: EffectsSettings(reducedMotion: true),
    demo: demo,
  );
}

Widget _scoped(AppState appState, LivingServices services, Widget child) => MaterialApp(
      theme: ThemeData(extensions: const [UriColors.graphite]),
      home: AppStateScope(
        state: appState,
        child: LivingScope(
          services: services,
          child: Scaffold(body: SizedBox(width: 1400, height: 900, child: child)),
        ),
      ),
    );

class _FakeTarget extends ChangeNotifier implements OfficeRequestTarget {
  final asks = <String>[];
  @override
  bool acceptsRequests = true;
  @override
  bool busy = false;
  @override
  Future<void> instruct(String text, {String? activeSheet}) async => asks.add(text);
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  group('Office target selection', () {
    test('only an open workbook in Office focus takes the companion requests', () {
      final services = _services();
      addTearDown(services.dispose);
      final target = _FakeTarget();
      expect(services.activeOfficeTarget(), isNull);
      services.officeTarget.value = target;
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      expect(services.activeOfficeTarget(), isNull, reason: 'conversation focus keeps the ordinary conversation');
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.office);
      expect(services.activeOfficeTarget(), same(target));
      target.acceptsRequests = false;
      expect(services.activeOfficeTarget(), isNull, reason: 'no workbook open');
      target.acceptsRequests = true;
      services.presentation.setMode(UiPresentationMode.dashboard);
      expect(services.activeOfficeTarget(), isNull);
    });
  });

  group('controller conversation', () {
    test('a request and URI\'s reply are recorded; the change stays a card, never auto-accepted', () async {
      final (client, calls) = _service();
      final c = OfficeController(client: client, surface: FakeSurface());
      addTearDown(c.dispose);
      expect(c.acceptsRequests, isFalse);
      await c.instruct('Mark row 2 as checked');
      expect(calls['/workbook/w1/instruct'], isNull, reason: 'no workbook open: nothing is sent');
      expect(c.conversation, isEmpty);

      await c.openLocal(r'C:\Users\me\book.xlsx');
      expect(c.acceptsRequests, isTrue);
      await c.instruct('  Mark row 2 as checked  ');
      expect(calls['/workbook/w1/instruct']!.single['text'], 'Mark row 2 as checked');
      expect([for (final t in c.conversation) (t.speaker, t.text)], [
        (OfficeSpeaker.owner, 'Mark row 2 as checked'),
        (OfficeSpeaker.uri, 'I will write it in C2.'),
      ]);
      expect(c.proposed.single['cid'], 'c1');
      expect(calls['/workbook/w1/decide'], isNull);
    });

    test('an empty Brain message still tells the owner what happened', () async {
      final (client, _) = _service(message: '');
      final c = OfficeController(client: client, surface: FakeSurface());
      addTearDown(c.dispose);
      await c.openLocal(r'C:\Users\me\book.xlsx');
      await c.instruct('Mark row 2 as checked');
      expect(c.conversation.last.speaker, OfficeSpeaker.uri);
      expect(c.conversation.last.text, 'I suggested 1 change. Review below.');
    });

    // R1-01 (review URI-OFFICE-M1-c): the conversation and approval card of the previous workbook stayed in the pane.
    test('opening another workbook clears the previous conversation and approval card', () async {
      var opened = 0;
      final mock = MockClient((req) async {
        switch (req.url.path) {
          case '/open/local':
            final id = 'w${++opened}';
            return http.Response(jsonEncode({'workbook_id': id, 'engine': 'local', 'label': '$id.xlsx',
              'workbook': _workbook, 'draft': {..._draft([]), 'workbook_id': id}, 'history_on': false}), 200);
          case '/workbook/w1/instruct':
            return http.Response(jsonEncode({'message': 'Done.', 'proposed': [], 'refused': [], 'metrics': {},
              'draft': _draft([])}), 200);
          case '/workbook/w1/propose_save':
            return http.Response(jsonEncode({'messages': [
              {'version': 'v0.9', 'createSurface': {'surfaceId': 'save-w1', 'catalogId': 'uri:a2ui/catalog/v1',
                'theme': {'agentDisplayName': 'URI', 'placement': 'workspace'}}},
              {'version': 'v0.9', 'updateComponents': {'surfaceId': 'save-w1', 'components': [
                {'id': 'root', 'component': 'Column', 'children': ['t']},
                {'id': 't', 'component': 'Text', 'text': 'Save these changes to the file?'},
              ]}},
            ]}), 200);
        }
        return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
      });
      final c = OfficeController(
          client: OfficeClient.forTest(Uri.parse('http://127.0.0.1:18530'), 'tok', mock), surface: FakeSurface());
      addTearDown(c.dispose);
      await c.openLocal(r'C:\Users\me\one.xlsx');
      await c.instruct('Mark row 2');
      await c.proposeSave();
      expect(c.conversation, hasLength(2));
      expect(c.hub.surfaces.map((s) => s.id), ['save-w1']);

      await c.openLocal(r'C:\Users\me\two.xlsx');
      expect(c.workbookId, 'w2');
      expect(c.conversation, isEmpty);
      expect(c.brainMessage, isNull);
      expect(c.hub.surfaces, isEmpty);
    });

    test('the conversation is capped', () async {
      final (client, _) = _service();
      final c = OfficeController(client: client, surface: FakeSurface());
      addTearDown(c.dispose);
      await c.openLocal(r'C:\Users\me\book.xlsx');
      for (var i = 0; i < 60; i++) {
        await c.instruct('request $i');
      }
      expect(c.conversation.length, OfficeController.conversationCap);
      expect(c.conversation.last.text, 'I will write it in C2.');
    });
  });

  group('companion pane', () {
    testWidgets('on its own: the right pane takes the request and shows the reply and the change card', (tester) async {
      final surface = FakeSurface();
      final (client, calls) = _service();
      await tester.pumpWidget(MaterialApp(
        theme: ThemeData(extensions: const [UriColors.graphite]),
        home: Scaffold(body: SizedBox(width: 1400, height: 900,
            child: OfficeRegion(environment: _env(surface), clientFactory: () => client))),
      ));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('office-companion')), findsOneWidget, reason: 'the pane is there before a workbook');
      expect(find.textContaining('Open a workbook'), findsOneWidget);
      surface.ctl.add({'type': 'ready'});
      await tester.tap(find.byKey(const ValueKey('office-open-file')));
      await tester.pumpAndSettle();

      await tester.enterText(find.byKey(const ValueKey('office-ask')), 'Mark row 2 as checked');
      await tester.tap(find.byKey(const ValueKey('office-ask-send')));
      await tester.pumpAndSettle();
      expect(calls['/workbook/w1/instruct']!.single['text'], 'Mark row 2 as checked');
      expect(find.byKey(const ValueKey('office-turn-0-owner')), findsOneWidget);
      expect(find.text('URI: I will write it in C2.'), findsOneWidget);
      expect(find.byKey(const ValueKey('office-change-c1')), findsOneWidget);
      expect(find.byKey(const ValueKey('office-uri-mark')), findsOneWidget);
    });

    testWidgets('inside the living UI: the companion composer sends to the open workbook, not the conversation',
        (tester) async {
      final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
      final services = _services();
      addTearDown(services.dispose);
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.office);
      final surface = FakeSurface();
      final (client, calls) = _service();
      await tester.pumpWidget(_scoped(appState, services,
          OfficeRegion(environment: _env(surface), clientFactory: () => client)));
      await tester.pumpAndSettle();
      expect(find.byType(LivingComposer), findsOneWidget);
      expect(find.byKey(const ValueKey('office-ask')), findsNothing);
      expect(services.officeTarget.value, isA<OfficeController>(), reason: 'the region registers its workbook');
      expect(services.activeOfficeTarget(), isNull, reason: 'nothing is open yet');

      surface.ctl.add({'type': 'ready'});
      await tester.tap(find.byKey(const ValueKey('office-open-file')));
      await tester.pumpAndSettle();
      expect(services.activeOfficeTarget(), same(services.officeTarget.value));
      expect(find.text('Ask URI to change this sheet'), findsOneWidget);
      // Testing-only conversation toggles do not apply to sheet requests.
      expect(find.byKey(const ValueKey('living-composer-dictation')), findsNothing);

      await tester.enterText(find.byKey(const ValueKey('living-composer-field')), 'Mark row 2 as checked');
      await tester.tap(find.byKey(const ValueKey('living-composer-send')));
      await tester.pumpAndSettle();
      expect(calls['/workbook/w1/instruct']!.single['text'], 'Mark row 2 as checked');
      expect(appState.isSendingAsk, isFalse);
      expect(find.text('URI: I will write it in C2.'), findsOneWidget);
      expect(find.byKey(const ValueKey('office-change-c1')), findsOneWidget);
      expect(calls['/workbook/w1/decide'], isNull, reason: 'a request never accepts a change');

      // Leaving the region releases the workbook: requests go back to the ordinary conversation.
      await tester.pumpWidget(_scoped(appState, services, const SizedBox()));
      await tester.pumpAndSettle();
      expect(services.officeTarget.value, isNull);
    });

    testWidgets('outside Office focus the composer keeps the ordinary conversation', (tester) async {
      final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
      final services = _services();
      addTearDown(services.dispose);
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      final target = _FakeTarget();
      services.officeTarget.value = target;
      await tester.pumpWidget(_scoped(appState, services, const Align(
          alignment: Alignment.bottomCenter, child: LivingComposer())));
      await tester.pumpAndSettle();
      expect(find.text('Ask URI to change this sheet'), findsNothing);
      await tester.enterText(find.byKey(const ValueKey('living-composer-field')), 'Hello');
      await tester.tap(find.byKey(const ValueKey('living-composer-send')));
      await tester.pumpAndSettle();
      expect(target.asks, isEmpty);
    });

    testWidgets('a busy workbook keeps the typed request in the composer', (tester) async {
      final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
      final services = _services();
      addTearDown(services.dispose);
      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.office);
      final target = _FakeTarget()..busy = true;
      services.officeTarget.value = target;
      await tester.pumpWidget(_scoped(appState, services, const Align(
          alignment: Alignment.bottomCenter, child: LivingComposer())));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const ValueKey('living-composer-field')), 'Sum column B');
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pumpAndSettle();
      expect(target.asks, isEmpty);
      expect(find.text('Sum column B'), findsOneWidget);
    });
  });
}
