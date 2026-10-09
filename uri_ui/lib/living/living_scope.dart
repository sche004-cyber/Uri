import 'package:flutter/widgets.dart';

import 'companion/companion_preferences.dart';
import 'companion/companion_sources.dart';
import 'companion/energy_orb.dart' show OrbPalette, OrbVariant;
import 'companion/effects_settings.dart';
import 'companion/frame_clock.dart';
import 'contracts/readiness_report.dart';
import 'contracts/work_items.dart';
import 'integration/oi_conversation.dart';
import 'presentation/presentation_controller.dart';
import 'voice/voice_catalog.dart';
import 'voice/voice_session.dart';

/// Reasoning depth the user asks for. UI-only preference in this phase;
/// the mock does not change behaviour with it, and the Settings region
/// says so (Simulated).
enum ReasoningMode { fast, balanced, deep }

extension ReasoningModeLabel on ReasoningMode {
  String get label => switch (this) {
    ReasoningMode.fast => 'Fast',
    ReasoningMode.balanced => 'Balanced',
    ReasoningMode.deep => 'Deep',
  };
}

/// Everything the living UI shares below its root, in one place, so
/// screens never construct their own controllers or sources.
///
/// All members are observed by the widgets that need them; none is a
/// backend. `AppState` itself is still provided by the Hybrid app's
/// [AppStateScope] so the conversation widgets are reused unchanged.
class LivingServices {
  LivingServices({
    required this.presentation,
    required this.companion,
    required this.work,
    required this.readiness,
    required this.effects,
    required this.demo,
    this.appDataIsMock = true,
    this.oi,
  });

  /// Working-system integration: the real conversation over the integrated
  /// worker (Core + Operational Intelligence + Runtime v1). Null in the mock
  /// preview. Owned by the root that created it (not disposed here).
  final OiConversation? oi;

  final UiPresentationController presentation;

  /// Merged signal the orb renders.
  final CompositeCompanionSource companion;

  /// Office work (mock simulator in this phase).
  final WorkItemSource work;

  final ReadinessSource readiness;
  final EffectsSettings effects;

  /// A hand-driven source for the state showcase and demo buttons
  /// (listening / speaking have no real source yet).
  final MockCompanionSource demo;

  /// True while `AppState` is backed by `MockUriClient`: regions that
  /// render AppState data then carry the Simulated badge too.
  final bool appDataIsMock;

  /// Executor selection (harness id) and reasoning depth. Selection is a
  /// UI preference here; a real run would bind it into an execution
  /// proposal that the user approves (Phase 2 `proposal_digest`).
  final ValueNotifier<String?> selectedHarness = ValueNotifier<String?>(null);
  final ValueNotifier<ReasoningMode> reasoningMode =
      ValueNotifier<ReasoningMode>(ReasoningMode.balanced);

  /// Click responses on the orb (each increment plays the poke animation
  /// and shows a question bubble). UI-local; never a Brain event.
  final ValueNotifier<int> orbPokes = ValueNotifier<int>(0);

  /// One focus node for whichever composer is mounted, so a click on the
  /// orb can hand the keyboard to it.
  final FocusNode composerFocus = FocusNode(debugLabel: 'living-composer');

  /// Visual family of the orb (owner choice; see UI_ORB_OPTIONS.md).
  final ValueNotifier<OrbVariant> orbVariant = ValueNotifier<OrbVariant>(
    OrbVariant.nebula,
  );

  /// Colour palette; null = the style's own default palette.
  final ValueNotifier<OrbPalette?> orbPalette = ValueNotifier<OrbPalette?>(
    null,
  );

  /// The user's companion, appearance, performance and voice preferences
  /// (Companion Settings). The app root restores them in place from
  /// `uri.living.companion.*` at start-up; the selected companion decides
  /// the theme.
  final CompanionPreferences companionPrefs = CompanionPreferences();

  /// The one clock the companion and the voice waveform animate on.
  final CompanionFrameClock frameClock = CompanionFrameClock();

  /// Applies the frame-rate preference (fixed or adaptive) to [frameClock].
  late final CompanionFrameGovernor frameGovernor = CompanionFrameGovernor(
    clock: frameClock,
    preferences: companionPrefs,
  );

  /// The voice session the presentation draws. Fed only by a
  /// [VoiceServiceAdapter] through [bindVoice]; with none bound it stays off.
  final VoiceSessionController voice = VoiceSessionController();
  VoiceServiceBinding? _voiceBinding;
  VoiceCompanionSource? _voiceSource;

  /// Installed voices and previews (Companion Settings). The default says
  /// that no engine is available; the Windows entry point installs the real
  /// one.
  VoiceCatalog voiceCatalog = const UnavailableVoiceCatalog();

  /// The adapter currently feeding [voice], if any.
  VoiceServiceAdapter? get voiceAdapter => _voiceBinding?.adapter;

  /// Connects URI's voice service (or a labelled simulation) to the
  /// presentation, and adds the voice session to the companion's merged
  /// signal so the orb listens and speaks with it.
  void bindVoice(VoiceServiceAdapter adapter) {
    _voiceBinding?.dispose();
    voice.add(const VoiceReset());
    voice.simulated = adapter.simulated;
    _voiceBinding = VoiceServiceBinding(adapter, voice);
    companion.addSource(_voiceSource ??= VoiceCompanionSource(voice));
  }

  void dispose() {
    presentation.dispose();
    companion.dispose();
    work.dispose();
    readiness.dispose();
    effects.dispose();
    demo.dispose();
    selectedHarness.dispose();
    reasoningMode.dispose();
    orbVariant.dispose();
    orbPalette.dispose();
    orbPokes.dispose();
    composerFocus.dispose();
    _voiceBinding?.dispose();
    _voiceSource?.dispose();
    voice.dispose();
    frameGovernor.dispose();
    frameClock.dispose();
    companionPrefs.dispose();
  }
}

class LivingScope extends InheritedWidget {
  const LivingScope({super.key, required this.services, required super.child});

  final LivingServices services;

  static LivingServices of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<LivingScope>();
    assert(scope != null, 'LivingScope missing above this widget');
    return scope!.services;
  }

  @override
  bool updateShouldNotify(LivingScope oldWidget) =>
      services != oldWidget.services;
}
