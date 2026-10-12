import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import 'assist_controller.dart';

/// The Companion's active-scope indicator (docs/assist/A0_UI_INTERACTION_SPEC.md
/// §5): visible whenever a scope is ACTIVE or PAUSED, with Pause/Resume and a
/// one-tap Stop. Nothing is shown while Assist is OFF.
class AssistScopeLine extends StatelessWidget {
  const AssistScopeLine({super.key, required this.assist});
  final AssistController assist;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: assist,
      builder: (context, _) {
        if (assist.off) return const SizedBox.shrink();
        final c = UriColors.of(context);
        final scope = assist.scope ?? const {};
        final n = assist.findings.length;
        return Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Row(
            key: const ValueKey('assist-scope-line'),
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.visibility_outlined, size: 14, color: assist.active ? c.success : c.inkFaint),
              const SizedBox(width: 6),
              ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 260),
                child: Text(
                  '${assist.paused ? 'Paused · ' : 'URI can see · '}${scope['label'] ?? ''}'
                  '${n > 0 ? ' · $n suggestion${n == 1 ? '' : 's'}' : ''}',
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 12, color: c.inkSoft),
                ),
              ),
              IconButton(
                key: ValueKey(assist.paused ? 'assist-line-resume' : 'assist-line-pause'),
                visualDensity: VisualDensity.compact,
                iconSize: 16,
                tooltip: assist.paused ? 'Resume' : 'Pause',
                onPressed: assist.busy ? null : (assist.paused ? assist.resume : assist.pause),
                icon: Icon(assist.paused ? Icons.play_arrow_rounded : Icons.pause_rounded),
              ),
              IconButton(
                key: const ValueKey('assist-line-stop'),
                visualDensity: VisualDensity.compact,
                iconSize: 16,
                tooltip: 'Stop sharing',
                onPressed: assist.revoke,
                icon: Icon(Icons.stop_rounded, color: c.danger),
              ),
            ],
          ),
        );
      },
    );
  }
}

/// Dashboard summary (spec §6): Assist state, each adapter's availability and
/// the vision pathway's qualification. Read-only; no content.
class AssistStatusSummary extends StatelessWidget {
  const AssistStatusSummary({super.key, required this.assist});
  final AssistController assist;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: assist,
      builder: (context, _) {
        final c = UriColors.of(context);
        final vision = (assist.status['vision'] as Map?) ?? const {};
        final style = TextStyle(fontSize: 12.5, color: c.ink);
        return Column(
          key: const ValueKey('dashboard-assist'),
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              assist.off ? 'Off — URI sees nothing' : '${assist.state}: ${assist.scope?['label'] ?? ''}',
              style: style,
            ),
            const SizedBox(height: 4),
            for (final a in assist.adapters)
              Row(
                children: [
                  Icon(a['state'] == 'AVAILABLE' ? Icons.check_rounded : Icons.remove_rounded, size: 14,
                      color: a['state'] == 'AVAILABLE' ? c.success : c.inkFaint),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text('${a['kind']}: ${a['state']}', maxLines: 1, overflow: TextOverflow.ellipsis,
                        style: TextStyle(fontSize: 12, color: c.inkSoft)),
                  ),
                ],
              ),
            Text('Vision: ${vision['application'] ?? 'unknown'}', maxLines: 2, overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 12, color: c.inkFaint)),
          ],
        );
      },
    );
  }
}
