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
import '../services/file_picker_service.dart';
import '../theme/uri_theme.dart';
import 'companion/companion_sources.dart';
import 'companion/effects_settings.dart';
import 'contracts/readiness_report.dart';
import 'contracts/work_items.dart';
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
        AppStateCompanionSource(appState),
        work.companion,
        demo,
      ]),
      work: work,
      readiness: MockReadinessSource(),
      effects: EffectsSettings(),
      demo: demo,
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
    final done = widget.skipOnboarding || (prefs.getBool(LivingPrefs.onboardingDone) ?? false);
    final reduced = prefs.getBool(LivingPrefs.reducedEffects);
    final themeName = prefs.getString(LivingPrefs.themeChoice);
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
    final palette = resolveUriColors(_theme, platformBrightness);
    return AppStateScope(
      state: widget.appState,
      child: LivingScope(
        services: _services,
        child: EffectsSettingsScope(
          settings: _services.effects,
          child: LivingThemeController(
            current: _theme,
            setTheme: setTheme,
            child: MaterialApp(
              title: 'URI',
              debugShowCheckedModeBanner: false,
              theme: buildUriTheme(palette),
              themeMode: ThemeMode.light,
              home: switch (_onboardingDone) {
                null => const Scaffold(body: SizedBox.shrink()),
                false => LivingOnboardingFlow(onFinished: _finishOnboarding),
                true => LivingShell(
                    filePicker: widget.filePicker,
                    attachmentOpener: widget.attachmentOpener,
                  ),
              },
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
