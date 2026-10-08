import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/app.dart';
import 'package:uri_ui/models/user_preferences.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/screens/ask/ask_uri_screen.dart';

void main() {
  testWidgets('voice navigation opens existing Chat and leaves compact mode', (tester) async {
    SharedPreferences.setMockInitialValues({});
    tester.view.physicalSize = const Size(1280, 900);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final state = AppState(MockUriClient());
    await state.updatePreferences(const UserPreferences.initial()
        .copyWith(completedOnboarding: true));
    await tester.pumpWidget(UriApp(appState: state));
    await tester.pumpAndSettle();
    expect(find.byType(AskUriScreen), findsNothing);
    state.setCompact(true);
    await tester.pumpAndSettle();
    state.requestVoiceConversation();
    await tester.pumpAndSettle();
    expect(state.isCompact, isFalse);
    expect(find.byType(AskUriScreen), findsOneWidget);
    expect(state.conversation, isEmpty);
  });
}
