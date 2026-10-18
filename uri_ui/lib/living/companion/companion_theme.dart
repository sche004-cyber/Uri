import 'package:flutter/widgets.dart';

import '../../theme/uri_theme.dart';
import 'companion_orb.dart';

/// Binds a companion identity to the rest of URI's appearance.
///
/// The companion is not a widget that happens to sit on a page: choosing it
/// chooses the palette the workspace, dashboard, onboarding, navigation and
/// conversation all read. This is the single place that mapping lives, so
/// there is no second definition to drift.
///
/// It deliberately resolves to the existing [UriColors] / [UriThemeChoice]
/// contract rather than introducing a parallel theme system. Every living
/// widget already reads `UriColors.of(context)` and `UriGlass.of(context)`;
/// adding three palettes behind those lookups themes the whole app without a
/// single new call site.
class CompanionTheme {
  const CompanionTheme._();

  static UriThemeChoice choiceFor(CompanionIdentity identity) =>
      switch (identity) {
        // Ember is a fire spirit: it adopts the existing warm Solar Ember
        // surface rather than a theme of its own.
        CompanionIdentity.solar ||
        CompanionIdentity.ember => UriThemeChoice.solarEmber,
        CompanionIdentity.sakura => UriThemeChoice.sakuraBloom,
        // The hybrid is a night scene, so it adopts the lunar surface colours
        // and lets its own rose accents live in the companion itself. Tinting
        // the whole workspace pink under a silver moon reads as two themes
        // fighting.
        CompanionIdentity.lunar ||
        CompanionIdentity.moonlit => UriThemeChoice.lunarSilver,
      };

  static UriColors paletteFor(CompanionIdentity identity) => switch (identity) {
    CompanionIdentity.solar ||
    CompanionIdentity.ember => UriColors.solarEmber,
    CompanionIdentity.sakura => UriColors.sakuraBloom,
    CompanionIdentity.lunar ||
    CompanionIdentity.moonlit => UriColors.lunarSilver,
  };
}

/// Holds the selected companion for the running app.
///
/// A [ChangeNotifier] rather than a rebuild-the-world setState: switching
/// companion must not disturb navigation, conversation state, permissions or
/// anything in flight. Only the theme and the companion widget listen.
class CompanionController extends ChangeNotifier {
  CompanionController({CompanionIdentity identity = CompanionIdentity.solar})
    : _identity = identity;
  // ignore_for_file: prefer_initializing_formals

  CompanionIdentity _identity;
  CompanionIdentity get identity => _identity;

  UriColors get palette => CompanionTheme.paletteFor(_identity);
  UriThemeChoice get themeChoice => CompanionTheme.choiceFor(_identity);

  void select(CompanionIdentity next) {
    if (_identity == next) return;
    _identity = next;
    notifyListeners();
  }

  static CompanionController of(BuildContext context) {
    final scope = context
        .dependOnInheritedWidgetOfExactType<CompanionScope>();
    return scope?.notifier ?? _fallback;
  }

  /// Used only when no scope is installed (a bare widget in a test).
  static final CompanionController _fallback = CompanionController();
}

class CompanionScope extends InheritedNotifier<CompanionController> {
  const CompanionScope({
    super.key,
    required CompanionController controller,
    required super.child,
  }) : super(notifier: controller);
}
