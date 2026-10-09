import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../integration/scheduler_client.dart';
import 'a2ui_contract.dart';
import 'sha256.dart';

/// One rendered A2UI surface: validated components + the local data model.
///
/// Inputs write the local model only (never under `/bound`). Nothing leaves
/// the renderer except an `action` message built by [A2uiHub.act].
class A2uiSurface {
  A2uiSurface(this.id, this.placement);

  final String id;
  String placement;
  List<Map<String, dynamic>> components = const [];
  Map<String, Map<String, dynamic>> byId = const {};
  Map<String, dynamic> data = {};

  bool get ready => byId.containsKey('root');
  String? get digest => _bound('digest') as String?;
  String get title => (_bound('title') as String?) ?? '';
  String get kind => (_bound('kind') as String?) ?? '';
  int get revision => (_bound('revision') as num?)?.toInt() ?? 0;

  Object? _bound(String k) {
    final b = data['bound'];
    final s = b is Map ? b['surface'] : null;
    return s is Map ? s[k] : null;
  }

  /// Value at a JSON pointer; a relative pointer resolves against [scope].
  Object? read(String pointer, {String? scope}) {
    final abs = pointer.startsWith('/') ? pointer : '${scope ?? ''}/$pointer';
    if (abs == '/') return data;
    Object? cur = data;
    for (final raw in abs.substring(1).split('/')) {
      final seg = raw.replaceAll('~1', '/').replaceAll('~0', '~');
      if (cur is Map) {
        cur = cur[seg];
      } else if (cur is List) {
        final i = int.tryParse(seg);
        cur = (i != null && i >= 0 && i < cur.length) ? cur[i] : null;
      } else {
        return null;
      }
    }
    return cur;
  }

  /// Writes an input value. Refuses read-only data (returns false).
  bool write(String pointer, Object? value, {String? scope}) {
    final abs = pointer.startsWith('/') ? pointer : '${scope ?? ''}/$pointer';
    if (a2uiReadOnlyPrefixes.any((p) => abs == p || abs.startsWith('$p/'))) {
      return false;
    }
    final segs = abs.substring(1).split('/');
    Map<String, dynamic> cur = data;
    for (final s in segs.take(segs.length - 1)) {
      final next = cur[s];
      if (next is Map<String, dynamic>) {
        cur = next;
      } else {
        final m = <String, dynamic>{};
        cur[s] = m;
        cur = m;
      }
    }
    cur[segs.last] = value;
    return true;
  }
}

/// Calls the authority for an action and returns its reply
/// (`{"result", "messages"}`); throws with the authority's refusal code.
typedef A2uiAuthorityCall =
    Future<Map<String, dynamic>> Function(Map<String, dynamic> action);

/// The renderer side of URI A2UI: applies validated messages, keeps surfaces,
/// and routes Button actions through a registry of authorized calls.
///
/// * A message batch for a surface is applied only if EVERY message in it is
///   valid; otherwise nothing changes and the refusal is shown ([notices]).
/// * An action name that is not in [registry] is never sent anywhere.
/// * Every action carries `surface_digest`, the version the user saw; the
///   authority refuses a stale one.
class A2uiHub extends ChangeNotifier {
  A2uiHub({this.scheduler, Stream<Map<String, dynamic>>? handoffs}) {
    final s = scheduler;
    if (s != null) {
      for (final name in a2uiActions.keys) {
        if (name.startsWith('scheduler.') ||
            name.startsWith('calendar.') ||
            name == 'surface.dismiss') {
          registry[name] = s.a2uiAction;
        }
      }
    }
    _sub = handoffs?.listen(handoff);
  }

  final SchedulerClient? scheduler;
  final Map<String, A2uiAuthorityCall> registry = {};
  StreamSubscription<Map<String, dynamic>>? _sub;

  final Map<String, A2uiSurface> _surfaces = {};
  final List<String> _order = [];

  /// Owner-visible problems (refused definitions, unavailable authority).
  final List<String> notices = [];

  /// Last refusal per surface (shown under the surface).
  final Map<String, String> errors = {};
  final Set<String> busy = {};

  /// Measured timings (A-AC9), newest last, bounded.
  final List<Map<String, Object>> timings = [];

  List<A2uiSurface> get surfaces => [
    for (final id in _order)
      if (_surfaces[id]?.ready ?? false) _surfaces[id]!,
  ];

  List<A2uiSurface> placed(String placement) =>
      surfaces.where((s) => s.placement == placement).toList();

  A2uiSurface? surface(String id) => _surfaces[id];

  void _notice(String text) {
    notices.add(text);
    if (notices.length > 20) notices.removeAt(0);
  }

  void _time(String what, Stopwatch sw) {
    timings.add({'what': what, 'ms': sw.elapsedMicroseconds / 1000.0});
    if (timings.length > 200) timings.removeAt(0);
  }

  /// Applies server->client messages. Returns the surfaces changed.
  Set<String> apply(List<dynamic> messages) {
    final sw = Stopwatch()..start();
    final batches = <String, List<Map>>{};
    final refused = <String, String>{};
    for (final m in messages) {
      final errs = validateMessage(m, jsonEncode);
      final sid = _sid(m);
      if (errs.isNotEmpty) {
        refused[sid ?? '?'] = errs.first.code;
        continue;
      }
      batches.putIfAbsent(sid!, () => []).add(m as Map);
    }
    for (final e in refused.entries) {
      batches.remove(e.key);
      _notice('URI refused an interface definition (${e.value}); nothing from it is shown.');
    }
    final changed = <String>{};
    for (final e in batches.entries) {
      final staged = _stage(e.key, e.value);
      if (staged == null) continue;
      if (staged.isEmpty) {
        _surfaces.remove(e.key);
        _order.remove(e.key);
        errors.remove(e.key);
      } else {
        _surfaces[e.key] = staged.first;
        if (!_order.contains(e.key)) _order.add(e.key);
        errors.remove(e.key);
      }
      changed.add(e.key);
    }
    _time('apply', sw);
    if (changed.isNotEmpty || refused.isNotEmpty) notifyListeners();
    return changed;
  }

  String? _sid(Object? m) {
    if (m is! Map) return null;
    for (final k in m.keys) {
      if (k != 'version' && m[k] is Map) {
        final s = (m[k] as Map)['surfaceId'];
        if (s is String) return s;
      }
    }
    return null;
  }

  /// Applies one surface's batch to a COPY; null = refused, [] = deleted.
  List<A2uiSurface>? _stage(String sid, List<Map> batch) {
    final cur = _surfaces[sid];
    A2uiSurface? s;
    if (cur != null) {
      s = A2uiSurface(sid, cur.placement)
        ..components = cur.components
        ..byId = cur.byId
        ..data = jsonDecode(jsonEncode(cur.data)) as Map<String, dynamic>;
    }
    for (final m in batch) {
      if (m.containsKey('deleteSurface')) return const [];
      if (m['createSurface'] is Map) {
        final theme = (m['createSurface']['theme'] as Map?) ?? const {};
        s = A2uiSurface(sid, (theme['placement'] as String?) ?? 'inline');
      } else if (s == null) {
        _notice('URI sent an update for an unknown surface; ignored.');
        return null;
      } else if (m['updateComponents'] is Map) {
        final comps = (m['updateComponents']['components'] as List)
            .map((c) => (c as Map).cast<String, dynamic>())
            .toList();
        s.components = comps;
        s.byId = {for (final c in comps) c['id'] as String: c};
      } else if (m['updateDataModel'] is Map) {
        final u = m['updateDataModel'] as Map;
        final path = (u['path'] as String?) ?? '/';
        final value = jsonDecode(jsonEncode(u['value']));
        if (path == '/') {
          s.data = value is Map<String, dynamic> ? value : <String, dynamic>{};
        } else {
          final segs = path.substring(1).split('/');
          Map<String, dynamic> c = s.data;
          for (final seg in segs.take(segs.length - 1)) {
            c = (c[seg] is Map<String, dynamic>) ? c[seg] : (c[seg] = <String, dynamic>{});
          }
          if (u.containsKey('value')) {
            c[segs.last] = value;
          } else {
            c.remove(segs.last);
          }
        }
      }
    }
    return s == null ? null : [s];
  }

  /// Input from a component: local model only.
  void input(String sid, String pointer, Object? value, {String? scope}) {
    final s = _surfaces[sid];
    if (s == null) return;
    if (s.write(pointer, value, scope: scope)) {
      errors.remove(sid);
      notifyListeners();
    }
  }

  /// A Button press: resolve its declared context, add the digest, send it
  /// through the registry, apply the reply.
  Future<void> act(String sid, String componentId, {String? scope}) async {
    final s = _surfaces[sid];
    final comp = s?.byId[componentId];
    if (s == null || comp == null || comp['component'] != 'Button' || busy.contains(sid)) {
      return;
    }
    final ev = (comp['action'] as Map)['event'] as Map;
    final name = ev['name'] as String;
    final call = registry[name];
    if (call == null) {
      errors[sid] = 'This action is not available here ($name).';
      notifyListeners();
      return;
    }
    final schema = a2uiActions[name]!;
    final ctx = <String, dynamic>{'surface_digest': s.digest};
    final declared = (ev['context'] as Map?) ?? const {};
    for (final e in declared.entries) {
      final v = e.value;
      final resolved = isBinding(v) ? s.read((v as Map)['path'] as String, scope: scope) : v;
      if (!a2uiTyped(schema[e.key]!, resolved)) {
        errors[sid] = _humanField(e.key);
        notifyListeners();
        return;
      }
      ctx[e.key as String] = resolved;
    }
    final msg = {
      'name': name,
      'surfaceId': sid,
      'sourceComponentId': componentId,
      'timestamp': DateTime.now().toUtc().toIso8601String(),
      'context': ctx,
    };
    busy.add(sid);
    errors.remove(sid);
    notifyListeners();
    final sw = Stopwatch()..start();
    try {
      final reply = await call(msg);
      _time('action:$name', sw);
      apply((reply['messages'] as List?) ?? const []);
    } on SchedulerApiError catch (e) {
      errors[sid] = _humanRefusal(e.code, e.detail);
      if (e.code == 'STALE_SURFACE' || e.code == 'UNKNOWN_SURFACE') {
        unawaited(refresh());
      }
    } catch (e) {
      errors[sid] = 'URI could not reach the scheduler: $e';
    } finally {
      busy.remove(sid);
      notifyListeners();
    }
  }

  String _humanField(Object key) => switch (key) {
    'selection' => 'Pick at least one festival.',
    'time' => 'Pick a time.',
    'start' => 'Pick a valid date.',
    'instruction' => 'Say what should change.',
    _ => 'Check "$key" before continuing.',
  };

  String _humanRefusal(String code, String? detail) => switch (code) {
    'DRAFT_CHANGED' => 'You changed the choices. Press "Update proposal" first, then confirm the new proposal.',
    'STALE_SURFACE' => 'This view was out of date and has been refreshed. Please check it again.',
    'PROPOSAL_MISMATCH' => 'The proposal changed. Please review it again.',
    'ARTIFACT_VERSION_MISMATCH' || 'ARTIFACT_CHANGED_ON_DISK' =>
      'The GIF is not the version shown. Nothing was decided.',
    'INSTRUCTION_REQUIRED' => 'Say what should change.',
    'DATE_REQUIRED' => 'Pick the corrected date.',
    _ => 'Refused: $code${detail == null || detail.isEmpty ? '' : ' ($detail)'}',
  };

  /// A worker `a2ui.handoff`: ask the domain authority to propose.
  Future<void> handoff(Map<String, dynamic> data) async {
    final s = scheduler;
    if (data['domain'] != 'scheduler' || data['request'] is! Map) return;
    if (s == null) {
      _notice('The scheduler is not running, so the schedule could not be prepared. Start it and ask again.');
      notifyListeners();
      return;
    }
    final sw = Stopwatch()..start();
    try {
      final r = await s.a2uiPropose((data['request'] as Map).cast<String, dynamic>());
      _time('handoff->surface', sw);
      apply((r['messages'] as List?) ?? const []);
    } on SchedulerApiError catch (e) {
      _notice('The scheduler refused the request: ${e.code}.');
      notifyListeners();
    } catch (e) {
      _notice('The scheduler is not reachable ($e). Nothing was scheduled.');
      notifyListeners();
    }
  }

  /// Re-reads every open surface from the authority (after a restart).
  Future<void> refresh() async {
    final s = scheduler;
    if (s == null) return;
    try {
      final r = await s.a2uiSurfaces();
      final msgs = (r['messages'] as List?) ?? const [];
      final live = <String>{for (final m in msgs) ?_sid(m)};
      for (final id in _order.toList()) {
        if (!live.contains(id)) {
          _surfaces.remove(id);
          _order.remove(id);
        }
      }
      apply(msgs);
      notifyListeners();
    } catch (e) {
      _notice('Could not refresh from the scheduler ($e).');
      notifyListeners();
    }
  }

  Future<void> openCalendar() async {
    final s = scheduler;
    if (s == null) {
      _notice('The scheduler is not running.');
      notifyListeners();
      return;
    }
    try {
      apply((await s.a2uiCalendar())['messages'] as List? ?? const []);
    } catch (e) {
      _notice('Could not open the calendar ($e).');
      notifyListeners();
    }
  }

  /// Artifact bytes, shown only if they hash to the bound SHA-256.
  Future<Uint8List> artifact(int id, String sha256) async {
    final s = scheduler;
    if (s == null) throw StateError('NO_SCHEDULER');
    final bytes = await s.artifactBytes(id);
    if (sha256Hex(bytes) != sha256) throw StateError('ARTIFACT_HASH_MISMATCH');
    return bytes;
  }

  void dismissNotice(int i) {
    if (i >= 0 && i < notices.length) {
      notices.removeAt(i);
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}
