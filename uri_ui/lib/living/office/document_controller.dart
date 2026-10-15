import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../a2ui/a2ui_hub.dart';
import '../integration/scheduler_client.dart' show SchedulerApiError;
import '../presentation/presentation_controller.dart';
import 'office_bridge.dart';
import 'office_client.dart';
import 'office_controller.dart';
import 'office_conversation.dart';

/// Contract o2.1 error texts (uri_office/contracts.py ERRORS), shown with their recovery actions (refinement 7).
const officeErrorText = <String, String>{
  'ENGINE_MISSING': 'The document engine is not installed on this PC.',
  'ENGINE_INTEGRITY': 'The document engine failed its safety check and was not started.',
  'ENGINE_START_FAILED': 'The document engine did not start.',
  'ENGINE_TIMEOUT': 'The document took too long to process.',
  'ENGINE_CRASHED': 'The document engine stopped unexpectedly. It will restart on the next try.',
  'ENGINE_UNAVAILABLE': 'Previews and conversions are not available right now.',
  'WORKER_INTEGRITY': 'A helper program failed its safety check and was not run.',
  'CLM_ACTIVE': 'Windows security policy on this PC blocks the PDF renderer.',
  'PREVIEW_UNAVAILABLE': 'This page could not be shown.',
  'NO_TEXT_LAYER': 'This PDF has no searchable text (it may be a scan).',
  'UNSUPPORTED_KIND': 'URI Office opens Word, PowerPoint, Excel and PDF files only.',
  'ENCRYPTED': 'This file is password-protected, so URI cannot open it.',
  'ARCHIVE_REFUSED': 'This file looks damaged or unsafe and was not opened.',
  'XML_REFUSED': 'This file contains content URI does not read for safety reasons.',
  'FILE_TOO_LARGE': 'This file is larger than URI Office accepts.',
  'TOO_MANY_PAGES': 'This PDF has more pages than URI Office accepts.',
  'TOO_MANY_OPEN': 'Too many files are open. Close one first.',
  'PATH_REFUSED': 'URI cannot use that location.',
  'UNSAVED_CHANGES': 'Save your changes first, or discard them.',
  'CAPABILITY_PLANNED': 'This is not available yet.',
  'DESTINATION_EXISTS': 'A file with that name already exists. URI never replaces files.',
  'HAS_ERRORS': 'The result has problems that must be fixed before it can be saved.',
  'WARNINGS_NOT_ACCEPTED': 'Review the warnings and accept them before saving.',
  'INPUT_CHANGED': 'A file changed since this task started, so it was stopped.',
  'STALE_PLAN': 'The plan changed after it was shown. Review it again.',
  'WRITE_FAILED': 'The file could not be written. Nothing was left half-written.',
  'DISK_FULL': 'The disk is full. Nothing was saved.',
  'INTERRUPTED': 'This task was interrupted.',
};

String officeErrorMessage(Object e) {
  if (e is SchedulerApiError) return officeErrorText[e.code] ?? 'URI Office could not do that (${e.code}).';
  if (e is TimeoutException) return 'URI Office did not answer in time.';
  return 'URI Office could not do that.';
}

enum OfficeCentre { home, list, sheet, document, workflow }

/// An open, read-only document (DOCX, PPTX or PDF) as the service shows it.
class OfficeDocument {
  OfficeDocument(this.view);
  Map<String, dynamic> view;
  String get id => view['document_id'] as String;
  String get kind => view['kind'] as String;
  String get name => view['name'] as String? ?? '';
  int? get pages => view['pages'] as int?;
  String get previewState => ((view['preview'] as Map?)?['state'] as String?) ?? 'rendering';
  String? get previewReason => (view['preview'] as Map?)?['reason'] as String?;
  String get renderer => view['renderer'] as String? ?? 'LibreOffice';
  List<Map<String, dynamic>> get outline =>
      [for (final o in (view['outline'] as List? ?? const [])) (o as Map).cast<String, dynamic>()];
  List<Map<String, dynamic>> get findings =>
      [for (final f in (view['findings'] as List? ?? const [])) (f as Map).cast<String, dynamic>()];
  String get kindLabel => switch (kind) { 'docx' => 'Document', 'pptx' => 'Presentation', 'pdf' => 'PDF', _ => kind };
}

/// Layout and hint state kept through the existing settings store (SharedPreferences), plan §4.2 and §4.6.
class OfficeLayoutPrefs {
  double leftWidth = 260;
  double rightWidth = 380;
  bool leftCollapsed = false;
  bool rightCollapsed = false;
  bool firstVisitDismissed = false;
  final Set<String> kindHintsSeen = {};

  static const _k = 'office.layout.v1';

  Future<void> load() async {
    try {
      final p = await SharedPreferences.getInstance();
      final l = p.getStringList(_k);
      if (l == null || l.length < 5) return;
      leftWidth = double.tryParse(l[0])?.clamp(180, 360).toDouble() ?? leftWidth;
      rightWidth = double.tryParse(l[1])?.clamp(320, 520).toDouble() ?? rightWidth;
      leftCollapsed = l[2] == '1';
      rightCollapsed = l[3] == '1';
      firstVisitDismissed = l[4] == '1';
      kindHintsSeen.addAll(l.skip(5));
    } catch (_) {}
  }

  Future<void> save() async {
    try {
      final p = await SharedPreferences.getInstance();
      await p.setStringList(_k, [
        leftWidth.toStringAsFixed(0),
        rightWidth.toStringAsFixed(0),
        leftCollapsed ? '1' : '0',
        rightCollapsed ? '1' : '0',
        firstVisitDismissed ? '1' : '0',
        ...kindHintsSeen,
      ]);
    } catch (_) {}
  }
}

/// State of the Office workspace (B1): what the centre shows, the open documents and workflows, the one region-level
/// A2UI hub, the one conversation, hints, and the status strip. As the companion's [OfficeRequestTarget] it takes
/// every request made in the Office region: sheet requests go to the sheet controller unchanged; everything else goes
/// to the service's intent routing (`POST /request`).
class OfficeWorkspaceController extends ChangeNotifier implements OfficeRequestTarget {
  OfficeWorkspaceController({required this.client, this.presentation, this.environment, OfficeLayoutPrefs? prefs})
      : prefs = prefs ?? OfficeLayoutPrefs() {
    hub.registry['office.apply_change'] = _action;
    hub.registry['office.reject_change'] = _action;
    hub.registry['office.run_plan'] = _action;
    hub.registry['office.discard_plan'] = _action;
    presentation?.addListener(_onPresentation);
  }

  final OfficeClient client;
  final UiPresentationController? presentation;
  final OfficeEnvironment? environment;
  final OfficeLayoutPrefs prefs;
  final A2uiHub hub = A2uiHub();
  final OfficeConversation conversation = OfficeConversation();

  OfficeController? sheet;                       // set by the sheet view while a workbook is open
  OfficeCentre centre = OfficeCentre.home;
  Map<String, dynamic> capabilities = const {};
  List<Map<String, dynamic>> engines = const [];
  List<Map<String, dynamic>> recent = const [];
  Map<String, dynamic> workflows = const {'running': [], 'done': []};
  final Map<String, OfficeDocument> documents = {};
  String? activeDocument;
  String? activeWorkflow;
  Map<String, dynamic>? workflowView;
  int selectedPage = 1;
  int zoomWidth = 880;
  List<Map<String, dynamic>> searchMatches = const [];
  String? searchNotice;

  @override
  bool busy = false;
  String? lastError;
  String? lastErrorCode;
  String? stepLabel;
  bool contractMismatch = false;
  String? hint;                                  // at most one hint at a time (U8)
  Timer? _poll;
  bool _disposed = false;

  // ---- startup -------------------------------------------------------------------------------------------------
  Future<void> start() async {
    await prefs.load();
    try {
      final c = await client.contract();
      final major = '${c['contract']}'.split('.').first;
      contractMismatch = major != 'o2';
    } catch (_) {
      contractMismatch = false;            // an older service without /contract: O2 parts stay unavailable
    }
    await refresh();
    if (!prefs.firstVisitDismissed) {
      hint = 'Tell URI what you need, or open a file. URI shows a plan before it changes anything.';
    }
    _schedulePoll();
    _notify();
  }

  Future<void> refresh() async {
    try {
      capabilities = await client.capabilities();
    } catch (_) {}
    try {
      engines = [for (final e in ((await client.engines())['engines'] as List? ?? const [])) (e as Map).cast()];
    } catch (_) {}
    try {
      recent = [for (final e in ((await client.recent())['items'] as List? ?? const [])) (e as Map).cast()];
    } catch (_) {}
    try {
      workflows = await client.workflows();
    } catch (_) {}
    _notify();
  }

  void _schedulePoll() {
    _poll?.cancel();
    _poll = Timer.periodic(const Duration(milliseconds: 700), (_) => unawaited(_tick()));
  }

  bool _ticking = false;
  Future<void> _tick() async {
    if (_ticking || _disposed) return;
    _ticking = true;
    try {
      final d = activeDocument == null ? null : documents[activeDocument];
      if (d != null && d.previewState == 'rendering') {
        d.view = await client.document(d.id);
        if (d.previewState == 'ready') _kindHint(d.kind);
        _notify();
      }
      final w = activeWorkflow;
      if (w != null && (workflowView == null || workflowView!['state'] == 'running')) {
        workflowView = await client.workflow(w);
        stepLabel = _stepLabel(workflowView!);
        if (workflowView!['state'] != 'running') _onWorkflowSettled();
        _notify();
      }
    } catch (_) {
      // the next tick tries again; errors of owner actions are shown where they happen
    } finally {
      _ticking = false;
    }
  }

  // ---- capabilities ----------------------------------------------------------------------------------------------
  List<Map<String, dynamic>> get capabilityList =>
      [for (final c in (capabilities['capabilities'] as List? ?? const [])) (c as Map).cast<String, dynamic>()];
  List<Map<String, dynamic>> get goals =>
      [for (final g in (capabilities['goals'] as List? ?? const [])) (g as Map).cast<String, dynamic>()];

  /// Goal groups with their available capabilities; empty groups are left out (U4).
  List<(Map<String, dynamic>, List<Map<String, dynamic>>)> availableGroups() => [
        for (final g in goals)
          if (capabilityList.any((c) => c['goal'] == g['id'] && c['status'] == 'available'))
            (g, [for (final c in capabilityList) if (c['goal'] == g['id'] && c['status'] == 'available') c]),
      ];

  bool available(String id) => capabilityList.any((c) => c['id'] == id && c['status'] == 'available');
  bool ready(String id) => capabilityList.any((c) => c['id'] == id && c['ready'] == true);

  Map<String, dynamic>? engine(String id) => engines.where((e) => e['id'] == id).firstOrNull;

  // ---- navigation ------------------------------------------------------------------------------------------------
  OfficeView get view => presentation?.officeView ?? _localView;
  OfficeView _localView = OfficeView.home;

  void showView(OfficeView v) {
    if (presentation != null) {
      presentation!.setOfficeView(v);
    } else {
      _localView = v;
    }
    centre = v == OfficeView.home ? OfficeCentre.home : OfficeCentre.list;
    _notify();
  }

  void _onPresentation() {
    final v = presentation!.officeView;
    if (centre == OfficeCentre.home || centre == OfficeCentre.list) {
      centre = v == OfficeView.home ? OfficeCentre.home : OfficeCentre.list;
    }
    _notify();
  }

  void showSheet() {
    centre = OfficeCentre.sheet;
    _notify();
  }

  void showDocument(String id) {
    activeDocument = id;
    centre = OfficeCentre.document;
    selectedPage = 1;
    searchMatches = const [];
    searchNotice = null;
    _notify();
  }

  void showWorkflow(String id) {
    activeWorkflow = id;
    workflowView = null;
    centre = OfficeCentre.workflow;
    _notify();
  }

  void back() {
    if (centre == OfficeCentre.document || centre == OfficeCentre.workflow || centre == OfficeCentre.sheet) {
      centre = view == OfficeView.home ? OfficeCentre.home : OfficeCentre.list;
      _notify();
      return;
    }
    presentation?.officeBack();
  }

  String get targetLabel => switch (centre) {
        OfficeCentre.sheet => 'Sheet · ${sheet?.view?['label'] ?? ''}',
        OfficeCentre.document => '${documents[activeDocument]?.kindLabel ?? 'Document'} · '
            '${documents[activeDocument]?.name ?? ''}',
        OfficeCentre.workflow => 'Task',
        _ => 'Home',
      };

  String? get targetKind => switch (centre) {
        OfficeCentre.sheet => 'xlsx',
        OfficeCentre.document => documents[activeDocument]?.kind,
        _ => null,
      };

  // ---- documents -------------------------------------------------------------------------------------------------
  Future<void> openDocumentPath(String path) => _guard(() async {
        final v = await client.openDocument(path);
        final d = OfficeDocument(v);
        documents[d.id] = d;
        conversation.say(OfficeSpeaker.notice, 'Opened ${d.name}.', '${d.kindLabel} · ${d.name}');
        showDocument(d.id);
        unawaited(refresh());
      });

  Future<void> pickAndOpenDocument() async {
    final pick = environment?.pickDocumentPath;
    if (pick == null) return;
    final path = await pick();
    if (path != null) await openDocumentPath(path);
  }

  Future<void> closeDocument(String id) => _guard(() async {
        await client.closeDocument(id);
        documents.remove(id);
        if (activeDocument == id) {
          activeDocument = documents.keys.lastOrNull;
          centre = activeDocument == null ? OfficeCentre.home : OfficeCentre.document;
        }
      });

  final Map<String, Uint8List> _pages = {};
  Future<Uint8List?> pageImage(String docId, int page, int width) async {
    final key = '$docId/$page/$width';
    final cached = _pages[key];
    if (cached != null) return cached;
    final bytes = await client.documentPage(docId, page, width);
    if (bytes != null) {
      if (_pages.length > 120) _pages.remove(_pages.keys.first);
      _pages[key] = bytes;
    }
    return bytes;
  }

  final Map<String, Uint8List> _outPages = {};
  Future<Uint8List?> outputPage(String wid, int page, int width) async {
    final key = '$wid/$page/$width';
    return _outPages[key] ??= (await client.outputPage(wid, page, width)) ?? Uint8List(0);
  }

  void selectPage(int p) {
    selectedPage = p;
    _notify();
  }

  void setZoom(int width) {
    zoomWidth = width;
    _notify();
  }

  Future<void> search(String text) async {
    final d = activeDocument;
    if (d == null || text.trim().isEmpty) return;
    try {
      final r = await client.searchDocument(d, text.trim());
      searchMatches = [for (final m in (r['matches'] as List? ?? const [])) (m as Map).cast()];
      searchNotice = searchMatches.isEmpty ? 'No matches.' : (r['truncated'] == true ? 'Showing the first 50.' : null);
      if (searchMatches.isNotEmpty) selectedPage = searchMatches.first['page'] as int;
    } catch (e) {
      searchMatches = const [];
      searchNotice = officeErrorMessage(e);
    }
    _notify();
  }

  // ---- workflows -------------------------------------------------------------------------------------------------
  /// Save as PDF for the document or workbook in the centre (A1 §A3). Shows the plan card; nothing runs until the
  /// owner presses Run on it.
  Future<void> saveAsPdf() => _guard(() async {
        final Map<String, dynamic> input;
        if (centre == OfficeCentre.sheet && sheet?.workbookId != null) {
          input = {'workbook_id': sheet!.workbookId};
        } else if (activeDocument != null && documents[activeDocument]!.kind != 'pdf') {
          input = {'document_id': activeDocument};
        } else {
          conversation.say(OfficeSpeaker.uri, 'Open a Word, PowerPoint or Excel file first, then ask again.',
              targetLabel);
          return;
        }
        final r = await client.createWorkflow('save_as_pdf', [input]);
        hub.apply((r['messages'] as List?) ?? const []);
        activeWorkflow = r['workflow_id'] as String;
        workflowView = (r['view'] as Map).cast<String, dynamic>();
        conversation.say(OfficeSpeaker.uri, 'Here is the plan. Nothing happens until you press Run.', targetLabel);
        stepLabel = 'Waiting for your approval';
      });

  Future<void> acceptWarnings() => _guard(() async {
        workflowView = await client.acceptWarnings(activeWorkflow!);
      });

  Future<void> saveWorkflowOutput() => _guard(() async {
        final out = (workflowView?['outputs'] as List?)?.firstOrNull as Map?;
        final pick = environment?.pickPdfSavePath;
        if (out == null || pick == null) return;
        final path = await pick(out['name'] as String);
        if (path == null) return;
        final r = await client.proposeWorkflowSave(activeWorkflow!, path);
        hub.apply((r['messages'] as List?) ?? const []);
      });

  Future<void> cancelWorkflow() => _guard(() async {
        workflowView = await client.cancelWorkflow(activeWorkflow!);
        _clearCards(activeWorkflow!);
        stepLabel = null;
      });

  Future<void> resumeWorkflow() => _guard(() async {
        final pick = environment?.pickDocumentPath;
        final inputs = (workflowView?['inputs'] as List?) ?? const [];
        if (pick == null || inputs.isEmpty) return;
        final paths = <String>[];
        for (final _ in inputs) {
          final p = await pick();
          if (p == null) return;
          paths.add(p);
        }
        workflowView = await client.resumeWorkflow(activeWorkflow!, paths);
      });

  void _clearCards(String subject) {
    final ids = [for (final s in hub.surfaces) if (s.id.contains('.$subject.')) s.id];
    if (ids.isNotEmpty) hub.apply([for (final id in ids) {'version': 'v0.9', 'deleteSurface': {'surfaceId': id}}]);
  }

  void _onWorkflowSettled() {
    final v = workflowView!;
    final state = v['state'];
    final findings = (v['findings'] as List? ?? const []);
    if (state == 'ready_to_save') {
      stepLabel = 'Ready to save';
      final warn = findings.where((f) => (f as Map)['severity'] == 'warning').length;
      conversation.say(OfficeSpeaker.uri,
          warn == 0 ? 'The PDF is ready. Check the pages, then press Save.'
              : 'The PDF is ready with $warn warning(s). Review them, then accept and save.', 'Task');
    } else if (state == 'needs_review') {
      stepLabel = 'Needs review';
      conversation.say(OfficeSpeaker.uri, 'The PDF has problems that block saving. See the findings.', 'Task');
    } else if (state == 'failed') {
      final errs = (v['errors'] as List? ?? const []);
      final code = errs.isEmpty ? '' : '${(errs.last as Map)['code']}';
      stepLabel = 'Failed';
      lastErrorCode = code;
      lastError = officeErrorText[code] ?? 'The task stopped.';
      conversation.say(OfficeSpeaker.notice, lastError!, 'Task');
    }
    unawaited(refresh());
  }

  static String _stepLabel(Map<String, dynamic> v) {
    final steps = (v['steps'] as List? ?? const []).cast<Map>();
    final names = {'prepare': 'Making a safe copy', 'convert': 'Converting to PDF', 'validate': 'Checking the PDF',
                   'preview': 'Drawing the pages'};
    for (final s in steps) {
      if (s['state'] == 'running') return '${names[s['id']] ?? s['id']}…';
    }
    return v['state'] == 'running' ? 'Starting…' : '${v['state']}';
  }

  /// The one region-level handler for every office.* card (plan §4.3): sheet results go back to the sheet
  /// controller; plan and output results update the workflow.
  Future<Map<String, dynamic>> _action(Map<String, dynamic> action) async {
    final r = await client.a2uiAction(action);
    final result = (r['result'] as Map).cast<String, dynamic>();
    if (result['workbook_id'] != null && sheet != null) {
      await sheet!.handleApprovalResult(result);
    }
    final kind = result['subject_kind'];
    if (kind == 'plan') {
      if (result['status'] == 'applied') {
        stepLabel = 'Starting…';
        workflowView = {...?workflowView, 'state': 'running'};
        centre = OfficeCentre.workflow;
        conversation.say(OfficeSpeaker.uri, 'Working on it. Your original file is not changed.', 'Task');
      } else {
        stepLabel = null;
        conversation.say(OfficeSpeaker.notice, 'Plan discarded. Nothing was done.', 'Task');
      }
    } else if (kind == 'output_files') {
      if (result['status'] == 'applied') {
        stepLabel = 'Saved';
        conversation.say(OfficeSpeaker.uri, 'Saved ${result['saved_to']}.', 'Task',
            chips: const [('Show my PDFs', 'nav:pdfs')]);
        if (prefs.firstVisitDismissed == false) {
          prefs.firstVisitDismissed = true;            // the first completed workflow ends the first-visit hint
          hint = null;
          unawaited(prefs.save());
        }
      } else {
        conversation.say(OfficeSpeaker.notice, 'Not saved. The PDF is still ready if you change your mind.', 'Task');
      }
      if (activeWorkflow != null) workflowView = await client.workflow(activeWorkflow!);
      unawaited(refresh());
    }
    _notify();
    return r;
  }

  // ---- requests (OfficeRequestTarget) -----------------------------------------------------------------------------
  @override
  bool get acceptsRequests => true;

  @override
  Future<void> instruct(String text, {String? activeSheet}) async {
    final t = text.trim();
    if (t.isEmpty || busy) return;
    if (centre == OfficeCentre.sheet && sheet != null && sheet!.workbookId != null) {
      await sheet!.instruct(t, activeSheet: activeSheet);    // sheet requests are unchanged (M1/M2)
      return;
    }
    conversation.say(OfficeSpeaker.owner, t, targetLabel);
    await _route({'text': t, 'target': {'kind': ?targetKind}, 'history': conversation.ownerTurns()});
  }

  /// A goal or clarification chip: a fixed intent, the matcher is skipped.
  Future<void> chip(String intent) async {
    if (intent.startsWith('nav:')) {
      final v = OfficeView.values.where((x) => x.name == intent.substring(4)).firstOrNull;
      if (v != null) showView(v);
      return;
    }
    await _route({'text': '', 'chip': intent, 'target': {'kind': ?targetKind}});
  }

  Future<void> _route(Map<String, dynamic> body) => _guard(() async {
        final r = await client.request(body);
        switch (r['result']) {
          case 'navigate':
            final v = OfficeView.values.where((x) => x.name == r['view']).firstOrNull;
            if (v != null) {
              // A Brain-originated move goes through the presentation controller's cooldown (plan §4.4); if refused,
              // the destination is offered as a chip instead of moving silently.
              final moved = presentation?.apply(
                      ShowModeCommand(UiPresentationMode.workspace, focus: WorkspaceFocus.office, officeView: v),
                      origin: UiCommandOrigin.brain) ??
                  true;
              if (!moved) {
                conversation.say(OfficeSpeaker.uri, 'Open ${v.name}?', targetLabel, chips: [('Open ${v.name}', 'nav:${v.name}')]);
              } else {
                centre = v == OfficeView.home ? OfficeCentre.home : OfficeCentre.list;
                if (presentation == null) _localView = v;
              }
            }
          case 'planned':
            conversation.say(OfficeSpeaker.uri, '${r['message']}', targetLabel);
          case 'clarify':
            conversation.say(OfficeSpeaker.uri, "I'm not sure what you need. Choose one:", targetLabel, chips: [
              for (final c in (r['chips'] as List? ?? const []).cast<Map>()) ('${c['label']}', '${c['intent']}'),
            ]);
          case 'help':
            final avail = [for (final c in capabilityList) if (c['status'] == 'available' && c['goal'] != null) c['title']];
            final planned = [for (final c in capabilityList) if (c['status'] != 'available') c['title']];
            conversation.say(OfficeSpeaker.uri,
                'Available now: ${avail.join(', ')}. Planned, not available yet: ${planned.join(', ')}.', targetLabel);
          case 'matched':
            await _runIntent('${r['intent']}', ((r['inputs_needed'] as List?) ?? const []).cast<String>());
        }
      });

  Future<void> _runIntent(String intent, List<String> needed) async {
    switch (intent) {
      case 'save_as_pdf':
        if (needed.contains('input_file')) {
          conversation.say(OfficeSpeaker.uri, 'Which file? Open a Word, PowerPoint or Excel file first.', targetLabel,
              chips: const [('Open a document', 'open_document'), ('Open a workbook', 'open_workbook')]);
          return;
        }
        busy = false;                                       // saveAsPdf takes its own guard
        await saveAsPdf();
      case 'open_document':
      case 'view_pdf':
        busy = false;
        await pickAndOpenDocument();
      case 'open_workbook':
      case 'new_workbook_from_files':
        conversation.say(OfficeSpeaker.uri, 'Use Open workbook in the sheet view.', targetLabel);
        centre = OfficeCentre.sheet;
      default:
        conversation.say(OfficeSpeaker.uri, 'That is not available yet.', targetLabel);
    }
  }

  // ---- hints (plan §4.6; one at a time, dismissible, U6/U8) -----------------------------------------------------
  void _kindHint(String kind) {
    if (prefs.kindHintsSeen.contains(kind) || hint != null) return;
    if (workflowView != null && workflowView!['state'] == 'running') return;     // no hint while a workflow runs
    prefs.kindHintsSeen.add(kind);
    unawaited(prefs.save());
    hint = switch (kind) {
      'docx' when available('save_as_pdf') => 'You can make a PDF of this document.',
      'pptx' when available('save_as_pdf') => 'You can make a PDF of this presentation.',
      'pdf' => 'You can search this PDF and jump to a page. Ask me to open another file.',
      _ => 'Ask me to open another file.',
    };
  }

  void dismissHint() {
    if (hint != null && hint!.startsWith('Tell URI what you need')) prefs.firstVisitDismissed = true;
    hint = null;
    unawaited(prefs.save());
    _notify();
  }

  // ---- layout ----------------------------------------------------------------------------------------------------
  void setLeftWidth(double w) {
    prefs.leftWidth = w.clamp(180, 360).toDouble();
    _notify();
  }

  void setRightWidth(double w) {
    prefs.rightWidth = w.clamp(320, 520).toDouble();
    _notify();
  }

  void toggleLeft() {
    prefs.leftCollapsed = !prefs.leftCollapsed;
    unawaited(prefs.save());
    _notify();
  }

  void toggleRight() {
    prefs.rightCollapsed = !prefs.rightCollapsed;
    unawaited(prefs.save());
    _notify();
  }

  void saveLayout() => unawaited(prefs.save());

  /// Cards waiting for the owner (plan, output, sheet approval); shown as a badge when the URI pane is hidden (U13).
  int get waitingCards => hub.placed('workspace').length + (sheet?.hub == hub ? 0 : sheet?.hub.placed('workspace').length ?? 0);

  // ---- plumbing --------------------------------------------------------------------------------------------------
  Future<void> _guard(Future<void> Function() fn) async {
    if (busy) return;
    busy = true;
    lastError = null;
    lastErrorCode = null;
    _notify();
    try {
      await fn();
    } catch (e) {
      lastErrorCode = e is SchedulerApiError ? e.code : null;
      lastError = officeErrorMessage(e);
      conversation.say(OfficeSpeaker.notice, lastError!, targetLabel);
    } finally {
      busy = false;
      _notify();
    }
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _poll?.cancel();
    presentation?.removeListener(_onPresentation);
    for (final id in documents.keys.toList()) {
      unawaited(client.closeDocument(id).then((_) {}, onError: (_) {}));
    }
    hub.dispose();
    conversation.dispose();
    super.dispose();
  }
}
