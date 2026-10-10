import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../services/attachment_opener_service.dart';
import '../../services/file_picker_service.dart';
import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../companion/living_companion.dart';
import '../living_scope.dart';
import '../voice/voice_stage.dart';
import '../widgets/frame_stats_overlay.dart';
import '../widgets/glass_panel.dart';
import '../screens/companion_mode_view.dart';
import '../screens/dashboard_mode_view.dart';
import '../screens/workspace_mode_view.dart';
import 'presentation_controller.dart';

/// Where the one orb sits in each form, as a fraction of the shell.
///
/// The orb is a single widget instance under a [GlobalKey]; the shell
/// only moves and resizes it, so a mode change reads as the companion
/// travelling to a new place in the same space, not as a different
/// screen with a different mascot.
@immutable
class OrbDock {
  const OrbDock({required this.rect, required this.lightAt});
  final Rect rect;
  final Alignment lightAt;

  /// Workspace rail geometry, shared with the rail so the orb and the space
  /// the rail leaves for it always agree. The rail is expanded from this
  /// shell width.
  static const double railExpandAt = 1100;
  static double railWidth(double shellWidth) =>
      shellWidth >= railExpandAt ? 200.0 : 88.0;

  /// In the Workspace the orb is the heart of the rail: centred in it and
  /// large enough to read as the centre of URI, not as a corner logo.
  static double railOrbSize(double shellWidth) =>
      shellWidth >= railExpandAt ? 132.0 : 64.0;
  static const double railOrbTop = 18;

  /// Height the rail reserves above its status line for the docked orb.
  static double railOrbSpace(double shellWidth) =>
      railOrbTop + railOrbSize(shellWidth) + 12;

  static OrbDock forMode(UiPresentationMode mode, Size shell) {
    switch (mode) {
      case UiPresentationMode.companion:
        final size = (shell.shortestSide * 0.58).clamp(180.0, 320.0);
        final cx = shell.width / 2;
        final cy = shell.height * 0.36;
        return OrbDock(
          rect: Rect.fromCenter(
            center: Offset(cx, cy),
            width: size,
            height: size,
          ),
          lightAt: const Alignment(0, -0.45),
        );
      case UiPresentationMode.workspace:
        final size = railOrbSize(shell.width);
        return OrbDock(
          rect: Rect.fromLTWH(
            (railWidth(shell.width) - size) / 2,
            railOrbTop,
            size,
            size,
          ),
          lightAt: const Alignment(-0.95, -0.95),
        );
      case UiPresentationMode.dashboard:
        const size = 128.0;
        return OrbDock(
          rect: Rect.fromLTWH(shell.width / 2 - size / 2, 18, size, size),
          lightAt: const Alignment(0, -1),
        );
    }
  }
}

/// Where the voice exchange (waveform and transcript) sits in each form. It
/// is placed next to the companion and never over it, nor over the controls:
///
/// * Companion mode: under the status line, sized to the space left above the
///   composer (the waveform shrinks first). When even the transcript does not
///   fit there, a slim pill above the companion; in a window too short for
///   either, no stage at all rather than an overlap.
/// * Workspace: a slim pill centred in the header row.
/// * Dashboard: a slim pill beside the companion.
@immutable
class VoiceDock {
  const VoiceDock({
    required this.rect,
    required this.compact,
    this.hidden = false,
  });
  final Rect rect;
  final bool compact;

  /// True when the window is too short for any place that covers neither
  /// the companion nor the controls (below about 560 px of height, where
  /// Companion mode's own column no longer fits). The stage is then not
  /// shown; the status line still says who is speaking.
  final bool hidden;

  /// Height the Companion-mode controls take at the bottom of the shell
  /// (composer, mode chips, hint and their gaps).
  static const double companionControls = 168;

  /// Height of the status line and its detail under the companion.
  static const double companionStatus = 66;

  static VoiceDock forMode(UiPresentationMode mode, Size shell, Rect orb) {
    switch (mode) {
      case UiPresentationMode.companion:
        final w = (shell.width - 32).clamp(200.0, 520.0);
        final top = orb.bottom + companionStatus;
        final room = shell.height - companionControls - top;
        final minimum = VoiceStage.heightFor(w, waveform: false);
        if (room >= minimum) {
          return VoiceDock(
            rect: Rect.fromLTWH(
              (shell.width - w) / 2,
              top,
              w,
              room.clamp(minimum, VoiceStage.heightFor(w)),
            ),
            compact: false,
          );
        }
        // A short window has no room under the companion: the slim pill goes
        // above it instead, in the space Companion mode leaves at the top.
        final pw = (shell.width - 32).clamp(200.0, 440.0);
        final above = orb.top - VoiceStage.compactHeight - 6;
        if (above >= 4) {
          return VoiceDock(
            rect: Rect.fromLTWH(
              (shell.width - pw) / 2,
              above,
              pw,
              VoiceStage.compactHeight,
            ),
            compact: true,
          );
        }
        // Shorter still: no free place, so no stage rather than an overlap.
        return const VoiceDock(rect: Rect.zero, compact: true, hidden: true);
      case UiPresentationMode.workspace:
        final w = (shell.width * 0.36).clamp(240.0, 440.0);
        return VoiceDock(
          rect: Rect.fromLTWH(
            (shell.width - w) / 2,
            6,
            w,
            VoiceStage.compactHeight,
          ),
          compact: true,
        );
      case UiPresentationMode.dashboard:
        final left = orb.right + 24;
        final room = shell.width - left - 24;
        // A narrow Dashboard has no free place beside the companion.
        if (room < 200) {
          return const VoiceDock(rect: Rect.zero, compact: true, hidden: true);
        }
        return VoiceDock(
          rect: Rect.fromLTWH(
            left,
            orb.center.dy - VoiceStage.compactHeight / 2,
            room.clamp(200.0, 420.0),
            VoiceStage.compactHeight,
          ),
          compact: true,
        );
    }
  }
}

/// Root of the living experience below the theme: ambient background,
/// the current mode's content, and the travelling orb on top.
class LivingShell extends StatefulWidget {
  const LivingShell({super.key, this.filePicker, this.attachmentOpener});

  final FilePickerFn? filePicker;
  final AttachmentOpenerFn? attachmentOpener;

  /// The one orb. Tests assert the same element survives mode changes.
  static final GlobalKey orbKey = GlobalKey(debugLabel: 'living-orb');

  @override
  State<LivingShell> createState() => _LivingShellState();
}

class _LivingShellState extends State<LivingShell> {
  Timer? _bubbleTimer;
  String? _bubbleText;

  static const List<String> _questions = [
    'Yes? What should I do?',
    "I'm here. What's next?",
    'Tell me what you need.',
    'Listening. Type it below.',
  ];

  void _onOrbTap(LivingServices services) {
    final n = services.orbPokes.value + 1;
    services.orbPokes.value = n;
    setState(() => _bubbleText = _questions[n % _questions.length]);
    _bubbleTimer?.cancel();
    _bubbleTimer = Timer(const Duration(seconds: 4), () {
      if (mounted) setState(() => _bubbleText = null);
    });
    services.composerFocus.requestFocus();
  }

  @override
  void dispose() {
    _bubbleTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    return ListenableBuilder(
      listenable: Listenable.merge([
        services.presentation,
        services.companion,
        services.orbVariant,
        services.orbPalette,
        services.companionPrefs,
      ]),
      builder: (context, _) {
        final mode = services.presentation.mode;
        final signal = services.companion.signal;
        return LayoutBuilder(
          builder: (context, constraints) {
            final shellSize = Size(constraints.maxWidth, constraints.maxHeight);
            final dock = OrbDock.forMode(mode, shellSize);
            final voiceDock = VoiceDock.forMode(mode, shellSize, dock.rect);
            final prefs = services.companionPrefs;
            return CallbackShortcuts(
              // Keyboard: Esc -> Companion, Ctrl+1/2/3 -> the three forms.
              bindings: {
                const SingleActivator(LogicalKeyboardKey.escape): () =>
                    services.presentation.setMode(UiPresentationMode.companion),
                const SingleActivator(
                  LogicalKeyboardKey.digit1,
                  control: true,
                ): () =>
                    services.presentation.setMode(UiPresentationMode.companion),
                const SingleActivator(
                  LogicalKeyboardKey.digit2,
                  control: true,
                ): () =>
                    services.presentation.setMode(UiPresentationMode.workspace),
                const SingleActivator(
                  LogicalKeyboardKey.digit3,
                  control: true,
                ): () =>
                    services.presentation.setMode(UiPresentationMode.dashboard),
              },
              child: Focus(
                autofocus: true,
                child: Scaffold(
                  backgroundColor: Colors.transparent,
                  body: AmbientBackground(
                    lightAt: dock.lightAt,
                    lightStrength: mode == UiPresentationMode.companion
                        ? 1
                        : 0.6,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        // Mode content, cross-faded with a small drift so it
                        // feels like the space re-arranging, not a page flip.
                        AnimatedSwitcher(
                          duration: UriMotion.mode,
                          switchInCurve: UriMotion.enter,
                          switchOutCurve: Curves.easeIn,
                          transitionBuilder: (child, animation) {
                            final drift = Tween<Offset>(
                              begin: const Offset(0, 0.015),
                              end: Offset.zero,
                            ).animate(animation);
                            return FadeTransition(
                              opacity: animation,
                              child: SlideTransition(
                                position: drift,
                                child: child,
                              ),
                            );
                          },
                          layoutBuilder: (current, previous) => Stack(
                            fit: StackFit.expand,
                            children: [...previous, ?current],
                          ),
                          child: KeyedSubtree(
                            key: ValueKey(mode),
                            child: switch (mode) {
                              UiPresentationMode.companion => CompanionModeView(
                                orbRect: dock.rect,
                                filePicker: widget.filePicker,
                              ),
                              UiPresentationMode.workspace => WorkspaceModeView(
                                filePicker: widget.filePicker,
                                attachmentOpener: widget.attachmentOpener,
                              ),
                              UiPresentationMode.dashboard => DashboardModeView(
                                orbRect: dock.rect,
                              ),
                            },
                          ),
                        ),
                        // The travelling orb.
                        AnimatedPositioned.fromRect(
                          duration: UriMotion.mode,
                          curve: UriMotion.move,
                          rect: dock.rect,
                          child: GestureDetector(
                            behavior: HitTestBehavior.opaque,
                            onTap: () => _onOrbTap(services),
                            onDoubleTap: () => services.presentation.setMode(
                              UiPresentationMode.workspace,
                            ),
                            // The user's companion (Companion Settings): a
                            // living identity, or the classic orb with its
                            // style and palette.
                            child: LivingCompanion(
                              key: LivingShell.orbKey,
                              state: signal.state,
                              progress: signal.progress,
                              size: dock.rect.width,
                              variant: services.orbVariant.value,
                              palette: services.orbPalette.value,
                              pokes: services.orbPokes,
                            ),
                          ),
                        ),
                        // The voice exchange, beside the companion.
                        if (!voiceDock.hidden)
                          AnimatedPositioned.fromRect(
                            duration: UriMotion.mode,
                            curve: UriMotion.move,
                            rect: voiceDock.rect,
                            child: IgnorePointer(
                              child: VoiceStage(
                                key: const ValueKey('shell-voice-stage'),
                                voice: services.voice,
                                compact: voiceDock.compact,
                              ),
                            ),
                          ),
                        _QuestionBubble(
                          text: _bubbleText,
                          orbRect: dock.rect,
                          shellSize: shellSize,
                        ),
                        _CommandNotice(services: services),
                        if (prefs.statsOverlay)
                          Positioned(
                            right: 10,
                            bottom: 10,
                            child: FrameStatsOverlay(
                              governor: services.frameGovernor,
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            );
          },
        );
      },
    );
  }
}

/// "URI opened Dashboard · Back": shown only after a command (not a
/// user gesture) moved the presentation, so the user always knows why
/// the UI changed and can undo it with one tap.
class _CommandNotice extends StatelessWidget {
  const _CommandNotice({required this.services});
  final LivingServices services;

  @override
  Widget build(BuildContext context) {
    final p = services.presentation;
    final show = p.lastCommandOrigin != UiCommandOrigin.user;
    final c = UriColors.of(context);
    return Positioned(
      left: 0,
      right: 0,
      bottom: 14,
      child: IgnorePointer(
        ignoring: !show,
        child: AnimatedOpacity(
          duration: UriMotion.fast,
          opacity: show ? 1 : 0,
          child: Center(
            child: Material(
              color: c.surfaceSunken.withValues(alpha: 0.92),
              borderRadius: BorderRadius.circular(999),
              child: Padding(
                padding: const EdgeInsets.fromLTRB(14, 6, 6, 6),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.auto_awesome, size: 14, color: c.accent),
                    const SizedBox(width: 8),
                    Text(
                      'URI opened ${p.mode.label}',
                      style: TextStyle(fontSize: 12.5, color: c.ink),
                    ),
                    const SizedBox(width: 6),
                    TextButton(
                      onPressed: () => p.back(),
                      child: const Text('Back'),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// The orb's click response: a short question, UI-local copy (never a
/// Brain reply), shown under the orb for a few seconds while the
/// composer takes focus.
class _QuestionBubble extends StatelessWidget {
  const _QuestionBubble({
    required this.text,
    required this.orbRect,
    required this.shellSize,
  });
  final String? text;
  final Rect orbRect;
  final Size shellSize;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    final show = text != null;
    // Below the orb when there is room, otherwise to its right.
    final below = orbRect.bottom + 48 < shellSize.height;
    final left = below
        ? (orbRect.center.dx - 110).clamp(8.0, shellSize.width - 228)
        : (orbRect.right + 8).clamp(8.0, shellSize.width - 228);
    final top = below ? orbRect.bottom - 6 : orbRect.center.dy - 16;
    return Positioned(
      left: left,
      top: top,
      width: 220,
      child: IgnorePointer(
        child: AnimatedOpacity(
          duration: UriMotion.fast,
          opacity: show ? 1 : 0,
          child: AnimatedSlide(
            duration: UriMotion.fast,
            offset: show ? Offset.zero : const Offset(0, -0.2),
            child: Center(
              child: Container(
                key: const ValueKey('orb-question-bubble'),
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 7,
                ),
                decoration: BoxDecoration(
                  color: glass.fillStrong,
                  borderRadius: BorderRadius.circular(999),
                  border: Border.all(color: glass.glow.withValues(alpha: 0.4)),
                ),
                child: Text(
                  text ?? '',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12.5, color: c.ink),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
