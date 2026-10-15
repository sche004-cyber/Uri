import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../services/app_state_scope.dart';
import '../../models/uri_turn.dart';
import '../../theme/uri_theme.dart';
import '../integration/oi_widgets.dart';
import '../widgets/living_composer.dart';
import '../../services/attachment_opener_service.dart';
import '../../services/file_picker_service.dart';
import '../a2ui/a2ui_view.dart';
import '../a2ui/companion_actions.dart';
import '../living_scope.dart';
import '../presentation/presentation_controller.dart';
import '../voice/voice_interaction.dart' as interaction;
import '../voice/voice_session.dart';
import '../voice/voice_stage.dart';
import 'workspace_mode_view.dart' show pendingDecisionCount;

/// Approved detached-chat composition, using the existing Companion and
/// shared conversation. Open/closed chat is transient, never a design choice.
class CompanionModeView extends StatefulWidget {
  const CompanionModeView({
    super.key,
    required this.orbRect,
    this.filePicker,
    this.attachmentOpener,
    this.expanded = false,
    this.onCollapse,
    this.acknowledgement,
    this.chatOpen = false,
    this.onChatChanged,
    this.angle = 0,
    this.onPointerNear,
  });
  final Rect orbRect;
  final bool chatOpen;
  final double angle;
  final VoidCallback? onPointerNear;
  final ValueChanged<bool>? onChatChanged;
  final FilePickerFn? filePicker;
  final AttachmentOpenerFn? attachmentOpener;
  final bool expanded;
  final VoidCallback? onCollapse;
  final String? acknowledgement;

  static List<CompanionUiAction> actions(LivingServices s, int pending) => [
    CompanionUiAction.chat,
    if (pending > 0) CompanionUiAction.review,
    if (s.voiceInteraction?.available == true &&
        s.voiceInteraction?.stage == interaction.VoiceStage.idle &&
        s.oi?.busy != true)
      CompanionUiAction.voiceStart,
    if (s.voiceInteraction?.stage == interaction.VoiceStage.listening)
      CompanionUiAction.voiceFinish,
    if (s.voiceInteraction != null &&
        s.voiceInteraction!.stage != interaction.VoiceStage.idle)
      CompanionUiAction.voiceCancel,
    CompanionUiAction.dashboard,
  ];
  static Map<CompanionUiAction, Rect> buttonRects(
    Size size,
    Rect orb,
    List<CompanionUiAction> actions, {
    double textScale = 1,
    double angle = 0,
  }) {
    if (actions.length <= 4 && textScale <= 1.2 && usesOrbit(size)) {
      final diameter = buttonDiameter(size);
      final radius = orbitRadius(size);
      final result = <CompanionUiAction, Rect>{};
      for (final action in actions) {
        final phase = switch (action) {
          CompanionUiAction.chat => math.pi,
          CompanionUiAction.dashboard => 0.0,
          CompanionUiAction.review => -math.pi / 2,
          CompanionUiAction.voiceCancel =>
            actions.contains(CompanionUiAction.voiceFinish)
                ? -math.pi / 2
                : math.pi / 2,
          _ => math.pi / 2,
        };
        result[action] = Rect.fromCenter(
          center:
              orb.center +
              Offset(
                math.cos(phase + angle) * radius,
                math.sin(phase + angle) * orbitVerticalRadius(size),
              ),
          width: diameter,
          height: diameter,
        );
      }
      return result;
    }
    final maxWidth = ((size.width - orb.width) / 2 - 20).clamp(52.0, 144.0);
    final rows = (actions.length / 2).ceil();
    final sizes = <Size>[];
    for (final action in actions) {
      final text = TextPainter(
        text: TextSpan(
          text: CompanionActions.labels[action],
          style: const TextStyle(fontSize: 14, fontFamily: 'Segoe UI'),
        ),
        textDirection: TextDirection.ltr,
        textScaler: TextScaler.linear(textScale),
      )..layout();
      final width = (text.width.ceilToDouble() + 20).clamp(44.0, maxWidth);
      text.layout(maxWidth: width - 20);
      sizes.add(
        Size(
          width,
          (text.height.ceilToDouble() + 16).clamp(44.0, double.infinity),
        ),
      );
      text.dispose();
    }
    final heights = List.generate(rows, (row) {
      final first = sizes[row * 2].height;
      return row * 2 + 1 < sizes.length && sizes[row * 2 + 1].height > first
          ? sizes[row * 2 + 1].height
          : first;
    });
    final total = heights.fold<double>(0, (a, b) => a + b) + (rows - 1) * 12;
    var top = (orb.center.dy - total / 2).clamp(
      12.0,
      (size.height - total - 12).clamp(12.0, double.infinity),
    );
    final result = <CompanionUiAction, Rect>{};
    for (var i = 0; i < actions.length; i++) {
      final button = sizes[i];
      result[actions[i]] = Rect.fromLTWH(
        i.isEven ? 8 : size.width - button.width - 8,
        top + (heights[i ~/ 2] - button.height) / 2,
        button.width,
        button.height,
      );
      if (i.isOdd) top += heights[i ~/ 2] + 12;
    }
    return result;
  }

  static bool usesOrbit(Size size) => size.height >= size.width * 1.4;
  static double buttonDiameter(Size size) =>
      (size.width * .12).clamp(80.0, 100.0);
  static double voiceScale(Size size) =>
      usesOrbit(size) ? (size.width / 500).clamp(1.0, 1.7) : 1;
  static double orbitRadius(Size size) {
    final diameter = buttonDiameter(size);
    final wanted = size.width > 480
        ? size.width * .34
        : ((size.width - diameter) / 2 - 20).clamp(0.0, 160.0);
    final centerY = size.height * (size.width > 480 ? .297 : .31);
    return math.min(
      wanted,
      math.min(size.width / 2 - diameter / 2 - 12, centerY - diameter / 2 - 12),
    );
  }

  static double orbitVerticalRadius(Size size) =>
      orbitRadius(size) * (size.width > 480 ? .947 : 1);

  static Rect voiceRect(
    Size size,
    Rect orb, {
    Iterable<Rect> buttons = const [],
    double textScale = 1,
  }) {
    final bottom = textScale > 1.2 || !usesOrbit(size)
        ? buttons.fold<double>(orb.bottom, (b, r) => math.max(b, r.bottom))
        : math.max(
            orb.bottom,
            orb.center.dy +
                orbitVerticalRadius(size) +
                buttonDiameter(size) / 2,
          );
    return Rect.fromLTWH(
      24,
      bottom + (size.width > 480 ? 20 : 10),
      size.width - 48,
      (textScale > 1.2 ? 90 : 64) * voiceScale(size),
    );
  }

  static Rect chatRect(
    Size size,
    Rect orb, {
    double textScale = 1,
    Iterable<Rect> buttons = const [],
    bool voiceVisible = true,
  }) {
    final width = textScale > 1.2
        ? size.width - 24
        : size.width > 480
        ? math.min(size.width * .54, 450.0)
        : (size.width * .72).clamp(260.0, 320.0);
    final wave = voiceRect(size, orb, textScale: textScale, buttons: buttons);
    final top = voiceVisible
        ? wave.bottom + (size.width > 480 ? 20 : 10)
        : wave.top;
    return Rect.fromLTWH(
      (size.width - width) / 2,
      top,
      width,
      math.max(
        96,
        textScale > 1.2
            ? size.height - top - 12
            : math.min(
                size.height - top - 12,
                math.max(184, size.height * .215),
              ),
      ),
    );
  }

  static int reviewCount(LivingServices s, BuildContext context) =>
      pendingDecisionCount(AppStateScope.of(context), s.work) +
      (s.oi?.pendingApproval == null ? 0 : 1) +
      (s.oi?.pendingConfirmation == null ? 0 : 1) +
      (s.a2ui?.surfaces.length ?? 0) +
      ((s.a2ui?.notices.isNotEmpty ?? false) ? 1 : 0);
  @override
  State<CompanionModeView> createState() => _CompanionModeViewState();
}

class _CompanionModeViewState extends State<CompanionModeView> {
  late final _actions = CompanionActions(_invoke);
  @override
  void dispose() {
    _actions.dispose();
    super.dispose();
  }

  Future<void> _invoke(CompanionUiAction action) async {
    if (!mounted) return;
    final s = LivingScope.of(context);
    final voice = s.voiceInteraction;
    switch (action) {
      case CompanionUiAction.chat:
        widget.onChatChanged?.call(!widget.chatOpen);
      case CompanionUiAction.workspace:
        s.presentation.setMode(
          UiPresentationMode.workspace,
          focus: WorkspaceFocus.conversation,
        );
      case CompanionUiAction.review:
        if (CompanionModeView.reviewCount(s, context) > 0) {
          s.presentation.setMode(
            UiPresentationMode.workspace,
            focus: WorkspaceFocus.tasks,
          );
        }
      case CompanionUiAction.dashboard:
        s.presentation.setMode(UiPresentationMode.dashboard);
      case CompanionUiAction.collapse:
        widget.onCollapse?.call();
      case CompanionUiAction.voiceStart:
        if (voice?.available != true ||
            voice!.stage != interaction.VoiceStage.idle ||
            s.oi?.busy == true) {
          return;
        }
        await voice.pressTalk();
      case CompanionUiAction.voiceFinish:
        if (voice?.stage == interaction.VoiceStage.listening) {
          voice!.releaseTalk();
        }
      case CompanionUiAction.voiceCancel:
        voice?.cancel();
    }
  }

  @override
  Widget build(BuildContext context) {
    if (!widget.expanded) return const SizedBox.shrink();
    final s = LivingScope.of(context);
    return ListenableBuilder(
      listenable: Listenable.merge([
        AppStateScope.of(context),
        s.work,
        s.voice,
        ?s.oi,
        ?s.voiceInteraction,
        ?s.liveVoice?.status,
        ?s.a2ui,
      ]),
      builder: (_, _) {
        final actions = CompanionModeView.actions(
          s,
          CompanionModeView.reviewCount(s, context),
        );
        WidgetsBinding.instance.addPostFrameCallback((_) {
          if (mounted) _actions.project(actions);
        });
        return LayoutBuilder(
          builder: (_, box) {
            final rects = CompanionModeView.buttonRects(
              box.biggest,
              widget.orbRect,
              actions,
              textScale: MediaQuery.textScalerOf(context).scale(14) / 14,
              angle: widget.angle,
            );
            return MouseRegion(
              onEnter: (_) => widget.onPointerNear?.call(),
              onHover: (_) => widget.onPointerNear?.call(),
              child: Listener(
                onPointerDown: (_) => widget.onPointerNear?.call(),
                child: Stack(
                  children: [
                    if (CompanionModeView.usesOrbit(box.biggest))
                      Positioned.fill(
                        child: IgnorePointer(
                          child: CustomPaint(
                            painter: _OrbitArcs(
                              widget.orbRect.center,
                              CompanionModeView.orbitRadius(box.biggest),
                              UriColors.of(context).accentSoft,
                            ),
                          ),
                        ),
                      ),
                    if (widget.chatOpen)
                      Positioned.fromRect(
                        rect: CompanionModeView.chatRect(
                          box.biggest,
                          widget.orbRect,
                          voiceVisible:
                              s.voice.session.phase != VoicePhase.off,
                          textScale:
                              MediaQuery.textScalerOf(context).scale(14) / 14,
                          buttons: rects.values,
                        ),
                        child: MediaQuery(
                          data: MediaQuery.of(context).copyWith(
                            textScaler: TextScaler.linear(
                              MediaQuery.textScalerOf(context).scale(14) /
                                  14 *
                                  (MediaQuery.textScalerOf(context).scale(14) /
                                              14 >
                                          1.2
                                      ? 1
                                      : (box.maxWidth / 440).clamp(1.0, 1.5)),
                            ),
                          ),
                          child: _DetachedChat(
                            filePicker: widget.filePicker,
                            attachmentOpener: widget.attachmentOpener,
                            onClose: () => widget.onChatChanged?.call(false),
                          ),
                        ),
                      ),
                    if (widget.acknowledgement != null)
                      Semantics(
                        liveRegion: true,
                        label: widget.acknowledgement,
                        child: const SizedBox.shrink(),
                      ),
                    for (final entry in rects.entries)
                      Positioned.fromRect(
                        rect: entry.value,
                        child: SizedBox(
                          height: entry.value.height,
                          child: Tooltip(
                            message: switch (entry.key) {
                              CompanionUiAction.voiceStart =>
                                'Start voice input',
                              CompanionUiAction.voiceFinish =>
                                'Finish speaking',
                              CompanionUiAction.voiceCancel =>
                                'Cancel voice input',
                              CompanionUiAction.review =>
                                'Review pending decisions',
                              _ => CompanionActions.labels[entry.key]!,
                            },
                            child: A2uiSurfaceView(
                              hub: _actions.hub,
                              surfaceId: CompanionActions.surfaceId,
                              rootId: entry.key.name,
                              compact: true,
                              bare: true,
                              hostIcon:
                                  actions.length <= 4 &&
                                      CompanionModeView.usesOrbit(
                                        box.biggest,
                                      ) &&
                                      MediaQuery.textScalerOf(context)
                                                  .scale(14) /
                                              14 <=
                                          1.2
                                  ? switch (entry.key) {
                                      CompanionUiAction.chat =>
                                        Icons.chat_bubble_outline_rounded,
                                      CompanionUiAction.dashboard =>
                                        Icons.bar_chart_rounded,
                                      CompanionUiAction.review =>
                                        Icons.fact_check_outlined,
                                      CompanionUiAction.voiceFinish =>
                                        Icons.stop_rounded,
                                      CompanionUiAction.voiceCancel =>
                                        Icons.close_rounded,
                                      _ => Icons.mic_none_rounded,
                                    }
                                  : null,
                            ),
                          ),
                        ),
                      ),
                    if (s.voice.session.phase != VoicePhase.off)
                      Positioned.fromRect(
                        rect: CompanionModeView.voiceRect(
                          box.biggest,
                          widget.orbRect,
                          buttons: rects.values,
                          textScale:
                              MediaQuery.textScalerOf(context).scale(14) / 14,
                        ),
                        child: VoiceStage(
                          key: const ValueKey('companion-voice-visual'),
                          voice: s.voice,
                          compact: true,
                          borderless: true,
                          showListening: true,
                          vertical: true,
                          visualScale: CompanionModeView.voiceScale(
                            box.biggest,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }
}

class _DetachedChat extends StatelessWidget {
  const _DetachedChat({
    this.filePicker,
    this.attachmentOpener,
    required this.onClose,
  });
  final FilePickerFn? filePicker;
  final AttachmentOpenerFn? attachmentOpener;
  final VoidCallback onClose;
  @override
  Widget build(BuildContext context) {
    final s = LivingScope.of(context);
    final c = UriColors.of(context);
    return LayoutBuilder(
      builder: (context, box) {
        final referenceSize = box.maxWidth > 350;
        return Material(
          key: const ValueKey('companion-detached-chat'),
          color: c.surface,
          borderRadius: BorderRadius.circular(referenceSize ? 22 : 18),
          clipBehavior: Clip.antiAlias,
          child: Column(
            children: [
              SizedBox(
                height: referenceSize ? 64 : 48,
                child: Padding(
                  padding: EdgeInsets.only(
                    left: referenceSize ? 24 : 14,
                    right: referenceSize ? 10 : 4,
                  ),
                  child: Row(
                    children: [
                      Expanded(
                        child: Text(
                          'Conversation',
                          style: TextStyle(fontSize: referenceSize ? 18 : 16),
                        ),
                      ),
                      IconButton(
                        key: const ValueKey('companion-close-chat'),
                        tooltip: 'Close conversation',
                        onPressed: onClose,
                        icon: Icon(
                          Icons.close_rounded,
                          size: referenceSize ? 26 : 20,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              Expanded(
                // Earlier messages fade out under the header instead of
                // being cut into a thin sliver.
                child: ShaderMask(
                  key: const ValueKey('companion-chat-fade'),
                  blendMode: BlendMode.dstIn,
                  shaderCallback: (bounds) => LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: const [Colors.transparent, Colors.black],
                    stops: [0, (16 / math.max(bounds.height, 16)).clamp(0, 1)],
                  ).createShader(bounds),
                  child: Padding(
                    padding: EdgeInsets.symmetric(
                      horizontal: referenceSize ? 24 : 12,
                    ),
                    child: s.oi != null
                        ? OiConversationPane(conversation: s.oi!, compact: true)
                        : const _DetachedClassicConversation(),
                  ),
                ),
              ),
              Padding(
                padding: EdgeInsets.only(
                  left: referenceSize ? 10 : 0,
                  right: referenceSize ? 10 : 0,
                  bottom: referenceSize ? 12 : 2,
                ),
                child: LivingComposer(
                  compact: true,
                  minimal: true,
                  floating: true,
                  hint: 'Ask URI…',
                  filePicker: filePicker,
                ),
              ),
            ],
          ),
        );
      },
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
    final paint = Paint()
      ..color = color.withValues(alpha: .85)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.4;
    final bounds = Rect.fromCircle(center: center, radius: radius);
    for (final arc in [
      (-2.87, .58),
      (-.84, .57),
      (.24, .41),
      (.86, .45),
      (2.28, .62),
    ]) {
      final angle = arc.$1;
      canvas.drawArc(bounds, angle, arc.$2, false, paint);
      final point =
          center +
          Offset(math.cos(angle + .23), math.sin(angle + .23)) * radius;
      canvas.drawCircle(point, radius > 200 ? 4 : 3, Paint()..color = color);
    }
  }

  @override
  bool shouldRepaint(_OrbitArcs old) =>
      old.center != center || old.radius != radius || old.color != color;
}

/// A compact projection of the same classic conversation. Decisions and
/// receipts stay on the full review surface, never inferred from reply text.
class _DetachedClassicConversation extends StatelessWidget {
  const _DetachedClassicConversation();
  @override
  Widget build(BuildContext context) {
    final app = AppStateScope.of(context);
    final c = UriColors.of(context);
    return ListenableBuilder(
      listenable: app,
      builder: (context, _) {
        final referenceSize = MediaQuery.sizeOf(context).width > 480;
        Widget bubble(String text, bool user) => Align(
          alignment: user ? Alignment.centerRight : Alignment.centerLeft,
          child: Container(
            margin: EdgeInsets.only(bottom: referenceSize ? 16 : 8),
            padding: EdgeInsets.symmetric(
              horizontal: referenceSize ? 16 : 12,
              vertical: referenceSize ? 12 : 6,
            ),
            decoration: BoxDecoration(
              color: user
                  ? Color.lerp(c.surface, c.surfaceSunken, .6)
                  : c.surface,
              borderRadius: BorderRadius.circular(referenceSize ? 20 : 14),
            ),
            child: Text(text, style: TextStyle(fontSize: 14, color: c.ink)),
          ),
        );
        final messages = <Widget>[];
        for (final turn in app.conversation) {
          messages.add(bubble(turn.userText, true));
          final text =
              turn.failureReason ?? turn.result?.summary ?? turn.understanding;
          if (text != null && text.isNotEmpty) {
            messages.add(bubble(text, false));
          }
          if (turn.stage != TurnStage.completed) {
            messages.add(
              Text(
                switch (turn.stage) {
                  TurnStage.understanding => 'Waiting for URI…',
                  TurnStage.proposalReady ||
                  TurnStage.awaitingApproval => 'Awaiting review — open Review',
                  TurnStage.executing =>
                    'Working — open Review for execution details',
                  TurnStage.cancelled => 'Cancelled',
                  TurnStage.failed => 'Request failed',
                  TurnStage.needsConnection =>
                    'Connection required — open Dashboard',
                  _ => '',
                },
                style: TextStyle(
                  fontSize: 14,
                  color: turn.stage == TurnStage.failed ? c.danger : c.inkSoft,
                ),
              ),
            );
          }
        }
        if (messages.isEmpty) {
          messages.add(
            Text(
              'Ask URI anything to begin.',
              style: TextStyle(color: c.inkSoft, fontSize: 14),
            ),
          );
        }
        return LayoutBuilder(
          builder: (context, box) => Align(
            alignment: Alignment.topCenter,
            child: ListView(
              shrinkWrap: true,
              reverse: true,
              padding: EdgeInsets.only(top: box.maxWidth > 350 ? 0 : 4),
              children: messages.reversed.toList(),
            ),
          ),
        );
      },
    );
  }
}
