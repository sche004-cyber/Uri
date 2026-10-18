import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';

/// Truth labels the living UI attaches to every capability, provider,
/// harness, model and data region (brief section 5: "distinguish
/// configured, qualified, unavailable, and simulated functionality").
enum TruthStatus { configured, qualified, unavailable, simulated, pending }

extension TruthStatusLabel on TruthStatus {
  String get label => switch (this) {
    TruthStatus.configured => 'Configured',
    TruthStatus.qualified => 'Qualified',
    TruthStatus.unavailable => 'Unavailable',
    TruthStatus.simulated => 'Simulated',
    TruthStatus.pending => 'Not checked',
  };
}

class StatusBadge extends StatelessWidget {
  const StatusBadge(this.status, {super.key, this.compact = false});

  /// Shorthand used by every mock-backed region.
  const StatusBadge.simulated({super.key, this.compact = false})
    : status = TruthStatus.simulated;

  final TruthStatus status;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final (Color fg, Color bg) = switch (status) {
      TruthStatus.configured => (c.accentInk, c.accentSoft),
      TruthStatus.qualified => (c.success, c.successSoft),
      TruthStatus.unavailable => (c.danger, c.dangerSoft),
      TruthStatus.simulated => (c.warning, c.warningSoft),
      TruthStatus.pending => (c.inkSoft, c.surfaceSunken),
    };
    return Semantics(
      label: 'Status: ${status.label}',
      child: Container(
        padding: EdgeInsets.symmetric(
          horizontal: compact ? 6 : 8,
          vertical: compact ? 1 : 3,
        ),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(999),
          border: Border.all(color: fg.withValues(alpha: 0.35)),
        ),
        child: Text(
          status.label.toUpperCase(),
          style: TextStyle(
            fontSize: compact ? UriType.micro : UriType.micro,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.6,
            color: fg,
          ),
        ),
      ),
    );
  }
}

/// Section eyebrow used across living screens ("CURRENT TASKS" etc.).
class Eyebrow extends StatelessWidget {
  const Eyebrow(this.text, {super.key, this.trailing});

  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Row(
      children: [
        Expanded(
          child: Text(
            text.toUpperCase(),
            style: TextStyle(
              fontSize: UriType.caption,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.2,
              color: c.inkFaint,
            ),
          ),
        ),
        ?trailing,
      ],
    );
  }
}
