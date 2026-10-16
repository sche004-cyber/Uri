// Office completion (authoring A/B/C, folders, Excel rows) real-application driver, built from the O2 driver's start and helpers;
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
  testWidgets('Office completion qualification: production main, real Core, real Office service', (t) async {
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
      // Live run i4 (UI V2 layout, 1264x681 window): the Office icon strip scrolls once many files are open, and its
      // lazily built icons above the fold do not exist until scrolled back, as a user would. Scroll it to the top once.
      // Lazily built lists (Office icon strip; the editors' slide strip, block list and item panels): scroll the list
      // that should hold the target, as a user would.
      final lists = find.byWidgetPredicate((w) => w.key is ValueKey && const ['office-nav-compact', 'authoring-slides',
          'authoring-blocks'].contains('${(w.key as ValueKey).value}') ||
          (w.key is ValueKey && ('${(w.key as ValueKey).value}'.startsWith('authoring-items-') ||
              '${(w.key as ValueKey).value}'.startsWith('authoring-block-panel-'))));
      for (final el in f.evaluate().isEmpty ? lists.evaluate().toList() : const <Element>[]) {
        final list = find.byWidget(el.widget);
        final sc = find.descendant(of: list, matching: find.byType(Scrollable)).evaluate().isNotEmpty
            ? find.descendant(of: list, matching: find.byType(Scrollable)).first
            : find.ancestor(of: list, matching: find.byType(Scrollable)).first;
        try {
          await t.drag(list, const Offset(0, 3000));
          await t.pump(const Duration(milliseconds: 200));
          if (f.evaluate().isEmpty) await t.scrollUntilVisible(f, 120, scrollable: sc, maxScrolls: 60);
        } catch (_) {}
        if (f.evaluate().isNotEmpty) {
          record('scroll', {'target': what, 'list': '${(el.widget.key as ValueKey).value}'});
          break;
        }
      }
      final strip = find.byKey(const ValueKey('office-nav-compact'));
      if (f.evaluate().isEmpty && strip.evaluate().isNotEmpty) {
        await settle(1500);
        if (f.evaluate().isEmpty) {
          await t.drag(strip, const Offset(0, 2000));
          await t.pump(const Duration(milliseconds: 300));
          if (f.evaluate().isEmpty) {
            try {
              await t.scrollUntilVisible(f, 80,
                  scrollable: find.descendant(of: strip, matching: find.byType(Scrollable)).first, maxScrolls: 30);
            } catch (_) {}
          }
          record('scroll', {'target': what, 'scrolled': 'Office icon strip', 'found': f.evaluate().isNotEmpty});
        }
      }
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

    // ================================================================== AUTHORING (milestones A/B/C, plan 11 and 12)
    // Every step is a tap or text entry on the editor's own widgets; files come from the real Windows dialogs.
    Future<void> waitEditor() async {
      await until(() => c.editor != null && c.centre == OfficeCentre.edit, 'editor open', seconds: 60);
      await until(() => c.editor!.previewReady || c.editor!.previewFailed, 'working copy preview', seconds: 240);
      await settle(1200);
    }

    Future<void> waitOp(int before) async {
      // a change can wait on a real file dialog first: wait for the change (or an error), not for "not busy"
      await until(() => (c.editor?.changes.length ?? 0) > before || c.editor?.error != null, 'change applied',
          seconds: 150);
      await until(() => !(c.editor?.busy ?? false), 'editor idle', seconds: 120);
      await settle(300);
      if (c.editor?.error != null) throw StateError('editor error: ${c.editor!.error}');
      await until(() => c.editor!.previewReady || c.editor!.previewFailed, 'preview of the change', seconds: 240);
      await settle(600);
    }

    Future<void> apply(Finder field, String text, String applyKey) async {
      await t.ensureVisible(field.first);
      await t.enterText(field.first, text);
      await t.pump(const Duration(milliseconds: 200));
      final n = c.editor!.changes.length;
      await tapFinder(find.byKey(ValueKey(applyKey)), 'apply $applyKey');
      await waitOp(n);
    }

    Future<void> approveSaveCard(String label) async {
      await until(() => find.text('Save this presentation?').evaluate().isNotEmpty ||
          find.text('Save this document?').evaluate().isNotEmpty || c.editor?.error != null, 'save card', seconds: 120);
      if (c.editor?.error != null) throw StateError('save refused: ${c.editor!.error}');
      await shot('$label-save-card');
      await tapFinder(find.widgetWithText(FilledButton, 'Save').last, 'card: Save');
      await until(() => (c.editor?.state ?? '').startsWith('Saved') || c.editor?.error != null, 'saved', seconds: 120);
      if (c.editor?.error != null) throw StateError('save failed: ${c.editor!.error}');
    }

    Future<void> done({bool discard = false}) async {
      await tapFinder(find.byKey(const ValueKey('authoring-done')), 'Done');
      await settle(800);
      if (find.byKey(const ValueKey('authoring-leave-dialog')).evaluate().isNotEmpty) {
        await shot('leave-dialog');
        await tapFinder(find.byKey(ValueKey(discard ? 'authoring-leave-discard' : 'authoring-leave-keep')),
            discard ? 'leave: discard' : 'leave: keep');
      }
      await settle(1500);
    }

    Future<void> home() async {
      await tapFinder(find.byKey(const ValueKey('office-nav-home')), 'nav Home');
      await settle(800);
    }

    // ---------------------------------------------------------------- PowerPoint (AB-8, AB-9, AB-10)
    await journey('A01-pptx-edit-structure-and-text', () async {
      await openDoc('deck', opener());
      final before = File(fpath('deck')).readAsBytesSync();
      await tapFinder(find.byKey(const ValueKey('office-edit')), 'Edit (discoverable on the presentation view)');
      await waitEditor();
      await shot('pptx-editor');
      final e = c.editor!;
      final first = e.slides.first;
      // title
      await apply(find.byKey(const ValueKey('authoring-title')), 'Quarterly Review 2026', 'authoring-title-apply');
      // add a slide after slide 1
      var n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-add-slide')), 'Add slide');
      await settle(500);
      await tapFinder(find.byKey(const ValueKey('authoring-layout-Title Only')).last, 'layout Title Only');
      await waitOp(n);
      // duplicate the chart slide (slide 11 in the fixture deck has the chart)
      final chartIndex = e.slides.indexWhere((s) => ((s['items'] as List?) ?? const []).any((it) => (it as Map)['kind'] == 'chart'));
      if (chartIndex < 0) throw StateError('no chart slide in the fixture deck');
      final chartTile = find.byKey(ValueKey('authoring-slide-${chartIndex + 1}'));
      if (chartTile.evaluate().isEmpty) {
        await t.scrollUntilVisible(chartTile, 150, maxScrolls: 80, scrollable: find.descendant(
            of: find.byKey(const ValueKey('authoring-slides')), matching: find.byType(Scrollable)).first);
        record('scroll', {'target': 'chart slide', 'list': 'authoring-slides', 'found': chartTile.evaluate().isNotEmpty});
      }
      await tapFinder(chartTile, 'select chart slide');
      await settle(400);
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-duplicate-slide')), 'Duplicate slide');
      await waitOp(n);
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-move-up')), 'Move up');
      await waitOp(n);
      // a table on the new slide, then a cell
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-insert-table')), 'Insert table');
      await waitOp(n);
      final tbl = (e.selectedSlide!['items'] as List).cast<Map>().lastWhere((it) => it['kind'] == 'table')['id'];
      await apply(find.byKey(ValueKey('authoring-cell-$tbl-0-0')), 'Budget', 'authoring-cell-$tbl-0-0-apply');
      // notes
      await apply(find.byKey(const ValueKey('authoring-notes')), 'Explain the copied chart', 'authoring-notes-apply');
      // picture through the real dialog
      queueDialog('Insert a picture', path: fpath('picture'));
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-insert-picture')), 'Insert picture');
      await waitOp(n);
      // undo and redo
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-undo')), 'Undo');
      await until(() => e.changes.length == n - 1, 'undo', seconds: 60);
      await tapFinder(find.byKey(const ValueKey('authoring-redo')), 'Redo');
      await until(() => e.changes.length == n, 'redo', seconds: 60);
      await until(() => e.previewReady, 'preview after redo', seconds: 240);
      await shot('pptx-edited');
      record('pptx edit', {'changes': e.changes, 'slides': e.slides.length, 'first_slide': first['id']});
      final now = File(fpath('deck')).readAsBytesSync();
      if (now.length != before.length || !List.generate(now.length, (i) => now[i] == before[i]).every((x) => x)) {
        throw StateError('the original changed before Save');
      }
      // Save: the card lists the changes; the file is replaced only through it
      await tapFinder(find.byKey(const ValueKey('authoring-save')), 'Save...');
      await approveSaveCard('pptx');
      await shot('pptx-saved');
      await done();
      await until(() => c.centre == OfficeCentre.document, 'viewer shows the saved file', seconds: 120);
      final reopened = c.documents[c.activeDocument]!;
      await until(() => c.documents[c.activeDocument]?.previewState != 'rendering', 'saved preview', seconds: 240);
      record('pptx reopened', {'pages': c.documents[c.activeDocument]?.pages, 'name': reopened.name});
      await shot('pptx-reopened');
    });

    await journey('A02-pptx-saved-file-exports-to-pdf', () async {
      await tapFinder(find.byKey(const ValueKey('office-save-as-pdf')), 'Save as PDF');
      await until(() => find.text('Run').evaluate().isNotEmpty, 'plan card', seconds: 60);
      await tapFinder(find.widgetWithText(FilledButton, 'Run').last, 'plan: Run');
      await until(() => c.workflowView?['state'] == 'ready_to_save' || c.workflowView?['state'] == 'needs_review' ||
          c.workflowView?['state'] == 'failed', 'PDF ready', seconds: 300);
      if (c.workflowView?['state'] == 'failed') throw StateError('PDF failed');
      record('pptx pdf', {'state': c.workflowView?['state']});
      await shot('pptx-pdf-ready');
    });

    await journey('A03-pptx-new-blank-save-as', () async {
      await home();
      await tapFinder(find.byKey(const ValueKey('office-home-new-presentation')), 'Home: New presentation');
      await waitEditor();
      final e = c.editor!;
      await apply(find.byKey(const ValueKey('authoring-title')), 'Plan for 2027', 'authoring-title-apply');
      queueDialog('Save the presentation in this folder', path: savedDir);
      await tapFinder(find.byKey(const ValueKey('authoring-save-as')), 'Save as...');
      await approveSaveCard('pptx-new');
      final saved = File('$savedDir\\New presentation.pptx');
      if (!saved.existsSync()) throw StateError('no new file');
      record('pptx new saved', {'bytes': saved.lengthSync(), 'changes_after_save': e.changes.length});
      await done();
    });

    await journey('A04-pptx-from-template', () async {
      await home();
      queueDialog('Start from a presentation or template', path: fpath('potx'));
      await tapFinder(find.byKey(const ValueKey('office-home-new-from-template')), 'Home: New from a template');
      await waitEditor();
      record('from template', {'name': c.editor!.name, 'layouts': c.editor!.layouts.length,
        'slides': c.editor!.slides.length});
      await shot('pptx-from-template');
      await done(discard: true);
    });

    await journey('A05-leave-with-unsaved-and-refused-save', () async {
      // the saved deck was reopened in A01 under a new id: open it again from the file
      await openDoc('deck', opener());
      await settle(800);
      await tapFinder(find.byKey(const ValueKey('office-edit')), 'Edit');
      await waitEditor();
      await apply(find.byKey(const ValueKey('authoring-notes')), 'Draft note', 'authoring-notes-apply');
      await done();                                          // keep editing
      if (c.editor == null) throw StateError('Keep editing closed the editor');
      // someone else changes the file on disk: the save is refused in words and nothing is replaced
      final f = File(c.editor!.savedPath!);
      final changed = f.readAsBytesSync();
      f.writeAsBytesSync([...changed, 0x20]);
      final onDisk = f.readAsBytesSync();
      await tapFinder(find.byKey(const ValueKey('authoring-save')), 'Save...');
      await until(() => find.text('Save this presentation?').evaluate().isNotEmpty, 'card', seconds: 60);
      await tapFinder(find.widgetWithText(FilledButton, 'Save').last, 'card: Save');
      await settle(2500);
      await shot('refused-target-changed');
      final unchanged = f.readAsBytesSync().length == onDisk.length;
      record('target changed', {'file_unchanged': unchanged, 'texts': visibleTexts().take(60).toList()});
      if (!unchanged) throw StateError('a changed file was replaced');
      await done(discard: true);
      if (c.editor != null) throw StateError('Discard did not close the editor');
    });

    // ---------------------------------------------------------------- Word (C-8)
    await journey('C01-docx-edit', () async {
      await openDoc('report', opener());
      await tapFinder(find.byKey(const ValueKey('office-edit')), 'Edit (Word)');
      await waitEditor();
      final e = c.editor!;
      await shot('docx-editor');
      final firstPara = e.blocks.indexWhere((b) => b['kind'] == 'paragraph' && b['locked'] == null &&
          '${b['text']}'.trim().isNotEmpty && b['level'] == null);
      await tapFinder(find.byKey(ValueKey('authoring-block-$firstPara')), 'select a body paragraph');
      await settle(300);
      await apply(find.byKey(const ValueKey('authoring-para-text')), 'This paragraph was rewritten in URI.',
          'authoring-para-text-apply');
      var n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-style')), 'Style menu');
      await settle(400);
      await tapFinder(find.byKey(const ValueKey('authoring-style-Quote')).last, 'style Quote');
      await waitOp(n);
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-para-bold')), 'Bold');
      await waitOp(n);
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-insert-table')), 'Insert table after');
      await waitOp(n);
      await apply(find.byKey(const ValueKey('authoring-wcell-0-0')), 'Item', 'authoring-wcell-0-0-apply');
      queueDialog('Insert a picture', path: fpath('picture'));
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-insert-picture')), 'Insert picture');
      await waitOp(n);
      await apply(find.byKey(const ValueKey('authoring-header')), 'Records Division', 'authoring-header-apply');
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-page-numbers')), 'Page numbers');
      await waitOp(n);
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-orientation')), 'Landscape');
      await waitOp(n);
      await t.ensureVisible(find.byKey(const ValueKey('authoring-find')));
      await t.enterText(find.byKey(const ValueKey('authoring-find')), 'the');
      await t.enterText(find.byKey(const ValueKey('authoring-replace')), 'THE');
      n = e.changes.length;
      await tapFinder(find.byKey(const ValueKey('authoring-replace-all')), 'Replace all');
      await waitOp(n);
      record('docx edit', {'changes': e.changes, 'replace': '${e.lastResult}', 'pages': e.preview?['pages']});
      await shot('docx-edited');
      await tapFinder(find.byKey(const ValueKey('authoring-save')), 'Save...');
      await approveSaveCard('docx');
      await done();
      await until(() => c.centre == OfficeCentre.document, 'viewer shows the saved document', seconds: 120);
      await shot('docx-reopened');
    });

    await journey('C02-docx-new-from-layout-save-as', () async {
      await home();
      await tapFinder(find.byKey(const ValueKey('office-home-new-document')), 'Home: New document');
      await settle(500);
      await tapFinder(find.byKey(const ValueKey('office-layout-letter')).last, 'layout Letter');
      await waitEditor();
      await tapFinder(find.byKey(const ValueKey('authoring-block-0')), 'first line');
      await apply(find.byKey(const ValueKey('authoring-para-text')), 'Records Division, Block A',
          'authoring-para-text-apply');
      queueDialog('Save the document in this folder', path: savedDir);
      await tapFinder(find.byKey(const ValueKey('authoring-save-as')), 'Save as...');
      await approveSaveCard('docx-new');
      if (!File('$savedDir\\Letter.docx').existsSync()) throw StateError('no new letter');
      await done();
    });

    await journey('C03-docx-from-template', () async {
      await home();
      queueDialog('Start from a document or template', path: fpath('dotx'));
      await tapFinder(find.byKey(const ValueKey('office-home-new-document')), 'Home: New document');
      await settle(500);
      await tapFinder(find.byKey(const ValueKey('office-layout-template')).last, 'From my template');
      await waitEditor();
      record('docx from template', {'name': c.editor!.name, 'header': c.editor!.doc['header']});
      await shot('docx-from-template');
      await done(discard: true);
    });

    // ---------------------------------------------------------------- folders the owner allows (OD-R1, FA-7)
    await journey('F01-folder-on-another-drive', () async {
      final dir = Directory(r'D:\uri-dev\uri-auth-live\owner-folder');
      dir.createSync(recursive: true);
      final target = File('${dir.path}${Platform.pathSeparator}Minutes on D.docx');
      if (!target.existsSync()) File(fpath('letter')).copySync(target.path);
      // before: refused
      queueDialog('Open a document in URI Office', path: target.path);
      await tapFinder(find.byKey(ValueKey(opener())), 'open a file on D: (not allowed yet)');
      await until(() => c.lastErrorCode != null || c.documents.values.any((d) => d.name == 'Minutes on D.docx'),
          'refusal', seconds: 60);
      record('before allow', {'code': c.lastErrorCode, 'message': c.lastError});
      if (c.lastErrorCode != 'PATH_REFUSED') throw StateError('a file on D: opened before its folder was allowed');
      await shot('folder-refused');
      // allow the folder through the real folder dialog
      await tapFinder(find.byKey(const ValueKey('office-nav-folders')), 'Folders');
      await settle(800);
      queueDialog('Allow URI to use this folder', path: dir.path);
      await tapFinder(find.byKey(const ValueKey('office-folder-add')), 'Add folder...');
      await until(() => find.byKey(ValueKey('office-folder-${dir.path}')).evaluate().isNotEmpty, 'folder listed',
          seconds: 60);
      await shot('folder-added');
      await tapFinder(find.text('Close').last, 'close Folders');
      await settle(600);
      record('after allow', {'status_message_cleared': c.lastErrorCode == null});
      queueDialog('Open a document in URI Office', path: target.path);
      await tapFinder(find.byKey(ValueKey(opener())), 'open the file on D:');
      await until(() => c.documents.values.any((d) => d.name == 'Minutes on D.docx') ||
          (c.lastErrorCode != null && c.lastErrorCode != 'PATH_REFUSED'), 'opened from D:', seconds: 90);
      if (!c.documents.values.any((d) => d.name == 'Minutes on D.docx')) throw StateError('not opened: ${c.lastError}');
      final id = c.documents.values.firstWhere((d) => d.name == 'Minutes on D.docx').id;
      await tapFinder(find.byKey(ValueKey('office-open-doc-$id')), 'file list: file on D:', seconds: 10);
      await settle(500);
      await shot('folder-file-open');
      // removal is refused while the file is open
      await tapFinder(find.byKey(const ValueKey('office-back')), 'Back');
      await tapFinder(find.byKey(const ValueKey('office-nav-folders')), 'Folders');
      await settle(800);
      await tapFinder(find.byKey(ValueKey('office-folder-remove-${dir.path}')), 'Remove (file open)');
      await settle(1500);
      record('remove while open', {'texts': visibleTexts().where((x) => x.contains('open')).take(5).toList()});
      await tapFinder(find.text('Close').last, 'close Folders');
      if (!c.documents.containsKey(id)) throw StateError('document vanished');
      record('folder journey', {'opened_from_d': true});
    });

    // ---------------------------------------------------------------- Excel rows through URI (OD-R3, XC-8; Brain runs)
    if (mode == 'brain') {
      await journey('X01-excel-insert-row-through-uri', () async {
        await tapFinder(find.byKey(const ValueKey('office-open-sheet-view')).evaluate().isNotEmpty
            ? find.byKey(const ValueKey('office-open-sheet-view')) : find.byKey(const ValueKey('office-nav-sheet')),
            'Spreadsheet');
        await until(() => c.centre == OfficeCentre.sheet, 'sheet view', seconds: 30);
        await settle(2000);
        if (c.sheet?.workbookId == null) {
          queueDialog('Open a workbook in URI Office', path: fpath('budget'));
          await tapFinder(find.text('Open file'), 'sheet: Open file');
          await until(() => c.sheet?.workbookId != null && c.sheet!.pageReady, 'workbook ready', seconds: 120);
          await settle(3000);
        }
        final sheet = c.sheet!;
        final f = find.byKey(const ValueKey('living-composer-field'));
        await tapFinder(f, 'composer');
        await t.enterText(f, 'Insert a new row above row 6 with Contingency and 5000');
        await tapFinder(find.byKey(const ValueKey('living-composer-send')), 'send');
        try {
          await until(() => find.byKey(const ValueKey('office-companion-busy')).evaluate().isNotEmpty, 'busy', seconds: 5);
        } catch (_) {}
        await until(() => find.byKey(const ValueKey('office-companion-busy')).evaluate().isEmpty, 'Brain answer',
            seconds: 300);
        await settle(1500);
        await shot('excel-row-proposal');
        record('excel row proposal', {'proposed': sheet.proposed, 'brain_message': sheet.brainMessage,
          'texts': visibleTexts().where((x) => x.contains('row') || x.contains('Row')).take(20).toList()});
        if (sheet.proposed.isEmpty) throw StateError('no proposal: ${sheet.brainMessage}');
        if (find.byKey(const ValueKey('office-accept-all')).evaluate().isNotEmpty) {
          await tapFinder(find.byKey(const ValueKey('office-accept-all')), 'Accept all');
        } else {
          final cid = sheet.proposed.first['cid'];
          await tapFinder(find.descendant(of: find.byKey(ValueKey('office-change-$cid')), matching: find.text('Accept')),
              'Accept (change card)');
        }
        await settle(1000);
        await tapFinder(find.byKey(const ValueKey('office-save')), 'Save to file');
        await until(() => find.text('Save these changes to the file?').evaluate().isNotEmpty, 'save card', seconds: 60);
        await shot('excel-row-save-card');
        final before = File(fpath('budget')).readAsBytesSync().length;
        // the card's button has the same words as the sheet's own Save button: tap the one that is not the sheet's
        final cardSave = find.ancestor(of: find.text('Save to file'), matching: find.byWidgetPredicate(
            (w) => w is FilledButton && w.key != const ValueKey('office-save')));
        await tapFinder(cardSave.first, 'card: Save to file');
        await until(() => File(fpath('budget')).readAsBytesSync().length != before, 'workbook written', seconds: 60);
        await settle(4000);
        await shot('excel-row-saved');
        record('excel row saved', {'notice': sheet.notice});
      });
    }

    record('summary', {'journeys': journeys, 'total_seconds': sw.elapsedMilliseconds / 1000});
    File('${out.path}/ui-finished.json').writeAsStringSync(jsonEncode({'finished': true, 'journeys': journeys}));
    await settle(1000);
  }, timeout: const Timeout(Duration(minutes: 40)));
}
