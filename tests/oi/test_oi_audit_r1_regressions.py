"""Regression tests for the Codex audit round-1 findings (2026-10-08). One test (or more) per finding."""
import copy
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence import harness_choice as H
from uri_operational_intelligence import planner as P
from uri_operational_intelligence import runtime_v1 as R
from uri_operational_intelligence.orchestrator import Orchestrator, core_turn_status, step_state_for
from uri_operational_intelligence.runtime_v1 import Readiness
from uri_operational_intelligence.server import create_app
from uri_operational_intelligence.task_ledger import TaskLedger
from tests.oi.fake_llama import FakeLlama, free_port
from tests.oi.test_oi_orchestrator import SEL, FakeCore

PLAN = {"goal": "g", "clarifications": [], "steps": [
    {"id": "s1", "description": "a", "kind": "action", "capability": "remember_fact", "source_span": "x", "depends_on": []},
    {"id": "s2", "description": "b", "kind": "answer", "capability": None, "source_span": None, "depends_on": ["s1"]},
    {"id": "s3", "description": "c", "kind": "answer", "capability": None, "source_span": None, "depends_on": ["s2"]}]}


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def mk(fake, tmp_path, core):
    return Orchestrator(client=BC.BrainClient(fake.url), core=core, brain_selection=SEL, ledger=TaskLedger(tmp_path),
                        readiness=lambda: Readiness("READY", fake.url),
                        harness_statuses=lambda: [H.HarnessStatus("codex", "Codex", "QUALIFIED", auth="OK", quota="OK",
                                                                  offered_by_policy=True),
                                                  H.HarnessStatus("claude_code", "Claude Code", "QUALIFIED", auth="OK",
                                                                  quota="OK", offered_by_policy=True)])


# F1 (High): crash between approve and record_step must recover as UNCERTAIN, never restart the step.
def test_step_is_durably_executing_before_core_receives_the_approval(fake, tmp_path):
    seen = {}

    class CrashCore(FakeCore):
        def decide(self, text, session_id, selection, turn, approve):
            seen["state_at_decide"] = o.ledger.get(tid)["steps"][0]["state"]
            raise KeyboardInterrupt("process dies here")

    o = mk(fake, tmp_path, CrashCore())
    tid = o.ledger.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    o.ledger.set_step(tid, "s1", "IN_CORE")
    o.ledger.set_step(tid, "s1", "WAITING_APPROVAL", core={"state": "approval_required"})
    with pytest.raises(KeyboardInterrupt):
        o.decide_step(tid, "s1", {"turn_id": "t"}, True)
    assert seen["state_at_decide"] == "EXECUTING"
    # simulate a hard crash: the handler above did not run for BaseException-free paths; recovery decides
    t = o.ledger.get(tid)
    if t["steps"][0]["state"] == "EXECUTING":
        TaskLedger(tmp_path).recover()
    assert o.ledger.get(tid)["steps"][0]["state"] == "UNCERTAIN"
    assert o.advance(tid)["status"] in ("not_running", "no_ready_step")
    assert [c[0] for c in o.core.calls] == []        # Core.begin never called again


def test_decide_step_transport_error_marks_uncertain(fake, tmp_path):
    class Boom(FakeCore):
        def decide(self, *a):
            raise ConnectionError("lost")
    o = mk(fake, tmp_path, Boom())
    tid = o.ledger.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    o.ledger.set_step(tid, "s1", "IN_CORE")
    o.ledger.set_step(tid, "s1", "WAITING_APPROVAL")
    with pytest.raises(ConnectionError):
        o.decide_step(tid, "s1", {"turn_id": "t"}, True)
    assert o.ledger.get(tid)["steps"][0]["state"] == "UNCERTAIN"


def test_decide_step_denied_never_marks_executing(fake, tmp_path):
    core = FakeCore([{"turn_id": "t", "state": "cancelled", "code": "APPROVAL_DENIED"}])
    o = mk(fake, tmp_path, core)
    tid = o.ledger.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    o.ledger.set_step(tid, "s1", "IN_CORE")
    o.ledger.set_step(tid, "s1", "WAITING_APPROVAL")
    o.decide_step(tid, "s1", {"turn_id": "t"}, False)
    assert o.ledger.get(tid)["steps"][0]["state"] == "CANCELLED"
    assert not any(e.get("state") == "EXECUTING" for e in o.ledger.get(tid)["events"] if e["kind"] == "step_state")


# F2 (High): SKIPPED never satisfies a dependency; skips propagate transitively.
def test_skip_propagates_transitively(fake, tmp_path):
    o = mk(fake, tmp_path, FakeCore([{"turn_id": "c", "state": "failed", "code": "SETTLED_FAILED"}]))
    tid = o.ledger.create(session_id="s", request_text="x", plan=PLAN, state="RUNNING")["task_id"]
    o.advance(tid)
    o.advance(tid)
    assert [s["state"] for s in o.ledger.get(tid)["steps"]] == ["FAILED", "SKIPPED", "SKIPPED"]
    assert fake.requests == []                         # no answer step ran on top of the failure


# F3 (High): attaching to a running instance verifies the pinned artifacts; cache binds file identity.
def test_attach_requires_artifact_match(tmp_path, monkeypatch):
    cfg = copy.deepcopy(R.load_config())
    cfg["model"]["path"] = str(tmp_path / "missing.gguf")
    cfg["runtime"]["port"] = free_port()
    mgr = R.RuntimeManager(cfg, tmp_path / "s")
    monkeypatch.setattr(mgr, "status", lambda: Readiness(R.READY, mgr.url, pid=1))
    r = mgr.ensure_ready(start=False)
    assert r.state == R.IDENTITY_MISMATCH and r.detail == "ARTIFACT_MISSING"


def test_hash_cache_requires_file_identity(tmp_path, monkeypatch):
    import hashlib
    from tests.oi.test_oi_runtime_v1 import _cfg_for
    files = {n: n.encode() for n in ["llama-server.exe", "ggml-vulkan.dll", "model.gguf", "mmproj.gguf", "mtp.gguf"]}
    monkeypatch.setattr(R, "VULKAN_DLL_SHA256", hashlib.sha256(files["ggml-vulkan.dll"]).hexdigest())
    cfg = _cfg_for(tmp_path, files)
    state = tmp_path / "st"
    R.verify_artifacts(cfg, state)
    cache_path = state / "artifact_hash_cache.json"
    cache = json.loads(cache_path.read_text())
    assert all("ino" in v and "ctime_ns" in v for v in cache.values())
    for v in cache.values():
        v["ino"] = -1                                   # a different file with restored size/mtime
    cache_path.write_text(json.dumps(cache))
    assert R.verify_artifacts(cfg, state)["methods"] == ["full"]


# F4 (High): clause-level negation and exact user substrings.
@pytest.mark.parametrize("text,span", [
    ("Do not under any circumstances email Ravi.", "email Ravi"),
    ("Please don't, whatever happens tomorrow, delete the reports.", "delete the reports"),
    ("I never want you to send it to the principal.", "send it to the principal"),
])
def test_long_range_negation_rejected(text, span):
    p = {"goal": "g", "clarifications": [], "steps": [
        {"id": "s1", "description": "x", "kind": "action", "capability": "remember_fact", "source_span": span, "depends_on": []}]}
    s = P.validate_plan(p, text, {"remember_fact"})["plan"]["steps"][0]
    assert s["kind"] == "ask_user" and s["unusable_reason"] == "SOURCE_SPAN_NEGATED"


def test_core_receives_the_users_exact_characters():
    text = "Remember  that the Audit is on MONDAY, then draft notes."
    p = {"goal": "g", "clarifications": [], "steps": [
        {"id": "s1", "description": "x", "kind": "action", "capability": "remember_fact",
         "source_span": "remember that the audit is on monday", "depends_on": []}]}
    s = P.validate_plan(p, text, {"remember_fact"})["plan"]["steps"][0]
    assert s["source_span"] == "Remember  that the Audit is on MONDAY"


# F5 (Medium): allowlisted success only.
def test_success_allowlists():
    assert step_state_for({"state": "failed", "code": "SETTLED_VERIFIED"}) == "FAILED"
    assert core_turn_status({"state": "reply", "code": "SOMETHING_NEW"}, "none") == "reported"
    assert core_turn_status({"state": "reply", "code": "SETTLED_VERIFIED"}, "none") == "ok"
    assert core_turn_status({"state": "execution_uncertain", "code": "SETTLED_EXECUTION_UNCERTAIN"}, "none") == "not_verified"
    assert core_turn_status({"state": "reply", "code": "REFUSED_UNSUPPORTED"}, "none") == "refused"


def test_complete_json_unknown_finish_reason_is_not_success(fake):
    fake.scripts.append({"json": "{}", "finish": "weird"})
    r = BC.BrainClient(fake.url).complete_json({"messages": []})
    assert r.status == BC.INTERRUPTED and "UNKNOWN_FINISH_REASON" in r.error


# F6 (Medium): SSE reader disconnect cancels the turn (real uvicorn server: TestClient does not propagate disconnects).
def test_sse_disconnect_cancels_turn(fake, tmp_path):
    import httpx
    import uvicorn
    fake.scripts.append({"chunks": [("answer", "x")] * 600, "finish": "stop", "delay": 0.01})
    o = mk(fake, tmp_path, FakeCore())
    cancelled = []
    real = o.cancel
    o.cancel = lambda tid, reason="user": (cancelled.append((tid, reason)), real(tid, reason))[1]
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(token="k" * 40, orchestrator=o), host="127.0.0.1", port=port,
                                           log_level="error"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.05)
        with httpx.stream("POST", "http://127.0.0.1:%d/oi/v1/turns" % port,
                          json={"text": "tell a long story", "session_id": "s", "turn_id": "D1"},
                          headers={"Authorization": "Bearer " + "k" * 40}, timeout=10) as r:
            for line in r.iter_lines():
                if '"answer.delta"' in line:
                    break
        deadline = time.monotonic() + 8
        while not cancelled and time.monotonic() < deadline:
            time.sleep(0.05)
    finally:
        server.should_exit = True
        th.join(5)
    assert cancelled and cancelled[0] == ("D1", "client_disconnected")


# F7 (Medium): quota pause offers other providers, excludes the exhausted one, selects nothing.
def test_waiting_for_model_emits_choice_without_switching(fake, tmp_path):
    core = FakeCore([{"turn_id": "q", "state": "reply", "code": "WAITING_FOR_MODEL", "message": "quota"}])
    o = mk(fake, tmp_path, core)
    codex = {"kind": "client_external_harness", "provider": "codex", "model": None}
    out = o.begin_harness("refactor the app and run tests", "s", codex)
    ev = [e for e in out.events if e["type"] == "harness.choice_required"][0]["data"]
    assert out.status == "needs_harness_choice" and ev["excluded"] == ["codex"]
    assert ev["recommendation"] == "claude_code" and ev["requires_user_choice"] and ev["selected"] is None
    assert core.calls == [("begin", "refactor the app and run tests", codex)]
