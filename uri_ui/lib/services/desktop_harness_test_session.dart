import 'package:shared_preferences/shared_preferences.dart';

import 'session_store.dart';

/// URI login for the separate test Core. Never overwrites the installation's session.
class DesktopHarnessTestSession extends SessionStore {
  static const tokenKey = 'uri.desktopHarnessTest.session.token';
  static const usernameKey = 'uri.desktopHarnessTest.session.username';
  @override
  Future<PersistedSession?> load() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString(tokenKey);
    final username = prefs.getString(usernameKey);
    if (token == null || username == null) return null;
    return PersistedSession(token: token, username: username);
  }

  @override
  Future<void> save({required String token, required String username}) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(tokenKey, token);
    await prefs.setString(usernameKey, username);
  }

  @override
  Future<void> clear() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(tokenKey);
    await prefs.remove(usernameKey);
  }
}
