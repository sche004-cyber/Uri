"""Crash / restart / replay across the boundary. A child process runs the bridge (SYNTHETIC ticket) and is killed by
the supervisor's deterministic crash points (os._exit, no cleanup). Then a fresh bridge is constructed (restart):
recovery decides, authority is revoked, nothing is re-launched, and the same ticket can never run again.
NOT exercised: power loss / OS write reordering (see PHASE2A_POWER_LOSS_TEST_PLAN.md)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from phase2b.conftest import CLAUDE, SyntheticAuthority, fake_binding, fake_registry
from uri_supervisor_bridge.bridge import SupervisorBridge

CHILD = str(Path(__file__).parent / "helpers" / "bridge_child.py")
POINTS = ["after_submit", "after_admit_commit", "after_intents", "after_spawning_marked", "after_pid_record",
          "after_spawn_resumed", "mid_stream", "after_terminal_event_recorded", "after_attempt_ended",
          "recovery_after_fence", "recovery_before_decision"]


def cfg_for(tmp_path, auth, scenario="slow_honest", **kw):
    signed, request, now = auth.issue()
    cfg = {"mode": "execute", "client_root": str(tmp_path / "client"), "scenario": scenario, "counter": str(tmp_path / "counter.txt"),
           "key": auth.private_hex(), "generation": auth.generation, "binding": auth.binding, "signed": signed, "request": request,
           "now": now}
    cfg.update(kw)
    return cfg, signed, request, now


def child(cfg, crash_at=None, scenario_env=None):
    env = dict(os.environ)
    env.pop("URI_SUPERVISOR_CRASH_AT", None)
    env["URI_FAKE_SLEEP"] = "1.5"
    if crash_at:
        env["URI_SUPERVISOR_CRASH_AT"] = crash_at
    return subprocess.run([sys.executable, CHILD, json.dumps(cfg)], env=env, capture_output=True, timeout=180)


def effects(tmp_path):
    p = tmp_path / "counter.txt"
    return p.read_text().count("effect") if p.exists() else 0


def restart(tmp_path, **kw):
    return SupervisorBridge(tmp_path / "client", registry=fake_registry("claude_code"),
                            executors={"claude_code": fake_binding("claude_code")}, timeout_s=20, inactivity_s=5, **kw)


@pytest.mark.parametrize("point", POINTS)
def test_crash_at_each_point_then_restart_never_relaunches_and_same_ticket_is_dead(tmp_path, point, monkeypatch):
    auth = SyntheticAuthority()
    cfg, signed, request, now = cfg_for(tmp_path, auth)
    if point.startswith("recovery_"):
        # leave an unreconciled ended attempt first, then crash during the restart's recovery
        r = child(cfg, crash_at="after_attempt_ended")
        assert r.returncode == 137, r.stderr[-500:]
        r = child({**cfg, "mode": "restart_only"}, crash_at=point)
    else:
        r = child(cfg, crash_at=point)
    assert r.returncode == 137, (point, r.returncode, r.stderr[-500:])
    before = effects(tmp_path)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    b = restart(tmp_path)
    try:
        L = b.L
        tid = signed["ticket"]["operation_id"]
        t = L.task(tid)
        if t is None:
            # every point here is after the submit commit, so the task must be durable
            pytest.fail(f"task missing after crash at {point}")
        assert t["state"] not in ("RUNNING", "RECOVERING", "QUEUED", "RETRY_SAFE"), (point, t["state"])
        # authority revoked at restart: no admission is possible for this task regardless of state
        assert b.sup.admit_next(only_task_id=tid) is None and b.sup.admit_next() is None
        auth_row = L.q1("SELECT * FROM authorization WHERE task_id=? AND superseded_at_us IS NULL", (tid,))
        assert auth_row["valid_until_us"] <= L.now_us()
        if t["state"] != "COMPLETE":
            assert any(r["task_id"] == tid and r["authority"] == "revoked" for r in b.reconcile_restart()), b.reconcile_restart()
        # the restart itself launched nothing
        assert effects(tmp_path) == before
        # replaying the same ticket after restart: never a second task, never a relaunch
        work = auth.verify(signed, request, CLAUDE, now=now)
        assert b.execute(work) == ("execution_uncertain", [], "DUPLICATE_OPERATION")
        assert effects(tmp_path) == before and effects(tmp_path) <= 1
        assert L.q1("SELECT COUNT(*) FROM attempt WHERE status IN ('ADMITTED','SPAWNING','RUNNING')")[0] == 0
        # recovery is idempotent: a second restart changes no decision
        decisions = [tuple(d) for d in L.q("SELECT decision_id,outcome FROM recovery_decision ORDER BY decision_id")]
        b.close()
        b = restart(tmp_path)
        L = b.L
        assert [tuple(d) for d in L.q("SELECT decision_id,outcome FROM recovery_decision ORDER BY decision_id")] == decisions
        # a NEW ticket (new authority from URI) still works, and the old task stays untouched
        signed2, request2, now2 = auth.issue()
        work2 = auth.verify(signed2, request2, CLAUDE, now=now2)
        assert b.execute(work2)[0] == "verified"
        assert L.task(tid)["state"] == t["state"]
        assert L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (tid,))[0] == L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (tid,))[0]
    finally:
        b.close()


def test_restart_with_a_retry_safe_task_fails_it_rather_than_running_it(tmp_path, monkeypatch):
    """after_admit_commit: attempt ADMITTED, never spawned. Recovery proves NEVER_STARTED -> RETRY_SAFE, which under
    a live ticket would be re-admittable. The restart revokes it: FAILED, no run."""
    auth = SyntheticAuthority()
    cfg, signed, request, now = cfg_for(tmp_path, auth)
    assert child(cfg, crash_at="after_admit_commit").returncode == 137
    b = restart(tmp_path)
    try:
        tid = signed["ticket"]["operation_id"]
        t = b.L.task(tid)
        assert t["state"] == "FAILED" and t["reason_code"] == "AUTHORITY_REVOKED_RESTART"
        assert [r["was"] for r in b.reconcile_restart() if r["task_id"] == tid] == ["RETRY_SAFE"]
        assert effects(tmp_path) == 0 and b.L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (tid,))[0] == 1
    finally:
        b.close()


def test_uncertain_task_survives_restart_as_uncertain_and_user_retry_needs_new_authority(tmp_path):
    auth = SyntheticAuthority()
    cfg, signed, request, now = cfg_for(tmp_path, auth, scenario="partial_then_die")
    r = child(cfg)
    assert r.returncode == 0, r.stderr[-500:]
    assert json.loads(r.stdout.decode().strip().splitlines()[-1])["outcome"] == "execution_uncertain"
    b = restart(tmp_path)
    try:
        tid = signed["ticket"]["operation_id"]
        assert b.L.task(tid)["state"] == "NEEDS_USER"
        b.sup.record_user_decision(tid, "retry", auth.binding["principal_id"])
        assert b.L.task(tid)["state"] == "RETRY_SAFE" and b.sup.admit_next(only_task_id=tid) is None
        # restart again: the RETRY_SAFE leftover is closed
        b.close()
        b = restart(tmp_path)
        assert b.L.task(tid)["state"] == "FAILED"
    finally:
        b.close()


def test_two_bridges_on_one_client_root_are_refused(tmp_path):
    b = restart(tmp_path)
    try:
        with pytest.raises(Exception, match="SUPERVISOR_ALREADY_RUNNING"):
            restart(tmp_path)
    finally:
        b.close()
