import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';

/// Push-to-enable controls for the Brain Quick Controls
/// (UI-CONTROLS-TYPO-20261018).
///
/// * [QcToggle]: one button, one click enables, the next disables. Its
///   look follows [QcVisual], which the caller derives from the VERIFIED
///   runtime state (never from the click itself).
/// * [QcSegmented]: a selection between mutually exclusive values (the
///   context size). The selected segment has the same enabled look.
///
/// States: off (subdued), on (accent fill + a static glow), loading
/// (spinner, no glow), error (danger outline), disabled (faint, not
/// interactive), plus hover and pressed feedback while interactive. The
/// glow is one static [BoxShadow]; the only animation is a 140 ms
/// transition on a state change (no ticker runs while idle).
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

/// Hover / pressed tracking shared by the toggle and the segments.
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
    this.trailing,
  });

  final IconData icon;
  final String label;

  /// A short qualifier after the label ("Auto", "starting"), or null.
  final String? status;
  final QcVisual visual;
  final String tooltip;

  /// Null = disabled (the tooltip says why).
  final VoidCallback? onPressed;

  /// An optional attached control (e.g. a small menu caret).
  final Widget? trailing;

  @override
  State<QcToggle> createState() => _QcToggleState();
}

class _QcToggleState extends State<QcToggle> with _Pointer {
  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final v = widget.visual;
    final enabled = widget.onPressed != null && v != QcVisual.loading;
    final on = v == QcVisual.on;
    final ink = QcStyle.ink(c, v, enabled: enabled);
    final h = enabled && hover;
    return Semantics(
      button: true,
      toggled: on,
      enabled: enabled,
      label: widget.label,
      value: widget.status,
      excludeSemantics: true,
      child: Tooltip(
        message: widget.tooltip,
        waitDuration: const Duration(milliseconds: 400),
        child: AnimatedContainer(
          duration: QcStyle.change,
          decoration: BoxDecoration(
            color: QcStyle.fill(c, v, hover: h, pressed: enabled && pressed, enabled: enabled),
            border: Border.all(color: QcStyle.border(c, v, hover: h, enabled: enabled)),
            borderRadius: BorderRadius.circular(QcStyle.radius),
            boxShadow: on ? QcStyle.glow(c, hover: h) : const [],
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Flexible(
              child: MouseRegion(
                cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
                onEnter: (_) => setHover(true),
                onExit: (_) => setHover(false),
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTapDown: enabled ? (_) => setPressed(true) : null,
                  onTapUp: enabled ? (_) => setPressed(false) : null,
                  onTapCancel: enabled ? () => setPressed(false) : null,
                  onTap: enabled ? widget.onPressed : null,
                  child: Padding(
                    padding: EdgeInsets.fromLTRB(9, 4, widget.trailing == null ? 10 : 4, 4),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      if (v == QcVisual.loading)
                        SizedBox(
                            width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 1.5, color: c.accent))
                      else
                        Icon(v == QcVisual.error ? Icons.error_outline_rounded : widget.icon,
                            size: 14, color: on ? c.accent : ink),
                      const SizedBox(width: 5),
                      Flexible(
                        child: Text.rich(
                          TextSpan(children: [
                            TextSpan(text: widget.label, style: QcStyle.text(context, ink, strong: on)),
                            if (widget.status != null)
                              TextSpan(
                                  text: ' · ${widget.status}',
                                  style: QcStyle.text(context, on ? c.accentInk : c.inkFaint)),
                          ]),
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                        ),
                      ),
                    ]),
                  ),
                ),
              ),
            ),
            ?widget.trailing,
          ]),
        ),
      ),
    );
  }
}

/// One choice of a [QcSegmented].
class QcSegment {
  const QcSegment({required this.key, required this.label, required this.tooltip, this.selected = false, this.onTap});
  final Key key;
  final String label;
  final String tooltip;
  final bool selected;

  /// Null = not choosable (the tooltip says why).
  final VoidCallback? onTap;
}

class QcSegmented extends StatelessWidget {
  const QcSegmented({
    super.key,
    required this.icon,
    required this.label,
    required this.segments,
    required this.tooltip,
    this.status,
    this.loading = false,
    this.error = false,
  });

  final IconData icon;
  final String label;
  final String? status;
  final String tooltip;
  final List<QcSegment> segments;
  final bool loading;
  final bool error;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final v = loading ? QcVisual.loading : error ? QcVisual.error : QcVisual.off;
    final anyEnabled = !loading && segments.any((s) => s.onTap != null);
    final ink = QcStyle.ink(c, v, enabled: anyEnabled || segments.any((s) => s.selected));
    return Semantics(
      container: true,
      label: '$label${status == null ? '' : ', $status'}',
      child: AnimatedContainer(
        duration: QcStyle.change,
        padding: const EdgeInsets.all(2),
        decoration: BoxDecoration(
          border: Border.all(color: QcStyle.border(c, v, enabled: anyEnabled)),
          borderRadius: BorderRadius.circular(QcStyle.radius),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Tooltip(
            message: tooltip,
            waitDuration: const Duration(milliseconds: 400),
            child: Padding(
              padding: const EdgeInsets.fromLTRB(7, 2, 5, 2),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                if (loading)
                  SizedBox(width: 12, height: 12, child: CircularProgressIndicator(strokeWidth: 1.5, color: c.accent))
                else
                  Icon(error ? Icons.error_outline_rounded : icon, size: 14, color: ink),
                const SizedBox(width: 5),
                Text(status == null ? label : '$label · $status', style: QcStyle.text(context, ink)),
              ]),
            ),
          ),
          for (final s in segments)
            Padding(
              padding: const EdgeInsets.only(left: 2),
              child: _Segment(segment: s, loading: loading),
            ),
        ]),
      ),
    );
  }
}

class _Segment extends StatefulWidget {
  const _Segment({required this.segment, required this.loading});
  final QcSegment segment;
  final bool loading;

  @override
  State<_Segment> createState() => _SegmentState();
}

class _SegmentState extends State<_Segment> with _Pointer {
  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final s = widget.segment;
    final enabled = s.onTap != null && !s.selected && !widget.loading;
    final v = s.selected && !widget.loading ? QcVisual.on : QcVisual.off;
    final h = enabled && hover;
    return Semantics(
      key: s.key,
      button: true,
      selected: s.selected,
      enabled: enabled || s.selected,
      label: s.label,
      excludeSemantics: true,
      child: Tooltip(
        message: s.tooltip,
        waitDuration: const Duration(milliseconds: 400),
        child: MouseRegion(
          cursor: enabled ? SystemMouseCursors.click : SystemMouseCursors.basic,
          onEnter: (_) => setHover(true),
          onExit: (_) => setHover(false),
          child: GestureDetector(
            behavior: HitTestBehavior.opaque,
            onTapDown: enabled ? (_) => setPressed(true) : null,
            onTapUp: enabled ? (_) => setPressed(false) : null,
            onTapCancel: enabled ? () => setPressed(false) : null,
            onTap: enabled ? s.onTap : null,
            child: AnimatedContainer(
              duration: QcStyle.change,
              padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
              decoration: BoxDecoration(
                color: QcStyle.fill(c, v, hover: h, pressed: enabled && pressed, enabled: enabled),
                border: Border.all(color: v == QcVisual.on ? c.accent : Colors.transparent),
                borderRadius: BorderRadius.circular(QcStyle.radius),
                boxShadow: v == QcVisual.on ? QcStyle.glow(c) : const [],
              ),
              child: Text(
                s.label,
                style: QcStyle.text(
                    context,
                    v == QcVisual.on
                        ? c.accentInk
                        : enabled
                            ? (h ? c.ink : c.inkSoft)
                            : c.inkFaint,
                    strong: v == QcVisual.on),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
