from pathlib import Path
p=Path('uri_ui/tool/capture/ui_v2_capture.dart');s=p.read_text(encoding='utf-8');s=s.replace("import 'dart:io';", "import 'dart:io';\nimport 'dart:async';");s=s.replace("import 'package:uri_ui/services/app_state.dart';", "import 'package:uri_ui/services/app_state.dart';\nimport 'package:uri_ui/services/live_voice_service.dart';\nimport 'package:uri_ui/models/uri_turn.dart';")
s=s.replace('Future<void> main() async {', '''class FixtureVoiceTransport implements VoiceTransport {
  final eventsController = StreamController<Map<String, dynamic>>.broadcast();
  @override Stream<Map<String, dynamic>> get events => eventsController.stream;
  @override Future<int> get exitCode => Completer<int>().future;
  @override void send(Map<String, Object?> command) {}
  @override Future<void> close() => eventsController.close();
}

Future<void> main() async {''')
s=s.replace("      gesture!.onTap!();\n      await shot('companion-action-launcher');", '''      final fixtureVoice = LiveVoiceService(launch: () async => FixtureVoiceTransport());
      services.attachLiveVoice(fixtureVoice);
      await fixtureVoice.ensureStarted();
      fixtureVoice.status.value = const VoiceServiceStatus(state: VoiceServiceState.ready);
      gesture!.onTap!();
      await shot('companion-action-launcher');
      app.conversation.add(UriTurn(id: 'visual-fixture', userText: 'Can you help with my draft?',
        timestamp: DateTime(2026,10,13), stage: TurnStage.completed,
        result: const ActionResult(summary: 'What would you like to change?')));
      press('a2ui.companion-controls.chat');
      await shot('companion-detached-chat');''')
s=s.replace("      press('a2ui.companion-controls.chat');\n      await shot('chat-workspace');", "      services.presentation.setMode(UiPresentationMode.workspace, focus: WorkspaceFocus.conversation);\n      await shot('chat-workspace');")
p.write_text(s,encoding='utf-8')
