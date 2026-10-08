import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../../models/memory_entry.dart';
import '../../../models/uri_turn.dart' show TurnStage;
import '../../../services/app_state.dart';
import '../../../services/app_state_scope.dart';
import '../../../theme/glass_theme.dart';
import '../../../theme/uri_theme.dart';
import '../../companion/companion_state.dart';
import '../../contracts/intelligence_snapshot.dart';
import '../../contracts/work_items.dart';
import '../../living_scope.dart';
import '../../widgets/glass_panel.dart';
import '../../widgets/status_badge.dart';

/// Builds the intelligence snapshot from what the UI can actually
/// observe. Pure function; tested directly.
///
/// Honesty rules: a stage is `active` only when a real signal says so;
/// `done` only for things that visibly happened (a request exists, a
/// result exists); `blocked` only for awaiting-approval; everything
/// else `idle`. No stage is ever given a fabricated duration or text.
IntelligenceSnapshot deriveIntelligenceSnapshot({
  required CompanionSignal signal,
  required AppState appState,
  required LivingServices services,
}) {
  final lastTurn = appState.conversation.isEmpty
      ? null
      : appState.conversation.last;
  final activeWork = services.work.items.where((i) => !i.state.isTerminal);
  final hasRequest = lastTurn != null || activeWork.isNotEmpty;
  final harnessId = services.selectedHarness.value;
  final harness = services.readiness.harnesses
      .where((h) => h.id == harnessId)
      .toList();
  final st = signal.state;

  // Facts only. A stage is `done` when something observable says that
  // step produced output; `active`/`blocked` only from the live signal;
  // everything else `idle` with a "not observed" detail. Route, harness
  // and model are shown as facts about the selection, never as a claim
  // that the stage ran.
  final intentObserved = lastTurn?.understanding != null;
  final decisionObserved =
      (lastTurn != null &&
          lastTurn.proposedAction != null &&
          (lastTurn.stage == TurnStage.executing ||
              lastTurn.stage == TurnStage.completed)) ||
      services.work.items.any(
        (i) => i.decided && i.state == WorkItemState.completed,
      );
  final receiptObserved =
      lastTurn?.result != null ||
      services.work.items.any((i) => i.decided && i.outputName != null);

  StageState s(PipelineStage stage) {
    switch (stage) {
      case PipelineStage.request:
        return hasRequest ? StageState.done : StageState.idle;
      case PipelineStage.intent:
        if (st == CompanionState.thinking) return StageState.active;
        return intentObserved ? StageState.done : StageState.idle;
      case PipelineStage.route:
      case PipelineStage.harness:
      case PipelineStage.model:
        return StageState.idle; // facts shown in detail; not observed as steps
      case PipelineStage.approval:
        if (st == CompanionState.awaitingApproval) return StageState.blocked;
        return decisionObserved ? StageState.done : StageState.idle;
      case PipelineStage.execution:
        if (st == CompanionState.working) return StageState.active;
        if (st == CompanionState.error) return StageState.failed;
        return StageState.idle;
      case PipelineStage.receipt:
        if (st == CompanionState.success) return StageState.done;
        return receiptObserved ? StageState.done : StageState.idle;
    }
  }

  final nodes = <MemoryNode>[
    for (final m in appState.memories)
      MemoryNode(id: m.memoryId, label: m.content, kind: m.category),
  ];
  final edges = _sharedTermEdges(appState.memories);

  return IntelligenceSnapshot(
    stages: [
      for (final stage in PipelineStage.values)
        StageFact(
          stage: stage,
          state: s(stage),
          detail: switch (stage) {
            PipelineStage.route => 'not reported by this client',
            PipelineStage.harness =>
              harness.isEmpty
                  ? 'none selected'
                  : 'selected: ${harness.first.displayName}',
            PipelineStage.model =>
              appState.activeBrain?.model == null
                  ? 'no Brain set'
                  : 'active: ${appState.activeBrain!.model}',
            PipelineStage.intent =>
              intentObserved
                  ? lastTurn!.understanding
                  : (st == CompanionState.thinking
                        ? signal.detail
                        : 'not observed'),
            PipelineStage.approval =>
              st == CompanionState.awaitingApproval
                  ? signal.detail
                  : (decisionObserved ? 'decision recorded' : 'not observed'),
            PipelineStage.execution =>
              st == CompanionState.working
                  ? signal.detail
                  : (st == CompanionState.error
                        ? signal.detail
                        : 'not observed'),
            PipelineStage.receipt =>
              receiptObserved || st == CompanionState.success
                  ? 'result present'
                  : 'not observed',
            PipelineStage.request => hasRequest ? 'present' : 'none',
          },
        ),
    ],
    routing: 'unknown',
    harnessName: harness.isEmpty ? null : harness.first.displayName,
    providerName:
        appState.activeBrain?.displayName ?? appState.activeBrain?.providerId,
    modelName: appState.activeBrain?.model,
    memoryNodes: nodes,
    memoryEdges: edges,
    simulated: services.appDataIsMock || signal.simulated,
    lastError: st == CompanionState.error
        ? signal.detail
        : appState.lastConnectionErrorDetail,
  );
}

List<MemoryEdge> _sharedTermEdges(List<MemoryEntry> memories) {
  final words = <String, Set<String>>{};
  for (final m in memories) {
    words[m.memoryId] = m.content
        .toLowerCase()
        .split(RegExp(r'[^a-z0-9]+'))
        .where((w) => w.length > 4)
        .toSet();
  }
  final edges = <MemoryEdge>[];
  final ids = words.keys.toList();
  for (var i = 0; i < ids.length; i++) {
    for (var j = i + 1; j < ids.length; j++) {
      final shared = words[ids[i]]!.intersection(words[ids[j]]!);
      if (shared.isNotEmpty) {
        edges.add(
          MemoryEdge(ids[i], ids[j], reason: 'shares "${shared.first}"'),
        );
      }
    }
  }
  return edges;
}

/// Intelligence overview: pipeline, executor facts, memory graph
/// prototype, work/approvals/errors, and the raw signal sources.
class IntelligenceOverviewView extends StatefulWidget {
  const IntelligenceOverviewView({super.key});

  @override
  State<IntelligenceOverviewView> createState() =>
      _IntelligenceOverviewViewState();
}

class _IntelligenceOverviewViewState extends State<IntelligenceOverviewView> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final s = AppStateScope.of(context);
      if (!s.hasLoadedMemory) s.loadMemory();
      if (s.activeBrain == null) s.loadActiveBrain();
    });
  }

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final appState = AppStateScope.of(context);
    final c = UriColors.of(context);
    return ListenableBuilder(
      listenable: Listenable.merge([
        services.companion,
        services.work,
        services.selectedHarness,
        appState,
      ]),
      builder: (context, _) {
        final signal = services.companion.signal;
        final snap = deriveIntelligenceSnapshot(
          signal: signal,
          appState: appState,
          services: services,
        );
        final wide = MediaQuery.sizeOf(context).width >= 1100;
        final left = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Eyebrow(
              'Request pipeline',
              trailing: snap.simulated
                  ? const StatusBadge.simulated(compact: true)
                  : null,
            ),
            const SizedBox(height: 8),
            GlassPanel(child: _PipelineStrip(stages: snap.stages)),
            const SizedBox(height: UriSpace.lg),
            const Eyebrow('Executor facts'),
            const SizedBox(height: 8),
            GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _Fact(
                    'Routing',
                    'Not reported by this client (Edge/Core is decided server-side)',
                  ),

                  _Fact('Harness', snap.harnessName ?? 'None selected'),
                  _Fact('Provider', snap.providerName ?? 'Not set'),
                  _Fact('Model', snap.modelName ?? '—'),
                  _Fact('Reasoning', services.reasoningMode.value.label),
                  if (snap.lastError != null)
                    _Fact('Last error', snap.lastError!, danger: true),
                ],
              ),
            ),
            const SizedBox(height: UriSpace.lg),
            const Eyebrow('Signal sources'),
            const SizedBox(height: 8),
            GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final s in services.companion.all)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 110,
                            child: Text(
                              s.sourceName ?? 'none',
                              style: TextStyle(
                                fontSize: 11.5,
                                color: c.inkFaint,
                              ),
                            ),
                          ),
                          Expanded(
                            child: Text(
                              '${s.state.label}${s.detail != null ? ' · ${s.detail}' : ''}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 12.5, color: c.ink),
                            ),
                          ),
                          if (s.simulated)
                            const StatusBadge.simulated(compact: true),
                        ],
                      ),
                    ),
                  const SizedBox(height: 4),
                  Text(
                    'The orb shows the highest-priority signal above. Nothing here is URI\'s internal reasoning; these are observed states.',
                    style: TextStyle(fontSize: 11.5, color: c.inkFaint),
                  ),
                ],
              ),
            ),
          ],
        );
        final right = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Eyebrow('Memory graph', trailing: _PrototypeBadge()),
            const SizedBox(height: 8),
            GlassPanel(
              padding: EdgeInsets.zero,
              child: SizedBox(
                height: 260,
                child: Column(
                  children: [
                    Expanded(
                      child: CustomPaint(
                        key: const ValueKey('memory-graph'),
                        painter: _MemoryGraphPainter(
                          nodes: snap.memoryNodes,
                          edges: snap.memoryEdges,
                          glow: UriGlass.of(context).glow,
                          ink: c.ink,
                          faint: c.inkFaint,
                        ),
                        child: const SizedBox.expand(),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
                      child: Text(
                        'PROTOTYPE: not connected to a memory backend. Nodes are the ${services.appDataIsMock ? 'mock client\'s' : 'client\'s'} memory entries (${snap.memoryNodes.length}); edges join entries that share a word.',
                        key: const ValueKey('memory-graph-disclaimer'),
                        style: TextStyle(fontSize: 11, color: c.warning),
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: UriSpace.lg),
            const Eyebrow('Active work and approvals'),
            const SizedBox(height: 8),
            GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  for (final w in services.work.items.where(
                    (i) => !i.state.isTerminal,
                  ))
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Row(
                        children: [
                          Icon(
                            w.state == WorkItemState.awaitingApproval
                                ? Icons.rule_rounded
                                : Icons.autorenew_rounded,
                            size: 14,
                            color: w.state == WorkItemState.awaitingApproval
                                ? c.warning
                                : c.accent,
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              '${w.title} · ${w.state.label}',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 12.5, color: c.ink),
                            ),
                          ),
                          if (w.simulated)
                            const StatusBadge.simulated(compact: true),
                        ],
                      ),
                    ),
                  for (final t in appState.tasks)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 3),
                      child: Row(
                        children: [
                          Icon(Icons.rule_rounded, size: 14, color: c.warning),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              '${t.description} · Needs approval',
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 12.5, color: c.ink),
                            ),
                          ),
                          if (services.appDataIsMock)
                            const StatusBadge.simulated(compact: true),
                        ],
                      ),
                    ),
                  if (services.work.items.every((i) => i.state.isTerminal) &&
                      appState.tasks.isEmpty)
                    Text(
                      'Nothing active.',
                      style: TextStyle(fontSize: 12.5, color: c.inkFaint),
                    ),
                ],
              ),
            ),
          ],
        );
        return SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(
            UriSpace.md,
            0,
            UriSpace.md,
            UriSpace.lg,
          ),
          child: wide
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(child: left),
                    const SizedBox(width: UriSpace.md),
                    Expanded(child: right),
                  ],
                )
              : Column(
                  children: [
                    left,
                    const SizedBox(height: UriSpace.lg),
                    right,
                  ],
                ),
        );
      },
    );
  }
}

class _PrototypeBadge extends StatelessWidget {
  const _PrototypeBadge();
  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: c.warningSoft,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: c.warning.withValues(alpha: 0.4)),
      ),
      child: Text(
        'PROTOTYPE',
        style: TextStyle(
          fontSize: 9.5,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.6,
          color: c.warning,
        ),
      ),
    );
  }
}

class _Fact extends StatelessWidget {
  const _Fact(this.k, this.v, {this.danger = false});
  final String k;
  final String v;
  final bool danger;
  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 90,
            child: Text(k, style: TextStyle(fontSize: 11.5, color: c.inkFaint)),
          ),
          Expanded(
            child: Text(
              v,
              style: TextStyle(
                fontSize: 12.5,
                color: danger ? c.danger : c.ink,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

/// The eight pipeline stages as a connected strip.
class _PipelineStrip extends StatelessWidget {
  const _PipelineStrip({required this.stages});
  final List<StageFact> stages;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return LayoutBuilder(
      builder: (context, constraints) {
        final narrow = constraints.maxWidth < 560;
        return Wrap(
          spacing: 6,
          runSpacing: 8,
          children: [
            for (final f in stages)
              Semantics(
                label: '${f.stage.label}: ${f.state.name}',
                child: SizedBox(
                  width: narrow
                      ? (constraints.maxWidth - 6) / 2
                      : (constraints.maxWidth - 6 * 3) / 4,
                  child: Row(
                    children: [
                      _StageDot(state: f.state),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              f.stage.label,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: f.state == StageState.active
                                    ? FontWeight.w700
                                    : FontWeight.w500,
                                color: f.state == StageState.idle
                                    ? c.inkFaint
                                    : c.ink,
                              ),
                            ),
                            Text(
                              f.detail ?? f.state.name,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(
                                fontSize: 10.5,
                                color: c.inkFaint,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        );
      },
    );
  }
}

class _StageDot extends StatelessWidget {
  const _StageDot({required this.state});
  final StageState state;
  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final color = switch (state) {
      StageState.idle => c.border,
      StageState.active => c.accent,
      StageState.done => c.success,
      StageState.blocked => c.warning,
      StageState.failed => c.danger,
    };
    return Container(
      width: 10,
      height: 10,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: color,
        boxShadow: state == StageState.active
            ? [BoxShadow(color: color.withValues(alpha: 0.7), blurRadius: 8)]
            : null,
      ),
    );
  }
}

/// Static ring layout; decorative by design (the disclaimer under it
/// says so). No physics, no "activity" animation.
class _MemoryGraphPainter extends CustomPainter {
  _MemoryGraphPainter({
    required this.nodes,
    required this.edges,
    required this.glow,
    required this.ink,
    required this.faint,
  });
  final List<MemoryNode> nodes;
  final List<MemoryEdge> edges;
  final Color glow;
  final Color ink;
  final Color faint;

  @override
  void paint(Canvas canvas, Size size) {
    if (nodes.isEmpty) {
      final tp = TextPainter(
        text: TextSpan(
          text: 'No memory entries',
          style: TextStyle(color: faint, fontSize: 12),
        ),
        textDirection: TextDirection.ltr,
      )..layout();
      tp.paint(
        canvas,
        size.center(Offset.zero) - Offset(tp.width / 2, tp.height / 2),
      );
      return;
    }
    final center = size.center(Offset.zero);
    final r = math.min(size.width, size.height) * 0.36;
    final positions = <String, Offset>{};
    for (var i = 0; i < nodes.length; i++) {
      final a = -math.pi / 2 + i * (math.pi * 2 / nodes.length);
      positions[nodes[i].id] = center + Offset(math.cos(a), math.sin(a)) * r;
    }
    final edgePaint = Paint()
      ..color = glow.withValues(alpha: 0.35)
      ..strokeWidth = 1;
    for (final e in edges) {
      final a = positions[e.from];
      final b = positions[e.to];
      if (a != null && b != null) canvas.drawLine(a, b, edgePaint);
    }
    final nodePaint = Paint()..color = glow;
    final haloPaint = Paint()..color = glow.withValues(alpha: 0.18);
    for (final n in nodes) {
      final p = positions[n.id]!;
      canvas.drawCircle(p, 9, haloPaint);
      canvas.drawCircle(p, 4, nodePaint);
      final label = n.label.length > 22
          ? '${n.label.substring(0, 21)}…'
          : n.label;
      final tp = TextPainter(
        text: TextSpan(
          text: label,
          style: TextStyle(color: ink, fontSize: 10.5),
        ),
        textDirection: TextDirection.ltr,
        maxLines: 1,
        ellipsis: '…',
      )..layout(maxWidth: 120);
      final toRight = p.dx >= center.dx;
      tp.paint(
        canvas,
        Offset(
          toRight ? p.dx + 10 : p.dx - 10 - tp.width,
          p.dy - tp.height / 2,
        ),
      );
    }
  }

  @override
  bool shouldRepaint(covariant _MemoryGraphPainter old) =>
      old.nodes != nodes || old.edges != edges || old.glow != glow;
}
