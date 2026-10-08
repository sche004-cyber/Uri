import 'dart:ui' show lerpDouble;

import 'package:flutter/material.dart';

import 'uri_theme.dart';

/// "Dark Glass + Cyan" surface tokens for the Living Companion UI.
///
/// A [ThemeExtension] next to [UriColors]: every value is derived from
/// the active palette by [UriGlass.fromPalette], so the living widgets
/// keep working under the four user-approved Hybrid themes (Graphite,
/// Deep Navy, Slate + Teal, Light Professional) and simply look best
/// under [UriColors.obsidianCyan]. Nothing in `lib/living/` hardcodes a
/// cyan hex; the orb, glows and glass all read this extension.
@immutable
class UriGlass extends ThemeExtension<UriGlass> {
  const UriGlass({
    required this.fill,
    required this.fillStrong,
    required this.border,
    required this.highlight,
    required this.glow,
    required this.glowSoft,
    required this.ambientTop,
    required this.ambientBottom,
    required this.blurSigma,
    required this.isDark,
    required this.specular,
  });

  /// Translucent panel fill (over the ambient background).
  final Color fill;

  /// Slightly denser fill for elevated/hovered panels and the composer.
  final Color fillStrong;

  /// Hairline panel border.
  final Color border;

  /// One-pixel top-edge light catch that sells the glass.
  final Color highlight;

  /// Illumination color (the orb core, focus rings, volumetric light).
  final Color glow;

  /// Low-alpha version of [glow] for halos and ambient spill.
  final Color glowSoft;

  /// Background gradient end points (deep charcoal / near-black blue).
  final Color ambientTop;
  final Color ambientBottom;

  /// Backdrop blur strength used by [GlassPanel] when effects are on.
  final double blurSigma;

  final bool isDark;

  /// Brightest light the orb may show (specular highlights, hot core).
  /// A token so the painter never names a literal colour.
  final Color specular;

  static UriGlass of(BuildContext context) =>
      Theme.of(context).extension<UriGlass>() ??
      UriGlass.fromPalette(UriColors.of(context));

  /// Derives glass tokens from a palette. On dark palettes the glass is
  /// a faint white veil over the canvas; on the light palette it is a
  /// faint ink veil, so the same widgets stay legible.
  factory UriGlass.fromPalette(UriColors p) {
    final dark =
        ThemeData.estimateBrightnessForColor(p.canvas) == Brightness.dark;
    final veil = dark ? Colors.white : p.ink;
    return UriGlass(
      fill: veil.withValues(alpha: dark ? 0.045 : 0.035),
      fillStrong: veil.withValues(alpha: dark ? 0.08 : 0.06),
      border: veil.withValues(alpha: dark ? 0.10 : 0.12),
      highlight: veil.withValues(alpha: dark ? 0.20 : 0.35),
      glow: p.accent,
      glowSoft: p.accent.withValues(alpha: 0.18),
      ambientTop: Color.lerp(p.canvas, p.accent, dark ? 0.06 : 0.03)!,
      ambientBottom: p.canvas,
      blurSigma: 18,
      isDark: dark,
      specular: dark ? const Color(0xFFFFFFFF) : const Color(0xFFF4FAFF),
    );
  }

  @override
  UriGlass copyWith({
    Color? fill,
    Color? fillStrong,
    Color? border,
    Color? highlight,
    Color? glow,
    Color? glowSoft,
    Color? ambientTop,
    Color? ambientBottom,
    double? blurSigma,
    bool? isDark,
    Color? specular,
  }) {
    return UriGlass(
      fill: fill ?? this.fill,
      fillStrong: fillStrong ?? this.fillStrong,
      border: border ?? this.border,
      highlight: highlight ?? this.highlight,
      glow: glow ?? this.glow,
      glowSoft: glowSoft ?? this.glowSoft,
      ambientTop: ambientTop ?? this.ambientTop,
      ambientBottom: ambientBottom ?? this.ambientBottom,
      blurSigma: blurSigma ?? this.blurSigma,
      isDark: isDark ?? this.isDark,
      specular: specular ?? this.specular,
    );
  }

  @override
  UriGlass lerp(ThemeExtension<UriGlass>? other, double t) {
    if (other is! UriGlass) return this;
    return UriGlass(
      fill: Color.lerp(fill, other.fill, t)!,
      fillStrong: Color.lerp(fillStrong, other.fillStrong, t)!,
      border: Color.lerp(border, other.border, t)!,
      highlight: Color.lerp(highlight, other.highlight, t)!,
      glow: Color.lerp(glow, other.glow, t)!,
      glowSoft: Color.lerp(glowSoft, other.glowSoft, t)!,
      ambientTop: Color.lerp(ambientTop, other.ambientTop, t)!,
      ambientBottom: Color.lerp(ambientBottom, other.ambientBottom, t)!,
      blurSigma: lerpDouble(blurSigma, other.blurSigma, t)!,
      isDark: t < 0.5 ? isDark : other.isDark,
      specular: Color.lerp(specular, other.specular, t)!,
    );
  }
}

/// Motion tokens shared by the living UI so every transition has the
/// same feel. Durations are deliberately short: the orb is the only
/// thing that may move continuously; panels move once, then rest.
class UriMotion {
  UriMotion._();
  static const Duration fast = Duration(milliseconds: 160);
  static const Duration mode = Duration(milliseconds: 520);
  static const Duration orbState = Duration(milliseconds: 650);
  static const Curve enter = Curves.easeOutCubic;
  static const Curve move = Curves.easeInOutCubicEmphasized;
}
