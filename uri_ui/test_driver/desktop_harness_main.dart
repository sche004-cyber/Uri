import 'dart:convert';
import 'dart:ui' as ui;

import 'package:flutter/rendering.dart';

import 'package:flutter_driver/driver_extension.dart';

import 'package:uri_ui/main.dart' as application;
import 'package:uri_ui/widgets/desktop_harness_test.dart';

/// Local test entry point only; never used by normal URI builds.
Future<void> main() async {
  enableFlutterDriverExtension(
    enableTextEntryEmulation: false,
    handler: (message) async {
      if (message == 'harness-screenshot') {
        final boundary =
            DesktopHarnessTest.captureKey.currentContext!.findRenderObject()
                as RenderRepaintBoundary;
        final image = await boundary.toImage(pixelRatio: 1);
        try {
          final data = await image.toByteData(format: ui.ImageByteFormat.png);
          return base64Encode(data!.buffer.asUint8List());
        } finally {
          image.dispose();
        }
      }
      if (message != 'harness-receipt') return 'unsupported';
      return jsonEncode(DesktopHarnessTest.lastRunReceipt);
    },
  );
  application.main();
}
