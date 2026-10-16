// Text intelligence draft, as the integrated worker reports it
// (`draft.updated` events and `draft_get` / `draft_op` replies).
//
// A draft is language work only: it never carries an action outcome, and
// nothing in the UI may treat it as sent or saved.

class OiDraftBlock {
  const OiDraftBlock({required this.id, required this.role, required this.text});
  final String id;
  final String role;
  final String text;
}

class OiDraftFlag {
  const OiDraftFlag({required this.code, required this.severity, required this.detail});
  final String code;
  final String severity; // error | review
  final String detail;
  bool get isError => severity == 'error';
}

class OiDraftVersion {
  const OiDraftVersion({
    required this.n,
    required this.blocks,
    required this.text,
    required this.op,
    required this.summary,
    required this.instruction,
    required this.changed,
    required this.removed,
    required this.flags,
    required this.missing,
  });

  final int n;
  final List<OiDraftBlock> blocks;
  final String text;
  final String op;
  final String summary;
  final String instruction;
  final Set<String> changed;
  final List<String> removed;
  final List<OiDraftFlag> flags;
  final List<String> missing;

  static OiDraftVersion? parse(Object? v) {
    if (v is! Map) return null;
    List<String> strings(Object? x) => [for (final e in (x as List? ?? const [])) if (e is String) e];
    return OiDraftVersion(
      n: (v['n'] as num?)?.toInt() ?? 0,
      blocks: [
        for (final b in (v['blocks'] as List? ?? const []))
          if (b is Map)
            OiDraftBlock(id: '${b['id']}', role: '${b['role']}', text: '${b['text'] ?? ''}'),
      ],
      text: v['text'] as String? ?? '',
      op: v['op'] as String? ?? '',
      summary: v['summary'] as String? ?? '',
      instruction: v['instruction'] as String? ?? '',
      changed: strings(v['changed']).toSet(),
      removed: strings(v['removed']),
      flags: [
        for (final f in (v['flags'] as List? ?? const []))
          if (f is Map)
            OiDraftFlag(
              code: '${f['code']}',
              severity: '${f['severity']}',
              detail: '${f['detail'] ?? ''}',
            ),
      ],
      missing: strings(v['missing']),
    );
  }
}

class OiDraft {
  const OiDraft({
    required this.draftId,
    required this.docType,
    required this.source,
    required this.originalText,
    required this.position,
    required this.count,
    required this.canUndo,
    required this.canRedo,
    required this.current,
    this.first,
    this.previous,
    this.pendingQuestion,
    this.replacedDocType,
  });

  final String draftId;
  final String docType;

  /// The input that created the draft: `{"source": "typed"}` or the
  /// transcript envelope (`raw`, `engine`, `simulated`, ...).
  final Map<String, dynamic> source;

  /// The user's first words, verbatim (the raw transcript for speech).
  final String originalText;
  final int position;
  final int count;
  final bool canUndo;
  final bool canRedo;
  final OiDraftVersion current;
  final OiDraftVersion? first;
  final OiDraftVersion? previous;
  final String? pendingQuestion;

  /// UIV2-F1: set on the first version of a draft that replaced an open
  /// one; Undo brings that one back (worker `replaced`).
  final String? replacedDocType;

  bool get fromTranscript => source['source'] == 'transcript';
  bool get simulatedTranscript => fromTranscript && source['simulated'] == true;

  /// "Typed", "Simulated transcript" or "Transcript · `engine`". A real
  /// recogniser is named; a simulated one is always labelled as such.
  String get sourceLabel {
    final base = !fromTranscript
        ? 'Typed'
        : simulatedTranscript
            ? 'Simulated transcript'
            : 'Transcript · ${source['engine'] ?? 'unknown engine'}';
    return source['mode'] == 'dictation' ? '$base · Dictation' : base;
  }

  static OiDraft? parse(Object? d) {
    if (d is! Map) return null;
    final cur = OiDraftVersion.parse(d['current']);
    if (cur == null) return null;
    return OiDraft(
      draftId: '${d['draft_id']}',
      docType: d['doc_type'] as String? ?? 'document',
      source: (d['source'] as Map?)?.cast<String, dynamic>() ?? const {'source': 'typed'},
      originalText: d['original_text'] as String? ?? '',
      position: (d['position'] as num?)?.toInt() ?? 1,
      count: (d['count'] as num?)?.toInt() ?? 1,
      canUndo: d['can_undo'] == true,
      canRedo: d['can_redo'] == true,
      current: cur,
      first: OiDraftVersion.parse(d['first']),
      previous: OiDraftVersion.parse(d['previous']),
      pendingQuestion: d['pending_question'] as String?,
      replacedDocType: d['replaced'] is Map ? ((d['replaced'] as Map)['doc_type'] as String? ?? 'document') : null,
    );
  }
}

/// One word-level difference segment.
class DiffSegment {
  const DiffSegment(this.text, this.kind);
  final String text;
  final DiffKind kind;
}

enum DiffKind { same, added, removed }

/// Word-level diff (LCS over whitespace-separated tokens; whitespace is kept
/// with the token before it). Bounded: very long texts fall back to a
/// whole-text replacement rather than an O(n*m) table that could stall the UI.
List<DiffSegment> wordDiff(String before, String after, {int maxTokens = 1500}) {
  List<String> tok(String s) => RegExp(r'\S+\s*|\s+').allMatches(s).map((m) => m.group(0)!).toList();
  final a = tok(before), b = tok(after);
  if (a.length > maxTokens || b.length > maxTokens) {
    return [
      if (before.isNotEmpty) DiffSegment(before, DiffKind.removed),
      if (after.isNotEmpty) DiffSegment(after, DiffKind.added),
    ];
  }
  String norm(String t) => t.trim();
  // A removed word keeps one space, never its line break: otherwise the replacement that follows it is pushed onto
  // a new line (real-app finding, TI live run 2026-10-09).
  String gone(String t) => t.trimRight().isEmpty ? '' : '${t.trimRight()} ';
  final n = a.length, m = b.length;
  final lcs = List.generate(n + 1, (_) => List<int>.filled(m + 1, 0));
  for (var i = n - 1; i >= 0; i--) {
    for (var j = m - 1; j >= 0; j--) {
      lcs[i][j] = norm(a[i]) == norm(b[j]) ? lcs[i + 1][j + 1] + 1 : (lcs[i + 1][j] >= lcs[i][j + 1] ? lcs[i + 1][j] : lcs[i][j + 1]);
    }
  }
  final out = <DiffSegment>[];
  void add(String t, DiffKind k) {
    if (out.isNotEmpty && out.last.kind == k) {
      out[out.length - 1] = DiffSegment(out.last.text + t, k);
    } else {
      out.add(DiffSegment(t, k));
    }
  }

  var i = 0, j = 0;
  while (i < n && j < m) {
    if (norm(a[i]) == norm(b[j])) {
      add(b[j], DiffKind.same);
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) {
      add(gone(a[i++]), DiffKind.removed);
    } else {
      add(b[j++], DiffKind.added);
    }
  }
  while (i < n) {
    add(gone(a[i++]), DiffKind.removed);
  }
  while (j < m) {
    add(b[j++], DiffKind.added);
  }
  return out;
}
