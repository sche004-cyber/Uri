import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/screens/connections/google_setup_card.dart';
import 'package:uri_ui/services/app_state.dart';
import 'package:uri_ui/services/mock_uri_client.dart';
import 'package:uri_ui/services/uri_client.dart';

class _GoogleClient extends MockUriClient {
  @override
  Future<Map<String, dynamic>> googleSetup() async => <String, dynamic>{
    'steps': [
      {
        'id': 'client_secret',
        'status': 'ready',
        'message': 'Credentials configured',
        'help_url': 'https://console.cloud.google.com/auth/clients',
      },
      {
        'id': 'signed_in',
        'status': 'action_required',
        'message': 'Sign in with Google',
        'help_url': 'https://console.cloud.google.com/auth/audience',
      },
    ],
    'pending': false,
  };

  @override
  Future<ConnectionAuthorizeOutcome> authorizeConnection(
    String connectionId,
  ) async {
    final existing = (await listConnections()).firstWhere(
      (item) => item.id == connectionId,
    );
    return ConnectionAuthorizeOutcome(
      connection: existing,
      explanation: 'Complete sign-in.',
      authUrl: 'https://accounts.google.com/o/oauth2/v2/auth?state=test',
    );
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('shows setup steps and opens returned Google auth URL', (
    tester,
  ) async {
    final opened = <String>[];
    const channel = MethodChannel('plugins.flutter.io/url_launcher');
    tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(channel, (
      call,
    ) async {
      if (call.method == 'launch') {
        opened.add((call.arguments as Map)['url'] as String);
        return true;
      }
      return true;
    });
    addTearDown(
      () => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        channel,
        null,
      ),
    );
    final state = AppState(_GoogleClient());
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: SingleChildScrollView(
            child: GoogleSetupCard(
              state: state,
              onConfigure: () {},
              openUrl: (uri) async {
                opened.add(uri.toString());
                return true;
              },
            ),
          ),
        ),
      ),
    );
    await tester.pump();
    expect(find.text('Set up Google'), findsOneWidget);
    expect(find.text('Google OAuth credentials'), findsOneWidget);
    expect(find.text('Sign in with Google'), findsWidgets);
    await tester.tap(find.widgetWithText(FilledButton, 'Sign in with Google'));
    await tester.pumpAndSettle();
    expect(
      opened,
      contains('https://accounts.google.com/o/oauth2/v2/auth?state=test'),
    );
  });
}
