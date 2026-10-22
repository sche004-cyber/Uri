import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../widgets/glass_panel.dart';
import 'oi_conversation.dart';

/// WS hardening surfaces: Brain health, worker trouble, and the real
/// Dashboard Brain card. Every value shown comes from the worker's
/// `brain_health` report (readiness, Brain host report, real-turn timings);
/// nothing is estimated here. Recovery buttons map to one explicit worker
/// command each, and none of them is available while a turn runs.

Color healthColor(UriColors c, String? state) => switch (state) {
      'READY' => c.success,
      'BUSY' => c.accent,
      'DEGRADED' => c.warning,
      'RECOVERING' => c.accent,
      'UNAVAILABLE' => c.danger,
      _ => c.inkFaint,
    };

String healthLabel(String? state) => switch (state) {
      'READY' => 'Ready',
      'BUSY' => 'Working',
      'DEGRADED' => 'Slow',
      'RECOVERING' => 'Starting',
      'UNAVAILABLE' => 'Unavailable',
      _ => 'Checking',
    };

double? _num(Object? v) => v is num ? v.toDouble() : null;

/// Latest measured decode speed and where it came from.
({double? tps, String source})? measuredSpeed(Map<String, dynamic> health) {
  final p = (health['performance'] as Map?) ?? const {};
  final median = _num(p['decode_tps_median']);
  final samples = (p['decode_samples'] as num?)?.toInt() ?? 0;
  if (median != null && samples >= 3) return (tps: median, source: 'median of $samples answers');
  final cal = _num(p['calibration_tps']);
  if (cal != null) return (tps: cal, source: 'speed check at start');
  return null;
}

class OiHealthChip extends StatelessWidget {
  const OiHealthChip({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final st = conversation.healthState;
    final speed = measuredSpeed(conversation.brainHealth);
    final tone = healthColor(c, st);
    return Container(
      key: const ValueKey('oi-health-chip'),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(border: Border.all(color: tone.withValues(alpha: 0.6)), borderRadius: BorderRadius.circular(999)),
      child: Text(
        [healthLabel(st), if (speed?.tps != null) '${speed!.tps!.toStringAsFixed(0)} tok/s'].join(' · '),
        style: TextStyle(color: tone, fontSize: UriType.caption),
      ),
    );
  }
}

const _actionLabels = {'restart_brain': 'Restart Brain', 'start_brain': 'Start Brain'};
const _actionCommands = {'restart_brain': 'restart', 'start_brain': 'start'};

/// Shown when the Brain is not healthy: the reason in plain words and the
/// recovery the evidence supports.
class OiHealthBanner extends StatelessWidget {
  const OiHealthBanner({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final h = conversation.brainHealth;
    final st = conversation.healthState;
    final warning = h['warning'] as String?;
    if (st == null || ((st == 'READY' || st == 'BUSY') && warning == null)) return const SizedBox.shrink();
    final options = [for (final o in (h['recovery_options'] as List? ?? const [])) '$o'];
    final consumers = [
      for (final x in ((h['gpu'] as Map?)?['consumers'] as List? ?? const []))
        if (x is Map && x['role'] == null) '${x['name'] ?? 'pid ${x['pid']}'} ${((_num(x['dedicated_mib']) ?? 0) / 1024).toStringAsFixed(1)} GB'
    ];
    return Padding(
      padding: const EdgeInsets.fromLTRB(UriSpace.md, UriSpace.sm, UriSpace.md, 0),
      child: GlassPanel(
        key: const ValueKey('oi-health-banner'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Icon(st == 'RECOVERING' ? Icons.autorenew_rounded : Icons.speed_rounded, size: 16, color: healthColor(c, st)),
              const SizedBox(width: 6),
              Text('Brain: ${healthLabel(st)}${warning != null ? ' · GPU memory taken' : ''}',
                  style: TextStyle(color: c.ink, fontWeight: FontWeight.w600)),
            ]),
            if (warning != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(warning, key: const ValueKey('oi-health-warning'), style: TextStyle(color: c.warning, fontSize: UriType.body)),
              ),
            if (h['explain'] != null && warning == null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('${h['explain']}', key: const ValueKey('oi-health-explain'), style: TextStyle(color: c.inkSoft, fontSize: UriType.body)),
              ),
            if (options.contains('close_gpu_apps') && consumers.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('Using the GPU: ${consumers.join(', ')}. URI never closes other apps.',
                    style: TextStyle(color: c.inkFaint, fontSize: UriType.label)),
              ),
            if (options.contains('start_from_launcher'))
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('Start the Brain with "Launch URI Working System".', style: TextStyle(color: c.inkFaint, fontSize: UriType.label)),
              ),
            if (options.any(_actionLabels.containsKey))
              Padding(
                padding: const EdgeInsets.only(top: 8),
                child: Wrap(spacing: 8, children: [
                  for (final o in options.where(_actionLabels.containsKey))
                    OutlinedButton(
                      key: ValueKey('oi-health-$o'),
                      onPressed: conversation.busy ? null : () => conversation.brainAction(_actionCommands[o]!),
                      child: Text(_actionLabels[o]!),
                    ),
                ]),
              ),
          ],
        ),
      ),
    );
  }
}

/// Shown when the worker itself is in trouble (R-BUSY): unresponsive,
/// a silent turn, or an unexpected exit.
class OiWorkerBanner extends StatelessWidget {
  const OiWorkerBanner({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final conv = conversation;
    if (!conv.workerTrouble && !conv.restarting) return const SizedBox.shrink();
    final idle = (conv.turnStatus['idle_s'] as num?)?.toInt();
    final text = conv.restarting
        ? 'Restarting URI…'
        : conv.workerUnresponsive
            ? 'URI is not responding. You can restart it; an unfinished request will not be repeated.'
            : conv.workerExited
                ? 'URI stopped unexpectedly. Restart it to continue.'
                : 'This request has produced nothing for ${idle ?? '?'} s. Stop it, or restart URI.';
    return Padding(
      padding: const EdgeInsets.fromLTRB(UriSpace.md, UriSpace.sm, UriSpace.md, 0),
      child: GlassPanel(
        key: const ValueKey('oi-worker-banner'),
        child: Row(
          children: [
            Icon(Icons.report_gmailerrorred_rounded, size: 18, color: c.warning),
            const SizedBox(width: 8),
            Expanded(child: Text(text, key: const ValueKey('oi-worker-text'), style: TextStyle(color: c.ink, fontSize: UriType.body))),
            if (conv.turnStalled && conv.busy)
              Padding(
                padding: const EdgeInsets.only(left: 8),
                child: OutlinedButton(onPressed: conv.cancel, child: const Text('Stop')),
              ),
            if (conv.respawn != null && !conv.restarting)
              Padding(
                padding: const EdgeInsets.only(left: 8),
                child: FilledButton(
                  key: const ValueKey('oi-restart-worker'),
                  onPressed: conv.restartWorker,
                  child: const Text('Restart URI'),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

/// Dashboard "Brain & models" content from the real worker report.
class OiBrainCard extends StatelessWidget {
  const OiBrainCard({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final conv = conversation;
    final h = conv.brainHealth;
    final st = conv.healthState;
    final b = (h['backend'] as Map?) ?? const {};
    final p = (h['performance'] as Map?) ?? const {};
    final g = (h['gpu'] as Map?) ?? const {};
    final speed = measuredSpeed(h);
    final reasons = [for (final r in (h['reasons'] as List? ?? const [])) '$r'];
    final small = TextStyle(fontSize: UriType.label, color: c.inkSoft);
    final faint = TextStyle(fontSize: UriType.label, color: c.inkFaint);
    final lastTier = conv.messages.reversed.firstWhere((m) => m.tier != null, orElse: () => OiMessage(role: OiRole.uri, text: '')).tier;
    String gpuLine() {
      if (g['measured'] != true) return 'GPU: not measured (no Brain host report)';
      final ded = _num(g['server_dedicated_mib']);
      final nonLocal = _num(g['server_non_local_mib']);
      final others = _num(g['others_mib']);
      return [
        'GPU: ${g['verdict_now'] ?? g['verdict_at_start'] ?? '?'}',
        if (ded != null) 'Brain ${(ded / 1024).toStringAsFixed(1)} GB in VRAM',
        if (nonLocal != null) '${(nonLocal / 1024).toStringAsFixed(1)} GB in system memory',
        if (others != null) 'others ${(others / 1024).toStringAsFixed(1)} GB',
      ].join(' · ');
    }

    return Column(
      key: const ValueKey('oi-brain-card'),
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(children: [
          Expanded(
            child: Text('${b['provider'] ?? 'Runtime v1 (local)'}',
                style: TextStyle(fontSize: UriType.titleLarge, fontWeight: FontWeight.w600, color: c.ink)),
          ),
          Container(
            key: const ValueKey('oi-brain-card-state'),
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
            decoration: BoxDecoration(
                border: Border.all(color: healthColor(c, st).withValues(alpha: 0.6)), borderRadius: BorderRadius.circular(999)),
            child: Text(st ?? 'CHECKING', style: TextStyle(fontSize: UriType.caption, color: healthColor(c, st))),
          ),
        ]),
        Text('${b['model_id'] ?? conv.brainStatus['model_id'] ?? '—'}', style: small),
        Text('${b['engine'] ?? '—'}${b['speculative'] != null ? ' · ${b['speculative']}' : ''}', style: faint),
        const SizedBox(height: 8),
        Text(
          speed?.tps != null ? '${speed!.tps!.toStringAsFixed(0)} tok/s · ${speed.source}' : 'Speed: not measured yet',
          key: const ValueKey('oi-brain-card-speed'),
          style: small,
        ),
        Text('Healthy above ${_num(p['threshold_tps'])?.toStringAsFixed(0) ?? '60'} tok/s (measured: healthy 96-157, slow 24-42)',
            style: faint),
        Text('Thinking: depth ${conv.depth.name}${lastTier != null ? ' · last answer ${lastTier == 'NORMAL' ? 'thinking' : lastTier.toLowerCase()}' : ''}'
            ' · reasoning text stays private',
            style: faint),
        Text(gpuLine(), key: const ValueKey('oi-brain-card-gpu'), style: faint),
        if (reasons.isNotEmpty && st != 'READY' && st != 'BUSY')
          Text('Why: ${reasons.join(', ')}', key: const ValueKey('oi-brain-card-reasons'), style: TextStyle(fontSize: UriType.label, color: c.warning)),
        if (h['explain'] != null && st != 'READY' && st != 'BUSY') Text('${h['explain']}', style: small),
        const SizedBox(height: 6),
        Wrap(spacing: 8, children: [
          for (final o in [for (final x in (h['recovery_options'] as List? ?? const [])) '$x'].where(_actionLabels.containsKey))
            OutlinedButton(
              key: ValueKey('oi-brain-card-$o'),
              onPressed: conv.busy ? null : () => conv.brainAction(_actionCommands[o]!),
              child: Text(_actionLabels[o]!),
            ),
        ]),
      ],
    );
  }
}
