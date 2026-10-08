// Isolated demonstration test bench for URI's TurnCard component.
// Exercises Impeccable design guidance (spacing rhythm, Edge Brain indicators,
// human approval decision gates, attachment chip disclosures) across all 4
// approved URI theme palettes without modifying any production application code.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/models/attachment.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/theme/uri_theme.dart';
import 'package:uri_ui/widgets/turn_card.dart';

void main() {
  Widget wrapTheme(Widget child, ThemeData theme) {
    return MaterialApp(
      theme: theme,
      home: Scaffold(
        backgroundColor: theme.extension<UriColors>()?.canvas,
        body: SingleChildScrollView(child: child),
      ),
    );
  }

  group('TurnCard Isolated Design Preview & Acceptance Tests', () {
    testWidgets('renders Edge Brain proposal turn with human approval decision gate', (tester) async {
      bool approved = false;
      bool cancelled = false;

      final turn = UriTurn(
        id: 't-preview-1',
        userText: 'Reconcile Q3 spreadsheet against ledger',
        timestamp: DateTime.now(),
        stage: TurnStage.awaitingApproval,
        servingModel: 'URI Auto (Local Edge)',
        durationSeconds: 0.84,
        promptTokens: 120,
        evalTokens: 42,
        understanding: 'Edge Brain parsed 4 sheets with 0 formula errors in copy-in workspace (hash: 7f8a12). Ready for approved write-back.',
        proposedAction: const ProposedAction(
          title: 'Deterministic Cell Reconciliation',
          description: 'Reconcile 2 discrepancy rows and write verified ledger back to URI workspace.',
          targetService: 'Spreadsheet',
          impact: ActionImpact.routine,
        ),
        attachments: const [
          Attachment(
            fileId: 'f-1',
            filename: 'Q3_Financial_Ledger_2026_Final_Audited_Draft.xlsx',
            mediaType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            sizeBytes: 1048576,
          ),
        ],
      );

      await tester.pumpWidget(
        wrapTheme(
          TurnCard(
            turn: turn,
            compact: false,
            onApprove: () => approved = true,
            onCancel: () => cancelled = true,
            onConnectService: (_) {},
            onOpenAttachment: (_) {},
          ),
          buildUriTheme(UriColors.graphite),
        ),
      );

      // Verify prompt and proposal contents
      expect(find.text('Reconcile Q3 spreadsheet against ledger'), findsOneWidget);
      expect(find.textContaining('Edge Brain parsed 4 sheets'), findsOneWidget);
      expect(find.textContaining('Reconcile 2 discrepancy rows'), findsOneWidget);

      // Verify human approval decision gate
      expect(find.text('Awaiting your approval'), findsOneWidget);
      final approveBtn = find.text('Approve');
      final cancelBtn = find.text('Cancel');
      expect(approveBtn, findsOneWidget);
      expect(cancelBtn, findsOneWidget);

      // Verify interactive callback functionality
      await tester.tap(approveBtn);
      expect(approved, isTrue);

      await tester.tap(cancelBtn);
      expect(cancelled, isTrue);

      // Verify metadata caption with Edge model info
      expect(find.textContaining('Conversation model: URI Auto (Local Edge)'), findsOneWidget);
      expect(find.textContaining('0.8s'), findsOneWidget);
      expect(find.textContaining('162 total tokens'), findsOneWidget);
    });

    testWidgets('renders cleanly across all 4 approved themes in compact mode', (tester) async {
      final turn = UriTurn(
        id: 't-preview-2',
        userText: 'Compact test',
        timestamp: DateTime.now(),
        stage: TurnStage.completed,
        servingModel: 'Claude Sonnet 3.5',
        understanding: 'Routine query executed smoothly without warnings.',
      );

      final palettes = [
        UriColors.graphite,
        UriColors.deepNavy,
        UriColors.slateTeal,
        UriColors.lightProfessional,
      ];

      for (final palette in palettes) {
        await tester.pumpWidget(
          wrapTheme(
            TurnCard(
              turn: turn,
              compact: true,
              onApprove: () {},
              onCancel: () {},
              onConnectService: (_) {},
              onOpenAttachment: (_) {},
            ),
            buildUriTheme(palette),
          ),
        );

        expect(find.text('Compact test'), findsOneWidget);
        expect(find.text('Routine query executed smoothly without warnings.'), findsOneWidget);
      }
    });
  });
}
