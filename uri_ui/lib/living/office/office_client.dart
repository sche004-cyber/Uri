import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../integration/scheduler_client.dart' show SchedulerApiError;

/// HTTP client for the URI Office service (`python -m uri_office.service run`), the same discovery as the
/// scheduler: `<state>/service.json` gives the port, `<state>/api-token` (current user only) the bearer token.
/// The state folder is `URI_OFFICE_STATE`, or `%LOCALAPPDATA%\URI\office`.
///
/// Only Dart talks to the service; the sheet page never does (it has no network access at all).
class OfficeClient {
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
  Future<Map<String, dynamic>> openLocal(String path) => _post('/open/local', {'path': path});
  Future<Map<String, dynamic>> openGoogle(String url) => _post('/open/google', {'url': url});
  Future<Map<String, dynamic>> view(String wid) => _get('/workbook/$wid');
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

  void closeClient() => _http.close();
}
