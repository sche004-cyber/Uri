"""REAL processes over the frozen framed stdio: the Phase 2 server profile and the Phase 2 worker profile, driven
with the exact frames the supervised UI sends. The worker's frame loop must stay responsive while the executor runs
(status / cancel mid-run), a worker crash must leave a reconstructable `uncertain` record for the next worker, and
the executor must die with the worker (kill-on-close job)."""
import json
import subprocess
import time
from pathlib import Path

import psutil

from phase2b.conftest import CLAUDE, uid
from phase2d.test_worker_process import SERVER, WORKER, frames, procs  # noqa: F401  (fixture: real server + worker)
from uri_core.core.runtime_identity import child_environment
from uri_supervisor import winproc

TEXT = "use the harness to write a greeting into out.txt"
HANG = TEXT + " (fake scenario: hang)"   # in-band marker: the worker profile sanitizes its env


def _spawn_worker(client, scenario):
    m = client.data
    return subprocess.Popen([m["interpreter"], "-B", "-I", WORKER, "--manifest", str(client.path), "--allow-fixture-qualification"],
                            cwd=m["client_root"], env={**child_environment(Path(m["client_root"]), Path(m["interpreter"])),
                                                       "URI_FAKE_SCENARIO": scenario},
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _poll(cmd, eid, pred, timeout=40):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = cmd({"command": "execution_status", "execution_id": eid})
        assert last["result"] == "OK", last
        if pred(last["value"]):
            return last["value"]
        time.sleep(0.1)
    raise AssertionError(f"timeout: {last}")


def _running(v):
    return v["state"] == "running" and any(a["status"] == "RUNNING" and a["pid"] for a in (v.get("ledger") or {}).get("attempts") or [])


def test_lifecycle_and_mid_run_cancel_over_real_frames(procs):
    wp, client = procs["worker"], procs["client"]
    wp.kill(); wp.wait(15)                                    # the fixture's worker runs 'honest'; this test needs 'hang'
    wp = _spawn_worker(client, "hang")
    try:
        cmd = frames(wp)
        pre = cmd({"command": "preflight"})["value"]
        assert pre["worker_profile"] == "phase2d-supervised" and pre["mid_run_cancel"] is True and pre["execution_active"] is None
        assert pre["execution_lifecycle"] == ["execution_begin", "execution_cancel", "execution_list", "execution_status"]
        assert cmd({"command": "execution_list"})["value"]["executions"] == []
        turn = cmd({"command": "turn_start", "session_id": uid(), "text": HANG, "reasoning": CLAUDE})
        assert turn["result"] == "OK" and turn["value"]["state"] == "approval_required", turn
        v = turn["value"]
        prop = v["execution_proposal"]
        assert prop["provider"] == "claude_code" and prop["qualification"]["level"] == "FIXTURE_ONLY"
        t0 = time.monotonic()
        out = cmd({"command": "execution_begin", "turn_id": v["turn_id"], "approval_digest": v["approval_request"]["approval_digest"],
                   "proposal_digest": prop["proposal_digest"]})
        assert out["result"] == "OK" and out["value"]["state"] == "queued", out
        assert time.monotonic() - t0 < 5                       # returned while the harness hangs
        eid = out["value"]["execution_id"]
        run = _poll(cmd, eid, _running)
        att = run["ledger"]["attempts"][-1]
        assert winproc.identity_state(att["pid"], att["pid_create_time"]).startswith("ALIVE")
        # the loop is responsive: other frames are answered while the executor runs
        assert cmd({"command": "turn_start", "session_id": uid(), "text": TEXT, "reasoning": CLAUDE}) == {"result": "REFUSED", "code": "EXECUTION_IN_PROGRESS"}
        assert cmd({"command": "snapshot", "session_id": uid(), "queries": []}) == {"result": "REFUSED", "code": "EXECUTION_IN_PROGRESS"}
        assert cmd({"command": "preflight"})["value"]["execution_active"] == eid
        rep = cmd({"command": "execution_cancel", "execution_id": eid})
        assert rep["result"] == "OK" and rep["value"]["kill"]["granted"] is True, rep
        final = _poll(cmd, eid, lambda s: s["state"] not in ("queued", "approving", "starting", "running"))
        assert final["state"] == "uncertain" and final["reason"] == "CANCELLED_AFTER_DISPATCH"
        assert final["ledger"]["attempts"][-1]["end_reason"] == "cancelled_killed" and final["server_turn"]["state"] == "execution_uncertain"
        deadline = time.monotonic() + 15
        while winproc.identity_state(att["pid"], att["pid_create_time"]).startswith("ALIVE") and time.monotonic() < deadline:
            time.sleep(0.1)
        assert winproc.identity_state(att["pid"], att["pid_create_time"]) in ("DEAD", "PID_REUSED")
        assert cmd({"command": "execution_cancel", "execution_id": eid}) == {"result": "REFUSED", "code": "EXECUTION_TERMINAL"}
        assert not list((Path(client.data["client_root"]) / "workspace/results").rglob("out.txt"))
        closed = cmd({"command": "close"})
        assert closed["result"] == "CLOSED" and closed["execution"] == {"active": None}
        wp.stdin.close()
        assert wp.wait(15) == 0
    finally:
        if wp.poll() is None:
            wp.kill()


def test_worker_crash_mid_run_kills_the_executor_and_the_next_worker_reports_uncertain(procs):
    wp, client = procs["worker"], procs["client"]
    wp.kill(); wp.wait(15)
    wp = _spawn_worker(client, "hang")
    try:
        cmd = frames(wp)
        turn = cmd({"command": "turn_start", "session_id": uid(), "text": HANG, "reasoning": CLAUDE})["value"]
        eid = cmd({"command": "execution_begin", "turn_id": turn["turn_id"], "approval_digest": turn["approval_request"]["approval_digest"],
                   "proposal_digest": turn["execution_proposal"]["proposal_digest"]})["value"]["execution_id"]
        att = _poll(cmd, eid, _running)["ledger"]["attempts"][-1]
        wp.kill()                                              # the UI's worker dies without any close frame
        wp.wait(15)
        deadline = time.monotonic() + 20
        while winproc.identity_state(att["pid"], att["pid_create_time"]).startswith("ALIVE") and time.monotonic() < deadline:
            time.sleep(0.1)
        assert winproc.identity_state(att["pid"], att["pid_create_time"]) in ("DEAD", "PID_REUSED")   # kill-on-close job
    finally:
        if wp.poll() is None:
            wp.kill()
    rec = json.loads((Path(client.data["client_root"]) / "control/supervisor/executions" / (eid + ".json")).read_text())
    assert rec["state"] == "running"                           # the dead worker could not update it: the next one must
    wp2 = _spawn_worker(client, "honest")
    try:
        cmd = frames(wp2)
        rows = cmd({"command": "execution_list"})["value"]
        assert rows["active"] is None
        assert rows["startup"]["executions"] == [{"execution_id": eid, "was": "running", "state": "uncertain", "reason": "WORKER_RESTARTED"}]
        st = cmd({"command": "execution_status", "execution_id": eid})["value"]
        assert st["state"] == "uncertain" and st["reason"] == "WORKER_RESTARTED"
        assert st["ledger"]["task"]["state"] in ("FAILED", "UNCERTAIN", "NEEDS_USER") and st["ledger"]["open_authorizations"] == 0
        assert st["ledger"]["attempts"][-1]["status"] in ("ENDED", "FENCED")
        assert st["journal"]["state"] == "execution_uncertain"                 # frozen journal recovery ran
        assert st["server_turn"]["state"] in ("executing", "execution_uncertain")
        assert cmd({"command": "execution_cancel", "execution_id": eid}) == {"result": "REFUSED", "code": "EXECUTION_TERMINAL"}
        # the same session is held by the never-settled turn (frozen rule); a new session continues normally
        held = cmd({"command": "turn_start", "session_id": turn["execution_proposal"]["session_id"], "text": TEXT, "reasoning": CLAUDE})
        assert held["result"] == "REFUSED" and held["code"].startswith("SERVER_REFUSED:")
        again = cmd({"command": "turn_start", "session_id": uid(), "text": TEXT, "reasoning": CLAUDE})["value"]
        eid2 = cmd({"command": "execution_begin", "turn_id": again["turn_id"], "approval_digest": again["approval_request"]["approval_digest"],
                    "proposal_digest": again["execution_proposal"]["proposal_digest"]})["value"]["execution_id"]
        done = _poll(cmd, eid2, lambda s: s["state"] not in ("queued", "approving", "starting", "running"))
        assert done["state"] == "completed"
        ids = [r["execution_id"] for r in cmd({"command": "execution_list"})["value"]["executions"]]
        assert set(ids) == {eid, eid2}
        assert cmd({"command": "close"})["result"] == "CLOSED"
        wp2.stdin.close()
        assert wp2.wait(15) == 0
    finally:
        if wp2.poll() is None:
            wp2.kill()


def test_cap1_close_and_stdin_eof_release_pending_cards_over_real_frames(procs):
    """CAP-1 (Phase 2 closure): a UI that closes with an approval card still pending must not leave the server turn
    holding the session (frozen TURN_CAPACITY) for 15 minutes. Real server process, real worker processes."""
    wp, client = procs["worker"], procs["client"]
    cmd = frames(wp)
    held_session, eof_session = uid(), uid()
    first = cmd({"command": "turn_start", "session_id": held_session, "text": TEXT, "reasoning": CLAUDE})
    assert first["result"] == "OK" and first["value"]["state"] == "approval_required", first
    closed = cmd({"command": "close"})
    assert closed["result"] == "CLOSED" and closed["execution"] == {"active": None}
    assert [(r["turn_id"], r["why"], r["released"]) for r in closed["released"]] == [(first["value"]["turn_id"], "WORKER_CLOSED", True)]
    wp.stdin.close()
    assert wp.wait(15) == 0
    wp2 = _spawn_worker(client, "honest")
    try:
        cmd = frames(wp2)
        again = cmd({"command": "turn_start", "session_id": held_session, "text": TEXT, "reasoning": CLAUDE})
        assert again["result"] == "OK" and again["value"]["state"] == "approval_required", again    # was TURN_CAPACITY
        pending = cmd({"command": "turn_start", "session_id": eof_session, "text": TEXT, "reasoning": CLAUDE})
        assert pending["result"] == "OK", pending
        wp2.stdin.close()                                      # the UI vanished: no close frame, only EOF
        assert wp2.wait(30) == 0
    finally:
        if wp2.poll() is None:
            wp2.kill()
    wp3 = _spawn_worker(client, "honest")
    try:
        cmd = frames(wp3)
        for session in (held_session, eof_session):
            r = cmd({"command": "turn_start", "session_id": session, "text": TEXT, "reasoning": CLAUDE})
            assert r["result"] == "OK" and r["value"]["state"] == "approval_required", (session, r)
        assert cmd({"command": "close"})["result"] == "CLOSED"
        wp3.stdin.close()
        assert wp3.wait(15) == 0
    finally:
        if wp3.poll() is None:
            wp3.kill()
