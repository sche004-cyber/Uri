import 'dart:async';

import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import '../living_scope.dart';
import '../a2ui/a2ui_hub.dart';
import 'office_bridge.dart';
import 'office_companion_pane.dart';
import 'office_client.dart';
import 'office_controller.dart';

/// The Office region of the Workspace: open a workbook (file picker or Google Sheets link), co-edit it in the
/// sheet view, ask URI for changes, accept or reject each URI change, then approve saving through the service's
/// hash-bound approval card. The workbook is never written without that approval.
///
/// The right pane is the URI companion for the open workbook: the owner's requests (typed in the companion composer
/// or spoken with push-to-talk), URI's replies, URI's suggested changes with Accept and Reject, and the approval
/// card. While this region shows an open workbook, the companion's requests go to it (see
/// [LivingServices.activeOfficeTarget]); elsewhere they go to the ordinary conversation.
class OfficeRegion extends StatefulWidget {
  const OfficeRegion({super.key, required this.environment, this.clientFactory = OfficeClient.discover, this.hub,
      this.onController, this.onTurn});

  /// Null when the platform cannot host the sheet view (no WebView2); the region says so.
  final OfficeEnvironment? environment;
  final OfficeClient? Function() clientFactory;

  /// O2: inside the Office workspace, the region-level A2UI hub, a callback with the sheet controller, and the
  /// workspace conversation's sink. When [hub] is given, the workspace is the companion's request target.
  final A2uiHub? hub;
  final void Function(OfficeController controller)? onController;
  final void Function(OfficeTurn turn)? onTurn;

  @override
  State<OfficeRegion> createState() => _OfficeRegionState();
}

class _OfficeRegionState extends State<OfficeRegion> {
  OfficeController? _c;
  String? _startError;
  final _link = TextEditingController();
  ValueNotifier<OfficeRequestTarget?>? _target;   // the living scope's Office target, when there is a scope

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final target = LivingScope.maybeOf(context)?.officeTarget;
    if (!identical(target, _target)) {
      _release();
      _target = target;
      _claim();
    }
  }

  void _claim() {
    final c = _c;
    if (widget.hub != null) return;            // inside the workspace, the workspace is the target
    if (c != null && _target != null) _target!.value = c;
  }

  void _release() {
    if (widget.hub != null) return;
    final t = _target;
    if (t != null && _c != null && identical(t.value, _c)) t.value = null;
  }

  @override
  void initState() {
    super.initState();
    unawaited(_start());
  }

  Future<void> _start() async {
    final env = widget.environment;
    if (env == null) {
      setState(() => _startError = 'The sheet view needs the Windows WebView2 runtime, which is not available here.');
      return;
    }
    final client = widget.clientFactory();
    if (client == null) {
      setState(() => _startError = 'The URI Office service is not running. Start URI Office, then open this again.');
      return;
    }
    final surface = env.surfaceFactory();
    // Read without registering a dependency: this runs from initState.
    final keep = context.getInheritedWidgetOfExactType<LivingScope>()?.services.officeKeep;
    final c = OfficeController(client: client, surface: surface, keep: keep, hub: widget.hub, onTurn: widget.onTurn);
    widget.onController?.call(c);
    try {
      await surface.start();
    } catch (e) {
      c.dispose();
      if (mounted) setState(() => _startError = 'The sheet view could not start safely: $e');
      return;
    }
    if (!mounted) {
      c.dispose();
      return;
    }
    setState(() => _c = c);
    _claim();
    await c.resume();                    // the workbook kept while the owner was away from Office (R1-02)
  }

  @override
  void dispose() {
    _release();
    _c?.dispose();
    _link.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colors = UriColors.of(context);
    final c = _c;
    if (_startError != null) {
      return Center(child: Padding(padding: const EdgeInsets.all(24), child: Text(_startError!, key: const ValueKey('office-start-error'))));
    }
    if (c == null) return const Center(child: CircularProgressIndicator());
    return ListenableBuilder(
      listenable: Listenable.merge([c, c.hub]),
      builder: (context, _) {
        final open = c.workbookId != null;
        return Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _toolbar(context, c, open),
              if (c.notice != null)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(c.notice!, key: const ValueKey('office-notice'), style: TextStyle(color: colors.warning)),
                ),
              const SizedBox(height: 8),
              Expanded(
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Expanded(
                      child: ClipRRect(
                        borderRadius: BorderRadius.circular(8),
                        child: c.surface.build(context),
                      ),
                    ),
                    const SizedBox(width: 12),
                    SizedBox(width: 380, child: OfficeSheetCompanion(controller: c, environment: widget.environment!)),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _toolbar(BuildContext context, OfficeController c, bool open) {
    final env = widget.environment!;
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        FilledButton.icon(
          key: const ValueKey('office-open-file'),
          onPressed: c.busy
              ? null
              : () async {
                  final path = await env.pickWorkbookPath();
                  if (path != null) await c.openLocal(path);
                },
          icon: const Icon(Icons.folder_open_rounded),
          label: const Text('Open file'),
        ),
        if (env.pickSourcePaths != null)
          OutlinedButton.icon(
            key: const ValueKey('office-new-from-files'),
            onPressed: c.busy
                ? null
                : () async {
                    final paths = await env.pickSourcePaths!();
                    if (paths.isNotEmpty) await c.openNew(paths);
                  },
            icon: const Icon(Icons.note_add_outlined),
            label: const Text('New from files...'),
          ),
        SizedBox(
          width: 320,
          child: TextField(
            key: const ValueKey('office-google-link'),
            controller: _link,
            decoration: const InputDecoration(isDense: true, hintText: 'Paste a Google Sheets link'),
            onSubmitted: (v) => c.openGoogle(v.trim()),
          ),
        ),
        if (open) ...[
          Text(
            c.working != null ? 'Working file: ${c.view?['label'] ?? ''}' : c.view?['label'] as String? ?? '',
            key: const ValueKey('office-label'),
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
          if (c.view?['engine'] == 'google' && c.view?['open_url'] is String)
            OutlinedButton(
              onPressed: () => env.openExternalLink(Uri.parse(c.view!['open_url'] as String)),
              child: const Text('Open in Google Sheets'),
            ),
        ],
      ],
    );
  }

}
