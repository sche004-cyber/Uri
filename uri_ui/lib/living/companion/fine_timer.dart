import 'dart:ffi';
import 'dart:io' show Platform;

/// Requests 1 ms timer resolution on Windows while a frame-rate cap is being
/// paced, and releases it afterwards.
///
/// Measured on the development PC (Windows 11 26200, 2026-10-09): Dart timers
/// fire on the default 15.6 ms system tick, so a 10 ms wait takes 15.6 ms and
/// a 20 ms wait takes 31 ms. Without this a 60 FPS cap would deliver about
/// 50 frames a second and a 90 FPS cap about 60. Since Windows 10 version 2004
/// the request applies to this process only; it changes no system setting.
/// Every other platform is a no-op.
class FineTimer {
  FineTimer._();

  static int _holds = 0;
  static int Function(int)? _begin;
  static int Function(int)? _end;
  static bool _loaded = false;

  /// Whether the resolution request is currently held.
  static bool get active => _holds > 0;

  static void request(bool on) {
    if (on) {
      if (_holds++ == 0) _call(true);
    } else if (_holds > 0) {
      if (--_holds == 0) _call(false);
    }
  }

  static void _call(bool begin) {
    if (!Platform.isWindows) return;
    try {
      if (!_loaded) {
        _loaded = true;
        final winmm = DynamicLibrary.open('winmm.dll');
        _begin = winmm
            .lookupFunction<Uint32 Function(Uint32), int Function(int)>(
              'timeBeginPeriod',
            );
        _end = winmm.lookupFunction<Uint32 Function(Uint32), int Function(int)>(
          'timeEndPeriod',
        );
      }
      (begin ? _begin : _end)?.call(1);
    } catch (_) {
      // Coarser pacing, never a crash.
    }
  }
}
