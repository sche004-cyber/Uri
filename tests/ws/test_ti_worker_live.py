"""LIVE (TI-AC11): the owner's warden demonstration through the REAL integrated worker (C1 gates, paired Core) with
Runtime v1 READY. Input is labelled: the first run sends typed text; the second sends the same words as a SIMULATED
transcript (`uri.text_input.v1`, engine "simulated"). No microphone or recogniser is used.

Opt-in, run from the MATERIALIZED runtime after `scripts/ws_provision.py`, with the integrated server and Runtime v1
running:
    set URI_WS_LIVE=1 && .venv\\Scripts\\python.exe -m pytest tests/ws/test_ti_worker_live.py -s
Evidence: work/c1/ws-evidence/ti_worker_live_<ts>.json (full draft texts; they contain no secrets).
"""
import json
import os
import time
import uuid

import pytest

from tests.ws.test_ws_worker_live import ROOT, Worker

pytestmark = pytest.mark.skipif(os.environ.get("URI_WS_LIVE") != "1", reason="opt-in: URI_WS_LIVE=1")
EVIDENCE = {"runs": []}
STEPS = [
    "URI draft a letter to the warden regarding five students, sorry seven students, who left the hostel on Monday "
    "without permission. Make it formal.",
    "Actually, don't say without permission. Say they left without recording their departure in the hostel register.",
    "Make it more diplomatic and shorten the second paragraph.",
    "Undo the last change.",
]


@pytest.fixture(scope="module")
def w():
    current = json.loads((ROOT / "work/c1/ws-current.json").read_text(encoding="utf-8"))
    EVIDENCE["installation"] = {k: current[k] for k in ("name", "port", "provisioned")}
    worker = Worker(current)
    yield worker
    worker.close()
    EVIDENCE["worker_exit"] = worker.p.returncode
    out = ROOT / "work/c1/ws-evidence" / ("ti_worker_live_%s.json" % time.strftime("%Y%m%d-%H%M%S"))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(EVIDENCE, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("EVIDENCE", out)


def _turn(w, sid, text, simulated):
    cmd = {"command": "oi_turn", "session_id": sid, "text": text, "depth": "auto"}
    if simulated:
        cmd["input"] = {"schema": "uri.text_input.v1", "source": "transcript",
                        "transcript": {"raw": text, "engine": "simulated", "simulated": True, "language": "en-IN"}}
    n = len(w.events)
    t0 = time.monotonic()
    r = w.ok(cmd)
    evs = w.until_finished(r["turn_id"], timeout=300, after=n)
    wall = round(time.monotonic() - t0, 3)
    upd = [e["data"] for e in evs if e["type"] == "draft.updated"]
    routed = [e["data"] for e in evs if e["type"] == "turn.routed"]
    done = [e["data"] for e in evs if e["type"] == "answer.done"]
    return {"text": text, "simulated_transcript": simulated, "wall_s": wall,
            "route": routed[-1]["route"] if routed else None, "op": upd[-1]["op"] if upd else None,
            "draft": upd[-1]["draft"] if upd else None, "metrics": done[-1]["metrics"] if done else None,
            "errors": [e["data"] for e in evs if e["type"] == "error"],
            "event_types": [e["type"] for e in evs]}


@pytest.mark.parametrize("simulated", [False, True], ids=["typed", "simulated_transcript"])
def test_owner_warden_demonstration(w, simulated):
    assert w.ok({"command": "brain_status"})["state"] == "READY", "Runtime v1 must be READY for this journey"
    sid = str(uuid.uuid4())
    steps = [_turn(w, sid, t, simulated) for t in STEPS]
    EVIDENCE["runs"].append({"input": "simulated_transcript" if simulated else "typed", "steps": steps})
    d1, d2, d3, d4 = (s["draft"] for s in steps)
    assert all(s["route"] == "draft" and not s["errors"] for s in steps), [(s["route"], s["errors"]) for s in steps]
    t1, t2, t3, t4 = (d["current"]["text"] for d in (d1, d2, d3, d4))
    low = t1.lower()
    assert ("seven" in low or " 7 " in low) and "five" not in low
    assert d1["source"]["source"] == ("transcript" if simulated else "typed")
    if simulated:
        assert d1["source"]["simulated"] is True and d1["source"]["engine"] == "simulated"
    assert "without permission" not in t2.lower() and "hostel register" in t2.lower()
    prev = {b["id"]: b["text"] for b in d1["current"]["blocks"]}
    assert all(prev[b["id"]] == b["text"] for b in d2["current"]["blocks"]
               if b["id"] in prev and b["id"] not in d2["current"]["changed"])
    assert "register" in t3.lower() and ("seven" in t3.lower() or " 7 " in t3.lower())
    assert d3["current"]["n"] == 3 and steps[3]["op"] == "undo" and t4 == t2 and d4["can_redo"]
    assert not (steps[3]["metrics"] or {}).get("model_used")
    # Nothing reached Core and nothing was sent or saved: the draft desk has no capability.
    assert all("core.result" not in s["event_types"] and "approval.required" not in s["event_types"] for s in steps)
