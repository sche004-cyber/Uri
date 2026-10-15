import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../a2ui/a2ui_view.dart';
import '../living_scope.dart';
import '../widgets/glass_panel.dart';
import '../widgets/living_composer.dart';
import 'document_controller.dart';
import 'office_bridge.dart';
import 'office_controller.dart';
import 'office_conversation.dart';

/// The URI companion for an open workbook (extracted unchanged from `office_panel.dart`, plan §4.3): the owner's
/// requests, URI's replies, URI's suggested changes with Accept and Reject, the added files and their roles, and the
/// approval card. Excel behaviour is the M1/M2 behaviour.
class OfficeSheetCompanion extends StatefulWidget {
  const OfficeSheetCompanion({super.key, required this.controller, required this.environment});
  final OfficeController controller;
  final OfficeEnvironment environment;

  @override
  State<OfficeSheetCompanion> createState() => _OfficeSheetCompanionState();
}

class _OfficeSheetCompanionState extends State<OfficeSheetCompanion> {
  final _ask = TextEditingController();

  @override
  void dispose() {
    _ask.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    final open = c.workbookId != null;
    final env = widget.environment;
    final colors = UriColors.of(context);
    final google = c.view?['engine'] == 'google';
    final scoped = LivingScope.maybeOf(context) != null;
    return GlassPanel(
      key: const ValueKey('office-companion'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(children: [
            Icon(Icons.blur_on_rounded, size: 18, color: colors.accent),
            const SizedBox(width: 6),
            const Expanded(child: Text('URI', style: TextStyle(fontWeight: FontWeight.w600))),
            if (c.busy)
              const SizedBox(
                key: ValueKey('office-companion-busy'),
                width: 14,
                height: 14,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
          ]),
          const Divider(height: 16),
          Expanded(
            child: ListView(
              key: const ValueKey('office-conversation'),
              children: [
                if (!open)
                  Text('Open a workbook, then tell URI what to change. URI suggests; you accept, reject and save.',
                      style: TextStyle(color: colors.inkSoft)),
                if (c.sources.isNotEmpty) _sources(context, c, env),
                for (final (i, t) in c.conversation.indexed) _turn(context, t, i),
                if (c.busy)
                  Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('URI is working on it...', style: TextStyle(color: colors.inkSoft)),
                  ),
                if (c.proposed.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text('URI\'s suggested changes (${c.proposed.length})', style: const TextStyle(fontWeight: FontWeight.w600)),
                ],
                // M2-D2: one request can propose thousands of cells; decide them all at once, bound to what is shown.
                if (c.proposed.length > 1)
                  Wrap(spacing: 6, children: [
                    FilledButton.tonal(
                      key: const ValueKey('office-accept-all'),
                      onPressed: c.busy ? null : () => c.decideAll('accept'),
                      child: Text('Accept all ${c.proposed.length}'),
                    ),
                    TextButton(
                      key: const ValueKey('office-reject-all'),
                      onPressed: c.busy ? null : () => c.decideAll('reject'),
                      child: Text('Reject all ${c.proposed.length}'),
                    ),
                  ]),
                for (final ch in c.proposed.take(maxCards))
                  Container(
                    key: ValueKey('office-change-${ch['cid']}'),
                    margin: const EdgeInsets.only(top: 6),
                    padding: const EdgeInsets.all(8),
                    decoration: BoxDecoration(
                      color: colors.warningSoft,
                      borderRadius: BorderRadius.circular(6),
                      border: Border.all(color: colors.warning),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(children: [
                          Icon(Icons.auto_awesome_rounded, size: 14, color: colors.warning, key: const ValueKey('office-uri-mark')),
                          const SizedBox(width: 4),
                          Expanded(child: Text(_describe(ch), maxLines: 3, overflow: TextOverflow.ellipsis)),
                        ]),
                        Row(children: [
                          TextButton(onPressed: c.busy ? null : () => c.decide(ch, 'accept'), child: const Text('Accept')),
                          TextButton(onPressed: c.busy ? null : () => c.decide(ch, 'reject'), child: const Text('Reject')),
                        ]),
                      ],
                    ),
                  ),
                if (c.proposed.length > maxCards)
                  Padding(
                    key: const ValueKey('office-more-changes'),
                    padding: const EdgeInsets.only(top: 6),
                    child: Text('and ${c.proposed.length - maxCards} more, marked in the sheet',
                        style: TextStyle(color: colors.inkSoft)),
                  ),
                for (final s in c.hub.placed('workspace'))
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: A2uiSurfaceView(hub: c.hub, surfaceId: s.id),
                  ),
                if (open) ...[
                  const Divider(height: 24),
                  Wrap(spacing: 6, runSpacing: 6, children: [
                    OutlinedButton(onPressed: c.busy || c.draft['can_undo'] != true ? null : c.undo, child: const Text('Undo')),
                    OutlinedButton(onPressed: c.busy || c.draft['can_redo'] != true ? null : c.redo, child: const Text('Redo')),
                    if (c.isNew)
                      FilledButton(
                        key: const ValueKey('office-save-new'),
                        onPressed: c.busy
                            ? null
                            : () async {
                                final p = await env.pickSavePath('New workbook');
                                if (p != null) await c.proposeSave(saveAsPath: p);
                              },
                        child: const Text('Save as new file...'),
                      )
                    else
                      FilledButton(
                        key: const ValueKey('office-save'),
                        onPressed: c.busy ? null : () => c.proposeSave(),
                        child: Text(google ? 'Apply to Google Sheet' : 'Save to file'),
                      ),
                    if (!google && !c.isNew)
                      OutlinedButton(
                        onPressed: c.busy
                            ? null
                            : () async {
                                final p = await env.pickSavePath('${c.view?['label'] ?? 'workbook'}');
                                if (p != null) await c.proposeSave(saveAsPath: p);
                              },
                        child: const Text('Save as...'),
                      ),
                    if (!google && !c.isNew)
                      OutlinedButton(onPressed: c.busy ? null : c.proposeShare, child: const Text('Share via Google')),
                    if (google && c.view?['writable'] != true)
                      OutlinedButton(onPressed: c.busy ? null : c.editCopy, child: const Text('Edit a copy')),
                  ]),
                  if (!c.isNew)
                  SwitchListTile(
                    key: const ValueKey('office-history-consent'),
                    dense: true,
                    contentPadding: EdgeInsets.zero,
                    title: const Text('Keep a correction history for this workbook'),
                    subtitle: const Text('What changed and why, never cell values. Off unless you turn it on.'),
                    value: c.view?['history_on'] == true,
                    onChanged: c.busy ? null : c.setHistory,
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 6),
          // The companion's own composer (with push-to-talk) inside the living UI; a plain request box when this
          // region is shown on its own.
          if (scoped)
            const LivingComposer(compact: true, hint: 'Ask URI to change this sheet')
          else
            Row(children: [
              Expanded(
                child: TextField(
                  key: const ValueKey('office-ask'),
                  controller: _ask,
                  enabled: open,
                  minLines: 1,
                  maxLines: 4,
                  decoration: const InputDecoration(hintText: 'Ask URI to change the sheet'),
                  onSubmitted: (_) => _sendAsk(c),
                ),
              ),
              IconButton(
                key: const ValueKey('office-ask-send'),
                tooltip: 'Ask URI',
                onPressed: c.busy || !open ? null : () => _sendAsk(c),
                icon: const Icon(Icons.arrow_upward_rounded),
              ),
            ]),
        ],
      ),
    );
  }

  /// At most this many change cards; the rest are marked in the sheet (M2-AC8).
  static const int maxCards = 50;

  /// M2: the added files and what each is for (M2-D10/D11): the working file (check or edit; shown in the sheet
  /// view) or a reference (read-only). URI does not work with the files until each has a role.
  Widget _sources(BuildContext context, OfficeController c, OfficeEnvironment env) {
    final colors = UriColors.of(context);
    final missing = c.rolesNeeded.isNotEmpty;
    return Container(
      key: const ValueKey('office-sources'),
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        border: Border.all(color: missing ? colors.warning : colors.inkFaint),
        borderRadius: BorderRadius.circular(6),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(
          missing ? 'What is each file for?' : 'Files',
          key: const ValueKey('office-roles-title'),
          style: TextStyle(color: missing ? colors.warning : colors.inkSoft, fontSize: 12, fontWeight: FontWeight.w600),
        ),
        if (missing)
          Text('Choose a reference (URI only reads it) or the working file (URI checks or edits it; one at a time).',
              style: TextStyle(color: colors.inkSoft, fontSize: 12)),
        const SizedBox(height: 4),
        for (final s in c.sources) _roleRow(context, c, s),
        Wrap(spacing: 6, runSpacing: 4, children: [
          if (env.pickSourcePaths != null)
            ActionChip(
              key: const ValueKey('office-add-source'),
              visualDensity: VisualDensity.compact,
              avatar: const Icon(Icons.add, size: 16),
              label: const Text('Add file'),
              onPressed: c.busy
                  ? null
                  : () async {
                      final paths = await env.pickSourcePaths!();
                      if (paths.isNotEmpty) await c.addSources(paths);
                    },
            ),
        ]),
      ]),
    );
  }

  Widget _roleRow(BuildContext context, OfficeController c, Map<String, dynamic> s) {
    final colors = UriColors.of(context);
    final id = s['id'] as String;
    final role = s['role'] as String?;
    final working = role == 'check' || role == 'edit';
    return Padding(
      key: ValueKey('office-source-$id'),
      padding: const EdgeInsets.only(bottom: 6),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(working ? Icons.edit_document : Icons.description_outlined, size: 16,
              color: working ? colors.accent : colors.inkSoft),
          const SizedBox(width: 4),
          Expanded(child: Text('$id ${s['label']}', overflow: TextOverflow.ellipsis)),
          if (working)
            Text('Working file', key: ValueKey('office-working-$id'),
                style: TextStyle(color: colors.accent, fontSize: 12, fontWeight: FontWeight.w600))
          else if (role == 'reference')
            Text('Reference', style: TextStyle(color: colors.inkSoft, fontSize: 12)),
        ]),
        const SizedBox(height: 2),
        SegmentedButton<String>(
          key: ValueKey('office-role-$id'),
          showSelectedIcon: false,
          emptySelectionAllowed: true,
          style: const ButtonStyle(visualDensity: VisualDensity.compact),
          segments: const [
            ButtonSegment(value: 'reference', label: Text('Reference')),
            ButtonSegment(value: 'check', label: Text('Check')),
            ButtonSegment(value: 'edit', label: Text('Edit')),
          ],
          selected: {?role},
          onSelectionChanged: c.busy
              ? null
              : (sel) {
                  if (sel.isNotEmpty) c.setRole(id, sel.first);
                },
        ),
      ]),
    );
  }

  Future<void> _sendAsk(OfficeController c) async {
    final text = _ask.text.trim();
    if (text.isEmpty || c.busy) return;
    _ask.clear();
    await c.instruct(text);
  }

  Widget _turn(BuildContext context, OfficeTurn t, int i) {
    final colors = UriColors.of(context);
    final owner = t.speaker == OfficeSpeaker.owner;
    return Align(
      alignment: owner ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        key: ValueKey('office-turn-$i-${t.speaker.name}'),
        margin: const EdgeInsets.only(top: 6),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        constraints: const BoxConstraints(maxWidth: 300),
        decoration: BoxDecoration(
          color: owner ? colors.accent.withValues(alpha: 0.14) : colors.surface,
          borderRadius: BorderRadius.circular(10),
        ),
        child: Text(
          t.speaker == OfficeSpeaker.uri ? 'URI: ${t.text}' : t.text,
          style: TextStyle(color: t.speaker == OfficeSpeaker.notice ? colors.warning : colors.ink),
        ),
      ),
    );
  }

  static String _describe(Map<String, dynamic> ch) {
    if (ch['kind'] == 'struct') return 'Structure: ${ch['op']}';
    final after = (ch['after'] as Map?) ?? const {};
    final v = after['f'] ?? after['v'];
    return '${ch['sheet']}!${ch['cell']} -> ${v ?? '(empty)'}';
  }
}

/// The persistent URI pane of the Office workspace for Home, lists, documents and tasks (B1 right pane): the region
/// conversation with each line's target, clarification and follow-up chips, the hint (one at a time), the plan and
/// output cards through the region-level A2UI hub, and the companion's composer. Requests made here go to the
/// workspace controller (the Office request target).
class OfficeCompanionPane extends StatelessWidget {
  const OfficeCompanionPane({super.key, required this.controller, this.composerFocus, this.onClose});
  final OfficeWorkspaceController controller;
  final FocusNode? composerFocus;
  final VoidCallback? onClose;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final colors = UriColors.of(context);
    final scoped = LivingScope.maybeOf(context) != null;
    final lines = c.conversation.lines;
    return GlassPanel(
      key: const ValueKey('office-uri-pane'),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(children: [
            Icon(Icons.blur_on_rounded, size: 18, color: colors.accent),
            const SizedBox(width: 6),
            Expanded(child: Text('URI · ${c.targetLabel}', overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w600))),
            if (c.busy)
              const SizedBox(key: ValueKey('office-uri-busy'), width: 14, height: 14,
                  child: CircularProgressIndicator(strokeWidth: 2)),
            if (onClose != null)
              IconButton(tooltip: 'Close URI pane', onPressed: onClose, icon: const Icon(Icons.close_rounded, size: 18)),
          ]),
          const Divider(height: 16),
          if (c.hint != null)
            Container(
              key: const ValueKey('office-hint'),
              padding: const EdgeInsets.all(UriSpace.sm),
              margin: const EdgeInsets.only(bottom: UriSpace.sm),
              decoration: BoxDecoration(color: colors.accentSoft, borderRadius: BorderRadius.circular(UriRadius.sm)),
              child: Row(children: [
                Expanded(child: Text(c.hint!, style: TextStyle(color: colors.ink))),
                IconButton(key: const ValueKey('office-hint-dismiss'), tooltip: 'Dismiss hint',
                    onPressed: c.dismissHint, icon: const Icon(Icons.close_rounded, size: 16)),
              ]),
            ),
          Expanded(
            child: ListView(
              key: const ValueKey('office-region-conversation'),
              children: [
                if (lines.isEmpty)
                  Text('Ask for what you need, or open a file. URI shows a plan before it changes anything.',
                      style: TextStyle(color: colors.inkSoft)),
                for (final (i, l) in lines.indexed) _line(context, c, l, i),
                for (final s in c.hub.placed('workspace'))
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: A2uiSurfaceView(hub: c.hub, surfaceId: s.id),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 6),
          if (scoped)
            const LivingComposer(compact: true, hint: 'Ask URI Office')
          else
            _PlainComposer(controller: c, focus: composerFocus),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton(
              key: const ValueKey('office-help-chip'),
              onPressed: c.busy ? null : () => c.chip('help'),
              child: const Text('What can URI Office do?'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _line(BuildContext context, OfficeWorkspaceController c, OfficeLine l, int i) {
    final colors = UriColors.of(context);
    final owner = l.speaker == OfficeSpeaker.owner;
    final chips = [for (final ch in l.chips) if (!c.conversation.chipDismissed('$i:${ch.$2}')) ch];
    return Align(
      alignment: owner ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        key: ValueKey('office-line-$i-${l.speaker.name}'),
        margin: const EdgeInsets.only(top: 6),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        constraints: const BoxConstraints(maxWidth: 320),
        decoration: BoxDecoration(
          color: owner ? colors.accentSoft : colors.surface,
          borderRadius: BorderRadius.circular(UriRadius.sm),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(l.target, style: TextStyle(fontSize: 11, color: colors.inkFaint)),
          Text(l.speaker == OfficeSpeaker.uri ? 'URI: ${l.text}' : l.text,
              style: TextStyle(color: l.speaker == OfficeSpeaker.notice ? colors.warning : colors.ink)),
          if (chips.isNotEmpty)
            Wrap(spacing: 6, runSpacing: 4, children: [
              for (final ch in chips)
                InputChip(
                  key: ValueKey('office-chip-${ch.$2}'),
                  label: Text(ch.$1),
                  onPressed: c.busy ? null : () => c.chip(ch.$2),
                  onDeleted: () => c.conversation.dismissChip('$i:${ch.$2}'),
                  deleteButtonTooltipMessage: 'Dismiss',
                ),
            ]),
        ]),
      ),
    );
  }
}

/// A request box for the workspace when it is shown without the living scope (tests, the live harness).
class _PlainComposer extends StatefulWidget {
  const _PlainComposer({required this.controller, this.focus});
  final OfficeWorkspaceController controller;
  final FocusNode? focus;

  @override
  State<_PlainComposer> createState() => _PlainComposerState();
}

class _PlainComposerState extends State<_PlainComposer> {
  final _t = TextEditingController();

  @override
  void dispose() {
    _t.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _t.text.trim();
    if (text.isEmpty || widget.controller.busy) return;
    _t.clear();
    await widget.controller.instruct(text);
  }

  @override
  Widget build(BuildContext context) => Row(children: [
        Expanded(
          child: TextField(
            key: const ValueKey('office-request'),
            controller: _t,
            focusNode: widget.focus,
            minLines: 1,
            maxLines: 4,
            decoration: const InputDecoration(hintText: 'Ask URI Office'),
            onSubmitted: (_) => _send(),
          ),
        ),
        IconButton(key: const ValueKey('office-request-send'), tooltip: 'Send to URI', onPressed: _send,
            icon: const Icon(Icons.arrow_upward_rounded)),
      ]);
}
