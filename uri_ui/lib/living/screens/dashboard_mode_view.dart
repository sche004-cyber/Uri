import 'package:flutter/material.dart';

import '../../services/app_state_scope.dart';
import '../../theme/uri_theme.dart';
import '../assist/assist_scope_line.dart' show AssistStatusSummary;
import '../companion/companion_state.dart';
import '../contracts/work_items.dart';
import '../integration/oi_health_widgets.dart';
import '../integration/scheduler_client.dart';
import '../living_scope.dart';
import '../presentation/presentation_controller.dart';
import '../widgets/glass_panel.dart';
import '../widgets/status_badge.dart';
import 'scheduler/scheduler_view.dart';
import 'workspace_mode_view.dart'
    show HarnessRow, PermissionRow, pendingDecisionCount;

/// Dashboard: one calm overview of what URI can do, is doing, and is
/// made of. Every tile names its data source; mock-backed tiles carry
/// the Simulated badge. No tile shows a metric with no source.
class DashboardModeView extends StatefulWidget {
  const DashboardModeView({super.key, required this.orbRect});
  final Rect orbRect;

  @override
  State<DashboardModeView> createState() => _DashboardModeViewState();
}

class _DashboardModeViewState extends State<DashboardModeView> {
  final SchedulerClient? _scheduler = SchedulerClient.fromEnvironment();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final s = AppStateScope.of(context);
      s.loadTasks();
      if (!s.hasLoadedCapabilities) s.loadCapabilities();
      if (s.activeBrain == null) s.loadActiveBrain();
      if (!s.hasLoadedDevices) s.loadDevices();
      // Status only: no adapter is called and nothing is observed.
      final assist = LivingScope.of(context).assist;
      if (assist != null && !assist.loaded) assist.refresh();
    });
  }

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final appState = AppStateScope.of(context);
    final c = UriColors.of(context);
    return ListenableBuilder(
      listenable: Listenable.merge([
        services.companion,
        services.work,
        services.readiness,
        services.selectedHarness,
        appState,
      ]),
      builder: (context, _) {
        final signal = services.companion.signal;
        final needsYou = pendingDecisionCount(appState, services.work);
        final running = services.work.items
            .where(
              (i) =>
                  i.state == WorkItemState.working ||
                  i.state == WorkItemState.queued,
            )
            .toList();
        final usable = services.readiness.harnesses
            .where((h) => h.usable)
            .length;
        final mock = services.appDataIsMock;
        return LayoutBuilder(
          builder: (context, constraints) {
            final cols = constraints.maxWidth >= 1200
                ? 3
                : constraints.maxWidth >= 760
                ? 2
                : 1;
            return CustomScrollView(
              slivers: [
                SliverToBoxAdapter(
                  child: Column(
                    children: [
                      SizedBox(height: widget.orbRect.bottom + 6),
                      Text(
                        'URI overview',
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.w700,
                          color: c.ink,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        '${signal.state.label}${signal.detail != null ? ' · ${signal.detail}' : ''}',
                        key: const ValueKey('dashboard-state-line'),
                        style: TextStyle(fontSize: 13, color: c.inkSoft),
                      ),
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        children: [
                          OutlinedButton.icon(
                            onPressed: () => services.presentation.setMode(
                              UiPresentationMode.workspace,
                            ),
                            icon: const Icon(
                              Icons.view_sidebar_outlined,
                              size: 16,
                            ),
                            label: const Text('Open workspace'),
                          ),
                          OutlinedButton.icon(
                            onPressed: () => services.presentation.setMode(
                              UiPresentationMode.companion,
                            ),
                            icon: const Icon(
                              Icons.blur_circular_rounded,
                              size: 16,
                            ),
                            label: const Text('Companion'),
                          ),
                        ],
                      ),
                      const SizedBox(height: UriSpace.lg),
                    ],
                  ),
                ),
                SliverPadding(
                  padding: const EdgeInsets.fromLTRB(
                    UriSpace.lg,
                    0,
                    UriSpace.lg,
                    UriSpace.xl,
                  ),
                  sliver: SliverGrid(
                    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: cols,
                      mainAxisSpacing: 14,
                      crossAxisSpacing: 14,
                      mainAxisExtent: 250,
                    ),
                    delegate: SliverChildListDelegate([
                      _Tile(
                        title: 'Readiness',
                        source: 'ReadinessSource.checks',
                        simulated: services.readiness.isSimulated,
                        trailing: IconButton(
                          tooltip: 'Re-check',
                          icon: const Icon(Icons.refresh_rounded, size: 16),
                          color: c.inkSoft,
                          onPressed: services.readiness.refresh,
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            for (final ch in services.readiness.checks)
                              Padding(
                                padding: const EdgeInsets.symmetric(
                                  vertical: 3,
                                ),
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        ch.label,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: TextStyle(
                                          fontSize: 12.5,
                                          color: c.ink,
                                        ),
                                      ),
                                    ),
                                    StatusBadge(ch.status, compact: true),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                      _Tile(
                        title: 'Scheduled tasks',
                        source: 'uri_scheduler GET /overview',
                        simulated: false,
                        child: _SchedulerTileBody(client: _scheduler),
                      ),
                      _Tile(
                        title: 'Current tasks',
                        source: 'GET /tasks + WorkItemSource',
                        simulated: mock || services.work.isSimulated,
                        trailing: TextButton(
                          onPressed: () => services.presentation.setMode(
                            UiPresentationMode.workspace,
                            focus: WorkspaceFocus.tasks,
                          ),
                          child: const Text('Open'),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _BigNumber(
                              value: '$needsYou',
                              label: 'need your decision',
                              color: needsYou > 0 ? c.warning : c.ink,
                            ),
                            const SizedBox(height: 8),
                            _BigNumber(
                              value: '${running.length}',
                              label: 'in progress',
                              color: c.ink,
                            ),
                            const SizedBox(height: 8),
                            for (final r in running.take(2))
                              Text(
                                r.title,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: 12,
                                  color: c.inkSoft,
                                ),
                              ),
                          ],
                        ),
                      ),
                      if (services.oi != null)
                        // Working system: the real worker report (WS hardening, L-DASH).
                        ListenableBuilder(
                          listenable: services.oi!,
                          builder: (context, _) => _Tile(
                            title: 'Brain & models',
                            source: 'integrated worker · brain_health',
                            simulated: false,
                            child: OiBrainCard(conversation: services.oi!),
                          ),
                        )
                      else
                      _Tile(
                        title: 'Brain & models',
                        source: 'GET /providers/active-brain',
                        simulated: mock,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              appState.activeBrain?.displayName ??
                                  appState.activeBrain?.providerId ??
                                  'No Brain selected',
                              style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                                color: c.ink,
                              ),
                            ),
                            Text(
                              appState.activeBrain?.model ?? '—',
                              style: TextStyle(
                                fontSize: 12.5,
                                color: c.inkSoft,
                              ),
                            ),
                            const SizedBox(height: 10),
                            Text(
                              appState.activeBrain == null
                                  ? 'Choose a provider in Settings.'
                                  : (appState.activeBrain!.isConfigured
                                        ? 'Configured'
                                        : 'Not configured'),
                              style: TextStyle(fontSize: 12, color: c.inkFaint),
                            ),
                          ],
                        ),
                      ),
                      _Tile(
                        title: 'Harnesses',
                        source: 'harness_discover (mock)',
                        simulated: services.readiness.isSimulated,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _BigNumber(
                              value:
                                  '$usable / ${services.readiness.harnesses.length}',
                              label: 'usable',
                              color: c.ink,
                            ),
                            const SizedBox(height: 6),
                            for (final h in services.readiness.harnesses.take(
                              3,
                            ))
                              Padding(
                                padding: const EdgeInsets.symmetric(
                                  vertical: 2,
                                ),
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: Text(
                                        h.displayName,
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: TextStyle(
                                          fontSize: 12.5,
                                          color: c.ink,
                                        ),
                                      ),
                                    ),
                                    StatusBadge(
                                      h.truth == TruthStatus.simulated
                                          ? _truthIgnoringSim(h)
                                          : h.truth,
                                      compact: true,
                                    ),
                                  ],
                                ),
                              ),
                          ],
                        ),
                      ),
                      _Tile(
                        title: 'Connected clients',
                        source: 'GET /devices + ClientFact',
                        simulated: true,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            for (final cl in services.readiness.clients)
                              Padding(
                                padding: const EdgeInsets.symmetric(
                                  vertical: 3,
                                ),
                                child: Row(
                                  children: [
                                    Icon(
                                      cl.platform == 'Android'
                                          ? Icons.smartphone_rounded
                                          : Icons.computer_rounded,
                                      size: 16,
                                      color: c.accentInk,
                                    ),
                                    const SizedBox(width: 8),
                                    Expanded(
                                      child: Text(
                                        '${cl.label}${cl.isThisDevice ? ' (this device)' : ''}',
                                        style: TextStyle(
                                          fontSize: 12.5,
                                          color: c.ink,
                                        ),
                                      ),
                                    ),
                                  ],
                                ),
                              ),
                            const SizedBox(height: 6),
                            Text(
                              '${appState.devices.length} device session(s) reported by the client',
                              style: TextStyle(
                                fontSize: 11.5,
                                color: c.inkFaint,
                              ),
                            ),
                          ],
                        ),
                      ),
                      _Tile(
                        title: 'Permissions',
                        source: 'client grants (mock)',
                        simulated: services.readiness.isSimulated,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            for (final p in services.readiness.permissions.take(
                              4,
                            ))
                              PermissionRow(fact: p),
                          ],
                        ),
                      ),
                      _Tile(
                        title: 'Capabilities',
                        source: 'GET /capabilities',
                        simulated: mock,
                        child: appState.capabilities.isEmpty
                            ? Text(
                                'No capabilities reported.',
                                style: TextStyle(
                                  fontSize: 12.5,
                                  color: c.inkFaint,
                                ),
                              )
                            : Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  for (final cap in appState.capabilities.take(
                                    5,
                                  ))
                                    Padding(
                                      padding: const EdgeInsets.symmetric(
                                        vertical: 2,
                                      ),
                                      child: Row(
                                        children: [
                                          Icon(
                                            cap.isUsable
                                                ? Icons.check_rounded
                                                : Icons.remove_rounded,
                                            size: 14,
                                            color: cap.isUsable
                                                ? c.success
                                                : c.inkFaint,
                                          ),
                                          const SizedBox(width: 6),
                                          Expanded(
                                            child: Text(
                                              cap.id,
                                              maxLines: 1,
                                              overflow: TextOverflow.ellipsis,
                                              style: TextStyle(
                                                fontSize: 12.5,
                                                color: c.ink,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                ],
                              ),
                      ),
                      if (services.assist != null)
                        _Tile(
                          title: 'Assist',
                          source: 'worker assist_status (read-only)',
                          simulated: false,
                          child: AssistStatusSummary(assist: services.assist!),
                        ),
                      _Tile(
                        title: 'Selected harness',
                        source: 'UI selection',
                        simulated: services.readiness.isSimulated,
                        child: Builder(
                          builder: (context) {
                            final id = services.selectedHarness.value;
                            final h = services.readiness.harnesses
                                .where((x) => x.id == id)
                                .toList();
                            if (h.isEmpty) {
                              return Text(
                                'None selected. Pick one in Workspace › Settings.',
                                style: TextStyle(
                                  fontSize: 12.5,
                                  color: c.inkFaint,
                                ),
                              );
                            }
                            return HarnessRow(fact: h.first, selectable: false);
                          },
                        ),
                      ),
                    ]),
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  static TruthStatus _truthIgnoringSim(dynamic h) {
    if (!h.installed) return TruthStatus.unavailable;
    if (h.usable) return TruthStatus.qualified;
    return TruthStatus.configured;
  }
}

class _Tile extends StatelessWidget {
  const _Tile({
    required this.title,
    required this.source,
    required this.simulated,
    required this.child,
    this.trailing,
  });
  final String title;
  final String source;
  final bool simulated;
  final Widget child;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return GlassPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: TextStyle(
                    fontSize: 13.5,
                    fontWeight: FontWeight.w600,
                    color: c.ink,
                  ),
                ),
              ),
              if (simulated) const StatusBadge.simulated(compact: true),
              ?trailing,
            ],
          ),
          Text(source, style: TextStyle(fontSize: 10.5, color: c.inkFaint)),
          const SizedBox(height: 10),
          Expanded(child: SingleChildScrollView(child: child)),
        ],
      ),
    );
  }
}

class _BigNumber extends StatelessWidget {
  const _BigNumber({
    required this.value,
    required this.label,
    required this.color,
  });
  final String value;
  final String label;
  final Color color;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Row(
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: [
        Text(
          value,
          style: TextStyle(
            fontSize: 26,
            fontWeight: FontWeight.w700,
            color: color,
            height: 1,
          ),
        ),
        const SizedBox(width: 8),
        Text(label, style: TextStyle(fontSize: 12.5, color: c.inkSoft)),
      ],
    );
  }
}


/// Scheduled-tasks tile: counts from the scheduler service and the way in.
/// Without a configured service it says so instead of showing numbers.
class _SchedulerTileBody extends StatelessWidget {
  const _SchedulerTileBody({required this.client});
  final SchedulerClient? client;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final cl = client;
    if (cl == null) {
      return Text(
        'Scheduler service not configured (URI_SCHEDULER_STATE).',
        style: TextStyle(fontSize: 12.5, color: c.inkSoft),
      );
    }
    return FutureBuilder<Map<String, dynamic>>(
      future: cl.overview(),
      builder: (context, s) {
        final ov = s.data;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (ov != null) ...[
              _BigNumber(
                value: '${(ov['pending_approvals'] as List).length}',
                label: 'waiting for approval',
                color: c.ink,
              ),
              const SizedBox(height: 6),
              Text(
                '${(ov['upcoming'] as List).length} upcoming · '
                '${(ov['errors'] as List).length} need attention · '
                '${(ov['paused_jobs'] as List).length} paused',
                style: TextStyle(fontSize: 12.5, color: c.inkSoft),
              ),
            ] else
              Text(
                s.hasError ? 'Not reachable: ${s.error}' : 'Loading…',
                style: TextStyle(fontSize: 12.5, color: c.inkSoft),
              ),
            const SizedBox(height: 10),
            OutlinedButton.icon(
              key: const Key('dashboard.openScheduler'),
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => SchedulerView(
                    client: cl,
                    poll: const Duration(seconds: 5),
                  ),
                ),
              ),
              icon: const Icon(Icons.schedule, size: 16),
              label: const Text('Open scheduler'),
            ),
          ],
        );
      },
    );
  }
}
