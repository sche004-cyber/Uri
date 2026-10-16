/// URI Office: the contract between the panel and its sheet page, and between the panel and the environment.
///
/// Nothing in this file touches a platform plugin, so widget tests can use it. The WebView2 implementation of
/// [OfficeSurface] lives in `webview_host/webview2_office_surface.dart` and is injected from `main.dart`.
library;

import 'dart:async';

import 'package:flutter/widgets.dart';

/// The sheet page's host: a locked-down web view that shows the page and exchanges JSON messages with it.
abstract class OfficeSurface {
  /// Validated messages from the page (see [parsePageMessage]); anything else has already been dropped.
  Stream<Map<String, dynamic>> get messages;

  /// Loads the page. Throws [OfficeSurfaceError] when the host cannot be locked down or the page is not the
  /// recorded bundle.
  Future<void> start();

  Future<void> post(Map<String, dynamic> message);

  /// The host's lockdown counters and settings (for diagnostics and tests).
  Future<Map<String, dynamic>> securityReport();

  Widget build(BuildContext context);

  Future<void> dispose();
}

class OfficeSurfaceError implements Exception {
  OfficeSurfaceError(this.code, [this.detail = '']);
  final String code;
  final String detail;
  @override
  String toString() => detail.isEmpty ? code : '$code: $detail';
}

/// Everything the Office panel needs from the platform, injected by `main.dart`.
class OfficeEnvironment {
  const OfficeEnvironment({
    required this.surfaceFactory,
    required this.pickWorkbookPath,
    required this.pickSavePath,
    required this.openExternalLink,
    this.pickSourcePaths,
    this.pickDocumentPath,
    this.pickPdfSavePath,
    this.openPrinterSettings,
    this.startService,
    this.pickPresentationSavePath,
    this.pickTemplatePath,
    this.pickImagePath,
    this.pickDocumentSavePath,
    this.pickWordTemplatePath,
  });

  final OfficeSurface Function() surfaceFactory;

  /// File picker for an existing .xlsx; returns its absolute path or null.
  final Future<String?> Function() pickWorkbookPath;

  /// Save dialog for a new .xlsx; returns its absolute path or null.
  final Future<String?> Function(String suggestedName) pickSavePath;

  /// Opens a Google Sheets link in the owner's browser (outside URI).
  final Future<void> Function(Uri url) openExternalLink;

  /// M2: file picker for one or more .xlsx source files; returns their absolute paths (empty when cancelled).
  /// Null where the platform cannot pick several files; "New from files" is then not offered.
  final Future<List<String>> Function()? pickSourcePaths;

  /// O2: file picker for a Word, PowerPoint or PDF file to view (read-only); returns its absolute path or null.
  /// Null where the platform has no picker; the Office workspace then offers workbooks only.
  final Future<String?> Function()? pickDocumentPath;

  /// O2: where to save a new PDF; returns a path that did not exist when chosen, or null. The service checks again
  /// and never replaces a file.
  final Future<String?> Function(String suggestedName)? pickPdfSavePath;

  /// O2P "Connect a printer": opens Windows Settings › Printers & scanners after the owner's explicit click. Windows
  /// does any discovery, driver install or elevation in its own UI; URI installs and changes nothing.
  final Future<void> Function()? openPrinterSettings;

  /// Starts the URI Office service when it is not running (the app starts it on demand, the way it starts the live
  /// voice service). Returns null once the process is started, or a sentence for the owner saying why it cannot be.
  /// Null where the platform cannot start it; the workspace then asks the owner to start URI Office.
  final Future<String?> Function()? startService;

  /// Authoring (A/B): where to save a presentation as a new file; returns a path that did not exist when chosen, or
  /// null. The service checks again and never replaces a file.
  final Future<String?> Function(String suggestedName)? pickPresentationSavePath;

  /// Authoring (OD-A5): the owner's presentation or template (.pptx, .potx) to start a new presentation from.
  final Future<String?> Function()? pickTemplatePath;

  /// Authoring (C): where to save a Word document as a new file; same rules as [pickPresentationSavePath].
  final Future<String?> Function(String suggestedName)? pickDocumentSavePath;

  /// Authoring (C, OD-A5): the owner's Word document or template (.docx, .dotx) to start a new document from.
  final Future<String?> Function()? pickWordTemplatePath;

  /// Authoring (B): a picture to insert (.png, .jpg, .gif, .bmp).
  final Future<String?> Function()? pickImagePath;
}

final RegExp _cellRef = RegExp(r'^[A-Z]{1,3}[1-9][0-9]{0,6}$');

/// The only messages the panel accepts from the page. Everything else is dropped (returns null).
///
/// ```text
///   {"type": "ready"}
///   {"type": "edit", "sheet": <1..31 chars>, "cell": "B3", "value": <string|number|bool|null>}
///   {"type": "edit", "sheet": ..., "cell": ..., "formula": "=..."}
///   {"type": "error", "code": <string>, "detail": <string>?}
/// ```
Map<String, dynamic>? parsePageMessage(Object? raw) {
  if (raw is! Map) return null;
  final type = raw['type'];
  switch (type) {
    case 'ready':
      return raw.length == 1 ? const {'type': 'ready'} : null;
    case 'edit':
      final sheet = raw['sheet'];
      final cell = raw['cell'];
      if (sheet is! String || sheet.isEmpty || sheet.length > 31) return null;
      if (cell is! String || !_cellRef.hasMatch(cell)) return null;
      final keys = raw.keys.toSet();
      if (keys.containsAll({'value', 'formula'})) return null;
      if (keys.contains('formula')) {
        final f = raw['formula'];
        if (f is! String || !f.startsWith('=') || f.length > 8192) return null;
        if (keys.difference({'type', 'sheet', 'cell', 'formula'}).isNotEmpty) return null;
        return {'type': 'edit', 'sheet': sheet, 'cell': cell, 'formula': f};
      }
      if (!keys.contains('value') || keys.difference({'type', 'sheet', 'cell', 'value'}).isNotEmpty) return null;
      final v = raw['value'];
      if (v != null && v is! String && v is! num && v is! bool) return null;
      if (v is String && v.length > 32767) return null;
      return {'type': 'edit', 'sheet': sheet, 'cell': cell, 'value': v};
    case 'error':
      final code = raw['code'];
      if (code is! String || code.length > 64) return null;
      final detail = raw['detail'];
      return {'type': 'error', 'code': code, 'detail': detail is String ? detail.substring(0, detail.length.clamp(0, 200)) : ''};
  }
  return null;
}

/// The open Office workbook as a target for the companion's requests. While the owner works in Office focus with a
/// workbook open, the companion's composer and push-to-talk send requests here instead of to the conversation turn.
/// A request only asks URI to suggest changes: nothing here accepts, rejects or saves anything (those stay buttons).
abstract interface class OfficeRequestTarget implements Listenable {
  /// True while a workbook is open and requests can be taken.
  bool get acceptsRequests;

  /// True while URI is working on the previous request.
  bool get busy;

  /// Asks URI to change the open workbook. The reply and the suggested changes appear in the Office conversation.
  Future<void> instruct(String text, {String? activeSheet});
}

/// O2: a request target that says what the composer should offer (live run 2026-10-15, UX finding: the hint said
/// "change this sheet" on Home, documents and tasks).
abstract interface class OfficeRequestHint {
  String get requestHint;
}

enum OfficeSpeaker { owner, uri, notice }

/// One line of the Office conversation.
class OfficeTurn {
  const OfficeTurn(this.speaker, this.text);
  final OfficeSpeaker speaker;
  final String text;
}

/// What survives leaving the Office region (R1-02, review URI-OFFICE-M1-c2): the open workbook stays open in the
/// Office service with its draft, so accepted but unsaved changes are not lost, and the conversation comes back when
/// the owner returns. Owned by the living scope; the Office region reads and writes it.
class OfficeKeep {
  String? workbookId;
  List<OfficeTurn> conversation = const [];

  void clear() {
    workbookId = null;
    conversation = const [];
  }
}
