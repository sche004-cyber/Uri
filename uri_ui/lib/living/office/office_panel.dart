import 'dart:async';

import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../a2ui/a2ui_view.dart';
import '../living_scope.dart';
import '../widgets/glass_panel.dart';
import '../widgets/living_composer.dart';
import 'office_bridge.dart';
import 'office_client.dart';
import 'office_controller.dart';

/// The Office region of the Workspace: open a workbook (file picker or Google Sheets link), co-edit it in the
/// sheet view, ask URI for changes, accept or reject each URI change, then approve saving through the service's
/// hash-bound approval card. The workbook is never written without that approval.
///
/// The right pane is the URI companion for the open workbook: the owner's requests (typed in the companion composer
/// or spoken with push-to-talk), URI's replies, URI's suggested changes with Accept and Reject, and the approval
/// card. While this region shows an open workbook, the companion's requests go to it (see
/// [LivingServices.activeOfficeTarget]); elsewhere they go to the ordinary conversation.
class OfficeRegion extends StatefulWidget {
  const OfficeRegion({super.key, required this.environment, this.clientFactory = OfficeClient.discover});

  /// Null when the platform cannot host the sheet view (no WebView2); the region says so.
  final OfficeEnvironment? environment;
  final OfficeClient? Function() clientFactory;

  @override
  State<OfficeRegion> createState() => _OfficeRegionState();
}

class _OfficeRegionState extends State<OfficeRegion> {
  OfficeController? _c;
  String? _startError;
  final _ask = TextEditingController();
  final _link = TextEditingController();
  ValueNotifier<OfficeRequestTarget?>? _target;   // the living scope's Office target, when there is a scope

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final target = LivingScope.maybeOf(context)?.officeTarget;
    if (!identical(target, _target)) {
      _release();
      _target = target;
      _claim();
    }
  }

  void _claim() {
    final c = _c;
    if (c != null && _target != null) _target!.value = c;
  }

  void _release() {
    final t = _target;
    if (t != null && _c != null && identical(t.value, _c)) t.value = null;
  }

  @override
  void initState() {
    super.initState();
    unawaited(_start());
  }

  Future<void> _start() async {
    final env = widget.environment;
    if (env == null) {
      setState(() => _startError = 'The sheet view needs the Windows WebView2 runtime, which is not available here.');
      return;
    }
    final client = widget.clientFactory();
    if (client == null) {
      setState(() => _startError = 'The URI Office service is not running. Start URI Office, then open this again.');
      return;
    }
    final surface = env.surfaceFactory();
    // Read without registering a dependency: this runs from initState.
    final keep = context.getInheritedWidgetOfExactType<LivingScope>()?.services.officeKeep;
    final c = OfficeController(client: client, surface: surface, keep: keep);
    try {
      await surface.start();
    } catch (e) {
      c.dispose();
      if (mounted) setState(() => _startError = 'The sheet view could not start safely: $e');
      return;
    }
    if (!mounted) {
      c.dispose();
      return;
    }
    setState(() => _c = c);
    _claim();
    await c.resume();                    // the workbook kept while the owner was away from Office (R1-02)
  }

  @override
  void dispose() {
    _release();
    _c?.dispose();
    _ask.dispose();
    _link.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = UriColors.of(context);
    final c = _c;
    if (_startError != null) {
      return Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(_startError!, key: const ValueKey('office-start-error'))));
    }
    if (c == null) return const Center(child: CircularProgressIndicator());
    return ListenableBuilder(
      listenable: Listenable.merge([c, c.hub]),
      builder: (context, _) {
        final open = c.workbookId != null;
        return Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _toolbar(context, c, open),
              if (c.notice != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(c.notice!, key: const ValueKey('office-notice'), style: TextStyle(color: colors.warning)),
                ),
              const SizedBox(height: 8),
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: c.surface.build(context),
                      ),
                    ),
                    const SizedBox(width: 12),
                    SizedBox(width: 380, child: _companion(context, c, open)),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _toolbar(BuildContext context, OfficeController c, bool open) {
    final env = widget.environment!;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        FilledButton.icon(
          key: const ValueKey('office-open-file'),
          onPressed: c.busy
              ? null
              : () async {
                  final path = await env.pickWorkbookPath();
                  if (path != null) await c.openLocal(path);
                },
          icon: const Icon(Icons.folder_open_rounded),
          label: const Text('Open file'),
        ),
        SizedBox(
          width: 320,
          child: TextField(
            key: const ValueKey('office-google-link'),
            controller: _link,
            decoration: const InputDecoration(isDense: true, hintText: 'Paste a Google Sheets link'),
            onSubmitted: (v) => c.openGoogle(v.trim()),
          ),
        ),
        if (open) ...[
          Text(c.view?['label'] as String? ?? '', style: const TextStyle(fontWeight: FontWeight.w600)),
          if (c.view?['engine'] == 'google' && c.view?['open_url'] is String)
            OutlinedButton(
              onPressed: () => env.openExternalLink(Uri.parse(c.view!['open_url'] as String)),
              child: const Text('Open in Google Sheets'),
            ),
        ],
      ],
    );
  }

  /// The URI companion pane for this workbook.
  Widget _companion(BuildContext context, OfficeController c, bool open) {
    final env = widget.environment!;
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
                for (final ch in c.proposed)
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
                    FilledButton(
                      key: const ValueKey('office-save'),
                      onPressed: c.busy ? null : () => c.proposeSave(),
                      child: Text(google ? 'Apply to Google Sheet' : 'Save to file'),
                    ),
                    if (!google)
                      OutlinedButton(
                        onPressed: c.busy
                            ? null
                            : () async {
                                final p = await env.pickSavePath('${c.view?['label'] ?? 'workbook'}');
                                if (p != null) await c.proposeSave(saveAsPath: p);
                              },
                        child: const Text('Save as...'),
                      ),
                    if (!google) OutlinedButton(onPressed: c.busy ? null : c.proposeShare, child: const Text('Share via Google')),
                    if (google && c.view?['writable'] != true)
                      OutlinedButton(onPressed: c.busy ? null : c.editCopy, child: const Text('Edit a copy')),
                  ]),
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
