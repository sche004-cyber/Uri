/// URI Office O2 scripted live check of the B1 Office workspace (plan §12, A1 §A8). Run by Claude; it is NOT the
/// owner's check. A separate release entry point that drives the real pieces end to end: the Office service (HTTP,
/// engines, approvals), the app's Office workspace with its URI pane, the region-level A2UI hub and the WebView2 sheet
/// view, inside the living UI's scope as the app uses them. No Brain (GPU window not authorised): ambiguous requests
/// show clarification chips.
///
/// ```text
///   flutter build windows --release -t lib/office_o2_live_check.dart
///   URI_OFFICE_STATE=<service state> URI_O2_LIVE_DOCX=<docx> URI_O2_LIVE_PDF=<pdf> URI_O2_LIVE_XLSX=<xlsx>
///   URI_O2_LIVE_OUT=<folder> URI_O2_LIVE_PRINT_DIR=<empty folder> <build>\uri_ui.exe
/// ```
///
/// Every approval is pressed through the hub action the card's button sends (`A2uiHub.act`), never bypassed. A window
/// screenshot is written after each step and `result.json` records what happened.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';

import 'living/companion/companion_sources.dart';
import 'living/companion/effects_settings.dart';
import 'living/contracts/readiness_report.dart';
import 'living/contracts/work_items.dart';
import 'living/living_app.dart' show LivingPreferencesStore;
import 'living/living_scope.dart';
import 'living/office/document_controller.dart';
import 'living/office/office_bridge.dart';
import 'living/office/office_client.dart';
import 'living/office/office_workspace.dart';
import 'living/presentation/presentation_controller.dart';
import 'living/webview_host/webview2_office_surface.dart';
import 'services/app_state.dart';
import 'services/app_state_scope.dart';
import 'services/mock_uri_client.dart';
import 'theme/uri_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const _Live());
}

class _Live extends StatefulWidget {
  const _Live();
  @override
  State<_Live> createState() => _LiveState();
}

class _LiveState extends State<_Live> {
  final _shot = GlobalKey();
  late final AppState appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
  late final LivingServices services = _services();
  String step = 'starting';
  double? width;                                  // null = the whole window; otherwise the Office region's width
  final log = <Map<String, dynamic>>[];
  final env_ = Platform.environment;
  String get outDir => env_['URI_O2_LIVE_OUT'] ?? '.';
  int _printed = 0;

  static LivingServices _services() {
    final demo = MockCompanionSource();
    final work = MockWorkSimulator();
    return LivingServices(
      presentation: UiPresentationController(),
      companion: CompositeCompanionSource([work.companion, demo]),
      work: work,
      readiness: MockReadinessSource(),
      effects: EffectsSettings(reducedMotion: true),
      demo: demo,
    );
  }

  String _next = '';
  late final OfficeEnvironment env = OfficeEnvironment(
    surfaceFactory: () => WebView2OfficeSurface(),
    pickWorkbookPath: () async => env_['URI_O2_LIVE_XLSX'],
    pickSavePath: (_) async => null,
    openExternalLink: (_) async {},
    pickDocumentPath: () async => _next,
    pickPdfSavePath: (name) async {
      final dir = _printed++ == 0 ? outDir : (env_['URI_O2_LIVE_PRINT_DIR'] ?? outDir);
      return '$dir\\${name.replaceAll(RegExp(r'\.(docx|pptx|xlsx|pdf)$'), '')}-live${_printed}.pdf';
    },
    openPrinterSettings: () async {},             // never opened by the scripted check
  );

  @override
  void initState() {
    super.initState();
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.office);
    unawaited(_run());
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: ThemeData(brightness: Brightness.dark, extensions: const [UriColors.graphite]),
        home: AppStateScope(
          state: appState,
          child: LivingScope(
            services: services,
            child: RepaintBoundary(
              key: _shot,
              child: Scaffold(
                backgroundColor: UriColors.graphite.canvas,
                body: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  Padding(
                    padding: const EdgeInsets.all(6),
                    child: Text('URI Office O2 scripted live check (by Claude, not the owner): $step',
                        style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 12)),
                  ),
                  Expanded(
                    child: Align(
                      alignment: Alignment.topLeft,
                      child: SizedBox(
                        width: width,
                        child: OfficeWorkspace(
                          environment: env,
                          clientFactory: () => OfficeClient.discover(stateDir: env_['URI_OFFICE_STATE']),
                        ),
                      ),
                    ),
                  ),
                ]),
              ),
            ),
          ),
        ),
      );

  Future<void> _snap(String name) async {
    await Future<void>.delayed(const Duration(milliseconds: 1500));
    await WidgetsBinding.instance.endOfFrame;
    try {
      final boundary = _shot.currentContext!.findRenderObject() as RenderRepaintBoundary;
      final img = await boundary.toImage(pixelRatio: 1);
      final png = await img.toByteData(format: ui.ImageByteFormat.png);
      File('$outDir\\$name.png').writeAsBytesSync(png!.buffer.asUint8List());
    } catch (e) {
      log.add({'step': name, 'screenshot_error': '$e'});
    }
  }

  void _record(String name, Map<String, dynamic> data) {
    log.add({'step': name, 'at': DateTime.now().toUtc().toIso8601String(), ...data});
    setState(() => step = name);
  }

  Future<T> _until<T>(T? Function() f, {int seconds = 240}) async {
    for (var i = 0; i < seconds * 4; i++) {
      final v = f();
      if (v != null && v != false) return v;
      await Future<void>.delayed(const Duration(milliseconds: 250));
    }
    throw TimeoutException('waited $seconds s');
  }

  Future<void> _press(OfficeWorkspaceController c, String button) async {
    final s = c.hub.placed('workspace').last;
    final sw = Stopwatch()..start();
    await c.hub.act(s.id, button);              // the same action the card's button sends
    log.add({'pressed': button, 'surface': s.id, 'ms': sw.elapsedMilliseconds, 'hub_errors': c.hub.errors});
  }

  Future<void> _run() async {
    final report = <String, dynamic>{
      'started': DateTime.now().toUtc().toIso8601String(),
      'kind': 'scripted live check run by Claude, not the owner check',
      'ui': 'app OfficeWorkspace (B1) inside LivingScope, Office focus, real Office service, real engines',
    };
    try {
      final c = await _until(() {
        final t = services.officeTarget.value;
        return t is OfficeWorkspaceController ? t : null;
      }, seconds: 30);
      await _until(() => c.capabilityList.isNotEmpty ? true : null, seconds: 60);
      _record('01_home', {'goals': [for (final (g, caps) in c.availableGroups()) {g['id']: [for (final x in caps) x['id']]}],
        'hint': c.hint, 'engines': c.engines});
      await _snap('01_home');

      // documents: open a Word letter and preview it
      _next = env_['URI_O2_LIVE_DOCX'] ?? '';
      var sw = Stopwatch()..start();
      await c.pickAndOpenDocument();
      await _until(() => c.documents[c.activeDocument]?.previewState == 'ready' ? true : null);
      _record('02_docx_preview', {'seconds_to_ready': sw.elapsedMilliseconds / 1000,
        'doc': c.documents[c.activeDocument]?.view, 'hint': c.hint});
      await _snap('02_docx_preview');

      // Save as PDF: plan card, Run, task view, output card, Save
      await c.saveAsPdf();
      await _until(() => c.hub.placed('workspace').isNotEmpty ? true : null, seconds: 30);
      _record('03_plan_card', {'cards': c.hub.placed('workspace').length});
      await _snap('03_plan_card');
      await _press(c, 'apply');
      sw = Stopwatch()..start();
      await _until(() => c.workflowView != null && c.workflowView!['state'] != 'running' &&
          c.workflowView!['state'] != 'waiting_approval' ? true : null, seconds: 300);
      _record('04_task_done', {'seconds': sw.elapsedMilliseconds / 1000, 'workflow': c.workflowView});
      await _snap('04_task_done');
      if ((c.workflowView!['findings'] as List).any((f) => f['severity'] == 'warning')) {
        await c.acceptWarnings();
      }
      await c.saveWorkflowOutput();
      await _until(() => c.hub.placed('workspace').isNotEmpty ? true : null, seconds: 30);
      _record('05_output_card', {'cards': c.hub.placed('workspace').length});
      await _snap('05_output_card');
      await _press(c, 'apply');
      await _until(() => c.workflowView?['state'] == 'saved' ? true : null, seconds: 60);
      _record('06_saved', {'workflow': c.workflowView, 'lines': [for (final l in c.conversation.lines) '${l.target}: ${l.text}']});
      await _snap('06_saved');

      // requests without the Brain: deterministic match, navigation, clarification
      c.showDocument(c.activeDocument!);
      await c.instruct('show my PDFs');
      _record('07_navigate_pdfs', {'view': c.view.name, 'centre': c.centre.name});
      await _snap('07_navigate_pdfs');
      await c.instruct('do the usual');
      _record('08_clarify', {'last': c.conversation.lines.last.text,
        'chips': [for (final ch in c.conversation.lines.last.chips) ch.$1]});
      await _snap('08_clarify');

      // a PDF: view, zoom, search
      _next = env_['URI_O2_LIVE_PDF'] ?? '';
      await c.pickAndOpenDocument();
      await _until(() => c.documents[c.activeDocument]?.previewState == 'ready' ? true : null);
      c.setZoom(440);
      await c.search('Tender clause 37');
      _record('09_pdf_search', {'matches': c.searchMatches.take(3).toList(), 'page': c.selectedPage,
        'notice': c.searchNotice});
      await _snap('09_pdf_search');

      // printing (O2P, virtual printer under OD-U13): panel, card, Print
      if (c.available('print_document')) {
        await c.startPrint();
        c.setPrintPages('1-2');
        await c.previewPrint();
        _record('10_print_panel', {'printers': [for (final p in c.printers) p['name']],
          'physical': c.physicalPrinter, 'preview': c.printPreviewResult});
        await _snap('10_print_panel');
        await c.proposePrint();
        await _until(() => c.hub.placed('workspace').isNotEmpty ? true : null, seconds: 30);
        _record('11_print_card', {'job': c.printJob});
        await _snap('11_print_card');
        await _press(c, 'apply');
        await _until(() => const {'sent', 'failed', 'printer_problem'}.contains(c.printJobView?['state']) ? true : null,
            seconds: 120);
        _record('12_printed_virtual', {'job': c.printJobView});
        await _snap('12_printed_virtual');
      }

      // responsive widths (the Office region's width; the window stays the same)
      for (final w in [1100.0, 900.0, 700.0]) {
        setState(() => width = w);
        await Future<void>.delayed(const Duration(milliseconds: 600));
        _record('13_width_${w.toInt()}', {'width': w});
        await _snap('13_width_${w.toInt()}');
      }
      setState(() => width = null);

      // the Excel sheet view inside the workspace (WebView2), then back to the PDF without reloading the sheet
      c.showSheet();
      await Future<void>.delayed(const Duration(seconds: 2));
      final sheet = c.sheet;
      if (sheet != null && env_['URI_O2_LIVE_XLSX'] != null) {
        await sheet.openLocal(env_['URI_O2_LIVE_XLSX']!);
        await _until(() => sheet.pageReady ? true : null, seconds: 60);
        _record('14_sheet', {'workbook': sheet.view?['label'], 'page_ready': sheet.pageReady});
        await _snap('14_sheet');
        c.showDocument(c.activeDocument!);
        await Future<void>.delayed(const Duration(seconds: 1));
        c.showSheet();
        await Future<void>.delayed(const Duration(seconds: 1));
        _record('15_sheet_kept', {'same_workbook': sheet.workbookId != null, 'page_ready': sheet.pageReady});
        await _snap('15_sheet_kept');
      }
      report['result'] = 'COMPLETED_WITH_RESULT';
    } catch (e, st) {
      report['result'] = 'FAILED';
      report['error'] = '$e';
      report['stack'] = '$st'.split('\n').take(8).join('\n');
      await _snap('zz_failure');
    }
    report['steps'] = log;
    report['finished'] = DateTime.now().toUtc().toIso8601String();
    File('$outDir\\result.json').writeAsStringSync(const JsonEncoder.withIndent('  ').convert(report));
    exit(0);
  }
}
