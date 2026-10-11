import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/assist/assist_controller.dart';
import 'package:uri_ui/services/integrated_runtime.dart';

/// Review R9-05: findings, the last observation and an ask are derived from one
/// grant generation. Pause, resume, a new grant and Stop discard them, and a
/// reply that arrives after one of those is dropped.
class _Runtime implements IntegratedRuntime {
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  String state = 'OFF';
  String label = 'Bank page';
  int asks = 0;

  /// When set, the next assist_ask / assist_check reply waits for it.
  Completer<void>? hold;

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
      case 'assist_check':
        final h = hold;
        if (h != null) await h.future;
        return {
          'observation': {'title': label},
          'findings': [{'code': 'EMAIL_FORMAT', 'field': 'E-mail', 'message': 'x'}],
          'changed_anything': false,
        };
      case 'assist_ask':
        final h = hold;
        if (h != null) await h.future;
        asks++;
        return {'ask_id': 'ask-$asks', 'method': 'structured', 'observation': {'title': label}};
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
  for (final step in ['pause', 'resume', 'grant']) {
    test('R9-05: $step discards findings, the observation and the answer', () async {
      final rt = _Runtime();
      final a = AssistController(runtime: () => rt, events: rt.events, pollEvery: const Duration(hours: 1));
      await a.grant('browser_tab', 'tab-bank', suggest: true);
      await a.check();
      await a.ask('What is my balance?');
      expect(a.findings, isNotEmpty);
      expect(a.lastObservation, isNotNull);
      expect(a.askId, 'ask-1');
      if (step == 'resume') await a.pause();
      switch (step) {
        case 'pause':
          await a.pause();
        case 'resume':
          // Something shown while paused must not survive resume either.
          a.findings = [{'code': 'X'}];
          a.lastObservation = {'title': 'Bank page'};
          await a.resume();
        case 'grant':
          rt.label = 'News page';
          await a.grant('browser_tab', 'tab-news', suggest: false);
      }
      expect(a.findings, isEmpty);
      expect(a.lastObservation, isNull);
      expect(a.askId, isNull);
      expect(a.answer, isNull);
      a.dispose();
    });
  }

  test('R9-05: an ask reply arriving after Stop does not restore the old observation', () async {
    final rt = _Runtime();
    final a = AssistController(runtime: () => rt, events: rt.events, pollEvery: const Duration(hours: 1));
    await a.grant('browser_tab', 'tab-bank', suggest: true);
    rt.hold = Completer<void>();
    final pending = a.ask('What is my balance?');
    await Future<void>.delayed(Duration.zero);
    await a.revoke();
    rt.hold!.complete();
    await pending;
    expect(a.off, isTrue);
    expect(a.askId, isNull);
    expect(a.lastObservation, isNull);
    a.dispose();
  });

  test('R9-05: a check reply arriving after a new grant is dropped', () async {
    final rt = _Runtime();
    final a = AssistController(runtime: () => rt, events: rt.events, pollEvery: const Duration(hours: 1));
    await a.grant('browser_tab', 'tab-bank', suggest: true);
    final held = rt.hold = Completer<void>();
    final pending = a.check();
    await Future<void>.delayed(Duration.zero);
    rt.hold = null;
    await a.grant('browser_tab', 'tab-news', suggest: true);
    held.complete();                      // the old page's reply arrives after the new grant
    await pending;
    expect(a.findings, isEmpty);
    expect(a.lastObservation, isNull);
    a.dispose();
  });
}
