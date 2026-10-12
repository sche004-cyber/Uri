import 'package:flutter/material.dart';

import 'glass_theme.dart';

/// URI's own visual identity: a warm-neutral, spacious SaaS surface
/// with a single confident accent (a deep violet-blue) rather than the
/// brighter indigo/purple gradients common to template SaaS sites.
/// Inspired, by direction only, by premium SaaS product marketing —
/// no colors, assets, copy, or layout are copied from any reference.
///
/// A [ThemeExtension] rather than static constants: every value here
/// legitimately differs between light and dark, so nothing in this
/// class can be a compile-time constant looked up by name alone —
/// call sites read the active palette via [UriColors.of], which
/// resolves through [Theme.of] the same way `Theme.of(context).textTheme`
/// already does. This is what makes "respects the selected theme"
/// actually true instead of aspirational: there is no code path left
/// that can reference a hardcoded light-only color.
@immutable
class UriColors extends ThemeExtension<UriColors> {
  const UriColors({
    required this.ink,
    required this.inkSoft,
    required this.inkFaint,
    required this.canvas,
    required this.surface,
    required this.surfaceSunken,
    required this.border,
    required this.accent,
    required this.accentSoft,
    required this.accentInk,
    required this.success,
    required this.successSoft,
    required this.warning,
    required this.warningSoft,
    required this.danger,
    required this.dangerSoft,
  });

  final Color ink;
  final Color inkSoft;
  final Color inkFaint;

  final Color canvas;
  final Color surface;
  final Color surfaceSunken;
  final Color border;

  final Color accent;
  final Color accentSoft;
  final Color accentInk;

  final Color success;
  final Color successSoft;
  final Color warning;
  final Color warningSoft;
  final Color danger;
  final Color dangerSoft;

  /// Hybrid UI Frozen Blueprint §4.1/§5 — one of the 4 real themes,
  /// values transcribed from `Palettes.dc.html` (canvas/surface/elevated
  /// swatches + accent, per-theme success/warning pill tones and border).
  /// `inkSoft`/`inkFaint`/`accentSoft`/`accentInk`/`danger`/`dangerSoft`
  /// are not given by that reference (a 4-swatch demo, not a full
  /// per-theme token sheet) — these are derived here (ink/canvas blends
  /// for the ink tiers, surface/accent blends for accentSoft, an
  /// accent-lightened/darkened blend for accentInk) or reused from this
  /// app's previously-accepted dark/light danger colors, since no
  /// per-theme error tone exists in the reference either. Disclosed as a
  /// judgment call, not literal artifact data, in the Batch 3 report.
  static const graphite = UriColors(
    ink: Color(0xFFEEF0F1),
    inkSoft: Color(0xFFAAACAD),
    inkFaint: Color(0xFF727375),
    canvas: Color(0xFF0C0D0F),
    surface: Color(0xFF17181B),
    surfaceSunken: Color(0xFF1F2124),
    border: Color(0xFF2A2C30),
    accent: Color(0xFFC8A25A),
    accentSoft: Color(0xFF373126),
    accentInk: Color(0xFFDBC394),
    success: Color(0xFF5FD6A0),
    successSoft: Color(0xFF123524),
    warning: Color(0xFFE3AB4F),
    warningSoft: Color(0xFF3A2C12),
    danger: Color(0xFFFF8080),
    dangerSoft: Color(0xFF3B1E1E),
  );

  static const deepNavy = UriColors(
    ink: Color(0xFFE8EDF5),
    inkSoft: Color(0xFFA5AAB3),
    inkFaint: Color(0xFF6E737D),
    canvas: Color(0xFF0A0F1A),
    surface: Color(0xFF101828),
    surfaceSunken: Color(0xFF182234),
    border: Color(0xFF243349),
    accent: Color(0xFF5B8FC7),
    accentSoft: Color(0xFF1E2D45),
    accentInk: Color(0xFF94B6DB),
    success: Color(0xFF5CC7AB),
    successSoft: Color(0xFF0F2E28),
    warning: Color(0xFFDBA24D),
    warningSoft: Color(0xFF332711),
    danger: Color(0xFFFF8080),
    dangerSoft: Color(0xFF3B1E1E),
  );

  static const slateTeal = UriColors(
    ink: Color(0xFFE8EBED),
    inkSoft: Color(0xFFA8ABAD),
    inkFaint: Color(0xFF737678),
    canvas: Color(0xFF131619),
    surface: Color(0xFF1A1E22),
    surfaceSunken: Color(0xFF20252A),
    border: Color(0xFF2C3238),
    accent: Color(0xFF4A9C92),
    accentSoft: Color(0xFF233536),
    accentInk: Color(0xFF89BFB8),
    success: Color(0xFF5ECDB2),
    successSoft: Color(0xFF123A30),
    warning: Color(0xFFD9A552),
    warningSoft: Color(0xFF332A13),
    danger: Color(0xFFFF8080),
    dangerSoft: Color(0xFF3B1E1E),
  );

  static const lightProfessional = UriColors(
    ink: Color(0xFF1C2024),
    inkSoft: Color(0xFF5D6064),
    inkFaint: Color(0xFF949699),
    canvas: Color(0xFFF6F7F8),
    surface: Color(0xFFFFFFFF),
    surfaceSunken: Color(0xFFEEF0F2),
    border: Color(0xFFDDE1E5),
    accent: Color(0xFF3B5A78),
    accentSoft: Color(0xFFE7EBEF),
    accentInk: Color(0xFF324C66),
    success: Color(0xFF1C7A4C),
    successSoft: Color(0xFFE2F3EA),
    warning: Color(0xFF93650F),
    warningSoft: Color(0xFFFBF0DC),
    danger: Color(0xFFC23B3B),
    dangerSoft: Color(0xFFFBE9E9),
  );

  /// UI Living Companion phase (2026-10-08, `docs/ui_phase/`): the
  /// "Dark Glass + Cyan" direction. Deep charcoal/blue-black canvas,
  /// restrained glass surfaces (see `glass_theme.dart`) and one cool
  /// cyan illumination. Added as a fifth choice so the four Hybrid
  /// themes above (user-approved 2026-09-16) stay byte-identical.
  /// Token rationale in `docs/ui_phase/UI_DESIGN_REFERENCE.md`.
  static const obsidianCyan = UriColors(
    ink: Color(0xFFE6EEF5),
    inkSoft: Color(0xFF9FB0C0),
    inkFaint: Color(0xFF70849A),
    canvas: Color(0xFF070A0F),
    surface: Color(0xFF0E131A),
    surfaceSunken: Color(0xFF141B24),
    border: Color(0xFF1E2A36),
    accent: Color(0xFF38D1E8),
    accentSoft: Color(0xFF0F2A33),
    accentInk: Color(0xFF8AE6F3),
    success: Color(0xFF4FD6A6),
    successSoft: Color(0xFF0E2F26),
    warning: Color(0xFFE8B44F),
    warningSoft: Color(0xFF332810),
    danger: Color(0xFFFF7A7A),
    dangerSoft: Color(0xFF3A1C1C),
  );

  // -------------------------------------------------------------------------
  // Living Companion themes (2026-10-08, docs/companions/).
  //
  // One palette per companion identity. The four Hybrid themes above stay
  // byte-identical; these are added alongside them.
  //
  // Rule applied to all three: the status colours (success / warning / danger)
  // keep their own hue family in every companion theme, because they carry
  // meaning rather than mood. Where a companion accent sits near a status hue
  // the accent was moved, not the status - Solar's accent is solar orange
  // rather than amber so that `warning` stays legible beside it, and Sakura's
  // accent sits at magenta-pink rather than rose so that `danger` does not
  // read as a brand colour. Status is additionally never colour-only: every
  // badge carries its text label and a `Semantics` label (status_badge.dart).
  // -------------------------------------------------------------------------

  /// Solar: dark glass and warm celestial energy.
  static const solarEmber = UriColors(
    ink: Color(0xFFF6ECE3),
    inkSoft: Color(0xFFB9A796),
    // 0xFF86776A measured 4.42:1 on `surface`, just under WCAG AA 4.5:1 for
    // normal text, and this tier is used for placeholder and inactive labels.
    // Lifted to 4.73:1. Measurements in rnd/companions/contrast.py.
    inkFaint: Color(0xFF8B7C6F),
    canvas: Color(0xFF0A0806),
    surface: Color(0xFF130F0B),
    surfaceSunken: Color(0xFF1B1511),
    border: Color(0xFF2E241B),
    accent: Color(0xFFFF9F45),
    accentSoft: Color(0xFF33200E),
    accentInk: Color(0xFFFFD79A),
    success: Color(0xFF5FD6A0),
    successSoft: Color(0xFF0F2E24),
    warning: Color(0xFFF2D04C),
    warningSoft: Color(0xFF332E10),
    danger: Color(0xFFFF6B5E),
    dangerSoft: Color(0xFF3A1714),
  );

  /// Sakura: dark glass and elegant spring luminosity.
  static const sakuraBloom = UriColors(
    ink: Color(0xFFF7EAF0),
    inkSoft: Color(0xFFC2A7B4),
    inkFaint: Color(0xFF8E7585),
    canvas: Color(0xFF0B060A),
    surface: Color(0xFF150C13),
    surfaceSunken: Color(0xFF1D121A),
    border: Color(0xFF33202C),
    accent: Color(0xFFFF77B4),
    accentSoft: Color(0xFF331323),
    accentInk: Color(0xFFFFBBD8),
    success: Color(0xFF5BD3A6),
    successSoft: Color(0xFF0F2E25),
    warning: Color(0xFFE9B457),
    warningSoft: Color(0xFF342713),
    danger: Color(0xFFFF5A4E),
    dangerSoft: Color(0xFF3A1613),
  );

  /// Lunar: dark glass and moonlit night.
  static const lunarSilver = UriColors(
    ink: Color(0xFFEAEFF7),
    inkSoft: Color(0xFFA7B2C4),
    inkFaint: Color(0xFF78839A),
    canvas: Color(0xFF070912),
    surface: Color(0xFF0D1120),
    surfaceSunken: Color(0xFF131829),
    border: Color(0xFF222A42),
    accent: Color(0xFFB9C6E8),
    accentSoft: Color(0xFF1A2138),
    accentInk: Color(0xFFE2E9F8),
    success: Color(0xFF56CFA8),
    successSoft: Color(0xFF0E2E26),
    warning: Color(0xFFE3B35A),
    warningSoft: Color(0xFF332912),
    danger: Color(0xFFFF7A7A),
    dangerSoft: Color(0xFF3A1C1C),
  );

  // Approved Concept C material, ink and brass values. Semantic status
  // tones are derived; the existing companion renderer is unaffected.
  static const ivoryFoundry = UriColors(
    ink: Color(0xFF292821),
    inkSoft: Color(0xFF5C574C),
    inkFaint: Color(0xFF5C574C),
    canvas: Color(0xFFE9E3D5),
    surface: Color(0xFFF2EDE2),
    surfaceSunken: Color(0xFFDCD2BF),
    border: Color(0xFF89795F),
    accent: Color(0xFF77603C),
    accentSoft: Color(0xFFE0D0AD),
    accentInk: Color(0xFF554329),
    success: Color(0xFF36513A),
    successSoft: Color(0xFFDEE5D9),
    warning: Color(0xFF735117),
    warningSoft: Color(0xFFF1E2BE),
    danger: Color(0xFF933D33),
    dangerSoft: Color(0xFFF0DED8),
  );
  static const snowArchive = UriColors(
    ink: Color(0xFF292A27),
    inkSoft: Color(0xFF5B5C56),
    inkFaint: Color(0xFF5B5C56),
    canvas: Color(0xFFF5F4EF),
    surface: Color(0xFFFFFEFA),
    surfaceSunken: Color(0xFFE7E4DA),
    border: Color(0xFF858674),
    accent: Color(0xFF776541),
    accentSoft: Color(0xFFE4D9C1),
    accentInk: Color(0xFF554329),
    success: Color(0xFF36513A),
    successSoft: Color(0xFFDEE5D9),
    warning: Color(0xFF735117),
    warningSoft: Color(0xFFF1E2BE),
    danger: Color(0xFF933D33),
    dangerSoft: Color(0xFFF0DED8),
  );
  static const ashLimestone = UriColors(
    ink: Color(0xFF262824),
    inkSoft: Color(0xFF43473E),
    inkFaint: Color(0xFF43473E),
    canvas: Color(0xFFBABBB5),
    surface: Color(0xFFD1D0C7),
    surfaceSunken: Color(0xFFA5A69D),
    border: Color(0xFF62665A),
    accent: Color(0xFF55462D),
    accentSoft: Color(0xFFD6C8A6),
    accentInk: Color(0xFF443820),
    success: Color(0xFF29432D),
    successSoft: Color(0xFFBCC9B6),
    warning: Color(0xFF59400F),
    warningSoft: Color(0xFFD6C8A6),
    danger: Color(0xFF793128),
    dangerSoft: Color(0xFFD8BCB5),
  );

  /// The active palette for [context], resolved through the current
  /// theme exactly like `Theme.of(context).textTheme` — never a bare
  /// static field, so it always tracks the selected theme correctly.
  /// Falls back to [lightProfessional] only when no [MaterialApp] has
  /// installed the extension yet (e.g. a widget test that builds a bare
  /// widget outside a themed app), never as a "usual" path.
  static UriColors of(BuildContext context) {
    return Theme.of(context).extension<UriColors>() ?? lightProfessional;
  }

  @override
  UriColors copyWith({
    Color? ink,
    Color? inkSoft,
    Color? inkFaint,
    Color? canvas,
    Color? surface,
    Color? surfaceSunken,
    Color? border,
    Color? accent,
    Color? accentSoft,
    Color? accentInk,
    Color? success,
    Color? successSoft,
    Color? warning,
    Color? warningSoft,
    Color? danger,
    Color? dangerSoft,
  }) {
    return UriColors(
      ink: ink ?? this.ink,
      inkSoft: inkSoft ?? this.inkSoft,
      inkFaint: inkFaint ?? this.inkFaint,
      canvas: canvas ?? this.canvas,
      surface: surface ?? this.surface,
      surfaceSunken: surfaceSunken ?? this.surfaceSunken,
      border: border ?? this.border,
      accent: accent ?? this.accent,
      accentSoft: accentSoft ?? this.accentSoft,
      accentInk: accentInk ?? this.accentInk,
      success: success ?? this.success,
      successSoft: successSoft ?? this.successSoft,
      warning: warning ?? this.warning,
      warningSoft: warningSoft ?? this.warningSoft,
      danger: danger ?? this.danger,
      dangerSoft: dangerSoft ?? this.dangerSoft,
    );
  }

  @override
  UriColors lerp(ThemeExtension<UriColors>? other, double t) {
    if (other is! UriColors) return this;
    return UriColors(
      ink: Color.lerp(ink, other.ink, t)!,
      inkSoft: Color.lerp(inkSoft, other.inkSoft, t)!,
      inkFaint: Color.lerp(inkFaint, other.inkFaint, t)!,
      canvas: Color.lerp(canvas, other.canvas, t)!,
      surface: Color.lerp(surface, other.surface, t)!,
      surfaceSunken: Color.lerp(surfaceSunken, other.surfaceSunken, t)!,
      border: Color.lerp(border, other.border, t)!,
      accent: Color.lerp(accent, other.accent, t)!,
      accentSoft: Color.lerp(accentSoft, other.accentSoft, t)!,
      accentInk: Color.lerp(accentInk, other.accentInk, t)!,
      success: Color.lerp(success, other.success, t)!,
      successSoft: Color.lerp(successSoft, other.successSoft, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      warningSoft: Color.lerp(warningSoft, other.warningSoft, t)!,
      danger: Color.lerp(danger, other.danger, t)!,
      dangerSoft: Color.lerp(dangerSoft, other.dangerSoft, t)!,
    );
  }
}

/// Consistent spacing scale so cards, sections, and gaps stay visually
/// disciplined instead of ad hoc. Pure numeric design tokens — nothing
/// here varies with brightness, so (unlike [UriColors]) these stay
/// plain compile-time constants.
class UriSpace {
  UriSpace._();
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 16;
  static const double lg = 24;
  static const double xl = 32;
  static const double xxl = 48;
}

class UriRadius {
  UriRadius._();
  static const double sm = 10;
  static const double md = 16;
  static const double lg = 22;
}

/// Semantic typography roles for the compact dashboard.  These derive from
/// the active [TextTheme] so every surface shares the application font,
/// weight, spacing, and brightness-aware colours rather than introducing
/// local font families.
extension UriDashboardTextTheme on TextTheme {
  TextStyle get metricValue => headlineSmall!.copyWith(
    fontWeight: FontWeight.w700,
    letterSpacing: -0.2,
    height: 1.1,
  );

  TextStyle get cardHeader => titleMedium!.copyWith(
    fontWeight: FontWeight.w600,
    letterSpacing: 0,
    height: 1.25,
  );

  TextStyle get metricCaption => labelSmall!.copyWith(
    fontWeight: FontWeight.w500,
    letterSpacing: 0,
    height: 1.35,
  );

  TextStyle get keyValue => bodyMedium!.copyWith(fontSize: 11, height: 1.35);

  TextStyle get footerCaption => labelSmall!.copyWith(
    fontSize: 9,
    fontWeight: FontWeight.w500,
    letterSpacing: 0,
    height: 1.3,
  );
}

/// Layout breakpoints shared by every screen that adapts between a
/// compact phone layout and a wider tablet/desktop one (Settings'
/// master-detail, Home's dashboard grid, the app shell's sidebar vs.
/// bottom nav) — one definition so "wide" means the same width
/// everywhere rather than each screen picking its own threshold.
class UriBreakpoints {
  UriBreakpoints._();

  /// Sidebar navigation, dashboard grid, Settings master-detail all
  /// switch on here — matches [AppShell]'s pre-existing threshold.
  static const double wide = 900;

  static bool isWide(BuildContext context) =>
      MediaQuery.sizeOf(context).width >= wide;
}

/// Hybrid UI Frozen Blueprint §4.1/§4.7 — the 4 real Appearance choices,
/// plus `system` (follows the OS light/dark signal by resolving to
/// [UriColors.graphite] or [UriColors.lightProfessional] — the same pair
/// this app's old binary dark/light default mapped to — until the user
/// makes an explicit 4-theme choice; see [ThemeStore]).
enum UriThemeChoice {
  ivoryFoundry,
  snowArchive,
  ashLimestone,
  system,
  graphite,
  deepNavy,
  slateTeal,
  lightProfessional,

  /// Living Companion phase: Dark Glass + Cyan (see [UriColors.obsidianCyan]).
  obsidianCyan,

  /// Companion themes. Selected by choosing a companion rather than from the
  /// Appearance list alone, but listed here so one resolver serves both.
  solarEmber,
  sakuraBloom,
  lunarSilver,
}

extension UriThemeChoiceLabel on UriThemeChoice {
  String get label => switch (this) {
    UriThemeChoice.ivoryFoundry => 'Ivory Foundry',
    UriThemeChoice.snowArchive => 'Snow Archive',
    UriThemeChoice.ashLimestone => 'Ash & Limestone',
    UriThemeChoice.system => 'System',
    UriThemeChoice.graphite => 'Graphite',
    UriThemeChoice.deepNavy => 'Deep Navy',
    UriThemeChoice.slateTeal => 'Slate + Teal',
    UriThemeChoice.lightProfessional => 'Light Professional',
    UriThemeChoice.obsidianCyan => 'Obsidian Cyan',
    UriThemeChoice.solarEmber => 'Solar Ember',
    UriThemeChoice.sakuraBloom => 'Sakura Bloom',
    UriThemeChoice.lunarSilver => 'Lunar Silver',
  };

  /// The circular swatch color shown for this choice in the topbar and
  /// the Appearance picker — the same accent hex named in Blueprint
  /// §4.1 for the 4 real themes; `system` has no swatch of its own.
  Color? get swatch => switch (this) {
    UriThemeChoice.ivoryFoundry => UriColors.ivoryFoundry.accent,
    UriThemeChoice.snowArchive => UriColors.snowArchive.accent,
    UriThemeChoice.ashLimestone => UriColors.ashLimestone.accent,
    UriThemeChoice.system => null,
    UriThemeChoice.graphite => UriColors.graphite.accent,
    UriThemeChoice.deepNavy => UriColors.deepNavy.accent,
    UriThemeChoice.slateTeal => UriColors.slateTeal.accent,
    UriThemeChoice.lightProfessional => UriColors.lightProfessional.accent,
    UriThemeChoice.obsidianCyan => UriColors.obsidianCyan.accent,
    UriThemeChoice.solarEmber => UriColors.solarEmber.accent,
    UriThemeChoice.sakuraBloom => UriColors.sakuraBloom.accent,
    UriThemeChoice.lunarSilver => UriColors.lunarSilver.accent,
  };
}

/// Resolves a [UriThemeChoice] to the actual palette to render.
/// [platformBrightness] only matters for [UriThemeChoice.system].
UriColors resolveUriColors(
  UriThemeChoice choice,
  Brightness platformBrightness,
) {
  switch (choice) {
    case UriThemeChoice.ivoryFoundry:
      return UriColors.ivoryFoundry;
    case UriThemeChoice.snowArchive:
      return UriColors.snowArchive;
    case UriThemeChoice.ashLimestone:
      return UriColors.ashLimestone;
    case UriThemeChoice.system:
      return platformBrightness == Brightness.dark
          ? UriColors.graphite
          : UriColors.lightProfessional;
    case UriThemeChoice.graphite:
      return UriColors.graphite;
    case UriThemeChoice.deepNavy:
      return UriColors.deepNavy;
    case UriThemeChoice.slateTeal:
      return UriColors.slateTeal;
    case UriThemeChoice.lightProfessional:
      return UriColors.lightProfessional;
    case UriThemeChoice.obsidianCyan:
      return UriColors.obsidianCyan;
    case UriThemeChoice.solarEmber:
      return UriColors.solarEmber;
    case UriThemeChoice.sakuraBloom:
      return UriColors.sakuraBloom;
    case UriThemeChoice.lunarSilver:
      return UriColors.lunarSilver;
  }
}

ThemeData buildUriTheme(UriColors palette) {
  final brightness = ThemeData.estimateBrightnessForColor(palette.canvas);

  final base = ThemeData(
    useMaterial3: true,
    brightness: brightness,
    colorScheme: ColorScheme.fromSeed(
      seedColor: palette.accent,
      brightness: brightness,
      surface: palette.surface,
    ),
    scaffoldBackgroundColor: palette.canvas,
    fontFamily: 'Segoe UI',
  );

  final textTheme = base.textTheme.copyWith(
    displaySmall: TextStyle(
      fontSize: 34,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.8,
      color: palette.ink,
      height: 1.15,
    ),
    headlineMedium: TextStyle(
      fontSize: 24,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.4,
      color: palette.ink,
      height: 1.2,
    ),
    headlineSmall: TextStyle(
      fontSize: 19,
      fontWeight: FontWeight.w700,
      letterSpacing: -0.2,
      color: palette.ink,
      height: 1.25,
    ),
    titleMedium: TextStyle(
      fontSize: 15,
      fontWeight: FontWeight.w600,
      color: palette.ink,
      height: 1.3,
    ),
    bodyLarge: TextStyle(
      fontSize: 15,
      fontWeight: FontWeight.w400,
      color: palette.inkSoft,
      height: 1.5,
    ),
    bodyMedium: TextStyle(
      fontSize: 13.5,
      fontWeight: FontWeight.w400,
      color: palette.inkSoft,
      height: 1.5,
    ),
    labelLarge: TextStyle(
      fontSize: 13,
      fontWeight: FontWeight.w600,
      color: palette.ink,
      letterSpacing: 0.1,
    ),
    labelSmall: TextStyle(
      fontSize: 11.5,
      fontWeight: FontWeight.w600,
      color: palette.inkFaint,
      letterSpacing: 0.4,
    ),
  );

  return base.copyWith(
    extensions: [palette, UriGlass.fromPalette(palette)],
    textTheme: textTheme,
    dividerColor: palette.border,
    cardTheme: CardThemeData(
      color: palette.surface,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(UriRadius.md),
        side: BorderSide(color: palette.border),
      ),
      margin: EdgeInsets.zero,
    ),
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: palette.accent,
        foregroundColor: brightness == Brightness.dark
            ? palette.canvas
            : Colors.white,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(UriRadius.sm),
        ),
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: palette.ink,
        side: BorderSide(color: palette.border),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(UriRadius.sm),
        ),
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: palette.inkSoft,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        textStyle: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: palette.surface,
      contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(UriRadius.sm),
        borderSide: BorderSide(color: palette.border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(UriRadius.sm),
        borderSide: BorderSide(color: palette.border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(UriRadius.sm),
        borderSide: BorderSide(color: palette.accent, width: 1.4),
      ),
      hintStyle: TextStyle(color: palette.inkFaint),
    ),
  );
}
