from pathlib import Path
p=Path('uri_ui/lib/living/a2ui/a2ui_view.dart')
s=p.read_text();s=s.replace("this.rootId = 'root',", "this.rootId = 'root',\n    this.hostIcon,")
s=s.replace('final String rootId;', 'final String rootId;\n\n  /// Local host presentation; never read from untrusted surface definitions.\n  final IconData? hostIcon;')
s=s.replace('if (bare) {', '''if (hostIcon != null) {
          return SizedBox.expand(child: _Node(
            hub: hub, s: s, id: rootId, compact: compact, hostIcon: hostIcon,
          ));
        }
        if (bare) {''')
s=s.replace('this.scope,\n  });','this.scope,\n    this.hostIcon,\n  });')
s=s.replace('final String? scope;', 'final String? scope;\n  final IconData? hostIcon;')
s=s.replace("final label = Text(_text(comp['label']));", '''final label = Text(_text(comp['label']), textAlign: TextAlign.center);
        if (hostIcon != null) {
          return OutlinedButton(
            key: _key(),
            style: OutlinedButton.styleFrom(
              shape: const CircleBorder(), side: BorderSide.none,
              backgroundColor: c.surface, foregroundColor: c.ink,
              padding: const EdgeInsets.all(8),
              tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              textStyle: const TextStyle(fontSize: 14, height: 1.1),
            ),
            onPressed: enabled ? () => hub.act(s.id, id, scope: scope) : null,
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              Icon(hostIcon, size: 25, color: c.accent),
              const SizedBox(height: 5), label,
            ]),
          );
        }''')
p.write_text(s)
p=Path('uri_ui/lib/living/screens/companion_mode_view.dart');s=p.read_text();s="import 'dart:math' as math;\n"+s
s=s.replace("import '../../services/app_state_scope.dart';", "import '../../services/app_state_scope.dart';\nimport '../../screens/ask/ask_uri_screen.dart' show UriConversationPane;\nimport '../../theme/uri_theme.dart';\nimport '../integration/oi_widgets.dart';\nimport '../widgets/living_composer.dart';")
s=s.replace('/// No chat box or enclosing panel: contextual A2UI buttons float around the\n/// actual Companion. Chat/review open the existing full Workspace surfaces.', '/// Approved detached-chat composition, using the existing Companion and\n/// shared conversation. Open/closed chat is transient, never a design choice.')
s=s.replace('this.acknowledgement,','this.acknowledgement,\n    this.chatOpen = false,\n    this.onChatChanged,')
s=s.replace('final Rect orbRect;', 'final Rect orbRect;\n  final bool chatOpen;\n  final ValueChanged<bool>? onChatChanged;')
s=s.replace('    CompanionUiAction.workspace,\n    CompanionUiAction.collapse,\n','')
s=s.replace('double textScale = 1,\n  }) {','''double textScale = 1,
    double angle = 0,
  }) {
    if (actions.length <= 4 && textScale <= 1.2) {
      final diameter = buttonDiameter(size);
      final radius = orbitRadius(size);
      final result = <CompanionUiAction, Rect>{};
      for (final action in actions) {
        final phase = switch(action) {
          CompanionUiAction.chat => math.pi,
          CompanionUiAction.dashboard => 0.0,
          CompanionUiAction.review => -math.pi / 2,
          CompanionUiAction.voiceCancel => actions.contains(CompanionUiAction.voiceFinish)
              ? -math.pi / 2 : math.pi / 2,
          _ => math.pi / 2,
        };
        result[action] = Rect.fromCenter(
          center: orb.center + Offset(math.cos(phase + angle), math.sin(phase + angle)) * radius,
          width: diameter, height: diameter,
        );
      }
      return result;
    }''')
start=s.index('  static Rect voiceRect(');end=s.index('  static int reviewCount',start)
s=s[:start]+'''  static double buttonDiameter(Size size) => (size.width * .20).clamp(68.0, 88.0);
  static double orbitRadius(Size size) => (size.width - buttonDiameter(size)) / 2 - 12;

  static Rect voiceRect(Size size, Rect orb, {Iterable<Rect> buttons = const []}) {
    final bottom = math.max(orb.bottom, orb.center.dy + orbitRadius(size) + buttonDiameter(size) / 2);
    return Rect.fromLTWH(24, bottom + 10, size.width - 48, 64);
  }

  static Rect chatRect(Size size, Rect orb, {double textScale = 1}) {
    final width = math.min(320.0, size.width - 24);
    final top = voiceRect(size, orb).bottom + 10;
    return Rect.fromLTWH((size.width - width) / 2, top, width,
      math.max(96, size.height - top - 12));
  }

'''+s[end:]
s=s.replace('case CompanionUiAction.chat:\n      case CompanionUiAction.workspace:', 'case CompanionUiAction.chat:\n        widget.onChatChanged?.call(!widget.chatOpen);\n      case CompanionUiAction.workspace:')
s=s.replace('bare: true,','''bare: true,
                          hostIcon: actions.length <= 4 && MediaQuery.textScalerOf(context).scale(14) / 14 <= 1.2
                              ? switch(entry.key) {
                                  CompanionUiAction.chat => Icons.chat_bubble_outline_rounded,
                                  CompanionUiAction.dashboard => Icons.bar_chart_rounded,
                                  CompanionUiAction.review => Icons.fact_check_outlined,
                                  CompanionUiAction.voiceFinish => Icons.stop_rounded,
                                  CompanionUiAction.voiceCancel => Icons.close_rounded,
                                  _ => Icons.mic_none_rounded,
                                } : null,''')
s=s.replace('children: [\n                if (widget.acknowledgement', '''children: [
                Positioned.fill(child: IgnorePointer(child: CustomPaint(
                  painter: _OrbitArcs(widget.orbRect.center, CompanionModeView.orbitRadius(box.biggest), UriColors.of(context).accent),
                ))),
                if (widget.chatOpen)
                  Positioned.fromRect(
                    rect: CompanionModeView.chatRect(box.biggest, widget.orbRect),
                    child: _DetachedChat(
                      filePicker: widget.filePicker, attachmentOpener: widget.attachmentOpener,
                      onClose: () => widget.onChatChanged?.call(false),
                    ),
                  ),
                if (widget.acknowledgement''')
s=s.replace('showListening: true,','showListening: true,\n                      vertical: true,')
s+='''

class _DetachedChat extends StatelessWidget {
  const _DetachedChat({this.filePicker, this.attachmentOpener, required this.onClose});
  final FilePickerFn? filePicker;
  final AttachmentOpenerFn? attachmentOpener;
  final VoidCallback onClose;
  @override
  Widget build(BuildContext context) {
    final s = LivingScope.of(context);
    final c = UriColors.of(context);
    return Material(
      key: const ValueKey('companion-detached-chat'),
      color: c.surface, borderRadius: BorderRadius.circular(18),
      clipBehavior: Clip.antiAlias,
      child: Column(children: [
        Padding(padding: const EdgeInsets.only(left: 16, right: 4), child: Row(children: [
          const Expanded(child: Text('Conversation', style: TextStyle(fontSize: 16))),
          IconButton(key: const ValueKey('companion-close-chat'), tooltip: 'Close conversation',
            onPressed: onClose, icon: const Icon(Icons.close_rounded, size: 20)),
        ])),
        Expanded(child: Padding(padding: const EdgeInsets.symmetric(horizontal: 12), child:
          s.oi != null ? OiConversationPane(conversation: s.oi!, compact: true)
            : UriConversationPane(compact: true, attachmentOpener: attachmentOpener, supervisedHandoff: false),
        )),
        LivingComposer(compact: true, minimal: true, hint: 'Ask URI…', filePicker: filePicker),
      ]),
    );
  }
}

class _OrbitArcs extends CustomPainter {
  const _OrbitArcs(this.center, this.radius, this.color);
  final Offset center;
  final double radius;
  final Color color;
  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()..color = color.withValues(alpha: .55)..style = PaintingStyle.stroke..strokeWidth = 1;
    final bounds = Rect.fromCircle(center: center, radius: radius);
    for (final angle in [-1.38, .23, 1.78, 3.36]) {
      canvas.drawArc(bounds, angle, .65, false, paint);
      final point = center + Offset(math.cos(angle + .23), math.sin(angle + .23)) * radius;
      canvas.drawCircle(point, 2, Paint()..color = color.withValues(alpha: .8));
    }
  }
  @override
  bool shouldRepaint(_OrbitArcs old) => old.center != center || old.radius != radius || old.color != color;
}
'''
p.write_text(s)
p=Path('uri_ui/lib/living/presentation/living_shell.dart');s=p.read_text();s=s.replace('(shell.shortestSide - 220).clamp(140.0, 180.0)', '(shell.width * .46).clamp(140.0, 220.0)');s=s.replace('(shell.height - size) / 2,','shell.height * .29 - size / 2,',1)
s=s.replace('bool _panelExpanded = false;', 'bool _panelExpanded = false;\n  bool _chatOpen = false;')
s=s.replace('              panel:\n                  _panelExpanded', '              controls:\n                  _panelExpanded')
s=s.replace('                  : null,\n            );\n            if (layout', '''                  : null,
              panel: _panelExpanded && _chatOpen
                  ? CompanionModeView.chatRect(shellSize, dock.rect) : null,
            );
            if (layout''')
s=s.replace('expanded: _panelExpanded,\n                                        acknowledgement:', 'expanded: _panelExpanded,\n                                        chatOpen: _chatOpen,\n                                        onChatChanged: (value) => setState(() => _chatOpen = value),\n                                        acknowledgement:')
p.write_text(s)
p=Path('uri_ui/lib/living/voice/voice_stage.dart');s=p.read_text();s=s.replace('this.showListening = false,', 'this.showListening = false,\n    this.vertical = false,');s=s.replace('final bool showListening;', 'final bool showListening;\n  final bool vertical;');s=s.replace('child: widget.compact\n', '''child: widget.vertical
                  ? Column(children: [
                      if (prefs.voice.waveform) SizedBox(width: 170, height: 34, child: _waveform(v)),
                      Text(session.phase == VoicePhase.listening ? 'Listening' : speaker == VoiceSpeaker.user ? 'You' : 'URI speaking',
                        style: TextStyle(fontSize: 14, color: UriGlass.of(context).ink)),
                      if (widget.voice.simulated) const Text('SIMULATED', style: TextStyle(fontSize: 10)),
                    ])
                  : widget.compact
''')
# UriGlass has no ink; use theme UriColors.
s=s.replace("import '../../theme/glass_theme.dart';", "import '../../theme/glass_theme.dart';\nimport '../../theme/uri_theme.dart';");s=s.replace('UriGlass.of(context).ink', 'UriColors.of(context).ink')
p.write_text(s)
ref=Path(r'C:/Users/cheta/.codex-remote-attachments/01a1305a-4e45-76d0-a524-d644140bedee/936d162a-9ee0-4269-b32f-b01e93c4b08a/1-1000090089.jpg')
Path('docs/ui_v2/evidence/reference/companion-approved.jpg').write_bytes(ref.read_bytes())
