import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/services/desktop_harness_test_client.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/widgets/harness_checkpoint_inspector.dart';

void main() {
  testWidgets(
    'inspects interruption and filters real receipt fields without execution',
    (tester) async {
      final client = DesktopHarnessTestClient(MockUriClient());
      addTearDown(client.close);
      final saved = <String, dynamic>{
        'task_id': 'retained-checkpoint',
        'status': 'QUOTA_INTERRUPTED',
        'progress': 'Settled',
        'potentially_non_idempotent': true,
        'verified_completed_work': false,
        'receipt': <String, dynamic>{
          'error_family': 'QUOTA',
          'verification_status': 'NOT_VERIFIED',
          'harness_duration_ms': 123,
        },
      };
      Map<String, dynamic>? chosen;
      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: SingleChildScrollView(
              child: HarnessCheckpointInspector(
                client: client,
                pending: null,
                task: saved,
                savedTasks: [saved],
                desktopDurationMs: null,
                onSelect: (value) => chosen = value,
              ),
            ),
          ),
        ),
      );
      await tester.tap(find.text('Console inspection'));
      await tester.pumpAndSettle();
      expect(find.text('Interruption/error: QUOTA'), findsOneWidget);
      expect(find.text('Verified completed work: false'), findsOneWidget);
      await tester.tap(find.text('retained-checkpoint · QUOTA_INTERRUPTED'));
      expect(chosen, same(saved));
      await tester.ensureVisible(
        find.byKey(const ValueKey('harness-console-search')),
      );
      await tester.enterText(
        find.byKey(const ValueKey('harness-console-search')),
        'verification',
      );
      await tester.pump();
      final text = tester
          .widget<SelectableText>(
            find.byKey(const ValueKey('harness-console-fields')),
          )
          .data!;
      expect(text, contains('NOT_VERIFIED'));
      expect(text, isNot(contains('harness_duration_ms')));
      expect(text, isNot(contains('application_round_trip_ms')));
      expect(find.textContaining('Host CPU:'), findsNothing);
      expect(
        find.textContaining('not evidence of an Edge model being loaded'),
        findsOneWidget,
      );
    },
  );
}
