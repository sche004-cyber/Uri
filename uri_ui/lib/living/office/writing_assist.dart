import 'dart:async';

import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../integration/scheduler_client.dart' show SchedulerApiError;

/// Writing Intelligence (plan 16, WI-A): the suggestions service an editor field uses. The Office client implements
/// it over `/writing/*`; tests use a fake.
abstract class WritingService {
  Future<Map<String, dynamic>> writingCheck(String text, {List<String> ignore = const []});
  Future<Map<String, dynamic>> writingApply(String text, List<Map<String, dynamic>> accepted);
  Future<Map<String, dynamic>> writingProofread(String text);
  Future<Map<String, dynamic>> writingRewrite(String text, String tone);
  Future<Map<String, dynamic>> writingComplete(String text);
  Future<void> writingPrewarm();
}

/// Plain words for the service's refusal codes.
String writingRefusal(String code) => switch (code) {
      'BRAIN_UNAVAILABLE' => 'The local Brain is not running, so Proofread and tone changes are off. Spelling checks '
          'still work.',
      'SENSITIVE_TEXT' => 'This text looks like it holds a key, card or ID number, so it is not sent to the Brain. '
          'Spelling checks still work.',
      'SENSITIVE_FIELD' => 'URI does not read this field.',
      'TEXT_TOO_LONG' => 'This text is too long for one check; select a shorter part.',
      'STALE_SUGGESTION' => 'The text changed, so that suggestion no longer fits. Check again.',
      'OVERLAPPING_SUGGESTIONS' => 'Two suggestions change the same words; accept them one at a time.',
      'CANCELLED' => 'Stopped.',
      _ => 'Writing help is not available right now ($code).',
    };

String _spellingStatus(String? code) => switch (code) {
      null || 'ok' => '',
      'SPELL_UNAVAILABLE' => 'Spelling is off: the Windows spell checker is not available. Grammar rules still run.',
      'SPELL_LANGUAGE_UNAVAILABLE' => 'Spelling is off: no English dictionary is installed in Windows.',
      'SPELL_TIMEOUT' => 'Spelling did not answer in time; it will try again.',
      'SPELL_STARTING' => 'Spelling is starting…',
      _ => 'Spelling is off right now.',
    };

/// The suggestion strip under an editor field. It reads the field's text, never changes the document: an accepted
/// suggestion changes the text in the field, and the editor's own Apply sends it to the document as one op.
/// Checks run after a pause in typing; the Brain runs only when a button is pressed.
class WritingStrip extends StatefulWidget {
  const WritingStrip({super.key, required this.controller, required this.service, this.enabled = true,
      this.debounce = const Duration(milliseconds: 700), this.keyPrefix = 'writing', this.brainButtons = true,
      this.hideWhenEmpty = false});
  final TextEditingController controller;
  final WritingService service;
  final bool enabled;
  final Duration debounce;
  final String keyPrefix;
  /// Proofread / Formal / Concise / Finish sentence. Off in the chat composer, where only the quick spelling and
  /// grammar items are shown.
  final bool brainButtons;
  /// Shows nothing at all until there is a suggestion (the composer stays as it was).
  final bool hideWhenEmpty;

  @override
  State<WritingStrip> createState() => _WritingStripState();
}

class _WritingStripState extends State<WritingStrip> {
  Timer? _timer;
  String? _checkedText;                     // the text the suggestions were made for
  List<Map<String, dynamic>> _items = [];
  final Set<String> _dismissed = {};
  final List<String> _undo = [];            // earlier texts, newest last
  String? _status;                          // spelling status or a refusal, in words
  String? _busy;                            // "Proofreading…" while the Brain works
  List<String> _flags = [];                 // meaning checks on a Brain answer, in words (review FB1 R2-01)
  int _gen = 0;
  bool _ownEdit = false;                    // the strip itself is changing the text (accept / undo)

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_changed);
    unawaited(widget.service.writingPrewarm().catchError((_) {}));
    // Review FB3 R2-05: compact strips (table cells, titles) check only once the field is edited, so opening
    // a large table does not send one check per cell.
    if (!widget.hideWhenEmpty) _schedule();
  }

  @override
  void didUpdateWidget(WritingStrip old) {
    super.didUpdateWidget(old);
    if (old.controller != widget.controller) {
      old.controller.removeListener(_changed);
      widget.controller.addListener(_changed);
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    widget.controller.removeListener(_changed);
    super.dispose();
  }

  void _changed() {
    if (widget.controller.text == _checkedText) return;
    // Review FB1 R2-05: Undo restores the text before an accept only while nothing else changed it; any other
    // edit (typing, the composer clearing the field after Send) ends that.
    final clearUndo = !_ownEdit && _undo.isNotEmpty;
    if (_items.isNotEmpty || clearUndo || _flags.isNotEmpty) {
      setState(() {
        _items = [];                                         // never show suggestions for older text
        _flags = [];
        if (clearUndo) _undo.clear();
      });
    }
    _schedule();
  }

  void _schedule() {
    _timer?.cancel();
    if (!widget.enabled) return;
    _timer = Timer(widget.debounce, () => unawaited(_check()));
  }

  String k(String s) => '${widget.keyPrefix}-$s';

  Future<void> _check() async {
    final text = widget.controller.text;
    final gen = ++_gen;
    try {
      // review FB2 R3-03: the newest dismissals win when the list is long (the worker reads at most 200)
      final ignore = _dismissed.toList();
      final r = await widget.service.writingCheck(text,
          ignore: ignore.length > 200 ? ignore.sublist(ignore.length - 200) : ignore);
      if (!mounted || gen != _gen || widget.controller.text != text) return;
      setState(() {
        _checkedText = text;
        _items = [for (final s in (r['suggestions'] as List? ?? const [])) (s as Map).cast<String, dynamic>()];
        _status = _spellingStatus((r['status'] as Map?)?['spelling'] as String?);
      });
      // The spell checker starts in the background (it never holds up typing); check again once it is up.
      if ((r['status'] as Map?)?['spelling'] == 'SPELL_STARTING') {
        _timer?.cancel();
        _timer = Timer(const Duration(seconds: 2), () => unawaited(_check()));
      }
    } on SchedulerApiError catch (e) {
      if (mounted && gen == _gen) setState(() => _status = writingRefusal(e.code));
    } catch (_) {
      if (mounted && gen == _gen) setState(() => _status = null);   // the service is away: show nothing
    }
  }

  Future<void> _brain(String label, Future<Map<String, dynamic>> Function(String) call) async {
    final text = widget.controller.text;
    _timer?.cancel();          // Codex r4 R7-02: a pending typing check must not make the requested answer stale
    final gen = ++_gen;
    setState(() => _busy = label);
    try {
      final r = await call(text);
      if (!mounted || gen != _gen || widget.controller.text != text) return;
      final got = [for (final s in (r['suggestions'] as List? ?? const [])) (s as Map).cast<String, dynamic>()];
      setState(() {
        _checkedText = text;
        _items = got;
        _flags = [for (final f in (r['flags'] as List? ?? const [])) '${(f as Map)['detail'] ?? ''}'];
        _status = got.isEmpty ? ((r['message'] as String?)?.isNotEmpty == true ? r['message'] as String
            : 'No changes suggested.') : null;
      });
    } on SchedulerApiError catch (e) {
      if (mounted) setState(() => _status = writingRefusal(e.code));
    } catch (_) {
      if (mounted) setState(() => _status = writingRefusal('UNAVAILABLE'));
    } finally {
      if (mounted) setState(() => _busy = null);
    }
  }

  Map<String, dynamic> _accepted(Map<String, dynamic> s, [int choice = 0]) => {
        'start': s['start'], 'end': s['end'], 'original': s['original'],
        'replacement': ((s['replacements'] as List?) ?? const ['']).isEmpty ? '' : (s['replacements'] as List)[choice],
      };

  Future<void> _accept(List<Map<String, dynamic>> items) async {
    final text = widget.controller.text;
    if (text != _checkedText || items.isEmpty) return;
    try {
      final r = await widget.service.writingApply(text, items);
      if (!mounted || widget.controller.text != text) return;
      final ids = {for (final i in items) '${i['start']}:${i['end']}:${i['original']}'};
      final next = r['text'] as String;
      // Review FB2 R3-04: the other suggestions stay, moved by the accepted changes (offsets are in characters as
      // the engine counts them, so lengths are counted in runes); any that touched an accepted span is dropped.
      final kept = <Map<String, dynamic>>[];
      for (final s in _items) {
        if (ids.contains('${s['start']}:${s['end']}:${s['original']}')) continue;
        final originalStart = s['start'] as int, originalEnd = s['end'] as int;
        var shift = 0;
        var clash = false;
        for (final a in items) {
          final aStart = a['start'] as int, aEnd = a['end'] as int;
          if (originalStart < aEnd && originalEnd > aStart ||
              (originalStart == originalEnd && originalStart == aStart) ||
              (aStart == aEnd && aStart > originalStart && aStart < originalEnd)) {
            clash = true;
            break;
          }
          if (originalStart >= aEnd) {
            shift += '${a['replacement']}'.runes.length - (aEnd - aStart);
          }
        }
        if (!clash) kept.add({...s, 'start': originalStart + shift, 'end': originalEnd + shift});
      }
      setState(() {
        _undo.add(text);
        _items = kept;
        _checkedText = next;
      });
      _setText(next);
    } on SchedulerApiError catch (e) {
      if (mounted) setState(() => _status = writingRefusal(e.code));
    }
  }

  void _setText(String t) {
    _ownEdit = true;
    try {
      widget.controller.value = TextEditingValue(text: t, selection: TextSelection.collapsed(offset: t.length));
    } finally {
      _ownEdit = false;
    }
  }

  void _dismiss(Map<String, dynamic> s) {
    setState(() {
      _dismissed.add('${s['id']}');
      // Review FB1 R2-06: a dismissed word stays dismissed after earlier text changes (ids carry offsets).
      // (review FB2 R3-03: by word only for spelling, so one dismissed capital or a/an does not hide all others)
      final word = '${s['original']}'.trim().toLowerCase();
      if (s['kind'] == 'spelling' && RegExp(r'\w').hasMatch(word)) _dismissed.add(word);
      _items = [for (final x in _items) if (x['id'] != s['id']) x];
    });
  }

  void _undoLast() {
    if (_undo.isEmpty) return;
    final t = _undo.removeLast();
    setState(() {});
    _setText(t);
  }

  @override
  Widget build(BuildContext context) {
    final colors = UriColors.of(context);
    final on = widget.enabled && _busy == null;
    // There is no "Accept all corrections": every suggestion is applied by its own Accept, after the owner has seen
    // it. Reviews FB3, FB4 and FB5 and driver r4 showed that for free text no bulk set is safe by construction
    // (doubled particles, letter case of units and acronyms, references, paths, names). Bringing back a narrow bulk
    // accept is the owner's usability decision OD-WI-3 (plan 16).
    final small = TextStyle(fontSize: UriType.label, color: colors.inkSoft);
    if (widget.hideWhenEmpty && _items.isEmpty && _undo.isEmpty) return const SizedBox.shrink();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, mainAxisSize: MainAxisSize.min, children: [
      if (widget.brainButtons || _undo.isNotEmpty) Wrap(spacing: UriSpace.xs, runSpacing: 0, crossAxisAlignment: WrapCrossAlignment.center, children: [
        if (widget.brainButtons) ...[
        TextButton(key: ValueKey(k('proofread')), onPressed: on ? () => _brain('Proofreading…',
            widget.service.writingProofread) : null, child: const Text('Proofread')),
        TextButton(key: ValueKey(k('formal')), onPressed: on ? () => _brain('Making it formal…',
            (t) => widget.service.writingRewrite(t, 'formal')) : null, child: const Text('Formal')),
        TextButton(key: ValueKey(k('concise')), onPressed: on ? () => _brain('Making it concise…',
            (t) => widget.service.writingRewrite(t, 'concise')) : null, child: const Text('Concise')),
        TextButton(key: ValueKey(k('complete')), onPressed: on ? () => _brain('Finishing the sentence…',
            widget.service.writingComplete) : null, child: const Text('Finish sentence')),
        ],
        if (_undo.isNotEmpty)
          TextButton(key: ValueKey(k('undo')), onPressed: _undoLast, child: const Text('Undo')),
      ]),
      if (_busy != null) Text(_busy!, key: ValueKey(k('busy')), style: small),
      if (_status != null && _status!.isNotEmpty) Text(_status!, key: ValueKey(k('status')), style: small),
      if (_flags.isNotEmpty)
        Text('Check before accepting: ${_flags.join('; ')}', key: ValueKey(k('flags')),
            style: TextStyle(fontSize: UriType.label, color: colors.warning)),
      for (final (i, s) in _items.take(8).indexed) _row(context, i, s),
      if (_items.length > 8) Text('${_items.length - 8} more after these.', style: small),
    ]);
  }

  Widget _row(BuildContext context, int i, Map<String, dynamic> s) {
    final colors = UriColors.of(context);
    final reps = [for (final r in (s['replacements'] as List? ?? const [])) '$r'];
    final rewrite = s['class'] == 'rewrite';
    final original = '${s['original']}';
    final shown = original.trim().isEmpty ? '(add)' : original.length > 60 ? '${original.substring(0, 60)}…' : original;
    String rep(String r) => r.trim().isEmpty ? '(remove)' : r.length > 120 ? '${r.substring(0, 120)}…' : r;
    return Container(
      key: ValueKey(k('item-$i')),
      margin: const EdgeInsets.only(top: UriSpace.xs),
      padding: const EdgeInsets.all(UriSpace.xs),
      decoration: BoxDecoration(
        color: rewrite ? colors.warningSoft.withValues(alpha: .5) : colors.surfaceSunken,
        borderRadius: BorderRadius.circular(UriRadius.sm),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(rewrite ? 'May change meaning: ${s['message'] ?? ''}' : '${s['message'] ?? ''}',
            style: TextStyle(fontSize: UriType.label, color: colors.inkSoft)),
        Text('$shown  →  ${reps.isEmpty ? '' : rep(reps.first)}', style: const TextStyle(fontSize: UriType.label)),
        Wrap(spacing: UriSpace.xs, children: [
          for (final (j, r) in reps.take(3).indexed)
            TextButton(
              key: ValueKey(k('item-$i-accept-$j')),
              onPressed: widget.enabled ? () => _accept([_accepted(s, j)]) : null,
              child: Text(reps.length == 1 ? (rewrite ? 'Use this' : 'Accept') : rep(r)),
            ),
          TextButton(key: ValueKey(k('item-$i-dismiss')), onPressed: () => _dismiss(s), child: const Text('Dismiss')),
        ]),
      ]),
    );
  }
}
