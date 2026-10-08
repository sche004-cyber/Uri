"""Working-system integrated worker bridge (WS blueprint W1, AC-4/5/6/9/10)."""
import threading
import time

import pytest

from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence.orchestrator import Orchestrator
from uri_operational_intelligence.runtime_v1 import Readiness
from uri_operational_intelligence.task_ledger import TaskLedger
from uri_operational_intelligence.worker_bridge import BridgeRefused, IntegratedTurns
from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore

CFG = {"model": {"id": "qwen-test"}, "runtime": {"port": 18470, "ctx": 32768}}
DIGEST = "a" * 64


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


class Frames:
    def __init__(self):
        self.events, self.lock = [], threading.Lock()

    def __call__(self, ev):
        with self.lock:
            self.events.append(ev)

    def types(self, turn_id=None):
        return [e["type"] for e in self.events if turn_id is None or e["turn_id"] == turn_id]

    def data(self, type_):
        return [e["data"] for e in self.events if e["type"] == type_]


def make(fake, tmp_path, core, ready="READY", memory=None):
    status = lambda: Readiness(ready, fake.url, model_id="qwen-test")
    o = Orchestrator(client=BC.BrainClient(fake.url), core=core, brain_selection={}, ledger=TaskLedger(tmp_path),
                     capability_ids={"remember_fact"}, readiness=status, harness_statuses=lambda: [])
    frames = Frames()
    b = IntegratedTurns(orchestrator=o, cfg=CFG, status=status, write_event=frames, memory=memory)
    return b, frames, o


def approval_core(digest=DIGEST):
    return FakeCore([{"turn_id": "c1", "state": "approval_required", "code": "APPROVAL_REQUIRED", "message": "Approve?",
                      "approval_request": {"capability_id": "remember_fact", "arguments": {"inputs": {"request_text": "x"}},
                                           "approval_digest": digest}}])


def test_runtime_v1_is_the_default_selection(fake, tmp_path):
    b, _, o = make(fake, tmp_path, FakeCore())
    assert b.selected == {"kind": "server_local_model", "provider": "llamacpp-runtime-v1", "model": "qwen-test"}
    assert o.brain_selection == b.selected
    cat = b.handle("brain_catalog", {"command": "brain_catalog"})
    sel = [r for r in cat["rows"] if r["selected"]]
    assert [r["id"] for r in sel] == ["runtime-v1"] and cat["fallback"] == "none"
    assert all(not r["selectable"] for r in cat["rows"] if r["id"].startswith("cloud-") or r["id"] == "other-local")


def test_answer_streams_as_events_and_replies_at_once(fake, tmp_path):
    fake.scripts.append({"chunks": [("answer", "Hel"), ("answer", "lo")], "finish": "stop", "delay": 0.05})
    b, frames, _ = make(fake, tmp_path, FakeCore())
    t0 = time.monotonic()
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "What is VRAM?", "depth": "auto"})
    assert time.monotonic() - t0 < 0.5 and r["accepted"]
    b.wait(10)
    t = frames.types(r["turn_id"])
    assert t.count("answer.delta") == 2 and t.index("answer.delta") < t.index("answer.done")
    assert t[-2:] == ["turn.finished", "companion.state"]
    assert "".join(d["text"] for d in frames.data("answer.delta")) == "Hello"
    assert [e["seq"] for e in frames.events] == sorted(e["seq"] for e in frames.events)


def test_reasoning_tier_and_progress_without_reasoning_text(fake, tmp_path):
    fake.scripts.append({"chunks": [("reasoning", "r" * 450), ("answer", "Because.")], "finish": "stop"})
    b, frames, _ = make(fake, tmp_path, FakeCore())
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "depth": "normal",
                             "text": "Compare the pros and cons of two backup strategies"})
    b.wait(10)
    routed = frames.data("turn.routed")[0]
    assert routed["tier"]["tier"] == "NORMAL"
    assert frames.data("thinking.progress")
    assert all("r" * 50 not in str(e["data"]) for e in frames.events)    # reasoning text never leaves the worker
    assert r["turn_id"]


def test_second_turn_refused_while_one_runs_and_cancel_stays_open(fake, tmp_path):
    fake.scripts.append({"chunks": [("answer", "x")] * 400, "finish": "stop", "delay": 0.01})
    b, frames, _ = make(fake, tmp_path, FakeCore())
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "Tell me a long story", "depth": "auto"})
    time.sleep(0.3)
    with pytest.raises(BridgeRefused) as e:
        b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "again", "depth": "auto"})
    assert e.value.code == "TURN_IN_PROGRESS"
    with pytest.raises(BridgeRefused):
        b.handle("memory_list", {"command": "memory_list"})
    assert b.handle("oi_cancel", {"command": "oi_cancel", "turn_id": r["turn_id"]})["cancelled"] is True
    b.wait(10)
    done = frames.data("answer.done")
    assert done and done[-1]["status"] == "CANCELLED"
    assert frames.data("turn.finished")[-1]["status"] == "cancelled"


def test_approval_needs_the_digest_shown_and_typed_text_is_never_a_decision(fake, tmp_path):
    core = approval_core()
    b, frames, _ = make(fake, tmp_path, core)
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "remember that the lab is closed",
                             "depth": "auto"})
    b.wait(10)
    assert frames.data("approval.required")[0]["approval_digest"] == DIGEST
    assert frames.data("turn.finished")[-1]["status"] == "needs_user"
    # A typed "approve" is just another turn: it never reaches a decision path.
    b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "approve", "depth": "auto"})
    b.wait(10)
    assert ("decide", True) not in core.calls
    # The structured decision with the shown digest approves exactly once.
    b.handle("oi_decide", {"command": "oi_decide", "turn_id": r["turn_id"], "approve": True, "approval_digest": DIGEST})
    b.wait(10)
    assert core.calls.count(("decide", True)) == 1
    assert frames.data("core.result")[-1]["code"] == "SETTLED_VERIFIED"
    with pytest.raises(BridgeRefused) as e:
        b.handle("oi_decide", {"command": "oi_decide", "turn_id": r["turn_id"], "approve": True, "approval_digest": DIGEST})
    assert e.value.code == "TURN_NOT_PENDING"


def test_digest_mismatch_drops_and_releases_as_denial(fake, tmp_path):
    core = approval_core()
    b, _, _ = make(fake, tmp_path, core)
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "remember that the lab is closed",
                             "depth": "auto"})
    b.wait(10)
    with pytest.raises(BridgeRefused) as e:
        b.handle("oi_decide", {"command": "oi_decide", "turn_id": r["turn_id"], "approve": True,
                               "approval_digest": "b" * 64})
    assert e.value.code == "APPROVAL_DIGEST_MISMATCH"
    assert ("decide", True) not in core.calls and ("decide", False) in core.calls


def test_deny_changes_nothing_and_is_reported(fake, tmp_path):
    core = approval_core()
    core.replies.append({"turn_id": "c1", "state": "reply", "code": "APPROVAL_DENIED", "message": "Denied."})
    b, frames, _ = make(fake, tmp_path, core)
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "remember that the lab is closed",
                             "depth": "auto"})
    b.wait(10)
    b.handle("oi_decide", {"command": "oi_decide", "turn_id": r["turn_id"], "approve": False, "approval_digest": DIGEST})
    b.wait(10)
    assert ("decide", False) in core.calls and ("decide", True) not in core.calls
    assert frames.data("turn.finished")[-1]["status"] != "ok"


def test_unavailable_runtime_is_an_honest_error_and_deterministic_commands_still_work(fake, tmp_path):
    b, frames, _ = make(fake, tmp_path, FakeCore(), ready="STOPPED", memory=lambda: ["the lab is closed"])
    b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "What is VRAM?", "depth": "auto"})
    b.wait(10)
    assert frames.data("error")[0]["code"] == "BRAIN_UNAVAILABLE"
    assert fake.requests == []                                    # nothing was sent to a model
    assert b.handle("memory_list", {"command": "memory_list"}) == {"facts": ["the lab is closed"],
                                                                   "source": "client_store", "model_used": False}
    assert b.handle("brain_status", {"command": "brain_status"})["state"] == "STOPPED"


def test_explicit_selection_only_and_deterministic_never_falls_back(fake, tmp_path):
    core = FakeCore([{"turn_id": "c1", "state": "reply", "code": "REFUSED_NOT_QUALIFIED", "message": "no"}])
    b, frames, o = make(fake, tmp_path, core)
    with pytest.raises(BridgeRefused):
        b.handle("brain_select", {"command": "brain_select", "row_id": "cloud-anthropic"})
    assert b.handle("brain_select", {"command": "brain_select", "row_id": "deterministic"})["selected"]["provider"] == "uri-deterministic"
    b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "What is VRAM?", "depth": "auto"})
    b.wait(10)
    assert fake.requests == [] and frames.data("error")[0]["code"] == "BRAIN_UNAVAILABLE"
    b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "remember that x is y", "depth": "auto"})
    b.wait(10)
    assert core.calls[0][2]["provider"] == "uri-deterministic"


def test_schema_is_exact(fake, tmp_path):
    b, _, _ = make(fake, tmp_path, FakeCore())
    for bad in ({"command": "oi_turn", "session_id": "s", "text": "x"},
                {"command": "oi_decide", "turn_id": "t", "approve": True},
                {"command": "oi_turn", "session_id": "s", "text": "x", "depth": "auto", "approve": True}):
        with pytest.raises(BridgeRefused):
            b.handle(bad["command"], bad)
    with pytest.raises(BridgeRefused):
        b.handle("oi_turn", {"command": "oi_turn", "session_id": "s", "text": "x", "depth": "turbo"})
