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
  }) {
    _sub = events?.listen(_onEvent);
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
  IntegratedRuntime? _lastRuntime;
  StreamSubscription<Map<String, dynamic>>? _sub;

  /// Last `assist_status` reply (state, scope, permissions, adapters, vision).
  Map<String, dynamic> status = const {'state': 'OFF'};
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
      notifyListeners();
      return null;
    }
    if (_lastRuntime != null && !identical(rt, _lastRuntime)) {
      // A restarted worker starts with Assist OFF; never show the old grant.
      status = const {'state': 'OFF'};
      findings = const [];
      lastObservation = null;
      answer = null;
      researchJobId = null;
    }
    _lastRuntime = rt;
    busy = true;
    notifyListeners();
    try {
      final v = await rt.call(command);
      lastError = null;
      if (updatesStatus) {
        status = v;
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
    await _call({
      'command': 'assist_grant',
      'kind': kind,
      'target_id': targetId,
      'permissions': ['observe', if (suggest) 'suggest'],
      'confirm_screen': confirmScreen,
    }, updatesStatus: true);
    if (lastError == null) cancelChoosing();
  }

  Future<void> pause() => _call({'command': 'assist_pause'}, updatesStatus: true);
  Future<void> resume() => _call({'command': 'assist_resume'}, updatesStatus: true);

  /// Stop: one tap, no confirmation; everything derived is discarded.
  Future<void> revoke() async {
    findings = const [];
    lastObservation = null;
    answer = null;
    await _call({'command': 'assist_revoke'}, updatesStatus: true);
  }

  Future<void> check() async {
    final v = await _call({'command': 'assist_check'});
    if (v == null) return;
    findings = [for (final f in (v['findings'] as List? ?? const [])) (f as Map).cast<String, dynamic>()];
    lastObservation = (v['observation'] as Map?)?.cast<String, dynamic>();
    notifyListeners();
  }

  Future<void> ask(String question, {bool useScreenshot = false}) async {
    answer = null;
    final v = await _call({'command': 'assist_ask', 'question': question, 'use_screenshot': useScreenshot});
    if (v == null) return;
    answer = v['answer'] as String?;
    lastObservation = (v['observation'] as Map?)?.cast<String, dynamic>();
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
    notifyListeners();
  }

  Future<void> cancelResearch() async {
    final id = researchJobId;
    if (id == null) return;
    await _call({'command': 'web_research_cancel', 'job_id': id});
  }

  void _onEvent(Map<String, dynamic> ev) {
    if (ev['turn_id'] != researchJobId || researchJobId == null) return;
    final data = (ev['data'] as Map?)?.cast<String, dynamic>() ?? const {};
    switch (ev['type']) {
      case 'research.progress':
        researchStage = data['stage'] as String?;
      case 'research.finished':
        researchStatus = data['status'] as String? ?? 'FAILED';
        researchStage = 'finished';
        researchA2ui = data['a2ui'] as List?;
        if (researchA2ui != null) results.apply(researchA2ui!);
      default:
        return;
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _sub?.cancel();
    results.dispose();
    super.dispose();
  }
}
