import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/services/paired_runtime.dart';
import 'package:uri_ui/services/supervised_runtime.dart';

/// Live bridge test: the REAL Dart runtime driving the REAL Phase 2 worker
/// profile against the REAL Phase 2 server profile (scripts/phase2ops_validate_ui_bridge.py
/// provisions both and sets URI_CLIENT_MANIFEST). Executor: the SYNTHETIC fake
/// harness through a persisted FIXTURE_ONLY record, which is why the worker is
/// spawned here with `--allow-fixture-qualification` (the production
/// `fromManifest` path can never pass that flag).
Future<ExecutionStatus> _until(SupervisedRuntime rt, String id, bool Function(ExecutionStatus) ok,
    {Duration timeout = const Duration(seconds: 60)}) async {
  final deadline = DateTime.now().add(timeout);
  ExecutionStatus? last;
  while (DateTime.now().isBefore(deadline)) {
    last = await rt.executionStatus(id);
    if (ok(last)) return last;
    await Future<void>.delayed(const Duration(milliseconds: 150));
  }
  throw StateError('timeout: ${last?.state} ${last?.reason}');
}

void main() {
  final manifestPath = Platform.environment['URI_CLIENT_MANIFEST'];
  test('Dart runtime drives the REAL supervised worker: lifecycle, mid-run cancel, reconnect', () async {
    final manifest = jsonDecode(File(manifestPath!).readAsStringSync()) as Map<String, dynamic>;
    expect(SupervisedWorkerRuntime.optInConfigured(manifestPath), isTrue);
    final sep = Platform.pathSeparator;
    final entry = '${manifest['source_root']}$sep${supervisedWorkerEntrypoint.replaceAll('/', sep)}';
    Future<SupervisedWorkerRuntime> spawn() => SupervisedWorkerRuntime.spawn(
        interpreter: manifest['interpreter'] as String,
        entrypoint: entry,
        manifestPath: manifestPath,
        workingDirectory: manifest['client_root'] as String,
        extraArgs: const ['--allow-fixture-qualification']);
    const session = '22222222-2222-4222-8222-222222222222';
    const claude = ReasoningChoice('client_external_harness', 'claude_code');
    var rt = await spawn();
    late String completedId;
    late String cancelledId;
    try {
      final pre = await rt.preflight();
      expect(pre['worker_profile'], 'phase2d-supervised');
      expect(pre['production_cutover'], false);
      expect(pre['mid_run_cancel'], true);
      final harnesses = await rt.discoverHarnesses();
      expect(harnesses.firstWhere((h) => h.id == 'claude_code').usable, isTrue);
      expect(harnesses.firstWhere((h) => h.id == 'codex_cli').usable, isFalse);
      expect((await rt.listExecutions()).executions, isEmpty);

      // 1. full lifecycle to a verified receipt
      final turn = await rt.startTurn(session, 'use the harness to write a greeting into out.txt', claude) as SupervisedTurn;
      expect(turn.needsApproval, isTrue);
      final p = turn.proposal!;
      expect(p.provider, 'claude_code');
      expect(p.expectedFile, 'out.txt');
      expect(p.qualification!['level'], 'FIXTURE_ONLY');
      final handle = await rt.beginExecution(turn.turnId!, p.approvalDigest!, p.proposalDigest);
      expect(handle.state, 'queued');
      completedId = handle.id;
      final done = await _until(rt, handle.id, (s) => s.isTerminal);
      expect(done.state, 'completed');
      expect(done.code, 'SETTLED_VERIFIED');
      expect(done.ledgerTaskState, 'COMPLETE');
      expect(done.journalState, 'verified');
      expect(done.serverTurnState, 'reply');
      expect(done.evidence.single['matched'], true);

      // 2. the frame loop stays responsive and a real mid-run cancel kills the harness
      const session2 = '33333333-3333-4333-8333-333333333333';
      final hang = await rt.startTurn(session2, 'use the harness to write a greeting into out.txt (fake scenario: hang)', claude) as SupervisedTurn;
      final h2 = await rt.beginExecution(hang.turnId!, hang.proposal!.approvalDigest!, hang.proposal!.proposalDigest);
      cancelledId = h2.id;
      final running = await _until(rt, h2.id, (s) => s.state == 'running' && (s.ledger?['attempts'] as List? ?? const []).any((a) => a['status'] == 'RUNNING' && a['pid'] != null));
      expect(running.state, 'running');
      final rep = await rt.cancelExecution(h2.id);
      expect((rep['kill'] as Map)['granted'], true);
      final ended = await _until(rt, h2.id, (s) => s.isTerminal);
      expect(ended.state, 'uncertain');
      expect(ended.reason, 'CANCELLED_AFTER_DISPATCH');
      expect(ended.cancelRequested, isTrue);
      expect((ended.ledger!['attempts'] as List).last['end_reason'], 'cancelled_killed');
      expect(ended.serverTurnState, 'execution_uncertain');
      expect(() => rt.cancelExecution(h2.id), throwsA(isA<PairedRuntimeException>()));
    } finally {
      await rt.close();
    }

    // 3. reconnect: a fresh worker (what a reopened UI gets) still knows both executions
    rt = await spawn();
    try {
      final listing = await rt.listExecutions();
      expect(listing.active, isNull);
      expect(listing.executions.map((e) => e.id).toSet(), {completedId, cancelledId});
      final again = await rt.executionStatus(completedId);
      expect(again.state, 'completed');
      expect(again.ledgerTaskState, 'COMPLETE');
      final gone = await rt.executionStatus(cancelledId);
      expect(gone.state, 'uncertain');
      expect(() => rt.beginExecution('t-stale', 'a' * 64, 'b' * 64), throwsA(isA<PairedRuntimeException>()));
    } finally {
      await rt.close();
    }
  }, skip: manifestPath == null ? 'needs URI_CLIENT_MANIFEST (scripts/phase2ops_validate_ui_bridge.py)' : false,
      timeout: const Timeout(Duration(minutes: 5)));
}
