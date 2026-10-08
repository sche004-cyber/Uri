"""Regression tests for the Codex audit round-2 findings (2026-10-08)."""
import copy
import threading
import time

import pytest

from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence import planner as P
from uri_operational_intelligence import runtime_v1 as R
from uri_operational_intelligence.orchestrator import Orchestrator
from uri_operational_intelligence.runtime_v1 import Readiness
from uri_operational_intelligence.task_ledger import LedgerError, TaskLedger
from tests.oi.fake_llama import FakeLlama, free_port
from tests.oi.test_oi_orchestrator import SEL, FakeCore

PLAN = {"goal": "g", "clarifications": [], "steps": [
    {"id": "s1", "description": "a", "kind": "action", "capability": "remember_fact", "source_span": "x", "depends_on": []},
    {"id": "s2", "description": "b", "kind": "answer", "capability": None, "source_span": None, "depends_on": ["s1"]}]}


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


# R2-1 (High): concurrent advance() must reach Core.begin at most once (threads AND separate ledger instances).
def test_concurrent_advance_dispatches_once(fake, tmp_path):
    calls = []

    class SlowCore(FakeCore):
        def begin(self, text, session_id, selection):
            calls.append(text)
            time.sleep(0.3)
            return {"turn_id": "t", "state": "reply", "code": "INTENT_CONFIRMATION_REQUIRED",
                    "confirmation": {"intent_id": "i", "revision": 1, "digest": "d"}}

    core = SlowCore()
    mk = lambda: Orchestrator(client=BC.BrainClient(fake.url), core=core, brain_selection=SEL,
                              ledger=TaskLedger(tmp_path), readiness=lambda: Readiness("READY", fake.url))
    a, b = mk(), mk()                         # two orchestrators, two ledger objects, same files
    tid = a.ledger.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    results = []
    threads = [threading.Thread(target=lambda o=o: results.append(o.advance(tid))) for o in (a, b, a, b)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(calls) == 1
    assert sorted(r["status"] for r in results).count("step_waiting_confirmation") == 1


def test_claim_cannot_be_taken_twice(tmp_path):
    L = TaskLedger(tmp_path)
    tid = L.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    L.set_step(tid, "s1", "IN_CORE")
    with pytest.raises(LedgerError) as e:
        TaskLedger(tmp_path).set_step(tid, "s1", "IN_CORE")
    assert str(e.value) == "STEP_ALREADY_CLAIMED"


# R2-2 (High): spans match whole words only.
@pytest.mark.parametrize("text,span", [
    ("Please deactivate account 42 today.", "activate account"),
    ("Unsubscribe me from the newsletter.", "subscribe me"),
    ("Reschedule the meeting.", "schedule the meeting"),
])
def test_partial_word_spans_rejected(text, span):
    p = {"goal": "g", "clarifications": [], "steps": [
        {"id": "s1", "description": "x", "kind": "action", "capability": "remember_fact", "source_span": span, "depends_on": []}]}
    s = P.validate_plan(p, text, {"remember_fact"})["plan"]["steps"][0]
    assert s["kind"] == "ask_user" and s["unusable_reason"] == "SOURCE_SPAN_NOT_VERBATIM"


def test_whole_word_span_still_accepted():
    assert P.exact_user_span("Please activate account 42.", "activate account") == "activate account"
    assert P.exact_user_span("Email: send it (now)", "send it (now)") == "send it (now)"


# R2-3 (High): no path from an approval to an outcome without EXECUTING.
def test_record_step_cannot_settle_an_approval_directly(fake, tmp_path):
    o = Orchestrator(client=BC.BrainClient(fake.url), core=FakeCore(), brain_selection=SEL, ledger=TaskLedger(tmp_path))
    tid = o.ledger.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    o.ledger.set_step(tid, "s1", "IN_CORE")
    o.ledger.set_step(tid, "s1", "WAITING_APPROVAL")
    with pytest.raises(LedgerError):
        o.record_step(tid, "s1", {"turn_id": "t", "state": "reply", "code": "SETTLED_VERIFIED"})
    assert o.ledger.get(tid)["steps"][0]["state"] == "WAITING_APPROVAL"


# R2-4 (High): status() never says READY without verified artifacts for the live instance.
def test_status_ready_requires_artifacts(tmp_path, monkeypatch):
    cfg = copy.deepcopy(R.load_config())
    cfg["model"]["path"] = str(tmp_path / "missing.gguf")
    mgr = R.RuntimeManager(cfg, tmp_path / "s")
    props = {"reachable": True, "health_status": 200, "model_path": cfg["model"]["path"], "n_ctx": 32768,
             "build_info": "b11425-e117148a4", "total_slots": 1}
    monkeypatch.setattr(R, "probe_server", lambda url, timeout=2.0: props)
    monkeypatch.setattr(R, "_listener_pid", lambda port: 4242)
    monkeypatch.setattr(R, "inspect_process", lambda pid, cfg: {"pid": pid, "authorized": True, "reason": None})
    r = mgr.status()
    assert r.state == R.IDENTITY_MISMATCH and "ARTIFACT_MISSING" in r.detail


# R2-5 (Medium): Core declining an ACTION step as conversation is not success; dependents do not run.
def test_action_step_conversation_is_refused_and_blocks_dependents(fake, tmp_path):
    core = FakeCore([{"turn_id": "t", "state": "reply", "code": "CONVERSATION"}])
    o = Orchestrator(client=BC.BrainClient(fake.url), core=core, brain_selection=SEL, ledger=TaskLedger(tmp_path),
                     readiness=lambda: Readiness("READY", fake.url))
    tid = o.ledger.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    assert o.advance(tid)["status"] == "step_refused"
    o.advance(tid)
    t = o.ledger.get(tid)
    assert [s["state"] for s in t["steps"]] == ["REFUSED", "SKIPPED"] and t["state"] == "NEEDS_ATTENTION"
    assert fake.requests == []
