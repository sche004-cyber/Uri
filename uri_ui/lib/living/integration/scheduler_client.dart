import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

/// Client for the local URI Scheduler service (`python -m uri_scheduler.service run`).
///
/// Discovery: the service writes `service.json` (port) and `api-token` into its
/// state directory; the UI reads both from `URI_SCHEDULER_STATE`. The API binds
/// 127.0.0.1 only. Nothing here can publish, post or send an artifact: the
/// service has no such endpoint.
class SchedulerClient {
  SchedulerClient({
    required this.baseUrl,
    required this.token,
    required this.principal,
    http.Client? client,
  }) : _http = client ?? http.Client();

  final String baseUrl;
  final String token;
  final String principal;
  final http.Client _http;

  /// Null when no scheduler service is configured or it has not started yet.
  static SchedulerClient? fromEnvironment({http.Client? client}) {
    final env = Platform.environment;
    final dir = env['URI_SCHEDULER_STATE'];
    if (dir == null || dir.isEmpty) return null;
    try {
      final svc = jsonDecode(File('$dir/service.json').readAsStringSync());
      final token = File('$dir/api-token').readAsStringSync().trim();
      return SchedulerClient(
        baseUrl: 'http://127.0.0.1:${svc['port']}',
        token: token,
        principal: env['URI_SCHEDULER_PRINCIPAL'] ?? 'owner',
        client: client,
      );
    } catch (_) {
      return null;
    }
  }

  Map<String, String> get _headers => {
    'Authorization': 'Bearer $token',
    'Content-Type': 'application/json',
  };

  Future<Map<String, dynamic>> _get(String path) async {
    final r = await _http.get(Uri.parse('$baseUrl$path'), headers: _headers);
    final body = jsonDecode(r.body);
    if (r.statusCode != 200) throw SchedulerApiError.from(body);
    return body as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> _post(
    String path, [
    Map<String, dynamic>? body,
  ]) async {
    final r = await _http.post(
      Uri.parse('$baseUrl$path'),
      headers: _headers,
      body: jsonEncode({'principal': principal, ...?body}),
    );
    final decoded = jsonDecode(r.body);
    if (r.statusCode != 200) throw SchedulerApiError.from(decoded);
    return decoded as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> overview() => _get('/overview?owner=$principal');

  Future<Uint8List> artifactBytes(int artifactId) async {
    final r = await _http.get(
      Uri.parse('$baseUrl/artifacts/$artifactId/file'),
      headers: _headers,
    );
    if (r.statusCode != 200) {
      throw SchedulerApiError('HTTP_${r.statusCode}', null);
    }
    return r.bodyBytes;
  }

  Future<Map<String, dynamic>> proposeFestivals({
    List<String>? festivals,
    String time = '09:00',
  }) => _post('/jobs/propose-festivals', {
    'festivals': ?festivals,
    'time': time,
  });

  Future<Map<String, dynamic>> confirm(String jobId, String proposalSha256) =>
      _post('/jobs/$jobId/confirm', {'proposal_sha256': proposalSha256});

  Future<Map<String, dynamic>> jobAction(String jobId, String action) =>
      _post('/jobs/$jobId/$action');

  Future<Map<String, dynamic>> occurrenceAction(int occId, String action) =>
      _post('/occurrences/$occId/$action');

  /// Approval and every other decision names the exact artifact version.
  Future<Map<String, dynamic>> review(
    int artifactId,
    String action, {
    required String sha256,
    String? instruction,
  }) => _post('/artifacts/$artifactId/review', {
    'action': action,
    'sha256': sha256,
    'instruction': ?instruction,
  });
}

class SchedulerApiError implements Exception {
  SchedulerApiError(this.code, this.detail);
  factory SchedulerApiError.from(dynamic body) => body is Map
      ? SchedulerApiError('${body['error']}', body['detail']?.toString())
      : SchedulerApiError('UNKNOWN', '$body');
  final String code;
  final String? detail;
  @override
  String toString() => detail == null ? code : '$code: $detail';
}
