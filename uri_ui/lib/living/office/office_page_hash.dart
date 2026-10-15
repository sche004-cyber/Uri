/// The recorded hash of the built Office page (AC18). Must equal `uri_ui/office_web/BUNDLE_SHA256`; a test checks
/// that. The panel refuses to load a page folder whose hash differs, so a modified page on disk is never shown.
library;

import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import '../a2ui/sha256.dart';

const String kOfficeBundleSha256 = 'abf10165e82f17131f94fffcd6de61f1261672050b2e905cd1334de1182ecb65';

/// Same algorithm as `uri_office.page_build.bundle_hash`: SHA-256 over the compact JSON list of
/// [relative posix path, SHA-256 of file] for every file, sorted by path.
Future<String> officeBundleHash(Directory dir) async {
  final files = <File>[
    await for (final e in dir.list(recursive: true, followLinks: false))
      if (e is File) e,
  ];
  final rows = <List<String>>[];
  for (final f in files) {
    final rel = f.path.substring(dir.path.length + 1).replaceAll('\\', '/');
    rows.add([rel, sha256Hex(await f.readAsBytes())]);
  }
  rows.sort((a, b) => a[0].compareTo(b[0]));
  return sha256Hex(Uint8List.fromList(utf8.encode(jsonEncode(rows))));
}
