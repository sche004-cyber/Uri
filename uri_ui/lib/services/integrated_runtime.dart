import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

/// Working-system integration (WS blueprint W8, owner decision WS-D1): the
/// integrated client worker (`scripts/run_uri_integrated_worker.py`) seen from
/// the Flutter UI.
///
/// The worker speaks the accepted framed stdio protocol (4-byte big-endian
/// length + JSON). Replies come back in request order. OI turns also stream
/// separate `{"event": ...}` frames (`uri.oi.event.v1`), which are delivered
/// on [events] and never matched against a pending request.
///
/// The UI holds turn ids only. Core envelopes, tickets and credentials stay in
/// the worker. A decision is a structured command that echoes the
/// `approval_digest` the card showed (`oi_decide`). Typed text is only ever
/// sent as `oi_turn` text.
///
/// Explicit opt-in per installation: the client root must hold
/// `control/ui-integrated-profile.json`. No manifest or launcher is changed.
const integratedProfileFile = 'control/ui-integrated-profile.json';
const integratedProfileSchema = 'uri.ws.ui_profile.v1';
const integratedWorkerProfile = 'ws-integrated';
const integratedWorkerEntrypoint = 'scripts/run_uri_integrated_worker.py';

class IntegratedRuntimeException implements Exception {
  IntegratedRuntimeException(this.code);
  final String code;
  @override
  String toString() => code;
}

/// The command surface the living UI uses. Tests provide a fake.
abstract class IntegratedRuntime {
  Stream<Map<String, dynamic>> get events;

  /// Sends one command and returns its `value` (throws
  /// [IntegratedRuntimeException] with the worker's refusal code).
  Future<Map<String, dynamic>> call(Map<String, dynamic> command);

  /// True once the worker process has gone away.
  bool get closed;
  Future<void> close();
}

class WorkerIntegratedRuntime implements IntegratedRuntime {
  WorkerIntegratedRuntime._(this._process);

  final Process _process;
  final _pending = <Completer<Map<String, dynamic>>>[];
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  bool _closed = false;

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;

  @override
  bool get closed => _closed;

  static Map<String, dynamic>? _readJson(String path) {
    try {
      final f = File(path);
      if (!f.existsSync()) return null;
      final v = jsonDecode(f.readAsStringSync());
      return v is Map<String, dynamic> ? v : null;
    } catch (_) {
      return null;
    }
  }

  /// True only for a paired installation that carries the integrated opt-in.
  static bool optInConfigured(String? manifestPath) {
    if (manifestPath == null || manifestPath.isEmpty) return false;
    final m = _readJson(manifestPath);
    final root = m?['client_root'];
    if (root is! String || root.isEmpty) return false;
    final optIn = _readJson('$root${Platform.pathSeparator}${integratedProfileFile.replaceAll('/', Platform.pathSeparator)}');
    return optIn != null &&
        optIn['schema'] == integratedProfileSchema &&
        optIn['worker_profile'] == integratedWorkerProfile;
  }

  /// Spawns the integrated worker named by the manifest's pinned
  /// `source_root`, with the manifest's interpreter and client root, then
  /// checks through `preflight` that it really is the integrated profile.
  static Future<WorkerIntegratedRuntime?> fromManifest(String? manifestPath) async {
    if (!optInConfigured(manifestPath)) return null;
    final m = _readJson(manifestPath!)!;
    final sourceRoot = m['source_root'] as String;
    final entry =
        '$sourceRoot${Platform.pathSeparator}${integratedWorkerEntrypoint.replaceAll('/', Platform.pathSeparator)}';
    final process = await Process.start(
      m['interpreter'] as String,
      ['-B', '-I', entry, '--manifest', manifestPath],
      workingDirectory: m['client_root'] as String,
    );
    final rt = WorkerIntegratedRuntime._(process).._listen();
    try {
      final pre = await rt.call({'command': 'preflight'});
      if (pre['worker_profile'] != integratedWorkerProfile ||
          pre['production_cutover'] != false ||
          pre['event_schema'] != 'uri.oi.event.v1') {
        throw IntegratedRuntimeException('WORKER_PROFILE_MISMATCH');
      }
    } catch (_) {
      await rt.close();
      rethrow;
    }
    return rt;
  }

  void _listen() {
    final buf = BytesBuilder(copy: false);
    var pending = Uint8List(0);
    _process.stdout.listen((chunk) {
      buf.add(pending);
      buf.add(chunk);
      var bytes = buf.takeBytes();
      var offset = 0;
      while (bytes.length - offset >= 4) {
        final size = ByteData.sublistView(bytes, offset, offset + 4).getUint32(0, Endian.big);
        if (bytes.length - offset - 4 < size) break;
        final body = utf8.decode(bytes.sublist(offset + 4, offset + 4 + size));
        offset += 4 + size;
        _dispatch(body);
      }
      pending = Uint8List.fromList(bytes.sublist(offset));
    }, onDone: _onExit);
    _process.stderr.drain<void>();
  }

  void _dispatch(String body) {
    final Map<String, dynamic> frame;
    try {
      frame = jsonDecode(body) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    final ev = frame['event'];
    if (ev is Map<String, dynamic>) {
      if (!_events.isClosed) _events.add(ev);
      return;
    }
    if (_pending.isNotEmpty) _pending.removeAt(0).complete(frame);
  }

  void _onExit() {
    _closed = true;
    for (final w in _pending) {
      w.completeError(IntegratedRuntimeException('WORKER_EXITED'));
    }
    _pending.clear();
    if (!_events.isClosed) {
      _events.add({'type': 'worker.exited', 'turn_id': null, 'data': const {}});
      _events.close();
    }
  }

  Future<Map<String, dynamic>> _raw(Map<String, dynamic> command, Duration timeout) {
    if (_closed) return Future.error(IntegratedRuntimeException('WORKER_CLOSED'));
    final c = Completer<Map<String, dynamic>>();
    _pending.add(c);
    final payload = utf8.encode(jsonEncode(command));
    final header = ByteData(4)..setUint32(0, payload.length, Endian.big);
    _process.stdin.add(header.buffer.asUint8List());
    _process.stdin.add(payload);
    return c.future.timeout(timeout, onTimeout: () => throw IntegratedRuntimeException('WORKER_TIMEOUT'));
  }

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    final reply = await _raw(command, const Duration(minutes: 2));
    if (reply['result'] != 'OK') {
      throw IntegratedRuntimeException((reply['code'] as String?) ?? 'CLIENT_COMMAND_REFUSED');
    }
    final v = reply['value'];
    return v is Map<String, dynamic> ? v : <String, dynamic>{};
  }

  @override
  Future<void> close() async {
    if (_closed) return;
    try {
      await _raw({'command': 'close'}, const Duration(seconds: 60));
    } catch (_) {}
    _closed = true;
    try {
      await _process.stdin.close();
    } catch (_) {}
    await _process.exitCode.timeout(const Duration(seconds: 30), onTimeout: () {
      _process.kill();
      return -1;
    });
  }
}
