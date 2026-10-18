import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../widgets/status_badge.dart';
import 'document_controller.dart';

/// Read-only page view for DOCX, PPTX and PDF (plan §4.3 `page_preview.dart`, A1 §A3): the selected page at the
/// chosen zoom (440 / 880 / 1240 px), a thumbnail rail, the outline, search with page jumps, and the renderer label
/// (U14). Pages keep their white paper on a canvas well in both themes.
class PagePreview extends StatefulWidget {
  const PagePreview({super.key, required this.controller});
  final OfficeWorkspaceController controller;

  @override
  State<PagePreview> createState() => _PagePreviewState();
}

class _PagePreviewState extends State<PagePreview> {
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.controller;
    final colors = UriColors.of(context);
    final d = c.documents[c.activeDocument];
    if (d == null) return const SizedBox.shrink();
    if (d.previewState == 'rendering') {
      return Center(
        key: const ValueKey('office-preview-rendering'),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          const CircularProgressIndicator(),
          const SizedBox(height: UriSpace.sm),
          Text(d.renderer == 'LibreOffice' ? 'Preparing the preview…' : 'Reading the PDF…',
              style: TextStyle(color: colors.inkSoft)),
          // Real-app run r2: the first Word preview took over 3 minutes while the engine was checked, with no word
          // about why.
          if (d.renderer == 'LibreOffice' && c.engineNotReady)
            Padding(
              padding: const EdgeInsets.only(top: UriSpace.xs),
              child: Text('First use: URI is checking the document engine. This takes about 2 minutes, once.',
                  key: const ValueKey('office-preview-first-use'), style: TextStyle(color: colors.inkSoft, fontSize: UriType.label)),
            ),
        ]),
      );
    }
    if (d.previewState != 'ready') {
      return Center(
        key: const ValueKey('office-preview-unavailable'),
        child: Padding(
          padding: const EdgeInsets.all(UriSpace.lg),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text('Preview unavailable: ${officeErrorText[d.previewReason] ?? 'the preview could not be made.'}',
                textAlign: TextAlign.center, style: TextStyle(color: colors.warning)),
            const SizedBox(height: UriSpace.sm),
            if (c.stepLabel != null) Text(c.stepLabel!, style: TextStyle(color: colors.inkSoft)),
            if (!const {'ENCRYPTED', 'ARCHIVE_REFUSED', 'XML_REFUSED', 'TOO_MANY_PAGES', 'FILE_TOO_LARGE'}
                .contains(d.previewReason))
              FilledButton(
                key: const ValueKey('office-preview-retry'),
                onPressed: c.busy ? null : () => c.retryPreview(d.id),
                child: Text(c.engineNotReady ? 'Check the engine and try again' : 'Try again'),
              ),
          ]),
        ),
      );
    }
    final pages = d.pages ?? 0;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: UriSpace.sm),
        child: Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
          Text('Page ${c.selectedPage} of $pages', key: const ValueKey('office-page-label')),
          IconButton(key: const ValueKey('office-page-prev'), tooltip: 'Previous page',
              onPressed: c.selectedPage > 1 ? () => c.selectPage(c.selectedPage - 1) : null,
              icon: const Icon(Icons.chevron_left_rounded)),
          IconButton(key: const ValueKey('office-page-next'), tooltip: 'Next page',
              onPressed: c.selectedPage < pages ? () => c.selectPage(c.selectedPage + 1) : null,
              icon: const Icon(Icons.chevron_right_rounded)),
          SegmentedButton<int>(
            key: const ValueKey('office-zoom'),
            showSelectedIcon: false,
            segments: const [
              ButtonSegment(value: 440, label: Text('Fit')),
              ButtonSegment(value: 880, label: Text('100%')),
              ButtonSegment(value: 1240, label: Text('150%')),
            ],
            selected: {c.zoomWidth},
            onSelectionChanged: (s) => c.setZoom(s.first),
          ),
          SizedBox(
            width: 220,
            child: TextField(
              key: const ValueKey('office-search'),
              controller: _search,
              decoration: const InputDecoration(isDense: true, hintText: 'Search', prefixIcon: Icon(Icons.search, size: 18)),
              onSubmitted: c.search,
            ),
          ),
          if (c.searchNotice != null) Text(c.searchNotice!, key: const ValueKey('office-search-notice')),
          Text('Preview rendered by ${d.renderer}', key: const ValueKey('office-renderer-label'),
              style: TextStyle(color: colors.inkFaint, fontSize: UriType.caption)),
        ]),
      ),
      if (c.searchMatches.isNotEmpty)
        SizedBox(
          height: 36,
          child: ListView(scrollDirection: Axis.horizontal, children: [
            for (final m in c.searchMatches)
              Padding(
                padding: const EdgeInsets.only(right: 6),
                child: ActionChip(label: Text('p. ${m['page']}'), onPressed: () => c.selectPage(m['page'] as int)),
              ),
          ]),
        ),
      Expanded(
        child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          SizedBox(width: 120, child: _rail(context, c, d)),
          Expanded(
            child: Container(
              color: colors.surfaceSunken,
              child: SingleChildScrollView(
                key: const ValueKey('office-page-scroll'),
                padding: const EdgeInsets.all(UriSpace.md),
                child: Center(child: _PageImage(controller: c, docId: d.id, page: c.selectedPage, width: c.zoomWidth,
                    key: ValueKey('office-page-${d.id}-${c.selectedPage}-${c.zoomWidth}'))),
              ),
            ),
          ),
          if (d.outline.isNotEmpty) SizedBox(width: 200, child: _outline(context, c, d)),
        ]),
      ),
    ]);
  }

  Widget _rail(BuildContext context, OfficeWorkspaceController c, OfficeDocument d) {
    final colors = UriColors.of(context);
    return ListView.builder(
      key: const ValueKey('office-thumbnails'),
      itemCount: d.pages ?? 0,
      itemBuilder: (context, i) => InkWell(
        onTap: () => c.selectPage(i + 1),
        child: Container(
          margin: const EdgeInsets.all(6),
          decoration: BoxDecoration(border: Border.all(
              color: c.selectedPage == i + 1 ? colors.accent : colors.border, width: c.selectedPage == i + 1 ? 2 : 1)),
          child: Column(children: [
            _PageImage(controller: c, docId: d.id, page: i + 1, width: 160),
            Text('${i + 1}', style: const TextStyle(fontSize: UriType.caption)),
          ]),
        ),
      ),
    );
  }

  Widget _outline(BuildContext context, OfficeWorkspaceController c, OfficeDocument d) => ListView(
        key: const ValueKey('office-outline'),
        padding: const EdgeInsets.all(UriSpace.sm),
        children: [
          const Eyebrow('Outline'),
          for (final o in d.outline)
            InkWell(
              onTap: o['page'] is int ? () => c.selectPage(o['page'] as int) : null,
              child: Padding(
                padding: EdgeInsets.only(left: 8.0 * (((o['level'] as int?) ?? 1) - 1).clamp(0, 4), top: 4, bottom: 4),
                child: Text('${o['title']}', maxLines: 2, overflow: TextOverflow.ellipsis),
              ),
            ),
        ],
      );
}

/// One page image, fetched lazily (and cached by the controller). Retries while the page is still being prepared.
class _PageImage extends StatefulWidget {
  const _PageImage({super.key, required this.controller, required this.docId, required this.page, required this.width,
      this.output = false});
  final OfficeWorkspaceController controller;
  final String docId;
  final int page;
  final int width;
  final bool output;

  @override
  State<_PageImage> createState() => _PageImageState();
}

class _PageImageState extends State<_PageImage> {
  Uint8List? _bytes;
  String? _error;
  bool _canRetry = false;

  // Codex review R4-2: the first LibreOffice / WinRT start can take minutes, so a page keeps being asked for (with a
  // growing pause) for up to three minutes before it is reported, and the owner can ask again.
  static const _patience = Duration(minutes: 3);

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final sw = Stopwatch()..start();
    var pause = 400;
    while (mounted && sw.elapsed < _patience) {
      try {
        final b = widget.output
            ? await widget.controller.outputPage(widget.docId, widget.page, widget.width)
            : await widget.controller.pageImage(widget.docId, widget.page, widget.width);
        if (b != null && b.isNotEmpty) {
          if (mounted) setState(() => _bytes = b);
          return;
        }
      } catch (e) {
        if (mounted) setState(() => _error = officeErrorMessage(e));
        return;
      }
      await Future<void>.delayed(Duration(milliseconds: pause));
      pause = (pause * 3 ~/ 2).clamp(400, 3000);
    }
    // CX-1: a page that never arrives is said, not shown as an endless spinner.
    if (mounted && _bytes == null && _error == null) {
      setState(() {
        _error = 'This page is not ready yet.';
        _canRetry = true;
      });
    }
  }

  void _retry() {
    setState(() {
      _error = null;
      _canRetry = false;
    });
    _load();
  }

  @override
  Widget build(BuildContext context) {
    final colors = UriColors.of(context);
    final w = widget.width.toDouble();
    if (_error != null) {
      return SizedBox(width: w, height: w * 1.3, child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
        Text(_error!, textAlign: TextAlign.center, style: TextStyle(color: colors.warning)),
        if (_canRetry)
          TextButton(key: ValueKey('office-page-retry-${widget.page}'), onPressed: _retry, child: const Text('Try again')),
      ])));
    }
    final b = _bytes;
    if (b == null) {
      return SizedBox(width: w, height: w * 1.3, child: const Center(child: CircularProgressIndicator(strokeWidth: 2)));
    }
    return Semantics(
      label: 'Page ${widget.page}',
      image: true,
      child: DecoratedBox(
        decoration: BoxDecoration(boxShadow: [BoxShadow(color: colors.border, blurRadius: 4)]),
        child: Image.memory(b, width: w, gaplessPlayback: true, filterQuality: FilterQuality.medium),
      ),
    );
  }
}

/// A task in the centre (plan §4.7): each step with its state and kind, the output pages, the findings, and the next
/// action (Accept warnings, Save, Cancel, Resume).
class OfficeWorkflowView extends StatelessWidget {
  const OfficeWorkflowView({super.key, required this.controller});
  final OfficeWorkspaceController controller;

  static const _labels = {
    'prepare': 'Make a safe working copy',
    'convert': 'Convert to PDF (LibreOffice)',
    'validate': 'Check the PDF',
    'preview': 'Draw the pages for review',
  };

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final colors = UriColors.of(context);
    final v = c.workflowView;
    if (v == null) return const Center(child: CircularProgressIndicator());
    final state = '${v['state']}';
    final steps = [for (final s in (v['steps'] as List? ?? const [])) (s as Map).cast<String, dynamic>()];
    final findings = [for (final f in (v['findings'] as List? ?? const [])) (f as Map).cast<String, dynamic>()];
    final out = (v['outputs'] as List?)?.firstOrNull as Map?;
    final errors = findings.where((f) => f['severity'] == 'error').length;
    final warnings = findings.where((f) => f['severity'] == 'warning').length;
    return ListView(key: const ValueKey('office-workflow'), padding: const EdgeInsets.all(UriSpace.md), children: [
      Text('Task: ${_stateLabel(state)}', key: const ValueKey('office-workflow-state'),
          style: Theme.of(context).textTheme.titleMedium),
      // Real-app run r2 (2026-10-15): the Save button sat under the findings and twelve page images, out of sight.
      // The task's actions now come first; after saving, the file is named and can be opened from here.
      const SizedBox(height: UriSpace.sm),
      Wrap(spacing: 8, runSpacing: 8, children: [
        if (state == 'ready_to_save' && warnings > 0 && v['warnings_accepted'] != true)
          OutlinedButton(key: const ValueKey('office-accept-warnings'), onPressed: c.busy ? null : c.acceptWarnings,
              child: const Text('Accept with warnings')),
        if (state == 'ready_to_save' && (warnings == 0 || v['warnings_accepted'] == true))
          FilledButton.icon(key: const ValueKey('office-save-output'), onPressed: c.busy ? null : c.saveWorkflowOutput,
              icon: const Icon(Icons.save_alt_rounded, size: 18), label: const Text('Save…')),
        if (state == 'interrupted')
          FilledButton(key: const ValueKey('office-resume'), onPressed: c.busy ? null : c.resumeWorkflow,
              child: const Text('Resume (confirm the file again)')),
        if (!{'saved', 'cancelled', 'failed', 'discarded'}.contains(state))
          TextButton(key: const ValueKey('office-cancel'), onPressed: c.busy ? null : c.cancelWorkflow,
              child: const Text('Cancel')),
      ]),
      if (state == 'saved' && v['saved'] is Map) ...[
        const SizedBox(height: UriSpace.sm),
        Row(children: [
          Expanded(child: Text('Saved as ${(v['saved'] as Map)['name']}. It is listed under Recent and PDFs.',
              key: const ValueKey('office-saved-name'))),
          // A saved file is opened like any file: the owner confirms it in the picker (a recent entry is not a
          // grant; Codex O2-R6-01).
          if (c.environment?.pickDocumentPath != null)
            TextButton.icon(key: const ValueKey('office-open-saved'),
                onPressed: c.busy ? null : c.pickAndOpenDocument,
                icon: const Icon(Icons.folder_open_rounded, size: 18), label: const Text('Open it…')),
        ]),
      ],
      const SizedBox(height: UriSpace.sm),
      for (final s in steps)
        ListTile(
          key: ValueKey('office-step-${s['id']}'),
          dense: true,
          leading: Icon(switch (s['state']) {
            'done' => Icons.check_circle_rounded,
            'running' => Icons.timelapse_rounded,
            'failed' => Icons.error_outline_rounded,
            'cancelled' => Icons.cancel_outlined,
            _ => Icons.radio_button_unchecked_rounded,
          }, color: s['state'] == 'failed' ? colors.danger : s['state'] == 'done' ? colors.success : colors.inkSoft),
          title: Text(_labels['${s['id']}'] ?? '${s['id']}'),
          subtitle: Text(switch (s['kind']) { 'D' => 'Rule-based', 'E' => 'Engine', _ => 'URI-written' }),
        ),
      if (findings.isNotEmpty) ...[
        const SizedBox(height: UriSpace.sm),
        Eyebrow('Findings: $errors error(s), $warnings warning(s)'),
        for (final f in findings)
          ListTile(
            key: ValueKey('office-finding-${f['id']}'),
            dense: true,
            leading: Icon(f['severity'] == 'error' ? Icons.error_outline_rounded : Icons.warning_amber_rounded,
                color: f['severity'] == 'error' ? colors.danger : colors.warning),
            title: Text('${f['message']}${f['weak'] == true ? ' (rough check)' : ''}'),
          ),
      ],
      // CX-1: a cancelled task says so instead of drawing pages that can never load.
      if (state == 'cancelled')
        Padding(
          padding: const EdgeInsets.only(top: UriSpace.sm),
          child: Text('Cancelled. Nothing was saved, and your original file is unchanged. Use the arrow at the top to '
              'go back.', key: const ValueKey('office-workflow-cancelled')),
        ),
      // Codex review R4-1: pages exist only while the output waits for review; after a save (or cancel, failure,
      // discard) the work files are removed, so no page is requested.
      if (out != null && const {'ready_to_save', 'needs_review'}.contains(state)) ...[
        const SizedBox(height: UriSpace.sm),
        Eyebrow('${out['name']} · ${out['pages']} page(s)'),
        SizedBox(
          height: 260,
          child: ListView(scrollDirection: Axis.horizontal, children: [
            for (var p = 1; p <= ((out['pages'] as int?) ?? 0) && p <= 12; p++)
              Padding(
                padding: const EdgeInsets.all(6),
                child: _PageImage(controller: c, docId: c.activeWorkflow!, page: p, width: 160, output: true,
                    key: ValueKey('office-out-${c.activeWorkflow}-$p')),
              ),
          ]),
        ),
      ],
      if (state == 'failed')
        Padding(
          padding: const EdgeInsets.only(top: UriSpace.sm),
          child: Text(c.lastError ?? 'The task stopped. Your original file was not changed.',
              style: TextStyle(color: colors.danger)),
        ),
    ]);
  }

  static String _stateLabel(String s) => switch (s) {
        'waiting_approval' => 'waiting for your approval',
        'running' => 'working',
        'ready_to_save' => 'ready to save',
        'needs_review' => 'needs review (cannot be saved)',
        'interrupted' => 'interrupted',
        'saved' => 'saved',
        'cancelled' => 'cancelled',
        'failed' => 'stopped',
        'discarded' => 'discarded',
        _ => s,
      };
}
