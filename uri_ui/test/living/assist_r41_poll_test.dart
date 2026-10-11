import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/assist/assist_controller.dart';
import 'package:uri_ui/services/integrated_runtime.dart';

/// Review R41-01: a poll reply for an ask that is in flight while Pause, Stop
/// or a new grant happens is dropped, never shown.
class _Runtime implements IntegratedRuntime {
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  String state = 'OFF';
  int asks = 0;
  int statusCalls = 0;

  /// Released by the test: the assist_ask_status reply waits for it.
  final hold = Completer<void>();

  Map<String, dynamic> _status() => {'state': state, 'generation': 1, 'scope': null, 'permissions': const {}};

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;
  @override
  bool get closed => false;

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> c) async {
    switch (c['command']) {
      case 'assist_grant':
      case 'assist_resume':
        state = 'ACTIVE';
        return _status();
      case 'assist_pause':
        state = 'PAUSED';
        return _status();
      case 'assist_revoke':
        state = 'OFF';
        return _status();
      case 'assist_ask':
        asks++;
        return {'ask_id': 'ask-$asks', 'method': 'structured', 'observation': {'title': 'Bank'}};
      case 'assist_ask_status':
        statusCalls++;
        await hold.future;
        return {
          'state': 'FINISHED',
          'ask_id': c['ask_id'],
          'status': 'COMPLETE',
          'answer': 'Your balance is 1234',
          'method': 'structured',
          'observation': {'title': 'Bank'},
        };
      default:
        return _status();
    }
  }

  @override
  Future<void> close() async {}
  @override
  Future<void> kill() async {}
}

void main() {
  for (final step in ['pause', 'revoke', 'grant']) {
    test('R41-01: a status reply in flight across $step is dropped', () async {
      final rt = _Runtime();
      final a = AssistController(runtime: () => rt, events: rt.events, pollEvery: const Duration(milliseconds: 5));
      await a.grant('browser_tab', 'tab-bank', suggest: true);
      await a.ask('What is my balance?');
      // Wait until the poll has sent assist_ask_status and holds its reply.
      for (var i = 0; i < 200 && rt.statusCalls == 0; i++) {
        await Future<void>.delayed(const Duration(milliseconds: 5));
      }
      expect(rt.statusCalls, greaterThan(0));
      switch (step) {
        case 'pause':
          await a.pause();
        case 'revoke':
          await a.revoke();
        case 'grant':
          await a.grant('browser_tab', 'tab-other', suggest: false);
      }
      expect(a.answer, isNull);
      rt.hold.complete();
      await Future<void>.delayed(const Duration(milliseconds: 30));
      expect(a.answer, isNull, reason: 'answer derived before $step must not be shown after it');
      a.dispose();
    });
  }

  test('R41-01: a status reply without any change is still applied', () async {
    final rt = _Runtime();
    final a = AssistController(runtime: () => rt, events: rt.events, pollEvery: const Duration(milliseconds: 5));
    await a.grant('browser_tab', 'tab-bank', suggest: true);
    await a.ask('What is my balance?');
    rt.hold.complete();
    for (var i = 0; i < 200 && a.answer == null; i++) {
      await Future<void>.delayed(const Duration(milliseconds: 5));
    }
    expect(a.answer, 'Your balance is 1234');
    a.dispose();
  });
}
