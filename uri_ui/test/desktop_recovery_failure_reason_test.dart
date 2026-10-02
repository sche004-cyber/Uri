import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/services/http_uri_client.dart';

void main() {
  Future<UriTurn> askWithBody(Map<String, dynamic> body) {
    final client = HttpUriClient(
      httpClient: MockClient(
        (_) async => http.Response(jsonEncode(body), 200),
      ),
    );
    return client.ask('check my gmail');
  }

  test('unavailable response shows the backend capability reason', () async {
    final turn = await askWithBody({
      'status': 'unavailable',
      'response': {'message': 'Gmail is not connected.'},
    });
    expect(turn.stage, TurnStage.failed);
    expect(turn.failureReason, 'Gmail is not connected.');
  });

  test('failed response shows the backend capability reason', () async {
    final turn = await askWithBody({
      'status': 'failed',
      'response': {'message': 'That capability is not connected right now.'},
    });
    expect(turn.failureReason, 'That capability is not connected right now.');
  });

  test('top-level error retains priority over response message', () async {
    final turn = await askWithBody({
      'status': 'failed',
      'error': 'Direct error',
      'response': {'message': 'Nested error'},
    });
    expect(turn.failureReason, 'Direct error');
  });

  test('Brain setup reason retains priority over response message', () async {
    final turn = await askWithBody({
      'status': 'unavailable',
      'narrative_unavailable_reason': 'no_brain_configured',
      'response': {'message': 'Nested error'},
    });
    expect(turn.failureReason, contains('set an Active Brain'));
  });

  test('missing response message keeps the generic fallback', () async {
    final turn = await askWithBody({'status': 'failed'});
    expect(turn.failureReason, 'URI could not process this request.');
  });
}
