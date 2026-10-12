"""SUP-1: a supervisor killed inside the suspended-spawn window must not leave a suspended orphan.

REAL processes. A host process creates a child CREATE_SUSPENDED and is then killed BEFORE it assigns the child to any
attempt job (the exact window of `winproc.spawn_contained`). Negative control: without self-containment the suspended
child survives (the defect, as observed 2026-10-08 in the power-loss harness tests); with
`winproc.contain_current_process()` the OS kills it when the host dies."""
import os
import subprocess
import sys
import time
from pathlib import Path

import psutil
import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST = r'''
import subprocess, sys, time
sys.path.insert(0, sys.argv[1])
from uri_supervisor import winproc
state = winproc.contain_current_process() if sys.argv[2] == "contain" else "NOT_CONTAINED"
child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(600)"],
                         creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW | winproc.CREATE_SUSPENDED)
print(state, child.pid, flush=True)
time.sleep(600)
'''


def _run_host(mode):
    host = subprocess.Popen([sys.executable, "-c", HOST, str(ROOT), mode], stdout=subprocess.PIPE, text=True)
    state, pid = host.stdout.readline().split()
    child = psutil.Process(int(pid))
    assert child.status() in (psutil.STATUS_STOPPED, psutil.STATUS_RUNNING)      # suspended threads (no instruction ran)
    host.kill()                                                                  # supervisor death inside the window
    host.wait(10)
    return state, child


def _gone(proc, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not proc.is_running() or proc.status() == psutil.STATUS_ZOMBIE:
            return True
        time.sleep(0.1)
    return False


@pytest.mark.skipif(os.name != "nt", reason="Windows job objects")
def test_negative_control_without_self_containment_the_suspended_child_is_orphaned():
    state, child = _run_host("plain")
    try:
        assert state == "NOT_CONTAINED"
        assert not _gone(child, timeout=3)                                        # the SUP-1 defect, reproduced
        assert all(t.id for t in child.threads())
    finally:
        child.kill()


@pytest.mark.skipif(os.name != "nt", reason="Windows job objects")
def test_self_contained_host_death_kills_the_suspended_child():
    state, child = _run_host("contain")
    try:
        assert state == "CONTAINED"
        assert _gone(child), "suspended child survived its host"
    finally:
        if child.is_running():
            child.kill()


def test_supervisor_contains_its_host_before_any_spawn(tmp_path):
    from uri_supervisor.supervisor import Supervisor
    sup = Supervisor(tmp_path / "ledger.db")
    try:
        assert sup.self_containment in ("CONTAINED", "ALREADY_CONTAINED") or sup.self_containment.startswith("UNAVAILABLE:")
        if os.name == "nt":
            assert sup.self_containment in ("CONTAINED", "ALREADY_CONTAINED")
    finally:
        sup.ledger.close() if hasattr(sup.ledger, "close") else None


def test_oq_r1_3_no_supervisor_without_self_containment(tmp_path, monkeypatch):
    """Review round 1, OQ-R1-3: a Windows host that cannot contain itself gets no supervisor (fail closed)."""
    from uri_supervisor import winproc
    from uri_supervisor.supervisor import Supervisor, SupervisorError
    if not winproc.IS_WINDOWS:
        pytest.skip("Windows job objects")
    monkeypatch.setattr(winproc, "contain_current_process", lambda: "UNAVAILABLE:AssignProcessToJobObject:5")
    with pytest.raises(SupervisorError, match="SELF_CONTAINMENT_UNAVAILABLE"):
        Supervisor(tmp_path / "ledger.db")
