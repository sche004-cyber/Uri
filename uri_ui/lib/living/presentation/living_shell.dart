import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../services/attachment_opener_service.dart';
import '../../services/file_picker_service.dart';
import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../companion/energy_orb.dart';
import '../living_scope.dart';
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
        const size = 72.0;
        return const OrbDock(
          rect: Rect.fromLTWH(8, 10, size, size),
          lightAt: Alignment(-0.95, -0.95),
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
      ]),
      builder: (context, _) {
        final mode = services.presentation.mode;
        final signal = services.companion.signal;
        return LayoutBuilder(
          builder: (context, constraints) {
            final shellSize = Size(constraints.maxWidth, constraints.maxHeight);
            final dock = OrbDock.forMode(mode, shellSize);
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
                            child: EnergyOrb(
                              key: LivingShell.orbKey,
                              state: signal.state,
                              progress: signal.progress,
                              size: dock.rect.width,
                              variant: services.orbVariant.value,
                              pokes: services.orbPokes,
                            ),
                          ),
                        ),
                        _QuestionBubble(
                          text: _bubbleText,
                          orbRect: dock.rect,
                          shellSize: shellSize,
                        ),
                        _CommandNotice(services: services),
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
