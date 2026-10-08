import 'package:flutter/widgets.dart';

import 'companion/companion_sources.dart';
import 'companion/effects_settings.dart';
import 'contracts/readiness_report.dart';
import 'contracts/work_items.dart';
import 'presentation/presentation_controller.dart';

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
  });

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

  void dispose() {
    presentation.dispose();
    companion.dispose();
    work.dispose();
    readiness.dispose();
    effects.dispose();
    demo.dispose();
    selectedHarness.dispose();
    reasoningMode.dispose();
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
  bool updateShouldNotify(LivingScope oldWidget) => services != oldWidget.services;
}
