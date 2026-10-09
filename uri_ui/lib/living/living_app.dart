/// Plugin-free root of the Living Companion experience.
///
/// Mirrors the Hybrid split: this file (and everything under
/// `lib/living/`) imports no platform plugin, so widget tests can build
/// the full tree; `main_living.dart` is the only place that wires a real
/// picker/opener in. One [AppState] (mock client in this phase) is
/// shared with the Hybrid conversation widgets through [AppStateScope].
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/app_state.dart';
import '../services/app_state_scope.dart';
import '../services/attachment_opener_service.dart';
import '../models/user_preferences.dart';
import '../services/file_picker_service.dart';
import '../services/preferences_store.dart';
import '../theme/uri_theme.dart';
import 'a2ui/a2ui_hub.dart';
import 'companion/companion_preferences.dart';
import 'companion/companion_sources.dart';
import 'companion/effects_settings.dart';
import 'companion/frame_clock.dart';
import 'contracts/readiness_report.dart';
import 'contracts/work_items.dart';
import 'integration/oi_conversation.dart';
import 'integration/oi_sources.dart';
import 'integration/scheduler_client.dart';
import 'living_scope.dart';
import 'presentation/living_shell.dart';
import 'presentation/presentation_controller.dart';
import 'screens/onboarding/living_onboarding_flow.dart';

/// Keys are namespaced so the living preview never writes the Hybrid
/// app's keys in the shared `shared_preferences.json`.
class LivingPrefs {
  LivingPrefs._();
  static const onboardingDone = 'uri.living.onboardingDone';
  static const reducedEffects = 'uri.living.reducedEffects';
  static const themeChoice = 'uri.living.themeChoice';
}

/// Namespaced replacement for the Hybrid [PreferencesStore].
///
/// All `uri_ui` builds share one `shared_preferences.json` on this PC
/// (the live Hybrid app included), so the preview must never write the
/// Hybrid keys (`uri.completedOnboarding`, `uri.focusAreas`, ...). This
/// store keeps the same [UserPreferences] shape under `uri.living.*`.
class LivingPreferencesStore extends PreferencesStore {
  static const keyCompletedOnboarding = 'uri.living.prefs.completedOnboarding';
  static const keyFocusAreas = 'uri.living.prefs.focusAreas';
  static const keyCommunicationStyle = 'uri.living.prefs.communicationStyle';
  static const keyAutonomyLevel = 'uri.living.prefs.autonomyLevel';

  @override
  Future<UserPreferences> load() async {
    final prefs = await SharedPreferences.getInstance();
    return UserPreferences(
      focusAreas: prefs.getStringList(keyFocusAreas) ?? const [],
      communicationStyle:
          CommunicationStyle.values
              .where((v) => v.name == prefs.getString(keyCommunicationStyle))
              .firstOrNull ??
          CommunicationStyle.concise,
      autonomyLevel:
          AutonomyLevel.values
              .where((v) => v.name == prefs.getString(keyAutonomyLevel))
              .firstOrNull ??
          AutonomyLevel.askEveryTime,
      completedOnboarding: prefs.getBool(keyCompletedOnboarding) ?? false,
    );
  }

  @override
  Future<void> save(UserPreferences preferences) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(
      keyCompletedOnboarding,
      preferences.completedOnboarding,
    );
    await prefs.setStringList(keyFocusAreas, preferences.focusAreas);
    await prefs.setString(
      keyCommunicationStyle,
      preferences.communicationStyle.name,
    );
    await prefs.setString(keyAutonomyLevel, preferences.autonomyLevel.name);
  }
}

class LivingApp extends StatefulWidget {
  const LivingApp({
    super.key,
    required this.appState,
    this.services,
    this.filePicker,
    this.attachmentOpener,
    this.initialTheme = UriThemeChoice.obsidianCyan,
    this.skipOnboarding = false,
  });

  final AppState appState;

  /// Tests may inject prepared services; the app builds defaults.
  final LivingServices? services;
  final FilePickerFn? filePicker;
  final AttachmentOpenerFn? attachmentOpener;
  final UriThemeChoice initialTheme;

  /// Tests and the `--no-onboarding` demo path.
  final bool skipOnboarding;

  @override
  State<LivingApp> createState() => _LivingAppState();

  /// Default wiring: real AppState-derived signal + mock work simulator
  /// + mock readiness, merged by priority.
  static LivingServices buildDefaultServices(AppState appState) {
    final demo = MockCompanionSource();
    final work = MockWorkSimulator();
    return LivingServices(
      presentation: UiPresentationController(),
      companion: CompositeCompanionSource([
        AppStateCompanionSource(appState, dataIsMock: true),
        work.companion,
        demo,
      ]),
      work: work,
      readiness: MockReadinessSource(),
      effects: EffectsSettings(),
      demo: demo,
    );
  }

  /// Working-system wiring (WS blueprint W9): the orb follows the real OI
  /// event stream and readiness comes from the integrated worker. Office
  /// work items have no backend yet and stay on the flagged simulator.
  /// A2UI: surfaces come from the scheduler (`URI_SCHEDULER_STATE`); the
  /// worker's `a2ui.handoff` events ask it to propose. Without a scheduler
  /// the hub still shows an honest notice for a handoff.
  static A2uiHub _a2uiHub(OiConversation oi) {
    final hub = A2uiHub(scheduler: SchedulerClient.fromEnvironment(), handoffs: oi.a2uiHandoffs);
    hub.refresh();
    return hub;
  }

  static LivingServices buildIntegratedServices(OiConversation oi) {
    final demo = MockCompanionSource();
    final work = MockWorkSimulator();
    return LivingServices(
      presentation: UiPresentationController(),
      companion: CompositeCompanionSource([OiCompanionSource(oi), work.companion, demo]),
      work: work,
      readiness: OiReadinessSource(oi),
      effects: EffectsSettings(),
      demo: demo,
      appDataIsMock: true,
      oi: oi,
      a2ui: _a2uiHub(oi),
    );
  }
}

class _LivingAppState extends State<LivingApp> {
  late final LivingServices _services =
      widget.services ?? LivingApp.buildDefaultServices(widget.appState);
  late UriThemeChoice _theme = widget.initialTheme;
  bool? _onboardingDone;

  @override
  void initState() {
    super.initState();
    _loadPrefs();
  }

  Future<void> _loadPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    if (!mounted) return;
    final done =
        widget.skipOnboarding ||
        (prefs.getBool(LivingPrefs.onboardingDone) ?? false);
    final reduced = prefs.getBool(LivingPrefs.reducedEffects);
    final themeName = prefs.getString(LivingPrefs.themeChoice);
    _services.companionPrefs.restoreFrom(prefs);
    setState(() {
      _onboardingDone = done;
      if (reduced != null) _services.effects.setReducedEffects(reduced);
      if (themeName != null) {
        for (final t in UriThemeChoice.values) {
          if (t.name == themeName) _theme = t;
        }
      }
    });
  }

  Future<void> _finishOnboarding() async {
    setState(() => _onboardingDone = true);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(LivingPrefs.onboardingDone, true);
  }

  Future<void> setTheme(UriThemeChoice choice) async {
    setState(() => _theme = choice);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(LivingPrefs.themeChoice, choice.name);
  }

  @override
  void dispose() {
    if (widget.services == null) _services.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final platformBrightness =
        WidgetsBinding.instance.platformDispatcher.platformBrightness;
    // The engine reports the display the window is on; the frame-rate
    // settings and the adaptive governor are bounded by it.
    final hz = View.maybeOf(context)?.display.refreshRate;
    final governor = _services.frameGovernor;
    if (hz != null && (hz - governor.displayHz).abs() >= 0.5) {
      // After the frame: the governor notifies listeners, which must not
      // happen while this tree is building.
      WidgetsBinding.instance.addPostFrameCallback(
        (_) => governor.updateDisplay(hz),
      );
    }
    governor.install();
    final prefs = _services.companionPrefs;
    return AppStateScope(
      state: widget.appState,
      child: LivingScope(
        services: _services,
        child: EffectsSettingsScope(
          settings: _services.effects,
          child: CompanionPreferencesScope(
            preferences: prefs,
            child: CompanionClockScope(
              clock: _services.frameClock,
              // While the window is minimised every ticker below is muted,
              // including ones that do not run on the companion clock (the
              // classic orb, transitions): nothing on screen, no frames.
              child: ValueListenableBuilder<bool>(
                valueListenable: _services.frameClock.visibility,
                builder: (context, visible, child) =>
                    TickerMode(enabled: visible, child: child!),
                child: ListenableBuilder(
                  listenable: prefs,
                  builder: (context, _) {
                    // The selected companion decides the theme; the free theme
                    // choice applies only to the classic orb.
                    final theme = CompanionPreferences.themeFor(
                      prefs.choice,
                      _theme,
                    );
                    final palette = resolveUriColors(theme, platformBrightness);
                    return LivingThemeController(
                      current: _theme,
                      setTheme: setTheme,
                      child: MaterialApp(
                        title: 'URI',
                        debugShowCheckedModeBanner: false,
                        theme: buildUriTheme(palette),
                        themeMode: ThemeMode.light,
                        home: switch (_onboardingDone) {
                          null => const Scaffold(body: SizedBox.shrink()),
                          false => LivingOnboardingFlow(
                            onFinished: _finishOnboarding,
                          ),
                          true => LivingShell(
                            filePicker: widget.filePicker,
                            attachmentOpener: widget.attachmentOpener,
                          ),
                        },
                      ),
                    );
                  },
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// Lets the Settings region change the theme without reaching into the
/// app state object.
class LivingThemeController extends InheritedWidget {
  const LivingThemeController({
    super.key,
    required this.current,
    required this.setTheme,
    required super.child,
  });

  final UriThemeChoice current;
  final Future<void> Function(UriThemeChoice) setTheme;

  static LivingThemeController? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<LivingThemeController>();

  @override
  bool updateShouldNotify(LivingThemeController old) => old.current != current;
}
