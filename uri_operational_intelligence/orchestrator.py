"""One URI turn under Operational Intelligence: triage -> (Core authority | answer channel | plan | harness choice).

Authority map (unchanged from Phase 1/2):
  * Anything that may change state goes to URI Core through a CoreGateway (the paired client loop). Core performs
    Intent Discovery, confirmation, gates, approval, signed ticket, execution and independent verification.
  * The answer channel only talks. If it detects an action request (ACTION_MARKER) the turn is re-routed to Core.
  * Plans are proposals; their executable steps reach Core with the user's verbatim words.
  * Harness work needs the user's explicit provider choice; quota exhaustion pauses the task with Core's checkpoint.
  * The orchestrator never retries an uncertain execution and never substitutes another reasoning source.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from . import answer as A
from . import brain_client as BC
from . import harness_choice as H
from . import planner as P
from . import reasoning_policy as RP
from . import triage as T
from .events import EventSink
from .task_ledger import LedgerError, TaskLedger


class CoreGateway(Protocol):
    def begin(self, text: str, session_id: str, selection: dict) -> dict: ...
    def confirm(self, session_id: str, selection: dict, turn: dict) -> dict: ...
    def decide(self, text: str, session_id: str, selection: dict, turn: dict, approve: bool) -> dict: ...
    def continue_waiting(self, session_id: str, turn_id: str, selection: dict, approve: Callable) -> dict: ...


class PairedCoreGateway:
    """Real Core: the frozen client TurnRunner talking to the paired server (create_app + PairedCoordinator)."""

    def __init__(self, runner):
        self.runner = runner

    def begin(self, text, session_id, selection):
        return self.runner.begin(text, session_id, selection)

    def confirm(self, session_id, selection, turn):
        return self.runner.confirm(session_id, selection, turn)

    def decide(self, text, session_id, selection, turn, approve):
        return self.runner.decide(text, session_id, selection, turn, approve)

    def continue_waiting(self, session_id, turn_id, selection, approve):
        return self.runner.continue_waiting(session_id, turn_id, selection, approve)


def core_turn_status(env: dict, needs: str) -> str:
    """Allowlist: "ok" only for Core's verified settlement. Everything else is needs_user / error / not_verified /
    refused / reported (Core's message shown as is), never success."""
    code, state = env.get("code") or "", env.get("state")
    if needs != "none":
        return "needs_user"
    if code == "SETTLED_VERIFIED" and state == "reply":
        return "ok"
    if state == "failed":
        return "error"
    if code.startswith("SETTLED_") or state in ("execution_uncertain", "cancelled"):
        return "not_verified"
    if code.startswith("REFUSED_") or code.startswith("CLARIFICATION_") or code.startswith("INTENT_"):
        return "refused"
    return "reported"


def core_needs(env: dict) -> str:
    if env.get("state") == "approval_required":
        return "approval"
    if env.get("confirmation"):
        return "confirmation"
    if env.get("clarification"):
        return "clarification"
    return "none"


def step_state_for(env: dict) -> str:
    code, state = env.get("code") or "", env.get("state")
    if state == "approval_required":
        return "WAITING_APPROVAL"
    if env.get("confirmation") or env.get("clarification"):
        return "WAITING_CONFIRMATION"
    if code == "SETTLED_VERIFIED" and state == "reply":
        return "VERIFIED"   # success needs BOTH Core's verified code and its reply state
    if state == "execution_uncertain" or code in ("SETTLED_EXECUTION_UNCERTAIN", "INTENT_EXECUTION_UNCERTAIN"):
        return "UNCERTAIN"
    if code == "WAITING_FOR_MODEL":
        return "WAITING_USER_CHOICE"
    if state == "cancelled" or code == "APPROVAL_DENIED":
        return "CANCELLED"
    if code in ("CLARIFICATION_REQUIRED", "INTENT_CLARIFICATION"):
        return "WAITING_CONFIRMATION"
    if code == "INTENT_ABANDONED":
        return "CANCELLED"
    if (code.startswith("REFUSED_") or code.startswith("CLARIFICATION_") or code in
            ("INTENT_ALREADY_EXECUTED", "INTENT_STATE_STALE", "INTENT_DECISION_STALE", "INTENT_UNGROUNDED_VALUE")):
        return "REFUSED"
    if code == "CONVERSATION":
        return "ANSWERED"
    # Anything else (failed state or an unknown code) is a failure: never read as success.
    return "FAILED"


@dataclass
class TurnOutcome:
    turn_id: str
    route: str
    triage: dict
    tier: dict
    status: str
    answer: Optional[dict] = None
    core: Optional[dict] = None
    task_id: Optional[str] = None
    harness: Optional[dict] = None
    total_s: float = 0.0
    events: list = field(default_factory=list)


class Orchestrator:
    def __init__(self, *, client: BC.BrainClient, core: CoreGateway | None, brain_selection: dict,
                 ledger: TaskLedger, capability_ids=(), readiness: Callable | None = None,
                 harness_statuses: Callable | None = None, deadlines: BC.Deadlines | None = None, perf=None):
        self.client, self.core, self.brain_selection = client, core, brain_selection
        self.ledger, self.capability_ids = ledger, set(capability_ids)
        self.readiness = readiness
        self.harness_statuses = harness_statuses or (lambda: H.documented_status())
        self.deadlines = deadlines or BC.Deadlines()
        self.perf = perf       # optional PerfMonitor (OI-PERF-1): throughput health from finished answers
        self.cancels = {}      # turn_id -> CancelToken
        # Core turn ids issued on SINGLE-turn routes (not plan steps). confirm()/decide() accept only these
        # (allowlist, fail closed): a plan step's Core turn can only be continued through confirm_step/decide_step.
        self._single_turns = set()
        self._single_lock = __import__("threading").Lock()

    # ---- public API ---------------------------------------------------------------------------
    def cancel(self, turn_id, reason="user"):
        tok = self.cancels.get(turn_id)
        if tok:
            tok.cancel(reason)
            return True
        return False

    def handle_turn(self, text, session_id, *, depth="auto", history=(), sink: EventSink | None = None,
                    turn_id=None) -> TurnOutcome:
        turn_id = turn_id or str(uuid.uuid4())
        sink = sink or EventSink()
        cancel = self.cancels.setdefault(turn_id, BC.CancelToken())
        t0 = time.monotonic()
        emit = lambda t, **d: sink.emit(turn_id, t, **d)
        try:
            emit("turn.started", text_chars=len(text), depth=depth)
            emit("companion.state", state="thinking")
            tri = T.triage(text)
            tier = RP.decide(tri.kind, depth)
            out = self._route(text, session_id, tri, tier, depth, history, emit, cancel, turn_id)
        finally:
            self.cancels.pop(turn_id, None)
        out.total_s = round(time.monotonic() - t0, 4)
        out.events = sink.events
        emit("turn.finished", status=out.status, route=out.route, total_s=out.total_s)
        emit("companion.state", state="waiting_user" if out.status in ("needs_user", "awaiting_plan_approval",
                                                                          "needs_harness_choice") else
             ("error" if out.status == "error" else "idle"))
        return out

    # ---- routing ------------------------------------------------------------------------------
    def _brain_ready(self):
        if self.readiness is None:
            return True, None
        r = self.readiness()
        return r.state == "READY", r

    def _route(self, text, session_id, tri, tier, depth, history, emit, cancel, turn_id) -> TurnOutcome:
        if tier.tier == RP.ESCALATE:
            emit("turn.routed", route="escalation_offer", triage=tri.to_dict(), tier=tier.to_dict())
            choice = H.choose(self.harness_statuses()).to_dict()
            emit("escalation.offer", reason=tier.reason, options=choice)
            return TurnOutcome(turn_id, "escalation_offer", tri.to_dict(), tier.to_dict(), "needs_harness_choice",
                               harness=choice)
        if tri.kind == T.HARNESS:
            emit("turn.routed", route="harness_choice", triage=tri.to_dict(), tier=tier.to_dict())
            choice = H.choose(self.harness_statuses()).to_dict()
            emit("harness.choice_required", **choice)
            return TurnOutcome(turn_id, "harness_choice", tri.to_dict(), tier.to_dict(), "needs_harness_choice",
                               harness=choice)
        if tri.kind == T.ACTION:
            return self._core_turn(text, session_id, tri, tier, emit, turn_id, history, cancel)
        if tri.kind == T.MULTI_STEP:
            return self._plan_turn(text, session_id, tri, tier, emit, turn_id)
        return self._answer_turn(text, session_id, tri, tier, emit, turn_id, history, cancel)

    def _answer_turn(self, text, session_id, tri, tier, emit, turn_id, history, cancel, executed_action=False,
                     rerouted_from=None) -> TurnOutcome:
        ready, r = self._brain_ready()
        emit("turn.routed", route="answer", triage=tri.to_dict(), tier=tier.to_dict())
        if not ready:
            emit("error", code="BRAIN_UNAVAILABLE", message="The local Brain is not ready (%s)." % (r.state if r else "?"),
                 recoverable=True, recovery_options=["start_brain", "retry", "choose_other_source"])
            return TurnOutcome(turn_id, "answer", tri.to_dict(), tier.to_dict(), "error",
                               answer={"status": "BRAIN_UNAVAILABLE", "readiness": r.state if r else None})
        reasoning_chars = {"n": 0, "last": 0}
        spoke = {"v": False}

        def on_delta(kind, chunk):
            if kind == "reasoning":
                reasoning_chars["n"] += len(chunk)
                if reasoning_chars["n"] - reasoning_chars["last"] >= 200:
                    reasoning_chars["last"] = reasoning_chars["n"]
                    emit("thinking.progress", chars=reasoning_chars["n"])
                return
            if not spoke["v"]:
                spoke["v"] = True
                emit("companion.state", state="speaking")
            emit("answer.delta", text=chunk)

        use = "trivial" if tri.kind == T.TRIVIAL and tier.tier == RP.FAST else "answer"
        res = A.answer(self.client, text, tier=tier.tier, use=use, history=history, cancel=cancel,
                       deadlines=self.deadlines, on_delta=on_delta, executed_action=executed_action)
        if res.status == "ACTION_REQUESTED" and rerouted_from is None:
            # Model-side guard: the user asked URI to DO something. Core decides; nothing was said to the user yet.
            return self._core_turn(text, session_id, T.Triage(T.ACTION, ["answer_channel_action_marker"]),
                                   RP.decide(T.ACTION), emit, turn_id, history, cancel, rerouted_from="answer")
        emit("answer.done", status=res.status, complete=res.complete, escalation_candidate=res.escalation_candidate,
             flags=res.flags, metrics=res.metrics)
        if self.perf is not None:
            self.perf.record(res.metrics)
            health = self.perf.assess(sample=False)
            if health["state"] == "DEGRADED":
                emit("brain.status", state="DEGRADED", model_id=self.brain_selection.get("model"), owned=None,
                     detail=",".join(health["reasons"]), identity={}, performance=health)
        if res.escalation_candidate:
            emit("escalation.offer", reason="normal_budget_exhausted", options=H.choose(self.harness_statuses()).to_dict())
        if res.status not in (BC.COMPLETE, BC.INCOMPLETE_LENGTH, BC.CANCELLED):
            emit("error", code="BRAIN_" + res.status, message="The local Brain did not finish this answer.",
                 recoverable=True, recovery_options=["retry"] + (["keep_partial"] if res.text else []))
        status = {"COMPLETE": "ok", "INCOMPLETE_LENGTH": "incomplete", "CANCELLED": "cancelled"}.get(res.status, "error")
        return TurnOutcome(turn_id, "answer", tri.to_dict(), tier.to_dict(), status, answer=res.to_dict())

    def _core_turn(self, text, session_id, tri, tier, emit, turn_id, history, cancel, rerouted_from=None) -> TurnOutcome:
        emit("turn.routed", route="core", triage=tri.to_dict(), tier=tier.to_dict(),
             **({"rerouted_from": rerouted_from} if rerouted_from else {}))
        if self.core is None:
            emit("error", code="CORE_UNAVAILABLE", message="URI Core is not connected; nothing was done.",
                 recoverable=True, recovery_options=["retry"])
            return TurnOutcome(turn_id, "core", tri.to_dict(), tier.to_dict(), "error")
        if self.brain_selection.get("provider") != "uri-deterministic":
            # Fast, honest failure: with the selected Brain down Core would report SELECTED_MODEL_UNAVAILABLE after
            # its connect attempts (measured ~4.7 s). Nothing is sent and nothing is substituted.
            ready, r = self._brain_ready()
            if not ready:
                emit("error", code="BRAIN_UNAVAILABLE", message="The selected Brain is not ready (%s); nothing was done."
                     % (r.state if r else "?"), recoverable=True,
                     recovery_options=["start_brain", "retry", "choose_other_source"])
                return TurnOutcome(turn_id, "core", tri.to_dict(), tier.to_dict(), "error")
        try:
            env = self.core.begin(text, session_id, self.brain_selection)
        except Exception as exc:     # transport / Core control error: report, never guess an outcome
            emit("error", code="CORE_ERROR", message=type(exc).__name__ + ": " + str(exc)[:200], recoverable=True,
                 recovery_options=["retry"])
            return TurnOutcome(turn_id, "core", tri.to_dict(), tier.to_dict(), "error")
        return self._relay_core(env, text, session_id, tri, tier, emit, turn_id, history, cancel)

    def _register_single(self, env):
        if isinstance(env, dict) and env.get("turn_id"):
            with self._single_lock:
                self._single_turns.add(env["turn_id"])

    def _require_single(self, turn):
        with self._single_lock:
            if not isinstance(turn, dict) or turn.get("turn_id") not in self._single_turns:
                raise LedgerError("NOT_A_SINGLE_TURN_ISSUED_HERE")

    def _relay_core(self, env, text, session_id, tri, tier, emit, turn_id, history, cancel, selection=None) -> TurnOutcome:
        self._register_single(env)
        needs = core_needs(env)
        emit("core.result", state=env.get("state"), code=env.get("code"), message=env.get("message"), needs=needs,
             **{k: env[k] for k in ("intent", "confirmation", "clarification") if env.get(k) is not None})
        if needs == "approval":
            a = env["approval_request"]
            emit("approval.required", core_turn_id=env.get("turn_id"), capability_id=a["capability_id"],
                 arguments=a["arguments"], approval_digest=a["approval_digest"], effect=a.get("effect"),
                 reversible=a.get("reversible"))
        if env.get("code") == "CONVERSATION":
            # Core found nothing to act on: answer the language request on the answer channel (no action ran).
            out = self._answer_turn(text, session_id, T.Triage(T.QUESTION, ["core_conversation"]),
                                    RP.decide(T.QUESTION), emit, turn_id, history, cancel, rerouted_from="core")
            out.core = env
            out.route = "core+answer"
            return out
        if env.get("code") == "WAITING_FOR_MODEL":
            # Provider quota: Core kept the checkpoint. Offer the other providers; never switch silently.
            used = (selection or self.brain_selection).get("provider")
            choice = H.choose(self.harness_statuses(), exclude=(used,)).to_dict()
            emit("harness.choice_required", **choice)
            return TurnOutcome(turn_id, "core", tri.to_dict(), tier.to_dict(), "needs_harness_choice", core=env,
                               harness=choice)
        return TurnOutcome(turn_id, "core", tri.to_dict(), tier.to_dict(), core_turn_status(env, needs), core=env)

    # ---- user decisions on Core turns ------------------------------------------------------------
    def confirm(self, session_id, turn, sink: EventSink | None = None):
        """Confirmation for a SINGLE-turn Core request issued by this orchestrator (allowlist)."""
        self._require_single(turn)
        sink = sink or EventSink()
        env = self.core.confirm(session_id, self.brain_selection, turn)
        return self._relay_core(env, "Confirm", session_id, T.Triage(T.ACTION, ["user_confirmed"]), RP.decide(T.ACTION),
                                lambda t, **d: sink.emit(turn.get("turn_id"), t, **d), turn.get("turn_id"), (), None)

    def decide(self, text, session_id, turn, approve: bool, sink: EventSink | None = None):
        """Approval decision for a SINGLE-turn Core request issued by this orchestrator (allowlist). Plan steps can
        only be approved through decide_step (durable EXECUTING before Core)."""
        self._require_single(turn)
        sink = sink or EventSink()
        env = self.core.decide(text, session_id, self.brain_selection, turn, approve)
        emit = lambda t, **d: sink.emit(turn.get("turn_id"), t, **d)
        emit("core.result", state=env.get("state"), code=env.get("code"), message=env.get("message"), needs=core_needs(env))
        return env

    def begin_harness(self, text, session_id, provider_selection: dict, sink: EventSink | None = None) -> TurnOutcome:
        """Run a harness request through Core with the provider the USER chose (explicit selection row)."""
        sink = sink or EventSink()
        turn_id = str(uuid.uuid4())
        emit = lambda t, **d: sink.emit(turn_id, t, **d)
        tri, tier = T.Triage(T.HARNESS, ["user_selected_provider"]), RP.decide(T.HARNESS)
        emit("turn.routed", route="core", triage=tri.to_dict(), tier=tier.to_dict())
        env = self.core.begin(text, session_id, provider_selection)
        out = self._relay_core(env, text, session_id, tri, tier, emit, turn_id, (), None, selection=provider_selection)
        out.events = sink.events
        return out

    # ---- multi-step -------------------------------------------------------------------------------
    def _plan_turn(self, text, session_id, tri, tier, emit, turn_id) -> TurnOutcome:
        emit("turn.routed", route="plan", triage=tri.to_dict(), tier=tier.to_dict())
        ready, r = self._brain_ready()
        if not ready:
            emit("error", code="BRAIN_UNAVAILABLE", message="The local Brain is not ready; no plan was made.",
                 recoverable=True, recovery_options=["start_brain", "retry"])
            return TurnOutcome(turn_id, "plan", tri.to_dict(), tier.to_dict(), "error")
        v = P.propose_plan(self.client, text, self.capability_ids)
        if not v["ok"]:
            emit("error", code="PLAN_UNAVAILABLE", message="I could not make a usable plan: " + ",".join(v["problems"]),
                 recoverable=True, recovery_options=["retry", "rephrase"] + (["escalate"] if v.get("escalation_candidate") else []))
            return TurnOutcome(turn_id, "plan", tri.to_dict(), tier.to_dict(), "error")
        task = self.ledger.create(session_id=session_id, request_text=text, plan=v["plan"], state="AWAITING_PLAN_APPROVAL")
        emit("plan.proposed", task_id=task["task_id"], goal=v["plan"].get("goal"), steps=v["plan"]["steps"],
             clarifications=v["plan"].get("clarifications") or [], problems=v["problems"], downgraded=v["downgraded"],
             meta=v.get("meta"))
        return TurnOutcome(turn_id, "plan", tri.to_dict(), tier.to_dict(), "awaiting_plan_approval",
                           task_id=task["task_id"])

    def approve_plan(self, task_id):
        return self.ledger.set_state(task_id, "RUNNING", by="user")

    def advance(self, task_id, *, sink: EventSink | None = None, history=()):
        """Run the next ready step (one at a time). Action steps stop at Core's confirmation/approval and wait for
        the user; the caller resumes with confirm()/decide() on the returned Core envelope, then record_step()."""
        sink = sink or EventSink()
        task = self.ledger.get(task_id)
        if task["state"] != "RUNNING":
            return {"status": "not_running", "state": task["state"]}
        for s in self.ledger.blocked_steps(task):
            self.ledger.set_step(task_id, s["step_id"], "SKIPPED", note="dependency_did_not_succeed")
        task = self.ledger.get(task_id)
        ready = self.ledger.ready_steps(task)
        if not ready:
            return {"status": "no_ready_step", "state": task["state"]}
        s = ready[0]
        emit = lambda t, **d: sink.emit(task_id, t, **d)
        if s["kind"] == "answer":
            res = A.answer(self.client, s["description"] + "\n\nOriginal request: " + task["request_text"],
                           tier=RP.FAST, history=history, deadlines=self.deadlines,
                           on_delta=lambda k, c: emit("answer.delta", text=c) if k == "answer" else None)
            self.ledger.set_step(task_id, s["step_id"], "ANSWERED" if res.status == BC.COMPLETE else "FAILED",
                                 note=res.status)
            emit("task.step", task_id=task_id, step_id=s["step_id"], state="ANSWERED" if res.status == BC.COMPLETE else "FAILED")
            return {"status": "step_done", "step_id": s["step_id"], "answer": res.to_dict()}
        if s["kind"] == "ask_user":
            self.ledger.set_step(task_id, s["step_id"], "WAITING_USER_CHOICE", note="needs_user_input")
            emit("task.step", task_id=task_id, step_id=s["step_id"], state="WAITING_USER_CHOICE")
            return {"status": "needs_user_input", "step_id": s["step_id"], "question": s["description"]}
        if s["kind"] == "harness":
            self.ledger.set_step(task_id, s["step_id"], "WAITING_USER_CHOICE", note="harness_choice")
            choice = H.choose(self.harness_statuses(), task_choice_history=[c["provider"] for c in task["provider_choices"]])
            emit("harness.choice_required", **choice.to_dict())
            return {"status": "needs_harness_choice", "step_id": s["step_id"], "choice": choice.to_dict()}
        # action: the user's verbatim words go to Core. The IN_CORE write is an exclusive claim: a concurrent advance()
        # (thread or process) gets STEP_ALREADY_CLAIMED and never reaches Core.
        try:
            self.ledger.set_step(task_id, s["step_id"], "IN_CORE")
        except LedgerError as exc:
            return {"status": "not_claimed", "step_id": s["step_id"], "reason": str(exc)}
        env = self.core.begin(s["source_span"], task["session_id"], self.brain_selection)
        return self.record_step(task_id, s["step_id"], env, sink=sink)

    def confirm_step(self, task_id, step_id, turn, *, sink: EventSink | None = None):
        """The user's explicit confirmation for a plan step. Claims IN_CORE first, so two concurrent confirmations
        cannot both reach Core."""
        try:
            self.ledger.set_step(task_id, step_id, "IN_CORE", core={"turn_id": turn.get("turn_id"),
                                                                   "state": "confirming", "code": None})
        except LedgerError as exc:
            return {"status": "not_claimed", "step_id": step_id, "reason": str(exc)}
        env = self.core.confirm(self.ledger.get(task_id)["session_id"], self.brain_selection, turn)
        return self.record_step(task_id, step_id, env, sink=sink)

    def decide_step(self, task_id, step_id, turn, approve: bool, *, sink: EventSink | None = None):
        """The user's approval decision for a plan step. Before an APPROVAL is handed to Core the step is durably
        EXECUTING: a crash from here on recovers as UNCERTAIN, never as a step to start again."""
        task = self.ledger.get(task_id)
        if approve:
            self.ledger.set_step(task_id, step_id, "EXECUTING",
                                 core={"turn_id": turn.get("turn_id"), "state": "approved_by_user", "code": None})
        try:
            env = self.core.decide(task["request_text"], task["session_id"], self.brain_selection, turn, approve)
        except Exception as exc:
            if approve:
                self.ledger.set_step(task_id, step_id, "UNCERTAIN", note="decide_error:" + type(exc).__name__)
            raise
        return self.record_step(task_id, step_id, env, sink=sink)

    def record_step(self, task_id, step_id, env, *, sink: EventSink | None = None):
        sink = sink or EventSink()
        state = step_state_for(env)
        kind = self.ledger.step(self.ledger.get(task_id), step_id)["kind"]
        if kind == "action" and state == "ANSWERED":
            # Core found nothing to act on. For an ACTION step that is not success: dependents must not run.
            state = "REFUSED"
        current = self.ledger.step(self.ledger.get(task_id), step_id)["state"]
        if current == "EXECUTING" and state not in ("VERIFIED", "FAILED", "UNCERTAIN", "WAITING_USER_CHOICE",
                                                    "CANCELLED", "REFUSED"):
            # After an approval only an outcome is acceptable. Anything else is not proof that nothing ran.
            state = "UNCERTAIN"
        core = {"turn_id": env.get("turn_id"), "state": env.get("state"), "code": env.get("code")}
        self.ledger.set_step(task_id, step_id, state, core=core)
        sink.emit(task_id, "task.step", task_id=task_id, step_id=step_id, state=state, core_code=env.get("code"))
        if state == "WAITING_APPROVAL":
            a = env["approval_request"]
            sink.emit(task_id, "approval.required", core_turn_id=env.get("turn_id"), capability_id=a["capability_id"],
                      arguments=a["arguments"], approval_digest=a["approval_digest"], effect=a.get("effect"),
                      reversible=a.get("reversible"))
        return {"status": "step_" + state.lower(), "step_id": step_id, "core": env}
