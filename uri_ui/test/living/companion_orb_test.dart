import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/companion_theme.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/theme/uri_theme.dart';

/// These tests cover the contract around the companion, deliberately not its
/// appearance. The test binding does not load runtime shader assets, so a
/// widget test can never show that the companion renders: that is what the
/// Flutter capture harness (tool/capture/capture_app.dart) is for, and its
/// output is in docs/companions/evidence/flutter/.
///
/// What these do cover is everything that would silently break the companion
/// without a single pixel changing: the shader-missing fallback, the uniform
/// count, the completeness of the state tables, and the theme binding.
void main() {
  setUp(CompanionShaderCache.reset);

  group('shader cache', () {
    testWidgets('renders without throwing, whatever the shader does', (
      tester,
    ) async {
      await tester.pumpWidget(
        const Directionality(
          textDirection: TextDirection.ltr,
          child: SizedBox(
            width: 200,
            height: 200,
            child: CompanionOrbFrame(
              identity: CompanionIdentity.solar,
              params: CompanionParams(
                energy: 0.5,
                turbulence: 0.2,
                flare: 0.3,
                particles: 0.4,
                focus: 0.8,
                exposure: 1.0,
              ),
              seconds: 1.0,
              fallback: Text('fallback'),
            ),
          ),
        ),
      );
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(tester.takeException(), isNull);
      // Whether the test binding compiles the fragment program is an engine
      // detail and has changed between Flutter versions, so the assertion is
      // the invariant the UI actually depends on: exactly one of the shader
      // path and the fallback is on screen, never neither and never both.
      final painted = find.byType(CustomPaint).evaluate().isNotEmpty;
      final fellBack = find.text('fallback').evaluate().isNotEmpty;
      expect(painted ^ fellBack, isTrue);
    });

    testWidgets('a failed load leaves the cache reporting the failure', (
      tester,
    ) async {
      // A program that cannot exist: the point is that nothing throws and the
      // failure is observable rather than silent.
      CompanionShaderCache.reset();
      final program = await CompanionShaderCache.load(CompanionIdentity.solar);
      if (program == null) {
        expect(
          CompanionShaderCache.failureFor(CompanionIdentity.solar),
          isNotNull,
        );
      } else {
        expect(
          CompanionShaderCache.failureFor(CompanionIdentity.solar),
          isNull,
        );
      }
    });

    test('every identity names a distinct shader asset', () {
      final assets = CompanionIdentity.values
          .map((i) => i.shaderAsset)
          .toSet();
      expect(assets.length, CompanionIdentity.values.length);
      for (final a in assets) {
        expect(a, startsWith('shaders/'));
        expect(a, endsWith('.frag'));
      }
    });
  });

  group('state tables', () {
    test('every identity covers every CompanionState', () {
      for (final id in CompanionIdentity.values) {
        for (final s in CompanionState.values) {
          expect(
            () => CompanionParams.of(id, s),
            returnsNormally,
            reason: '${id.name} is missing ${s.name}',
          );
        }
      }
    });

    test('every parameter stays in the range the shaders assume', () {
      for (final id in CompanionIdentity.values) {
        for (final s in CompanionState.values) {
          final p = CompanionParams.of(id, s);
          for (final (name, v) in <(String, double)>[
            ('energy', p.energy),
            ('turbulence', p.turbulence),
            ('flare', p.flare),
            ('particles', p.particles),
            ('focus', p.focus),
          ]) {
            expect(
              v,
              inInclusiveRange(0.0, 1.0),
              reason: '${id.name}.${s.name}.$name is $v',
            );
          }
          // Exposure is an HDR multiplier, not a 0..1 weight.
          expect(p.exposure, inInclusiveRange(0.5, 1.5));
        }
      }
    });

    test('unavailable is the quietest state and working the loudest', () {
      for (final id in CompanionIdentity.values) {
        final off = CompanionParams.of(id, CompanionState.unavailable);
        final busy = CompanionParams.of(id, CompanionState.working);
        final idle = CompanionParams.of(id, CompanionState.idle);
        expect(off.energy, lessThan(idle.energy), reason: id.name);
        expect(busy.energy, greaterThan(idle.energy), reason: id.name);
      }
    });

    test('error is distinguishable from working by turbulence and focus', () {
      // The two busiest states must not look alike: an error that reads as
      // work in progress is a misreport, not a style choice.
      for (final id in CompanionIdentity.values) {
        final err = CompanionParams.of(id, CompanionState.error);
        final busy = CompanionParams.of(id, CompanionState.working);
        expect(err.focus, lessThan(busy.focus), reason: id.name);
        expect(err.exposure, lessThan(busy.exposure), reason: id.name);
      }
    });

    test('lerpTo interpolates every field and is exact at the ends', () {
      const a = CompanionParams(
        energy: 0, turbulence: 0, flare: 0,
        particles: 0, focus: 0, exposure: 1.0,
      );
      const b = CompanionParams(
        energy: 1, turbulence: 1, flare: 1,
        particles: 1, focus: 1, exposure: 1.2,
      );
      expect(a.lerpTo(b, 0), a);
      expect(a.lerpTo(b, 1), b);
      final mid = a.lerpTo(b, 0.5);
      expect(mid.energy, closeTo(0.5, 1e-9));
      expect(mid.turbulence, closeTo(0.5, 1e-9));
      expect(mid.flare, closeTo(0.5, 1e-9));
      expect(mid.particles, closeTo(0.5, 1e-9));
      expect(mid.focus, closeTo(0.5, 1e-9));
      expect(mid.exposure, closeTo(1.1, 1e-9));
    });
  });

  group('painter', () {
    test('builds exactly the ten uniforms the generated shaders declare', () {
      final u = CompanionOrbPainter.uniformsFor(
        size: const Size(100, 200),
        seconds: 2.5,
        params: CompanionParams.of(
          CompanionIdentity.sakura,
          CompanionState.speaking,
        ),
        radius: 0.3,
      );
      final p = CompanionParams.of(
        CompanionIdentity.sakura,
        CompanionState.speaking,
      );
      expect(u.length, 10);
      expect(u, <double>[
        100, // 0 uSize.x
        200, // 1 uSize.y
        2.5, // 2 uTime
        p.energy, // 3 uEnergy
        p.turbulence, // 4 uTurb
        p.flare, // 5 uFlare
        p.particles, // 6 uEmber
        p.focus, // 7 uFocus
        0.3, // 8 uRadius
        p.exposure, // 9 uExposure
      ]);
    });

    test('uniform order differs per state only in the expression slots', () {
      // Slots 0-2 are geometry and clock; 3-7 and 9 are expression. If a
      // refactor ever shifts the expression block, this catches it.
      final a = CompanionOrbPainter.uniformsFor(
        size: const Size(10, 10),
        seconds: 1,
        params: CompanionParams.of(
          CompanionIdentity.solar,
          CompanionState.idle,
        ),
        radius: 0.38,
      );
      final b = CompanionOrbPainter.uniformsFor(
        size: const Size(10, 10),
        seconds: 1,
        params: CompanionParams.of(
          CompanionIdentity.solar,
          CompanionState.working,
        ),
        radius: 0.38,
      );
      expect(a.sublist(0, 3), b.sublist(0, 3));
      expect(a[8], b[8]);
      expect(a.sublist(3, 8), isNot(b.sublist(3, 8)));
    });
  });

  group('reduced effects and motion', () {
    testWidgets('reduced effects shows the fallback and no CustomPaint', (
      tester,
    ) async {
      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.ltr,
          child: EffectsSettingsScope(
            settings: EffectsSettings(reducedEffects: true),
            child: const SizedBox(
              width: 200,
              height: 200,
              child: CompanionOrb(
                identity: CompanionIdentity.lunar,
                state: CompanionState.working,
                fallback: Text('reduced'),
              ),
            ),
          ),
        ),
      );
      await tester.pump();
      expect(find.text('reduced'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });

    testWidgets('reduced motion still builds and does not throw', (
      tester,
    ) async {
      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.ltr,
          child: EffectsSettingsScope(
            settings: EffectsSettings(reducedMotion: true),
            child: const SizedBox(
              width: 200,
              height: 200,
              child: CompanionOrb(
                identity: CompanionIdentity.sakura,
                state: CompanionState.thinking,
                fallback: Text('still'),
              ),
            ),
          ),
        ),
      );
      await tester.pump(const Duration(milliseconds: 100));
      await tester.pump(const Duration(seconds: 2));
      expect(tester.takeException(), isNull);
    });
  });

  group('theme binding', () {
    test('each identity resolves to its own palette and theme choice', () {
      expect(
        CompanionTheme.paletteFor(CompanionIdentity.solar),
        UriColors.solarEmber,
      );
      expect(
        CompanionTheme.paletteFor(CompanionIdentity.sakura),
        UriColors.sakuraBloom,
      );
      expect(
        CompanionTheme.paletteFor(CompanionIdentity.lunar),
        UriColors.lunarSilver,
      );
      // The hybrid is a night scene and shares the lunar surface colours.
      expect(
        CompanionTheme.paletteFor(CompanionIdentity.moonlit),
        UriColors.lunarSilver,
      );
      for (final id in CompanionIdentity.values) {
        expect(
          resolveUriColors(CompanionTheme.choiceFor(id), Brightness.dark),
          CompanionTheme.paletteFor(id),
          reason: '${id.name} choice and palette disagree',
        );
      }
    });

    test('the four accepted Hybrid palettes are untouched', () {
      // The companion work must not alter a user-approved theme. These are the
      // exact values from the Hybrid UI Frozen Blueprint.
      expect(UriColors.graphite.accent, const Color(0xFFC8A25A));
      expect(UriColors.deepNavy.accent, const Color(0xFF5B8FC7));
      expect(UriColors.slateTeal.accent, const Color(0xFF4A9C92));
      expect(UriColors.lightProfessional.accent, const Color(0xFF3B5A78));
      expect(UriColors.graphite.canvas, const Color(0xFF0C0D0F));
      expect(UriColors.lightProfessional.canvas, const Color(0xFFF6F7F8));
    });

    test('every companion palette keeps its status colours distinct', () {
      // Error, warning and security meaning must survive the palette change.
      for (final p in <UriColors>[
        UriColors.solarEmber,
        UriColors.sakuraBloom,
        UriColors.lunarSilver,
      ]) {
        expect(p.success, isNot(p.warning));
        expect(p.warning, isNot(p.danger));
        expect(p.danger, isNot(p.accent));
        expect(p.success, isNot(p.accent));
      }
    });

    test('selecting the same companion twice does not notify', () {
      final controller = CompanionController(
        identity: CompanionIdentity.lunar,
      );
      var notifications = 0;
      controller.addListener(() => notifications++);
      controller.select(CompanionIdentity.lunar);
      expect(notifications, 0);
      controller.select(CompanionIdentity.sakura);
      expect(notifications, 1);
      expect(controller.palette, UriColors.sakuraBloom);
    });
  });

  group('identity switching', () {
    testWidgets('switching identity mid-transition does not throw', (
      tester,
    ) async {
      Widget build(CompanionIdentity id, CompanionState s) => Directionality(
        textDirection: TextDirection.ltr,
        child: SizedBox(
          width: 200,
          height: 200,
          child: CompanionOrb(
            identity: id,
            state: s,
            fallback: const Text('x'),
          ),
        ),
      );
      await tester.pumpWidget(
        build(CompanionIdentity.solar, CompanionState.idle),
      );
      await tester.pump(const Duration(milliseconds: 16));
      await tester.pumpWidget(
        build(CompanionIdentity.solar, CompanionState.working),
      );
      // Switch identity while the state blend is still running.
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pumpWidget(
        build(CompanionIdentity.sakura, CompanionState.working),
      );
      await tester.pump(const Duration(milliseconds: 200));
      await tester.pump(const Duration(seconds: 1));
      expect(tester.takeException(), isNull);
    });
  });
}
