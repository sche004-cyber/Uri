import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../integration/scheduler_client.dart' show SchedulerApiError;
import 'document_controller.dart';
import 'office_client.dart';

/// Authoring error texts (uri_office/authoring), in the words the owner sees.
const authoringErrorText = <String, String>{
  'AUTHORING_NOT_SUPPORTED': 'URI cannot do that to this presentation.',
  'BAD_BOX': 'That position or size does not fit on the slide.',
  'BAD_FORMAT': 'That formatting is not available.',
  'BAD_OP': 'URI could not make that change.',
  'BAD_POSITION': 'That slide position does not exist.',
  'BAD_TABLE': 'A table needs between 1 and 20 rows and columns.',
  'BAD_TEXT': 'That text is too long.',
  'NOTHING_TO_REDO': 'Nothing to redo.',
  'NOTHING_TO_SAVE': 'There are no changes to save.',
  'NOTHING_TO_UNDO': 'Nothing to undo.',
  'NOT_A_PRESENTATION': 'This file is not a presentation URI can edit.',
  'SAVE_AS_REQUIRED': 'Choose where to save the new presentation (Save as).',
  'STALE_CHANGE': 'The presentation changed after the save card was shown. Save again to review it.',
  'TARGET_CHANGED': 'The file changed on disk since it was opened. Save as a new file instead.',
  'FILE_READ_ONLY': 'The file is read-only. Save as a new file instead.',
  'UNKNOWN_EDIT': 'This edit is no longer open.',
  'UNKNOWN_LAYOUT': 'That slide layout is not in this presentation.',
  'UNKNOWN_SHAPE': 'That item is no longer on the slide.',
  'UNKNOWN_SLIDE': 'That slide is no longer in the presentation.',
  'UNKNOWN_BLOCK': 'That paragraph is no longer in the document.',
  'STALE_BLOCK': 'The document changed since this was shown. Look again and retry.',
  'UNKNOWN_STYLE': 'That style is not in this document.',
  'NOT_A_DOCUMENT': 'This file is not a Word document URI can edit.',
  'NOT_FOUND': 'No matches.',
  'BAD_IMAGE': 'That picture could not be read.',
  'PREVIEW_NOT_READY': 'Wait until the preview shows your changes, then save.',
  'PREVIEW_FAILED': 'The changed file could not be shown, so it is not saved. Undo the last change or try again.',
  'DESTINATION_EXISTS': 'A file with that name already exists. URI never replaces files with Save as.',
};

String authoringErrorMessage(Object e) {
  if (e is SchedulerApiError) {
    final text = authoringErrorText[e.code];
    if (text != null) {
      // AUTHORING_NOT_SUPPORTED names what stopped it ("video", "embedded object").
      return e.code == 'AUTHORING_NOT_SUPPORTED' && (e.detail ?? '').isNotEmpty ? '$text (${e.detail})' : text;
    }
  }
  return officeErrorMessage(e);
}

/// One open edit of a presentation (milestones A/B) or a Word document (milestone C): the service's working copy, its
/// change list, undo/redo and the preview of the working copy. Nothing reaches a file until the owner approves the
/// save card.
class PresentationEditController extends ChangeNotifier {
  PresentationEditController(this.client, Map<String, dynamic> view) : _view = view {
    _selected = slides.isEmpty ? null : slides.first['id'] as int;
    _poll = Timer.periodic(const Duration(milliseconds: 700), (_) => unawaited(_tick()));
  }

  final OfficeClient client;
  Map<String, dynamic> _view;
  Map<String, dynamic>? preview;                  // the preview document's view (pages, preview state)
  int? _selected;
  bool busy = false;
  String? error;
  String? state;                                  // "Saving…", "Saved as Plan.pptx", "Not saved"
  Timer? _poll;
  bool _disposed = false;

  String get id => _view['authoring_id'] as String;
  String get name => _view['name'] as String? ?? 'Presentation';
  bool get isNew => _view['new'] == true;
  String get kind => _view['kind'] as String? ?? 'pptx';
  bool get isWord => kind == 'docx';
  /// Word (milestone C): the document's blocks, styles, page setup, header and footer.
  Map<String, dynamic> get doc => ((_view['doc'] as Map?) ?? const {}).cast<String, dynamic>();
  List<Map<String, dynamic>> get blocks =>
      [for (final b in (doc['blocks'] as List? ?? const [])) (b as Map).cast<String, dynamic>()];
  List<String> get styles => [for (final s in (doc['styles'] as List? ?? const [])) '$s'];
  int _block = 0;
  int get selectedBlock => blocks.isEmpty ? 0 : _block.clamp(0, blocks.length - 1);
  Map<String, dynamic>? get selectedBlockView => blocks.isEmpty ? null : blocks[selectedBlock];
  void selectBlock(int i) {
    _block = i;
    _notify();
  }
  /// The address of block [i] as the last view showed it (the service refuses it if the block moved).
  Map<String, dynamic> at(int i) => {'block': i, 'expect': blocks[i]['expect']};
  int previewPage = 1;
  /// What the last op answered (Word find and replace reports its counts here).
  Object? lastResult;
  void showPage(int p) {
    previewPage = p;
    _notify();
  }
  /// The file this edit saves to (the opened file, or the file chosen with Save as); null for a new presentation.
  String? get savedPath => _view['path'] as String?;
  Map<String, dynamic> get deck => ((_view['deck'] as Map?) ?? const {}).cast<String, dynamic>();
  List<Map<String, dynamic>> get slides =>
      [for (final s in (deck['slides'] as List? ?? const [])) (s as Map).cast<String, dynamic>()];
  List<String> get layouts => [for (final l in (deck['layouts'] as List? ?? const [])) '$l'];
  double get aspect => (deck['aspect'] as num?)?.toDouble() ?? 16 / 9;
  List<String> get changes => [for (final c in (_view['changes'] as List? ?? const [])) '${(c as Map)['text']}'];
  bool get canUndo => _view['can_undo'] == true;
  bool get canRedo => _view['can_redo'] == true;
  String? get previewId => _view['preview_document_id'] as String?;
  bool get previewReady => preview != null && preview!['document_id'] == previewId &&
      ((preview!['preview'] as Map?)?['state']) == 'ready';
  bool get previewFailed => preview != null && preview!['document_id'] == previewId &&
      ((preview!['preview'] as Map?)?['state']) == 'unavailable';

  /// The state line: Editing (n unsaved changes), Saving, Saved, Not saved, Failed.
  String get stateLine {
    if (state != null) return state!;
    final n = changes.length;
    // "a copy": the URI pane (which says so) is a side sheet while editing, so the editor says it itself
    return n == 0 ? 'Editing a copy · no unsaved changes' : 'Editing a copy · $n unsaved change${n == 1 ? '' : 's'}';
  }

  int get selectedIndex {
    final i = slides.indexWhere((s) => s['id'] == _selected);
    return i < 0 ? 0 : i;
  }

  Map<String, dynamic>? get selectedSlide => slides.isEmpty ? null : slides[selectedIndex];

  void select(int slideId) {
    _selected = slideId;
    _notify();
  }

  void _take(Map<String, dynamic> v) {
    final before = slides.map((s) => s['id']).toSet();
    _view = v;
    lastResult = v['result'];
    if (isWord && v['result'] is int) _block = v['result'] as int;       // an inserted block is selected
    final ids = slides.map((s) => s['id'] as int).toList();
    final added = ids.where((i) => !before.contains(i)).toList();
    if (added.length == 1) {
      _selected = added.single;                      // a new or duplicated slide is selected
    } else if (!ids.contains(_selected)) {
      _selected = ids.isEmpty ? null : ids[(selectedIndex).clamp(0, ids.length - 1)];
    }
  }

  Future<bool> _run(Future<Map<String, dynamic>> Function() call) async {
    if (busy) return false;
    busy = true;
    error = null;
    _notify();
    try {
      _take(await call());
      state = null;
      return true;
    } catch (e) {
      error = authoringErrorMessage(e);
      return false;
    } finally {
      busy = false;
      _notify();
    }
  }

  Future<bool> op(Map<String, dynamic> op, {String? imagePath}) =>
      _run(() => client.authoringOp(id, op, imagePath: imagePath));
  Future<bool> undo() => _run(() => client.authoringUndo(id));
  Future<bool> redo() => _run(() => client.authoringUndo(id, redo: true));
  Future<bool> refresh() => _run(() => client.authoringView(id));

  /// The save card's A2UI messages, or null (the error says why).
  Future<List<dynamic>?> proposeSave({String? saveAsPath}) async {
    if (busy) return null;
    busy = true;
    error = null;
    _notify();
    try {
      final r = await client.authoringSave(id, saveAsPath: saveAsPath);
      state = 'Waiting for your approval to save';
      return (r['messages'] as List?) ?? const [];
    } catch (e) {
      error = authoringErrorMessage(e);
      return null;
    } finally {
      busy = false;
      _notify();
    }
  }

  /// The save card was answered (the service result of the A2UI action).
  Future<void> saveAnswered(Map<String, dynamic> result) async {
    if (result['status'] == 'applied') {
      await refresh();
      state = 'Saved as ${result['saved_to'] ?? name}';
    } else {
      state = 'Not saved. Your changes are still here.';
    }
    _notify();
  }

  void failed(Object e) {
    error = authoringErrorMessage(e);
    state = null;
    _notify();
  }

  Future<void> close() async {
    _poll?.cancel();
    try {
      await client.authoringClose(id);
    } catch (_) {}
  }

  Future<void> _tick() async {
    final pid = previewId;
    if (_disposed || pid == null || previewReady || previewFailed) return;
    try {
      preview = await client.document(pid);
      _notify();
    } catch (_) {}
  }

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _poll?.cancel();
    super.dispose();
  }
}

/// The presentation editor (plan 11 §4): slide strip with slide actions, the selected slide's preview, the slide's
/// editable items with Insert and simple formatting, and a top bar with the change counter, Undo, Redo, Save and
/// Save as. The URI pane beside it shows the save card.
class PresentationEditor extends StatelessWidget {
  const PresentationEditor({super.key, required this.workspace, required this.editor});
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
          _bar(context, e),
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
              final strip = SizedBox(width: narrow ? 120 : 168, child: _SlideStrip(workspace: workspace, editor: e));
              final items = SizedBox(width: narrow ? 260 : 320, child: _ItemsPanel(workspace: workspace, editor: e));
              return Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                strip,
                const VerticalDivider(width: 1),
                Expanded(child: _SlidePreview(workspace: workspace, editor: e)),
                const VerticalDivider(width: 1),
                items,
              ]);
            }),
          ),
        ]);
      },
    );
  }

  Widget _bar(BuildContext context, PresentationEditController e) => AuthoringBar(workspace: workspace, editor: e);
}

/// The editor's top bar (both kinds): state line, Undo, Redo, Save..., Save as..., Done.
class AuthoringBar extends StatelessWidget {
  const AuthoringBar({super.key, required this.workspace, required this.editor});
  final OfficeWorkspaceController workspace;
  final PresentationEditController editor;

  @override
  Widget build(BuildContext context) {
    final e = editor;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: UriSpace.sm, vertical: UriSpace.xs),
      child: Wrap(crossAxisAlignment: WrapCrossAlignment.center, spacing: UriSpace.xs, children: [
        Text(e.stateLine, key: const ValueKey('authoring-state')),
        if (e.busy) const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2)),
        IconButton(
          key: const ValueKey('authoring-undo'),
          tooltip: 'Undo',
          onPressed: e.busy || !e.canUndo ? null : e.undo,
          icon: const Icon(Icons.undo_rounded, size: 18),
        ),
        IconButton(
          key: const ValueKey('authoring-redo'),
          tooltip: 'Redo',
          onPressed: e.busy || !e.canRedo ? null : e.redo,
          icon: const Icon(Icons.redo_rounded, size: 18),
        ),
        if (!e.isNew)
          FilledButton.tonal(
            key: const ValueKey('authoring-save'),
            onPressed: e.busy || e.changes.isEmpty ? null : () => workspace.saveEdit(),
            child: const Text('Save…'),
          ),
        OutlinedButton(
          key: const ValueKey('authoring-save-as'),
          onPressed: e.busy ? null : () => workspace.saveEdit(saveAs: true),
          child: const Text('Save as…'),
        ),
        TextButton(
          key: const ValueKey('authoring-done'),
          onPressed: e.busy ? null : () => finishEditing(context, workspace),
          child: const Text('Done'),
        ),
      ]),
    );
  }
}

/// Leaving the editor: with unsaved changes the owner chooses to keep editing or discard them.
Future<void> finishEditing(BuildContext context, OfficeWorkspaceController c) async {
  final e = c.editor;
  if (e == null) return;
  if (e.changes.isNotEmpty) {
    final discard = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const ValueKey('authoring-leave-dialog'),
        title: const Text('Leave without saving?'),
        content: Text('${e.changes.length} change${e.changes.length == 1 ? ' is' : 's are'} not saved. '
            'Your file has not been changed.'),
        actions: [
          TextButton(
            key: const ValueKey('authoring-leave-keep'),
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Keep editing'),
          ),
          TextButton(
            key: const ValueKey('authoring-leave-discard'),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Discard changes'),
          ),
        ],
      ),
    );
    if (discard != true) return;
  }
  await c.closeEdit();
}

class _SlideStrip extends StatelessWidget {
  const _SlideStrip({required this.workspace, required this.editor});
  final OfficeWorkspaceController workspace;
  final PresentationEditController editor;

  @override
  Widget build(BuildContext context) {
    final colors = UriColors.of(context);
    final e = editor;
    final slides = e.slides;
    final sel = e.selectedSlide;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Expanded(
        child: ListView.builder(
          key: const ValueKey('authoring-slides'),
          padding: const EdgeInsets.all(UriSpace.xs),
          itemCount: slides.length,
          itemBuilder: (context, i) {
            final s = slides[i];
            final selected = sel != null && s['id'] == sel['id'];
            return Padding(
              padding: const EdgeInsets.only(bottom: UriSpace.xs),
              child: InkWell(
                key: ValueKey('authoring-slide-${i + 1}'),
                onTap: () => e.select(s['id'] as int),
                child: Container(
                  decoration: BoxDecoration(
                    border: Border.all(color: selected ? colors.accent : colors.inkSoft.withValues(alpha: .3),
                        width: selected ? 2 : 1),
                  ),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                    AspectRatio(
                      aspectRatio: e.aspect,
                      child: AuthoringPage(workspace: workspace, editor: e, page: i + 1, width: 200),
                    ),
                    Padding(
                      padding: const EdgeInsets.all(4),
                      child: Text('${i + 1}. ${(s['title'] as String?)?.isNotEmpty == true ? s['title'] : s['layout']}',
                          maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11)),
                    ),
                  ]),
                ),
              ),
            );
          },
        ),
      ),
      Wrap(alignment: WrapAlignment.center, children: [
        PopupMenuButton<String>(
          key: const ValueKey('authoring-add-slide'),
          tooltip: 'Add a slide',
          enabled: !e.busy,
          icon: const Icon(Icons.add_box_outlined, size: 18),
          itemBuilder: (_) => [
            for (final l in e.layouts) PopupMenuItem(value: l, child: Text(l, key: ValueKey('authoring-layout-$l'))),
          ],
          onSelected: (l) => e.op({'op': 'add_slide', 'layout': l, 'after': ?sel?['id']}),
        ),
        IconButton(
          key: const ValueKey('authoring-duplicate-slide'),
          tooltip: 'Duplicate this slide',
          onPressed: e.busy || sel == null ? null : () => e.op({'op': 'duplicate_slide', 'slide': sel['id']}),
          icon: const Icon(Icons.copy_all_outlined, size: 18),
        ),
        IconButton(
          key: const ValueKey('authoring-move-up'),
          tooltip: 'Move up',
          onPressed: e.busy || sel == null || e.selectedIndex == 0
              ? null
              : () => e.op({'op': 'move_slide', 'slide': sel['id'], 'to': e.selectedIndex - 1}),
          icon: const Icon(Icons.arrow_upward_rounded, size: 18),
        ),
        IconButton(
          key: const ValueKey('authoring-move-down'),
          tooltip: 'Move down',
          onPressed: e.busy || sel == null || e.selectedIndex >= slides.length - 1
              ? null
              : () => e.op({'op': 'move_slide', 'slide': sel['id'], 'to': e.selectedIndex + 1}),
          icon: const Icon(Icons.arrow_downward_rounded, size: 18),
        ),
        IconButton(
          key: const ValueKey('authoring-delete-slide'),
          tooltip: 'Delete this slide',
          onPressed: e.busy || sel == null || slides.length < 2
              ? null
              : () => e.op({'op': 'delete_slide', 'slide': sel['id']}),
          icon: const Icon(Icons.delete_outline_rounded, size: 18),
        ),
      ]),
    ]);
  }
}

/// One page of the working copy's preview, or words while it is being drawn.
class AuthoringPage extends StatelessWidget {
  const AuthoringPage({super.key, required this.workspace, required this.editor, required this.page, required this.width});
  final OfficeWorkspaceController workspace;
  final PresentationEditController editor;
  final int page;
  final int width;

  @override
  Widget build(BuildContext context) {
    final pid = editor.previewId;
    if (pid == null || editor.previewFailed) {
      return const Center(child: Text('No preview', style: TextStyle(fontSize: 11)));
    }
    if (!editor.previewReady) {
      return const Center(child: Text('Updating…', key: ValueKey('authoring-preview-updating'),
          style: TextStyle(fontSize: 11)));
    }
    return FutureBuilder<Uint8List?>(
      key: ValueKey('$pid/$page/$width'),
      future: workspace.pageImage(pid, page, width),
      builder: (context, snap) => snap.data == null
          ? const SizedBox.shrink()
          : Image.memory(snap.data!, fit: BoxFit.contain, gaplessPlayback: true),
    );
  }
}

class _SlidePreview extends StatelessWidget {
  const _SlidePreview({required this.workspace, required this.editor});
  final OfficeWorkspaceController workspace;
  final PresentationEditController editor;

  @override
  Widget build(BuildContext context) {
    final e = editor;
    return Padding(
      padding: const EdgeInsets.all(UriSpace.md),
      child: Column(children: [
        Expanded(
          child: Center(
            child: AspectRatio(
              aspectRatio: e.aspect,
              child: DecoratedBox(
                key: const ValueKey('authoring-slide-preview'),
                decoration: BoxDecoration(border: Border.all(color: UriColors.of(context).inkSoft.withValues(alpha: .3))),
                child: AuthoringPage(workspace: workspace, editor: e, page: e.selectedIndex + 1, width: 1100),
              ),
            ),
          ),
        ),
        Text('Slide ${e.selectedIndex + 1} of ${e.slides.length} · preview drawn by LibreOffice',
            key: const ValueKey('authoring-slide-label'), style: const TextStyle(fontSize: 12)),
      ]),
    );
  }
}

class _ItemsPanel extends StatelessWidget {
  const _ItemsPanel({required this.workspace, required this.editor});
  final OfficeWorkspaceController workspace;
  final PresentationEditController editor;

  @override
  Widget build(BuildContext context) {
    final e = editor;
    final s = e.selectedSlide;
    if (s == null) return const SizedBox.shrink();
    final sid = s['id'] as int;
    final items = [for (final it in (s['items'] as List? ?? const [])) (it as Map).cast<String, dynamic>()];
    final titleId = s['title_id'];
    return ListView(
      key: ValueKey('authoring-items-$sid'),
      padding: const EdgeInsets.all(UriSpace.sm),
      children: [
        Text('SLIDE ${e.selectedIndex + 1}', style: const TextStyle(fontSize: 11, letterSpacing: 1.2)),
        const SizedBox(height: UriSpace.xs),
        if (titleId != null)
          AuthoringTextField(
            key: ValueKey('authoring-title-$sid-${s['title']}'),
            fieldKey: const ValueKey('authoring-title'),
            label: 'Title',
            initial: '${s['title'] ?? ''}',
            enabled: !e.busy,
            onApply: (t) => e.op({'op': 'set_title', 'slide': sid, 'text': t}),
          ),
        for (final it in items)
          if (it['id'] != titleId) _item(context, e, sid, it),
        AuthoringTextField(
          key: ValueKey('authoring-notes-$sid-${s['notes']}'),
          fieldKey: const ValueKey('authoring-notes'),
          label: 'Speaker notes',
          initial: '${s['notes'] ?? ''}',
          multiline: true,
          enabled: !e.busy,
          onApply: (t) => e.op({'op': 'set_notes', 'slide': sid, 'text': t}),
        ),
        const Divider(),
        const Text('INSERT', style: TextStyle(fontSize: 11, letterSpacing: 1.2)),
        Wrap(spacing: UriSpace.xs, children: [
          OutlinedButton.icon(
            key: const ValueKey('authoring-insert-text'),
            onPressed: e.busy
                ? null
                : () => e.op({'op': 'insert_text_box', 'slide': sid, 'paragraphs': ['New text'],
                      'box': {'x': 0.1, 'y': 0.75, 'w': 0.8, 'h': 0.12}}),
            icon: const Icon(Icons.text_fields_rounded, size: 16),
            label: const Text('Text box'),
          ),
          if (workspace.environment?.pickImagePath != null)
            OutlinedButton.icon(
              key: const ValueKey('authoring-insert-picture'),
              onPressed: e.busy ? null : () => workspace.insertPicture(sid),
              icon: const Icon(Icons.image_outlined, size: 16),
              label: const Text('Picture'),
            ),
          OutlinedButton.icon(
            key: const ValueKey('authoring-insert-table'),
            onPressed: e.busy
                ? null
                : () => e.op({'op': 'insert_table', 'slide': sid, 'cells': [['', ''], ['', '']],
                      'box': {'x': 0.1, 'y': 0.3, 'w': 0.8, 'h': 0.3}}),
            icon: const Icon(Icons.table_chart_outlined, size: 16),
            label: const Text('Table'),
          ),
        ]),
      ],
    );
  }

  Widget _item(BuildContext context, PresentationEditController e, int sid, Map<String, dynamic> it) {
    final shape = it['id'] as int;
    final remove = IconButton(
      key: ValueKey('authoring-remove-$shape'),
      tooltip: it['placeholder'] == true ? 'Empty this item' : 'Remove this item',
      onPressed: e.busy ? null : () => e.op({'op': 'delete_shape', 'slide': sid, 'shape': shape}),
      icon: const Icon(Icons.close_rounded, size: 16),
    );
    switch (it['kind']) {
      case 'text':
        final paras = [for (final p in (it['paragraphs'] as List? ?? const [])) '$p'];
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          AuthoringTextField(
            key: ValueKey('authoring-text-$sid-$shape-${paras.join('\n')}'),
            fieldKey: ValueKey('authoring-text-$shape'),
            label: it['placeholder'] == true ? 'Text' : 'Text box',
            initial: paras.join('\n'),
            multiline: true,
            enabled: !e.busy,
            onApply: (t) => e.op({'op': 'set_text', 'slide': sid, 'shape': shape, 'paragraphs': t.split('\n')}),
          ),
          Row(children: [
            IconButton(
              key: ValueKey('authoring-bold-$shape'),
              tooltip: 'Bold',
              isSelected: it['bold'] == true,
              onPressed: e.busy ? null : () => e.op({'op': 'format_text', 'slide': sid, 'shape': shape,
                  'format': {'b': it['bold'] != true}}),
              icon: const Icon(Icons.format_bold_rounded, size: 16),
            ),
            IconButton(
              key: ValueKey('authoring-italic-$shape'),
              tooltip: 'Italic',
              isSelected: it['italic'] == true,
              onPressed: e.busy ? null : () => e.op({'op': 'format_text', 'slide': sid, 'shape': shape,
                  'format': {'i': it['italic'] != true}}),
              icon: const Icon(Icons.format_italic_rounded, size: 16),
            ),
            PopupMenuButton<int>(
              key: ValueKey('authoring-size-$shape'),
              tooltip: 'Text size',
              enabled: !e.busy,
              icon: const Icon(Icons.format_size_rounded, size: 16),
              itemBuilder: (_) => [for (final n in const [14, 18, 24, 32, 44]) PopupMenuItem(value: n, child: Text('$n pt'))],
              onSelected: (n) => e.op({'op': 'format_text', 'slide': sid, 'shape': shape, 'format': {'size': n}}),
            ),
            PopupMenuButton<String>(
              key: ValueKey('authoring-align-$shape'),
              tooltip: 'Alignment',
              enabled: !e.busy,
              icon: const Icon(Icons.format_align_center_rounded, size: 16),
              itemBuilder: (_) => const [
                PopupMenuItem(value: 'left', child: Text('Left')),
                PopupMenuItem(value: 'center', child: Text('Centre')),
                PopupMenuItem(value: 'right', child: Text('Right')),
              ],
              onSelected: (a) => e.op({'op': 'format_text', 'slide': sid, 'shape': shape, 'format': {'align': a}}),
            ),
            const Spacer(),
            remove,
          ]),
          const SizedBox(height: UriSpace.xs),
        ]);
      case 'table':
        final cells = [for (final r in (it['cells'] as List? ?? const [])) [for (final c in (r as List)) '$c']];
        return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Row(children: [const Text('Table', style: TextStyle(fontSize: 12)), const Spacer(), remove]),
          for (var r = 0; r < cells.length; r++)
            Row(children: [
              for (var col = 0; col < cells[r].length; col++)
                Expanded(
                  child: Padding(
                    padding: const EdgeInsets.all(2),
                    child: AuthoringTextField(
                      key: ValueKey('authoring-cell-$sid-$shape-$r-$col-${cells[r][col]}'),
                      fieldKey: ValueKey('authoring-cell-$shape-$r-$col'),
                      label: '',
                      initial: cells[r][col],
                      dense: true,
                      enabled: !e.busy,
                      onApply: (t) => e.op({'op': 'set_table_cell', 'slide': sid, 'shape': shape, 'row': r,
                          'col': col, 'text': t}),
                    ),
                  ),
                ),
            ]),
          const SizedBox(height: UriSpace.xs),
        ]);
      default:
        final label = switch (it['kind']) {
          'chart' => 'Chart (kept as it is; editing charts is not available)',
          'picture' => 'Picture',
          _ => '${it['name']}',
        };
        return Row(children: [Expanded(child: Text(label, style: const TextStyle(fontSize: 12))), remove]);
    }
  }
}

/// A text field that sends its text when the owner presses Apply (or Enter on a one-line field).
class AuthoringTextField extends StatefulWidget {
  const AuthoringTextField({super.key, required this.fieldKey, required this.label, required this.initial,
      required this.onApply, this.multiline = false, this.dense = false, this.enabled = true});
  final Key fieldKey;
  final String label;
  final String initial;
  final bool multiline;
  final bool dense;
  final bool enabled;
  final Future<bool> Function(String) onApply;

  @override
  State<AuthoringTextField> createState() => _AuthoringTextFieldState();
}

class _AuthoringTextFieldState extends State<AuthoringTextField> {
  late final TextEditingController _t = TextEditingController(text: widget.initial);

  @override
  void initState() {
    super.initState();
    _t.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _t.dispose();
    super.dispose();
  }

  bool get _changed => _t.text != widget.initial;

  void _apply() {
    if (_changed && widget.enabled) unawaited(widget.onApply(_t.text));
  }

  @override
  Widget build(BuildContext context) {
    final field = TextField(
      key: widget.fieldKey,
      controller: _t,
      enabled: widget.enabled,
      minLines: widget.multiline ? 2 : 1,
      maxLines: widget.multiline ? 6 : 1,
      style: TextStyle(fontSize: widget.dense ? 12 : 14),
      decoration: InputDecoration(
        labelText: widget.label.isEmpty ? null : widget.label,
        isDense: true,
        border: const OutlineInputBorder(),
      ),
      onSubmitted: widget.multiline ? null : (_) => _apply(),
    );
    if (widget.dense && !_changed) return field;
    return Padding(
      padding: const EdgeInsets.only(bottom: UriSpace.xs),
      child: Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
        field,
        if (_changed)
          TextButton(
            key: ValueKey('${(widget.fieldKey as ValueKey).value}-apply'),
            onPressed: widget.enabled ? _apply : null,
            child: const Text('Apply'),
          ),
      ]),
    );
  }
}
