import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../theme/uri_theme.dart';
import '../widgets/scroll_when_short.dart';
import '../widgets/glass_panel.dart';
import 'oi_conversation.dart';
import 'oi_draft.dart';

/// What the draft panel shows.
enum DraftView { current, changes, original }

/// The session's draft beside the conversation (text intelligence, TI-AC9).
///
/// * Current: the latest accepted text; blocks changed by the last step are
///   marked.
/// * Changes: word-level comparison with the previous version.
/// * Original: the first version and the user's own words. For speech the
///   raw transcript is shown apart from URI's interpretation and labelled
///   SIMULATED when it was.
///
/// Undo / Redo / Close are structured `draft_op` commands; they never send,
/// save or overwrite anything. Copy puts the text on the clipboard only.
class DraftPanel extends StatefulWidget {
  const DraftPanel({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  State<DraftPanel> createState() => _DraftPanelState();
}

class _DraftPanelState extends State<DraftPanel> {
  DraftView _view = DraftView.current;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return ListenableBuilder(
      listenable: widget.conversation,
      builder: (context, _) {
        final conv = widget.conversation;
        final d = conv.draft;
        if (d == null) return const SizedBox.shrink();
        final cur = d.current;
        final errors = cur.flags.where((f) => f.isError).toList();
        final reviews = cur.flags.where((f) => f.severity == 'review').toList();
        final infos = cur.flags.where((f) => f.severity == 'info').toList();
        return GlassPanel(
          key: const ValueKey('draft-panel'),
          padding: const EdgeInsets.all(UriSpace.md),
          // UIV2-F3: a panel squeezed below its natural height (the one-frame
          // shrink into Companion, a short window) scrolls instead of overflowing.
          child: ScrollWhenShort(
            child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Icon(Icons.edit_note_rounded, size: 18, color: c.accent),
                  const SizedBox(width: 6),
                  Expanded(
                    child: Text(
                      _title(d.docType),
                      style: TextStyle(color: c.ink, fontWeight: FontWeight.w600),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Flexible(
                    child: Text(
                      'Version ${d.position} of ${d.count}',
                      key: const ValueKey('draft-version'),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(color: c.inkSoft, fontSize: 12),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 6),
              Wrap(
                spacing: 6,
                runSpacing: 4,
                children: [
                  _Tag(d.sourceLabel, key: const ValueKey('draft-source'),
                      tone: d.simulatedTranscript ? c.warning : c.inkSoft),
                  _Tag(_opLabel(cur.op)),
                  _Tag('Not sent · not saved', tone: c.inkSoft),
                  if (d.replacedDocType != null)
                    _Tag('Replaced your earlier ${d.replacedDocType} · Undo brings it back',
                        key: const ValueKey('draft-replaced'), tone: c.warning),
                ],
              ),
              if (cur.summary.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text(cur.summary, style: TextStyle(color: c.inkSoft, fontSize: 12)),
                ),
              const SizedBox(height: 8),
              SegmentedButton<DraftView>(
                key: const ValueKey('draft-view'),
                showSelectedIcon: false,
                segments: [
                  const ButtonSegment(value: DraftView.current, label: Text('Current')),
                  ButtonSegment(
                    value: DraftView.changes,
                    label: const Text('Changes'),
                    enabled: d.previous != null,
                  ),
                  const ButtonSegment(value: DraftView.original, label: Text('Original')),
                ],
                selected: {_view == DraftView.changes && d.previous == null ? DraftView.current : _view},
                onSelectionChanged: (s) => setState(() => _view = s.first),
              ),
              const SizedBox(height: 8),
              // Everything between the header and the toolbar scrolls together, so many checks or missing
              // items can never overflow the panel (live UI finding, TI live run 2026-10-09).
              Expanded(
                child: ShortIntrinsic(
                // a few lines of the draft stay visible even when the panel scrolls
                height: 140,
                child: SingleChildScrollView(
                  key: const ValueKey('draft-scroll'),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      if (conv.draftQuestion != null)
                        _Banner(conv.draftQuestion!, tone: c.accent, icon: Icons.help_outline_rounded),
                      for (final f in errors)
                        _Banner('${_flagLabel(f.code)}: ${f.detail}', tone: c.danger, icon: Icons.error_outline_rounded),
                      for (final f in reviews)
                        _Banner('${_flagLabel(f.code)}: ${f.detail}', tone: c.warning, icon: Icons.visibility_outlined),
                      for (final f in infos)
                        _Banner('${_flagLabel(f.code)}: ${f.detail}', tone: c.inkSoft, icon: Icons.info_outline_rounded),
                      if (cur.missing.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(bottom: 6),
                          child: Wrap(
                            spacing: 6,
                            runSpacing: 4,
                            crossAxisAlignment: WrapCrossAlignment.center,
                            children: [
                              Text('Missing:', style: TextStyle(color: c.inkSoft, fontSize: 12)),
                              for (final m in cur.missing) _Tag(m, tone: c.warning),
                            ],
                          ),
                        ),
                      switch (_view) {
                        DraftView.current => _CurrentText(version: cur),
                        DraftView.changes => d.previous == null
                            ? _CurrentText(version: cur)
                            : _DiffText(before: d.previous!.text, after: cur.text),
                        DraftView.original => _OriginalView(draft: d),
                      },
                    ],
                  ),
                ),
                ),
              ),
              const SizedBox(height: 8),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  OutlinedButton.icon(
                    key: const ValueKey('draft-undo'),
                    onPressed: d.canUndo && !conv.draftActionsBlocked ? () => conv.draftOp('undo') : null,
                    icon: const Icon(Icons.undo_rounded, size: 16),
                    label: const Text('Undo'),
                  ),
                  OutlinedButton.icon(
                    key: const ValueKey('draft-redo'),
                    onPressed: d.canRedo && !conv.draftActionsBlocked ? () => conv.draftOp('redo') : null,
                    icon: const Icon(Icons.redo_rounded, size: 16),
                    label: const Text('Redo'),
                  ),
                  OutlinedButton.icon(
                    key: const ValueKey('draft-copy'),
                    onPressed: () => Clipboard.setData(ClipboardData(text: cur.text)),
                    icon: const Icon(Icons.copy_rounded, size: 16),
                    label: const Text('Copy'),
                  ),
                  TextButton(
                    key: const ValueKey('draft-close'),
                    onPressed: conv.draftActionsBlocked ? null : () => conv.draftOp('discard'),
                    child: const Text('Close draft'),
                  ),
                ],
              ),
            ],
          ),
          ),
        );
      },
    );
  }

  static String _title(String docType) =>
      docType.isEmpty ? 'Draft' : '${docType[0].toUpperCase()}${docType.substring(1)}';

  static String _opLabel(String op) => switch (op) {
        'created' => 'Drafted',
        'revised' => 'Revised',
        'corrected' => 'Grammar corrected',
        'rewritten' => 'Rewritten',
        'restored' => 'Restored',
        'original' => 'Your text',
        _ => op,
      };

  static String _flagLabel(String code) => switch (code) {
        'FACT_UNSOURCED' => 'Detail not from you',
        'FACT_MISSING' => 'Detail missing',
        'SUPERSEDED_VALUE_PRESENT' => 'Corrected value still present',
        'EXCLUDED_PHRASE_PRESENT' => 'Excluded wording present',
        'MEANING_CHANGED' => 'Meaning may have changed',
        'NEW_DETAIL' => 'Please check',
        'CORRECTION_UNCONFIRMED' => 'Check your correction',
        'POSSIBLE_MISHEARING' => 'Possibly misheard',
        'EDIT_OUTSIDE_TARGET' => 'Kept unchanged',
        'DETAIL_DROPPED' => 'Left out',
        'DETAIL_REMOVED' => 'Removed',
        'USER_DETAIL_MISSING' => 'Not in the draft',
        'SUPERSESSION_UNVERIFIED' => 'Check this replacement',
        _ => code,
      };
}

class _CurrentText extends StatelessWidget {
  const _CurrentText({required this.version});
  final OiDraftVersion version;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Column(
      key: const ValueKey('draft-current'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final b in version.blocks)
          Container(
            key: ValueKey('draft-block-${b.id}'),
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.only(left: 8),
            decoration: BoxDecoration(
              border: Border(
                left: BorderSide(
                  width: 3,
                  color: version.changed.contains(b.id) && version.op != 'created' ? c.accent : Colors.transparent,
                ),
              ),
            ),
            child: SelectableText(
              b.text,
              style: TextStyle(
                color: c.ink,
                height: 1.45,
                fontWeight: b.role == 'subject' ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ),
      ],
    );
  }
}

class _DiffText extends StatelessWidget {
  const _DiffText({required this.before, required this.after});
  final String before;
  final String after;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final segs = wordDiff(before, after);
    return SelectableText.rich(
      key: const ValueKey('draft-diff'),
      TextSpan(
        style: TextStyle(color: c.ink, height: 1.45),
        children: [
          for (final s in segs)
            TextSpan(
              text: s.text,
              style: switch (s.kind) {
                DiffKind.same => null,
                DiffKind.added => TextStyle(backgroundColor: c.successSoft, color: c.ink),
                DiffKind.removed => TextStyle(
                    backgroundColor: c.dangerSoft,
                    color: c.inkSoft,
                    decoration: TextDecoration.lineThrough,
                  ),
              },
            ),
        ],
      ),
    );
  }
}

class _OriginalView extends StatelessWidget {
  const _OriginalView({required this.draft});
  final OiDraft draft;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final label = draft.fromTranscript
        ? (draft.simulatedTranscript ? 'Original transcript — SIMULATED input (no microphone)' : 'Original transcript (as heard)')
        : 'Your original words';
    return Column(
      key: const ValueKey('draft-original'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(label, style: TextStyle(color: draft.simulatedTranscript ? c.warning : c.inkSoft, fontSize: 12)),
        const SizedBox(height: 4),
        Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(color: c.surfaceSunken, borderRadius: BorderRadius.circular(UriRadius.sm)),
          child: SelectableText(draft.originalText, key: const ValueKey('draft-original-text'),
              style: TextStyle(color: c.ink, height: 1.4)),
        ),
        if (draft.first != null) ...[
          const SizedBox(height: 10),
          Text('First version (URI\'s interpretation)', style: TextStyle(color: c.inkSoft, fontSize: 12)),
          const SizedBox(height: 4),
          SelectableText(draft.first!.text, style: TextStyle(color: c.ink, height: 1.45)),
        ],
      ],
    );
  }
}

class _Banner extends StatelessWidget {
  const _Banner(this.text, {required this.tone, required this.icon});
  final String text;
  final Color tone;
  final IconData icon;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 15, color: tone),
          const SizedBox(width: 6),
          Expanded(child: Text(text, style: TextStyle(color: tone, fontSize: 12))),
        ],
      ),
    );
  }
}

class _Tag extends StatelessWidget {
  const _Tag(this.label, {super.key, this.tone});
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

