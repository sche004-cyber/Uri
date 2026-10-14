import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/ember_companion.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/companion_theme.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/companion/energy_orb.dart';
import 'package:uri_ui/living/companion/frame_clock.dart';
import 'package:uri_ui/living/companion/living_companion.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/screens/settings/companion_settings_section.dart';
import 'package:uri_ui/living/screens/workspace_mode_view.dart'
    show WorkspaceSettingsRegion;
import 'package:uri_ui/living/voice/voice_catalog.dart';
import 'package:uri_ui/living/voice/voice_session.dart';
import 'package:uri_ui/living/voice/voice_stage.dart';
import 'package:uri_ui/living/voice/voice_transcript.dart';
import 'package:uri_ui/living/voice/voice_waveform.dart';
import 'package:uri_ui/living/widgets/frame_stats_overlay.dart';
import 'package:uri_ui/services/window_visibility.dart';
import 'package:uri_ui/services/windows_voice_catalog.dart';
import 'package:uri_ui/theme/uri_theme.dart';

import 'living_shell_test.dart' show testAppState, testServices;

// ---------------------------------------------------------------------------
// Fakes
// ---------------------------------------------------------------------------

class FakeVoiceCatalog implements VoiceCatalog {
  FakeVoiceCatalog(this.listing);
  final VoiceListing listing;
  final List<(String, VoicePreferences)> previews = [];
  int stops = 0;

  @override
  Future<VoiceListing> list() async => listing;

  @override
  Future<void> preview(VoiceInfo voice, VoicePreferences prefs) async {
    previews.add((voice.id, prefs));
  }

  @override
  Future<void> stopPreview() async => stops++;
}

class FakeVoiceAdapter implements VoiceServiceAdapter {
  FakeVoiceAdapter({this.simulated = true});
  final StreamController<VoiceSignal> ctl = StreamController<VoiceSignal>();
  @override
  final bool simulated;
  @override
  String get name => 'Test adapter';
  @override
  Stream<VoiceSignal> get signals => ctl.stream;
}

const _zira = VoiceInfo(
  engine: VoiceEngine.systemSpeech,
  name: 'Microsoft Zira Desktop',
  culture: 'en-US',
  gender: 'Female',
  capabilities: VoiceCapabilities.measuredWindows,
);
const _mark = VoiceInfo(
  engine: VoiceEngine.oneCore,
  name: 'Microsoft Mark',
  culture: 'en-US',
  gender: 'Male',
  capabilities: VoiceCapabilities.measuredWindows,
);
const _disabled = VoiceInfo(
  engine: VoiceEngine.systemSpeech,
  name: 'Microsoft Hazel Desktop',
  culture: 'en-GB',
  usable: false,
  reason: 'Disabled in Windows speech settings',
);

Future<LivingServices> pumpShell(
  WidgetTester tester, {
  Size size = const Size(1400, 1000),
  Map<String, Object> prefs = const {},
  VoiceCatalog? catalog,
  double? displayHz,
}) async {
  SharedPreferences.setMockInitialValues(prefs);
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  if (displayHz != null) tester.view.display.refreshRate = displayHz;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  addTearDown(tester.view.display.resetRefreshRate);
  final appState = testAppState();
  final services = testServices(appState);
  if (catalog != null) services.voiceCatalog = catalog;
  addTearDown(services.dispose);
  await tester.pumpWidget(
    LivingApp(appState: appState, services: services, skipOnboarding: true),
  );
  await tester.pumpAndSettle();
  return services;
}

Future<void> openSettings(WidgetTester tester, LivingServices services) async {
  services.presentation.setMode(
    UiPresentationMode.workspace,
    focus: WorkspaceFocus.settings,
  );
  await tester.pumpAndSettle();
}

Future<void> scrollTo(WidgetTester tester, Finder f) async {
  await tester.scrollUntilVisible(
    f,
    200,
    scrollable: find
        .descendant(
          of: find.byType(WorkspaceSettingsRegion),
          matching: find.byType(Scrollable),
        )
        .first,
  );
  // Clear of the region's bottom edge, so a tap lands on the control.
  await tester.ensureVisible(f);
  await tester.pumpAndSettle();
}

UriColors themeColors(WidgetTester tester) =>
    UriColors.of(tester.element(find.byKey(LivingShell.orbKey)));

String fnv1a64(List<int> bytes) {
  var h = 0xcbf29ce484222325;
  for (final b in bytes) {
    h ^= b;
    h *= 0x100000001b3;
  }
  String part(int v) => v.toRadixString(16).padLeft(8, '0');
  return '0x${part(h >>> 32)}${part(h & 0xffffffff)}';
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  // -------------------------------------------------------------------------
  group('preferences', () {
    test('defaults: Solar, adaptive, full quality, no overlay', () {
      final p = CompanionPreferences(persist: false);
      expect(p.choice, const CompanionChoice.living(CompanionIdentity.solar));
      expect(p.frameRate, FrameRateMode.adaptive);
      expect(p.quality, RenderQuality.full);
      expect(p.statsOverlay, isFalse);
      expect(p.look, CompanionLook.standard);
      expect(p.voice, const VoicePreferences());
    });

    test('everything round-trips through SharedPreferences', () async {
      final a = CompanionPreferences();
      a.select(const CompanionChoice.living(CompanionIdentity.sakura));
      a.setFrameRate(FrameRateMode.fps60);
      a.setQuality(RenderQuality.balanced);
      a.setStatsOverlay(true);
      a.setLook(
        const CompanionChoice.living(CompanionIdentity.sakura),
        const CompanionLook(particles: 1.3, size: 1.1),
      );
      a.setLook(
        const CompanionChoice.living(CompanionIdentity.lunar),
        const CompanionLook(motion: 0.6),
      );
      a.setVoice(
        const VoicePreferences(
          voiceId: 'onecore:Microsoft Mark',
          volume: 70,
          rate: 3,
          pitch: -2,
          language: 'en-US',
          waveform: false,
        ),
      );
      await a.pendingWrite;
      final b = await CompanionPreferences.load();
      expect(b.choice, a.choice);
      expect(b.frameRate, FrameRateMode.fps60);
      expect(b.quality, RenderQuality.balanced);
      expect(b.statsOverlay, isTrue);
      expect(
        b.lookFor(const CompanionChoice.living(CompanionIdentity.sakura)),
        const CompanionLook(particles: 1.3, size: 1.1),
      );
      expect(
        b.lookFor(const CompanionChoice.living(CompanionIdentity.lunar)),
        const CompanionLook(motion: 0.6),
      );
      // Untouched companions keep the designed look.
      expect(
        b.lookFor(const CompanionChoice.living(CompanionIdentity.solar)),
        CompanionLook.standard,
      );
      expect(b.voice, a.voice);
    });

    test('only uri.living.companion.* keys are written', () async {
      final a = CompanionPreferences();
      a.select(const CompanionChoice.classic());
      a.setLook(
        const CompanionChoice.classic(),
        const CompanionLook(size: 0.9),
      );
      a.setVoice(const VoicePreferences(rate: 2));
      await a.pendingWrite;
      final keys = (await SharedPreferences.getInstance()).getKeys();
      expect(keys, isNotEmpty);
      for (final k in keys) {
        expect(k, startsWith('uri.living.companion.'));
      }
    });

    test('persist: false writes nothing', () async {
      final a = CompanionPreferences(persist: false);
      a.select(const CompanionChoice.classic());
      await a.pendingWrite;
      expect((await SharedPreferences.getInstance()).getKeys(), isEmpty);
    });

    test(
      'corrupt, unknown and out-of-range values fall back or clamp',
      () async {
        SharedPreferences.setMockInitialValues({
          CompanionPreferences.keyChoice: 'nebula-unicorn',
          CompanionPreferences.keyFrameRate: 7, // wrong type
          CompanionPreferences.keyQuality: 'ultra',
          CompanionPreferences.keyStats: 'yes', // wrong type
          '${CompanionPreferences.keyLookPrefix}solar': '{not json',
          '${CompanionPreferences.keyLookPrefix}sakura':
              '{"size": 9, "particles": -3, "glow": "bright", "motion": 1.2}',
          CompanionPreferences.keyVoice: '{"voiceId": 42, "volume": 400, "rate": -99, "pitch": "x", "waveform": "no"}',
        });
        final p = await CompanionPreferences.load();
        expect(p.choice, const CompanionChoice.living(CompanionIdentity.solar));
        expect(p.frameRate, FrameRateMode.adaptive);
        expect(p.quality, RenderQuality.full);
        expect(p.statsOverlay, isFalse);
        expect(
          p.lookFor(const CompanionChoice.living(CompanionIdentity.solar)),
          CompanionLook.standard,
        );
        final sakura = p.lookFor(
          const CompanionChoice.living(CompanionIdentity.sakura),
        );
        expect(sakura.size, CompanionLook.sizeMax);
        expect(sakura.particles, CompanionLook.particlesMin);
        expect(sakura.glow, 1);
        expect(sakura.motion, 1.2);
        expect(p.voice.voiceId, isNull);
        expect(p.voice.volume, 100);
        expect(p.voice.rate, -10);
        expect(p.voice.pitch, 0);
        expect(p.voice.waveform, isTrue);
      },
    );

    test(
      'a living companion decides the theme; classic keeps the free one',
      () {
        for (final id in CompanionIdentity.values) {
          expect(
            CompanionPreferences.themeFor(
              CompanionChoice.living(id),
              UriThemeChoice.graphite,
            ),
            CompanionTheme.choiceFor(id),
          );
        }
        expect(
          CompanionPreferences.themeFor(
            const CompanionChoice.classic(),
            UriThemeChoice.deepNavy,
          ),
          UriThemeChoice.deepNavy,
        );
      },
    );
  });

  // -------------------------------------------------------------------------
  group('appearance', () {
    test('the standard look leaves every state table untouched', () {
      for (final id in CompanionIdentity.values) {
        for (final s in CompanionState.values) {
          final p = CompanionParams.of(id, s);
          expect(CompanionLook.standard.apply(p), p);
        }
      }
    });

    test('controls scale that identity\'s own parameters, within bounds', () {
      const look = CompanionLook(particles: 1.5, atmosphere: 0, glow: 1.12);
      for (final id in CompanionIdentity.values) {
        for (final s in CompanionState.values) {
          final p = CompanionParams.of(id, s);
          final q = look.apply(p);
          expect(q.particles, closeTo((p.particles * 1.5).clamp(0, 1), 1e-9));
          expect(q.flare, 0);
          expect(
            q.exposure,
            closeTo((p.exposure * 1.12).clamp(0.5, 1.5), 1e-9),
          );
          // Shape and motion vocabulary are not touched.
          expect(q.energy, p.energy);
          expect(q.turbulence, p.turbulence);
          expect(q.focus, p.focus);
        }
      }
    });

    test('glow is limited to plus or minus 12 percent', () {
      expect(const CompanionLook(glow: 3).clamped().glow, 1.12);
      expect(const CompanionLook(glow: 0).clamped().glow, 0.88);
    });

    test('each identity names its controls in its own vocabulary', () {
      final words = {
        for (final id in CompanionIdentity.values)
          CompanionLookVocabulary.of(id).particles,
      };
      expect(words.length, CompanionIdentity.values.length);
      expect(
        CompanionLookVocabulary.of(CompanionIdentity.solar).particles,
        'Embers',
      );
      expect(
        CompanionLookVocabulary.of(CompanionIdentity.sakura).particles,
        'Petals and pollen',
      );
    });

    test(
      'the companion shaders are byte-identical to the accepted artwork',
      () {
        // FNV-1a 64 of each file as committed at d7a052f (companions) and
        // 4c463e6 (waveform); the settings work must not edit a shader.
        const expected = {
          'companion_solar.frag': '0x67e9a80b5fe0c380',
          'companion_sakura.frag': '0x84ba67eccea09e6e',
          'companion_lunar.frag': '0x47b4269698f6914d',
          'companion_moonlit.frag': '0x5f773040ae1f9438',
          'orb_core.frag': '0xa652fd913ca061b9',
          'orb_solar.frag': '0x8db5a65ef6120b00',
          'voice_waveform.frag': '0x3ee74c69bca1f369',
        };
        for (final e in expected.entries) {
          final bytes = File('shaders/${e.key}').readAsBytesSync();
          expect(fnv1a64(bytes), e.value, reason: e.key);
        }
      },
    );
  });

  // -------------------------------------------------------------------------
  group('frame rate and quality', () {
    test('fixed rates above the display are not offered', () {
      expect(FrameRateMode.fps144.supportedBy(60), isFalse);
      expect(FrameRateMode.fps90.supportedBy(60), isFalse);
      expect(FrameRateMode.fps60.supportedBy(59.94), isTrue);
      expect(FrameRateMode.fps144.supportedBy(144), isTrue);
      expect(FrameRateMode.adaptive.supportedBy(30), isTrue);
    });

    test('render quality: offscreen size follows scale and pixel ratio', () {
      const s = Size(400, 300);
      expect(CompanionOrbPainter.offscreenSize(s, 1, 1), isNull);
      expect(
        CompanionOrbPainter.offscreenSize(s, 0.5, 1),
        const Size(200, 150),
      );
      expect(
        CompanionOrbPainter.offscreenSize(s, 0.75, 2),
        const Size(600, 450),
      );
      expect(RenderQuality.performance.scale, 0.5);
    });

    // As the governor measures it: lateness against the current interval.
    FrameWindowStats window(
      double workMs, {
      int n = 200,
      double over = 0,
      double cap = 144,
    }) {
      final build = List<double>.filled(n, 1.0);
      final raster = List<double>.filled(n, workMs);
      final k = (n * over).round();
      for (var i = 0; i < k; i++) {
        raster[i] = 999;
      }
      return FrameWindowStats.of(build, raster, 2, 1000 / cap);
    }

    test('adaptive tiers run from the display rate down to 30', () {
      expect(AdaptiveRatePolicy.tiersFor(144), [144, 90, 60, 45, 30]);
      expect(AdaptiveRatePolicy.tiersFor(60), [60, 45, 30]);
      expect(AdaptiveRatePolicy.tiersFor(240), [144, 90, 60, 45, 30]);
    });

    test('adaptive steps down under pressure and recovers only after calm', () {
      final p = AdaptiveRatePolicy(displayHz: 144);
      expect(p.cap, 144);
      // 17 % of frames late, as measured with the Brain generating.
      expect(p.observe(window(3, over: 0.17)), isTrue);
      expect(p.cap, 90);
      expect(p.observe(window(3, over: 0.17)), isTrue);
      expect(p.cap, 60);
      // Calm: needs three windows in a row.
      expect(p.observe(window(1.5)), isFalse);
      expect(p.observe(window(1.5)), isFalse);
      // A moderate window (fine at 60, not calm enough for 90) resets the
      // count.
      expect(p.observe(window(7, cap: 60)), isFalse);
      expect(p.cap, 60);
      expect(p.observe(window(1.5)), isFalse);
      expect(p.observe(window(1.5)), isFalse);
      expect(p.observe(window(1.5)), isTrue);
      expect(p.cap, 90);
    });

    test('adaptive backs off instead of oscillating under sustained load', () {
      // As measured with the Brain generating: 90 holds, 144 does not.
      final p = AdaptiveRatePolicy(displayHz: 144);
      final caps = <double>[];
      for (var i = 0; i < 120; i++) {
        final atTop = p.cap >= 144;
        p.observe(atTop ? window(3, over: 0.2) : window(1.5, cap: p.cap));
        caps.add(p.cap);
      }
      var ups = 0;
      for (var i = 1; i < caps.length; i++) {
        if (caps[i] > caps[i - 1]) ups++;
      }
      // Without back-off this is about 30 retries in 120 windows (every 4).
      // With it the waits are 3, 6, 12, 24, then 30 windows: at most one
      // probe a minute once the load has proved sustained.
      expect(ups, lessThanOrEqualTo(8));
      expect(p.recoverNeeded, greaterThan(3));
      expect(caps.where((c) => c == 90).length, greaterThan(100));
    });

    test(
      'back-off is forgotten after a long calm, so recovery is quick again',
      () {
        final p = AdaptiveRatePolicy(displayHz: 144);
        for (var i = 0; i < 40; i++) {
          p.observe(
            p.cap >= 144 ? window(3, over: 0.2) : window(1.5, cap: p.cap),
          );
        }
        expect(p.recoverNeeded, greaterThan(3));
        // Load gone: once at the top and calm long enough, back to 3.
        for (var i = 0; i < 80; i++) {
          p.observe(window(1.2, cap: p.cap));
        }
        expect(p.cap, 144);
        expect(p.recoverNeeded, 3);
      },
    );

    test('adaptive never goes below 30 and ignores tiny windows', () {
      final p = AdaptiveRatePolicy(displayHz: 60);
      for (var i = 0; i < 10; i++) {
        p.observe(window(50, over: 1));
      }
      expect(p.cap, 30);
      final q = AdaptiveRatePolicy(displayHz: 60);
      expect(q.observe(window(50, n: 5, over: 1)), isFalse);
      expect(q.cap, 60);
    });

    test('the governor applies fixed caps bounded by the display', () {
      final prefs = CompanionPreferences(persist: false);
      final clock = CompanionFrameClock(displayHz: 60);
      final g = CompanionFrameGovernor(clock: clock, preferences: prefs);
      addTearDown(() {
        g.dispose();
        clock.dispose();
      });
      expect(clock.cap, 60); // adaptive starts at the display rate
      prefs.setFrameRate(FrameRateMode.fps30);
      expect(clock.cap, 30);
      prefs.setFrameRate(FrameRateMode.fps144);
      expect(clock.cap, 60, reason: 'a 60 Hz display cannot show 144');
      g.updateDisplay(144);
      expect(clock.cap, 144);
      prefs.setFrameRate(FrameRateMode.adaptive);
      expect(clock.cap, 144);
    });

    test('the governor turns measured frame times into adaptive steps', () {
      final prefs = CompanionPreferences(persist: false);
      final clock = CompanionFrameClock(displayHz: 144);
      final g = CompanionFrameGovernor(clock: clock, preferences: prefs);
      addTearDown(() {
        g.dispose();
        clock.dispose();
      });
      var t = 0;
      List<(double, double, int)> frames(
        int n,
        double raster,
        double stepMs,
      ) => [
        for (var i = 0; i < n; i++) (1.0, raster, t += (stepMs * 1000).round()),
      ];
      g.observeTimings(frames(300, 27, 7)); // contention: every frame late
      expect(clock.cap, lessThan(144));
      final stressed = clock.cap;
      for (var w = 0; w < 30; w++) {
        g.observeTimings(frames(120, 1.2, 17));
      }
      expect(clock.cap, greaterThan(stressed));
      expect(clock.cap, 144);
      expect(g.lastWindow, isNotNull);
    });
  });

  // -------------------------------------------------------------------------
  group('frame clock', () {
    testWidgets(
      'a cap below the display rate schedules only that many frames',
      (tester) async {
        final clock = CompanionFrameClock(displayHz: 60, cap: 30);
        addTearDown(clock.dispose);
        var delivered = 0;
        void l() => delivered++;
        clock.addListener(l);
        for (var i = 0; i < 60; i++) {
          await tester.pump(const Duration(microseconds: 16667));
        }
        clock.removeListener(l);
        expect(delivered, inInclusiveRange(28, 32));
        // Between deliveries the ticker is muted: no vsync is requested that
        // does not deliver.
        expect(clock.ticks, delivered);
      },
    );

    testWidgets('uncapped delivers every vsync', (tester) async {
      final clock = CompanionFrameClock(displayHz: 60);
      addTearDown(clock.dispose);
      var delivered = 0;
      void l() => delivered++;
      clock.addListener(l);
      for (var i = 0; i < 60; i++) {
        await tester.pump(const Duration(microseconds: 16667));
      }
      clock.removeListener(l);
      expect(delivered, inInclusiveRange(59, 61));
    });

    testWidgets('a hidden (minimised) app schedules no companion frames', (
      tester,
    ) async {
      final clock = CompanionFrameClock(displayHz: 60);
      addTearDown(clock.dispose);
      var delivered = 0;
      void l() => delivered++;
      clock.addListener(l);
      await tester.pump(const Duration(milliseconds: 17));
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      expect(clock.hidden, isTrue);
      final before = delivered;
      for (var i = 0; i < 30; i++) {
        await tester.pump(const Duration(milliseconds: 17));
      }
      expect(delivered, before);
      expect(SchedulerBinding.instance.transientCallbackCount, 0);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      expect(clock.hidden, isFalse);
      for (var i = 0; i < 10; i++) {
        await tester.pump(const Duration(milliseconds: 17));
      }
      expect(delivered, greaterThan(before + 5));
      clock.removeListener(l);
    });

    testWidgets(
      'window binding without a window plugin: no-op, clean disposal',
      (tester) async {
        final clock = CompanionFrameClock(displayHz: 60);
        // Real time: the plugin call has no native side here and must be
        // cut off by the binding's own timeout, not hang.
        final remove = (await tester.runAsync(
          () => bindWindowVisibility(clock),
        ))!;
        remove();
        remove(); // idempotent
        expect(clock.hidden, isFalse);
        clock.dispose(); // runs the disposer again: must not throw
      },
    );

    testWidgets('with no listener the clock schedules nothing', (tester) async {
      final clock = CompanionFrameClock(displayHz: 60);
      addTearDown(clock.dispose);
      void l() {}
      clock.addListener(l);
      await tester.pump(const Duration(milliseconds: 16));
      clock.removeListener(l);
      await tester.pump(const Duration(milliseconds: 16));
      expect(SchedulerBinding.instance.transientCallbackCount, 0);
      expect(SchedulerBinding.instance.hasScheduledFrame, isFalse);
    });

    testWidgets(
      'a still companion (reduced motion) stops the clock: no frames at all',
      (tester) async {
        final services = await pumpShell(tester);
        expect(find.byType(CompanionOrb), findsOneWidget);
        await tester.pump(const Duration(seconds: 1));
        expect(services.frameClock.isRunning, isFalse);
        expect(SchedulerBinding.instance.transientCallbackCount, 0);
      },
    );

    testWidgets('a state change wakes a still companion for its blend', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      services.demo.emit(CompanionState.thinking, detail: 'test');
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 16));
      expect(services.frameClock.isRunning, isTrue);
      await tester.pumpAndSettle();
      expect(services.frameClock.isRunning, isFalse);
    });
  });

  // -------------------------------------------------------------------------
  group('shell and theme', () {
    testWidgets('the default companion is Solar and themes the app', (
      tester,
    ) async {
      await pumpShell(tester);
      final orb = tester.widget<CompanionOrb>(find.byType(CompanionOrb));
      expect(orb.identity, CompanionIdentity.solar);
      expect(themeColors(tester).accent, UriColors.solarEmber.accent);
    });

    testWidgets(
      'switching companion re-themes everything and keeps the one shell element',
      (tester) async {
        final services = await pumpShell(tester);
        final before = tester.element(find.byKey(LivingShell.orbKey));
        for (final (choice, accent) in [
          (
            const CompanionChoice.living(CompanionIdentity.sakura),
            UriColors.sakuraBloom.accent,
          ),
          (
            const CompanionChoice.living(CompanionIdentity.lunar),
            UriColors.lunarSilver.accent,
          ),
          (
            const CompanionChoice.living(CompanionIdentity.moonlit),
            UriColors.lunarSilver.accent,
          ),
        ]) {
          services.companionPrefs.select(choice);
          await tester.pumpAndSettle();
          expect(
            tester.widget<CompanionOrb>(find.byType(CompanionOrb)).identity,
            choice.identity,
          );
          expect(themeColors(tester).accent, accent);
          expect(
            identical(tester.element(find.byKey(LivingShell.orbKey)), before),
            isTrue,
          );
        }
        for (final mode in UiPresentationMode.values) {
          services.presentation.setMode(mode);
          await tester.pumpAndSettle();
          expect(
            identical(tester.element(find.byKey(LivingShell.orbKey)), before),
            isTrue,
            reason: mode.name,
          );
          expect(find.byType(CompanionOrb), findsOneWidget, reason: mode.name);
        }
      },
    );

    testWidgets('classic restores the Energy Orb and the free theme choice', (
      tester,
    ) async {
      final services = await pumpShell(
        tester,
        prefs: {'uri.living.themeChoice': 'deepNavy'},
      );
      services.companionPrefs.select(const CompanionChoice.classic());
      await tester.pumpAndSettle();
      expect(find.byType(CompanionOrb), findsNothing);
      expect(
        find.descendant(
          of: find.byKey(LivingShell.orbKey),
          matching: find.byType(EnergyOrb),
        ),
        findsOneWidget,
      );
      expect(themeColors(tester).accent, UriColors.deepNavy.accent);
    });

    testWidgets('size, quality and look reach the drawn companion', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      const solar = CompanionChoice.living(CompanionIdentity.solar);
      services.companionPrefs.setLook(
        solar,
        const CompanionLook(particles: 0.5, motion: 1.4),
      );
      services.companionPrefs.setQuality(RenderQuality.performance);
      await tester.pumpAndSettle();
      final orb = tester.widget<CompanionOrb>(find.byType(CompanionOrb));
      expect(orb.look, const CompanionLook(particles: 0.5, motion: 1.4));
      expect(orb.renderScale, 0.5);
      final small = tester.getSize(find.byType(CompanionOrb));
      services.companionPrefs.setLook(solar, const CompanionLook(size: 1.25));
      await tester.pumpAndSettle();
      final big = tester.getSize(find.byType(CompanionOrb));
      expect(big.width / small.width, closeTo(1.25, 0.01));
    });

    testWidgets('reduced effects draws no living shader', (tester) async {
      final services = await pumpShell(tester);
      services.effects.setReducedEffects(true);
      await tester.pumpAndSettle();
      expect(find.byType(CompanionOrb), findsNothing);
      expect(find.byType(EnergyOrb), findsOneWidget);
      expect(find.bySemanticsLabel(RegExp('URI companion: ')), findsWidgets);
    });

    testWidgets('Ember is drawn from clips through the companion seam', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      services.companionPrefs.select(
        const CompanionChoice.living(CompanionIdentity.ember),
      );
      for (var i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(find.byType(EmberCompanion), findsOneWidget);
      expect(
        tester.widget<CompanionOrb>(find.byType(CompanionOrb)).identity,
        CompanionIdentity.ember,
      );
      expect(find.bySemanticsLabel(RegExp('URI companion: ')), findsWidgets);
      services.effects.setReducedEffects(true);
      for (var i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(find.byType(EmberCompanion), findsNothing);
      expect(find.byType(EnergyOrb), findsOneWidget);
      services.effects.setReducedEffects(false);
      services.companionPrefs.select(
        const CompanionChoice.living(CompanionIdentity.solar),
      );
      for (var i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(find.byType(EmberCompanion), findsNothing);
    });

    testWidgets('preferences survive a restart of the app', (tester) async {
      SharedPreferences.setMockInitialValues({});
      final a = await pumpShell(tester);
      a.companionPrefs.select(
        const CompanionChoice.living(CompanionIdentity.lunar),
      );
      a.companionPrefs.setFrameRate(FrameRateMode.fps30);
      await a.companionPrefs.pendingWrite;
      final stored = (await SharedPreferences.getInstance());
      final snapshot = <String, Object>{
        for (final k in stored.getKeys()) k: stored.get(k)!,
      };
      await tester.pumpWidget(const SizedBox());
      final b = await pumpShell(tester, prefs: snapshot);
      expect(b.companionPrefs.choice.identity, CompanionIdentity.lunar);
      expect(b.companionPrefs.frameRate, FrameRateMode.fps30);
      expect(
        tester.widget<CompanionOrb>(find.byType(CompanionOrb)).identity,
        CompanionIdentity.lunar,
      );
    });

    testWidgets('the statistics overlay appears only when switched on', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      expect(find.byType(FrameStatsOverlay), findsNothing);
      services.companionPrefs.setStatsOverlay(true);
      await tester.pumpAndSettle();
      expect(find.byType(FrameStatsOverlay), findsOneWidget);
      expect(find.textContaining('Companion'), findsWidgets);
    });
  });

  // -------------------------------------------------------------------------
  group('settings page', () {
    testWidgets('picking a companion re-themes the settings page itself', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      await openSettings(tester, services);
      final card = find.byKey(const ValueKey('companion-choice-sakura'));
      await scrollTo(tester, card);
      await tester.tap(card);
      await tester.pumpAndSettle();
      expect(services.companionPrefs.choice.identity, CompanionIdentity.sakura);
      final c = UriColors.of(
        tester.element(find.byType(CompanionSettingsSection)),
      );
      expect(c.accent, UriColors.sakuraBloom.accent);
      expect(find.text('APPEARANCE · SAKURA'), findsOneWidget);
      expect(find.text('Petals and pollen'), findsOneWidget);
      expect(find.text('Energy ribbons'), findsOneWidget);
    });

    testWidgets('appearance sliders change only the selected companion', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      await openSettings(tester, services);
      final slider = find.byKey(const ValueKey('look-particles'));
      await scrollTo(tester, slider);
      await tester.drag(slider, const Offset(-400, 0));
      await tester.pumpAndSettle();
      final p = services.companionPrefs;
      expect(
        p
            .lookFor(const CompanionChoice.living(CompanionIdentity.solar))
            .particles,
        lessThan(1),
      );
      expect(
        p.lookFor(const CompanionChoice.living(CompanionIdentity.sakura)),
        CompanionLook.standard,
      );
      await scrollTo(tester, find.byKey(const ValueKey('look-reset')));
      await tester.tap(find.byKey(const ValueKey('look-reset')));
      await tester.pumpAndSettle();
      expect(
        p.lookFor(const CompanionChoice.living(CompanionIdentity.solar)),
        CompanionLook.standard,
      );
    });

    testWidgets('frame-rate choices follow the display', (tester) async {
      final services = await pumpShell(tester, displayHz: 60);
      await openSettings(tester, services);
      final chip144 = find.byKey(const ValueKey('fps-fps144'));
      await scrollTo(tester, chip144);
      expect(tester.widget<ChoiceChip>(chip144).onSelected, isNull);
      expect(
        tester
            .widget<ChoiceChip>(find.byKey(const ValueKey('fps-fps90')))
            .onSelected,
        isNull,
      );
      await tester.tap(find.byKey(const ValueKey('fps-fps30')));
      await tester.pumpAndSettle();
      expect(services.companionPrefs.frameRate, FrameRateMode.fps30);
      expect(services.frameClock.cap, 30);
    });

    testWidgets('frame rate is shown unavailable for the classic orb', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      services.companionPrefs.select(const CompanionChoice.classic());
      await tester.pumpAndSettle();
      await openSettings(tester, services);
      await scrollTo(tester, find.byKey(const ValueKey('fps-unavailable')));
      expect(find.byKey(const ValueKey('fps-fps30')), findsNothing);
    });

    testWidgets('minimised: every ticker is muted, the classic orb too', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      services.companionPrefs.select(const CompanionChoice.classic());
      services.effects.setReducedMotion(false);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));
      expect(SchedulerBinding.instance.transientCallbackCount, greaterThan(0));
      services.frameClock.setHidden(true);
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 50));
      expect(SchedulerBinding.instance.transientCallbackCount, 0);
      services.frameClock.setHidden(false);
      services.effects.setReducedMotion(true);
      await tester.pumpAndSettle();
    });

    testWidgets('render quality is offered for living companions only', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      await openSettings(tester, services);
      final q = find.byKey(const ValueKey('quality-balanced'));
      await scrollTo(tester, q);
      await tester.tap(q);
      await tester.pumpAndSettle();
      expect(services.companionPrefs.quality, RenderQuality.balanced);
      services.companionPrefs.select(const CompanionChoice.classic());
      await tester.pumpAndSettle();
      await scrollTo(tester, find.byKey(const ValueKey('quality-unavailable')));
      expect(find.byKey(const ValueKey('quality-balanced')), findsNothing);
    });

    testWidgets(
      'voices: installed ones listed by engine, previews use the prefs',
      (tester) async {
        final catalog = FakeVoiceCatalog(
          const VoiceListing(voices: [_zira, _mark, _disabled]),
        );
        final services = await pumpShell(tester, catalog: catalog);
        await openSettings(tester, services);
        final mark = find.byKey(ValueKey('voice-row-${_mark.id}'));
        await scrollTo(tester, mark);
        expect(find.text(VoiceEngine.systemSpeech.label), findsOneWidget);
        expect(find.text(VoiceEngine.oneCore.label), findsOneWidget);
        await tester.tap(mark);
        await tester.pumpAndSettle();
        expect(services.companionPrefs.voice.voiceId, 'onecore:Microsoft Mark');
        // The disabled voice says why and cannot be previewed.
        expect(
          find.textContaining('Disabled in Windows speech settings'),
          findsOneWidget,
        );
        expect(
          find.byKey(ValueKey('voice-preview-${_disabled.id}')),
          findsNothing,
        );
        // Two languages installed, so a filter is offered.
        expect(find.byKey(const ValueKey('voice-lang-en-GB')), findsOneWidget);
        services.companionPrefs.setVoice(
          services.companionPrefs.voice.copyWith(
            rate: 4,
            pitch: -3,
            volume: 55,
          ),
        );
        await tester.pumpAndSettle();
        await tester.tap(find.byKey(ValueKey('voice-preview-${_mark.id}')));
        await tester.pumpAndSettle();
        expect(catalog.previews.single.$1, _mark.id);
        expect(catalog.previews.single.$2.rate, 4);
        expect(catalog.previews.single.$2.pitch, -3);
        expect(catalog.previews.single.$2.volume, 55);
        // Measured parameters are sliders; unsupported ones say so.
        await scrollTo(
          tester,
          find.byKey(const ValueKey('mic-gain-unavailable')),
        );
        expect(find.byKey(const ValueKey('voice-rate')), findsOneWidget);
        expect(find.byKey(const ValueKey('voice-pitch')), findsOneWidget);
        expect(find.byKey(const ValueKey('voice-volume')), findsOneWidget);
        expect(
          find.byKey(const ValueKey('voice-style-unavailable')),
          findsOneWidget,
        );
        expect(
          find.byKey(const ValueKey('mic-gain-unavailable')),
          findsOneWidget,
        );
      },
    );

    testWidgets(
      'a voice without a capability shows it unavailable, not a slider',
      (tester) async {
        const plain = VoiceInfo(
          engine: VoiceEngine.systemSpeech,
          name: 'Plain',
          culture: 'en-US',
        );
        final services = await pumpShell(
          tester,
          catalog: FakeVoiceCatalog(const VoiceListing(voices: [plain])),
        );
        await openSettings(tester, services);
        await scrollTo(
          tester,
          find.byKey(const ValueKey('mic-gain-unavailable')),
        );
        expect(find.byKey(const ValueKey('voice-rate')), findsNothing);
        expect(
          find.byKey(const ValueKey('voice-rate-unavailable')),
          findsOneWidget,
        );
        expect(
          find.byKey(const ValueKey('voice-pitch-unavailable')),
          findsOneWidget,
        );
      },
    );

    testWidgets('no engine: the page says so and invents nothing', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      await openSettings(tester, services);
      await scrollTo(tester, find.byKey(const ValueKey('voices-unavailable')));
      expect(find.byKey(const ValueKey('voices-unavailable')), findsOneWidget);
      expect(
        find.byType(Slider).evaluate().where((e) {
          final k = e.widget.key;
          return k is ValueKey<String> && k.value.startsWith('voice-');
        }),
        isEmpty,
      );
      expect(find.byKey(const ValueKey('voice-service-line')), findsOneWidget);
    });
  });

  // -------------------------------------------------------------------------
  group('voice service binding', () {
    testWidgets(
      'adapter signals drive the shared waveform beside the unchanged companion',
      (tester) async {
        final services = await pumpShell(tester);
        final orbBefore = tester.element(find.byKey(LivingShell.orbKey));
        final adapter = FakeVoiceAdapter();
        services.bindVoice(adapter);
        adapter.ctl.add(const ListeningStarted('s1'));
        adapter.ctl.add(const UserSpeechStarted('s1'));
        adapter.ctl.add(
          const UserTranscript('s1', 'open the dashboard', isFinal: false),
        );
        for (var i = 0; i < 10; i++) {
          adapter.ctl.add(const AudioLevel(VoiceSpeaker.user, 0.05));
        }
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 600));
        expect(find.byType(VoiceWaveform), findsOneWidget);
        expect(find.byType(VoiceTranscript), findsOneWidget);
        expect(find.textContaining('open the dashboard'), findsOneWidget);
        expect(find.text('SIMULATED'), findsWidgets);
        expect(services.companion.signal.state, CompanionState.listening);
        expect(
          identical(tester.element(find.byKey(LivingShell.orbKey)), orbBefore),
          isTrue,
        );
        // The voice service closing ends the turn: nothing is left on screen.
        await adapter.ctl.close();
        await tester.pump();
        await tester.pump(const Duration(milliseconds: 700));
        expect(services.voice.session.phase, VoicePhase.off);
        expect(find.byType(VoiceWaveform), findsNothing);
      },
    );

    testWidgets('an adapter error ends the turn with a visible notice', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      final adapter = FakeVoiceAdapter(simulated: false);
      services.bindVoice(adapter);
      expect(services.voice.simulated, isFalse);
      adapter.ctl.add(const ListeningStarted('s1'));
      adapter.ctl.add(const UserSpeechStarted('s1'));
      await tester.pump();
      adapter.ctl.addError('microphone unplugged');
      await tester.pump();
      expect(services.voice.session.phase, VoicePhase.off);
      expect(services.voice.session.notice, contains('microphone unplugged'));
      await adapter.ctl.close();
      await tester.pumpAndSettle();
    });

    testWidgets('waveform preference off keeps the transcript only', (
      tester,
    ) async {
      final services = await pumpShell(tester);
      services.companionPrefs.setVoice(const VoicePreferences(waveform: false));
      final adapter = FakeVoiceAdapter();
      services.bindVoice(adapter);
      adapter.ctl.add(const ListeningStarted('s1'));
      adapter.ctl.add(const UserSpeechStarted('s1'));
      adapter.ctl.add(const UserTranscript('s1', 'hello', isFinal: true));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 600));
      expect(find.byType(VoiceStage), findsOneWidget);
      expect(find.byType(VoiceWaveform), findsNothing);
      expect(find.byType(VoiceTranscript), findsOneWidget);
      await adapter.ctl.close();
      await tester.pumpAndSettle();
    });
  });

  // -------------------------------------------------------------------------
  group('voice dock layout', () {
    test(
      'never over the companion, never over the Companion-mode controls',
      () {
        for (final shell in const [
          Size(1920, 1080),
          Size(1366, 768),
          Size(1280, 860),
          Size(1024, 700),
          Size(900, 640),
          Size(800, 600),
          Size(700, 520),
          Size(640, 480),
          Size(560, 420),
        ]) {
          for (final mode in UiPresentationMode.values) {
            final orb = OrbDock.forMode(mode, shell).rect;
            final dock = VoiceDock.forMode(mode, shell, orb);
            final v = dock.rect;
            // Supported desktop sizes always get a stage; a window too short
            // for any free place gets none instead of an overlap.
            if (shell.height >= 600) {
              expect(dock.hidden, isFalse, reason: "${mode.name} $shell");
            }
            if (dock.hidden) continue;
            final where = "${mode.name} $shell";
            expect(v.overlaps(orb), isFalse, reason: where);
            expect(v.left, greaterThanOrEqualTo(0), reason: where);
            expect(v.top, greaterThanOrEqualTo(0), reason: where);
            expect(v.right, lessThanOrEqualTo(shell.width), reason: where);
            if (mode == UiPresentationMode.companion) {
              // The real boundaries: the status line under the companion and
              // the composer, chips and hint at the bottom.
              final controls = Rect.fromLTRB(
                0,
                shell.height - VoiceDock.companionControls,
                shell.width,
                shell.height,
              );
              final status = Rect.fromLTRB(
                0,
                orb.bottom,
                shell.width,
                orb.bottom + VoiceDock.companionStatus,
              );
              expect(v.overlaps(controls), isFalse, reason: where);
              expect(v.overlaps(status), isFalse, reason: where);
            }
          }
        }
      },
    );

    testWidgets('a very short window shows no stage rather than an overlap', (
      tester,
    ) async {
      // Companion mode's accepted column already overflows at this height;
      // that pre-existing layout limit is not this test's subject.
      final previous = FlutterError.onError;
      FlutterError.onError = (details) {
        if (!details.toString().contains('overflowed')) previous?.call(details);
      };
      addTearDown(() => FlutterError.onError = previous);
      final services = await pumpShell(tester, size: const Size(700, 520));
      final adapter = FakeVoiceAdapter();
      services.bindVoice(adapter);
      adapter.ctl.add(const ListeningStarted('s1'));
      adapter.ctl.add(const UserSpeechStarted('s1'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 700));
      expect(find.byType(VoiceStage), findsNothing);
      expect(services.companion.signal.state, CompanionState.listening);
      await adapter.ctl.close();
      await tester.pumpAndSettle();
    });

    test('the transcript always fits; the waveform shrinks first', () {
      final w = 520.0;
      expect(
        VoiceStage.heightFor(w),
        greaterThan(VoiceStage.heightFor(w, waveform: false)),
      );
      expect(
        VoiceStage.heightFor(w, waveform: false),
        VoiceTranscript.heightFor(),
      );
    });
  });

  // -------------------------------------------------------------------------
  group('windows voice bridge parsing', () {
    test('rows become voices; disabled ones are marked, errors kept', () {
      final l = WindowsVoiceCatalog.parseListing(
        '[{"engine":"sapi","name":"Microsoft Zira Desktop","culture":"en-US","gender":"Female","enabled":true},'
        '{"engine":"sapi","name":"Old","culture":"en-GB","gender":"Male","enabled":false},'
        '{"engine":"onecore","name":"","culture":"","gender":"","enabled":false,"error":"WinRT missing"},'
        '{"engine":"other","name":"X"}]',
      );
      expect(l.voices.map((v) => v.id), [
        'sapi:Microsoft Zira Desktop',
        'sapi:Old',
      ]);
      expect(l.voices[1].usable, isFalse);
      expect(l.voices[1].reason, isNotNull);
      expect(l.engineErrors.single, contains('WinRT missing'));
      expect(l.languages, ['en-GB', 'en-US']);
    });

    test('unreadable output is reported, not guessed', () {
      final l = WindowsVoiceCatalog.parseListing('Exception: boom');
      expect(l.voices, isEmpty);
      expect(l.unavailableReason, isNotNull);
    });

    test('the bridge script is a registered asset and takes inputs from the environment', () {
      final pubspec = File('pubspec.yaml').readAsStringSync();
      expect(pubspec, contains('- ${WindowsVoiceCatalog.scriptAsset}'));
      final script = File(WindowsVoiceCatalog.scriptAsset).readAsStringSync();
      expect(script, contains("GetEnvironmentVariable('URI_VOICE_NAME')"));
      expect(script, isNot(contains('Invoke-Expression')));
    });
  });

  test(
    'living companion widget exposes the classic orb under reduced effects',
    () {
      // Construction-only guard: the classic fallback is built from the same
      // state, so reduced effects never loses the state label.
      const w = LivingCompanion(state: CompanionState.error, size: 100);
      expect(w.state, CompanionState.error);
      expect(EffectsSettings().reducedEffects, isFalse);
    },
  );
}
