import 'package:flutter/material.dart';

import '../../widgets/desktop_harness_test.dart';
import 'ask_uri_screen.dart';
import '../../services/file_picker_service.dart';
import '../../services/attachment_opener_service.dart';

class WorkspaceScreen extends StatelessWidget {
  const WorkspaceScreen({super.key, this.filePicker, this.attachmentOpener});
  final FilePickerFn? filePicker;
  final AttachmentOpenerFn? attachmentOpener;
  @override
  Widget build(BuildContext context) {
    final access = HarnessAccess.maybeOf(context);
    if (access == null) {
      return AskUriScreen(
        filePicker: filePicker,
        attachmentOpener: attachmentOpener,
      );
    }
    return DefaultTabController(
      length: 2,
      initialIndex: access.selected == null ? 0 : 1,
      child: Column(
        children: [
          const TabBar(
            tabs: [
              Tab(text: 'Chat'),
              Tab(
                key: ValueKey('workspace-harness-tab'),
                text: 'Harness tasks',
              ),
            ],
          ),
          Expanded(
            child: TabBarView(
              children: [
                AskUriScreen(
                  filePicker: filePicker,
                  attachmentOpener: attachmentOpener,
                ),
                Builder(builder: access.workspaceBuilder),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
