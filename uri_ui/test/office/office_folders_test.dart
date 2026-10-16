/// OD-R1 (2026-10-16): the Folders dialog lists, adds (folder picker) and removes folders URI may use.
library;

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/living/office/office_bridge.dart';
import 'package:uri_ui/living/office/office_client.dart';
import 'package:uri_ui/living/office/office_folders.dart';
import 'package:uri_ui/theme/uri_theme.dart';

void main() {
  testWidgets('list, add with the folder picker, refused removal says why, then removal', (tester) async {
    final added = <String>[];
    var inUse = true;
    final mock = MockClient((req) async {
      List<Map<String, Object>> folders() => [
            {'path': r'C:\Users\me', 'kind': 'default', 'removable': false},
            for (final a in added) {'path': a, 'kind': 'added', 'removable': true},
          ];
      switch (req.url.path) {
        case '/folders':
          return http.Response(jsonEncode({'folders': folders()}), 200);
        case '/folders/add':
          added.add((jsonDecode(req.body) as Map)['path'] as String);
          return http.Response(jsonEncode({'added': true, 'folders': folders()}), 200);
        case '/folders/remove':
          if (inUse) {
            return http.Response(jsonEncode({'error': 'FOLDER_IN_USE', 'detail': 'close the files first'}), 409);
          }
          added.clear();
          return http.Response(jsonEncode({'removed': true, 'folders': folders()}), 200);
      }
      return http.Response(jsonEncode({'error': 'NOT_FOUND'}), 404);
    });
    final client = OfficeClient.forTest(Uri.parse('http://127.0.0.1:1'), 't', mock);
    final env = OfficeEnvironment(
      surfaceFactory: () => throw UnimplementedError(),
      pickWorkbookPath: () async => null,
      pickSavePath: (_) async => null,
      openExternalLink: (_) async {},
      pickFolderPath: () async => r'D:\Work\Budgets',
    );
    await tester.pumpWidget(MaterialApp(
      theme: ThemeData(extensions: const [UriColors.graphite]),
      home: Scaffold(body: OfficeFoldersDialog(client: client, environment: env)),
    ));
    await tester.pumpAndSettle();
    expect(find.text(r'C:\Users\me'), findsOneWidget);
    expect(find.text('Always allowed'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey('office-folder-add')));
    await tester.pumpAndSettle();
    expect(find.text(r'D:\Work\Budgets'), findsOneWidget);
    expect(find.textContaining('Added.'), findsOneWidget);

    await tester.tap(find.byKey(const ValueKey(r'office-folder-remove-D:\Work\Budgets')));
    await tester.pumpAndSettle();
    expect(find.textContaining('Close the files from that folder first'), findsOneWidget);
    expect(find.text(r'D:\Work\Budgets'), findsOneWidget);

    inUse = false;
    await tester.tap(find.byKey(const ValueKey(r'office-folder-remove-D:\Work\Budgets')));
    await tester.pumpAndSettle();
    expect(find.text(r'D:\Work\Budgets'), findsNothing);
    expect(find.textContaining('Removed.'), findsOneWidget);
  });
}
