from pathlib import Path
p=Path('uri_ui/lib/living/voice/voice_stage.dart');s=p.read_text(encoding='utf-8').replace("import '../../theme/uri_theme.dart';\n",'');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/tool/capture/ui_v2_capture.dart');s=p.read_text(encoding='utf-8').replace("services.voice.add(const ListeningStarted('capture-fixture'));", "services.voice.add(const ListeningStarted('capture-fixture'));\n      services.voice.add(const AudioLevel(VoiceSpeaker.user, 0.18));")
s=s.replace('          orb: openOrb,\n          buttons:', '''          orb: openOrb,
          orbit: Rect.fromCircle(center: openOrb.center, radius: CompanionModeView.orbitRadius(const Size(440,680))),
          panel: CompanionModeView.chatRect(const Size(440,680),openOrb),
          buttons:''');p.write_text(s,encoding='utf-8')
