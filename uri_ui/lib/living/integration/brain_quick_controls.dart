import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import 'oi_conversation.dart';

/// Brain Quick Controls (BRAIN-QC-20261018): Thinking, Vision and Context
/// under the chat box.
///
/// * Thinking is per message (turn depth: Off = fast, On = normal, Auto =
///   URI decides). Nothing reloads. The chip also says what the latest
///   answer actually did (its tier), not only what was asked.
/// * Vision and Context choose a qualified Brain profile from the worker's
///   `brain_health.controls`. A change is a controlled Brain reload, asked
///   for only after the user confirmed it; the conversation stays.
/// * Truthfulness: a value is shown as current only when the worker verified
///   the running Brain against it (`controls.active`). While a switch runs
///   the chips say so, and an unqualified combination is listed disabled
///   with its reason, never offered.

class QcOption {
  QcOption(this.raw);
  final Map<String, dynamic> raw;
  String get id => raw['id'] as String;
  String get label => raw['label'] as String? ?? id;
  String get summary => raw['summary'] as String? ?? '';
  int get ctx => (raw['ctx'] as num).toInt();
  bool get visionOn => raw['vision_on'] == true;
  bool get qualified => raw['qualified'] == true;
  String? get reason => raw['reason'] as String?;
  int? get requiredMib => (raw['required_mib'] as num?)?.toInt();
}

/// One menu entry: what choosing it would load, or why it cannot.
class QcChoice {
  const QcChoice({required this.title, this.target, this.note, this.blocked, this.current = false});
  final String title;
  final QcOption? target;
  final String? note;
  final String? blocked;
  final bool current;
}

String ctxLabel(int ctx) => '${ctx ~/ 1024}K';

List<QcOption> qcOptions(Map<String, dynamic> controls) => [
      for (final o in (controls['options'] as List? ?? const []))
        if (o is Map && o['id'] is String && o['ctx'] is num) QcOption(o.cast<String, dynamic>()),
    ];

QcOption? _firstQualified(Iterable<QcOption> xs) {
  for (final o in xs) {
    if (o.qualified) return o;
  }
  return null;
}

QcOption? _firstUnqualified(Iterable<QcOption> xs) {
  for (final o in xs) {
    if (!o.qualified) return o;
  }
  return null;
}

/// Vision On / Off from the profile now verified as running ([active]).
/// Prefers keeping the context; when that combination is not qualified, the
/// qualified profile with the asked vision is offered and the menu says that
/// the context changes too.
List<QcChoice> visionChoices(List<QcOption> options, Map<String, dynamic>? active) {
  final out = <QcChoice>[];
  final activeOn = active?['vision_on'] == true;
  final activeCtx = (active?['ctx'] as num?)?.toInt();
  for (final on in [true, false]) {
    final title = on ? 'On' : 'Off';
    if (active != null && activeOn == on) {
      out.add(QcChoice(title: title, current: true, note: 'Current: ${active['label'] ?? ''}'));
      continue;
    }
    final same = options.where((o) => o.visionOn == on && (activeCtx == null || o.ctx == activeCtx));
    final exact = _firstQualified(same);
    if (exact != null) {
      out.add(QcChoice(title: title, target: exact, note: '${exact.label}: ${exact.summary}'));
      continue;
    }
    final blocked = _firstUnqualified(same);
    final other = _firstQualified(options.where((o) => o.visionOn == on));
    if (blocked != null && activeCtx != null) {
      out.add(QcChoice(title: '$title at ${ctxLabel(activeCtx)}', blocked: blocked.reason ?? 'Not qualified.'));
    }
    if (other != null) {
      out.add(QcChoice(
          title: title,
          target: other,
          note: activeCtx != null && other.ctx != activeCtx
              ? 'Also changes context to ${ctxLabel(other.ctx)} (${other.label})'
              : '${other.label}: ${other.summary}'));
    } else if (blocked == null) {
      out.add(QcChoice(title: title, blocked: 'No qualified Brain profile offers this.'));
    }
  }
  return out;
}

/// Context sizes known to the catalog. Prefers keeping vision as it is; when
/// that combination is not qualified, the qualified profile with that context
/// is offered and the menu says that vision changes too.
List<QcChoice> contextChoices(List<QcOption> options, Map<String, dynamic>? active) {
  final out = <QcChoice>[];
  final activeOn = active == null ? null : active['vision_on'] == true;
  final activeCtx = (active?['ctx'] as num?)?.toInt();
  final sizes = {for (final o in options) o.ctx}.toList()..sort();
  for (final ctx in sizes) {
    final title = ctxLabel(ctx);
    if (activeCtx == ctx) {
      out.add(QcChoice(title: title, current: true, note: 'Current: ${active!['label'] ?? ''}'));
      continue;
    }
    final same = options.where((o) => o.ctx == ctx && (activeOn == null || o.visionOn == activeOn));
    final exact = _firstQualified(same);
    if (exact != null) {
      out.add(QcChoice(title: title, target: exact, note: '${exact.label}: ${exact.summary}'));
      continue;
    }
    final blocked = _firstUnqualified(same);
    final other = _firstQualified(options.where((o) => o.ctx == ctx));
    if (blocked != null) {
      out.add(QcChoice(
          title: '$title with vision ${activeOn == true ? 'on' : 'off'}',
          blocked: blocked.reason ?? 'Not qualified.'));
    }
    if (other != null) {
      out.add(QcChoice(
          title: title,
          target: other,
          note: activeOn != null && other.visionOn != activeOn
              ? 'Turns vision ${other.visionOn ? 'on' : 'off'} (${other.label})'
              : '${other.label}: ${other.summary}'));
    } else if (blocked == null) {
      out.add(QcChoice(title: title, blocked: 'No qualified Brain profile offers this.'));
    }
  }
  return out;
}

String thinkingLabel(OiDepth d) => switch (d) {
      OiDepth.auto => 'Auto',
      OiDepth.fast => 'Off',
      OiDepth.normal => 'On',
      OiDepth.deep => 'Deep',
    };

class BrainQuickControls extends StatelessWidget {
  const BrainQuickControls({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final conv = conversation;
    final controls = conv.brainControls;
    final options = qcOptions(controls);
    final active = (controls['active'] as Map?)?.cast<String, dynamic>();
    final switchState = (controls['switch'] as Map?)?.cast<String, dynamic>() ?? const {};
    final pending = switchState['pending'] == true;
    final canSwitch = controls['can_switch'] == true && !conv.busy && !conv.restarting && !conv.workerExited;
    final hasProfiles = options.isNotEmpty;
    final configured = (controls['configured'] as Map?)?.cast<String, dynamic>();
    final health = conv.healthState;
    final style = TextStyle(color: c.inkSoft, fontSize: 12);

    String unconfirmed(String value) =>
        '$value (${health == 'RECOVERING' ? 'starting' : 'not running'})';

    final chips = <Widget>[
      _MenuChip<OiDepth>(
        key: const ValueKey('qc-thinking'),
        icon: Icons.psychology_alt_outlined,
        label: 'Thinking: ${thinkingLabel(conv.depth)}',
        tooltip: 'Thinking applies to your next message. Nothing reloads.',
        enabled: !conv.restarting && !conv.workerExited,
        onSelected: conv.setDepth,
        items: [
          _item(context, OiDepth.auto, 'Auto', 'URI decides for each message', selected: conv.depth == OiDepth.auto),
          _item(context, OiDepth.fast, 'Off', 'Answers directly (fastest)', selected: conv.depth == OiDepth.fast),
          _item(context, OiDepth.normal, 'On', 'Thinks first, within a fixed budget',
              selected: conv.depth == OiDepth.normal),
          if (conv.lastAnswerTier != null)
            PopupMenuItem<OiDepth>(
              enabled: false,
              height: 28,
              child: Text(
                conv.lastAnswerTier == 'NORMAL'
                    ? 'Last answer: thought first'
                    : conv.lastAnswerTier == 'FAST'
                        ? 'Last answer: answered directly'
                        : 'Last answer: ${conv.lastAnswerTier}',
                key: const ValueKey('qc-thinking-last'),
                style: TextStyle(color: c.inkFaint, fontSize: 11),
              ),
            ),
        ],
      ),
    ];

    if (hasProfiles && pending) {
      final target = (switchState['target'] as Map?)?['label'] ?? 'the new setting';
      chips.add(Container(
        key: const ValueKey('qc-switching'),
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          border: Border.all(color: c.accent.withValues(alpha: .6)),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          SizedBox(width: 10, height: 10, child: CircularProgressIndicator(strokeWidth: 1.5, color: c.accent)),
          const SizedBox(width: 6),
          Flexible(
            child: Text('Switching to $target…',
                overflow: TextOverflow.ellipsis, style: TextStyle(color: c.accent, fontSize: 12)),
          ),
        ]),
      ));
    } else if (hasProfiles) {
      final vis = visionChoices(options, active);
      final ctx = contextChoices(options, active);
      final visValue = active != null
          ? (active['vision_on'] == true ? 'On' : 'Off')
          : configured == null
              ? '?'
              : unconfirmed(configured['vision'] == 'off' ? 'Off' : 'On');
      final ctxValue = active != null
          ? ctxLabel((active['ctx'] as num).toInt())
          : configured == null || configured['ctx'] is! num
              ? '?'
              : unconfirmed(ctxLabel((configured['ctx'] as num).toInt()));
      final why = canSwitch
          ? null
          : conv.busy
              ? 'Wait until URI has finished answering.'
              : brainSwitchRefusal('${controls['cannot_switch_reason'] ?? 'UNAVAILABLE'}');
      chips.add(_profileChip(context, const ValueKey('qc-vision'), Icons.image_outlined, 'Vision: $visValue', vis,
          canSwitch, why ?? 'Vision lets the Brain read images. Changing it reloads the Brain.'));
      chips.add(_profileChip(context, const ValueKey('qc-context'), Icons.notes_rounded, 'Context: $ctxValue', ctx,
          canSwitch, why ?? 'How much of the conversation the Brain reads at once. Changing it reloads the Brain.'));
    }

    final notice = _notice(conv, switchState);
    return Padding(
      padding: const EdgeInsets.only(top: 2),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(spacing: 6, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: chips),
          if (notice != null)
            Padding(
              padding: const EdgeInsets.only(top: 2, left: 4),
              child: Text(notice, key: const ValueKey('qc-notice'), style: style.copyWith(fontSize: 11)),
            ),
        ],
      ),
    );
  }

  /// The outcome of this UI's latest switch request, in plain words.
  String? _notice(OiConversation conv, Map<String, dynamic> switchState) {
    if (conv.profileNotice != null) return conv.profileNotice;
    final last = (switchState['last'] as Map?)?.cast<String, dynamic>();
    if (last == null || conv.profileRequestId == null || last['id'] != conv.profileRequestId) return null;
    if (switchState['pending'] == true) return null;
    final result = last['result'] as String?;
    if (result == null || result == 'IN_PROGRESS' || result == 'ALREADY_ACTIVE') return null;
    if (result.startsWith('REFUSED_')) {
      return (last['explain'] as String?) ?? brainSwitchRefusal(result);
    }
    if (result == 'READY') {
      final s = (last['seconds'] as num?)?.toStringAsFixed(0);
      return s == null ? 'Brain switched. Your conversation is kept.' : 'Brain switched in $s s. Your conversation is kept.';
    }
    if (result == 'DEGRADED') return 'Brain switched, but it is running slowly (GPU memory was short).';
    if (result == 'FAILED') return 'The Brain did not start with the new setting. Choose another setting or Restart Brain.';
    if (result == 'WAITING_FOR_GPU' || result == 'WAITING_FOR_LEASE' || result == 'RELEASE_WAIT') {
      return 'The new setting is waiting for GPU memory. Choose the previous setting to go back.';
    }
    if (result == 'STOPPED') return 'The switch was stopped; the Brain is not running.';
    return 'The switch ended without a ready Brain. Choose a setting again or Restart Brain.';
  }

  Widget _profileChip(BuildContext context, Key key, IconData icon, String label, List<QcChoice> choices,
      bool canSwitch, String tooltip) {
    final c = UriColors.of(context);
    return _MenuChip<QcChoice>(
      key: key,
      icon: icon,
      label: label,
      tooltip: tooltip,
      enabled: canSwitch,
      onSelected: (choice) => _confirmAndSwitch(context, choice),
      items: [
        for (final ch in choices)
          PopupMenuItem<QcChoice>(
            key: ValueKey('${(key as ValueKey).value}-${ch.title}'),
            value: ch,
            enabled: ch.target != null && !ch.current,
            child: ListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              leading: Icon(
                ch.current
                    ? Icons.check_rounded
                    : ch.blocked != null
                        ? Icons.block_rounded
                        : Icons.swap_horiz_rounded,
                size: 16,
                color: ch.current ? c.success : ch.blocked != null ? c.inkFaint : c.accent,
              ),
              title: Text(ch.title, style: TextStyle(fontSize: 13, color: ch.blocked != null ? c.inkFaint : c.ink)),
              subtitle: Text(ch.blocked ?? ch.note ?? '', style: TextStyle(fontSize: 11, color: c.inkSoft)),
            ),
          ),
      ],
    );
  }

  Future<void> _confirmAndSwitch(BuildContext context, QcChoice choice) async {
    final target = choice.target;
    if (target == null) return;
    final conv = conversation;
    final controls = conv.brainControls;
    final active = (controls['active'] as Map?)?.cast<String, dynamic>();
    final nowMib = (active?['required_mib'] as num?)?.toInt();
    final hostState = (conv.brainHealth['host'] as Map?)?['state'];
    String gb(int mib) => (mib / 1024).toStringAsFixed(1);
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        key: const ValueKey('qc-confirm-switch'),
        title: Text('Switch the Brain to ${target.label}?'),
        content: Text([
          target.summary,
          'The Brain reloads, which takes about half a minute. Messages wait until it is ready.',
          'Your conversation stays: URI keeps it and the Brain reads it again after the switch.',
          if (target.requiredMib != null)
            'GPU memory: ${gb(target.requiredMib!)} GB${nowMib != null ? ' (now ${gb(nowMib)} GB)' : ''}. '
                'If URI sees before the switch that it does not fit, it keeps the current Brain. If the new '
                'setting then fails to start or waits for memory, choose the previous setting again.',
          if (hostState == 'STOPPED') 'The Brain is stopped now: switching starts it with the new setting.',
        ].join('\n\n')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            key: const ValueKey('qc-confirm-switch-go'),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Switch'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    // A context the conversation does not fit in is refused by the worker and explained in the notice (R1-02).
    await conv.reconfigureBrain(target.id);
  }

  PopupMenuItem<T> _item<T>(BuildContext context, T value, String title, String subtitle, {bool selected = false}) {
    final c = UriColors.of(context);
    return PopupMenuItem<T>(
      key: ValueKey('qc-thinking-$title'),
      value: value,
      child: ListTile(
        dense: true,
        contentPadding: EdgeInsets.zero,
        leading: Icon(selected ? Icons.check_rounded : Icons.circle_outlined, size: 16,
            color: selected ? c.success : c.inkFaint),
        title: Text(title, style: TextStyle(fontSize: 13, color: c.ink)),
        subtitle: Text(subtitle, style: TextStyle(fontSize: 11, color: c.inkSoft)),
      ),
    );
  }
}

class _MenuChip<T> extends StatelessWidget {
  const _MenuChip({
    super.key,
    required this.icon,
    required this.label,
    required this.tooltip,
    required this.enabled,
    required this.onSelected,
    required this.items,
  });
  final IconData icon;
  final String label;
  final String tooltip;
  final bool enabled;
  final ValueChanged<T> onSelected;
  final List<PopupMenuEntry<T>> items;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final tone = enabled ? c.inkSoft : c.inkFaint;
    return ConstrainedBox(
      constraints: const BoxConstraints(maxWidth: 240),
      child: PopupMenuButton<T>(
        tooltip: tooltip,
        enabled: enabled,
        onSelected: onSelected,
        itemBuilder: (_) => items,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
          decoration: BoxDecoration(
            border: Border.all(color: c.border),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Icon(icon, size: 14, color: tone),
            const SizedBox(width: 4),
            Flexible(
              child: Text(label, overflow: TextOverflow.ellipsis, style: TextStyle(color: tone, fontSize: 12)),
            ),
            Icon(Icons.arrow_drop_down_rounded, size: 16, color: tone),
          ]),
        ),
      ),
    );
  }
}
