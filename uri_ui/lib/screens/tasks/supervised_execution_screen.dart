import 'dart:async';
import 'dart:convert' show JsonEncoder;
import 'dart:io' show Platform;
import 'dart:math';

import 'package:flutter/material.dart';

import '../../services/paired_runtime.dart';
import '../../services/supervised_runtime.dart';
import '../../theme/uri_theme.dart';

/// Phase 2 UI/operations: the URI UI driving the supervised execution path.
///
/// Flow: explicit executor choice -> text -> (clarification / confirmation)
/// -> digest-bound approval card (task, provider, model, effect scope,
/// qualification, digests) -> `execution_begin` -> lifecycle card polled from
/// the worker (queued / approving / starting / running / terminal) with a real
/// mid-run Cancel -> receipt. On open the screen lists every execution the
/// worker knows about (reconnect): nothing shown here is UI memory, every
/// state is re-read from the worker, which re-reads the ledger, the journal
/// and the server. Nothing is simulated when no installation has opted in.
class SupervisedExecutionScreen extends StatefulWidget {
  const SupervisedExecutionScreen({
    super.key,
    this.runtimeOverride,
    this.sessionId,
    this.pollInterval = const Duration(milliseconds: 500),
  });

  /// Tests inject a runtime; production resolves URI_CLIENT_MANIFEST + opt-in.
  final SupervisedRuntime? runtimeOverride;
  final String? sessionId;
  final Duration pollInterval;

  @override
  State<SupervisedExecutionScreen> createState() => _SupervisedExecutionScreenState();
}

String _uuid4() {
  final r = Random.secure();
  final b = List<int>.generate(16, (_) => r.nextInt(256));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  final h = b.map((x) => x.toRadixString(16).padLeft(2, '0')).join();
  return '${h.substring(0, 8)}-${h.substring(8, 12)}-${h.substring(12, 16)}-${h.substring(16, 20)}-${h.substring(20)}';
}

String _short(String? digest) => digest == null ? '—' : (digest.length > 16 ? '${digest.substring(0, 16)}…' : digest);

String _when(double? epochSeconds) {
  if (epochSeconds == null) return '—';
  final t = DateTime.fromMillisecondsSinceEpoch((epochSeconds * 1000).round());
  return t.toIso8601String().replaceFirst('T', ' ').substring(0, 19);
}

String _shortId(String id) => id.length > 8 ? id.substring(0, 8) : id;

class _SupervisedExecutionScreenState extends State<SupervisedExecutionScreen> {
  SupervisedRuntime? _runtime;
  String? _unavailable;
  Map<String, dynamic> _preflight = const {};
  List<HarnessStatus> _harnesses = const [];
  ReasoningChoice? _choice; // never preselected: the user chooses
  late final String _session = widget.sessionId ?? _uuid4();
  final _text = TextEditingController();
  SupervisedTurn? _pending; // approval card: proposal shown, nothing sent yet
  SupervisedTurn? _question;
  SupervisedTurn? _confirm;
  ExecutionStatus? _execution;
  List<ExecutionSummary> _history = const [];
  Map<String, dynamic>? _startup;
  Timer? _poll;
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
          await SupervisedWorkerRuntime.fromManifest(Platform.environment['URI_CLIENT_MANIFEST']);
      if (_runtime == null) {
        setState(() => _unavailable = 'No paired client installation has opted in to the supervised profile '
            '(control/ui-supervised-profile.json). Nothing is simulated.');
        return;
      }
      final pre = await _runtime!.preflight();
      final list = await _runtime!.discoverHarnesses();
      if (!mounted) return;
      setState(() {
        _preflight = pre;
        _harnesses = list;
      });
      await _reconnect();
    } catch (e) {
      if (mounted) setState(() => _unavailable = 'Supervised worker unavailable: $e');
    }
  }

  /// Reconnect: whatever the worker knows (durable records, reconciled at its
  /// start) is listed; an execution still active in this worker is followed.
  Future<void> _reconnect() async {
    final listing = await _runtime!.listExecutions();
    if (!mounted) return;
    setState(() {
      _history = listing.executions;
      _startup = listing.startup;
    });
    final active = listing.active;
    if (active != null) {
      await _focus(active);
    } else if (_execution != null) {
      await _focus(_execution!.id);
    }
  }

  Future<void> _focus(String executionId) async {
    try {
      final st = await _runtime!.executionStatus(executionId);
      if (!mounted) return;
      setState(() => _execution = st);
      _pollWhileActive();
    } catch (e) {
      if (mounted) setState(() => _outcome = 'Blocked: $e');
    }
  }

  void _pollWhileActive() {
    _poll?.cancel();
    _poll = null;
    final current = _execution;
    if (current == null || current.isTerminal) return;
    _poll = Timer.periodic(widget.pollInterval, (_) => _refresh());
  }

  Future<void> _refresh() async {
    final current = _execution;
    if (current == null || _runtime == null) return;
    try {
      final st = await _runtime!.executionStatus(current.id);
      if (!mounted) return;
      setState(() => _execution = st);
      if (st.isTerminal) {
        _poll?.cancel();
        _poll = null;
        final listing = await _runtime!.listExecutions();
        if (mounted) setState(() => _history = listing.executions);
      }
    } catch (e) {
      if (mounted) setState(() => _outcome = 'Status unavailable: $e');
      _poll?.cancel();
      _poll = null;
    }
  }

  @override
  void dispose() {
    _poll?.cancel();
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
      _apply(await _runtime!.startTurn(_session, _text.text.trim(), choice));
    } catch (e) {
      setState(() => _outcome = 'Blocked: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _apply(TurnResult result) {
    final turn = result is SupervisedTurn ? result : SupervisedTurn(state: result.state, turnId: result.turnId,
        code: result.code, message: result.message, approval: result.approval, clarification: result.clarification,
        confirmation: result.confirmation, intent: result.intent);
    setState(() {
      _question = turn.needsClarification ? turn : null;
      _confirm = turn.needsConfirmation ? turn : null;
      if (turn.needsApproval) {
        _pending = turn;
      } else {
        _pending = null;
        _outcome = (_question != null || _confirm != null) ? null : '${turn.code ?? turn.state}: ${turn.message ?? ''}';
      }
      if (_question != null) _text.clear();
    });
  }

  Future<void> _intent(Map<String, dynamic> decision) async {
    final choice = _choice;
    if (choice == null) return;
    setState(() => _busy = true);
    try {
      _apply(await _runtime!.intentDecision(_session, choice, decision));
    } catch (e) {
      setState(() => _outcome = 'Blocked: $e');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Approve: echo exactly the two digests of the card on screen. The worker
  /// refuses anything else and drops the turn.
  Future<void> _approveAndRun() async {
    final pending = _pending;
    final proposal = pending?.proposal;
    if (pending == null || pending.turnId == null || proposal == null || proposal.approvalDigest == null) return;
    setState(() => _busy = true);
    try {
      final handle = await _runtime!.beginExecution(pending.turnId!, proposal.approvalDigest!, proposal.proposalDigest);
      setState(() {
        _pending = null;
        _outcome = null;
      });
      await _focus(handle.id);
    } catch (e) {
      setState(() {
        // A refused begin drops the turn worker-side too, except when the worker only asked us to wait
        // (another execution is in flight): the card stays, the approval is still the user's to give.
        if (!(e is PairedRuntimeException && e.code == 'EXECUTION_IN_PROGRESS')) _pending = null;
        _outcome = 'Blocked: $e';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _decline() async {
    final pending = _pending;
    if (pending == null || pending.turnId == null) return;
    setState(() => _busy = true);
    try {
      _apply(await _runtime!.decide(pending.turnId!, false));
    } catch (e) {
      setState(() {
        _pending = null;
        _outcome = 'Blocked: $e';
      });
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _cancel() async {
    final current = _execution;
    if (current == null) return;
    setState(() => _busy = true);
    try {
      await _runtime!.cancelExecution(current.id);
      await _refresh();
      _pollWhileActive();
    } catch (e) {
      setState(() => _outcome = 'Cancel refused: $e');
      await _refresh();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  // ---- cards ---------------------------------------------------------------------------

  Widget _clarificationCard(BuildContext context) {
    final c = _question!.clarification!;
    final options = (c['options'] is List ? c['options'] as List : const []).whereType<Map>().toList();
    return Card(
      key: const Key('sx-clarification'),
      child: Padding(
        padding: const EdgeInsets.all(UriSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(c['question'] is String ? c['question'] as String : '', style: Theme.of(context).textTheme.titleSmall),
          for (final o in options)
            if (o['candidate_id'] != null)
              OutlinedButton(
                key: Key('sx-option-${o['candidate_id']}'),
                onPressed: _busy
                    ? null
                    : () => _intent({'intent_id': c['intent_id'], 'revision': c['revision'], 'decision': 'select',
                          'candidate_id': o['candidate_id']}),
                child: Text('${o['label']}'),
              ),
          const Text('Or type your answer below and press Send.'),
        ]),
      ),
    );
  }

  Widget _confirmationCard(BuildContext context) {
    final c = _confirm!.confirmation!;
    final args = (c['arguments'] is Map ? c['arguments'] as Map : const {});
    return Card(
      key: const Key('sx-confirmation'),
      child: Padding(
        padding: const EdgeInsets.all(UriSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Confirm exactly what URI will do', style: Theme.of(context).textTheme.titleSmall),
          for (final e in args.entries) Text('${e.key}: ${e.value}'),
          const Text('Nothing runs until you confirm and then approve.'),
          Row(children: [
            FilledButton(
                key: const Key('sx-confirm'),
                onPressed: _busy
                    ? null
                    : () => _intent({'intent_id': c['intent_id'], 'revision': c['revision'], 'decision': 'confirm',
                          'digest': c['digest']}),
                child: const Text('Confirm')),
            const SizedBox(width: UriSpace.sm),
            OutlinedButton(
                key: const Key('sx-abandon'),
                onPressed: _busy
                    ? null
                    : () => _intent({'intent_id': c['intent_id'], 'revision': c['revision'], 'decision': 'abandon'}),
                child: const Text('Cancel request')),
          ]),
        ]),
      ),
    );
  }

  Widget _approvalCard(BuildContext context) {
    final p = _pending!.proposal;
    final req = _pending!.approval ?? const {};
    final q = p?.qualification;
    final textTheme = Theme.of(context).textTheme;
    return Card(
      key: const Key('sx-approval'),
      child: Padding(
        padding: const EdgeInsets.all(UriSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Approve this exact execution?', style: textTheme.titleSmall),
          const SizedBox(height: UriSpace.sm),
          Text('Task: ${p?.instruction ?? req['capability_id'] ?? '—'}', key: const Key('sx-proposal-task')),
          if (p?.expectedFile != null) Text('Result file: ${p!.expectedFile}', key: const Key('sx-proposal-file')),
          Text('Capability: ${p?.capabilityId ?? req['capability_id'] ?? '—'}', key: const Key('sx-proposal-capability')),
          Text('Executor: ${p?.provider ?? '—'} · model ${p?.model ?? 'not pinned'} (${p?.kind ?? '—'})',
              key: const Key('sx-proposal-executor')),
          Text('Effect: ${p?.effect ?? req['effect'] ?? '—'} · reversible: ${p?.reversible ?? req['reversible'] ?? '—'} '
              '· runs in a fresh workspace on this client', key: const Key('sx-proposal-effect')),
          Text(q == null
              ? 'Qualification: not applicable (deterministic, local)'
              : 'Qualification: ${q['level'] ?? '—'} · ${q['status'] ?? '—'}'
                  '${q['expires_at'] is num ? ' · expires ${_when((q['expires_at'] as num).toDouble())}' : ''}',
              key: const Key('sx-proposal-qualification')),
          const SizedBox(height: UriSpace.sm),
          // C6 contract: the exact arguments object, verbatim, before the button is enabled (review round 1, OPS-3).
          Text('Exact arguments (as the server bound them):', style: textTheme.labelMedium),
          Text(const JsonEncoder.withIndent('  ').convert(p?.arguments ?? req['arguments'] ?? const {}),
              key: const Key('sx-proposal-arguments'), style: textTheme.bodySmall),
          Text('Argument digest ${_short(p?.argumentDigest ?? (req['argument_digest'] is String ? req['argument_digest'] as String : null))}',
              key: const Key('sx-proposal-argument-digest'), style: textTheme.bodySmall),
          Text('Approval digest ${_short(p?.approvalDigest)} · proposal digest ${_short(p?.proposalDigest)}',
              key: const Key('sx-proposal-digests'), style: textTheme.bodySmall),
          const Text('Approving binds exactly these fields. Any change needs a new approval. Typed text never approves.'),
          const SizedBox(height: UriSpace.sm),
          Row(children: [
            FilledButton(
                key: const Key('sx-approve'),
                onPressed: (_busy || p == null) ? null : _approveAndRun,
                child: const Text('Approve and run')),
            const SizedBox(width: UriSpace.sm),
            OutlinedButton(key: const Key('sx-decline'), onPressed: _busy ? null : _decline, child: const Text('Decline')),
          ]),
        ]),
      ),
    );
  }

  Widget _executionCard(BuildContext context) {
    final x = _execution!;
    final p = x.proposal;
    final textTheme = Theme.of(context).textTheme;
    final attempts = (x.ledger?['attempts'] is List ? x.ledger!['attempts'] as List : const []).whereType<Map>().toList();
    final lastAttempt = attempts.isEmpty ? null : attempts.last;
    final ev = x.evidence.isEmpty ? null : x.evidence.first;
    return Card(
      key: const Key('sx-execution'),
      child: Padding(
        padding: const EdgeInsets.all(UriSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Execution ${_shortId(x.id)} · ${x.state.toUpperCase()}',
              key: const Key('sx-state'), style: textTheme.titleSmall),
          if (x.reason != null) Text('Reason: ${x.reason}', key: const Key('sx-reason')),
          if (x.recordedState != null && x.recordedState != x.state)
            Text('The local record says "${x.recordedState}", but the ledger/journal/server do not confirm it; '
                'URI reports what it can prove.', key: const Key('sx-uncorroborated')),
          if (x.code != null) Text('Settlement: ${x.code}${x.message != null ? ' — ${x.message}' : ''}', key: const Key('sx-code')),
          Text('Executor: ${p?.provider ?? '—'} · model ${p?.model ?? 'not pinned'} · '
              'qualification ${p?.qualification?['level'] ?? 'n/a'}'),
          Text('Task: ${p?.instruction ?? x.requestText ?? '—'}'),
          Text('Queued ${_when(x.queuedAt)} · approving ${_when(x.approvingAt)} · starting ${_when(x.startingAt)} · '
              'running ${_when(x.runningAt)} · ended ${_when(x.endedAt)}', style: textTheme.bodySmall),
          Text('Supervisor task: ${x.taskId ?? 'none'} · ledger ${x.ledgerTaskState ?? '—'}'
              '${lastAttempt == null ? '' : ' · attempt ${lastAttempt['attempt_id']} ${lastAttempt['status']}'
                  '${lastAttempt['end_reason'] != null ? ' (${lastAttempt['end_reason']})' : ''}'}',
              key: const Key('sx-ledger')),
          Text('Client journal: ${x.journalState ?? '—'} · server turn: ${x.serverTurnState ?? '—'}', key: const Key('sx-journal')),
          if (x.cancelRequested) const Text('Cancellation was requested.', key: Key('sx-cancel-flag')),
          if (ev != null)
            Text('Result: ${p?.expectedFile ?? 'file'} verified by URI · sha256 '
                '${_short(ev['output_sha256'] is String ? ev['output_sha256'] as String : null)} '
                '· ${ev['output_bytes'] is int ? ev['output_bytes'] : '?'} bytes', key: const Key('sx-receipt')),
          if (x.state == 'uncertain')
            const Text('URI cannot prove a clean outcome for this execution. Nothing is retried automatically; '
                'check the result yourself before asking again.', key: Key('sx-uncertain')),
          if (x.state == 'quota_paused')
            const Text('The provider refused for quota. The task is saved; choose another executor explicitly.',
                key: Key('sx-quota')),
          const SizedBox(height: UriSpace.sm),
          Row(children: [
            OutlinedButton(
                key: const Key('sx-cancel'),
                onPressed: (x.isTerminal || _busy) ? null : _cancel,
                child: const Text('Cancel execution')),
            const SizedBox(width: UriSpace.sm),
            TextButton(key: const Key('sx-refresh'), onPressed: _busy ? null : _refresh, child: const Text('Refresh')),
          ]),
        ]),
      ),
    );
  }

  Widget _historyCard(BuildContext context) {
    final restarted = (_startup?['executions'] is List ? _startup!['executions'] as List : const []);
    return Card(
      key: const Key('sx-history'),
      child: Padding(
        padding: const EdgeInsets.all(UriSpace.md),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Executions on this client', style: Theme.of(context).textTheme.titleSmall),
          if (restarted.isNotEmpty)
            Text('${restarted.length} execution(s) were in flight when the worker last stopped; they are uncertain.',
                key: const Key('sx-restart-note')),
          if (_history.isEmpty) const Text('None yet.'),
          for (final h in _history)
            ListTile(
              key: Key('sx-exec-${h.id}'),
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text('${_shortId(h.id)} · ${h.state}${h.reason != null ? ' · ${h.reason}' : ''}'),
              subtitle: Text('${h.provider ?? '—'} · ${h.model ?? 'no model'} · ${_when(h.queuedAt)}'),
              onTap: _busy ? null : () => _focus(h.id),
            ),
        ]),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_unavailable != null) {
      return Padding(
        padding: const EdgeInsets.all(UriSpace.md),
        child: Text(_unavailable!, key: const Key('sx-unavailable')),
      );
    }
    final pendingSomething = _pending != null || _question != null || _confirm != null;
    return ListView(
      padding: const EdgeInsets.all(UriSpace.md),
      children: [
        Text('Supervised execution', style: Theme.of(context).textTheme.titleMedium),
        Text('Worker profile: ${_preflight['worker_profile'] ?? '—'} · production cutover: '
            '${_preflight['production_cutover'] ?? '—'} · mid-run cancel: ${_preflight['mid_run_cancel'] ?? '—'}',
            key: const Key('sx-preflight')),
        const SizedBox(height: UriSpace.md),
        Text('Executor', style: Theme.of(context).textTheme.titleSmall),
        RadioGroup<ReasoningChoice>(
          groupValue: _choice,
          // Changing the executor while a card is pending would change an authority field: locked until decided.
          onChanged: (v) {
            if (_busy || pendingSomething) return;
            setState(() => _choice = v);
          },
          child: Column(children: [
            RadioListTile<ReasoningChoice>(
              key: const Key('sx-choice-nobrain'),
              value: ReasoningChoice.noBrain,
              enabled: !pendingSomething,
              title: const Text('URI deterministic rules (no Brain)'),
              subtitle: const Text('Local, runs on this client. Explicit requests only.'),
            ),
            for (final h in _harnesses)
              RadioListTile<ReasoningChoice>(
                key: Key('sx-choice-${h.id}'),
                value: ReasoningChoice('client_external_harness', h.id),
                enabled: h.usable && !pendingSomething,
                title: Text(h.id),
                subtitle: Text(_harnessLine(h)),
              ),
          ]),
        ),
        const SizedBox(height: UriSpace.md),
        TextField(
          key: const Key('sx-input'),
          controller: _text,
          decoration: const InputDecoration(labelText: 'Ask URI to do something'),
        ),
        const SizedBox(height: UriSpace.sm),
        FilledButton(
          key: const Key('sx-send'),
          onPressed: (_busy || _choice == null || _pending != null) ? null : _send,
          child: Text(_choice == null ? 'Choose an executor first' : 'Send'),
        ),
        if (_question != null) ...[const SizedBox(height: UriSpace.md), _clarificationCard(context)],
        if (_confirm != null) ...[const SizedBox(height: UriSpace.md), _confirmationCard(context)],
        if (_pending != null) ...[const SizedBox(height: UriSpace.md), _approvalCard(context)],
        if (_execution != null) ...[const SizedBox(height: UriSpace.md), _executionCard(context)],
        if (_outcome != null) ...[const SizedBox(height: UriSpace.md), Text(_outcome!, key: const Key('sx-outcome'))],
        const SizedBox(height: UriSpace.md),
        _historyCard(context),
      ],
    );
  }

  String _harnessLine(HarnessStatus h) {
    final state = !h.installed ? 'not installed' : h.authState.toLowerCase().replaceAll('_', ' ');
    final action = h.requiredAction == null ? '' : ' — ${h.requiredAction}';
    return '$state · ${h.qualification.toLowerCase().replaceAll('_', ' ')}${h.usable ? '' : ' · unavailable'}$action';
  }
}

/// The entry shown on the Tasks destination when, and only when, the paired
/// installation has opted in to the supervised profile. Otherwise it renders
/// nothing: no fabricated state, no hint of a capability that is not wired.
class SupervisedExecutionEntry extends StatelessWidget {
  const SupervisedExecutionEntry({super.key, this.configured, this.runtimeOverride});

  /// Tests override the opt-in probe; production checks the manifest + file.
  final bool? configured;
  final SupervisedRuntime? runtimeOverride;

  @override
  Widget build(BuildContext context) {
    final on = configured ?? SupervisedWorkerRuntime.optInConfigured(Platform.environment['URI_CLIENT_MANIFEST']);
    if (!on) return const SizedBox.shrink(key: Key('sx-entry-absent'));
    return Padding(
      padding: const EdgeInsets.fromLTRB(UriSpace.xl, UriSpace.md, UriSpace.xl, 0),
      child: Card(
        key: const Key('sx-entry'),
        child: ListTile(
          leading: const Icon(Icons.play_circle_outline),
          title: const Text('Supervised execution (Phase 2, opt-in)'),
          subtitle: const Text('Run a task through the supervised worker with a digest-bound approval, live status, '
              'cancellation and a receipt.'),
          trailing: const Icon(Icons.chevron_right),
          onTap: () => Navigator.of(context).push(MaterialPageRoute<void>(
            builder: (_) => Scaffold(
              appBar: AppBar(title: const Text('Supervised execution')),
              body: SupervisedExecutionScreen(runtimeOverride: runtimeOverride),
            ),
          )),
        ),
      ),
    );
  }
}
