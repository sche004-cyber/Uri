import 'dart:async';

import 'package:flutter_test/flutter_test.dart';

import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_sources.dart';
import 'package:uri_ui/services/integrated_runtime.dart';

/// FCV-10: while the Brain starts, the first screen said "Unavailable /
/// Brain STOPPED" with no guidance. The companion now names the phase the
/// worker and the Brain host actually report, and invents no progress.
class _Runtime implements IntegratedRuntime {
  String brainState = 'STOPPED';
  Map<String, dynamic> health = const {};
  final _events = StreamController<Map<String, dynamic>>.broadcast();

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;

  @override
  bool get closed => false;

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    switch (command['command']) {
      case 'brain_status':
        return {'state': brainState, 'model_id': 'qwen-test'};
      case 'brain_health':
        return health;
      case 'brain_catalog':
        return {
          'rows': [
            {'id': 'runtime-v1', 'display': 'Runtime v1 (local)', 'selectable': true, 'selected': true, 'state': brainState},
          ],
          'fallback': 'none',
        };
      default:
        return {'ok': true};
    }
  }

  @override
  Future<void> close() async => _events.close();

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Map<String, dynamic> _health(String? hostState, {String? explain, bool running = true}) => {
      'state': 'RECOVERING',
      'host': {'running': running, 'state': hostState},
      'explain': ?explain,
    };

void main() {
  group('brainNotReadyPresentation', () {
    test('host phases name the real startup step, never STOPPED', () {
      for (final (host, headline) in [
        ('STARTING_HOST', 'Starting Brain'),
        ('STARTING', 'Starting Brain'),
        ('LOADING', 'Loading model'),
        ('CALIBRATING', 'Checking Brain speed'),
      ]) {
        final p = brainNotReadyPresentation('STOPPED', _health(host));
        expect(p.headline, headline, reason: host);
        expect(p.state, CompanionState.working, reason: host);
        expect('${p.headline} ${p.detail}', isNot(contains('STOPPED')));
      }
    });

    test("the host's own explanation is shown when it gives one", () {
      final p = brainNotReadyPresentation('STOPPED', _health('LOADING', explain: 'Starting the Brain (Runtime v1).'));
      expect(p.detail, 'Starting the Brain (Runtime v1).');
    });

    test('a stale (not running) host report is ignored', () {
      final p = brainNotReadyPresentation('STOPPED', _health('LOADING', running: false));
      expect(p.headline, 'Brain not running');
      expect(p.state, CompanionState.unavailable);
    });

    test('readiness alone still distinguishes loading, failure and setup states', () {
      expect(brainNotReadyPresentation('LOADING', const {}).headline, 'Loading model');
      expect(brainNotReadyPresentation('STARTING', const {}).headline, 'Starting Brain');
      expect(brainNotReadyPresentation('NOT_CONFIGURED', const {}).headline, 'Brain not set up');
      expect(brainNotReadyPresentation('ARTIFACT_MISSING', const {}).headline, 'Brain files missing');
      expect(brainNotReadyPresentation('IDENTITY_MISMATCH', const {}).state, CompanionState.error);
      expect(brainNotReadyPresentation('FOREIGN_INSTANCE', const {}).state, CompanionState.error);
      expect(brainNotReadyPresentation('FAILED', const {}).headline, 'Brain failed to start');
      expect(brainNotReadyPresentation('SOMETHING_NEW', const {}).headline, 'Brain unavailable');
    });

    test('waiting for GPU memory says so and does not claim URI closes apps', () {
      final p = brainNotReadyPresentation('STOPPED', _health('WAITING_FOR_GPU'));
      expect(p.headline, 'Waiting for GPU');
      expect(p.state, CompanionState.unavailable);
      expect(p.detail, contains('does not close other apps'));
    });

    test('no percentage or time estimate is invented', () {
      for (final r in ['STOPPED', 'STARTING', 'LOADING', 'FAILED', 'NOT_CONFIGURED']) {
        for (final h in [null, 'STARTING', 'LOADING', 'CALIBRATING', 'WAITING_FOR_GPU']) {
          final p = brainNotReadyPresentation(r, h == null ? const {} : _health(h));
          expect('${p.headline} ${p.detail}', isNot(matches(RegExp(r'\d+\s*(%|s\b|sec|min)'))));
        }
      }
    });
  });

  test('the companion shows the loading phase from the worker health report', () async {
    final rt = _Runtime()
      ..brainState = 'STOPPED'
      ..health = _health('LOADING');
    final conv = OiConversation(rt);
    await conv.refreshStatus();
    final src = OiCompanionSource(conv);
    expect(src.signal.title, 'Loading model');
    expect(src.signal.detail, isNot(contains('STOPPED')));
    expect(src.signal.simulated, isFalse);
    rt
      ..brainState = 'READY'
      ..health = {'state': 'READY'};
    await conv.refreshStatus();
    expect(src.signal.state, CompanionState.idle);
    expect(src.signal.title, 'Idle');
  });
}
