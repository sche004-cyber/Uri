import 'dart:async';
import 'dart:io';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:window_manager/window_manager.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../living/presentation/companion_window_layout.dart';

/// Candidate-only native view adapter. Serialized transitions prevent stale
/// compact resizing from winning over a rapid dashboard transition.
class CompanionWindowAdapter {
  CompanionWindowAdapter() {
    _channel.setMethodCallHandler((call) async {
      if (call.method == 'metricsChanged' && _last != null) {
        await update(_last!);
      }
    });
  }
  static const _channel = MethodChannel('uri/companion_window');
  bool _active = false;
  bool _wasMaximized = false;
  Rect? _previous;
  CompanionWindowLayout? _last;
  String? lastError;
  Future<void> _pending = Future.value();
  Future<void> update(CompanionWindowLayout layout) {
    _last = layout;
    _pending = _pending.then((_) => _update(layout)).catchError((Object error) {
      lastError = 'Native Companion window unavailable: ${error.runtimeType}';
    });
    return _pending;
  }

  Future<void> _update(CompanionWindowLayout layout) async {
    if (!Platform.isWindows) return;
    lastError = null;
    if (_active != layout.active) {
      if (layout.active) {
        _previous = await windowManager.getBounds();
        _wasMaximized = await windowManager.isMaximized();
        if (_wasMaximized) await windowManager.unmaximize();
        await windowManager.setMinimumSize(Size.zero);
        await windowManager.setMaximumSize(const Size(100000, 100000));
        await windowManager.setAsFrameless();
        await windowManager.setBackgroundColor(Colors.transparent);
        await windowManager.setSize(const Size(440, 680));
        final prefs = await SharedPreferences.getInstance();
        try {
          final saved = jsonDecode(
            prefs.getString('uri.v2.companion.position') ?? 'null',
          );
          if (saved is List &&
              saved.length == 2 &&
              saved.every((v) => v is num && v.isFinite)) {
            await windowManager.setPosition(
              Offset(
                (saved[0] as num).toDouble(),
                (saved[1] as num).toDouble(),
              ),
            );
          }
        } catch (_) {
          /* Obsolete placement falls back to current monitor. */
        }
        await windowManager.setResizable(false);
      } else {
        await _channel.invokeMethod<void>('regions', {'active': false});
        await windowManager.setBackgroundColor(Colors.white);
        await windowManager.setTitleBarStyle(TitleBarStyle.normal);
        await windowManager.setResizable(true);
        if (_previous != null) await windowManager.setBounds(_previous!);
        if (_wasMaximized) await windowManager.maximize();
      }
      _active = layout.active;
    }
    // Native region union excludes all unrelated desktop hit areas. Native
    // clamping uses the current monitor work area, including negative origins.
    await _channel.invokeMethod<void>('regions', layout.toJson());
  }

  /// Own-window cursor coordinates only; no global hooks or observation.
  Future<Offset?> cursorPosition() async {
    if (!Platform.isWindows) return null;
    try {
      final point = await _channel.invokeListMethod<double>('cursor');
      return point?.length == 2 ? Offset(point![0], point[1]) : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> move() async {
    if (Platform.isWindows) {
      await windowManager.startDragging();
      await _channel.invokeMethod<void>('clamp');
      final position = await windowManager.getPosition();
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString(
        'uri.v2.companion.position',
        jsonEncode([position.dx, position.dy]),
      );
    }
  }
}
