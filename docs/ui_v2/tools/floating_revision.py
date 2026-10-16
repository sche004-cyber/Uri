from pathlib import Path
r=Path(__file__).resolve().parents[3]
p=r/'uri_ui/lib/living/presentation/living_shell.dart'
s=p.read_text();a=s.index('            final panelDock =');b=s.index('            if (layout != _windowLayout)',a)
s=s[:a]+'''            final buttonRects = _panelExpanded ? CompanionModeView.buttonRects(shellSize,dock.rect,
              CompanionModeView.actions(services,CompanionModeView.reviewCount(services,context))).values.toList() : <Rect>[];
            final layout = CompanionWindowLayout(
              active: mode == UiPresentationMode.companion,orb:dock.rect,
              buttons:buttonRects,
              panel: _panelExpanded && services.voice.session.phase != VoicePhase.off ? CompanionModeView.voiceRect(shellSize,dock.rect) : null,
            );
'''+s[b:];p.write_text(s)
p=r/'uri_ui/lib/living/living_scope.dart';s=p.read_text();s=s.replace("  final ValueNotifier<String> companionPanelPage = ValueNotifier('actions');\n",'');s=s.replace('    companionPanelPage.dispose();\n','');p.write_text(s)
p=r/'uri_ui/lib/living/presentation/living_shell.dart';s=p.read_text();s=s.replace("        if (!_panelExpanded) services.companionPanelPage.value = 'actions';\n",'');s=s.replace('        services.companionPanelPage,\n','');s=s.replace("(!services.visualV2 ||\n              services.companionPanelPage.value == 'chat')",'!services.visualV2');p.write_text(s)
p=r/'uri_ui/test/living/ui_v2_test.dart';s=p.read_text();s='\n'.join(x for x in s.split('\n') if 'VOICE_LAYOUT' not in x)
s=s.replace("single click acknowledges once; generated chat action starts actual chat", "single click acknowledges once; floating Chat opens shared Workspace")
s=s.replace("find.byKey(const ValueKey('expanded-companion-panel'))", "find.byKey(const ValueKey('a2ui.companion-controls.chat'))")
s=s.replace("await tester.tap(find.byKey(const ValueKey('collapse-companion-panel')));", "services.presentation.setMode(UiPresentationMode.companion);\n      await tester.pumpAndSettle();\n      await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.collapse')));")
s=s.replace("expect(services.presentation.mode, UiPresentationMode.companion);", "expect(services.presentation.mode, UiPresentationMode.workspace);")
a=s.index("  test('panel geometry stays inside")
b=s.index('  testWidgets(',a)
s=s[:a]+'''  test('floating controls fit both sizes without covering the Companion', () {
    for(final size in [const Size(440,680),const Size(360,560)]) {
      final orb=OrbDock.forMode(UiPresentationMode.companion,size,visualV2:true,expanded:true).rect;
      final rects=CompanionModeView.buttonRects(size,orb,CompanionUiAction.values.take(6).toList());
      for(final rect in rects.values){expect(rect.overlaps(orb),isFalse); expect(rect.left,greaterThanOrEqualTo(0));expect(rect.bottom,lessThanOrEqualTo(size.height));}
      expect(CompanionModeView.voiceRect(size,orb).top,greaterThan(orb.bottom));
    }
  });
'''+s[b:]
a=s.index("  testWidgets(\n    'compact contextual A2UI")
b=s.index("  testWidgets(\n    'existing voice visual",a)
s=s[:a]+'''  testWidgets('floating controls omit unavailable actions and preserve shared draft', (tester) async {
    final (client,app,services)=await pumpV2(tester);
    app.setComposerDraft('Keep this draft');
    await tester.tap(find.byKey(LivingShell.orbKey));
    await tester.pump(const Duration(milliseconds:350));await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('expanded-companion-panel')),findsNothing);
    expect(find.byKey(const ValueKey('living-composer-field')),findsNothing);
    expect(find.byKey(const ValueKey('a2ui.companion-controls.review')),findsNothing);
    expect(find.byKey(const ValueKey('a2ui.companion-controls.voiceStart')),findsNothing);
    await tester.tap(find.byKey(const ValueKey('a2ui.companion-controls.chat')));
    await tester.pumpAndSettle();
    expect(services.presentation.mode,UiPresentationMode.workspace);
    expect(app.composerDraft,'Keep this draft');expect(client.asks,0);
    await tester.pump(const Duration(seconds:5));
  });
'''+s[b:]
# At 200% text a floating Chat action now opens Workspace.
s=s.replace("      expect(services.presentation.mode, UiPresentationMode.workspace);\n      await tester.tap", "      expect(services.presentation.mode, UiPresentationMode.workspace);\n      await tester.tap")
p.write_text(s)
p=r/'uri_ui/test/ws/ws_integration_test.dart';s=p.read_text().replace("ValueKey('expanded-companion-panel')","ValueKey('a2ui.companion-controls.chat')");p.write_text(s)
p=r/'uri_ui/tool/capture/ui_v2_capture.dart';s=p.read_text();a=s.index("      press('a2ui.companion-controls.chat');");b=s.index('      await native.update(\n        const CompanionWindowLayout',a)
s=s[:a]+'''      _size.value = const Size(360,560);
      await shot('companion-floating-360');
      _size.value=const Size(440,680); await settle();
      final openOrb=OrbDock.forMode(UiPresentationMode.companion,const Size(440,680),visualV2:true,expanded:true).rect;
      await native.update(CompanionWindowLayout(active:true,orb:openOrb,buttons:CompanionModeView.buttonRects(const Size(440,680),openOrb,
        CompanionModeView.actions(services,CompanionModeView.reviewCount(services,LivingShell.orbKey.currentContext!))).values.toList()));
      final openFacts=await const MethodChannel('uri/companion_window').invokeMapMethod<String,dynamic>('facts');
      _log.writeln('NATIVE_FLOATING ${jsonEncode(openFacts)} error=${native.lastError}');
      if(native.lastError!=null || closedFacts?['cornerHit']!=false || openFacts?['cornerHit']!=false) failed=true;
      press('a2ui.companion-controls.chat');
      await shot('chat-workspace');
'''+s[b:];p.write_text(s)
