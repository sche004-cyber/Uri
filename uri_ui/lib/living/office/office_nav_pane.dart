import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../presentation/presentation_controller.dart';
import '../widgets/status_badge.dart';
import 'document_controller.dart';
import 'office_bridge.dart';

/// The B1 left pane: Home and Recent, goal groups built from the capability registry (only available capabilities,
/// empty groups hidden: U4), files by kind (from the recent list; no folder crawling), and tasks. In compact mode
/// (1000–1279 px, or collapsed) it is a 56 px icon strip.
class OfficeNavPane extends StatelessWidget {
  const OfficeNavPane({super.key, required this.controller, required this.compact, this.environment,
      required this.onOpenSheet});
  final OfficeWorkspaceController controller;
  final bool compact;
  final OfficeEnvironment? environment;
  final VoidCallback onOpenSheet;

  static const _views = [
    (OfficeView.home, Icons.home_outlined, 'Home'),
    (OfficeView.recent, Icons.history_rounded, 'Recent'),
    (OfficeView.documents, Icons.description_outlined, 'Documents'),
    (OfficeView.spreadsheets, Icons.table_chart_outlined, 'Spreadsheets'),
    (OfficeView.presentations, Icons.slideshow_outlined, 'Presentations'),
    (OfficeView.pdfs, Icons.picture_as_pdf_outlined, 'PDFs'),
    (OfficeView.workflows, Icons.playlist_play_rounded, 'Tasks'),
  ];

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final colors = UriColors.of(context);
    if (compact) {
      return Material(
        key: const ValueKey('office-nav-compact'),
        color: colors.surfaceSunken,
        child: ListView(children: [
          for (final (v, icon, label) in _views)
            IconButton(
              key: ValueKey('office-nav-${v.name}'),
              tooltip: label,
              isSelected: c.view == v && (c.centre == OfficeCentre.home || c.centre == OfficeCentre.list),
              onPressed: () => c.showView(v),
              icon: Icon(icon, size: 20),
            ),
          if (environment?.pickDocumentPath != null)
            IconButton(key: const ValueKey('office-nav-open'), tooltip: 'Open a document',
                onPressed: c.busy ? null : c.pickAndOpenDocument, icon: const Icon(Icons.folder_open_rounded)),
          IconButton(key: const ValueKey('office-nav-sheet'), tooltip: 'Spreadsheet view', onPressed: onOpenSheet,
              icon: const Icon(Icons.grid_on_rounded)),
        ]),
      );
    }
    final groups = c.availableGroups();
    return Material(
      key: const ValueKey('office-nav'),
      color: colors.surfaceSunken,
      child: ListView(padding: const EdgeInsets.all(UriSpace.sm), children: [
        Wrap(spacing: 6, runSpacing: 6, children: [
          if (environment?.pickDocumentPath != null)
            FilledButton.icon(
              key: const ValueKey('office-open-document'),
              onPressed: c.busy ? null : c.pickAndOpenDocument,
              icon: const Icon(Icons.folder_open_rounded, size: 18),
              label: const Text('Open'),
            ),
          OutlinedButton.icon(
            key: const ValueKey('office-open-sheet-view'),
            onPressed: onOpenSheet,
            icon: const Icon(Icons.grid_on_rounded, size: 18),
            label: const Text('Spreadsheet'),
          ),
        ]),
        const SizedBox(height: UriSpace.sm),
        for (final (v, icon, label) in _views)
          ListTile(
            key: ValueKey('office-nav-${v.name}'),
            dense: true,
            leading: Icon(icon, size: 18),
            title: Text(label),
            selected: c.view == v && (c.centre == OfficeCentre.home || c.centre == OfficeCentre.list),
            onTap: () => c.showView(v),
          ),
        if (groups.isNotEmpty) ...[
          const SizedBox(height: UriSpace.sm),
          const Eyebrow('Goals'),
          for (final (g, caps) in groups) ...[
            Padding(
              padding: const EdgeInsets.only(top: UriSpace.xs),
              child: Text('${g['title']}', key: ValueKey('office-goal-${g['id']}'),
                  style: TextStyle(color: colors.inkSoft, fontSize: 12, fontWeight: FontWeight.w600)),
            ),
            for (final cap in caps)
              ListTile(
                key: ValueKey('office-cap-${cap['id']}'),
                dense: true,
                visualDensity: VisualDensity.compact,
                title: Text('${cap['title']}'),
                subtitle: cap['ready'] == true
                    ? null
                    : Text(officeErrorText['${cap['unready_reason']}'] ?? 'Not ready yet.',
                        style: TextStyle(color: colors.warning, fontSize: 11)),
                onTap: c.busy ? null : () => c.chip('${cap['id']}'),
              ),
          ],
        ],
        if (c.available('print_document')) ...[
          const SizedBox(height: UriSpace.sm),
          const Eyebrow('Devices'),
          ListTile(
            key: const ValueKey('office-nav-printers'),
            dense: true,
            leading: const Icon(Icons.print_outlined, size: 18),
            title: const Text('Printers'),
            selected: c.centre == OfficeCentre.devices,
            onTap: c.showDevices,
          ),
        ],
        if (c.documents.isNotEmpty) ...[
          const SizedBox(height: UriSpace.sm),
          const Eyebrow('Open'),
          for (final d in c.documents.values)
            ListTile(
              key: ValueKey('office-open-doc-${d.id}'),
              dense: true,
              leading: Icon(d.kind == 'pdf' ? Icons.picture_as_pdf_outlined : Icons.description_outlined, size: 18),
              title: Text(d.name, overflow: TextOverflow.ellipsis),
              selected: c.activeDocument == d.id && c.centre == OfficeCentre.document,
              onTap: () => c.showDocument(d.id),
              trailing: IconButton(
                tooltip: 'Close ${d.name}',
                icon: const Icon(Icons.close_rounded, size: 16),
                onPressed: () => c.closeDocument(d.id),
              ),
            ),
        ],
      ]),
    );
  }
}
