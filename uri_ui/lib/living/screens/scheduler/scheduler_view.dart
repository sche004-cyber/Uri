import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../../theme/uri_theme.dart';
import '../../integration/scheduler_client.dart';
import '../../widgets/glass_panel.dart';

/// Minimal Task Scheduler view: pending approvals (with the GIF itself),
/// upcoming jobs, errors, recent executions and jobs (pause / resume / cancel).
///
/// Truth rules: every execution shows whether it was LIVE (real Claude) or
/// FIXTURE (synthetic stand-in); approval names the exact artifact sha256; the
/// view never offers publishing or sharing because the service cannot do it.
class SchedulerView extends StatefulWidget {
  const SchedulerView({super.key, required this.client, this.poll});
  final SchedulerClient client;

  /// Refresh interval; null disables polling (tests).
  final Duration? poll;

  @override
  State<SchedulerView> createState() => _SchedulerViewState();
}

class _SchedulerViewState extends State<SchedulerView> {
  Map<String, dynamic>? _ov;
  String? _error;
  Timer? _timer;
  final Map<int, Future<Uint8List>> _gifs = {};

  @override
  void initState() {
    super.initState();
    _refresh();
    if (widget.poll != null) {
      _timer = Timer.periodic(widget.poll!, (_) => _refresh());
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    try {
      final ov = await widget.client.overview();
      if (mounted) {
        setState(() {
          _ov = ov;
          _error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _error = '$e');
    }
  }

  Future<void> _act(Future<Object?> Function() f, String done) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await f();
      messenger.showSnackBar(SnackBar(content: Text(done)));
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Refused: $e')));
    }
    await _refresh();
  }

  Future<void> _setupFestivals() async {
    final client = widget.client;
    Map<String, dynamic> p;
    try {
      p = await client.proposeFestivals();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context)
          .showSnackBar(SnackBar(content: Text('Refused: $e')));
      return;
    }
    if (!mounted) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => _ProposalDialog(proposal: p),
    );
    if (ok == true) {
      await _act(
        () => client.confirm('${p['job_id']}', '${p['proposal_sha256']}'),
        'Festival schedule activated',
      );
    } else {
      await _act(
        () => client.jobAction('${p['job_id']}', 'cancel'),
        'Proposal discarded',
      );
    }
  }

  Future<String?> _ask(String title, String hint) {
    final ctl = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: TextField(
          key: const Key('scheduler.instruction'),
          controller: ctl,
          autofocus: true,
          maxLength: 1000,
          decoration: InputDecoration(hintText: hint),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, ctl.text),
            child: const Text('Send'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final ov = _ov;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scheduled tasks'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            onPressed: _refresh,
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      body: ov == null
          ? Center(
              child: Text(
                _error == null ? 'Loading…' : 'Scheduler not reachable: $_error',
                style: TextStyle(color: c.inkSoft),
              ),
            )
          : ListView(
              padding: const EdgeInsets.all(UriSpace.lg),
              children: [
                _HarnessBanner(harness: ov['harness'] as Map?),
                const SizedBox(height: UriSpace.md),
                Wrap(
                  spacing: 8,
                  children: [
                    FilledButton.icon(
                      key: const Key('scheduler.setupFestivals'),
                      onPressed: _setupFestivals,
                      icon: const Icon(Icons.celebration_outlined, size: 18),
                      label: const Text('Festival GIFs (2 days before)'),
                    ),
                  ],
                ),
                const SizedBox(height: UriSpace.lg),
                _Section(
                  title: 'Waiting for your approval',
                  empty: 'Nothing waiting.',
                  children: [
                    for (final o in (ov['pending_approvals'] as List))
                      for (final a in (o['candidates'] as List))
                        _ReviewCard(
                          occ: o as Map<String, dynamic>,
                          art: a as Map<String, dynamic>,
                          gif: _gifs.putIfAbsent(
                            a['artifact_id'] as int,
                            () => widget.client.artifactBytes(
                              a['artifact_id'] as int,
                            ),
                          ),
                          onAction: (action) async {
                            String? instruction;
                            if (action == 'refine') {
                              instruction = await _ask(
                                'Refine this GIF',
                                'e.g. More floral energy',
                              );
                              if (instruction == null ||
                                  instruction.trim().isEmpty) {
                                return;
                              }
                            }
                            await _act(
                              () => widget.client.review(
                                a['artifact_id'] as int,
                                action,
                                sha256: '${a['sha256']}',
                                instruction: instruction,
                              ),
                              switch (action) {
                                'approve' => 'Approved (not published)',
                                'refine' => 'Refinement queued',
                                'regenerate' => 'Alternative queued',
                                _ => 'Rejected',
                              },
                            );
                          },
                        ),
                  ],
                ),
                _Section(
                  title: 'Needs attention',
                  empty: 'No errors.',
                  children: [
                    for (final o in (ov['errors'] as List))
                      _OccRow(
                        occ: o as Map<String, dynamic>,
                        actions: [
                          if (o['state'] == 'AWAITING_CONFIRMATION')
                            TextButton(
                              key: Key('scheduler.confirmDate.${o['occ_id']}'),
                              onPressed: () => _act(
                                () => widget.client.occurrenceAction(
                                  o['occ_id'] as int,
                                  'confirm',
                                ),
                                'Date confirmed',
                              ),
                              child: const Text('Confirm date'),
                            )
                          else
                            TextButton(
                              onPressed: () => _act(
                                () => widget.client.occurrenceAction(
                                  o['occ_id'] as int,
                                  'retry',
                                ),
                                'Retry queued',
                              ),
                              child: const Text('Retry'),
                            ),
                          TextButton(
                            onPressed: () => _act(
                              () => widget.client.occurrenceAction(
                                o['occ_id'] as int,
                                'cancel',
                              ),
                              'Cancelled',
                            ),
                            child: const Text('Cancel'),
                          ),
                        ],
                      ),
                  ],
                ),
                _Section(
                  title: 'Upcoming',
                  empty: 'Nothing scheduled.',
                  children: [
                    for (final o in (ov['upcoming'] as List).take(12))
                      _OccRow(occ: o as Map<String, dynamic>),
                  ],
                ),
                _Section(
                  title: 'Jobs',
                  empty: 'No jobs.',
                  children: [
                    for (final j in (ov['jobs'] as List))
                      _JobRow(
                        job: j as Map<String, dynamic>,
                        onAction: (a) => _act(
                          () => widget.client.jobAction('${j['job_id']}', a),
                          'Job $a',
                        ),
                      ),
                  ],
                ),
                _Section(
                  title: 'Recent executions',
                  empty: 'No executions yet.',
                  children: [
                    for (final a in (ov['recent_executions'] as List).take(10))
                      Text(
                        '${a['started_utc']}  ${a['mode']}  ${a['harness']}  '
                        '${a['kind']}  →  ${a['outcome'] ?? 'running'}'
                        '${a['reason'] != null ? '  (${a['reason']})' : ''}',
                        style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
                      ),
                  ],
                ),
              ],
            ),
    );
  }
}

class _HarnessBanner extends StatelessWidget {
  const _HarnessBanner({required this.harness});
  final Map? harness;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final ok = harness?['available'] == true;
    final mode = '${harness?['mode'] ?? '?'}';
    return GlassPanel(
      glowBorder: !ok,
      child: Row(
        children: [
          Icon(
            ok ? Icons.check_circle_outline : Icons.block_outlined,
            color: ok ? c.success : c.danger,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              ok
                  ? 'Claude harness available ($mode'
                        '${mode == 'FIXTURE' ? ': synthetic stand-in, not Claude' : ''})'
                  : 'Claude harness unavailable: ${harness?['code'] ?? 'not configured'}. '
                        'Scheduled work waits; no other or paid provider is used.',
              style: TextStyle(color: c.ink),
            ),
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  const _Section({
    required this.title,
    required this.children,
    required this.empty,
  });
  final String title;
  final List<Widget> children;
  final String empty;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: UriSpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: UriType.title,
              fontWeight: FontWeight.w600,
              color: c.ink,
            ),
          ),
          const SizedBox(height: 8),
          if (children.isEmpty)
            Text(empty, style: TextStyle(color: c.inkFaint, fontSize: UriType.body))
          else
            ...children,
        ],
      ),
    );
  }
}

class _OccRow extends StatelessWidget {
  const _OccRow({required this.occ, this.actions = const []});
  final Map<String, dynamic> occ;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final meta = (occ['meta'] as Map?) ?? {};
    final name = meta['festival'] ?? occ['title'];
    final date = meta['festival_date'] != null
        ? ' · festival ${meta['festival_date']}'
        : '';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text(
            '$name$date · due ${occ['due_local']} · ${occ['state']}'
            '${occ['reason'] != null ? ' (${occ['reason']})' : ''}',
            style: TextStyle(fontSize: UriType.body, color: c.ink),
          ),
          if (actions.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 8),
              child: Wrap(spacing: 8, runSpacing: 8, children: actions),
            ),
        ],
      ),
    );
  }
}

class _JobRow extends StatelessWidget {
  const _JobRow({required this.job, required this.onAction});
  final Map<String, dynamic> job;
  final void Function(String) onAction;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final state = '${job['state']}';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          '${job['title']} · $state\n${job['interpretation']}',
          style: TextStyle(fontSize: UriType.body, color: c.ink),
        ),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            if (state == 'ACTIVE')
              TextButton(
                onPressed: () => onAction('pause'),
                child: const Text('Pause'),
              ),
            if (state == 'PAUSED')
              TextButton(
                onPressed: () => onAction('resume'),
                child: const Text('Resume'),
              ),
            if (state != 'CANCELLED')
              TextButton(
                onPressed: () => onAction('cancel'),
                child: const Text('Cancel'),
              ),
          ],
        ),
      ],
    );
  }
}

class _ReviewCard extends StatelessWidget {
  const _ReviewCard({
    required this.occ,
    required this.art,
    required this.gif,
    required this.onAction,
  });
  final Map<String, dynamic> occ;
  final Map<String, dynamic> art;
  final Future<Uint8List> gif;
  final void Function(String action) onAction;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final info = (art['info'] as Map?) ?? {};
    final quality = (info['quality'] as Map?) ?? {};
    final checks = (info['gif_checks'] as Map?) ?? {};
    final meta = (occ['meta'] as Map?) ?? {};
    final mode = '${info['mode']}';
    final sha = '${art['sha256']}';
    return Padding(
      padding: const EdgeInsets.only(bottom: UriSpace.md),
      child: GlassPanel(
        glowBorder: true,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 220,
              height: 220,
              child: FutureBuilder<Uint8List>(
                future: gif,
                builder: (context, s) => s.hasData
                    ? Image.memory(
                        s.data!,
                        key: Key('scheduler.gif.${art['artifact_id']}'),
                        gaplessPlayback: true,
                        fit: BoxFit.contain,
                      )
                    : Center(
                        child: Text(
                          s.hasError ? 'Preview failed' : 'Loading…',
                          style: TextStyle(color: c.inkFaint),
                        ),
                      ),
              ),
            ),
            const SizedBox(width: UriSpace.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${meta['festival'] ?? occ['title']}'
                    '${meta['festival_date'] != null ? ' · ${meta['festival_date']}' : ''}'
                    '  ·  version ${art['version']}',
                    style: TextStyle(
                      fontSize: UriType.title,
                      fontWeight: FontWeight.w600,
                      color: c.ink,
                    ),
                  ),
                  if (mode == 'FIXTURE')
                    Text(
                      'FIXTURE: made by the synthetic stand-in, not by Claude.',
                      style: TextStyle(color: c.warning, fontSize: UriType.label),
                    ),
                  const SizedBox(height: 6),
                  Text(
                    '${art['concept']}'.trim(),
                    maxLines: 6,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: UriType.body, color: c.inkSoft),
                  ),
                  const SizedBox(height: 6),
                  SelectableText(
                    '${art['path']}\nsha256 ${sha.substring(0, 16)}…  ·  '
                    '${checks['n_frames']} frames  ·  ${art['bytes']} bytes',
                    style: TextStyle(fontSize: UriType.caption, color: c.inkFaint),
                  ),
                  Text(
                    'Checks: animated GIF ${quality['animated_gif'] == true ? '✓' : '✗'}  '
                    'legible text ${quality['text_legible'] == true ? '✓' : '✗'}  '
                    'seamless loop ${quality['loop_seamless'] == true ? '✓' : '✗'}  '
                    'size budget ${quality['within_size_budget'] == true ? '✓' : '✗'}',
                    style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
                  ),
                  const SizedBox(height: 8),
                  Wrap(
                    spacing: 8,
                    children: [
                      FilledButton(
                        key: Key('scheduler.approve.${art['artifact_id']}'),
                        onPressed: () => onAction('approve'),
                        child: const Text('Approve'),
                      ),
                      OutlinedButton(
                        key: Key('scheduler.refine.${art['artifact_id']}'),
                        onPressed: () => onAction('refine'),
                        child: const Text('Refine'),
                      ),
                      OutlinedButton(
                        onPressed: () => onAction('regenerate'),
                        child: const Text('Regenerate'),
                      ),
                      TextButton(
                        onPressed: () => onAction('reject'),
                        child: const Text('Reject'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ProposalDialog extends StatelessWidget {
  const _ProposalDialog({required this.proposal});
  final Map<String, dynamic> proposal;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final rows = (proposal['upcoming'] as List).cast<Map>();
    final excluded = (proposal['excluded'] as List).cast<Map>();
    return AlertDialog(
      title: const Text('Confirm festival GIF schedule'),
      content: SizedBox(
        width: 560,
        height: 420,
        child: ListView(
          children: [
            Text(
              '${proposal['interpretation']}',
              style: TextStyle(color: c.ink),
            ),
            const SizedBox(height: 8),
            for (final r in rows)
              Text(
                '${r['festival']} · ${r['festival_date']} → GIF ${r['due_local']}'
                '  [${(r['source'] as Map?)?['verification'] ?? ''}]',
                style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
              ),
            if (excluded.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Not scheduled until you confirm their dates:',
                style: TextStyle(color: c.warning),
              ),
              for (final e in excluded)
                Text(
                  '${e['festival_key']} ${e['date']} (${e['status']})',
                  style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
                ),
            ],
            const SizedBox(height: 8),
            for (final n in (proposal['notes'] as List))
              Text('• $n', style: TextStyle(fontSize: UriType.label, color: c.inkFaint)),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: const Text('Discard'),
        ),
        FilledButton(
          key: const Key('scheduler.confirmProposal'),
          onPressed: () => Navigator.pop(context, true),
          child: const Text('Activate'),
        ),
      ],
    );
  }
}
