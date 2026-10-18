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
"""
from __future__ import annotations

import threading
import time
import uuid
from collections import deque

from . import brain_catalog
from . import brain_profile as BP
from . import images as IMG
from . import runtime_profiles as RPROF
from . import brain_health
from . import cloud_policy
from . import schedule_intent
from . import text_input as TI
from . import text_intent as TX
from .draft_desk import DeskError, DraftDesk
from .events import EventSink
from .perf_monitor import PerfMonitor

COMMANDS = {
    "oi_turn": ({"command", "session_id", "text", "depth"}, {"command", "session_id", "text", "depth", "input"},
                {"command", "session_id", "text", "depth", "images"},
                {"command", "session_id", "text", "depth", "input", "images"}),
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
    # Brain quick controls (BRAIN-QUICK-CONTROLS): Vision / Context / Speed as a measured Runtime v1 profile.
    "brain_profile_get": ({"command"},),
    "brain_profile_set": ({"command", "vision", "context", "speed"}, {"command", "vision", "context", "speed",
                                                                     "confirm_shrink"}),
    "oi_turn_status": ({"command"},),
    # Text intelligence: read the session's draft; deterministic draft operations (no model, no authority).
    "draft_get": ({"command", "session_id"},),
    "draft_op": ({"command", "session_id", "op"}, {"command", "session_id", "op", "version"}),
}
OPEN_WHILE_BUSY = {"oi_cancel", "brain_status", "brain_catalog", "cloud_policy", "brain_health",
                   "oi_turn_status", "draft_get", "brain_profile_get"}
PERF_SAMPLES = 48
# A Brain restart/stop request blocks new turns until the host has acted on it (Codex H-r1 F2): the busy check and
# the request are made on the worker's single command thread, and no turn can start between them or after them while
# the host has not finished. Bounded: a host that never answers releases the gate after this long.
RESTART_GATE_S = 600.0
# Brain host states in which no Brain runs or loads and the host only waits for the GPU (ws_brain_host.WAIT_STATES).
HOST_WAIT_STATES = ("WAITING_FOR_GPU", "WAITING_FOR_LEASE", "RELEASE_WAIT")
DRAFT_OPS = ("undo", "redo", "restore", "discard")
# A decision on the turn whose job is still finishing (the card is shown by an event the job emits before it records
# the continuation) waits for that job instead of being refused (Codex WS round 1, F1).
CONTINUATIONS = {"oi_decide", "oi_confirm", "oi_abandon"}
JOIN_S = 30.0
DEPTHS = ("auto", "fast", "normal", "deep")
MAX_TEXT = 20000
MAX_HISTORY = 24
MAX_PENDING = 64


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


class IntegratedTurns:
    def __init__(self, *, orchestrator, cfg, status, write_event, memory=None, cloud=None, defer_start=False,
                 host_report=None, host_request=None, profiles=None, choice_dir=None):
        """
        orchestrator: an OI Orchestrator whose `core` is the paired Core gateway for this client.
        cfg:          the frozen Runtime v1 configuration (already loaded).
        status:       callable -> runtime_v1.Readiness (read-only; never starts the runtime).
        write_event:  callable(dict) that writes ONE event frame under the worker's write lock.
        memory:       callable() -> list of remembered facts (deterministic client read), or None.
        defer_start:  a started job waits for `release()`, which the worker calls right AFTER it wrote the reply.
                      The reply that carries the turn id therefore always precedes the turn's first event frame.
        host_report:  callable() -> (Brain host report | None, host_alive) (read-only), or None without a host.
        host_request: callable(action, profile=None) that writes one explicit request for the Brain host, or None.
        profiles:     brain_profile.ProfileStatus (active profile of the live Brain), or None (frozen config only).
        choice_dir:   directory of the user's persisted profile choice (brain_profile.json), or None.
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
        self._profiles, self._choice_dir = profiles, choice_dir
        self._perf = deque(maxlen=PERF_SAMPLES)     # (wall time, llama-server timings) of finished answers
        self._job_started = None      # monotonic start of the running job
        self._last_event = None       # monotonic time of the job's last event frame
        self._job_events = 0
        self._restart = None          # {"id", "t", "until"} of a Brain request the host has not finished
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
                or result in ("DONE", "IGNORED_INVALID_OR_STALE", "SUPERSEDED"))
        if done:
            self._restart = None
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
        images = None
        if "images" in c:
            try:
                images = IMG.parse(c["images"])
            except IMG.ImageRejected as exc:
                raise BridgeRefused(exc.code) from None
            refusal = self._image_refusal()
            if refusal is not None:
                raise BridgeRefused(refusal)
        turn_id = str(uuid.uuid4())
        history = list(self.history.get(session_id, ()))
        # A transcript reaches the ordinary path with fillers removed; the raw transcript stays in the envelope.
        plain = TI.clean_transcript(text) if inp.is_transcript else text
        with self._lock:
            clarifications = {tid: p for tid, p in self.pending.items()
                              if p["session_id"] == session_id and p["env"].get("clarification")
                              and not p["env"].get("confirmation")
                              and p["env"].get("state") != "approval_required"}
        continue_core = bool(clarifications) and inp.mode != "dictation"
        if images is not None and continue_core:
            # URI waits for the answer to its own question: that answer goes to Core, which takes no images. Its own
            # code, so the UI asks for the answer first instead of advising "ask about the image" (R4-03).
            raise BridgeRefused("IMAGE_DURING_CLARIFICATION")
        if images is not None and (inp.mode in ("dictation", "draft") or schedule_intent.interpret(plain) is not None):
            # An image is a question for the answer channel only: never a draft, a Core continuation or a handoff.
            raise BridgeRefused("IMAGE_ACTION_UNSUPPORTED")
        if continue_core and len(clarifications) != 1:
            # No arbitrary selection or bulk retirement of independent cards. Keep all records and let the
            # caller surface the ambiguous state; nothing reaches a model, Core continuation or decision.
            raise BridgeRefused("CLARIFICATION_STATE_AMBIGUOUS")

        def ordinary(sink, request=None):
            words = request if request is not None else plain
            extra = {"images": images} if images is not None else {}
            out = self.o.handle_turn(words, session_id, depth=depth, history=history, sink=sink, turn_id=turn_id,
                                     core_clarification=continue_core, **extra)
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
            # History never holds image bytes: a later switch to Vision Off must not need media tokens.
            recorded = words if images is None else words + "".join("\n" + IMG.placeholder(i) for i in images)
            self._record_history(session_id, recorded, answer if out.status in ("ok", "incomplete") else None)
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
                if images is not None:
                    ordinary(sink)
                    return
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
                                  selected=self.selected, cfg=self._active_cfg(),
                                  server={"pid": proc.get("pid"), "create_time": proc.get("create_time")})
        if self._restart_pending() and out["state"] != brain_health.RECOVERING:
            out.update(state=brain_health.RECOVERING, reasons=["RESTART_REQUESTED"] + list(out.get("reasons") or []),
                       recovery_options=[], explain="The Brain restart was requested; URI is waiting for it.")
        out["profile"] = self._profile_state(host, alive, readiness)
        out["checked_at"] = round(time.time(), 3)
        return out

    # ---- Brain quick controls (BRAIN-QUICK-CONTROLS) ----------------------------------------------------
    def _active_cfg(self):
        cfg = self._profiles.active_cfg() if self._profiles is not None else None
        return cfg if cfg is not None else self.cfg

    def _image_refusal(self):
        """Images are accepted only when the active profile has vision AND the live server is READY with it (the
        profile-aware readiness checks the server's /props modalities). R4-01: VISION_OFF only when the profile has
        no vision; a vision profile whose server is not READY (loading, failed, mismatch) is VISION_NOT_READY."""
        if not self._active_cfg()["runtime"].get("vision_enabled"):
            return "VISION_OFF"
        try:
            ready = self._status().state == "READY"
        except Exception:
            ready = False
        return None if ready else "VISION_NOT_READY"

    def _profile_state(self, host, alive, readiness=None):
        """Truthful profile view: what runs (the live host's report), what is requested, what the user chose."""
        key, source, error = BP.read_choice(self._choice_dir) if self._choice_dir is not None else \
            (None, "none", None)
        active = (host or {}).get("profile") if alive else None
        akey = BP.key_of_described(active)
        switch = (host or {}).get("switch") if alive else None
        ready = (readiness or {}).get("state") == "READY"
        lr = (host or {}).get("last_request") if alive else None
        return {"host_state": (host or {}).get("state") if alive else None,
                "host_explain": (host or {}).get("explain") if alive else None,
                # R1-01: during a GPU wait no Brain runs; the controls stay usable and a new choice retargets the wait.
                "host_waiting": bool(alive and (host or {}).get("state") in HOST_WAIT_STATES),
                "last_request": {k: lr.get(k) for k in ("id", "action", "result", "t")} if isinstance(lr, dict) else None,
                "host_choice_error": ((host or {}).get("profile_choice") or {}).get("error") if alive else None,
                "active": dict(active, **BP.controls(akey)) if akey else None,
                "vision_live": bool(ready and akey and akey[1] != "off"),
                "choice": dict(BP.controls(key), id=RPROF.profile_id(key), source=source, error=error) if key else None,
                "switching": {"from": switch.get("from", {}).get("id"), "to": switch.get("to", {}).get("id")}
                if isinstance(switch, dict) else None,
                "last_switch": (host or {}).get("last_switch") if alive else None,
                "pending_request": self._restart_pending()}

    def _live_tokens(self):
        """Conservative size of the largest live conversation (chars / 4 + the system prompt allowance)."""
        sizes = [sum(len(m.get("content") or "") for m in h) for h in self.history.values()]
        return (max(sizes) // 4 + 2048) if sizes and max(sizes) else 0

    def _brain_profile_get(self, _c):
        host, alive = self._host()
        return {"offer": BP.offer(), "state": self._profile_state(host, alive),
                "host_state": (host or {}).get("state") if alive else None}

    def _brain_profile_set(self, c):
        try:
            key = BP.key_from_controls(c["vision"], c["context"], c["speed"])
        except BP.ChoiceError as exc:
            raise BridgeRefused(exc.code) from None
        if "confirm_shrink" in c and not isinstance(c["confirm_shrink"], bool):
            raise BridgeRefused("COMMAND_SCHEMA")
        if self._host_request is None or self._choice_dir is None:
            raise BridgeRefused("BRAIN_CONTROL_UNAVAILABLE")
        host, alive = self._host()
        if not alive:
            raise BridgeRefused("BRAIN_HOST_NOT_RUNNING")
        if self._restart_pending() and not self._host_took_request_and_waits(host):
            raise BridgeRefused("BRAIN_REQUEST_PENDING")
        akey = BP.key_of_described((host or {}).get("profile"))
        if akey is None:
            raise BridgeRefused("PROFILE_UNKNOWN")
        current = {"ctx": akey[0], "vision": akey[1], "mtp": akey[2]}
        plan = RPROF.plan_change(current, context=key[0], vision=key[1], mtp=key[2],
                                 live_tokens=self._live_tokens(), confirm_shrink=bool(c.get("confirm_shrink")))
        if plan["refused"]:
            if plan["refused"] == "CONTEXT_SMALLER_THAN_CONVERSATION":
                raise BridgeRefused("CONTEXT_SMALLER_THAN_CONVERSATION")
            raise BridgeRefused(plan["refused"])
        running = (host or {}).get("state") in ("READY", "DEGRADED")
        if not plan["reload"] and running:
            BP.write_choice(self._choice_dir, key)      # the profile that runs: nothing for the host to take
            return {"requested": None, "profile": RPROF.profile_id(key), "unchanged": True}
        # The choice file is written by the host once it takes the switch (R1-02): a refused or ignored request
        # never leaves a choice behind that the next host start would apply.
        now = time.time()
        req = self._host_request("reconfigure", key)
        self._restart = {"id": req.get("id"), "t": now, "until": now + RESTART_GATE_S}
        return {"requested": "reconfigure", "request_id": req.get("id"), "profile": RPROF.profile_id(key),
                "host_state": (host or {}).get("state")}

    def _host_took_request_and_waits(self, host):
        """R1-01: the pending request was taken by the host, which now only waits for the GPU (no Brain runs or
        loads). A new choice may replace it there; an untaken request is never overwritten."""
        r = self._restart
        taken = r is not None and ((host or {}).get("requests") or {}).get(r["id"]) == "ACCEPTED"
        return taken and (host or {}).get("state") in HOST_WAIT_STATES

    def _brain_restart(self, c):
        action = c["action"]
        # A profile switch goes through brain_profile_set (validated, with a target), never brain_restart (R3-05).
        if action not in brain_health.ACTIONS or action == "reconfigure":
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
