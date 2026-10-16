from pathlib import Path
p=Path('uri_ui/lib/living/presentation/living_shell.dart');s=p.read_text(encoding='utf-8').replace('(shell.width - 220).clamp(140.0, 220.0)', 'shell.width > 480 ? math.min(shell.width * .53, shell.height * .36) : (shell.width - 220).clamp(140.0, 220.0)').replace('shell.height * .29 - size / 2,', 'shell.height * (shell.width > 480 ? .30 : .31) - size / 2,')
s=s.replace('mode == UiPresentationMode.companion &&\n                  !services.effects.reducedMotion', 'mode == UiPresentationMode.companion &&\n                  CompanionModeView.usesOrbit(shellSize) &&\n                  !services.effects.reducedMotion');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/screens/companion_mode_view.dart');s=p.read_text(encoding='utf-8').replace('actions.length <= 4 && textScale <= 1.2', 'actions.length <= 4 && textScale <= 1.2 && usesOrbit(size)')
a=s.index('  static double buttonDiameter(');b=s.index('  static Rect voiceRect(',a)
s=s[:a]+'''  static bool usesOrbit(Size size) => size.height >= size.width * 1.4;
  static double buttonDiameter(Size size) => (size.width * .12).clamp(80.0, 100.0);
  static double voiceScale(Size size) => (size.width / 500).clamp(1.0, 1.7);
  static double orbitRadius(Size size) {
    final diameter = buttonDiameter(size);
    final wanted = size.width > 480 ? size.width * .34 : ((size.width - diameter) / 2 - 20).clamp(0.0, 160.0);
    final centerY = size.height * (size.width > 480 ? .30 : .31);
    return math.min(wanted, math.min(size.width / 2 - diameter / 2 - 12, centerY - diameter / 2 - 12));
  }

'''+s[b:]
s=s.replace('final bottom = textScale > 1.2', 'final bottom = textScale > 1.2 || !usesOrbit(size)');s=s.replace('textScale > 1.2 ? 90 : 64,', '(textScale > 1.2 ? 90 : 64) * voiceScale(size),');s=s.replace('math.min(300.0, size.width - 24)', 'math.min(size.width * .54, 450.0)');s=s.replace('math.max(96, size.height - top - 12),', 'math.max(96, textScale > 1.2 ? size.height - top - 12 : math.min(size.height - top - 12, math.max(184, size.height * .215))),')
s=s.replace('                    Positioned.fill(\n                      child: IgnorePointer(', '                    if (CompanionModeView.usesOrbit(box.biggest)) Positioned.fill(\n                      child: IgnorePointer(')
s=s.replace('child: _DetachedChat(\n                          filePicker:', '''child: MediaQuery(
                          data: MediaQuery.of(context).copyWith(textScaler: TextScaler.linear(
                            MediaQuery.textScalerOf(context).scale(14) / 14 * (box.maxWidth / 440).clamp(1.0, 1.5))),
                          child: _DetachedChat(
                          filePicker:''');s=s.replace('onClose: () => widget.onChatChanged?.call(false),\n                        ),', 'onClose: () => widget.onChatChanged?.call(false),\n                        )),')
s=s.replace('vertical: true,', 'vertical: true,\n                          visualScale: CompanionModeView.voiceScale(box.biggest),');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/voice/voice_stage.dart');s=p.read_text(encoding='utf-8').replace('this.vertical = false,', 'this.vertical = false,\n    this.visualScale = 1,').replace('final bool vertical;', 'final bool vertical;\n  final double visualScale;').replace('width: 170,\n                            height: 34,','width: 170 * widget.visualScale,\n                            height: 34 * widget.visualScale,').replace('fontSize: 14,\n                            color:', 'fontSize: 14 * widget.visualScale,\n                            color:');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/test/living/ui_v2_test.dart');s=p.read_text(encoding='utf-8').replace('expect(b.left, greaterThanOrEqualTo(0));','expect(b.left, greaterThanOrEqualTo(0));\n          expect(b.top, greaterThanOrEqualTo(0));');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/tool/capture/ui_v2_capture.dart');s=p.read_text(encoding='utf-8').replace("      _size.value = const Size(440, 680);\n      await settle();", "      _size.value = const Size(828, 1280);\n      services.voice.add(const ListeningStarted('capture-reference-fixture'));\n      services.voice.add(const AudioLevel(VoiceSpeaker.user, 0.18));\n      await shot('companion-approved-828');\n      services.voice.add(const VoiceReset());\n      _size.value = const Size(440, 680);\n      await settle();",1);p.write_text(s,encoding='utf-8')
