/// URI's WebView2 host for the Office sheet page (AC15 layer 1). Imports the vendored, URI-patched
/// `webview_flutter_windows` (uri_ui/packages/webview_flutter_windows, PATCHES.md), so only `main.dart` and the
/// security probe import this file (plugins hang `flutter test`).
///
/// What this host guarantees, together with the native patch:
///   * the page is served only from the virtual host https://office.uri.local, mapped to a page folder whose
///     bundle hash equals [kOfficeBundleSha256]; any other folder is refused;
///   * the native policy allows requests and navigations only to that origin (plus about:blank), refuses new
///     windows, cancels downloads and external-scheme launches, denies permissions, turns developer tools off in
///     release builds and delivers web messages only from that origin;
///   * the WebView2 user-data folder is URI's own (%LOCALAPPDATA%\URI\office\webview2), restricted to the
///     current Windows user and opened for exclusive access, so it is never shared with Edge; password saving and
///     autofill are off;
///   * every message that does arrive is re-validated by [parsePageMessage]; anything else is dropped.
/// This host is qualified for the Office page only. RW1 (general web content) needs its own qualification.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:webview_flutter_windows/webview_flutter_windows.dart';

import '../office/office_bridge.dart';
import '../office/office_page_hash.dart';

const String kOfficeHost = 'office.uri.local';
const String kOfficeOrigin = 'https://office.uri.local';

/// Where the built page is installed. First match wins; each candidate must hold the recorded bundle.
List<String> officePageCandidates() {
  final env = Platform.environment['URI_OFFICE_PAGE_DIR'];
  final exeDir = File(Platform.resolvedExecutable).parent.path;
  return [
    if (env != null && env.isNotEmpty) env,
    '$exeDir\\data\\office_page',
  ];
}

Future<Directory> locateVerifiedOfficePage({List<String>? candidates, String expected = kOfficeBundleSha256}) async {
  for (final p in candidates ?? officePageCandidates()) {
    final d = Directory(p);
    if (!await d.exists() || !await File('${d.path}\\index.html').exists()) continue;
    final h = await officeBundleHash(d);
    if (h != expected) {
      throw OfficeSurfaceError('PAGE_HASH_MISMATCH', 'the Office page at ${d.path} is not the recorded build');
    }
    return d;
  }
  throw OfficeSurfaceError('PAGE_NOT_INSTALLED', 'the Office page is not installed next to URI');
}

/// %LOCALAPPDATA%\URI\office\webview2, created and restricted to the current user (one inheritable
/// full-control entry, inheritance removed). Fails closed when the restriction cannot be applied.
Future<String> prepareUserDataFolder({String? path}) async {
  final local = Platform.environment['LOCALAPPDATA'];
  final dir = Directory(path ?? '$local\\URI\\office\\webview2');
  await dir.create(recursive: true);
  final user = Platform.environment['USERNAME'];
  if (user == null || user.isEmpty) throw OfficeSurfaceError('USER_DATA_ACL', 'no current user');
  final r = await Process.run('icacls', [dir.path, '/inheritance:r', '/grant:r', '$user:(OI)(CI)F']);
  if (r.exitCode != 0) throw OfficeSurfaceError('USER_DATA_ACL', 'could not restrict the WebView2 data folder');
  return dir.path;
}

class WebView2OfficeSurface implements OfficeSurface {
  /// [extraNavigationOrigins] and [pageFolderOverride] exist only for the security probe; the app never sets them.
  WebView2OfficeSurface({
    this.extraNavigationOrigins = const [],
    this.extraVirtualHosts = const {},
    this.pageFolderOverride,
    this.userDataPathOverride,
  });

  final List<String> extraNavigationOrigins;
  final Map<String, String> extraVirtualHosts;   // host -> folder (probe only)
  final String? pageFolderOverride;
  final String? userDataPathOverride;

  static Future<void>? _environment;

  final WebviewController controller = WebviewController();
  final StreamController<Map<String, dynamic>> _messages = StreamController.broadcast();
  StreamSubscription<dynamic>? _sub;
  int droppedByDart = 0;

  @override
  Stream<Map<String, dynamic>> get messages => _messages.stream;

  @override
  Future<void> start() async {
    if (!Platform.isWindows) throw OfficeSurfaceError('NOT_WINDOWS');
    final version = await WebviewController.getWebViewVersion();
    if (version == null) throw OfficeSurfaceError('WEBVIEW2_MISSING', 'the WebView2 runtime is not installed');
    final page = pageFolderOverride != null
        ? Directory(pageFolderOverride!)
        : await locateVerifiedOfficePage();
    _environment ??= () async {
      final userData = await prepareUserDataFolder(path: userDataPathOverride);
      await WebviewController.initializeEnvironment(userDataPath: userData);
    }();
    await _environment;
    await controller.initialize();
    // Policy first: until it is set the native host allows nothing but about:blank.
    await controller.setNetworkPolicy(
      navigationOrigins: [kOfficeOrigin, ...extraNavigationOrigins],
      messageOrigins: const [kOfficeOrigin],
    );
    await controller.setPopupWindowPolicy(WebviewPopupWindowPolicy.deny);
    await controller.addVirtualHostNameMapping(kOfficeHost, page.path, WebviewHostResourceAccessKind.deny);
    for (final e in extraVirtualHosts.entries) {
      await controller.addVirtualHostNameMapping(e.key, e.value, WebviewHostResourceAccessKind.deny);
    }
    _sub = controller.webMessage.listen((raw) {
      final m = parsePageMessage(raw is String ? _tryJson(raw) : raw);
      if (m == null) {
        droppedByDart++;
        return;
      }
      _messages.add(m);
    });
    await controller.loadUrl('$kOfficeOrigin/index.html');
  }

  static Object? _tryJson(String s) {
    try {
      return jsonDecode(s);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> post(Map<String, dynamic> message) => controller.postWebMessage(jsonEncode(message));

  @override
  Future<Map<String, dynamic>> securityReport() async =>
      {...await controller.getSecurityReport(), 'dropped_by_dart': droppedByDart};

  @override
  Widget build(BuildContext context) => Webview(controller);

  @override
  Future<void> dispose() async {
    await _sub?.cancel();
    await _messages.close();
    await controller.dispose();
  }
}

/// The installed WebView2 runtime version, or null when none is installed.
Future<String?> webView2RuntimeVersion() => WebviewController.getWebViewVersion();
