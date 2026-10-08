"""PROCESS-LEVEL: the real `python -m uri_scheduler.service run` process (fixture executor, SYNTHETIC Claude stand-in).

Duplicate startup, token-protected local API, and kill -9 of the scheduler process while an attempt runs followed by a
restart (interrupted-execution recovery, executor contained by the supervisor's kill-on-close job).
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FAKE = Path(__file__).parent / "helpers" / "fake_claude.py"
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows process semantics")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def start(state, port, scenario="honest", tick=1):
    env = dict(os.environ, URI_FAKE_SCENARIO=scenario, PYTHONPATH=str(ROOT))
    p = subprocess.Popen([sys.executable, "-m", "uri_scheduler.service", "run", "--state", str(state), "--mode", "fixture",
                          "--fixture-script", str(FAKE), "--port", str(port), "--tick-s", str(tick), "--timeout-s", "120",
                          "--inactivity-s", "120"], cwd=str(ROOT), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
    line = p.stdout.readline().decode()
    return p, json.loads(line)


def api(port, state, method, path, body=None, token=True):
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", method=method,
                                 data=json.dumps(body).encode() if body is not None else None)
    if token:
        req.add_header("Authorization", "Bearer " + (Path(state) / "api-token").read_text(encoding="utf-8"))
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def wait(pred, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        v = pred()
        if v:
            return v
        time.sleep(0.3)
    raise AssertionError("timeout")


def kill(p):
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True)
    p.wait(30)


def test_duplicate_startup_and_api(tmp_path):
    state, port = tmp_path / "state", free_port()
    p, ready = start(state, port)
    try:
        assert ready["ready"] and ready["mode"] == "fixture"
        q = subprocess.run([sys.executable, "-m", "uri_scheduler.service", "run", "--state", str(state), "--mode", "fixture",
                            "--fixture-script", str(FAKE), "--port", str(free_port())], cwd=str(ROOT), capture_output=True,
                           env=dict(os.environ, PYTHONPATH=str(ROOT)), timeout=60)
        assert q.returncode == 3 and b"SCHEDULER_ALREADY_RUNNING" in q.stdout
        assert api(port, state, "GET", "/overview", token=False)[0] == 401
        code, prop = api(port, state, "POST", "/jobs/propose-festivals", {"principal": "owner", "festivals": ["diwali", "dussehra"]})
        assert code == 200 and prop["schedule"]["offset_days"] == -2
        code, err = api(port, state, "POST", f"/jobs/{prop['job_id']}/confirm", {"principal": "owner", "proposal_sha256": "x"})
        assert code == 400 and err["error"] == "PROPOSAL_MISMATCH"
        code, job = api(port, state, "POST", f"/jobs/{prop['job_id']}/confirm",
                        {"principal": "owner", "proposal_sha256": prop["proposal_sha256"]})
        assert code == 200 and job["state"] == "ACTIVE"
        code, ov = api(port, state, "GET", "/overview")
        assert [o["occurrence_key"] for o in ov["upcoming"]][:2] == ["dussehra:2026", "diwali:2026"]
    finally:
        kill(p)


def test_kill_during_run_then_restart_recovers(tmp_path):
    state, port = tmp_path / "state", free_port()
    p, _ = start(state, port, scenario="hang")
    try:
        code, prop = api(port, state, "POST", "/jobs/propose", {
            "principal": "owner", "title": "t", "template_id": "festival_gif.v1",
            "params": {"festival": {"key": "diwali", "name": "Diwali (Deepavali)", "date": "2026-11-08"}},
            "schedule": {"kind": "once", "at": "2026-01-01T00:00"}})
        api(port, state, "POST", f"/jobs/{prop['job_id']}/confirm", {"principal": "owner", "proposal_sha256": prop["proposal_sha256"]})
        wait(lambda: any(o["state"] == "RUNNING" for o in api(port, state, "GET", "/overview")[1]["upcoming"]))
        time.sleep(1.0)
    finally:
        kill(p)
    # the hanging synthetic executor must not survive its supervisor (kill-on-close job)
    import sqlite3
    db = sqlite3.connect(str(state / "supervisor" / "ledger.db"))
    pid = db.execute("SELECT pid FROM attempt ORDER BY attempt_id DESC LIMIT 1").fetchone()[0]
    db.close()
    assert pid
    alive = wait(lambda: str(pid) not in subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True,
                                                        text=True).stdout, 20)
    assert alive
    p2, ready = start(state, port, scenario="honest")
    try:
        assert ready["startup"]["interrupted"] and ready["startup"]["interrupted"][0]["next"] == "SCHEDULED"
        ov = wait(lambda: (lambda o: o if o["pending_approvals"] else None)(api(port, state, "GET", "/overview")[1]), 120)
        cand = ov["pending_approvals"][0]["candidates"][0]
        code, ev = api(port, state, "GET", "/events?limit=200")
        kinds = [e["kind"] for e in ev]
        assert "occurrence.interrupted" in kinds and kinds.count("scheduler.started") == 2
        code, gif = 200, urllib.request.urlopen(urllib.request.Request(
            f"http://127.0.0.1:{port}/artifacts/{cand['artifact_id']}/file",
            headers={"Authorization": "Bearer " + (state / "api-token").read_text(encoding="utf-8")})).read()
        assert gif[:6] == b"GIF89a"
    finally:
        kill(p2)
