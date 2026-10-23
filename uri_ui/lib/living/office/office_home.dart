import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../presentation/presentation_controller.dart';
import '../widgets/status_badge.dart';
import 'document_controller.dart';
import 'office_bridge.dart';

/// Office Home (plan §4.3): what URI can do now (goal chips from the registry), recent work and running tasks.
/// The request box is the companion composer in the right pane.
class OfficeHome extends StatelessWidget {
  const OfficeHome({super.key, required this.controller, this.environment, required this.onOpenSheet});
  final OfficeWorkspaceController controller;
  final OfficeEnvironment? environment;
  final VoidCallback onOpenSheet;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final colors = UriColors.of(context);
    final running = [for (final w in (c.workflows['running'] as List? ?? const [])) (w as Map).cast<String, dynamic>()];
    return ListView(
      key: const ValueKey('office-home'),
      padding: const EdgeInsets.all(UriSpace.lg),
      children: [
        Text('What do you need?', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: UriSpace.xs),
        Text('Ask URI on the right, pick a task, or open a file. URI shows a plan before it changes anything.',
            style: TextStyle(color: colors.inkSoft)),
        const SizedBox(height: UriSpace.md),
        Wrap(spacing: 8, runSpacing: 8, children: [
          if (environment?.pickDocumentPath != null)
            ActionChip(key: const ValueKey('office-home-open'), avatar: const Icon(Icons.folder_open_rounded, size: 18),
                label: const Text('Open a Word, PowerPoint or PDF file'), onPressed: c.busy ? null : c.pickAndOpenDocument),
          ActionChip(key: const ValueKey('office-home-sheet'), avatar: const Icon(Icons.grid_on_rounded, size: 18),
              label: const Text('Work on a spreadsheet'), onPressed: onOpenSheet),
          // Authoring (C): a new Word document from a built-in layout or the owner's template.
          // Live run a9 (first visit): the layouts were not loaded yet, so a first-time owner saw no way to start a
          // Word document. The chip is always there; until the service lists its layouts it offers a blank one.
          if (environment?.pickDocumentSavePath != null)
            PopupMenuButton<String>(
              key: const ValueKey('office-home-new-document'),
              tooltip: 'New Word document',
              enabled: !c.busy,
              itemBuilder: (_) => [
                for (final l in (c.wordLayouts.isNotEmpty ? c.wordLayouts : const [{'id': 'blank',
                    'title': 'Blank document'}]))
                  PopupMenuItem(value: '${l['id']}', child: Text('${l['title']}', key: ValueKey('office-layout-${l['id']}'))),
                if (environment?.pickWordTemplatePath != null)
                  const PopupMenuItem(value: '@template', child: Text('From my template…',
                      key: ValueKey('office-layout-template'))),
              ],
              onSelected: (v) => v == '@template'
                  ? c.newWordDocument(fromTemplate: true)
                  : c.newWordDocument(layout: v),
              child: const Chip(avatar: Icon(Icons.note_add_outlined, size: 18), label: Text('New document')),
            ),
          // OD-2 (plan 16): URI drafts a Word document from the owner's instruction.
          if (c.available('write_document'))
            Tooltip(
              // the service says BRAIN_UNAVAILABLE when no Brain is connected
              message: c.ready('write_document')
                  ? ''
                  : (officeErrorText['${c.capabilityList.where((x) => x['id'] == 'write_document').firstOrNull?['unready_reason']}'] ??
                      'Not ready yet.'),
              child: ActionChip(key: const ValueKey('office-home-draft'),
                  avatar: const Icon(Icons.edit_note_rounded, size: 18), label: const Text('Draft with URI…'),
                  onPressed: c.busy || c.editor != null || !c.ready('write_document')
                      ? null
                      : () => showDraftDialog(context, c)),
            ),
          // Authoring (A/B, AB-10): a new presentation, blank or from the owner's presentation or template.
          if (environment?.pickPresentationSavePath != null) ...[
            ActionChip(key: const ValueKey('office-home-new-presentation'),
                avatar: const Icon(Icons.slideshow_rounded, size: 18), label: const Text('New presentation'),
                onPressed: c.busy ? null : () => c.newPresentation()),
            if (environment?.pickTemplatePath != null)
              ActionChip(key: const ValueKey('office-home-new-from-template'),
                  avatar: const Icon(Icons.dashboard_customize_outlined, size: 18),
                  label: const Text('New presentation from a template'),
                  onPressed: c.busy ? null : () => c.newPresentation(fromTemplate: true)),
          ],
          for (final (g, caps) in c.availableGroups())
            for (final cap in caps)
              if (cap['id'] != 'open_workbook' && cap['id'] != 'write_document')   // drafting: the chip above
                Tooltip(
                  // Real-app run 2026-10-15: a greyed-out goal gave no reason.
                  message: cap['ready'] == true
                      ? ''
                      : (cap['id'] == 'save_as_pdf'
                          ? (c.saveAsPdfBlockedReason ?? '')
                          : (officeErrorText['${cap['unready_reason']}'] ?? 'Not ready yet.')),
                  child: ActionChip(
                    key: ValueKey('office-home-cap-${cap['id']}'),
                    label: Text('${g['title']}: ${cap['title']}'),
                    onPressed: c.busy || cap['ready'] != true ? null : () => c.chip('${cap['id']}'),
                  ),
                ),
        ]),
        const SizedBox(height: UriSpace.lg),
        if (running.isNotEmpty) ...[
          const Eyebrow('Running'),
          for (final w in running)
            ListTile(
              key: ValueKey('office-home-wf-${w['workflow_id']}'),
              leading: const Icon(Icons.playlist_play_rounded),
              title: Text(_capTitle(c, '${w['capability']}')),
              subtitle: Text('${w['state']}'),
              onTap: () => c.showWorkflow('${w['workflow_id']}'),
            ),
        ],
        const Eyebrow('Recent'),
        if (c.recent.isEmpty)
          Padding(padding: const EdgeInsets.symmetric(vertical: UriSpace.sm),
              child: Text('Nothing opened yet.', style: TextStyle(color: colors.inkSoft))),
        for (final r in c.recent.take(8)) _RecentTile(controller: c, item: r, onOpenSheet: onOpenSheet),
      ],
    );
  }

  static String _capTitle(OfficeWorkspaceController c, String id) =>
      '${c.capabilityList.where((x) => x['id'] == id).firstOrNull?['title'] ?? id}';
}

/// OD-2: what to write and, optionally, which kind of document. The kind is otherwise taken from the words
/// ("office order", "note sheet", ...); with neither, URI asks.
Future<void> showDraftDialog(BuildContext context, OfficeWorkspaceController c) async {
  final layouts = [for (final l in c.wordLayouts) if (l['id'] != 'blank') l];
  final got = await showDialog<(String, String?)>(context: context, builder: (_) => _DraftDialog(layouts: layouts));
  if (got != null && got.$1.trim().isNotEmpty) await c.draftWordDocument(got.$1, layout: got.$2);
}

class _DraftDialog extends StatefulWidget {
  const _DraftDialog({required this.layouts});
  final List<Map<String, dynamic>> layouts;

  @override
  State<_DraftDialog> createState() => _DraftDialogState();
}

class _DraftDialogState extends State<_DraftDialog> {
  final _text = TextEditingController();
  String? _layout;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      key: const ValueKey('office-draft-dialog'),
      title: const Text('Draft with URI'),
      content: SizedBox(
        width: 520,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          TextField(
            key: const ValueKey('office-draft-instruction'),
            controller: _text,
            autofocus: true,
            minLines: 3,
            maxLines: 8,
            maxLength: 2000,
            decoration: const InputDecoration(
                hintText: 'For example: write an office order transferring Shri A. Kumar, Section Officer, to the '
                    'Accounts Section from 1 November'),
          ),
          const SizedBox(height: UriSpace.sm),
          DropdownButton<String?>(
            key: const ValueKey('office-draft-layout'),
            value: _layout,
            isExpanded: true,
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('Kind of document: from my words')),
              for (final l in widget.layouts)
                DropdownMenuItem<String?>(value: '${l['id']}', child: Text('${l['title']}')),
            ],
            onChanged: (v) => setState(() => _layout = v),
          ),
          Text('URI writes a draft for you to read and change. Nothing is saved until you approve Save as.',
              style: TextStyle(color: UriColors.of(context).inkSoft, fontSize: UriType.caption)),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
        FilledButton(key: const ValueKey('office-draft-go'),
            onPressed: () => Navigator.pop(context, (_text.text, _layout)), child: const Text('Draft')),
      ],
    );
  }
}

/// A list view of the Office region (Recent, Documents, Spreadsheets, Presentations, PDFs, Tasks, Templates).
/// Files come from the recent list only; opening one goes through the picker again (a recent entry is not a grant).
class OfficeFileList extends StatelessWidget {
  const OfficeFileList({super.key, required this.controller, this.environment, required this.onOpenSheet});
  final OfficeWorkspaceController controller;
  final OfficeEnvironment? environment;
  final VoidCallback onOpenSheet;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final colors = UriColors.of(context);
    final v = c.view;
    if (v == OfficeView.workflows) {
      final all = [
        for (final w in (c.workflows['running'] as List? ?? const [])) (w as Map).cast<String, dynamic>(),
        for (final w in (c.workflows['done'] as List? ?? const [])) (w as Map).cast<String, dynamic>(),
      ];
      return ListView(key: const ValueKey('office-list-workflows'), padding: const EdgeInsets.all(UriSpace.md),
          children: [
        if (all.isEmpty) Text('No tasks yet.', style: TextStyle(color: colors.inkSoft)),
        for (final w in all)
          ListTile(
            key: ValueKey('office-wf-${w['workflow_id']}'),
            leading: const Icon(Icons.playlist_play_rounded),
            title: Text(OfficeHome._capTitle(c, '${w['capability']}')),
            subtitle: Text('${w['state']}'),
            onTap: () => c.showWorkflow('${w['workflow_id']}'),
          ),
      ]);
    }
    if (v == OfficeView.templates) {
      return Center(child: Text('Templates arrive with Word documents (planned for O3).',
          key: const ValueKey('office-list-templates'), style: TextStyle(color: colors.inkSoft)));
    }
    final kinds = switch (v) {
      OfficeView.documents => {'docx'},
      OfficeView.spreadsheets => {'xlsx'},
      OfficeView.presentations => {'pptx'},
      OfficeView.pdfs => {'pdf'},
      _ => {'docx', 'xlsx', 'pptx', 'pdf'},
    };
    final items = [for (final r in c.recent) if (kinds.contains(r['kind'])) r];
    return ListView(key: ValueKey('office-list-${v.name}'), padding: const EdgeInsets.all(UriSpace.md), children: [
      Row(children: [
        Expanded(child: Text('Files you opened recently', style: TextStyle(color: colors.inkSoft))),
        if (c.recent.isNotEmpty)
          TextButton(key: const ValueKey('office-recent-clear'), onPressed: () async {
            await c.client.recentClear();
            await c.refresh();
          }, child: const Text('Clear list')),
      ]),
      if (items.isEmpty)
        Padding(padding: const EdgeInsets.symmetric(vertical: UriSpace.md),
            child: Text('Nothing here yet.', style: TextStyle(color: colors.inkSoft))),
      for (final r in items) _RecentTile(controller: c, item: r, onOpenSheet: onOpenSheet),
    ]);
  }
}

class _RecentTile extends StatelessWidget {
  const _RecentTile({required this.controller, required this.item, required this.onOpenSheet});
  final OfficeWorkspaceController controller;
  final Map<String, dynamic> item;
  final VoidCallback onOpenSheet;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final path = '${item['path']}';
    final name = path.split(RegExp(r'[\\/]')).last;
    final kind = '${item['kind']}';
    return ListTile(
      key: ValueKey('office-recent-$name'),
      dense: true,
      leading: Icon(switch (kind) {
        'pdf' => Icons.picture_as_pdf_outlined,
        'xlsx' => Icons.table_chart_outlined,
        'pptx' => Icons.slideshow_outlined,
        _ => Icons.description_outlined,
      }, size: 18),
      title: Text(name, overflow: TextOverflow.ellipsis),
      subtitle: Text(path, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: UriType.caption)),
      // A recent entry is not a grant: opening it asks the picker again (plan §5 recent.py).
      onTap: kind == 'xlsx' ? onOpenSheet : (c.busy ? null : c.pickAndOpenDocument),
      trailing: IconButton(
        tooltip: 'Remove from the list',
        icon: const Icon(Icons.close_rounded, size: 16),
        onPressed: () async {
          await c.client.recentRemove(path);
          await c.refresh();
        },
      ),
    );
  }
}
