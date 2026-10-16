import '../../theme/uri_theme.dart';
import 'companion_orb.dart';
import 'companion_preferences.dart';
import 'energy_orb.dart';

/// Catalog adapter over accepted renderers, not a second style system.
/// Future model renderers can declare their own genuine viewer capabilities.
class CompanionDesign {
  const CompanionDesign(this.id, this.choice, {this.classicVariant});
  final String id;
  final CompanionChoice choice;
  final OrbVariant? classicVariant;
  String get displayName => classicVariant?.label ?? choice.label;
  String get rendererReference =>
      choice.identity?.shaderAsset ?? 'EnergyOrb/${classicVariant!.name}';
  UriThemeChoice get originalTheme =>
      CompanionPreferences.themeFor(choice, UriThemeChoice.graphite);
  String get originalThemeLabel => choice.isClassic
      ? 'Legacy free theme (Graphite fallback)'
      : originalTheme.label;
  bool get supportsModelRotation => false;
  static final List<CompanionDesign> installed = List.unmodifiable([
    for (final id in CompanionIdentity.values)
      CompanionDesign(id.name, CompanionChoice.living(id)),
    for (final variant in OrbVariant.values)
      CompanionDesign(
        'classic-${variant.name}',
        const CompanionChoice.classic(),
        classicVariant: variant,
      ),
  ]);
  static CompanionDesign active(CompanionPreferences prefs) =>
      installed.firstWhere(
        (d) =>
            d.choice == prefs.choice &&
            (!d.choice.isClassic || d.classicVariant == prefs.classicVariant),
        orElse: () => installed.first,
      );
  void applyTo(CompanionPreferences prefs) {
    if (classicVariant != null) prefs.setClassicVariant(classicVariant!);
    prefs.select(choice);
  }
}

/// Legacy neon/teal palettes still decode saved preferences. They are no
/// longer offered by the V2 selector, per the owner's visual direction.
const installedInterfaceThemes = [
  UriThemeChoice.ivoryFoundry,
  UriThemeChoice.snowArchive,
  UriThemeChoice.ashLimestone,
  UriThemeChoice.system,
  UriThemeChoice.graphite,
  UriThemeChoice.deepNavy,
  UriThemeChoice.lightProfessional,
  UriThemeChoice.solarEmber,
  UriThemeChoice.sakuraBloom,
  UriThemeChoice.lunarSilver,
];
