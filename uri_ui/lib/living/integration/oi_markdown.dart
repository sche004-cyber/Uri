import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';

/// Minimal, safe Markdown for Brain answers (WS hardening L-MD).
///
/// Supported: headings (#, ##, ###), paragraphs, bullet and numbered lists,
/// block quotes, fenced code blocks, horizontal rules, and inline **bold**,
/// *italic*, `code` and ~~strike~~. Links show their text only and are never
/// opened; raw HTML is shown as text. Tables are shown as monospace text.
/// No dependency is added: a streaming answer is re-parsed on every delta,
/// and an unclosed marker simply stays literal until it closes.
class OiMarkdown extends StatelessWidget {
  const OiMarkdown(this.source, {super.key, this.color});
  final String source;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final base = TextStyle(color: color ?? c.ink, height: 1.4, fontSize: 14);
    final blocks = parseMarkdownBlocks(source);
    return SelectionArea(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (final b in blocks)
            Padding(
              padding: EdgeInsets.only(bottom: b.kind == MdKind.listItem ? 2 : 6),
              child: _block(b, base, c),
            ),
        ],
      ),
    );
  }

  Widget _block(MdBlock b, TextStyle base, UriColors c) {
    final mono = base.copyWith(fontFamily: 'Consolas', fontSize: 12.5, height: 1.35);
    switch (b.kind) {
      case MdKind.heading:
        final size = <double>[0, 18, 16, 15][b.level.clamp(1, 3)];
        return Text.rich(TextSpan(children: inlineSpans(b.text, base.copyWith(fontSize: size, fontWeight: FontWeight.w700), c)));
      case MdKind.code:
        return Container(
          width: double.infinity,
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(
            color: c.ink.withValues(alpha: 0.06),
            borderRadius: BorderRadius.circular(UriRadius.sm),
            border: Border.all(color: c.ink.withValues(alpha: 0.10)),
          ),
          child: Text(b.text, style: mono),
        );
      case MdKind.table:
        return Text(b.text, style: mono);
      case MdKind.rule:
        return Divider(color: c.ink.withValues(alpha: 0.18), height: 8);
      case MdKind.quote:
        return Container(
          padding: const EdgeInsets.only(left: 10),
          decoration: BoxDecoration(border: Border(left: BorderSide(color: c.accent.withValues(alpha: 0.6), width: 3))),
          child: Text.rich(TextSpan(children: inlineSpans(b.text, base.copyWith(color: c.inkSoft), c))),
        );
      case MdKind.listItem:
        return Padding(
          padding: EdgeInsets.only(left: 14.0 * b.level),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SizedBox(width: 22, child: Text(b.marker, style: base.copyWith(color: c.inkSoft))),
              Expanded(child: Text.rich(TextSpan(children: inlineSpans(b.text, base, c)))),
            ],
          ),
        );
      case MdKind.paragraph:
        return Text.rich(TextSpan(children: inlineSpans(b.text, base, c)));
    }
  }
}

enum MdKind { heading, paragraph, listItem, quote, code, table, rule }

class MdBlock {
  MdBlock(this.kind, this.text, {this.level = 0, this.marker = ''});
  final MdKind kind;
  final String text;
  final int level;
  final String marker;
  @override
  String toString() => '$kind($level,$marker):$text';
}

final _heading = RegExp(r'^(#{1,6})\s+(.*)$');
final _bullet = RegExp(r'^(\s*)[-*+]\s+(.*)$');
final _numbered = RegExp(r'^(\s*)(\d{1,3})[.)]\s+(.*)$');
final _rule = RegExp(r'^\s*([-*_])(\s*\1){2,}\s*$');
final _fence = RegExp(r'^\s*(```|~~~)');

List<MdBlock> parseMarkdownBlocks(String src) {
  final out = <MdBlock>[];
  final lines = src.replaceAll('\r\n', '\n').split('\n');
  final para = <String>[];
  void flush() {
    if (para.isNotEmpty) {
      out.add(MdBlock(MdKind.paragraph, para.join(' ')));
      para.clear();
    }
  }

  var i = 0;
  while (i < lines.length) {
    final line = lines[i];
    if (_fence.hasMatch(line)) {
      flush();
      final code = <String>[];
      i++;
      while (i < lines.length && !_fence.hasMatch(lines[i])) {
        code.add(lines[i]);
        i++;
      }
      out.add(MdBlock(MdKind.code, code.join('\n')));
      i++; // closing fence (or end of a still-streaming block)
      continue;
    }
    if (line.trim().isEmpty) {
      flush();
      i++;
      continue;
    }
    final h = _heading.firstMatch(line);
    if (h != null) {
      flush();
      out.add(MdBlock(MdKind.heading, h.group(2)!.trim(), level: h.group(1)!.length));
      i++;
      continue;
    }
    if (_rule.hasMatch(line) && para.isEmpty) {
      out.add(MdBlock(MdKind.rule, ''));
      i++;
      continue;
    }
    if (line.trimLeft().startsWith('|')) {
      flush();
      final rows = <String>[];
      while (i < lines.length && lines[i].trimLeft().startsWith('|')) {
        rows.add(lines[i].trim());
        i++;
      }
      out.add(MdBlock(MdKind.table, rows.join('\n')));
      continue;
    }
    final b = _bullet.firstMatch(line);
    if (b != null) {
      flush();
      out.add(MdBlock(MdKind.listItem, b.group(2)!, level: b.group(1)!.length ~/ 2, marker: '•'));
      i++;
      continue;
    }
    final n = _numbered.firstMatch(line);
    if (n != null) {
      flush();
      out.add(MdBlock(MdKind.listItem, n.group(3)!, level: n.group(1)!.length ~/ 2, marker: '${n.group(2)}.'));
      i++;
      continue;
    }
    if (line.trimLeft().startsWith('>')) {
      flush();
      final q = <String>[];
      while (i < lines.length && lines[i].trimLeft().startsWith('>')) {
        q.add(lines[i].trimLeft().substring(1).trim());
        i++;
      }
      out.add(MdBlock(MdKind.quote, q.join(' ')));
      continue;
    }
    para.add(line.trim());
    i++;
  }
  flush();
  return out;
}

// Inline: `code` first (its content is literal), then links, bold, strike, italic.
final _inline = RegExp(
  r'`([^`\n]+)`'                               // 1 code
  r'|\[([^\]\n]+)\]\(([^)\s]+)\)'              // 2 link text, 3 url (never opened)
  r'|\*\*(?=\S)(.+?)(?<=\S)\*\*'               // 4 bold **
  r'|(?<![\w])__(?=\S)(.+?)(?<=\S)__(?![\w])'  // 5 bold __
  r'|~~(?=\S)(.+?)(?<=\S)~~'                   // 6 strike
  r'|(?<![\w*])\*(?=[^\s*])(.+?)(?<=[^\s*])\*(?![\w*])' // 7 italic *
  r'|(?<![\w])_(?=[^\s_])(.+?)(?<=[^\s_])_(?![\w])',    // 8 italic _ (not snake_case)
);

List<InlineSpan> inlineSpans(String text, TextStyle base, UriColors c) {
  final spans = <InlineSpan>[];
  var pos = 0;
  for (final m in _inline.allMatches(text)) {
    if (m.start > pos) spans.add(TextSpan(text: text.substring(pos, m.start), style: base));
    if (m.group(1) != null) {
      spans.add(TextSpan(
          text: m.group(1),
          style: base.copyWith(fontFamily: 'Consolas', fontSize: (base.fontSize ?? 14) - 1, backgroundColor: c.ink.withValues(alpha: 0.08))));
    } else if (m.group(2) != null) {
      spans.add(TextSpan(text: m.group(2), style: base.copyWith(decoration: TextDecoration.underline, color: c.accent)));
    } else if (m.group(4) != null || m.group(5) != null) {
      spans.addAll(inlineSpans(m.group(4) ?? m.group(5)!, base.copyWith(fontWeight: FontWeight.w700), c));
    } else if (m.group(6) != null) {
      spans.addAll(inlineSpans(m.group(6)!, base.copyWith(decoration: TextDecoration.lineThrough), c));
    } else {
      spans.addAll(inlineSpans(m.group(7) ?? m.group(8)!, base.copyWith(fontStyle: FontStyle.italic), c));
    }
    pos = m.end;
  }
  if (pos < text.length) spans.add(TextSpan(text: text.substring(pos), style: base));
  return spans;
}

/// Plain text of the rendered markdown (tests, accessibility checks).
String markdownPlainText(String src) => parseMarkdownBlocks(src).map((b) {
      final t = b.kind == MdKind.code || b.kind == MdKind.table ? b.text : _strip(b.text);
      return b.kind == MdKind.listItem ? '${b.marker} $t' : t;
    }).join('\n');

String _strip(String t) => t.replaceAllMapped(_inline, (m) =>
    m.group(1) ?? m.group(2) ?? m.group(4) ?? m.group(5) ?? m.group(6) ?? m.group(7) ?? m.group(8) ?? '');
