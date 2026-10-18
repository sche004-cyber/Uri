"""Integrated worker bridge: Operational Intelligence turns served over the client worker's framed stdio
(WS blueprint W1, owner decision WS-D1).

The accepted supervised worker answers one request with one reply. This bridge adds STREAMED event frames for OI
turns. The protocol keeps its existing guarantees:

  * Replies keep the accepted shape, `{"result": "OK"|"REFUSED", ...}`, and are written in request order.
  * Events are separate frames, `{"event": <uri.oi.event.v1>}`. A reader matches replies FIFO and routes event frames
    by `turn_id`. All frames go through ONE write lock, so frames never interleave.
  * An OI turn runs on a background thread. The command that starts it replies at once with the turn id. Events
    follow, and the stream ends with `turn.finished` and a final `companion.state`.
  * Core envelopes stay in this process. The UI refers to a turn only by id. An approval is accepted only as a
    structured `oi_decide` that echoes the `approval_digest` the card displayed; a mismatch drops the pending turn
    (same rule as the accepted `turn_decide`). Typed text never reaches a decision path.
  * One OI job at a time per worker. While a job runs, the integrated worker refuses commands that use the same
    runner or stores (`busy`). Status, catalog and cancel stay open.
  * The Brain selection changes only through `brain_select` with a catalog row id. A model or a turn cannot change
    it.
  * Health (WS hardening): `brain_health` reports READY / BUSY / DEGRADED / UNAVAILABLE / RECOVERING from the accepted
    readiness, the Brain host report and the timings of real turns. `brain_restart` asks the Brain host for an
    explicit restart / stop / start and is refused while a turn runs. `oi_turn_status` tells the UI whether the
    running job is alive and how long it has been silent, so an alive-but-silent worker can be told apart from an
    unresponsive one (R-BUSY).
  * Brain Quick Controls (BRAIN-QC-20261018): `brain_health` also carries `controls` (the Vision / Context profile
    choices, which one the worker has VERIFIED as serving, and any switch in flight). `brain_reconfigure` asks the
    Brain host for a controlled switch to a qualified profile (brain_quick_controls.CATALOG); it is refused while a
    turn runs, and the conversation history kept here is not touched by it (the worker keeps running).
"""
from __future__ import annotations

import threading
import time
import uuid
from collections import deque

from . import brain_catalog
from . import brain_health
from . import brain_quick_controls as QC
from . import runtime_profiles as RP
from . import cloud_policy
from . import schedule_intent
from . import text_input as TI
from . import text_intent as TX
from .draft_desk import DeskError, DraftDesk
from .events import EventSink
from .perf_monitor import PerfMonitor

COMMANDS = {
    "oi_turn": ({"command", "session_id", "text", "depth"}, {"command", "session_id", "text", "depth", "input"}),
    "oi_cancel": ({"command", "turn_id"},),
    "oi_confirm": ({"command", "turn_id"},),
    "oi_decide": ({"command", "turn_id", "approve", "approval_digest"},),
    "oi_abandon": ({"command", "turn_id"},),
    "brain_status": ({"command"},),
    "brain_catalog": ({"command"},),
    "brain_select": ({"command", "row_id"},),
    "memory_list": ({"command"},),
    "cloud_policy": ({"command"},),
    "brain_health": ({"command"},),
    "brain_restart": ({"command", "action"},),
    "brain_reconfigure": ({"command", "profile_id"},),
    "oi_turn_status": ({"command"},),
    # Text intelligence: read the session's draft; deterministic draft operations (no model, no authority).
    "draft_get": ({"command", "session_id"},),
    "draft_op": ({"command", "session_id", "op"}, {"command", "session_id", "op", "version"}),
}
OPEN_WHILE_BUSY = {"oi_cancel", "brain_status", "brain_catalog", "cloud_policy", "brain_health",
                   "oi_turn_status", "draft_get"}
PERF_SAMPLES = 48
# A Brain restart/stop request blocks new turns until the host has acted on it (Codex H-r1 F2): the busy check and
# the request are made on the worker's single command thread, and no turn can start between them or after them while
# the host has not finished. Bounded: a host that never answers releases the gate after this long.
RESTART_GATE_S = 600.0
DRAFT_OPS = ("undo", "redo", "restore", "discard")
# A decision on the turn whose job is still finishing (the card is shown by an event the job emits before it records
# the continuation) waits for that job instead of being refused (Codex WS round 1, F1).
CONTINUATIONS = {"oi_decide", "oi_confirm", "oi_abandon"}
JOIN_S = 30.0
DEPTHS = ("auto", "fast", "normal", "deep")
MAX_TEXT = 20000
MAX_HISTORY = 24
MAX_PENDING = 64
# Room kept for the next answer when judging whether a conversation fits a smaller context: the largest local output
# cap (reasoning_policy MAX_TOKENS["normal"] = 4,000) rounded up. A heuristic, not a guarantee: the next user message
# (up to MAX_TEXT characters) is not counted. The check covers every session this worker has answered since it started
# (sizes are never cleared except by LRU eviction beyond MAX_PENDING = 64 sessions; the worker keeps their history
# too), so it is conservative (review R2-02, R3-03).
ANSWER_RESERVE_TOKENS = 4096


class BridgeRefused(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class _Rerouted:
    """The draft desk handed its turn to the ordinary path (the Brain said the message is not a draft edit). The
    turn already started, so the orchestrator's second `turn.started` is dropped and its `turn.routed` says where it
    came from: the UI sees one turn, re-routed, with one `turn.finished`."""

    def __init__(self, inner):
        self.inner = inner

    @property
    def events(self):
        return self.inner.events

    def emit(self, turn_id, type_, **data):
        if type_ == "turn.started":
            return None
        if type_ == "turn.routed":
            data.setdefault("rerouted_from", "draft")
        return self.inner.emit(turn_id, type_, **data)


def completion_outcome(request_env: dict, env: dict, before, after):
    """What actually happened after an approval, in plain words (FCV UX-D).

    Only Core's verified settlement of a remember_fact request is described: Core settles it as verified only after
    the client runtime read the new fact back from the client store. The saved text comes from that same store
    (facts present after and not before), never from the request. Anything else keeps Core's own message.
    """
    if env.get("code") != "SETTLED_VERIFIED" or env.get("state") != "reply":
        return None
    capability = (request_env.get("approval_request") or {}).get("capability_id")
    if capability != "remember_fact":
        return None
    saved = [f for f in (after or []) if before is not None and f not in before]
    if before is None or after is None:
        summary = ("Saved to URI's memory on this computer, and read back from the memory store to check it. "
                   "URI could not list the store just now, so it cannot show the saved text here.")
    elif saved:
        quoted = "; ".join("\u201c%s\u201d" % f for f in saved[:3])
        summary = ("Saved to URI's memory on this computer: %s. URI read it back from the memory store to check "
                   "it was stored." % quoted)
    else:
        summary = ("Saved to URI's memory on this computer, and read back from the memory store to check it. "
                   "No new entry appeared in the list, so it may already have been there.")
    return {"capability_id": capability, "summary": summary, "saved": saved[:3], "read_back": True}


def _is_uuid(value) -> bool:
    try:
        return isinstance(value, str) and str(uuid.UUID(value)) == value.lower()
    except ValueError:
        return False


def valid(kind, command) -> bool:
    return kind in COMMANDS and any(set(command) == shape for shape in COMMANDS[kind])


class _NotSelected:
    state = "NOT_SELECTED"
    detail = "No Brain is selected; the deterministic source does not answer open questions."


def assist_state_of(assist) -> dict:
    """Closure D2/D6: what the Quick Controls need from URI Assist. `granted` is true for any held grant, ACTIVE or
    PAUSED (review QCC-R1-02): a paused session can resume at any moment, so vision stays."""
    return {"asking": bool(assist.asking), "granted": assist.access.snapshot().get("state") != "OFF"}


class IntegratedTurns:
    def __init__(self, *, orchestrator, cfg, status, write_event, memory=None, cloud=None, defer_start=False,
                 host_report=None, host_request=None):
        """
        orchestrator: an OI Orchestrator whose `core` is the paired Core gateway for this client.
        cfg:          the frozen Runtime v1 configuration (already loaded).
        status:       callable -> runtime_v1.Readiness (read-only; never starts the runtime).
        write_event:  callable(dict) that writes ONE event frame under the worker's write lock.
        memory:       callable() -> list of remembered facts (deterministic client read), or None.
        defer_start:  a started job waits for `release()`, which the worker calls right AFTER it wrote the reply.
                      The reply that carries the turn id therefore always precedes the turn's first event frame.
        host_report:  callable() -> (Brain host report | None, host_alive) (read-only), or None without a host.
        host_request: callable(action) that writes one explicit request for the Brain host, or None.
        """
        self.o, self.cfg, self._status, self._write = orchestrator, cfg, status, write_event
        self._memory, self.cloud = memory, cloud or cloud_policy.CloudSpendPolicy()
        self.o.remembered_facts = memory  # same consented client store used by Settings; no second store/cache
        self.selected = brain_catalog.runtime_v1_selection(cfg)          # Runtime v1 is the default Brain
        self.o.brain_selection = dict(self.selected)
        self._readiness_for_orchestrator()
        self._lock = threading.Lock()
        self._job = None              # (turn_id, thread) of the running job
        self._defer = defer_start
        self._go = None               # threading.Event the deferred job waits on
        self.closing = False          # set by the worker's shutdown: late continuations are released, not kept
        self.pending = {}             # oi turn_id -> {"env", "text", "session_id"} (Core turn awaiting the user)
        self.history = {}             # session_id -> [{"role", "content"}] (answer-channel context, bounded)
        self._host_report, self._host_request = host_report, host_request
        self._perf = deque(maxlen=PERF_SAMPLES)     # (wall time, llama-server timings) of finished answers
        self._job_started = None      # monotonic start of the running job
        self._last_event = None       # monotonic time of the job's last event frame
        self._job_events = 0
        self._restart = None          # {"id", "t", "until"} of a Brain request the host has not finished
        self._switch = None           # {"id", "to", "label", "t"} of a profile switch the host has not finished
        # Tokens of each session's last answer context (prompt + cache + answer), and the session of each turn id.
        self._context_tokens = {}
        self._turn_session = {}
        self._perf_ident = None       # (pid, create_time) of the server the timing samples belong to
        self.desk = DraftDesk(orchestrator)   # text intelligence: drafts per session (language work only)

    # ---- state ---------------------------------------------------------------------------------
    @property
    def busy(self):
        with self._lock:
            return self._job is not None and self._job[1].is_alive()

    def _readiness_for_orchestrator(self):
        if self.selected.get("provider") == brain_catalog.DETERMINISTIC["provider"]:
            self.o.readiness = lambda: _NotSelected()
        else:
            self.o.readiness = self._status

    # ---- dispatch ------------------------------------------------------------------------------
    def handle(self, kind, command):
        if not valid(kind, command):
            raise BridgeRefused("COMMAND_SCHEMA")
        if kind in CONTINUATIONS:
            job = self._job
            if job is not None and job[0] == command["turn_id"] and job[1].is_alive():
                job[1].join(JOIN_S)
        if kind not in OPEN_WHILE_BUSY and self.busy:
            raise BridgeRefused("TURN_IN_PROGRESS")
        if kind == "oi_turn" and self._restart_pending():
            raise BridgeRefused("BRAIN_RESTARTING")
        return getattr(self, "_" + kind)(command)

    def _restart_pending(self):
        """Open the gate only on positive evidence (Codex H-r2): the host marked THIS request DONE, or a readable
        report names a host process that no longer exists, or the bounded gate expired. An unreadable report keeps
        the gate closed."""
        r = self._restart
        if r is None:
            return False
        host, alive = self._host()
        result = ((host or {}).get("requests") or {}).get(r["id"])
        done = (time.time() > r["until"]
                or (host is not None and alive is False)
                or result in ("DONE", "IGNORED_INVALID_OR_STALE")
                or (isinstance(result, str) and result.startswith("REFUSED_")))
        if done:
            self._restart = None
            if self._switch is not None and self._switch.get("id") == r["id"]:
                self._switch = None
        return not done

    def _start(self, turn_id, fn):
        with self._lock:
            if self._job is not None and self._job[1].is_alive():
                raise BridgeRefused("TURN_IN_PROGRESS")
            go = threading.Event()
            if not self._defer:
                go.set()

            def gated():
                go.wait()
                fn()
            t = threading.Thread(target=gated, name="oi-turn-" + turn_id[:8], daemon=True)
            self._job, self._go = (turn_id, t), go
            self._job_started = self._last_event = time.monotonic()
            self._job_events = 0
        t.start()
        return t

    def begin_close(self):
        """Shutdown step 1: from now on a continuation is released instead of kept (atomic with _remember)."""
        with self._lock:
            self.closing = True

    def release(self):
        """Let a deferred job run (the worker calls this after writing the reply)."""
        go = self._go
        if go is not None:
            go.set()

    def wait(self, timeout=None):
        """Test helper: join the running job."""
        job = self._job
        if job is not None:
            job[1].join(timeout)

    def _sink(self, turn_id):
        """Every event of a job is keyed by the OI turn id the UI holds. The orchestrator's single-turn
        confirm()/decide() emit under Core's turn id; the UI never sees that id, so it is moved into the data."""
        def forward(ev):
            if ev["turn_id"] != turn_id:
                ev["data"] = dict(ev["data"], core_turn_id=ev["turn_id"])
                ev["turn_id"] = turn_id
            self._last_event = time.monotonic()
            self._job_events += 1
            if ev["type"] == "answer.done":
                m = ev["data"].get("metrics") or {}
                ctx_n = sum(int(m.get(k) or 0) for k in ("prompt_n", "cache_n", "predicted_n"))
                if ctx_n:
                    sid = self._turn_session.get(turn_id)
                    self._context_tokens.pop(sid, None)          # re-insert: the dict order is least recently used
                    self._context_tokens[sid] = ctx_n
                    while len(self._context_tokens) > MAX_PENDING:
                        self._context_tokens.pop(next(iter(self._context_tokens)))
                if m.get("predicted_n") and m.get("predicted_per_second"):
                    self._perf.append((time.time(), {"predicted_n": m["predicted_n"],
                                                     "predicted_per_second": m["predicted_per_second"]}))
            self._write(ev)
        return EventSink(callback=forward)

    # ---- turns ---------------------------------------------------------------------------------
    def _oi_turn(self, c):
        text, session_id, depth = c["text"], c["session_id"], c["depth"]
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            raise BridgeRefused("TEXT_INVALID")
        if not _is_uuid(session_id):
            raise BridgeRefused("SESSION_INVALID")      # Core binds turns to UUID session ids
        if depth not in DEPTHS:
            raise BridgeRefused("DEPTH_INVALID")
        try:
            inp = TI.parse(c.get("input"), text)
        except TI.InputRejected as exc:
            raise BridgeRefused(exc.code) from None
        turn_id = str(uuid.uuid4())
        self._turn_session[turn_id] = session_id
        while len(self._turn_session) > MAX_PENDING:
            self._turn_session.pop(next(iter(self._turn_session)))
        history = list(self.history.get(session_id, ()))
        # A transcript reaches the ordinary path with fillers removed; the raw transcript stays in the envelope.
        plain = TI.clean_transcript(text) if inp.is_transcript else text
        with self._lock:
            clarifications = {tid: p for tid, p in self.pending.items()
                              if p["session_id"] == session_id and p["env"].get("clarification")
                              and not p["env"].get("confirmation")
                              and p["env"].get("state") != "approval_required"}
        continue_core = bool(clarifications) and inp.mode != "dictation"
        if continue_core and len(clarifications) != 1:
            # No arbitrary selection or bulk retirement of independent cards. Keep all records and let the
            # caller surface the ambiguous state; nothing reaches a model, Core continuation or decision.
            raise BridgeRefused("CLARIFICATION_STATE_AMBIGUOUS")

        def ordinary(sink, request=None):
            words = request if request is not None else plain
            out = self.o.handle_turn(words, session_id, depth=depth, history=history, sink=sink, turn_id=turn_id,
                                     core_clarification=continue_core)
            out.events = getattr(sink, "events", out.events)
            if continue_core and out.core is not None:
                # Core returned the replacement state. Retire only the questions it continued; never an
                # approval or confirmation. On transport failure retain the question for an explicit retry.
                with self._lock:
                    for tid, old in clarifications.items():
                        if self.pending.get(tid) is old:
                            self.pending.pop(tid)
            self._remember(turn_id, session_id, words, out.core, out.status)
            answer = (out.answer or {}).get("text")
            self._record_history(session_id, words, answer if out.status in ("ok", "incomplete") else None)
            return out

        # A2UI slice (docs/a2ui/A2UI_ARCHITECTURE.md): a festival-greeting scheduling request is handed to the
        # scheduler, which proposes and renders an editable surface. No authority is exercised here.
        # Combined with text intelligence: the interpreter reads the cleaned transcript (`plain`); dictated content is
        # never handed off (TI L-2: dictation is content); a handoff ends an open draft question like any new request.
        handoff = schedule_intent.interpret(plain) if inp.mode != "dictation" and not continue_core else None
        if handoff is not None:
            self.desk.drop_open_question(session_id)
            self._start(turn_id, lambda: self._a2ui_handoff(turn_id, session_id, plain, handoff))
            return {"turn_id": turn_id, "accepted": True, "selection": self.selected}

        def run():
            sink = self._sink(turn_id)
            try:
                if continue_core:
                    self.desk.drop_open_question(session_id)
                    ordinary(sink)
                    return
                # L-2: explicit modes. "command" is an instruction for the ordinary path (intent discovery, Core,
                # approvals) and never a draft; "dictation" is content and never reaches Core.
                if inp.mode == "command":
                    self.desk.drop_open_question(session_id)
                    ordinary(sink)
                    return
                if inp.mode == "dictation":
                    self.desk.drop_open_question(session_id)
                    intent = TX.TextIntent(TX.REWRITE if inp.scope == "rewrite" else TX.CORRECT, ["dictation_mode"],
                                           payload=plain, instruction=plain)
                # UIV2-F1 (c4 R2-01): an explicit target is honoured at every depth. Deep keeps routing ordinary
                # requests through the ordinary path; it never bypasses the target the user chose.
                elif inp.mode == "conversation":
                    intent = self.desk.classify_conversation(plain, session_id)
                elif inp.mode == "draft":
                    intent = self.desk.classify_draft_target(plain, session_id)
                else:
                    intent = self.desk.classify(plain, session_id) if depth != "deep" else None
                if intent is not None and intent.reasons[:1] == ["ambiguity_action"]:
                    # The user chose "do it": the ORIGINAL request goes to the ordinary path; Core decides.
                    ordinary(sink, request=TI.clean_transcript(intent.payload))
                    return
                if intent is not None and intent.is_text_task:
                    fb = None if inp.mode == "dictation" else \
                        (lambda: dict(ordinary(_Rerouted(sink)).__dict__, delegated=True))
                    out = self.desk.handle(turn_id, text, session_id, intent, inp, sink, fallback=fb)
                    if not out.get("delegated"):
                        cur = (out.get("draft") or {}).get("current") or {}
                        note = ("[Draft version %s]\n%s" % (cur.get("n"), cur.get("text", "")))[:2000] if cur \
                            else out.get("question")
                        self._record_history(session_id, plain, note)
                    return
                ordinary(sink)
            except Exception as exc:          # never leave the UI waiting: close the stream as an error
                self._fail(sink, turn_id, exc)
                return

        self._start(turn_id, run)
        return {"turn_id": turn_id, "accepted": True, "selection": self.selected}

    def _a2ui_handoff(self, turn_id, session_id, text, handoff):
        sink = self._sink(turn_id)
        emit = lambda t, **d: sink.emit(turn_id, t, **d)   # noqa: E731
        # The scheduler (the domain authority) builds the proposal after this reply, in the UI's A2UI hub; the reply
        # must not claim it exists yet (INT-F1, final integration 2026-10-10: with no scheduler the UI said both
        # "prepared" and "could not be prepared").
        reply = ("I'll try to prepare a festival GIF schedule for you to review; it appears here if the scheduler "
                 "accepts the request. Nothing runs until you confirm it.")
        emit("turn.started", text_chars=len(text), depth="auto")
        emit("turn.routed", route="a2ui", triage={"kind": "SCHEDULE_REQUEST", "interpreter": handoff["interpreter"]},
             tier={"tier": "NONE", "selected_by": "deterministic", "reason": "no model call"})
        emit("a2ui.handoff", **handoff)
        emit("answer.delta", text=reply)
        emit("answer.done", status="COMPLETE", complete=True, escalation_candidate=False, flags=[], metrics={})
        emit("turn.finished", status="ok", route="a2ui", total_s=0)
        emit("companion.state", state="waiting_user")
        self._record_history(session_id, text, reply)

    def _remember(self, turn_id, session_id, text, env, status):
        if env is not None and status == "needs_user":
            entry = {"env": env, "text": text, "session_id": session_id}
            with self._lock:      # the same lock begin_close() takes: no card can slip in after the shutdown sweep
                closing = self.closing
                if not closing:
                    self.pending[turn_id] = entry
                    while len(self.pending) > MAX_PENDING:
                        self.pending.pop(next(iter(self.pending)))
            if closing and env.get("state") == "approval_required":
                # The worker is shutting down: nobody can decide this card. Release it as a denial now (CAP-1).
                self._release(entry)

    def _record_history(self, session_id, user_text, answer_text):
        h = self.history.setdefault(session_id, [])
        h.append({"role": "user", "content": user_text})
        if answer_text:
            h.append({"role": "assistant", "content": answer_text})
        del h[:-MAX_HISTORY]

    def _fail(self, sink, turn_id, exc):
        sink.emit(turn_id, "error", code="TURN_FAILED", message=type(exc).__name__, recoverable=True,
                  recovery_options=["retry"])
        sink.emit(turn_id, "turn.finished", status="error", route="unknown", total_s=0)
        sink.emit(turn_id, "companion.state", state="error")

    def _oi_cancel(self, c):
        return {"cancelled": bool(self.o.cancel(c["turn_id"], "user"))}

    def _take(self, turn_id, need):
        with self._lock:
            p = self.pending.get(turn_id)
            if p is None:
                raise BridgeRefused("TURN_NOT_PENDING")
            env = p["env"]
            has = ("approval" if env.get("state") == "approval_required" else
                   "confirmation" if env.get("confirmation") else
                   "clarification" if env.get("clarification") else "none")
            if has != need:
                raise BridgeRefused("TURN_NEEDS_" + has.upper())
            return self.pending.pop(turn_id)

    def _oi_confirm(self, c):
        turn_id = c["turn_id"]
        p = self._take(turn_id, "confirmation")

        def run():
            sink = self._sink(turn_id)
            try:
                sink.emit(turn_id, "companion.state", state="thinking")
                out = self.o.confirm(p["session_id"], p["env"], sink=sink)
            except Exception as exc:
                self._fail(sink, turn_id, exc)
                return
            self._remember(turn_id, p["session_id"], p["text"], out.core, out.status)
            sink.emit(turn_id, "turn.finished", status=out.status, route=out.route, total_s=out.total_s)
            sink.emit(turn_id, "companion.state", state="waiting_user" if out.status == "needs_user" else
                      ("error" if out.status == "error" else "idle"))

        self._start(turn_id, run)
        return {"turn_id": turn_id, "accepted": True}

    def _oi_decide(self, c):
        turn_id, approve, digest = c["turn_id"], c["approve"], c["approval_digest"]
        if not isinstance(approve, bool):
            raise BridgeRefused("APPROVE_NOT_BOOLEAN")
        p = self._take(turn_id, "approval")
        shown = (p["env"].get("approval_request") or {}).get("approval_digest")
        if not isinstance(digest, str) or digest != shown:
            # The card the user saw is not the request Core holds: drop it and release the server turn as a denial.
            self._release(p)
            raise BridgeRefused("APPROVAL_DIGEST_MISMATCH")

        def run():
            sink = self._sink(turn_id)
            try:
                sink.emit(turn_id, "companion.state", state="thinking")
                before = self._facts() if approve else None
                env = self.o.decide(p["text"], p["session_id"], p["env"], approve, sink=sink)
            except Exception as exc:
                self._fail(sink, turn_id, exc)
                return
            outcome = completion_outcome(p["env"], env, before, self._facts()) if approve else None
            if outcome:
                sink.emit(turn_id, "core.outcome", **outcome)
            from .orchestrator import core_needs, core_turn_status
            status = core_turn_status(env, core_needs(env))
            sink.emit(turn_id, "turn.finished", status=status, route="core", total_s=0)
            sink.emit(turn_id, "companion.state", state="error" if status == "error" else "idle")

        self._start(turn_id, run)
        return {"turn_id": turn_id, "accepted": True, "approve": approve}

    def _release(self, p):
        try:
            self.o.core.decide(p["text"], p["session_id"], self.o.brain_selection, p["env"], False)
        except Exception:
            pass        # the server's own idle expiry is the backstop

    def _oi_abandon(self, c):
        turn_id = c["turn_id"]
        with self._lock:
            p = self.pending.pop(turn_id, None)
        if p is None:
            raise BridgeRefused("TURN_NOT_PENDING")
        if p["env"].get("state") == "approval_required":
            self._release(p)
            return {"abandoned": True}
        if not (p["env"].get("confirmation") or p["env"].get("clarification")):
            return {"abandoned": True}

        def run():
            # FCVR-01: dropping the card locally left Core's intent open, so every later action request in the
            # session was answered with that old request. "No" now reaches Core as its structured abandon.
            sink = self._sink(turn_id)
            try:
                env = self.o.abandon(p["session_id"], p["env"], sink=sink)
            except Exception as exc:
                self._fail(sink, turn_id, exc)
                return
            from .orchestrator import core_needs, core_turn_status
            status = core_turn_status(env, core_needs(env))
            sink.emit(turn_id, "turn.finished", status=status, route="core", total_s=0)
            sink.emit(turn_id, "companion.state", state="error" if status == "error" else "idle")

        self._start(turn_id, run)
        return {"turn_id": turn_id, "accepted": True}       # the outcome is Core's, relayed as core.result

    # ---- Brain / memory / cloud -----------------------------------------------------------------
    def _brain_status(self, _c):
        r = self._status()
        out = r.to_dict()
        out.pop("live_identity", None)          # process/server detail stays in the worker
        art = out.pop("artifact_identity", None) or {}
        out["artifacts"] = art.get("overall")
        out["selected"] = self.selected
        return out

    def _brain_catalog(self, _c):
        try:
            state = self._status().state
        except Exception:
            state = "UNKNOWN"
        return brain_catalog.catalog(self.cfg, state, self.selected)

    def _brain_select(self, c):
        try:
            sel = brain_catalog.resolve(self.cfg, c["row_id"])
        except ValueError as exc:
            raise BridgeRefused(str(exc)) from None
        self.selected = sel
        self.o.brain_selection = dict(sel)
        self._readiness_for_orchestrator()
        return {"selected": sel}

    def _facts(self):
        """The client store's facts, or None when they cannot be read (never a guess)."""
        if self._memory is None:
            return None
        try:
            rows = self._memory()
        except Exception:
            return None
        return [f for f in rows if isinstance(f, str)] if isinstance(rows, list) else None

    def _memory_list(self, _c):
        if self._memory is None:
            raise BridgeRefused("MEMORY_UNAVAILABLE")
        return {"facts": self._memory(), "source": "client_store", "model_used": False}

    def _cloud_policy(self, _c):
        return self.cloud.summary()

    # ---- health / recovery (WS hardening) -------------------------------------------------------
    def _host(self):
        if self._host_report is None:
            return None, False
        try:
            return self._host_report()
        except Exception:
            return None, False

    def _brain_health(self, _c):
        try:
            readiness = self._status().to_dict()
        except Exception as exc:
            readiness = {"state": "UNKNOWN", "detail": type(exc).__name__}
        proc = ((readiness.pop("live_identity", None) or {}).get("process") or {})
        host, alive = self._host()
        # Real-turn timings of the CURRENT instance only (Codex H-r4). The instance is the verified server process
        # (pid + start time from the accepted readiness check); when it changes the samples are dropped, and when it
        # cannot be established none is used. With a live host, samples older than its calibration are excluded too.
        ident = (proc.get("pid"), proc.get("create_time")) if readiness.get("state") == "READY" else None
        if ident is None or None in ident:
            samples = []
        else:
            if ident != self._perf_ident:
                self._perf_ident = ident
                self._perf = deque((s for s in self._perf if s[0] >= (proc.get("create_time") or 0)), maxlen=PERF_SAMPLES)
            since = ((host or {}).get("calibration") or {}).get("t") if alive else None
            samples = [timings for t, timings in list(self._perf) if since is None or t >= since]
        mon = PerfMonitor(sampler=lambda _pid: (None, None))
        for timings in samples:
            mon.record(timings)
        perf = mon.assess(sample=False)
        out = brain_health.assess(readiness=readiness, host=host, host_alive=alive, perf=perf, busy=self.busy,
                                  selected=self.selected, cfg=self.cfg,
                                  server={"pid": proc.get("pid"), "create_time": proc.get("create_time")})
        pending = self._restart_pending()
        switching = pending and self._switch is not None
        if switching:
            out.update(state=brain_health.RECOVERING, reasons=["PROFILE_SWITCH"] + list(out.get("reasons") or []),
                       recovery_options=[],
                       explain="Switching the Brain to %s. It reloads (about half a minute); your conversation stays."
                       % self._switch["label"])
        elif pending and out["state"] != brain_health.RECOVERING:
            out.update(state=brain_health.RECOVERING, reasons=["RESTART_REQUESTED"] + list(out.get("reasons") or []),
                       recovery_options=[], explain="The Brain restart was requested; URI is waiting for it.")
        out["controls"] = self._controls(out["state"], host, alive, switching)
        out["checked_at"] = round(time.time(), 3)
        return out

    def _controls(self, state, host, alive, switching):
        """Quick Controls state. `active` only when this worker's readiness verified the server (never before)."""
        last = (host or {}).get("profile_switch") if alive else None
        switch = {"pending": bool(switching), "target": dict(self._switch) if switching else None,
                  "last": last, "context_tokens": self._largest_context()}
        reason = None
        if self._host_request is None:
            reason = "BRAIN_CONTROL_UNAVAILABLE"
        elif not alive:
            reason = "BRAIN_HOST_NOT_RUNNING"
        elif self.selected.get("provider") != "llamacpp-runtime-v1":
            reason = "NOT_SELECTED"
        try:
            return QC.controls(self.cfg, state, host_profile=(host or {}).get("profile") if alive else None,
                               switch=switch, can_switch=reason is None, cannot_switch_reason=reason,
                               host_selection_error=(host or {}).get("selection_error") if alive else None,
                               host_alive=bool(alive and host), assist=self._assist())
        except Exception as exc:          # a config the catalog cannot describe is reported, never guessed
            return {"schema": QC.SCHEMA, "active": None, "error": type(exc).__name__, "switch": switch,
                    "options": [], "can_switch": False, "cannot_switch_reason": "PROFILE_UNDESCRIBED"}

    def switch_pending(self) -> bool:
        """A profile switch this worker asked for has not finished (closure QCC-R1-04: Assist waits for it)."""
        return bool(self._switch is not None and self._restart_pending())

    def _assist(self):
        """{"asking", "granted"} from the worker's Assist commands (set by the worker as `assist_state`), or None."""
        fn = getattr(self, "assist_state", None)
        if fn is None:
            return None
        try:
            return fn()
        except Exception:                 # Assist state is advisory for the controls; never breaks a status read
            return None

    def _largest_context(self):
        """The largest last-answer context of any session in this worker (0 when none is known)."""
        return max(self._context_tokens.values(), default=0)

    def _brain_reconfigure(self, c):
        """Explicit user action: switch the Brain to a qualified profile (Vision / Context). Refused while a turn
        runs (handled by `handle`), while another Brain request is unfinished, and for anything outside the catalog.
        A context that the live conversation (plus one answer) would not fit in is refused (review R1-02): nothing
        trims the history sent to the Brain, so a smaller window would make the next turns fail. The reply says so,
        with the numbers; the user keeps the larger context for this conversation."""
        try:
            key = QC.switch_target(c["profile_id"])
        except (QC.QuickControlError, RP.ProfileError) as exc:
            raise BridgeRefused(exc.code) from None
        if self._host_request is None:
            raise BridgeRefused("BRAIN_CONTROL_UNAVAILABLE")
        if self.selected.get("provider") != "llamacpp-runtime-v1":
            raise BridgeRefused("NOT_SELECTED")
        host, alive = self._host()
        if not alive:
            raise BridgeRefused("BRAIN_HOST_NOT_RUNNING")
        if self._restart_pending():
            raise BridgeRefused("BRAIN_RESTARTING")
        current = RP.describe(self.cfg)
        # Closure D2/D6: no reload under a running Assist answer, and vision stays on while Assist holds a grant.
        a = self._assist()
        if a and a.get("asking"):
            raise BridgeRefused("ASSIST_ASK_IN_PROGRESS")
        if a and a.get("granted") and current.get("vision") in QC.VISION_ON and key[1] not in QC.VISION_ON:
            raise BridgeRefused("ASSIST_NEEDS_VISION")
        live = self._largest_context()
        needed = live + ANSWER_RESERVE_TOKENS if live else 0
        plan = RP.plan_change(current, context=key[0], vision=key[1], mtp=key[2], live_tokens=needed)
        entry = QC.entry_by_key(key)
        if plan["refused"] == "CONTEXT_SMALLER_THAN_CONVERSATION":
            return {"requested": None, "refused": plan["refused"], "target": QC.describe_key(key),
                    "detail": {"live_tokens": live, "answer_reserve": ANSWER_RESERVE_TOKENS, "ctx": key[0]}}
        if plan["refused"]:
            raise BridgeRefused(plan["refused"])
        # Review R4-01: the host may run a profile the worker does not follow (a research --profile launch such as P1:
        # the worker stays on the frozen config). The host's own report decides whether the target is already running.
        host_profile = (host or {}).get("profile")
        try:
            host_key = QC.key_of(host_profile) if host_profile else None
        except (KeyError, TypeError, ValueError):
            host_key = None
        reload = plan["reload"] or (host_key is not None and host_key != tuple(key))
        if not reload:
            return {"requested": None, "already_active": True, "target": QC.describe_key(key)}
        now = time.time()
        req = self._host_request("reconfigure", QC.target_dict(key))
        self._restart = {"id": req.get("id"), "t": now, "until": now + RESTART_GATE_S}
        self._switch = {"id": req.get("id"), "to": entry["id"], "label": entry["label"], "t": round(now, 3),
                        "from": current.get("id")}
        return {"requested": "reconfigure", "request_id": req.get("id"), "target": QC.describe_key(key),
                "host_state": host.get("state")}

    def _brain_restart(self, c):
        action = c["action"]
        if action not in brain_health.RESTART_ACTIONS:
            raise BridgeRefused("ACTION_INVALID")
        if self._host_request is None:
            raise BridgeRefused("BRAIN_CONTROL_UNAVAILABLE")
        host, alive = self._host()
        if not alive:
            raise BridgeRefused("BRAIN_HOST_NOT_RUNNING")
        now = time.time()
        req = self._host_request(action)
        # The gate follows the LATEST control request (Codex H-r3): a later request overwrites the request file, so
        # an earlier one may never be read; the host acts on the latest and marks its id.
        self._restart = {"id": req.get("id"), "t": now, "until": now + RESTART_GATE_S}
        return {"requested": action, "request_id": req.get("id"), "host_state": host.get("state")}

    def _oi_turn_status(self, _c):
        job, now = self._job, time.monotonic()
        alive = job is not None and job[1].is_alive()
        return {"busy": alive, "turn_id": job[0] if alive else None,
                "age_s": round(now - self._job_started, 1) if alive and self._job_started else None,
                "idle_s": round(now - self._last_event, 1) if alive and self._last_event else None,
                "events": self._job_events if alive else None,
                "pending_cards": len(self.pending)}

    # ---- text intelligence: drafts --------------------------------------------------------------------
    def _draft_get(self, c):
        if not _is_uuid(c["session_id"]):
            raise BridgeRefused("SESSION_INVALID")
        return {"draft": self.desk.snapshot(c["session_id"])}

    def _draft_op(self, c):
        """Button path for undo/redo/restore/discard. Deterministic, no model, works with the Brain stopped. A draft
        operation never sends, saves or executes anything."""
        if not _is_uuid(c["session_id"]):
            raise BridgeRefused("SESSION_INVALID")
        op = c["op"]
        if op not in DRAFT_OPS or (op == "restore") != ("version" in c):
            raise BridgeRefused("DRAFT_OP_INVALID")
        try:
            draft = self.desk.op(c["session_id"], op, c.get("version"))
        except DeskError as exc:
            raise BridgeRefused(exc.code) from None
        return {"draft": draft, "op": op}
