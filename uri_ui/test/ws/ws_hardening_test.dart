import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:uri_ui/living/a2ui/a2ui_hub.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/contracts/readiness_report.dart';
import 'package:uri_ui/living/contracts/work_items.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_health_widgets.dart';
import 'package:uri_ui/living/integration/oi_markdown.dart';
import 'package:uri_ui/living/integration/oi_sources.dart';
import 'package:uri_ui/living/integration/oi_widgets.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/widgets/glass_panel.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/theme/uri_theme.dart';

/// WS hardening, simulation level: a scriptable worker that can stop
/// answering (alive but unresponsive), report a stalled job, and serve
/// `brain_health` reports.
class HardeningRuntime implements IntegratedRuntime {
  HardeningRuntime({this.name = 'w1'});
  final String name;
  final commands = <Map<String, dynamic>>[];
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  bool responsive = true;
  bool killed = false;
  bool _closed = false;
  Map<String, dynamic> health = {'state': 'READY'};
  Map<String, dynamic> turnStatus = {'busy': true, 'idle_s': 1.0};
  int _turn = 0;

  void emit(String turnId, String type, [Map<String, dynamic> data = const {}]) =>
      _events.add({'schema': 'uri.oi.event.v1', 'turn_id': turnId, 'type': type, 'data': data});

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;
  @override
  bool get closed => _closed;

  final _hung = <Completer<Map<String, dynamic>>>[];

  /// Completes every unanswered call with an error (a late failure after the test moved on).
  void failPending(String code) {
    for (final c in _hung) {
      c.completeError(IntegratedRuntimeException(code));
    }
    _hung.clear();
  }

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) {
    commands.add(command);
    if (!responsive) {
      final c = Completer<Map<String, dynamic>>(); // never answers unless failPending()
      _hung.add(c);
      return c.future;
    }
    switch (command['command']) {
      case 'oi_turn':
        return Future.value({'turn_id': '$name-t${++_turn}', 'accepted': true});
      case 'brain_health':
        return Future.value(health);
      case 'oi_turn_status':
        return Future.value(turnStatus);
      case 'brain_status':
        return Future.value({'state': health['state'] == 'UNAVAILABLE' ? 'STOPPED' : 'READY', 'model_id': 'qwen-test'});
      case 'brain_catalog':
        return Future.value({'rows': [], 'fallback': 'none'});
      case 'brain_restart':
        return Future.value({'requested': command['action']});
      default:
        return Future.value({'ok': true});
    }
  }

  @override
  Future<void> close() async => _closed = true;

  @override
  Future<void> kill() async {
    killed = true;
    _closed = true;
  }
}

Widget host(Widget child) {
  final palette = resolveUriColors(UriThemeChoice.obsidianCyan, Brightness.dark);
  return MaterialApp(theme: buildUriTheme(palette), home: Scaffold(body: child));
}

const fast = Duration(milliseconds: 1);
const shortProbe = Duration(milliseconds: 60);

Map<String, dynamic> degraded() => {
      'state': 'DEGRADED',
      'reasons': ['DECODE_THROUGHPUT_LOW'],
      'explain': 'The Brain is running slowly (27 tok/s, healthy is above 60).',
      'recovery_options': ['restart_brain', 'close_gpu_apps', 'continue_slow'],
      'performance': {'calibration_tps': 27.0, 'threshold_tps': 60.0, 'decode_samples': 0},
      'backend': {'provider': 'Runtime v1 (local)', 'model_id': 'qwen-test', 'engine': 'llama.cpp b11425 (Vulkan, win x64)'},
      'gpu': {
        'measured': true,
        'verdict_now': 'CONTENDED',
        'server_dedicated_mib': 13907.0,
        'server_non_local_mib': 1819.0,
        'others_mib': 1914.0,
        'consumers': [
          {'pid': 18372, 'name': 'llama-server.exe', 'dedicated_mib': 1602.0, 'role': null},
          {'pid': 1580, 'name': 'dwm.exe', 'dedicated_mib': 311.0, 'role': 'desktop compositor'},
        ],
      },
    };

void main() {
  group('markdown (L-MD)', () {
    test('blocks: headings, lists, code fences, quotes, tables, rules', () {
      final b = parseMarkdownBlocks('# Title\n\nSome **bold** text\ncontinues.\n\n- one\n- two\n  - nested\n1. first\n'
          '> quoted\n```\ncode **not bold**\n```\n| a | b |\n|---|---|\n---\nend');
      expect(b.map((x) => x.kind).toList(), [
        MdKind.heading, MdKind.paragraph, MdKind.listItem, MdKind.listItem, MdKind.listItem, MdKind.listItem,
        MdKind.quote, MdKind.code, MdKind.table, MdKind.rule, MdKind.paragraph,
      ]);
      expect(b[1].text, 'Some **bold** text continues.');
      expect(b[4].level, 1);
      expect(b[5].marker, '1.');
      expect(b[7].text, 'code **not bold**');
    });

    test('inline markers are removed; snake_case and unclosed markers stay literal; links never carry a URL', () {
      expect(markdownPlainText('**Bold**, *it*, `x_y`, ~~old~~'), 'Bold, it, x_y, old');
      expect(markdownPlainText('use file_name_here and 2*3*4'), 'use file_name_here and 2*3*4');
      expect(markdownPlainText('streaming **unfinis'), 'streaming **unfinis');
      expect(markdownPlainText('see [the docs](https://example.com/x)'), 'see the docs');
      expect(markdownPlainText('<b>html</b>'), '<b>html</b>');
    });

    testWidgets('a Brain answer renders without raw markdown markers', (tester) async {
      final rt = HardeningRuntime();
      final conv = OiConversation(rt);
      await conv.send('explain');
      rt.emit('w1-t1', 'answer.delta', {'text': '## Plan\n\n**Step one** is `fast`.\n\n- a\n- b'});
      rt.emit('w1-t1', 'turn.finished', {'status': 'ok'});
      await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
      await tester.pump();
      expect(find.byType(OiMarkdown), findsOneWidget);
      expect(find.textContaining('**'), findsNothing);
      expect(find.textContaining('##'), findsNothing);
      expect(find.textContaining('Step one', findRichText: true), findsOneWidget);
    });
  });

  group('A2UI handoff without a proposal (INT-F1)', () {
    test('a handoff the hub cannot turn into a proposal stops the waiting-for-you state', () async {
      final rt = HardeningRuntime();
      final conv = OiConversation(rt);
      final hub = A2uiHub(
        handoffs: conv.a2uiHandoffs,
        onHandoffFailed: (h) => conv.handoffProducedNothing(h['turn_id'] as String?),
      );
      await conv.send('URI, schedule Claude to create a festival GIF two days before each major Indian festival');
      // The worker's order: the handoff first, then "waiting for you".
      rt.emit('w1-t1', 'a2ui.handoff', {
        'domain': 'scheduler',
        'request': {'template': 'festival_gif', 'offset_days': 2},
      });
      await Future<void>.delayed(const Duration(milliseconds: 20)); // the hub fails before the next event
      rt.emit('w1-t1', 'companion.state', {'state': 'waiting_user'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      // No scheduler: an honest notice, nothing to decide, so no "needs you".
      expect(hub.notices.single, contains('scheduler is not running'));
      expect(conv.companionState, 'idle');
      hub.dispose();
    });

    test('the reverse order clears it too, and a later turn may wait again', () async {
      final rt = HardeningRuntime();
      final conv = OiConversation(rt);
      await conv.send('x');
      rt.emit('w1-t1', 'companion.state', {'state': 'waiting_user'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(conv.companionState, 'waiting_user');
      conv.handoffProducedNothing('w1-t1');
      expect(conv.companionState, 'idle');
      rt.emit('w1-t1', 'turn.finished', {'status': 'ok'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await conv.send('y');
      rt.emit('w1-t2', 'companion.state', {'state': 'waiting_user'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(conv.companionState, 'waiting_user');
    });

    test('interleaved failures of two turns each clear their own waiting state', () async {
      final rt = HardeningRuntime();
      final conv = OiConversation(rt);
      conv.handoffProducedNothing('w1-t1'); // both failures arrive before either waiting_user
      conv.handoffProducedNothing('w1-t2');
      await conv.send('a');
      rt.emit('w1-t1', 'companion.state', {'state': 'waiting_user'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(conv.companionState, 'idle');
      rt.emit('w1-t1', 'turn.finished', {'status': 'ok'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await conv.send('b');
      rt.emit('w1-t2', 'companion.state', {'state': 'waiting_user'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(conv.companionState, 'idle');
      rt.emit('w1-t2', 'turn.finished', {'status': 'ok'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await conv.send('c'); // a real approval of another turn is never hidden
      rt.emit('w1-t3', 'companion.state', {'state': 'waiting_user'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(conv.companionState, 'waiting_user');
    });

    test("a failed turn's late waiting event never replaces another turn's real wait", () async {
      final rt = HardeningRuntime();
      final conv = OiConversation(rt);
      await conv.send('a');
      rt.emit('w1-t1', 'turn.finished', {'status': 'ok'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      conv.handoffProducedNothing('w1-t1'); // turn A's handoff failed; its waiting event is still in flight
      await conv.send('b');
      rt.emit('w1-t2', 'companion.state', {'state': 'waiting_user'}); // turn B: a real proposal waits
      await Future<void>.delayed(const Duration(milliseconds: 20));
      rt.emit('w1-t1', 'companion.state', {'state': 'waiting_user'}); // A's late event
      await Future<void>.delayed(const Duration(milliseconds: 20));
      expect(conv.companionState, 'waiting_user');
      conv.handoffProducedNothing('w1-t1'); // a repeated failure report for A changes nothing for B
      expect(conv.companionState, 'waiting_user');
    });

    test("B waits, A's wait arrives, A's handoff fails: B's real wait stays (Codex r4)", () async {
      final rt = HardeningRuntime();
      final conv = OiConversation(rt);
      await conv.send('a');
      rt.emit('w1-t1', 'turn.finished', {'status': 'ok'});
      await Future<void>.delayed(const Duration(milliseconds: 20));
      await conv.send('b');
      rt.emit('w1-t2', 'companion.state', {'state': 'waiting_user'}); // B: a real proposal waits
      rt.emit('w1-t1', 'companion.state', {'state': 'waiting_user'}); // A's wait arrives later
      await Future<void>.delayed(const Duration(milliseconds: 20));
      conv.handoffProducedNothing('w1-t1'); // then A's handoff fails
      expect(conv.companionState, 'waiting_user');
    });

    test('a waiting state from anything else is left alone', () {
      final conv = OiConversation(HardeningRuntime());
      conv.companionState = 'thinking';
      conv.handoffProducedNothing('w1-t9');
      expect(conv.companionState, 'thinking');
    });
  });

  group('health (H-AC5/6)', () {
    test('health is read with the status and exposes the state', () async {
      final rt = HardeningRuntime()..health = {'state': 'READY', 'performance': {'calibration_tps': 121.0}};
      final conv = OiConversation(rt);
      await conv.refreshStatus();
      expect(conv.healthState, 'READY');
      expect(measuredSpeed(conv.brainHealth)!.tps, 121.0);
      expect(rt.commands.map((c) => c['command']), containsAll(['brain_status', 'brain_catalog', 'brain_health']));
    });

    testWidgets('DEGRADED shows why, who uses the GPU (not the desktop), and an explicit restart', (tester) async {
      final rt = HardeningRuntime()..health = degraded();
      final conv = OiConversation(rt);
      await conv.refreshHealth();
      await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
      expect(find.byKey(const ValueKey('oi-health-banner')), findsOneWidget);
      expect(find.textContaining('27 tok/s'), findsWidgets);
      expect(find.textContaining('llama-server.exe 1.6 GB'), findsOneWidget);
      expect(find.textContaining('dwm.exe'), findsNothing);
      expect(find.textContaining('never closes other apps'), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('oi-health-restart_brain')));
      await tester.pump();
      expect(rt.commands.where((c) => c['command'] == 'brain_restart').single['action'], 'restart');
    });

    testWidgets('memory taken after load shows a warning while the state stays Ready', (tester) async {
      final rt = HardeningRuntime()
        ..health = {
          'state': 'READY',
          'reasons': ['GPU_MEMORY_TAKEN_AFTER_LOAD'],
          'recovery_options': ['restart_brain'],
          'warning': 'Another app took GPU memory after the Brain loaded (1.6 GB moved to system memory).',
          'performance': {'calibration_tps': 141.0},
        };
      final conv = OiConversation(rt);
      await conv.refreshHealth();
      await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
      expect(find.byKey(const ValueKey('oi-health-warning')), findsOneWidget);
      expect(find.textContaining('Ready · 141 tok/s'), findsOneWidget);
      expect(find.byKey(const ValueKey('oi-health-restart_brain')), findsOneWidget);
    });

    testWidgets('restart is not offered while a turn runs', (tester) async {
      final rt = HardeningRuntime()..health = degraded();
      final conv = OiConversation(rt);
      await conv.refreshHealth();
      await conv.send('long question');
      await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
      final btn = tester.widget<OutlinedButton>(find.byKey(const ValueKey('oi-health-restart_brain')));
      expect(btn.onPressed, isNull);
      await conv.brainAction('restart');
      expect(rt.commands.where((c) => c['command'] == 'brain_restart'), isEmpty);
    });

    testWidgets('UNAVAILABLE without a host tells the user how to start the Brain', (tester) async {
      final rt = HardeningRuntime()
        ..health = {
          'state': 'UNAVAILABLE',
          'reasons': ['RUNTIME_STOPPED'],
          'recovery_options': ['start_from_launcher'],
          'explain': 'The Brain is not running.',
        };
      final conv = OiConversation(rt);
      await conv.refreshHealth();
      await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
      expect(find.textContaining('Launch URI Working System'), findsOneWidget);
      expect(find.byKey(const ValueKey('oi-health-restart_brain')), findsNothing);
    });
  });

  group('worker failure (R-BUSY, H-AC7)', () {
    test('an alive but unresponsive worker is detected within the probe bound', () async {
      final rt = HardeningRuntime();
      final conv = OiConversation(rt, probeAfter: Duration.zero, probeTimeout: shortProbe);
      await conv.send('hello');
      expect(conv.busy, isTrue);
      rt.responsive = false;
      final t0 = DateTime.now();
      await conv.monitorTick();
      expect(conv.workerUnresponsive, isTrue);
      expect(conv.workerTrouble, isTrue);
      expect(DateTime.now().difference(t0), lessThan(const Duration(seconds: 2)));
    });

    test('a worker that hangs before replying to the turn is detected; the request is not repeated', () async {
      final rt = HardeningRuntime()..responsive = false;
      final conv = OiConversation(rt, probeAfter: Duration.zero, probeTimeout: shortProbe);
      final sending = conv.send('hello'); // never answered
      await Future<void>.delayed(fast);
      expect(conv.busy, isTrue);
      await conv.send('second'); // refused locally while the first is outstanding
      expect(rt.commands.where((c) => c['command'] == 'oi_turn').length, 1);
      await conv.monitorTick();
      expect(conv.workerUnresponsive, isTrue);
      expect(conv.workerTrouble, isTrue);
      unawaited(sending);
    });

    test('a probe that answers clears the alarm; a long-silent job is stalled, not unresponsive', () async {
      final rt = HardeningRuntime()..turnStatus = {'busy': true, 'idle_s': 120.0, 'age_s': 130.0};
      final conv = OiConversation(rt, probeAfter: Duration.zero, probeTimeout: shortProbe);
      await conv.send('hello');
      await conv.monitorTick();
      expect(conv.workerUnresponsive, isFalse);
      expect(conv.turnStalled, isTrue);
      rt.emit('w1-t1', 'answer.delta', {'text': 'late'});
      await Future<void>.delayed(fast);
      expect(conv.turnStalled, isFalse); // progress clears the alarm
    });

    test('a job that ended without its turn.finished is reconciled without claiming an outcome', () async {
      final rt = HardeningRuntime()..turnStatus = {'busy': false};
      final conv = OiConversation(rt, probeAfter: Duration.zero, probeTimeout: shortProbe);
      await conv.send('hello');
      await conv.monitorTick();
      expect(conv.busy, isFalse);
      expect(conv.messages.firstWhere((m) => m.role == OiRole.uri).finishedStatus, 'unknown');
      expect(conv.messages.last.text, contains('Check before repeating any action'));
    });

    test('Restart URI replaces the worker, never retries the turn, and withdraws the card', () async {
      final w1 = HardeningRuntime();
      final w2 = HardeningRuntime(name: 'w2');
      final conv = OiConversation(w1, respawn: () async => w2, probeAfter: Duration.zero, probeTimeout: shortProbe);
      await conv.send('remember that the lab is closed');
      w1.emit('w1-t1', 'turn.routed', {'route': 'core'});
      w1.emit('w1-t1', 'approval.required', {'capability_id': 'remember_fact', 'approval_digest': 'd' * 64});
      await Future<void>.delayed(fast);
      w1.responsive = false;
      await conv.monitorTick();
      expect(conv.workerUnresponsive, isTrue);
      await conv.restartWorker();
      expect(w1.killed, isTrue);
      expect(conv.runtime, same(w2));
      expect(conv.busy, isFalse);
      expect(conv.pendingApproval, isNull);
      expect(conv.workerTrouble, isFalse);
      final texts = conv.messages.where((m) => m.role == OiRole.system).map((m) => m.text).join('\n');
      expect(texts, contains('not retried'));
      expect(texts, contains('outcome is unknown'));
      expect(texts, contains('nothing was approved'));
      expect(w2.commands.any((c) => c['command'] == 'oi_turn' || c['command'] == 'oi_decide'), isFalse);
      expect(w1.commands.any((c) => c['command'] == 'oi_decide'), isFalse);
      // the conversation continues on the new worker; old-worker events are no longer heard
      w1.emit('w1-t1', 'turn.finished', {'status': 'ok'});
      await conv.send('next question');
      expect(w2.commands.last['command'], 'oi_turn');
      expect(conv.sessionId, isNotEmpty);
    });

    test('a late reply or timeout from the replaced worker does not touch the new worker state', () async {
      final w1 = HardeningRuntime()..responsive = false;
      final w2 = HardeningRuntime(name: 'w2');
      final conv = OiConversation(w1, respawn: () async => w2, probeAfter: Duration.zero, probeTimeout: shortProbe);
      unawaited(conv.send('first')); // outstanding on w1
      await Future<void>.delayed(fast);
      await conv.restartWorker();
      w2.responsive = false; // keep the new send outstanding
      unawaited(conv.send('second'));
      await Future<void>.delayed(fast);
      expect(conv.busy, isTrue);
      // the old worker's pending call now fails late: nothing about w2 may change
      w1.failPending('WORKER_TIMEOUT');
      await Future<void>.delayed(fast);
      expect(conv.busy, isTrue);
      expect(conv.workerUnresponsive, isFalse);
    });

    test('nothing is sent while the worker is being replaced', () async {
      final w1 = HardeningRuntime();
      final gate = Completer<IntegratedRuntime?>();
      final conv = OiConversation(w1, respawn: () => gate.future);
      final restarting = conv.restartWorker();
      await Future<void>.delayed(fast);
      expect(conv.restarting, isTrue);
      await conv.send('during restart');
      expect(w1.commands.where((c) => c['command'] == 'oi_turn'), isEmpty);
      final w2 = HardeningRuntime(name: 'w2');
      gate.complete(w2);
      await restarting;
      await conv.send('after restart');
      expect(w2.commands.last['command'], 'oi_turn');
    });

    test('a failed restart says so', () async {
      final conv = OiConversation(HardeningRuntime(), respawn: () async => null);
      await conv.restartWorker();
      expect(conv.lastError, 'WORKER_RESTART_FAILED');
      expect(conv.workerExited, isTrue);
    });

    testWidgets('the worker banner offers Restart URI when unresponsive', (tester) async {
      final rt = HardeningRuntime();
      final conv = OiConversation(rt, respawn: () async => HardeningRuntime(name: 'w2'),
          probeAfter: Duration.zero, probeTimeout: shortProbe);
      await conv.send('hello');
      rt.responsive = false;
      await tester.pumpWidget(host(OiConversationPane(conversation: conv)));
      await tester.runAsync(conv.monitorTick);
      await tester.pump();
      expect(find.textContaining('not responding'), findsOneWidget);
      expect(find.byKey(const ValueKey('oi-restart-worker')), findsOneWidget);
    });
  });

  group('Dashboard Brain card (L-DASH, H-AC8)', () {
    Future<LivingServices> pumpDashboard(WidgetTester tester, OiConversation? conv) async {
      SharedPreferences.setMockInitialValues({});
      tester.view.physicalSize = const Size(1400, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      final appState = AppState(MockUriClient(), preferencesStore: LivingPreferencesStore());
      final demo = MockCompanionSource();
      final work = MockWorkSimulator(stepInterval: const Duration(milliseconds: 100));
      final services = LivingServices(
        presentation: UiPresentationController(commandCooldown: Duration.zero),
        companion: CompositeCompanionSource([if (conv != null) OiCompanionSource(conv), work.companion, demo]),
        work: work,
        readiness: conv != null ? OiReadinessSource(conv) : MockReadinessSource(),
        effects: EffectsSettings(reducedMotion: true),
        demo: demo,
        appDataIsMock: true,
        oi: conv,
      );
      addTearDown(services.dispose);
      await tester.pumpWidget(LivingApp(appState: appState, services: services, skipOnboarding: true));
      services.presentation.setMode(UiPresentationMode.dashboard);
      for (var i = 0; i < 20; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      return services;
    }

    testWidgets('real worker data, no Simulated badge on the Brain tile', (tester) async {
      final rt = HardeningRuntime()..health = degraded();
      final conv = OiConversation(rt);
      await tester.runAsync(conv.refreshStatus);
      await pumpDashboard(tester, conv);
      final tile = find.ancestor(of: find.text('Brain & models'), matching: find.byType(GlassPanel));
      expect(find.descendant(of: tile, matching: find.byKey(const ValueKey('oi-brain-card'))), findsOneWidget);
      expect(find.descendant(of: tile, matching: find.text('SIMULATED')), findsNothing);
      expect(find.text('integrated worker · brain_health'), findsOneWidget);
      expect(find.byKey(const ValueKey('oi-brain-card-state')), findsOneWidget);
      expect(find.textContaining('27 tok/s · speed check at start'), findsOneWidget);
      expect(find.textContaining('GPU: CONTENDED'), findsOneWidget);
      expect(find.textContaining('llama.cpp b11425'), findsOneWidget);
      expect(find.byKey(const ValueKey('oi-brain-card-restart_brain')), findsOneWidget);
      // other mock tiles keep their badge
      final tasks = find.ancestor(of: find.text('Current tasks'), matching: find.byType(GlassPanel));
      expect(find.descendant(of: tasks, matching: find.text('SIMULATED')), findsWidgets);
      expect(tester.takeException(), isNull);
    });

    testWidgets('without the integrated worker the Brain tile stays the badged mock', (tester) async {
      await pumpDashboard(tester, null);
      final tile = find.ancestor(of: find.text('Brain & models'), matching: find.byType(GlassPanel));
      expect(find.descendant(of: tile, matching: find.text('SIMULATED')), findsWidgets);
      expect(find.byKey(const ValueKey('oi-brain-card')), findsNothing);
    });
  });
}
