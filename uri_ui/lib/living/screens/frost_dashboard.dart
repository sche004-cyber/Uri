import 'dart:math' as math;

import 'package:flutter/material.dart';

import '../../screens/connections/connections_providers_screen.dart';
import '../../services/app_state_scope.dart';
import '../../theme/uri_theme.dart';
import '../companion/companion_design.dart';
import '../companion/companion_state.dart';
import '../living_scope.dart';
import '../integration/scheduler_client.dart';
import '../integration/ws_settings.dart' show WorkingSystemShellSwitch;
import '../presentation/living_shell.dart' show OrbDock;
import '../presentation/presentation_controller.dart';
import '../widgets/living_composer.dart';
import 'scheduler/scheduler_view.dart';
import 'workspace_mode_view.dart' show pendingDecisionCount;

/// One line on what each destination is for (hover hint).
const _navHints = {
  'Dashboard': 'Overview of URI and what needs you',
  'Conversation': 'Talk with URI',
  'Tasks': 'Decisions waiting for you and work in progress',
  'Documents': 'Start a letter, sheet, document or research',
  'Office': 'Open a workbook, document or presentation from your folders',
  'Assist': 'Let URI help in the apps you allow',
  'Scheduler': 'Reminders and scheduled jobs',
  'Connections': 'Accounts and tools URI can use',
  'Settings': 'Brain, permissions, companion and preferences',
  'Companion': 'Float URI on your desktop. Click it for Chat; double-click to come back here.',
};

/// The housing and associations surround the shell's actual Companion.
class FrostDashboard extends StatelessWidget {
  const FrostDashboard({
    super.key,
    required this.orbRect,
    required this.details,
  });
  final Rect orbRect;
  final Widget details;
  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final app = AppStateScope.of(context);
    final c = UriColors.of(context);
    void focus(WorkspaceFocus target) => services.presentation.setMode(
      UiPresentationMode.workspace,
      focus: target,
    );
    // On the integrated worker the classic account screens would run on the
    // working system's local placeholder client and show made-up results, so
    // the destination says plainly that accounts are not managed here yet.
    final connectionsUnavailable =
        services.oi != null && services.appDataIsMock;
    void connections() => Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => connectionsUnavailable
            ? _ConnectionsUnavailable(
                openSettings: () => focus(WorkspaceFocus.settings),
                openClassic: WorkingSystemShellSwitch.maybeOf(context)
                    ?.openClassic,
              )
            : const ConnectionsProvidersScreen(),
      ),
    );
    // The integrated worker's open approval or confirmation waits for the
    // user too (the Workspace counts it the same way).
    final oi = services.oi;
    final needs =
        pendingDecisionCount(app, services.work) +
        (oi?.pendingApproval != null ? 1 : 0) +
        (oi?.pendingConfirmation != null ? 1 : 0);
    final signal = services.companion.signal;
    final cards = <(String, String, VoidCallback)>[
      (
        'Memory',
        'Context with a source.',
        () => focus(WorkspaceFocus.intelligence),
      ),
      (
        'Tasks',
        app.isLoadingTasks
            ? 'Loading task status…'
            : app.tasksError != null
            ? 'Task status unavailable'
            : needs == 0
            ? 'No pending decisions reported'
            : needs == 1
            ? '1 pending decision'
            : '$needs pending decisions',
        () => focus(WorkspaceFocus.tasks),
      ),
      (
        'Brain & models',
        services.oi != null
            ? 'Integrated worker · view health'
            : app.activeBrain?.displayName ?? 'No Brain selected',
        () => focus(WorkspaceFocus.settings),
      ),
      (
        'Connections',
        connectionsUnavailable
            ? 'Not managed here yet'
            : 'Your tools, in view.',
        connections,
      ),
      (
        'Permissions',
        'Scope stays explicit',
        () => focus(WorkspaceFocus.settings),
      ),
      (
        'Operational state',
        services.readiness.isSimulated
            ? 'Simulated readiness'
            : 'View reported readiness',
        () => _showDetails(context),
      ),
    ];
    return LayoutBuilder(
      builder: (context, box) {
        final textScale = MediaQuery.textScalerOf(context).scale(14) / 14;
        final wide = OrbDock.dashboardWide(box.biggest, textScale);
        final medium = OrbDock.dashboardMedium(box.biggest, textScale);
        final rail = OrbDock.dashboardRail(box.biggest, textScale);
        final width = box.maxWidth - rail;
        Widget card(int i) => Material(
          color: c.surface,
          shape: RoundedRectangleBorder(
            side: BorderSide(color: c.border),
            borderRadius: BorderRadius.circular(3),
          ),
          child: InkWell(
            onTap: cards[i].$3,
            child: Padding(
              // Medium windows place the cards beside the companion: one
              // line of detail keeps them inside their fixed height.
              padding: medium
                  ? const EdgeInsets.symmetric(horizontal: 14, vertical: 8)
                  : const EdgeInsets.all(14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Row(
                    children: [
                      Text(
                        '0${i + 1}',
                        style: TextStyle(fontSize: 12, color: c.accent),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(
                          cards[i].$1,
                          style: TextStyle(fontSize: 14, color: c.ink),
                        ),
                      ),
                      const Icon(Icons.north_east, size: 14),
                    ],
                  ),
                  SizedBox(height: medium ? 6 : 10),
                  Text(
                    cards[i].$2,
                    maxLines: medium ? 1 : 2,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: 14,
                      height: 1.2,
                      color: c.inkSoft,
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
        final nav = <(String, IconData, VoidCallback)>[
          ('Dashboard', Icons.dashboard_outlined, () {}),
          (
            'Conversation',
            Icons.chat_bubble_outline,
            () => focus(WorkspaceFocus.conversation),
          ),
          ('Tasks', Icons.check, () => focus(WorkspaceFocus.tasks)),
          (
            'Documents',
            Icons.description_outlined,
            () => focus(WorkspaceFocus.documents),
          ),
          // URI Office (integration live run i1, finding INT-L1): the V2 landing lists Office like the Workspace rail.
          (
            'Office',
            Icons.table_chart_outlined,
            () => focus(WorkspaceFocus.office),
          ),
          (
            'Assist',
            Icons.center_focus_weak,
            () => services.presentation.setMode(UiPresentationMode.assist),
          ),
          (
            'Scheduler',
            Icons.schedule,
            () {
              final client = SchedulerClient.fromEnvironment();
              Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => client == null
                      ? Scaffold(
                          appBar: AppBar(title: const Text('Scheduler')),
                          body: const Center(
                            child: Text(
                              'Scheduler unavailable: no isolated service configured.',
                            ),
                          ),
                        )
                      : SchedulerView(client: client),
                ),
              );
            },
          ),
          ('Connections', Icons.cable, connections),
          (
            'Settings',
            Icons.settings_outlined,
            () => focus(WorkspaceFocus.settings),
          ),
          (
            'Companion',
            Icons.blur_circular,
            () => services.presentation.setMode(UiPresentationMode.companion),
          ),
        ];
        Widget navigation() => ListView(
          padding: const EdgeInsets.fromLTRB(16, 32, 16, 20),
          children: [
            const Padding(
              padding: EdgeInsets.all(14),
              child: Text(
                'WORKSPACE',
                style: TextStyle(fontSize: 11, letterSpacing: 1.2),
              ),
            ),
            for (final item in nav)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Tooltip(
                  // First-time help where the choice is made.
                  message: _navHints[item.$1] ?? item.$1,
                  waitDuration: const Duration(milliseconds: 600),
                  child: Material(
                    type: MaterialType.transparency,
                    child: ListTile(
                      selected: item.$1 == 'Dashboard',
                      selectedTileColor: c.accentSoft.withValues(alpha: .35),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(4),
                      ),
                      leading: Icon(item.$2, size: 18),
                      title: Text(
                        item.$1,
                        style: const TextStyle(fontSize: 14),
                      ),
                      onTap: item.$3,
                    ),
                  ),
                ),
              ),
          ],
        );
        Widget reviewButton() => OutlinedButton(
          onPressed: () => focus(WorkspaceFocus.tasks),
          child: Text(
            app.isLoadingTasks
                ? 'Checking decisions…'
                : app.tasksError != null
                ? 'Review status unavailable'
                : needs == 0
                ? 'Nothing to review'
                : needs == 1
                ? '1 review needed'
                : '$needs reviews needed',
          ),
        );
        final header = Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: double.infinity,
              child: rail > 0
                  ? Wrap(
                      alignment: WrapAlignment.spaceBetween,
                      spacing: 16,
                      runSpacing: 8,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        const Text(
                          'Personal workspace / Dashboard',
                          style: TextStyle(fontSize: 12),
                        ),
                        reviewButton(),
                      ],
                    )
                  : Row(
                      children: [
                        Builder(
                          builder: (context) => IconButton(
                            tooltip: 'Navigation',
                            icon: const Icon(Icons.menu),
                            onPressed: () => Scaffold.of(context).openDrawer(),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Align(
                            alignment: Alignment.centerRight,
                            child: reviewButton(),
                          ),
                        ),
                      ],
                    ),
            ),
            if (wide) ...[
              const SizedBox(height: 16),
              Divider(color: c.border.withValues(alpha: .5)),
            ],
            SizedBox(height: wide ? 16 : 8),
            Text(
              'URI / COMMAND CHAMBER',
              style: TextStyle(
                fontSize: 12,
                letterSpacing: 1.6,
                color: c.accent,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Your work, connected.',
              style: TextStyle(
                fontFamily: 'Georgia',
                fontSize: wide
                    ? 38
                    : medium
                    ? 30
                    : 24,
                color: c.ink,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'A clear view of your intelligence, your context, and what needs you.',
              style: TextStyle(fontSize: 14, color: c.inkSoft),
            ),
            if (services.appDataIsMock && services.oi == null)
              Text(
                'SIMULATED PREVIEW · no backend connected',
                style: TextStyle(fontSize: 12, color: c.accent),
              ),
          ],
        );
        final footer = Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '◇   Static conduits show association. They do not signal execution.',
              style: TextStyle(fontSize: 12, color: c.inkSoft),
            ),
            const SizedBox(height: 14),
            Divider(color: c.border.withValues(alpha: .5)),
            const SizedBox(height: 16),
            const Text(
              'CONTINUE YOUR WORK',
              style: TextStyle(fontSize: 11, letterSpacing: 1),
            ),
            const SizedBox(height: 14),
            const LivingComposer(hint: 'What would you like to work on?'),
            const SizedBox(height: 12),
            Text(
              'Shared context and pending decisions stay with you.',
              style: TextStyle(fontSize: 12, color: c.inkSoft),
            ),
          ],
        );
        final body = wide
            ? Stack(
                children: [
                  Positioned(left: 36, right: 36, top: 24, child: header),
                  Positioned.fill(
                    child: IgnorePointer(
                      child: CustomPaint(
                        painter: _Conduits(
                          orbRect.shift(Offset(-rail, 0)),
                          c.accent,
                          width,
                        ),
                      ),
                    ),
                  ),
                  for (var i = 0; i < 6; i++)
                    Positioned(
                      left: i < 3 ? 36 : width - 36 - (width - 584) / 2,
                      top: orbRect.center.dy - 114 + (i % 3) * 130,
                      width: (width - 584) / 2,
                      height: 100,
                      child: card(i),
                    ),
                  Positioned(
                    top: orbRect.bottom + 12,
                    left: width / 2 - 200,
                    width: 400,
                    child: Column(
                      children: [
                        Text(
                          signal.state == CompanionState.success
                              ? 'Reply received'
                              : signal.title,
                          key: const ValueKey('dashboard-state-line'),
                          style: const TextStyle(fontSize: 18),
                        ),
                        const SizedBox(height: 12),
                        Text(
                          '${CompanionDesign.active(services.companionPrefs).displayName}${signal.simulated ? ' · simulated' : ''}',
                          style: TextStyle(fontSize: 14, color: c.accent),
                        ),
                        const SizedBox(height: 12),
                        OutlinedButton(
                          onPressed: () => _showDetails(context),
                          child: const Text('Show region details ↓'),
                        ),
                      ],
                    ),
                  ),
                  Positioned(left: 36, right: 232, bottom: 32, child: footer),
                  const Positioned(
                    right: 36,
                    bottom: 32,
                    width: 164,
                    child: UriArtwork(),
                  ),
                ],
              )
            : medium
            ? _mediumBody(
                orb: orbRect.shift(Offset(-rail, 0)),
                width: width,
                header: header,
                card: card,
                stateLine:
                    '${signal.state == CompanionState.success ? 'Reply received' : signal.title} · ${CompanionDesign.active(services.companionPrefs).displayName}${signal.simulated ? ' · simulated' : ''}',
                inkSoft: c.inkSoft,
              )
            : Column(
                children: [
                  SizedBox(
                    height: math.max(0, orbRect.top - 20),
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.all(20),
                      child: header,
                    ),
                  ),
                  SizedBox(height: (box.maxHeight * .35).clamp(0, 220)),
                  Expanded(
                    child: ListView(
                      padding: const EdgeInsets.all(20),
                      children: [
                        Text(
                          '${signal.state == CompanionState.success ? 'Reply received' : signal.title}${signal.simulated ? ' · simulated preview' : ''}',
                          textAlign: TextAlign.center,
                        ),
                        const SizedBox(height: 24),
                        for (var i = 0; i < 6; i++)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 12),
                            child: card(i),
                          ),
                        const Align(
                          alignment: Alignment.centerRight,
                          child: SizedBox(width: 120, child: UriArtwork()),
                        ),
                        const SizedBox(height: 24),
                        footer,
                      ],
                    ),
                  ),
                ],
              );
        return Scaffold(
          backgroundColor: Colors.transparent,
          drawer: rail > 0 ? null : Drawer(child: navigation()),
          body: Row(
            children: [
              if (rail > 0)
                Container(
                  width: rail,
                  decoration: BoxDecoration(
                    color: c.surfaceSunken.withValues(alpha: .55),
                    border: Border(
                      right: BorderSide(color: c.border.withValues(alpha: .5)),
                    ),
                  ),
                  child: navigation(),
                ),
              Expanded(child: body),
            ],
          ),
        );
      },
    );
  }

  /// Medium windows: header on top, three destinations on each side of the
  /// companion, and the composer kept in view at the bottom. Same cards,
  /// header, composer and artwork as the other layouts.
  Widget _mediumBody({
    required Rect orb,
    required double width,
    required Widget header,
    required Widget Function(int) card,
    required String stateLine,
    required Color inkSoft,
  }) {
    const cardHeight = 84.0, gap = 10.0;
    final column = ((width - 72 - orb.width - 112) / 2).clamp(200.0, 380.0);
    final top = orb.center.dy - (3 * cardHeight + 2 * gap) / 2;
    return Stack(
      children: [
        Positioned(
          left: 36,
          right: 36,
          top: 0,
          height: OrbDock.dashboardHeader,
          child: SingleChildScrollView(
            padding: const EdgeInsets.only(top: 20),
            child: header,
          ),
        ),
        for (var i = 0; i < 6; i++)
          Positioned(
            left: i < 3 ? 36 : width - 36 - column,
            top: top + (i % 3) * (cardHeight + gap),
            width: column,
            height: cardHeight,
            child: card(i),
          ),
        Positioned(
          top: orb.bottom + 6,
          left: orb.center.dx - 180,
          width: 360,
          child: Text(
            stateLine,
            key: const ValueKey('dashboard-state-line'),
            textAlign: TextAlign.center,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 14, color: inkSoft),
          ),
        ),
        Positioned(
          left: 36,
          right: 36 + 92 + 20,
          bottom: 20,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'CONTINUE YOUR WORK',
                style: TextStyle(fontSize: 11, letterSpacing: 1),
              ),
              const SizedBox(height: 10),
              const LivingComposer(hint: 'What would you like to work on?'),
              const SizedBox(height: 8),
              Text(
                'Shared context and pending decisions stay with you.',
                style: TextStyle(fontSize: 12, color: inkSoft),
              ),
            ],
          ),
        ),
        const Positioned(right: 36, bottom: 16, width: 92, child: UriArtwork()),
      ],
    );
  }

  void _showDetails(BuildContext context) => Navigator.of(context).push(
    MaterialPageRoute<void>(
      builder: (_) => Scaffold(
        appBar: AppBar(title: const Text('Dashboard details')),
        body: details,
      ),
    ),
  );
}

/// Honest Connections page for the integrated worker (UI V2 completion R1-01).
class _ConnectionsUnavailable extends StatelessWidget {
  const _ConnectionsUnavailable({required this.openSettings, this.openClassic});
  final VoidCallback openSettings;
  final VoidCallback? openClassic;
  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Connections')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          key: const ValueKey('connections-unavailable'),
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Accounts such as Gmail and Google Drive are not connected or managed in this working system yet. Nothing on this screen is connected for URI.',
              style: TextStyle(fontSize: 15, color: c.ink),
            ),
            const SizedBox(height: 8),
            Text(
              'The Brain, cloud providers and what URI remembers are in Settings.',
              style: TextStyle(fontSize: 13, color: c.inkSoft),
            ),
            const SizedBox(height: 20),
            Wrap(
              spacing: 12,
              runSpacing: 8,
              children: [
                FilledButton(
                  onPressed: () {
                    Navigator.of(context).pop();
                    openSettings();
                  },
                  child: const Text('Open Settings'),
                ),
                if (openClassic != null)
                  OutlinedButton(
                    onPressed: () {
                      Navigator.of(context).pop();
                      openClassic!();
                    },
                    child: const Text('Open the classic interface'),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// The owner's supplied artwork; the source asset stays unchanged.
/// Theme-derived etched tones blend directly into the matte canvas, with no
/// visible plate border. This static artwork is not a Companion or an action.
class UriArtwork extends StatelessWidget {
  const UriArtwork({super.key});
  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final steel = Color.lerp(c.canvas, const Color(0xFFAEB0AD), .35)!;
    final engraving = Color.lerp(steel, c.ink, .75)!;
    List<double> row(double ink, double paper) => [
      (paper - ink) * .2126,
      (paper - ink) * .7152,
      (paper - ink) * .0722,
      0,
      ink * 255,
    ];
    return Semantics(
      label:
          'URI artwork engraved on steel. The puppy who inspired this project.',
      image: true,
      child: IgnorePointer(
        child: RepaintBoundary(
          child: AspectRatio(
            aspectRatio: 2 / 3,
            child: ShaderMask(
              blendMode: BlendMode.dstIn,
              shaderCallback: (bounds) => const LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Colors.transparent,
                  Colors.black,
                  Colors.black,
                  Colors.transparent,
                ],
                stops: [0, .08, .88, 1],
              ).createShader(bounds),
              child: Opacity(
                opacity: .46,
                child: ColorFiltered(
                  colorFilter: ColorFilter.matrix([
                    ...row(engraving.r, c.canvas.r),
                    ...row(engraving.g, c.canvas.g),
                    ...row(engraving.b, c.canvas.b),
                    0,
                    0,
                    0,
                    1,
                    0,
                  ]),
                  child: Image.asset(
                    'assets/uri_engraving_cutout_v2.png',
                    fit: BoxFit.contain,
                    excludeFromSemantics: true,
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _Conduits extends CustomPainter {
  _Conduits(this.orb, this.color, this.width);
  final Rect orb;
  final Color color;
  final double width;
  @override
  void paint(Canvas canvas, Size size) {
    final p = Paint()
      ..color = color.withValues(alpha: .6)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    final center = orb.center;
    final radius = orb.width / 2 + 6;
    for (var i = 0; i < 72; i++) {
      final a = i * math.pi / 36;
      final u = Offset(math.cos(a), math.sin(a));
      canvas.drawLine(
        center + u * radius,
        center + u * (radius + (i % 6 == 0 ? 8 : 2)),
        p,
      );
    }
    canvas.drawCircle(
      center,
      radius - 4,
      p..color = color.withValues(alpha: .25),
    );
    p.color = color.withValues(alpha: .65);
    for (var i = 0; i < 3; i++) {
      for (final side in [-1.0, 1.0]) {
        final dy = (i - 1) * 48.0;
        final port =
            center + Offset(side * math.sqrt(radius * radius - dy * dy), dy);
        final end = Offset(
          side < 0 ? 36 + (width - 584) / 2 : width - 36 - (width - 584) / 2,
          center.dy - 64 + i * 130,
        );
        final elbow = (port.dx + end.dx) / 2;
        canvas.drawPath(
          Path()
            ..moveTo(port.dx, port.dy)
            ..lineTo(elbow, port.dy)
            ..lineTo(elbow, end.dy)
            ..lineTo(end.dx, end.dy),
          p,
        );
        canvas.drawCircle(port, 3, p);
      }
    }
  }

  @override
  bool shouldRepaint(_Conduits old) =>
      old.orb != orb || old.color != color || old.width != width;
}
