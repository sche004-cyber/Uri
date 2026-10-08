import 'dart:convert';
import 'dart:io';

import 'package:flutter_driver/flutter_driver.dart';

// Real native app controls. No credentials inspected and no automatic task retry.
Future<void> main(List<String> args) async {
  final driver = await FlutterDriver.connect(dartVmServiceUrl: args[0]);
  final step = args.length > 1 ? args[1] : 'capture';
  final output = Directory('../docs/plans/HARNESS_DESKTOP_COMPLETION_EVIDENCE');
  await output.create(recursive: true);
  Future<void> capture(String name) async {
    final encoded = await driver.requestData('harness-screenshot');
    await File('${output.path}/$name.png').writeAsBytes(base64Decode(encoded));
    stdout.writeln('Saved $name.png');
  }

  try {
    await driver.runUnsynchronized(() async {
      if (step == 'keyboard') {
        await driver.setTextEntryEmulation(enabled: false);
        return;
      } else if (step == 'signup') {
        await driver.setTextEntryEmulation(enabled: true);
        // Disposable local URI account, never a provider account or token transfer.
        final stamp = DateTime.now().microsecondsSinceEpoch.toString();
        await driver.tap(find.byValueKey('uri-login-username'));
        await driver.enterText('harness_$stamp');
        await driver.tap(find.byValueKey('uri-login-password'));
        await driver.enterText('Disposable-$stamp-Qualification!');
        await driver.tap(find.text('New here? Create an account'));
        await driver.tap(find.text('Create account'));
        await Future<void>.delayed(const Duration(seconds: 2));
      } else if (step == 'management') {
        await driver.tap(find.byValueKey('harness-management'));
        await Future<void>.delayed(const Duration(seconds: 8));
      } else if (step == 'quota_recovery') {
        await driver.tap(find.text('Refresh task status'));
        await Future<void>.delayed(const Duration(seconds: 1));
      } else if (step == 'antigravity_details') {
        await driver.scroll(
          find.descendant(
            of: find.byType('AlertDialog'),
            matching: find.byType('SingleChildScrollView'),
          ),
          0,
          -300,
          const Duration(milliseconds: 500),
        );
      } else if (step == 'select') {
        await driver.tap(
          find.byValueKey('select-claude_code'),
          timeout: const Duration(seconds: 10),
        );
      } else if (step == 'prepare') {
        await driver.tap(find.byValueKey('desktop-harness-prepare'));
        await driver.waitForTappable(
          find.byValueKey('desktop-harness-approve'),
        );
      } else if (step == 'execute') {
        await driver.tap(find.byValueKey('desktop-harness-approve'));
        await Future<void>.delayed(const Duration(milliseconds: 500));
        await capture('execution');
        final deadline = DateTime.now().add(const Duration(seconds: 180));
        while (DateTime.now().isBefore(deadline)) {
          final raw = await driver.requestData('harness-receipt');
          if (raw != 'null') {
            final receipt = jsonDecode(raw) as Map<String, dynamic>;
            await File('${output.path}/fresh_claude_receipt.json')
                .writeAsString(
                  '${const JsonEncoder.withIndent('  ').convert(receipt)}\n',
                );
            stdout.writeln(jsonEncode(receipt));
            await capture('result');
            if (receipt['status'] == 'QUOTA_INTERRUPTED') {
              await capture('quota_recovery');
            }
            return;
          }
          await Future<void>.delayed(const Duration(seconds: 1));
        }
        throw StateError(
          'No final receipt; outcome unknown. No automatic retry.',
        );
      }
      await Future<void>.delayed(const Duration(milliseconds: 500));
      await capture(step);
    });
  } finally {
    await driver.setTextEntryEmulation(enabled: false);
    await driver.close();
  }
}
