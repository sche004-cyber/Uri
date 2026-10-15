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
    'brain_status' => {'state': brainState, 'model_id': 'qwen-test', 'artifacts': 'MATCH'},
    'brain_health' => {
      'readiness': brainState,
      'host': {'running': hostState != null, 'state': hostState},
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

    for (final st in ['STARTING', 'LOADING', 'STARTING_HOST', 'CALIBRATING']) {
      final s = await at(st);
      expect(s.state, CompanionState.initializing, reason: st);
      expect(s.detail, 'Brain loading', reason: st);
      expect(s.simulated, isFalse);
    }
    for (final st in ['WAITING_FOR_GPU', 'WAITING_FOR_LEASE']) {
      final s = await at(st);
      expect(s.state, CompanionState.initializing, reason: st);
      expect(s.detail, 'Waiting for the GPU', reason: st);
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
    // A host that is stopping, or a runtime fault, is never shown as starting.
    rt.hostState = 'STOPPING';
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
