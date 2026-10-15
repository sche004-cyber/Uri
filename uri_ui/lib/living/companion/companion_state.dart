/// What the Energy Orb is allowed to express.
///
/// Each state is a presentation of an authoritative fact, never a guess
/// (see `docs/architecture/PHASE2CLOSE_UI_READINESS.md` section 3 and
/// `docs/ui_phase/UI_INTERFACE_CONTRACTS.md`). The mapping from facts to
/// states lives in `companion_sources.dart`; this file only names them.
enum CompanionState {
  /// No backend / no opt-in / worker failed preflight. Dim, slow.
  unavailable,

  /// The Brain is starting normally (loading its model, or waiting for the
  /// GPU). Calm and neutral, never the failed look: a first-time user must
  /// not read a normal startup as a fault (owner decision, Ember V2.1
  /// final). Failures and stopped Brains stay [unavailable].
  initializing,

  /// Nothing pending, nothing running. Breathing.
  idle,

  /// A voice listener reports listening. No listener exists in this
  /// tree, so it can only come from a mock source (flagged simulated).
  listening,

  /// A request is in flight (`AppState.isSendingAsk`) or an intent is
  /// being understood.
  thinking,

  /// URI is producing output (streamed reply / TTS). Mock-only today.
  speaking,

  /// An execution is queued/approving/starting/running.
  working,

  /// A proposal or clarification needs the user. Nothing proceeds
  /// until a structured decision; typed or spoken words never approve.
  awaitingApproval,

  /// A corroborated completion. Short bloom, then back to idle.
  success,

  /// Failed, uncertain, quota-paused, or backend unreachable.
  error,
}

extension CompanionStateLabel on CompanionState {
  /// Short human label used by badges and semantics.
  String get label => switch (this) {
    CompanionState.unavailable => 'Unavailable',
    CompanionState.initializing => 'Initializing',
    CompanionState.idle => 'Idle',
    CompanionState.listening => 'Listening',
    CompanionState.thinking => 'Thinking',
    CompanionState.speaking => 'Speaking',
    CompanionState.working => 'Working',
    CompanionState.awaitingApproval => 'Needs your approval',
    CompanionState.success => 'Done',
    CompanionState.error => 'Attention needed',
  };

  /// States in which URI is waiting on the user rather than on itself.
  bool get needsUser => this == CompanionState.awaitingApproval;

  bool get isActive =>
      this == CompanionState.thinking ||
      this == CompanionState.working ||
      this == CompanionState.listening ||
      this == CompanionState.speaking;
}

/// One observed companion signal: the state plus what it was derived
/// from. [simulated] is true whenever the source is a mock/scripted
/// event; every surface that shows a simulated signal must say so.
class CompanionSignal {
  const CompanionSignal({
    required this.state,
    this.detail,
    this.progress,
    this.simulated = false,
    this.sourceName,
  });

  const CompanionSignal.idle()
    : state = CompanionState.idle,
      detail = null,
      progress = null,
      simulated = false,
      sourceName = 'none';

  final CompanionState state;

  /// One line for the status strip, e.g. "Drafting letter to Mr Rai".
  final String? detail;

  /// 0..1 when a bounded execution reports progress; null otherwise.
  final double? progress;

  final bool simulated;

  /// Which source produced it (for the intelligence overview, never
  /// for authority).
  final String? sourceName;

  CompanionSignal copyWith({
    CompanionState? state,
    String? detail,
    double? progress,
    bool? simulated,
    String? sourceName,
  }) {
    return CompanionSignal(
      state: state ?? this.state,
      detail: detail ?? this.detail,
      progress: progress ?? this.progress,
      simulated: simulated ?? this.simulated,
      sourceName: sourceName ?? this.sourceName,
    );
  }

  @override
  bool operator ==(Object other) =>
      other is CompanionSignal &&
      other.state == state &&
      other.detail == detail &&
      other.progress == progress &&
      other.simulated == simulated &&
      other.sourceName == sourceName;

  @override
  int get hashCode =>
      Object.hash(state, detail, progress, simulated, sourceName);

  @override
  String toString() =>
      'CompanionSignal(${state.name}, detail: $detail, progress: $progress, '
      'simulated: $simulated, source: $sourceName)';
}
