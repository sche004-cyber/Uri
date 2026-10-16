// INT-L2 (integration live runs i2, i3): the Windows file-dialog module is loaded once and kept loaded.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/services/windows_shell_dialog_module.dart';

void main() {
  test('the shell dialog module is held on Windows, and asking again keeps one hold', () {
    expect(keepShellDialogModuleLoaded(), Platform.isWindows);
    expect(keepShellDialogModuleLoaded(), Platform.isWindows);
  });
}
