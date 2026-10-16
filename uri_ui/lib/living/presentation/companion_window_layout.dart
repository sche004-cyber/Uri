import 'package:flutter/widgets.dart';
import 'package:flutter/foundation.dart';

/// Logical client-coordinate hit regions. Native adapters convert with the
/// target window's current DPI; this contract contains no runtime authority.
@immutable
class CompanionWindowLayout {
  const CompanionWindowLayout({
    required this.active,
    required this.orb,
    this.panel,
    this.controls,
    this.orbit,
    this.buttons = const [],
  });
  final bool active;
  final Rect orb;
  final Rect? panel;
  final Rect? controls;
  final Rect? orbit;
  final List<Rect> buttons;
  Map<String, Object?> toJson() => {
    'active': active,
    'orb': [orb.left, orb.top, orb.right, orb.bottom],
    'panel': panel == null
        ? null
        : [panel!.left, panel!.top, panel!.right, panel!.bottom],
    'controls': controls == null
        ? null
        : [controls!.left, controls!.top, controls!.right, controls!.bottom],
    'orbit': orbit == null
        ? null
        : [orbit!.left, orbit!.top, orbit!.right, orbit!.bottom],
    'buttons': [
      for (final r in buttons) [r.left, r.top, r.right, r.bottom],
    ],
  };
  @override
  bool operator ==(Object other) =>
      other is CompanionWindowLayout &&
      other.active == active &&
      other.orb == orb &&
      other.panel == panel &&
      other.controls == controls &&
      other.orbit == orbit &&
      listEquals(other.buttons, buttons);
  @override
  int get hashCode =>
      Object.hash(active, orb, panel, controls, orbit, Object.hashAll(buttons));
}
