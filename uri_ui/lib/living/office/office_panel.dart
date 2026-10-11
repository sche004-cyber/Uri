import 'dart:async';

import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../a2ui/a2ui_view.dart';
import '../widgets/glass_panel.dart';
import 'office_bridge.dart';
import 'office_client.dart';
import 'office_controller.dart';

/// The Office region of the Workspace: open a workbook (file picker or Google Sheets link), co-edit it in the
/// sheet view, ask URI for changes, accept or reject each URI change, then approve saving through the service's
/// hash-bound approval card. The workbook is never written without that approval.
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
    final c = OfficeController(client: client, surface: surface);
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
  }

  @override
  void dispose() {
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
                    if (open) ...[
                      const SizedBox(width: 12),
                      SizedBox(width: 340, child: _side(context, c)),
                    ],
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

  Widget _side(BuildContext context, OfficeController c) {
    final env = widget.environment!;
    final colors = UriColors.of(context);
    final google = c.view?['engine'] == 'google';
    return GlassPanel(
      child: ListView(
        children: [
          TextField(
            key: const ValueKey('office-ask'),
            controller: _ask,
            minLines: 1,
            maxLines: 4,
            decoration: const InputDecoration(hintText: 'Ask URI to change the sheet'),
          ),
          const SizedBox(height: 6),
          FilledButton(
            key: const ValueKey('office-ask-send'),
            onPressed: c.busy ? null : () => c.instruct(_ask.text.trim()),
            child: Text(c.busy ? 'Working...' : 'Ask URI'),
          ),
          if (c.brainMessage != null && c.brainMessage!.isNotEmpty)
            Padding(padding: const EdgeInsets.only(top: 8), child: Text(c.brainMessage!)),
          const Divider(height: 24),
          Text('URI\'s suggested changes (${c.proposed.length})', style: const TextStyle(fontWeight: FontWeight.w600)),
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
          for (final s in c.hub.placed('workspace'))
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: A2uiSurfaceView(hub: c.hub, surfaceId: s.id),
            ),
          const Divider(height: 24),
          SwitchListTile(
            key: const ValueKey('office-history-consent'),
            contentPadding: EdgeInsets.zero,
            title: const Text('Keep a correction history for this workbook'),
            subtitle: const Text('What changed and why, never cell values. Off unless you turn it on.'),
            value: c.view?['history_on'] == true,
            onChanged: c.busy ? null : c.setHistory,
          ),
        ],
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
