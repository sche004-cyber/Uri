import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../widgets/status_badge.dart';
import 'document_controller.dart';

/// The print panel (O2P, A1 §A4): printer, pages, copies, paper, orientation, two-sided, colour and fit, each offered
/// only when the printer reports it; a preview of exactly the pages to be printed; then the print card in the URI pane.
/// Nothing is printed without that card.
class OfficePrintView extends StatefulWidget {
  const OfficePrintView({super.key, required this.controller});
  final OfficeWorkspaceController controller;

  @override
  State<OfficePrintView> createState() => _OfficePrintViewState();
}

class _OfficePrintViewState extends State<OfficePrintView> {
  final _pages = TextEditingController();

  @override
  void dispose() {
    _pages.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    final colors = UriColors.of(context);
    final p = c.selectedPrinter;
    final caps = (p?['capabilities'] as Map?)?.cast<String, dynamic>() ?? const {};
    final papers = [for (final x in (caps['papers'] as List? ?? const [])) '${(x as Map)['name']}'];
    final s = c.printSettings;
    final total = c.documents[c.activeDocument]?.pages ?? 0;
    final pagesValid = c.printPages == 'all' || OfficeWorkspaceController.parsePages(c.printPages, total) != null;
    final job = c.printJobView;
    return ListView(key: const ValueKey('office-print'), padding: const EdgeInsets.all(UriSpace.md), children: [
      Text('Print', style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: UriSpace.sm),
      if (c.printers.isEmpty)
        Text('No printer is installed.', key: const ValueKey('office-no-printer'),
            style: TextStyle(color: colors.warning))
      else
        DropdownButton<String>(
          key: const ValueKey('office-printer'),
          value: c.printerId,
          isExpanded: true,
          items: [
            for (final pr in c.printers)
              DropdownMenuItem(
                value: '${pr['id']}',
                child: Text(
                  '${pr['name']}${pr['is_default'] == true ? ' (default)' : ''}'
                  '${pr['connection'] == 'virtual' ? ' · virtual' : ''}'
                  '${pr['connection'] == 'network' ? ' · network' : ''}'
                  '${pr['status'] == 'ready' ? '' : ' · ${pr['status']}'}${pr['new'] == true ? ' · New' : ''}',
                  overflow: TextOverflow.ellipsis,
                ),
              ),
          ],
          onChanged: c.busy ? null : (v) => v == null ? null : c.choosePrinter(v),
        ),
      if (c.printers.isNotEmpty && !c.physicalPrinter)
        Padding(
          padding: const EdgeInsets.only(top: UriSpace.xs),
          child: Text('No physical printer found. Only virtual printers (they write files) are installed.',
              key: const ValueKey('office-no-physical'), style: TextStyle(color: colors.inkSoft)),
        ),
      if (p != null && p['status'] != 'ready')
        Text('${p['status_detail'] ?? 'The printer is not ready.'}', key: const ValueKey('office-printer-status'),
            style: TextStyle(color: colors.warning)),
      const SizedBox(height: UriSpace.sm),
      Wrap(spacing: UriSpace.md, runSpacing: UriSpace.sm, crossAxisAlignment: WrapCrossAlignment.center, children: [
        SizedBox(
          width: 180,
          child: TextField(
            key: const ValueKey('office-print-pages'),
            controller: _pages,
            decoration: InputDecoration(isDense: true, labelText: 'Pages (all, or 1-3, 5)',
                errorText: pagesValid ? null : 'Pages 1 to $total'),
            onChanged: c.setPrintPages,
          ),
        ),
        if (((caps['max_copies'] as int?) ?? 1) > 1)
          DropdownButton<int>(
            key: const ValueKey('office-print-copies'),
            value: s['copies'] as int,
            items: [for (var i = 1; i <= ((caps['max_copies'] as int).clamp(1, 20)); i++)
                DropdownMenuItem(value: i, child: Text('$i ${i == 1 ? 'copy' : 'copies'}'))],
            onChanged: (v) => c.setPrintSetting('copies', v ?? 1),
          ),
        if (papers.isNotEmpty)
          DropdownButton<String>(
            key: const ValueKey('office-print-paper'),
            value: papers.contains(s['paper']) ? s['paper'] as String : papers.first,
            items: [for (final n in papers) DropdownMenuItem(value: n, child: Text(n))],
            onChanged: (v) => c.setPrintSetting('paper', v ?? papers.first),
          ),
        SegmentedButton<bool>(
          key: const ValueKey('office-print-orientation'),
          showSelectedIcon: false,
          segments: const [ButtonSegment(value: false, label: Text('Portrait')),
                           ButtonSegment(value: true, label: Text('Landscape'))],
          selected: {s['landscape'] == true},
          onSelectionChanged: (v) => c.setPrintSetting('landscape', v.first),
        ),
        if (caps['duplex'] == true)
          DropdownButton<String>(
            key: const ValueKey('office-print-duplex'),
            value: s['duplex'] as String,
            items: const [
              DropdownMenuItem(value: 'simplex', child: Text('One-sided')),
              DropdownMenuItem(value: 'long', child: Text('Two-sided, long edge')),
              DropdownMenuItem(value: 'short', child: Text('Two-sided, short edge')),
            ],
            onChanged: (v) => c.setPrintSetting('duplex', v ?? 'simplex'),
          ),
        if (caps['color'] == true)
          SegmentedButton<bool>(
            key: const ValueKey('office-print-colour'),
            showSelectedIcon: false,
            segments: const [ButtonSegment(value: true, label: Text('Colour')),
                             ButtonSegment(value: false, label: Text('Black and white'))],
            selected: {s['color'] == true},
            onSelectionChanged: (v) => c.setPrintSetting('color', v.first),
          ),
        SegmentedButton<String>(
          key: const ValueKey('office-print-fit'),
          showSelectedIcon: false,
          segments: const [ButtonSegment(value: 'fit', label: Text('Fit to page')),
                           ButtonSegment(value: 'actual', label: Text('Actual size'))],
          selected: {s['fit'] as String},
          onSelectionChanged: (v) => c.setPrintSetting('fit', v.first),
        ),
      ]),
      const SizedBox(height: UriSpace.md),
      Wrap(spacing: 8, children: [
        OutlinedButton(key: const ValueKey('office-print-preview'),
            onPressed: c.busy || p == null || !pagesValid ? null : c.previewPrint, child: const Text('Preview')),
        FilledButton.icon(
          key: const ValueKey('office-print-propose'),
          onPressed: c.busy || p == null || !pagesValid || p['status'] != 'ready' ? null : c.proposePrint,
          icon: const Icon(Icons.print_outlined, size: 18),
          label: const Text('Print…'),
        ),
        if (job != null && const {'waiting_approval', 'queued', 'printing', 'sent'}.contains(job['state']))
          TextButton(key: const ValueKey('office-print-cancel'), onPressed: c.busy ? null : c.cancelPrint,
              child: const Text('Cancel print')),
      ]),
      if (c.printPreviewResult != null) ..._preview(context, c, c.printPreviewResult!),
      if (job != null)
        Padding(
          padding: const EdgeInsets.only(top: UriSpace.sm),
          child: Text(_jobText(job), key: const ValueKey('office-print-job')),
        ),
      const SizedBox(height: UriSpace.lg),
      ConnectPrinterCard(controller: c),
    ]);
  }

  List<Widget> _preview(BuildContext context, OfficeWorkspaceController c, Map<String, dynamic> pv) {
    final colors = UriColors.of(context);
    final pages = [for (final n in (pv['pages'] as List? ?? const [])) n as int];
    final area = (pv['printable_area'] as Map?) ?? const {};
    return [
      const SizedBox(height: UriSpace.sm),
      Eyebrow('Preview: ${pages.length} page(s)'),
      if (area['printable_mm'] is List)
        Text('Printable area ${(area['printable_mm'] as List)[2]} × ${(area['printable_mm'] as List)[3]} mm on '
            '${(area['paper_mm'] as List?)?.join(' × ')} mm paper',
            style: TextStyle(color: colors.inkSoft, fontSize: 12)),
      for (final w in (pv['warnings'] as List? ?? const [])) Text('$w', style: TextStyle(color: colors.warning)),
      SizedBox(
        height: 230,
        child: ListView(scrollDirection: Axis.horizontal, children: [
          if (c.activeDocument != null)
            for (final n in pages.take(12))
              Padding(
                padding: const EdgeInsets.all(6),
                child: FutureBuilder(
                  future: c.pageImage(c.activeDocument!, n, 160),
                  builder: (context, snap) => snap.data == null
                      ? const SizedBox(width: 160, child: Center(child: CircularProgressIndicator(strokeWidth: 2)))
                      : Image.memory(snap.data!, width: 160),
                ),
              ),
        ]),
      ),
    ];
  }

  static String _jobText(Map<String, dynamic> j) => switch (j['state']) {
        'waiting_approval' => 'Waiting for you to approve the print card.',
        'queued' => 'Queued.',
        'printing' => 'Sending pages to Windows… (${(j['events'] as List?)?.length ?? 0} done)',
        'sent' => j['output_written'] == true
            ? 'Done: the printer wrote the file.'
            : (j['spooler'] == null ? 'Sent; status unavailable.' : 'Sent to the printer.'),
        'printer_problem' => 'The printer reported a problem. Check the printer, then try again.',
        'cancelled' => 'Cancelled.',
        'declined' => 'Not printed.',
        'failed' => 'Printing failed: ${j['error'] ?? ''}.',
        _ => '${j['state']}',
      };
}

/// "Connect a printer" (A1 §A6 onboarding): steps, the Windows Settings hand-off after an explicit click, and Check
/// again. URI never installs a driver, adds a printer or changes the default.
class ConnectPrinterCard extends StatelessWidget {
  const ConnectPrinterCard({super.key, required this.controller});
  final OfficeWorkspaceController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final colors = UriColors.of(context);
    return Container(
      key: const ValueKey('office-connect-printer'),
      padding: const EdgeInsets.all(UriSpace.md),
      decoration: BoxDecoration(border: Border.all(color: colors.border), borderRadius: BorderRadius.circular(UriRadius.sm)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text('Connect a printer', style: Theme.of(context).textTheme.titleSmall),
        const SizedBox(height: UriSpace.xs),
        const Text('1. Turn the printer on.'),
        const Text('2. Connect it with a USB cable, or to the same network as this PC.'),
        const Text('3. Add it in Windows. Windows finds it and installs what it needs, with its own prompts.'),
        const Text('4. Come back here and press Check again.'),
        const SizedBox(height: UriSpace.sm),
        Wrap(spacing: 8, children: [
          if (c.environment?.openPrinterSettings != null)
            OutlinedButton.icon(key: const ValueKey('office-open-printer-settings'),
                onPressed: c.openPrinterSettings, icon: const Icon(Icons.open_in_new_rounded, size: 18),
                label: const Text('Open Windows Printers & scanners')),
          TextButton(key: const ValueKey('office-printers-check-again'),
              onPressed: () => c.loadPrinters(refresh: true), child: const Text('Check again')),
        ]),
        Text('URI does not install drivers, add printers or change your default printer.',
            style: TextStyle(color: colors.inkSoft, fontSize: 12)),
      ]),
    );
  }
}

/// Devices › Printers (A1 §A6): every printer Windows has, with its connection, status, default and New badges.
class OfficePrintersView extends StatelessWidget {
  const OfficePrintersView({super.key, required this.controller});
  final OfficeWorkspaceController controller;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final colors = UriColors.of(context);
    return ListView(key: const ValueKey('office-printers'), padding: const EdgeInsets.all(UriSpace.md), children: [
      Text('Printers', style: Theme.of(context).textTheme.titleLarge),
      if (c.printers.isEmpty) Text('No printer is installed.', style: TextStyle(color: colors.inkSoft)),
      if (c.printers.isNotEmpty && !c.physicalPrinter)
        Text('No physical printer found.', key: const ValueKey('office-no-physical-list'),
            style: TextStyle(color: colors.inkSoft)),
      for (final p in c.printers)
        ListTile(
          key: ValueKey('office-printer-${p['id']}'),
          leading: Icon(p['connection'] == 'virtual' ? Icons.picture_as_pdf_outlined : Icons.print_outlined),
          title: Text('${p['name']}', overflow: TextOverflow.ellipsis),
          subtitle: Text([
            '${p['connection']}',
            '${p['status']}',
            if (p['is_default'] == true) 'default',
            if (p['new'] == true) 'New',
          ].join(' · ')),
        ),
      const SizedBox(height: UriSpace.md),
      ConnectPrinterCard(controller: c),
    ]);
  }
}
