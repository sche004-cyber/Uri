import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';

/// Push-to-enable controls for the Brain Quick Controls
/// (UI-CONTROLS-TYPO-20261018).
///
/// * [QcToggle]: one button, one click enables, the next disables. Its
///   look follows [QcVisual], which the caller derives from the VERIFIED
///   runtime state (never from the click itself).
///
/// States: off (subdued), on (accent fill + a static glow), loading
/// (spinner, no glow), error (danger outline), disabled (faint, not
/// interactive), plus hover, pressed and keyboard-focus feedback while
/// interactive. The glow is one static [BoxShadow]; the only animation is a
/// 140 ms transition on a state change (no ticker runs while idle).
///
/// Accessibility (review R1-01): the toggle is in the focus traversal order
/// (Tab), Enter and Space activate it, a focus ring shows where the keyboard
/// is, and a screen reader gets a toggle button with its label, state and a
/// tap action.
enum QcVisual { off, on, loading, error }

class QcStyle {
  QcStyle._();
  static const Duration change = Duration(milliseconds: 140);
  static const double radius = 999;

  /// The enabled glow: one soft accent shadow, stronger on hover.
  static List<BoxShadow> glow(UriColors c, {bool hover = false}) => [
        // ui-1 live review: .32 / blur 9 read as faint on the dark companion themes; still one static shadow.
        BoxShadow(color: c.accent.withValues(alpha: hover ? .55 : .42), blurRadius: hover ? 14 : 12, spreadRadius: .5),
      ];

  static Color fill(UriColors c, QcVisual v, {bool hover = false, bool pressed = false, bool enabled = true}) {
    if (v == QcVisual.on) return pressed ? Color.alphaBlend(c.accent.withValues(alpha: .18), c.accentSoft) : c.accentSoft;
    if (!enabled) return Colors.transparent;
    if (pressed) return c.ink.withValues(alpha: .12);
    if (hover) return c.ink.withValues(alpha: .06);
    return Colors.transparent;
  }

  static Color border(UriColors c, QcVisual v, {bool hover = false, bool enabled = true}) => switch (v) {
        QcVisual.on => c.accent,
        QcVisual.error => c.danger,
        QcVisual.loading => c.accent.withValues(alpha: .55),
        QcVisual.off => !enabled ? c.border.withValues(alpha: .6) : hover ? c.inkFaint : c.border,
      };

  /// The keyboard focus ring: drawn inside the control's edge, so focus never
  /// changes the layout. Ink, not accent, so it differs from the "on" border.
  static BoxDecoration focusRing(UriColors c) => BoxDecoration(
        border: Border.all(color: c.ink, width: 2),
        borderRadius: BorderRadius.circular(radius),
      );

  static Color ink(UriColors c, QcVisual v, {bool enabled = true}) => switch (v) {
        QcVisual.on => c.accentInk,
        QcVisual.error => c.danger,
        QcVisual.loading => c.inkSoft,
        QcVisual.off => enabled ? c.inkSoft : c.inkFaint,
      };

  static TextStyle text(BuildContext context, Color color, {bool strong = false}) =>
      Theme.of(context).textTheme.labelMedium!.copyWith(
            fontSize: UriType.label,
            color: color,
            fontWeight: strong ? FontWeight.w600 : FontWeight.w500,
            height: 1.2,
            letterSpacing: 0,
          );
}

/// Hover / pressed tracking.
mixin _Pointer<T extends StatefulWidget> on State<T> {
  bool hover = false;
  bool pressed = false;
  void setHover(bool v) => hover == v ? null : setState(() => hover = v);
  void setPressed(bool v) => pressed == v ? null : setState(() => pressed = v);
}

class QcToggle extends StatefulWidget {
  const QcToggle({
    super.key,
    required this.icon,
    required this.label,
    required this.visual,
    required this.tooltip,
    this.onPressed,
    this.status,
  });

  final IconData icon;
  final String label;

  /// A short qualifier after the label ("Paused", "starting"), or null.
  final String? status;
  final QcVisual visual;
  final String tooltip;

  /// Null = disabled (the tooltip says why).
  final VoidCallback? onPressed;

  @override
  State<QcToggle> createState() => _QcToggleState();
}

class _QcToggleState extends State<QcToggle> with _Pointer {
  bool focused = false;

  late final Map<Type, Action<Intent>> _actions = {
    ActivateIntent: CallbackAction<ActivateIntent>(onInvoke: (_) => _activate()),
  };

  bool get _enabled => widget.onPressed != null && widget.visual != QcVisual.loading;

  Object? _activate() {
    if (_enabled) widget.onPressed!.call();
    return null;
  }

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final v = widget.visual;
    final enabled = _enabled;
    final on = v == QcVisual.on;
    final ink = QcStyle.ink(c, v, enabled: enabled);
    final h = enabled && hover;
    return Semantics(
      button: true,
      toggled: on,
      enabled: enabled,
      focusable: enabled,
      focused: enabled && focused,
      label: widget.label,
      value:
          widget.status ??
          (v == QcVisual.loading
              ? 'changing'
              : v == QcVisual.error
              ? 'error'
              : null),
      hint: widget.tooltip,
      onTap: enabled ? _activate : null,
      excludeSemantics: true,
      child: FocusableActionDetector(
        enabled: enabled,
        actions: _actions,
        onShowFocusHighlight: (f) => focused == f ? null : setState(() => focused = f),
        child: MouseRegion(
          cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
          onEnter: (_) => setHover(true),
          onExit: (_) => setHover(false),
          child: Tooltip(
            message: widget.tooltip,
            waitDuration: const Duration(milliseconds: 400),
            child: GestureDetector(
              behavior: HitTestBehavior.opaque,
              onTapDown: enabled ? (_) => setPressed(true) : null,
              onTapUp: enabled ? (_) => setPressed(false) : null,
              onTapCancel: enabled ? () => setPressed(false) : null,
              onTap: enabled ? _activate : null,
              child: AnimatedContainer(
                duration: QcStyle.change,
                padding: const EdgeInsets.fromLTRB(9, 4, 10, 4),
                decoration: BoxDecoration(
                  color: QcStyle.fill(c, v, hover: h, pressed: enabled && pressed, enabled: enabled),
                  border: Border.all(
                    color: QcStyle.border(c, v, hover: h, enabled: enabled),
                  ),
                  borderRadius: BorderRadius.circular(QcStyle.radius),
                  boxShadow: on ? QcStyle.glow(c, hover: h) : const [],
                ),
                foregroundDecoration: enabled && focused ? QcStyle.focusRing(c) : null,
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (v == QcVisual.loading)
                      SizedBox(
                        width: 12,
                        height: 12,
                        child: CircularProgressIndicator(strokeWidth: 1.5, color: c.accent),
                      )
                    else
                      Icon(
                        v == QcVisual.error ? Icons.error_outline_rounded : widget.icon,
                        size: 14,
                        color: on ? c.accent : ink,
                      ),
                    const SizedBox(width: 5),
                    Flexible(
                      child: Text.rich(
                        TextSpan(
                          children: [
                            TextSpan(
                              text: widget.label,
                              style: QcStyle.text(context, ink, strong: on),
                            ),
                            if (widget.status != null)
                              TextSpan(
                                text: ' · ${widget.status}',
                                style: QcStyle.text(context, on ? c.accentInk : c.inkFaint),
                              ),
                          ],
                        ),
                        overflow: TextOverflow.ellipsis,
                        maxLines: 1,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
