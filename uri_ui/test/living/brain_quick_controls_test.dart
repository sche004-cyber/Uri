import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:uri_ui/living/assist/assist_controller.dart';
import 'package:uri_ui/living/integration/brain_quick_controls.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/qc_toggle.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'package:uri_ui/theme/uri_theme.dart';

import '../ws/ws_integration_test.dart' show host;
import 'uiv2_postint_test.dart' show pumpRoot, settle;

/// Quick controls (BRAIN-QC-20261018; URI-CONTROLS-3: Thinking / Vision /
/// URI Assist, exactly three ON / OFF toggles). The
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
      opt('standard-nodraft', 'Standard, draft off', '32K context, vision on, no speculative draft (about 1.2 GB less '
          'GPU memory)', 32768, 'gpu', false, true, 14360, active: active == 'standard-nodraft'),
      opt('long-vision', 'Long context with vision', '64K context, vision on', 65536, 'gpu', false, false, 14764,
          reason: lvReason),
    ];

Map<String, dynamic> controls({String? active, bool pending = false, Map<String, dynamic>? last, bool canSwitch = true,
    Map<String, dynamic>? mismatch, bool visionLocked = false}) {
  final opts = options(active: active);
  return {
    'mismatch': mismatch,
    'vision_locked': visionLocked,
    'schema': 'uri.brain.quick_controls.v1',
    'active': active == null ? null : opts.firstWhere((o) => o['id'] == active),
    'configured': {'id': active == 'long' ? 'c64k-visoff-mtpoff' : 'frozen', 'ctx': active == 'long' ? 65536 : 32768,
        'vision': active == 'long' ? 'off' : 'gpu', 'mtp': active != 'long'},
    'switch': {'pending': pending, 'target': pending ? {'id': 'long', 'label': 'Long context'} : null, 'last': last},
    'options': opts,
    'thinking': {'off': 'fast', 'on': 'normal', 'auto': 'auto', 'reload': false},
    'can_switch': canSwitch,
    'cannot_switch_reason': canSwitch ? null : 'BRAIN_HOST_NOT_RUNNING',
    // the worker's Assist state (worker_bridge._assist): a grant locks vision on
    'assist': {'asking': false, 'granted': visionLocked},
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
  Map<String, dynamic> assistStatus = {'state': 'OFF'};

  /// When set, brain_health's controls.assist follows [assistStatus], as the real worker's does.
  bool assistLinked = false;

  /// When set, assist_status fails with this code.
  String? assistError;

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
        final c = health['controls'];
        // a fresh Map per reading, as a decoded worker reply is (review R4-03)
        if (!assistLinked || c is! Map) return Map.of(health);
        final granted = assistStatus['state'] == 'ACTIVE' || assistStatus['state'] == 'PAUSED';
        return {...health, 'controls': {...c, 'assist': {'asking': false, 'granted': granted}, 'vision_locked': granted}};
      case 'brain_status':
        if (statusError != null) throw IntegratedRuntimeException(statusError!);
        return status;
      case 'brain_reconfigure':
        if (refuse != null) throw IntegratedRuntimeException(refuse!);
        return onReconfigure?.call(command) ??
            {'requested': 'reconfigure', 'request_id': 'req-1', 'target': {'id': command['profile_id']}};
      case 'oi_turn':
        return {'turn_id': 't${commands.length}', 'accepted': true};
      case 'assist_status':
        if (assistError != null) throw IntegratedRuntimeException(assistError!);
        return assistStatus;
      case 'assist_grant':
        return assistStatus = {'state': 'ACTIVE'};
      case 'assist_revoke':
        return assistStatus = {'state': 'OFF'};
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

Future<void> pumpControls(WidgetTester tester, OiConversation conv,
    {AssistController? assist, VoidCallback? openAssist}) async {
  await tester.pumpWidget(host(ListenableBuilder(
    listenable: conv,
    builder: (_, _) => Align(
        alignment: Alignment.topLeft,
        child: BrainQuickControls(conversation: conv, assist: assist, openAssist: openAssist)),
  )));
  await tester.pump();
}

List<String> titles(List<QcChoice> xs) => [for (final x in xs) x.title];

QcToggle toggle(WidgetTester t, String key) => t.widget<QcToggle>(find.byKey(ValueKey(key)));

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
    });

    test('from Long context: vision on is offered only with 32K (Standard, the frozen default)', () {
      // Keep the original baseline identity and its legacy-catalog fallback coverage.
      final legacy = opts.where((o) => o.id != 'standard-nodraft').toList();
      final active = options(active: 'long')[1];
      final vis = visionChoices(legacy, active);
      expect(titles(vis), ['On at 64K', 'On', 'Off']);
      expect(vis[0].blocked, lvReason);
      expect(vis[1].target!.id, 'standard', reason: 'an older worker can offer only the frozen vision fallback');
      expect(vis[1].note, contains('Also changes context to 32K'));
      expect(vis[2].current, isTrue);
    });

    test('from Long context: vision on prefers the qualified lighter 32K profile', () {
      final vis = visionChoices(opts, options(active: 'long')[1]);
      expect(vis.firstWhere((c) => c.target != null).target!.id, 'standard-nodraft');
    });

    test('an unswitchable lighter profile is never preferred', () {
      final raw = options();
      raw[2]['switchable'] = false;
      final filtered = [for (final o in raw) QcOption(o)];
      final choice = visionChoices(filtered, options(active: 'long')[1]).firstWhere((c) => c.target != null);
      expect(choice.target!.id, 'standard');
    });

    test('an unqualified option is never a target', () {
      for (final active in [null, options(active: 'standard').first, options(active: 'long')[1]]) {
        for (final ch in visionChoices(opts, active)) {
          expect(ch.target?.qualified ?? true, isTrue);
          expect(ch.target?.id, isNot('long-vision'));
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
      rt.health = {'state': 'UNAVAILABLE', 'controls': controls()};
      await conv.refreshHealth();
      await tester.pump();
      expect(toggle(tester, 'qc-vision').status, 'not running');
      rt.health = {'state': 'READY', 'controls': controls(active: 'standard')};
      await conv.refreshHealth();
      await tester.pump();
      expect(toggle(tester, 'qc-vision').visual, QcVisual.on);
      expect(toggle(tester, 'qc-vision').status, isNull);
    });

    testWidgets('while a switch runs the controls say so and offer nothing', (tester) async {
      final rt = QcRuntime()..health = {'state': 'RECOVERING', 'controls': controls(pending: true)};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(find.byKey(const ValueKey('qc-switching')), findsOneWidget);
      expect(find.text('Switching to Long context…'), findsOneWidget);
      // the reload controls show the loading state: no glow, not choosable
      expect(toggle(tester, 'qc-vision').visual, QcVisual.loading);
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

    testWidgets('a worker without quick controls shows Thinking and URI Assist, no Vision', (tester) async {
      final rt = QcRuntime()..health = {'state': 'READY'};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(find.byKey(const ValueKey('qc-thinking')), findsOneWidget);
      expect(find.byKey(const ValueKey('qc-vision')), findsNothing);
      expect(toggle(tester, 'qc-assist').onPressed, isNull, reason: 'no Assist mirror here: shown unavailable');
      expect(toggle(tester, 'qc-assist').status, 'unavailable');
    });
  });

  group('switching', () {
    testWidgets('Vision off asks first, then sends one reconfigure for Long context', (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(toggle(tester, 'qc-vision').tooltip, contains('Also changes context to 64K'));
      await tester.tap(find.byKey(const ValueKey('qc-vision')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('qc-confirm-switch')), findsOneWidget);
      expect(find.textContaining('Your conversation stays'), findsOneWidget);
      expect(find.text('13.3 GB'), findsOneWidget);
      expect(find.text('15.3 GB'), findsOneWidget);
      expect(find.textContaining('URI goes back to the current one automatically'), findsOneWidget);
      // R1-06: memory taken by another program between the check and the start is stated
      expect(find.textContaining('URI waits and says so'), findsOneWidget);
      // Cancel sends nothing
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(rt.commands.where((c) => c['command'] == 'brain_reconfigure'), isEmpty);
      await tester.tap(find.byKey(const ValueKey('qc-vision')));
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
      await tester.tap(find.byKey(const ValueKey('qc-vision')));
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
        {'command': 'brain_reconfigure', 'profile_id': 'standard-nodraft'},
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
      await tester.tap(find.byKey(const ValueKey('qc-vision')));
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
      expect(toggle(tester, 'qc-vision').visual, QcVisual.off);
    });

    testWidgets('no switch while URI is answering or without the Brain host', (tester) async {
      final rt = QcRuntime()..health = {'state': 'READY', 'controls': controls(active: 'standard', canSwitch: false)};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      await tester.tap(find.byKey(const ValueKey('qc-vision')), warnIfMissed: false);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('qc-confirm-switch')), findsNothing, reason: 'toggle disabled');
      expect(toggle(tester, 'qc-vision').tooltip, contains('Not switched: the Brain host is not running'));
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
    testWidgets('Thinking is On / Off only, is the next turn depth and reports what the answer did', (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      // URI-CONTROLS-3: Off until the user turns it on; no Auto state and no menu
      expect(conv.depth, OiDepth.fast);
      expect(toggle(tester, 'qc-thinking').status, isNull);
      expect(toggle(tester, 'qc-thinking').visual, QcVisual.off);
      expect(find.byKey(const ValueKey('qc-thinking-menu')), findsNothing);
      await tester.tap(find.byKey(const ValueKey('qc-thinking')));
      await tester.pumpAndSettle();
      expect(conv.depth, OiDepth.normal);
      expect(toggle(tester, 'qc-thinking').visual, QcVisual.on);
      await tester.tap(find.byKey(const ValueKey('qc-thinking')));
      await tester.pumpAndSettle();
      expect(conv.depth, OiDepth.fast);
      expect(toggle(tester, 'qc-thinking').visual, QcVisual.off);
      await conv.send('hello');
      expect(rt.commands.lastWhere((c) => c['command'] == 'oi_turn')['depth'], 'fast');
      rt.emit(conv.activeTurnId!, 'turn.finished', {'status': 'ok'});
      await tester.pump();
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
      expect(toggle(tester, 'qc-thinking').tooltip, contains('Last answer: thought first'));
      expect(rt.commands.where((c) => c['command'] == 'brain_reconfigure'), isEmpty, reason: 'no reload');
    });

    test('the depth change is reported for storing and a stored depth is restored', () async {
      final conv = await ready(QcRuntime());
      final seen = <OiDepth>[];
      conv.onDepthChanged = seen.add;
      conv.setDepth(OiDepth.normal);
      expect(seen, [OiDepth.normal]);
      final again = await ready(QcRuntime());
      again.restoreDepth('normal');
      expect(again.depth, OiDepth.normal);
      again.restoreDepth('nonsense');
      expect(again.depth, OiDepth.normal, reason: 'unknown names are ignored');
    });

    testWidgets('restart: the Thinking choice is stored and comes back in a new app', (tester) async {
      final (_, services) = await pumpRoot(tester, const Size(1280, 860));
      expect(services.oi!.depth, OiDepth.fast);
      services.oi!.setDepth(OiDepth.normal);
      await tester.pump();
      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('uri.living.thinking'), 'normal');
      // a second app on the same stored preferences (an app restart)
      await tester.pumpWidget(const SizedBox());
      final (_, again) = await pumpRoot(tester, const Size(1280, 860), prefs: {'uri.living.thinking': 'normal'});
      await settle(tester);
      expect(again.oi!.depth, OiDepth.normal);
      again.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await settle(tester);
      expect(toggle(tester, 'qc-thinking').visual, QcVisual.on);
    });
  });

  group('URI-CONTROLS-3: exactly three controls, keyboard and screen reader', () {
    testWidgets('the row holds exactly Thinking, Vision and URI Assist, in that order', (tester) async {
      final conv = await ready(QcRuntime());
      await pumpControls(tester, conv);
      final keys = [for (final w in tester.widgetList<QcToggle>(find.byType(QcToggle))) (w.key as ValueKey).value];
      expect(keys, ['qc-thinking', 'qc-vision', 'qc-assist']);
      expect([for (final w in tester.widgetList<QcToggle>(find.byType(QcToggle))) w.label],
          ['Thinking', 'Vision', 'URI Assist']);
      expect(find.byKey(const ValueKey('qc-context')), findsNothing);
      expect(find.byKey(const ValueKey('qc-draft')), findsNothing);
    });

    testWidgets('R1-01: Tab reaches each toggle, Space and Enter switch it, and the focus is shown', (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pumpAndSettle();
      final thinking = tester.widget<AnimatedContainer>(
          find.descendant(of: find.byKey(const ValueKey('qc-thinking')), matching: find.byType(AnimatedContainer)));
      expect(thinking.foregroundDecoration, isNotNull, reason: 'focus ring');
      await tester.sendKeyEvent(LogicalKeyboardKey.space);
      await tester.pumpAndSettle();
      expect(conv.depth, OiDepth.normal, reason: 'Space switched Thinking on');
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);
      await tester.pumpAndSettle();
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('qc-confirm-switch')), findsOneWidget, reason: 'Enter on Vision asks first');
      expect(find.text('Switch the Brain to Long context?'), findsOneWidget);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(rt.commands.where((c) => c['command'] == 'brain_reconfigure'), isEmpty);
    });

    testWidgets('R1-01: a disabled toggle is skipped by Tab and does nothing on Enter', (tester) async {
      final rt = QcRuntime()..health = {'state': 'READY', 'controls': controls(active: 'standard', canSwitch: false)};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);   // Thinking
      await tester.sendKeyEvent(LogicalKeyboardKey.tab);   // Vision is disabled: focus moves past it
      await tester.pumpAndSettle();
      final visionNode = Focus.of(tester.element(find.descendant(
          of: find.byKey(const ValueKey('qc-vision')), matching: find.byType(AnimatedContainer))));
      expect(visionNode.hasPrimaryFocus, isFalse, reason: 'a disabled toggle never takes focus');
      await tester.sendKeyEvent(LogicalKeyboardKey.enter);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('qc-confirm-switch')), findsNothing);
      expect(rt.commands.where((c) => c['command'] == 'brain_reconfigure'), isEmpty);
    });

    testWidgets('R1-01: a screen reader gets toggle buttons with label, state and a working tap action',
        (tester) async {
      final handle = tester.ensureSemantics();
      final rt = QcRuntime();
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      final vision = tester.getSemantics(find.byKey(const ValueKey('qc-vision')));
      expect(
          vision,
          isSemantics(
              label: 'Vision',
              isButton: true,
              hasToggledState: true,
              isToggled: true,
              hasEnabledState: true,
              isEnabled: true,
              isFocusable: true,
              hasTapAction: true));
      expect(
          tester.getSemantics(find.byKey(const ValueKey('qc-thinking'))),
          isSemantics(label: 'Thinking', isButton: true, hasToggledState: true, isToggled: false,
              hasTapAction: true));
      expect(
          tester.getSemantics(find.byKey(const ValueKey('qc-assist'))),
          isSemantics(label: 'URI Assist', isButton: true, hasToggledState: true, value: 'unavailable',
              hasTapAction: false));
      // the screen reader's tap does what a click does
      tester.binding.renderViews.first.owner!.semanticsOwner!.performAction(vision.id, SemanticsAction.tap);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('qc-confirm-switch')), findsOneWidget);
      handle.dispose();
    });
  });

  testWidgets('R2-03: a focused toggle keeps focus while it shows loading', (tester) async {
    final rt = QcRuntime();
    final conv = await ready(rt);
    await pumpControls(tester, conv);
    final inner = find.descendant(of: find.byKey(const ValueKey('qc-vision')), matching: find.byType(AnimatedContainer));
    Focus.of(tester.element(inner)).requestFocus();
    await tester.pumpAndSettle();
    expect(Focus.of(tester.element(inner)).hasPrimaryFocus, isTrue);
    rt.health = {'state': 'RECOVERING', 'controls': controls(pending: true)};
    await conv.refreshHealth();
    await tester.pump(const Duration(milliseconds: 500));  // the spinner never settles
    expect(toggle(tester, 'qc-vision').visual, QcVisual.loading);
    expect(Focus.of(tester.element(inner)).hasPrimaryFocus, isTrue, reason: 'focus does not jump to the composer');
    await tester.sendKeyEvent(LogicalKeyboardKey.enter);
    await tester.pump(const Duration(milliseconds: 500));  // the spinner never settles
    expect(find.byKey(const ValueKey('qc-confirm-switch')), findsNothing, reason: 'loading: activation guarded');
  });

  testWidgets('R1-03: a restore still running after the worker gate is a warning, not "failed too"', (tester) async {
    final rt = QcRuntime();
    final conv = await ready(rt);
    await conv.reconfigureBrain('long');
    rt.health = {
      'state': 'UNAVAILABLE',
      'controls': controls(last: {'id': 'req-1', 'result': 'FAILED', 'restored': false,
          'fallback': {'to': 'frozen', 'label': 'Standard', 'result': 'IN_PROGRESS'}}),
    };
    await conv.refreshHealth();
    await pumpControls(tester, conv);
    expect(find.text('The Brain did not start with the new setting; URI is still going back to Standard.'),
        findsOneWidget);
    expect(find.textContaining('failed too'), findsNothing);
    expect(toggle(tester, 'qc-vision').visual, isNot(QcVisual.error));
    final notice = tester.widget<Text>(find.byKey(const ValueKey('qc-notice')));
    expect(notice.style!.color, UriColors.of(tester.element(find.byKey(const ValueKey('qc-notice')))).warning);
  });

  testWidgets('R2-02: the conversation pane has no second Depth picker', (tester) async {
    final (_, services) = await pumpRoot(tester, const Size(1280, 860));
    services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
    await settle(tester);
    expect(find.byKey(const ValueKey('oi-depth')), findsNothing);
    expect(find.textContaining('Depth: '), findsNothing);
    services.oi!.setDepth(OiDepth.deep);                      // an old caller: never stored, never restored
    await tester.pump();
    expect((await SharedPreferences.getInstance()).getString('uri.living.thinking'), isNull);
  });

  group('URI Assist toggle', () {
    Future<(QcRuntime, OiConversation, AssistController)> withAssist(WidgetTester tester,
        {Map<String, dynamic> status = const {'state': 'OFF'}, void Function()? open}) async {
      final rt = QcRuntime()
        ..assistStatus = Map.of(status)
        ..assistLinked = true;
      final conv = await ready(rt);
      final assist = AssistController(runtime: () => rt);
      addTearDown(assist.dispose);
      await assist.refresh();
      await pumpControls(tester, conv, assist: assist, openAssist: open);
      return (rt, conv, assist);
    }

    testWidgets('off: a click opens the Assist consent view; nothing is granted by the click', (tester) async {
      var opened = 0;
      final (rt, _, _) = await withAssist(tester, open: () => opened++);
      expect(toggle(tester, 'qc-assist').visual, QcVisual.off);
      expect(toggle(tester, 'qc-assist').tooltip, contains('URI sees nothing'));
      await tester.tap(find.byKey(const ValueKey('qc-assist')));
      await tester.pumpAndSettle();
      expect(opened, 1);
      expect(rt.commands.where((c) => c['command'] == 'assist_grant'), isEmpty, reason: 'consent is the user\'s');
      expect(toggle(tester, 'qc-assist').visual, QcVisual.off, reason: 'glows only after a grant');
    });

    testWidgets('on: it glows from the worker status and one click stops the session', (tester) async {
      final (rt, _, assist) = await withAssist(tester, status: {'state': 'ACTIVE'}, open: () {});
      expect(toggle(tester, 'qc-assist').visual, QcVisual.on);
      await tester.tap(find.byKey(const ValueKey('qc-assist')));
      await tester.pumpAndSettle();
      expect(rt.commands.where((c) => c['command'] == 'assist_revoke'), hasLength(1));
      expect(assist.state, 'OFF');
      expect(toggle(tester, 'qc-assist').visual, QcVisual.off);
    });

    testWidgets('paused: still on (the grant is held), says Paused, and a click stops it', (tester) async {
      final (rt, _, _) = await withAssist(tester, status: {'state': 'PAUSED'}, open: () {});
      expect(toggle(tester, 'qc-assist').visual, QcVisual.on);
      expect(toggle(tester, 'qc-assist').status, 'Paused');
      await tester.tap(find.byKey(const ValueKey('qc-assist')));
      await tester.pumpAndSettle();
      expect(rt.commands.where((c) => c['command'] == 'assist_revoke'), hasLength(1));
    });

    testWidgets('R2-01: the worker ended the grant: the toggle follows the worker and both are read again',
        (tester) async {
      final rt = QcRuntime()..assistStatus = {'state': 'ACTIVE'};
      rt.health = {'state': 'READY', 'controls': controls(active: 'standard', visionLocked: true)};
      final conv = await ready(rt);
      final assist = AssistController(runtime: () => rt);
      addTearDown(assist.dispose);
      await assist.refresh();
      await pumpControls(tester, conv, assist: assist, openAssist: () {});
      expect(toggle(tester, 'qc-assist').visual, QcVisual.on);
      // the worker ends the grant by itself (time limit / target lost); its next health says so
      rt.assistStatus = {'state': 'OFF'};
      rt.health = {'state': 'READY', 'controls': controls(active: 'standard')};
      await conv.refreshHealth();
      final reads = rt.commands.where((c) => c['command'] == 'assist_status').length;
      await tester.pumpAndSettle();
      expect(toggle(tester, 'qc-assist').visual, QcVisual.off, reason: 'the worker is the authority');
      expect(rt.commands.where((c) => c['command'] == 'assist_status').length, greaterThan(reads),
          reason: 'the stale mirror is read again');
      expect(assist.state, 'OFF');
      expect(toggle(tester, 'qc-vision').onPressed, isNotNull, reason: 'vision lock lifted with the grant');
    });

    testWidgets('R3-01: the worker goes away while Assist is granted: off, unavailable, and no call loop',
        (tester) async {
      final rt = QcRuntime()
        ..assistStatus = {'state': 'ACTIVE'}
        ..assistLinked = true;
      var connected = true;
      final conv = await ready(rt);
      final assist = AssistController(runtime: () => connected ? rt : null);
      addTearDown(assist.dispose);
      await assist.refresh();
      await pumpControls(tester, conv, assist: assist, openAssist: () {});
      expect(toggle(tester, 'qc-assist').visual, QcVisual.on);
      connected = false;                           // the worker exits; the last health reading still says granted
      await assist.refresh();                      // what the worker change does: the mirror resets (WORKER_NOT_CONNECTED)
      final calls = rt.commands.length;
      for (var i = 0; i < 50; i++) {
        await tester.pump(const Duration(milliseconds: 16));
      }
      expect(toggle(tester, 'qc-assist').visual, QcVisual.off, reason: 'no worker, no grant');
      expect(toggle(tester, 'qc-assist').onPressed, isNull);
      expect(rt.commands.length, calls, reason: 'no calls while unavailable');
    });

    testWidgets('R3-01 / R4-03: a failing Assist status is read again exactly once per newer health reading',
        (tester) async {
      final rt = QcRuntime()..assistStatus = {'state': 'OFF'};
      rt.health = {'state': 'READY', 'controls': controls(active: 'standard', visionLocked: true)};
      final conv = await ready(rt);
      final assist = AssistController(runtime: () => rt);
      addTearDown(assist.dispose);
      await assist.refresh();                      // mirror OFF ...
      await conv.refreshHealth();                  // ... then a newer worker reading says granted: they disagree
      rt.assistError = 'WORKER_TIMEOUT';           // and the Assist status keeps failing
      int statusCalls() => rt.commands.where((c) => c['command'] == 'assist_status').length;
      final before = statusCalls();
      await pumpControls(tester, conv, assist: assist, openAssist: () {});
      for (var i = 0; i < 50; i++) {
        await tester.pump(const Duration(milliseconds: 16));
      }
      expect(statusCalls() - before, 1, reason: 'one re-read for this health reading');
      expect(toggle(tester, 'qc-assist').visual, QcVisual.on, reason: 'the newer (worker) reading is shown');
      await conv.refreshHealth();                  // the next poll: exactly one more re-read
      for (var i = 0; i < 50; i++) {
        await tester.pump(const Duration(milliseconds: 16));
      }
      expect(statusCalls() - before, 2);
    });

    testWidgets('R4-01: a grant made in the consent view shows at once, also while a turn runs', (tester) async {
      final rt = QcRuntime()..assistLinked = true;
      final conv = await ready(rt);                // worker reading: no grant
      final assist = AssistController(runtime: () => rt);
      addTearDown(assist.dispose);
      await assist.refresh();
      await pumpControls(tester, conv, assist: assist, openAssist: () {});
      expect(toggle(tester, 'qc-assist').visual, QcVisual.off);
      await conv.send('hello');                    // a turn runs: no health poll meanwhile
      expect(conv.busy, isTrue);
      await assist.grant('desktop_window', 'w1', suggest: false);   // what the consent view does
      for (var i = 0; i < 20; i++) {
        await tester.pump(const Duration(milliseconds: 16));
      }
      expect(toggle(tester, 'qc-assist').visual, QcVisual.on, reason: 'the newer Assist status wins');
      expect(toggle(tester, 'qc-assist').tooltip, contains('URI Assist is on'));
      await tester.tap(find.byKey(const ValueKey('qc-assist')));   // a click now stops it
      await tester.pumpAndSettle();
      expect(rt.commands.where((c) => c['command'] == 'assist_revoke'), hasLength(1));
      expect(toggle(tester, 'qc-assist').visual, QcVisual.off);
    });

    testWidgets('an unreadable worker Assist state falls back to the Assist status (R2-06)', (tester) async {
      final rt = QcRuntime()..assistStatus = {'state': 'ACTIVE'};
      rt.health = {'state': 'READY', 'controls': {...controls(active: 'standard'),
          'assist': {'asking': false, 'granted': null, 'error': 'ASSIST_STATE_UNREADABLE'}}};
      final conv = await ready(rt);
      final assist = AssistController(runtime: () => rt);
      addTearDown(assist.dispose);
      await assist.refresh();
      await pumpControls(tester, conv, assist: assist, openAssist: () {});
      expect(toggle(tester, 'qc-assist').visual, QcVisual.on);
      expect(toggle(tester, 'qc-assist').onPressed, isNotNull, reason: 'not "unavailable"');
    });

    testWidgets('a worker without URI Assist shows it unavailable, with the reason', (tester) async {
      final rt = QcRuntime();
      rt.health = {'state': 'READY', 'controls': {...controls(active: 'standard'), 'assist': null}};
      final conv = await ready(rt);
      final assist = AssistController(runtime: () => rt);
      addTearDown(assist.dispose);
      await pumpControls(tester, conv, assist: assist, openAssist: () {});
      expect(toggle(tester, 'qc-assist').onPressed, isNull);
      expect(toggle(tester, 'qc-assist').tooltip, contains('not available in this URI worker'));
    });

    testWidgets('Thinking, Vision and URI Assist switch independently', (tester) async {
      final (rt, conv, _) = await withAssist(tester, status: {'state': 'ACTIVE'}, open: () {});
      await tester.tap(find.byKey(const ValueKey('qc-thinking')));
      await tester.pumpAndSettle();
      expect(conv.depth, OiDepth.normal);
      expect(toggle(tester, 'qc-assist').visual, QcVisual.on, reason: 'Thinking leaves Assist alone');
      expect(toggle(tester, 'qc-vision').visual, QcVisual.on, reason: 'and Vision');
      await tester.tap(find.byKey(const ValueKey('qc-assist')));
      await tester.pumpAndSettle();
      expect(conv.depth, OiDepth.normal, reason: 'Assist leaves Thinking alone');
      expect(toggle(tester, 'qc-vision').visual, QcVisual.on, reason: 'and Vision (no reload)');
      expect(rt.commands.where((c) => c['command'] == 'brain_reconfigure'), isEmpty);
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
    expect(find.byKey(const ValueKey('qc-assist')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  group('closure: Assist vision lock, host/worker mismatch', () {
    final opts = qcOptions(controls());

    test('from Standard, draft off (P3, started by flag): Vision Off leads to Long context', () {
      final p3 = options(active: 'standard-nodraft')[2];
      final vis = visionChoices(opts, p3);
      expect(vis.firstWhere((c) => c.title == 'Off').target!.id, 'long');
    });

    test('while Assist holds a grant, every choice that turns vision off is blocked', () {
      final std = options(active: 'standard').first;
      final vis = lockVision(visionChoices(opts, std), true, std);
      final off = vis.firstWhere((c) => c.title == 'Off');
      expect(off.target, isNull);
      expect(off.blocked, contains('A URI Assist session is open'));
      expect(lockVision(visionChoices(opts, std), false, std).firstWhere((c) => c.title == 'Off').target!.id, 'long');
    });

    testWidgets('UI-CONTROLS-TYPO: while Assist holds a grant the Vision toggle is disabled with the reason',
        (tester) async {
      final rt = QcRuntime()..health = {'state': 'READY', 'controls': controls(active: 'standard', visionLocked: true)};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(toggle(tester, 'qc-vision').visual, QcVisual.on);
      expect(toggle(tester, 'qc-vision').onPressed, isNull);
      expect(toggle(tester, 'qc-vision').tooltip, contains('A URI Assist session is open'));
      expect(toggle(tester, 'qc-assist').visual, QcVisual.on, reason: 'the worker reports the grant');
    });

    testWidgets('a host/worker mismatch is shown in words, never silently', (tester) async {
      final rt = QcRuntime()
        ..health = {
          'state': 'FOREIGN_INSTANCE',
          'controls': controls(mismatch: {
            'code': 'PROFILE_NOT_SELECTABLE',
            'host': 'Long context with vision',
            'host_qualified': false,
            'worker': 'Standard',
          }),
        };
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(find.byKey(const ValueKey('qc-mismatch')), findsOneWidget);
      expect(find.textContaining('runs Long context with vision, which is not a qualified choice'), findsOneWidget);
      rt.health = {'state': 'READY', 'controls': controls(active: 'standard')};
      await conv.refreshHealth();
      await tester.pump();
      expect(find.byKey(const ValueKey('qc-mismatch')), findsNothing);
    });

    test('lockVision changes nothing without a verified vision-on profile (QCC-R1-06)', () {
      final long = options(active: 'long')[1];
      final visLong = visionChoices(opts, long);
      expect(lockVision(visLong, true, long), visLong, reason: 'vision already off: nothing to keep');
      final visNull = visionChoices(opts, null);
      expect(lockVision(visNull, true, null), visNull, reason: 'nothing verified as running');
    });

    test('a selection error with agreeing profiles is explained, not called a mismatch (QCC-R1-05)', () {
      final n = mismatchNotice(controls(active: 'long', mismatch: {
        'code': 'HOST_SELECTION_ERROR', 'host': 'Long context', 'worker': 'Long context', 'host_qualified': true,
        'selection_error': 'PermissionError'}));
      expect(n, contains('could not save its setting (PermissionError)'));
      expect(n, isNot(contains('expects')));
      expect(mismatchNotice(controls(active: 'long')), isNull);
    });

    test('the Assist refusals have plain words', () {
      expect(brainSwitchRefusal('ASSIST_NEEDS_VISION'), contains('a URI Assist session is open'));
      expect(brainSwitchRefusal('ASSIST_ASK_IN_PROGRESS'), contains('URI Assist has finished'));
    });
  });
}
