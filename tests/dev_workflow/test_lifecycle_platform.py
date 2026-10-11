"""DEV-LIFECYCLE-2 (TEST ONLY): Windows containment (F2). F1 and F3: test_lifecycle_remote.py.

Windows containment is tested two ways:
* on every platform, the containment LOGIC with a fake kernel32 (call order, flags, the ActiveProcesses rule,
  fail-closed paths) - these run on Linux and fail on the baseline (no containment module, os.killpg crash);
* on Windows only, the real job objects (``windows_only``: reported by name as PLATFORM-GATED elsewhere).
"""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.dev_workflow import containment as C
from scripts.dev_workflow import lifecycle as L
from scripts.dev_workflow import lifecycle_providers as LP

PY = sys.executable
REAL_POPEN = subprocess.Popen
WIN = pytest.mark.windows_only


# ---------------------------------------------------------------- F2: Windows job containment logic (fake kernel32)

class FakeApi:
    def __init__(self, create_fails=False, assign_fails=False, resume_fails=False, stuck=0, terminate_fails=False):
        self.calls, self.jobs, self.n = [], {}, 0
        self.create_fails, self.assign_fails, self.resume_fails, self.stuck = create_fails, assign_fails, resume_fails, stuck
        self.terminate_fails = terminate_fails

    def create(self):
        self.calls.append("create")
        if self.create_fails:
            raise OSError(5, "CreateJobObjectW failed")
        self.n += 1
        self.jobs[self.n] = {"active": 1, "terminated": False}
        return self.n

    def assign(self, job, handle):
        self.calls.append(("assign", job))
        if self.assign_fails:
            raise OSError(5, "AssignProcessToJobObject failed")

    def resume(self, pid):
        self.calls.append(("resume", pid))
        if self.resume_fails:
            raise OSError(5, "ResumeThread failed")
        return 1

    def terminate(self, job):
        self.calls.append(("terminate", job))
        if self.terminate_fails:
            raise OSError(5, "TerminateJobObject failed")
        self.jobs[job]["terminated"] = True
        self.jobs[job]["active"] = self.stuck

    def active(self, job):
        return self.jobs[job]["active"]

    def close(self, job):
        self.calls.append(("close", job))


class FakeProc:
    def __init__(self, argv, **kw):
        self.argv, self.kw, self.pid, self._handle = argv, kw, 4242, 77
        self.killed = False

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        return 0


@pytest.fixture
def fake_windows(monkeypatch):
    def install(**kw):
        api = FakeApi(**kw)
        monkeypatch.setattr(C, "WINDOWS", True)
        monkeypatch.setattr(C, "_API", api)
        monkeypatch.setattr(C, "_OPEN_JOBS", [])
        monkeypatch.setattr(C, "_TAINTED", [], raising=False)
        monkeypatch.setattr(C.subprocess, "Popen", FakeProc)
        monkeypatch.setattr(C.subprocess, "run", lambda *a, **k: None)
        return api
    return install


def test_f2_job_flags_kill_on_close_and_no_breakaway():
    flags = C.JOB_LIMIT_FLAGS
    assert flags & C.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    assert not flags & (C.JOB_OBJECT_LIMIT_BREAKAWAY_OK | C.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK)


def test_f2_suspended_assigned_then_resumed(fake_windows):
    api = fake_windows()
    p = C.spawn(["worker"], stdout=None)
    assert p.kw["creationflags"] & C.CREATE_SUSPENDED and "start_new_session" not in p.kw
    assert api.calls == ["create", ("assign", 1), ("resume", 4242)]   # nothing runs before it is in the job
    r = C.finish(p)
    assert r["contained"] is True and r["active_processes"] == 0 and ("terminate", 1) in api.calls


def test_f2_contained_only_when_active_processes_is_zero(fake_windows, monkeypatch):
    fake_windows(stuck=2)
    monkeypatch.setattr(C, "EMPTY_WAIT_S", 0.1)
    r = C.finish(C.spawn(["worker"]), wait_s=0.1)
    assert r["contained"] is False and "2 process" in r["reason"]


@pytest.mark.parametrize("failure", ["create_fails", "assign_fails"])
def test_f2_job_failure_is_not_contained(fake_windows, failure):
    api = fake_windows(**{failure: True})
    p = C.spawn(["worker"])
    assert ("resume", 4242) in api.calls        # it runs, but is reported as not contained
    r = C.finish(p)
    assert r["contained"] is False and r["reason"]


def test_f2_unresumable_process_is_killed_and_refused(fake_windows):
    api = fake_windows(resume_fails=True)
    with pytest.raises(OSError):
        C.spawn(["worker"])
    assert ("terminate", 1) in api.calls


def test_f2_precheck_confirms_earlier_jobs_are_empty(fake_windows, monkeypatch):
    api = fake_windows()
    C.finish(C.spawn(["worker"]))
    assert C.precheck()["contained"] is True and ("close", 1) in api.calls and C._OPEN_JOBS == []
    C.finish(C.spawn(["worker"]))
    api.jobs[2]["active"] = 1                    # something reappeared in the earlier job
    api.stuck = 1
    r = C.precheck(wait_s=0.1)
    assert r["contained"] is False and "earlier" in r["reason"]


@pytest.mark.parametrize("failure", ["create_fails", "assign_fails"])
def test_r1_01_precheck_after_a_worker_without_a_job_is_not_contained(fake_windows, failure):
    """R1-01: a worker or gate that ran outside any job may have left processes nobody can verify; every later
    precheck() must fail closed, also after a later worker that was contained."""
    api = fake_windows(**{failure: True})
    assert C.finish(C.spawn(["gate"]))["contained"] is False
    r = C.precheck(wait_s=0.1)
    assert r["contained"] is False and "outside a job" in r["reason"]
    api.create_fails = api.assign_fails = False
    assert C.finish(C.spawn(["worker"]))["contained"] is True
    assert C.precheck(wait_s=0.1)["contained"] is False


def test_r1_01_precheck_after_a_failed_termination_is_not_contained(fake_windows):
    """R1-01: TerminateJobObject failing in finish() keeps the job; precheck() re-checks it and fails closed while it
    still cannot be emptied, and is contained once a later termination has emptied it."""
    api = fake_windows(terminate_fails=True)
    r = C.finish(C.spawn(["gate"]), wait_s=0.1)
    assert r["contained"] is False and "not verified" in r["reason"]
    assert C._OPEN_JOBS == [1]
    r = C.precheck(wait_s=0.1)
    assert r["contained"] is False and "earlier job" in r["reason"]
    api.terminate_fails = False
    assert C.precheck(wait_s=0.1) == {"contained": True, "killed": 1}
    assert ("close", 1) in api.calls and C._OPEN_JOBS == []


def test_r1_01_precheck_after_a_failed_empty_check_is_not_contained(fake_windows, monkeypatch):
    """R1-01: QueryInformationJobObject failing in finish() keeps the job for precheck()."""
    api = fake_windows()
    real_active = api.active
    def broken(job):
        raise OSError(5, "QueryInformationJobObject failed")
    monkeypatch.setattr(api, "active", broken)
    assert C.finish(C.spawn(["gate"]), wait_s=0.1)["contained"] is False
    assert C.precheck(wait_s=0.1)["contained"] is False
    monkeypatch.setattr(api, "active", real_active)
    assert C.precheck(wait_s=0.1)["contained"] is True and C._OPEN_JOBS == []


def test_f2_no_kernel32_is_not_contained(monkeypatch):
    monkeypatch.setattr(C, "WINDOWS", True)
    monkeypatch.setattr(C, "_API", False)
    assert C.precheck()["contained"] is False
    assert LP.sweep_orphans()["contained"] is False


def _real_milestone_round(worker_rec):
    w = {"status": "COMPLETED", "provider": "claude_cli", "binary_is_default": True, "binary_anchor_ok": True,
         "config_isolated": True, "session_id": "s-1", "contained": worker_rec["contained"]}
    return {"worker": w, "integrity": {"ok": True}}


def test_f2_job_creation_failure_means_the_review_does_not_count(fake_windows, monkeypatch, tmp_path):
    """End to end through run_worker: a job that cannot be created -> contained False -> is_independent False."""
    fake_windows(create_fails=True)
    def popen_without_windows_flags(argv, **kw):
        kw.pop("creationflags", None)
        return REAL_POPEN(argv, **kw)
    monkeypatch.setattr(C.subprocess, "Popen", popen_without_windows_flags)
    spec = {"provider": "command", "argv": [PY, "-c", "import sys; sys.stdin.read(); print('done')"]}
    rec = LP.run_worker(spec, "reviewer", "prompt", tmp_path, tmp_path / "log", timeout_s=60)
    assert rec["status"] == "COMPLETED" and rec["contained"] is False
    ok, why = L.is_independent({"milestone": "M-REAL-1", "reviewer": {"provider": "claude_cli"}},
                               _real_milestone_round(rec))
    assert not ok and "containment" in why


# ---------------------------------------------------------------- F2: real job objects (Windows only)

def _alive(pid: int) -> bool:
    import ctypes
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    h = k.OpenProcess(0x1000, False, pid)          # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    code = ctypes.c_ulong()
    try:
        k.GetExitCodeProcess(h, ctypes.byref(code))
        return code.value == 259                    # STILL_ACTIVE
    finally:
        k.CloseHandle(h)


@WIN
def test_win_kill_tree_on_exited_pid_and_on_a_live_tree():
    C.kill_pid_tree(999999)                         # an exited / unknown pid: no exception
    p = C.spawn([PY, "-c", "import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; "
                           "time.sleep(60)']); time.sleep(60)"])
    time.sleep(1.5)
    C.kill_tree(p)
    p.wait(timeout=10)
    assert C.finish(p)["contained"] is True


@WIN
def test_win_grandchild_is_gone_after_the_sweep(tmp_path):
    out = tmp_path / "gc.txt"
    code = ("import subprocess,sys; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(120)'], "
            "creationflags=0x00000008|0x00000200); open(sys.argv[1],'w').write(str(p.pid))")
    p = C.spawn([PY, "-c", code, str(out)])
    p.wait(timeout=30)
    gc = int(out.read_text())
    assert _alive(gc)                               # outlived its parent (detached), but is in the job
    r = C.finish(p)
    assert r["contained"] is True and r["active_processes"] == 0
    assert not _alive(gc)
    assert C.precheck()["contained"] is True


@WIN
def test_win_breakaway_is_refused(tmp_path):
    out = tmp_path / "ba.txt"
    code = ("import subprocess,sys\ntry:\n subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'], "
            "creationflags=0x01000000)\n r='STARTED'\nexcept OSError as e:\n r='REFUSED %s' % e.winerror\n"
            "open(sys.argv[1],'w').write(r)")
    p = C.spawn([PY, "-c", code, str(out)])
    p.wait(timeout=30)
    r = C.finish(p)
    assert out.read_text().startswith("REFUSED") and r["contained"] is True


@WIN
def test_win_active_processes_rule_on_a_real_job():
    p = C.spawn([PY, "-c", "import time; time.sleep(60)"])
    api = C.win_api()
    assert api.active(p._uri_job) == 1
    flags = api.limit_flags(p._uri_job)
    assert flags & C.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    assert not flags & (C.JOB_OBJECT_LIMIT_BREAKAWAY_OK | C.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK)
    r = C.finish(p)
    assert r == {"contained": True, "killed": "job terminated", "active_processes": 0}


@WIN
def test_win_job_creation_failure_is_not_contained(monkeypatch):
    api = C.win_api()

    def fail():
        raise OSError(5, "simulated")
    monkeypatch.setattr(api, "create", fail)
    p = C.spawn([PY, "-c", "pass"])
    p.wait(timeout=30)
    assert C.finish(p)["contained"] is False
