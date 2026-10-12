"""Live synthetic Windows containment; never invokes a native harness."""
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

import pytest

from uri_core.client_runtime import process_tree as tree
from uri_core.core.runtime_identity import child_environment

ROOT = Path(__file__).resolve().parent
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows process component")


@pytest.fixture
def fixture_root():
    root = ROOT / "work/c1" / ("windows_job_" + uuid.uuid4().hex)
    for rel in ("home/roaming", "home/local", "temp"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    return root


def spawn(root, code):
    return tree.spawn([sys.executable, "-B", "-I", "-c", code], cwd=str(root),
                      env=child_environment(root, Path(sys.executable)),
                      stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def wait_dead(pid):
    deadline = time.monotonic() + 5
    while tree.process_alive(pid) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not tree.process_alive(pid)


def test_job_flags_and_owned_termination(fixture_root):
    proc = spawn(fixture_root, "import time; time.sleep(30)")
    try:
        flags = proc._uri_job.limit_flags()
        assert flags & tree.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        assert not flags & (tree.JOB_OBJECT_LIMIT_BREAKAWAY_OK | tree.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK)
        assert tree.kill_tree(proc) is True
        wait_dead(proc.pid)
    finally:
        tree.release(proc)
        proc.wait(timeout=5)


@pytest.mark.parametrize("close_only", [False, True])
def test_orphaned_detached_descendant_is_still_owned(fixture_root, close_only):
    code = ('import subprocess,sys; p=subprocess.Popen([sys.executable,"-I","-c","import time; time.sleep(30)"],'
            'creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS,'
            'stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL); print(p.pid,flush=True)')
    proc = spawn(fixture_root, code)
    try:
        output, err = proc.communicate(timeout=5)
        assert proc.returncode == 0
        child = int(output.strip())
        assert tree.process_alive(child)
        if close_only:
            tree.release(proc)
        else:
            assert tree.kill_tree(proc) is True
        wait_dead(child)
    finally:
        tree.release(proc)
        proc.wait(timeout=5)


def test_assignment_failure_never_runs_child_code(fixture_root, monkeypatch):
    marker = fixture_root / "must-not-exist.txt"
    def refuse(*_):
        raise tree.ContainmentError("synthetic_assignment_failure")
    monkeypatch.setattr(tree.JobTree, "assign", refuse)
    with pytest.raises(tree.ContainmentError):
        spawn(fixture_root, 'from pathlib import Path; Path("must-not-exist.txt").write_text("executed")')
    assert not marker.exists()


def test_job_disallows_breakaway_child(fixture_root):
    code = ('import subprocess,sys;\ntry:\n'
            ' p=subprocess.Popen([sys.executable,"-I","-c","import time; time.sleep(30)"],creationflags=0x01000000)\n'
            ' print("CREATED",p.pid,flush=True)\n'
            'except OSError as e:\n print("REFUSED",e.winerror,flush=True)')
    proc = spawn(fixture_root, code)
    try:
        output = proc.stdout.readline().strip()
        proc.wait(timeout=5)
        assert proc.returncode == 0
        if output.startswith(b"CREATED "):
            child = int(output.split()[1])
            # Nested jobs may ignore partial breakaway requests. Creation
            # succeeding is not escape; prove exact job membership/death.
            assert proc._uri_job.contains(child)
            assert tree.kill_tree(proc) is True
            wait_dead(child)
        else:
            assert output == b"REFUSED 5"
    finally:
        assert tree.kill_tree(proc) is True
        tree.release(proc)


def test_owner_crash_kills_job_child(fixture_root):
    code = ('import sys,os,time; sys.path.insert(0,' + repr(str(ROOT)) + ');'
            'from uri_core.client_runtime import process_tree as t;'
            'p=t.spawn([sys.executable,"-I","-c","import time; time.sleep(30)"]);'
            'print(p.pid,flush=True); os._exit(0)')
    owner = subprocess.Popen([sys.executable, "-B", "-I", "-c", code], cwd=fixture_root,
        env=child_environment(fixture_root, Path(sys.executable)), stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
    output, _ = owner.communicate(timeout=5)
    assert owner.returncode == 0
    wait_dead(int(output.strip()))


def test_uncontained_process_cleanup_is_refused(fixture_root):
    # This unrelated fixture is owned by this test, not by JobTree. The
    # component must leave it alone; cleanup uses our original process handle.
    proc = subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(30)"], cwd=fixture_root,
                            env=child_environment(fixture_root, Path(sys.executable)),
                            creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        assert tree.kill_tree(proc) is False
        assert proc.poll() is None
    finally:
        proc.terminate(); proc.wait(timeout=5)


@pytest.mark.parametrize("options", [{"shell": True}, {"creationflags": 0}, {"start_new_session": True}])
def test_caller_cannot_weaken_spawn_containment(fixture_root, options):
    with pytest.raises(tree.ContainmentError, match="OPTIONS_RESERVED"):
        tree.spawn([sys.executable, "-c", "raise SystemExit(0)"], cwd=fixture_root, **options)
