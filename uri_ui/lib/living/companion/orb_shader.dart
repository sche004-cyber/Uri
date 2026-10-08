import 'dart:ui' show FragmentProgram;

import 'package:flutter/foundation.dart';

/// Loads the Energy Orb core shader once per process and never throws.
///
/// The orb must render with or without the shader (reduced-effects mode,
/// a platform without runtime-shader support, a missing asset in some
/// test harness), so a failed load degrades to `null` and the painter
/// draws its own gradient core. The failure reason is kept for the
/// diagnostics panel; it is never shown as an error to the user.
class OrbShaderCache {
  OrbShaderCache._();

  static const String assetKey = 'shaders/orb_core.frag';

  static Future<FragmentProgram?>? _loading;
  static FragmentProgram? _program;
  static String? _failure;

  static FragmentProgram? get programIfLoaded => _program;
  static String? get lastFailure => _failure;

  /// Test hook: forget any cached outcome.
  @visibleForTesting
  static void reset() {
    _loading = null;
    _program = null;
    _failure = null;
  }

  static Future<FragmentProgram?> load() {
    return _loading ??= _doLoad();
  }

  static Future<FragmentProgram?> _doLoad() async {
    try {
      final program = await FragmentProgram.fromAsset(assetKey);
      _program = program;
      _failure = null;
      return program;
    } catch (error) {
      _program = null;
      _failure = error.toString();
      return null;
    }
  }
}
