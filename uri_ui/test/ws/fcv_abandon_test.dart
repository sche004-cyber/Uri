import 'package:flutter_test/flutter_test.dart';

import 'package:uri_ui/living/integration/oi_conversation.dart';

import 'ws_integration_test.dart' show FakeRuntime;

/// FCVR-01 (live): "No" on a Core confirmation is now Core's abandon decision, a worker job. The conversation stays
/// busy until that job finishes, so the next request is not refused as TURN_IN_PROGRESS.
class _AbandonRuntime extends FakeRuntime {
  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    if (command['command'] == 'oi_abandon') {
      commands.add(command);
      return {'turn_id': command['turn_id'], 'accepted': true, 'abandoned': true};
    }
    return super.call(command);
  }
}

void main() {
  test('abandoning a confirmation stays busy until Core settles it', () async {
    final rt = _AbandonRuntime();
    final conv = OiConversation(rt);
    await conv.refreshStatus();
    await conv.send('remember that the staff meeting is on Tuesday');
    rt.emit('t1', 'core.result', {'state': 'reply', 'code': 'INTENT_CONFIRMATION_REQUIRED', 'needs': 'confirmation',
      'message': 'Is this right?', 'confirmation': {'arguments': {}}});
    rt.emit('t1', 'turn.finished', {'status': 'needs_user'});
    await pumpEventQueue();
    expect(conv.pendingConfirmation, isNotNull);
    expect(conv.busy, isFalse);
    await conv.abandon();
    expect(rt.commands.last['command'], 'oi_abandon');
    expect(conv.busy, isTrue);                     // Core is still settling the abandon
    rt.emit('t1', 'core.result', {'state': 'reply', 'code': 'INTENT_ABANDONED', 'needs': 'none',
      'message': 'Okay, I dropped that request. Nothing was done.'});
    rt.emit('t1', 'turn.finished', {'status': 'refused'});
    await pumpEventQueue();
    expect(conv.busy, isFalse);
    expect(conv.messages.last.coreCode, 'INTENT_ABANDONED');
  });

  test('a refused turn says why in plain words', () {
    expect(notSentMessage('TURN_IN_PROGRESS'), isNot(contains('TURN_IN_PROGRESS')));
    expect(notSentMessage('SOMETHING_NEW'), isNot(contains('SOMETHING_NEW')));
  });
}
