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
from . import brain_health
from . import cloud_policy
from .events import EventSink
from .perf_monitor import PerfMonitor

COMMANDS = {
    "oi_turn": ({"command", "session_id", "text", "depth"},),
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
    "oi_turn_status": ({"command"},),
}
OPEN_WHILE_BUSY = {"oi_cancel", "brain_status", "brain_catalog", "cloud_policy", "brain_health", "oi_turn_status"}
PERF_SAMPLES = 48
# A Brain restart/stop request blocks new turns until the host has acted on it (Codex H-r1 F2): the busy check and
# the request are made on the worker's single command thread, and no turn can start between them or after them while
# the host has not finished. Bounded: a host that never answers releases the gate after this long.
RESTART_GATE_S = 600.0
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
        lr = (host or {}).get("last_request") or {}
        done = (time.time() > r["until"]
                or (host is not None and not alive)
                or (lr.get("id") == r["id"] and lr.get("result") in ("DONE", "IGNORED_INVALID_OR_STALE")))
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
        turn_id = str(uuid.uuid4())
        history = list(self.history.get(session_id, ()))

        def run():
            sink = self._sink(turn_id)
            try:
                out = self.o.handle_turn(text, session_id, depth=depth, history=history, sink=sink, turn_id=turn_id)
            except Exception as exc:          # never leave the UI waiting: close the stream as an error
                self._fail(sink, turn_id, exc)
                return
            self._remember(turn_id, session_id, text, out.core, out.status)
            answer = (out.answer or {}).get("text")
            self._record_history(session_id, text, answer if out.status in ("ok", "incomplete") else None)

        self._start(turn_id, run)
        return {"turn_id": turn_id, "accepted": True, "selection": self.selected}

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
                env = self.o.decide(p["text"], p["session_id"], p["env"], approve, sink=sink)
            except Exception as exc:
                self._fail(sink, turn_id, exc)
                return
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
        with self._lock:
            p = self.pending.pop(c["turn_id"], None)
        if p is None:
            raise BridgeRefused("TURN_NOT_PENDING")
        if p["env"].get("state") == "approval_required":
            self._release(p)
        return {"abandoned": True}

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
        readiness.pop("live_identity", None)
        host, alive = self._host()
        # Real-turn timings of the CURRENT instance only: samples older than this instance's calibration belong to a
        # previous process (a restart resets the evidence).
        since = ((host or {}).get("calibration") or {}).get("t") if alive else None
        mon = PerfMonitor(sampler=lambda _pid: (None, None))
        for t, timings in list(self._perf):
            if since is None or t >= since:
                mon.record(timings)
        perf = mon.assess(sample=False)
        out = brain_health.assess(readiness=readiness, host=host, host_alive=alive, perf=perf, busy=self.busy,
                                  selected=self.selected, cfg=self.cfg)
        if self._restart_pending() and out["state"] != brain_health.RECOVERING:
            out.update(state=brain_health.RECOVERING, reasons=["RESTART_REQUESTED"] + list(out.get("reasons") or []),
                       recovery_options=[], explain="The Brain restart was requested; URI is waiting for it.")
        out["checked_at"] = round(time.time(), 3)
        return out

    def _brain_restart(self, c):
        action = c["action"]
        if action not in brain_health.ACTIONS:
            raise BridgeRefused("ACTION_INVALID")
        if self._host_request is None:
            raise BridgeRefused("BRAIN_CONTROL_UNAVAILABLE")
        host, alive = self._host()
        if not alive:
            raise BridgeRefused("BRAIN_HOST_NOT_RUNNING")
        now = time.time()
        req = self._host_request(action)
        if action in ("restart", "stop"):
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
