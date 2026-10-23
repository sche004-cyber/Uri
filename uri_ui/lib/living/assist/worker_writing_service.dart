import 'dart:async';

import '../../services/integrated_runtime.dart';
import '../integration/scheduler_client.dart' show SchedulerApiError;
import '../office/writing_assist.dart';

/// Writing Intelligence (plan 16, WI-A) over the integrated worker's Assist commands, for text the owner writes in
/// URI itself (the composer). Checks are local and fast; Brain work runs as a job the worker stops when a user turn
/// starts, and its result is read with `assist_write_status`. Refusals arrive as [SchedulerApiError] codes so the
/// strip can say them in words.
class WorkerWritingService implements WritingService {
  WorkerWritingService(this.runtime, {this.pollEvery = const Duration(milliseconds: 300),
      this.timeout = const Duration(seconds: 150)});

  final IntegratedRuntime? Function() runtime;
  final Duration pollEvery;
  final Duration timeout;

  Future<Map<String, dynamic>> _call(Map<String, dynamic> command) async {
    final rt = runtime();
    if (rt == null) throw SchedulerApiError('WORKER_NOT_CONNECTED', null);
    try {
      return await rt.call(command);
    } on IntegratedRuntimeException catch (e) {
      throw SchedulerApiError(e.code, null);
    }
  }

  @override
  Future<Map<String, dynamic>> writingCheck(String text, {List<String> ignore = const []}) =>
      _call({'command': 'assist_write_check', 'text': text, 'ignore': ignore});

  @override
  Future<Map<String, dynamic>> writingApply(String text, List<Map<String, dynamic>> accepted) =>
      _call({'command': 'assist_write_apply', 'text': text, 'accepted': accepted});

  Future<Map<String, dynamic>> _brain(Map<String, dynamic> command) async {
    final id = (await _call(command))['write_id'] as String;
    final end = DateTime.now().add(timeout);
    while (DateTime.now().isBefore(end)) {
      await Future<void>.delayed(pollEvery);
      final s = await _call({'command': 'assist_write_status', 'write_id': id});
      if (s['state'] != 'FINISHED') continue;
      if (s['status'] != 'COMPLETE') throw SchedulerApiError('${s['error'] ?? s['status']}', null);
      return s;
    }
    throw SchedulerApiError('WRITING_TIMEOUT', null);
  }

  @override
  Future<Map<String, dynamic>> writingProofread(String text) =>
      _brain({'command': 'assist_write_brain', 'text': text, 'op': 'proofread'});

  @override
  Future<Map<String, dynamic>> writingRewrite(String text, String tone) =>
      _brain({'command': 'assist_write_brain', 'text': text, 'op': 'rewrite', 'tone': tone});

  @override
  Future<Map<String, dynamic>> writingComplete(String text) =>
      _brain({'command': 'assist_write_brain', 'text': text, 'op': 'complete'});

  @override
  Future<void> writingPrewarm() async {
    try {
      await _call({'command': 'assist_write_check', 'text': ''});
    } catch (_) {}
  }
}
