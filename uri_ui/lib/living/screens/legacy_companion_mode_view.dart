import 'package:flutter/material.dart';

import '../../services/file_picker_service.dart';
import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../a2ui/a2ui_dock.dart';
import '../companion/companion_state.dart';
import '../assist/assist_scope_line.dart';
import '../living_scope.dart';
import '../presentation/presentation_controller.dart';
import '../widgets/living_composer.dart';
import '../widgets/status_badge.dart';

/// Companion mode: the orb (drawn by the shell at [orbRect]), one status
/// line, a composer, and two quiet ways into the larger forms.
///
/// Nothing else. The brief's "minimal floating Energy Orb with contextual
/// interactions and quick access" is satisfied by: tap orb -> Workspace;
/// type -> conversation; the two mode chips; and the state-specific
/// action under the status line (Approve / Review when something waits).
class LegacyCompanionModeView extends StatelessWidget {
  const LegacyCompanionModeView({
    super.key,
    required this.orbRect,
    this.filePicker,
  });

  final Rect orbRect;
  final FilePickerFn? filePicker;

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    return ListenableBuilder(
      listenable: Listenable.merge([services.companion, services.work]),
      builder: (context, _) {
        final signal = services.companion.signal;
        final needsUser = signal.state.needsUser;
        return LayoutBuilder(
          builder: (context, constraints) {
            final narrow = constraints.maxWidth < 520;
            final composerWidth = (constraints.maxWidth - 32).clamp(
              200.0,
              560.0,
            );
            return Column(
              children: [
                // Space the shell's orb occupies.
                SizedBox(height: orbRect.bottom + 12),
                // Status line.
                AnimatedSwitcher(
                  duration: UriMotion.fast,
                  child: Column(
                    key: ValueKey('${signal.state}-${signal.headline}-${signal.detail}'),
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          _StateDot(state: signal.state),
                          const SizedBox(width: 8),
                          Text(
                            signal.title,
                            key: const ValueKey('companion-state-label'),
                            style: TextStyle(
                              fontSize: 15,
                              fontWeight: FontWeight.w600,
                              color: c.ink,
                              letterSpacing: 0.2,
                            ),
                          ),
                          if (signal.simulated) ...[
                            const SizedBox(width: 8),
                            const StatusBadge.simulated(compact: true),
                          ],
                        ],
                      ),
                      if (signal.detail != null && signal.detail!.isNotEmpty)
                        Padding(
                          padding: const EdgeInsets.only(top: 4),
                          child: ConstrainedBox(
                            constraints: BoxConstraints(
                              maxWidth: composerWidth,
                            ),
                            child: Text(
                              signal.detail!,
                              textAlign: TextAlign.center,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: TextStyle(fontSize: 13, color: c.inkSoft),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 14),
                if (needsUser)
                  FilledButton.icon(
                    key: const ValueKey('companion-review'),
                    style: FilledButton.styleFrom(
                      backgroundColor: c.warning,
                      foregroundColor: c.canvas,
                    ),
                    onPressed: () => services.presentation.setMode(
                      UiPresentationMode.workspace,
                      focus: WorkspaceFocus.tasks,
                    ),
                    icon: const Icon(Icons.rule_rounded, size: 16),
                    label: const Text('Review and decide'),
                  ),
                if (services.a2ui != null)
                  Expanded(
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Align(
                        alignment: Alignment.topCenter,
                        child: A2uiCompanionSlot(
                          hub: services.a2ui!,
                          presentation: services.presentation,
                          width: composerWidth,
                        ),
                      ),
                    ),
                  )
                else
                  const Spacer(),
                SizedBox(
                  width: composerWidth,
                  child: LivingComposer(
                    filePicker: filePicker,
                    compact: narrow,
                    hint: 'Ask URI, or say "URI dashboard"',
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 8,
                  alignment: WrapAlignment.center,
                  children: [
                    _ModeChip(
                      icon: Icons.view_sidebar_outlined,
                      label: 'Workspace',
                      onTap: () => services.presentation.setMode(
                        UiPresentationMode.workspace,
                      ),
                    ),
                    _ModeChip(
                      icon: Icons.grid_view_rounded,
                      label: 'Dashboard',
                      onTap: () => services.presentation.setMode(
                        UiPresentationMode.dashboard,
                      ),
                    ),
                    _ModeChip(
                      icon: Icons.visibility_outlined,
                      label: 'Assist',
                      onTap: () => services.presentation.setMode(
                        UiPresentationMode.assist,
                      ),
                    ),
                  ],
                ),
                if (services.assist != null)
                  AssistScopeLine(assist: services.assist!),
                SizedBox(height: narrow ? 14 : 22),
                Text(
                  'Click the orb to ask; double-click opens the workspace',
                  style: TextStyle(
                    fontSize: 11,
                    color: glass.isDark ? c.inkFaint : c.inkSoft,
                  ),
                ),
                const SizedBox(height: 10),
              ],
            );
          },
        );
      },
    );
  }
}

class _StateDot extends StatelessWidget {
  const _StateDot({required this.state});
  final CompanionState state;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final color = switch (state) {
      CompanionState.awaitingApproval => c.warning,
      CompanionState.success => c.success,
      CompanionState.error => c.danger,
      CompanionState.unavailable => c.inkFaint,
      _ => c.accent,
    };
    return Container(
      width: 8,
      height: 8,
      decoration: BoxDecoration(
        color: color,
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(color: color.withValues(alpha: 0.6), blurRadius: 6),
        ],
      ),
    );
  }
}

class _ModeChip extends StatelessWidget {
  const _ModeChip({
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
      shape: StadiumBorder(side: BorderSide(color: glass.border)),
      child: InkWell(
        customBorder: const StadiumBorder(),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(icon, size: 15, color: c.inkSoft),
              const SizedBox(width: 7),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12.5,
                  color: c.ink,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
