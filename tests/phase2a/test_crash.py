"""Kill the supervisor process (os._exit, no cleanup) at each important transition, restart, and check:
no duplicated unsafe effect, a correct durable state, structural invariants, and recovery idempotence.

NOT exercised here: power loss / OS write reordering (needs a VM; see docs/plans/PHASE2A_REPORT.md).
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from uri_supervisor import winproc
from uri_supervisor.supervisor import Supervisor

CHILD = str(Path(__file__).parent / "helpers" / "child.py")

RUN_POINTS = ["after_epoch_begin", "after_submit", "after_admit_commit", "after_intents", "after_spawning_marked",
              "after_pid_record", "after_spawn_resumed", "mid_stream", "after_terminal_event_recorded", "after_attempt_ended"]
RECOVERY_POINTS = ["recovery_after_fence", "recovery_after_process_inspection", "recovery_before_postconditions",
                   "recovery_before_decision", "recovery_after_decision"]


def child(cfg, crash_at=None):
    env = dict(os.environ)
    env.pop("URI_SUPERVISOR_CRASH_AT", None)
    if crash_at:
        env["URI_SUPERVISOR_CRASH_AT"] = crash_at
    return subprocess.run([sys.executable, CHILD, json.dumps(cfg)], env=env, capture_output=True, timeout=120)


def cfg_for(tmp_path, scenario="ok_write", **kw):
    target = tmp_path / "work" / "out file.txt"
    target.parent.mkdir(exist_ok=True)
    cfg = {"db": str(tmp_path / "l" / "ledger.db"), "mode": "run", "task_id": "t", "scenario": scenario, "cwd": str(tmp_path),
           "path": str(target), "counter": str(tmp_path / "counter.txt"),
           "effects": [{"op_class": "local_write", "operation": "write", "target": str(target), "paths": [str(target)]}],
           "postconditions": [{"kind": "file_exists", "spec": {"path": str(target)}}]}
    cfg.update(kw)
    return cfg, target


def invariants(L):
    for r in L.q("SELECT p.name,p.capacity,COALESCE(SUM(c.amount),0) h FROM resource_pool p LEFT JOIN claim c ON c.pool=p.name AND c.state='held' GROUP BY p.name"):
        assert r["h"] <= r["capacity"], r["name"]
    for t in L.q("SELECT * FROM task"):
        if t["state"] == "COMPLETE":
            assert t["completion_ref"] is not None
        assert t["state"] not in ("RUNNING", "RECOVERING"), (t["task_id"], t["state"])
        if t["state"] in ("COMPLETE", "FAILED", "RETRY_SAFE", "UNCERTAIN", "NEEDS_USER"):
            assert L.q1("SELECT COUNT(*) FROM claim WHERE task_id=? AND state='held' AND attempt_id IN (SELECT attempt_id FROM attempt WHERE task_id=?)",
                        (t["task_id"], t["task_id"]))[0] == 0 or t["state"] in ("UNCERTAIN", "NEEDS_USER")
    assert L.q1("SELECT COUNT(*) FROM attempt WHERE status IN ('SPAWNING','RUNNING','ADMITTED')")[0] == 0


def effects_count(path):
    return len(Path(path).read_text().split()) if Path(path).exists() else 0


@pytest.mark.parametrize("point", RUN_POINTS)
def test_kill_supervisor_at_each_transition_then_recover_without_duplicate_effect(tmp_path, point):
    cfg, target = cfg_for(tmp_path)
    r = child(cfg, crash_at=point)
    assert r.returncode == 137, (point, r.returncode, r.stderr[-400:])
    sup = Supervisor(cfg["db"])                       # restart: new epoch + recovery
    try:
        L = sup.ledger
        if L.task("t") is None:                       # crashed before the task was even durable: nothing to recover
            assert point in ("after_epoch_begin",)
            return
        # whatever happened, nothing may be left half-done
        invariants(L)
        st = L.task("t")["state"]
        assert st in ("QUEUED", "COMPLETE", "RETRY_SAFE"), (point, st)
        # if recovery says RETRY_SAFE the effect was provably absent; finishing the task must yield exactly one effect
        guard = 0
        while L.task("t")["state"] in ("QUEUED", "RETRY_SAFE") and guard < 4:
            guard += 1
            a = sup.admit_next()
            assert a is not None
            from dataclasses import replace
            sup.run_attempt(a, cwd=str(tmp_path), resolved_executable=sys.executable,
                            extra_argv=[str(Path(CHILD).parent / "fake_executor.py"), "--scenario", "ok_write", "--path", str(target),
                                        "--counter", cfg["counter"]])
        assert L.task("t")["state"] == "COMPLETE", point
        assert effects_count(cfg["counter"]) <= 1, f"duplicated effect after crash at {point}"
        invariants(L)
    finally:
        sup.close()


@pytest.mark.parametrize("point", RECOVERY_POINTS)
def test_kill_supervisor_during_recovery_then_recover_again_same_outcome(tmp_path, point):
    cfg, target = cfg_for(tmp_path)
    assert child(cfg, crash_at="after_attempt_ended").returncode == 137          # leaves an unreconciled ended attempt
    r = child({"db": cfg["db"], "mode": "recover"}, crash_at=point)
    assert r.returncode == 137, (point, r.stderr[-400:])
    sup = Supervisor(cfg["db"])
    try:
        L = sup.ledger
        invariants(L)
        assert L.task("t")["state"] == "COMPLETE"                                 # postconditions proved the write
        assert L.q1("SELECT COUNT(*) FROM recovery_decision WHERE task_id='t'")[0] == 1
        before = L.q1("SELECT decision_id,outcome FROM recovery_decision")
        assert sup.recover_all() == []
        assert tuple(L.q1("SELECT decision_id,outcome FROM recovery_decision")) == tuple(before)
        assert effects_count(cfg["counter"]) == 1
    finally:
        sup.close()


def test_executor_dies_with_supervisor_job_kill_on_close(tmp_path):
    cfg, target = cfg_for(tmp_path, scenario="sleep", sleep=300)
    r = child(cfg, crash_at="mid_stream")
    assert r.returncode == 137
    L = Supervisor(cfg["db"], run_recovery=False)
    try:
        a = L.ledger.q1("SELECT * FROM attempt")
        assert a["job_name"] and a["pid"]
        exists, active = winproc.job_state(a["job_name"])
        assert (exists, active) == (False, 0), "named job (and its executor) must vanish when the supervisor dies"
        assert winproc.identity_state(a["pid"], a["pid_create_time"]) in ("DEAD", "PID_REUSED")
    finally:
        L.close()


def test_supervisor_crash_mid_effect_with_partial_state_needs_user_never_retried(tmp_path):
    """A non-idempotent write whose postcondition cannot be proven after a crash is escalated, never repeated."""
    import hashlib
    full = hashlib.sha256(b"FULL").hexdigest()
    cfg, target = cfg_for(tmp_path, scenario="partial_write_then_die")
    cfg["postconditions"] = [{"kind": "file_hash", "spec": {"path": str(target), "sha256": full}}]
    assert child(cfg).returncode == 0                                              # supervisor survives; executor dies mid-effect
    sup = Supervisor(cfg["db"])
    try:
        assert sup.ledger.task("t")["state"] == "NEEDS_USER"
        assert sup.admit_next() is None
        assert target.read_text() == "PART" and sup.ledger.q1("SELECT COUNT(*) FROM attempt")[0] == 1   # not re-run
    finally:
        sup.close()


def test_second_supervisor_cannot_start_while_first_is_alive(tmp_path):
    from uri_supervisor.supervisor import SupervisorError
    a = Supervisor(tmp_path / "x" / "l.db")
    try:
        with pytest.raises(SupervisorError, match="SUPERVISOR_ALREADY_RUNNING"):
            Supervisor(tmp_path / "x" / "l.db")
    finally:
        a.close()
    Supervisor(tmp_path / "x" / "l.db").close()                                    # lock released on close


def test_lock_is_released_when_holder_process_is_killed(tmp_path):
    cfg, _ = cfg_for(tmp_path)
    assert child(cfg, crash_at="after_submit").returncode == 137
    Supervisor(cfg["db"]).close()                                                  # OS freed the lock on process death
