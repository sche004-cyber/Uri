import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../a2ui/a2ui_view.dart';
import '../living_scope.dart';
import '../presentation/living_shell.dart' show VoiceDock;
import '../widgets/glass_panel.dart';
import 'assist_controller.dart';

/// Assist (docs/assist/A0_UI_INTERACTION_SPEC.md): share ONE scope with URI,
/// read-only, revocable in one tap. Opening this view observes nothing; it
/// only reads the worker's Assist status (no adapter is called).
class AssistModeView extends StatefulWidget {
  const AssistModeView({super.key, required this.orbRect});
  final Rect orbRect;

  @override
  State<AssistModeView> createState() => _AssistModeViewState();
}

enum _Tab { live, ask, research, teach, fill }

const _kindLabels = {
  'browser_tab': ('Browser tab', Icons.tab_outlined),
  'desktop_window': ('Desktop window', Icons.web_asset_outlined),
  'entire_screen': ('Entire screen', Icons.monitor_outlined),
};

class _AssistModeViewState extends State<AssistModeView> {
  _Tab _tab = _Tab.live;
  bool _suggest = false;
  bool _screenshot = false;
  Map<String, dynamic>? _confirmScreenTarget;
  final _question = TextEditingController();
  final _query = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final a = LivingScope.of(context).assist;
      if (a != null && !a.loaded) a.refresh();
    });
  }

  @override
  void dispose() {
    _question.dispose();
    _query.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final a = LivingScope.of(context).assist;
    final c = UriColors.of(context);
    if (a == null || !a.available) {
      return _Frame(
        orbRect: widget.orbRect,
        title: 'Assist',
        subtitle: 'Assist needs the URI worker (integrated mode). Nothing is observed here.',
        trailing: const SizedBox.shrink(),
        child: Center(
          child: Text(
            'Start URI with the working system to use Assist.',
            key: const ValueKey('assist-unavailable'),
            style: TextStyle(color: c.inkSoft),
          ),
        ),
      );
    }
    return ListenableBuilder(
      listenable: a,
      builder: (context, _) {
        final scope = a.scope;
        final subtitle = a.off
            ? 'URI can\'t see anything. Choose one tab, window or screen to share — read-only.'
            : a.paused
            ? 'Paused. URI sees nothing until you resume.'
            : 'URI can see ${_scopeText(scope)} only, when you ask. Nothing is changed.';
        return _Frame(
          orbRect: widget.orbRect,
          title: 'Assist',
          subtitle: subtitle,
          trailing: a.off ? const SizedBox.shrink() : _ScopeChip(a: a),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _tabs(c),
              const SizedBox(height: UriSpace.sm),
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.only(bottom: UriSpace.md),
                  child: _body(a, c),
                ),
              ),
              if (a.lastError != null)
                Padding(
                  padding: const EdgeInsets.only(bottom: UriSpace.xs),
                  child: Text(
                    _errorText(a.lastError!),
                    key: const ValueKey('assist-error'),
                    style: TextStyle(color: c.danger, fontSize: 13),
                  ),
                ),
              _PermissionsRow(a: a),
              _Diagnostics(a: a),
            ],
          ),
        );
      },
    );
  }

  Widget _tabs(UriColors c) {
    const labels = {
      _Tab.live: 'Live Assist',
      _Tab.ask: 'Ask URI',
      _Tab.research: 'Research',
      _Tab.teach: 'Teach URI',
      _Tab.fill: 'Smart Fill',
    };
    return Wrap(
      spacing: 6,
      runSpacing: 6,
      children: [
        for (final t in _Tab.values)
          ChoiceChip(
            key: ValueKey('assist-tab-${t.name}'),
            label: Text(labels[t]!),
            selected: _tab == t,
            onSelected: (_) => setState(() => _tab = t),
          ),
      ],
    );
  }

  Widget _body(AssistController a, UriColors c) {
    switch (_tab) {
      case _Tab.research:
        return _research(a, c);
      case _Tab.teach:
        return const _ComingCard(
          title: 'Teach URI — coming in A1',
          text: 'Show URI a task once; it will propose the steps it learned for you to review, correct and approve. '
              'Nothing is recorded today.',
        );
      case _Tab.fill:
        return const _ComingCard(
          title: 'Smart Fill — coming in A1',
          text: 'URI will preview suggested values for a form and fill only the ones you pick. It will never submit. '
              'Not available today.',
        );
      case _Tab.live:
      case _Tab.ask:
        if (a.off) return _picker(a, c);
        return _tab == _Tab.live ? _live(a, c) : _ask(a, c);
    }
  }

  Widget _picker(AssistController a, UriColors c) {
    final adapters = {for (final ad in a.adapters) ad['kind'] as String: ad};
    final confirm = _confirmScreenTarget;
    if (confirm != null) {
      return GlassPanel(
        key: const ValueKey('assist-confirm-screen'),
        glowBorder: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Share your entire screen?', style: TextStyle(fontWeight: FontWeight.w700, color: c.ink)),
            const SizedBox(height: 6),
            Text(
              'URI will be able to see everything on your screen when you ask, including notifications and other '
              'windows. Private fields are hidden where URI can find them; if it can\'t, no screenshot is used.',
              style: TextStyle(color: c.inkSoft, fontSize: 13),
            ),
            const SizedBox(height: UriSpace.sm),
            Wrap(
              spacing: 8,
              children: [
                FilledButton(
                  key: const ValueKey('assist-confirm-screen-allow'),
                  onPressed: () {
                    setState(() => _confirmScreenTarget = null);
                    a.grant('entire_screen', confirm['target_id'] as String, suggest: _suggest, confirmScreen: true);
                  },
                  child: const Text('Allow entire screen'),
                ),
                OutlinedButton(
                  onPressed: () => setState(() => _confirmScreenTarget = null),
                  child: const Text('Cancel'),
                ),
              ],
            ),
          ],
        ),
      );
    }
    return Column(
      key: const ValueKey('assist-picker'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Choose what URI can see', style: TextStyle(fontWeight: FontWeight.w700, color: c.ink)),
        const SizedBox(height: UriSpace.sm),
        for (final e in _kindLabels.entries)
          Padding(
            padding: const EdgeInsets.only(bottom: UriSpace.sm),
            child: _KindCard(
              kind: e.key,
              label: e.value.$1,
              icon: e.value.$2,
              adapter: adapters[e.key],
              choosing: a.choosingKind == e.key,
              targets: a.choosingKind == e.key ? a.targets : const [],
              onChoose: () => a.listTargets(e.key),
              onPick: (t) {
                if (e.key == 'entire_screen') {
                  setState(() => _confirmScreenTarget = t);
                } else {
                  a.grant(e.key, t['target_id'] as String, suggest: _suggest);
                }
              },
            ),
          ),
        CheckboxListTile(
          key: const ValueKey('assist-suggest-toggle'),
          contentPadding: EdgeInsets.zero,
          value: _suggest,
          onChanged: (v) => setState(() => _suggest = v ?? false),
          title: const Text('Also let URI point out possible mistakes (Suggest)'),
          subtitle: const Text('Separate from seeing. URI never changes anything.'),
        ),
      ],
    );
  }

  Widget _live(AssistController a, UriColors c) {
    final canSuggest = a.permissions['suggest'] == true;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          children: [
            FilledButton.icon(
              key: const ValueKey('assist-check'),
              onPressed: a.active && canSuggest && !a.busy ? a.check : null,
              icon: const Icon(Icons.fact_check_outlined, size: 16),
              label: const Text('Check this now'),
            ),
            const SizedBox(width: UriSpace.sm),
            Expanded(
              child: Text(
                canSuggest
                    ? 'Reads one fresh view and lists possible mistakes. Nothing is changed.'
                    : 'Suggestions are off for this scope. Stop and choose again to allow them.',
                style: TextStyle(color: c.inkSoft, fontSize: 12),
              ),
            ),
          ],
        ),
        const SizedBox(height: UriSpace.sm),
        if (a.lastObservation != null)
          Text(
            'Read "${a.lastObservation!['title']}" · ${a.lastObservation!['fields']} fields · '
            '${a.lastObservation!['sensitive_fields']} private (hidden)',
            style: TextStyle(color: c.inkFaint, fontSize: 12),
          ),
        for (final f in a.findings)
          ListTile(
            dense: true,
            leading: Icon(Icons.lightbulb_outline, color: c.warning, size: 18),
            title: Text(f['field'] as String? ?? ''),
            subtitle: Text(f['message'] as String? ?? ''),
          ),
        if (a.lastObservation != null && a.findings.isEmpty)
          Text('No problems found.', style: TextStyle(color: c.success)),
      ],
    );
  }

  Widget _ask(AssistController a, UriColors c) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TextField(
          key: const ValueKey('assist-question'),
          controller: _question,
          maxLength: 1000,
          decoration: const InputDecoration(hintText: 'Ask about what you shared (e.g. "What does this field mean?")'),
        ),
        CheckboxListTile(
          key: const ValueKey('assist-screenshot-toggle'),
          contentPadding: EdgeInsets.zero,
          value: _screenshot,
          onChanged: (v) => setState(() => _screenshot = v ?? false),
          title: const Text('Include a screenshot for this question'),
          subtitle: const Text('Only now, only this scope. Private fields are blacked out first.'),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton(
            key: const ValueKey('assist-ask'),
            onPressed: a.active && !a.busy && !a.asking
                ? () {
                    final q = _question.text.trim();
                    if (q.isNotEmpty) a.ask(q, useScreenshot: _screenshot);
                  }
                : null,
            child: const Text('Ask'),
          ),
        ),
        if (a.asking)
          Padding(
            padding: const EdgeInsets.only(top: UriSpace.sm),
            child: Text('URI is reading what you shared… Stop cancels it.', key: const ValueKey('assist-asking'),
                style: TextStyle(color: c.inkSoft, fontSize: 12)),
          ),
        if (a.answer != null)
          Padding(
            padding: const EdgeInsets.only(top: UriSpace.sm),
            child: GlassPanel(
              key: const ValueKey('assist-answer'),
              child: Text(a.answer!.isEmpty ? 'URI could not answer this.' : a.answer!, style: TextStyle(color: c.ink)),
            ),
          ),
      ],
    );
  }

  Widget _research(AssistController a, UriColors c) {
    final results = a.results;
    final query = TextField(
      key: const ValueKey('assist-research-query'),
      controller: _query,
      maxLength: 400,
      decoration: const InputDecoration(hintText: 'What should URI look up?'),
    );
    final action = a.researching
        ? OutlinedButton(
            key: const ValueKey('assist-research-cancel'),
            onPressed: a.cancelResearch,
            child: const Text('Cancel'),
          )
        : FilledButton(
            key: const ValueKey('assist-research-go'),
            onPressed: a.busy
                ? null
                : () {
                    final q = _query.text.trim();
                    if (q.isNotEmpty) a.research(q);
                  },
            child: const Text('Research'),
          );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Searches public sources and answers with citations. It never looks at your screen.',
          style: TextStyle(color: c.inkSoft, fontSize: 12),
        ),
        const SizedBox(height: UriSpace.xs),
        LayoutBuilder(
          builder: (context, box) {
            if (box.maxWidth < 520 ||
                MediaQuery.textScalerOf(context).scale(14) > 18) {
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  query,
                  const SizedBox(height: 8),
                  Align(alignment: Alignment.centerRight, child: action),
                ],
              );
            }
            return Row(
              children: [
                Expanded(child: query),
                const SizedBox(width: 12),
                action,
              ],
            );
          },
        ),
        if (a.researching)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: UriSpace.xs),
            child: Text('Working: ${a.researchStage ?? 'starting'}…', key: const ValueKey('assist-research-stage'),
                style: TextStyle(color: c.inkSoft, fontSize: 12)),
          ),
        ListenableBuilder(
          listenable: results,
          builder: (context, _) => Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final s in results.placed('workspace'))
                A2uiSurfaceView(hub: results, surfaceId: s.id),
              for (final n in results.notices)
                Text(n, style: TextStyle(color: c.danger, fontSize: 12)),
            ],
          ),
        ),
      ],
    );
  }
}

String _scopeText(Map<String, dynamic>? scope) {
  if (scope == null) return 'nothing';
  final kind = _kindLabels[scope['kind']]?.$1.toLowerCase() ?? 'this';
  return '$kind "${scope['label']}"';
}

String _errorText(String code) => switch (code) {
  'ADAPTER_UNAVAILABLE' => 'URI can\'t read this kind of target on this PC yet.',
  'SCOPE_NOT_ACTIVE' => 'Assist is off. Choose what URI can see first.',
  'SCOPE_PAUSED' => 'Assist is paused.',
  'OBSERVATION_STALE' => 'That view is out of date; try again.',
  'TARGET_CHANGED' || 'TARGET_UNKNOWN' => 'The tab or window changed; choose it again.',
  'BRAIN_BUSY' => 'URI is answering you elsewhere; try again in a moment.',
  'VISION_NOT_QUALIFIED' => 'Screenshot understanding isn\'t available yet.',
  'SENSITIVE_FIELDS_UNLOCATED' => 'This screen has private fields URI can\'t hide, so no screenshot was used.',
  'WORKER_NOT_CONNECTED' => 'The URI worker is not connected.',
  'RESEARCH_IN_PROGRESS' => 'A research task is already running.',
  'ANSWER_CANCELLED' => 'The answer was cancelled (you stopped sharing, paused, or started a conversation).',
  'ASK_IN_PROGRESS' => 'URI is still answering your last question.',
  'TARGET_UNBOUND' => 'URI could not confirm which tab or window it read; nothing was used.',
  _ => 'URI refused: $code',
};

class _Frame extends StatelessWidget {
  const _Frame({
    required this.orbRect,
    required this.title,
    required this.subtitle,
    required this.trailing,
    required this.child,
  });
  final Rect orbRect;
  final String title;
  final String subtitle;
  final Widget trailing;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Padding(
      padding: EdgeInsets.fromLTRB(UriSpace.lg, 0, UriSpace.lg, VoiceDock.assistBottomReserve),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SizedBox(
            height: orbRect.bottom + 8,
            child: Padding(
              padding: EdgeInsets.only(left: orbRect.right + 8 - UriSpace.lg, top: orbRect.top),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(title, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: c.ink)),
                        const SizedBox(height: 4),
                        Text(subtitle, key: const ValueKey('assist-subtitle'),
                            style: TextStyle(fontSize: 13, color: c.inkSoft)),
                      ],
                    ),
                  ),
                  trailing,
                ],
              ),
            ),
          ),
          Expanded(child: child),
        ],
      ),
    );
  }
}

class _ScopeChip extends StatelessWidget {
  const _ScopeChip({required this.a});
  final AssistController a;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.circle, size: 10, color: a.active ? c.success : c.inkFaint),
        const SizedBox(width: 6),
        ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 220),
          child: Text(
            _scopeText(a.scope),
            key: const ValueKey('assist-scope-label'),
            overflow: TextOverflow.ellipsis,
            style: TextStyle(color: c.ink, fontSize: 13),
          ),
        ),
        IconButton(
          key: ValueKey(a.paused ? 'assist-resume' : 'assist-pause'),
          tooltip: a.paused ? 'Resume' : 'Pause',
          onPressed: a.busy ? null : (a.paused ? a.resume : a.pause),
          icon: Icon(a.paused ? Icons.play_arrow_rounded : Icons.pause_rounded),
        ),
        IconButton(
          key: const ValueKey('assist-stop'),
          tooltip: 'Stop sharing',
          onPressed: a.revoke,           // revocation is never disabled
          icon: Icon(Icons.stop_rounded, color: c.danger),
        ),
      ],
    );
  }
}

class _KindCard extends StatelessWidget {
  const _KindCard({
    required this.kind,
    required this.label,
    required this.icon,
    required this.adapter,
    required this.choosing,
    required this.targets,
    required this.onChoose,
    required this.onPick,
  });
  final String kind;
  final String label;
  final IconData icon;
  final Map<String, dynamic>? adapter;
  final bool choosing;
  final List<Map<String, dynamic>> targets;
  final VoidCallback onChoose;
  final void Function(Map<String, dynamic>) onPick;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final ok = adapter?['state'] == 'AVAILABLE';
    return GlassPanel(
      key: ValueKey('assist-kind-$kind'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, color: ok ? c.accent : c.inkFaint),
              const SizedBox(width: UriSpace.sm),
              Expanded(child: Text(label, style: TextStyle(fontWeight: FontWeight.w600, color: c.ink))),
              TextButton(onPressed: ok ? onChoose : null, child: Text(kind == 'entire_screen' ? 'Choose…' : 'Choose')),
            ],
          ),
          if (!ok)
            Text(
              'Not available on this PC: ${adapter?['reason'] ?? 'no adapter'}',
              key: ValueKey('assist-kind-$kind-unavailable'),
              style: TextStyle(color: c.inkFaint, fontSize: 12),
            ),
          if (choosing)
            for (final t in targets)
              ListTile(
                dense: true,
                key: ValueKey('assist-target-${t['target_id']}'),
                title: Text(t['label'] as String? ?? ''),
                subtitle: t['origin'] != null ? Text(t['origin'] as String) : null,
                onTap: () => onPick(t),
              ),
          if (choosing && targets.isEmpty)
            Text('Nothing to choose.', style: TextStyle(color: c.inkFaint, fontSize: 12)),
        ],
      ),
    );
  }
}

class _PermissionsRow extends StatelessWidget {
  const _PermissionsRow({required this.a});
  final AssistController a;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    const names = {
      'observe': 'See',
      'suggest': 'Suggest',
      'remember': 'Remember',
      'insert': 'Insert',
      'act': 'Act',
    };
    final p = a.permissions;
    return Wrap(
      key: const ValueKey('assist-permissions'),
      spacing: 10,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Text('Permissions:', style: TextStyle(color: c.inkSoft, fontSize: 12)),
        for (final e in names.entries)
          Text(
            '${e.value} ${p[e.key] == true ? '✓' : '–'}',
            key: ValueKey('assist-perm-${e.key}'),
            style: TextStyle(color: p[e.key] == true ? c.success : c.inkFaint, fontSize: 12),
          ),
      ],
    );
  }
}

class _Diagnostics extends StatelessWidget {
  const _Diagnostics({required this.a});
  final AssistController a;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final vision = (a.status['vision'] as Map?) ?? const {};
    return ExpansionTile(
      key: const ValueKey('assist-diagnostics'),
      tilePadding: EdgeInsets.zero,
      title: Text('Diagnostics', style: TextStyle(color: c.inkSoft, fontSize: 12)),
      children: [
        for (final ad in a.adapters)
          Align(
            alignment: Alignment.centerLeft,
            child: Text('${ad['adapter']}: ${ad['state']}${ad['reason'] != null ? ' — ${ad['reason']}' : ''}',
                style: TextStyle(color: c.inkFaint, fontSize: 11)),
          ),
        Align(
          alignment: Alignment.centerLeft,
          child: Text('Vision: model ${vision['model_level'] ?? '?'}; app ${vision['application'] ?? '?'}',
              style: TextStyle(color: c.inkFaint, fontSize: 11)),
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: Text('State ${a.state} · generation ${a.status['generation'] ?? '-'} · last refusal ${a.status['last_refusal'] ?? '-'}',
              style: TextStyle(color: c.inkFaint, fontSize: 11)),
        ),
      ],
    );
  }
}

class _ComingCard extends StatelessWidget {
  const _ComingCard({required this.title, required this.text});
  final String title;
  final String text;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return GlassPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: TextStyle(fontWeight: FontWeight.w700, color: c.ink)),
          const SizedBox(height: 6),
          Text(text, style: TextStyle(color: c.inkSoft, fontSize: 13)),
        ],
      ),
    );
  }
}
