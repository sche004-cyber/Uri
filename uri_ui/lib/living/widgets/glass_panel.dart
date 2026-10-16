import 'dart:ui' as ui;

import 'package:flutter/material.dart';

import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../companion/effects_settings.dart';

/// A restrained glass surface: translucent fill, hairline border, a
/// one-pixel top highlight, and (effects on) a backdrop blur.
///
/// Rules that keep the look calm: never nest a [GlassPanel] inside
/// another; keep to a handful per screen; the blur is the only costly
/// part and is skipped entirely under reduced effects, where the panel
/// becomes a plain translucent surface with the same border.
class GlassPanel extends StatelessWidget {
  const GlassPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(UriSpace.md),
    this.radius = UriRadius.md,
    this.strong = false,
    this.glowBorder = false,
    this.clip = true,
    this.blur = false,
    this.borderless = false,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final double radius;

  /// Denser fill for the composer / elevated panels.
  final bool strong;

  /// Accent-tinted border (focused or "needs you" panels).
  final bool glowBorder;

  final bool clip;

  /// Backdrop blur. Off by default: over the flat ambient background a
  /// blur adds cost and no depth (profile run: eight blurred tiles cost
  /// 22 ms raster p95 on the dashboard). Enable only for a panel that
  /// floats over moving content, e.g. the composer over the conversation.
  final bool blur;
  final bool borderless;

  @override
  Widget build(BuildContext context) {
    final glass = UriGlass.of(context);
    final effects = EffectsSettings.of(context);
    final border = BorderRadius.circular(radius);

    Widget surface = DecoratedBox(
      decoration: BoxDecoration(
        color: strong ? glass.fillStrong : glass.fill,
        borderRadius: border,
        border: borderless
            ? null
            : Border.all(
                color: glowBorder
                    ? glass.glow.withValues(alpha: 0.45)
                    : glass.border,
              ),
      ),
      child: Stack(
        children: [
          // Top-edge light catch.
          if (!borderless)
            Positioned(
              left: radius,
              right: radius,
              top: 0,
              child: Container(height: 1, color: glass.highlight),
            ),
          // Transparent Material so ListTiles/ink inside a panel paint
          // correctly (they need a Material between them and the fill).
          Material(
            type: MaterialType.transparency,
            child: Padding(padding: padding, child: child),
          ),
        ],
      ),
    );

    if (blur && !effects.reducedEffects) {
      surface = BackdropFilter(
        filter: ui.ImageFilter.blur(
          sigmaX: glass.blurSigma,
          sigmaY: glass.blurSigma,
        ),
        child: surface,
      );
    }
    if (!clip) return surface;
    return ClipRRect(borderRadius: border, child: surface);
  }
}

/// The deep ambient background every living mode sits on: a vertical
/// charcoal gradient with one soft volumetric light pool near [lightAt].
class AmbientBackground extends StatelessWidget {
  const AmbientBackground({
    super.key,
    required this.child,
    this.lightAt = const Alignment(0, -0.6),
    this.lightStrength = 1,
  });

  final Widget child;
  final Alignment lightAt;
  final double lightStrength;

  @override
  Widget build(BuildContext context) {
    final glass = UriGlass.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [glass.ambientTop, glass.ambientBottom],
        ),
      ),
      child: Stack(
        fit: StackFit.expand,
        children: [
          IgnorePointer(
            child: AnimatedAlign(
              duration: UriMotion.mode,
              curve: UriMotion.move,
              alignment: lightAt,
              child: AnimatedContainer(
                duration: UriMotion.mode,
                width: 900 * lightStrength,
                height: 900 * lightStrength,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      glass.glow.withValues(alpha: 0.10 * lightStrength),
                      glass.glow.withValues(alpha: 0.0),
                    ],
                  ),
                ),
              ),
            ),
          ),
          child,
        ],
      ),
    );
  }
}
