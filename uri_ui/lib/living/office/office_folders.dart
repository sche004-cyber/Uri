import 'package:flutter/material.dart';

import '../../theme/uri_theme.dart';
import 'document_controller.dart';
import 'office_bridge.dart';
import 'office_client.dart';

/// OD-R1: the folders URI may open and save files in. The user folder is always allowed; the owner adds other
/// folders (any drive, never a whole drive or a system folder) with the Windows folder dialog and removes them here.
/// The service is the authority: it checks every folder and refuses a removal while a file from it is open.
class OfficeFoldersDialog extends StatefulWidget {
  const OfficeFoldersDialog({super.key, required this.client, this.environment});
  final OfficeClient client;
  final OfficeEnvironment? environment;

  static Future<void> show(BuildContext context, OfficeClient client, OfficeEnvironment? environment) =>
      showDialog<void>(context: context,
          builder: (_) => OfficeFoldersDialog(client: client, environment: environment));

  @override
  State<OfficeFoldersDialog> createState() => _OfficeFoldersDialogState();
}

class _OfficeFoldersDialogState extends State<OfficeFoldersDialog> {
  List<Map<String, dynamic>> _folders = const [];
  String? _message;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _run(() async => widget.client.folders());
  }

  Future<void> _run(Future<Map<String, dynamic>> Function() call, {String? done}) async {
    setState(() {
      _busy = true;
      _message = null;
    });
    try {
      final r = await call();
      final f = r['folders'];
      if (!mounted) return;
      setState(() {
        if (f is List) _folders = [for (final x in f) (x as Map).cast<String, dynamic>()];
        _message = r['already_allowed'] == true ? 'URI can already use that folder.' : done;
      });
    } catch (e) {
      if (mounted) setState(() => _message = officeErrorMessage(e));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _add() async {
    final pick = widget.environment?.pickFolderPath;
    if (pick == null) return;
    final path = await pick();
    if (path == null) return;
    await _run(() => widget.client.addFolder(path), done: 'Added. URI can now open and save files in that folder.');
  }

  @override
  Widget build(BuildContext context) {
    final colors = UriColors.of(context);
    return AlertDialog(
      key: const ValueKey('office-folders'),
      title: const Text('Folders URI may use'),
      content: SizedBox(
        width: 520,
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('URI opens and saves files only inside these folders. Your user folder is always included.',
              style: TextStyle(color: colors.inkSoft)),
          const SizedBox(height: UriSpace.sm),
          for (final f in _folders)
            ListTile(
              key: ValueKey('office-folder-${f['path']}'),
              dense: true,
              leading: Icon(f['kind'] == 'default' ? Icons.home_outlined : Icons.folder_outlined, size: 18),
              title: Text('${f['path']}', overflow: TextOverflow.ellipsis),
              subtitle: f['kind'] == 'default' ? const Text('Always allowed') : null,
              trailing: f['removable'] == true
                  ? TextButton(
                      key: ValueKey('office-folder-remove-${f['path']}'),
                      onPressed: _busy ? null : () => _run(() => widget.client.removeFolder('${f['path']}'),
                          done: 'Removed. URI no longer opens or saves files there.'),
                      child: const Text('Remove'))
                  : null,
            ),
          if (_message != null)
            Padding(
              padding: const EdgeInsets.only(top: UriSpace.sm),
              child: Text(_message!, key: const ValueKey('office-folders-message')),
            ),
        ]),
      ),
      actions: [
        if (widget.environment?.pickFolderPath != null)
          FilledButton.icon(key: const ValueKey('office-folder-add'), onPressed: _busy ? null : _add,
              icon: const Icon(Icons.create_new_folder_outlined, size: 18), label: const Text('Add folder…')),
        TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Close')),
      ],
    );
  }
}
