import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../services/integrated_runtime.dart';
import '../a2ui/a2ui_hub.dart';

/// UI mirror of URI Assist (docs/assist/A0_UI_INTERACTION_SPEC.md).
///
/// The worker (`uri_assist.access`) is the only authority: this controller
/// never decides a permission, never keeps a grant across a restart and never
/// captures anything itself. Every state shown comes from the worker's last
/// reply; a refusal is shown with its code, never hidden.
class AssistController extends ChangeNotifier {
  AssistController({
    required this.runtime,
    Stream<Map<String, dynamic>>? events,
    Listenable? workerChanges,
    this.pollEvery = const Duration(seconds: 2),
  }) {
    _sub = events?.listen(_onEvent);
    // A restarted worker starts with Assist OFF: drop the old grant as soon as
    // the runtime is replaced, not only at the next command (interim review).
    _workerChanges = workerChanges?..addListener(_checkWorker);
    // Research results render through the existing A2UI renderer; its Dart
    // contract validates every message again. "Close" is presentation only.
    results.registry['surface.dismiss'] = (msg) async => {
      'messages': [
        {
          'version': 'v0.9',
          'deleteSurface': {'surfaceId': msg['surfaceId']},
        },
      ],
    };
  }

  /// Research result surfaces (placement `workspace`).
  final A2uiHub results = A2uiHub();

  /// The current worker (null when none is connected).
  final IntegratedRuntime? Function() runtime;
  final Duration pollEvery;
  Listenable? _workerChanges;
  Timer? _poll;

  /// Events whose job/ask id is not known yet (they can race the reply that
  /// carries the id); bounded (interim review F1).
  final Map<String, List<Map<String, dynamic>>> _early = {};

  /// The running Ask URI request (answers arrive as `assist.answer`).
  String? askId;
  bool get asking => askId != null && answer == null;
  IntegratedRuntime? _lastRuntime;
  StreamSubscription<Map<String, dynamic>>? _sub;

  /// Last `assist_status` reply (state, scope, permissions, adapters, vision).
  Map<String, dynamic> status = const {'state': 'OFF'};

  /// When [status] was last set (microseconds since epoch; 0 = never), so a
  /// view can tell which of two readings of the same worker state is newer.
  int statusAt = 0;
  bool loaded = false;
  bool busy = false;

  /// Last refusal or failure code (shown, never hidden).
  String? lastError;

  /// Targets listed for the kind being chosen (read once, on request).
  String? choosingKind;
  List<Map<String, dynamic>> targets = const [];

  List<Map<String, dynamic>> findings = const [];
  Map<String, dynamic>? lastObservation;
  String? answer;

  /// Bumped by every grant, pause, resume, Stop and worker change: a reply to
  /// a check or ask sent before one of those is dropped, never shown (R9-05).
  int _epoch = 0;

  /// Everything derived from an observation is discarded together.
  void _discardDerived() {
    _epoch++;
    findings = const [];
    lastObservation = null;
    answer = null;
    askId = null;
  }

  /// Research (W1) through the same worker.
  String? researchJobId;
  String? researchStage;
  String? researchStatus;
  List<dynamic>? researchA2ui;
  List<Map<String, dynamic>> providers = const [];

  bool get available => runtime() != null;
  String get state => status['state'] as String? ?? 'OFF';
  bool get active => state == 'ACTIVE';
  bool get paused => state == 'PAUSED';
  bool get off => state == 'OFF';
  Map<String, dynamic>? get scope => (status['scope'] as Map?)?.cast<String, dynamic>();
  Map<String, bool> get permissions =>
      ((status['permissions'] as Map?) ?? const {}).map((k, v) => MapEntry('$k', v == true));
  List<Map<String, dynamic>> get adapters =>
      [for (final a in (status['adapters'] as List? ?? const [])) (a as Map).cast<String, dynamic>()];
  bool get researching => researchJobId != null && researchStatus == null;

  Future<Map<String, dynamic>?> _call(Map<String, dynamic> command, {bool updatesStatus = false}) async {
    final rt = runtime();
    if (rt == null) {
      lastError = 'WORKER_NOT_CONNECTED';
      status = const {'state': 'OFF'};
      statusAt = DateTime.now().microsecondsSinceEpoch;
      notifyListeners();
      return null;
    }
    if (_lastRuntime != null && !identical(rt, _lastRuntime)) _resetForNewWorker();
    _lastRuntime = rt;
    busy = true;
    notifyListeners();
    try {
      final v = await rt.call(command);
      lastError = null;
      if (updatesStatus) {
        status = v;
        statusAt = DateTime.now().microsecondsSinceEpoch;
        loaded = true;
      }
      return v;
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      return null;
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  void _resetForNewWorker() {
    // A restarted worker starts with Assist OFF; never show the old grant.
    status = const {'state': 'OFF'};
    statusAt = DateTime.now().microsecondsSinceEpoch;
    _discardDerived();
    researchJobId = null;
    _poll?.cancel();
  }

  void _checkWorker() {
    final rt = runtime();
    if (_lastRuntime != null && !identical(rt, _lastRuntime)) {
      _resetForNewWorker();
      _lastRuntime = rt;
      notifyListeners();
    }
  }

  Future<void> refresh() => _call({'command': 'assist_status'}, updatesStatus: true);

  Future<void> listTargets(String kind) async {
    choosingKind = kind;
    targets = const [];
    final v = await _call({'command': 'assist_targets', 'kind': kind});
    targets = [for (final t in (v?['targets'] as List? ?? const [])) (t as Map).cast<String, dynamic>()];
    notifyListeners();
  }

  void cancelChoosing() {
    choosingKind = null;
    targets = const [];
    notifyListeners();
  }

  Future<void> grant(String kind, String targetId, {required bool suggest, bool confirmScreen = false}) async {
    // A new grant discards any earlier ask, findings and observation (the worker drops answers from another grant).
    _discardDerived();
    await _call({
      'command': 'assist_grant',
      'kind': kind,
      'target_id': targetId,
      'permissions': ['observe', if (suggest) 'suggest'],
      'confirm_screen': confirmScreen,
    }, updatesStatus: true);
    if (lastError == null) cancelChoosing();
  }

  // Pause and resume end the observation generation on the worker: nothing derived before survives (R9-05).
  Future<void> pause() {
    _discardDerived();
    return _call({'command': 'assist_pause'}, updatesStatus: true);
  }

  Future<void> resume() {
    _discardDerived();
    return _call({'command': 'assist_resume'}, updatesStatus: true);
  }

  /// Stop: one tap, no confirmation; everything derived is discarded.
  Future<void> revoke() async {
    _discardDerived();          // Stop cancels the ask; otherwise `asking` stays true and Ask stays disabled (R1-03)
    await _call({'command': 'assist_revoke'}, updatesStatus: true);
  }

  Future<void> check() async {
    final epoch = _epoch;
    final v = await _call({'command': 'assist_check'});
    if (v == null || epoch != _epoch) return;   // Stop, pause or a new grant meanwhile: drop the reply
    findings = [for (final f in (v['findings'] as List? ?? const [])) (f as Map).cast<String, dynamic>()];
    lastObservation = (v['observation'] as Map?)?.cast<String, dynamic>();
    notifyListeners();
  }

  /// Starts an answer; it arrives as an `assist.answer` event (or by polling).
  Future<void> ask(String question, {bool useScreenshot = false}) async {
    answer = null;
    askId = null;
    final epoch = _epoch;
    final v = await _call({'command': 'assist_ask', 'question': question, 'use_screenshot': useScreenshot});
    if (v == null || epoch != _epoch) return;   // Stop, pause or a new grant meanwhile: drop the reply
    askId = v['ask_id'] as String?;
    lastObservation = (v['observation'] as Map?)?.cast<String, dynamic>();
    _drainEarly(askId);
    _startPoll();
    notifyListeners();
  }

  Future<void> loadProviders() async {
    final v = await _call({'command': 'web_providers'});
    providers = [for (final p in (v?['providers'] as List? ?? const [])) (p as Map).cast<String, dynamic>()];
    notifyListeners();
  }

  Future<void> research(String query, {List<String> urls = const []}) async {
    researchJobId = null;
    researchStatus = null;
    researchStage = null;
    researchA2ui = null;
    final v = await _call({'command': 'web_research', 'query': query, 'urls': urls, 'feeds': <String>[], 'use_brain': true});
    researchJobId = v?['job_id'] as String?;
    if (researchJobId != null) researchStage = 'queued';
    _drainEarly(researchJobId);
    _startPoll();
    notifyListeners();
  }

  Future<void> cancelResearch() async {
    final id = researchJobId;
    if (id == null) return;
    await _call({'command': 'web_research_cancel', 'job_id': id});
  }

  void _drainEarly(String? id) {
    if (id == null) return;
    for (final ev in _early.remove(id) ?? const <Map<String, dynamic>>[]) {
      _onEvent(ev);
    }
  }

  /// Fallback when an event is lost: ask the worker for the job's state.
  void _startPoll() {
    _poll?.cancel();
    _poll = Timer.periodic(pollEvery, (_) => _pollOnce());
  }

  Future<void> _pollOnce() async {
    final rt = runtime();
    if (rt == null || (!researching && !asking)) {
      _poll?.cancel();
      return;
    }
    try {
      // A reply is applied only to the job it was asked about and only if no grant, pause, resume, Stop or
      // worker change happened while it was in flight (R41-01, R9-05).
      if (researching) {
        final id = researchJobId, epoch = _epoch;
        final v = await rt.call({'command': 'web_research_status', 'job_id': id});
        if (v['state'] == 'FINISHED' && id == researchJobId && epoch == _epoch) {
          final r = (v['result'] as Map?)?.cast<String, dynamic>() ?? const {};
          _finishResearch(r['status'] as String? ?? 'FAILED', v['a2ui'] as List?);
        }
      }
      if (asking) {
        final id = askId, epoch = _epoch;
        final v = await rt.call({'command': 'assist_ask_status', 'ask_id': id});
        if (v['state'] == 'FINISHED' && id == askId && epoch == _epoch) _finishAnswer(v);
      }
    } on IntegratedRuntimeException catch (_) {
      // Unknown job (worker restarted): stop polling; the reset path shows OFF.
      _poll?.cancel();
    }
  }

  void _finishResearch(String status, List<dynamic>? a2ui) {
    if (researchStatus != null) return;
    researchStatus = status;
    researchStage = 'finished';
    researchA2ui = a2ui;
    if (a2ui != null) results.apply(a2ui);
    _stopPollIfIdle();
    notifyListeners();
  }

  void _stopPollIfIdle() {
    if (!researching && !asking) _poll?.cancel();
  }

  void _finishAnswer(Map<String, dynamic> data) {
    if (answer != null) return;
    final st = data['status'] as String? ?? 'FAILED';
    answer = st == 'COMPLETE' ? (data['answer'] as String? ?? '') : '';
    if (st != 'COMPLETE') lastError = st == 'CANCELLED' ? 'ANSWER_CANCELLED' : 'ANSWER_$st';
    _stopPollIfIdle();
    notifyListeners();
  }

  void _onEvent(Map<String, dynamic> ev) {
    final id = ev['turn_id'] as String?;
    if (id == null) return;
    if (id != researchJobId && id != askId) {
      // Possibly ahead of the reply that names it: keep a few, briefly.
      final q = _early.putIfAbsent(id, () => []);
      if (q.length < 200) q.add(ev);
      while (_early.length > 8) {
        _early.remove(_early.keys.first);
      }
      return;
    }
    final data = (ev['data'] as Map?)?.cast<String, dynamic>() ?? const {};
    if (ev['type'] == 'assist.answer') {
      if (id == askId) _finishAnswer(data);
      return;
    }
    switch (ev['type']) {
      case 'research.progress':
        researchStage = data['stage'] as String?;
      case 'research.finished':
        _finishResearch(data['status'] as String? ?? 'FAILED', data['a2ui'] as List?);
        return;
      default:
        return;
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _sub?.cancel();
    _poll?.cancel();
    _workerChanges?.removeListener(_checkWorker);
    results.dispose();
    super.dispose();
  }
}
