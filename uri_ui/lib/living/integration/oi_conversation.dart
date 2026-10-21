import 'dart:async';
import 'dart:math';

import 'package:flutter/foundation.dart';

import '../../services/integrated_runtime.dart';
import 'oi_draft.dart';

/// Working-system conversation model (WS blueprint W9): renders the real
/// `uri.oi.event.v1` stream from the integrated worker.
///
/// Rules carried over from the OI UI contract:
/// * Only `core.result` / `task.step` carry action outcomes; answer text
///   never does. An answer flagged `UNVERIFIED_ACTION_CLAIM` is marked.
/// * Approval happens only through [decide], from a button. It echoes the
///   digest of the card the user saw. [send] never decides anything.
/// * Reasoning text is never received; only the tier and a progress count.
/// * The Brain selection changes only through [selectBrain] (explicit).
/// * Health (WS hardening): [brainHealth] is the worker's READY / BUSY /
///   DEGRADED / UNAVAILABLE / RECOVERING report. A Brain restart is an
///   explicit request ([brainAction]) the worker refuses while a turn runs.
/// * Liveness (R-BUSY): while a turn runs and nothing arrives, the monitor
///   asks the worker for the job's state with a bound longer than the
///   worker's longest legitimate block. No answer = unresponsive; an answer
///   with a long-silent job = stalled. Both offer Restart worker. A restart
///   never retries the interrupted turn; its outcome is reported as unknown.

enum OiRole { user, uri, system }

/// Plain words for a turn the worker did not accept (FCV-08); the code stays in the worker's evidence.
String notSentMessage(String code) => switch (code) {
      'TURN_IN_PROGRESS' => 'Not sent: URI is still finishing the previous request. Try again in a moment.',
      'BRAIN_RESTARTING' => 'Not sent: the Brain is restarting. Try again when it is ready.',
      'TEXT_INVALID' => 'Not sent: the message was empty or too long.',
      'WORKER_TIMEOUT' => 'Not sent: URI did not answer in time. Try again.',
      _ => 'Not sent: URI could not accept this request right now.',
    };

/// Plain words for a Brain profile switch the worker or the host refused (BRAIN-QC).
String brainSwitchRefusal(String code) => switch (code) {
      'TURN_IN_PROGRESS' => 'Not switched: wait until URI has finished answering.',
      'BRAIN_RESTARTING' => 'Not switched: the Brain is already restarting or switching.',
      'BRAIN_HOST_NOT_RUNNING' => 'Not switched: the Brain host is not running. Start URI with its launcher.',
      'BRAIN_CONTROL_UNAVAILABLE' => 'Not switched: this URI build cannot control the Brain.',
      'NOT_SELECTED' => 'Not switched: no local Brain is selected.',
      'PROFILE_NOT_QUALIFIED' => 'Not switched: that combination is not qualified yet.',
      'PROFILE_NOT_OFFERED' => 'Not switched: that Brain setting is not offered here.',
      'PROFILE_UNKNOWN' || 'PROFILE_INVALID' => 'Not switched: URI does not know that Brain setting.',
      'REFUSED_DOES_NOT_FIT' => 'Not switched: there is not enough free GPU memory. The Brain keeps running as it was.',
      'REFUSED_GPU_UNMEASURED' => 'Not switched: GPU memory could not be measured. The Brain keeps running as it was.',
      'REFUSED_ATTACHED_INSTANCE' => 'Not switched: this Brain was started outside URI.',
      'ASSIST_NEEDS_VISION' => 'Not switched: a URI Assist session is open, so URI keeps vision on. End it first.',
      'ASSIST_ASK_IN_PROGRESS' => 'Not switched: wait until URI Assist has finished answering.',
      _ => 'Not switched ($code).',
    };

class OiMessage {
  OiMessage({required this.role, required this.text, this.turnId});
  final OiRole role;
  String text;
  final String? turnId;

  /// Answer-channel status (COMPLETE, CANCELLED, ...) once done.
  String? answerStatus;

  /// Core's authoritative code for an action turn (SETTLED_VERIFIED, ...).
  String? coreCode;
  String? coreMessage;

  /// What actually changed after Core's verified settlement, read by the
  /// worker from the client store (`core.outcome`). Shown instead of Core's
  /// generic message when present.
  String? outcomeSummary;

  /// FAST / NORMAL tier actually used, and the route (answer, core, plan...).
  String? tier;
  String? route;
  int thinkingChars = 0;

  /// Draft desk: characters of structured output generated so far.
  int draftChars = 0;
  List<String> flags = const [];
  Map<String, dynamic> metrics = const {};
  String? errorCode;
  String? errorMessage;
  List<String> recoveryOptions = const [];
  bool streaming = false;
  String? finishedStatus;

  /// User messages: how the words arrived (null = typed). Simulated
  /// transcripts are always labelled as simulated.
  String? inputLabel;

  bool get unverifiedClaim => flags.contains('UNVERIFIED_ACTION_CLAIM');
}

class OiApproval {
  const OiApproval({
    required this.turnId,
    required this.capabilityId,
    required this.arguments,
    required this.approvalDigest,
    this.effect,
    this.reversible,
  });
  final String turnId;
  final String capabilityId;
  final Map<String, dynamic> arguments;
  final String approvalDigest;
  final String? effect;
  final bool? reversible;
}

class OiConfirmation {
  const OiConfirmation({required this.turnId, required this.message, required this.data});
  final String turnId;
  final String? message;
  final Map<String, dynamic> data;
}

/// Depth the user asks for on the next turn (`auto` lets the policy decide).
enum OiDepth { auto, fast, normal, deep }

class OiConversation extends ChangeNotifier {
  OiConversation(
    this.runtime, {
    String? sessionId,
    this.respawn,
    this.probeAfter = const Duration(seconds: 20),
    this.probeTimeout = const Duration(seconds: 40),
    this.stalledAfter = const Duration(seconds: 90),
  }) : sessionId = sessionId ?? _uuid4() {
    _sub = runtime.events.listen(_onEvent);
  }

  /// The current worker. Replaced only by [restartWorker].
  IntegratedRuntime runtime;
  final String sessionId;
  late StreamSubscription<Map<String, dynamic>> _sub;

  /// Starts a fresh worker for [restartWorker] (null: restart unavailable).
  final Future<IntegratedRuntime?> Function()? respawn;

  /// Silence before the monitor probes a running turn.
  final Duration probeAfter;

  /// Probe bound. Longer than the worker's longest legitimate block (a
  /// continuation joins its finishing job for up to 30 s, `JOIN_S`).
  final Duration probeTimeout;

  /// A job that is alive but has sent nothing for this long is "stalled".
  final Duration stalledAfter;

  Timer? _monitor;
  bool _probing = false;
  DateTime _lastFrame = DateTime.now();

  /// The worker did not answer a status probe within [probeTimeout].
  bool workerUnresponsive = false;

  /// The worker answers, but the running job has been silent for [stalledAfter].
  bool turnStalled = false;
  bool restarting = false;
  Map<String, dynamic> turnStatus = const {};
  Map<String, dynamic> brainHealth = const {};

  /// When [brainHealth] was last read successfully (microseconds since epoch; 0 = never).
  int brainHealthAt = 0;

  final List<OiMessage> messages = [];

  final _a2uiHandoffs = StreamController<Map<String, dynamic>>.broadcast();

  /// `a2ui.handoff` events (A2UI slice): an interpreted request for a domain
  /// authority to propose a surface. Carries no authority itself.
  Stream<Map<String, dynamic>> get a2uiHandoffs => _a2uiHandoffs.stream;

  /// Frames of the Web Intelligence / Assist commands (schema
  /// `uri.assist.event.v1`, docs/assist). They share the worker's event
  /// stream but are not OI turn events: they are handed to the Assist view
  /// and never touch turn, stall or companion state here.
  static const assistEventSchema = 'uri.assist.event.v1';
  final _assistEvents = StreamController<Map<String, dynamic>>.broadcast();
  Stream<Map<String, dynamic>> get assistEvents => _assistEvents.stream;
  final Map<String, OiMessage> _byTurn = {};

  /// Events for a turn id this model has not registered yet (defensive: the
  /// worker writes the reply first, but stream and future callbacks may still
  /// interleave). Replayed by [_begin]; bounded.
  final Map<String, List<Map<String, dynamic>>> _early = {};

  /// Jobs started vs `turn.finished` received, per turn. A turn is active until every job it started (the turn
  /// itself, then each confirm/decide continuation) has finished, so the original job's late `turn.finished`
  /// cannot end a continuation that is still running (Codex WS round 2).
  final Map<String, int> _jobs = {};
  final Map<String, int> _finishes = {};

  String? activeTurnId;
  String companionState = 'idle';
  OiApproval? pendingApproval;
  OiConfirmation? pendingConfirmation;
  String? lastError;
  bool workerExited = false;
  /// Turn depth for the next message. The Thinking toggle is On / Off only
  /// (URI-CONTROLS-3): Off (fast) until the user turns it on; LivingApp
  /// restores the user's last choice at start ([restoreDepth]).
  OiDepth depth = OiDepth.fast;

  /// Called after the user changes the depth (LivingApp stores it).
  void Function(OiDepth depth)? onDepthChanged;

  /// Restores a stored depth by name; unknown names are ignored.
  void restoreDepth(String? name) {
    for (final d in OiDepth.values) {
      if (d.name == name && d != depth) {
        depth = d;
        notifyListeners();
      }
    }
  }

  /// Text intelligence: the session's current draft (null when none), the
  /// desk's open clarification question, and generation progress.
  OiDraft? draft;
  String? draftQuestion;

  /// c5 C2-01: the open question is about a NEW document (the worker sent it
  /// without a draft), not about the open draft: it is answered in the
  /// conversation, never through the open draft's target.
  bool draftQuestionIsNew = false;
  int draftProgress = 0;

  /// When on, typed text is sent as a SIMULATED transcript
  /// (`uri.text_input.v1`, engine "simulated"). There is no microphone path.
  bool transcriptMode = false;

  /// Dictation (TI L-2): the words are draft CONTENT, never an instruction.
  /// Sent as `mode: dictation`; the worker never routes them to Core.
  bool dictationMode = false;

  Map<String, dynamic> brainStatus = const {};
  Map<String, dynamic> catalog = const {};
  List<String> memory = const [];
  Map<String, dynamic> cloud = const {};
  bool _disposed = false;
  bool _active(IntegratedRuntime rt) => !_disposed && identical(rt, runtime);

  /// When the `oi_turn` that is awaiting its reply was sent (Codex H-r1 F4).
  DateTime? _sendingSince;

  bool get busy => activeTurnId != null || _sendingSince != null;
  bool get brainReady => brainStatus['state'] == 'READY';

  /// READY / BUSY / DEGRADED / UNAVAILABLE / RECOVERING, or null before the
  /// first health report.
  String? get healthState => brainHealth['state'] as String?;

  /// The worker needs the user's attention (offer Restart worker).
  bool get workerTrouble => workerUnresponsive || turnStalled || workerExited;

  /// Draft buttons that need the worker (Undo/Redo/Close) are off while a turn runs, while the worker is being
  /// replaced, and after the worker exited: the draft lived in that worker (TI L-7). Copy stays available, so
  /// the text on screen can still be kept before Restart URI clears it.
  bool get draftActionsBlocked => busy || restarting || workerExited;
  String get selectedRowId {
    final rows = (catalog['rows'] as List?) ?? const [];
    for (final r in rows) {
      if (r is Map && r['selected'] == true) return r['id'] as String;
    }
    return 'runtime-v1';
  }

  // ---- commands ---------------------------------------------------------

  Future<void> refreshStatus() async {
    if (_disposed) return;
    final rt = runtime;
    try {
      final status = await rt.call({'command': 'brain_status'});
      if (!_active(rt)) return;
      brainStatus = status;
      final rows = await rt.call({'command': 'brain_catalog'});
      if (!_active(rt)) return;
      catalog = rows;
      lastError = null;
    } on IntegratedRuntimeException catch (e) {
      if (!_active(rt)) return;
      lastError = e.code;
    }
    await refreshHealth(notify: false);
    if (_active(rt)) notifyListeners();
  }

  Future<void> refreshHealth({bool notify = true}) async {
    if (_disposed) return;
    final rt = runtime;
    try {
      final health = await rt.call({'command': 'brain_health'}).timeout(probeTimeout);
      if (!_active(rt)) return;
      final changed = brainHealth.isNotEmpty && health['state'] != brainHealth['state'];
      brainHealth = health;
      brainHealthAt = DateTime.now().microsecondsSinceEpoch;
      // BRAIN-QC (review R1-01 correction): the readiness the header shows is re-read on a health change AND on every
      // poll while the Brain is recovering or switching. During a profile switch it never reads "ready": the old
      // server still answers READY until it is stopped, and the new one before its calibration, but neither is the
      // confirmed Brain yet; the header says "starting" until the switch is finished.
      final switching = (brainControls['switch'] as Map?)?['pending'] == true;
      // R2-01: a masked status left by a failed read is re-read until a real one replaces it.
      if (changed || switching || health['state'] == 'RECOVERING' || brainStatus['switching'] == true) {
        final status = await rt.call({'command': 'brain_status'}).timeout(probeTimeout);
        if (!_active(rt)) return;
        brainStatus = switching && status['state'] == 'READY'
            ? {...status, 'state': 'STARTING', 'runtime_state': 'READY', 'switching': true}
            : status;
      }
    } on IntegratedRuntimeException catch (e) {
      if (!_active(rt)) return;
      lastError = e.code;
    } on TimeoutException {
      // The liveness probe decides about the worker; a slow health read alone does not.
    }
    if (notify && _active(rt)) notifyListeners();
  }

  /// Explicit Brain host request: 'restart', 'stop' or 'start'.
  Future<void> brainAction(String action) async {
    if (busy) return;
    try {
      await runtime.call({'command': 'brain_restart', 'action': action});
      lastError = null;
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      messages.add(OiMessage(role: OiRole.system, text: 'Brain $action refused: ${e.code}'));
    }
    await refreshHealth();
  }

  /// Health polling and the liveness monitor (one timer).
  void startMonitor([Duration every = const Duration(seconds: 5)]) {
    if (_disposed) return;
    _monitor?.cancel();
    _monitor = Timer.periodic(every, (_) => monitorTick());
  }

  /// One monitor step (public for tests).
  Future<void> monitorTick() async {
    if (_disposed || _probing || restarting || workerExited) return;
    final rt = runtime;
    _probing = true;
    try {
      if (busy && DateTime.now().difference(_lastFrame) >= probeAfter) {
        await _probe();
      } else if (!busy) {
        turnStalled = false;
        await refreshHealth(notify: false);
        if (_active(rt)) notifyListeners();
      }
    } finally {
      _probing = false;
    }
  }

  Future<void> _probe() async {
    final rt = runtime;
    final Map<String, dynamic> st;
    try {
      st = await rt.call({'command': 'oi_turn_status'}).timeout(probeTimeout);
    } on TimeoutException {
      if (!_active(rt)) return;
      workerUnresponsive = true;
      notifyListeners();
      return;
    } on IntegratedRuntimeException catch (e) {
      if (!_active(rt)) return;
      lastError = e.code;
      notifyListeners();
      return;
    }
    if (!_active(rt)) return;
    workerUnresponsive = false;
    turnStatus = st;
    final t = activeTurnId;
    if (st['busy'] != true && t != null) {
      // The job ended but its turn.finished never arrived: stop waiting, claim nothing about the outcome.
      final m = _byTurn[t];
      m?.streaming = false;
      m?.finishedStatus ??= 'unknown';
      activeTurnId = null;
      turnStalled = false;
      messages.add(OiMessage(
          role: OiRole.system,
          text: 'URI finished this turn but its result did not arrive. Check before repeating any action.'));
    } else {
      final idle = (st['idle_s'] as num?)?.toDouble() ?? 0;
      turnStalled = idle >= stalledAfter.inSeconds;
    }
    notifyListeners();
  }

  /// Explicit user action: end the current worker and start a fresh one.
  /// The interrupted turn is never retried; pending cards lived in the old
  /// worker and are withdrawn (the server's expiry releases them).
  Future<void> restartWorker() async {
    final start = respawn;
    if (start == null || restarting) return;
    restarting = true;
    notifyListeners();
    final t = activeTurnId;
    if (t != null) {
      final m = _byTurn[t];
      m?.streaming = false;
      m?.finishedStatus = 'interrupted';
      final action = m?.route != null && m!.route != 'answer';
      messages.add(OiMessage(
          role: OiRole.system,
          text: action
              ? 'URI was restarted. The interrupted request was not retried and its outcome is unknown: '
                  'check whether the action happened before asking again.'
              : 'URI was restarted. The interrupted request was not retried.'));
    }
    if (pendingApproval != null || pendingConfirmation != null) {
      messages.add(OiMessage(role: OiRole.system, text: 'The open approval was withdrawn by the restart; nothing was approved.'));
    }
    if (_sendingSince != null) {
      messages.add(OiMessage(role: OiRole.system, text: 'A request was still being sent; it was not repeated and may not have started.'));
    }
    // Drafts live in the worker's memory (TI limitation L-7): the new worker has none, so the panel must not keep
    // offering Undo/Redo on a draft that no longer exists.
    if (draft != null) {
      messages.add(OiMessage(role: OiRole.system, text: 'The draft was held by the old worker and is gone after the restart.'));
    }
    draft = null;
    draftQuestion = null;
    draftProgress = 0;
    activeTurnId = null;
    _sendingSince = null;
    pendingApproval = null;
    pendingConfirmation = null;
    await _sub.cancel();
    final old = runtime;
    try {
      await old.kill();
    } catch (_) {}
    IntegratedRuntime? fresh;
    String reason = 'not configured';
    try {
      fresh = await start();
    } on IntegratedRuntimeException catch (e) {
      reason = e.code;
      fresh = null;
    } catch (e) {
      reason = e.runtimeType.toString();
      fresh = null;
    }
    if (fresh == null) {
      lastError = 'WORKER_RESTART_FAILED';
      workerExited = true;
      restarting = false;
      messages.add(OiMessage(role: OiRole.system, text: 'URI could not restart its worker ($reason). Close and reopen the app.'));
      notifyListeners();
      return;
    }
    runtime = fresh;
    _sub = runtime.events.listen(_onEvent);
    workerExited = false;
    workerUnresponsive = false;
    turnStalled = false;
    restarting = false;
    lastError = null;
    _lastFrame = DateTime.now();
    await refreshStatus();
  }

  Future<void> refreshMemory() async {
    if (_disposed) return;
    final rt = runtime;
    try {
      final v = await rt.call({'command': 'memory_list'});
      if (!_active(rt)) return;
      memory = [for (final f in (v['facts'] as List? ?? const [])) if (f is String) f];
    } on IntegratedRuntimeException catch (e) {
      if (!_active(rt)) return;
      lastError = e.code;
    }
    notifyListeners();
  }

  Future<void> refreshCloud() async {
    if (_disposed) return;
    final rt = runtime;
    try {
      final policy = await rt.call({'command': 'cloud_policy'});
      if (!_active(rt)) return;
      cloud = policy;
    } on IntegratedRuntimeException catch (e) {
      if (!_active(rt)) return;
      lastError = e.code;
    }
    notifyListeners();
  }

  /// UIV2-F1: the input mode a turn needs while a draft is open (null when
  /// none is open: routing as before). The draft changes only on explicit
  /// intent: from a surface that does not show it ([draftInView] false:
  /// Companion, dashboard, voice away from the Workspace conversation) a turn
  /// is "command" (the ordinary path, never a draft); in the Workspace it is
  /// "conversation" (default: as if no draft were open) or, when the user set
  /// the composer to the draft, "draft" (an instruction for it).
  String? _draftMode(bool draftInView) {
    final d = draft;
    if (d == null) return null;
    if (!draftInView) return 'command';
    return _draftTargetFor(d) ? 'draft' : 'conversation';
  }

  /// UIV2-F1: the Workspace composer's explicit target while a draft is open.
  /// The conversation by default (nothing can change the draft); the draft
  /// only after the user chose it (composer chip, the draft panel's "Change
  /// with URI" or "Answer"). A new draft starts with the conversation again.
  bool get draftTarget => draft != null && _draftTargetFor(draft!);
  String? _targetDraftId;
  bool _draftTargetFor(OiDraft d) => _targetDraftId != null && _targetDraftId == d.draftId;

  void setDraftTarget(bool toDraft) {
    _targetDraftId = toDraft ? draft?.draftId : null;
    notifyListeners();
  }

  /// Sends the user's words as a turn. Never a decision, whatever it says.
  /// With [transcriptMode] on, the words are sent as a simulated transcript.
  /// [newWork]: a "Start new work" request (C1-02): it may start a new
  /// document but never changes the open draft, whatever the target.
  Future<void> send(String text, {bool draftInView = true, bool newWork = false}) async {
    if (transcriptMode) {
      return sendTranscript(text,
          engine: 'simulated', simulated: true, dictation: dictationMode, draftInView: draftInView);
    }
    if (dictationMode) {
      // Dictation is explicit content the user chose to write; it starts its own draft (the replaced one is kept
      // and Undo brings it back).
      return _turn(text.trim(), {'schema': 'uri.text_input.v1', 'source': 'typed', 'mode': 'dictation'}, 'Dictation');
    }
    final mode = newWork && draft != null ? 'conversation' : _draftMode(draftInView);
    if (mode != null) {
      return _turn(text.trim(), {'schema': 'uri.text_input.v1', 'source': 'typed', 'mode': mode},
          mode == 'draft' ? 'To the draft' : null);
    }
    return _turn(text.trim(), null, null);
  }

  /// Integration point for a speech pipeline (`uri.text_input.v1`). [raw] is
  /// exactly what the recogniser produced; URI keeps it and shows its own
  /// interpretation separately. A real recogniser must name itself in
  /// [engine] and pass `simulated: false`; until one exists only simulated
  /// input is sent.
  Future<void> sendTranscript(
    String raw, {
    required String engine,
    required bool simulated,
    String? language,
    List<String> uncertain = const [],
    bool dictation = false,
    bool draftInView = true,
  }) {
    // The raw transcript is kept byte for byte (contract: turn text == transcript.raw); only emptiness is
    // judged on a trimmed copy.
    final t = raw;
    final mode = dictation ? null : _draftMode(draftInView);
    final input = {
      'schema': 'uri.text_input.v1',
      'source': 'transcript',
      'transcript': {
        'raw': t,
        'engine': engine,
        'simulated': simulated,
        'language': ?language,
        if (uncertain.isNotEmpty) 'uncertain': uncertain,
      },
      if (dictation) 'mode': 'dictation',
      'mode': ?mode,
    };
    final label = simulated ? 'Simulated transcript' : 'Transcript · $engine';
    return _turn(t, input, dictation ? '$label · Dictation' : label);
  }

  Future<void> _turn(String t, Map<String, dynamic>? input, String? label) async {
    // Nothing goes to a worker that is being replaced (WS hardening).
    if (t.trim().isEmpty || busy || restarting) return;
    messages.add(OiMessage(role: OiRole.user, text: t)..inputLabel = label);
    lastError = null;
    draftProgress = 0;
    _sendingSince = DateTime.now();
    _lastFrame = DateTime.now();
    notifyListeners();
    final rt = runtime;
    try {
      final r = await rt.call({
        'command': 'oi_turn',
        'session_id': sessionId,
        'text': t,
        'depth': depth.name,
        'input': ?input,
      });
      // A late reply from a worker that was replaced by Restart URI changes nothing (Codex H-r2).
      if (!identical(rt, runtime)) return;
      _sendingSince = null;
      _begin(r['turn_id'] as String);
    } on IntegratedRuntimeException catch (e) {
      if (!identical(rt, runtime)) return;
      _sendingSince = null;
      lastError = e.code;
      if (e.code == 'WORKER_TIMEOUT') {
        // The worker said nothing for the whole bound: it may or may not have started the turn.
        workerUnresponsive = true;
        messages.add(OiMessage(
            role: OiRole.system,
            text: 'No reply from URI. The request may or may not have started; it was not repeated.'));
      } else {
        messages.add(OiMessage(role: OiRole.system, text: notSentMessage(e.code)));
      }
      notifyListeners();
    }
  }

  void _begin(String turnId) {
    activeTurnId = turnId;
    _lastFrame = DateTime.now();
    _jobs[turnId] = (_jobs[turnId] ?? 0) + 1;
    final m = OiMessage(role: OiRole.uri, text: '', turnId: turnId)..streaming = true;
    messages.add(m);
    _byTurn[turnId] = m;
    for (final ev in _early.remove(turnId) ?? const <Map<String, dynamic>>[]) {
      _onEvent(ev);
    }
    notifyListeners();
  }

  Future<void> cancel() async {
    final t = activeTurnId;
    if (t == null) return;
    try {
      await runtime.call({'command': 'oi_cancel', 'turn_id': t});
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      notifyListeners();
    }
  }

  /// Button-only: approve or deny the card that is shown.
  Future<void> decide({required bool approve}) async {
    final a = pendingApproval;
    // The card's own turn may still be finishing (the worker waits for it); another turn blocks.
    if (a == null || (busy && activeTurnId != a.turnId)) return;
    pendingApproval = null;
    // Active BEFORE the command: the decision's events may arrive right after the reply.
    activeTurnId = a.turnId;
    _jobs[a.turnId] = (_jobs[a.turnId] ?? 0) + 1;
    _byTurn[a.turnId]?.streaming = true;
    notifyListeners();
    try {
      await runtime.call({
        'command': 'oi_decide',
        'turn_id': a.turnId,
        'approve': approve,
        'approval_digest': a.approvalDigest,
      });
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      if (e.code == 'WORKER_TIMEOUT') {
        // Unknown outcome: the worker may have accepted the decision. Stay busy with the job counted and offer no
        // retry; its turn.finished or a worker exit reconciles the state (Codex WS round 3).
        messages.add(OiMessage(role: OiRole.system, text: 'No reply yet from URI for this decision; waiting.'));
        notifyListeners();
        return;
      }
      _jobs[a.turnId] = (_jobs[a.turnId] ?? 1) - 1;
      if ((_finishes[a.turnId] ?? 0) >= (_jobs[a.turnId] ?? 0)) activeTurnId = null;
      _byTurn[a.turnId]?.streaming = false;
      // A definite transient refusal keeps the card; a digest mismatch or a released turn does not.
      if (e.code == 'TURN_IN_PROGRESS') pendingApproval = a;
      messages.add(OiMessage(role: OiRole.system, text: 'Decision refused: ${e.code}'));
    }
    notifyListeners();
  }

  Future<void> confirm() async {
    final c = pendingConfirmation;
    if (c == null || (busy && activeTurnId != c.turnId)) return;
    pendingConfirmation = null;
    activeTurnId = c.turnId;
    _jobs[c.turnId] = (_jobs[c.turnId] ?? 0) + 1;
    _byTurn[c.turnId]?.streaming = true;
    notifyListeners();
    try {
      await runtime.call({'command': 'oi_confirm', 'turn_id': c.turnId});
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      if (e.code == 'WORKER_TIMEOUT') {
        notifyListeners(); // unknown outcome: stay busy, no retry (see decide)
        return;
      }
      _jobs[c.turnId] = (_jobs[c.turnId] ?? 1) - 1;
      if ((_finishes[c.turnId] ?? 0) >= (_jobs[c.turnId] ?? 0)) activeTurnId = null;
      _byTurn[c.turnId]?.streaming = false;
      if (e.code == 'TURN_IN_PROGRESS') pendingConfirmation = c;
    }
    notifyListeners();
  }

  /// Withdraws a pending confirmation or approval (released as a denial).
  Future<void> abandon() async {
    final id = pendingApproval?.turnId ?? pendingConfirmation?.turnId;
    if (id == null) return;
    // A confirmation's "No" is now Core's abandon decision, a short worker job: stay busy until it finishes so
    // the next request is not refused as TURN_IN_PROGRESS (FCVR-01, live). An approval is released at once.
    final viaCore = pendingApproval == null;
    pendingApproval = null;
    pendingConfirmation = null;
    if (viaCore) {
      activeTurnId = id;
      _jobs[id] = (_jobs[id] ?? 0) + 1;
    }
    notifyListeners();
    try {
      final r = await runtime.call({'command': 'oi_abandon', 'turn_id': id});
      if (viaCore && r['accepted'] != true) {
        _jobs[id] = (_jobs[id] ?? 1) - 1;
        if ((_finishes[id] ?? 0) >= (_jobs[id] ?? 0)) activeTurnId = null;
      }
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
      if (viaCore) {
        _jobs[id] = (_jobs[id] ?? 1) - 1;
        if ((_finishes[id] ?? 0) >= (_jobs[id] ?? 0)) activeTurnId = null;
      }
    }
    notifyListeners();
  }

  Future<void> selectBrain(String rowId) async {
    if (busy) return;
    try {
      await runtime.call({'command': 'brain_select', 'row_id': rowId});
    } on IntegratedRuntimeException catch (e) {
      lastError = e.code;
    }
    await refreshStatus();
  }

  void setTranscriptMode(bool on) {
    transcriptMode = on;
    notifyListeners();
  }

  void setDictationMode(bool on) {
    dictationMode = on;
    notifyListeners();
  }

  /// Deterministic draft operation from a button: undo, redo, restore
  /// (with [version]) or discard. No model call; nothing is sent or saved.
  Future<void> draftOp(String op, {int? version}) async {
    if (draftActionsBlocked) return;
    final rt = runtime;
    try {
      final r = await rt.call({
        'command': 'draft_op',
        'session_id': sessionId,
        'op': op,
        'version': ?version,
      });
      if (!identical(rt, runtime)) return; // late reply from a replaced worker (WS hardening)
      draft = OiDraft.parse(r['draft']);
      draftQuestion = draft?.pendingQuestion;
      lastError = null;
    } on IntegratedRuntimeException catch (e) {
      if (!identical(rt, runtime)) return;
      lastError = e.code;
    }
    notifyListeners();
  }

  Future<void> refreshDraft() async {
    if (_disposed || restarting || workerExited) return;
    final rt = runtime;
    try {
      final r = await rt.call({'command': 'draft_get', 'session_id': sessionId});
      if (!_active(rt)) return;
      draft = OiDraft.parse(r['draft']);
      draftQuestion = draft?.pendingQuestion;
    } on IntegratedRuntimeException catch (e) {
      if (!_active(rt)) return;
      lastError = e.code;
    }
    notifyListeners();
  }

  void setDepth(OiDepth d) {
    depth = d;
    notifyListeners();
    onDepthChanged?.call(d);
  }

  // ---- Brain Quick Controls (BRAIN-QC-20261018) ---------------------------

  /// The worker's Quick Controls state (`brain_health.controls`), or empty
  /// when this worker does not offer them. `active` is set only after the
  /// worker verified the running Brain against that profile.
  Map<String, dynamic> get brainControls =>
      (brainHealth['controls'] as Map?)?.cast<String, dynamic>() ?? const {};

  /// Tier (FAST / NORMAL) the latest URI answer actually used, from its
  /// `turn.tier` event: what Thinking did, not what was asked.
  String? get lastAnswerTier {
    for (final m in messages.reversed) {
      if (m.role == OiRole.uri && m.tier != null) return m.tier;
    }
    return null;
  }

  /// The id of the switch this UI requested (its outcome is shown once).
  String? profileRequestId;

  /// Plain-words outcome of the latest refused switch request, or null. It
  /// is shown for [profileNoticeFor] and then clears (review R1-08.1).
  String? get profileNotice {
    final at = _profileNoticeAt;
    if (_profileNotice == null || at == null) return null;
    return DateTime.now().difference(at) > profileNoticeFor ? null : _profileNotice;
  }

  set profileNotice(String? v) {
    _profileNotice = v;
    _profileNoticeAt = v == null ? null : DateTime.now();
  }

  String? _profileNotice;
  DateTime? _profileNoticeAt;
  static Duration profileNoticeFor = const Duration(seconds: 20);

  /// Explicit user action: switch the Brain to a qualified profile (Vision /
  /// Context). Returns the worker's reply. A context the conversation would
  /// not fit in is refused by the worker (`refused`, review R1-02); refusals
  /// are reported in [profileNotice].
  Future<Map<String, dynamic>?> reconfigureBrain(String profileId) async {
    if (busy || restarting || workerExited) return null;
    final rt = runtime;
    try {
      final r = await rt.call({'command': 'brain_reconfigure', 'profile_id': profileId});
      if (!_active(rt)) return null;
      lastError = null;
      profileNotice = null;
      if (r['requested'] == 'reconfigure') profileRequestId = r['request_id'] as String?;
      if (r['refused'] == 'CONTEXT_SMALLER_THAN_CONVERSATION') {
        final d = (r['detail'] as Map?) ?? const {};
        final ctx = (d['ctx'] as num?)?.toInt();
        // R2-02: the worker judges the longest conversation it has held since it started, not only this one.
        profileNotice = 'Not switched: a conversation URI has held since it started uses about '
            '${d['live_tokens'] ?? '?'} tokens; with room for an answer it does not fit in '
            '${ctx == null ? 'the smaller context' : '${ctx ~/ 1024}K'}. Keep the larger context until URI is restarted.';
      }
      await refreshHealth();
      return r;
    } on IntegratedRuntimeException catch (e) {
      if (!_active(rt)) return null;
      profileNotice = brainSwitchRefusal(e.code);
      notifyListeners();
      return null;
    }
  }

  // ---- events -----------------------------------------------------------

  void _onEvent(Map<String, dynamic> ev) {
    if (_disposed) return;
    if (ev['schema'] == assistEventSchema) {
      // A research job's progress must not make a silent OI turn look alive.
      if (!_assistEvents.isClosed) _assistEvents.add(ev);
      return;
    }
    final type = ev['type'];
    _lastFrame = DateTime.now();
    if (workerUnresponsive || turnStalled) {
      workerUnresponsive = false;
      turnStalled = false;
    }
    if (type == 'worker.exited') {
      workerExited = true;
      activeTurnId = null;
      companionState = 'error';
      lastError = 'WORKER_EXITED';
      notifyListeners();
      return;
    }
    final turnId = ev['turn_id'] as String?;
    final data = (ev['data'] as Map?)?.cast<String, dynamic>() ?? const {};
    final m = turnId == null ? null : _byTurn[turnId];
    if (m == null && turnId != null && type != 'brain.status') {
      final q = _early.putIfAbsent(turnId, () => []);
      if (q.length < 2000) q.add(ev);
      while (_early.length > 8) {
        _early.remove(_early.keys.first);
      }
      return;
    }
    switch (type) {
      case 'companion.state':
        final state = data['state'] as String? ?? 'idle';
        // A "waiting for you" of a turn whose handoff produced nothing is ignored: there is nothing to decide, and
        // it must not replace another turn's real wait (INT-F1).
        if (!(state == 'waiting_user' && turnId != null && _handoffsWithoutProposal.contains(turnId))) {
          companionState = state;
          if (turnId != null) {
            // Which turns wait for the user, so a failed handoff removes only its own wait (Codex INT-F1 r4).
            if (state == 'waiting_user') {
              _waitingTurns.add(turnId);
              while (_waitingTurns.length > 16) {
                _waitingTurns.remove(_waitingTurns.first);
              }
            } else {
              _waitingTurns.remove(turnId);
            }
          }
        }
      case 'turn.routed':
        m?.route = data['route'] as String?;
        m?.tier = ((data['tier'] as Map?)?['tier']) as String?;
      case 'draft.updated':
        final d = data['draft'];
        draft = d == null ? null : (OiDraft.parse(d) ?? draft);
        draftQuestion = draft?.pendingQuestion;
      case 'draft.clarify':
        draftQuestion = data['question'] as String?;
        draftQuestionIsNew = data['draft'] == null && draft != null && draftQuestion != null;
        if (data['draft'] != null) draft = OiDraft.parse(data['draft']) ?? draft;
      case 'draft.progress':
        draftProgress = (data['chars'] as num?)?.toInt() ?? 0;
        m?.draftChars = draftProgress;
      case 'thinking.progress':
        m?.thinkingChars = (data['chars'] as num?)?.toInt() ?? 0;
      case 'answer.delta':
        m?.text += data['text'] as String? ?? '';
      case 'answer.done':
        m?.answerStatus = data['status'] as String?;
        m?.flags = [for (final f in (data['flags'] as List? ?? const [])) '$f'];
        m?.metrics = (data['metrics'] as Map?)?.cast<String, dynamic>() ?? const {};
      case 'core.result':
        m?.coreCode = data['code'] as String?;
        m?.coreMessage = data['message'] as String?;
        if (data['needs'] == 'confirmation' && turnId != null) {
          pendingConfirmation = OiConfirmation(
            turnId: turnId,
            message: data['message'] as String?,
            data: (data['confirmation'] as Map?)?.cast<String, dynamic>() ?? const {},
          );
        }
      case 'core.outcome':
        final summary = data['summary'];
        if (summary is String && summary.isNotEmpty && m?.coreCode == 'SETTLED_VERIFIED') {
          m?.outcomeSummary = summary;
        }
      case 'approval.required':
        if (turnId != null) {
          pendingApproval = OiApproval(
            turnId: turnId,
            capabilityId: data['capability_id'] as String? ?? '?',
            arguments: (data['arguments'] as Map?)?.cast<String, dynamic>() ?? const {},
            approvalDigest: data['approval_digest'] as String? ?? '',
            effect: data['effect'] as String?,
            reversible: data['reversible'] as bool?,
          );
        }
      case 'error':
        m?.errorCode = data['code'] as String?;
        m?.errorMessage = data['message'] as String?;
        m?.recoveryOptions = [for (final o in (data['recovery_options'] as List? ?? const [])) '$o'];
      case 'brain.status':
        brainStatus = {...brainStatus, ...data};
      case 'turn.finished':
        m?.finishedStatus = data['status'] as String?;
        final done = (_finishes[turnId!] ?? 0) + 1;
        _finishes[turnId] = done;
        if (done >= (_jobs[turnId] ?? 0)) {
          m?.streaming = false;
          if (activeTurnId == turnId) activeTurnId = null;
        }
        // Memory may have changed after an approved action: re-read it (deterministic).
        if (m?.coreCode == 'SETTLED_VERIFIED') unawaited(refreshMemory());
      case 'a2ui.handoff':
        // The turn travels with the handoff so a failed proposal can clear that turn's waiting state (INT-F1).
        _a2uiHandoffs.add({...data, 'turn_id': turnId});
        // A handoff is a new request: the worker dropped any open draft question, so the panel stops showing it
        // (Codex TIWS r11).
        if (draftQuestion != null) {
          draftQuestion = null;
          notifyListeners();
        }
        return;
      default:
        return; // unknown types are ignored (contract rule)
    }
    notifyListeners();
  }

  /// The A2UI hub could not turn the handoff of [turnId] into a proposal
  /// (INT-F1): that turn's "waiting for you" does not hold, since there is
  /// nothing to decide. Order-independent: the worker's `companion.state`
  /// for that turn may arrive before or after the hub's failure.
  void handoffProducedNothing(String? turnId) {
    if (turnId == null) return;
    _handoffsWithoutProposal.add(turnId);
    while (_handoffsWithoutProposal.length > 16) {
      _handoffsWithoutProposal.remove(_handoffsWithoutProposal.first);
    }
    if (_waitingTurns.remove(turnId) && companionState == 'waiting_user') {
      // Another turn that still waits keeps "needs you"; otherwise nothing is left to decide.
      if (_waitingTurns.isEmpty) companionState = 'idle';
      notifyListeners();
    }
  }

  final Set<String> _handoffsWithoutProposal = <String>{}; // insertion-ordered, bounded
  final Set<String> _waitingTurns = <String>{}; // insertion-ordered, bounded

  @override
  void dispose() {
    _disposed = true;
    _monitor?.cancel();
    _sub.cancel();
    _a2uiHandoffs.close();
    _assistEvents.close();
    super.dispose();
  }
}

String _uuid4() {
  final r = Random.secure();
  final b = List<int>.generate(16, (_) => r.nextInt(256));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  String h(int i) => b[i].toRadixString(16).padLeft(2, '0');
  final s = List.generate(16, h).join();
  return '${s.substring(0, 8)}-${s.substring(8, 12)}-${s.substring(12, 16)}-${s.substring(16, 20)}-${s.substring(20)}';
}
