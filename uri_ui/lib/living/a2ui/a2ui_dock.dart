import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../presentation/presentation_controller.dart';
import 'a2ui_hub.dart';
import 'a2ui_view.dart';

/// Companion placement: a light card under the orb for `companion` surfaces.
///
/// A `workspace` surface is never forced into the Companion. It is announced
/// with one chip that opens the Workspace through the existing restricted
/// [UiPresentationController] vocabulary (mode + focus); a surface itself can
/// never change the mode.
class A2uiCompanionSlot extends StatelessWidget {
  const A2uiCompanionSlot({
    super.key,
    required this.hub,
    required this.presentation,
    required this.width,
  });

  final A2uiHub hub;
  final UiPresentationController presentation;
  final double width;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: hub,
      builder: (context, _) {
        final mine = [...hub.placed('companion'), ...hub.placed('inline')];
        final elsewhere = hub.placed('workspace');
        if (mine.isEmpty && elsewhere.isEmpty && hub.notices.isEmpty) {
          return const SizedBox.shrink();
        }
        final c = UriColors.of(context);
        return Center(
          child: SizedBox(
            width: width,
            child: SingleChildScrollView(
              key: const ValueKey('a2ui.companion-slot'),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  A2uiNotices(hub: hub),
                  for (final s in mine)
                    Padding(
                      padding: const EdgeInsets.only(bottom: UriSpace.sm),
                      child: A2uiSurfaceView(
                        hub: hub,
                        surfaceId: s.id,
                        compact: true,
                      ),
                    ),
                  if (elsewhere.isNotEmpty)
                    Center(
                      child: ActionChip(
                        key: const ValueKey('a2ui.open-workspace'),
                        avatar: Icon(
                          Icons.rule_rounded,
                          size: 16,
                          color: c.accent,
                        ),
                        label: Text(
                          elsewhere.length == 1
                              ? '${elsewhere.first.title}: ready for you in Workspace'
                              : '${elsewhere.length} items ready for you in Workspace',
                        ),
                        onPressed: () => presentation.setMode(
                          UiPresentationMode.workspace,
                          focus: WorkspaceFocus.tasks,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

/// Workspace placement: every open surface of the given placements, in a
/// bounded scroll area, with the calendar review entry point.
class A2uiDock extends StatelessWidget {
  const A2uiDock({
    super.key,
    required this.hub,
    this.placements = const ['companion', 'inline', 'workspace'],
    this.maxHeightFraction = 0.55,
    this.showCalendarEntry = false,
  });

  final A2uiHub hub;
  final List<String> placements;
  final double maxHeightFraction;
  final bool showCalendarEntry;

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: hub,
      builder: (context, _) {
        final list = [for (final p in placements) ...hub.placed(p)];
        if (list.isEmpty && hub.notices.isEmpty && !showCalendarEntry) {
          return const SizedBox.shrink();
        }
        final h = MediaQuery.sizeOf(context).height * maxHeightFraction;
        return ConstrainedBox(
          constraints: BoxConstraints(maxHeight: h),
          child: SingleChildScrollView(
            key: ValueKey('a2ui.dock.${placements.join('-')}'),
            padding: const EdgeInsets.fromLTRB(
              UriSpace.md,
              UriSpace.sm,
              UriSpace.md,
              UriSpace.sm,
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                A2uiNotices(hub: hub),
                if (showCalendarEntry &&
                    hub.scheduler != null &&
                    hub.surface('calendar-review') == null)
                  Align(
                    alignment: Alignment.centerLeft,
                    child: TextButton.icon(
                      key: const ValueKey('a2ui.open-calendar'),
                      icon: const Icon(Icons.event_note_rounded, size: 16),
                      label: const Text('Review festival calendar'),
                      onPressed: hub.openCalendar,
                    ),
                  ),
                for (final s in list)
                  Padding(
                    padding: const EdgeInsets.only(bottom: UriSpace.md),
                    child: A2uiSurfaceView(hub: hub, surfaceId: s.id),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}
