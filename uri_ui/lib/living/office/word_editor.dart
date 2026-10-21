import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import 'document_controller.dart';
import 'presentation_editor.dart';

/// The Word editor (plan 12 §5): the document's blocks on the left (headings indented, tables and pictures named),
/// the working copy's pages in the centre, and on the right the selected block's editor (text, style, formatting,
/// table cells), Insert after it, the Page section (header, footer, page numbers, orientation, margins) and Find and
/// replace. Every change goes to the service as one op against the latest view; the file changes only through the
/// save card shown in the URI pane.
class WordEditor extends StatelessWidget {
  const WordEditor({super.key, required this.workspace, required this.editor});
  final OfficeWorkspaceController workspace;
  final PresentationEditController editor;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: editor,
      builder: (context, _) {
        final colors = UriColors.of(context);
        final e = editor;
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          AuthoringBar(workspace: workspace, editor: e),
          if (e.error != null)
            Container(
              key: const ValueKey('authoring-error'),
              color: colors.accentSoft.withValues(alpha: .4),
              padding: const EdgeInsets.symmetric(horizontal: UriSpace.md, vertical: UriSpace.xs),
              child: Text(e.error!),
            ),
          Expanded(
            child: LayoutBuilder(builder: (context, box) {
              final narrow = box.maxWidth < 900;
              return Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                SizedBox(width: narrow ? 160 : 220, child: _BlockList(editor: e)),
                const VerticalDivider(width: 1),
                Expanded(child: _Pages(workspace: workspace, editor: e)),
                const VerticalDivider(width: 1),
                SizedBox(width: narrow ? 260 : 330, child: _BlockPanel(workspace: workspace, editor: e)),
              ]);
            }),
          ),
        ]);
      },
    );
  }
}

class _BlockList extends StatelessWidget {
  const _BlockList({required this.editor});
  final PresentationEditController editor;

  @override
  Widget build(BuildContext context) {
    final colors = UriColors.of(context);
    final e = editor;
    final blocks = e.blocks;
    final sel = e.selectedBlock;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Expanded(
        child: ListView.builder(
          key: const ValueKey('authoring-blocks'),
          itemCount: blocks.length,
          itemBuilder: (context, i) {
            final b = blocks[i];
            final level = b['level'] as int?;
            final label = switch (b['kind']) {
              'table' => 'Table (${b['rows']} x ${b['cols']})',
              _ => b['picture'] == true && '${b['text']}'.trim().isEmpty
                  ? 'Picture'
                  : b['page_break'] == true && '${b['text']}'.trim().isEmpty
                      ? 'Page break'
                      : '${b['text']}'.trim().isEmpty
                          ? '(empty paragraph)'
                          : '${b['text']}',
            };
            return InkWell(
              key: ValueKey('authoring-block-$i'),
              onTap: () => e.selectBlock(i),
              child: Container(
                color: i == sel ? colors.accentSoft.withValues(alpha: .45) : null,
                padding: EdgeInsets.fromLTRB(8.0 + 10.0 * ((level ?? 3) - 0).clamp(0, 3), 6, 8, 6),
                child: Text(label, maxLines: 2, overflow: TextOverflow.ellipsis,
                    style: TextStyle(fontSize: level != null ? UriType.body : UriType.label,
                        fontWeight: level != null ? FontWeight.w600 : FontWeight.normal,
                        color: b['locked'] != null ? colors.inkSoft : null)),
              ),
            );
          },
        ),
      ),
      Wrap(alignment: WrapAlignment.center, children: [
        IconButton(
          key: const ValueKey('authoring-block-up'),
          tooltip: 'Move up',
          onPressed: e.busy || blocks.isEmpty || sel == 0 ? null : () => e.op({'op': 'move_block', ...e.at(sel),
              'to': sel - 1}),
          icon: const Icon(Icons.arrow_upward_rounded, size: 18),
        ),
        IconButton(
          key: const ValueKey('authoring-block-down'),
          tooltip: 'Move down',
          onPressed: e.busy || blocks.isEmpty || sel >= blocks.length - 1
              ? null
              : () => e.op({'op': 'move_block', ...e.at(sel), 'to': sel + 1}),
          icon: const Icon(Icons.arrow_downward_rounded, size: 18),
        ),
        IconButton(
          key: const ValueKey('authoring-block-delete'),
          tooltip: 'Delete this block',
          onPressed: e.busy || blocks.length < 2 ? null : () => e.op({'op': 'delete_block', ...e.at(sel)}),
          icon: const Icon(Icons.delete_outline_rounded, size: 18),
        ),
      ]),
    ]);
  }
}

class _Pages extends StatelessWidget {
  const _Pages({required this.workspace, required this.editor});
  final OfficeWorkspaceController workspace;
  final PresentationEditController editor;

  @override
  Widget build(BuildContext context) {
    final e = editor;
    final pages = (e.preview?['pages'] as int?) ?? 1;
    final page = e.previewPage.clamp(1, pages);
    return Padding(
      padding: const EdgeInsets.all(UriSpace.md),
      child: Column(children: [
        Expanded(
          child: Center(
            child: AspectRatio(
              aspectRatio: 21 / 29.7,
              child: DecoratedBox(
                key: const ValueKey('authoring-page-preview'),
                decoration: BoxDecoration(border: Border.all(color: UriColors.of(context).inkSoft.withValues(alpha: .3))),
                child: AuthoringPage(workspace: workspace, editor: e, page: page, width: 900),
              ),
            ),
          ),
        ),
        Row(mainAxisAlignment: MainAxisAlignment.center, children: [
          IconButton(key: const ValueKey('authoring-page-prev'), tooltip: 'Previous page',
              onPressed: page > 1 ? () => e.showPage(page - 1) : null, icon: const Icon(Icons.chevron_left_rounded)),
          Flexible(
            child: Text('Page $page of $pages · preview drawn by LibreOffice', key: const ValueKey('authoring-page-label'),
                maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: UriType.label)),
          ),
          IconButton(key: const ValueKey('authoring-page-next'), tooltip: 'Next page',
              onPressed: page < pages ? () => e.showPage(page + 1) : null,
              icon: const Icon(Icons.chevron_right_rounded)),
        ]),
      ]),
    );
  }
}

class _BlockPanel extends StatelessWidget {
  const _BlockPanel({required this.workspace, required this.editor});
  final OfficeWorkspaceController workspace;
  final PresentationEditController editor;

  @override
  Widget build(BuildContext context) {
    final e = editor;
    final b = e.selectedBlockView;
    final i = e.selectedBlock;
    const eyebrow = TextStyle(fontSize: UriType.caption, letterSpacing: 1.2);
    return ListView(
      key: ValueKey('authoring-block-panel-$i-${b?['expect']}'),
      padding: const EdgeInsets.all(UriSpace.sm),
      children: [
        if (b != null) ...[
          Text('BLOCK ${i + 1}', style: eyebrow),
          const SizedBox(height: UriSpace.xs),
          if (b['locked'] != null)
            Text('This paragraph has ${b['locked']}, which URI keeps as it is.',
                key: const ValueKey('authoring-block-locked'), style: const TextStyle(fontSize: UriType.label)),
          if (b['kind'] == 'paragraph' && b['locked'] == null) ..._paragraph(context, e, i, b),
          if (b['kind'] == 'table') ..._table(e, i, b),
          const SizedBox(height: UriSpace.xs),
          const Text('INSERT AFTER THIS BLOCK', style: eyebrow),
          Wrap(spacing: UriSpace.xs, runSpacing: UriSpace.xs, children: [
            OutlinedButton(
              key: const ValueKey('authoring-insert-paragraph'),
              onPressed: e.busy ? null : () => e.op({'op': 'insert_paragraph', 'after': i, 'after_expect': b['expect'], 'text': ''}),
              child: const Text('Paragraph'),
            ),
            OutlinedButton(
              key: const ValueKey('authoring-insert-table'),
              onPressed: e.busy ? null : () => e.op({'op': 'insert_table', 'after': i, 'after_expect': b['expect'], 'cells': [['', ''], ['', '']]}),
              child: const Text('Table'),
            ),
            if (workspace.environment?.pickImagePath != null)
              OutlinedButton(
                key: const ValueKey('authoring-insert-picture'),
                onPressed: e.busy ? null : () => workspace.insertPicture(i),
                child: const Text('Picture'),
              ),
            OutlinedButton(
              key: const ValueKey('authoring-insert-page-break'),
              onPressed: e.busy ? null : () => e.op({'op': 'insert_page_break', 'after': i, 'after_expect': b['expect']}),
              child: const Text('Page break'),
            ),
          ]),
        ],
        const Divider(),
        const Text('PAGE', style: eyebrow),
        AuthoringTextField(
          key: ValueKey('authoring-header-${e.doc['header']}'),
          fieldKey: const ValueKey('authoring-header'),
          label: 'Header',
          initial: '${e.doc['header'] ?? ''}',
          enabled: !e.busy,
          onApply: (t) => e.op({'op': 'set_header_text', 'text': t}),
        ),
        AuthoringTextField(
          key: ValueKey('authoring-footer-${e.doc['footer']}'),
          fieldKey: const ValueKey('authoring-footer'),
          label: 'Footer',
          initial: '${e.doc['footer'] ?? ''}',
          enabled: !e.busy,
          onApply: (t) => e.op({'op': 'set_footer_text', 'text': t}),
        ),
        Wrap(spacing: UriSpace.xs, runSpacing: UriSpace.xs, children: [
          OutlinedButton(
            key: const ValueKey('authoring-page-numbers'),
            onPressed: e.busy ? null : () => e.op({'op': 'insert_page_number', 'where': 'footer', 'align': 'center'}),
            child: const Text('Page numbers'),
          ),
          OutlinedButton(
            key: const ValueKey('authoring-orientation'),
            onPressed: e.busy
                ? null
                : () => e.op({'op': 'set_page_setup',
                      'orientation': (e.doc['page'] as Map?)?['orientation'] == 'landscape' ? 'portrait' : 'landscape'}),
            child: Text((e.doc['page'] as Map?)?['orientation'] == 'landscape' ? 'Portrait' : 'Landscape'),
          ),
          PopupMenuButton<double>(
            key: const ValueKey('authoring-margins'),
            tooltip: 'Margins',
            enabled: !e.busy,
            itemBuilder: (_) => const [
              PopupMenuItem(value: 1.27, child: Text('Narrow (1.27 cm)')),
              PopupMenuItem(value: 2.54, child: Text('Normal (2.54 cm)')),
              PopupMenuItem(value: 3.18, child: Text('Wide (3.18 cm)')),
            ],
            onSelected: (m) => e.op({'op': 'set_page_setup',
                'margins_cm': {'top': m, 'bottom': m, 'left': m, 'right': m}}),
            child: const Padding(padding: EdgeInsets.all(8), child: Text('Margins')),
          ),
        ]),
        const Divider(),
        const Text('FIND AND REPLACE', style: eyebrow),
        _FindReplace(editor: e),
      ],
    );
  }

  List<Widget> _paragraph(BuildContext context, PresentationEditController e, int i, Map<String, dynamic> b) {
    final style = '${b['style']}';
    return [
      AuthoringTextField(
        key: ValueKey('authoring-para-$i-${b['expect']}'),
        fieldKey: const ValueKey('authoring-para-text'),
        label: 'Text',
        initial: '${b['text'] ?? ''}',
        multiline: true,
        enabled: !e.busy,
        onApply: (t) => e.op({'op': 'set_paragraph_text', ...e.at(i), 'text': t}),
      ),
      Row(children: [
        Expanded(
          child: PopupMenuButton<String>(
            key: const ValueKey('authoring-style'),
            tooltip: 'Style',
            enabled: !e.busy,
            itemBuilder: (_) => [
              for (final s in e.styles.take(40)) PopupMenuItem(value: s, child: Text(s, key: ValueKey('authoring-style-$s'))),
            ],
            onSelected: (s) => e.op({'op': 'set_style', ...e.at(i), 'style': s}),
            child: Padding(padding: const EdgeInsets.all(8), child: Text('Style: $style',
                overflow: TextOverflow.ellipsis)),
          ),
        ),
        IconButton(
          key: const ValueKey('authoring-para-bold'),
          tooltip: 'Bold',
          isSelected: b['bold'] == true,
          onPressed: e.busy ? null : () => e.op({'op': 'format_text', ...e.at(i), 'format': {'b': b['bold'] != true}}),
          icon: const Icon(Icons.format_bold_rounded, size: 16),
        ),
        IconButton(
          key: const ValueKey('authoring-para-italic'),
          tooltip: 'Italic',
          isSelected: b['italic'] == true,
          onPressed: e.busy ? null : () => e.op({'op': 'format_text', ...e.at(i), 'format': {'i': b['italic'] != true}}),
          icon: const Icon(Icons.format_italic_rounded, size: 16),
        ),
        PopupMenuButton<String>(
          key: const ValueKey('authoring-para-align'),
          tooltip: 'Alignment',
          enabled: !e.busy,
          icon: const Icon(Icons.format_align_left_rounded, size: 16),
          itemBuilder: (_) => const [
            PopupMenuItem(value: 'left', child: Text('Left')),
            PopupMenuItem(value: 'center', child: Text('Centre')),
            PopupMenuItem(value: 'right', child: Text('Right')),
            PopupMenuItem(value: 'justify', child: Text('Justify')),
          ],
          onSelected: (a) => e.op({'op': 'format_text', ...e.at(i), 'format': {'align': a}}),
        ),
      ]),
    ];
  }

  List<Widget> _table(PresentationEditController e, int i, Map<String, dynamic> b) {
    final cells = [for (final r in (b['cells'] as List? ?? const [])) [for (final c in (r as List)) '$c']];
    return [
      for (var r = 0; r < cells.length; r++)
        Row(children: [
          for (var c = 0; c < cells[r].length; c++)
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(2),
                child: AuthoringTextField(
                  key: ValueKey('authoring-wcell-$i-$r-$c-${cells[r][c]}'),
                  fieldKey: ValueKey('authoring-wcell-$r-$c'),
                  label: '',
                  initial: cells[r][c],
                  dense: true,
                  enabled: !e.busy,
                  onApply: (t) => e.op({'op': 'set_table_cell', ...e.at(i), 'row': r, 'col': c, 'text': t}),
                ),
              ),
            ),
        ]),
      Wrap(children: [
        TextButton(
          key: const ValueKey('authoring-table-add-row'),
          onPressed: e.busy || cells.isEmpty ? null
              : () => e.op({'op': 'add_table_row', ...e.at(i), 'after_row': cells.length - 1}),
          child: const Text('Add a row'),
        ),
        TextButton(
          key: const ValueKey('authoring-table-delete-row'),
          onPressed: e.busy || cells.length < 2 ? null
              : () => e.op({'op': 'delete_table_row', ...e.at(i), 'row': cells.length - 1}),
          child: const Text('Delete the last row'),
        ),
      ]),
    ];
  }
}

class _FindReplace extends StatefulWidget {
  const _FindReplace({required this.editor});
  final PresentationEditController editor;

  @override
  State<_FindReplace> createState() => _FindReplaceState();
}

class _FindReplaceState extends State<_FindReplace> {
  final _find = TextEditingController();
  final _replace = TextEditingController();

  @override
  void dispose() {
    _find.dispose();
    _replace.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final e = widget.editor;
    final r = e.lastResult;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      TextField(key: const ValueKey('authoring-find'), controller: _find,
          decoration: const InputDecoration(labelText: 'Find', isDense: true, border: OutlineInputBorder())),
      const SizedBox(height: UriSpace.xs),
      TextField(key: const ValueKey('authoring-replace'), controller: _replace,
          decoration: const InputDecoration(labelText: 'Replace with', isDense: true, border: OutlineInputBorder())),
      Align(
        alignment: Alignment.centerRight,
        child: TextButton(
          key: const ValueKey('authoring-replace-all'),
          onPressed: e.busy
              ? null
              : () {
                  if (_find.text.isEmpty) return;
                  e.op({'op': 'replace_text', 'find': _find.text, 'replace': _replace.text});
                },
          child: const Text('Replace all'),
        ),
      ),
      if (r is Map && r.containsKey('replaced'))
        Text(
          'Replaced ${r['replaced']}.'
          '${(r['split_across_formatting'] ?? 0) > 0 ? ' ${r['split_across_formatting']} more cross formatting changes and were left as they are.' : ''}'
          '${(r['skipped'] ?? 0) > 0 ? ' ${r['skipped']} in tracked changes or fields were left as they are.' : ''}',
          key: const ValueKey('authoring-replace-result'),
          style: const TextStyle(fontSize: UriType.label),
        ),
    ]);
  }
}
