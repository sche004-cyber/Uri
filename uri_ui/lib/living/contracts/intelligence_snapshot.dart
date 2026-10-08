import 'package:flutter/foundation.dart';

/// PROPOSED adapter contract (see `docs/ui_phase/UI_INTERFACE_CONTRACTS.md`
/// section 4): a read-only snapshot of where a request is in URI's
/// pipeline, for the intelligence overview.
///
/// Every stage below corresponds to a step that exists in the accepted
/// Phase 2 chain (intent -> proposal -> approval -> execution -> receipt,
/// `PHASE2OPS_UI_OPERATIONS.md`). The overview shows which stage is
/// current; it never shows invented reasoning text, token streams or
/// made-up timings. When no execution is in flight, every stage is
/// [StageState.idle].
enum PipelineStage { request, intent, route, harness, model, approval, execution, receipt }

enum StageState { idle, active, done, blocked, failed }

extension PipelineStageLabel on PipelineStage {
  String get label => switch (this) {
        PipelineStage.request => 'Request',
        PipelineStage.intent => 'Intent',
        PipelineStage.route => 'Route (Edge / Core)',
        PipelineStage.harness => 'Harness',
        PipelineStage.model => 'Model',
        PipelineStage.approval => 'Approval',
        PipelineStage.execution => 'Execution',
        PipelineStage.receipt => 'Receipt',
      };
}

@immutable
class StageFact {
  const StageFact({required this.stage, required this.state, this.detail});
  final PipelineStage stage;
  final StageState state;

  /// A fact string from the record (e.g. "codex / gpt-5-codex"), never prose.
  final String? detail;
}

/// A memory node for the memory-graph PROTOTYPE. Comes from the UI-side
/// `MemoryEntry` list (mock client in this phase). The graph layout is
/// decorative; edges are derived from shared words in the mock and are
/// labelled as such.
@immutable
class MemoryNode {
  const MemoryNode({required this.id, required this.label, this.kind = 'fact'});
  final String id;
  final String label;
  final String kind;
}

@immutable
class MemoryEdge {
  const MemoryEdge(this.from, this.to, {this.reason = 'shared term'});
  final String from;
  final String to;
  final String reason;
}

@immutable
class IntelligenceSnapshot {
  const IntelligenceSnapshot({
    required this.stages,
    required this.routing,
    required this.harnessName,
    required this.providerName,
    required this.modelName,
    required this.memoryNodes,
    required this.memoryEdges,
    required this.simulated,
    this.lastError,
  });

  final List<StageFact> stages;

  /// `edge`, `core` or `none`.
  final String routing;
  final String? harnessName;
  final String? providerName;
  final String? modelName;
  final List<MemoryNode> memoryNodes;
  final List<MemoryEdge> memoryEdges;
  final bool simulated;
  final String? lastError;

  static const IntelligenceSnapshot empty = IntelligenceSnapshot(
    stages: [],
    routing: 'none',
    harnessName: null,
    providerName: null,
    modelName: null,
    memoryNodes: [],
    memoryEdges: [],
    simulated: true,
  );
}

abstract class IntelligenceSnapshotSource extends ChangeNotifier {
  IntelligenceSnapshot get snapshot;
}
