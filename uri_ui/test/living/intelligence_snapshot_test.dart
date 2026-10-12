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

  testWidgets(
    'seeded history never counts as a recorded decision; only a decision on a waiting item does (Codex rounds 2-4)',
    (tester) async {
      final appState = testAppState();
      // Default simulator: seeds one completed item nobody approved in this session.
      final services = testServices(
        appState,
        work: MockWorkSimulator(stepInterval: const Duration(milliseconds: 50)),
      );
      expect(services.work.items.single.state, WorkItemState.completed);
      expect(services.work.items.single.decided, isFalse);
      IntelligenceSnapshot snap() => deriveIntelligenceSnapshot(
        signal: const CompanionSignal.idle(),
        appState: appState,
        services: services,
      );
      expect(stateOf(snap(), PipelineStage.approval), StageState.idle);
      expect(stateOf(snap(), PipelineStage.receipt), StageState.idle);

      // Cancel while working: withdrawal, not a decision (Codex round 4, finding 1).
      final a = services.work.create(title: 'A', kind: WorkItemKind.document);
      await tester.pump(const Duration(milliseconds: 50));
      expect(
        services.work.items.firstWhere((i) => i.id == a).state,
        WorkItemState.working,
      );
      services.work.cancel(a);
      expect(services.work.items.firstWhere((i) => i.id == a).decided, isFalse);
      expect(stateOf(snap(), PipelineStage.approval), StageState.idle);

      // Cancel while awaiting approval: a recorded decision (Codex round 3).
      final b = services.work.create(
        title: 'B',
        kind: WorkItemKind.spreadsheet,
      );
      for (var i = 0; i < 8; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(
        services.work.items.firstWhere((i) => i.id == b).state,
        WorkItemState.awaitingApproval,
      );
      services.work.cancel(b);
      expect(services.work.items.firstWhere((i) => i.id == b).decided, isTrue);
      expect(stateOf(snap(), PipelineStage.approval), StageState.done);
      expect(
        stateOf(snap(), PipelineStage.receipt),
        StageState.idle,
        reason: 'cancelled work has no output',
      );
      services.dispose();
    },
  );
}
