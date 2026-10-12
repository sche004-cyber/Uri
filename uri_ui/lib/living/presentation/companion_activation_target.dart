import 'package:flutter/material.dart';

/// Keyboard and assistive activation share the same local click action.
/// Pointer arbitration stays in Flutter's standard double-tap recognizer.
class CompanionActivationTarget extends StatelessWidget {
  const CompanionActivationTarget({
    super.key,
    required this.onActivate,
    required this.child,
    required this.label,
  });
  final VoidCallback onActivate;
  final Widget child;
  final String label;
  @override
  Widget build(BuildContext context) => FocusableActionDetector(
    actions: {
      ActivateIntent: CallbackAction<ActivateIntent>(
        onInvoke: (_) {
          onActivate();
          return null;
        },
      ),
    },
    child: Semantics(
      button: true,
      label: label,
      onTap: onActivate,
      child: child,
    ),
  );
}
