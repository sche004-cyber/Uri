import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence.orchestrator import Orchestrator
from uri_operational_intelligence.runtime_v1 import Readiness
from uri_operational_intelligence.server import create_app
from uri_operational_intelligence.task_ledger import TaskLedger
from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore, SEL

TOKEN = "t" * 40
H = {"Authorization": "Bearer " + TOKEN}


@pytest.fixture
def env(tmp_path):
    with FakeLlama() as fake:
        o = Orchestrator(client=BC.BrainClient(fake.url), core=FakeCore(), brain_selection=SEL, ledger=TaskLedger(tmp_path),
                         readiness=lambda: Readiness("READY", fake.url))
        with TestClient(create_app(token=TOKEN, orchestrator=o)) as http:
            yield fake, o, http


def events(resp):
    return [json.loads(line[5:]) for line in resp.iter_lines() if line.startswith("data:")]


def test_auth_required_everywhere(env):
    _, _, http = env
    assert http.get("/oi/v1/brain/status").status_code == 401
    assert http.post("/oi/v1/turns", json={"text": "hi", "session_id": "s"}).status_code == 401
    assert http.get("/oi/v1/simulate/answer", headers={"Authorization": "Bearer wrong"}).status_code == 401


def test_turn_streams_contract_events(env):
    fake, _, http = env
    fake.scripts.append({"chunks": [("answer", "A "), ("answer", "B")], "finish": "stop"})
    with http.stream("POST", "/oi/v1/turns", json={"text": "What is VRAM?", "session_id": "s"}, headers=H) as r:
        evs = events(r)
    types = [e["type"] for e in evs]
    assert types[0] == "turn.started" and types[-1] == "companion.state" and "turn.finished" in types
    assert "".join(e["data"]["text"] for e in evs if e["type"] == "answer.delta") == "A B"


def test_cancel_over_http(env):
    fake, o, http = env
    fake.scripts.append({"chunks": [("answer", "x")] * 400, "finish": "stop", "delay": 0.01})
    threading.Timer(0.5, lambda: http.post("/oi/v1/turns/T1/cancel", headers=H)).start()
    t0 = time.monotonic()
    with http.stream("POST", "/oi/v1/turns", json={"text": "Tell me a long story", "session_id": "s", "turn_id": "T1"},
                     headers=H) as r:
        evs = events(r)
    done = [e for e in evs if e["type"] == "answer.done"][0]["data"]
    assert done["status"] == "CANCELLED" and time.monotonic() - t0 < 3.0


def test_bad_depth_and_simulator(env):
    _, _, http = env
    assert http.post("/oi/v1/turns", json={"text": "x", "session_id": "s", "depth": "unbounded"}, headers=H).status_code == 422
    with http.stream("GET", "/oi/v1/simulate/approval", headers=H) as r:
        evs = events(r)
    assert any(e["type"] == "approval.required" for e in evs)
    assert http.get("/oi/v1/simulate/nope", headers=H).status_code == 404


def test_internal_error_still_finishes_the_stream(env):
    _, o, http = env
    o.handle_turn = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    with http.stream("POST", "/oi/v1/turns", json={"text": "x", "session_id": "s"}, headers=H) as r:
        evs = events(r)
    assert [e["type"] for e in evs] == ["error", "turn.finished"] and evs[0]["data"]["code"] == "OI_INTERNAL"
