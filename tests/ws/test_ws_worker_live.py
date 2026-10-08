"""LIVE: the real integrated worker (C1 gates) against the real integrated server and, when READY, Runtime v1.

Opt-in, run from the MATERIALIZED runtime after `scripts/ws_provision.py` and with the integrated server started:
    set URI_WS_LIVE=1 && .venv\\Scripts\\python.exe -m pytest tests/ws/test_ws_worker_live.py -s
Optional: URI_WS_EXPECT_BRAIN=READY|STOPPED selects which journeys must hold.
Writes evidence to work/c1/ws-evidence/worker_live_<ts>.json (events are recorded without answer text bodies beyond
the first 200 characters).
"""
import json
import os
import struct
import subprocess
import threading
import time
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("URI_WS_LIVE") != "1", reason="opt-in: URI_WS_LIVE=1")
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = {"journeys": []}


class Worker:
    def __init__(self, current):
        m = json.loads(Path(current["client_manifest"]).read_text(encoding="utf-8"))
        self.p = subprocess.Popen([m["interpreter"], "-B", "-I", str(ROOT / "scripts/run_uri_integrated_worker.py"),
                                   "--manifest", current["client_manifest"]], cwd=m["client_root"],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.replies, self.events, self.cv = [], [], threading.Condition()
        threading.Thread(target=self._read, daemon=True).start()

    def _read(self):
        out = self.p.stdout
        while True:
            h = out.read(4)
            if len(h) < 4:
                break
            body = json.loads(out.read(struct.unpack(">I", h)[0]))
            with self.cv:
                (self.events if "event" in body else self.replies).append(body.get("event", body))
                self.cv.notify_all()

    def call(self, cmd, timeout=120):
        data = json.dumps(cmd).encode()
        with self.cv:
            n = len(self.replies)
        self.p.stdin.write(struct.pack(">I", len(data)) + data)
        self.p.stdin.flush()
        with self.cv:
            assert self.cv.wait_for(lambda: len(self.replies) > n, timeout), "NO_REPLY"
            return self.replies[n]

    def ok(self, cmd, timeout=120):
        r = self.call(cmd, timeout)
        assert r["result"] == "OK", r
        return r["value"]

    def until_finished(self, turn_id, timeout=300, after=0):
        def done():
            return any(e["turn_id"] == turn_id and e["type"] == "turn.finished" for e in self.events[after:])
        with self.cv:
            assert self.cv.wait_for(done, timeout), "TURN_NOT_FINISHED"
            return [e for e in self.events[after:] if e["turn_id"] == turn_id]

    def close(self):
        try:
            self.call({"command": "close"}, timeout=60)
        finally:
            self.p.wait(30)


def record(name, evs, **extra):
    slim = [{"type": e["type"], "seq": e["seq"], "t": e["t"],
             "data": {k: (v[:200] if isinstance(v, str) else v) for k, v in e["data"].items()}} for e in evs]
    EVIDENCE["journeys"].append({"journey": name, "events": slim, **extra})


@pytest.fixture(scope="module")
def w():
    current = json.loads((ROOT / "work/c1/ws-current.json").read_text(encoding="utf-8"))
    EVIDENCE["installation"] = {k: current[k] for k in ("name", "port", "provisioned")}
    worker = Worker(current)
    yield worker
    worker.close()
    EVIDENCE["worker_exit"] = worker.p.returncode
    out = ROOT / "work/c1/ws-evidence" / ("worker_live_%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(EVIDENCE, indent=1, default=str), encoding="utf-8")
    print("EVIDENCE", out)


def brain_state(w):
    return w.ok({"command": "brain_status"})["state"]


def test_preflight_is_the_integrated_profile(w):
    pre = w.ok({"command": "preflight"})
    assert pre["worker_profile"] == "ws-integrated" and pre["production_cutover"] is False
    assert "oi_turn" in pre["oi_commands"] and pre["event_schema"] == "uri.oi.event.v1"
    cat = w.ok({"command": "brain_catalog"})
    assert [r["id"] for r in cat["rows"] if r["selected"]] == ["runtime-v1"]
    EVIDENCE["preflight"] = {k: pre[k] for k in ("worker_profile", "production_cutover", "oi_commands")}
    EVIDENCE["catalog"] = cat
    EVIDENCE["brain_status_start"] = w.ok({"command": "brain_status"})


def test_question_answer_or_honest_unavailable(w):
    n = len(w.events)
    t0 = time.monotonic()
    r = w.ok({"command": "oi_turn", "session_id": str(uuid.uuid4()), "text": "In one sentence, what is VRAM?",
              "depth": "auto"})
    reply_s = time.monotonic() - t0
    evs = w.until_finished(r["turn_id"], after=n)
    types = [e["type"] for e in evs]
    state = brain_state(w)
    if state == "READY":
        assert "answer.delta" in types and evs[[e["type"] for e in evs].index("answer.done")]["data"]["status"] == "COMPLETE"
    else:
        assert [e for e in evs if e["type"] == "error"][0]["data"]["code"] == "BRAIN_UNAVAILABLE"
    record("question", evs, brain=state, reply_s=round(reply_s, 3))


def test_reasoning_turn_when_ready(w):
    if brain_state(w) != "READY":
        pytest.skip("Runtime v1 not READY")
    n = len(w.events)
    r = w.ok({"command": "oi_turn", "session_id": str(uuid.uuid4()), "depth": "normal",
              "text": "Compare keeping school records on paper versus a spreadsheet: two pros and two cons each, briefly."})
    evs = w.until_finished(r["turn_id"], after=n)
    routed = [e for e in evs if e["type"] == "turn.routed"][0]["data"]
    assert routed["tier"]["tier"] == "NORMAL"
    record("reasoning", evs)


def test_cancel_mid_stream_when_ready(w):
    if brain_state(w) != "READY":
        pytest.skip("Runtime v1 not READY")
    n = len(w.events)
    r = w.ok({"command": "oi_turn", "session_id": str(uuid.uuid4()), "depth": "fast",
              "text": "Write a long, detailed story about a lighthouse keeper, at least 800 words."})
    with w.cv:
        w.cv.wait_for(lambda: any(e["turn_id"] == r["turn_id"] and e["type"] == "answer.delta" for e in w.events[n:]), 120)
    assert w.ok({"command": "oi_cancel", "turn_id": r["turn_id"]})["cancelled"] is True
    evs = w.until_finished(r["turn_id"], after=n)
    done = [e for e in evs if e["type"] == "answer.done"][0]["data"]
    assert done["status"] == "CANCELLED"
    record("cancel", evs)


def _remember(w, text, approve):
    """Action through Core. Uses the Brain row when READY, otherwise the explicit deterministic row (no fallback:
    the switch is an explicit brain_select, recorded in the evidence)."""
    selected = "runtime-v1" if brain_state(w) == "READY" else "deterministic"
    w.ok({"command": "brain_select", "row_id": selected})
    session = str(uuid.uuid4())
    before = w.ok({"command": "memory_list"})["facts"]
    n = len(w.events)
    r = w.ok({"command": "oi_turn", "session_id": session, "text": text, "depth": "auto"})
    evs = w.until_finished(r["turn_id"], after=n)
    core = [e for e in evs if e["type"] == "core.result"]
    assert core, [e["type"] for e in evs]
    if core[-1]["data"]["needs"] == "confirmation":
        n = len(w.events)
        w.ok({"command": "oi_confirm", "turn_id": r["turn_id"]})
        evs += w.until_finished(r["turn_id"], after=n)
    appr = [e for e in evs if e["type"] == "approval.required"]
    assert appr, [(e["type"], e["data"].get("code")) for e in evs]
    assert w.ok({"command": "memory_list"})["facts"] == before          # nothing before the decision
    n = len(w.events)
    w.ok({"command": "oi_decide", "turn_id": r["turn_id"], "approve": approve,
          "approval_digest": appr[-1]["data"]["approval_digest"]})
    evs += w.until_finished(r["turn_id"], after=n)
    after = w.ok({"command": "memory_list"})["facts"]
    w.ok({"command": "brain_select", "row_id": "runtime-v1"})
    return evs, before, after, selected


def test_supervised_action_approved_is_verified(w):
    evs, before, after, selected = _remember(w, "remember that the science lab is closed on Friday", True)
    final = [e for e in evs if e["type"] == "core.result"][-1]["data"]
    assert final["code"] == "SETTLED_VERIFIED", final
    assert len(after) == len(before) + 1
    record("action_approved", evs, selected=selected, memory_before=len(before), memory_after=len(after))


def test_supervised_action_denied_changes_nothing(w):
    evs, before, after, selected = _remember(w, "remember that the staff meeting moved to 4 pm", False)
    final = [e for e in evs if e["type"] == "core.result"][-1]["data"]
    assert final["code"] == "APPROVAL_DENIED", final
    assert after == before
    record("action_denied", evs, selected=selected)


def test_refusal_of_a_destructive_unqualified_request(w):
    w.ok({"command": "brain_select", "row_id": "deterministic"})
    n = len(w.events)
    r = w.ok({"command": "oi_turn", "session_id": str(uuid.uuid4()), "text": "delete every file on my D drive right now",
              "depth": "auto"})
    evs = w.until_finished(r["turn_id"], after=n)
    w.ok({"command": "brain_select", "row_id": "runtime-v1"})
    assert not [e for e in evs if e["type"] == "approval.required"]
    fin = [e for e in evs if e["type"] == "turn.finished"][-1]["data"]["status"]
    assert fin != "ok"
    record("refusal", evs, finished=fin)


def test_forged_digest_is_refused(w):
    w.ok({"command": "brain_select", "row_id": "deterministic"})
    n = len(w.events)
    r = w.ok({"command": "oi_turn", "session_id": str(uuid.uuid4()), "text": "remember that the bus leaves at 7",
              "depth": "auto"})
    evs = w.until_finished(r["turn_id"], after=n)
    if [e for e in evs if e["type"] == "core.result"][-1]["data"]["needs"] == "confirmation":
        n = len(w.events)
        w.ok({"command": "oi_confirm", "turn_id": r["turn_id"]})
        evs += w.until_finished(r["turn_id"], after=n)
    before = w.ok({"command": "memory_list"})["facts"]
    rep = w.call({"command": "oi_decide", "turn_id": r["turn_id"], "approve": True, "approval_digest": "f" * 64})
    w.ok({"command": "brain_select", "row_id": "runtime-v1"})
    assert rep == {"result": "REFUSED", "code": "APPROVAL_DIGEST_MISMATCH"}
    assert w.ok({"command": "memory_list"})["facts"] == before
    record("forged_digest", evs, reply=rep)
