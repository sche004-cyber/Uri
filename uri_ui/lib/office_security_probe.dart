/// URI Office WebView2 security probe (AC15 layer 1; item 6 of the OFF-O6 approval). A separate entry point:
///
/// ```text
///   flutter build windows --release -t lib/office_security_probe.dart
///   URI_OFFICE_PAGE_DIR=<built page> URI_OFFICE_PROBE_OUT=<out.json> <build>\uri_ui.exe
/// ```
///
/// Runs unattended in the real WebView2 runtime through URI's patched host, writes JSON and exits. It needs no
/// sign-in, microphone, camera or permission prompt (the host denies permissions without a prompt).
///
/// Layout, all local:
///   * https://office.uri.local  the real Office page (CSP + page patch + host): all three layers;
///   * https://probe.uri.local   a raw page with NO CSP and NO page patch, served in-process like the Office page
///                               and allowed for navigation ONLY in this probe: the host layer alone;
///   * 127.0.0.1 canary (TCP)    records any HTTP or WebSocket request that escapes;
///   * 127.0.0.1 canary (UDP)    records any datagram (WebRTC/STUN) that escapes;
///   * 127.0.0.1 redirect server allowed for navigation ONLY in this probe, to exercise redirects.
/// Messages are accepted only from https://office.uri.local, as in the app.
library;

import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';

import 'living/webview_host/webview2_office_surface.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const MaterialApp(home: _Probe()));
}

class _Probe extends StatefulWidget {
  const _Probe();
  @override
  State<_Probe> createState() => _ProbeState();
}

class _ProbeState extends State<_Probe> {
  WebView2OfficeSurface? surface;
  String status = 'starting';

  @override
  void initState() {
    super.initState();
    unawaited(_run());
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Column(children: [
          Text('URI Office security probe: $status'),
          Expanded(child: surface == null ? const SizedBox() : surface!.build(context)),
        ]),
      );

  Future<void> _run() async {
    final out = Platform.environment['URI_OFFICE_PROBE_OUT'] ?? 'office_security_probe.json';
    final report = <String, dynamic>{'started': DateTime.now().toUtc().toIso8601String()};
    try {
      await _probe(report);
      report['result'] = 'COMPLETED_WITH_RESULT';
    } catch (e, st) {
      report['result'] = 'FAILED';
      report['error'] = '$e';
      report['stack'] = '$st'.split('\n').take(8).join('\n');
    }
    report['finished'] = DateTime.now().toUtc().toIso8601String();
    File(out).writeAsStringSync(const JsonEncoder.withIndent('  ').convert(report));
    exit(0);
  }

  Future<void> _probe(Map<String, dynamic> report) async {
    final hits = <String>[];
    final canary = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    canary.listen((req) async {
      hits.add('${req.method} ${req.uri}${WebSocketTransformer.isUpgradeRequest(req) ? ' (websocket)' : ''}');
      if (req.uri.path == '/download') {
        req.response.headers.set('Content-Disposition', 'attachment; filename="uri-probe-canary.txt"');
      }
      req.response.write('canary');
      await req.response.close();
    });
    final c = 'http://127.0.0.1:${canary.port}';
    // UDP canary on all interfaces, so STUN to this PC's LAN address (a non-loopback route) is caught too.
    final udp = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
    String? lan;
    for (final ni in await NetworkInterface.list(type: InternetAddressType.IPv4)) {
      for (final a in ni.addresses) {
        if (!a.isLoopback && !a.isLinkLocal) lan ??= a.address;
      }
    }
    report['lan_address_used'] = lan;
    udp.listen((e) {
      if (e == RawSocketEvent.read) {
        final d = udp.receive();
        if (d != null) hits.add('UDP ${d.data.length} bytes');
      }
    });

    final redirect = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    final redirectOrigin = 'http://127.0.0.1:${redirect.port}';
    redirect.listen((req) async {
      hits.add('REDIRECT-SERVER ${req.uri}');
      req.response.statusCode = 302;
      req.response.headers.set('Location', req.uri.path == '/to-file' ? 'file:///C:/Windows/win.ini' : '$c/redirected');
      await req.response.close();
    });

    final rawDir = await Directory.systemTemp.createTemp('uri-office-probe-page');
    File('${rawDir.path}\\raw.html').writeAsStringSync(
        '<!doctype html><html><body>raw probe page: no CSP, no page patch</body></html>');
    final userData = '${Directory.systemTemp.path}\\uri-office-probe-${DateTime.now().millisecondsSinceEpoch}';

    final pageDir = Platform.environment['URI_OFFICE_PAGE_DIR'];
    if (pageDir != null && pageDir.isNotEmpty) {
      report['page_dir'] = (await locateVerifiedOfficePage(candidates: [pageDir])).path;
    }
    final s = WebView2OfficeSurface(
      extraNavigationOrigins: ['https://probe.uri.local', redirectOrigin],
      extraVirtualHosts: {'probe.uri.local': rawDir.path},
      userDataPathOverride: userData,
    );
    final received = <Map<String, dynamic>>[];
    setState(() {
      surface = s;
      status = 'running';
    });
    final ctl = s.controller;
    await s.start();
    s.messages.listen(received.add);
    await Future<void>.delayed(const Duration(seconds: 5));

    Future<String> js(String expr) async {
      try {
        return '${await ctl.executeScript(expr)}';
      } catch (e) {
        return 'error: $e';
      }
    }

    // Promise-valued attempts: store the settled value, then read it.
    Future<String> jsAwait(String promiseExpr, {int ms = 1500}) async {
      await js("window.__r = 'pending'; Promise.resolve().then(() => $promiseExpr).then(v => { window.__r = String(v); }, e => { window.__r = 'rejected ' + (e && e.name) + ' ' + (e && e.message); }); 'started'");
      await Future<void>.delayed(Duration(milliseconds: ms));
      return js('window.__r');
    }

    Future<Map<String, dynamic>> attempt(String name, String promiseExpr, {int ms = 1500}) async {
      final before = hits.length;
      final r = await jsAwait(promiseExpr, ms: ms);
      final got = hits.sublist(before);
      return {'name': name, 'page_result': r, 'canary_hits': got, 'blocked': got.isEmpty};
    }

    report['webview2_version'] = await webView2RuntimeVersion();

    // ---- 1. Office page: all layers ----------------------------------------------------------------------------
    final office = <String, dynamic>{
      'location': await js('location.href'),
      'ready_received': received.any((m) => m['type'] == 'ready'),
      'rtc_peer_connection': await js('typeof window.RTCPeerConnection'),
      'host_object_use': await jsAwait(
          "(async () => { try { const o = await chrome.webview.hostObjects.uri; return 'got ' + typeof o; } catch (e) { return 'refused ' + e.message; } })()"),
    };
    office['attempts'] = [for (final a in _attacks(c, udp.port, lan)) await attempt(a.$1, a.$2, ms: a.$1.startsWith('webrtc') ? 4000 : 1500)];
    final beforeMsgs = received.length;
    await js("chrome.webview.postMessage({type:'evil', cmd:'save'}); chrome.webview.postMessage({type:'edit', sheet:'S', cell:'1A', value:1}); chrome.webview.postMessage('not an object'); 'sent'");
    await Future<void>.delayed(const Duration(seconds: 1));
    office['bridge_misuse_delivered_to_panel'] = received.length - beforeMsgs;
    report['office_page'] = office;

    // ---- 2. Raw page (host layer alone) -------------------------------------------------------------------------
    await ctl.loadUrl('https://probe.uri.local/raw.html');
    await Future<void>.delayed(const Duration(seconds: 3));
    final raw = <String, dynamic>{
      'location': await js('location.href'),
      'host_object_use': await jsAwait(
          "(async () => { try { const o = await chrome.webview.hostObjects.uri; return 'got ' + typeof o; } catch (e) { return 'refused ' + e.message; } })()"),
    };
    raw['attempts'] = [
      for (final a in _attacks(c, udp.port, lan)) await attempt(a.$1, a.$2, ms: a.$1.startsWith('webrtc') ? 4000 : 1500),
      await attempt('data_url_image_works',
          "new Promise(r => { const i = new Image(); i.onload = () => r('loaded'); i.onerror = () => r('error'); i.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=='; })"),
      await attempt('blob_fetch_works', "fetch(URL.createObjectURL(new Blob(['ok']))).then(r => r.text())"),
      await attempt('permission_geolocation',
          "new Promise(r => navigator.geolocation.getCurrentPosition(() => r('granted'), e => r('denied code ' + e.code)))", ms: 2500),
      await attempt('permission_notifications', 'Notification.requestPermission()'),
      await attempt('permission_camera', "navigator.mediaDevices.getUserMedia({video: true}).then(() => 'granted')", ms: 2500),
      await attempt('clipboard_read', "navigator.clipboard.readText().then(() => 'read')"),
    ];
    final beforeWrong = received.length;
    await js("chrome.webview.postMessage({type:'ready'}); chrome.webview.postMessage({type:'edit', sheet:'Sales', cell:'B2', value:999}); 'sent'");
    await Future<void>.delayed(const Duration(seconds: 1));
    raw['wrong_origin_messages_delivered_to_panel'] = received.length - beforeWrong;
    report['raw_page'] = raw;

    // ---- 3. Top-level navigations -------------------------------------------------------------------------------
    final navs = <Map<String, dynamic>>[];
    for (final n in <(String, String)>[
      ('nav_canary', '$c/nav'),
      ('nav_file', 'file:///C:/Windows/win.ini'),
      ('nav_data_html', 'data:text/html,<b>x</b>'),
      ('nav_blob_like', 'blob:https://probe.uri.local/00000000-0000-0000-0000-000000000000'),
      ('nav_custom_scheme', 'uri-office-probe:test'),
      ('nav_redirect_to_canary', '$redirectOrigin/to-canary'),
      ('nav_redirect_to_file', '$redirectOrigin/to-file'),
      ('nav_download', '$c/download'),
    ]) {
      final before = hits.length;
      await ctl.loadUrl(n.$2);
      await Future<void>.delayed(const Duration(seconds: 2));
      final loc = await js('location.href');
      navs.add({'name': n.$1, 'target': n.$2, 'location_after': loc, 'hits': hits.sublist(before),
        'escaped_to_canary': hits.sublist(before).any((h) => !h.startsWith('REDIRECT-SERVER')),
        'target_loaded': loc.startsWith(n.$2)});
      await ctl.loadUrl('https://probe.uri.local/raw.html');
      await Future<void>.delayed(const Duration(seconds: 2));
    }
    final before = hits.length;
    await js("location.href = '$c/script-nav'; 'sent'");
    await Future<void>.delayed(const Duration(seconds: 2));
    navs.add({'name': 'nav_from_script', 'hits': hits.sublist(before), 'escaped_to_canary': hits.length != before,
      'location_after': await js('location.href')});
    report['navigations'] = navs;

    // ---- 4. Developer tools, downloads, host report -----------------------------------------------------------
    try {
      await ctl.openDevTools();
      report['open_dev_tools'] = 'call returned normally';
    } catch (e) {
      report['open_dev_tools'] = 'refused: $e';
    }
    final downloads = '${Platform.environment['USERPROFILE']}\\Downloads';
    report['downloads_written'] = [
      for (final n in ['uri-probe-canary.txt', 'uri-probe-blob.txt'])
        if (File('$downloads\\$n').existsSync()) n,
    ];
    report['security_report'] = await s.securityReport();
    report['all_hits'] = hits;
    report['user_data_folder'] = userData;
    final acl = await Process.run('icacls', [userData]);
    report['user_data_folder_acl'] = '${acl.stdout}'.trim();
    await canary.close(force: true);
    await redirect.close(force: true);
    udp.close();
  }

  static String _rtc(String target, {bool viaBlankFrame = false}) =>
      "(async () => { const w = ${viaBlankFrame ? "(() => { const f = document.createElement('iframe'); document.body.appendChild(f); return f.contentWindow; })()" : 'window'}; "
      "if (!w || !w.RTCPeerConnection) return 'no RTCPeerConnection'; const pc = new w.RTCPeerConnection({iceServers: [{urls: 'stun:$target'}]}); "
      "pc.createDataChannel('x'); await pc.setLocalDescription(await pc.createOffer()); setTimeout(() => pc.close(), 2500); return 'gathering'; })()";

  static List<(String, String)> _attacks(String c, int udpPort, String? lan) => [
        ('fetch', "fetch('$c/fetch').then(() => 'SENT')"),
        ('fetch_loopback_service_port', "fetch('http://127.0.0.1:18530/status').then(r => 'SENT ' + r.status)"),
        ('xhr', "new Promise((res) => { try { const x = new XMLHttpRequest(); x.onload = () => res('loaded'); x.onerror = () => res('error'); x.open('GET', '$c/xhr'); x.send(); } catch (e) { res('refused ' + e.name); } })"),
        ('websocket', "new Promise((res) => { try { const w = new WebSocket('${c.replaceFirst('http', 'ws')}/ws'); w.onopen = () => res('open'); w.onerror = () => res('error'); } catch (e) { res('refused ' + e.name); } })"),
        ('eventsource', "new Promise((res) => { try { const s = new EventSource('$c/sse'); s.onerror = () => res('error'); s.onopen = () => res('open'); } catch (e) { res('refused ' + e.name); } })"),
        ('sendbeacon', "String(navigator.sendBeacon && navigator.sendBeacon('$c/beacon', 'x'))"),
        ('image', "new Promise(r => { const i = new Image(); i.onload = () => r('loaded'); i.onerror = () => r('error'); i.src = '$c/img'; })"),
        ('css_url', "(() => { const s = document.createElement('style'); s.textContent = 'body{background-image:url($c/css)}'; document.head.appendChild(s); return 'attempted'; })()"),
        ('prefetch', "(() => { const l = document.createElement('link'); l.rel = 'prefetch'; l.href = '$c/prefetch'; document.head.appendChild(l); return 'attempted'; })()"),
        ('iframe_canary', "(() => { const f = document.createElement('iframe'); f.src = '$c/iframe'; document.body.appendChild(f); return 'attempted'; })()"),
        ('iframe_file', "(() => { const f = document.createElement('iframe'); f.src = 'file:///C:/Windows/win.ini'; document.body.appendChild(f); return 'attempted'; })()"),
        ('iframe_custom_scheme', "(() => { const f = document.createElement('iframe'); f.src = 'uri-office-probe:frame'; document.body.appendChild(f); return 'attempted'; })()"),
        ('iframe_data_html', "(() => { const f = document.createElement('iframe'); f.src = 'data:text/html,<script>fetch(\"$c/from-data-frame\")</script>'; document.body.appendChild(f); return 'attempted'; })()"),
        ('window_open', "String(window.open('$c/open'))"),
        ('worker_fetch', "(() => { try { new Worker(URL.createObjectURL(new Blob([\"fetch('$c/worker')\"], {type: 'text/javascript'}))); return 'worker started'; } catch (e) { return 'refused ' + e.name; } })()"),
        ('webrtc_stun_loopback', _rtc('127.0.0.1:$udpPort')),
        if (lan != null) ('webrtc_stun_lan', _rtc('$lan:$udpPort')),
        ('webrtc_via_blank_iframe', _rtc('127.0.0.1:$udpPort', viaBlankFrame: true)),
        ('webtransport_quic', "(async () => { if (!window.WebTransport) return 'no WebTransport'; try { const t = new WebTransport('https://127.0.0.1:$udpPort/wt'); await t.ready; return 'connected'; } catch (e) { return 'refused ' + e.name; } })()"),
        ('download_anchor', "(() => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob(['x'])); a.download = 'uri-probe-blob.txt'; document.body.appendChild(a); a.click(); return 'clicked'; })()"),
        ('fetch_file', "fetch('file:///C:/Windows/win.ini').then(r => 'READ ' + r.status)"),
      ];
}
