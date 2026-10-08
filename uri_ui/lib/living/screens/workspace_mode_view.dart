import 'package:flutter/material.dart';

import '../../models/task_item.dart';
import '../../models/user_preferences.dart';
import '../../screens/ask/ask_uri_screen.dart' show UriConversationPane;
import '../../services/app_state.dart';
import '../../services/app_state_scope.dart';
import '../../services/attachment_opener_service.dart';
import '../../services/file_picker_service.dart';
import '../../services/uri_client.dart';
import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../companion/companion_state.dart';
import '../companion/energy_orb.dart'
    show OrbPalette, OrbPaletteData, OrbVariant, OrbVariantLabel;
import '../contracts/readiness_report.dart';
import '../contracts/work_items.dart';
import '../integration/oi_widgets.dart';
import '../integration/ws_settings.dart';
import '../living_app.dart';
import '../living_scope.dart';
import '../presentation/presentation_controller.dart';
import '../widgets/glass_panel.dart';
import '../widgets/living_composer.dart';
import '../widgets/status_badge.dart';
import 'intelligence/intelligence_overview_view.dart';

/// Workspace: rail (the orb docks at its top) | focus region | context
/// panel. Progressive disclosure: the context panel is open only on
/// wide windows or when asked for; the focus region shows one thing.
class WorkspaceModeView extends StatefulWidget {
  const WorkspaceModeView({super.key, this.filePicker, this.attachmentOpener});

  final FilePickerFn? filePicker;
  final AttachmentOpenerFn? attachmentOpener;

  @override
  State<WorkspaceModeView> createState() => _WorkspaceModeViewState();
}

class _WorkspaceModeViewState extends State<WorkspaceModeView> {
  bool? _contextOverride;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      final s = AppStateScope.of(context);
      s.loadTasks();
      if (s.activeBrain == null) s.loadActiveBrain();
      if (!s.hasLoadedCapabilities) s.loadCapabilities();
    });
  }

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    return ListenableBuilder(
      listenable: services.presentation,
      builder: (context, _) {
        final focus = services.presentation.focus;
        return LayoutBuilder(
          builder: (context, constraints) {
            final w = constraints.maxWidth;
            final railExpanded = w >= 1100;
            final contextDefault = w >= 1180;
            final showContext = _contextOverride ?? contextDefault;
            return Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _Rail(expanded: railExpanded, focus: focus),
                Expanded(
                  child: Column(
                    children: [
                      _FocusHeader(
                        focus: focus,
                        contextOpen: showContext,
                        onToggleContext: () =>
                            setState(() => _contextOverride = !showContext),
                      ),
                      Expanded(
                        child: AnimatedSwitcher(
                          duration: UriMotion.fast,
                          child: KeyedSubtree(
                            key: ValueKey(focus),
                            child: switch (focus) {
                              WorkspaceFocus.conversation =>
                                _ConversationRegion(
                                  filePicker: widget.filePicker,
                                  attachmentOpener: widget.attachmentOpener,
                                ),
                              WorkspaceFocus.tasks => const TasksRegion(),
                              WorkspaceFocus.documents =>
                                const DocumentsRegion(),
                              WorkspaceFocus.intelligence =>
                                const IntelligenceOverviewView(),
                              WorkspaceFocus.settings =>
                                const WorkspaceSettingsRegion(),
                            },
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
                if (showContext) const _ContextPanel(),
              ],
            );
          },
        );
      },
    );
  }
}

// ---------------------------------------------------------------------------
// Rail
// ---------------------------------------------------------------------------

class _Rail extends StatelessWidget {
  const _Rail({required this.expanded, required this.focus});
  final bool expanded;
  final WorkspaceFocus focus;

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    final width = expanded ? 200.0 : 88.0;
    const items = [
      (
        WorkspaceFocus.conversation,
        Icons.chat_bubble_outline_rounded,
        'Conversation',
      ),
      (WorkspaceFocus.tasks, Icons.check_circle_outline_rounded, 'Tasks'),
      (WorkspaceFocus.documents, Icons.description_outlined, 'Documents'),
      (WorkspaceFocus.intelligence, Icons.hub_outlined, 'Intelligence'),
      (WorkspaceFocus.settings, Icons.tune_rounded, 'Settings'),
    ];
    return AnimatedContainer(
      duration: UriMotion.mode,
      width: width,
      decoration: BoxDecoration(
        border: Border(right: BorderSide(color: glass.border)),
        color: glass.fill,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Orb dock (the shell draws the orb here).
          const SizedBox(height: 92),
          ListenableBuilder(
            listenable: services.companion,
            builder: (context, _) {
              final s = services.companion.signal;
              return Padding(
                padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                child: Text(
                  s.state.label,
                  key: const ValueKey('rail-state-label'),
                  textAlign: expanded ? TextAlign.left : TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w600,
                    color: s.state.needsUser ? c.warning : c.inkSoft,
                  ),
                ),
              );
            },
          ),
          Divider(height: 1, color: glass.border),
          const SizedBox(height: 8),
          for (final (f, icon, label) in items)
            _RailItem(
              icon: icon,
              label: label,
              expanded: expanded,
              selected: focus == f,
              onTap: () => services.presentation.setFocus(f),
            ),
          const Spacer(),
          Divider(height: 1, color: glass.border),
          _RailItem(
            icon: Icons.grid_view_rounded,
            label: 'Dashboard',
            expanded: expanded,
            selected: false,
            onTap: () =>
                services.presentation.setMode(UiPresentationMode.dashboard),
          ),
          _RailItem(
            icon: Icons.blur_circular_rounded,
            label: 'Companion',
            expanded: expanded,
            selected: false,
            onTap: () =>
                services.presentation.setMode(UiPresentationMode.companion),
          ),
          const SizedBox(height: 10),
        ],
      ),
    );
  }
}

class _RailItem extends StatelessWidget {
  const _RailItem({
    required this.icon,
    required this.label,
    required this.expanded,
    required this.selected,
    required this.onTap,
  });
  final IconData icon;
  final String label;
  final bool expanded;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final child = Padding(
      padding: EdgeInsets.symmetric(
        horizontal: expanded ? 14 : 0,
        vertical: 10,
      ),
      child: Row(
        mainAxisAlignment: expanded
            ? MainAxisAlignment.start
            : MainAxisAlignment.center,
        children: [
          Icon(icon, size: 19, color: selected ? c.accent : c.inkSoft),
          if (expanded) ...[
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                label,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                  color: selected ? c.accent : c.ink,
                ),
              ),
            ),
          ],
        ],
      ),
    );
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      child: Material(
        color: selected ? c.accentSoft : Colors.transparent,
        borderRadius: BorderRadius.circular(UriRadius.sm),
        child: InkWell(
          borderRadius: BorderRadius.circular(UriRadius.sm),
          onTap: onTap,
          child: expanded ? child : Tooltip(message: label, child: child),
        ),
      ),
    );
  }
}

class _FocusHeader extends StatelessWidget {
  const _FocusHeader({
    required this.focus,
    required this.contextOpen,
    required this.onToggleContext,
  });
  final WorkspaceFocus focus;
  final bool contextOpen;
  final VoidCallback onToggleContext;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final title = switch (focus) {
      WorkspaceFocus.conversation => 'Conversation',
      WorkspaceFocus.tasks => 'Tasks',
      WorkspaceFocus.documents => 'Documents',
      WorkspaceFocus.intelligence => 'Intelligence',
      WorkspaceFocus.settings => 'Settings',
    };
    return SizedBox(
      height: 48,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: UriSpace.md),
        child: Row(
          children: [
            Text(
              title,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w600,
                color: c.ink,
              ),
            ),
            const Spacer(),
            IconButton(
              tooltip: contextOpen ? 'Hide context' : 'Show context',
              icon: Icon(
                contextOpen
                    ? Icons.view_sidebar_rounded
                    : Icons.view_sidebar_outlined,
                size: 18,
              ),
              color: c.inkSoft,
              onPressed: onToggleContext,
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Conversation
// ---------------------------------------------------------------------------

class _ConversationRegion extends StatelessWidget {
  const _ConversationRegion({this.filePicker, this.attachmentOpener});
  final FilePickerFn? filePicker;
  final AttachmentOpenerFn? attachmentOpener;

  @override
  Widget build(BuildContext context) {
    final oi = LivingScope.of(context).oi;
    return Column(
      children: [
        Expanded(
          child: oi != null
              ? OiConversationPane(conversation: oi)
              : UriConversationPane(
                  attachmentOpener: attachmentOpener,
                  supervisedHandoff: false,
                ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(
            UriSpace.md,
            0,
            UriSpace.md,
            UriSpace.md,
          ),
          child: LivingComposer(filePicker: filePicker, autofocus: true),
        ),
      ],
    );
  }
}

// ---------------------------------------------------------------------------
// Tasks
// ---------------------------------------------------------------------------

class TasksRegion extends StatelessWidget {
  const TasksRegion({super.key});

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final appState = AppStateScope.of(context);
    final c = UriColors.of(context);
    return ListenableBuilder(
      listenable: Listenable.merge([services.work, appState]),
      builder: (context, _) {
        final items = services.work.items;
        final waiting = items
            .where((i) => i.state == WorkItemState.awaitingApproval)
            .toList();
        final running = items
            .where(
              (i) =>
                  i.state == WorkItemState.working ||
                  i.state == WorkItemState.queued,
            )
            .toList();
        final done = items.where((i) => i.state.isTerminal).toList();
        final pending = appState.tasks;
        return ListView(
          padding: const EdgeInsets.fromLTRB(
            UriSpace.md,
            0,
            UriSpace.md,
            UriSpace.lg,
          ),
          children: [
            Eyebrow(
              'Needs your decision',
              trailing: Text(
                '${waiting.length + pending.length}',
                style: TextStyle(fontSize: 11, color: c.inkFaint),
              ),
            ),
            const SizedBox(height: 8),
            if (waiting.isEmpty && pending.isEmpty)
              _EmptyLine('Nothing is waiting for you.'),
            for (final w in waiting) _WorkApprovalCard(item: w),
            for (final t in pending) _PendingTaskCard(task: t),
            const SizedBox(height: UriSpace.lg),
            const Eyebrow('In progress'),
            const SizedBox(height: 8),
            if (running.isEmpty) _EmptyLine('No work is running.'),
            for (final w in running) _WorkProgressCard(item: w),
            const SizedBox(height: UriSpace.lg),
            Eyebrow(
              'History',
              trailing: TextButton(
                onPressed: () =>
                    services.presentation.setFocus(WorkspaceFocus.documents),
                child: const Text('New work'),
              ),
            ),
            const SizedBox(height: 8),
            if (done.isEmpty) _EmptyLine('No finished work yet.'),
            for (final w in done) _WorkHistoryRow(item: w),
          ],
        );
      },
    );
  }
}

class _EmptyLine extends StatelessWidget {
  const _EmptyLine(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 10),
    child: Text(
      text,
      style: TextStyle(fontSize: 13, color: UriColors.of(context).inkFaint),
    ),
  );
}

class _WorkApprovalCard extends StatelessWidget {
  const _WorkApprovalCard({required this.item});
  final WorkItem item;

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final c = UriColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassPanel(
        glowBorder: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.rule_rounded, size: 16, color: c.warning),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    item.title,
                    style: TextStyle(fontWeight: FontWeight.w600, color: c.ink),
                  ),
                ),
                if (item.simulated) const StatusBadge.simulated(compact: true),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              item.approvalSummary ?? 'Approve to continue',
              style: TextStyle(fontSize: 13, color: c.inkSoft),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                FilledButton(
                  key: ValueKey('approve-${item.id}'),
                  onPressed: () => services.work.approve(item.id),
                  child: const Text('Approve'),
                ),
                const SizedBox(width: 8),
                OutlinedButton(
                  key: ValueKey('cancel-${item.id}'),
                  onPressed: () => services.work.cancel(item.id),
                  child: const Text('Cancel'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

/// A real pending approval from `AppState.tasks` (`GET /tasks` shape),
/// decided through the same `approveTask`/`cancelTask` the Hybrid
/// Tasks screen uses.
class _PendingTaskCard extends StatelessWidget {
  const _PendingTaskCard({required this.task});
  final TaskItem task;

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final appState = AppStateScope.of(context);
    final c = UriColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassPanel(
        glowBorder: true,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(Icons.rule_rounded, size: 16, color: c.warning),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    task.description,
                    style: TextStyle(fontWeight: FontWeight.w600, color: c.ink),
                  ),
                ),
                if (services.appDataIsMock)
                  const StatusBadge.simulated(compact: true),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              '${task.capabilityId} · risk ${task.risk}',
              style: TextStyle(fontSize: 12, color: c.inkFaint),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                FilledButton(
                  onPressed: () => appState.approveTask(task.id),
                  child: const Text('Approve'),
                ),
                const SizedBox(width: 8),
                OutlinedButton(
                  onPressed: () => appState.cancelTask(task.id),
                  child: const Text('Cancel'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _WorkProgressCard extends StatelessWidget {
  const _WorkProgressCard({required this.item});
  final WorkItem item;

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final c = UriColors.of(context);
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: GlassPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    item.title,
                    style: TextStyle(fontWeight: FontWeight.w600, color: c.ink),
                  ),
                ),
                Text(
                  item.state.label,
                  style: TextStyle(fontSize: 12, color: c.inkSoft),
                ),
                const SizedBox(width: 8),
                if (item.simulated) const StatusBadge.simulated(compact: true),
                IconButton(
                  tooltip: 'Cancel',
                  icon: const Icon(Icons.close_rounded, size: 16),
                  color: c.inkFaint,
                  onPressed: () => services.work.cancel(item.id),
                ),
              ],
            ),
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(4),
              child: LinearProgressIndicator(
                value: item.progress,
                minHeight: 4,
                backgroundColor: c.surfaceSunken,
                color: c.accent,
              ),
            ),
            if (item.detail != null) ...[
              const SizedBox(height: 6),
              Text(
                item.detail!,
                style: TextStyle(fontSize: 12, color: c.inkFaint),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _WorkHistoryRow extends StatelessWidget {
  const _WorkHistoryRow({required this.item});
  final WorkItem item;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final (IconData icon, Color color) = switch (item.state) {
      WorkItemState.completed => (Icons.check_circle_rounded, c.success),
      WorkItemState.failed => (Icons.error_rounded, c.danger),
      _ => (Icons.remove_circle_outline_rounded, c.inkFaint),
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              item.title,
              style: TextStyle(fontSize: 13, color: c.ink),
            ),
          ),
          if (item.outputName != null)
            Text(
              item.outputName!,
              style: TextStyle(fontSize: 12, color: c.inkFaint),
            ),
          if (item.simulated) ...[
            const SizedBox(width: 8),
            const StatusBadge.simulated(compact: true),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Documents / office workflows
// ---------------------------------------------------------------------------

class DocumentsRegion extends StatelessWidget {
  const DocumentsRegion({super.key});

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final c = UriColors.of(context);
    const templates = [
      (
        WorkItemKind.letter,
        Icons.mail_outline_rounded,
        'Letter',
        'Draft a letter',
      ),
      (
        WorkItemKind.spreadsheet,
        Icons.table_chart_outlined,
        'Spreadsheet',
        'Build a sheet',
      ),
      (
        WorkItemKind.document,
        Icons.article_outlined,
        'Document',
        'Write a document',
      ),
      (
        WorkItemKind.research,
        Icons.travel_explore_rounded,
        'Research',
        'Research a topic',
      ),
    ];
    return ListenableBuilder(
      listenable: services.work,
      builder: (context, _) {
        final docs = services.work.documents;
        return ListView(
          padding: const EdgeInsets.fromLTRB(
            UriSpace.md,
            0,
            UriSpace.md,
            UriSpace.lg,
          ),
          children: [
            Eyebrow(
              'Start new work',
              trailing: services.work.isSimulated
                  ? const StatusBadge.simulated(compact: true)
                  : null,
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final (kind, icon, label, title) in templates)
                  _TemplateTile(
                    icon: icon,
                    label: label,
                    onTap: () {
                      services.work.create(title: title, kind: kind);
                      services.presentation.setFocus(WorkspaceFocus.tasks);
                    },
                  ),
              ],
            ),
            const SizedBox(height: UriSpace.lg),
            const Eyebrow('Recent documents'),
            const SizedBox(height: 8),
            if (docs.isEmpty) _EmptyLine('No documents yet.'),
            for (final d in docs)
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: GlassPanel(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 14,
                    vertical: 10,
                  ),
                  child: Row(
                    children: [
                      Icon(_iconFor(d.kind), size: 18, color: c.accentInk),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          d.name,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 13, color: c.ink),
                        ),
                      ),
                      Text(
                        _relative(d.modifiedAt),
                        style: TextStyle(fontSize: 11.5, color: c.inkFaint),
                      ),
                      if (d.simulated) ...[
                        const SizedBox(width: 8),
                        const StatusBadge.simulated(compact: true),
                      ],
                    ],
                  ),
                ),
              ),
          ],
        );
      },
    );
  }

  static IconData _iconFor(WorkItemKind k) => switch (k) {
    WorkItemKind.letter => Icons.mail_outline_rounded,
    WorkItemKind.spreadsheet => Icons.table_chart_outlined,
    WorkItemKind.document => Icons.article_outlined,
    WorkItemKind.email => Icons.alternate_email_rounded,
    WorkItemKind.research => Icons.travel_explore_rounded,
    WorkItemKind.other => Icons.insert_drive_file_outlined,
  };

  static String _relative(DateTime t) {
    final d = DateTime.now().difference(t);
    if (d.inMinutes < 1) return 'just now';
    if (d.inHours < 1) return '${d.inMinutes} min ago';
    if (d.inDays < 1) return '${d.inHours} h ago';
    return '${d.inDays} d ago';
  }
}

class _TemplateTile extends StatelessWidget {
  const _TemplateTile({
    required this.icon,
    required this.label,
    required this.onTap,
  });
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    return Material(
      color: glass.fill,
      borderRadius: BorderRadius.circular(UriRadius.md),
      child: InkWell(
        key: ValueKey('template-$label'),
        borderRadius: BorderRadius.circular(UriRadius.md),
        onTap: onTap,
        child: Container(
          width: 132,
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(UriRadius.md),
            border: Border.all(color: glass.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(icon, size: 20, color: c.accent),
              const SizedBox(height: 10),
              Text(
                label,
                style: TextStyle(
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                  color: c.ink,
                ),
              ),
              Text('New', style: TextStyle(fontSize: 11, color: c.inkFaint)),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Settings (executor, Brain, reasoning, permissions, appearance)
// ---------------------------------------------------------------------------

class WorkspaceSettingsRegion extends StatefulWidget {
  const WorkspaceSettingsRegion({super.key});

  @override
  State<WorkspaceSettingsRegion> createState() =>
      _WorkspaceSettingsRegionState();
}

class _WorkspaceSettingsRegionState extends State<WorkspaceSettingsRegion> {
  late Future<List<ProviderEntry>> _providers;

  @override
  void initState() {
    super.initState();
    _providers = context
        .getInheritedWidgetOfExactType<AppStateScope>()!
        .notifier!
        .listProviders();
  }

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final appState = AppStateScope.of(context);
    final c = UriColors.of(context);
    final themeCtl = LivingThemeController.maybeOf(context);
    return ListenableBuilder(
      listenable: Listenable.merge([
        services.readiness,
        services.selectedHarness,
        services.reasoningMode,
        services.effects,
        appState,
      ]),
      builder: (context, _) {
        return ListView(
          padding: const EdgeInsets.fromLTRB(
            UriSpace.md,
            0,
            UriSpace.md,
            UriSpace.lg,
          ),
          children: [
            if (services.oi != null) ...[
              WorkingSystemSettingsSection(conversation: services.oi!),
            ],
            Eyebrow(
              'Harness',
              trailing: services.readiness.isSimulated
                  ? const StatusBadge.simulated(compact: true)
                  : null,
            ),
            const SizedBox(height: 8),
            for (final h in services.readiness.harnesses) HarnessRow(fact: h),
            const SizedBox(height: UriSpace.lg),
            Eyebrow(
              'Brain / provider',
              trailing: services.appDataIsMock
                  ? const StatusBadge.simulated(compact: true)
                  : null,
            ),
            const SizedBox(height: 8),
            FutureBuilder<List<ProviderEntry>>(
              future: _providers,
              builder: (context, snap) {
                final providers = snap.data ?? const <ProviderEntry>[];
                if (providers.isEmpty) {
                  return _EmptyLine('No providers reported.');
                }
                return Column(
                  children: [
                    for (final p in providers)
                      _ProviderRow(
                        provider: p,
                        active:
                            appState.activeBrain?.providerId == p.providerId,
                        onSelect: p.configured && p.available
                            ? () => appState.setActiveBrain(p.providerId)
                            : null,
                      ),
                  ],
                );
              },
            ),
            const SizedBox(height: UriSpace.lg),
            const Eyebrow(
              'Reasoning mode',
              trailing: StatusBadge.simulated(compact: true),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              children: [
                for (final m in ReasoningMode.values)
                  ChoiceChip(
                    label: Text(m.label),
                    selected: services.reasoningMode.value == m,
                    onSelected: (_) => services.reasoningMode.value = m,
                  ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              'The mock does not change behaviour with this choice.',
              style: TextStyle(fontSize: 12, color: c.inkFaint),
            ),
            const SizedBox(height: UriSpace.lg),
            const Eyebrow('Approval boundary'),
            const SizedBox(height: 8),
            for (final level in AutonomyLevel.values)
              RadioListTile<AutonomyLevel>(
                value: level,
                // ignore: deprecated_member_use
                groupValue: appState.preferences.autonomyLevel,
                // ignore: deprecated_member_use
                onChanged: (v) => appState.updatePreferences(
                  appState.preferences.copyWith(autonomyLevel: v),
                ),
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text(
                  _autonomyLabel(level),
                  style: TextStyle(fontSize: 13, color: c.ink),
                ),
              ),
            const SizedBox(height: 8),
            Eyebrow(
              'Permissions',
              trailing: services.readiness.isSimulated
                  ? const StatusBadge.simulated(compact: true)
                  : null,
            ),
            const SizedBox(height: 8),
            for (final p in services.readiness.permissions)
              PermissionRow(fact: p),
            const SizedBox(height: UriSpace.lg),
            const Eyebrow('Orb style'),
            const SizedBox(height: 8),
            ListenableBuilder(
              listenable: services.orbVariant,
              builder: (context, _) => Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final v in OrbVariant.values)
                    ChoiceChip(
                      key: ValueKey('orb-variant-${v.name}'),
                      label: Text(v.label),
                      selected: services.orbVariant.value == v,
                      onSelected: (_) => services.orbVariant.value = v,
                    ),
                ],
              ),
            ),
            const SizedBox(height: UriSpace.md),
            const Eyebrow('Orb palette'),
            const SizedBox(height: 8),
            ListenableBuilder(
              listenable: Listenable.merge([
                services.orbPalette,
                services.orbVariant,
              ]),
              builder: (context, _) => Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  ChoiceChip(
                    key: const ValueKey('orb-palette-default'),
                    label: const Text('Style default'),
                    selected: services.orbPalette.value == null,
                    onSelected: (_) => services.orbPalette.value = null,
                  ),
                  for (final p in OrbPalette.values)
                    ChoiceChip(
                      key: ValueKey('orb-palette-${p.name}'),
                      avatar: SizedBox(
                        width: 18,
                        height: 10,
                        child: Row(
                          children: [
                            for (final h in p.hues.take(3))
                              Expanded(child: ColoredBox(color: h)),
                          ],
                        ),
                      ),
                      label: Text(p.label),
                      selected: services.orbPalette.value == p,
                      onSelected: (_) => services.orbPalette.value = p,
                    ),
                ],
              ),
            ),
            const SizedBox(height: UriSpace.lg),
            const Eyebrow('Appearance'),
            const SizedBox(height: 8),
            if (themeCtl != null)
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final t in UriThemeChoice.values)
                    if (t != UriThemeChoice.system)
                      ChoiceChip(
                        avatar: CircleAvatar(
                          backgroundColor: t.swatch,
                          radius: 6,
                        ),
                        label: Text(t.label),
                        selected: themeCtl.current == t,
                        onSelected: (_) => themeCtl.setTheme(t),
                      ),
                ],
              ),
            SwitchListTile(
              key: const ValueKey('reduced-effects-switch'),
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(
                'Reduced visual effects',
                style: TextStyle(fontSize: 13, color: c.ink),
              ),
              subtitle: Text(
                'No shader, blur or glow. Every state stays readable.',
                style: TextStyle(fontSize: 12, color: c.inkFaint),
              ),
              value: services.effects.reducedEffects,
              onChanged: (v) => services.effects.setReducedEffects(v),
            ),
            SwitchListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text(
                'Reduced motion',
                style: TextStyle(fontSize: 13, color: c.ink),
              ),
              subtitle: Text(
                'The orb holds still; state shows by colour and badge.',
                style: TextStyle(fontSize: 12, color: c.inkFaint),
              ),
              value: services.effects.reducedMotion,
              onChanged: (v) => services.effects.setReducedMotion(v),
            ),
          ],
        );
      },
    );
  }

  static String _autonomyLabel(AutonomyLevel l) => switch (l) {
    AutonomyLevel.askEveryTime => 'Ask me before every action',
    AutonomyLevel.routineAutoApprove =>
      'Auto-approve routine actions, ask for the rest',
  };
}

class HarnessRow extends StatelessWidget {
  const HarnessRow({super.key, required this.fact, this.selectable = true});
  final HarnessFact fact;
  final bool selectable;

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final c = UriColors.of(context);
    final selected = services.selectedHarness.value == fact.id;
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: GlassPanel(
        glowBorder: selected,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Row(
          children: [
            if (selectable)
              Radio<String>(
                value: fact.id,
                // ignore: deprecated_member_use
                groupValue: services.selectedHarness.value,
                // ignore: deprecated_member_use
                onChanged: fact.usable
                    ? (v) => services.selectedHarness.value = v
                    : null,
              ),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    fact.displayName,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: c.ink,
                    ),
                  ),
                  Text(
                    '${fact.installed ? 'installed' : 'not installed'} · ${fact.authState} · ${fact.qualification}',
                    style: TextStyle(fontSize: 11.5, color: c.inkFaint),
                  ),
                  if (fact.requiredAction != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        fact.requiredAction!,
                        style: TextStyle(fontSize: 12, color: c.warning),
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            StatusBadge(
              fact.simulated ? TruthStatus.simulated : fact.truth,
              compact: true,
            ),
          ],
        ),
      ),
    );
  }
}

class _ProviderRow extends StatelessWidget {
  const _ProviderRow({
    required this.provider,
    required this.active,
    this.onSelect,
  });
  final ProviderEntry provider;
  final bool active;
  final VoidCallback? onSelect;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final status = !provider.configured
        ? TruthStatus.pending
        : provider.available
        ? TruthStatus.configured
        : TruthStatus.unavailable;
    final local = provider.adapter == 'ollama';
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: GlassPanel(
        glowBorder: active,
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
        child: Row(
          children: [
            Icon(
              local ? Icons.computer_rounded : Icons.cloud_outlined,
              size: 18,
              color: c.accentInk,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    provider.displayName,
                    style: TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: c.ink,
                    ),
                  ),
                  Text(
                    '${local ? 'Local' : 'External'} · ${provider.activeModel ?? (provider.models.isNotEmpty ? provider.models.first.displayName : 'no model')}',
                    style: TextStyle(fontSize: 11.5, color: c.inkFaint),
                  ),
                ],
              ),
            ),
            StatusBadge(status, compact: true),
            const SizedBox(width: 8),
            if (active)
              Text(
                'Active',
                style: TextStyle(
                  fontSize: 12,
                  color: c.accent,
                  fontWeight: FontWeight.w600,
                ),
              )
            else
              TextButton(onPressed: onSelect, child: const Text('Use')),
          ],
        ),
      ),
    );
  }
}

class PermissionRow extends StatelessWidget {
  const PermissionRow({super.key, required this.fact});
  final PermissionFact fact;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 5),
      child: Row(
        children: [
          Icon(
            fact.granted ? Icons.check_circle_rounded : Icons.block_rounded,
            size: 16,
            color: fact.granted ? c.success : c.inkFaint,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              fact.label,
              style: TextStyle(fontSize: 13, color: c.ink),
            ),
          ),
          Text(
            fact.requiresApproval ? 'asks each time' : 'no approval needed',
            style: TextStyle(fontSize: 11.5, color: c.inkFaint),
          ),
          if (fact.simulated) ...[
            const SizedBox(width: 8),
            const StatusBadge.simulated(compact: true),
          ],
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Context panel
// ---------------------------------------------------------------------------

class _ContextPanel extends StatelessWidget {
  const _ContextPanel();

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final appState = AppStateScope.of(context);
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    return Container(
      width: 300,
      decoration: BoxDecoration(
        border: Border(left: BorderSide(color: glass.border)),
        color: glass.fill,
      ),
      child: ListenableBuilder(
        listenable: Listenable.merge([
          services.companion,
          services.work,
          services.selectedHarness,
          services.reasoningMode,
          appState,
          ?services.oi,
        ]),
        builder: (context, _) {
          final signal = services.companion.signal;
          final oi = services.oi;
          final harness = services.readiness.harnesses
              .cast<HarnessFact?>()
              .firstWhere(
                (h) => h!.id == services.selectedHarness.value,
                orElse: () => null,
              );
          final results = services.work.items
              .where(
                (i) =>
                    i.state == WorkItemState.completed && i.outputName != null,
              )
              .take(4)
              .toList();
          final lastTurn = appState.conversation.isEmpty
              ? null
              : appState.conversation.last;
          return ListView(
            padding: const EdgeInsets.all(UriSpace.md),
            children: [
              const Eyebrow('Now'),
              const SizedBox(height: 6),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      signal.state.label,
                      key: const ValueKey('context-now-state'),
                      style: TextStyle(
                        fontWeight: FontWeight.w600,
                        color: c.ink,
                      ),
                    ),
                  ),
                  if (signal.simulated)
                    const StatusBadge.simulated(compact: true),
                ],
              ),
              if (signal.detail != null)
                Text(
                  signal.detail!,
                  style: TextStyle(fontSize: 12.5, color: c.inkSoft),
                ),
              Text(
                'source: ${signal.sourceName ?? 'none'}',
                style: TextStyle(fontSize: 11, color: c.inkFaint),
              ),
              const SizedBox(height: UriSpace.lg),
              const Eyebrow('Executor'),
              const SizedBox(height: 6),
              _KeyValue('Harness', harness?.displayName ?? 'None selected'),
              // Working system: the real Brain selection and state from the integrated worker.
              if (oi != null) ...[
                _KeyValue('Brain', oi.selectedRowId == 'runtime-v1' ? 'Runtime v1 (local)' : (oi.selectedRowId == 'deterministic' ? 'No Brain (deterministic rules)' : oi.selectedRowId)),
                _KeyValue('Model', '${oi.brainStatus['model_id'] ?? '—'} · ${oi.brainStatus['state'] ?? '…'}'),
                _KeyValue('Reasoning', 'Depth ${oi.depth.name}'),
              ] else ...[
                _KeyValue(
                  'Brain',
                  appState.activeBrain?.displayName ??
                      appState.activeBrain?.providerId ??
                      'Not set',
                ),
                _KeyValue('Model', appState.activeBrain?.model ?? '—'),
                _KeyValue('Reasoning', services.reasoningMode.value.label),
              ],
              _KeyValue(
                'Approvals',
                appState.preferences.autonomyLevel == AutonomyLevel.askEveryTime
                    ? 'Ask every time'
                    : 'Routine auto-approve',
              ),
              const SizedBox(height: UriSpace.lg),
              const Eyebrow('Context & files'),
              const SizedBox(height: 6),
              if (appState.attachments.isEmpty)
                Text(
                  'No attachments staged.',
                  style: TextStyle(fontSize: 12.5, color: c.inkFaint),
                ),
              for (final a in appState.attachments)
                _KeyValue(
                  'Attached',
                  a.filename,
                  simulated: services.appDataIsMock,
                ),
              for (final d in services.work.documents.take(3))
                _KeyValue('Document', d.name, simulated: d.simulated),
              const SizedBox(height: UriSpace.lg),
              const Eyebrow('Results'),
              const SizedBox(height: 6),
              if (results.isEmpty && lastTurn?.result == null)
                Text(
                  'No results yet.',
                  style: TextStyle(fontSize: 12.5, color: c.inkFaint),
                ),
              if (lastTurn?.result != null)
                _KeyValue(
                  'Last reply',
                  lastTurn!.result!.summary,
                  simulated: services.appDataIsMock,
                ),
              for (final r in results)
                _KeyValue('Saved', r.outputName!, simulated: r.simulated),
            ],
          );
        },
      ),
    );
  }
}

class _KeyValue extends StatelessWidget {
  const _KeyValue(this.k, this.v, {this.simulated = false});
  final String k;
  final String v;
  final bool simulated;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 78,
            child: Text(k, style: TextStyle(fontSize: 11.5, color: c.inkFaint)),
          ),
          Expanded(
            child: Text(
              v,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: 12.5, color: c.ink),
            ),
          ),
          if (simulated) ...[
            const SizedBox(width: 6),
            const StatusBadge.simulated(compact: true),
          ],
        ],
      ),
    );
  }
}

/// Re-exported for the dashboard's "needs you" count.
int pendingDecisionCount(AppState appState, WorkItemSource work) =>
    appState.tasks.length +
    work.items.where((i) => i.state == WorkItemState.awaitingApproval).length;

/// Exposed for tests that assert the orb's "needs user" state matches
/// the tasks region.
bool workNeedsUser(CompanionSignal s) => s.state.needsUser;
