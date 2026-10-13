/// URI Office M2 scripted live check (M2-AC12; the owner allowed the GPU override for it on 2026-10-12; Claude runs it
/// and sends screenshots; it is NOT the owner's own check). A separate release entry point that drives the real pieces
/// end to end: the Office service, the local Brain (Runtime v1), the locked-down WebView2 page and the app's own
/// Office region with its URI companion pane, inside the living UI's scope as the app uses them.
///
/// ```text
///   flutter build windows --release --no-tree-shake-icons -t lib/office_m2_live_check.dart
///   URI_OFFICE_STATE=<service state> URI_OFFICE_PAGE_DIR=<page> URI_OFFICE_M2_SOURCES=<a.xlsx;b.xlsx>
///   URI_OFFICE_M2_DEST=<new .xlsx path> URI_OFFICE_LIVE_OUT=<folder> <build>/uri_ui.exe
/// ```
///
/// Steps: "New from files" with the sources -> one request through the companion's Office routing (the same call the
/// composer and push-to-talk make in Office focus) -> "Accept all" -> "Save as new file" -> press "Create file" on the
/// service's approval card (the same hub action the button sends). A screenshot is written after each step and
/// `result.json` records what happened. Nothing here bypasses an approval.
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
import 'living/office/office_bridge.dart';
import 'living/office/office_client.dart';
import 'living/office/office_controller.dart';
import 'living/office/office_panel.dart';
import 'living/presentation/presentation_controller.dart';
import 'living/webview_host/webview2_office_surface.dart';
import 'services/app_state.dart';
import 'services/app_state_scope.dart';
import 'services/mock_uri_client.dart';
import 'theme/uri_theme.dart';

const instruction = 'Add a sheet named Summary. Copy the Region and Amount table with its header from S1 sheet Data '
    'to Summary A1, then copy the rows below the header from S2 sheet Data directly under it.';
const checkInstruction = 'Check my budget against the rates file and fix anything that is wrong.';
const instruction2 = 'In Summary, in the first empty row under the regions write Total, and next to it a SUM formula '
    'of all the amounts above it.';

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
  final log = <Map<String, dynamic>>[];
  final sources =
      (Platform.environment['URI_OFFICE_M2_SOURCES'] ?? '').split(';').where((p) => p.isNotEmpty).toList();
  final dest = Platform.environment['URI_OFFICE_M2_DEST'] ?? '';
  WebView2OfficeSurface? surface;

  String get outDir => Platform.environment['URI_OFFICE_LIVE_OUT'] ?? '.';

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

  late final OfficeEnvironment env = OfficeEnvironment(
    surfaceFactory: () => surface = WebView2OfficeSurface(),
    pickWorkbookPath: () async => null,
    pickSavePath: (_) async => dest,
    openExternalLink: (_) async {},
    pickSourcePaths: () async => sources,
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
                    padding: const EdgeInsets.all(8),
                    child: Text('URI Office M2 scripted live check (by Claude, not the owner): $step',
                        style: const TextStyle(fontWeight: FontWeight.w600)),
                  ),
                  Expanded(
                    child: OfficeRegion(
                      environment: env,
                      clientFactory: () => OfficeClient.discover(stateDir: Platform.environment['URI_OFFICE_STATE']),
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

  /// Check mode (M2-D10/D11): S1 is the working file to check, S2 a reference. URI lists findings and suggests fixes;
  /// the fixes are accepted and saved in place through the hash-bound card.
  Future<void> _check(OfficeController ctl) async {
    await ctl.openNew(sources);
    _record('2_files_added', {'sources': ctl.sources, 'roles_needed': ctl.rolesNeeded});
    await _snap('2_files_added');
    await ctl.instruct(checkInstruction);                // refused locally: no roles yet
    _record('2a_request_before_roles', {'sent': false, 'last': ctl.conversation.last.text});
    await ctl.setRole('S1', 'check');
    await ctl.setRole('S2', 'reference');
    _record('2b_roles', {'roles': {for (final x in ctl.sources) x['id']: x['role']}, 'working': ctl.working,
      'task': ctl.task, 'label': ctl.view?['label'], 'engine': ctl.view?['engine']});
    await _snap('2b_roles');
    final target = services.activeOfficeTarget();
    if (target == null) throw StateError('the companion is not routed to the working file');
    final sw = Stopwatch()..start();
    await target.instruct(checkInstruction);
    _record('3_checked', {'seconds': sw.elapsedMilliseconds / 1000, 'notice': ctl.notice,
      'proposed': [for (final c in ctl.proposed) '${c['sheet']}!${c['cell']}=${c['after']}'],
      'conversation': [for (final t in ctl.conversation) {'speaker': t.speaker.name, 'text': t.text}]});
    await _snap('3_checked');
    if (ctl.proposed.isNotEmpty) await ctl.decideAll('accept');
    _record('4_accepted_fixes', {'accepted': ctl.changes.where((c) => c['state'] == 'accepted').length});
    await ctl.proposeSave();
    final surfaces = ctl.hub.surfaces;
    _record('5_approval_card', {'notice': ctl.notice,
      'card_text': [for (final s in surfaces) for (final x in s.components) if (x['component'] == 'Text') x['text']]});
    await _snap('5_approval_card');
    if (surfaces.isNotEmpty) await ctl.hub.act(surfaces.first.id, 'apply');
    _record('6_saved', {'notice': ctl.notice, 'hub_errors': ctl.hub.errors});
    await _snap('6_saved');
  }

  Future<void> _run() async {
    final report = <String, dynamic>{'started': DateTime.now().toUtc().toIso8601String(), 'instruction': instruction,
      'instruction2': instruction2,
      'kind': 'M2 scripted live check run by Claude (M2-AC12), not the owner check',
      'ui': 'app OfficeRegion with the URI companion pane inside LivingScope (Office focus)',
      'sources': sources, 'dest': dest};
    try {
      OfficeController? ctl;
      for (var i = 0; i < 80 && ctl == null; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 250));
        final t = services.officeTarget.value;
        if (t is OfficeController) ctl = t;
      }
      if (ctl == null) throw StateError('the Office region did not start (service not running or page refused)');
      for (var i = 0; i < 40 && !ctl.pageReady; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 250));
      }
      _record('1_page_ready', {'page_ready': ctl.pageReady});
      await _snap('1_page_ready');

      if (Platform.environment['URI_OFFICE_M2_MODE'] == 'check') {
        await _check(ctl);
        report['security_report'] = await surface?.securityReport();
        report['result'] = 'COMPLETED_WITH_RESULT';
        report['mode'] = 'check';
        report['steps'] = log;
        report['finished'] = DateTime.now().toUtc().toIso8601String();
        File('$outDir\\result.json').writeAsStringSync(const JsonEncoder.withIndent('  ').convert(report));
        exit(0);
      }
      await ctl.openNew(sources);
      _record('2_new_from_files', {'workbook_id': ctl.workbookId, 'engine': ctl.view?['engine'],
        'sources': ctl.sources, 'notice': ctl.notice,
        'companion_routes_to_office': identical(services.activeOfficeTarget(), ctl)});
      await _snap('2_new_from_files');

      // M2-D10: the owner says what each file is for; here both are references and URI builds a new workbook.
      for (final src in List.of(ctl.sources)) {
        await ctl.setRole(src['id'] as String, 'reference');
      }
      _record('2b_roles', {'roles': {for (final x in ctl.sources) x['id']: x['role']}, 'working': ctl.working,
        'notice': ctl.notice});
      await _snap('2b_roles');

      final target = services.activeOfficeTarget();
      if (target == null) throw StateError('the companion is not routed to the new workbook');
      final sw = Stopwatch()..start();
      await target.instruct(instruction);
      _record('3_asked_uri', {'seconds': sw.elapsedMilliseconds / 1000, 'brain_message': ctl.brainMessage,
        'notice': ctl.notice, 'proposed': ctl.proposed.length,
        'sheets': [for (final s in ((ctl.view?['workbook'] as Map?)?['sheets'] as List? ?? const [])) s['name']],
        'conversation': [for (final t in ctl.conversation) {'speaker': t.speaker.name, 'text': t.text}]});
      await _snap('3_uri_proposed');

      await ctl.decideAll('accept');
      // Second request: URI now sees the accepted rows, so it can place the total under them.
      await target.instruct(instruction2);
      _record('3b_asked_total', {'brain_message': ctl.brainMessage, 'notice': ctl.notice,
        'proposed': [for (final c in ctl.proposed) '${c['sheet']}!${c['cell']}=${c['after']}']});
      await _snap('3b_asked_total');
      await ctl.decideAll('accept');
      _record('4_accepted_all', {'proposed_left': ctl.proposed.length, 'notice': ctl.notice,
        'accepted_cells': ctl.changes.where((c) => c['state'] == 'accepted' && c['kind'] == 'cell').length});
      await _snap('4_accepted_all');

      await ctl.proposeSave(saveAsPath: dest);
      final surfaces = ctl.hub.surfaces;
      _record('5_approval_card', {'surfaces': surfaces.length, 'notice': ctl.notice,
        'card_text': [for (final s in surfaces) for (final x in s.components) if (x['component'] == 'Text') x['text']]});
      await _snap('5_approval_card');

      if (surfaces.isNotEmpty) {
        await ctl.hub.act(surfaces.first.id, 'apply');   // the same action the "Create file" button sends
      }
      _record('6_created', {'notice': ctl.notice, 'hub_errors': ctl.hub.errors, 'engine_now': ctl.view?['engine'],
        'label_now': ctl.view?['label']});
      await _snap('6_created');
      report['security_report'] = await surface?.securityReport();
      report['result'] = 'COMPLETED_WITH_RESULT';
    } catch (e, st) {
      report['result'] = 'FAILED';
      report['error'] = '$e';
      report['stack'] = '$st'.split('\n').take(6).join('\n');
    }
    report['steps'] = log;
    report['finished'] = DateTime.now().toUtc().toIso8601String();
    File('$outDir\\result.json').writeAsStringSync(const JsonEncoder.withIndent('  ').convert(report));
    exit(0);
  }
}
