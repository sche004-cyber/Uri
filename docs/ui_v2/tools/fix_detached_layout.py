from pathlib import Path
p=Path('uri_ui/lib/living/screens/companion_mode_view.dart');s=p.read_text(encoding='utf-8').replace('child: SingleChildScrollView(\n                      child: Tooltip(', 'child: SizedBox(\n                      height: entry.value.height,\n                      child: Tooltip(').replace('(size.width - buttonDiameter(size)) / 2 - 12;', '((size.width - buttonDiameter(size)) / 2 - 12).clamp(0.0, 164.0);');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/test/living/ui_v2_test.dart');s=p.read_text(encoding='utf-8').replace('single click acknowledges once; floating Chat opens shared Workspace','single click acknowledges once; detached Chat sends through shared service').replace('expect(services.presentation.mode, UiPresentationMode.workspace);','expect(services.presentation.mode, UiPresentationMode.companion);')
a=s.index('      services.presentation.setMode(UiPresentationMode.companion);',s.index("'single click acknowledges"));b=s.index('      await tester.pump(const Duration(seconds: 5));',a)
s=s[:a]+'''      await tester.enterText(find.byKey(const ValueKey('living-composer-field')), 'Retain detached draft');
      await tester.tap(find.byKey(const ValueKey('companion-close-chat')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('living-composer-field')), findsNothing);
      expect(app.composerDraft, 'Retain detached draft');
      await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.dashboard')));
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.dashboard);
      expect(app.composerDraft, 'Retain detached draft');
      expect(app.conversation, isNotEmpty);
'''+s[b:];p.write_text(s,encoding='utf-8')
