import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_sources.dart';
import 'package:uri_ui/living/integration/oi_widgets.dart';
import 'package:uri_ui/living/integration/ws_settings.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'package:uri_ui/theme/uri_theme.dart';
import 'package:uri_ui/working_system_app.dart';

const digest = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa';

/// Scriptable stand-in for the integrated worker: records every command and
/// lets the test push `uri.oi.event.v1` events.
class FakeRuntime implements IntegratedRuntime {
  final commands = <Map<String, dynamic>>[];
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  int _turn = 0;
  bool _closed = false;
  String brainState = 'READY';

  void emit(String turnId, String type, [Map<String, dynamic> data = const {}]) =>
      _events.add({'schema': 'uri.oi.event.v1', 'turn_id': turnId, 'type': type, 'data': data});

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;

  @override
  bool get closed => _closed;

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    commands.add(command);
    switch (command['command']) {
      case 'oi_turn':
        return {'turn_id': 't${++_turn}', 'accepted': true};
      case 'brain_status':
        return {'state': brainState, 'model_id': 'qwen-test', 'artifacts': 'MATCH'};
      case 'brain_catalog':
        return {
          'rows': [
            {'id': 'runtime-v1', 'display': 'Runtime v1 (local)', 'selectable': true, 'selected': true, 'state': brainState},
            {'id': 'deterministic', 'display': 'No Brain (deterministic rules)', 'selectable': true, 'selected': false, 'state': 'READY'},
            {'id': 'cloud-anthropic', 'display': 'Anthropic Claude (cloud)', 'selectable': false, 'selected': false,
              'state': 'DISABLED', 'why_not': 'Cloud activation is disabled'},
          ],
          'fallback': 'none',
        };
      case 'memory_list':
        return {'facts': ['the lab is closed on Friday'], 'model_used': false};
      case 'cloud_policy':
        return {'cap_usd': 5.0, 'spent_usd': 0.0, 'activation': 'disabled', 'providers': []};
      default:
        return {'ok': true};
    }
  }

  @override
  Future<void> close() async {
    _closed = true;
    commands.add({'command': 'close'});
  }

  @override
  Future<void> kill() async {
    _closed = true;
    commands.add({'command': '<kill>'});
  }
}

Widget host(Widget child) {
  final palette = resolveUriColors(UriThemeChoice.obsidianCyan, Brightness.dark);
  return MaterialApp(theme: buildUriTheme(palette), home: Scaffold(body: child));
}

void main() {
  test('typed text is only ever a turn; approval is the structured decision with the shown digest', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await conv.send('approve');
    expect(rt.commands.last['command'], 'oi_turn');
    expect(rt.commands.last['text'], 'approve');
    expect(rt.commands.where((c) => c['command'] == 'oi_decide'), isEmpty);

    rt.emit('t1', 'core.result', {'code': 'APPROVAL_REQUIRED', 'needs': 'approval'});
    rt.emit('t1', 'approval.required', {
      'capability_id': 'remember_fact',
      'arguments': {'inputs': {'request_text': 'remember that x'}},
      'approval_digest': digest,
    });
    rt.emit('t1', 'turn.finished', {'status': 'needs_user'});
    await pumpEventQueue();
    expect(conv.pendingApproval?.approvalDigest, digest);
    expect(conv.busy, isFalse);

    await conv.decide(approve: true);
    final d = rt.commands.last;
    expect(d, {'command': 'oi_decide', 'turn_id': 't1', 'approve': true, 'approval_digest': digest});
    expect(conv.pendingApproval, isNull);
  });

  test('streaming deltas build the answer; tier, metrics and cancel', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await conv.send('What is VRAM?');
    rt.emit('t1', 'turn.routed', {'route': 'answer', 'tier': {'tier': 'NORMAL'}});
    rt.emit('t1', 'thinking.progress', {'chars': 400});
    rt.emit('t1', 'answer.delta', {'text': 'Video '});
    rt.emit('t1', 'answer.delta', {'text': 'memory.'});
    await pumpEventQueue();
    final m = conv.messages.last;
    expect(m.text, 'Video memory.');
    expect(m.tier, 'NORMAL');
    expect(m.thinkingChars, 400);
    expect(conv.busy, isTrue);
    await conv.cancel();
    expect(rt.commands.last, {'command': 'oi_cancel', 'turn_id': 't1'});
    rt.emit('t1', 'answer.done', {'status': 'CANCELLED', 'flags': [], 'metrics': {'ttft_s': 0.3}});
    rt.emit('t1', 'turn.finished', {'status': 'cancelled'});
    await pumpEventQueue();
    expect(m.answerStatus, 'CANCELLED');
    expect(conv.busy, isFalse);
  });

  test('unverified action claims are flagged; unknown events are ignored', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await conv.send('hello');
    rt.emit('t1', 'something.new', {'x': 1});
    rt.emit('t1', 'answer.done', {'status': 'COMPLETE', 'flags': ['UNVERIFIED_ACTION_CLAIM'], 'metrics': {}});
    await pumpEventQueue();
    expect(conv.messages.last.unverifiedClaim, isTrue);
  });

  test('companion follows the event stream and Brain readiness', () async {
    final rt = FakeRuntime()..brainState = 'STOPPED';
    final conv = OiConversation(rt);
    await conv.refreshStatus();
    final src = OiCompanionSource(conv);
    expect(src.signal.state, CompanionState.unavailable);
    expect(src.signal.simulated, isFalse);
    await conv.send('hi');
    rt.emit('t1', 'companion.state', {'state': 'thinking'});
    await pumpEventQueue();
    expect(src.signal.state, CompanionState.thinking);
    rt.emit('t1', 'approval.required', {'capability_id': 'remember_fact', 'arguments': {}, 'approval_digest': digest});
    await pumpEventQueue();
    expect(src.signal.state, CompanionState.awaitingApproval);
  });

  testWidgets('approval card buttons send the decision; deny is a decision too', (tester) async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await tester.runAsync(() async {
      await conv.refreshStatus();
      await conv.send('remember that the bus leaves at 7');
    });
    rt.emit('t1', 'approval.required', {
      'capability_id': 'remember_fact',
      'arguments': {'inputs': {'request_text': 'remember that the bus leaves at 7'}},
      'approval_digest': digest,
    });
    rt.emit('t1', 'turn.finished', {'status': 'needs_user'});
    await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
    await tester.pump();
    expect(find.byKey(const ValueKey('oi-approval-card')), findsOneWidget);
    expect(find.text('Only these buttons approve. Typed text never does.'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('oi-deny')));
    await tester.pump();
    expect(rt.commands.last['command'], 'oi_decide');
    expect(rt.commands.last['approve'], false);
    expect(rt.commands.last['approval_digest'], digest);
  });

  testWidgets('Brain picker lists only selectable rows and selection is explicit', (tester) async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await tester.runAsync(conv.refreshStatus);
    await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
    await tester.pump();
    // Readiness is shown in plain words (FCV-R review R1-12); the raw code stays in the Dashboard detail.
    expect(find.textContaining('· ready'), findsOneWidget);
    expect(find.textContaining('READY'), findsNothing);
    await tester.tap(find.byKey(const ValueKey('oi-brain-picker')));
    await tester.pumpAndSettle();
    expect(find.text('Anthropic Claude (cloud)'), findsNothing);
    await tester.tap(find.text('No Brain (deterministic rules)').last);
    await tester.pumpAndSettle();
    expect(rt.commands.where((c) => c['command'] == 'brain_select').single['row_id'], 'deterministic');
  });

  test('legacy address detection', () {
    expect(isLegacyServerAddress('http://localhost:8000'), isTrue);
    expect(isLegacyServerAddress('http://127.0.0.1:8000/'), isTrue);
    expect(isLegacyServerAddress('http://127.0.0.1:18300'), isFalse);
    expect(isLegacyServerAddress('http://192.168.1.5:8000'), isFalse);
  });

  testWidgets('root: worker start failure is reported honestly', (tester) async {
    SharedPreferences.setMockInitialValues({});
    var attempts = 0;
    await tester.pumpWidget(WorkingSystemRoot(
      connect: () async {
        attempts++;
        throw IntegratedRuntimeException('WORKER_PROFILE_MISMATCH');
      },
      classicBuilder: (back) => const Directionality(textDirection: TextDirection.ltr, child: Text('CLASSIC')),
    ));
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(find.textContaining('WORKER_PROFILE_MISMATCH'), findsOneWidget);
    expect(attempts, 1);
    await tester.tap(find.text('Open the classic interface'));
    for (var i = 0; i < 5; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(find.text('CLASSIC'), findsOneWidget);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString(wsShellPref), 'classic');
  });

  testWidgets('root: Living is the default shell; opening classic closes the integrated worker first', (tester) async {
    SharedPreferences.setMockInitialValues({'uri.living.onboardingDone': true});
    final rt = FakeRuntime();
    await tester.pumpWidget(WorkingSystemRoot(
      connect: () async => rt,
      skipOnboarding: true,
      statusInterval: const Duration(hours: 1),
      classicBuilder: (back) => const Directionality(textDirection: TextDirection.ltr, child: Text('CLASSIC')),
    ));
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    final sw = tester.widget<WorkingSystemShellSwitch>(find.byType(WorkingSystemShellSwitch));
    expect(rt.commands.any((c) => c['command'] == 'brain_status'), isTrue);
    sw.openClassic();
    for (var i = 0; i < 10; i++) {
      await tester.pump(const Duration(milliseconds: 50));
    }
    expect(rt.closed, isTrue);
    expect(find.text('CLASSIC'), findsOneWidget);
  });

  test('events that arrive before the turn is registered are replayed, not lost', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    rt.emit('t1', 'answer.delta', {'text': 'early '});
    await pumpEventQueue();
    await conv.send('hello');
    rt.emit('t1', 'answer.delta', {'text': 'late'});
    rt.emit('t1', 'turn.finished', {'status': 'ok'});
    await pumpEventQueue();
    expect(conv.messages.last.text, 'early late');
    expect(conv.busy, isFalse);
  });

  test('a decision whose events beat its reply still ends the turn', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await conv.send('remember that x');
    rt.emit('t1', 'approval.required', {'capability_id': 'remember_fact', 'arguments': {}, 'approval_digest': digest});
    rt.emit('t1', 'turn.finished', {'status': 'needs_user'});
    await pumpEventQueue();
    final f = conv.decide(approve: false);
    rt.emit('t1', 'core.result', {'code': 'APPROVAL_DENIED', 'needs': 'none'});
    rt.emit('t1', 'turn.finished', {'status': 'refused'});
    await f;
    await pumpEventQueue();
    expect(conv.messages.last.coreCode, 'APPROVAL_DENIED');
    expect(conv.busy, isFalse);
  });

  test('the card can be decided while its own turn is still finishing', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await conv.send('remember that x');
    rt.emit('t1', 'approval.required', {'capability_id': 'remember_fact', 'arguments': {}, 'approval_digest': digest});
    await pumpEventQueue();
    expect(conv.busy, isTrue); // turn.finished not yet received
    await conv.decide(approve: true);
    expect(rt.commands.last['command'], 'oi_decide');
  });

  test("the original job's late turn.finished does not end the decision's continuation", () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await conv.send('remember that x');
    rt.emit('t1', 'approval.required', {'capability_id': 'remember_fact', 'arguments': {}, 'approval_digest': digest});
    await pumpEventQueue();
    await conv.decide(approve: true); // clicked before the original job's turn.finished arrived
    rt.emit('t1', 'turn.finished', {'status': 'needs_user'}); // original job
    await pumpEventQueue();
    expect(conv.busy, isTrue, reason: 'the decision job is still running');
    rt.emit('t1', 'core.result', {'code': 'SETTLED_VERIFIED', 'needs': 'none'});
    rt.emit('t1', 'turn.finished', {'status': 'ok'}); // decision job
    await pumpEventQueue();
    expect(conv.busy, isFalse);
    expect(conv.messages.last.coreCode, 'SETTLED_VERIFIED');
  });

  test('a refused confirmation keeps its card when the refusal is transient', () async {
    final rt = _RefusingRuntime('TURN_IN_PROGRESS');
    final conv = OiConversation(rt);
    await conv.send('remember that x');
    rt.emit('t1', 'core.result', {'code': 'INTENT_CONFIRMATION_REQUIRED', 'needs': 'confirmation', 'message': 'ok?'});
    rt.emit('t1', 'turn.finished', {'status': 'needs_user'});
    await pumpEventQueue();
    await conv.confirm();
    expect(conv.pendingConfirmation, isNotNull);
    expect(conv.busy, isFalse);
  });

  _timeoutTests();
}

void _timeoutTests() {
  test('a timed-out confirmation also stays busy without a retry card', () async {
    final rt = _RefusingRuntime('WORKER_TIMEOUT');
    final conv = OiConversation(rt);
    await conv.send('remember that x');
    rt.emit('t1', 'core.result', {'code': 'INTENT_CONFIRMATION_REQUIRED', 'needs': 'confirmation'});
    rt.emit('t1', 'turn.finished', {'status': 'needs_user'});
    await pumpEventQueue();
    await conv.confirm();
    expect(conv.pendingConfirmation, isNull);
    expect(conv.busy, isTrue);
  });

  test('worker exit clears busy and shows the error state', () async {
    final rt = FakeRuntime();
    final conv = OiConversation(rt);
    await conv.send('hello');
    expect(conv.busy, isTrue);
    rt._events.add({'type': 'worker.exited', 'turn_id': null, 'data': const {}});
    await pumpEventQueue();
    expect(conv.busy, isFalse);
    expect(conv.workerExited, isTrue);
  });

  test('a timed-out decision is an unknown outcome: busy, no retry card, reconciled by its turn.finished', () async {
    final rt = _RefusingRuntime('WORKER_TIMEOUT');
    final conv = OiConversation(rt);
    await conv.send('remember that x');
    rt.emit('t1', 'approval.required', {'capability_id': 'remember_fact', 'arguments': {}, 'approval_digest': digest});
    rt.emit('t1', 'turn.finished', {'status': 'needs_user'});
    await pumpEventQueue();
    await conv.decide(approve: true);
    expect(conv.pendingApproval, isNull);
    expect(conv.busy, isTrue);
    rt.emit('t1', 'core.result', {'code': 'SETTLED_VERIFIED', 'needs': 'none'});
    rt.emit('t1', 'turn.finished', {'status': 'ok'});
    await pumpEventQueue();
    expect(conv.busy, isFalse);
  });
}

class _RefusingRuntime extends FakeRuntime {
  _RefusingRuntime(this.code);
  final String code;
  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    if (command['command'] == 'oi_confirm' || command['command'] == 'oi_decide') {
      commands.add(command);
      throw IntegratedRuntimeException(code);
    }
    return super.call(command);
  }
}
