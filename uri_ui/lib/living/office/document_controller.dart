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
  'ENGINE_CHECK_FAILED': 'The document engine check did not finish. Check it again.',
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
  // OD-R1: say why and what to do (the default is the user folder; other folders are the owner's to add).
  'PATH_REFUSED': 'URI may not use files in that folder yet. Choose "Folders" in the Office side bar, add the folder, '
      'then open the file again.',
  'FOLDER_IN_USE': 'Close the files from that folder first.',
  'FOLDER_NOT_ADDED': 'Only folders you added can be removed.',
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
  'UNKNOWN_PRINTER': 'That printer is no longer installed.',
  'PRINTER_NOT_SUPPORTED': 'URI cannot print to this printer without opening another program.',
  'PRINTER_UNAVAILABLE': 'The printer is not ready (offline, out of paper or needing attention).',
  'SETTING_NOT_SUPPORTED': 'The printer cannot do one of the chosen settings.',
  'PRINT_TOO_LARGE': 'Print fewer pages at a time.',
  'UNKNOWN_PRINT_JOB': 'That print job no longer exists.',
  'PRINT_TIMEOUT': 'Printing took too long and was stopped.',
  'PRINT_FAILED': 'Printing failed. Nothing more will be sent.',
  'PAPER_NOT_SUPPORTED': 'The printer does not have that paper size.',
  'PRINTER_NOT_FOUND': 'Windows could not find that printer.',
};

String officeErrorMessage(Object e) {
  if (e is SchedulerApiError) return officeErrorText[e.code] ?? 'URI Office could not do that (${e.code}).';
  if (e is TimeoutException) return 'URI Office did not answer in time.';
  return 'URI Office could not do that.';
}

enum OfficeCentre { home, list, sheet, document, workflow, print, devices }

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
class OfficeWorkspaceController extends ChangeNotifier implements OfficeRequestTarget, OfficeRequestHint {
  OfficeWorkspaceController({required this.client, this.presentation, this.environment, OfficeLayoutPrefs? prefs})
      : prefs = prefs ?? OfficeLayoutPrefs() {
    hub.registry['office.apply_change'] = _action;
    hub.registry['office.reject_change'] = _action;
    hub.registry['office.run_plan'] = _action;
    hub.registry['office.discard_plan'] = _action;
    _lastView = presentation?.officeView;
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
  int _engineTicks = 0;
  Future<void> _tick() async {
    if (_ticking || _disposed) return;
    _ticking = true;
    try {
      // The engine check runs in the background (about 2 minutes the first time): follow it until it settles.
      final lo = engine('libreoffice')?['state'];
      if (lo == null || lo == 'verifying' || lo == 'unverified') {
        _engineTicks++;
        if (_engineTicks % 4 == 0) await refresh();
      }
      final d = activeDocument == null ? null : documents[activeDocument];
      if (d != null && d.previewState == 'rendering') {
        d.view = await client.document(d.id);
        if (d.previewState == 'ready') _kindHint(d.kind);
        _notify();
      }
      if (printJob != null &&
          (printJobView == null || const {'queued', 'printing', 'waiting_approval'}.contains(printJobView!['state']))) {
        await _pollPrint();
      }
      final w = activeWorkflow;
      if (w != null && (workflowView == null || workflowView!['state'] == 'running')) {
        _takeWorkflowView(w, await client.workflow(w));
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

  /// True while the document engine has not passed its check (first use, or a check that has to run again).
  bool get engineNotReady {
    final s = engine('libreoffice')?['state'];
    return s == null || s == 'verifying' || s == 'unverified' || s == 'unavailable';
  }

  /// Why Save as PDF cannot run now, in words, or null when it can.
  String? get saveAsPdfBlockedReason {
    if (ready('save_as_pdf')) return null;
    final s = engine('libreoffice')?['state'];
    if (s == 'verifying' || s == null || s == 'unverified') {
      return 'Available once URI has checked the document engine (about 2 minutes the first time).';
    }
    final cap = capabilityList.where((c) => c['id'] == 'save_as_pdf').firstOrNull;
    return officeErrorText['${cap?['unready_reason']}'] ?? 'Not available right now.';
  }

  /// Runs the engine check again when it is not ready, then prepares the document's preview again (R5-2, real-app
  /// run 2026-10-15: a preview that was unavailable because the engine check had not finished had no way back).
  Future<void> retryPreview(String id) => _guard(() async {
        if (engineNotReady) {
          stepLabel = 'Checking the document engine… (about 2 minutes the first time)';
          _notify();
          try {
            await client.verifyEngine();
          } finally {
            stepLabel = null;
            await refresh();
          }
        }
        final v = await client.retryDocument(id);
        documents[id]?.view = v;
      });

  /// A message about an earlier action is cleared when the owner moves to another view (real-app run: the damaged
  /// file's message stayed under the spreadsheet).
  void _leaveView() {
    if (!busy) {
      lastError = null;
      lastErrorCode = null;
    }
  }

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
    _leaveView();
    _notify();
  }

  OfficeView? _lastView;

  void _onPresentation() {
    final v = presentation!.officeView;
    // Review round 3, m4: a new Office view (a command such as "uri office pdfs", or Back) moves the centre from
    // any view, not only from Home and the lists.
    if (v != _lastView) {
      _lastView = v;
      centre = v == OfficeView.home ? OfficeCentre.home : OfficeCentre.list;
    }
    _notify();
  }

  /// The sheet controller changed (a workbook opened or closed).
  void sheetChanged() => _notify();

  void showSheet() {
    centre = OfficeCentre.sheet;
    _leaveView();
    _notify();
  }

  void showDocument(String id) {
    activeDocument = id;
    centre = OfficeCentre.document;
    selectedPage = 1;
    searchMatches = const [];
    searchNotice = null;
    _leaveView();
    _notify();
  }

  void showDevices() {
    centre = OfficeCentre.devices;
    unawaited(loadPrinters(refresh: true));
    _notify();
  }

  void showWorkflow(String id) {
    activeWorkflow = id;
    workflowView = null;
    centre = OfficeCentre.workflow;
    _notify();
  }

  void back() {
    if (centre == OfficeCentre.print) {
      centre = activeDocument != null ? OfficeCentre.document : OfficeCentre.home;
      _notify();
      return;
    }
    if (centre == OfficeCentre.document || centre == OfficeCentre.workflow || centre == OfficeCentre.sheet ||
        centre == OfficeCentre.devices) {
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
        OfficeCentre.print => 'Print',
        OfficeCentre.devices => 'Printers',
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
    final cached = _outPages[key];
    if (cached != null) return cached;
    // CX-1 (readiness run r2): a page that was not drawn yet (202) was cached as empty, so it never loaded later.
    final bytes = await client.outputPage(wid, page, width);
    if (bytes != null && bytes.isNotEmpty) _outPages[key] = bytes;
    return bytes;
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
        final w = activeWorkflow!;
        final v = await client.cancelWorkflow(w);
        _clearCards(w);
        // CX-1: the conversation said "Working on it" and nothing more after a cancel. Codex R4-R6: a running task
        // may still be stopping, may have ended another way first, or the poll may already have seen the outcome;
        // every answer goes through _takeWorkflowView, which says each outcome once.
        if (v['state'] == 'running') {
          final now = workflowView?['state'];
          if (activeWorkflow == w && !_isSettled(w) && (now == null || now == 'running')) {
            workflowView = v;
            conversation.say(OfficeSpeaker.notice, 'Stopping the task…', 'Task');
          }
        } else {
          _takeWorkflowView(w, v);
        }
      });

  /// Workflow views from the poll and from owner actions arrive concurrently (Codex R5-R7). One rule for all of them:
  /// [_lastSettled] keeps, per workflow, the last settled state that was taken (one entry per task run; a session holds
  /// few). A "running" view never replaces a known settled state unless the owner resumed the task, also after a
  /// revisit cleared the visible view. Each settled state is announced once, whether the task is shown or not.
  static const _settledStates = {'ready_to_save', 'needs_review', 'failed', 'cancelled', 'saved', 'discarded'};
  final Map<String, String> _lastSettled = {};

  bool _isSettled(String wid) => _settledStates.contains(_lastSettled[wid]);

  void _takeWorkflowView(String wid, Map<String, dynamic> v, {bool resumed = false}) {
    final state = '${v['state']}';
    if (state == 'running' && !resumed && _isSettled(wid)) return;
    final first = _settledStates.contains(state) && _lastSettled[wid] != state;
    if (_settledStates.contains(state)) _lastSettled[wid] = state;
    if (activeWorkflow == wid) {
      workflowView = v;
      stepLabel = _stepLabel(v);
    }
    if (first) _announce(wid, v);
  }

  /// The one place that says a task's outcome (shown task or not) and, for the shown task, sets its labels.
  void _announce(String wid, Map<String, dynamic> v) {
    final state = v['state'];
    final shown = activeWorkflow == wid;
    final findings = (v['findings'] as List? ?? const []);
    switch (state) {
      case 'ready_to_save':
        final warn = findings.where((f) => (f as Map)['severity'] == 'warning').length;
        if (shown) stepLabel = 'Ready to save';
        conversation.say(OfficeSpeaker.uri,
            warn == 0 ? 'The PDF is ready. Check the pages, then press Save.'
                : 'The PDF is ready with $warn warning(s). Review them, then accept and save.', 'Task');
      case 'needs_review':
        if (shown) stepLabel = 'Needs review';
        conversation.say(OfficeSpeaker.uri, 'The PDF has problems that block saving. See the findings.', 'Task');
      case 'cancelled':
        if (shown) stepLabel = 'Cancelled';
        conversation.say(OfficeSpeaker.notice, _cancelledText, 'Task');
      case 'failed':
        final errs = (v['errors'] as List? ?? const []);
        final code = errs.isEmpty ? '' : '${(errs.last as Map)['code']}';
        final text = officeErrorText[code] ?? 'The task stopped.';
        if (shown) {
          stepLabel = 'Failed';
          lastErrorCode = code;
          lastError = text;
        }
        conversation.say(OfficeSpeaker.notice, text, 'Task');
    }
    unawaited(refresh());
  }

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
        final w = activeWorkflow!;
        _lastSettled.remove(w);                                // a resumed task may settle again
        // Codex R6-3: a resume can settle before its answer is read; the answer goes through the settle path.
        _takeWorkflowView(w, await client.resumeWorkflow(w, paths), resumed: true);
      });

  void _clearCards(String subject) {
    final ids = [for (final s in hub.surfaces) if (s.id.contains('.$subject.')) s.id];
    if (ids.isNotEmpty) hub.apply([for (final id in ids) {'version': 'v0.9', 'deleteSurface': {'surfaceId': id}}]);
  }

  static const _cancelledText = 'Cancelled. Nothing was saved, and your original file is unchanged.';

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
        // Codex R6-2: only the workflow this plan belongs to, and never over an outcome the poll already saw.
        final wid = '${result['subject_id'] ?? activeWorkflow}';
        if (wid == activeWorkflow && !_isSettled(wid) && !_settledStates.contains(workflowView?['state'])) {
          stepLabel = 'Starting…';
          workflowView = {...?workflowView, 'state': 'running'};
          centre = OfficeCentre.workflow;
          // Codex R7-2: said only when it is still true.
          conversation.say(OfficeSpeaker.uri, 'Working on it. Your original file is not changed.', 'Task');
        }
      } else {
        stepLabel = null;
        conversation.say(OfficeSpeaker.notice, 'Plan discarded. Nothing was done.', 'Task');
      }
    } else if (kind == 'print_job') {
      if (result['status'] == 'applied') {
        stepLabel = 'Printing…';
        conversation.say(OfficeSpeaker.uri, 'Sent to Windows for printing.', targetLabel);
      } else {
        conversation.say(OfficeSpeaker.notice, 'Not printed.', targetLabel);
        printJob = null;
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
  String get requestHint => switch (centre) {
        OfficeCentre.sheet => sheet?.workbookId != null ? 'Ask URI to change this sheet' : 'Open a workbook first',
        OfficeCentre.document => 'Ask about this ${documents[activeDocument]?.kindLabel.toLowerCase() ?? 'file'}, '
            'or say what you need',
        OfficeCentre.print => 'Ask URI Office',
        _ => 'Ask URI Office, or open a file',
      };

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

  // ---- O2P printing (A1 §A4, §A6) --------------------------------------------------------------------------------
  List<Map<String, dynamic>> printers = const [];
  bool physicalPrinter = false;
  String? printerId;
  Map<String, dynamic> printSettings = {'copies': 1, 'landscape': false, 'duplex': 'simplex', 'fit': 'fit', 'dpi': 300};
  String printPages = 'all';                     // "all" or a range like "1-3,5"
  Map<String, dynamic>? printPreviewResult;
  Map<String, dynamic>? printSource;             // {document_id} or {workflow_id}
  String? printJob;
  Map<String, dynamic>? printJobView;
  String? printNotice;

  Map<String, dynamic>? get selectedPrinter => printers.where((p) => p['id'] == printerId).firstOrNull;

  /// Opens the print panel for the document in the centre (or the task's output PDF).
  Future<void> startPrint() => _guard(() async {
        if (centre == OfficeCentre.workflow && activeWorkflow != null) {
          printSource = {'workflow_id': activeWorkflow};
        } else if (activeDocument != null && documents[activeDocument]!.previewState == 'ready') {
          printSource = {'document_id': activeDocument};
        } else {
          conversation.say(OfficeSpeaker.uri, 'Open a document first, or make a PDF of the workbook and print that.',
              targetLabel);
          return;
        }
        printPreviewResult = null;
        printJob = null;
        printJobView = null;
        await loadPrinters();
        centre = OfficeCentre.print;
      });

  Future<void> loadPrinters({bool refresh = false}) async {
    try {
      final r = refresh ? await client.refreshPrinters() : await client.printers();
      printers = [for (final p in (r['printers'] as List? ?? const [])) (p as Map).cast<String, dynamic>()];
      physicalPrinter = r['physical'] == true;
      if (printerId == null || selectedPrinter == null || selectedPrinter!['supported'] == false) {
        final usable = printers.where((p) => p['supported'] != false);
        printerId = (usable.where((p) => p['is_default'] == true).firstOrNull ?? usable.firstOrNull)?['id'] as String?;
      }
      if (printerId != null) {
        final full = await client.printer(printerId!);
        printers = [for (final p in printers) p['id'] == printerId ? full : p];
        final papers = ((full['capabilities'] as Map?)?['papers'] as List?) ?? const [];
        final names = [for (final x in papers) (x as Map)['name']];
        if (!names.contains(printSettings['paper'])) {
          printSettings = {...printSettings, 'paper': names.contains('A4') ? 'A4' : names.firstOrNull};
        }
        printSettings = {...printSettings, 'color': (full['capabilities'] as Map?)?['color'] == true};
      }
    } catch (e) {
      printNotice = officeErrorMessage(e);
    }
    _notify();
  }

  void choosePrinter(String id) {
    printerId = id;
    printPreviewResult = null;
    unawaited(loadPrinters());
  }

  void setPrintSetting(String key, Object value) {
    printSettings = {...printSettings, key: value};
    printPreviewResult = null;
    _notify();
  }

  void setPrintPages(String pages) {
    printPages = pages.trim().isEmpty ? 'all' : pages.trim();
    printPreviewResult = null;
    _notify();
  }

  /// "1-3, 5" -> [1, 2, 3, 5]; null when the text is not a page list within 1..total.
  static List<int>? parsePages(String text, int total) {
    if (text == 'all') return [for (var i = 1; i <= total; i++) i];
    final out = <int>{};
    for (final part in text.split(',')) {
      final m = RegExp(r'^(\d+)(?:\s*-\s*(\d+))?$').firstMatch(part.trim());
      if (m == null) return null;
      final a = int.parse(m.group(1)!);
      final b = m.group(2) == null ? a : int.parse(m.group(2)!);
      if (a < 1 || b > total || a > b) return null;
      for (var i = a; i <= b; i++) {
        out.add(i);
      }
    }
    return out.isEmpty ? null : (out.toList()..sort());
  }

  /// Pages of the PDF being printed: the task's output or the open document (review round 3, m3).
  int get printTotalPages {
    final s = printSource;
    if (s != null && s['workflow_id'] != null) {
      return ((workflowView?['outputs'] as List?)?.firstOrNull as Map?)?['pages'] as int? ?? 0;
    }
    return documents[s?['document_id'] ?? activeDocument]?.pages ?? 0;
  }

  bool get printPagesValid => printPages == 'all' || parsePages(printPages, printTotalPages) != null;

  Map<String, dynamic> _printBody({String? outputPath}) {
    final pages = parsePages(printPages, printTotalPages);
    if (pages == null) throw StateError('invalid page range');      // the buttons are disabled before this
    return {
      'source': printSource,
      'printer_id': printerId,
      'pages': pages,
      'settings': printSettings,
      'output_path': ?outputPath,
    };
  }

  Future<void> previewPrint() => _guard(() async {
        printPreviewResult = await client.printPreview(_printBody());
      });

  /// Shows the print card. Nothing is printed until the owner presses Print on it.
  Future<void> proposePrint() => _guard(() async {
        final p = selectedPrinter;
        if (p == null) return;
        String? out;
        final port = '${p['port']}'.toUpperCase();
        if (port.startsWith('PORTPROMPT') || port == 'FILE:') {
          final pick = environment?.pickPdfSavePath;
          if (pick == null) return;
          out = await pick('${documents[activeDocument]?.name ?? 'printed'} (printed)');
          if (out == null) return;
        }
        final r = await client.printPropose(_printBody(outputPath: out));
        hub.apply((r['messages'] as List?) ?? const []);
        printJob = r['job'] as String?;
        printPreviewResult = (r['preview'] as Map?)?.cast<String, dynamic>();
        conversation.say(OfficeSpeaker.uri, 'Check the print card. Nothing is printed until you press Print.',
            targetLabel);
      });

  Future<void> cancelPrint() => _guard(() async {
        if (printJob == null) return;
        printJobView = await client.printCancel(printJob!);
        _clearCards(printJob!);
      });

  Future<void> _pollPrint() async {
    final j = printJob;
    if (j == null) return;
    try {
      printJobView = await client.printStatus(j);
      final st = printJobView!['state'];
      if (st == 'sent') {
        stepLabel = 'Sent to the printer';
      } else if (st == 'printer_problem') {
        stepLabel = 'The printer reported a problem';
      } else if (st == 'failed') {
        stepLabel = 'Printing failed';
      }
      _notify();
    } catch (_) {}
  }

  Future<void> openPrinterSettings() async {
    final open = environment?.openPrinterSettings;
    if (open == null) return;
    await open();                                 // Windows Settings; URI installs and changes nothing
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
