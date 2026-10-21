import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:uri_ui/living/integration/draft_panel.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_draft.dart';
import 'package:uri_ui/living/integration/oi_widgets.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/testing_tools.dart';
import 'package:uri_ui/living/widgets/scroll_when_short.dart';
import 'package:uri_ui/working_system_app.dart';

import '../ws/ti_draft_test.dart' show snapshot, v1, v2;
import '../ws/ws_integration_test.dart' show FakeRuntime, digest, host;

/// UI-V2-POSTINT (2026-10-16): UIV2-F1 (a draft changes only from the surface
/// that shows it), UIV2-F2 (testing-only composer controls hidden), UIV2-F3
/// (no overflow while the window shrinks into Companion).

Future<void> openDraft(FakeRuntime rt, OiConversation conv, String turn) async {
  rt.emit(turn, 'draft.updated', {'op': 'created', 'draft': snapshot(current: v2, previous: v1, simulated: false)});
  rt.emit(turn, 'turn.finished', {'status': 'ok'});
  await pumpEventQueue();
}

Future<(FakeRuntime, LivingServices)> pumpRoot(WidgetTester tester, Size size,
    {Map<String, Object> prefs = const {}}) async {
  SharedPreferences.setMockInitialValues({'uri.living.onboardingDone': true, ...prefs});
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final rt = FakeRuntime();
  LivingServices? services;
  await tester.pumpWidget(
    WorkingSystemRoot(
      connect: () async => rt,
      visualV2: true,
      skipOnboarding: true,
      statusInterval: const Duration(hours: 1),
      healthInterval: const Duration(hours: 1),
      configureServices: (value) {
        services = value;
        value.effects.setReducedMotion(true);
      },
      classicBuilder: (_) => const SizedBox.shrink(),
    ),
  );
  for (var i = 0; i < 10; i++) {
    await tester.pump(const Duration(milliseconds: 50));
  }
  return (rt, services!);
}

Future<void> settle(WidgetTester tester) async {
  for (var i = 0; i < 12; i++) {
    await tester.pump(const Duration(milliseconds: 100));
  }
}

void main() {
  tearDown(() => UriTestingTools.enabled = null);

  group('UIV2-F1: draft scope', () {
    test('without a draft every surface sends an ordinary turn', () async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await conv.send('Say hello in three words', draftInView: false);
      expect(rt.commands.last['command'], 'oi_turn');
      expect(rt.commands.last.containsKey('input'), isFalse);
    });

    test('with a draft open, a turn from a surface that does not show it is mode command', () async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await conv.send('draft a letter');
      await openDraft(rt, conv, 't1');
      expect(conv.draft, isNotNull);

      await conv.send('Say hello in three words', draftInView: false);
      expect(rt.commands.last['input'], {'schema': 'uri.text_input.v1', 'source': 'typed', 'mode': 'command'});
      expect(rt.commands.last['text'], 'Say hello in three words');
      rt.emit('t2', 'turn.finished', {'status': 'ok'});
      await pumpEventQueue();

      // The Workspace shows the draft: by default its composer talks to the conversation (as if no draft were
      // open); only the explicit draft target makes the words an instruction for the draft.
      await conv.send('Make it shorter');
      expect((rt.commands.last['input'] as Map)['mode'], 'conversation');
      rt.emit('t3', 'turn.finished', {'status': 'ok'});
      await pumpEventQueue();
      conv.setDraftTarget(true);
      await conv.send('Make it shorter');
      expect((rt.commands.last['input'] as Map)['mode'], 'draft');
      conv.setDraftTarget(false);
      rt.emit('t4', 'turn.finished', {'status': 'ok'});
      await pumpEventQueue();

      // Speech away from the draft: the transcript envelope keeps the raw words and adds mode command.
      await conv.sendTranscript('make it shorter', engine: 'faster-whisper', simulated: false, draftInView: false);
      final input = rt.commands.last['input'] as Map;
      expect(input['mode'], 'command');
      expect((input['transcript'] as Map)['raw'], 'make it shorter');
      rt.emit('t5', 'turn.finished', {'status': 'ok'});
      await pumpEventQueue();

      // Dictation is explicit content the user chose; it keeps its own mode.
      conv.setDictationMode(true);
      await conv.send('Dear Sir, please find attached.', draftInView: false);
      expect((rt.commands.last['input'] as Map)['mode'], 'dictation');
    });

    test('the Workspace draft target: conversation by default, draft only when chosen, reset by a new draft', () async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await conv.send('draft a letter');
      expect(rt.commands.last.containsKey('input'), isFalse);   // no draft yet: routing as before
      await openDraft(rt, conv, 't1');
      expect(conv.draftTarget, isFalse);
      await conv.send('Tell me a joke in a formal tone');
      expect((rt.commands.last['input'] as Map)['mode'], 'conversation');
      rt.emit('t2', 'turn.finished', {'status': 'ok'});
      await pumpEventQueue();
      conv.setDraftTarget(true);
      expect(conv.draftTarget, isTrue);
      await conv.send('Make my letter shorter');
      expect((rt.commands.last['input'] as Map)['mode'], 'draft');
      expect(conv.messages.lastWhere((m) => m.role == OiRole.user).inputLabel, 'To the draft');
      rt.emit('t3', 'draft.updated', {
        'op': 'created',
        'draft': {...snapshot(current: v1, previous: null, position: 1, count: 1, simulated: false), 'draft_id': 'd2'},
      });
      rt.emit('t3', 'turn.finished', {'status': 'ok'});
      await pumpEventQueue();
      expect(conv.draft!.draftId, 'd2');
      expect(conv.draftTarget, isFalse, reason: 'a new draft starts with the conversation as target');
    });

    test('deep depth keeps the explicit draft target and the chosen depth (the worker honours the target)', () async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await conv.send('draft a letter');
      await openDraft(rt, conv, 't1');
      conv.setDraftTarget(true);
      conv.setDepth(OiDepth.deep);

      await conv.send('Make my letter shorter');
      final typed = rt.commands.last;
      expect((typed['input'] as Map)['mode'], 'draft');
      expect(typed['depth'], 'deep');
      expect(conv.messages.where((m) => m.role == OiRole.system), isEmpty);
      rt.emit('t2', 'turn.finished', {'status': 'ok'});
      await pumpEventQueue();

      await conv.sendTranscript('shorten the second paragraph', engine: 'simulated', simulated: true);
      final spoken = rt.commands.last;
      expect((spoken['input'] as Map)['mode'], 'draft');
      expect(spoken['depth'], 'deep');
    });

    testWidgets('the Workspace composer shows the draft target chip and switches it', (tester) async {
      final (rt, s) = await pumpRoot(tester, const Size(1280, 860));
      await tester.runAsync(() async {
        await s.oi!.send('draft a letter');
        await openDraft(rt, s.oi!, 't1');
      });
      s.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await settle(tester);
      final chip = find.byKey(const ValueKey('composer-draft-target'));
      expect(chip, findsOneWidget);
      expect(find.text('To: conversation'), findsOneWidget);
      await tester.tap(chip);
      await settle(tester);
      expect(s.oi!.draftTarget, isTrue);
      expect(find.text('To: letter draft'), findsOneWidget);
      await tester.tap(chip);
      await settle(tester);
      expect(s.oi!.draftTarget, isFalse);
      // The draft panel offers the explicit way to address the draft.
      await tester.ensureVisible(find.byKey(const ValueKey('draft-edit-with-uri')));
      await tester.tap(find.byKey(const ValueKey('draft-edit-with-uri')));
      await settle(tester);
      expect(s.oi!.draftTarget, isTrue);
      s.presentation.setMode(UiPresentationMode.dashboard);
      await settle(tester);
      expect(find.byKey(const ValueKey('composer-draft-target')), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    });

    test('a Start new work request never changes the open draft, whatever the target (C1-02)', () async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await conv.send('draft a letter');
      await openDraft(rt, conv, 't1');
      conv.setDraftTarget(true);
      await conv.send('Draft a letter', draftInView: false, newWork: true);
      expect((rt.commands.last['input'] as Map)['mode'], 'conversation');
    });

    testWidgets('a question about a NEW document is labelled as such and has no Answer for the open draft (C2-01)',
        (tester) async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await tester.runAsync(() async {
        await conv.send('draft a letter');
        await openDraft(rt, conv, 't1');
        await conv.send('Draft a notice about the library timings.');
        rt.emit('t2', 'draft.clarify', {'question': 'Who should the notice be addressed to?', 'draft': null});
        rt.emit('t2', 'turn.finished', {'status': 'needs_user'});
        await pumpEventQueue();
      });
      expect(conv.draftQuestionIsNew, isTrue);
      tester.view.physicalSize = const Size(900, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(host(SizedBox(height: 800, child: DraftPanel(conversation: conv))));
      await tester.pump();
      expect(find.textContaining('About your new document'), findsOneWidget);
      expect(find.byKey(const ValueKey('draft-answer')), findsNothing);
    });

    test('the draft is in view only in the Workspace conversation', () {
      final p = UiPresentationController(commandCooldown: Duration.zero);
      addTearDown(p.dispose);
      p.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      expect(p.draftInView, isTrue);
      p.setFocus(WorkspaceFocus.documents);
      expect(p.draftInView, isFalse);
      for (final m in [UiPresentationMode.companion, UiPresentationMode.dashboard, UiPresentationMode.assist]) {
        p.setMode(m);
        expect(p.draftInView, isFalse, reason: m.name);
      }
    });

    test('a draft that replaced an open one says so; Undo brings it back', () {
      final d = OiDraft.parse({
        ...snapshot(current: v1, previous: null, position: 1, count: 1, simulated: false),
        'can_undo': true,
        'replaced': {'doc_type': 'letter', 'version': 3},
      })!;
      expect(d.replacedDocType, 'letter');
      expect(d.canUndo, isTrue);
      expect(OiDraft.parse(snapshot(current: v2, previous: v1))!.replacedDocType, isNull);
    });

    testWidgets('draft panel shows the replacement tag', (tester) async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await tester.runAsync(() async {
        await conv.send('draft a letter');
        rt.emit('t1', 'draft.updated', {
          'op': 'created',
          'draft': {
            ...snapshot(current: v1, previous: null, position: 1, count: 1, simulated: false),
            'can_undo': true,
            'replaced': {'doc_type': 'notice', 'version': 2},
          },
        });
        await pumpEventQueue();
      });
      tester.view.physicalSize = const Size(600, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(host(SizedBox(height: 800, child: DraftPanel(conversation: conv))));
      await tester.pump();
      expect(find.byKey(const ValueKey('draft-replaced')), findsOneWidget);
      expect(find.textContaining('Replaced your earlier notice'), findsOneWidget);
    });

    testWidgets('Companion chat with an open draft: a note, and its messages go as mode command', (tester) async {
      final (rt, s) = await pumpRoot(tester, const Size(1280, 860));
      await tester.runAsync(() async {
        await s.oi!.send('draft a letter');
        await openDraft(rt, s.oi!, 't1');
      });
      s.presentation.setMode(UiPresentationMode.companion);
      await settle(tester);
      await tester.tap(find.byKey(LivingShell.orbKey));
      await settle(tester);
      if (find.byKey(const ValueKey('a2ui.companion-controls.chat')).evaluate().isNotEmpty) {
        await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.chat')));
        await settle(tester);
      }
      expect(find.byKey(const ValueKey('companion-draft-note')), findsOneWidget);
      await tester.enterText(find.byKey(const ValueKey('living-composer-field')).last, 'Say hello in three words');
      await tester.tap(find.byKey(const ValueKey('living-composer-send')).last);
      await settle(tester);
      final turn = rt.commands.lastWhere((c) => c['command'] == 'oi_turn');
      expect(turn['text'], 'Say hello in three words');
      expect((turn['input'] as Map)['mode'], 'command');
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    });
  });

  group('UIV2-F2: testing-only composer controls', () {
    Future<void> toWorkspace(WidgetTester tester, LivingServices s) async {
      s.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await settle(tester);
    }

    testWidgets('hidden from ordinary users', (tester) async {
      final (_, s) = await pumpRoot(tester, const Size(1280, 860));
      await toWorkspace(tester, s);
      expect(find.byKey(const ValueKey('living-composer-field')), findsWidgets);
      expect(find.byKey(const ValueKey('living-composer-transcript')), findsNothing);
      expect(find.byKey(const ValueKey('living-composer-dictation')), findsNothing);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    });

    testWidgets('available with URI_UI_TESTING_TOOLS', (tester) async {
      UriTestingTools.enabled = true;
      final (_, s) = await pumpRoot(tester, const Size(1280, 860));
      await toWorkspace(tester, s);
      expect(find.byKey(const ValueKey('living-composer-transcript')), findsOneWidget);
      expect(find.byKey(const ValueKey('living-composer-dictation')), findsOneWidget);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    });

    test('environment values', () {
      for (final on in ['1', 'true', 'ON', ' yes ']) {
        expect(UriTestingTools.fromEnvironment(on), isTrue, reason: on);
      }
      for (final off in [null, '', '0', 'false', 'no', 'maybe']) {
        expect(UriTestingTools.fromEnvironment(off), isFalse, reason: '$off');
      }
    });
  });

  group('UIV2-F3: no overflow while the window shrinks into Companion', () {
    testWidgets('draft panel and conversation scroll instead of overflowing at any height', (tester) async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await tester.runAsync(() async {
        await conv.send('draft a letter');
        await openDraft(rt, conv, 't1');
      });
      tester.view.physicalSize = const Size(900, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      for (final w in [320.0, 520.0, 900.0]) {
        for (final h in [80.0, 140.0, 200.0, 280.0, 420.0, 700.0]) {
          for (final pane in [DraftPanel(conversation: conv), OiConversationPane(conversation: conv)]) {
            await tester.pumpWidget(host(Align(
              alignment: Alignment.topLeft,
              child: SizedBox(width: w, height: h, child: pane),
            )));
            await tester.pump();
            expect(tester.takeException(), isNull, reason: '${pane.runtimeType} $w x $h');
          }
        }
      }
      expect(find.byType(ScrollWhenShort), findsWidgets);
    });

    testWidgets('approval and confirmation cards never overflow the conversation pane (C1-03)', (tester) async {
      for (final kind in ['approval', 'confirmation']) {
        final rt = FakeRuntime();
        final conv = OiConversation(rt);
        await tester.runAsync(() async {
          await conv.send('remember a qualification fixture');
          if (kind == 'approval') {
            rt.emit('t1', 'approval.required',
                {'capability_id': 'remember_fact', 'arguments': {}, 'approval_digest': digest});
          } else {
            rt.emit('t1', 'core.result', {'code': 'INTENT_CONFIRMATION_REQUIRED', 'needs': 'confirmation',
              'message': 'Shall I remember that the project room code is K123?'});
          }
          rt.emit('t1', 'turn.finished', {'status': 'needs_user'});
          await pumpEventQueue();
        });
        expect(kind == 'approval' ? conv.pendingApproval : conv.pendingConfirmation, isNotNull);
        tester.view.physicalSize = const Size(900, 900);
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        for (final w in [300.0, 420.0, 600.0, 900.0]) {
          for (final h in [200.0, 320.0, 400.0, 500.0, 700.0]) {
            await tester.pumpWidget(host(Align(
              alignment: Alignment.topLeft,
              child: SizedBox(width: w, height: h, child: OiConversationPane(conversation: conv)),
            )));
            await tester.pump();
            expect(tester.takeException(), isNull, reason: '$kind $w x $h');
          }
        }
      }
    });

    testWidgets('an active testing mode keeps its toggle in a narrow composer (C1-06)', (tester) async {
      UriTestingTools.enabled = true;
      final (_, s) = await pumpRoot(tester, const Size(1280, 860));
      s.oi!.setTranscriptMode(true);
      s.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);
      await settle(tester);
      tester.view.physicalSize = const Size(560, 700);
      await settle(tester);
      expect(find.byKey(const ValueKey('living-composer-transcript')), findsWidgets);
      await tester.pumpWidget(const SizedBox.shrink());
      await tester.pump();
    });

    testWidgets('at a normal size the draft toolbar is in view without scrolling (live l1)', (tester) async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await tester.runAsync(() async {
        await conv.send('draft a letter');
        await openDraft(rt, conv, 't1');
      });
      tester.view.physicalSize = const Size(1264, 681);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      // l1: stacked layout, the panel gets 0.55 of a ~560 px region.
      await tester.pumpWidget(host(Align(
        alignment: Alignment.topLeft,
        child: SizedBox(width: 760, height: 308, child: DraftPanel(conversation: conv)),
      )));
      await tester.pump();
      expect(tester.takeException(), isNull);
      expect(find.byKey(const ValueKey('scroll-when-short')), findsNothing);
      final undo = tester.getRect(find.byKey(const ValueKey('draft-undo')));
      expect(undo.bottom <= 308, isTrue, reason: '$undo');
    });

    testWidgets('the Companion note stays visible under a long chat', (tester) async {
      final rt = FakeRuntime();
      final conv = OiConversation(rt);
      await tester.runAsync(() async {
        for (var i = 1; i <= 12; i++) {
          await conv.send('message $i');
          rt.emit('t$i', 'answer.delta', {'text': 'reply $i'});
          rt.emit('t$i', 'turn.finished', {'status': 'ok'});
          await pumpEventQueue();
        }
        await conv.send('draft a letter');
        await openDraft(rt, conv, 't13');
      });
      tester.view.physicalSize = const Size(440, 680);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      await tester.pumpWidget(
          host(SizedBox(width: 400, height: 260, child: OiConversationPane(conversation: conv, compact: true))));
      await tester.pump();
      expect(tester.takeException(), isNull);
      expect(find.byKey(const ValueKey('companion-draft-note')), findsOneWidget);
      expect(tester.getRect(find.byKey(const ValueKey('companion-draft-note'))).bottom <= 260 + 0.5, isTrue);
    });

    for (final ui in [UiPresentationMode.workspace, UiPresentationMode.dashboard]) {
      testWidgets('${ui.name} -> Companion across window sizes and scale, testing tools on', (tester) async {
        UriTestingTools.enabled = true;
        final (rt, s) = await pumpRoot(tester, const Size(1280, 860));
        await tester.runAsync(() async {
          await s.oi!.send('draft a letter');
          await openDraft(rt, s.oi!, 't1');
        });
        s.presentation.setMode(ui, focus: WorkspaceFocus.conversation);
        await settle(tester);
        // The live shrink passes through intermediate sizes for a frame each (l13: 681 px, then the Companion box).
        for (final (size, dpr) in [
          (const Size(1280, 860), 1.0),
          (const Size(900, 681), 1.0),
          (const Size(681, 520), 1.25),
          (const Size(520, 420), 1.5),
          (const Size(420, 360), 1.0),
          (const Size(360, 300), 2.0),
        ]) {
          tester.view.physicalSize = size * dpr;
          tester.view.devicePixelRatio = dpr;
          await tester.pump();
          expect(tester.takeException(), isNull, reason: '$size @ $dpr');
        }
        s.presentation.setMode(UiPresentationMode.companion);
        await settle(tester);
        expect(tester.takeException(), isNull);
        await tester.pumpWidget(const SizedBox.shrink());
        await tester.pump();
      });
    }
  });
}
