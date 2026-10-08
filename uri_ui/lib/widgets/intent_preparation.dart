import 'package:flutter/material.dart';

import '../services/desktop_harness_test_client.dart';
import '../theme/uri_theme.dart';

/// Preparation only; Accept confirms meaning and never invokes a harness.
class IntentPreparation extends StatefulWidget {
  const IntentPreparation({
    super.key,
    required this.client,
    required this.providers,
    required this.initialData,
    required this.onChanged,
  });
  final DesktopHarnessTestClient client;
  final List<Map<String, dynamic>> providers;
  final Map<String, dynamic>? initialData;
  final ValueChanged<Map<String, dynamic>?> onChanged;

  @override
  State<IntentPreparation> createState() => _IntentPreparationState();
}

class _IntentPreparationState extends State<IntentPreparation> {
  final request = TextEditingController();
  final response = TextEditingController();
  Map<String, dynamic>? data;
  bool busy = false, correcting = false;
  String? error, owner;
  double? userVisibleMs;

  @override
  void initState() {
    super.initState();
    data = widget.initialData;
    owner = widget.client.uri.authToken;
  }

  @override
  void didUpdateWidget(covariant IntentPreparation oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (owner != widget.client.uri.authToken) {
      owner = widget.client.uri.authToken;
      data = null;
      request.clear();
      response.clear();
      error = null;
      correcting = false;
    }
  }

  @override
  void dispose() {
    request.dispose();
    response.dispose();
    super.dispose();
  }

  Future<void> send(String operation, Map<String, dynamic> body) async {
    if (busy) return;
    final token = widget.client.uri.authToken;
    final responseWatch = Stopwatch()..start();
    setState(() {
      busy = true;
      error = null;
      userVisibleMs = null;
    });
    try {
      final next = await widget.client.intent(
        operation == 'begin'
            ? 'begin'
            : '${Uri.encodeComponent(data!['cycle_id'] as String)}/$operation',
        body,
      );
      if (!mounted || token != widget.client.uri.authToken) return;
      setState(() {
        data = next;
        response.clear();
        correcting = false;
      });
      widget.onChanged(next);
      WidgetsBinding.instance.addPostFrameCallback((_) {
        responseWatch.stop();
        if (mounted && token == widget.client.uri.authToken) {
          setState(
            () => userVisibleMs = responseWatch.elapsedMicroseconds / 1000,
          );
        }
      });
    } catch (_) {
      if (mounted && token == widget.client.uri.authToken) {
        setState(
          () => error = 'Intent preparation unavailable. Your accepted task has not been executed.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Map<String, dynamic> revision([Map<String, dynamic> fields = const {}]) => {
    'revision': data!['revision'],
    ...fields,
  };

  Widget items(String label, Object? value) {
    final lines = value is List
        ? value.map((v) => v.toString()).join('\n')
        : value?.toString() ?? '';
    if (lines.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: UriSpace.sm),
      child: Text('$label\n$lines'),
    );
  }

  @override
  Widget build(BuildContext context) {
    final audit = data?['audit'] as Map<String, dynamic>?;
    final status = data?['status'];
    return ExpansionTile(
      key: const ValueKey('intent-preparation'),
      title: const Text('Understand and prepare a task'),
      subtitle: const Text(
        'Provisional · acceptance confirms intent, not execution',
      ),
      expandedCrossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (data == null) ...[
          TextField(
            key: const ValueKey('intent-request'),
            controller: request,
            maxLength: 2000,
            minLines: 1,
            maxLines: 4,
            decoration: const InputDecoration(
              labelText: 'What would you like to accomplish?',
            ),
          ),
          TextButton(
            key: const ValueKey('intent-understand'),
            onPressed: busy
                ? null
                : () => send('begin', {
                    'session_id': widget.client.uri.sessionId,
                    'request': request.text,
                  }),
            child: const Text('Understand request'),
          ),
        ],
        if (error != null) Text(error!),
        if (busy) const LinearProgressIndicator(),
        if (data != null)
          Text('Clarification questions: ${data!['questions_asked']} / 5'),
        if (data != null)
          TextButton(
            key: const ValueKey('intent-new-task'),
            onPressed: busy
                ? null
                : () {
                    setState(() {
                      data = null;
                      correcting = false;
                      error = null;
                      userVisibleMs = null;
                      request.clear();
                      response.clear();
                    });
                    widget.onChanged(null);
                  },
            child: const Text('Start a different task'),
          ),
        if (status == 'REASONING_UNAVAILABLE' || status == 'AUDIT_REJECTED')
          Text(
            '${status == 'AUDIT_REJECTED' ? 'Intent audit rejected' : 'Reasoning unavailable'}: ${data!['error_explanation'] ?? 'Review the request and the configured reasoning route.'}',
          ),
        if (data?['reasoning_route'] != null)
          Text(
            'Configured reasoning: ${(data!['reasoning_route'] as Map)['provider']} / ${(data!['reasoning_route'] as Map)['model']}',
          ),
        for (final call in (data?['reasoning_calls'] as List? ?? []))
          Text('Reasoning: ${(call as Map)['provider']} / ${call['model']}'),
        if (data?['backend_inference_ms'] != null)
          Text('Backend inference: ${data!['backend_inference_ms']} ms'),
        if (userVisibleMs != null)
          Text('Visible response: ${userVisibleMs!.toStringAsFixed(2)} ms'),
        if (status == 'CLARIFICATION' && !correcting) ...[
          Text((data!['pending_question'] as Map)['question'].toString()),
          TextField(
            key: const ValueKey('intent-answer'),
            controller: response,
            maxLength: 2000,
            decoration: const InputDecoration(labelText: 'Your answer'),
          ),
          TextButton(
            onPressed: busy
                ? null
                : () => send('respond', revision({'answer': response.text})),
            child: const Text('Use this answer'),
          ),
        ],
        if (audit != null &&
            status != 'CLARIFICATION' &&
            status != 'REASONING_UNAVAILABLE' &&
            status != 'AUDIT_REJECTED') ...[
          Text(
            status == 'READY' ? 'Request understood' : 'Intent Audit',
            style: Theme.of(context).textTheme.titleSmall,
          ),
          items('Objective', audit['objective']),
          for (final source in (audit['relevant_context'] as List? ?? []))
            SelectableText(
              'Context · ${(source as Map)['status']} · ${source['source']}\n${source['content']}',
            ),
          items('Included', audit['scope_in']),
          items('Excluded', audit['scope_out']),
          items('Constraints', audit['constraints']),
          items('Assumptions', audit['assumptions']),
          items('Expected outcome', audit['expected_outcome']),
          items('Acceptance checks', audit['acceptance_checks']),
          items('Unresolved uncertainty', audit['uncertainty']),
          if (status == 'AUDIT' || status == 'READY')
            TextButton(
              key: const ValueKey('intent-accept'),
              onPressed: busy ? null : () => send('accept', revision()),
              child: Text(status == 'READY' ? 'Prepare task' : 'Accept intent'),
            ),
        ],
        if (data != null)
          TextButton(
            key: const ValueKey('intent-correct'),
            onPressed: busy ? null : () => setState(() => correcting = true),
            child: Text(
              audit == null ? 'Edit request / Retry' : 'Clarify / Correct',
            ),
          ),
        if (correcting) ...[
          TextField(
            key: const ValueKey('intent-correction'),
            controller: response,
            maxLength: 2000,
            decoration: InputDecoration(
              labelText: audit == null
                  ? 'Add or revise request details'
                  : 'Correct the interpretation',
            ),
          ),
          TextButton(
            onPressed: busy
                ? null
                : () =>
                      send('respond', revision({'correction': response.text})),
            child: Text(
              audit == null ? 'Retry understanding' : 'Update existing intent',
            ),
          ),
        ],
        if (data?['package'] != null) ...[
          const Text(
            'Task package prepared. Workspace, permissions and execution approval remain required.',
          ),
          Wrap(
            children: [
              for (final executor in [
                {'id': 'uri', 'label': 'URI'},
                ...widget.providers.where((p) => p['installed'] == true),
              ])
                TextButton(
                  key: ValueKey('intent-executor-${executor['id']}'),
                  onPressed: busy
                      ? null
                      : () => send(
                          'executor',
                          revision({'executor': executor['id']}),
                        ),
                  child: Text(executor['label'].toString()),
                ),
            ],
          ),
          Text('Executor choice: ${data!['executor'] ?? 'Not selected'}'),
          const Text(
            'General execution is unavailable in this preparation candidate. The fixed repair below is a separate task.',
          ),
          TextButton(
            key: const ValueKey('intent-deny'),
            onPressed: busy ? null : () => send('deny', revision()),
            child: const Text('Do not execute'),
          ),
        ],
      ],
    );
  }
}
