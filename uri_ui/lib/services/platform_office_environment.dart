/// Platform pieces of URI Office (file dialogs that return paths, the WebView2 surface, opening a Google link in
/// the owner's browser). Imported only by main.dart: it pulls in platform plugins.
library;

import 'dart:io';

import 'package:file_picker/file_picker.dart';
import 'package:url_launcher/url_launcher.dart';

import '../living/office/office_bridge.dart';
import '../living/webview_host/webview2_office_surface.dart';

OfficeEnvironment platformOfficeEnvironment() => OfficeEnvironment(
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
      openExternalLink: (url) async {
        // Only Google Sheets links reach here (the service builds them from a validated sheet id).
        if (url.scheme == 'https' && url.host == 'docs.google.com' && url.path.startsWith('/spreadsheets/d/')) {
          await launchUrl(url, mode: LaunchMode.externalApplication);
        }
      },
    );
