import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_draft.dart';

import 'ti_draft_test.dart' show snapshot, v1, v2;
import 'ws_hardening_test.dart' show HardeningRuntime, fast;

/// Text intelligence combined with WS hardening (integration candidate
/// glue). Drafts live in the worker's memory (TI L-7), so Restart URI must
/// not leave a draft on screen that the new worker does not have, and a
/// draft reply from the replaced worker must not change the new state.
void main() {
  test('Restart URI clears the draft it can no longer serve and says so', () async {
    final w1 = HardeningRuntime();
    final w2 = HardeningRuntime(name: 'w2');
    final conv = OiConversation(w1, respawn: () async => w2);
    conv.draft = OiDraft.parse(snapshot(current: v2, previous: v1));
    expect(conv.draft, isNotNull);
    await conv.restartWorker();
    expect(conv.runtime, same(w2));
    expect(conv.draft, isNull);
    expect(conv.draftQuestion, isNull);
    expect(conv.messages.where((m) => m.role == OiRole.system).map((m) => m.text).join('\n'),
        contains('draft was held by the old worker'));
    // nothing was sent to the new worker on the user's behalf
    expect(w2.commands.where((c) => c['command'] == 'draft_op' || c['command'] == 'oi_turn'), isEmpty);
  });

  test('no restart note when there was no draft', () async {
    final conv = OiConversation(HardeningRuntime(), respawn: () async => HardeningRuntime(name: 'w2'));
    await conv.restartWorker();
    expect(conv.messages.where((m) => m.text.contains('draft')), isEmpty);
  });

  test('draft buttons do nothing while the worker is being replaced', () async {
    final w1 = HardeningRuntime();
    final gate = Completer<HardeningRuntime?>();
    final conv = OiConversation(w1, respawn: () => gate.future);
    final restarting = conv.restartWorker();
    await Future<void>.delayed(fast);
    expect(conv.restarting, isTrue);
    await conv.draftOp('undo');
    await conv.refreshDraft();
    expect(w1.commands.where((c) => c['command'] == 'draft_op' || c['command'] == 'draft_get'), isEmpty);
    final w2 = HardeningRuntime(name: 'w2');
    gate.complete(w2);
    await restarting;
    await conv.draftOp('undo');
    expect(w2.commands.last, {'command': 'draft_op', 'session_id': conv.sessionId, 'op': 'undo'});
  });

  test('a late draft reply from the replaced worker does not change the new state', () async {
    final w1 = HardeningRuntime()..responsive = false;
    final w2 = HardeningRuntime(name: 'w2');
    final conv = OiConversation(w1, respawn: () async => w2);
    conv.draft = OiDraft.parse(snapshot(current: v2, previous: v1));
    unawaited(conv.draftOp('undo')); // outstanding on w1
    await Future<void>.delayed(fast);
    await conv.restartWorker();
    expect(conv.draft, isNull);
    w1.failPending('WORKER_TIMEOUT');
    await Future<void>.delayed(fast);
    expect(conv.lastError, isNull);
    expect(conv.draft, isNull);
  });

  test('a transcript turn is refused while the worker is being replaced', () async {
    final w1 = HardeningRuntime();
    final gate = Completer<HardeningRuntime?>();
    final conv = OiConversation(w1, respawn: () => gate.future)..setTranscriptMode(true);
    final restarting = conv.restartWorker();
    await Future<void>.delayed(fast);
    await conv.send('um the letter please');
    expect(w1.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
    final w2 = HardeningRuntime(name: 'w2');
    gate.complete(w2);
    await restarting;
    await conv.send('um the letter please');
    expect(w2.commands.last['command'], 'oi_turn');
    expect((w2.commands.last['input'] as Map)['schema'], 'uri.text_input.v1');
    expect(conv.busy, isTrue); // the send stamps liveness like any other turn
  });
}
