import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import 'voice_session.dart';

/// The words under the voice waveform: the user's live transcript, or URI's
/// reply as it is spoken.
///
/// Both speakers use the same typography, the same box and the same colours;
/// only the words and the one-word speaker label differ. The box has a fixed
/// height so partial transcripts that grow, shrink or are revised never push
/// the layout around.
class VoiceTranscript extends StatelessWidget {
  const VoiceTranscript({
    super.key,
    required this.speaker,
    required this.text,
    this.spokenChars,
    this.isFinal = false,
    this.simulated = false,
    this.lines = 2,
    this.fontSize = 15,
  });

  final VoiceSpeaker speaker;
  final String text;

  /// URI only: how much of [text] has been heard, from the speech engine's
  /// word timing. Null means no reliable timing, so the text is shown whole.
  final int? spokenChars;
  final bool isFinal;
  final bool simulated;
  final int lines;
  final double fontSize;

  static const double _lineHeight = 1.38;

  /// Height of the box for [lines] lines plus the label row. Constant for a
  /// given size, whatever the text.
  static double heightFor({int lines = 2, double fontSize = 15}) =>
      18 + lines * fontSize * _lineHeight + 2;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final label = speaker == VoiceSpeaker.user ? 'You' : 'URI';
    final body = TextStyle(
      fontSize: fontSize,
      height: _lineHeight,
      color: c.ink,
      fontWeight: FontWeight.w500,
    );
    return Semantics(
      container: true,
      label: speaker == VoiceSpeaker.user ? 'You are saying' : 'URI is saying',
      value: text,
      liveRegion: isFinal,
      child: ExcludeSemantics(
        child: SizedBox(
          height: heightFor(lines: lines, fontSize: fontSize),
          child: LayoutBuilder(
            builder: (context, box) {
              final window = speaker == VoiceSpeaker.user
                  ? TranscriptWindow.tail(text, box.maxWidth, fontSize, lines)
                  : TranscriptWindow.spoken(text, spokenChars);
              return Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        label,
                        key: const ValueKey('voice-transcript-label'),
                        style: TextStyle(
                          fontSize: 11,
                          letterSpacing: 0.8,
                          fontWeight: FontWeight.w600,
                          color: c.inkSoft,
                        ),
                      ),
                      if (simulated) ...[
                        const SizedBox(width: 6),
                        Text(
                          'SIMULATED',
                          style: TextStyle(
                            fontSize: 9.5,
                            letterSpacing: 0.8,
                            fontWeight: FontWeight.w700,
                            color: c.warning,
                          ),
                        ),
                      ],
                    ],
                  ),
                  const SizedBox(height: 4),
                  Expanded(
                    child: AnimatedSwitcher(
                      duration: const Duration(milliseconds: 180),
                      // Only a new sentence of URI's reply fades in. A growing
                      // user transcript keeps one key, so partial updates
                      // change text in place with no flicker.
                      child: KeyedSubtree(
                        key: ValueKey(window.key),
                        child: Text.rich(
                          TextSpan(
                            children: [
                              if (window.leadingEllipsis)
                                TextSpan(
                                  text: '…',
                                  style: body.copyWith(color: c.inkSoft),
                                ),
                              TextSpan(text: window.heard, style: body),
                              TextSpan(
                                text: window.ahead,
                                style: body.copyWith(color: c.inkSoft),
                              ),
                            ],
                          ),
                          key: const ValueKey('voice-transcript-text'),
                          textAlign: TextAlign.center,
                          maxLines: lines,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }
}

/// Which part of a transcript fits the box, split into what has been heard
/// and what is still ahead. Pure, so the windowing is unit-tested.
@immutable
class TranscriptWindow {
  const TranscriptWindow({
    required this.heard,
    required this.ahead,
    required this.key,
    this.leadingEllipsis = false,
  });

  final String heard;
  final String ahead;
  final Object key;
  final bool leadingEllipsis;

  /// The end of a growing user transcript: the newest words stay visible and
  /// older ones scroll off the start at a word boundary.
  factory TranscriptWindow.tail(
    String text,
    double width,
    double fontSize,
    int lines,
  ) {
    final t = text.trim();
    // A deliberately conservative average glyph width, so the window never
    // relies on the ellipsis at the end (which would hide the newest words).
    final perLine = (width / (fontSize * 0.56)).floor().clamp(8, 400);
    final budget = perLine * lines - 2;
    if (t.length <= budget) {
      return TranscriptWindow(heard: t, ahead: '', key: 'user');
    }
    var start = t.length - budget;
    final space = t.indexOf(' ', start);
    if (space != -1 && space < t.length - 1) start = space + 1;
    return TranscriptWindow(
      heard: t.substring(start),
      ahead: '',
      key: 'user',
      leadingEllipsis: true,
    );
  }

  /// URI's reply, one sentence at a time while it is spoken. The current
  /// sentence shows the heard words at full ink and the rest softer. Without
  /// timing ([spoken] null) the reply is shown whole from the start.
  factory TranscriptWindow.spoken(String text, int? spoken) {
    if (spoken == null) {
      return TranscriptWindow(heard: text.trim(), ahead: '', key: 'uri-all');
    }
    final sentences = splitSentences(text);
    // The current sentence is the last one whose first word has been heard.
    // A finished sentence stays up until the next one actually starts, so the
    // pause between sentences does not blank the box.
    var index = 0;
    for (var i = 0; i < sentences.length; i++) {
      if (sentences[i].$1 < spoken) index = i;
    }
    final (start, end) = sentences[index];
    final cut = spoken.clamp(start, end);
    return TranscriptWindow(
      heard: text.substring(start, cut),
      ahead: text.substring(cut, end),
      key: 'uri-$index',
    );
  }

  /// Sentence spans `[start, end)` over [text], trimmed of surrounding space.
  static List<(int, int)> splitSentences(String text) {
    final out = <(int, int)>[];
    final re = RegExp(r'[^.!?]+[.!?]*');
    for (final m in re.allMatches(text)) {
      var s = m.start;
      var e = m.end;
      while (s < e && text[s].trim().isEmpty) {
        s++;
      }
      while (e > s && text[e - 1].trim().isEmpty) {
        e--;
      }
      if (e > s) out.add((s, e));
    }
    if (out.isEmpty) out.add((0, text.length));
    return out;
  }
}
