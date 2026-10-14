// Simulation regression for the race observed in the actual main Windows app.
import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'ws_hardening_test.dart' show HardeningRuntime;

class DelayedRefreshRuntime extends HardeningRuntime {
  final pending = Completer<Map<String, dynamic>>();
  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) {
    commands.add(command);
    return pending.future;
  }
}

void main() {
  final reads = <String, Future<void> Function(OiConversation)>{
    'status': (c) => c.refreshStatus(),
    'health': (c) => c.refreshHealth(),
    'memory': (c) => c.refreshMemory(),
    'cloud': (c) => c.refreshCloud(),
    'draft': (c) => c.refreshDraft(),
  };
  for (final entry in reads.entries) {
    for (final error in [false, true]) {
      test('${entry.key} completion after dispose is discarded (${error ? 'error' : 'success'})', () async {
        final rt = DelayedRefreshRuntime();
        final conv = OiConversation(rt);
        var notifications = 0;
        conv.addListener(() => notifications++);
        final future = entry.value(conv);
        expect(rt.commands, hasLength(1));
        conv.dispose();
        if (error) {
          rt.pending.completeError(IntegratedRuntimeException('WORKER_CLOSED'));
        } else {
          rt.pending.complete({'state': 'READY', 'facts': ['late fact'], 'draft': null});
        }
        await expectLater(future, completes);
        expect(notifications, 0);
        expect(rt.commands, hasLength(1), reason: 'No subsequent worker read after owner disposal');
        expect(conv.brainStatus, isEmpty);
        expect(conv.memory, isEmpty);
        expect(conv.cloud, isEmpty);
        expect(conv.lastError, isNull);
        await rt.close();
      });
    }
    test('${entry.key} refresh does not start after disposal', () async {
      final rt = DelayedRefreshRuntime();
      final conv = OiConversation(rt)..dispose();
      final future = entry.value(conv);
      // Completing a hypothetical late worker future also bounds a broken old implementation.
      if (rt.commands.isNotEmpty) rt.pending.completeError(IntegratedRuntimeException('WORKER_CLOSED'));
      await expectLater(future, completes);
      expect(rt.commands, isEmpty);
      await rt.close();
    });
  }
}
