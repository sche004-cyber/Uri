import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';

import '../voice/companion_presence.dart' show SoftDisc, presenceScale;
import 'companion_orb.dart';
import 'companion_preferences.dart';
import 'companion_state.dart';
import 'effects_settings.dart';
import 'energy_orb.dart';

/// The user's chosen companion, wherever the app shows URI.
///
/// The shell, onboarding and the settings preview all draw the companion
/// through this one widget, so the choice, the appearance preferences and
/// the render quality apply everywhere at once. A living identity is drawn by
/// its own shader ([CompanionOrb]); the classic choice keeps the accepted
/// [EnergyOrb] exactly as it was, with its style and palette.
///
/// Switching companion cross-fades the two for a moment instead of cutting.
/// Within one identity nothing is ever remounted: a change of state, mode,
/// size or preference reaches the same element, so its clock and its blend
/// between states continue.
class LivingCompanion extends StatelessWidget {
  const LivingCompanion({
    super.key,
    required this.state,
    required this.size,
    this.progress,
    this.pokes,
    this.variant = OrbVariant.nebula,
    this.palette,
    this.interactive = true,
    this.semanticsLabel,
    this.preserveIdentityTheme = false,
    this.presentationScale = 1,
  });

  final CompanionState state;

  /// Side of the square the companion occupies, in logical pixels.
  final double size;
  final double? progress;
  final ValueNotifier<int>? pokes;

  /// Classic orb only.
  final OrbVariant variant;
  final OrbPalette? palette;
  final bool interactive;
  final String? semanticsLabel;
  final bool preserveIdentityTheme;

  /// View framing only. The existing renderer, state and saved look stay intact;
  /// the same soft disc still bounds its visible atmosphere to this layout box.
  final double presentationScale;

  /// Cross-fade between two companions when the user switches.
  static const Duration switchDuration = Duration(milliseconds: 450);

  @override
  Widget build(BuildContext context) {
    final prefs = CompanionPreferences.of(context);
    final choice = prefs.choice;
    final look = prefs.lookFor(choice);
    final id = choice.identity;
    Widget classic = EnergyOrb(
      state: state,
      progress: progress,
      size: size,
      variant: variant,
      palette: palette,
      pokes: pokes,
      interactive: interactive,
      semanticsLabel: semanticsLabel,
    );
    if (preserveIdentityTheme) {
      classic = Theme(
        data: buildUriTheme(
          resolveUriColors(
            CompanionPreferences.themeFor(choice, UriThemeChoice.graphite),
            Brightness.dark,
          ),
        ),
        child: classic,
      );
    }
    final effects = EffectsSettings.of(context);
    final Widget child;
    if (id == null) {
      child = KeyedSubtree(
        key: const ValueKey('companion-classic'),
        child: classic,
      );
    } else if (effects.reducedEffects) {
      // Reduced effects turns every shader off. The classic orb's
      // effect-free drawing, coloured by the companion's theme, carries the
      // state with tint, ring and label.
      child = KeyedSubtree(
        key: ValueKey('companion-${id.name}-reduced'),
        child: classic,
      );
    } else {
      // Rendered larger than its square so the body fills about half of it
      // (the owner's "in proportion to the space"), then faded to a disc that
      // ends at the square's edge. The size preference scales the same way.
      final scale = presenceScale(id) * look.size * presentationScale;
      child = KeyedSubtree(
        key: ValueKey('companion-${id.name}'),
        child: Semantics(
          label: semanticsLabel ?? 'URI companion: ${state.label}',
          child: OverflowBox(
            minWidth: 0,
            minHeight: 0,
            maxWidth: size * scale,
            maxHeight: size * scale,
            child: SizedBox(
              width: size * scale,
              height: size * scale,
              child: SoftDisc(
                outer: 1 / scale,
                child: CompanionOrb(
                  identity: id,
                  state: state,
                  attention: state == CompanionState.awaitingApproval,
                  look: look,
                  renderScale: prefs.quality.scale,
                ),
              ),
            ),
          ),
        ),
      );
    }
    return SizedBox(
      width: size,
      height: size,
      child: AnimatedSwitcher(
        duration: switchDuration,
        layoutBuilder: (current, previous) => Stack(
          alignment: Alignment.center,
          clipBehavior: Clip.none,
          children: [...previous, ?current],
        ),
        child: child,
      ),
    );
  }
}
