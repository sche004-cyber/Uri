/// Keeps the Windows file-dialog module loaded for the life of the app (integration live runs i2 and i3, finding
/// INT-L2).
///
/// The file picker plugin shows each Windows dialog on a short-lived worker thread that initialises and then
/// uninitialises COM. When that thread ends, Windows may unload the dialog module (ExplorerFrame.dll) while a shell
/// background task started by the dialog still runs code from it, and the app stops with an access violation in
/// "explorerframe.dll_unloaded" (Windows Application log, event 1000) shortly after a dialog closes. Loading the module
/// once here holds one more reference that is never released (`DynamicLibrary.open` does not free the library), so the
/// module stays mapped and that code can finish. Nothing else changes: the dialogs, their filters and their results
/// are the plugin's own.
library;

import 'dart:ffi';
import 'dart:io';

bool _held = false;

/// Loads ExplorerFrame.dll once and keeps it loaded. Returns true when the module is held (Windows only).
bool keepShellDialogModuleLoaded() {
  if (_held) return true;
  if (!Platform.isWindows) return false;
  try {
    DynamicLibrary.open('ExplorerFrame.dll');
    _held = true;
  } on ArgumentError {
    _held = false;                     // not present on this Windows: the dialogs behave as before
  }
  return _held;
}
