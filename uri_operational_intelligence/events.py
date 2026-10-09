"""UI event contract (schema "uri.oi.event.v1") and a simulator for the parallel UI session.

Every event: {"schema", "seq", "t", "turn_id", "type", "data"}. Types and their data are listed in EVENT_TYPES and
documented in docs/operational_intelligence/OI_UI_INTEGRATION_CONTRACT.md. The UI must treat unknown types as
ignorable and must never infer an action outcome from answer text: only `core.result` / `task.step` carry outcomes.
"""
from __future__ import annotations

import itertools
import threading
import time

SCHEMA = "uri.oi.event.v1"

EVENT_TYPES = {
    "brain.status": "state (READY|LOADING|STOPPED|DEGRADED|...), model_id, owned, detail, identity {artifacts, live}, "
                    "performance? {state, reasons, decode_tps_median, residency, recovery_options}",
    "turn.started": "text_chars, depth",
    "turn.routed": "route (answer|core|plan|harness_choice|escalation_offer), triage, tier {tier, selected_by, reason}",
    "companion.state": "state (idle|listening|thinking|speaking|waiting_user|error)",
    "thinking.progress": "chars (reasoning characters so far; reasoning text is not sent)",
    "answer.delta": "text",
    "answer.done": "status, complete, escalation_candidate, flags, metrics",
    "core.result": "state, code, message, needs (confirmation|clarification|approval|none), intent?, approval_request?",
    "approval.required": "core_turn_id, capability_id, arguments, approval_digest, effect, reversible",
    "plan.proposed": "task_id, goal, steps[], clarifications[], problems[], downgraded[]",
    "task.step": "task_id, step_id, state, core_code?",
    "harness.choice_required": "options[], recommendation, recommendation_reason, requires_user_choice, excluded[]",
    "escalation.offer": "reason, options (harness.choice_required data)",
    "error": "code, message, recoverable, recovery_options[]",
    "turn.finished": "status, route, total_s",
    # Text intelligence (docs/text_intelligence/TI_BLUEPRINT.md): drafts are language work; no outcome of any action.
    "draft.updated": "op (created|revised|corrected|rewritten|restored|undo|redo|show|original|unchanged|discard), "
                     "draft (DraftDesk snapshot or null)",
    "draft.clarify": "question, draft (snapshot or null)",
    "draft.progress": "chars (structured output characters so far)",
}

COMPANION_STATES = ("idle", "listening", "thinking", "speaking", "waiting_user", "error")


class EventSink:
    """Collects events and forwards them to an optional callback (SSE writer, UI bridge, test)."""

    def __init__(self, callback=None):
        self.callback = callback
        self.events = []
        self._seq = itertools.count(1)
        self._lock = threading.Lock()

    def emit(self, turn_id, type_, **data):
        if type_ not in EVENT_TYPES:
            raise ValueError("UNKNOWN_EVENT_TYPE:" + type_)
        with self._lock:
            ev = {"schema": SCHEMA, "seq": next(self._seq), "t": round(time.time(), 3), "turn_id": turn_id,
                  "type": type_, "data": data}
            self.events.append(ev)
        if self.callback:
            self.callback(ev)
        return ev


def simulate(scenario="answer", turn_id="sim-turn"):
    """Deterministic event sequences for UI development (no runtime needed)."""
    sink = EventSink()
    e = lambda t, **d: sink.emit(turn_id, t, **d)
    e("brain.status", state="READY", model_id="qwen3.6-35b-a3b-ud-iq3_s", owned=False, detail=None, identity={})
    e("turn.started", text_chars=24, depth="auto")
    e("companion.state", state="thinking")
    if scenario == "answer":
        e("turn.routed", route="answer", triage={"kind": "QUESTION"},
          tier={"tier": "FAST", "selected_by": "policy", "reason": "simple_language_task"})
        e("companion.state", state="speaking")
        for part in ("An office order ", "is a formal ", "internal directive."):
            e("answer.delta", text=part)
        e("answer.done", status="COMPLETE", complete=True, escalation_candidate=False, flags=[],
          metrics={"first_answer_s": 0.26, "total_s": 0.73})
    elif scenario == "reasoning":
        e("turn.routed", route="answer", triage={"kind": "ANALYSIS"},
          tier={"tier": "NORMAL", "selected_by": "policy", "reason": "analysis_or_planning"})
        for n in (400, 800, 1149):
            e("thinking.progress", chars=n)
        e("companion.state", state="speaking")
        e("answer.delta", text="The train arrives at 12:40.")
        e("answer.done", status="COMPLETE", complete=True, escalation_candidate=False, flags=[], metrics={"total_s": 3.6})
    elif scenario == "approval":
        e("turn.routed", route="core", triage={"kind": "ACTION"},
          tier={"tier": "FAST", "selected_by": "core_seam", "reason": "core_decides_actions_on_fast_seams"})
        e("core.result", state="reply", code="INTENT_CONFIRMATION_REQUIRED", message="Remember: 'my car is blue'?",
          needs="confirmation")
        e("companion.state", state="waiting_user")
        e("approval.required", core_turn_id="core-turn-1", capability_id="remember_fact",
          arguments={"action": "remember", "inputs": {"request_text": "remember that my car is blue"}},
          approval_digest="0" * 64, effect="local_write", reversible=True)
    elif scenario == "error":
        e("turn.routed", route="answer", triage={"kind": "QUESTION"},
          tier={"tier": "FAST", "selected_by": "policy", "reason": "simple_language_task"})
        e("error", code="BRAIN_UNAVAILABLE", message="The local Brain is not running.", recoverable=True,
          recovery_options=["start_brain", "retry", "choose_other_source"])
        e("companion.state", state="error")
    elif scenario == "plan":
        e("turn.routed", route="plan", triage={"kind": "MULTI_STEP"},
          tier={"tier": "NORMAL", "selected_by": "policy", "reason": "analysis_or_planning"})
        e("plan.proposed", task_id="00000000-0000-0000-0000-000000000001", goal="Draft and save a note",
          steps=[{"id": "s1", "kind": "answer", "description": "Draft the note"},
                 {"id": "s2", "kind": "action", "description": "Remember the deadline", "depends_on": ["s1"]}],
          clarifications=[], problems=[], downgraded=[])
        e("companion.state", state="waiting_user")
    elif scenario == "quota":
        e("turn.routed", route="core", triage={"kind": "HARNESS"},
          tier={"tier": "FAST", "selected_by": "core_seam", "reason": "core_decides_actions_on_fast_seams"})
        e("core.result", state="waiting_for_model", code="WAITING_FOR_MODEL",
          message="The selected provider is out of quota. Your task is saved.", needs="none")
        e("harness.choice_required", options=[{"provider": "claude_code", "usable": False, "why_not": "AUTH_NOT_LOGGED_IN"}],
          recommendation=None, recommendation_reason="no_usable_provider", requires_user_choice=True, excluded=["codex"])
        e("companion.state", state="waiting_user")
    else:
        raise ValueError("UNKNOWN_SCENARIO")
    e("turn.finished", status="ok" if scenario != "error" else "error", route=scenario, total_s=0.0)
    return sink.events
