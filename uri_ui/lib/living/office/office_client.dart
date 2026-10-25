import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../integration/scheduler_client.dart' show SchedulerApiError;
import 'writing_assist.dart';

/// HTTP client for the URI Office service (`python -m uri_office.service run`), the same discovery as the
/// scheduler: `<state>/service.json` gives the port, `<state>/api-token` (current user only) the bearer token.
/// The state folder is `URI_OFFICE_STATE`, or `%LOCALAPPDATA%\URI\office`.
///
/// Only Dart talks to the service; the sheet page never does (it has no network access at all).
class OfficeClient implements WritingService {
  OfficeClient._(this._base, this._token, {http.Client? client}) : _http = client ?? http.Client();

  final Uri _base;
  final String _token;
  final http.Client _http;

  static String defaultStateDir() {
    final env = Platform.environment['URI_OFFICE_STATE'];
    if (env != null && env.isNotEmpty) return env;
    final local = Platform.environment['LOCALAPPDATA'] ?? '';
    return '$local\\URI\\office';
  }

  /// Null when the service is not running (no service.json or token).
  static OfficeClient? discover({String? stateDir, http.Client? client}) {
    final dir = stateDir ?? defaultStateDir();
    try {
      final svc = jsonDecode(File('$dir${Platform.pathSeparator}service.json').readAsStringSync()) as Map;
      final token = File('$dir${Platform.pathSeparator}api-token').readAsStringSync().trim();
      final port = svc['port'];
      if (port is! int || token.isEmpty) return null;
      return OfficeClient._(Uri.parse('http://127.0.0.1:$port'), token, client: client);
    } catch (_) {
      return null;
    }
  }

  /// For tests: a client against a given base URL and token.
  factory OfficeClient.forTest(Uri base, String token, http.Client client) => OfficeClient._(base, token, client: client);

  Map<String, String> get _headers => {'Authorization': 'Bearer $_token', 'Content-Type': 'application/json'};

  Future<Map<String, dynamic>> _get(String path) async {
    final r = await _http.get(_base.resolve(path), headers: _headers).timeout(const Duration(seconds: 30));
    return _decode(r);
  }

  Future<Map<String, dynamic>> _post(String path, [Map<String, dynamic> body = const {}]) async {
    final r = await _http
        .post(_base.resolve(path), headers: _headers, body: jsonEncode(body))
        .timeout(const Duration(seconds: 240));   // a Brain turn can take minutes
    return _decode(r);
  }

  Map<String, dynamic> _decode(http.Response r) {
    final body = r.body.isEmpty ? <String, dynamic>{} : jsonDecode(r.body);
    if (r.statusCode != 200) throw SchedulerApiError.from(body);
    return (body as Map).cast<String, dynamic>();
  }

  Future<Map<String, dynamic>> status() => _get('/status');

  /// True when the service recorded in service.json answers on its port, accepts its token and serves the Office
  /// contract; false for a service.json left behind by a service that has ended, or another program on that port
  /// (Codex O2-R5-03, rounds 1 and 2).
  Future<bool> reachable() async {
    try {
      final r = await _http.get(_base.resolve('/contract'), headers: _headers).timeout(const Duration(seconds: 3));
      if (r.statusCode != 200) return false;
      final body = jsonDecode(r.body);
      return body is Map && body['contract'] is String && (body['contract'] as String).isNotEmpty;
    } catch (_) {
      return false;
    }
  }
  Future<Map<String, dynamic>> openLocal(String path) => _post('/open/local', {'path': path});
  Future<Map<String, dynamic>> openGoogle(String url) => _post('/open/google', {'url': url});
  Future<Map<String, dynamic>> view(String wid) => _get('/workbook/$wid');
  /// M2: a new workbook built from source files (the paths come from the owner's file picker only).
  Future<Map<String, dynamic>> openNew(List<String> paths) => _post('/open/new', {'paths': paths});
  Future<Map<String, dynamic>> addSources(String wid, List<String> paths) =>
      _post('/workbook/$wid/sources', {'paths': paths});
  /// M2-D10: what each added file is for ({"S1": "reference" | "check" | "edit"}).
  Future<Map<String, dynamic>> setRoles(String wid, Map<String, String> roles) =>
      _post('/workbook/$wid/roles', {'roles': roles});
  /// M2-D2: decide every proposed change at once, bound to the draft version and the set hash shown.
  Future<Map<String, dynamic>> decideAll(String wid, String decision, int version, String setSha) =>
      _post('/workbook/$wid/decide_all', {'decision': decision, 'draft_version': version, 'set_sha256': setSha});
  /// The workbook's open approval cards (A2UI messages), to show them again after the panel is rebuilt.
  Future<Map<String, dynamic>> surfaces(String wid) => _get('/a2ui/surfaces?workbook=${Uri.encodeQueryComponent(wid)}');
  Future<Map<String, dynamic>> reload(String wid) => _post('/workbook/$wid/reload');
  Future<Map<String, dynamic>> edit(String wid, Map<String, dynamic> edit) => _post('/workbook/$wid/edit', edit);
  Future<Map<String, dynamic>> decide(String wid, String changeId, String decision, String sha, {String reason = ''}) =>
      _post('/workbook/$wid/decide',
          {'change_id': changeId, 'decision': decision, 'change_sha256': sha, if (reason.isNotEmpty) 'reason': reason});
  Future<Map<String, dynamic>> undo(String wid) => _post('/workbook/$wid/undo');
  Future<Map<String, dynamic>> redo(String wid) => _post('/workbook/$wid/redo');
  Future<Map<String, dynamic>> instruct(String wid, String text, {String? activeSheet}) =>
      _post('/workbook/$wid/instruct', {'text': text, 'active_sheet': ?activeSheet});
  Future<Map<String, dynamic>> proposeSave(String wid, {String? saveAsPath}) =>
      _post('/workbook/$wid/propose_save', {'save_as_path': ?saveAsPath});
  Future<Map<String, dynamic>> proposeShare(String wid) => _post('/workbook/$wid/propose_share');
  Future<Map<String, dynamic>> editCopy(String wid) => _post('/workbook/$wid/edit_copy');
  Future<Map<String, dynamic>> history(String wid, String action, {bool? on, String? rowId}) =>
      _post('/workbook/$wid/history', {'action': action, 'on': ?on, 'row_id': ?rowId});
  Future<Map<String, dynamic>> close(String wid) => _post('/workbook/$wid/close');

  /// An A2UI action from the approval card. Returns the hub's reply shape: the result plus a deleteSurface
  /// message, because the service closes the approval after any decision.
  Future<Map<String, dynamic>> a2uiAction(Map<String, dynamic> action) async {
    final r = await _post('/a2ui/action', {'action': action});
    return {
      'result': r,
      'messages': [
        {'version': 'v0.9', 'deleteSurface': {'surfaceId': action['surfaceId']}},
      ],
    };
  }

  // ---- O2 (contract o2.1, docs/office/unified/O2_API_CONTRACT.md) ----------------------------------------------
  Future<Map<String, dynamic>> contract() => _get('/contract');

  // ---- authoring (milestones A/B): structured editing of a presentation ----
  Future<Map<String, dynamic>> authoringEdit(String documentId) =>
      _post('/authoring/edit', {'document_id': documentId});
  /// A new presentation (default) or, with [kind] 'docx', a Word document from a built-in [layout] or a template.
  Future<Map<String, dynamic>> authoringNew({String? templatePath, String? kind, String? layout}) =>
      _post('/authoring/new', {'template_path': ?templatePath, 'kind': ?kind, 'layout': ?layout});
  Future<Map<String, dynamic>> authoringLayouts() => _get('/authoring/layouts');
  /// OD-2 (plan 16): a Word document drafted by the Brain from [instruction], in [layout] or the kind the
  /// instruction names. Returns `status` propose (an authoring view of a new working copy, with `warnings`), clarify
  /// or cannot (a message only).
  Future<Map<String, dynamic>> authoringDraft(String instruction, {String? layout}) =>
      _post('/authoring/draft', {'instruction': instruction, 'layout': ?layout});
  Future<Map<String, dynamic>> authoringView(String aid) => _get('/authoring/$aid');
  /// One change; a picture's path comes from the owner's picker only.
  Future<Map<String, dynamic>> authoringOp(String aid, Map<String, dynamic> op, {String? imagePath}) =>
      _post('/authoring/$aid/op', {'op': op, 'image_path': ?imagePath});
  Future<Map<String, dynamic>> authoringUndo(String aid, {bool redo = false}) =>
      _post('/authoring/$aid/${redo ? 'redo' : 'undo'}');
  /// The save card (A2UI messages); nothing is written until the owner approves it.
  Future<Map<String, dynamic>> authoringSave(String aid, {String? saveAsPath}) =>
      _post('/authoring/$aid/save', {'save_as_path': ?saveAsPath});
  Future<Map<String, dynamic>> authoringClose(String aid) => _post('/authoring/$aid/close');
  // ---- Writing Intelligence (plan 16, WI-A): suggestions only; nothing here changes a document ----
  @override
  Future<Map<String, dynamic>> writingCheck(String text, {List<String> ignore = const []}) =>
      _post('/writing/check', {'text': text, 'ignore': ignore});
  @override
  Future<Map<String, dynamic>> writingApply(String text, List<Map<String, dynamic>> accepted) =>
      _post('/writing/apply', {'text': text, 'accepted': accepted});
  @override
  Future<Map<String, dynamic>> writingProofread(String text) => _post('/writing/proofread', {'text': text});
  @override
  Future<Map<String, dynamic>> writingRewrite(String text, String tone) =>
      _post('/writing/rewrite', {'text': text, 'tone': tone});
  @override
  Future<Map<String, dynamic>> writingComplete(String text) => _post('/writing/complete', {'text': text});
  bool _writingWarm = false;
  @override
  Future<void> writingPrewarm() async {
    if (_writingWarm) return;                // WI-UX-1: once per client, not once per editor field
    _writingWarm = true;
    await _post('/writing/prewarm', {'text': ''});
  }
  // OD-R1: folders URI may use (the user folder plus folders the owner added).
  Future<Map<String, dynamic>> folders() => _get('/folders');
  Future<Map<String, dynamic>> addFolder(String path) => _post('/folders/add', {'path': path});
  Future<Map<String, dynamic>> removeFolder(String path) => _post('/folders/remove', {'path': path});
  Future<Map<String, dynamic>> capabilities() => _get('/capabilities');
  Future<Map<String, dynamic>> engines() => _get('/engines');
  Future<Map<String, dynamic>> verifyEngine() => _post('/engines/verify', {'engine': 'libreoffice'});
  Future<Map<String, dynamic>> openDocument(String path) => _post('/open/document', {'path': path});
  Future<Map<String, dynamic>> document(String id) => _get('/document/$id');
  Future<Map<String, dynamic>> searchDocument(String id, String text) => _post('/document/$id/search', {'text': text});
  /// OD-3: a PDF's text, page by page (OCR of pages without a text layer only when [ocr] is true).
  Future<Map<String, dynamic>> documentText(String id, {bool ocr = false}) =>
      _post('/document/$id/text', {if (ocr) 'ocr': true});
  /// OD-3: a new Word working copy made from a PDF's text (saved only through the Save as card).
  Future<Map<String, dynamic>> documentToWord(String id, {bool ocr = false}) =>
      _post('/document/$id/to_word', {if (ocr) 'ocr': true});
  Future<Map<String, dynamic>> closeDocument(String id) => _post('/document/$id/close');
  Future<Map<String, dynamic>> retryDocument(String id) => _post('/document/$id/retry');
  Future<Map<String, dynamic>> request(Map<String, dynamic> body) => _post('/request', body);
  Future<Map<String, dynamic>> createWorkflow(String capability, List<Map<String, dynamic>> inputs) =>
      _post('/workflow', {'capability': capability, 'inputs': inputs});
  Future<Map<String, dynamic>> workflow(String id) => _get('/workflow/$id');
  Future<Map<String, dynamic>> workflows() => _get('/workflows');
  Future<Map<String, dynamic>> cancelWorkflow(String id) => _post('/workflow/$id/cancel');
  Future<Map<String, dynamic>> resumeWorkflow(String id, List<String> paths) =>
      _post('/workflow/$id/resume', {'inputs': [for (final p in paths) {'path': p}]});
  Future<Map<String, dynamic>> acceptWarnings(String id) => _post('/workflow/$id/accept_warnings');
  Future<Map<String, dynamic>> proposeWorkflowSave(String id, String path) =>
      _post('/workflow/$id/propose_save', {'save_as_path': path});
  Future<Map<String, dynamic>> recent() => _get('/recent');
  Future<Map<String, dynamic>> recentRemove(String path) => _post('/recent/remove', {'path': path});
  Future<Map<String, dynamic>> recentClear() => _post('/recent/clear');

  // ---- O2P printing (A1 §A4, §A6) ----
  Future<Map<String, dynamic>> printers() => _get('/devices/printers');
  Future<Map<String, dynamic>> refreshPrinters() => _post('/devices/refresh');
  Future<Map<String, dynamic>> printer(String id) => _get('/devices/printers/$id');
  Future<Map<String, dynamic>> printPreview(Map<String, dynamic> body) => _post('/print/preview', body);
  Future<Map<String, dynamic>> printPropose(Map<String, dynamic> body) => _post('/print/propose', body);
  Future<Map<String, dynamic>> printStatus(String job) => _get('/print/$job');
  Future<Map<String, dynamic>> printCancel(String job) => _post('/print/$job/cancel');

  /// A page image (PNG bytes), or null while the page is still being prepared (HTTP 202).
  Future<Uint8List?> documentPage(String id, int page, int width) => _png('/document/$id/page/$page?w=$width');
  Future<Uint8List?> outputPage(String workflowId, int page, int width) =>
      _png('/workflow/$workflowId/output/page/$page?w=$width');

  Future<Uint8List?> _png(String path) async {
    final r = await _http.get(_base.resolve(path), headers: _headers).timeout(const Duration(seconds: 60));
    if (r.statusCode == 202) return null;
    if (r.statusCode != 200) throw SchedulerApiError.from(r.body.isEmpty ? null : jsonDecode(r.body));
    if ((r.headers['content-type'] ?? '') != 'image/png') throw SchedulerApiError('NOT_AN_IMAGE', null);
    return r.bodyBytes;
  }

  void closeClient() => _http.close();
}
