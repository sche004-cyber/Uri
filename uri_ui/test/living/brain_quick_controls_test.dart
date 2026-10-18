import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:uri_ui/living/integration/brain_quick_controls.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/qc_toggle.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/services/integrated_runtime.dart';

import '../ws/ws_integration_test.dart' show host;
import 'uiv2_postint_test.dart' show pumpRoot, settle;

/// BRAIN-QC-20261018: Thinking / Vision / Context quick controls. The
/// `controls` maps mirror `uri_operational_intelligence.brain_quick_controls`
/// (catalog order: standard, long, standard-nodraft, long-vision).

Map<String, dynamic> opt(String id, String label, String summary, int ctx, String vision, bool mtp, bool qualified,
        int mib, {bool active = false, String? reason}) =>
    {
      'id': id,
      'label': label,
      'summary': summary,
      'ctx': ctx,
      'vision': vision,
      'vision_on': vision != 'off',
      'mtp': mtp,
      'qualified': qualified,
      'required_mib': mib,
      'active': active,
      'reason': ?reason,
    };

const lvReason = 'Not qualified yet: in tests it crashed once and slowed to a fifth of its speed next to a browser '
    '(findings CRASH-1, DEMOTE-P1).';

List<Map<String, dynamic>> options({String? active}) => [
      opt('standard', 'Standard', '32K context, vision on (the default Runtime v1)', 32768, 'gpu', true, true, 15620,
          active: active == 'standard'),
      opt('long', 'Long context', '64K context, vision off', 65536, 'off', false, true, 13658,
          active: active == 'long'),
      {...opt('standard-nodraft', 'Standard (no draft)', '32K context, vision on, no speculative draft', 32768, 'gpu',
          false, true, 14360, active: active == 'standard-nodraft'), 'switchable': false},
      opt('long-vision', 'Long context with vision', '64K context, vision on', 65536, 'gpu', false, false, 14764,
          reason: lvReason),
    ];

Map<String, dynamic> controls({String? active, bool pending = false, Map<String, dynamic>? last, bool canSwitch = true}) {
  final opts = options(active: active);
  return {
    'schema': 'uri.brain.quick_controls.v1',
    'active': active == null ? null : opts.firstWhere((o) => o['id'] == active),
    'configured': {'id': active == 'long' ? 'c64k-visoff-mtpoff' : 'frozen', 'ctx': active == 'long' ? 65536 : 32768,
        'vision': active == 'long' ? 'off' : 'gpu', 'mtp': active != 'long'},
    'switch': {'pending': pending, 'target': pending ? {'id': 'long', 'label': 'Long context'} : null, 'last': last},
    'options': opts,
    'thinking': {'off': 'fast', 'on': 'normal', 'auto': 'auto', 'reload': false},
    'can_switch': canSwitch,
    'cannot_switch_reason': canSwitch ? null : 'BRAIN_HOST_NOT_RUNNING',
  };
}

class QcRuntime implements IntegratedRuntime {
  final commands = <Map<String, dynamic>>[];
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  Map<String, dynamic> health = {'state': 'READY', 'controls': controls(active: 'standard')};
  Map<String, dynamic> Function(Map<String, dynamic>)? onReconfigure;
  String? refuse;
  Map<String, dynamic> status = {'state': 'READY'};
  String? statusError;

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;
  @override
  bool get closed => false;
  @override
  Future<void> close() async {}
  @override
  Future<void> kill() async {}

  void emit(String turnId, String type, [Map<String, dynamic> data = const {}]) =>
      _events.add({'schema': 'uri.oi.event.v1', 'turn_id': turnId, 'type': type, 'data': data});

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    commands.add(command);
    switch (command['command']) {
      case 'brain_health':
        return health;
      case 'brain_status':
        if (statusError != null) throw IntegratedRuntimeException(statusError!);
        return status;
      case 'brain_reconfigure':
        if (refuse != null) throw IntegratedRuntimeException(refuse!);
        return onReconfigure?.call(command) ??
            {'requested': 'reconfigure', 'request_id': 'req-1', 'target': {'id': command['profile_id']}};
      case 'oi_turn':
        return {'turn_id': 't${commands.length}', 'accepted': true};
      default:
        return {};
    }
  }
}

Future<OiConversation> ready(QcRuntime rt) async {
  final conv = OiConversation(rt);
  await conv.refreshHealth();
  return conv;
}

Future<void> pumpControls(WidgetTester tester, OiConversation conv) async {
  await tester.pumpWidget(host(ListenableBuilder(
    listenable: conv,
    builder: (_, _) => Align(alignment: Alignment.topLeft, child: BrainQuickControls(conversation: conv)),
  )));
  await tester.pump();
}

List<String> titles(List<QcChoice> xs) => [for (final x in xs) x.title];

QcToggle toggle(WidgetTester t, String key) => t.widget<QcToggle>(find.byKey(ValueKey(key)));
QcSegmented segmented(WidgetTester t) => t.widget<QcSegmented>(find.byKey(const ValueKey('qc-context')));
QcSegment segment(WidgetTester t, String label) => segmented(t).segments.firstWhere((s) => s.label == label);

void main() {
  group('choice resolution', () {
    final opts = [for (final o in options()) QcOption(o)];

    test('from Standard: vision off and 64K both lead to Long context, 64K + vision is disabled', () {
      final active = options(active: 'standard').first;
      final vis = visionChoices(opts, active);
      expect(titles(vis), ['On', 'Off']);
      expect(vis[0].current, isTrue);
      expect(vis[1].target!.id, 'long');
      expect(vis[1].note, contains('Also changes context to 64K'));
      final ctx = contextChoices(opts, active);
      expect(titles(ctx), ['32K', '64K with vision on', '64K']);
      expect(ctx[0].current, isTrue);
      expect(ctx[1].target, isNull);
      expect(ctx[1].blocked, lvReason);
      expect(ctx[2].target!.id, 'long');
      expect(ctx[2].note, contains('Turns vision off'));
    });

    test('from Long context: vision on is offered only with 32K (Standard, the frozen default)', () {
      final active = options(active: 'long')[1];
      final vis = visionChoices(opts, active);
      expect(titles(vis), ['On at 64K', 'On', 'Off']);
      expect(vis[0].blocked, lvReason);
      expect(vis[1].target!.id, 'standard', reason: 'catalog order prefers the frozen default for 32K + vision');
      expect(vis[1].note, contains('Also changes context to 32K'));
      expect(vis[2].current, isTrue);
      final ctx = contextChoices(opts, active);
      expect(ctx[0].title, '32K');
      expect(ctx[0].target!.id, 'standard');
      expect(ctx[0].note, contains('Turns vision on'));
      expect(ctx.last.current, isTrue);
    });

    test('an unqualified option is never a target', () {
      for (final active in [null, options(active: 'standard').first, options(active: 'long')[1]]) {
        for (final ch in [...visionChoices(opts, active), ...contextChoices(opts, active)]) {
          expect(ch.target?.qualified ?? true, isTrue);
          expect(ch.target?.id, isNot('long-vision'));
          expect(ch.target?.id, isNot('standard-nodraft'), reason: 'P3 is recognized but never a target');
        }
      }
    });
  });

  group('truthfulness', () {
    testWidgets('a profile not yet verified is never shown as current', (tester) async {
      final rt = QcRuntime()..health = {'state': 'RECOVERING', 'controls': controls()};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      // configured vision on, but not verified: no glow, no selected size, and the status says why
      expect(toggle(tester, 'qc-vision').visual, QcVisual.off);
      expect(toggle(tester, 'qc-vision').status, 'starting');
      expect(segmented(tester).status, 'starting');
      expect(segmented(tester).segments.where((s) => s.selected), isEmpty);
      rt.health = {'state': 'UNAVAILABLE', 'controls': controls()};
      await conv.refreshHealth();
      await tester.pump();
      expect(segmented(tester).status, 'not running');
      rt.health = {'state': 'READY', 'controls': controls(active: 'standard')};
      await conv.refreshHealth();
      await tester.pump();
      expect(toggle(tester, 'qc-vision').visual, QcVisual.on);
      expect(toggle(tester, 'qc-vision').status, isNull);
      expect(segment(tester, '32K').selected, isTrue);
    });

    testWidgets('while a switch runs the controls say so and offer nothing', (tester) async {
      final rt = QcRuntime()..health = {'state': 'RECOVERING', 'controls': controls(pending: true)};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(find.byKey(const ValueKey('qc-switching')), findsOneWidget);
      expect(find.text('Switching to Long context…'), findsOneWidget);
      // the reload controls show the loading state: no glow, not choosable
      expect(toggle(tester, 'qc-vision').visual, QcVisual.loading);
      expect(segmented(tester).loading, isTrue);
      await tester.tap(find.byKey(const ValueKey('qc-context-64K')), warnIfMissed: false);
      await tester.tap(find.byKey(const ValueKey('qc-vision')), warnIfMissed: false);
      await tester.pump(const Duration(milliseconds: 500));
      expect(find.byKey(const ValueKey('qc-confirm-switch')), findsNothing);
      expect(toggle(tester, 'qc-thinking').onPressed, isNotNull, reason: 'Thinking never reloads');
    });

    test('R1-01: the header never reads ready while a switch runs (status READY at the edge, STOPPED later)', () async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await conv.refreshHealth();
      conv.brainStatus = {'state': 'READY'};
      // the edge READY -> RECOVERING: the old server still answers READY (what happens live)
      rt.health = {'state': 'RECOVERING', 'controls': controls(pending: true)};
      rt.status = {'state': 'READY', 'model_id': 'qwen-test'};
      await conv.refreshHealth();
      expect(conv.brainStatus['state'], 'STARTING', reason: 'not the confirmed Brain while the switch is pending');
      expect(conv.brainStatus['runtime_state'], 'READY');
      expect(conv.brainReady, isFalse);
      // later polls, health unchanged (RECOVERING): the status is re-read every time
      rt.status = {'state': 'STOPPED'};
      await conv.refreshHealth();
      expect(conv.brainStatus['state'], 'STOPPED');
      rt.status = {'state': 'LOADING'};
      await conv.refreshHealth();
      expect(conv.brainStatus['state'], 'LOADING');
      // the new server answers before its calibration: still not ready while the switch is pending
      rt.status = {'state': 'READY'};
      await conv.refreshHealth();
      expect(conv.brainStatus['state'], 'STARTING');
      // switch finished: READY on the new profile
      rt.health = {'state': 'READY', 'controls': controls(active: 'long')};
      await conv.refreshHealth();
      expect(conv.brainStatus['state'], 'READY');
      final n = rt.commands.where((c) => c['command'] == 'brain_status').length;
      await conv.refreshHealth();                    // steady READY: no extra status call
      expect(rt.commands.where((c) => c['command'] == 'brain_status').length, n);
    });

    test('R2-01: a failed status read when the switch ends does not leave the masked "starting" behind', () async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await conv.refreshHealth();
      rt.health = {'state': 'RECOVERING', 'controls': controls(pending: true)};
      rt.status = {'state': 'READY'};
      await conv.refreshHealth();
      expect(conv.brainStatus['state'], 'STARTING');
      // the switch ends, but the status read on that very poll fails
      rt.health = {'state': 'READY', 'controls': controls(active: 'long')};
      rt.statusError = 'WORKER_TIMEOUT';
      await conv.refreshHealth();
      expect(conv.brainStatus['switching'], isTrue, reason: 'the failed read left the mask');
      // the next poll (health unchanged, READY) re-reads because the mask is still there
      rt.statusError = null;
      await conv.refreshHealth();
      expect(conv.brainStatus['state'], 'READY');
      expect(conv.brainStatus['switching'], isNull);
      expect(conv.brainReady, isTrue);
    });

    testWidgets('a worker without quick controls shows only Thinking', (tester) async {
      final rt = QcRuntime()..health = {'state': 'READY'};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(find.byKey(const ValueKey('qc-thinking')), findsOneWidget);
      expect(find.byKey(const ValueKey('qc-vision')), findsNothing);
    });
  });

  group('switching', () {
    testWidgets('choosing 64K asks first, then sends one reconfigure for Long context', (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      // a selection of the two sizes; the unqualified 64K + vision is explained on the 64K segment, never offered
      expect([for (final s in segmented(tester).segments) s.label], ['32K', '64K']);
      expect(segment(tester, '64K').tooltip, contains(lvReason));
      expect(segment(tester, '64K').tooltip, contains('Turns vision off'));
      await tester.tap(find.byKey(const ValueKey('qc-context-64K')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('qc-confirm-switch')), findsOneWidget);
      expect(find.textContaining('Your conversation stays'), findsOneWidget);
      expect(find.text('13.3 GB'), findsOneWidget);
      expect(find.text('15.3 GB'), findsOneWidget);
      expect(find.textContaining('64K with vision on: $lvReason'), findsOneWidget);
      expect(find.textContaining('URI goes back to the current one automatically'), findsOneWidget);
      // Cancel sends nothing
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(rt.commands.where((c) => c['command'] == 'brain_reconfigure'), isEmpty);
      await tester.tap(find.byKey(const ValueKey('qc-context-64K')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('qc-confirm-switch-go')));
      await tester.pumpAndSettle();
      final sent = rt.commands.where((c) => c['command'] == 'brain_reconfigure').toList();
      expect(sent, [
        {'command': 'brain_reconfigure', 'profile_id': 'long'},
      ]);
      expect(conv.profileRequestId, 'req-1');
    });

    testWidgets('R1-02: a conversation that does not fit the smaller context is refused with the numbers', (tester) async {
      final rt = QcRuntime()..health = {'state': 'READY', 'controls': controls(active: 'long')};
      rt.onReconfigure = (c) => {'requested': null, 'refused': 'CONTEXT_SMALLER_THAN_CONVERSATION',
          'detail': {'live_tokens': 30000, 'answer_reserve': 4096, 'ctx': 32768}};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      await tester.tap(find.byKey(const ValueKey('qc-context-32K')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('qc-confirm-switch-go')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('qc-confirm-shrink')), findsNothing, reason: 'no "switch anyway" path');
      expect(find.textContaining('about 30000 tokens'), findsOneWidget);
      expect(find.textContaining('Keep the larger context'), findsOneWidget);
      // R2-02 / R3-02: worded for every conversation the worker has held, not only this one
      expect(find.textContaining('a conversation URI has held since it started'), findsOneWidget);
      expect(find.textContaining('until URI is restarted'), findsOneWidget);
      final sent = rt.commands.where((c) => c['command'] == 'brain_reconfigure').toList();
      expect(sent, [
        {'command': 'brain_reconfigure', 'profile_id': 'standard'},
      ]);
    });

    testWidgets('R1-08.1: a refusal notice clears after its time', (tester) async {
      final rt = QcRuntime()..refuse = 'TURN_IN_PROGRESS';
      final conv = await ready(rt);
      await conv.reconfigureBrain('long');
      expect(conv.profileNotice, isNotNull);
      final keep = OiConversation.profileNoticeFor;
      OiConversation.profileNoticeFor = Duration.zero;
      addTearDown(() => OiConversation.profileNoticeFor = keep);
      await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 5)));
      expect(conv.profileNotice, isNull);
    });

    testWidgets('R1-08.2/.3: non-final outcomes are explained; a stopped Brain is started only with a warning',
        (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await conv.reconfigureBrain('long');
      rt.health = {'state': 'UNAVAILABLE', 'controls': controls(last: {'id': 'req-1', 'result': 'WAITING_FOR_GPU'})};
      await conv.refreshHealth();
      await pumpControls(tester, conv);
      expect(find.text('The new setting is waiting for GPU memory. Choose the previous setting to go back.'),
          findsOneWidget);
      rt.health = {'state': 'UNAVAILABLE', 'host': {'state': 'STOPPED'}, 'controls': controls(last: {'id': 'req-1', 'result': 'STOPPED'})};
      await conv.refreshHealth();
      await tester.pump();
      expect(find.text('The switch was stopped; the Brain is not running.'), findsOneWidget);
      expect(toggle(tester, 'qc-vision').visual, QcVisual.error, reason: 'no Brain serves after a stopped switch');
      await tester.tap(find.byKey(const ValueKey('qc-context-64K')));
      await tester.pumpAndSettle();
      expect(find.textContaining('The Brain is stopped now: switching starts it'), findsOneWidget);
      // no automatic going back when nothing was running before
      expect(find.textContaining('If the new setting fails to start, URI says so'), findsOneWidget);
    });

    testWidgets('a refusal is explained and nothing is shown as switched', (tester) async {
      final rt = QcRuntime()..refuse = 'BRAIN_RESTARTING';
      final conv = await ready(rt);
      await conv.reconfigureBrain('long');
      await pumpControls(tester, conv);
      expect(find.text('Not switched: the Brain is already restarting or switching.'), findsOneWidget);
      expect(toggle(tester, 'qc-vision').visual, QcVisual.on);
    });

    testWidgets('the host outcome of this UI request is reported once it is final', (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await conv.reconfigureBrain('long');
      rt.health = {
        'state': 'READY',
        'controls': controls(active: 'standard', last: {'id': 'req-1', 'result': 'REFUSED_DOES_NOT_FIT',
            'explain': 'The Brain was not switched. The Brain needs 13.3 GB of GPU memory but only 12.0 GB is free.'}),
      };
      await conv.refreshHealth();
      await pumpControls(tester, conv);
      expect(find.textContaining('The Brain was not switched.'), findsOneWidget);
      rt.health = {
        'state': 'READY',
        'controls': controls(active: 'long', last: {'id': 'req-1', 'result': 'READY', 'seconds': 31.2}),
      };
      await conv.refreshHealth();
      await tester.pump();
      expect(find.text('Brain switched in 31 s. Your conversation is kept.'), findsOneWidget);
      expect(segment(tester, '64K').selected, isTrue);
      expect(toggle(tester, 'qc-vision').visual, QcVisual.off);
    });

    testWidgets('no switch while URI is answering or without the Brain host', (tester) async {
      final rt = QcRuntime()..health = {'state': 'READY', 'controls': controls(active: 'standard', canSwitch: false)};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      await tester.tap(find.byKey(const ValueKey('qc-context-64K')), warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('qc-confirm-switch')), findsNothing, reason: 'selection disabled');
      expect(segment(tester, '64K').tooltip, contains('Not switched: the Brain host is not running'));
      rt.health = {'state': 'READY', 'controls': controls(active: 'standard')};
      await conv.refreshHealth();
      await conv.send('hello');                      // a turn is now running
      await tester.pump();
      expect(toggle(tester, 'qc-vision').onPressed, isNull);
      await tester.tap(find.byKey(const ValueKey('qc-vision')), warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('qc-confirm-switch')), findsNothing);
      expect(await conv.reconfigureBrain('long'), isNull);
      expect(rt.commands.where((c) => c['command'] == 'brain_reconfigure'), isEmpty);
    });
  });

  group('thinking', () {
    testWidgets('Thinking On / Off is the next turn depth and reports what the answer did', (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(toggle(tester, 'qc-thinking').status, 'Auto');
      expect(toggle(tester, 'qc-thinking').visual, QcVisual.off);
      // push to enable: one click turns it on (and it glows) ...
      await tester.tap(find.byKey(const ValueKey('qc-thinking')));
      await tester.pumpAndSettle();
      expect(conv.depth, OiDepth.normal);
      expect(toggle(tester, 'qc-thinking').visual, QcVisual.on);
      expect(toggle(tester, 'qc-thinking').status, isNull);
      // ... the next turns it off, the next on again
      await tester.tap(find.byKey(const ValueKey('qc-thinking')));
      await tester.pumpAndSettle();
      expect(conv.depth, OiDepth.fast);
      expect(toggle(tester, 'qc-thinking').visual, QcVisual.off);
      await tester.tap(find.byKey(const ValueKey('qc-thinking')));
      await tester.pumpAndSettle();
      expect(conv.depth, OiDepth.normal);
      await conv.send('compare these two plans');
      final turn = rt.commands.lastWhere((c) => c['command'] == 'oi_turn');
      expect(turn['depth'], 'normal');
      final id = conv.activeTurnId!;
      rt.emit(id, 'turn.routed', {'route': 'answer', 'tier': {'tier': 'NORMAL'}});
      rt.emit(id, 'answer.delta', {'text': 'ok'});
      rt.emit(id, 'turn.finished', {'status': 'ok'});
      await tester.pump();
      expect(conv.lastAnswerTier, 'NORMAL');
      await tester.tap(find.byKey(const ValueKey('qc-thinking-menu')));
      await tester.pumpAndSettle();
      expect(find.text('Last answer: thought first'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('qc-thinking-Auto')));
      await tester.pumpAndSettle();
      expect(conv.depth, OiDepth.auto, reason: 'Auto stays one menu choice away');
      expect(rt.commands.where((c) => c['command'] == 'brain_reconfigure'), isEmpty, reason: 'no reload');
    });
  });

  testWidgets('the Workspace composer carries the quick controls', (tester) async {
    final (_, services) = await pumpRoot(tester, const Size(1280, 860));
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
    await settle(tester);
    expect(find.byKey(const ValueKey('qc-thinking')), findsOneWidget);
  });

  testWidgets('R1-08.4: in a small window the chip row steps aside and one compact button opens the controls',
      (tester) async {
    final (_, services) = await pumpRoot(tester, const Size(800, 600));
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
    await settle(tester);
    expect(find.byKey(const ValueKey('qc-thinking')), findsNothing);
    expect(find.byKey(const ValueKey('qc-compact')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('qc-compact')));
    await settle(tester);
    expect(find.byKey(const ValueKey('qc-compact-dialog')), findsOneWidget);
    expect(find.byKey(const ValueKey('qc-thinking')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
