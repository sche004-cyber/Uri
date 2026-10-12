import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/services/paired_runtime.dart';

/// Live bridge test: runs only when scripts/validate_c6_bridge.py provides a
/// real isolated server + provisioned client via URI_CLIENT_MANIFEST.
void main() {
  final manifest = Platform.environment['URI_CLIENT_MANIFEST'];
  test('Dart bridge drives the REAL worker and server', () async {
    final runtime = (await WorkerPairedRuntime.fromManifest(manifest))!;
    try {
      final harnesses = await runtime.discoverHarnesses();
      expect(harnesses.every((h) => !h.usable), isTrue);
      expect(harnesses.firstWhere((h) => h.id == 'antigravity').qualification, 'REFUSED');
      final turn = await runtime.startTurn(
          '11111111-1111-4111-8111-111111111111', 'remember that dart bridge fact', ReasoningChoice.noBrain);
      expect(turn.needsApproval, isTrue);
      final done = await runtime.decide(turn.turnId!, true);
      expect(done.code, 'SETTLED_VERIFIED');
      final blocked = await runtime.startTurn('11111111-1111-4111-8111-111111111111', 'remember that x',
          const ReasoningChoice('client_external_harness', 'claude_code'));
      expect(blocked.code, 'ADAPTER_NOT_QUALIFIED');
    } finally {
      await runtime.close();
    }
  }, skip: manifest == null ? 'needs URI_CLIENT_MANIFEST (scripts/validate_c6_bridge.py)' : false);
}
