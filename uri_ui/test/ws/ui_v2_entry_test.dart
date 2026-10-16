// UI V2 completion (BLK-INT-1): the production integrated entry opens the V2
// presentation; URI_UI_VISUAL=living keeps the earlier living composition.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/working_system_app.dart';

void main() {
  test('V2 is the default integrated presentation', () {
    expect(useVisualV2(null), isTrue);
    expect(useVisualV2(''), isTrue);
    expect(useVisualV2('v2'), isTrue);
  });

  test('URI_UI_VISUAL=living keeps the earlier composition', () {
    expect(useVisualV2('living'), isFalse);
    expect(useVisualV2(' Living '), isFalse);
  });

  test('production main wires V2 and the companion window only on the integrated path', () {
    final source = File('lib/main.dart').readAsStringSync();
    final integrated = source.indexOf('WorkerIntegratedRuntime.optInConfigured');
    final classic = source.indexOf('AppState(HttpUriClient(deviceId: deviceId))');
    expect(integrated, greaterThan(0));
    expect(classic, greaterThan(integrated));
    final branch = source.substring(integrated, classic);
    expect(branch, contains("useVisualV2(Platform.environment['URI_UI_VISUAL'])"));
    expect(branch, contains('visualV2: visualV2'));
    expect(branch, contains('services.updateCompanionWindow'));
    expect(branch, contains('services.moveCompanionWindow'));
    expect(branch, contains('services.readCompanionPointer'));
    // The classic path leaves the shaped companion window before it opens.
    expect(branch, contains('CompanionWindowLayout(active: false, orb: Rect.zero)'));
    // The unpaired (classic UriApp) path is unchanged: no V2 window adapter.
    expect(source.substring(classic), isNot(contains('CompanionWindowAdapter')));
  });
}
