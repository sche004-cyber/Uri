import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../widgets/glass_panel.dart';
import 'oi_conversation.dart';

/// Lets the working-system root offer the classic (Hybrid) interface from
/// Living Settings (owner decision WS-D4). Absent in the mock preview.
class WorkingSystemShellSwitch extends InheritedWidget {
  const WorkingSystemShellSwitch({super.key, required this.openClassic, required super.child});

  final VoidCallback openClassic;

  static WorkingSystemShellSwitch? maybeOf(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<WorkingSystemShellSwitch>();

  @override
  bool updateShouldNotify(WorkingSystemShellSwitch old) => old.openClassic != openClassic;
}

/// Real settings for the working system: the Brain catalog (with why a row
/// is not selectable), remembered facts (deterministic read, no model), the
/// cloud policy ($5/month, activation disabled), and the classic interface.
class WorkingSystemSettingsSection extends StatefulWidget {
  const WorkingSystemSettingsSection({super.key, required this.conversation});
  final OiConversation conversation;

  @override
  State<WorkingSystemSettingsSection> createState() => _WorkingSystemSettingsSectionState();
}

class _WorkingSystemSettingsSectionState extends State<WorkingSystemSettingsSection> {
  @override
  void initState() {
    super.initState();
    final conv = widget.conversation;
    conv.refreshStatus();
    conv.refreshMemory();
    conv.refreshCloud();
  }

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final shell = WorkingSystemShellSwitch.maybeOf(context);
    final conv = widget.conversation;
    TextStyle h = TextStyle(color: c.ink, fontWeight: FontWeight.w600);
    TextStyle small = TextStyle(color: c.inkSoft, fontSize: 12);
    return ListenableBuilder(
      listenable: conv,
      builder: (context, _) {
        final rows = [for (final r in (conv.catalog['rows'] as List? ?? const [])) if (r is Map) r];
        final cloud = conv.cloud;
        return Column(
          key: const ValueKey('ws-settings'),
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Brain (reasoning source)', style: h),
                  const SizedBox(height: 4),
                  Text('Runtime v1 is the default. Switching is always your explicit choice; URI never falls back.',
                      style: small),
                  const SizedBox(height: 8),
                  for (final r in rows)
                    ListTile(
                      dense: true,
                      contentPadding: EdgeInsets.zero,
                      key: ValueKey('ws-brain-row-${r['id']}'),
                      leading: Icon(
                        r['selected'] == true ? Icons.radio_button_checked : Icons.radio_button_unchecked,
                        size: 18,
                        color: r['selectable'] == true ? c.accent : c.inkFaint,
                      ),
                      title: Text('${r['display']}', style: TextStyle(color: c.ink, fontSize: 13)),
                      subtitle: Text(
                        '${r['state']}${r['why_not'] != null ? ' · ${r['why_not']}' : ''}${r['note'] != null ? ' · ${r['note']}' : ''}',
                        style: small,
                      ),
                      onTap: r['selectable'] == true && r['selected'] != true && !conv.busy
                          ? () => conv.selectBrain(r['id'] as String)
                          : null,
                    ),
                ],
              ),
            ),
            const SizedBox(height: UriSpace.md),
            GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Expanded(child: Text('What URI remembers', style: h)),
                    IconButton(
                      tooltip: 'Refresh',
                      icon: const Icon(Icons.refresh_rounded, size: 16),
                      onPressed: conv.refreshMemory,
                    ),
                  ]),
                  Text('Read from this device\'s client store. No model is used.', style: small),
                  const SizedBox(height: 6),
                  if (conv.memory.isEmpty) Text('Nothing remembered yet.', style: small),
                  for (final f in conv.memory)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 2),
                      child: Text('• $f', key: const ValueKey('ws-memory-fact'), style: TextStyle(color: c.ink, fontSize: 13)),
                    ),
                  const SizedBox(height: 4),
                  Text('To add a fact, say "remember that …" and approve the card.', style: small),
                ],
              ),
            ),
            const SizedBox(height: UriSpace.md),
            GlassPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Cloud providers', style: h),
                  const SizedBox(height: 4),
                  Text(
                    cloud.isEmpty
                        ? 'Loading policy…'
                        : 'Policy: \$${(cloud['cap_usd'] as num?)?.toStringAsFixed(2)} per month, '
                            'spent \$${(cloud['spent_usd'] as num?)?.toStringAsFixed(2)}. Each paid call would need its own '
                            'manual approval. Activation: ${cloud['activation']}.',
                    key: const ValueKey('ws-cloud-policy'),
                    style: small,
                  ),
                  for (final p in (cloud['providers'] as List? ?? const []))
                    if (p is Map)
                      Text('• ${p['display']}: ${p['activation']}, credentials ${p['credentials']}', style: small),
                ],
              ),
            ),
            if (shell != null) ...[
              const SizedBox(height: UriSpace.md),
              OutlinedButton.icon(
                key: const ValueKey('ws-open-classic'),
                onPressed: shell.openClassic,
                icon: const Icon(Icons.view_sidebar_outlined, size: 16),
                label: const Text('Open the classic interface'),
              ),
            ],
            const SizedBox(height: UriSpace.lg),
          ],
        );
      },
    );
  }
}
