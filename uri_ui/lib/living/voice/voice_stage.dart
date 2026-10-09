import 'package:flutter/widgets.dart';

import '../companion/companion_preferences.dart';
import '../companion/effects_settings.dart';
import 'voice_session.dart';
import 'voice_transcript.dart';
import 'voice_waveform.dart';

/// The voice exchange inside the app shell: the shared waveform with the
/// transcript under it, beside the companion rather than in place of it.
///
/// It is the same [VoiceWaveform] and [VoiceTranscript] as the floating
/// presence, for both speakers; only the level it is given and the text
/// differ. The companion itself is never touched by it, so its identity and
/// animation continue while someone speaks.
///
/// It fades in when the session leaves `off` and out when it returns, by
/// retargeting one tween, so barge-in, cancellation and a lost signal glide
/// rather than jump. While fading out it keeps the last speaker's text.
class VoiceStage extends StatefulWidget {
  const VoiceStage({super.key, required this.voice, this.compact = false});

  final VoiceSessionController voice;

  /// One transcript line at a smaller size, for Workspace and Dashboard.
  final bool compact;

  /// Height for [width]: the waveform oval (when shown) plus the transcript.
  static double heightFor(
    double width, {
    bool compact = false,
    bool waveform = true,
  }) {
    final t = VoiceTranscript.heightFor(
      lines: compact ? 1 : 2,
      fontSize: compact ? 13 : 15,
    );
    return (waveform ? waveformHeight(width, compact: compact) + 6 : 0) + t;
  }

  static double waveformHeight(double width, {bool compact = false}) {
    final h = width / kVoiceWaveformAspect;
    return compact ? h.clamp(0.0, 56.0) : h.clamp(0.0, 150.0);
  }

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
            return LayoutBuilder(
              builder: (context, box) {
                final w = box.maxWidth;
                final waveH = VoiceStage.waveformHeight(
                  w,
                  compact: widget.compact,
                );
                return Opacity(
                  key: const ValueKey('voice-stage'),
                  opacity: v,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (prefs.voice.waveform) ...[
                        SizedBox(
                          width: waveH * kVoiceWaveformAspect,
                          height: waveH,
                          child: VoiceWaveform(
                            key: const ValueKey('stage-waveform'),
                            level: widget.voice.level,
                            flux: widget.voice.flux,
                            presence: v,
                          ),
                        ),
                        const SizedBox(height: 6),
                      ],
                      SizedBox(
                        width: w,
                        height: VoiceTranscript.heightFor(
                          lines: widget.compact ? 1 : 2,
                          fontSize: widget.compact ? 13 : 15,
                        ),
                        child: VoiceTranscript(
                          speaker: shown,
                          text: session.transcript,
                          spokenChars: session.spokenChars,
                          isFinal: session.transcriptFinal,
                          simulated: widget.voice.simulated,
                          lines: widget.compact ? 1 : 2,
                          fontSize: widget.compact ? 13 : 15,
                        ),
                      ),
                    ],
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
