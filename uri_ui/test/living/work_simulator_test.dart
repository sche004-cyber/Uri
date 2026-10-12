import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/contracts/work_items.dart';

void main() {
  testWidgets(
    'a created item runs queued -> working -> awaiting approval, and the orb follows',
    (tester) async {
      final sim = MockWorkSimulator(
        stepInterval: const Duration(milliseconds: 100),
      );
      addTearDown(sim.dispose);
      final id = sim.create(title: 'Draft a letter', kind: WorkItemKind.letter);
      expect(sim.items.first.state, WorkItemState.queued);
      expect(sim.items.first.simulated, isTrue);

      await tester.pump(const Duration(milliseconds: 100));
      expect(sim.items.first.state, WorkItemState.working);
      expect(sim.companion.signal.state, CompanionState.working);
      expect(sim.companion.signal.simulated, isTrue);
      expect(sim.companion.signal.progress, isNotNull);

      for (var i = 0; i < 6; i++) {
        await tester.pump(const Duration(milliseconds: 100));
      }
      expect(sim.items.first.state, WorkItemState.awaitingApproval);
      expect(sim.companion.signal.state, CompanionState.awaitingApproval);
      expect(sim.items.first.approvalSummary, contains('Draft a letter.docx'));

      // Only a structured decision moves it on.
      sim.approve(id);
      expect(sim.items.first.state, WorkItemState.completed);
      expect(sim.items.first.outputName, 'Draft a letter.docx');
      expect(sim.documents.first.name, 'Draft a letter.docx');
      expect(sim.companion.signal.state, CompanionState.success);

      await tester.pump(const Duration(seconds: 4));
      expect(sim.companion.signal.state, CompanionState.idle);
    },
  );

  testWidgets('cancel stops the timers and returns the orb to idle', (
    tester,
  ) async {
    final sim = MockWorkSimulator(
      stepInterval: const Duration(milliseconds: 100),
      seed: false,
    );
    addTearDown(sim.dispose);
    final id = sim.create(
      title: 'Build a sheet',
      kind: WorkItemKind.spreadsheet,
    );
    await tester.pump(const Duration(milliseconds: 100));
    expect(sim.companion.signal.state, CompanionState.working);
    sim.cancel(id);
    expect(sim.items.single.state, WorkItemState.cancelled);
    expect(sim.companion.signal.state, CompanionState.idle);
    await tester.pump(const Duration(seconds: 1));
    expect(sim.items.single.state, WorkItemState.cancelled);
  });

  testWidgets(
    'approve on a non-waiting item is refused (no invented completion)',
    (tester) async {
      final sim = MockWorkSimulator(
        stepInterval: const Duration(milliseconds: 100),
        seed: false,
      );
      addTearDown(sim.dispose);
      final id = sim.create(title: 'X', kind: WorkItemKind.document);
      sim.approve(id);
      expect(sim.items.single.state, WorkItemState.queued);
      sim.cancel(id); // clears the pending timer so the test ends clean
    },
  );
}
