import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/contracts/intelligence_snapshot.dart';
import 'package:uri_ui/living/contracts/work_items.dart';
import 'package:uri_ui/living/screens/intelligence/intelligence_overview_view.dart';

import 'living_shell_test.dart' show testServices, testAppState;

void main() {
  StageState stateOf(IntelligenceSnapshot s, PipelineStage st) =>
      s.stages.firstWhere((f) => f.stage == st).state;

  test('idle: every stage idle, routing none, flagged simulated under the mock client', () {
    final appState = testAppState();
    // No seeded history: nothing has happened yet.
    final services = testServices(
      appState,
      work: MockWorkSimulator(seed: false),
    );
    final snap = deriveIntelligenceSnapshot(
      signal: const CompanionSignal.idle(),
      appState: appState,
      services: services,
    );
    expect(snap.stages, hasLength(PipelineStage.values.length));
    expect(snap.routing, 'unknown');
    expect(snap.simulated, isTrue);
    for (final st in PipelineStage.values) {
      expect(stateOf(snap, st), StageState.idle, reason: st.name);
    }
    services.dispose();
  });

  test('awaiting approval blocks the approval stage; working activates execution; nothing is invented', () {
    final appState = testAppState();
    final services = testServices(
      appState,
      work: MockWorkSimulator(seed: false),
    );
    services.work.create(title: 'Letter', kind: WorkItemKind.letter);

    var snap = deriveIntelligenceSnapshot(
      signal: const CompanionSignal(
        state: CompanionState.awaitingApproval,
        detail: 'Save it',
        simulated: true,
      ),
      appState: appState,
      services: services,
    );
    expect(stateOf(snap, PipelineStage.request), StageState.done);
    expect(stateOf(snap, PipelineStage.approval), StageState.blocked);
    expect(stateOf(snap, PipelineStage.execution), StageState.idle);
    expect(
      snap.stages.firstWhere((f) => f.stage == PipelineStage.approval).detail,
      'Save it',
    );

    snap = deriveIntelligenceSnapshot(
      signal: const CompanionSignal(
        state: CompanionState.working,
        simulated: true,
      ),
      appState: appState,
      services: services,
    );
    // Working alone does not prove a decision was recorded: approval stays idle.
    expect(stateOf(snap, PipelineStage.approval), StageState.idle);
    expect(stateOf(snap, PipelineStage.execution), StageState.active);
    expect(stateOf(snap, PipelineStage.receipt), StageState.idle);
    // No harness selected, no Brain loaded: those stages stay idle rather than pretending.
    expect(stateOf(snap, PipelineStage.harness), StageState.idle);
    expect(snap.harnessName, isNull);
    // Route is never inferred.
    expect(stateOf(snap, PipelineStage.route), StageState.idle);
    expect(
      snap.stages.firstWhere((f) => f.stage == PipelineStage.route).detail,
      'not reported by this client',
    );
    services.dispose();
  });

  test('seeded history never counts as a recorded decision or receipt (Codex round 2, finding 1)', () {
    final appState = testAppState();
    // Default simulator: seeds one completed item nobody approved in this session.
    final services = testServices(appState);
    expect(services.work.items.single.state, WorkItemState.completed);
    expect(services.work.items.single.decided, isFalse);
    final snap = deriveIntelligenceSnapshot(
      signal: const CompanionSignal.idle(),
      appState: appState,
      services: services,
    );
    expect(stateOf(snap, PipelineStage.approval), StageState.idle);
    expect(stateOf(snap, PipelineStage.receipt), StageState.idle);
    expect(
      snap.stages.firstWhere((f) => f.stage == PipelineStage.approval).detail,
      'not observed',
    );

    // An in-session structured decision does count.
    final id = services.work.create(
      title: 'Sheet',
      kind: WorkItemKind.spreadsheet,
    );
    // Drive it to awaitingApproval without timers: cancel is also a decision.
    services.work.cancel(id);
    expect(services.work.items.firstWhere((i) => i.id == id).decided, isTrue);
    final after = deriveIntelligenceSnapshot(
      signal: const CompanionSignal.idle(),
      appState: appState,
      services: services,
    );
    // Codex round 3 MINOR: a cancel is a recorded decision too.
    expect(stateOf(after, PipelineStage.approval), StageState.done);
    expect(
      stateOf(after, PipelineStage.receipt),
      StageState.idle,
      reason: 'cancelled work has no output',
    );
    services.dispose();
  });
}
