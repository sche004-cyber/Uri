import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uri_ui/screens/auth/login_screen.dart';
import 'package:uri_ui/services/uri_client.dart';
import 'package:uri_ui/services/session_store.dart';
import 'package:uri_ui/services/desktop_harness_test_session.dart';
import 'package:uri_ui/theme/uri_theme.dart';

void main() {
  test(
    'test login persists/restores/clears without altering installation session',
    () async {
      SharedPreferences.setMockInitialValues({});
      final normal = SessionStore();
      final isolated = DesktopHarnessTestSession();
      await normal.save(token: 'normal-token', username: 'normal-user');
      await isolated.save(token: 'test-token', username: 'test-user');
      expect((await DesktopHarnessTestSession().load())?.token, 'test-token');
      await isolated.clear();
      expect(await isolated.load(), isNull);
      expect((await normal.load())?.token, 'normal-token');
    },
  );

  for (final size in [
    const Size(400, 300),
    const Size(800, 450),
    const Size(1200, 800),
  ]) {
    testWidgets(
      'login/signup error controls scroll without overflow at $size',
      (tester) async {
        tester.view.physicalSize = size;
        tester.view.devicePixelRatio = 1;
        addTearDown(tester.view.resetPhysicalSize);
        addTearDown(tester.view.resetDevicePixelRatio);
        Future<AuthOutcome> failure(String username, String password) async =>
            const AuthOutcome.failure('Invalid username or password');
        await tester.pumpWidget(
          MaterialApp(
            theme: buildUriTheme(UriColors.graphite),
            home: LoginScreen(onLogin: failure, onSignup: failure),
          ),
        );
        expect(tester.takeException(), isNull);
        await tester.enterText(find.byType(TextField).at(0), 'disposable');
        await tester.enterText(
          find.byType(TextField).at(1),
          'disposable-test-password',
        );
        await tester.ensureVisible(find.text('Sign in'));
        await tester.tap(find.text('Sign in'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        await tester.ensureVisible(find.text('New here? Create an account'));
        await tester.tap(find.text('New here? Create an account'));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull);
        await tester.ensureVisible(find.text('Create account'));
        expect(find.text('Create account'), findsOneWidget);
      },
    );
  }
}
