from pathlib import Path
root = Path(__file__).resolve().parents[3]
p = root/'uri_ui/test/living/ui_v2_test.dart'
s=p.read_text(encoding='utf-8')
s=s.replace("import 'package:uri_ui/living/companion/companion_design.dart';", "import 'package:uri_ui/living/a2ui/companion_actions.dart';\nimport 'package:uri_ui/living/a2ui/a2ui_hub.dart';\nimport 'package:uri_ui/living/voice/voice_session.dart';\nimport 'package:uri_ui/living/companion/companion_design.dart';")
s=s.replace("single click acknowledges once, opens chat; actual send remains in panel", "single click acknowledges once; generated chat action starts actual chat")
needle="      await tester.enterText(\n        find.byKey(const ValueKey('living-composer-field')),"
pos=s.index(needle,s.index("single click acknowledges"))
s=s[:pos]+"      expect(find.byKey(const ValueKey('living-composer-field')), findsNothing);\n      expect(transport.sent.where((m) => m['cmd'] == 'listen_start'), isEmpty);\n      await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.chat')));\n      await tester.pumpAndSettle();\n"+s[pos:]
pos=s.index("      expect(\n        find.byKey(const ValueKey('living-composer-field')),",s.index("200 percent text"))
s=s[:pos]+"      await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.chat')));\n      await tester.pumpAndSettle();\n"+s[pos:]
a=s.index("  testWidgets(\n    'compact borderless tabs")
b=s.index("  testWidgets(\n    'login guards",a)
s=s[:a]+'''  test('local A2UI catalog is isolated from runtime authority', () async {
    final invoked = <CompanionUiAction>[];
    final controls = CompanionActions((a) async => invoked.add(a));
    controls.project([CompanionUiAction.chat]);
    expect(controls.hub.surface(CompanionActions.surfaceId)?.ready, isTrue);
    await controls.hub.act(CompanionActions.surfaceId, 'voiceStart');
    expect(invoked, isEmpty);
    await controls.hub.act(CompanionActions.surfaceId, 'chat');
    expect(invoked, [CompanionUiAction.chat]);
    final runtime = A2uiHub();
    runtime.apply([{'version':'v0.9','createSurface': {'surfaceId':'attack',
      'catalogId':CompanionActions.policy.catalogId}}]);
    expect(runtime.surface('attack'), isNull);
    expect(controls.hub.registry.containsKey('scheduler.confirm'), isFalse);
    controls.dispose(); runtime.dispose();
  });
  testWidgets('compact contextual A2UI keeps drafts and omits unavailable actions', (tester) async {
    final (client, app, services) = await pumpV2(tester);
    await tester.tap(find.byKey(LivingShell.orbKey));
    await tester.pump(const Duration(milliseconds:350)); await tester.pumpAndSettle();
    final panel = find.byKey(const ValueKey('expanded-companion-panel'));
    expect(tester.getSize(panel), const Size(340,180));
    expect(tester.widget<Material>(panel).shape, isNull);
    expect(find.byKey(const ValueKey('a2ui.companion-controls.review')), findsNothing);
    expect(find.byKey(const ValueKey('a2ui.companion-controls.voiceStart')), findsNothing);
    await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.chat')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const ValueKey('living-composer-field')), 'Keep this draft');
    await tester.tap(find.byKey(const ValueKey('collapse-companion-panel'))); await tester.pump();
    await tester.tap(find.byKey(LivingShell.orbKey));
    await tester.pump(const Duration(milliseconds:350)); await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.chat'))); await tester.pumpAndSettle();
    expect(tester.widget<TextField>(find.byKey(const ValueKey('living-composer-field'))).controller!.text,'Keep this draft');
    expect(app.composerDraft,'Keep this draft');
    await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.workspace')));
    await tester.pump(const Duration(seconds:5)); await tester.pump(const Duration(seconds:1));
    expect(services.presentation.mode,UiPresentationMode.workspace); expect(client.asks,0);
  });
  testWidgets('existing voice visual follows listening, user speech and URI speech', (tester) async {
    final (_, _, services) = await pumpV2(tester);
    await tester.tap(find.byKey(LivingShell.orbKey));
    await tester.pump(const Duration(milliseconds:350)); await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('companion-voice-visual')), findsNothing);
    services.voice.add(const ListeningStarted('fixture'));
    await tester.pump(); await tester.pump(const Duration(milliseconds:600));
    expect(find.byKey(const ValueKey('stage-waveform')), findsOneWidget);
    services.voice.add(const UserSpeechStarted('fixture'));
    services.voice.add(const UserTranscript('fixture','A private fixture sentence'));
    await tester.pump();
    expect(find.text('You'), findsOneWidget);
    services.voice.add(const ListeningEnded('fixture',VoiceEndReason.completed));
    services.voice.add(const UriSpeechStarted('reply','A fixture reply'));
    await tester.pump(); await tester.pump(const Duration(milliseconds:600));
    expect(find.byKey(const ValueKey('stage-waveform')), findsOneWidget);
    services.voice.add(const VoiceReset());
    await tester.pump();
    expect(find.byKey(const ValueKey('companion-voice-visual')), findsNothing);
    await tester.pump(const Duration(seconds:5));
  });
''' +s[b:]
p.write_text(s,encoding='utf-8')
p=root/'uri_ui/tool/capture/ui_v2_capture.dart'
s=p.read_text(encoding='utf-8').replace("import 'package:uri_ui/living/living_app.dart';", "import 'package:uri_ui/living/voice/voice_session.dart';\nimport 'package:uri_ui/living/living_app.dart';")
s=s.replace("if (widget is TextButton && widget.key == ValueKey(key)) {", "if (widget is ButtonStyleButton && widget.key == ValueKey(key)) {")
a=s.index("      await shot('companion-expanded-chat');")
b=s.index("      _size.value = const Size(360, 560);",a)
s=s[:a]+'''      await shot('companion-action-launcher');
      services.voice.add(const ListeningStarted('capture-fixture'));
      await shot('companion-listening');
      services.voice.add(const UserSpeechStarted('capture-fixture'));
      services.voice.add(const UserTranscript('capture-fixture','Show the workspace'));
      services.voice.add(const AudioLevel(VoiceSpeaker.user,0.18));
      await shot('companion-user-speaking');
      services.voice.add(const ListeningEnded('capture-fixture',VoiceEndReason.completed));
      services.voice.add(const UriSpeechStarted('capture-reply','The workspace is ready to open.'));
      services.voice.add(const AudioLevel(VoiceSpeaker.uri,0.15));
      await shot('companion-uri-speaking');
      services.voice.add(const VoiceReset());
      press('a2ui.companion-controls.chat');
      await shot('companion-expanded-chat');
''' +s[b:]
s=s.replace("panel: CompanionModeView.panelRect(const Size(440, 680), openOrb)","panel: CompanionModeView.panelRect(const Size(440, 680), openOrb,preferredHeight:CompanionModeView.heightFor(services.companionPanelPage.value))")
p.write_text(s,encoding='utf-8')
