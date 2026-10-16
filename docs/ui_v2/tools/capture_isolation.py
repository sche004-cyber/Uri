from pathlib import Path
p=Path(__file__).resolve().parents[3]/'uri_ui/tool/capture/ui_v2_capture.dart'
s=p.read_text();a=s.index('      await native.update(CompanionWindowLayout(active: true, orb: closedOrb));');b=s.index('      GestureDetector? gesture;',a);block=s[a:b];s=s[:a]+s[b:]
a=s.index('      await native.update(\n        CompanionWindowLayout(\n          active: true,\n          orb: openOrb,')
s=s[:a]+block+s[a:]
# Keep native region inspection separate from UI screenshots.
a=s.index("      press('a2ui.companion-controls.chat');")
b=s.index('      _size.value = const Size(1440, 1000);',a)
s=s[:a]+'''      await native.update(const CompanionWindowLayout(active:false,orb:Rect.zero));
      press('a2ui.companion-controls.chat');
      await shot('chat-workspace');
'''+s[b:]
p.write_text(s)
