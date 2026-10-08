import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/companion/energy_orb.dart';
import 'package:uri_ui/theme/uri_theme.dart';

void main() {
  Widget host(Widget child, {bool reducedEffects = false, bool reducedMotion = false}) {
    return EffectsSettingsScope(
      settings: EffectsSettings(reducedEffects: reducedEffects, reducedMotion: reducedMotion),
      child: MaterialApp(
        theme: buildUriTheme(UriColors.obsidianCyan),
        home: Scaffold(body: Center(child: child)),
      ),
    );
  }

  for (final state in CompanionState.values) {
    testWidgets('renders ${state.name} with effects on, animating, no exceptions', (tester) async {
      await tester.pumpWidget(host(EnergyOrb(state: state, size: 200, progress: 0.4)));
      for (var i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 120));
      }
      expect(find.byType(EnergyOrb), findsOneWidget);
      expect(find.bySemanticsLabel('URI companion: ${state.label}'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('renders ${state.name} with reduced effects + reduced motion (still frame)',
        (tester) async {
      await tester.pumpWidget(
        host(EnergyOrb(state: state, size: 120), reducedEffects: true, reducedMotion: true),
      );
      await tester.pump(const Duration(milliseconds: 50));
      // With reduced motion the orb schedules no further frames: pumpAndSettle completes.
      await tester.pumpAndSettle();
      expect(find.bySemanticsLabel('URI companion: ${state.label}'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }

  test('every state has distinct painter parameters (state is never visually ambiguous)', () {
    final seen = <String>{};
    for (final s in CompanionState.values) {
      final p = OrbParams.forState(s);
      final signature =
          '${p.breathRate}|${p.particleSpeed}|${p.particleSpread}|${p.energy}|${p.turbulence}|${p.tintMix}|${p.ringStrength}|${p.orbitArc}|${p.bloom}|${p.rippleStrength}';
      expect(seen.add(signature), isTrue, reason: '${s.name} duplicates another state');
    }
  });

  test('OrbParams.lerp is continuous at both ends', () {
    final a = OrbParams.forState(CompanionState.idle);
    final b = OrbParams.forState(CompanionState.working);
    expect(OrbParams.lerp(a, b, 0).energy, a.energy);
    expect(OrbParams.lerp(a, b, 1).energy, b.energy);
    final mid = OrbParams.lerp(a, b, 0.5);
    expect(mid.orbitArc, closeTo(0.5, 1e-9));
  });

  testWidgets('state changes tween rather than cut: the same element survives', (tester) async {
    final key = GlobalKey();
    await tester.pumpWidget(host(EnergyOrb(key: key, state: CompanionState.idle, size: 160)));
    await tester.pump(const Duration(milliseconds: 100));
    final before = key.currentState;
    await tester.pumpWidget(host(EnergyOrb(key: key, state: CompanionState.thinking, size: 160)));
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.pump(const Duration(milliseconds: 400));
    expect(identical(before, key.currentState), isTrue);
    expect(find.bySemanticsLabel('URI companion: Thinking'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('the orb reads its glow from the active theme (no hardcoded cyan)', (tester) async {
    for (final palette in [UriColors.graphite, UriColors.lightProfessional, UriColors.obsidianCyan]) {
      await tester.pumpWidget(
        EffectsSettingsScope(
          settings: EffectsSettings(reducedMotion: true),
          child: MaterialApp(
            theme: buildUriTheme(palette),
            home: const Scaffold(body: EnergyOrb(state: CompanionState.idle, size: 100)),
          ),
        ),
      );
      await tester.pump();
      expect(tester.takeException(), isNull);
    }
  });
}
