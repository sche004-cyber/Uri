import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../companion/companion_preferences.dart';
import 'voice_interaction.dart';

/// The push-to-talk control beside the composer's send button.
///
/// * Hold (mouse or touch) to talk; release to finish.
/// * A short tap starts listening; the next tap finishes.
/// * While URI speaks, the button stops it (a hold stops it and listens).
/// * Keyboard: hold Ctrl+Space to talk; Esc cancels a capture or stops URI.
///
/// The button never sends anything itself; the transcript is routed by the
/// [VoiceInteractionController] like typed text.
class VoiceTalkButton extends StatefulWidget {
  const VoiceTalkButton({super.key, required this.controller});

  final VoiceInteractionController controller;

  static const Duration holdThreshold = Duration(milliseconds: 350);

  @override
  State<VoiceTalkButton> createState() => _VoiceTalkButtonState();
}

class _VoiceTalkButtonState extends State<VoiceTalkButton> {
  /// Mounted buttons, newest last. During a mode change two composers can be
  /// mounted at once; only the newest handles the keyboard, so one key press
  /// is one action.
  static final List<_VoiceTalkButtonState> _mounted = [];

  DateTime? _downAt;
  bool _toggled = false;
  bool _keyHeld = false;

  VoiceInteractionController get _c => widget.controller;

  @override
  void initState() {
    super.initState();
    _mounted.add(this);
    HardwareKeyboard.instance.addHandler(_onKey);
  }

  @override
  void dispose() {
    _mounted.remove(this);
    HardwareKeyboard.instance.removeHandler(_onKey);
    super.dispose();
  }

  bool _onKey(KeyEvent e) {
    if (_mounted.isEmpty || !identical(_mounted.last, this)) return false;
    final k = e.logicalKey;
    if (k == LogicalKeyboardKey.escape && e is KeyDownEvent) {
      if (_c.stage != VoiceStage.idle) {
        _toggled = false;
        _c.cancel();
        return true;
      }
      return false;
    }
    if (k != LogicalKeyboardKey.space) return false;
    final ctrl = HardwareKeyboard.instance.isControlPressed;
    if (e is KeyDownEvent && ctrl && !_keyHeld) {
      _keyHeld = true;
      _c.pressTalk();
      return true;
    }
    if (e is KeyRepeatEvent && _keyHeld) return true;
    if (e is KeyUpEvent && _keyHeld) {
      _keyHeld = false;
      _c.releaseTalk();
      return true;
    }
    return false;
  }

  void _down() {
    if (_toggled) return;
    _downAt = DateTime.now();
    _c.pressTalk();
  }

  void _up() {
    final down = _downAt;
    _downAt = null;
    if (_toggled) {
      _toggled = false;
      _c.releaseTalk();
      return;
    }
    if (down == null) return;
    final held = DateTime.now().difference(down);
    if (held < VoiceTalkButton.holdThreshold &&
        (_c.stage == VoiceStage.listening || _c.stage == VoiceStage.opening)) {
      _toggled = true; // tap: keep listening until the next tap
      return;
    }
    _c.releaseTalk();
  }

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    return ListenableBuilder(
      listenable: _c,
      builder: (context, _) {
        final stage = _c.stage;
        final listening =
            stage == VoiceStage.listening || stage == VoiceStage.opening;
        final speaking = stage == VoiceStage.speaking;
        final busy = stage == VoiceStage.transcribing;
        final unavailable = _c.service.status.value.state.name == 'unavailable';
        final drafting = _c.mode == VoiceInputMode.drafting;
        final tip = switch (stage) {
          VoiceStage.listening || VoiceStage.opening =>
            'Listening. Release (or tap) to finish, Esc to cancel',
          VoiceStage.transcribing => 'Transcribing',
          VoiceStage.speaking => 'Stop URI speaking (hold to talk)',
          _ =>
            unavailable
                ? (_c.service.status.value.problem ?? 'Voice input unavailable')
                : drafting
                ? 'Hold to dictate a draft (Ctrl+Space)'
                : 'Hold to talk (Ctrl+Space)',
        };
        if (speaking) {
          return Tooltip(
            message: tip,
            child: Listener(
              onPointerDown: (_) => _downAt = DateTime.now(),
              onPointerUp: (_) {
                final d = _downAt;
                _downAt = null;
                if (d != null &&
                    DateTime.now().difference(d) >=
                        VoiceTalkButton.holdThreshold) {
                  return;
                }
                _c.stopSpeaking();
              },
              child: _Disc(
                key: const ValueKey('voice-stop-speaking'),
                color: glass.glow,
                icon: Icons.stop_rounded,
                iconColor: c.canvas,
              ),
            ),
          );
        }
        return Tooltip(
          message: tip,
          child: Listener(
            onPointerDown: busy ? null : (_) => _down(),
            onPointerUp: busy ? null : (_) => _up(),
            onPointerCancel: busy ? null : (_) => _c.cancel(),
            child: _Disc(
              key: const ValueKey('voice-talk'),
              color: listening ? c.danger.withValues(alpha: 0.85) : glass.fill,
              icon: busy
                  ? Icons.graphic_eq_rounded
                  : drafting
                  ? Icons.edit_note_rounded
                  : Icons.mic_rounded,
              iconColor: listening
                  ? c.canvas
                  : unavailable
                  ? c.inkFaint
                  : c.inkSoft,
            ),
          ),
        );
      },
    );
  }
}

class _Disc extends StatelessWidget {
  const _Disc({
    super.key,
    required this.color,
    required this.icon,
    required this.iconColor,
  });
  final Color color;
  final IconData icon;
  final Color iconColor;

  @override
  Widget build(BuildContext context) => Material(
    color: color,
    shape: const CircleBorder(),
    child: SizedBox(
      width: 34,
      height: 34,
      child: Icon(icon, size: 18, color: iconColor),
    ),
  );
}

/// One line under the composer for voice notices (nothing heard, microphone
/// blocked, drafting unavailable). Empty when there is nothing to say.
class VoiceNoticeLine extends StatelessWidget {
  const VoiceNoticeLine({super.key, required this.controller});
  final VoiceInteractionController controller;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final n = controller.notice;
        if (n == null) return const SizedBox.shrink();
        return Padding(
          key: const ValueKey('voice-notice'),
          padding: const EdgeInsets.only(left: 6, right: 6, top: 4),
          child: Row(
            children: [
              Icon(Icons.info_outline_rounded, size: 14, color: c.inkSoft),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  n,
                  style: TextStyle(color: c.inkSoft, fontSize: 12),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
