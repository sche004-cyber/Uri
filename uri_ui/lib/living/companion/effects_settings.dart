import 'package:flutter/widgets.dart';

/// Per-device visual-effects preference for the living UI.
///
/// `reducedEffects == true` disables, in one place: the runtime fragment
/// shader under the orb core, every `BackdropFilter` blur in
/// [GlassPanel], and the blurred glow mask filters in the orb painter.
/// Everything that carries meaning (orb state, badges, progress,
/// approvals) must still be fully distinguishable with effects off; the
/// widget tests in `test/living/energy_orb_test.dart` render every state
/// both ways to keep that true.
///
/// Also honours the platform "reduce motion" accessibility flag by
/// default: when the OS asks for less motion, the orb breathes slower
/// and particles stop orbiting (they still render, statically).
class EffectsSettings extends ChangeNotifier {
  EffectsSettings({bool reducedEffects = false, bool reducedMotion = false})
    : _reducedEffects = reducedEffects,
      _reducedMotion = reducedMotion;
  // ignore_for_file: prefer_initializing_formals

  bool _reducedEffects;
  bool _reducedMotion;

  bool get reducedEffects => _reducedEffects;
  bool get reducedMotion => _reducedMotion;

  void setReducedEffects(bool value) {
    if (_reducedEffects == value) return;
    _reducedEffects = value;
    notifyListeners();
  }

  void setReducedMotion(bool value) {
    if (_reducedMotion == value) return;
    _reducedMotion = value;
    notifyListeners();
  }

  static EffectsSettings of(BuildContext context) {
    final scope = context
        .dependOnInheritedWidgetOfExactType<EffectsSettingsScope>();
    return scope?.notifier ?? _fallback;
  }

  /// Used only when no scope is installed (a bare widget in a test).
  static final EffectsSettings _fallback = EffectsSettings();
}

class EffectsSettingsScope extends InheritedNotifier<EffectsSettings> {
  const EffectsSettingsScope({
    super.key,
    required EffectsSettings settings,
    required super.child,
  }) : super(notifier: settings);
}
