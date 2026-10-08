import 'dart:convert';

import 'package:http/http.dart' as http;

import 'uri_client.dart';

/// Separate harness transport; never uses or configures a Brain provider.
class DesktopHarnessTestClient {
  DesktopHarnessTestClient(this.uri, {http.Client? httpClient})
    : _http = httpClient ?? http.Client();
  final UriClient uri;
  final http.Client _http;

  Future<Map<String, dynamic>> _post(String path, Object? body) async {
    final token = uri.authToken;
    if (token == null) throw StateError('Sign in to URI first.');
    final address = Uri.parse(uri.baseUrl);
    if (address.scheme != 'http' ||
        !['127.0.0.1', 'localhost', '::1'].contains(address.host)) {
      throw StateError('Harness qualification requires a loopback URI Core.');
    }
    final response =
        await (body == null
                ? _http.get(
                    address.resolve('/desktop/harness-test/$path'),
                    headers: {'Authorization': 'Bearer $token'},
                  )
                : _http.post(
                    address.resolve('/desktop/harness-test/$path'),
                    headers: {
                      'Authorization': 'Bearer $token',
                      'Content-Type': 'application/json',
                    },
                    body: jsonEncode(body),
                  ))
            .timeout(const Duration(seconds: 30));
    if (response.statusCode != 200) {
      throw StateError(
        'Harness test HTTP ${response.statusCode}. '
        'Execution is not retried. Prepare a new test after checking CLI login.',
      );
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> prepare() => _post('prepare', {});
  Future<Map<String, dynamic>> approve(String id) =>
      _post('${Uri.encodeComponent(id)}/approve', {'authorized': true});
  Future<Map<String, dynamic>> providers({bool refresh = false}) =>
      _post(refresh ? 'providers/refresh' : 'providers', refresh ? {} : null);
  Future<Map<String, dynamic>> prepareSelected(String provider) =>
      _post('tasks/prepare', {'provider': provider});
  Future<Map<String, dynamic>> start(String approvalId) => _post(
    'tasks/${Uri.encodeComponent(approvalId)}/start',
    {'authorized': true},
  );
  Future<Map<String, dynamic>> task(String taskId) =>
      _post('tasks/${Uri.encodeComponent(taskId)}', null);
  Future<Map<String, dynamic>> tasks() => _post('tasks', null);
  Future<Map<String, dynamic>> cancel(String taskId) =>
      _post('tasks/${Uri.encodeComponent(taskId)}/cancel', {});
  Future<Map<String, dynamic>> recover(String taskId, String action) => _post(
    'tasks/${Uri.encodeComponent(taskId)}/recover',
    {'authorized': true, 'action': action},
  );
  void close() => _http.close();
}
