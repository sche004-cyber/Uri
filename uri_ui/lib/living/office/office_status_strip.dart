import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import 'document_controller.dart';

/// The compact status strip under the Office workspace (plan §4.1, §4.7): current step, engine state, findings count,
/// and the last error with its recovery action. Wraps to two lines below 720 px.
class OfficeStatusStrip extends StatelessWidget {
  const OfficeStatusStrip({super.key, required this.controller, this.wrap = false});
  final OfficeWorkspaceController controller;
  final bool wrap;

  @override
  Widget build(BuildContext context) {
    final c = controller;
    final colors = UriColors.of(context);
    final lo = c.engine('libreoffice');
    final loState = '${lo?['state'] ?? 'unknown'}';
    final engineText = switch (loState) {
      'running' => 'Document engine running',
      'ready' || 'idle_stopped' => 'Document engine ready',
      'verifying' => 'Checking the document engine (first time: about 2 minutes)…',
      'starting' => 'Preparing preview engine…',
      'unavailable' => 'Document engine unavailable: ${officeErrorText['${lo?['reason']}'] ?? 'see diagnostics'}',
      _ => 'Document engine not checked yet',
    };
    final findings = (c.workflowView?['findings'] as List?)?.length ?? 0;
    final children = <Widget>[
      if (c.stepLabel != null) Text(c.stepLabel!, key: const ValueKey('office-status-step')),
      Text(engineText, key: const ValueKey('office-status-engine'),
          style: TextStyle(color: loState == 'unavailable' ? colors.warning : colors.inkSoft)),
      if (loState == 'unavailable' && c.lastError == null)
        TextButton(key: const ValueKey('office-status-verify-engine'), onPressed: c.busy ? null : () async {
          try {
            await c.client.verifyEngine();
          } catch (_) {}
          await c.refresh();
        }, child: const Text('Check the engine again')),
      if (findings > 0) Text('$findings finding(s)', key: const ValueKey('office-status-findings')),
      if (c.lastError != null)
        Row(mainAxisSize: MainAxisSize.min, children: [
          Text(c.lastError!, key: const ValueKey('office-status-error'), style: TextStyle(color: colors.danger)),
          if (const {'ENGINE_INTEGRITY', 'ENGINE_UNAVAILABLE', 'ENGINE_CHECK_FAILED'}.contains(c.lastErrorCode))
            TextButton(key: const ValueKey('office-status-verify'), onPressed: () async {
              try {
                await c.client.verifyEngine();
              } catch (_) {}
              await c.refresh();
            }, child: const Text('Verify engine')),
        ]),
    ];
    return Container(
      key: const ValueKey('office-status-strip'),
      color: colors.surfaceSunken,
      padding: const EdgeInsets.symmetric(horizontal: UriSpace.sm, vertical: UriSpace.xs),
      child: DefaultTextStyle.merge(
        style: const TextStyle(fontSize: 12),
        child: wrap
            ? Wrap(spacing: UriSpace.md, runSpacing: 2, children: children)
            : Row(children: [
                for (final w in children) ...[w, const SizedBox(width: UriSpace.md)],
              ]),
      ),
    );
  }
}
