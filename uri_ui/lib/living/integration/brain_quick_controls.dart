import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import 'oi_conversation.dart';
import 'qc_toggle.dart';

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
///   the controls say so, and an unqualified combination is listed disabled
///   with its reason, never offered.
/// * Push-to-enable (UI-CONTROLS-TYPO-20261018): Thinking and Vision are
///   toggles, Context is a selection ([QcToggle], [QcSegmented]). The
///   enabled glow follows the verified state only: a click asks, the
///   worker's `controls.active` decides what glows.

class QcOption {
  QcOption(this.raw);
  final Map<String, dynamic> raw;
  String get id => raw['id'] as String;
  String get label => raw['label'] as String? ?? id;
  String get summary => raw['summary'] as String? ?? '';
  int get ctx => (raw['ctx'] as num).toInt();
  bool get visionOn => raw['vision_on'] == true;
  bool get qualified => raw['qualified'] == true;

  /// A Quick Controls target: qualified AND offered (an older worker without the field: qualified).
  bool get switchable => qualified && (raw['switchable'] ?? true) == true;
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
    if (o.switchable) return o;
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

/// The choice a push-to-enable toggle makes (UI-CONTROLS-TYPO-20261018):
/// the first qualified, not-current entry of [choices] whose title starts
/// with [want] ('On' / 'Off', or a context label), and the reasons of the
/// entries for [want] that are blocked (shown with the control, never
/// hidden). Works for any choice list ([visionChoices], [contextChoices],
/// and later a Draft list).
({QcChoice? choice, List<String> blocked}) toggleChoice(List<QcChoice> choices, String want) {
  QcChoice? choice;
  final blocked = <String>[];
  for (final ch in choices) {
    if (!ch.title.startsWith(want)) continue;
    if (ch.blocked != null) {
      blocked.add('${ch.title}: ${ch.blocked}');
    } else if (choice == null && ch.target != null && !ch.current) {
      choice = ch;
    }
  }
  return (choice: choice, blocked: blocked);
}

/// How the latest switch this UI asked for ended, for the notice tone and
/// the controls' error look. `restored`: the host went back to the
/// previous setting after the new one failed to start.
enum QcOutcome { none, ok, restored, warning, error }

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
    final (notice, outcome) = _notice(conv, switchState);

    // Thinking: per message, nothing reloads. One click turns it On (think
    // first), the next Off (answer directly). Auto, the default, lets URI
    // decide per message and is chosen from the small menu next to it.
    final thinkingOn = conv.depth == OiDepth.normal || conv.depth == OiDepth.deep;
    final thinkingEnabled = !conv.restarting && !conv.workerExited;
    final controlsRow = <Widget>[
      QcToggle(
        key: const ValueKey('qc-thinking'),
        icon: Icons.psychology_alt_outlined,
        label: 'Thinking',
        status: conv.depth == OiDepth.auto ? 'Auto' : null,
        visual: thinkingOn ? QcVisual.on : QcVisual.off,
        tooltip: thinkingOn
            ? 'Thinking is on: URI thinks before answering your next message. Click to turn it off. Nothing reloads.'
            : conv.depth == OiDepth.auto
                ? 'Thinking is Auto: URI decides for each message. Click to turn it on. Nothing reloads.'
                : 'Thinking is off: URI answers directly (fastest). Click to turn it on. Nothing reloads.',
        onPressed: thinkingEnabled ? () => conv.setDepth(thinkingOn ? OiDepth.fast : OiDepth.normal) : null,
        trailing: _thinkingMenu(context, thinkingEnabled),
      ),
    ];

    if (hasProfiles) {
      final unverified = active == null
          ? pending
              ? 'switching'
              : configured == null
                  ? null
                  : health == 'RECOVERING'
                      ? 'starting'
                      : 'not running'
          : null;
      final errorLook = active == null && !pending && outcome == QcOutcome.error;
      final why = canSwitch
          ? null
          : conv.busy
              ? 'Wait until URI has finished answering.'
              : brainSwitchRefusal('${controls['cannot_switch_reason'] ?? 'UNAVAILABLE'}');

      // Vision: a toggle. Vision and context are coupled by the qualified
      // catalog, so the toggle's choice may change the context too; that is
      // stated in its tooltip and in the confirmation.
      final visionOn = active != null
          ? active['vision_on'] == true
          : configured == null
              ? null
              : configured['vision'] != 'off';
      final vis = visionChoices(options, active);
      final want = visionOn == true ? 'Off' : 'On';
      final vt = visionOn == null ? (choice: null, blocked: const <String>[]) : toggleChoice(vis, want);
      final visTip = why ??
          (visionOn == null
              ? 'The Brain setting is not known yet; Vision can be changed once URI has read it.'
              : vt.choice == null
              ? 'Vision ${want.toLowerCase()} is not available: '
                  '${vt.blocked.isEmpty ? 'no qualified Brain profile offers it.' : vt.blocked.join(' ')}'
              : 'Vision is ${visionOn == true ? 'on: the Brain can read images' : 'off'}. Click to turn it '
                  '${want.toLowerCase()}: ${vt.choice!.note}. The Brain reloads; your conversation stays.'
                  '${vt.blocked.isEmpty ? '' : ' (${vt.blocked.join(' ')})'}');
      controlsRow.add(QcToggle(
        key: const ValueKey('qc-vision'),
        icon: Icons.image_outlined,
        label: 'Vision',
        status: unverified ?? (active == null ? '?' : null),
        visual: pending
            ? QcVisual.loading
            : errorLook
                ? QcVisual.error
                : active != null && active['vision_on'] == true
                    ? QcVisual.on
                    : QcVisual.off,
        tooltip: visTip,
        onPressed: canSwitch && !pending && vt.choice != null
            ? () => _confirmAndSwitch(context, vt.choice!, blocked: vt.blocked)
            : null,
      ));

      // Context: one size at a time, so a selection, not toggles.
      final ctxChoices = contextChoices(options, active);
      final activeCtx = (active?['ctx'] as num?)?.toInt();
      final sizes = {for (final o in options) o.ctx}.toList()..sort();
      controlsRow.add(QcSegmented(
        key: const ValueKey('qc-context'),
        icon: Icons.notes_rounded,
        label: 'Context',
        status: unverified,
        loading: pending,
        error: errorLook,
        tooltip: why ?? 'How much of the conversation the Brain reads at once. Changing it reloads the Brain.',
        segments: [
          for (final ctx in sizes) _contextSegment(ctx, ctxChoices, active, activeCtx, why, canSwitch && !pending, context),
        ],
      ));

      if (pending) {
        final last = (switchState['last'] as Map?)?.cast<String, dynamic>();
        final target = (switchState['target'] as Map?)?.cast<String, dynamic>();
        final fb = last != null && target != null && last['id'] == target['id'] ? last['fallback'] as Map? : null;
        final text = fb != null && fb['result'] == 'IN_PROGRESS'
            ? 'Did not start; going back to ${fb['label'] ?? 'the previous setting'}…'
            : 'Switching to ${target?['label'] ?? 'the new setting'}…';
        controlsRow.add(Container(
          key: const ValueKey('qc-switching'),
          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
          decoration: BoxDecoration(
            border: Border.all(color: c.accent.withValues(alpha: .6)),
            borderRadius: BorderRadius.circular(999),
          ),
          child: Text(text, overflow: TextOverflow.ellipsis, style: QcStyle.text(context, c.accent)),
        ));
      }
    }

    final noticeColor = switch (outcome) {
      QcOutcome.error => c.danger,
      QcOutcome.warning || QcOutcome.restored => c.warning,
      _ => c.inkSoft,
    };
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(spacing: 8, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: controlsRow),
          if (notice != null)
            Padding(
              padding: const EdgeInsets.only(top: 4, left: 4),
              child: Text(notice,
                  key: const ValueKey('qc-notice'),
                  style: Theme.of(context).textTheme.bodySmall!.copyWith(
                      fontSize: UriType.caption, color: noticeColor, height: 1.35)),
            ),
        ],
      ),
    );
  }

  QcSegment _contextSegment(int ctx, List<QcChoice> ctxChoices, Map<String, dynamic>? active, int? activeCtx,
      String? why, bool canSwitch, BuildContext context) {
    final title = ctxLabel(ctx);
    final t = toggleChoice(ctxChoices, title);
    final selected = activeCtx == ctx;
    return QcSegment(
      key: ValueKey('qc-context-$title'),
      label: title,
      selected: selected,
      tooltip: selected
          ? 'Current: ${active!['label'] ?? title}'
          : why ??
              (t.choice == null
                  ? (t.blocked.isEmpty ? 'No qualified Brain profile offers this.' : t.blocked.join(' '))
                  : '${t.choice!.note}. The Brain reloads; your conversation stays.'
                      '${t.blocked.isEmpty ? '' : ' (${t.blocked.join(' ')})'}'),
      onTap: canSwitch && !selected && t.choice != null
          ? () => _confirmAndSwitch(context, t.choice!, blocked: t.blocked)
          : null,
    );
  }

  /// The outcome of this UI's latest switch request, in plain words.
  (String?, QcOutcome) _notice(OiConversation conv, Map<String, dynamic> switchState) {
    if (conv.profileNotice != null) return (conv.profileNotice, QcOutcome.warning);
    final last = (switchState['last'] as Map?)?.cast<String, dynamic>();
    if (last == null || conv.profileRequestId == null || last['id'] != conv.profileRequestId) {
      return (null, QcOutcome.none);
    }
    if (switchState['pending'] == true) return (null, QcOutcome.none);
    final result = last['result'] as String?;
    if (result == null || result == 'IN_PROGRESS' || result == 'ALREADY_ACTIVE') return (null, QcOutcome.none);
    if (result.startsWith('REFUSED_')) {
      return ((last['explain'] as String?) ?? brainSwitchRefusal(result), QcOutcome.warning);
    }
    if (result == 'READY') {
      final s = (last['seconds'] as num?)?.toStringAsFixed(0);
      return (
        s == null ? 'Brain switched. Your conversation is kept.' : 'Brain switched in $s s. Your conversation is kept.',
        QcOutcome.ok
      );
    }
    if (result == 'DEGRADED') {
      return ('Brain switched, but it is running slowly (GPU memory was short).', QcOutcome.warning);
    }
    if (result == 'FAILED') {
      final fb = (last['fallback'] as Map?)?.cast<String, dynamic>();
      final prev = fb?['label'] ?? 'the previous setting';
      if (fb != null && last['restored'] == true) {
        return (
          'The Brain did not start with the new setting, so URI went back to $prev'
              '${fb['result'] == 'DEGRADED' ? ' (running slowly)' : ''}. Your conversation is kept.',
          QcOutcome.restored
        );
      }
      if (fb != null && fb['result'] == 'STOPPED') {
        return ('The new setting did not start and going back was stopped; the Brain is not running.', QcOutcome.error);
      }
      if (fb != null) {
        return (
          'The Brain did not start with the new setting, and going back to $prev failed too. Use Restart Brain.',
          QcOutcome.error
        );
      }
      return ('The Brain did not start with the new setting. Choose another setting or Restart Brain.', QcOutcome.error);
    }
    if (result == 'WAITING_FOR_GPU' || result == 'WAITING_FOR_LEASE' || result == 'RELEASE_WAIT') {
      return ('The new setting is waiting for GPU memory. Choose the previous setting to go back.', QcOutcome.warning);
    }
    if (result == 'STOPPED') return ('The switch was stopped; the Brain is not running.', QcOutcome.error);
    return ('The switch ended without a ready Brain. Choose a setting again or Restart Brain.', QcOutcome.error);
  }

  Widget _thinkingMenu(BuildContext context, bool enabled) {
    final c = UriColors.of(context);
    final conv = conversation;
    return PopupMenuButton<OiDepth>(
      key: const ValueKey('qc-thinking-menu'),
      tooltip: 'Thinking: Auto, On or Off',
      enabled: enabled,
      onSelected: conv.setDepth,
      padding: EdgeInsets.zero,
      itemBuilder: (_) => [
        _item(context, OiDepth.auto, 'Auto', 'URI decides for each message', selected: conv.depth == OiDepth.auto),
        _item(context, OiDepth.normal, 'On', 'Thinks first, within a fixed budget',
            selected: conv.depth == OiDepth.normal),
        _item(context, OiDepth.fast, 'Off', 'Answers directly (fastest)', selected: conv.depth == OiDepth.fast),
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
              style: Theme.of(context).textTheme.bodySmall!.copyWith(fontSize: UriType.caption, color: c.inkFaint),
            ),
          ),
      ],
      child: Padding(
        padding: const EdgeInsets.fromLTRB(0, 3, 6, 3),
        child: Icon(Icons.arrow_drop_down_rounded,
            size: 16,
            color: conv.depth == OiDepth.normal
                ? c.accentInk
                : enabled
                    ? c.inkSoft
                    : c.inkFaint),
      ),
    );
  }

  Future<void> _confirmAndSwitch(BuildContext context, QcChoice choice, {List<String> blocked = const []}) async {
    final target = choice.target;
    if (target == null) return;
    final conv = conversation;
    final controls = conv.brainControls;
    final active = (controls['active'] as Map?)?.cast<String, dynamic>();
    final configured = (controls['configured'] as Map?)?.cast<String, dynamic>();
    final hostState = (conv.brainHealth['host'] as Map?)?['state'];
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => QcSwitchDialog(
        target: target,
        active: active,
        configured: configured,
        blocked: blocked,
        brainStopped: hostState == 'STOPPED',
      ),
    );
    if (ok != true) return;
    // A context the conversation does not fit in is refused by the worker and explained in the notice (R1-02).
    await conv.reconfigureBrain(target.id);
  }

  PopupMenuItem<T> _item<T>(BuildContext context, T value, String title, String subtitle, {bool selected = false}) {
    final c = UriColors.of(context);
    final tt = Theme.of(context).textTheme;
    return PopupMenuItem<T>(
      key: ValueKey('qc-thinking-$title'),
      value: value,
      child: ListTile(
        dense: true,
        contentPadding: EdgeInsets.zero,
        leading: Icon(selected ? Icons.check_rounded : Icons.circle_outlined,
            size: 16, color: selected ? c.success : c.inkFaint),
        title: Text(title, style: tt.bodyMedium!.copyWith(fontSize: UriType.body, color: c.ink, height: 1.3)),
        subtitle: Text(subtitle, style: tt.bodySmall!.copyWith(fontSize: UriType.caption, color: c.inkSoft)),
      ),
    );
  }
}

/// The Brain switch confirmation (UI-CONTROLS-TYPO-20261018): what changes
/// first, then what happens, then the two actions. Readable width, one type
/// scale, a distinct primary action.
class QcSwitchDialog extends StatelessWidget {
  const QcSwitchDialog({
    super.key,
    required this.target,
    this.active,
    this.configured,
    this.blocked = const [],
    this.brainStopped = false,
  });

  final QcOption target;
  final Map<String, dynamic>? active;
  final Map<String, dynamic>? configured;
  final List<String> blocked;
  final bool brainStopped;

  static String gb(int mib) => (mib / 1024).toStringAsFixed(1);

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final tt = Theme.of(context).textTheme;
    final body = tt.bodyMedium!.copyWith(fontSize: UriType.body, color: c.inkSoft, height: 1.45);
    final now = active ?? configured;
    final nowVision = active != null
        ? active!['vision_on'] == true
        : configured == null
            ? null
            : configured!['vision'] != 'off';
    final nowCtx = (now?['ctx'] as num?)?.toInt();
    final nowMib = (active?['required_mib'] as num?)?.toInt();
    // The host goes back automatically only to a qualified profile that was running (ws_brain_host.reconfigure).
    final running = !brainStopped && active != null && active!['qualified'] == true;

    Widget change(String what, String? from, String to) {
      final changed = from != to;
      final strong = tt.labelLarge!.copyWith(fontSize: UriType.body, color: changed ? c.accentInk : c.inkSoft);
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 3),
        child: Row(children: [
          SizedBox(width: 92, child: Text(what, style: body.copyWith(color: c.inkFaint))),
          if (from != null && changed) ...[
            Text(from, style: body),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 6),
              child: Icon(Icons.arrow_forward_rounded, size: 14, color: c.inkFaint),
            ),
          ],
          Flexible(child: Text(changed ? to : '$to (unchanged)', style: strong)),
        ]),
      );
    }

    Widget fact(IconData icon, String text) => Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Padding(padding: const EdgeInsets.only(top: 2), child: Icon(icon, size: 16, color: c.inkFaint)),
            const SizedBox(width: 10),
            Expanded(child: Text(text, style: body)),
          ]),
        );

    return AlertDialog(
      key: const ValueKey('qc-confirm-switch'),
      titlePadding: const EdgeInsets.fromLTRB(24, 22, 24, 0),
      contentPadding: const EdgeInsets.fromLTRB(24, 14, 24, 4),
      actionsPadding: const EdgeInsets.fromLTRB(24, 12, 24, 20),
      title: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 460),
        child: Text('Switch the Brain to ${target.label}?',
            style: tt.titleLarge!.copyWith(fontSize: UriType.titleLarge, color: c.ink)),
      ),
      content: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 460),
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(target.summary, style: body),
            const SizedBox(height: 12),
            Container(
              key: const ValueKey('qc-confirm-changes'),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
              decoration: BoxDecoration(
                color: c.surfaceSunken,
                borderRadius: BorderRadius.circular(UriRadius.sm),
                border: Border.all(color: c.border),
              ),
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                change('Vision', nowVision == null ? null : (nowVision ? 'On' : 'Off'), target.visionOn ? 'On' : 'Off'),
                change('Context', nowCtx == null ? null : ctxLabel(nowCtx), ctxLabel(target.ctx)),
                if (target.requiredMib != null)
                  change('GPU memory', nowMib == null ? null : '${gb(nowMib)} GB', '${gb(target.requiredMib!)} GB'),
              ]),
            ),
            for (final b in blocked) fact(Icons.block_rounded, b),
            fact(Icons.schedule_rounded,
                'The Brain reloads, which takes about half a minute. Messages wait until it is ready.'),
            fact(Icons.chat_bubble_outline_rounded,
                'Your conversation stays: URI keeps it and the Brain reads it again after the switch.'),
            fact(
                Icons.shield_outlined,
                running
                    ? 'If URI sees before the switch that it does not fit in GPU memory, it keeps the current Brain. '
                        'If the new setting fails to start, URI goes back to the current one automatically.'
                    : 'If it does not fit in GPU memory, URI waits. If the new setting fails to start, URI says so '
                        'and you can choose again.'),
            if (brainStopped)
              fact(Icons.play_circle_outline_rounded,
                  'The Brain is stopped now: switching starts it with the new setting.'),
          ]),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
        FilledButton.icon(
          key: const ValueKey('qc-confirm-switch-go'),
          onPressed: () => Navigator.pop(context, true),
          icon: const Icon(Icons.swap_horiz_rounded, size: 18),
          label: const Text('Switch Brain'),
        ),
      ],
    );
  }
}
