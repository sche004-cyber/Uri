import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../assist/assist_controller.dart';
import 'oi_conversation.dart';
import 'qc_toggle.dart';

/// Brain Quick Controls under the chat box: exactly three ON / OFF toggles
/// (owner decision 2026-10-21, URI-CONTROLS-3), each switched on its own:
///
/// * Thinking is per message (turn depth: Off = fast, On = normal). Nothing
///   reloads. The tooltip also says what the latest answer actually did
///   (its tier), not only what was asked. The choice is kept across a
///   restart (LivingApp stores it).
/// * Vision chooses a qualified Brain profile from the worker's
///   `brain_health.controls`. A change is a controlled Brain reload, asked
///   for only after the user confirmed it; the conversation stays.
/// * URI Assist is the worker's Assist session (`uri_assist`). On starts the
///   consent flow (the Assist view, where the user chooses what URI may see:
///   nothing is seen before a grant); Off stops the session at once (one tap,
///   A0 spec). It glows only while the worker reports a grant.
/// * Truthfulness: a value is shown as current only when the worker verified
///   it (`controls.active` for Vision, the Assist status for URI Assist).
///   While a switch runs the controls say so, and an unqualified choice is
///   disabled with its reason, never offered.
/// * Push-to-enable (UI-CONTROLS-TYPO-20261018, [QcToggle]): a click asks,
///   the worker's verified state decides what glows. Keyboard (Tab, Enter,
///   Space) and screen readers operate every toggle (review R1-01).
///
/// Context size and the speculative draft are no longer quick controls
/// (owner decision: exactly these three). The Vision toggle may still change
/// the context, because vision and context are coupled by the qualified
/// catalog; its tooltip and the confirmation say so.

class QcOption {
  QcOption(this.raw);
  final Map<String, dynamic> raw;
  String get id => raw['id'] as String;
  String get label => raw['label'] as String? ?? id;
  String get summary => raw['summary'] as String? ?? '';
  int get ctx => (raw['ctx'] as num).toInt();
  bool get visionOn => raw['vision_on'] == true;
  bool get mtp => raw['mtp'] == true;
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

/// Closure D2/D6: while URI Assist holds a grant ([locked]), a choice that
/// would turn vision off is shown disabled with the reason.
List<QcChoice> lockVision(List<QcChoice> xs, bool locked, Map<String, dynamic>? active) {
  if (!locked || active?['vision_on'] != true) return xs;
  return [
    for (final x in xs)
      if (x.target != null && !x.target!.visionOn)
        QcChoice(title: x.title, blocked: 'A URI Assist session is open, so URI keeps vision on. End it first.')
      else
        x,
  ];
}

/// The host and the worker disagree about the running Brain (closure D3,
/// QC-F9): what to tell the user, or null when they agree.
String? mismatchNotice(Map<String, dynamic> controls) {
  final m = (controls['mismatch'] as Map?)?.cast<String, dynamic>();
  if (m == null) return null;
  final host = m['host'] ?? 'an unknown setting';
  if (m['code'] == 'HOST_SELECTION_ERROR') {
    return 'The Brain host could not save its setting (${m['selection_error']}). The Brain works now; if URI '
        'stops recognising it, Restart Brain.';
  }
  if (m['code'] == 'PROFILE_NOT_SELECTABLE' || m['host_qualified'] == false) {
    return 'The Brain host runs $host, which is not a qualified choice. URI does not use it: choose a setting or '
        'Restart Brain.';
  }
  return 'The Brain host runs $host but URI expects ${m['worker'] ?? 'another setting'}. URI does not use it '
      'until they match: choose a setting or Restart Brain.';
}

String thinkingLabel(OiDepth d) => switch (d) {
      OiDepth.auto => 'Auto',
      OiDepth.fast => 'Off',
      OiDepth.normal => 'On',
      OiDepth.deep => 'Deep',
    };

/// The choice a push-to-enable toggle makes (UI-CONTROLS-TYPO-20261018):
/// the first qualified, not-current entry of [choices] whose title starts
/// with [want] ('On' / 'Off'), and the reasons of the entries for [want]
/// that are blocked (shown with the control, never hidden).
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
  const BrainQuickControls({super.key, required this.conversation, this.assist, this.openAssist});
  final OiConversation conversation;

  /// The worker's URI Assist mirror (null in the mock preview: the toggle is
  /// then shown unavailable, with the reason).
  final AssistController? assist;

  /// Shows the Assist view, where the user grants what URI may see.
  final VoidCallback? openAssist;

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
    // first), the next Off (answer directly).
    final thinkingOn = conv.depth == OiDepth.normal || conv.depth == OiDepth.deep;
    final thinkingEnabled = !conv.restarting && !conv.workerExited;
    final tier = conv.lastAnswerTier;
    final lastAnswer = tier == null
        ? ''
        : ' Last answer: ${tier == 'NORMAL' ? 'thought first' : tier == 'FAST' ? 'answered directly' : tier}.';
    final controlsRow = <Widget>[
      QcToggle(
        key: const ValueKey('qc-thinking'),
        icon: Icons.psychology_alt_outlined,
        label: 'Thinking',
        // An older caller may still have set Auto; it is shown as what it is, never as On or Off.
        status: conv.depth == OiDepth.auto ? 'Auto' : null,
        visual: thinkingOn ? QcVisual.on : QcVisual.off,
        tooltip: !thinkingEnabled
            ? 'Thinking can be changed once URI has restarted.'
            : (thinkingOn
                    ? 'Thinking is on: URI thinks before answering your next message. Click to turn it off. '
                        'Nothing reloads.'
                    : 'Thinking is off: URI answers directly (fastest). Click to turn it on. Nothing reloads.') +
                lastAnswer,
        onPressed: thinkingEnabled ? () => conv.setDepth(thinkingOn ? OiDepth.fast : OiDepth.normal) : null,
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
      final locked = controls['vision_locked'] == true;
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
      // Closure D2/D6: while URI Assist holds a grant, a choice that turns vision off is disabled with the reason.
      final vis = lockVision(visionChoices(options, active), locked, active);
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

    // URI Assist: after Vision, so the three controls keep one order.
    controlsRow.add(assist == null
        ? _assistToggle(context, null)
        : ListenableBuilder(listenable: assist!, builder: (ctx, _) => _assistToggle(ctx, assist)));

    final noticeColor = switch (outcome) {
      QcOutcome.error => c.danger,
      QcOutcome.warning || QcOutcome.restored => c.warning,
      _ => c.inkSoft,
    };
    // Closure D3: the host and the worker disagree about the running Brain (not shown while a switch runs).
    final mismatch = pending ? null : mismatchNotice(controls);
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(spacing: 8, runSpacing: 6, crossAxisAlignment: WrapCrossAlignment.center, children: controlsRow),
          if (mismatch != null)
            Padding(
              padding: const EdgeInsets.only(top: 4, left: 4),
              child: Text(mismatch,
                  key: const ValueKey('qc-mismatch'),
                  style: Theme.of(context).textTheme.bodySmall!.copyWith(
                      fontSize: UriType.caption, color: c.warning, height: 1.35)),
            ),
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
      // Review R1-03: the worker's 600 s gate can expire while the host is still going back; that is not a failure.
      final fbResult = '${fb?['result']}';
      if (fb != null && (fbResult == 'IN_PROGRESS' || fbResult.startsWith('WAITING_'))) {
        return ('The Brain did not start with the new setting; URI is still going back to $prev.', QcOutcome.warning);
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

  /// The URI Assist toggle. Its state is the worker's: the Assist status
  /// when this UI has read it, else the worker's own `controls.assist`.
  Widget _assistToggle(BuildContext context, AssistController? a) {
    final conv = conversation;
    final controls = conv.brainControls;
    final worker = (controls['assist'] as Map?)?.cast<String, dynamic>();
    // Review R2-01: the worker's own state (polled with brain health) is the authority. The worker ends a grant by
    // itself (time limit, target lost), so the Assist status this UI read last can be stale: when the two disagree
    // the worker's value is shown and both are read again.
    final workerGranted = worker?['granted'] is bool ? worker!['granted'] as bool : null;
    final mirrorGranted = a != null && a.loaded ? (a.active || a.paused) : null;
    final granted = workerGranted ?? mirrorGranted ?? false;
    final paused = granted && a != null && a.loaded && a.paused;
    if (a != null && workerGranted != null && mirrorGranted != null && workerGranted != mirrorGranted && !a.busy) {
      _resyncAssist(conv, a);
    }
    final String? unavailable = a == null
        ? 'URI Assist needs the URI worker; it is not connected here.'
        : conv.workerExited || conv.restarting || !a.available
            ? 'URI Assist is not available while URI is not running or restarting. A restarted URI starts with '
                'URI Assist off.'
            : controls.isNotEmpty && worker == null
                ? 'URI Assist is not available in this URI worker.'
                : null;
    final err = a?.lastError;
    final String tip;
    if (unavailable != null) {
      tip = unavailable;
    } else if (granted) {
      tip = '${paused ? 'URI Assist is paused' : 'URI Assist is on'}: URI may look only at what you allowed. '
          'Click to stop it; URI forgets what it saw. Vision stays on while URI Assist is on.';
    } else {
      tip = 'URI Assist is off: URI sees nothing on your screen. Click to choose what URI may look at '
          '(a window or the screen); nothing is seen before you allow it.';
    }
    return QcToggle(
      key: const ValueKey('qc-assist'),
      icon: Icons.visibility_outlined,
      label: 'URI Assist',
      status: unavailable != null
          ? 'unavailable'
          : paused
              ? 'Paused'
              : null,
      // Review R2-04: no loading look; Assist asks and checks share the controller's busy flag.
      visual: granted ? QcVisual.on : QcVisual.off,
      tooltip: err == null || unavailable != null ? tip : '$tip (Last refusal: $err.)',
      onPressed: unavailable != null
          ? null
          : granted
              ? () async {
                  await a!.revoke();
                  await conv.refreshHealth();
                }
              : openAssist == null
                  ? null
                  : () {
                      openAssist!();
                      a!.refresh();
                    },
    );
  }

  static bool _resyncing = false;

  /// Reads the worker's Assist status and brain health again after the two disagreed (once at a time).
  static void _resyncAssist(OiConversation conv, AssistController a) {
    if (_resyncing) return;
    _resyncing = true;
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        await a.refresh();
        await conv.refreshHealth();
      } finally {
        _resyncing = false;
      }
    });
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
                if (active != null && (active!['mtp'] == true) != target.mtp)
                  change('Draft', active!['mtp'] == true ? 'On' : 'Off', target.mtp ? 'On' : 'Off'),
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
                        'If the new setting fails to start, URI goes back to the current one automatically. If GPU '
                        'memory is taken by another program meanwhile, URI waits and says so.'
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
