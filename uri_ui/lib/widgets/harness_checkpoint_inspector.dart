import 'dart:convert';

import 'package:flutter/material.dart';

import '../models/system_performance.dart';
import '../services/desktop_harness_test_client.dart';
import '../services/uri_client.dart' show ModelStatus;

/// Read-only presentation of existing URI checkpoint/receipt APIs.
/// This is part of the provisional harness console, not a new log backend.
class HarnessCheckpointInspector extends StatefulWidget {
  const HarnessCheckpointInspector({
    super.key,
    required this.client,
    required this.pending,
    required this.task,
    required this.savedTasks,
    required this.desktopDurationMs,
    required this.onSelect,
  });
  final DesktopHarnessTestClient client;
  final Map<String, dynamic>? pending, task;
  final List<Map<String, dynamic>> savedTasks;
  final int? desktopDurationMs;
  final ValueChanged<Map<String, dynamic>>? onSelect;

  @override
  State<HarnessCheckpointInspector> createState() =>
      _HarnessCheckpointInspectorState();
}

class _HarnessCheckpointInspectorState
    extends State<HarnessCheckpointInspector> {
  String query = '', category = 'All fields';
  bool loading = false, checked = false;
  ModelStatus? model;
  SystemPerformanceSnapshot? performance;
  String? snapshotError;

  Future<void> refreshRuntime() async {
    final token = widget.client.uri.authToken;
    setState(() => loading = true);
    try {
      final values = await Future.wait([
        widget.client.uri.getModelStatus(),
        widget.client.uri.loadSystemPerformance(),
      ]);
      if (!mounted || widget.client.uri.authToken != token) return;
      setState(() {
        checked = true;
        model = values[0] as ModelStatus?;
        performance = values[1] as SystemPerformanceSnapshot?;
        snapshotError = null;
      });
    } catch (_) {
      if (!mounted || widget.client.uri.authToken != token) return;
      setState(() {
        checked = true;
        model = null;
        performance = null;
        snapshotError = 'Runtime snapshot unavailable.';
      });
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final record = widget.task;
    final receipt = record?['receipt'];
    final sections = <String, Map<String, dynamic>>{
      if (record != null)
        'Checkpoint': {
          for (final entry in record.entries)
            if (entry.key != 'receipt') entry.key: entry.value,
        },
      if (receipt is Map<String, dynamic>) 'Receipt': receipt,
      if (widget.pending != null) 'Approval request': widget.pending!,
      if (widget.desktopDurationMs != null)
        'Desktop measurement': {
          'application_round_trip_ms': widget.desktopDurationMs,
          'scope':
              'Start request to first terminal poll, including polling delay',
        },
    };
    final rows = <String>[];
    for (final section in sections.entries) {
      if (category != 'All fields' && category != section.key) continue;
      for (final entry in section.value.entries) {
        final line = '${section.key}.${entry.key}: ${jsonEncode(entry.value)}';
        if (line.toLowerCase().contains(query.toLowerCase())) rows.add(line);
      }
    }
    // A checkpoint is not an event stream. Never manufacture historical events
    // or approval decisions from the current status.
    return ExpansionTile(
      key: const ValueKey('harness-console-inspection'),
      title: const Text('Console inspection'),
      subtitle: const Text('Recorded checkpoints, approvals and URI receipts'),
      expandedCrossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Read-only inspection of this URI account. Checkpoints are current snapshots; '
          'full event streams and native CLI transcripts are not exposed by this API.',
        ),
        for (final saved in widget.savedTasks)
          TextButton(
            key: ValueKey('inspect-task-${saved['task_id']}'),
            onPressed: widget.onSelect == null
                ? null
                : () => widget.onSelect!(saved),
            child: Text('${saved['task_id']} · ${saved['status']}'),
          ),
        if (widget.savedTasks.isEmpty)
          const Text('No saved checkpoints loaded. Use Refresh saved tasks.'),
        if (record != null) ...[
          Text('Progress: ${record['progress'] ?? 'unavailable'}'),
          Text(
            'Verified completed work: ${record['verified_completed_work'] ?? 'unavailable'}',
          ),
          Text(
            'Potentially non-idempotent: ${record['potentially_non_idempotent'] ?? 'unavailable'}',
          ),
          Text(
            'Interruption/error: ${receipt is Map ? receipt['error_family'] ?? 'not recorded' : 'receipt unavailable'}',
          ),
          Text('Recovery: ${record['recommendation'] ?? 'not recorded'}'),
        ],
        const Text(
          'Permissions: fixed disposable Amount-column repair only; no shell, web, '
          'native plugins, MCP or write-back. Full historical permission decisions '
          'are not exposed. Preparing a test does not authorize execution.',
        ),
        TextField(
          key: const ValueKey('harness-console-search'),
          decoration: const InputDecoration(
            labelText: 'Search recorded fields',
          ),
          onChanged: (value) => setState(() => query = value),
        ),
        DropdownButton<String>(
          value: sections.containsKey(category) ? category : 'All fields',
          items: [
            for (final value in ['All fields', ...sections.keys])
              DropdownMenuItem(value: value, child: Text(value)),
          ],
          onChanged: (value) => setState(() => category = value!),
        ),
        SelectableText(
          rows.isEmpty ? 'No matching recorded fields.' : rows.join('\n'),
          key: const ValueKey('harness-console-fields'),
        ),
        TextButton(
          key: const ValueKey('harness-runtime-refresh'),
          onPressed: loading ? null : refreshRuntime,
          child: Text(
            loading ? 'Reading runtime…' : 'Refresh runtime snapshot',
          ),
        ),
        if (checked) ...[
          if (snapshotError != null) Text(snapshotError!),
          Text(
            model == null
                ? 'Current URI model: unavailable'
                : 'Current URI model: ${model!.providerName} · ${model!.modelName} · '
                      '${model!.available ? 'available' : 'unavailable'} (${model!.location})',
          ),
          Text(
            performance == null
                ? 'Host resource measurements: unavailable'
                : 'Host CPU: ${performance!.cpuPercent}% · '
                      'Host memory: ${performance!.memoryUsedPercent}% used',
          ),
        ],
        const Text(
          'Provider/model status comes from the existing capabilities API; it is '
          'not evidence of an Edge model being loaded. Host readings are not '
          'per-model measurements. Edge loading, GPU usage and stage-level '
          'model latency are unavailable here.',
        ),
      ],
    );
  }
}
