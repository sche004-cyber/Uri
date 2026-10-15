import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_sources.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'ws_hardening_test.dart' show HardeningRuntime;

class DelayedReadinessRuntime extends HardeningRuntime {
  DelayedReadinessRuntime(this.delayedCommand);
  final String delayedCommand;
  final pending = Completer<Map<String, dynamic>>();
  final entered = Completer<void>();
  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) {
    if (command['command'] == delayedCommand) {
      commands.add(command);
      if (!entered.isCompleted) entered.complete();
      return pending.future;
    }
    return super.call(command);
  }
}

void main() {
  for (final command in ['brain_status', 'harness_discover']) {
    for (final error in [false, true]) {
      test('readiness discards $command after dispose ($error)', () async {
        final rt = DelayedReadinessRuntime(command);
        final conv = OiConversation(rt);
        final source = OiReadinessSource(conv);
        var notices = 0;
        source.addListener(() => notices++);
        final future = source.refresh();
        await rt.entered.future;
        notices = 0;
        source.dispose();
        if (error) {
          rt.pending.completeError(IntegratedRuntimeException('WORKER_CLOSED'));
        } else {
          rt.pending.complete({'state': 'READY', 'harnesses': [{'harness_id': 'late', 'usable': true}]});
        }
        await expectLater(future, completes);
        expect(notices, 0);
        expect(source.harnesses, isEmpty);
        if (command == 'brain_status') {
          expect(rt.commands.where((x) => x['command'] == 'harness_discover'), isEmpty);
        }
        conv.dispose();
        await rt.close();
      });
    }
  }
  test('readiness does not start reads after disposal', () async {
    final rt = HardeningRuntime();
    final conv = OiConversation(rt);
    final source = OiReadinessSource(conv)..dispose();
    await expectLater(source.refresh(), completes);
    expect(rt.commands, isEmpty);
    conv.dispose();
    await rt.close();
  });
  for (final error in [false, true]) {
    test('readiness discards discovery from replaced worker ($error)', () async {
      final rt = DelayedReadinessRuntime('harness_discover');
      final replacement = HardeningRuntime(name: 'replacement');
      final conv = OiConversation(rt);
      final source = OiReadinessSource(conv);
      var notices = 0;
      source.addListener(() => notices++);
      final future = source.refresh();
      await rt.entered.future;
      notices = 0;
      conv.runtime = replacement;
      if (error) {
        rt.pending.completeError(IntegratedRuntimeException('WORKER_CLOSED'));
      } else {
        rt.pending.complete({'harnesses': [{'harness_id': 'old', 'usable': true}]});
      }
      await expectLater(future, completes);
      expect(notices, 0);
      expect(source.harnesses, isEmpty);
      source.dispose();
      conv.dispose();
      await rt.close();
      await replacement.close();
    });
  }
}
