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
          // Authoring (A/B, AB-10): a new presentation, blank or from the owner's presentation or template.
          if (environment?.pickPresentationSavePath != null) ...[
            ActionChip(key: const ValueKey('office-home-new-presentation'),
                avatar: const Icon(Icons.slideshow_rounded, size: 18), label: const Text('New presentation'),
                onPressed: c.busy ? null : () => c.newPresentation()),
            if (environment?.pickTemplatePath != null)
              ActionChip(key: const ValueKey('office-home-new-from-template'),
                  avatar: const Icon(Icons.dashboard_customize_outlined, size: 18),
                  label: const Text('New from a template'),
                  onPressed: c.busy ? null : () => c.newPresentation(fromTemplate: true)),
          ],
          for (final (g, caps) in c.availableGroups())
            for (final cap in caps)
              if (cap['id'] != 'open_workbook')
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
      subtitle: Text(path, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11)),
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
