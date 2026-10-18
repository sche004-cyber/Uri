import 'dart:async' show unawaited;

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
import '../a2ui/a2ui_dock.dart';
import '../companion/companion_state.dart';
import '../contracts/readiness_report.dart';
import '../contracts/work_items.dart';
import '../integration/draft_panel.dart';
import '../integration/oi_conversation.dart';
import '../integration/oi_widgets.dart';
import '../integration/ws_settings.dart';
import '../living_app.dart';
import '../living_scope.dart';
import '../office/office_workspace.dart';
import '../presentation/living_shell.dart';
import '../presentation/presentation_controller.dart';
import '../widgets/glass_panel.dart';
import '../widgets/living_composer.dart';
import '../widgets/scroll_when_short.dart';
import '../widgets/status_badge.dart';
import 'intelligence/intelligence_overview_view.dart';
import 'settings/companion_settings_section.dart';

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
      final services = LivingScope.of(context);
      if (services.visualV2 && services.oi != null) return;
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
            final railExpanded = w >= OrbDock.railExpandAt;
            // O2 (real-app run base1, R5-3): the context panel starts closed in Office, whose own panes need the width.
            final contextDefault = w >= 1180 && focus != WorkspaceFocus.office;
            final inlineContext = w >= 960;
            final showContext =
                inlineContext && (_contextOverride ?? contextDefault);
            return Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _Rail(
                  expanded: railExpanded,
                  focus: focus,
                  orbSpace: OrbDock.railOrbSpace(w),
                ),
                Expanded(
                  child: Column(
                    children: [
                      _FocusHeader(
                        focus: focus,
                        contextOpen: showContext,
                        onToggleContext: () {
                          if (inlineContext) {
                            setState(() => _contextOverride = !showContext);
                            return;
                          }
                          showDialog<void>(
                            context: context,
                            builder: (context) => Dialog(
                              child: SizedBox(
                                width: 320,
                                height: MediaQuery.sizeOf(context).height * .8,
                                child: Column(
                                  children: [
                                    Align(
                                      alignment: Alignment.centerRight,
                                      child: IconButton(
                                        tooltip: 'Close context',
                                        onPressed: () =>
                                            Navigator.of(context).pop(),
                                        icon: const Icon(Icons.close),
                                      ),
                                    ),
                                    const Expanded(child: _ContextPanel()),
                                  ],
                                ),
                              ),
                            ),
                          );
                        },
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
                              // URI Office (O2): the Office workspace. Reconciliation 2026-10-16 with UI V2: the
                              // Documents region stays (its 'Start new work' tiles send real turns in the integrated
                              // V2, BLK-INT-2) and Office is its own rail entry.
                              WorkspaceFocus.office =>
                                OfficeWorkspace(environment: LivingScope.of(context).office),
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
  const _Rail({
    required this.expanded,
    required this.focus,
    required this.orbSpace,
  });
  final bool expanded;
  final WorkspaceFocus focus;

  /// Space reserved at the top for the orb the shell docks there
  /// ([OrbDock.railOrbSpace]).
  final double orbSpace;

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    final width = expanded ? 200.0 : 88.0; // = OrbDock.railWidth
    const items = [
      (
        WorkspaceFocus.conversation,
        Icons.chat_bubble_outline_rounded,
        'Conversation',
      ),
      (WorkspaceFocus.tasks, Icons.check_circle_outline_rounded, 'Tasks'),
      (WorkspaceFocus.documents, Icons.description_outlined, 'Documents'),
      (WorkspaceFocus.office, Icons.table_chart_outlined, 'Office'),
      (WorkspaceFocus.intelligence, Icons.hub_outlined, 'Intelligence'),
      (WorkspaceFocus.settings, Icons.tune_rounded, 'Settings'),
    ];
    return AnimatedContainer(
      duration: UriMotion.mode,
      // Same curve as the shell's travelling orb, so at the expand threshold
      // the rail, its reserved orb space and the orb move together.
      curve: UriMotion.move,
      width: width,
      decoration: BoxDecoration(
        border: Border(right: BorderSide(color: glass.border)),
        color: glass.fill,
      ),
      // UIV2-F3: in a short window (the shrink into Companion) the rail
      // scrolls instead of overflowing (l13 evidence; 90 px at 300 px high).
      child: ScrollWhenShort(
        // label + dividers (~60) and every rail item (~44 each, the focus
        // items plus Dashboard and Companion); generous on purpose.
        minHeight: orbSpace + 80 + (items.length + 2) * 44,
        child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Orb dock (the shell draws the orb here, centred in the rail).
          AnimatedContainer(
            duration: UriMotion.mode,
            curve: UriMotion.move,
            height: orbSpace,
          ),
          ListenableBuilder(
            listenable: services.companion,
            builder: (context, _) {
              final s = services.companion.signal;
              return Padding(
                padding: const EdgeInsets.fromLTRB(10, 0, 10, 10),
                child: Text(
                  s.title,
                  key: const ValueKey('rail-state-label'),
                  textAlign: TextAlign.center,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontSize: UriType.caption,
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
                  fontSize: UriType.body,
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
      WorkspaceFocus.office => 'Office',
      WorkspaceFocus.intelligence => 'Intelligence',
      WorkspaceFocus.settings => 'Settings',
    };
    return ConstrainedBox(
      constraints: const BoxConstraints(minHeight: 56),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: UriSpace.md,
          vertical: 4,
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                title,
                style: TextStyle(
                  fontSize: UriType.title,
                  fontWeight: FontWeight.w600,
                  color: c.ink,
                ),
              ),
            ),
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
    final a2ui = LivingScope.of(context).a2ui;
    return Column(
      children: [
        Expanded(
          child: oi != null
              ? _OiWithDraft(conversation: oi)
              : UriConversationPane(
                  attachmentOpener: attachmentOpener,
                  supervisedHandoff: false,
                ),
        ),
        if (a2ui != null) A2uiDock(hub: a2ui, maxHeightFraction: 0.45),
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

/// Conversation plus the text-intelligence draft: side by side on wide
/// windows, stacked (draft above the composer) on narrow ones.
class _OiWithDraft extends StatelessWidget {
  const _OiWithDraft({required this.conversation});
  final OiConversation conversation;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: conversation,
      builder: (context, _) => LayoutBuilder(
        builder: (context, box) {
          final pane = OiConversationPane(conversation: conversation);
          if (conversation.draft == null) return pane;
          final panel = DraftPanel(conversation: conversation);
          if (box.maxWidth >= 900) {
            return Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Expanded(child: pane),
                const SizedBox(width: UriSpace.sm),
                SizedBox(
                  width: (box.maxWidth * 0.45).clamp(360.0, 560.0),
                  child: Padding(
                    padding: const EdgeInsets.only(
                      top: UriSpace.sm,
                      bottom: UriSpace.sm,
                    ),
                    child: panel,
                  ),
                ),
              ],
            );
          }
          return Column(
            children: [
              Expanded(child: pane),
              ConstrainedBox(
                constraints: BoxConstraints(maxHeight: box.maxHeight * 0.55),
                child: panel,
              ),
            ],
          );
        },
      ),
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
            if (services.visualV2 &&
                services.oi == null &&
                appState.isLoadingTasks)
              const Text('Loading pending decisions…'),
            if (services.visualV2 &&
                services.oi == null &&
                appState.tasksError != null)
              ListTile(
                title: const Text('Pending decisions unavailable'),
                subtitle: Text(appState.tasksError!),
                trailing: TextButton(
                  onPressed: appState.loadTasks,
                  child: const Text('Retry'),
                ),
              ),
            if (services.a2ui != null)
              A2uiDock(
                hub: services.a2ui!,
                placements: const ['workspace'],
                maxHeightFraction: 0.7,
                showCalendarEntry: true,
              ),
            Eyebrow(
              'Needs your decision',
              trailing: Text(
                '${waiting.length + pending.length + (services.visualV2 && services.oi?.pendingApproval != null ? 1 : 0) + (services.visualV2 && services.oi?.pendingConfirmation != null ? 1 : 0)}',
                style: TextStyle(fontSize: UriType.caption, color: c.inkFaint),
              ),
            ),
            const SizedBox(height: 8),
            if (waiting.isEmpty &&
                pending.isEmpty &&
                (!services.visualV2 ||
                    (services.oi?.pendingApproval == null &&
                        services.oi?.pendingConfirmation == null)) &&
                (!services.visualV2 ||
                    (!appState.isLoadingTasks && appState.tasksError == null)))
              _EmptyLine('Nothing is waiting for you.'),
            if (services.visualV2 && services.oi?.pendingConfirmation != null)
              OiConfirmationCard(conversation: services.oi!),
            if (services.visualV2 && services.oi?.pendingApproval != null)
              OiApprovalCard(conversation: services.oi!),
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
      style: TextStyle(fontSize: UriType.body, color: UriColors.of(context).inkFaint),
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
              style: TextStyle(fontSize: UriType.body, color: c.inkSoft),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton(
                  key: ValueKey('approve-${item.id}'),
                  onPressed: () => services.work.approve(item.id),
                  child: const Text('Approve'),
                ),
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
              style: TextStyle(fontSize: UriType.label, color: c.inkFaint),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                FilledButton(
                  onPressed: () => appState.approveTask(task.id),
                  child: const Text('Approve'),
                ),
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
                  style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
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
                style: TextStyle(fontSize: UriType.label, color: c.inkFaint),
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
              style: TextStyle(fontSize: UriType.body, color: c.ink),
            ),
          ),
          if (item.outputName != null)
            Text(
              item.outputName!,
              style: TextStyle(fontSize: UriType.label, color: c.inkFaint),
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
        final realTurns = services.visualV2 && services.oi != null;
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
              // In the integrated V2 the tiles start a real turn (below), so
              // they are not simulated even though the document list is.
              trailing: services.work.isSimulated && !realTurns
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
                      final oi = services.oi;
                      if (realTurns && oi != null) {
                        // Same rule as the composer: one turn at a time.
                        if (!oi.busy) unawaited(oi.send(title, newWork: true));
                        services.presentation.setFocus(
                          WorkspaceFocus.conversation,
                        );
                        return;
                      }
                      if (services.visualV2 && !services.appDataIsMock) {
                        AppStateScope.of(context).ask(title);
                        services.presentation.setFocus(
                          WorkspaceFocus.conversation,
                        );
                        return;
                      }
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
                          style: TextStyle(fontSize: UriType.body, color: c.ink),
                        ),
                      ),
                      Text(
                        _relative(d.modifiedAt),
                        style: TextStyle(fontSize: UriType.label, color: c.inkFaint),
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
                  fontSize: UriType.body,
                  fontWeight: FontWeight.w600,
                  color: c.ink,
                ),
              ),
              Text('New', style: TextStyle(fontSize: UriType.caption, color: c.inkFaint)),
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

/// Executor, Brain, reasoning and approvals; then the companion, its
/// appearance, performance and voice ([CompanionSettingsSection]), which also
/// carries the classic orb's free theme choice ([LivingThemeController]).
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
            if (services.classicInterfaceBuilder != null)
              ListTile(
                title: const Text('All settings and diagnostics'),
                subtitle: const Text(
                  'Open existing authentication, devices, connections and operational screens',
                ),
                trailing: const Icon(Icons.open_in_new),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: services.classicInterfaceBuilder!,
                  ),
                ),
              ),
            if (services.visualV2) const CompanionSettingsSection(),
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
              style: TextStyle(fontSize: UriType.label, color: c.inkFaint),
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
                  style: TextStyle(fontSize: UriType.body, color: c.ink),
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
            // Companion, appearance, performance and voice: one section, in
            // the selected companion's own theme.
            if (!services.visualV2) const CompanionSettingsSection(),
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
                      fontSize: UriType.body,
                      fontWeight: FontWeight.w600,
                      color: c.ink,
                    ),
                  ),
                  Text(
                    '${fact.installed ? 'installed' : 'not installed'} · ${fact.authState} · ${fact.qualification}',
                    style: TextStyle(fontSize: UriType.label, color: c.inkFaint),
                  ),
                  if (fact.requiredAction != null)
                    Padding(
                      padding: const EdgeInsets.only(top: 4),
                      child: Text(
                        fact.requiredAction!,
                        style: TextStyle(fontSize: UriType.label, color: c.warning),
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
                      fontSize: UriType.body,
                      fontWeight: FontWeight.w600,
                      color: c.ink,
                    ),
                  ),
                  Text(
                    '${local ? 'Local' : 'External'} · ${provider.activeModel ?? (provider.models.isNotEmpty ? provider.models.first.displayName : 'no model')}',
                    style: TextStyle(fontSize: UriType.label, color: c.inkFaint),
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
                  fontSize: UriType.label,
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
              style: TextStyle(fontSize: UriType.body, color: c.ink),
            ),
          ),
          Text(
            fact.requiresApproval ? 'asks each time' : 'no approval needed',
            style: TextStyle(fontSize: UriType.label, color: c.inkFaint),
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
          // With the real worker connected this rail is operational: placeholder
          // (simulated) documents and results are not mixed into it (FCV-10).
          final live = oi != null;
          final results = services.work.items
              .where(
                (i) =>
                    i.state == WorkItemState.completed &&
                    i.outputName != null &&
                    !(live && i.simulated),
              )
              .take(4)
              .toList();
          final documents = services.work.documents
              .where((d) => !(live && d.simulated))
              .take(3)
              .toList();
          final mockAppData = live && services.appDataIsMock;
          final attachments = mockAppData ? const [] : appState.attachments;
          final lastTurn = appState.conversation.isEmpty || mockAppData
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
                      signal.title,
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
                  style: TextStyle(fontSize: UriType.body, color: c.inkSoft),
                ),
              Text(
                'source: ${signal.sourceName ?? 'none'}',
                style: TextStyle(fontSize: UriType.caption, color: c.inkFaint),
              ),
              const SizedBox(height: UriSpace.lg),
              const Eyebrow('Executor'),
              const SizedBox(height: 6),
              _KeyValue('Harness', harness?.displayName ?? 'None selected'),
              // Working system: the real Brain selection and state from the integrated worker.
              if (oi != null) ...[
                _KeyValue(
                  'Brain',
                  oi.selectedRowId == 'runtime-v1'
                      ? 'Runtime v1 (local)'
                      : (oi.selectedRowId == 'deterministic'
                            ? 'No Brain (deterministic rules)'
                            : oi.selectedRowId),
                ),
                _KeyValue(
                  'Model',
                  '${oi.brainStatus['model_id'] ?? '—'} · ${oiBrainStateLabel(oi.brainStatus['state'] as String?)}',
                ),
                _KeyValue('Reasoning', 'Depth ${oi.depth.name}'),
                // Core requires an explicit approval for every action; nothing here is a preference.
                _KeyValue(
                  'Approvals',
                  'Every action needs your approval (Core)',
                ),
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
              if (oi == null)
                _KeyValue(
                  'Approvals',
                  appState.preferences.autonomyLevel ==
                          AutonomyLevel.askEveryTime
                      ? 'Ask every time'
                      : 'Routine auto-approve',
                ),
              const SizedBox(height: UriSpace.lg),
              const Eyebrow('Context & files'),
              const SizedBox(height: 6),
              if (attachments.isEmpty && documents.isEmpty)
                Text(
                  'No attachments staged.',
                  style: TextStyle(fontSize: UriType.body, color: c.inkFaint),
                ),
              for (final a in attachments)
                _KeyValue(
                  'Attached',
                  a.filename,
                  simulated: services.appDataIsMock,
                ),
              for (final d in documents)
                _KeyValue('Document', d.name, simulated: d.simulated),
              const SizedBox(height: UriSpace.lg),
              const Eyebrow('Results'),
              const SizedBox(height: 6),
              if (results.isEmpty && lastTurn?.result == null)
                Text(
                  'No results yet.',
                  style: TextStyle(fontSize: UriType.body, color: c.inkFaint),
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
            child: Text(k, style: TextStyle(fontSize: UriType.label, color: c.inkFaint)),
          ),
          Expanded(
            child: Text(
              v,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: UriType.body, color: c.ink),
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
