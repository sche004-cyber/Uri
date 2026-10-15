// The shared Initializing state (owner decision, Ember V2.1 final): a Brain
// that is starting normally reads as calm, not failed, for every companion.
import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_sources.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/ember_companion.dart';
import 'package:uri_ui/living/companion/energy_orb.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_sources.dart';
import 'package:uri_ui/services/integrated_runtime.dart';

/// Minimal integrated worker: answers `brain_status` with [brainState] and
/// lets the test push events.
class _Runtime implements IntegratedRuntime {
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  String brainState = 'READY';
  String? hostState;

  String? healthReadiness;

  /// When set, both reports carry `checked_at` like the real worker (review R6-7).
  num? statusAt;
  num? healthAt;
  int _turn = 0;

  void emit(String turnId, String type, Map<String, dynamic> data) =>
      _events.add({'schema': 'uri.oi.event.v1', 'turn_id': turnId, 'type': type, 'data': data});

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;

  @override
  bool get closed => false;

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async => switch (command['command']) {
    'oi_turn' => {'turn_id': 't${++_turn}', 'accepted': true},
    'brain_status' => {'state': brainState, 'model_id': 'qwen-test', 'artifacts': 'MATCH', 'checked_at': ?statusAt},
    'brain_health' => {
      'readiness': healthReadiness ?? brainState,
      'host': {'running': hostState != null, 'state': hostState},
      'checked_at': ?healthAt,
    },
    'brain_catalog' => {
      'rows': [
        {'id': 'runtime-v1', 'display': 'Runtime v1 (local)', 'selectable': true, 'selected': true, 'state': brainState},
      ],
      'fallback': 'none',
    },
    _ => {'ok': true},
  };

  @override
  Future<void> close() async {}

  @override
  Future<void> kill() async {}
}

void main() {
  test('the label is Initializing; it is neither active nor waiting on the user', () {
    expect(CompanionState.initializing.label, 'Initializing');
    expect(CompanionState.initializing.isActive, isFalse);
    expect(CompanionState.initializing.needsUser, isFalse);
  });

  test('a normally starting Brain shows initializing; stopped or failed stays unavailable', () async {
    final rt = _Runtime();
    final conv = OiConversation(rt);
    await conv.refreshStatus();
    final src = OiCompanionSource(conv);
    Future<CompanionSignal> at(String state) async {
      rt.brainState = state;
      await conv.refreshStatus();
      return src.signal;
    }

    for (final st in ['STARTING', 'LOADING']) {
      final s = await at(st);
      expect(s.state, CompanionState.initializing, reason: st);
      expect(s.detail, 'Brain loading', reason: st);
      expect(s.simulated, isFalse);
    }
    for (final st in ['STOPPED', 'FAILED', 'ARTIFACT_MISSING', 'IDENTITY_MISMATCH', 'FOREIGN_INSTANCE', 'DEGRADED', 'SOMETHING_NEW']) {
      final s = await at(st);
      expect(s.state, CompanionState.unavailable, reason: st);
      expect(s.detail, 'Brain $st', reason: st);
    }
    // The runtime still reads STOPPED while the Brain host boots or waits for
    // the lease: the running host's startup state decides.
    rt.hostState = 'STARTING_HOST';
    expect((await at('STOPPED')).state, CompanionState.initializing);
    expect(src.signal.detail, 'Brain loading');
    rt.hostState = 'WAITING_FOR_LEASE';
    expect((await at('STOPPED')).detail, 'Waiting for the GPU');
    // A host that is stopping, or waiting on GPU contention that needs the
    // user (review R3-02), or a runtime fault, is never shown as starting.
    rt.hostState = 'STOPPING';
    expect((await at('STOPPED')).state, CompanionState.unavailable);
    rt.hostState = 'WAITING_FOR_GPU';
    expect((await at('STOPPED')).state, CompanionState.unavailable);
    rt.hostState = 'STARTING_HOST';
    expect((await at('FAILED')).state, CompanionState.unavailable);
    rt.hostState = null;
    // Startup completes: initializing hands over to idle.
    expect((await at('LOADING')).state, CompanionState.initializing);
    expect((await at('READY')).state, CompanionState.idle);
    // The streamed brain.status event takes the same path.
    await conv.send('hi');
    rt.emit('t1', 'brain.status', {'state': 'LOADING'});
    await pumpEventQueue();
    expect(src.signal.state, CompanionState.initializing);
    src.dispose();
  });

  group('brainStartingDetail decides from both snapshots (review R3-01)', () {
    Map<String, dynamic> h(String? readiness, [String? host]) => {
      'readiness': ?readiness,
      'host': {'running': host != null, 'state': host},
    };

    test('a stale starting runtime never hides a newer failure', () {
      expect(brainStartingDetail('LOADING', h('FAILED')), isNull);
      expect(brainStartingDetail('LOADING', h('STOPPED')), isNull);
      expect(brainStartingDetail('LOADING', h('LOADING', 'FAILED')), isNull);
      expect(brainStartingDetail('STARTING', h('STARTING', 'STOPPING')), isNull);
      expect(brainStartingDetail('LOADING', h('LOADING', 'WAITING_FOR_GPU')), isNull);
      expect(brainStartingDetail('LOADING', h('ARTIFACT_MISSING')), isNull);
    });

    test('a stale STOPPED does not flash depleted while the Brain comes up', () {
      expect(brainStartingDetail('STOPPED', h('LOADING', 'STARTING')), 'Brain loading');
      expect(brainStartingDetail('STOPPED', h('READY', 'READY')), 'Brain loading');
      expect(brainStartingDetail('STOPPED', h('READY', 'CALIBRATING')), 'Brain loading');
      expect(brainStartingDetail('LOADING', h('READY')), 'Brain loading');
    });

    test('health older than a STOPPED read never turns a stopped Brain into Initializing (R4-N1)', () {
      // refreshHealth failed after a fresh STOPPED: the last report still says READY or LOADING.
      expect(brainStartingDetail('STOPPED', h('READY')), isNull);
      expect(brainStartingDetail('STOPPED', h('LOADING')), isNull);
    });

    test('the unavailable detail names the newer state (R4-N2)', () {
      // Health stamped after the status read (the worker stamps both).
      Map<String, dynamic> newer(String? r, [String? host]) => {...h(r, host), 'checked_at': 300};
      expect(brainUnavailableDetail('LOADING', newer('LOADING', 'FAILED'), statusCheckedAt: 200), 'Brain FAILED');
      expect(brainUnavailableDetail('LOADING', newer('FAILED'), statusCheckedAt: 200), 'Brain FAILED');
      expect(brainUnavailableDetail('STOPPED', newer('STOPPED', 'WAITING_FOR_GPU'), statusCheckedAt: 200),
          'Brain WAITING_FOR_GPU');
      expect(brainUnavailableDetail('STOPPED', newer('STOPPED'), statusCheckedAt: 200), 'Brain STOPPED');
      expect(brainUnavailableDetail('FAILED', const {}), 'Brain FAILED');
      // Unstamped health is of unknown age: the polled state stands (R5-N2).
      expect(brainUnavailableDetail('LOADING', h('FAILED')), 'Brain LOADING');
    });

    test('the newer snapshot decides when both are stamped (R5-N2/N3)', () {
      Map<String, dynamic> at(num t, String? readiness, [String? host]) => {...h(readiness, host), 'checked_at': t};
      // Health older than the status read: only the runtime state counts.
      expect(brainStartingDetail('STOPPED', at(100, 'LOADING', 'STARTING'), statusCheckedAt: 200), isNull);
      expect(brainStartingDetail('STOPPED', at(100, 'READY'), statusCheckedAt: 200), isNull);
      expect(brainStartingDetail('LOADING', at(100, 'FAILED', 'FAILED'), statusCheckedAt: 200), 'Brain loading');
      expect(brainUnavailableDetail('STOPPED', at(100, 'LOADING'), statusCheckedAt: 200), 'Brain STOPPED');
      expect(brainUnavailableDetail('FAILED', at(100, 'STARTING', 'STARTING'), statusCheckedAt: 200), 'Brain FAILED');
      // Health newer than the status read: it wins, also without a host.
      expect(brainStartingDetail('STOPPED', at(300, 'LOADING'), statusCheckedAt: 200), 'Brain loading');
      expect(brainStartingDetail('LOADING', at(300, 'FAILED'), statusCheckedAt: 200), isNull);
      expect(brainUnavailableDetail('LOADING', at(300, 'FAILED'), statusCheckedAt: 200), 'Brain FAILED');
      // UNKNOWN never replaces a known state.
      expect(brainUnavailableDetail('FAILED', at(300, 'UNKNOWN'), statusCheckedAt: 200), 'Brain FAILED');
    });

    test('a stopped Brain with no starting host stays unavailable', () {
      expect(brainStartingDetail('STOPPED', h('STOPPED')), isNull);
      expect(brainStartingDetail('STOPPED', h('STOPPED', 'STOPPED')), isNull);
      expect(brainStartingDetail('STOPPED', const {}), isNull);
      expect(brainStartingDetail('FAILED', h('LOADING', 'STARTING_HOST')), isNull);
      expect(brainStartingDetail(null, h('LOADING')), isNull);
    });

    test('without a health report the runtime state decides alone', () {
      expect(brainStartingDetail('LOADING', const {}), 'Brain loading');
      expect(brainStartingDetail('STARTING', const {}), 'Brain loading');
    });
  });

  test('stamped reports through the real conversation: the newer one decides (review R6-7)', () async {
    final rt = _Runtime()
      ..statusAt = 100
      ..healthAt = 200;
    final conv = OiConversation(rt);
    final src = OiCompanionSource(conv);
    // Newer health: the host has failed although the runtime read still says LOADING.
    rt
      ..brainState = 'LOADING'
      ..hostState = 'FAILED';
    await conv.refreshStatus();
    expect(src.signal.state, CompanionState.unavailable);
    expect(src.signal.detail, 'Brain FAILED');
    // Newer health says the Brain is up while the runtime read is a stale STOPPED: calm, not depleted.
    rt
      ..brainState = 'STOPPED'
      ..healthReadiness = 'READY'
      ..hostState = 'READY';
    await conv.refreshStatus();
    expect(src.signal.state, CompanionState.initializing);
    // Older health (a failed refresh kept it): only the fresh STOPPED counts.
    rt
      ..statusAt = 300
      ..healthReadiness = 'LOADING'
      ..hostState = 'STARTING';
    await conv.refreshStatus();
    expect(src.signal.state, CompanionState.unavailable);
    expect(src.signal.detail, 'Brain STOPPED');
    src.dispose();
  });

  test('initializing never hides a failure or a request from another source', () {
    final starting = MockCompanionSource()..emit(CompanionState.initializing);
    final failed = MockCompanionSource()..emit(CompanionState.unavailable);
    final busy = MockCompanionSource()..emit(CompanionState.working);
    expect(CompositeCompanionSource([starting, failed]).signal.state, CompanionState.unavailable);
    expect(CompositeCompanionSource([starting, busy]).signal.state, CompanionState.working);
    expect(CompositeCompanionSource([starting, MockCompanionSource()]).signal.state, CompanionState.initializing);
  });

  test('every companion has a calm initializing look: dimmer than idle, brighter than unavailable', () {
    for (final id in CompanionIdentity.values) {
      final init = CompanionParams.of(id, CompanionState.initializing);
      final idle = CompanionParams.of(id, CompanionState.idle);
      final off = CompanionParams.of(id, CompanionState.unavailable);
      expect(init.energy, lessThan(idle.energy), reason: id.name);
      expect(init.energy, greaterThan(off.energy), reason: id.name);
      expect(init.exposure, lessThan(idle.exposure), reason: id.name);
      expect(init.exposure, greaterThan(off.exposure), reason: id.name);
    }
    final orb = OrbParams.forState(CompanionState.initializing);
    expect(orb.energy, lessThan(OrbParams.forState(CompanionState.idle).energy));
    expect(orb.energy, greaterThan(OrbParams.forState(CompanionState.unavailable).energy));
    expect(EmberClips.forState(CompanionState.initializing), EmberClip.kindling);
    // Kindling hands over to idle with the normal cross-fade, not the slow
    // rekindle reserved for leaving depleted.
    expect(EmberClips.fadeBetween(EmberClip.kindling, EmberClip.idle),
        EmberClips.fadeBetween(EmberClip.idle, EmberClip.thinking));
  });
}
