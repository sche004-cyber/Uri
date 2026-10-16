import 'package:flutter/widgets.dart';

import '../../theme/glass_theme.dart';
import '../companion/companion_preferences.dart';
import '../companion/effects_settings.dart';
import 'voice_session.dart';
import 'voice_transcript.dart';
import 'voice_waveform.dart';

/// The voice exchange inside the app shell: the shared waveform with the
/// transcript, beside the companion rather than in place of it.
///
/// It is the same [VoiceWaveform] and [VoiceTranscript] as the floating
/// presence, for both speakers; only the level it is given and the text
/// differ. The companion itself is never touched by it, so its identity and
/// animation continue while someone speaks.
///
/// It fades in when someone starts speaking and out when the turn ends, by
/// retargeting one tween, so barge-in, cancellation and a lost signal glide
/// rather than jump. While fading out it keeps the last speaker's text.
class VoiceStage extends StatefulWidget {
  const VoiceStage({
    super.key,
    required this.voice,
    this.compact = false,
    this.borderless = false,
    this.showListening = false,
    this.vertical = false,
    this.visualScale = 1,
  });

  final bool borderless;
  final bool showListening;
  final bool vertical;
  final double visualScale;

  final VoiceSessionController voice;

  /// A slim horizontal pill (waveform beside one transcript line), for
  /// Workspace and Dashboard where the companion is docked.
  final bool compact;

  /// Full layout height for [width]: the waveform oval (when shown) above
  /// the two-line transcript.
  static double heightFor(double width, {bool waveform = true}) =>
      (waveform ? waveformHeight(width) + 6 : 0) + VoiceTranscript.heightFor();

  static double waveformHeight(double width) =>
      (width / kVoiceWaveformAspect).clamp(0.0, 150.0);

  /// Height of the compact pill.
  static const double compactHeight = 46;
  static const double _compactWave = 34;

  @override
  State<VoiceStage> createState() => _VoiceStageState();
}

class _VoiceStageState extends State<VoiceStage> {
  VoiceSpeaker? _lastSpeaker;

  @override
  Widget build(BuildContext context) {
    final prefs = CompanionPreferences.of(context);
    final reduced = EffectsSettings.of(context).reducedMotion;
    return ListenableBuilder(
      listenable: widget.voice,
      builder: (context, _) {
        final session = widget.voice.session;
        final speaker = switch (session.phase) {
          VoicePhase.listening when widget.showListening => VoiceSpeaker.user,
          VoicePhase.userSpeaking => VoiceSpeaker.user,
          VoicePhase.uriSpeaking => VoiceSpeaker.uri,
          _ => null,
        };
        if (speaker != null) _lastSpeaker = speaker;
        // Only real speech shows the stage; "listening" with nothing heard
        // yet is shown by the companion alone.
        final target = speaker != null ? 1.0 : 0.0;
        return TweenAnimationBuilder<double>(
          tween: Tween<double>(end: target),
          duration: reduced
              ? const Duration(milliseconds: 160)
              : const Duration(milliseconds: 520),
          builder: (context, v, _) {
            final shown = _lastSpeaker;
            if (v < 0.001 || shown == null) {
              return const SizedBox.shrink(key: ValueKey('voice-stage-idle'));
            }
            return Opacity(
              key: const ValueKey('voice-stage'),
              opacity: v,
              child: widget.vertical
                  ? Column(
                      children: [
                        if (prefs.voice.waveform)
                          SizedBox(
                            width: 170 * widget.visualScale,
                            height: 34 * widget.visualScale,
                            child: _waveform(v),
                          ),
                        Text(
                          session.phase == VoicePhase.listening
                              ? 'Listening'
                              : speaker == VoiceSpeaker.user
                              ? 'You'
                              : 'URI speaking',
                          style: TextStyle(
                            fontSize: 14 * widget.visualScale,
                            color: const Color(0xFFF1EEE5),
                            shadows: const [
                              Shadow(color: Color(0xCC000000), blurRadius: 4),
                            ],
                          ),
                        ),
                        if (widget.voice.simulated)
                          const Text(
                            'SIMULATED',
                            style: TextStyle(
                              fontSize: 10,
                              color: Color(0xFFF1EEE5),
                            ),
                          ),
                      ],
                    )
                  : widget.compact
                  ? _compact(context, session, shown, prefs.voice.waveform, v)
                  : _full(session, shown, prefs.voice.waveform, v),
            );
          },
        );
      },
    );
  }

  Widget _waveform(double presence) => VoiceWaveform(
    key: const ValueKey('stage-waveform'),
    level: widget.voice.level,
    flux: widget.voice.flux,
    presence: presence,
    bars: widget.vertical,
  );

  Widget _transcript(
    VoiceSession session,
    VoiceSpeaker speaker, {
    required int lines,
    required double fontSize,
  }) => VoiceTranscript(
    speaker: speaker,
    text:
        widget.showListening &&
            session.phase == VoicePhase.listening &&
            session.transcript.isEmpty
        ? 'Listening…'
        : session.transcript,
    spokenChars: session.spokenChars,
    isFinal: session.transcriptFinal,
    simulated: widget.voice.simulated,
    lines: lines,
    fontSize: fontSize,
  );

  /// Waveform above a two-line transcript. The waveform takes whatever
  /// height is left once the transcript fits, so a short window shrinks the
  /// oval rather than overlapping the controls below.
  Widget _full(
    VoiceSession session,
    VoiceSpeaker speaker,
    bool showWave,
    double v,
  ) {
    return LayoutBuilder(
      builder: (context, box) {
        final w = box.maxWidth;
        final tH = VoiceTranscript.heightFor();
        final room = box.maxHeight.isFinite ? box.maxHeight - tH - 6 : 150.0;
        final waveH = showWave
            ? VoiceStage.waveformHeight(w).clamp(0.0, room)
            : 0.0;
        return Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (waveH >= 16) ...[
              SizedBox(
                width: waveH * kVoiceWaveformAspect,
                height: waveH,
                child: _waveform(v),
              ),
              const SizedBox(height: 6),
            ],
            SizedBox(
              width: w,
              height: tH,
              child: _transcript(session, speaker, lines: 2, fontSize: 15),
            ),
          ],
        );
      },
    );
  }

  /// One line: the same waveform, small, beside the transcript, on a glass
  /// pill so it stays legible over whatever the docked layout shows.
  Widget _compact(
    BuildContext context,
    VoiceSession session,
    VoiceSpeaker speaker,
    bool showWave,
    double v,
  ) {
    final glass = UriGlass.of(context);
    return Container(
      height: VoiceStage.compactHeight,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
      decoration: BoxDecoration(
        color: glass.fillStrong,
        borderRadius: BorderRadius.circular(999),
        border: widget.borderless ? null : Border.all(color: glass.border),
      ),
      child: Row(
        children: [
          if (showWave) ...[
            SizedBox(
              width: VoiceStage._compactWave * kVoiceWaveformAspect,
              height: VoiceStage._compactWave,
              child: _waveform(v),
            ),
            const SizedBox(width: 10),
          ],
          Expanded(
            child: _transcript(session, speaker, lines: 1, fontSize: 13),
          ),
        ],
      ),
    );
  }
}
