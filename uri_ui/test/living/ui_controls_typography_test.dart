import 'dart:io';

import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:uri_ui/living/integration/brain_quick_controls.dart';
import 'package:uri_ui/living/integration/qc_toggle.dart';
import 'package:uri_ui/theme/uri_theme.dart';

import 'brain_quick_controls_test.dart' show QcRuntime, controls, ready, pumpControls, lvReason;

/// UI-CONTROLS-TYPO-20261018: push-to-enable controls (states, glow only
/// from verified state, coupled Vision / Context, failed-switch restore)
/// and the single type system.

BoxDecoration deco(WidgetTester t, String key) => t
    .widget<AnimatedContainer>(find.descendant(of: find.byKey(ValueKey(key)), matching: find.byType(AnimatedContainer)).first)
    .decoration! as BoxDecoration;

QcToggle toggle(WidgetTester t, String key) => t.widget<QcToggle>(find.byKey(ValueKey(key)));

int reconfigures(QcRuntime rt) => rt.commands.where((c) => c['command'] == 'brain_reconfigure').length;

void main() {
  group('Vision toggle (coupled to context by the qualified catalog)', () {
    testWidgets('on at Standard: one click asks to switch to Long context, glow stays until the switch is verified',
        (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(toggle(tester, 'qc-vision').visual, QcVisual.on);
      expect(toggle(tester, 'qc-vision').tooltip, contains('Also changes context to 64K'));
      await tester.tap(find.byKey(const ValueKey('qc-vision')));
      await tester.pumpAndSettle();
      expect(find.text('Switch the Brain to Long context?'), findsOneWidget);
      // the coupled change is stated: vision on -> off AND context 32K -> 64K
      final changes = find.byKey(const ValueKey('qc-confirm-changes'));
      expect(find.descendant(of: changes, matching: find.text('Off')), findsNWidgets(2), reason: 'vision and draft');
      expect(find.descendant(of: changes, matching: find.text('64K')), findsOneWidget);
      expect(find.descendant(of: changes, matching: find.text('32K')), findsOneWidget);
      await tester.tap(find.byKey(const ValueKey('qc-confirm-switch-go')));
      await tester.pumpAndSettle();
      expect(reconfigures(rt), 1);
      expect(rt.commands.firstWhere((c) => c['command'] == 'brain_reconfigure')['profile_id'], 'long');
      // the worker has not confirmed anything yet: the shown state is still the verified one
      expect(toggle(tester, 'qc-vision').visual, QcVisual.on);
      // switch running: loading, no glow
      rt.health = {'state': 'RECOVERING', 'controls': controls(pending: true)};
      await conv.refreshHealth();
      await tester.pump();
      expect(toggle(tester, 'qc-vision').visual, QcVisual.loading);
      expect(deco(tester, 'qc-vision').boxShadow, anyOf(isNull, isEmpty));
      // verified on Long context: vision off (subdued), 64K selected (glows)
      rt.health = {'state': 'READY', 'controls': controls(active: 'long', last: {'id': 'req-1', 'result': 'READY', 'seconds': 30})};
      await conv.refreshHealth();
      await tester.pumpAndSettle();
      expect(toggle(tester, 'qc-vision').visual, QcVisual.off);
      expect(deco(tester, 'qc-vision').boxShadow, anyOf(isNull, isEmpty));
      expect(deco(tester, 'qc-context-64K').boxShadow, isNotEmpty);
      expect(find.text('Brain switched in 30 s. Your conversation is kept.'), findsOneWidget);
    });

    testWidgets('off at Long context: vision on is offered only with 32K and the unqualified 64K + vision says why',
        (tester) async {
      final rt = QcRuntime()..health = {'state': 'READY', 'controls': controls(active: 'long')};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(toggle(tester, 'qc-vision').visual, QcVisual.off);
      expect(toggle(tester, 'qc-vision').tooltip, contains(lvReason));
      await tester.tap(find.byKey(const ValueKey('qc-vision')));
      await tester.pumpAndSettle();
      expect(find.text('Switch the Brain to Standard?'), findsOneWidget);
      expect(find.textContaining('On at 64K: $lvReason'), findsOneWidget);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(reconfigures(rt), 0);
    });

    testWidgets('no qualified target: the toggle is disabled and says why', (tester) async {
      final c = controls(active: 'standard');
      // only Standard is offered
      c['options'] = [for (final o in c['options'] as List) if (o['id'] == 'standard' || o['id'] == 'long-vision') o];
      final rt = QcRuntime()..health = {'state': 'READY', 'controls': c};
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      expect(toggle(tester, 'qc-vision').onPressed, isNull);
      expect(toggle(tester, 'qc-vision').tooltip, startsWith('Vision off is not available'));
    });
  });

  group('failed switch: the host restores the previous setting', () {
    Map<String, dynamic> last(Map<String, dynamic> fb, {bool restored = false}) =>
        {'id': 'req-1', 'result': 'FAILED', 'restored': restored, 'fallback': fb};

    testWidgets('while it goes back, the indicator says so; then the notice explains and nothing glows falsely',
        (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await conv.reconfigureBrain('long');
      final pending = controls(pending: true);
      (pending['switch'] as Map)['target'] = {'id': 'req-1', 'label': 'Long context'};
      (pending['switch'] as Map)['last'] = last({'to': 'frozen', 'label': 'Standard', 'result': 'IN_PROGRESS'});
      rt.health = {'state': 'RECOVERING', 'controls': pending};
      await conv.refreshHealth();
      await pumpControls(tester, conv);
      expect(find.text('Did not start; going back to Standard…'), findsOneWidget);
      expect(toggle(tester, 'qc-vision').visual, QcVisual.loading);
      // restored: Standard verified again, the notice says what happened (warning tone)
      rt.health = {
        'state': 'READY',
        'controls': controls(active: 'standard', last: last({'to': 'frozen', 'label': 'Standard', 'result': 'READY'}, restored: true)),
      };
      await conv.refreshHealth();
      await tester.pumpAndSettle();
      expect(find.text('The Brain did not start with the new setting, so URI went back to Standard. '
          'Your conversation is kept.'), findsOneWidget);
      expect(toggle(tester, 'qc-vision').visual, QcVisual.on, reason: 'Standard (vision on) runs again, verified');
      final notice = tester.widget<Text>(find.byKey(const ValueKey('qc-notice')));
      expect(notice.style!.color, UriColors.of(tester.element(find.byKey(const ValueKey('qc-notice')))).warning);
    });

    testWidgets('restore failed too: truthful error, error look, no glow', (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await conv.reconfigureBrain('long');
      rt.health = {
        'state': 'UNAVAILABLE',
        'controls': controls(last: last({'to': 'frozen', 'label': 'Standard', 'result': 'FAILED'})),
      };
      await conv.refreshHealth();
      await pumpControls(tester, conv);
      expect(find.text('The Brain did not start with the new setting, and going back to Standard failed too. '
          'Use Restart Brain.'), findsOneWidget);
      expect(toggle(tester, 'qc-vision').visual, QcVisual.error);
      final ctx = tester.element(find.byKey(const ValueKey('qc-vision')));
      expect((deco(tester, 'qc-vision').border as Border).top.color, UriColors.of(ctx).danger);
      expect(deco(tester, 'qc-vision').boxShadow, anyOf(isNull, isEmpty));
    });
  });

  group('states are distinguishable', () {
    testWidgets('off, hover, pressed, on (glow), disabled', (tester) async {
      final rt = QcRuntime();
      final conv = await ready(rt);
      await pumpControls(tester, conv);
      final off = deco(tester, 'qc-thinking');
      expect(off.boxShadow, anyOf(isNull, isEmpty));
      final mouse = await tester.createGesture(kind: PointerDeviceKind.mouse);
      await mouse.addPointer(location: Offset.zero);
      addTearDown(mouse.removePointer);
      await mouse.moveTo(tester.getCenter(find.textContaining('Thinking', findRichText: true).first));
      await tester.pumpAndSettle();
      final hover = deco(tester, 'qc-thinking');
      expect(hover.color, isNot(off.color), reason: 'hover tint');
      final press = await tester.startGesture(tester.getCenter(find.textContaining('Thinking', findRichText: true).first));
      await tester.pump(const Duration(milliseconds: 150)); // past the tap-down deadline (the tooltip also listens)
      await tester.pump(const Duration(milliseconds: 200));
      final pressed = deco(tester, 'qc-thinking');
      expect(pressed.color, isNot(hover.color), reason: 'pressed tint');
      await press.up();
      await tester.pumpAndSettle();
      final on = deco(tester, 'qc-thinking');
      expect(on.boxShadow, isNotEmpty, reason: 'enabled glow');
      expect((on.border as Border).top.color, isNot((off.border as Border).top.color));
      // idle with a glowing control: no animation keeps running (pumpAndSettle returned; nothing scheduled)
      expect(tester.binding.hasScheduledFrame, isFalse);
      // disabled: not interactive, faint
      rt.health = {'state': 'READY', 'controls': controls(active: 'standard', canSwitch: false)};
      await conv.refreshHealth();
      await tester.pumpAndSettle();
      expect(toggle(tester, 'qc-vision').onPressed, isNull);
      expect(deco(tester, 'qc-vision').boxShadow, isNotEmpty, reason: 'still the verified state (vision on)');
    });
  });

  testWidgets('the confirmation keeps a readable width on a wide window', (tester) async {
    tester.view.physicalSize = const Size(1600, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    final rt = QcRuntime();
    final conv = await ready(rt);
    await pumpControls(tester, conv);
    await tester.tap(find.byKey(const ValueKey('qc-context-64K')));
    await tester.pumpAndSettle();
    final w = tester.getSize(find.descendant(of: find.byType(Dialog), matching: find.byType(Material)).first).width;
    expect(w, lessThanOrEqualTo(520), reason: 'was full window width (REFERENCE_confirm_dialog_before.png)');
    expect(find.widgetWithText(FilledButton, 'Switch Brain'), findsOneWidget);
    expect(find.widgetWithText(TextButton, 'Cancel'), findsOneWidget);
  });

  test('toggleChoice picks the qualified target and keeps the blocked reasons', () {
    const blockedOn = QcChoice(title: 'On at 64K', blocked: 'Not qualified.');
    final target = QcChoice(title: 'On', target: QcOption({'id': 'standard', 'ctx': 32768, 'qualified': true}), note: 'x');
    const off = QcChoice(title: 'Off', current: true);
    final r = toggleChoice([blockedOn, target, off], 'On');
    expect(r.choice, same(target));
    expect(r.blocked, ['On at 64K: Not qualified.']);
    expect(toggleChoice([blockedOn, target, off], 'Off').choice, isNull, reason: 'current is never a target');
  });

  group('typography', () {
    test('every text role of every theme uses the one UI family on the URI scale', () {
      for (final palette in [UriColors.graphite, UriColors.solarEmber, UriColors.lightProfessional, UriColors.ivoryFoundry]) {
        final t = buildUriTheme(palette).textTheme;
        final roles = [
          t.displayLarge, t.displayMedium, t.displaySmall, t.headlineLarge, t.headlineMedium, t.headlineSmall,
          t.titleLarge, t.titleMedium, t.titleSmall, t.bodyLarge, t.bodyMedium, t.bodySmall,
          t.labelLarge, t.labelMedium, t.labelSmall,
        ];
        for (final r in roles) {
          expect(r!.fontFamily, UriType.family);
          expect(UriType.scale, contains(r.fontSize));
        }
      }
    });

    test('no font family or off-scale size is hard-coded outside the theme', () {
      // The classic dashboard is a frozen, pixel-transcribed 1024x682 board scaled as a whole (board units);
      // settings_shell.dart is a protected frozen file (scripts/ws_frozen_check.py).
      const exempt = {
        'lib/widgets/dashboard/reference_dashboard.dart',
        'lib/theme/dashboard_manifest.dart',
        'lib/screens/settings/settings_shell.dart',
      };
      final literal = RegExp(r'fontSize:\s*\d');
      final family = RegExp(r"fontFamily:\s*'");
      final offenders = <String>[];
      for (final f in Directory('lib').listSync(recursive: true).whereType<File>()) {
        final rel = f.path.replaceAll('\\', '/');
        if (!rel.endsWith('.dart') || exempt.contains(rel)) continue;
        final src = f.readAsStringSync();
        if (literal.hasMatch(src) && !rel.endsWith('lib/theme/uri_theme.dart')) offenders.add('$rel: numeric fontSize');
        if (family.hasMatch(src)) offenders.add('$rel: fontFamily literal');
        if (src.contains("'Georgia'")) offenders.add('$rel: Georgia');
      }
      expect(offenders, isEmpty);
    });
  });
}
