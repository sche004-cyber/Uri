import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/living/a2ui/companion_actions.dart';
import 'package:uri_ui/living/a2ui/a2ui_hub.dart';
import 'package:uri_ui/living/voice/voice_session.dart';
import 'package:uri_ui/living/companion/companion_design.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/living_companion.dart';
import 'package:uri_ui/living/companion/effects_settings.dart';
import 'package:uri_ui/living/companion/energy_orb.dart';
import 'package:uri_ui/living/contracts/readiness_report.dart';
import 'package:uri_ui/living/contracts/work_items.dart';
import 'package:uri_ui/living/living_app.dart';
import 'package:uri_ui/living/living_scope.dart';
import 'package:uri_ui/living/presentation/living_shell.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';
import 'package:uri_ui/living/screens/companion_mode_view.dart';
import 'package:uri_ui/living/screens/settings/companion_gallery.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/screens/auth/login_screen.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/live_voice_service.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/services/uri_client.dart';
import 'package:uri_ui/theme/uri_theme.dart';

class _CountingClient extends MockUriClient {
  int asks = 0;
  @override
  Future<UriTurn> ask(String message, {String? turnId, Object? modelOverride}) {
    asks++;
    return super.ask(message, turnId: turnId, modelOverride: modelOverride);
  }
}

class _VoiceTransport implements VoiceTransport {
  final controller = StreamController<Map<String, dynamic>>.broadcast();
  final sent = <Map<String, Object?>>[];
  @override
  Stream<Map<String, dynamic>> get events => controller.stream;
  @override
  Future<int> get exitCode => Completer<int>().future;
  @override
  void send(Map<String, Object?> command) => sent.add(command);
  @override
  Future<void> close() async {
    await controller.close();
  }
}

LivingServices v2Services(AppState app, {bool reducedMotion = true}) =>
    LivingServices(
      presentation: UiPresentationController(commandCooldown: Duration.zero),
      companion: CompositeCompanionSource([
        AppStateCompanionSource(app, dataIsMock: true),
      ]),
      work: MockWorkSimulator(seed: false),
      readiness: MockReadinessSource(),
      effects: EffectsSettings(reducedMotion: reducedMotion),
      demo: MockCompanionSource(),
      visualV2: true,
    );
Future<(_CountingClient, AppState, LivingServices)> pumpV2(
  WidgetTester tester, {
  Size size = const Size(440, 680),
}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.resetPhysicalSize);
  addTearDown(tester.view.resetDevicePixelRatio);
  final client = _CountingClient();
  final app = AppState(client);
  final services = v2Services(app);
  addTearDown(services.dispose);
  addTearDown(app.dispose);
  await tester.pumpWidget(
    LivingApp(appState: app, services: services, skipOnboarding: true),
  );
  await tester.pumpAndSettle();
  return (client, app, services);
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  test('every accepted design is represented once with original renderer and theme', () {
    expect(CompanionDesign.installed.length, 11);
    expect(CompanionDesign.installed.map((d) => d.id).toSet().length, 11);
    expect(
      CompanionDesign.installed
          .where((d) => d.classicVariant != null)
          .map((d) => d.classicVariant)
          .toSet(),
      OrbVariant.values.toSet(),
    );
    expect(
      CompanionDesign.installed.every((d) => !d.supportsModelRotation),
      isTrue,
    );
  });
  test('all design/theme combinations preserve renderer identity; original follows', () async {
    final prefs = CompanionPreferences(persist: false);
    addTearDown(prefs.dispose);
    for (final theme in installedInterfaceThemes) {
      await prefs.setInterfaceTheme(theme);
      for (final d in CompanionDesign.installed) {
        d.applyTo(prefs);
        expect(prefs.effectiveTheme(), theme);
        expect(CompanionDesign.active(prefs).id, d.id);
      }
    }
    await prefs.setInterfaceTheme(null);
    for (final d in CompanionDesign.installed) {
      d.applyTo(prefs);
      expect(prefs.effectiveTheme(), d.originalTheme);
    }
  });
  test('restart persistence, legacy Classic migration and unknown reference fallback', () async {
    final prefs = CompanionPreferences();
    addTearDown(prefs.dispose);
    CompanionDesign.installed.last.applyTo(prefs);
    await prefs.setInterfaceTheme(UriThemeChoice.ashLimestone);
    await prefs.pendingWrite;
    final restored = await CompanionPreferences.load(persist: false);
    addTearDown(restored.dispose);
    expect(CompanionDesign.active(restored).id, 'classic-energy');
    expect(restored.effectiveTheme(), UriThemeChoice.ashLimestone);
    await prefs.setInterfaceTheme(null);
    final original = await CompanionPreferences.load(persist: false);
    addTearDown(original.dispose);
    expect(original.interfaceTheme, isNull);
    SharedPreferences.setMockInitialValues({
      CompanionPreferences.keyChoice: 'classic',
      LivingPrefs.themeChoice: 'deepNavy',
    });
    final legacy = await CompanionPreferences.load(persist: false);
    addTearDown(legacy.dispose);
    expect(legacy.interfaceTheme, UriThemeChoice.deepNavy);
    SharedPreferences.setMockInitialValues({
      CompanionPreferences.keyChoice: 'retired',
      CompanionPreferences.keyInterfaceTheme: 'missing',
    });
    final fallback = await CompanionPreferences.load(persist: false);
    addTearDown(fallback.dispose);
    expect(fallback.choice.identity, CompanionIdentity.solar);
    expect(fallback.effectiveTheme(), UriThemeChoice.solarEmber);
  });
  for (final theme in [
    UriThemeChoice.ivoryFoundry,
    UriThemeChoice.snowArchive,
    UriThemeChoice.ashLimestone,
  ]) {
    test('${theme.label}: text, focus and status contrast', () {
      final c = resolveUriColors(theme, Brightness.light);
      double contrast(Color a, Color b) {
        final x = a.computeLuminance(), y = b.computeLuminance();
        return (math.max(x, y) + .05) / (math.min(x, y) + .05);
      }

      for (final bg in [c.canvas, c.surface]) {
        for (final fg in [c.ink, c.inkSoft, c.inkFaint, c.accent]) {
          expect(contrast(fg, bg), greaterThanOrEqualTo(4.5));
        }
        expect(contrast(c.border, bg), greaterThanOrEqualTo(3));
      }
      for (final pair in [
        (c.success, c.successSoft),
        (c.warning, c.warningSoft),
        (c.danger, c.dangerSoft),
      ]) {
        expect(contrast(pair.$1, pair.$2), greaterThanOrEqualTo(4.5));
      }
    });
  }
  testWidgets(
    'single click acknowledges once; detached Chat sends through shared service',
    (tester) async {
      final (client, app, services) = await pumpV2(tester);
      final transport = _VoiceTransport();
      final voice = LiveVoiceService(launch: () async => transport);
      services.attachLiveVoice(voice);
      await voice.ensureStarted();
      voice.status.value = const VoiceServiceStatus(
        state: VoiceServiceState.ready,
      );
      expect(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
        findsNothing,
      );
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pump();
      expect(services.orbPokes.value, 1);
      expect(client.asks, 0);
      expect(transport.sent.where((m) => m['cmd'] == 'speak').length, 1);
      expect(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
        findsOneWidget,
      );
      expect(find.byKey(const ValueKey('living-composer-field')), findsNothing);
      expect(transport.sent.where((m) => m['cmd'] == 'listen_start'), isEmpty);
      await tester.tap(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('living-composer-field')),
        'What is available?',
      );
      await tester.tap(find.byKey(const ValueKey('living-composer-send')));
      await tester.pumpAndSettle();
      expect(client.asks, 1);
      expect(app.conversation, isNotEmpty);
      expect(services.presentation.mode, UiPresentationMode.companion);
      await tester.enterText(
        find.byKey(const ValueKey('living-composer-field')),
        'Retain detached draft',
      );
      await tester.tap(find.byKey(const ValueKey('companion-close-chat')));
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('living-composer-field')), findsNothing);
      expect(app.composerDraft, 'Retain detached draft');
      await tester.tap(
        find.byKey(const ValueKey('a2ui.companion-controls.dashboard')),
      );
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.dashboard);
      expect(app.composerDraft, 'Retain detached draft');
      expect(app.conversation, isNotEmpty);
      await tester.pump(const Duration(seconds: 5));
    },
  );
  testWidgets(
    'Escape closes chat then floating controls without losing draft',
    (tester) async {
      final (client, app, services) = await pumpV2(tester);
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pump();
      await tester.tap(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
      );
      await tester.pumpAndSettle();
      await tester.enterText(
        find.byKey(const ValueKey('living-composer-field')),
        'Keep this draft',
      );
      await tester.sendKeyEvent(LogicalKeyboardKey.escape);
      await tester.pumpAndSettle();
      expect(find.byKey(const ValueKey('living-composer-field')), findsNothing);
      expect(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
        findsOneWidget,
      );
      await tester.sendKeyEvent(LogicalKeyboardKey.escape);
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
        findsNothing,
      );
      expect(app.composerDraft, 'Keep this draft');
      expect(client.asks, 0);
      expect(services.presentation.mode, UiPresentationMode.companion);
      await tester.pump(const Duration(seconds: 5));
    },
  );
  testWidgets(
    'double click suppresses single click and preserves shared draft',
    (tester) async {
      final (client, app, services) = await pumpV2(tester);
      app.setComposerDraft('Retain my draft');
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds: 80));
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pumpAndSettle();
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.dashboard);
      expect(services.orbPokes.value, 0);
      expect(client.asks, 0);
      expect(app.composerDraft, 'Retain my draft');
      expect(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
        findsNothing,
      );
    },
  );
  testWidgets(
    'gallery Cancel isolates identity, theme and active conversation; Apply persists',
    (tester) async {
      final (_, app, services) = await pumpV2(
        tester,
        size: const Size(1440, 1000),
      );
      services.presentation.setMode(
        UiPresentationMode.workspace,
        focus: WorkspaceFocus.settings,
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Companion Design'));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('gallery-live-renderer')),
        findsOneWidget,
      );
      await tester.tap(find.byKey(const ValueKey('gallery-design-sakura')));
      await tester.pumpAndSettle();
      expect(services.companionPrefs.choice.identity, CompanionIdentity.solar);
      expect(app.conversation, isEmpty);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
      expect(services.companionPrefs.choice.identity, CompanionIdentity.solar);
      await tester.tap(find.text('Companion Design'));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('gallery-design-lunar')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const ValueKey('gallery-apply')));
      await tester.pumpAndSettle();
      expect(services.companionPrefs.choice.identity, CompanionIdentity.lunar);
      final p = await SharedPreferences.getInstance();
      expect(p.getString(CompanionPreferences.keyChoice), 'lunar');
    },
  );
  for (final size in [
    const Size(1440, 1000),
    const Size(1920, 1080),
    const Size(1024, 768),
    const Size(390, 844),
    const Size(360, 560),
  ]) {
    testWidgets('dashboard responsive ${size.width}x${size.height}', (
      tester,
    ) async {
      final (_, _, services) = await pumpV2(tester, size: size);
      services.presentation.setMode(UiPresentationMode.dashboard);
      await tester.pumpAndSettle();
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();
      expect(find.text('Your work, connected.'), findsOneWidget);
      expect(tester.takeException(), isNull);
      final orb = tester.getRect(find.byKey(LivingShell.orbKey));
      expect(orb.left, greaterThanOrEqualTo(0));
      expect(orb.bottom, lessThanOrEqualTo(size.height));
    });
  }
  // UI V2 completion V-2: common laptop windows got the one-column layout,
  // with the destinations and the composer below the fold.
  for (final size in [
    const Size(1366, 768),
    const Size(1536, 864),
    const Size(1280, 800),
    const Size(1024, 768),
    const Size(900, 640),
  ]) {
    testWidgets(
      'dashboard medium ${size.width}x${size.height} keeps destinations and composer in view',
      (tester) async {
        final (_, _, services) = await pumpV2(tester, size: size);
        services.presentation.setMode(UiPresentationMode.dashboard);
        await tester.pumpAndSettle();
        await tester.pump(const Duration(seconds: 1));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        expect(OrbDock.dashboardMedium(size, 1), isTrue);
        final view = Offset.zero & size;
        final orb = tester.getRect(find.byKey(LivingShell.orbKey));
        final composer = tester.getRect(
          find.byKey(const ValueKey('living-composer-field')),
        );
        expect(view.contains(composer.bottomRight), isTrue);
        expect(composer.overlaps(orb), isFalse);
        for (final title in [
          'Memory',
          'Tasks',
          'Brain & models',
          'Connections',
          'Permissions',
          'Operational state',
        ]) {
          final card = tester.getRect(find.text(title).last);
          expect(view.contains(card.bottomRight), isTrue, reason: title);
          expect(card.overlaps(orb), isFalse, reason: title);
          expect(card.overlaps(composer), isFalse, reason: title);
        }
        // Navigation: a rail when there is room, the drawer otherwise.
        expect(
          find.byTooltip('Navigation'),
          size.width >= 1100 ? findsNothing : findsOneWidget,
        );
        final header = tester.getRect(find.text('Your work, connected.'));
        expect(header.bottom, lessThan(orb.top));
      },
    );
  }
  test(
    'dashboard layouts: wide only for tall windows, medium never at large text',
    () {
      expect(OrbDock.dashboardWide(const Size(1440, 1000), 1), isTrue);
      expect(OrbDock.dashboardMedium(const Size(1440, 1000), 1), isFalse);
      expect(OrbDock.dashboardMedium(const Size(1366, 768), 2), isFalse);
      expect(OrbDock.dashboardMedium(const Size(800, 640), 1), isFalse);
      expect(OrbDock.dashboardMedium(const Size(1366, 768), 1.3), isFalse);
      expect(OrbDock.dashboardMedium(const Size(1024, 600), 1), isFalse);
      expect(OrbDock.dashboardRail(const Size(1024, 768), 1), 0);
      expect(OrbDock.dashboardRail(const Size(1366, 768), 1), 208);
    },
  );
  // UI V2 completion LV-1 (live run l4): opening Settings started the voice
  // service inside initState, so its status notified listeners during build.
  testWidgets('opening Settings starts the voice service after the frame', (
    tester,
  ) async {
    final (_, _, services) = await pumpV2(tester, size: const Size(1280, 800));
    final never = Completer<_VoiceTransport>();
    final voice = LiveVoiceService(launch: () => never.future);
    services.attachLiveVoice(voice);
    services.presentation.setMode(
      UiPresentationMode.workspace,
      focus: WorkspaceFocus.settings,
    );
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(voice.status.value.state, VoiceServiceState.starting);
    voice.dispose();
    await tester.pump(const Duration(minutes: 1));
  });
  // UI V2 completion LV-2 (live run l4): after a focused control went away
  // (the composer is disabled while URI works), focus fell to the route's
  // scope above the shell and Ctrl+1..4 / Escape stopped working.
  testWidgets('mode shortcuts work when focus has fallen to the route scope', (
    tester,
  ) async {
    final (_, _, services) = await pumpV2(tester, size: const Size(1280, 800));
    services.presentation.setMode(
      UiPresentationMode.workspace,
      focus: WorkspaceFocus.conversation,
    );
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('living-composer-field')).first);
    await tester.pump();
    FocusManager.instance.primaryFocus!.unfocus();
    await tester.pump();
    expect(FocusManager.instance.primaryFocus, isA<FocusScopeNode>());
    Future<void> ctrl(LogicalKeyboardKey key) async {
      await tester.sendKeyDownEvent(LogicalKeyboardKey.controlLeft);
      await tester.sendKeyEvent(key);
      await tester.sendKeyUpEvent(LogicalKeyboardKey.controlLeft);
      await tester.pumpAndSettle();
    }

    await ctrl(LogicalKeyboardKey.digit3);
    expect(services.presentation.mode, UiPresentationMode.dashboard);
    await ctrl(LogicalKeyboardKey.digit2);
    expect(services.presentation.mode, UiPresentationMode.workspace);
    // A page pushed above the shell keeps its own keys: no mode change under it.
    final nav = Navigator.of(tester.element(find.byType(LivingShell)));
    unawaited(
      nav.push(
        MaterialPageRoute<void>(
          builder: (_) => const Scaffold(body: Text('page')),
        ),
      ),
    );
    await tester.pumpAndSettle();
    await ctrl(LogicalKeyboardKey.digit3);
    expect(services.presentation.mode, UiPresentationMode.workspace);
    nav.pop();
    await tester.pumpAndSettle();
    await tester.sendKeyEvent(LogicalKeyboardKey.escape);
    await tester.pumpAndSettle();
    expect(services.presentation.mode, UiPresentationMode.companion);
  });
  test('floating controls fit both sizes without covering the Companion', () {
    for (final size in [const Size(440, 680), const Size(360, 560)]) {
      final orb = OrbDock.forMode(
        UiPresentationMode.companion,
        size,
        visualV2: true,
        expanded: true,
      ).rect;
      final rects = CompanionModeView.buttonRects(
        size,
        orb,
        CompanionUiAction.values.take(6).toList(),
      );
      for (final rect in rects.values) {
        expect(rect.overlaps(orb), isFalse);
        expect(rect.left, greaterThanOrEqualTo(0));
        expect(rect.bottom, lessThanOrEqualTo(size.height));
      }
      expect(
        CompanionModeView.voiceRect(size, orb).top,
        greaterThan(orb.bottom),
      );
    }
  });
  test('text-sized controls keep click targets and separate at 200% text', () {
    for (final size in [const Size(360, 560), const Size(440, 680)]) {
      for (final scale in [1.0, 2.0]) {
        final orb = OrbDock.forMode(
          UiPresentationMode.companion,
          size,
          visualV2: true,
          expanded: true,
        ).rect;
        final rects = CompanionModeView.buttonRects(
          size,
          orb,
          CompanionUiAction.values,
          textScale: scale,
        ).values.toList();
        for (var i = 0; i < rects.length; i++) {
          expect(rects[i].height, greaterThanOrEqualTo(44));
          expect(rects[i].width, greaterThanOrEqualTo(44));
          expect(rects[i].overlaps(orb), isFalse);
          expect(rects[i].bottom, lessThanOrEqualTo(size.height));
          for (var j = i + 1; j < rects.length; j++) {
            expect(rects[i].overlaps(rects[j]), isFalse);
          }
        }
      }
    }
  });
  test(
    'full orbit preserves circular clearance and detached panel separation',
    () {
      const actions = [
        CompanionUiAction.chat,
        CompanionUiAction.dashboard,
        CompanionUiAction.voiceStart,
        CompanionUiAction.review,
      ];
      for (final size in [const Size(360, 560), const Size(440, 680)]) {
        final orb = OrbDock.forMode(
          UiPresentationMode.companion,
          size,
          visualV2: true,
          expanded: true,
        ).rect;
        final wave = CompanionModeView.voiceRect(size, orb);
        final chat = CompanionModeView.chatRect(size, orb);
        expect(chat.top, greaterThan(wave.bottom));
        expect(chat.bottom, lessThanOrEqualTo(size.height));
        for (var degrees = 0; degrees < 360; degrees++) {
          final buttons = CompanionModeView.buttonRects(
            size,
            orb,
            actions,
            angle: degrees * math.pi / 180,
          ).values.toList();
          for (var i = 0; i < buttons.length; i++) {
            final b = buttons[i];
            expect(
              (b.center - orb.center).distance,
              greaterThan(orb.width / 2 + b.width / 2 + 8),
            );
            expect(b.left, greaterThanOrEqualTo(0));
            expect(b.top, greaterThanOrEqualTo(0));
            expect(b.right, lessThanOrEqualTo(size.width));
            expect(b.bottom, lessThan(wave.top));
            for (var j = i + 1; j < buttons.length; j++) {
              expect(
                (b.center - buttons[j].center).distance,
                greaterThan((b.width + buttons[j].width) / 2 + 8),
              );
            }
          }
        }
      }
    },
  );
  for (final size in [const Size(360, 560), const Size(440, 680)]) {
    testWidgets('detached chat at 200 percent text $size', (tester) async {
      final (_, _, services) = await pumpV2(tester, size: size);
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('living-composer-field')),
        findsOneWidget,
      );
      expect(services.presentation.mode, UiPresentationMode.companion);
      expect(tester.takeException(), isNull);
    });
  }
  testWidgets('narrow context opens without squeezing the conversation', (
    tester,
  ) async {
    final (_, app, services) = await pumpV2(tester);
    services.presentation.setMode(UiPresentationMode.workspace);
    await tester.pumpAndSettle();
    final field = find.byKey(const ValueKey('living-composer-field'));
    await tester.enterText(field, 'Layout fixture draft');
    final before = tester.getRect(field);
    await tester.tap(find.byTooltip('Show context'));
    await tester.pumpAndSettle();
    expect(find.byType(Dialog), findsOneWidget);
    expect(tester.getRect(field), before);
    await tester.tap(find.byTooltip('Close context'));
    await tester.pumpAndSettle();
    expect(find.byType(Dialog), findsNothing);
    expect(app.composerDraft, 'Layout fixture draft');
    expect(tester.takeException(), isNull);
  });
  testWidgets('gallery actions remain visible below viewer at 200% text', (
    tester,
  ) async {
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    final (_, _, services) = await pumpV2(tester, size: const Size(390, 844));
    Navigator.of(LivingShell.orbKey.currentContext!).push(
      MaterialPageRoute<void>(
        builder: (_) => CompanionGallery(
          active: services.companionPrefs,
          services: services,
        ),
      ),
    );
    await tester.pumpAndSettle();
    final apply = tester.getRect(find.byKey(const ValueKey('gallery-apply')));
    final cancel = tester.getRect(find.byKey(const ValueKey('gallery-cancel')));
    final viewer = tester.getRect(
      find.byKey(const ValueKey('gallery-live-renderer')),
    );
    expect(apply.height, greaterThanOrEqualTo(48));
    expect(apply.bottom, lessThanOrEqualTo(844));
    expect(apply.overlaps(cancel), isFalse);
    expect(viewer.bottom, lessThanOrEqualTo(apply.top));
    await tester.tap(find.byKey(const ValueKey('gallery-cancel')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('gallery-apply')), findsNothing);
    expect(tester.takeException(), isNull);
  });
  testWidgets('small detached chat shows a complete latest reply above input', (
    tester,
  ) async {
    final (_, app, _) = await pumpV2(tester, size: const Size(360, 560));
    app.conversation.add(
      UriTurn(
        id: 'compact-layout-fixture',
        userText: 'Can you help with my draft?',
        timestamp: DateTime(2026, 10, 13),
        stage: TurnStage.completed,
        result: const ActionResult(summary: 'What would you like to change?'),
      ),
    );
    await tester.tap(find.byKey(LivingShell.orbKey));
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pumpAndSettle();
    await tester.tap(
      find.byKey(const ValueKey('a2ui.companion-controls.chat')),
    );
    await tester.pumpAndSettle();
    final reply = tester.getRect(find.text('What would you like to change?'));
    final header = tester.getRect(
      find.byKey(const ValueKey('companion-close-chat')),
    );
    final composer = tester.getRect(
      find.byKey(const ValueKey('living-composer-field')),
    );
    expect(reply.top, greaterThanOrEqualTo(header.bottom));
    expect(reply.bottom, lessThanOrEqualTo(composer.top));
    expect(tester.takeException(), isNull);
  });
  testWidgets('small dashboard initially shows all supporting header copy', (
    tester,
  ) async {
    final (_, _, services) = await pumpV2(tester, size: const Size(390, 844));
    services.presentation.setMode(UiPresentationMode.dashboard);
    await tester.pumpAndSettle();
    final disclaimer = find.text('SIMULATED PREVIEW · no backend connected');
    final scroll = find.ancestor(
      of: disclaimer,
      matching: find.byType(SingleChildScrollView),
    );
    expect(
      tester.getRect(disclaimer).bottom,
      lessThanOrEqualTo(tester.getRect(scroll).bottom),
    );
    expect(
      tester.getRect(scroll).bottom,
      lessThan(tester.getRect(find.byKey(LivingShell.orbKey)).top),
    );
    // Dashboard status reads use the mock client's bounded network delay.
    await tester.pump(const Duration(milliseconds: 500));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  });
  testWidgets('orbit stops for nearby pointer, open chat and reduced motion', (
    tester,
  ) async {
    final (_, _, services) = await pumpV2(tester);
    var pointer = const Offset(-1000, -1000);
    services.readCompanionPointer = () async => pointer;
    await tester.tap(find.byKey(LivingShell.orbKey));
    await tester.pump(const Duration(milliseconds: 350));
    await tester.pumpAndSettle();
    final chat = find.byKey(const ValueKey('a2ui.companion-controls.chat'));
    final start = tester.getRect(chat);
    services.effects.setReducedMotion(false);
    for (var i = 0; i < 25; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(
      (tester.getRect(chat).center - start.center).distance,
      greaterThan(1),
    );
    pointer = tester.getRect(find.byKey(LivingShell.orbKey)).center;
    for (var i = 0; i < 3; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    final paused = tester.getRect(chat);
    for (var i = 0; i < 20; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(tester.getRect(chat), paused);
    pointer = const Offset(-1000, -1000);
    await tester.tap(chat);
    await tester.pump();
    final opened = tester.getRect(chat);
    for (var i = 0; i < 25; i++) {
      await tester.pump(const Duration(milliseconds: 100));
    }
    expect(tester.getRect(chat), opened);
    services.effects.setReducedMotion(true);
    await tester.tap(find.byKey(const ValueKey('companion-close-chat')));
    await tester.pumpAndSettle();
    final reduced = tester.getRect(chat);
    await tester.pump(const Duration(seconds: 5));
    expect(tester.getRect(chat), reduced);
    expect(tester.takeException(), isNull);
  });
  testWidgets(
    'viewer exposes every existing design and state with one isolated renderer',
    (tester) async {
      final (_, _, services) = await pumpV2(
        tester,
        size: const Size(1440, 1000),
      );
      final navigator = Navigator.of(LivingShell.orbKey.currentContext!);
      navigator.push(
        MaterialPageRoute<void>(
          builder: (_) => CompanionGallery(
            active: services.companionPrefs,
            services: services,
          ),
        ),
      );
      await tester.pumpAndSettle();
      for (final design in CompanionDesign.installed) {
        final entry = find.byKey(ValueKey('gallery-design-${design.id}'));
        await tester.scrollUntilVisible(
          entry,
          120,
          scrollable: find
              .descendant(
                of: find.byType(CompanionGallery),
                matching: find.byType(Scrollable),
              )
              .first,
        );
        await tester.tap(entry);
        await tester.pumpAndSettle();
        for (final state in CompanionState.values) {
          tester
              .widget<DropdownButton<CompanionState>>(
                find.byType(DropdownButton<CompanionState>),
              )
              .onChanged!(state);
          await tester.pumpAndSettle();
          final renderer = tester.widget<LivingCompanion>(
            find.byKey(const ValueKey('gallery-live-renderer')),
          );
          expect(renderer.state, state);
          if (design.classicVariant != null) {
            expect(renderer.variant, design.classicVariant);
          }
        }
      }
      expect(services.companionPrefs.choice.identity, CompanionIdentity.solar);
      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();
    },
  );
  testWidgets(
    '200 percent text keeps dashboard navigation and chat reachable',
    (tester) async {
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      final (_, _, services) = await pumpV2(
        tester,
        size: const Size(1024, 768),
      );
      services.presentation.setMode(UiPresentationMode.dashboard);
      await tester.pumpAndSettle();
      await tester.pump(const Duration(seconds: 1));
      await tester.pumpAndSettle();
      expect(find.byTooltip('Navigation'), findsOneWidget);
      expect(tester.takeException(), isNull);
      services.presentation.setMode(UiPresentationMode.companion);
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();
      await tester.tap(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
      );
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('living-composer-field')),
        findsOneWidget,
      );
      expect(tester.takeException(), isNull);
      await tester.pump(const Duration(seconds: 5));
    },
  );
  test('local A2UI catalog is isolated from runtime authority', () async {
    final invoked = <CompanionUiAction>[];
    final controls = CompanionActions((a) async => invoked.add(a));
    controls.project([CompanionUiAction.chat]);
    expect(controls.hub.surface(CompanionActions.surfaceId)?.ready, isTrue);
    await controls.hub.act(CompanionActions.surfaceId, 'voiceStart');
    expect(invoked, isEmpty);
    await controls.hub.act(CompanionActions.surfaceId, 'chat');
    expect(invoked, [CompanionUiAction.chat]);
    final runtime = A2uiHub();
    runtime.apply([
      {
        'version': 'v0.9',
        'createSurface': {
          'surfaceId': 'attack',
          'catalogId': CompanionActions.policy.catalogId,
        },
      },
    ]);
    expect(runtime.surface('attack'), isNull);
    expect(controls.hub.registry.containsKey('scheduler.confirm'), isFalse);
    controls.dispose();
    runtime.dispose();
  });
  testWidgets(
    'floating controls omit unavailable actions and preserve shared draft',
    (tester) async {
      final (client, app, services) = await pumpV2(tester);
      app.setComposerDraft('Keep this draft');
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('expanded-companion-panel')),
        findsNothing,
      );
      expect(find.byKey(const ValueKey('living-composer-field')), findsNothing);
      expect(
        find.byKey(const ValueKey('a2ui.companion-controls.review')),
        findsNothing,
      );
      expect(
        find.byKey(const ValueKey('a2ui.companion-controls.voiceStart')),
        findsNothing,
      );
      await tester.tap(
        find.byKey(const ValueKey('a2ui.companion-controls.chat')),
      );
      await tester.pumpAndSettle();
      expect(services.presentation.mode, UiPresentationMode.companion);
      expect(app.composerDraft, 'Keep this draft');
      expect(client.asks, 0);
      await tester.pump(const Duration(seconds: 5));
    },
  );
  testWidgets(
    'existing voice visual follows listening, user speech and URI speech',
    (tester) async {
      final (_, _, services) = await pumpV2(tester);
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();
      expect(
        find.byKey(const ValueKey('companion-voice-visual')),
        findsNothing,
      );
      services.voice.add(const ListeningStarted('fixture'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 600));
      expect(find.byKey(const ValueKey('stage-waveform')), findsOneWidget);
      services.voice.add(const UserSpeechStarted('fixture'));
      services.voice.add(
        const UserTranscript('fixture', 'A private fixture sentence'),
      );
      await tester.pump();
      expect(find.text('You'), findsOneWidget);
      services.voice.add(
        const ListeningEnded('fixture', VoiceEndReason.completed),
      );
      services.voice.add(const UriSpeechStarted('reply', 'A fixture reply'));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 600));
      expect(find.byKey(const ValueKey('stage-waveform')), findsOneWidget);
      services.voice.add(const VoiceReset());
      await tester.pump();
      expect(
        find.byKey(const ValueKey('companion-voice-visual')),
        findsNothing,
      );
      await tester.pump(const Duration(seconds: 5));
    },
  );
  testWidgets(
    'generated voice actions require a click and start or cancel once',
    (tester) async {
      final (client, _, services) = await pumpV2(tester);
      final transport = _VoiceTransport();
      final voice = LiveVoiceService(launch: () async => transport);
      services.attachLiveVoice(voice);
      await voice.ensureStarted();
      voice.status.value = const VoiceServiceStatus(
        state: VoiceServiceState.ready,
      );
      await tester.tap(find.byKey(LivingShell.orbKey));
      await tester.pump(const Duration(milliseconds: 350));
      await tester.pumpAndSettle();
      expect(transport.sent.where((m) => m['cmd'] == 'listen_start'), isEmpty);
      await tester.tap(
        find.byKey(const ValueKey('a2ui.companion-controls.voiceStart')),
      );
      await tester.pumpAndSettle();
      expect(transport.sent.where((m) => m['cmd'] == 'listen_start').length, 1);
      expect(
        find.byKey(const ValueKey('a2ui.companion-controls.voiceStart')),
        findsNothing,
      );
      await tester.tap(
        find.byKey(const ValueKey('a2ui.companion-controls.voiceCancel')),
      );
      await tester.pumpAndSettle();
      expect(
        transport.sent.where((m) => m['cmd'] == 'listen_cancel').length,
        1,
      );
      expect(client.asks, 0);
      await tester.pump(const Duration(seconds: 5));
    },
  );
  testWidgets(
    'login guards duplicate submits, obscures password and shows real errors',
    (tester) async {
      var calls = 0;
      final result = Completer<AuthOutcome>();
      await tester.pumpWidget(
        MaterialApp(
          theme: buildUriTheme(UriColors.ivoryFoundry),
          home: LoginScreen(
            onLogin: (_, _) {
              calls++;
              return result.future;
            },
            onSignup: (_, _) async => const AuthOutcome.failure('Unavailable'),
          ),
        ),
      );
      expect(find.text('URI'), findsOneWidget);
      final fields = find.byType(TextField);
      expect(tester.widget<TextField>(fields.last).obscureText, isTrue);
      await tester.enterText(fields.first, 'visual-fixture');
      await tester.enterText(fields.last, 'test-only');
      await tester.tap(find.widgetWithText(ElevatedButton, 'Sign in'));
      await tester.pump();
      await tester.testTextInput.receiveAction(TextInputAction.done);
      await tester.pump();
      expect(calls, 1);
      result.complete(
        const AuthOutcome.failure('Fixture server refused sign-in'),
      );
      await tester.pumpAndSettle();
      expect(find.text('Fixture server refused sign-in'), findsOneWidget);
    },
  );
}
