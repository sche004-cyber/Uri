import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../widgets/glass_panel.dart';
import '../widgets/scroll_when_short.dart';
import 'oi_conversation.dart';
import 'oi_health_widgets.dart';
import 'oi_markdown.dart';

/// Working-system conversation surfaces (WS blueprint W9). Every control
/// here maps to one structured worker command; no widget infers an outcome
/// from answer text.

class OiConversationPane extends StatefulWidget {
  const OiConversationPane({
    super.key,
    required this.conversation,
    this.compact = false,
  });
  final OiConversation conversation;
  final bool compact;

  @override
  State<OiConversationPane> createState() => _OiConversationPaneState();
}

class _OiConversationPaneState extends State<OiConversationPane> {
  final _scroll = ScrollController();

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  void _follow() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scroll.hasClients) _scroll.jumpTo(_scroll.position.maxScrollExtent);
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return ListenableBuilder(
      listenable: widget.conversation,
      builder: (context, _) {
        final conv = widget.conversation;
        _follow();
        if (widget.compact) {
          final list = ListView(
            controller: _scroll,
            key: const ValueKey('oi-compact-messages'),
            // room under the last message for the pinned draft note
            padding: EdgeInsets.only(top: 8, bottom: conv.draft != null ? 30 : 8),
            children: [
              OiWorkerBanner(conversation: conv),
              OiHealthBanner(conversation: conv),
              if (conv.messages.isEmpty)
                Text(
                  conv.brainReady
                      ? 'Ask URI anything to begin.'
                      : 'The local Brain is not ready.',
                  style: TextStyle(color: c.inkSoft),
                ),
              for (final message in conv.messages)
                _MessageTile(message: message),
              if (conv.busy)
                TextButton.icon(
                  key: const ValueKey('oi-cancel'),
                  onPressed: conv.cancel,
                  icon: const Icon(Icons.stop_rounded, size: 16),
                  label: const Text('Stop'),
                ),
            ],
          );
          if (conv.draft == null) return list;
          // UIV2-F1: the compact (Companion) chat never changes an open draft;
          // a note pinned under the messages says so (no added fixed height).
          return Stack(
            children: [
              Positioned.fill(child: list),
              Positioned(
                left: 0,
                right: 0,
                bottom: 0,
                child: Container(
                  color: c.surface.withValues(alpha: .85),
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Text(
                    'A draft is open in Workspace. Messages here do not change it.',
                    key: const ValueKey('companion-draft-note'),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(color: c.inkSoft, fontSize: 11),
                  ),
                ),
              ),
            ],
          );
        }
        // UIV2-F3: banners, cards and the Stop button never push the pane
        // past a short window; it scrolls instead (l13: 34 px overflow).
        return ScrollWhenShort(
          // an approval or confirmation card needs room of its own (C1-03)
          minHeight: conv.pendingApproval != null || conv.pendingConfirmation != null ? 720 : 300,
          child: Column(
          children: [
            OiBrainBar(conversation: conv),
            OiWorkerBanner(conversation: conv),
            OiHealthBanner(conversation: conv),
            Expanded(
              child: ShortIntrinsic(
              child: conv.messages.isEmpty
                  ? Center(
                      child: Text(
                        conv.brainReady
                            ? 'Ask URI anything. Actions always need your approval.'
                            : 'The local Brain is not ready. Recognised commands still work.',
                        style: TextStyle(color: c.inkSoft),
                      ),
                    )
                  : ListView.builder(
                      key: const ValueKey('oi-messages'),
                      controller: _scroll,
                      padding: const EdgeInsets.all(UriSpace.md),
                      itemCount: conv.messages.length,
                      itemBuilder: (context, i) =>
                          _MessageTile(message: conv.messages[i]),
                    ),
              ),
            ),
            if (conv.pendingConfirmation != null)
              OiConfirmationCard(conversation: conv),
            if (conv.pendingApproval != null)
              OiApprovalCard(conversation: conv),
            if (conv.busy)
              Padding(
                padding: const EdgeInsets.only(bottom: UriSpace.sm),
                child: OutlinedButton.icon(
                  key: const ValueKey('oi-cancel'),
                  onPressed: conv.cancel,
                  icon: const Icon(Icons.stop_rounded, size: 16),
                  label: const Text('Stop'),
                ),
              ),
          ],
          ),
        );
      },
    );
  }
}

/// Plain words for Core's codes (FCV-08). The raw code stays in the chip's
/// tooltip and in the worker's event evidence.
String oiCoreLabel(String code) => switch (code) {
      'SETTLED_VERIFIED' => 'Done · checked',
      'SETTLED_FAILED' => 'Failed · nothing changed',
      'SETTLED_CANCELLED' => 'Cancelled',
      'SETTLED_EXECUTION_UNCERTAIN' || 'INTENT_EXECUTION_UNCERTAIN' => 'Outcome uncertain',
      'APPROVAL_REQUIRED' => 'Approval needed',
      'APPROVAL_DENIED' => 'Denied · nothing changed',
      'INTENT_CONFIRMATION_REQUIRED' => 'Please confirm',
      'INTENT_ABANDONED' => 'Stopped',
      'WAITING_FOR_MODEL' => 'Your choice needed',
      'CONVERSATION' => 'No action',
      _ when code.startsWith('CLARIFICATION_') || code == 'INTENT_CLARIFICATION' => 'Needs more detail',
      _ when code.startsWith('REFUSED_') => 'Not allowed',
      _ when code.startsWith('INTENT_') => 'Not done',
      _ => 'URI Core',
    };

/// Plain words for the worker's Brain readiness code (review R1-12); the code stays in the Dashboard detail.
String oiBrainStateLabel(String? state) => switch (state) {
      'READY' => 'ready',
      'LOADING' => 'loading',
      'STARTING' => 'starting',
      'STOPPED' => 'not running',
      'NOT_CONFIGURED' => 'not set up',
      'ARTIFACT_MISSING' => 'files missing',
      'IDENTITY_MISMATCH' || 'FOREIGN_INSTANCE' => 'check failed',
      'FAILED' => 'failed',
      null => 'checking',
      _ => 'unavailable',
    };

/// Plain words on the approval and confirmation cards (FCV-R final cycle). The internal capability id and effect
/// code stay in a tooltip; an unknown id or key is shown with spaces instead of underscores, never hidden.
String oiCapabilityLabel(String id) => switch (id) {
      'remember_fact' => "Save a fact to URI's memory on this computer",
      'external_harness_task' => 'Run a development task with the selected harness',
      _ => id.replaceAll('_', ' '),
    };

String oiArgumentLabel(String key) => switch (key) {
      'request_text' => 'Your request',
      'fact' => 'Fact',
      _ => key.replaceAll('_', ' '),
    };

String oiEffectLabel(String effect) => switch (effect) {
      'local_write' => 'Changes data on this computer',
      'external_write' => 'Changes something outside this computer',
      'read_only' => 'Only reads',
      _ => effect.replaceAll('_', ' '),
    };

String oiAnswerStatusLabel(String status) => switch (status) {
      'INCOMPLETE_LENGTH' => 'Cut short',
      'CANCELLED' => 'Stopped',
      'TIMED_OUT' || 'TIMEOUT' => 'Timed out',
      'ERROR' || 'FAILED' => 'Failed',
      _ => 'Incomplete',
    };

class _MessageTile extends StatelessWidget {
  const _MessageTile({required this.message});
  final OiMessage message;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final m = message;
    if (m.role == OiRole.user) {
      return Align(
        alignment: Alignment.centerRight,
        child: Container(
          margin: const EdgeInsets.symmetric(vertical: 4),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          constraints: const BoxConstraints(maxWidth: 560),
          decoration: BoxDecoration(
            color: c.accentSoft,
            borderRadius: BorderRadius.circular(UriRadius.sm),
          ),
          child: m.inputLabel == null
              ? Text(m.text, style: TextStyle(color: c.ink))
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    _Chip(
                      m.inputLabel!,
                      key: const ValueKey('oi-input-label'),
                      tone: c.warning,
                    ),
                    const SizedBox(height: 4),
                    Text(m.text, style: TextStyle(color: c.ink)),
                  ],
                ),
        ),
      );
    }
    if (m.role == OiRole.system) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Text(m.text, style: TextStyle(color: c.warning, fontSize: 12)),
      );
    }
    final chips = <Widget>[
      if (m.tier != null)
        _Chip(
          m.tier == 'NORMAL' ? 'Thinking' : 'Fast',
          key: const ValueKey('oi-tier'),
        ),
      if (m.route != null && m.route != 'answer') _Chip(_routeLabel(m.route!)),
      if (m.streaming && m.thinkingChars > 0 && m.text.isEmpty) _Chip('Reasoning… ${m.thinkingChars} chars'),
      if (m.streaming && m.draftChars > 0 && m.text.isEmpty) _Chip('Writing… ${m.draftChars} chars'),
      if (m.coreCode != null)
        Tooltip(message: m.coreCode!, child: _Chip(oiCoreLabel(m.coreCode!), tone: _coreTone(c, m.coreCode!))),
      if (m.answerStatus != null && m.answerStatus != 'COMPLETE')
        Tooltip(message: m.answerStatus!, child: _Chip(oiAnswerStatusLabel(m.answerStatus!), tone: c.warning)),
      if (m.unverifiedClaim) _Chip('Not an action receipt', tone: c.danger),
    ];
    final metrics = _metricsLine(m.metrics);
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        constraints: const BoxConstraints(maxWidth: 680),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (chips.isNotEmpty)
              Wrap(spacing: 6, runSpacing: 4, children: chips),
            if (m.text.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: OiMarkdown(m.text, key: ValueKey('oi-text-${m.turnId}')),
              )
            else if ((m.outcomeSummary ?? m.coreMessage) != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: SelectableText(
                  (m.outcomeSummary ?? m.coreMessage)!,
                  key: ValueKey('oi-text-${m.turnId}'),
                  style: TextStyle(color: c.ink, height: 1.4),
                ),
              ),
            if (m.streaming && m.text.isEmpty && m.coreMessage == null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('…', style: TextStyle(color: c.inkFaint)),
              ),
            if (m.errorCode != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Tooltip(
                  message: m.errorCode!,
                  child: Text(m.errorMessage ?? 'Something went wrong. Try again.',
                      key: const ValueKey('oi-error'), style: TextStyle(color: c.danger, fontSize: 12)),
                ),
              ),
            if (metrics != null)
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  metrics,
                  key: const ValueKey('oi-metrics'),
                  style: TextStyle(color: c.inkFaint, fontSize: 11),
                ),
              ),
          ],
        ),
      ),
    );
  }

  static String _routeLabel(String r) => switch (r) {
    'core' => 'URI Core',
    'core+answer' => 'Core → answer',
    'plan' => 'Plan',
    'draft' => 'Writing desk',
    'harness_choice' => 'Needs a tool choice',
    'escalation_offer' => 'Needs a stronger tool',
    _ => r,
  };

  static Color _coreTone(UriColors c, String code) => code == 'SETTLED_VERIFIED'
      ? c.success
      : (code.startsWith('REFUSED') ||
                code.contains('UNAVAILABLE') ||
                code.contains('UNCERTAIN')
            ? c.danger
            : c.inkSoft);

  static String? _metricsLine(Map<String, dynamic> m) {
    if (m.isEmpty) return null;
    String? f(String k, String unit, [int digits = 1]) {
      final v = m[k];
      return v is num ? '${v.toStringAsFixed(digits)}$unit' : null;
    }

    final parts = [
      if (f('ttft_s', ' s') case final x?) 'first token $x',
      ?f('predicted_per_second', ' tok/s'),
      if (f('total_s', ' s') case final x?) 'total $x',
    ];
    return parts.isEmpty ? null : parts.join(' · ');
  }
}

class _Chip extends StatelessWidget {
  const _Chip(this.label, {super.key, this.tone});
  final String label;
  final Color? tone;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final t = tone ?? c.inkSoft;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        border: Border.all(color: t.withValues(alpha: 0.6)),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(label, style: TextStyle(color: t, fontSize: 11)),
    );
  }
}

class OiApprovalCard extends StatelessWidget {
  const OiApprovalCard({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final a = conversation.pendingApproval!;
    final inputs = (a.arguments['inputs'] as Map?) ?? a.arguments;
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: UriSpace.md,
        vertical: UriSpace.sm,
      ),
      child: GlassPanel(
        key: const ValueKey('oi-approval-card'),
        glowBorder: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Tooltip(
              message: a.capabilityId,
              child: Text('URI wants to: ${oiCapabilityLabel(a.capabilityId)}',
                  style: TextStyle(color: c.ink, fontWeight: FontWeight.w600)),
            ),
            const SizedBox(height: 6),
            for (final e in inputs.entries)
              Text('${oiArgumentLabel('${e.key}')}: ${e.value}', style: TextStyle(color: c.inkSoft, fontSize: 13)),
            if (a.effect != null || a.reversible != null)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Tooltip(
                  message: a.effect ?? '',
                  child: Text(
                    [
                      if (a.effect != null) oiEffectLabel(a.effect!),
                      if (a.reversible != null) a.reversible! ? 'Can be undone' : 'Cannot be undone',
                    ].join(' · '),
                    style: TextStyle(color: c.inkFaint, fontSize: 12),
                  ),
                ),
              ),
            const SizedBox(height: 4),
            Text(
              'Only these buttons approve. Typed text never does.',
              style: TextStyle(color: c.inkFaint, fontSize: 11),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                FilledButton(
                  key: const ValueKey('oi-approve'),
                  onPressed: () => conversation.decide(approve: true),
                  child: const Text('Approve'),
                ),
                const SizedBox(width: 8),
                OutlinedButton(
                  key: const ValueKey('oi-deny'),
                  onPressed: () => conversation.decide(approve: false),
                  child: const Text('Deny'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class OiConfirmationCard extends StatelessWidget {
  const OiConfirmationCard({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final p = conversation.pendingConfirmation!;
    final args = (p.data['arguments'] as Map?) ?? const {};
    return Padding(
      padding: const EdgeInsets.symmetric(
        horizontal: UriSpace.md,
        vertical: UriSpace.sm,
      ),
      child: GlassPanel(
        key: const ValueKey('oi-confirmation-card'),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(p.message ?? 'Is this what you meant?', style: TextStyle(color: c.ink)),
            for (final e in args.entries)
              Text('${oiArgumentLabel('${e.key}')}: ${e.value}', style: TextStyle(color: c.inkSoft, fontSize: 13)),
            const SizedBox(height: 8),
            // UIV2-F3 (C1-03): the buttons wrap in a narrow pane instead of overflowing.
            Wrap(
              spacing: 8,
              runSpacing: 6,
              children: [
                FilledButton(
                  key: const ValueKey('oi-confirm'),
                  onPressed: conversation.confirm,
                  child: const Text('Yes, continue'),
                ),
                OutlinedButton(
                  onPressed: conversation.abandon,
                  child: const Text('No'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// Brain readiness + selection + depth. Selection is an explicit choice
/// among selectable catalog rows; there is no fallback.
class OiBrainBar extends StatelessWidget {
  const OiBrainBar({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final conv = conversation;
    final state = oiBrainStateLabel(conv.brainStatus['state'] as String?);
    final health = conv.healthState;
    final rows = [
      for (final r in (conv.catalog['rows'] as List? ?? const []))
        if (r is Map) r,
    ];
    final selectable = [
      for (final r in rows)
        if (r['selectable'] == true) r,
    ];
    // The label is plain words; readiness is decided on the raw state code.
    final ready = conv.brainStatus['state'] == 'READY';
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        UriSpace.md,
        UriSpace.sm,
        UriSpace.md,
        0,
      ),
      // UIV2-F3: a picker never grows past its line; in a narrow pane it
      // ellipsizes instead of overflowing (96 / 156 px in the shrink test).
      child: Builder(builder: (context) {
      Widget fit(Widget picker) => ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 260),
            child: IntrinsicWidth(child: picker),
          );
      return Wrap(
        spacing: 8,
        runSpacing: 6,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Icon(
            Icons.circle,
            size: 10,
            color: health != null
                ? healthColor(c, health)
                : (ready
                      ? c.success
                      : (state == 'checking' ? c.inkFaint : c.warning)),
          ),
          Text(
            'Brain: ${conv.brainStatus['model_id'] ?? 'Runtime v1'} · $state',
            key: const ValueKey('oi-brain-state'),
            style: TextStyle(color: c.inkSoft, fontSize: 12),
          ),
          if (health != null) OiHealthChip(conversation: conv),
          if (selectable.length > 1)
            fit(DropdownButton<String>(
              key: const ValueKey('oi-brain-picker'),
              value: conv.selectedRowId,
              isDense: true,
              isExpanded: true,
              underline: const SizedBox.shrink(),
              style: TextStyle(color: c.ink, fontSize: 12),
              items: [
                for (final r in selectable)
                  DropdownMenuItem(
                    value: r['id'] as String,
                    child: Text('${r['display']}', overflow: TextOverflow.ellipsis),
                  ),
              ],
              onChanged: conv.busy
                  ? null
                  : (v) => v == null ? null : conv.selectBrain(v),
            )),
          fit(DropdownButton<OiDepth>(
            key: const ValueKey('oi-depth'),
            value: conv.depth,
            isDense: true,
            isExpanded: true,
            underline: const SizedBox.shrink(),
            style: TextStyle(color: c.ink, fontSize: 12),
            items: const [
              DropdownMenuItem(value: OiDepth.auto, child: Text('Depth: auto', overflow: TextOverflow.ellipsis)),
              DropdownMenuItem(value: OiDepth.fast, child: Text('Depth: fast', overflow: TextOverflow.ellipsis)),
              DropdownMenuItem(
                value: OiDepth.normal,
                child: Text('Depth: thinking', overflow: TextOverflow.ellipsis),
              ),
              DropdownMenuItem(
                value: OiDepth.deep,
                child: Text('Depth: deep (offer a stronger tool)', overflow: TextOverflow.ellipsis),
              ),
            ],
            onChanged: (v) => v == null ? null : conv.setDepth(v),
          )),
          IconButton(
            tooltip: 'Refresh Brain status',
            icon: const Icon(Icons.refresh_rounded, size: 16),
            onPressed: conv.refreshStatus,
          ),
        ],
      );
      }),
    );
  }
}
