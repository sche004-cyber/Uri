import json

import pytest

from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence import harness_choice as H
from uri_operational_intelligence.events import EVENT_TYPES, EventSink, simulate
from uri_operational_intelligence.orchestrator import Orchestrator, step_state_for
from uri_operational_intelligence.runtime_v1 import Readiness
from uri_operational_intelligence.task_ledger import TaskLedger
from tests.oi.fake_llama import FakeLlama

SEL = {"kind": "server_local_model", "provider": "llamacpp-runtime-v1", "model": "m"}


class FakeCore:
    def __init__(self, replies=None):
        self.calls, self.replies = [], list(replies or [])

    def _next(self, default):
        return self.replies.pop(0) if self.replies else default

    def begin(self, text, session_id, selection):
        self.calls.append(("begin", text, selection))
        return self._next({"turn_id": "t1", "state": "reply", "code": "CONVERSATION", "message": "m"})

    def confirm(self, session_id, selection, turn):
        self.calls.append(("confirm", turn["turn_id"]))
        return self._next({"turn_id": "t2", "state": "approval_required", "code": "APPROVAL_REQUIRED",
                           "approval_request": {"capability_id": "remember_fact", "arguments": {}, "approval_digest": "0" * 64}})

    def decide(self, text, session_id, selection, turn, approve):
        self.calls.append(("decide", approve))
        return self._next({"turn_id": "t2", "state": "reply", "code": "SETTLED_VERIFIED"})

    def continue_waiting(self, *a):
        raise AssertionError("not used")


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def orch(fake, tmp_path, core=None, ready=True, statuses=None):
    rd = (lambda: Readiness("READY" if ready else "STOPPED", fake.url))
    return Orchestrator(client=BC.BrainClient(fake.url), core=core, brain_selection=SEL, ledger=TaskLedger(tmp_path),
                        capability_ids={"remember_fact", "external_harness_task"}, readiness=rd,
                        harness_statuses=statuses or (lambda: []))


def types(out):
    return [e["type"] for e in out.events]


def test_simple_question_never_calls_core(fake, tmp_path):
    core = FakeCore()
    fake.scripts.append({"chunks": [("answer", "An office order is ...")], "finish": "stop"})
    out = orch(fake, tmp_path, core).handle_turn("What is an office order?", "s")
    assert out.route == "answer" and out.status == "ok" and core.calls == []
    assert out.tier["tier"] == "FAST" and len(fake.requests) == 1
    t = types(out)
    assert t[0] == "turn.started" and "answer.delta" in t and "answer.done" in t and "turn.finished" in t
    assert all(e["type"] in EVENT_TYPES for e in out.events)


def test_action_goes_to_core_with_the_explicit_brain_selection(fake, tmp_path):
    core = FakeCore([{"turn_id": "t1", "state": "reply", "code": "INTENT_CONFIRMATION_REQUIRED", "message": "ok?",
                      "confirmation": {"intent_id": "i", "revision": 1, "digest": "d"}}])
    out = orch(fake, tmp_path, core).handle_turn("remember that my car is blue", "s")
    assert out.route == "core" and out.status == "needs_user"
    assert core.calls == [("begin", "remember that my car is blue", SEL)] and fake.requests == []
    ev = [e for e in out.events if e["type"] == "core.result"][0]
    assert ev["data"]["needs"] == "confirmation"


def test_answer_channel_marker_reroutes_to_core_without_showing_text(fake, tmp_path):
    core = FakeCore([{"turn_id": "t1", "state": "approval_required", "code": "APPROVAL_REQUIRED",
                      "approval_request": {"capability_id": "remember_fact", "arguments": {"x": 1},
                                           "approval_digest": "a" * 64, "effect": "local_write", "reversible": True}}])
    fake.scripts.append({"chunks": [("answer", "<<ACTION>>")], "finish": "stop"})
    out = orch(fake, tmp_path, core).handle_turn("my wifi password is hunter22, keep that somewhere safe", "s")
    assert out.route == "core" and core.calls[0][0] == "begin"
    assert "answer.delta" not in types(out) and "approval.required" in types(out)
    routed = [e for e in out.events if e["type"] == "turn.routed"]
    assert routed[0]["data"]["route"] == "answer" and routed[1]["data"]["rerouted_from"] == "answer"


def test_core_conversation_falls_back_to_answer_channel(fake, tmp_path):
    core = FakeCore()   # default: CONVERSATION
    fake.scripts.append({"chunks": [("answer", "Here is a list ...")], "finish": "stop"})
    out = orch(fake, tmp_path, core).handle_turn("make a list of 5 ideas for a school fair", "s")
    assert out.route == "core+answer" and out.status == "ok" and out.core["code"] == "CONVERSATION"


def test_core_failure_is_reported_never_guessed(fake, tmp_path):
    class Boom(FakeCore):
        def begin(self, *a):
            raise RuntimeError("server down")
    out = orch(fake, tmp_path, Boom()).handle_turn("delete the old drafts", "s")
    assert out.status == "error" and [e for e in out.events if e["type"] == "error"][0]["data"]["code"] == "CORE_ERROR"
    out2 = orch(fake, tmp_path, None).handle_turn("delete the old drafts", "s")
    assert out2.status == "error"


def test_brain_not_ready_is_an_honest_error(fake, tmp_path):
    out = orch(fake, tmp_path, FakeCore(), ready=False).handle_turn("What is VRAM?", "s")
    err = [e for e in out.events if e["type"] == "error"][0]["data"]
    assert out.status == "error" and err["code"] == "BRAIN_UNAVAILABLE" and "start_brain" in err["recovery_options"]
    assert fake.requests == []


def test_harness_request_needs_explicit_choice_and_calls_nothing(fake, tmp_path):
    core = FakeCore()
    statuses = lambda: [H.HarnessStatus("codex", "Codex", "QUALIFIED_RUN_SCOPED", auth="OK", offered_by_policy=True)]
    out = orch(fake, tmp_path, core, statuses=statuses).handle_turn("Fix the failing unit tests in the repo", "s")
    assert out.status == "needs_harness_choice" and out.harness["recommendation"] == "codex"
    assert out.harness["requires_user_choice"] and core.calls == [] and fake.requests == []


def test_deep_depth_is_an_escalation_offer_not_local_unbounded_thinking(fake, tmp_path):
    out = orch(fake, tmp_path, FakeCore()).handle_turn("What is VRAM?", "s", depth="deep")
    assert out.route == "escalation_offer" and fake.requests == []


def test_cancel_turn(fake, tmp_path):
    import threading
    fake.scripts.append({"chunks": [("answer", "x")] * 300, "finish": "stop", "delay": 0.01})
    o = orch(fake, tmp_path, FakeCore())
    threading.Timer(0.4, lambda: o.cancel("turn-c")).start()
    out = o.handle_turn("Tell me a long story", "s", turn_id="turn-c")
    assert out.status == "cancelled" and out.answer["status"] == "CANCELLED"


def test_multi_step_plan_then_steps_through_core(fake, tmp_path):
    text = "Remember that the audit is on Monday, then draft a checklist for it"
    plan = {"goal": "g", "clarifications": [], "steps": [
        {"id": "s1", "description": "remember", "kind": "action", "capability": "remember_fact",
         "source_span": "Remember that the audit is on Monday", "depends_on": []},
        {"id": "s2", "description": "Draft a checklist for the audit", "kind": "answer", "capability": None,
         "source_span": None, "depends_on": ["s1"]}]}
    fake.scripts.append({"json": json.dumps(plan), "finish": "stop"})
    core = FakeCore([{"turn_id": "c1", "state": "reply", "code": "INTENT_CONFIRMATION_REQUIRED",
                      "confirmation": {"intent_id": "i", "revision": 1, "digest": "d"}}])
    o = orch(fake, tmp_path, core)
    # triage would see one action verb at the start + an answer step; force the plan path explicitly
    from uri_operational_intelligence import triage as T, reasoning_policy as RP
    sink = EventSink()
    out = o._plan_turn(text, "s", T.Triage(T.MULTI_STEP), RP.decide(T.MULTI_STEP), lambda t, **d: sink.emit("x", t, **d), "x")
    assert out.status == "awaiting_plan_approval"
    tid = out.task_id
    assert o.advance(tid)["status"] == "not_running"            # nothing runs before the user approves the plan
    o.approve_plan(tid)
    r = o.advance(tid)
    assert core.calls[0] == ("begin", "Remember that the audit is on Monday", SEL)   # user's verbatim words
    assert r["status"] == "step_waiting_confirmation"
    env = o.core.confirm("s", SEL, r["core"])
    assert o.record_step(tid, "s1", env)["status"] == "step_waiting_approval"
    assert o.decide_step(tid, "s1", env, True)["status"] == "step_verified"
    fake.scripts.append({"chunks": [("answer", "Checklist: ...")], "finish": "stop"})
    assert o.advance(tid)["status"] == "step_done"
    assert o.ledger.get(tid)["state"] == "COMPLETED"


def test_uncertain_step_blocks_dependents(fake, tmp_path):
    o = orch(fake, tmp_path, FakeCore([{"turn_id": "c1", "state": "execution_uncertain", "code": "SETTLED_EXECUTION_UNCERTAIN"}]))
    plan = {"goal": "g", "clarifications": [], "steps": [
        {"id": "s1", "description": "a", "kind": "action", "capability": "remember_fact", "source_span": "x", "depends_on": []},
        {"id": "s2", "description": "b", "kind": "answer", "capability": None, "source_span": None, "depends_on": ["s1"]}]}
    tid = o.ledger.create(session_id="s", request_text="x", plan=plan, state="RUNNING")["task_id"]
    assert o.advance(tid)["status"] == "step_uncertain"
    o.advance(tid)
    t = o.ledger.get(tid)
    assert [s["state"] for s in t["steps"]] == ["UNCERTAIN", "SKIPPED"] and t["state"] == "NEEDS_ATTENTION"
    assert len(o.core.calls) == 1        # never retried


@pytest.mark.parametrize("env,state", [
    ({"state": "approval_required"}, "WAITING_APPROVAL"),
    ({"state": "reply", "code": "SETTLED_VERIFIED"}, "VERIFIED"),
    ({"state": "execution_uncertain", "code": "SETTLED_EXECUTION_UNCERTAIN"}, "UNCERTAIN"),
    ({"state": "failed", "code": "SETTLED_FAILED"}, "FAILED"),
    ({"state": "cancelled", "code": "APPROVAL_DENIED"}, "CANCELLED"),
    ({"state": "reply", "code": "REFUSED_PERMISSION_DENIED"}, "REFUSED"),
    ({"state": "reply", "code": "WAITING_FOR_MODEL"}, "WAITING_USER_CHOICE"),
    ({"state": "reply", "code": "SOMETHING_NEW"}, "FAILED"),
    ({"state": "failed", "code": "SELECTED_MODEL_UNAVAILABLE"}, "FAILED"),
])
def test_core_envelope_mapping_never_reads_unknown_as_success(env, state):
    assert step_state_for(env) == state


@pytest.mark.parametrize("scenario", ["answer", "reasoning", "approval", "error", "plan", "quota"])
def test_simulator_emits_only_contract_events(scenario):
    evs = simulate(scenario)
    assert evs[0]["type"] == "brain.status" and evs[-1]["type"] == "turn.finished"
    assert all(e["type"] in EVENT_TYPES and e["schema"] == "uri.oi.event.v1" for e in evs)
    assert [e["seq"] for e in evs] == list(range(1, len(evs) + 1))


def test_core_path_with_brain_down_fails_fast_without_calling_core(fake, tmp_path):
    core = FakeCore()
    out = orch(fake, tmp_path, core, ready=False).handle_turn("remember that the lab is closed", "s")
    assert out.status == "error" and core.calls == []
    assert [e for e in out.events if e["type"] == "error"][0]["data"]["code"] == "BRAIN_UNAVAILABLE"


def test_perf_monitor_detects_throughput_and_residency_degradation():
    from uri_operational_intelligence.perf_monitor import PerfMonitor
    samples = iter([(15534.0, 1101.0), (14845.0, 1895.0)])
    pm = PerfMonitor(sampler=lambda pid: next(samples))
    pm.set_baseline(42)
    for _ in range(3):
        pm.record({"predicted_n": 400, "predicted_per_second": 37.0})
    pm.record({"predicted_n": 10, "predicted_per_second": 5.0})     # short calls are ignored
    h = pm.assess(pid=42)
    assert h["state"] == "DEGRADED" and set(h["reasons"]) == {"DECODE_THROUGHPUT_LOW", "VRAM_RESIDENCY_EVICTED"}
    assert h["residency"]["dedicated_drop_mib"] == 689.0 and "restart_brain" in h["recovery_options"]
    ok = PerfMonitor(sampler=lambda pid: (15534.0, 1101.0))
    for _ in range(3):
        ok.record({"predicted_n": 400, "predicted_per_second": 115.0})
    assert ok.assess(sample=False)["state"] == "HEALTHY"
    assert PerfMonitor().assess(sample=False)["state"] == "UNKNOWN"


def test_orchestrator_surfaces_degraded_brain(fake, tmp_path):
    from uri_operational_intelligence.perf_monitor import PerfMonitor
    pm = PerfMonitor(sampler=lambda pid: (None, None))
    for _ in range(3):
        pm.record({"predicted_n": 400, "predicted_per_second": 30.0})
    o = orch(fake, tmp_path, FakeCore())
    o.perf = pm
    fake.scripts.append({"chunks": [("answer", "ok")], "finish": "stop"})
    out = o.handle_turn("What is VRAM?", "s")
    st = [e for e in out.events if e["type"] == "brain.status"]
    assert st and st[0]["data"]["state"] == "DEGRADED" and out.status == "ok"
