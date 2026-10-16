import 'dart:async';
import 'dart:math' as math;

import '../companion/frame_clock.dart';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../services/attachment_opener_service.dart';
import '../../services/file_picker_service.dart';
import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../companion/living_companion.dart';
import '../companion/companion_orb.dart' show CompanionIdentity;
import '../companion/companion_state.dart';
import '../living_scope.dart';
import '../voice/voice_stage.dart';
import '../voice/voice_session.dart' show VoicePhase;
import '../widgets/frame_stats_overlay.dart';
import '../assist/assist_mode_view.dart';
import '../screens/companion_mode_view.dart';
import '../screens/legacy_companion_mode_view.dart';
import '../widgets/glass_panel.dart';
import '../screens/dashboard_mode_view.dart';
import '../screens/workspace_mode_view.dart';
import 'presentation_controller.dart';
import 'companion_window_layout.dart';
import 'companion_activation_target.dart';

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

  /// Dashboard geometry, shared with FrostDashboard so the companion and the
  /// destinations around it always agree. Wide: the full composition (tall
  /// windows). Medium: the six destinations beside a smaller companion with
  /// the composer kept in view (common laptop windows such as 1366x768 and
  /// 1536x864). Otherwise one scrolling column.
  static bool dashboardWide(Size shell, double textScale) =>
      shell.width >= 1100 && shell.height >= 960 && textScale <= 22 / 14;
  static bool dashboardMedium(Size shell, double textScale) =>
      !dashboardWide(shell, textScale) &&
      shell.width >= 900 &&
      shell.height >= 640 &&
      textScale <= 1.2;
  static double dashboardRail(Size shell, double textScale) =>
      dashboardWide(shell, textScale) ||
          (dashboardMedium(shell, textScale) && shell.width >= 1100)
      ? 208
      : 0;
  static const double dashboardHeader = 196;
  static const double dashboardFooter = 150;

  /// Assist geometry, shared with the Assist header so they always agree.
  static const double assistOrbSize = 84;
  static const double assistOrbLeft = 20;
  static const double assistOrbTop = 16;

  static OrbDock forMode(
    UiPresentationMode mode,
    Size shell, {
    bool visualV2 = false,
    double textScale = 1,
    bool expanded = false,
  }) {
    switch (mode) {
      case UiPresentationMode.companion:
        if (visualV2 && expanded) {
          final size = shell.width > 480
              ? math.min(shell.width * .495, shell.height * .36)
              : (shell.width - 220).clamp(140.0, 220.0);
          return OrbDock(
            rect: Rect.fromLTWH(
              (shell.width - size) / 2,
              shell.height * (shell.width > 480 ? .297 : .31) - size / 2,
              size,
              size,
            ),
            lightAt: const Alignment(0, -1),
          );
        }
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
        if (!visualV2) {
          return OrbDock(
            rect: Rect.fromLTWH(shell.width / 2 - 64, 18, 128, 128),
            lightAt: const Alignment(0, -1),
          );
        }
        if (dashboardMedium(shell, textScale)) {
          final rail = dashboardRail(shell, textScale);
          final middle = shell.height - dashboardHeader - dashboardFooter;
          final size = (middle - 56).clamp(120.0, 200.0);
          return OrbDock(
            rect: Rect.fromCenter(
              center: Offset(
                rail + (shell.width - rail) / 2,
                dashboardHeader + (middle - 36) / 2,
              ),
              width: size,
              height: size,
            ),
            lightAt: const Alignment(0, -1),
          );
        }
        final wide = dashboardWide(shell, textScale);
        final size = wide ? 360.0 : 180.0;
        return OrbDock(
          rect: Rect.fromCenter(
            center: Offset(
              wide ? (shell.width + 208) / 2 : shell.width / 2,
              wide
                  ? shell.height * .45
                  : math.min(
                          shell.height * .5,
                          (shell.width < 500 ? 320.0 : 260.0) +
                              math.max(0, textScale - 1) * 100,
                        ) +
                        (shell.height * .35).clamp(0, 220) / 2,
            ),
            width: size,
            height: size,
          ),
          lightAt: const Alignment(0, -1),
        );
      case UiPresentationMode.assist:
        // Top-left, beside the Assist header (AssistModeView.orbSpace).
        return OrbDock(
          rect: Rect.fromLTWH(
            assistOrbLeft,
            assistOrbTop,
            assistOrbSize,
            assistOrbSize,
          ),
          lightAt: const Alignment(-0.8, -1),
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
/// * Assist: a slim pill centred at the bottom (the header holds the orb and
///   the scope controls; the view keeps [assistBottomReserve] free).
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

  /// Space the Assist view leaves free at its bottom for the voice pill.
  static const double assistBottomReserve = VoiceStage.compactHeight + 20;

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
      case UiPresentationMode.assist:
        final w = (shell.width - 32).clamp(200.0, 440.0);
        return VoiceDock(
          rect: Rect.fromLTWH(
            (shell.width - w) / 2,
            shell.height - VoiceStage.compactHeight - 10,
            w,
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
  bool _panelExpanded = false;
  bool _chatOpen = false;
  CompanionWindowLayout? _windowLayout;
  CompanionFrameClock? _orbitClock;
  double _orbitAngle = 0, _lastOrbitFrame = 0, _holdOrbitUntil = 0;
  bool _readingPointer = false;
  Rect? _orbitBounds;

  // Mode keys (Ctrl+1..4, Escape). The CallbackShortcuts below handles them
  // while focus is inside the shell. When a focused control goes away (the
  // composer is disabled while URI works), focus falls to the page's scope,
  // above the shell, and those keys stopped working; the keyboard handler
  // applies the same bindings then, and only while this page is on top.
  final FocusNode _shellFocus = FocusNode(debugLabel: 'living-shell');
  Map<ShortcutActivator, VoidCallback> _bindings = const {};

  @override
  void initState() {
    super.initState();
    HardwareKeyboard.instance.addHandler(_onKey);
  }

  bool _onKey(KeyEvent event) {
    if (!mounted || event is KeyUpEvent) return false;
    if (ModalRoute.of(context)?.isCurrent == false) return false;
    final primary = FocusManager.instance.primaryFocus;
    if (primary != null &&
        (primary == _shellFocus || primary.ancestors.contains(_shellFocus))) {
      return false; // inside the shell: the CallbackShortcuts handles it
    }
    for (final entry in _bindings.entries) {
      if (entry.key.accepts(event, HardwareKeyboard.instance)) {
        entry.value();
        return true;
      }
    }
    return false;
  }

  bool _orbitListening = false;
  void _configureOrbit(LivingServices services, bool enabled) {
    final clock = services.frameClock;
    if (!identical(clock, _orbitClock)) {
      if (_orbitListening) _orbitClock?.removeListener(_orbitTick);
      _orbitListening = false;
      _orbitClock = clock;
    }
    if (enabled == _orbitListening) return;
    _orbitListening = enabled;
    if (enabled) {
      clock.addListener(_orbitTick);
    } else {
      clock.removeListener(_orbitTick);
    }
  }

  void _holdOrbit() {
    _holdOrbitUntil = (_orbitClock?.seconds ?? 0) + 1.5;
  }

  void _orbitTick() {
    if (!mounted) return;
    final s = LivingScope.of(context);
    final now = s.frameClock.seconds;
    final delta = now - _lastOrbitFrame;
    if (delta < .1) return;
    _lastOrbitFrame = now;
    if (!s.visualV2 ||
        !_panelExpanded ||
        _chatOpen ||
        s.presentation.mode != UiPresentationMode.companion ||
        s.frameClock.hidden ||
        s.effects.reducedMotion ||
        MediaQuery.disableAnimationsOf(context) ||
        MediaQuery.textScalerOf(context).scale(14) / 14 > 1.2 ||
        s.composerFocus.hasFocus ||
        s.voice.session.phase != VoicePhase.off ||
        CompanionModeView.actions(
              s,
              CompanionModeView.reviewCount(s, context),
            ).length >
            4) {
      return;
    }
    final read = s.readCompanionPointer;
    if (read != null && !_readingPointer) {
      _readingPointer = true;
      read()
          .then((point) {
            if (!mounted) return;
            // Missing native cursor support fails static, never evasive controls.
            if (point == null ||
                _orbitBounds?.inflate(80).contains(point) == true) {
              _holdOrbit();
            }
          })
          .whenComplete(() => _readingPointer = false);
    }
    if (now < _holdOrbitUntil) return;
    setState(
      () => _orbitAngle =
          (_orbitAngle + math.min(delta, .15) * math.pi * 2 / 180) %
          (math.pi * 2),
    );
  }

  static const List<String> _questions = [
    'Yes? What should I do?',
    "I'm here. What's next?",
    'Tell me what you need.',
    'Listening. Type it below.',
  ];

  void _onOrbTap(LivingServices services) {
    final n = services.orbPokes.value + 1;
    services.orbPokes.value = n;
    final acknowledgement = _questions[n % _questions.length];
    setState(() {
      _bubbleText = acknowledgement;
      if (services.visualV2) {
        _panelExpanded = true;
      }
    });
    // Local acknowledgement only: never submit a Brain request or interrupt
    // an ongoing utterance. Use the installed live voice service when ready.
    if (services.visualV2 &&
        services.liveVoice?.status.value.ready == true &&
        services.voice.session.phase == VoicePhase.off) {
      services.liveVoice!.speak(
        'companion-ack-$n',
        acknowledgement,
        services.companionPrefs.voice,
      );
    }
    _bubbleTimer?.cancel();
    _bubbleTimer = Timer(const Duration(seconds: 4), () {
      if (mounted) setState(() => _bubbleText = null);
    });
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && !services.visualV2) {
        services.composerFocus.requestFocus();
      }
    });
  }

  @override
  void dispose() {
    HardwareKeyboard.instance.removeHandler(_onKey);
    _shellFocus.dispose();
    _bubbleTimer?.cancel();
    _orbitClock?.removeListener(_orbitTick);
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    return ListenableBuilder(
      listenable: Listenable.merge([
        services.presentation,
        services.effects,
        services.companion,
        services.orbVariant,
        services.orbPalette,
        services.companionPrefs,
        services.voice,
        ?services.voiceInteraction,
        ?services.liveVoice?.status,
        ?services.oi,
        services.work,
        ?services.a2ui,
      ]),
      builder: (context, _) {
        final mode = services.presentation.mode;
        final signal = services.companion.signal;
        return LayoutBuilder(
          builder: (context, constraints) {
            final shellSize = Size(constraints.maxWidth, constraints.maxHeight);
            _configureOrbit(
              services,
              services.visualV2 &&
                  _panelExpanded &&
                  !_chatOpen &&
                  mode == UiPresentationMode.companion &&
                  CompanionModeView.usesOrbit(shellSize) &&
                  !services.effects.reducedMotion &&
                  !MediaQuery.disableAnimationsOf(context) &&
                  MediaQuery.textScalerOf(context).scale(14) / 14 <= 1.2,
            );
            final dock = OrbDock.forMode(
              mode,
              shellSize,
              visualV2: services.visualV2,
              textScale: MediaQuery.textScalerOf(context).scale(14) / 14,
              expanded: _panelExpanded,
            );
            _orbitBounds = Rect.fromCircle(
              center: dock.rect.center,
              radius:
                  CompanionModeView.orbitRadius(shellSize) +
                  CompanionModeView.buttonDiameter(shellSize) / 2,
            );
            final voiceDock = VoiceDock.forMode(mode, shellSize, dock.rect);
            final prefs = services.companionPrefs;
            final duration = services.visualV2
                ? (mode == UiPresentationMode.companion ||
                          services.effects.reducedMotion ||
                          MediaQuery.disableAnimationsOf(context)
                      ? Duration.zero
                      : const Duration(milliseconds: 240))
                : UriMotion.mode;
            final buttonRects = _panelExpanded
                ? CompanionModeView.buttonRects(
                    shellSize,
                    dock.rect,
                    CompanionModeView.actions(
                      services,
                      CompanionModeView.reviewCount(services, context),
                    ),
                    textScale: MediaQuery.textScalerOf(context).scale(14) / 14,
                    angle: _orbitAngle,
                  ).values.toList()
                : <Rect>[];
            final layout = CompanionWindowLayout(
              active: mode == UiPresentationMode.companion,
              orb: dock.rect,
              buttons: buttonRects,
              orbit: _panelExpanded
                  ? Rect.fromCircle(
                      center: dock.rect.center,
                      radius: CompanionModeView.orbitRadius(shellSize),
                    )
                  : null,
              controls:
                  _panelExpanded &&
                      services.voice.session.phase != VoicePhase.off
                  ? CompanionModeView.voiceRect(
                      shellSize,
                      dock.rect,
                      buttons: buttonRects,
                      textScale:
                          MediaQuery.textScalerOf(context).scale(14) / 14,
                    )
                  : null,
              panel: _panelExpanded && _chatOpen
                  ? CompanionModeView.chatRect(
                      shellSize,
                      dock.rect,
                      voiceVisible:
                          services.voice.session.phase != VoicePhase.off,
                      textScale:
                          MediaQuery.textScalerOf(context).scale(14) / 14,
                      buttons: buttonRects,
                    )
                  : null,
            );
            if (layout != _windowLayout) {
              _windowLayout = layout;
              WidgetsBinding.instance.addPostFrameCallback((_) {
                if (mounted) services.updateCompanionWindow?.call(layout);
              });
            }
            _bindings = {
              const SingleActivator(LogicalKeyboardKey.escape): () {
                if (services.visualV2 &&
                    mode == UiPresentationMode.companion &&
                    (_chatOpen || _panelExpanded)) {
                  setState(() {
                    if (_chatOpen) {
                      _chatOpen = false;
                    } else {
                      _panelExpanded = false;
                    }
                  });
                } else {
                  services.presentation.setMode(UiPresentationMode.companion);
                }
              },
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
              const SingleActivator(
                LogicalKeyboardKey.digit4,
                control: true,
              ): () =>
                  services.presentation.setMode(UiPresentationMode.assist),
            };
            return CallbackShortcuts(
              // Escape dismisses transient Companion UI before changing forms.
              bindings: _bindings,
              child: Focus(
                focusNode: _shellFocus,
                autofocus: true,
                child: Scaffold(
                  backgroundColor: Colors.transparent,
                  body: _ShellCanvas(
                    mode: mode,
                    v2: services.visualV2,
                    dock: dock,
                    child: Stack(
                      fit: StackFit.expand,
                      children: [
                        // Mode content, cross-faded with a small drift so it
                        // feels like the space re-arranging, not a page flip.
                        AnimatedSwitcher(
                          duration: duration,
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
                              UiPresentationMode.companion =>
                                services.visualV2
                                    ? CompanionModeView(
                                        orbRect: dock.rect,
                                        filePicker: widget.filePicker,
                                        attachmentOpener:
                                            widget.attachmentOpener,
                                        expanded: _panelExpanded,
                                        chatOpen: _chatOpen,
                                        angle: _orbitAngle,
                                        onPointerNear: _holdOrbit,
                                        onChatChanged: (value) =>
                                            setState(() => _chatOpen = value),
                                        acknowledgement: _bubbleText,
                                        onCollapse: () => setState(
                                          () => _panelExpanded = false,
                                        ),
                                      )
                                    : LegacyCompanionModeView(
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
                              UiPresentationMode.assist => AssistModeView(
                                orbRect: dock.rect,
                              ),
                            },
                          ),
                        ),
                        // The travelling orb.
                        AnimatedPositioned.fromRect(
                          duration: duration,
                          curve: UriMotion.move,
                          rect: dock.rect,
                          child: GestureDetector(
                            behavior: HitTestBehavior.opaque,
                            excludeFromSemantics: services.visualV2,
                            onPanStart:
                                mode == UiPresentationMode.companion &&
                                    services.moveCompanionWindow != null
                                ? (_) => services.moveCompanionWindow!()
                                : null,
                            onTap: () => _onOrbTap(services),
                            onDoubleTap: () => services.presentation.setMode(
                              services.visualV2
                                  ? UiPresentationMode.dashboard
                                  : UiPresentationMode.workspace,
                            ),
                            // The user's companion (Companion Settings): a
                            // living identity, or the classic orb with its
                            // style and palette.
                            child: CompanionActivationTarget(
                              onActivate: () => _onOrbTap(services),
                              label:
                                  'URI Companion: ${signal.state == CompanionState.success ? 'Reply received' : signal.title}. Activate to open chat; Control 3 opens dashboard.',
                              child: LivingCompanion(
                                key: LivingShell.orbKey,
                                preserveIdentityTheme: services.visualV2,
                                presentationScale:
                                    services.visualV2 &&
                                        mode == UiPresentationMode.companion &&
                                        prefs.choice.identity ==
                                            CompanionIdentity.solar
                                    ? 1.85
                                    : 1,
                                state: signal.state,
                                progress: signal.progress,
                                size: dock.rect.width,
                                variant:
                                    services.visualV2 && prefs.choice.isClassic
                                    ? prefs.classicVariant
                                    : services.orbVariant.value,
                                palette: services.orbPalette.value,
                                pokes: services.orbPokes,
                              ),
                            ),
                          ),
                        ),
                        // The voice exchange, beside the companion.
                        if (!voiceDock.hidden &&
                            (!services.visualV2 ||
                                mode == UiPresentationMode.workspace ||
                                mode == UiPresentationMode.assist))
                          AnimatedPositioned.fromRect(
                            duration: duration,
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
                        if (!services.visualV2 ||
                            mode != UiPresentationMode.companion)
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
class _ShellCanvas extends StatelessWidget {
  const _ShellCanvas({
    required this.mode,
    required this.v2,
    required this.dock,
    required this.child,
  });
  final UiPresentationMode mode;
  final bool v2;
  final OrbDock dock;
  final Widget child;
  @override
  Widget build(BuildContext context) => v2
      ? Material(
          type: mode == UiPresentationMode.companion
              ? MaterialType.transparency
              : MaterialType.canvas,
          color: mode == UiPresentationMode.companion
              ? null
              : UriColors.of(context).canvas,
          child: child,
        )
      : AmbientBackground(
          lightAt: dock.lightAt,
          lightStrength: mode == UiPresentationMode.companion ? 1 : .6,
          child: child,
        );
}

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
