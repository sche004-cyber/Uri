import 'dart:io' show Platform;

import 'package:window_manager/window_manager.dart';

import '../living/companion/frame_clock.dart';

/// Suspends the companion's frame clock while the desktop window is
/// minimised.
///
/// Measured on Windows 11 with Flutter 3.47.2 (2026-10-09): minimising the
/// window reports only `AppLifecycleState.inactive`, never `hidden`, leaves
/// the view size unchanged, and the engine keeps producing about 64 frames a
/// second for an animation that still asks for them. The lifecycle alone
/// cannot tell a minimised window from an unfocused but visible one, so the
/// window's own minimise and restore events (window_manager, already a
/// dependency of this app) decide instead.
///
/// Call once from an entry point after `WidgetsFlutterBinding` is ready. The
/// returned callback removes the window listener (call it when the clock is
/// disposed before the process ends). Any failure leaves the clock running as
/// before and returns a no-op.
Future<void Function()> bindWindowVisibility(CompanionFrameClock clock) async {
  if (!(Platform.isWindows || Platform.isLinux || Platform.isMacOS)) {
    return () {};
  }
  try {
    await windowManager.ensureInitialized();
    final listener = _ClockWindowListener(clock);
    windowManager.addListener(listener);
    clock.setHidden(await windowManager.isMinimized());
    return () => windowManager.removeListener(listener);
  } catch (_) {
    // No window plugin (a test, an unsupported embedder): keep animating.
    return () {};
  }
}

class _ClockWindowListener with WindowListener {
  _ClockWindowListener(this.clock);
  final CompanionFrameClock clock;

  @override
  void onWindowMinimize() => clock.setHidden(true);

  @override
  void onWindowRestore() => clock.setHidden(false);

  @override
  void onWindowMaximize() => clock.setHidden(false);

  @override
  void onWindowFocus() => clock.setHidden(false);
}
