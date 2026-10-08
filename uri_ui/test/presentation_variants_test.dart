import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/models/attachment.dart';
import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/services/http_uri_client.dart';
import 'package:uri_ui/theme/uri_theme.dart';
import 'package:uri_ui/widgets/turn_card.dart';

Map<String, dynamic> reference(int n) => {
  'file_id': 'real-file-$n',
  'filename': 'Student-Welfare-$n.pptx',
  'media_type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'size_bytes': 36543,
};

void main() {
  test(
    'HTTP parses every real reference and deduplicates legacy first file',
    () async {
      final client = HttpUriClient(
        httpClient: MockClient(
          (_) async => http.Response(
            jsonEncode({
              'status': 'success',
              'execution': {'status': 'success', 'tool': 'generate_document'},
              'response': {
                'file': reference(1),
                'files': [
                  reference(1),
                  reference(2),
                  reference(3),
                  {'filename': 'fake.pptx'},
                ],
                'created_count': 3,
                'requested_count': 3,
                'complete': true,
                'message': 'Three local files created',
              },
            }),
            200,
          ),
        ),
      );
      final turn = await client.ask('Render all three designs');
      expect(turn.result!.allGeneratedFiles.map((f) => f.fileId), [
        'real-file-1',
        'real-file-2',
        'real-file-3',
      ]);
    },
  );

  test('legacy single-file response still provides one download', () async {
    final client = HttpUriClient(
      httpClient: MockClient(
        (_) async => http.Response(
          jsonEncode({
            'status': 'success',
            'response': {'file': reference(1), 'message': 'One file created'},
          }),
          200,
        ),
      ),
    );
    final turn = await client.ask('Make one deck');
    expect(turn.result!.allGeneratedFiles.single.fileId, 'real-file-1');
  });

  testWidgets(
    'all three actual output chips open their own authenticated references',
    (tester) async {
      final files = List.generate(
        3,
        (n) => Attachment(
          fileId: 'real-file-${n + 1}',
          filename: 'Student-Welfare-${n + 1}.pptx',
          mediaType: 'application/pptx',
          sizeBytes: 36543,
        ),
      );
      final opened = <String>[];
      final turn = UriTurn(
        id: 't',
        userText: 'Render all three designs',
        timestamp: DateTime(2026),
        stage: TurnStage.completed,
        result: ActionResult(summary: 'Three files', generatedFiles: files),
      );
      await tester.pumpWidget(
        MaterialApp(
          theme: buildUriTheme(UriColors.graphite),
          home: Scaffold(
            body: SingleChildScrollView(
              child: TurnCard(
                turn: turn,
                onApprove: () {},
                onCancel: () {},
                onConnectService: (_) {},
                onOpenAttachment: (file) => opened.add(file.fileId),
              ),
            ),
          ),
        ),
      );
      for (final file in files) {
        final chip = find.widgetWithText(
          ActionChip,
          '${file.filename} · 36 KB',
        );
        expect(chip, findsOneWidget);
        await tester.ensureVisible(chip);
        await tester.tap(chip);
      }
      expect(opened, files.map((f) => f.fileId));
      expect(tester.takeException(), isNull);
    },
  );
}
