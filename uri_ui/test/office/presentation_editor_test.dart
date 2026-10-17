// Authoring milestones A/B (plan 11 §4): the presentation editor in the Office workspace. Edit from a .pptx view and
// New presentation from Home (AB-10), change list and state line, undo, slide actions, a refused change in words,
// the real save card (made by the Python service, fixtures/authoring_save_card.json) and leaving with unsaved changes
// (AB-9). The Office service is a fake (package:http/testing MockClient).
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_nav_pane.dart';
import 'package:uri_ui/living/office/office_workspace.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/theme/uri_theme.dart';

final _png = base64Decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=');

List<dynamic> _card() =>
    jsonDecode(File('test/office/fixtures/authoring_save_card.json').readAsStringSync()) as List<dynamic>;

/// The authoring id inside the fixture card's surface id.
String _cardAid() => RegExp(r'office\.authoring_save\.([0-9a-f]{16})\.')
    .firstMatch('${(_card().first as Map)['createSurface']['surfaceId']}')!
    .group(1)!;

class FakeAuthoringOffice {
  FakeAuthoringOffice() : aid = _cardAid();
  final String aid;
  final calls = <String>[];
  final bodies = <String, List<Map<String, dynamic>>>{};
  List<Map<String, dynamic>> slides = [
    {'id': 256, 'index': 0, 'layout': 'Title Slide', 'title': 'Quarterly Review', 'title_id': 2, 'notes': '',
     'items': [{'id': 2, 'kind': 'text', 'placeholder': true, 'paragraphs': ['Quarterly Review']}]},
    {'id': 257, 'index': 1, 'layout': 'Title and Content', 'title': 'Highlights', 'title_id': 2, 'notes': 'Say thanks',
     'items': [
       {'id': 2, 'kind': 'text', 'placeholder': true, 'paragraphs': ['Highlights']},
       {'id': 3, 'kind': 'text', 'placeholder': true, 'paragraphs': ['Revenue up', 'Costs flat']},
     ]},
  ];
  List<String> changes = [];
  bool isNew = false;
  Map<String, dynamic>? opError;            // the next op answers this error (409) when set
  Map<String, dynamic>? actionError;        // the card action answers this error (409) when set
  int previewN = 1;

  Map<String, dynamic> view() => {
        'authoring_id': aid, 'kind': 'pptx', 'name': isNew ? 'New presentation.pptx' : 'Quarterly Review.pptx',
        'new': isNew, 'path': isNew ? null : r'C:\Users\me\Documents\Quarterly Review.pptx',
        'deck': {'slides': slides, 'layouts': ['Title Slide', 'Title and Content', 'Title Only', 'Blank'],
                 'aspect': 1.7778},
        'changes': [for (final c in changes) {'text': c}], 'can_undo': changes.isNotEmpty, 'can_redo': false,
        'preview_document_id': 'p$previewN', 'sha256_prefix': 'abc',
      };

  Map<String, dynamic> doc = {
    'document_id': '0123456789abcdef', 'kind': 'pptx', 'name': 'Quarterly Review.pptx', 'pages': 2,
    'outline': [], 'preview': {'state': 'ready', 'reason': null}, 'findings': [], 'renderer': 'LibreOffice',
  };

  http.Client client() => MockClient((req) async {
        final path = req.url.path;
        calls.add('${req.method} $path');
        Map<String, dynamic> body = {};
        if (req.body.isNotEmpty) body = (jsonDecode(req.body) as Map).cast<String, dynamic>();
        bodies.putIfAbsent(path, () => []).add(body);
        if (path.contains('/page/')) return http.Response.bytes(_png, 200, headers: {'content-type': 'image/png'});
        Map<String, dynamic>? out;
        if (path.startsWith('/document/p')) {
          out = {'document_id': path.split('/')[2], 'kind': 'pptx', 'name': 'x', 'pages': slides.length,
                 'preview': {'state': 'ready'}, 'outline': [], 'findings': []};
        } else if (path == '/authoring/edit' || path == '/authoring/new') {
          isNew = path == '/authoring/new';
          out = view();
        } else if (path == '/authoring/$aid') {
          out = view();
        } else if (path == '/authoring/$aid/op') {
          if (opError != null) {
            final e = opError!;
            opError = null;
            return http.Response(jsonEncode(e), 409);
          }
          final op = (body['op'] as Map).cast<String, dynamic>();
          if (op['op'] == 'set_title') {
            slides = [for (final s in slides) s['id'] == op['slide'] ? {...s, 'title': op['text']} : s];
            changes = [...changes, "Slide 1: title '${op['text']}'"];
          } else if (op['op'] == 'add_slide') {
            slides = [...slides, {'id': 300, 'index': slides.length, 'layout': op['layout'], 'title': '',
                                  'title_id': 2, 'notes': '', 'items': []}];
            changes = [...changes, "Add a '${op['layout']}' slide"];
          } else {
            changes = [...changes, '${op['op']}'];
          }
          previewN++;
          out = view();
        } else if (path == '/authoring/$aid/undo') {
          changes = changes.sublist(0, changes.length - 1);
          slides = [for (final s in slides) s['id'] == 256 ? {...s, 'title': 'Quarterly Review'} : s];
          previewN++;
          out = view();
        } else if (path == '/authoring/$aid/save') {
          out = {'messages': _card(), 'surface_id': 'x'};
        } else if (path == '/authoring/$aid/close') {
          out = {'closed': true, 'unsaved_changes': changes.length};
        } else if (path == '/a2ui/action') {
          if (actionError != null) return http.Response(jsonEncode(actionError), 409);
          changes = [];
          out = {'status': 'applied', 'subject_kind': 'authoring_save', 'subject_id': aid,
                 'saved_to': 'Quarterly Review.pptx', 'authoring_id': aid};
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
            'POST /document/0123456789abcdef/close' => {'closed': true},
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
      pickDocumentPath: () async => r'C:\Users\me\Documents\Quarterly Review.pptx',
      pickPdfSavePath: (_) async => null,
      pickPresentationSavePath: (_) async => saveAs,
      pickTemplatePath: () async => null,
      pickImagePath: () async => null,
    );

Future<FakeAuthoringOffice> _pump(WidgetTester tester, {String? saveAs, Size size = const Size(1600, 1000)}) async {
  SharedPreferences.setMockInitialValues({});
  await tester.binding.setSurfaceSize(size);
  addTearDown(() => tester.binding.setSurfaceSize(null));
  final fake = FakeAuthoringOffice();
  final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', fake.client());
  await tester.pumpWidget(MaterialApp(
    theme: ThemeData(extensions: const [UriColors.graphite]),
    home: Scaffold(body: OfficeWorkspace(environment: _env(saveAs: saveAs), clientFactory: () => client)),
  ));
  await tester.pumpAndSettle();
  return fake;
}

Future<void> _settle(WidgetTester tester) async {
  await tester.pump(const Duration(milliseconds: 800));       // the preview poll
  await tester.pumpAndSettle();
}

Future<void> _openAndEdit(WidgetTester tester) async {
  await tester.tap(find.byKey(const ValueKey('office-open-document')));
  await tester.pumpAndSettle();
  expect(find.byKey(const ValueKey('office-edit')), findsOneWidget, reason: 'Edit is offered on a .pptx view');
  await tester.tap(find.byKey(const ValueKey('office-edit')));
  await _settle(tester);
}

Future<void> _unmount(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox());
  await tester.pump(const Duration(seconds: 1));
}

void main() {
  testWidgets('AB-10/AB-5: edit from the presentation view, change, undo, add a slide, save through the card',
      (tester) async {
    final fake = await _pump(tester);
    await _openAndEdit(tester);
    expect(fake.calls, contains('POST /authoring/edit'));
    expect(find.byKey(const ValueKey('authoring-slide-1')), findsOneWidget);
    expect(find.byKey(const ValueKey('authoring-slide-2')), findsOneWidget);
    expect(find.text('Editing a copy · no unsaved changes'), findsOneWidget);

    // change the title: nothing is sent until Apply
    await tester.enterText(find.byKey(const ValueKey('authoring-title')), 'Quarterly Review 2026');
    await tester.pump();
    expect(fake.calls.where((c) => c.endsWith('/op')), isEmpty);
    await tester.tap(find.byKey(const ValueKey('authoring-title-apply')));
    await _settle(tester);
    expect(fake.bodies['/authoring/${fake.aid}/op']!.last['op'],
        {'op': 'set_title', 'slide': 256, 'text': 'Quarterly Review 2026'});
    expect(find.text('Editing a copy · 1 unsaved change'), findsOneWidget);

    // undo restores the earlier copy
    await tester.tap(find.byKey(const ValueKey('authoring-undo')));
    await _settle(tester);
    expect(find.text('Editing a copy · no unsaved changes'), findsOneWidget);

    // add a slide after the selected one; the new slide is selected
    await tester.tap(find.byKey(const ValueKey('authoring-add-slide')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('authoring-layout-Title Only')));
    await _settle(tester);
    expect(fake.bodies['/authoring/${fake.aid}/op']!.last['op'], {'op': 'add_slide', 'layout': 'Title Only',
        'after': 256});
    expect(find.text('Slide 3 of 3 · preview drawn by LibreOffice'), findsOneWidget);

    // While editing the URI pane gives its width to the editor; the save card opens it as a side sheet
    expect(find.byKey(const ValueKey('office-uri-pane')), findsNothing);
    expect(find.byKey(const ValueKey('office-side-sheet')), findsNothing);

    // Save shows the real card; the file is written only through the card
    await tester.tap(find.byKey(const ValueKey('authoring-save')));
    await _settle(tester);
    expect(find.byKey(const ValueKey('office-side-sheet')), findsOneWidget);
    expect(find.text('Save this presentation?'), findsOneWidget);
    expect(find.textContaining("title 'Quarterly Review 2026'"), findsOneWidget);
    expect(find.textContaining('replaces the file you opened'), findsOneWidget);
    expect(find.text('Waiting for your approval to save'), findsOneWidget);
    expect(fake.calls.where((c) => c == 'POST /a2ui/action'), isEmpty);
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await _settle(tester);
    expect(fake.calls, contains('POST /a2ui/action'));
    expect(find.text('Saved as Quarterly Review.pptx'), findsOneWidget);
    expect(find.byKey(const ValueKey('office-side-sheet')), findsNothing, reason: 'the card is answered');

    // Done after a save: the saved file is opened again in the viewer
    await tester.tap(find.byKey(const ValueKey('authoring-done')));
    await _settle(tester);
    expect(fake.calls, contains('POST /authoring/${fake.aid}/close'));
    expect(fake.calls.where((c) => c == 'POST /open/document').length, 2);
    expect(find.byKey(const ValueKey('office-edit')), findsOneWidget);
    expect(tester.takeException(), isNull);
    await _unmount(tester);
  });

  testWidgets('AB-9: a refused change is said in words; leaving with unsaved changes asks first', (tester) async {
    final fake = await _pump(tester);
    await _openAndEdit(tester);
    fake.opError = {'error': 'AUTHORING_NOT_SUPPORTED', 'detail': 'this slide has video, which URI cannot copy'};
    await tester.tap(find.byKey(const ValueKey('authoring-duplicate-slide')));
    await _settle(tester);
    expect(find.byKey(const ValueKey('authoring-error')), findsOneWidget);
    expect(find.textContaining('URI cannot do that to this presentation. (this slide has video'), findsOneWidget);

    await tester.enterText(find.byKey(const ValueKey('authoring-title')), 'Draft');
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('authoring-title-apply')));
    await _settle(tester);
    expect(find.byKey(const ValueKey('authoring-error')), findsNothing, reason: 'a later change clears the message');

    await tester.tap(find.byKey(const ValueKey('authoring-done')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('authoring-leave-dialog')), findsOneWidget);
    expect(find.textContaining('1 change is not saved. Your file has not been changed.'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('authoring-leave-keep')));
    await tester.pumpAndSettle();
    expect(find.text('Editing a copy · 1 unsaved change'), findsOneWidget);
    expect(fake.calls.where((c) => c.endsWith('/close') && c.contains('authoring')), isEmpty);

    // Back asks the same way
    await tester.tap(find.byKey(const ValueKey('office-back')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('authoring-leave-discard')));
    await _settle(tester);
    expect(fake.calls, contains('POST /authoring/${fake.aid}/close'));
    expect(find.byKey(const ValueKey('office-edit')), findsOneWidget, reason: 'back on the presentation view');
    expect(fake.calls.where((c) => c == 'POST /a2ui/action'), isEmpty);
    expect(tester.takeException(), isNull);
    await _unmount(tester);
  });

  for (final destination in ['home', 'recent']) {
    testWidgets('AB-9: $destination navigation asks before leaving an unsaved edit', (tester) async {
      final fake = await _pump(tester);
      await _openAndEdit(tester);
      await tester.enterText(find.byKey(const ValueKey('authoring-title')), 'Draft');
      await tester.pump();
      await tester.tap(find.byKey(const ValueKey('authoring-title-apply')));
      await _settle(tester);

      await tester.tap(find.byKey(ValueKey('office-nav-$destination')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('authoring-leave-dialog')), findsOneWidget);
      expect(fake.calls.where((c) => c == 'POST /authoring/${fake.aid}/close'), isEmpty);
      await tester.tap(find.byKey(const ValueKey('authoring-leave-keep')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('authoring-done')), findsOneWidget);

      final controller = tester.widget<OfficeNavPane>(find.byType(OfficeNavPane)).controller;
      controller.showView(destination == 'home' ? OfficeView.home : OfficeView.recent);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('authoring-done')), findsOneWidget,
          reason: 'a controller navigation without a dialog context cannot hide the editor');

      await tester.tap(find.byKey(ValueKey('office-nav-$destination')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('authoring-leave-discard')));
      await _settle(tester);
      expect(fake.calls.where((c) => c == 'POST /authoring/${fake.aid}/close').length, 1);
      expect(find.byKey(const ValueKey('authoring-done')), findsNothing);
      expect(find.text(destination == 'home' ? 'Office' : 'Recent'), findsWidgets);
      expect(tester.takeException(), isNull);
      await _unmount(tester);
    });
  }

  testWidgets('AB-10: New presentation from Home needs Save as, which goes to the picked new file', (tester) async {
    final fake = await _pump(tester, saveAs: r'C:\Users\me\Documents\Plan.pptx');
    expect(find.byKey(const ValueKey('office-home-new-presentation')), findsOneWidget);
    expect(find.byKey(const ValueKey('office-home-new-from-template')), findsOneWidget);
    expect(find.text('New presentation from a template'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('office-home-new-presentation')));
    await _settle(tester);
    expect(fake.calls, contains('POST /authoring/new'));
    expect(find.byKey(const ValueKey('authoring-save')), findsNothing, reason: 'a new file has only Save as');
    await tester.tap(find.byKey(const ValueKey('authoring-save-as')));
    await _settle(tester);
    expect(fake.bodies['/authoring/${fake.aid}/save']!.last, {'save_as_path': r'C:\Users\me\Documents\Plan.pptx'});
    expect(find.text('Save this presentation?'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await _unmount(tester);
  });

  for (final size in const [Size(1064, 640), Size(900, 640), Size(760, 600)]) {
    testWidgets('the presentation editor fits a ${size.width.toInt()}x${size.height.toInt()} Office region',
        (tester) async {
      await _pump(tester, size: size);
      await tester.tap(find.byKey(const ValueKey('office-home-open')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('office-edit')));
      await _settle(tester);
      expect(find.byKey(const ValueKey('authoring-slides')), findsOneWidget);
      expect(tester.takeException(), isNull);
      await _unmount(tester);
    });
  }

  testWidgets('AB-9: a refused save says why on the card and in the editor (live run a2)', (tester) async {
    final fake = await _pump(tester);
    await _openAndEdit(tester);
    await tester.enterText(find.byKey(const ValueKey('authoring-title')), 'Draft');
    await tester.pump();
    await tester.tap(find.byKey(const ValueKey('authoring-title-apply')));
    await _settle(tester);
    await tester.tap(find.byKey(const ValueKey('authoring-save')));
    await _settle(tester);
    fake.actionError = {'error': 'TARGET_CHANGED', 'detail': 'the file changed on disk since it was opened'};
    await tester.tap(find.widgetWithText(FilledButton, 'Save'));
    await _settle(tester);
    expect(find.textContaining('Refused: TARGET_CHANGED'), findsNothing);
    expect(find.text('The file changed on disk since it was opened. Save as a new file instead.'), findsOneWidget);
    expect(find.text('Waiting for your approval to save'), findsNothing);
    expect(tester.takeException(), isNull);
    await _unmount(tester);
  });
}
