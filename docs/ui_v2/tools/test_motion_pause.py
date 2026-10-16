from pathlib import Path
p=Path('uri_ui/lib/main_v2_preview.dart');s=p.read_text(encoding='utf-8').replace('services.moveCompanionWindow = native.move;', 'services.moveCompanionWindow = native.move;\n  services.readCompanionPointer = native.cursorPosition;');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/voice/voice_stage.dart');s=p.read_text(encoding='utf-8').replace('color: UriColors.of(context).ink)', "color: const Color(0xFFF1EEE5), shadows: const [Shadow(color: Color(0xCC000000), blurRadius: 4)])")
# Requires material Color/Shadow already imported via widgets? Shadow exported rendering and Color via widgets yes.
p.write_text(s,encoding='utf-8')
p=Path('uri_ui/test/living/ui_v2_test.dart');s=p.read_text(encoding='utf-8');a=s.index("  testWidgets(\n    'viewer exposes")
s=s[:a]+'''  testWidgets('orbit stops for nearby pointer, open chat and reduced motion', (tester) async {
    final (_, _, services) = await pumpV2(tester);
    var pointer = const Offset(-1000,-1000);
    services.readCompanionPointer = () async => pointer;
    await tester.tap(find.byKey(LivingShell.orbKey));
    await tester.pump(const Duration(milliseconds:350)); await tester.pumpAndSettle();
    final chat = find.byKey(const ValueKey('a2ui.companion-controls.chat'));
    final start = tester.getRect(chat);
    services.effects.setReducedMotion(false);
    for(var i=0;i<25;i++) { await tester.pump(const Duration(milliseconds:100)); }
    expect((tester.getRect(chat).center-start.center).distance, greaterThan(1));
    pointer = tester.getRect(find.byKey(LivingShell.orbKey)).center;
    for(var i=0;i<3;i++) { await tester.pump(const Duration(milliseconds:100)); }
    final paused = tester.getRect(chat);
    for(var i=0;i<20;i++) { await tester.pump(const Duration(milliseconds:100)); }
    expect(tester.getRect(chat), paused);
    pointer = const Offset(-1000,-1000);
    await tester.tap(chat); await tester.pump();
    final opened = tester.getRect(chat);
    for(var i=0;i<25;i++) { await tester.pump(const Duration(milliseconds:100)); }
    expect(tester.getRect(chat), opened);
    services.effects.setReducedMotion(true);
    await tester.tap(find.byKey(const ValueKey('companion-close-chat')));
    await tester.pumpAndSettle();
    final reduced = tester.getRect(chat);
    await tester.pump(const Duration(seconds:5));
    expect(tester.getRect(chat), reduced);
    expect(tester.takeException(), isNull);
  });
'''+s[a:];p.write_text(s,encoding='utf-8')
