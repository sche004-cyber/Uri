from pathlib import Path
p=Path('uri_ui/lib/living/presentation/living_shell.dart');s=p.read_text(encoding='utf-8');a=s.index('                      orbit: _panelExpanded',s.index('              controls:'));b=s.index('                    )',a);s=s[:a]+s[b:];s=s.replace('            4)\n      return;', '            4) {\n      return;\n    }').replace('_orbitBounds?.inflate(80).contains(point) == true)\n              _holdOrbit();','_orbitBounds?.inflate(80).contains(point) == true) {\n              _holdOrbit();\n            }');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/screens/companion_mode_view.dart');s=p.read_text(encoding='utf-8').replace("import '../../screens/ask/ask_uri_screen.dart' show UriConversationPane;", "import '../../models/uri_turn.dart';")
a=s.index(': UriConversationPane(');b=s.index('\n          ),',a);s=s[:a]+': const _DetachedClassicConversation(),'+s[b:]
s+='''

/// A compact projection of the same classic conversation. Decisions and
/// receipts stay on the full review surface, never inferred from reply text.
class _DetachedClassicConversation extends StatelessWidget {
  const _DetachedClassicConversation();
  @override
  Widget build(BuildContext context) {
    final app = AppStateScope.of(context);
    final c = UriColors.of(context);
    return ListenableBuilder(listenable: app, builder: (context, _) {
      Widget bubble(String text, bool user) => Align(
        alignment: user ? Alignment.centerRight : Alignment.centerLeft,
        child: Container(margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(color: user ? c.accentSoft : c.canvas,
            borderRadius: BorderRadius.circular(12)),
          child: Text(text, style: TextStyle(fontSize: 14, color: c.ink)),
        ),
      );
      final messages = <Widget>[];
      for (final turn in app.conversation) {
        messages.add(bubble(turn.userText, true));
        final text = turn.failureReason ?? turn.result?.summary ?? turn.understanding;
        if (text != null && text.isNotEmpty) messages.add(bubble(text, false));
        if (turn.stage != TurnStage.completed) {
          messages.add(Text(switch(turn.stage) {
            TurnStage.understanding => 'Waiting for URI…',
            TurnStage.proposalReady || TurnStage.awaitingApproval => 'Awaiting review — open Review',
            TurnStage.executing => 'Working — open Review for execution details',
            TurnStage.cancelled => 'Cancelled',
            TurnStage.failed => 'Request failed',
            TurnStage.needsConnection => 'Connection required — open Dashboard',
            _ => '',
          }, style: TextStyle(fontSize: 14, color: turn.stage == TurnStage.failed ? c.danger : c.inkSoft)));
        }
      }
      if (messages.isEmpty) messages.add(Text('Ask URI anything to begin.', style: TextStyle(color: c.inkSoft, fontSize: 14)));
      return ListView(reverse: true, padding: const EdgeInsets.only(top: 4), children: messages.reversed.toList());
    });
  }
}
''';p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/voice/voice_waveform.dart');s=p.read_text(encoding='utf-8');s=s.replace('this.motion = 1,', 'this.motion = 1,\n    this.bars = false,').replace('final double motion;', 'final double motion;\n  final bool bars;',1);s=s.replace('    final shader = _shader;','''    if (widget.bars) {
      return CustomPaint(size: Size.infinite, painter: VoiceBarsPainter(widget.level, c.accent, widget.presence));
    }
    final shader = _shader;''',1)
# constructor of live waveform only
pos=s.index('class VoiceWaveform extends StatefulWidget');s=s[:pos]+s[pos:].replace('this.presence = 1,','this.presence = 1,\n    this.bars = false,',1).replace('final double presence;', 'final double presence;\n  final bool bars;',1).replace('motion: reduced ? 0 : 1,', 'motion: reduced ? 0 : 1,\n      bars: widget.bars,',1)
s+='''

/// RMS-level display, not a frequency spectrum or fabricated audio recording.
/// Silent listening stays at short marks; only the real controller level grows
/// the bars. It uses the existing paced/hidden-window waveform driver.
class VoiceBarsPainter extends CustomPainter {
  const VoiceBarsPainter(this.level, this.color, this.presence);
  final double level, presence;
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    final amplitude = math.sqrt(level.clamp(0, 1));
    final paint = Paint()..color = color.withValues(alpha: presence.clamp(0, 1))
      ..strokeWidth = 2..strokeCap = StrokeCap.round;
    for (var i=0;i<33;i++) {
      final x = (i+.5)*size.width/33;
      final envelope = math.pow(math.sin((i+1)*math.pi/34), 1.4).toDouble();
      final shape = .55 + .45 * math.cos(i*1.73).abs();
      final h = 2 + amplitude * (size.height-2) * envelope * shape;
      canvas.drawLine(Offset(x,(size.height-h)/2), Offset(x,(size.height+h)/2), paint);
    }
  }
  @override
  bool shouldRepaint(VoiceBarsPainter old) => old.level != level || old.color != color || old.presence != presence;
}
''';p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/voice/voice_stage.dart');s=p.read_text(encoding='utf-8').replace('presence: presence,', 'presence: presence,\n    bars: widget.vertical,');p.write_text(s,encoding='utf-8')
