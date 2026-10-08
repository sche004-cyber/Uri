// Script to capture authentic Flutter-rendered screenshots of TurnCard
// in both compact and workspace modes across URI's 4 approved themes.

import 'dart:io';
import 'dart:ui' as ui;
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:uri_ui/models/attachment.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/theme/uri_theme.dart';
import 'package:uri_ui/widgets/turn_card.dart';

void main() {
  const artifactDir = 'C:/Users/cheta/.gemini/antigravity/brain/1de44588-7eae-4935-a13a-ca9ea5a849bd';

  setUpAll(() async {
    final fontFile = File('C:/Windows/Fonts/segoeui.ttf');
    if (fontFile.existsSync()) {
      final fontBytes = fontFile.readAsBytesSync();
      for (final family in ['Segoe UI', 'Roboto', 'Arial', 'sans-serif']) {
        final loader = FontLoader(family)..addFont(Future.value(ByteData.sublistView(fontBytes)));
        await loader.load();
      }
    }
  });

  Future<void> captureWidget({
    required WidgetTester tester,
    required Widget widget,
    required ThemeData theme,
    required String filename,
    required Size size,
  }) async {
    tester.view.physicalSize = Size(size.width, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);

    await tester.pumpWidget(
      MaterialApp(
        theme: theme,
        debugShowCheckedModeBanner: false,
        home: Scaffold(
          backgroundColor: theme.extension<UriColors>()?.canvas,
          body: SingleChildScrollView(
            child: Center(
              child: RepaintBoundary(
                key: const ValueKey('capture_node'),
                child: Container(
                  width: size.width,
                  color: theme.extension<UriColors>()?.surface,
                  child: widget,
                ),
              ),
            ),
          ),
        ),
      ),
    );

    await tester.pumpAndSettle();

    await tester.runAsync(() async {
      final boundary = tester.renderObject<RenderRepaintBoundary>(find.byKey(const ValueKey('capture_node')));
      final image = await boundary.toImage(pixelRatio: 2.0);
      final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
      final outPath = '$artifactDir/$filename';
      File(outPath).writeAsBytesSync(bytes!.buffer.asUint8List());
    });
  }

  // 1. Proposal & Pending Approval Turn
  final approvalTurn = UriTurn(
    id: 'turn-approval-1',
    userText: 'Reconcile Q3 spreadsheet against financial ledger',
    timestamp: DateTime.now(),
    stage: TurnStage.awaitingApproval,
    servingModel: 'URI Auto (Local Edge)',
    durationSeconds: 0.82,
    promptTokens: 140,
    evalTokens: 48,
    understanding: 'Edge Brain parsed 4 sheets with 0 formula errors in isolated copy-in workspace (hash: 7f8a12). 2 discrepancy rows detected.',
    proposedAction: const ProposedAction(
      title: 'Deterministic Cell Reconciliation',
      description: 'Reconcile 2 discrepancy rows and write verified ledger back to URI workspace.',
      targetService: 'Spreadsheet',
      impact: ActionImpact.routine,
    ),
    attachments: const [
      Attachment(
        fileId: 'f-1',
        filename: 'Q3_Financial_Ledger_2026.xlsx',
        mediaType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        sizeBytes: 1048576,
      ),
    ],
  );

  // 2. Verified Result Turn
  final completedTurn = UriTurn(
    id: 'turn-completed-1',
    userText: 'Execute ledger reconciliation and update audit log',
    timestamp: DateTime.now(),
    stage: TurnStage.completed,
    servingModel: 'URI Auto (Local Edge)',
    durationSeconds: 1.15,
    promptTokens: 210,
    evalTokens: 95,
    understanding: 'Reconciliation complete. All 4 sheets balanced. Verification ledger written with SHA-256 hash match.',
    result: const ActionResult(
      summary: 'Successfully updated 2 reconciliation rows. Ledger status: VERIFIED.',
      detail: 'Artifact sha256: 8a4f91c0e3... Written to copy-in workspace.',
      generatedFile: Attachment(
        fileId: 'f-out-1',
        filename: 'Q3_Financial_Ledger_Reconciled.xlsx',
        mediaType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        sizeBytes: 1052672,
      ),
    ),
  );

  testWidgets('Capture TurnCard across themes and modes', (tester) async {
    final themes = {
      'graphite': UriColors.graphite,
      'deep_navy': UriColors.deepNavy,
      'slate_teal': UriColors.slateTeal,
      'light_professional': UriColors.lightProfessional,
    };

    for (final entry in themes.entries) {
      final theme = buildUriTheme(entry.value);

      // Workspace Mode - Awaiting Approval
      await captureWidget(
        tester: tester,
        widget: TurnCard(
          turn: approvalTurn,
          compact: false,
          onApprove: () {},
          onCancel: () {},
          onConnectService: (_) {},
          onOpenAttachment: (_) {},
        ),
        theme: theme,
        filename: 'turn_card_workspace_approval_${entry.key}.png',
        size: const Size(800, 500),
      );

      // Compact Mode - Awaiting Approval
      await captureWidget(
        tester: tester,
        widget: TurnCard(
          turn: approvalTurn,
          compact: true,
          onApprove: () {},
          onCancel: () {},
          onConnectService: (_) {},
          onOpenAttachment: (_) {},
        ),
        theme: theme,
        filename: 'turn_card_compact_approval_${entry.key}.png',
        size: const Size(420, 550),
      );
    }

    // Verified Result in Graphite (Workspace)
    await captureWidget(
      tester: tester,
      widget: TurnCard(
        turn: completedTurn,
        compact: false,
        onApprove: () {},
        onCancel: () {},
        onConnectService: (_) {},
        onOpenAttachment: (_) {},
      ),
      theme: buildUriTheme(UriColors.graphite),
      filename: 'turn_card_workspace_verified_result.png',
      size: const Size(800, 450),
    );
  });
}
