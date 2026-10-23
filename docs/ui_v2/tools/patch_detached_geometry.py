from pathlib import Path
p=Path('uri_ui/test/living/ui_v2_test.dart');s=p.read_text(encoding='utf-8');a=s.index("  testWidgets(\n    'viewer exposes")
s=s[:a]+'''  test('full orbit preserves circular clearance and detached panel separation', () {
    const actions = [CompanionUiAction.chat, CompanionUiAction.dashboard, CompanionUiAction.voiceStart, CompanionUiAction.review];
    for (final size in [const Size(360, 560), const Size(440, 680)]) {
      final orb = OrbDock.forMode(UiPresentationMode.companion, size, visualV2: true, expanded: true).rect;
      final wave = CompanionModeView.voiceRect(size, orb);
      final chat = CompanionModeView.chatRect(size, orb);
      expect(chat.top, greaterThan(wave.bottom));
      expect(chat.bottom, lessThanOrEqualTo(size.height));
      for (var degrees=0; degrees<360; degrees++) {
        final buttons = CompanionModeView.buttonRects(size, orb, actions, angle: degrees*math.pi/180).values.toList();
        for (var i=0; i<buttons.length; i++) {
          final b = buttons[i];
          expect((b.center-orb.center).distance, greaterThan(orb.width/2+b.width/2+8));
          expect(b.left, greaterThanOrEqualTo(0)); expect(b.right, lessThanOrEqualTo(size.width));
          expect(b.bottom, lessThan(wave.top));
          for(var j=i+1; j<buttons.length; j++) {
            expect((b.center-buttons[j].center).distance, greaterThan((b.width+buttons[j].width)/2+8));
          }
        }
      }
    }
  });
  for (final size in [const Size(360,560), const Size(440,680)]) {
    testWidgets('detached chat at 200 percent text $size', (tester) async {
      final (_, _, services) = await pumpV2(tester, size: size);
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds:350)); await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.chat')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('living-composer-field')), findsOneWidget);
      expect(services.presentation.mode, UiPresentationMode.companion);
      expect(tester.takeException(), isNull);
    });
  }
'''+s[a:];p.write_text(s,encoding='utf-8')
