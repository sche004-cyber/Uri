import 'dart:convert';
import 'dart:io';

import 'package:flutter_driver/flutter_driver.dart';

// Explicitly authorized fixed disposable task, using the native UI controls.
Future<void> main(List<String> args) async {
  if (args.length != 1) throw ArgumentError('Expected local VM service URL');
  final driver = await FlutterDriver.connect(dartVmServiceUrl: args.single);
  try {
    await driver.runUnsynchronized(() async {
      await driver.tap(find.byValueKey('desktop-harness-prepare'));
      await driver.waitForTappable(find.byValueKey('desktop-harness-approve'));
      await driver.tap(find.byValueKey('desktop-harness-approve'));
      final deadline = DateTime.now().add(const Duration(seconds: 180));
      while (DateTime.now().isBefore(deadline)) {
        final data = await driver.requestData('harness-receipt');
        if (data != 'null') {
          final receipt = jsonDecode(data) as Map<String, dynamic>;
          final pretty = const JsonEncoder.withIndent('  ').convert(receipt);
          await File('../docs/plans/DESKTOP_HARNESS_DESKTOP_RESULT.json')
              .writeAsString('$pretty\n');
          stdout.writeln(pretty);
          if (receipt['verified'] != true || receipt['execution_ok'] != true) {
            exitCode = 1;
          }
          return;
        }
        await Future<void>.delayed(const Duration(seconds: 1));
      }
      throw StateError('No desktop receipt within 180 seconds; do not retry');
    });
  } finally {
    await driver.close();
  }
}
