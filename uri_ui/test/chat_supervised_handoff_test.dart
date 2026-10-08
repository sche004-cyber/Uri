// C6 owner decision 2, Option B (owner accepted 2026-10-08): the Chat pane
// mounts "Make this a supervised task" under the user's own message, only for
// an opted-in installation, and tapping it never reaches `/ask`.

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:uri_ui/models/uri_turn.dart';
import 'package:uri_ui/screens/ask/ask_uri_screen.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/app_state_scope.dart';
import 'package:uri_ui/services/mock_uri_client.dart';

/// Counts `/ask` calls; the handoff must never add one.
class _CountingClient extends MockUriClient {
  int asks = 0;

  @override
  Future<UriTurn> ask(String text, {String? turnId, Object? modelOverride}) async {
    asks += 1;
    return UriTurn(id: turnId ?? 'x', userText: text, timestamp: DateTime(2026, 10, 8), stage: TurnStage.completed,
        result: const ActionResult(summary: 'Done.'));
  }
}

Widget _pane(AppState state, {required bool supervised}) => AppStateScope(
      state: state,
      child: MaterialApp(home: Scaffold(body: UriConversationPane(supervisedHandoff: supervised))),
    );

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('the Chat pane offers the handoff under a settled user message only when opted in', (tester) async {
    final client = _CountingClient();
    final state = AppState(client);
    await state.ask('write a greeting into out.txt');
    expect(client.asks, 1);
    final id = state.conversation.single.id;

    await tester.pumpWidget(_pane(state, supervised: false));
    await tester.pumpAndSettle();
    expect(find.byKey(Key('chat-handoff-$id')), findsNothing);

    await tester.pumpWidget(_pane(state, supervised: true));
    await tester.pumpAndSettle();
    expect(find.byKey(Key('chat-handoff-$id')), findsOneWidget);
    expect(find.text('Make this a supervised task'), findsOneWidget);
    expect(client.asks, 1); // rendering the action sent nothing
  });
}
