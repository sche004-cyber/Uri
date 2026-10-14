import 'package:flutter_test/flutter_test.dart';

import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_widgets.dart';

import 'ws_integration_test.dart' show FakeRuntime, digest, host;

/// FCV UX-D / FCV-08: after an approved save the reply names what was saved
/// (from the worker's `core.outcome`), chips use plain words and keep the raw
/// code only as a tooltip, and errors show their message, not their code.
void main() {
  Future<OiConversation> approvedSave(WidgetTester tester, FakeRuntime rt, {bool outcome = true}) async {
    final conv = OiConversation(rt);
    await tester.runAsync(() async {
      await conv.refreshStatus();
      await conv.send('remember that the science lab is closed on Friday');
    });
    rt.emit('t1', 'core.result', {'state': 'reply', 'code': 'SETTLED_VERIFIED',
        'message': 'Done. The result was independently verified by URI.', 'needs': 'none'});
    if (outcome) {
      rt.emit('t1', 'core.outcome', {
        'capability_id': 'remember_fact',
        'summary': 'Saved to URI’s memory on this computer: “the science lab is closed on Friday”.',
        'saved': ['the science lab is closed on Friday'],
        'read_back': true,
      });
    }
    rt.emit('t1', 'turn.finished', {'status': 'ok'});
    await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
    await tester.pump();
    return conv;
  }

  testWidgets('a verified save shows what was saved, not a generic verification claim', (tester) async {
    await approvedSave(tester, FakeRuntime());
    expect(find.textContaining('the science lab is closed on Friday”'), findsOneWidget);
    expect(find.textContaining('independently verified'), findsNothing);
    expect(find.text('Done · checked'), findsOneWidget);
    expect(find.text('SETTLED_VERIFIED'), findsNothing);
    expect(find.byTooltip('SETTLED_VERIFIED'), findsOneWidget);
  });

  testWidgets("without an outcome event Core's own message stays", (tester) async {
    await approvedSave(tester, FakeRuntime(), outcome: false);
    expect(find.textContaining('independently verified'), findsOneWidget);
  });

  testWidgets('an outcome event never overrides a non-verified settlement', (tester) async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await tester.runAsync(() async {
      await conv.refreshStatus();
      await conv.send('remember that x');
    });
    rt.emit('t1', 'core.result', {'state': 'failed', 'code': 'SETTLED_FAILED', 'message': 'The action failed; nothing was verified.', 'needs': 'none'});
    rt.emit('t1', 'core.outcome', {'summary': 'Saved to URI’s memory on this computer.'});
    rt.emit('t1', 'turn.finished', {'status': 'error'});
    await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
    await tester.pump();
    expect(find.textContaining('Saved to URI'), findsNothing);
    expect(find.text('Failed · nothing changed'), findsOneWidget);
  });

  test('every chip label is plain words, never a raw code', () {
    const codes = ['SETTLED_VERIFIED', 'SETTLED_FAILED', 'SETTLED_CANCELLED', 'SETTLED_EXECUTION_UNCERTAIN',
      'APPROVAL_REQUIRED', 'APPROVAL_DENIED', 'INTENT_CONFIRMATION_REQUIRED', 'INTENT_ABANDONED', 'WAITING_FOR_MODEL',
      'CONVERSATION', 'CLARIFICATION_REQUIRED', 'INTENT_CLARIFICATION', 'REFUSED_UNSUPPORTED', 'INTENT_STATE_STALE',
      'SOMETHING_NEW'];
    for (final code in codes) {
      expect(oiCoreLabel(code), isNot(matches(RegExp(r'[A-Z]{2,}_'))), reason: code);
    }
    for (final s in ['INCOMPLETE_LENGTH', 'CANCELLED', 'TIMED_OUT', 'ERROR', 'NEW_STATUS']) {
      expect(oiAnswerStatusLabel(s), isNot(matches(RegExp(r'[A-Z]{2,}'))), reason: s);
    }
  });

  testWidgets('an error shows its message; the code is only a tooltip', (tester) async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await tester.runAsync(() async {
      await conv.refreshStatus();
      await conv.send('hello');
    });
    rt.emit('t1', 'error', {'code': 'BRAIN_UNAVAILABLE', 'message': 'The local Brain is not ready.', 'recoverable': true});
    rt.emit('t1', 'turn.finished', {'status': 'error'});
    await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
    await tester.pump();
    expect(find.text('The local Brain is not ready.'), findsOneWidget);
    expect(find.textContaining('(BRAIN_UNAVAILABLE)'), findsNothing);
    expect(find.byTooltip('BRAIN_UNAVAILABLE'), findsOneWidget);
    expect(digest, isNotEmpty);
  });
}
