/// Platform pieces of URI Office (file dialogs that return paths, the WebView2 surface, opening a Google link in
/// the owner's browser). Imported only by main.dart: it pulls in platform plugins.
library;

import 'dart:convert';
import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';

import '../living/office/office_bridge.dart';
import '../living/office/office_client.dart';
import '../living/webview_host/webview2_office_surface.dart';
import 'windows_shell_dialog_module.dart';

OfficeEnvironment platformOfficeEnvironment() {
  keepShellDialogModuleLoaded();        // INT-L2: file dialogs must not unload the shell module under the app
  return _environment();
}

OfficeEnvironment _environment() => OfficeEnvironment(
      surfaceFactory: WebView2OfficeSurface.new,
      pickWorkbookPath: () async {
        final f = await FilePicker.pickFile(
          dialogTitle: 'Open a workbook in URI Office',
          type: FileType.custom,
          allowedExtensions: const ['xlsx'],
        );
        return f?.path;
      },
      // file_picker's save dialog writes the file itself, and the Office service never saves over an existing
      // file. So "Save as" picks a folder and URI forms a new name in it; the service checks it again.
      pickSavePath: (suggested) async {
        final dir = await FilePicker.getDirectoryPath(dialogTitle: 'Save a copy in this folder');
        if (dir == null) return null;
        final base = suggested.replaceAll(RegExp(r'\.xlsx$', caseSensitive: false), '');
        for (var n = 1; n < 100; n++) {
          final name = n == 1 ? '$base (URI).xlsx' : '$base (URI $n).xlsx';
          final path = '$dir${Platform.pathSeparator}$name';
          if (!File(path).existsSync()) return path;
        }
        return null;
      },
      pickSourcePaths: () async {
        final files = await FilePicker.pickFiles(
          dialogTitle: 'Choose one or more Excel files for URI to work from',
          type: FileType.custom,
          allowedExtensions: const ['xlsx'],
        );
        return [for (final f in files) ?f.path];
      },
      pickDocumentPath: () async {
        final f = await FilePicker.pickFile(
          dialogTitle: 'Open a document in URI Office',
          type: FileType.custom,
          allowedExtensions: const ['docx', 'pptx', 'pdf'],
        );
        return f?.path;
      },
      pickFolderPath: () => FilePicker.getDirectoryPath(dialogTitle: 'Allow URI to use this folder'),
      pickPdfSavePath: (suggested) async {
        final dir = await FilePicker.getDirectoryPath(dialogTitle: 'Save the PDF in this folder');
        if (dir == null) return null;
        final base = suggested.replaceAll(RegExp(r'\.(docx|pptx|xlsx|pdf)$', caseSensitive: false), '');
        for (var n = 1; n < 100; n++) {
          final name = n == 1 ? '$base.pdf' : '$base ($n).pdf';
          final path = '$dir${Platform.pathSeparator}$name';
          if (!File(path).existsSync()) return path;
        }
        return null;
      },
      openPrinterSettings: () async {
        await launchUrl(Uri.parse('ms-settings:printers'), mode: LaunchMode.externalApplication);
      },
      startService: startOfficeService,
      openExternalLink: (url) async {
        // Only Google Sheets links reach here (the service builds them from a validated sheet id).
        if (url.scheme == 'https' && url.host == 'docs.google.com' && url.path.startsWith('/spreadsheets/d/')) {
          await launchUrl(url, mode: LaunchMode.externalApplication);
        }
      },
    );

/// Starts the URI Office service for this application (on demand, the first time Office is opened). The interpreter
/// and the URI source folder come from the installation's client manifest (`interpreter`, `source_root`), the same
/// ones the integrated worker uses; URI_OFFICE_PYTHON and URI_OFFICE_SOURCE override them for development runs.
/// Nothing comes from user input. The service binds 127.0.0.1 only, writes a per-launch token, and stops by itself
/// when this application exits (`--parent-pid`).
Future<String?> startOfficeService() async {
  final env = Platform.environment;
  String? python = env['URI_OFFICE_PYTHON'];
  String? source = env['URI_OFFICE_SOURCE'];
  final manifest = env['URI_CLIENT_MANIFEST'];
  if ((python == null || source == null) && manifest != null && manifest.isNotEmpty) {
    try {
      final m = jsonDecode(File(manifest).readAsStringSync()) as Map;
      python ??= m['interpreter'] as String?;
      source ??= m['source_root'] as String?;
    } catch (_) {}
  }
  if (python == null || source == null) {
    return 'URI Office cannot start here: this copy of URI does not say where URI is installed.';
  }
  final script = '$source${Platform.pathSeparator}scripts${Platform.pathSeparator}run_uri_office_service.py';
  if (!File(python).existsSync() || !File(script).existsSync()) {
    return 'URI Office is not installed with this copy of URI.';
  }
  try {
    await Process.start(
      python,
      ['-B', '-I', script, 'run', '--state', OfficeClient.defaultStateDir(), '--parent-pid', '$pid',
        '--brain-from-runtime'],
      workingDirectory: source,
      mode: ProcessStartMode.detached,
    );
  } catch (_) {
    return 'URI Office could not start. Close URI and open it again.';
  }
  return null;
}
