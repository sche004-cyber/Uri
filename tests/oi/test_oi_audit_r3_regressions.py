"""Regression tests for the Codex audit round-3 findings (2026-10-08)."""
import copy
import os
import threading
import time

import pytest

from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence import planner as P
from uri_operational_intelligence import runtime_v1 as R
from uri_operational_intelligence.orchestrator import Orchestrator
from uri_operational_intelligence.runtime_v1 import Readiness
from uri_operational_intelligence.task_ledger import LedgerError, TaskLedger
from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import SEL, FakeCore

PLAN = {"goal": "g", "clarifications": [], "steps": [
    {"id": "s1", "description": "a", "kind": "action", "capability": "remember_fact", "source_span": "x", "depends_on": []},
    {"id": "s2", "description": "b", "kind": "answer", "capability": None, "source_span": None, "depends_on": ["s1"]}]}


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def orch(fake, tmp_path, core):
    return Orchestrator(client=BC.BrainClient(fake.url), core=core, brain_selection=SEL, ledger=TaskLedger(tmp_path),
                        readiness=lambda: Readiness("READY", fake.url))


def waiting_approval_task(o):
    tid = o.ledger.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    o.ledger.set_step(tid, "s1", "IN_CORE", core={"turn_id": "core-1", "state": None, "code": None})
    o.ledger.set_step(tid, "s1", "WAITING_APPROVAL", core={"turn_id": "core-1", "state": "approval_required"})
    return tid


# R3-1 (High): the single-turn decide() cannot be used on a plan step's Core turn.
def test_decide_refuses_plan_step_turns(fake, tmp_path):
    core = FakeCore()
    o = orch(fake, tmp_path, core)
    tid = waiting_approval_task(o)
    with pytest.raises(LedgerError) as e:
        o.decide("x", "s", {"turn_id": "core-1"}, True)
    assert str(e.value) == "PLAN_STEP_TURN_USE_DECIDE_STEP" and core.calls == []
    assert o.ledger.get(tid)["steps"][0]["state"] == "WAITING_APPROVAL"
    o.decide("x", "s", {"turn_id": "unrelated-single-turn"}, True)      # single turns still work
    assert core.calls == [("decide", True)]


# R3-2 (High): every READY probe re-checks artifacts; losing one after a READY makes the next probe fail.
def test_ready_rechecked_on_every_probe(tmp_path, monkeypatch):
    import hashlib
    from tests.oi.test_oi_runtime_v1 import _cfg_for
    files = {n: n.encode() for n in ["llama-server.exe", "ggml-vulkan.dll", "model.gguf", "mmproj.gguf", "mtp.gguf"]}
    monkeypatch.setattr(R, "VULKAN_DLL_SHA256", hashlib.sha256(files["ggml-vulkan.dll"]).hexdigest())
    cfg = _cfg_for(tmp_path, files)
    mgr = R.RuntimeManager(cfg, tmp_path / "s")
    props = {"reachable": True, "health_status": 200, "model_path": cfg["model"]["path"], "n_ctx": 32768,
             "build_info": "b11425-e117148a4", "total_slots": 1}
    monkeypatch.setattr(R, "probe_server", lambda url, timeout=2.0: props)
    monkeypatch.setattr(R, "_listener_pid", lambda port: os.getpid())
    monkeypatch.setattr(R, "inspect_process", lambda pid, cfg: {"pid": pid, "authorized": True, "reason": None})
    first = mgr.status()
    assert first.state == R.READY and first.live_identity["process"]["create_time"] is not None
    os.remove(cfg["model"]["path"])
    second = mgr.status()
    assert second.state == R.IDENTITY_MISMATCH and "ARTIFACT_MISSING" in second.detail


# R3-3 (High): hyphen/punctuation boundaries.
@pytest.mark.parametrize("text,span,ok", [
    ("Please de-activate account 42.", "activate account", False),
    ("Please de-activate account 42.", "-activate account", False),
    ("Don't re-send the invoice.", "send the invoice", False),
    ("Email: send it (now)", "send it (now)", True),
    ("Please activate account 42.", "activate account", True),
])
def test_span_boundaries(text, span, ok):
    assert (P.exact_user_span(text, span) is not None) is ok


# R3-4 (Medium): recovery requires exclusive ledger ownership; a second process cannot reset a live owner's steps.
def test_recovery_requires_ledger_ownership(tmp_path):
    a, b = TaskLedger(tmp_path), TaskLedger(tmp_path)
    with pytest.raises(LedgerError) as e:
        a.recover()
    assert str(e.value) == "NOT_LEDGER_OWNER"
    a.acquire_owner()
    try:
        with pytest.raises(LedgerError) as e2:
            b.acquire_owner()
        assert str(e2.value) == "LEDGER_OWNED_BY_ANOTHER_PROCESS"
        assert a.recover() == []
    finally:
        a.release_owner()
    b.acquire_owner()
    b.release_owner()


# R3-5 (Medium): confirm_step claims first; EXECUTING never ends in a non-outcome state.
def test_concurrent_confirm_step_reaches_core_once(fake, tmp_path):
    calls = []

    class SlowCore(FakeCore):
        def confirm(self, session_id, selection, turn):
            calls.append(turn["turn_id"])
            time.sleep(0.3)
            return {"turn_id": "c2", "state": "approval_required", "code": "APPROVAL_REQUIRED",
                    "approval_request": {"capability_id": "remember_fact", "arguments": {}, "approval_digest": "0" * 64}}

    o = orch(fake, tmp_path, SlowCore())
    tid = o.ledger.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    o.ledger.set_step(tid, "s1", "IN_CORE")
    o.ledger.set_step(tid, "s1", "WAITING_CONFIRMATION", core={"turn_id": "c1"})
    res = []
    ts = [threading.Thread(target=lambda: res.append(o.confirm_step(tid, "s1", {"turn_id": "c1"}))) for _ in range(3)]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert len(calls) == 1 and sorted(r["status"] for r in res).count("not_claimed") == 2


def test_unexpected_reply_after_approval_is_uncertain(fake, tmp_path):
    core = FakeCore([{"turn_id": "core-1", "state": "approval_required", "code": "APPROVAL_REQUIRED",
                      "approval_request": {"capability_id": "remember_fact", "arguments": {}, "approval_digest": "0" * 64}}])
    o = orch(fake, tmp_path, core)
    tid = waiting_approval_task(o)
    r = o.decide_step(tid, "s1", {"turn_id": "core-1"}, True)
    assert r["status"] == "step_uncertain" and o.ledger.get(tid)["steps"][0]["state"] == "UNCERTAIN"
