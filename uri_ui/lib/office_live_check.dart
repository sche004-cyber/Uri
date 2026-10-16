/// URI Office scripted live check (owner chose "2(b)" on 2026-10-12: Claude runs it and sends screenshots; it is NOT
/// the owner's own check). A separate release entry point that drives the real pieces end to end:
/// the Office service (HTTP, approvals, cell patching), the local Brain (Runtime v1), the locked-down WebView2 page and
/// the app's own Office region with its URI companion pane, inside the living UI's scope as the app uses them.
///
/// ```text
///   flutter build windows --release -t lib/office_live_check.dart
///   URI_OFFICE_STATE=<service state> URI_OFFICE_PAGE_DIR=<page> URI_OFFICE_LIVE_BOOK=<xlsx>
///   URI_OFFICE_LIVE_OUT=<folder> <build>\uri_ui.exe
/// ```
///
/// Steps: open the workbook -> send one request through the companion's Office routing (the same call the companion
/// composer and push-to-talk make in Office focus) -> accept URI's change -> propose saving -> press "Save to file" on
/// the service's approval card (the same hub action the button sends). A screenshot of the window is written after
/// each step, and `result.json` records what happened. Nothing here bypasses an approval: the save goes through the
/// hash-bound A2UI action like a click.
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

const instruction = 'In cell C2 write the text "Checked by URI".';

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
  final book = Platform.environment['URI_OFFICE_LIVE_BOOK'] ?? '';
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
    pickWorkbookPath: () async => book,
    pickSavePath: (_) async => null,
    openExternalLink: (_) async {},
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
                    child: Text('URI Office scripted live check (by Claude, not the owner): $step',
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
    await Future<void>.delayed(const Duration(milliseconds: 1200));
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

  Future<void> _run() async {
    final report = <String, dynamic>{'started': DateTime.now().toUtc().toIso8601String(), 'instruction': instruction,
      'kind': 'scripted live check run by Claude (owner choice 2b), not the owner check',
      'ui': 'app OfficeRegion with the URI companion pane inside LivingScope (Office focus)'};
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
      _record('1_page_ready', {'page_ready': ctl.pageReady, 'companion_routes_to_office': services.activeOfficeTarget() != null});
      await _snap('1_page_ready');

      await ctl.openLocal(book);
      _record('2_opened', {'workbook_id': ctl.workbookId, 'notice': ctl.notice,
        'companion_routes_to_office': identical(services.activeOfficeTarget(), ctl)});
      await _snap('2_opened');

      final target = services.activeOfficeTarget();
      if (target == null) throw StateError('the companion is not routed to the open workbook');
      final sw = Stopwatch()..start();
      await target.instruct(instruction);
      _record('3_asked_uri', {'seconds': sw.elapsedMilliseconds / 1000, 'brain_message': ctl.brainMessage,
        'notice': ctl.notice, 'proposed': ctl.proposed,
        'conversation': [for (final t in ctl.conversation) {'speaker': t.speaker.name, 'text': t.text}]});
      await _snap('3_uri_proposed');

      for (final ch in List.of(ctl.proposed)) {
        await ctl.decide(ch, 'accept');
      }
      _record('4_accepted', {'changes': ctl.changes, 'notice': ctl.notice});
      await _snap('4_accepted');

      await ctl.proposeSave();
      final surfaces = ctl.hub.surfaces;
      _record('5_approval_card', {'surfaces': surfaces.length,
        'card_text': [for (final s in surfaces) for (final x in s.components) if (x['component'] == 'Text') x['text']]});
      await _snap('5_approval_card');

      if (surfaces.isNotEmpty) {
        await ctl.hub.act(surfaces.first.id, 'apply');   // the same action the "Save to file" button sends
      }
      _record('6_saved', {'notice': ctl.notice, 'hub_errors': ctl.hub.errors});
      await _snap('6_saved');
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
