// O2 real-application qualification driver (temporary, external; copied into the candidate's integration_test/ for
// one run and removed afterwards). It calls the ORIGINAL production main() of the candidate: real integrated worker,
// real paired Core, real Office service, real engines, and (in --brain runs) the real Runtime v1 Brain.
//
// Every Office action goes through the widgets a user sees: taps on buttons, chips, the plan and output cards and
// the composer (Flutter WidgetTester pointer and text input, not physical OS input), and the REAL Windows file dialogs,
// which harness/dialog_helper.py fills (Win32 messages to the dialog's own controls). No controller method is called
// to perform an action; the controller is only READ to check results.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:path_provider_windows/path_provider_windows.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:shared_preferences_windows/shared_preferences_windows.dart';
import 'package:shared_preferences_platform_interface/shared_preferences_platform_interface.dart';
import 'package:uri_ui/main.dart' as app;
import 'package:uri_ui/working_system_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/office/document_controller.dart';

class QualificationPaths extends PathProviderWindows {
  @override
  Future<String?> getApplicationSupportPath() async => Platform.environment['URI_QUAL_PREFS'];
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('O2 qualification: production main, real Core, real Office service', (t) async {
    final env = Platform.environment;
    final out = Directory(env['URI_QUAL_UI_OUT']!)..createSync(recursive: true);
    final fx = Directory(env['URI_QUAL_FX']!);
    final fixtures = jsonDecode(File('${fx.path}/fixtures.json').readAsStringSync()) as Map<String, dynamic>;
    String fpath(String k) => (fixtures[k] as Map)['path'] as String;
    final savedDir = fixtures['_saved_dir'] as String;
    final mode = env['URI_QUAL_MODE'] ?? 'main';
    final rows = <Map<String, Object?>>[];
    final journeys = <String, String>{};
    void record(String label, Map<String, Object?> fields) {
      rows.add({'utc': DateTime.now().toUtc().toIso8601String(), 'label': label, ...fields});
      File('${out.path}/observations.json').writeAsStringSync(const JsonEncoder.withIndent('  ').convert(rows));
    }

    void verdict(String id, String result, [Map<String, Object?> detail = const {}]) {
      journeys[id] = result;
      record('journey', {'id': id, 'result': result, ...detail});
      File('${out.path}/journeys.json').writeAsStringSync(const JsonEncoder.withIndent('  ').convert(journeys));
    }

    Future<void> until(bool Function() ok, String label, {int seconds = 180}) async {
      final end = DateTime.now().add(Duration(seconds: seconds));
      while (!ok()) {
        if (DateTime.now().isAfter(end)) throw StateError('Timeout: $label');
        await t.pump(const Duration(milliseconds: 100));
      }
    }

    Future<void> settle([int ms = 600]) async {
      for (var i = 0; i < ms ~/ 100; i++) {
        await t.pump(const Duration(milliseconds: 100));
      }
    }

    var shotNo = 0;
    List<String> visibleTexts() => [
          for (final e in find.byType(Text).evaluate())
            if (((e.widget as Text).data ?? (e.widget as Text).textSpan?.toPlainText() ?? '').trim().isNotEmpty)
              ((e.widget as Text).data ?? (e.widget as Text).textSpan?.toPlainText() ?? ''),
        ];
    Future<void> shot(String name) async {
      await settle(400);
      shotNo++;
      final file = '${shotNo.toString().padLeft(2, '0')}-$name';
      try {
        final view = t.binding.renderViews.first;
        final im = await (view.debugLayer! as OffsetLayer).toImage(Offset.zero & view.size, pixelRatio: 1);
        final bytes = await im.toByteData(format: ui.ImageByteFormat.png);
        File('${out.path}/$file.png').writeAsBytesSync(bytes!.buffer.asUint8List());
      } catch (e) {
        record('screenshot error', {'name': file, 'error': '$e'});
      }
      record('screen', {'shot': '$file.png', 'texts': visibleTexts().take(160).toList()});
    }

    void queueDialog(String title, {String? path, bool cancel = false}) {
      File('${fx.path}/pick-queue.jsonl').writeAsStringSync(
          '${jsonEncode({'title': title, if (path != null) 'path': path, if (cancel) 'cancel': true})}\n',
          mode: FileMode.append);
    }

    Future<void> tapFinder(Finder f, String what, {int seconds = 30}) async {
      await until(() => f.evaluate().isNotEmpty, 'visible: $what', seconds: seconds);
      await t.ensureVisible(f.first);
      await t.pump(const Duration(milliseconds: 100));
      await t.tap(f.first, warnIfMissed: false);
      await t.pump(const Duration(milliseconds: 150));
      record('tap', {'target': what});
    }

    Future<void> tapRail(String label) async {
      final f = find.text(label);
      if (f.evaluate().isNotEmpty) return tapFinder(f, 'rail $label');
      return tapFinder(find.byTooltip(label), 'rail $label (tooltip)');
    }

    // ------------------------------------------------------------------ start (journey 1)
    t.testTextInput.register();
    addTearDown(t.testTextInput.unregister);
    record('input transport', {'pointer': 'Flutter WidgetTester taps on real widgets', 'keyboard': 'Flutter TestTextInput',
      'file_dialogs': 'real Windows dialogs filled by harness/dialog_helper.py', 'physical_input_qualified': false,
      'core_office_brain_mocked': false, 'mode': mode});
    SharedPreferencesStorePlatform.instance = SharedPreferencesWindows()..pathProvider = QualificationPaths();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(wsShellPref, 'living');
    await prefs.setBool('uri.living.onboardingDone', true);
    final sw = Stopwatch()..start();
    app.main();
    await until(() => find.byType(WorkingSystemRoot).evaluate().isNotEmpty, 'production manifest opt-in');
    await until(() => find.byType(LivingScope).evaluate().isNotEmpty, 'real integrated worker bootstrap');
    final services = t.widget<LivingScope>(find.byType(LivingScope).first).services;
    record('production main connected', {'seconds': sw.elapsedMilliseconds / 1000, 'real_worker': services.oi != null,
      'office_environment': services.office != null});
    await settle(1500);
    await shot('start');
    verdict('J01-start', services.oi != null ? 'PASS' : 'FAIL', {'seconds': sw.elapsedMilliseconds / 1000});
    if (mode == 'brain') {
      // Brain speed with the app open but Office not yet started (to separate the app's own GPU use from Office's)
      File('${fx.path}/bench-request-app-only.json').writeAsStringSync('{}');
      await until(() => File('${fx.path}/bench-done-app-only.json').existsSync(), 'bench app-only', seconds: 600);
    }

    OfficeWorkspaceController? ctl() {
      final v = services.officeWorkspace;
      return v is OfficeWorkspaceController ? v : null;
    }

    Future<void> journey(String id, Future<void> Function() body) async {
      final s = Stopwatch()..start();
      try {
        await body();
        if (!journeys.containsKey(id)) verdict(id, 'PASS', {'seconds': s.elapsedMilliseconds / 1000});
      } catch (e, st) {
        await shot('$id-failure');
        verdict(id, 'FAIL', {'error': '$e', 'stack': '$st'.split('\n').take(6).join(' | '),
          'last_error': ctl()?.lastError, 'last_error_code': ctl()?.lastErrorCode});
      }
    }

    // ------------------------------------------------------------------ open Office (journey 2)
    await journey('J02-open-office', () async {
      if (find.text('Workspace').evaluate().isNotEmpty) {
        await tapFinder(find.text('Workspace'), 'companion: Workspace');
        await settle(1200);
      }
      await shot('workspace');
      await tapRail('Office');
      await settle(1500);
      await shot('office-first-entry');
      final starting = find.byKey(const ValueKey('office-starting')).evaluate().isNotEmpty;
      record('office starting shown', {'starting': starting});
      if (starting) await until(() => find.byKey(const ValueKey('office-starting')).evaluate().isEmpty, 'Office started by the app', seconds: 90);
      final notRunning = find.byKey(const ValueKey('office-start-error')).evaluate().isNotEmpty;
      record('office first entry', {'service_not_running_message': notRunning, 'texts': visibleTexts().take(40).toList()});
      if (notRunning) {
        // The application cannot start the Office service itself: recorded as a finding. The harness starts it the
        // way the message asks the user to ("Start URI Office"), then the user opens Office again.
        final state = env['URI_OFFICE_STATE'] ?? '${env['LOCALAPPDATA']}\\URI\\office';
        File('${fx.path}/office-start-request.json').writeAsStringSync(jsonEncode({'state': state,
          'reason': 'app showed: The URI Office service is not running (no way to start it from the app)'}));
        await until(() => File('$state\\service.json').existsSync(), 'Office service started', seconds: 120);
        await tapRail('Tasks');
        await settle(500);
        await tapRail('Office');
        await settle(1000);
      }
      final waitSw = Stopwatch()..start();
      var engineShot = false;
      await until(() {
        final c = ctl();
        if (c != null && !engineShot && c.capabilityList.isNotEmpty && !c.ready('save_as_pdf')) {
          engineShot = true;
        }
        return c != null && c.capabilityList.isNotEmpty;
      }, 'Office home with capabilities', seconds: 120);
      await shot('office-home');
      record('office home', {'seconds_to_home': waitSw.elapsedMilliseconds / 1000,
        'engines': ctl()!.engines, 'service_started_by_harness': notRunning});
      if (notRunning) {
        verdict('J02-open-office', 'PASS_WITH_FINDING', {'finding': 'service had to be started outside the app'});
      }
    });
    final c = ctl();
    if (c == null) {
      verdict('ABORT', 'FAIL', {'reason': 'no Office workspace controller'});
      File('${out.path}/ui-finished.json').writeAsStringSync('{"finished":true}');
      return;
    }

    Future<String> openDoc(String key, String opener) async {
      final before = c.documents.keys.toSet();
      queueDialog('Open a document in URI Office', path: fpath(key));
      final s = Stopwatch()..start();
      await tapFinder(find.byKey(ValueKey(opener)), 'open document ($opener)');
      await until(() => c.documents.keys.toSet().difference(before).isNotEmpty || c.lastError != null,
          'document opened', seconds: 90);
      if (c.lastError != null && c.documents.keys.toSet().difference(before).isEmpty) {
        throw StateError('open failed: ${c.lastError}');
      }
      final id = c.documents.keys.toSet().difference(before).first;
      await until(() => c.documents[id]?.previewState != 'rendering', 'preview finished', seconds: 240);
      await settle(1500);                         // page image fetch
      record('opened', {'key': key, 'seconds_to_preview': s.elapsedMilliseconds / 1000,
        'state': c.documents[id]?.previewState, 'pages': c.documents[id]?.pages, 'kind': c.documents[id]?.kind,
        'findings': c.documents[id]?.findings});
      return id;
    }

    String opener() => find.byKey(const ValueKey('office-home-open')).evaluate().isNotEmpty
        ? 'office-home-open'
        : (find.byKey(const ValueKey('office-open-document')).evaluate().isNotEmpty ? 'office-open-document' : 'office-nav-open');

    // ------------------------------------------------------------------ Word (journeys 4-5)
    String? letter;
    await journey('J04-word-open', () async {
      letter = await openDoc('report', opener());
      if (c.documents[letter]!.previewState != 'ready') throw StateError('preview ${c.documents[letter]!.previewState}');
      await shot('word-preview');
    });
    await journey('J05-word-navigate', () async {
      final p0 = c.selectedPage;
      await tapFinder(find.byKey(const ValueKey('office-page-next')), 'next page');
      await tapFinder(find.byKey(const ValueKey('office-page-next')), 'next page');
      await settle(1200);
      if (c.selectedPage != p0 + 2) throw StateError('page ${c.selectedPage} after two Next from $p0');
      await tapFinder(find.text('150%'), 'zoom 150%');
      await settle(1500);
      await shot('word-page3-150');
      final outline = find.byKey(const ValueKey('office-outline'));
      record('word outline', {'outline_visible': outline.evaluate().isNotEmpty, 'outline': c.documents[letter]?.outline.take(8).toList()});
      await tapFinder(find.text('Fit'), 'zoom Fit');
      await settle(800);
    });

    // ------------------------------------------------------------------ PowerPoint (journeys 6-7)
    String? deck;
    await journey('J06-pptx-open', () async {
      deck = await openDoc('deck', opener());
      if (c.documents[deck]!.previewState != 'ready') throw StateError('preview ${c.documents[deck]!.previewState}');
      if (c.documents[deck]!.pages != 11) throw StateError('slides ${c.documents[deck]!.pages}');
      await shot('pptx-preview');
    });
    await journey('J07-pptx-navigate', () async {
      for (var i = 0; i < 10; i++) {
        await tapFinder(find.byKey(const ValueKey('office-page-next')), 'next slide');
      }
      await settle(1500);
      if (c.selectedPage != 11) throw StateError('slide ${c.selectedPage}');
      await shot('pptx-slide11-chart');
    });

    // ------------------------------------------------------------------ PDF (journeys 8-9)
    String? tender;
    await journey('J08-pdf-open', () async {
      tender = await openDoc('tender_pdf', opener());
      if (c.documents[tender]!.pages != 60) throw StateError('pages ${c.documents[tender]!.pages}');
      await shot('pdf-preview');
    });
    await journey('J09-pdf-search-zoom-navigate', () async {
      await tapFinder(find.byKey(const ValueKey('office-search')), 'search box');
      await t.enterText(find.byKey(const ValueKey('office-search')), 'Clause 37');
      await t.testTextInput.receiveAction(TextInputAction.search);
      await t.pump(const Duration(milliseconds: 200));
      await until(() => c.searchMatches.isNotEmpty || c.searchNotice != null, 'search result', seconds: 60);
      await settle(800);
      await shot('pdf-search');
      final chip = find.text('p. 37');
      if (chip.evaluate().isNotEmpty) await tapFinder(chip, 'search result p. 37');
      await settle(1500);
      record('pdf search', {'matches': c.searchMatches.take(5).toList(), 'notice': c.searchNotice, 'page': c.selectedPage});
      if (c.selectedPage != 37) throw StateError('page ${c.selectedPage} after choosing p. 37');
      await tapFinder(find.text('100%'), 'zoom 100%');
      await tapFinder(find.byKey(const ValueKey('office-page-prev')), 'previous page');
      await settle(1500);
      await shot('pdf-p36-100');
      if (c.selectedPage != 36) throw StateError('page ${c.selectedPage}');
      // a search with no match
      await t.enterText(find.byKey(const ValueKey('office-search')), 'nonexistent phrase xyz');
      await t.testTextInput.receiveAction(TextInputAction.search);
      await until(() => c.searchNotice != null || c.searchMatches.isEmpty, 'no-match notice', seconds: 60);
      await settle(600);
      record('pdf no match', {'notice': c.searchNotice});
      await shot('pdf-no-match');
    });

    // ------------------------------------------------------------------ Save as PDF (journeys 12-19)
    Future<String> saveAsPdf(String docId, String label, {bool cancelPlan = false}) async {
      await tapFinder(find.byKey(ValueKey('office-open-doc-$docId')), 'file list: $label');
      await settle(800);
      await tapFinder(find.byKey(const ValueKey('office-save-as-pdf')), 'Save as PDF ($label)');
      await until(() => c.hub.placed('workspace').isNotEmpty, 'plan card', seconds: 60);
      await settle(800);
      await shot('plan-card-$label');
      record('plan card', {'label': label, 'texts': visibleTexts().where((s) => s.length < 200).toList().take(60).toList()});
      if (cancelPlan) {
        await tapFinder(find.text('Not now'), 'plan card: Not now');
        await settle(800);
        return '';
      }
      final s = Stopwatch()..start();
      await tapFinder(find.text('Run'), 'plan card: Run');
      await until(() => c.workflowView != null && !const {'running', 'waiting_approval', 'planned'}.contains(c.workflowView!['state']),
          'task finished', seconds: 300);
      await settle(1500);
      await shot('task-done-$label');
      record('task', {'label': label, 'seconds': s.elapsedMilliseconds / 1000, 'state': c.workflowView!['state'],
        'findings': c.workflowView!['findings']});
      if (find.text('Accept with warnings').evaluate().isNotEmpty) {
        await tapFinder(find.text('Accept with warnings'), 'Accept with warnings');
        await settle(800);
      }
      final name = label.replaceAll(RegExp(r'[^A-Za-z0-9 -]'), '');
      queueDialog('Save the PDF in this folder', path: savedDir);
      await tapFinder(find.byKey(const ValueKey('office-save-output')), 'Save… ($label)');
      await until(() => c.hub.placed('workspace').isNotEmpty || c.workflowView?['state'] == 'saved', 'output card', seconds: 90);
      await settle(800);
      await shot('output-card-$label');
      await tapFinder(find.text('Save'), 'output card: Save');
      await until(() => c.workflowView?['state'] == 'saved' || c.lastError != null, 'saved', seconds: 90);
      await settle(1000);
      await shot('saved-$label');
      final outputs = (c.workflowView?['outputs'] as List?) ?? const [];
      record('saved', {'label': label, 'state': c.workflowView?['state'], 'outputs': outputs, 'name': name,
        'error': c.lastError});
      if (c.workflowView?['state'] != 'saved') throw StateError('not saved: ${c.lastError}');
      final dest = outputs.isNotEmpty ? ((outputs.first as Map)['path'] ?? (outputs.first as Map)['destination']) : null;
      return '${dest ?? ''}';
    }

    var wordPdf = '';
    var deckPdf = '';
    await journey('J12-word-to-pdf', () async {
      wordPdf = await saveAsPdf(letter!, 'report');
    });
    await journey('J13-pptx-to-pdf', () async {
      deckPdf = await saveAsPdf(deck!, 'deck');
    });
    record('outputs', {'word_pdf': wordPdf, 'deck_pdf': deckPdf,
      'saved_dir_listing': Directory(savedDir).listSync().map((e) => e.path).toList()});

    await journey('J18-reopen-saved', () async {
      final saved = Directory(savedDir).listSync().whereType<File>().where((f) => f.path.toLowerCase().endsWith('.pdf')).toList();
      if (saved.isEmpty) throw StateError('no saved PDF in $savedDir');
      final reportPdf = saved.firstWhere((f) => f.path.contains('Annual'), orElse: () => saved.first);
      fixtures['saved_report'] = {'path': reportPdf.path};
      final id = await openDoc('saved_report', opener());
      record('reopened', {'path': reportPdf.path, 'pages': c.documents[id]?.pages,
        'source_pages': c.documents[letter]?.pages});
      if (c.documents[id]?.pages != c.documents[letter]?.pages) throw StateError('page count differs');
      await shot('reopened-saved-pdf');
    });

    // cancellation: discard a plan, then cancel a running task
    await journey('J20a-discard-plan', () async {
      await saveAsPdf(letter!, 'report-discard', cancelPlan: true);
      await shot('plan-discarded');
      if (c.hub.placed('workspace').isNotEmpty) throw StateError('card still placed');
    });

    // failure recovery: a damaged file
    await journey('J20b-damaged-file', () async {
      final before = c.documents.keys.toSet();
      queueDialog('Open a document in URI Office', path: fpath('corrupt'));
      await tapFinder(find.byKey(ValueKey(opener())), 'open damaged file');
      await until(() => c.lastError != null || c.documents.keys.toSet().difference(before).isNotEmpty, 'damaged file answer',
          seconds: 120);
      final added = c.documents.keys.toSet().difference(before);
      if (added.isNotEmpty) {
        await until(() => c.documents[added.first]?.previewState != 'rendering', 'damaged preview finished', seconds: 120);
      }
      await settle(1000);
      await shot('damaged-file');
      record('damaged', {'last_error': c.lastError, 'code': c.lastErrorCode,
        'preview': added.isNotEmpty ? c.documents[added.first]?.view : null,
        'texts': visibleTexts().where((s) => s.length < 300).toList().take(50).toList()});
      // recovery: the user can still open and view a good document
      await tapFinder(find.byKey(ValueKey('office-open-doc-$tender')), 'file list: tender (after error)');
      await settle(1200);
      if (c.activeDocument != tender) throw StateError('could not return to a good document');
      await shot('after-error-recovered');
    });

    // dialog cancelled by the user
    await journey('J20c-dialog-cancel', () async {
      final before = c.documents.length;
      queueDialog('Open a document in URI Office', cancel: true);
      await tapFinder(find.byKey(ValueKey(opener())), 'open, then cancel the dialog');
      await settle(3000);
      if (c.documents.length != before) throw StateError('a document was opened after Cancel');
      await shot('dialog-cancelled');
    });

    // ------------------------------------------------------------------ Excel in the workspace (10, 11, 14)
    await journey('J10-excel-open', () async {
      await tapFinder(find.byKey(const ValueKey('office-open-sheet-view')).evaluate().isNotEmpty
          ? find.byKey(const ValueKey('office-open-sheet-view')) : find.byKey(const ValueKey('office-nav-sheet')), 'Spreadsheet');
      await settle(2500);
      await shot('sheet-view-empty');
      queueDialog('Open a workbook in URI Office', path: fpath('budget'));
      await tapFinder(find.text('Open file'), 'sheet: Open file');
      await until(() => c.sheet?.workbookId != null && c.sheet!.pageReady, 'workbook ready', seconds: 120);
      await settle(3000);
      await shot('sheet-open');
    });
    await journey('J11-excel-companion', () async {
      final companion = find.byKey(const ValueKey('office-companion'));
      record('excel companion', {'visible': companion.evaluate().isNotEmpty,
        'texts': visibleTexts().where((s) => s.length < 200).toList().take(60).toList()});
      if (companion.evaluate().isEmpty) throw StateError('Excel companion not visible');
    });
    var sheetPdf = '';
    await journey('J14-excel-to-pdf', () async {
      await tapFinder(find.byKey(const ValueKey('office-save-as-pdf')), 'Save as PDF (sheet)');
      await until(() => c.hub.placed('workspace').isNotEmpty || (c.lastError != null && !c.busy), 'sheet plan card', seconds: 60);
      await settle(800);
      await shot('plan-card-sheet');
      if (c.hub.placed('workspace').isEmpty) throw StateError('no plan card: ${c.lastError}');
      await tapFinder(find.text('Run'), 'plan card: Run (sheet)');
      await until(() => c.workflowView != null && !const {'running', 'waiting_approval', 'planned'}.contains(c.workflowView!['state']),
          'sheet task finished', seconds: 300);
      await settle(1500);
      await shot('task-done-sheet');
      if (find.text('Accept with warnings').evaluate().isNotEmpty) await tapFinder(find.text('Accept with warnings'), 'Accept with warnings');
      queueDialog('Save the PDF in this folder', path: savedDir);
      await tapFinder(find.byKey(const ValueKey('office-save-output')), 'Save… (sheet)');
      await until(() => c.hub.placed('workspace').isNotEmpty, 'sheet output card', seconds: 90);
      await tapFinder(find.text('Save'), 'output card: Save (sheet)');
      await until(() => c.workflowView?['state'] == 'saved' || c.lastError != null, 'sheet saved', seconds: 90);
      await settle(1000);
      await shot('saved-sheet');
      sheetPdf = '${c.workflowView?['outputs']}';
      if (c.workflowView?['state'] != 'saved') throw StateError('sheet not saved: ${c.lastError}');
    });

    // ------------------------------------------------------------------ navigation and state (3, 21, 22)
    await journey('J03-navigate-views', () async {
      await tapFinder(find.byKey(const ValueKey('office-nav-recent')), 'nav Recent');
      await settle(800);
      await shot('view-recent');
      await tapFinder(find.byKey(const ValueKey('office-nav-pdfs')), 'nav PDFs');
      await settle(800);
      await shot('view-pdfs');
      await tapFinder(find.byKey(const ValueKey('office-nav-home')), 'nav Home');
      await settle(800);
      await shot('view-home-returning');
      await tapFinder(find.byKey(ValueKey('office-open-doc-$deck')), 'file list: deck');
      await settle(1000);
      await tapFinder(find.byKey(const ValueKey('office-back')), 'Back');
      await settle(800);
      record('back', {'centre': c.centre.name, 'view': c.view.name});
    });
    await journey('J21-state-preserved', () async {
      await tapFinder(find.byKey(ValueKey('office-open-doc-$tender')), 'file list: tender');
      await settle(800);
      final page = c.selectedPage;
      final docs = c.documents.length;
      await tapRail('Conversation');
      await settle(1500);
      await shot('main-conversation');
      await tapRail('Office');
      await settle(2000);
      final c2 = ctl();
      record('state after leaving', {'same_controller': identical(c2, c), 'documents': c2?.documents.length,
        'active_is_tender': c2?.activeDocument == tender, 'page': c2?.selectedPage, 'page_before': page,
        'sheet_still_open': c2?.sheet?.workbookId != null});
      await shot('office-returned');
      if (!identical(c2, c) || c2!.documents.length != docs || c2.activeDocument != tender) {
        throw StateError('Office state not kept');
      }
    });

    // ------------------------------------------------------------------ requests in the composer (15, 16 without Brain)
    await journey('J15-composer-requests', () async {
      final field = find.byKey(const ValueKey('living-composer-field'));
      record('composer', {'present': field.evaluate().isNotEmpty, 'note': 'workspace mode has no living composer; Office requests go to the Office URI pane'});
      if (field.evaluate().isEmpty) await tapFinder(find.byKey(const ValueKey('office-toggle-uri')), 'show URI pane');
      await t.enterText(field, 'show my PDFs');
      await tapFinder(find.byKey(const ValueKey('living-composer-send')), 'composer send');
      await settle(2000);
      await shot('request-show-pdfs');
      record('request show my PDFs', {'view': c.view.name, 'centre': c.centre.name,
        'last_line': c.conversation.lines.isEmpty ? null : c.conversation.lines.last.text});
      await t.enterText(field, 'do the usual');
      await tapFinder(find.byKey(const ValueKey('living-composer-send')), 'composer send');
      await until(() => !c.busy, 'answer', seconds: 120);
      await settle(1500);
      await shot('request-do-the-usual');
      record('request do the usual', {'last_line': c.conversation.lines.isEmpty ? null : c.conversation.lines.last.text,
        'chips': c.conversation.lines.isEmpty ? [] : [for (final ch in c.conversation.lines.last.chips) ch.$1]});
      await t.enterText(field, 'convert this to PDF');
      await tapFinder(find.byKey(const ValueKey('living-composer-send')), 'composer send');
      await until(() => !c.busy, 'answer', seconds: 120);
      await settle(1500);
      await shot('request-convert-to-pdf');
      record('request convert', {'last_line': c.conversation.lines.isEmpty ? null : c.conversation.lines.last.text,
        'cards': c.hub.placed('workspace').length});
      if (find.text('Not now').evaluate().isNotEmpty) await tapFinder(find.text('Not now'), 'Not now');
    });

    // ------------------------------------------------------------------ Brain journeys (B5; only in --brain runs)
    if (mode == 'brain') {
      Future<Map<String, Object?>> ask(String label, String text, {String? targetDoc}) async {
        if (targetDoc != null) {
          await tapFinder(find.byKey(ValueKey('office-open-doc-$targetDoc')), 'file list ($label)');
          await settle(800);
        }
        final lines0 = c.conversation.lines.length;
        final cards0 = c.hub.placed('workspace').length;
        final s = Stopwatch()..start();
        await t.enterText(find.byKey(const ValueKey('living-composer-field')), text);
        await tapFinder(find.byKey(const ValueKey('living-composer-send')), 'composer send ($label)');
        try {
          await until(() => c.busy, 'busy', seconds: 5);
        } catch (_) {}
        await until(() => !c.busy, 'Brain answer ($label)', seconds: 240);
        await settle(1200);
        await shot('brain-$label');
        final fresh = c.conversation.lines.skip(lines0).toList();
        final row = <String, Object?>{'label': label, 'request': text, 'seconds': s.elapsedMilliseconds / 1000,
          'target': targetDoc == null ? null : c.documents[targetDoc]?.kind,
          'answer': [for (final l in fresh) l.text],
          'chips': fresh.isEmpty ? [] : [for (final ch in fresh.last.chips) ch.$1],
          'new_cards': c.hub.placed('workspace').length - cards0, 'view': c.view.name, 'centre': c.centre.name};
        record('brain request', row);
        if (find.text('Not now').evaluate().isNotEmpty) await tapFinder(find.text('Not now'), 'Not now');
        await settle(500);
        return row;
      }

      await journey('B5-ambiguous-to-plan', () async {
        final r = await ask('email-format', 'I need it in a format I can email', targetDoc: letter);
        if ((r['new_cards'] as int) < 1) throw StateError('no plan card: ${r['answer']}');
      });
      await journey('B5-ambiguous-pptx', () async {
        final r = await ask('ready-to-share', 'make this ready to share', targetDoc: deck);
        if ((r['new_cards'] as int) < 1) throw StateError('no plan card: ${r['answer']}');
      });
      await journey('B5-unclear-clarifies', () async {
        final r = await ask('send-it', 'send it to the department', targetDoc: letter);
        if ((r['new_cards'] as int) != 0) throw StateError('acted on an unclear request');
        if ((r['chips'] as List).isEmpty && (r['answer'] as List).isEmpty) throw StateError('no clarification');
      });
      await journey('B5-unsupported-said-plainly', () async {
        final r = await ask('fix-spelling', 'fix the spelling', targetDoc: letter);
        if ((r['new_cards'] as int) != 0) throw StateError('acted on an unsupported request');
      });
      await journey('B5-pdf-planned', () async {
        final r = await ask('what-about', 'what is this about', targetDoc: tender);
        if ((r['new_cards'] as int) != 0) throw StateError('acted on a planned (O4) request');
      });
      await journey('B5-continuity', () async {
        final r1 = await ask('report-too', 'and do the same for the report', targetDoc: letter);
        record('continuity', {'first': r1});
      });
      await journey('B5-excel-brain', () async {
        await tapFinder(find.byKey(const ValueKey('office-open-sheet-view')).evaluate().isNotEmpty
            ? find.byKey(const ValueKey('office-open-sheet-view')) : find.byKey(const ValueKey('office-nav-sheet')), 'Spreadsheet');
        await settle(2000);
        final sheet = c.sheet;
        if (sheet == null || sheet.workbookId == null) throw StateError('no workbook open');
        final s = Stopwatch()..start();
        // In the app the sheet companion holds the shared living composer (keys living-composer-*).
        final f = find.byKey(const ValueKey('office-ask')).evaluate().isNotEmpty
            ? find.byKey(const ValueKey('office-ask')) : find.byKey(const ValueKey('living-composer-field'));
        final send = find.byKey(const ValueKey('office-ask')).evaluate().isNotEmpty
            ? find.byKey(const ValueKey('office-ask-send')) : find.byKey(const ValueKey('living-composer-send'));
        await tapFinder(f, 'sheet ask box');
        await t.enterText(f, 'Add a row for Travel with 25000 below Digitization');
        await tapFinder(send, 'sheet ask send');
        try {
          await until(() => find.byKey(const ValueKey('office-companion-busy')).evaluate().isNotEmpty, 'busy', seconds: 5);
        } catch (_) {}
        await until(() => find.byKey(const ValueKey('office-companion-busy')).evaluate().isEmpty, 'Excel Brain answer',
            seconds: 300);
        await settle(1500);
        await shot('excel-brain-changes');
        final changes = find.byWidgetPredicate((w) => w.key is ValueKey && '${(w.key as ValueKey).value}'.startsWith('office-change-'));
        record('excel brain', {'seconds': s.elapsedMilliseconds / 1000, 'change_cards': changes.evaluate().length,
          'texts': visibleTexts().where((x) => x.length < 200).toList().take(60).toList()});
        if (changes.evaluate().isEmpty) throw StateError('no change suggested');
        if (find.byKey(const ValueKey('office-reject-all')).evaluate().isNotEmpty) {
          await tapFinder(find.byKey(const ValueKey('office-reject-all')), 'Reject all');
          await settle(800);
        }
      });
      await journey('B5-brain-speed-with-office', () async {
        // Brain decode speed while the app, the Office service, LibreOffice and the PDF workers are all running
        File('${fx.path}/bench-request-with-office.json').writeAsStringSync('{}');
        await until(() => File('${fx.path}/bench-done-with-office.json').existsSync(), 'bench done', seconds: 600);
      });
      await journey('B5-C1-corpus-http', () async {
        // the 16 ambiguous corpus requests through this run's live Office service and Brain (HTTP, by the harness)
        File('${fx.path}/corpus-request.json').writeAsStringSync('{}');
        await until(() => File('${fx.path}/corpus-done.json').existsSync(), 'corpus done', seconds: 1800);
        record('corpus', {'done': File('${fx.path}/corpus-done.json').readAsStringSync()});
      });
      await journey('B5-concurrent', () async {
        // a conversion and a Brain request at the same time
        await tapFinder(find.byKey(ValueKey('office-open-doc-$deck')), 'file list: deck');
        await settle(600);
        await tapFinder(find.byKey(const ValueKey('office-save-as-pdf')), 'Save as PDF (deck, concurrent)');
        await until(() => c.hub.placed('workspace').isNotEmpty, 'plan card', seconds: 60);
        final s = Stopwatch()..start();
        await tapFinder(find.text('Run'), 'Run (concurrent)');
        await t.enterText(find.byKey(const ValueKey('living-composer-field')), 'make this ready to share');
        await tapFinder(find.byKey(const ValueKey('living-composer-send')), 'composer send (concurrent)');
        await until(() => c.workflowView != null && !const {'running', 'waiting_approval', 'planned'}.contains(c.workflowView!['state']),
            'concurrent task finished', seconds: 300);
        await until(() => !c.busy, 'concurrent Brain answer', seconds: 240);
        await settle(1500);
        await shot('concurrent');
        record('concurrent', {'seconds': s.elapsedMilliseconds / 1000, 'task_state': c.workflowView?['state']});
        if (find.text('Not now').evaluate().isNotEmpty) await tapFinder(find.text('Not now'), 'Not now');
      });
    }

    // printing must be off in O2 runs
    await journey('J-print-off', () async {
      final printBtn = find.byKey(const ValueKey('office-print'));
      final printers = find.byKey(const ValueKey('office-nav-printers'));
      record('print entry points', {'print_button': printBtn.evaluate().isNotEmpty, 'printers_nav': printers.evaluate().isNotEmpty,
        'print_capability': c.capabilityList.where((x) => x['id'] == 'print_document').toList()});
      if (printBtn.evaluate().isNotEmpty) throw StateError('Print button shown with printing off');
    });

    // keyboard shortcuts (synthetic key events through Flutter, not physical keys)
    await journey('J-keyboard', () async {
      final left = c.prefs.leftCollapsed;
      await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await t.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
      await t.sendKeyEvent(LogicalKeyboardKey.keyB);
      await t.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
      await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await settle(800);
      record('ctrl+shift+b', {'left_before': left, 'left_after': c.prefs.leftCollapsed});
      await shot('ctrl-shift-b');
      if (c.prefs.leftCollapsed == left) throw StateError('Ctrl+Shift+B did nothing');
      await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await t.sendKeyDownEvent(LogicalKeyboardKey.shiftLeft);
      await t.sendKeyEvent(LogicalKeyboardKey.keyB);
      await t.sendKeyUpEvent(LogicalKeyboardKey.shiftLeft);
      await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await settle(500);
      await t.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await t.sendKeyEvent(LogicalKeyboardKey.keyK);
      await t.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await settle(600);
      final focused = FocusManager.instance.primaryFocus;
      record('ctrl+k', {'focused': '$focused', 'is_composer': identical(focused, services.composerFocus)});
      await shot('ctrl-k');
      if (!identical(focused, services.composerFocus)) throw StateError('Ctrl+K did not put the cursor in the request box');
    });

    // return to the main URI workspace (22)
    await journey('J22-return-main', () async {
      await tapRail('Conversation');
      await settle(1500);
      await shot('final-main-workspace');
    });

    record('summary', {'journeys': journeys, 'total_seconds': sw.elapsedMilliseconds / 1000, 'sheet_pdf': sheetPdf});
    File('${out.path}/ui-finished.json').writeAsStringSync(jsonEncode({'finished': true, 'journeys': journeys}));
    await settle(1000);
  }, timeout: const Timeout(Duration(minutes: 40)));
}
