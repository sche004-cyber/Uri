import 'dart:io' show Platform;

import 'package:flutter/material.dart';

import '../../services/paired_runtime.dart';
import '../../theme/uri_theme.dart';

/// Paired-runtime panel: explicit executor choice, harness availability and
/// authentication state, user approval of sensitive actions, and honest
/// outcomes. Everything shown comes from the real paired client worker; if no
/// client installation is configured it says so instead of simulating one.
class PairedRuntimeScreen extends StatefulWidget {
  const PairedRuntimeScreen({super.key, this.runtimeOverride, this.sessionId = 'ui-session'});

  /// Tests inject a runtime; production resolves URI_CLIENT_MANIFEST.
  final PairedRuntime? runtimeOverride;
  final String sessionId;

  @override
  State<PairedRuntimeScreen> createState() => _PairedRuntimeScreenState();
}

class _PairedRuntimeScreenState extends State<PairedRuntimeScreen> {
  PairedRuntime? _runtime;
  String? _unavailable;
  List<HarnessStatus> _harnesses = const [];
  ReasoningChoice? _choice; // never preselected: the user chooses
  final _text = TextEditingController();
  TurnResult? _pending;
  TurnResult? _question; // intent clarification waiting for the user's answer
  TurnResult? _confirm; // exact request waiting for explicit confirmation
  String? _outcome;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _connect();
  }

  Future<void> _connect() async {
    try {
      _runtime = widget.runtimeOverride ??
          await WorkerPairedRuntime.fromManifest(Platform.environment['URI_CLIENT_MANIFEST']);
      if (_runtime == null) {
        setState(() => _unavailable =
            'No paired client installation is configured (CLIENT_UI_PENDING). Nothing is simulated.');
        return;
      }
      final list = await _runtime!.discoverHarnesses();
      if (mounted) setState(() => _harnesses = list);
    } catch (e) {
      if (mounted) setState(() => _unavailable = 'Paired client unavailable: $e');
    }
  }

  @override
  void dispose() {
    _text.dispose();
    _runtime?.close();
    super.dispose();
  }

  Future<void> _send() async {
    final choice = _choice;
    if (choice == null || _text.text.trim().isEmpty) return;
    setState(() {
      _busy = true;
      _outcome = null;
    });
    try {
      final result = await _runtime!.startTurn(widget.sessionId, _text.text.trim(), choice);
      _apply(result);
    } catch (e) {
      setState(() => _outcome = 'Blocked: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _apply(TurnResult result) {
    setState(() {
      _question = result.needsClarification ? result : null;
      _confirm = result.needsConfirmation ? result : null;
      if (result.needsApproval) {
        _pending = result;
      } else {
        _pending = null;
        _outcome = (_question != null || _confirm != null)
            ? null
            : '${result.code ?? result.state}: ${result.message ?? ''}';
      }
      if (_question != null) _text.clear(); // the next message answers the question
    });
  }

  Future<void> _intent(Map<String, dynamic> decision) async {
    final choice = _choice;
    if (choice == null) return;
    setState(() => _busy = true);
    try {
      _apply(await _runtime!.intentDecision(widget.sessionId, choice, decision));
    } catch (e) {
      setState(() => _outcome = 'Blocked: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Widget _clarificationCard(BuildContext context) {
    final c = _question!.clarification!;
    final options = (c['options'] as List? ?? const []).cast<Map>();
    return Card(
      key: const Key('paired-clarification'),
      child: Padding(
        padding: const EdgeInsets.all(UriSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(c['question'] as String? ?? '', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: UriSpace.sm),
          for (final o in options)
            if (o['candidate_id'] != null)
              OutlinedButton(
                key: Key('paired-option-${o['candidate_id']}'),
                onPressed: _busy
                    ? null
                    : () => _intent({
                          'intent_id': c['intent_id'],
                          'revision': c['revision'],
                          'decision': 'select',
                          'candidate_id': o['candidate_id'],
                        }),
                child: Text('${o['label']}'),
              ),
          const Text('Or type your answer below and press Send.'),
        ]),
      ),
    );
  }

  Widget _confirmationCard(BuildContext context) {
    final c = _confirm!.confirmation!;
    final args = (c['arguments'] as Map? ?? const {});
    final refs = (_confirm!.intent?['references'] as Map? ?? const {});
    final sources = (_confirm!.intent?['sources'] as Map? ?? const {});
    final interpreted = [for (final e in sources.entries) if (e.value == 'interpreted_from_request') '${e.key}'];
    return Card(
      key: const Key('paired-confirmation'),
      child: Padding(
        padding: const EdgeInsets.all(UriSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Confirm exactly what URI will do', style: Theme.of(context).textTheme.titleSmall),
          for (final e in args.entries) Text('${e.key}: ${e.value}', key: Key('paired-confirm-${e.key}')),
          for (final r in refs.values)
            if (r is Map && r['title'] != null)
              Text('"${r['expression']}" means ${r['title']} (${(r['state'] as String? ?? '').toLowerCase()})'),
          if (interpreted.isNotEmpty)
            Text('Read from your words by the selected Brain: ${interpreted.join(', ')}. Check it is what you meant.',
                key: const Key('paired-confirm-interpreted')),
          const Text('Nothing runs until you confirm and then approve. Say what to change to correct it.'),
          const SizedBox(height: UriSpace.sm),
          Row(children: [
            FilledButton(
                key: const Key('paired-confirm'),
                onPressed: _busy
                    ? null
                    : () => _intent({
                          'intent_id': c['intent_id'],
                          'revision': c['revision'],
                          'decision': 'confirm',
                          'digest': c['digest'],
                        }),
                child: const Text('Confirm')),
            const SizedBox(width: UriSpace.sm),
            OutlinedButton(
                key: const Key('paired-abandon'),
                onPressed: _busy
                    ? null
                    : () => _intent({'intent_id': c['intent_id'], 'revision': c['revision'], 'decision': 'abandon'}),
                child: const Text('Cancel request')),
          ]),
        ]),
      ),
    );
  }

  Future<void> _decide(bool approve) async {
    final pending = _pending;
    if (pending == null || pending.turnId == null) return;
    setState(() => _busy = true);
    try {
      _apply(await _runtime!.decide(pending.turnId!, approve));
    } catch (e) {
      setState(() {
        _pending = null;
        _outcome = 'Blocked: $e';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_unavailable != null) {
      return Text(_unavailable!, key: const Key('paired-unavailable'));
    }
    return ListView(
      children: [
        Text('Executor', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: UriSpace.sm),
        RadioGroup<ReasoningChoice>(
          groupValue: _choice,
          onChanged: (v) => setState(() => _choice = v),
          child: Column(
            children: [
              const RadioListTile<ReasoningChoice>(
                key: Key('choice-nobrain'),
                value: ReasoningChoice.noBrain,
                title: Text('URI deterministic rules (no Brain)'),
                subtitle: Text('Local, runs on this client. Explicit requests only.'),
              ),
              for (final h in _harnesses)
                RadioListTile<ReasoningChoice>(
                  key: Key('choice-${h.id}'),
                  value: ReasoningChoice('client_external_harness', h.id),
                  enabled: h.usable,
                  title: Text(h.id),
                  subtitle: Text(_harnessLine(h)),
                ),
            ],
          ),
        ),
        const SizedBox(height: UriSpace.md),
        TextField(
          key: const Key('paired-input'),
          controller: _text,
          decoration: const InputDecoration(labelText: 'Ask URI to do something'),
        ),
        const SizedBox(height: UriSpace.sm),
        FilledButton(
          key: const Key('paired-send'),
          onPressed: (_busy || _choice == null) ? null : _send,
          child: Text(_choice == null ? 'Choose an executor first' : 'Send'),
        ),
        if (_question != null) ...[
          const SizedBox(height: UriSpace.md),
          _clarificationCard(context),
        ],
        if (_confirm != null) ...[
          const SizedBox(height: UriSpace.md),
          _confirmationCard(context),
        ],
        if (_pending != null) ...[
          const SizedBox(height: UriSpace.md),
          Card(
            key: const Key('paired-approval'),
            child: Padding(
              padding: const EdgeInsets.all(UriSpace.md),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Approval needed: ${_pending!.approval?['capability_id']}',
                      style: Theme.of(context).textTheme.titleSmall),
                  Text('Executes locally on this client; reversible: ${_pending!.approval?['reversible']}.'),
                  const SizedBox(height: UriSpace.sm),
                  Row(children: [
                    FilledButton(
                        key: const Key('paired-approve'),
                        onPressed: _busy ? null : () => _decide(true),
                        child: const Text('Approve')),
                    const SizedBox(width: UriSpace.sm),
                    OutlinedButton(
                        key: const Key('paired-deny'),
                        onPressed: _busy ? null : () => _decide(false),
                        child: const Text('Decline')),
                  ]),
                ],
              ),
            ),
          ),
        ],
        if (_outcome != null) ...[
          const SizedBox(height: UriSpace.md),
          Text(_outcome!, key: const Key('paired-outcome')),
        ],
      ],
    );
  }

  String _harnessLine(HarnessStatus h) {
    final state = !h.installed ? 'not installed' : h.authState.toLowerCase().replaceAll('_', ' ');
    final action = h.requiredAction == null ? '' : ' — ${h.requiredAction}';
    return '$state · ${h.qualification.toLowerCase().replaceAll('_', ' ')}${h.usable ? '' : ' · unavailable'}$action';
  }
}
