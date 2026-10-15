import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../companion/companion_orb.dart';
import '../companion/companion_state.dart';
import '../companion/effects_settings.dart';
import '../widgets/status_badge.dart';
import 'voice_session.dart';
import 'voice_transcript.dart';
import 'voice_waveform.dart';

/// What the presence shows at one instant: the companion, or the shared voice
/// waveform with the companion held small above it.
enum PresenceMode { companion, voice }

/// The resolved presentation. Pure data, produced only by [resolvePresence].
@immutable
class PresenceView {
  const PresenceView({
    required this.mode,
    required this.orbState,
    required this.status,
    required this.statusState,
    this.speaker,
    this.detail,
    this.notice,
    this.simulated = false,
  });

  final PresenceMode mode;

  /// The state the companion expresses. In voice mode this drives the small
  /// identity mark above the waveform.
  final CompanionState orbState;
  final VoiceSpeaker? speaker;

  /// The status line. Always text: colour and motion are never the only
  /// carrier of a state.
  final String status;

  /// The state whose colour and icon the status line uses. Differs from
  /// [orbState] when a pending approval or error is named over the waveform.
  final CompanionState statusState;
  final String? detail;

  /// Why voice stopped, when the user did not stop it.
  final String? notice;
  final bool simulated;

  bool get attention => orbState == CompanionState.awaitingApproval;
}

/// Combines the authoritative companion signal with the voice channel.
///
/// * Speech (the user's or URI's) shows the waveform. Nothing else does: a
///   state that merely claims "speaking" without audio keeps the companion.
/// * Otherwise the companion expresses the signal. Blocking and failure states
///   (error, unavailable, awaiting approval) win over an open listener, which
///   wins over everything else, because it is the most immediate thing the
///   user is doing.
/// * The status line keeps naming a pending approval or an error even while
///   the waveform is up, so voice can never hide something the user must see.
PresenceView resolvePresence(CompanionSignal signal, VoiceSession voice) {
  final simulated = signal.simulated;
  final blocking =
      signal.state == CompanionState.error ||
      signal.state == CompanionState.unavailable ||
      signal.state == CompanionState.awaitingApproval;
  final speaker = voice.speaker;
  if (speaker != null) {
    return PresenceView(
      mode: PresenceMode.voice,
      orbState: speaker == VoiceSpeaker.user
          ? CompanionState.listening
          : CompanionState.speaking,
      speaker: speaker,
      status: blocking
          ? signal.title
          : (speaker == VoiceSpeaker.user ? 'Listening' : 'Speaking'),
      statusState: blocking
          ? signal.state
          : (speaker == VoiceSpeaker.user
                ? CompanionState.listening
                : CompanionState.speaking),
      detail: blocking ? signal.detail : null,
      simulated: simulated,
    );
  }
  final state = blocking
      ? signal.state
      : (voice.phase == VoicePhase.listening
            ? CompanionState.listening
            : signal.state);
  return PresenceView(
    mode: PresenceMode.companion,
    orbState: state,
    status: state == signal.state ? signal.title : state.label,
    statusState: state,
    detail: state == CompanionState.listening && !blocking
        ? null
        : signal.detail,
    notice: voice.notice,
    simulated: simulated,
  );
}

/// Where everything sits for a given size and voice blend [v] (0 companion,
/// 1 voice). Shared by the live widget and the deterministic capture frame so
/// the evidence shows exactly the layout that ships.
@immutable
class PresenceLayout {
  const PresenceLayout({
    required this.orb,
    required this.wave,
    required this.transcript,
    required this.status,
  });

  final Rect orb;
  final Rect wave;
  final Rect transcript;
  final Rect status;

  static const double statusHeight = 46;

  static PresenceLayout of(Size size, double v, {bool showStatus = true}) {
    final w = size.width;
    final statusH = showStatus ? statusHeight : 0.0;
    final area = math.max(0.0, size.height - statusH);
    final e = Curves.easeInOutCubic.transform(v.clamp(0.0, 1.0));

    // Companion mode: the largest centred square, less a small margin so the
    // enlarged companion's atmosphere has faded out before the box edge.
    final s0 = math.min(w, area) * 0.94;
    final full = Rect.fromCenter(
      center: Offset(w / 2, area / 2),
      width: s0,
      height: s0,
    );

    // Voice mode: the companion becomes a small mark at the top, the oval
    // takes the centre and the transcript sits under it.
    final waveW = math.min(w * 0.86, 520.0);
    final waveH = waveW / kVoiceWaveformAspect;
    final fontSize = waveW < 300 ? 13.5 : 15.0;
    final textH = VoiceTranscript.heightFor(fontSize: fontSize);
    final seal = math.min(s0 * 0.42, area * 0.34);
    const gap = 10.0;
    final stack = seal + gap + waveH + gap + textH;
    final top = math.max(0.0, (area - stack) / 2);
    final sealRect = Rect.fromLTWH((w - seal) / 2, top, seal, seal);
    final waveRect = Rect.fromLTWH(
      (w - waveW) / 2,
      sealRect.bottom + gap,
      waveW,
      waveH,
    );
    final textW = math.min(w - 16, waveW + 48);
    final textRect = Rect.fromLTWH(
      (w - textW) / 2,
      waveRect.bottom + gap,
      textW,
      textH,
    );
    return PresenceLayout(
      orb: Rect.lerp(full, sealRect, e)!,
      wave: waveRect,
      transcript: textRect,
      status: Rect.fromLTWH(0, area, w, statusH),
    );
  }

  /// Opacity of the waveform and transcript for blend [v]: they arrive after
  /// the companion has started to make room and leave before it returns.
  static double voiceOpacity(double v) =>
      Curves.easeOut.transform(((v - 0.45) / 0.55).clamp(0.0, 1.0));
}

/// How much larger than its layout box the companion is rendered.
///
/// The shaders draw the companion body at [CompanionIdentityInfo.bodyRadius]
/// of their square and keep the rest for corona, petals or cloud. Rendered at
/// exactly the layout box, the body filled only 30-38% of the available width
/// and read as small in the space it was given. The render square is enlarged
/// so the body spans about half of the box, capped so the widest atmosphere
/// (Sakura's petal field) is not cut short; [SoftDisc] fades the enlarged
/// square out at the box edge so nothing spills visibly beyond it.
double presenceScale(CompanionIdentity id) =>
    (kPresenceBodyFraction / id.bodyRadius).clamp(1.0, 1.4);

/// Target body diameter as a fraction of the companion's layout box.
const double kPresenceBodyFraction = 0.50;

/// The live presence: URI's companion, and the shared voice waveform when
/// someone speaks.
///
/// The companion widget stays mounted for the whole life of the presence, in
/// the same place in the tree, so its clock, its blended expression and its
/// identity are never reset by a voice turn; it only moves and resizes.
class CompanionPresence extends StatefulWidget {
  const CompanionPresence({
    super.key,
    required this.identity,
    required this.signal,
    required this.voice,
    this.showStatus = true,
  });

  final CompanionIdentity identity;
  final CompanionSignal signal;
  final VoiceSessionController voice;
  final bool showStatus;

  @override
  State<CompanionPresence> createState() => _CompanionPresenceState();
}

class _CompanionPresenceState extends State<CompanionPresence> {
  // Remembered only so a fading transcript keeps its label; never read for
  // anything that decides state.
  VoiceSpeaker? _lastSpeaker;

  @override
  Widget build(BuildContext context) {
    final voice = widget.voice;
    final signal = widget.signal;
    final identity = widget.identity;
    final showStatus = widget.showStatus;
    final reduced = EffectsSettings.of(context).reducedMotion;
    return ListenableBuilder(
      listenable: voice,
      builder: (context, _) {
        final session = voice.session;
        final view = resolvePresence(
          signal.copyWith(simulated: signal.simulated || voice.simulated),
          session,
        );
        final target = view.mode == PresenceMode.voice ? 1.0 : 0.0;
        return TweenAnimationBuilder<double>(
          tween: Tween<double>(end: target),
          // Interrupting this mid-way retargets from the current value, so
          // rapid barge-ins and cancellations glide instead of jumping.
          duration: reduced
              ? const Duration(milliseconds: 160)
              : const Duration(milliseconds: 520),
          curve: Curves.linear,
          builder: (context, v, _) {
            return LayoutBuilder(
              builder: (context, box) {
                final layout = PresenceLayout.of(
                  box.biggest,
                  v,
                  showStatus: showStatus,
                );
                // The transcript belongs to the last speaker while it fades.
                final speaker = view.speaker ?? _lastSpeaker;
                if (view.speaker != null) _lastSpeaker = view.speaker;
                return PresenceComposition(
                  layout: layout,
                  orbScale: presenceScale(identity),
                  voiceOpacity: PresenceLayout.voiceOpacity(v),
                  view: view,
                  session: session,
                  transcriptSpeaker: speaker,
                  showStatus: showStatus,
                  orb: CompanionOrb(
                    key: const ValueKey('presence-orb'),
                    identity: identity,
                    state: view.orbState,
                    attention: view.attention,
                  ),
                  waveform: (o) => VoiceWaveform(
                    key: const ValueKey('presence-waveform'),
                    level: voice.level,
                    flux: voice.flux,
                    presence: o,
                  ),
                );
              },
            );
          },
        );
      },
    );
  }
}

/// Places the companion, the waveform, the transcript and the status line.
///
/// Takes the companion and the waveform as widgets so the live presence (with
/// tickers) and the capture harness (with fixed frames) share one layout and
/// one composition: the evidence shows the arrangement that ships.
class PresenceComposition extends StatelessWidget {
  const PresenceComposition({
    super.key,
    required this.layout,
    required this.voiceOpacity,
    required this.view,
    required this.session,
    required this.orb,
    required this.waveform,
    this.orbScale = 1,
    this.transcriptSpeaker,
    this.showStatus = true,
  });

  /// Render size of the companion relative to [PresenceLayout.orb]; see
  /// [presenceScale].
  final double orbScale;

  final PresenceLayout layout;
  final double voiceOpacity;
  final PresenceView view;
  final VoiceSession session;
  final Widget orb;
  final Widget Function(double presence) waveform;
  final VoiceSpeaker? transcriptSpeaker;
  final bool showStatus;

  @override
  Widget build(BuildContext context) {
    final o = voiceOpacity;
    final speaker = transcriptSpeaker;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        Positioned.fromRect(
          rect: Rect.fromCenter(
            center: layout.orb.center,
            width: layout.orb.width * orbScale,
            height: layout.orb.height * orbScale,
          ),
          child: SoftDisc(outer: 1 / orbScale, child: orb),
        ),
        if (o > 0.001) ...[
          Positioned.fromRect(rect: layout.wave, child: waveform(o)),
          if (speaker != null)
            Positioned.fromRect(
              rect: layout.transcript,
              child: Opacity(
                opacity: o,
                child: VoiceTranscript(
                  speaker: speaker,
                  text: session.transcript,
                  spokenChars: session.spokenChars,
                  isFinal: session.transcriptFinal,
                  simulated: view.simulated,
                  fontSize: layout.wave.width < 300 ? 13.5 : 15,
                ),
              ),
            ),
        ],
        if (showStatus)
          Positioned.fromRect(
            rect: layout.status,
            child: PresenceStatus(view: view),
          ),
      ],
    );
  }
}

/// Fades the companion's square render target to a soft disc.
///
/// The companion shaders paint their own sky (the lunar night, the solar
/// dark) to the edge of their square. Over a canvas that is not exactly that
/// sky, the square shows as a box, most visibly when the companion is held
/// small above the waveform. A radial mask removes the corners without
/// touching the shaders themselves; everything inside 72% of the half-side,
/// which holds the body and most of its atmosphere, is untouched.
class SoftDisc extends StatelessWidget {
  const SoftDisc({super.key, required this.child, this.outer = 1});
  final Widget child;

  /// Radius, as a fraction of the half-side, where the fade reaches zero.
  /// Less than 1 when the companion is rendered larger than its box, so the
  /// fade ends at the box edge rather than the render square's.
  final double outer;

  @override
  Widget build(BuildContext context) {
    return ShaderMask(
      blendMode: BlendMode.dstIn,
      shaderCallback: (rect) => RadialGradient(
        colors: <Color>[
          Color(0xFFFFFFFF),
          Color(0xFFFFFFFF),
          Color(0x00FFFFFF),
        ],
        stops: <double>[0.0, outer * 0.72, outer],
      ).createShader(rect),
      child: child,
    );
  }
}

/// The one status line under the presence: the state in words, the detail,
/// a simulated badge when the source is not live, and a voice notice.
class PresenceStatus extends StatelessWidget {
  const PresenceStatus({super.key, required this.view});

  final PresenceView view;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final (Color dot, IconData? icon) = switch (view.statusState) {
      CompanionState.awaitingApproval => (c.warning, Icons.rule_rounded),
      CompanionState.error => (c.danger, Icons.error_outline_rounded),
      CompanionState.unavailable => (c.inkSoft, Icons.cloud_off_rounded),
      CompanionState.success => (c.success, null),
      _ => (c.accent, null),
    };
    final shownStatus = view.status;
    return Semantics(
      container: true,
      liveRegion: true,
      label: [
        shownStatus,
        if (view.detail != null) view.detail!,
        if (view.notice != null) view.notice!,
        if (view.simulated) 'simulated',
      ].join('. '),
      child: ExcludeSemantics(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null)
                  Icon(icon, size: 15, color: dot)
                else
                  Container(
                    width: 7,
                    height: 7,
                    decoration: BoxDecoration(
                      color: dot,
                      shape: BoxShape.circle,
                    ),
                  ),
                const SizedBox(width: 7),
                Text(
                  shownStatus,
                  key: const ValueKey('presence-status'),
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                    color: c.ink,
                  ),
                ),
                if (view.simulated) ...[
                  const SizedBox(width: 8),
                  const StatusBadge.simulated(compact: true),
                ],
              ],
            ),
            if (view.notice != null || view.detail != null)
              Padding(
                padding: const EdgeInsets.only(top: 3),
                child: Text(
                  view.notice ?? view.detail!,
                  key: const ValueKey('presence-detail'),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 12,
                    color: view.notice != null ? c.warning : c.inkSoft,
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
