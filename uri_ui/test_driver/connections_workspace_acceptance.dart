import 'dart:convert';
import 'dart:io';

import 'package:flutter_driver/flutter_driver.dart';

Future<void> main(List<String> args) async {
  final driver = await FlutterDriver.connect(dartVmServiceUrl: args[0]);
  final output = Directory(
    '../docs/plans/HARNESS_CONNECTIONS_CONSOLE_EVIDENCE',
  );
  await output.create(recursive: true);
  Future<void> capture(String name) async {
    await File('${output.path}/$name.png').writeAsBytes(
      base64Decode(await driver.requestData('harness-screenshot')),
    );
    stdout.writeln('Captured $name');
  }

  try {
    await driver.runUnsynchronized(() async {
      try {
        await driver.tap(
          find.byValueKey('expand_btn'),
          timeout: const Duration(seconds: 2),
        );
      } catch (_) {}
      await driver.tap(find.descendant(of: find.byType('_Sidebar'), matching: find.text('Home')));
      await capture('home');
      await driver.tap(find.descendant(of: find.byType('_Sidebar'), matching: find.text('Settings')));
      await capture('settings');
      await driver.tap(find.descendant(of: find.byType('_Sidebar'), matching: find.text('Connections & Providers')));
      await driver.tap(find.byValueKey('connections-models'));
      await Future<void>.delayed(const Duration(seconds: 2));
      await capture('models');
      await driver.tap(find.byValueKey('connections-plugins'));
      await Future<void>.delayed(const Duration(seconds: 1));
      await capture('plugins');
      await driver.tap(find.byValueKey('connections-harnesses'));
      await Future<void>.delayed(const Duration(seconds: 12));
      await capture('harnesses');
      await driver.tap(find.byValueKey('harness-details-codex'));
      await driver.scroll(
        find.byType('SingleChildScrollView'),
        0,
        -380,
        const Duration(milliseconds: 500),
      );
      await Future<void>.delayed(const Duration(milliseconds: 400));
      await capture('codex_details');
      await driver.tap(find.descendant(of: find.byType('_Sidebar'), matching: find.text('Chat')));
      await driver.tap(find.byValueKey('workspace-harness-tab'));
      await Future<void>.delayed(const Duration(milliseconds: 500));
      await capture('workspace');
      await driver.scrollIntoView(find.byValueKey('harness-console-inspection'));
      await driver.tap(find.text('Console inspection'));
      await driver.scrollIntoView(find.byValueKey('harness-runtime-refresh'));
      await driver.tap(find.byValueKey('harness-runtime-refresh'));
      await Future<void>.delayed(const Duration(seconds: 2));
      await capture('console_inspection');
      await driver.tap(find.descendant(of: find.byType('_Sidebar'), matching: find.text('Home')));
      await capture('home_after_workspace');
      await driver.tap(find.descendant(of: find.byType('_Sidebar'), matching: find.text('Chat')));
      await driver.tap(find.byValueKey('workspace-harness-tab'));
    });
  } finally {
    await driver.close();
  }
}
