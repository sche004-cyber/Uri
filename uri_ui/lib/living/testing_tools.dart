import 'dart:io' show Platform;

/// UIV2-F2: testing-only composer controls (simulated speech transcript,
/// typed dictation) are hidden from ordinary users. Developers and the
/// live qualification harness turn them on with `URI_UI_TESTING_TOOLS=1`
/// (read once at start, like `URI_UI_VISUAL`); tests set [enabled].
class UriTestingTools {
  UriTestingTools._();

  static bool? _override;

  static bool get enabled =>
      _override ?? fromEnvironment(Platform.environment['URI_UI_TESTING_TOOLS']);

  static set enabled(bool? on) => _override = on;

  static bool fromEnvironment(String? value) {
    final v = (value ?? '').trim().toLowerCase();
    return v == '1' || v == 'true' || v == 'on' || v == 'yes';
  }
}
