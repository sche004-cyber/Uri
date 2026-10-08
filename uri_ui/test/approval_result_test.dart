import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/services/http_uri_client.dart';

void main() {
  Future<UriTurn> decide(Map<String, dynamic> result) async {
    final client = HttpUriClient(
      sessionId: 'own-session',
      httpClient: MockClient((request) async {
        expect(request.url.path, '/approve');
        expect(request.headers['Authorization'], 'Bearer mock-session-token');
        expect(jsonDecode(request.body), {
          'action_id': 'bound-action',
          'session_id': 'own-session',
        });
        return http.Response(jsonEncode(result), 200);
      }),
    );
    client.restoreSession(token: 'mock-session-token', username: 'fixture');
    return client.approve('bound-action');
  }

  for (final status in [
    'unavailable',
    'input_required',
    'degraded',
    'failed',
    'error',
  ]) {
    test('approval reports $status rather than completion', () async {
      final turn = await decide({
        'status': 'success',
        'data': {'status': status, 'message': 'Execution could not finish'},
        'narrative': '',
      });
      expect(turn.stage, TurnStage.failed);
      expect(turn.failureReason, 'Execution could not finish');
      expect(turn.result, isNull);
    });
  }
  test('canonical execution failure remains a failure', () async {
    final turn = await decide({
      'status': 'success',
      'execution': {'status': 'unavailable'},
      'response': {'message': 'Permission denied'},
    });
    expect(turn.stage, TurnStage.failed);
    expect(turn.failureReason, 'Permission denied');
  });
  test('empty narrative retains actual cloud result link', () async {
    final turn = await decide({
      'status': 'success',
      'narrative': '',
      'data': {
        'status': 'success',
        'name': 'Disposable slides',
        'file_id': 'cloud-id',
        'webViewLink': 'https://docs.google.com/presentation/d/cloud-id/edit',
      },
    });
    expect(turn.stage, TurnStage.completed);
    expect(turn.result!.summary, 'Result: Disposable slides');
    expect(
      turn.result!.sources.single.url,
      'https://docs.google.com/presentation/d/cloud-id/edit',
    );
    expect(turn.result!.allGeneratedFiles, isEmpty);
  });
  test('approval preserves actual local file references and preview', () async {
    final turn = await decide({
      'status': 'success',
      'response': {
        'status': 'success',
        'message': 'Created files',
        'preview': 'Document preview',
        'files': [
          for (final n in [1, 2, 3])
            {'file_id': 'own-$n', 'filename': 'draft-$n.pptx'},
        ],
      },
    });
    expect(turn.result!.allGeneratedFiles.length, 3);
    expect(turn.result!.draftText, 'Document preview');
  });
  test('unknown execution status cannot claim completion', () async {
    expect((await decide({'status': 'mystery'})).stage, TurnStage.failed);
  });
  test('credential-bearing or invalid links are omitted', () async {
    for (final url in [
      'https://secret@example.com/file',
      'javascript:alert(1)',
    ]) {
      final turn = await decide({
        'status': 'success',
        'data': {'name': 'File', 'webViewLink': url},
      });
      expect(turn.result!.sources, isEmpty);
    }
  });
}
