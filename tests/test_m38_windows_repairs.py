"""Regressions for Antigravity's audit of a87e158 (F-1..F-4) and the Codex audit of
3cd3557 (failed kill ignored; secret file readable on Windows), plus the flaky
differential-rerun comparison found while re-running round 3's suite.

Tests marked `windows_only` exercise the Windows code paths (Job Object, OpenProcess
liveness, owner-only DACL) and are skipped on POSIX; the POSIX-runnable tests cover the
shared behavior and the platform-independent logic (path semantics simulated with
`ntpath`, SDDL parsing).
"""
import ntpath
import os
from pathlib import Path
import subprocess
import sys
import textwrap
import time

import pytest

from tests.m37_edge_support import intake
from uri_v1.execution import proctree
from uri_v1.execution.harness.contracts import ElevationGrant, HarnessError, _names_same_path
from uri_v1.execution.harness.process import supervise
from uri_v1.execution.private_files import is_private, owner_only_sddl, sddl_is_owner_only, write_private
from uri_v1.execution.verify import _differential_rerun, run_process

windows_only = pytest.mark.skipif(os.name != "nt", reason="exercises the Windows code path")
posix_only = pytest.mark.skipif(os.name == "nt", reason="exercises the POSIX code path")


def _wait_dead(pid: int, seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not proctree.process_alive(pid): return True
        time.sleep(0.05)
    return False


def _parent_that_orphans(pid_file: Path, *, creationflags: str = "0") -> list:
    """A parent that starts a long-lived grandchild, records its PID, and exits at once."""
    code = textwrap.dedent(f"""
        import subprocess, sys
        flags = {creationflags}
        try:
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"], creationflags=flags,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:  # e.g. breakaway refused by the job: fall back to a plain detached child
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"],
                                     creationflags=0x00000008 | 0x00000200 if sys.platform == "win32" else 0,
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        open({str(pid_file)!r}, "w").write(str(child.pid))
    """)
    return [sys.executable, "-c", code]


# ---- F-1 / Codex: process-tree containment ---------------------------------------------------

def test_orphan_of_an_already_exited_parent_is_killed(tmp_path):
    """F-1: the parent exits cleanly first; its grandchild must still be reachable and killed.
    `taskkill /T` after the parent's exit could not do this on Windows."""
    pid_file = tmp_path / "gc.pid"
    proc = proctree.spawn(_parent_that_orphans(pid_file), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
    assert proc.wait(timeout=30) == 0
    gc = int(pid_file.read_text())
    assert proctree.process_alive(gc)
    try:
        assert proctree.kill_tree(proc) is True
        assert _wait_dead(gc)
    finally:
        proctree.release(proc)


def test_supervise_reports_settled_only_when_the_tree_is_confirmed_dead(tmp_path, monkeypatch):
    """Codex (3cd3557): a failed kill used to be swallowed, so a harness URI could not stop
    still counted as settled and its workspace could be verified. Now a kill that cannot be
    confirmed makes the run unsettled."""
    argv = [sys.executable, "-c", "print('hi')"]
    r = supervise(argv, cwd=tmp_path, env=dict(os.environ), stdin_bytes=None, timeout_s=30, inactivity_s=30,
                  log_path=tmp_path / "ok.log")
    assert r.settled and r.exit_code == 0
    monkeypatch.setattr(proctree, "kill_tree", lambda proc: (proc.wait(), False)[1])
    r = supervise(argv, cwd=tmp_path, env=dict(os.environ), stdin_bytes=None, timeout_s=30, inactivity_s=30,
                  log_path=tmp_path / "bad.log")
    assert not r.settled


def test_verifier_script_whose_tree_is_not_contained_never_passes(tmp_path, monkeypatch):
    """Codex (3cd3557), verifier side: `run_process` now reports containment and a
    script-run whose tree could not be confirmed dead is never a PASS."""
    assert run_process([sys.executable, "-c", "pass"], cwd=tmp_path, env=dict(os.environ), timeout_s=30)["contained"]
    monkeypatch.setattr(proctree, "kill_tree", lambda proc: (proc.wait(), False)[1])
    assert not run_process([sys.executable, "-c", "pass"], cwd=tmp_path, env=dict(os.environ), timeout_s=30)["contained"]


@posix_only
def test_posix_kill_refused_is_reported_not_swallowed(tmp_path, monkeypatch):
    proc = proctree.spawn([sys.executable, "-c", "pass"])
    proc.wait()
    def refused(pgid, sig): raise PermissionError("EPERM")
    monkeypatch.setattr(os, "killpg", refused)
    assert proctree.kill_tree(proc) is False


@windows_only
def test_job_is_kill_on_close_and_forbids_breakaway():
    job = proctree.JobTree()
    try:
        flags = job.limit_flags()
        assert flags & proctree.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        assert not flags & (proctree.JOB_OBJECT_LIMIT_BREAKAWAY_OK | proctree.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK)
    finally:
        job.close()


@windows_only
def test_detached_or_breakaway_grandchild_is_still_contained(tmp_path):
    """A grandchild asking for CREATE_BREAKAWAY_FROM_JOB | DETACHED_PROCESS |
    CREATE_NEW_PROCESS_GROUP is refused breakaway (or, falling back, starts detached
    inside the job) and still dies with the tree."""
    pid_file = tmp_path / "gc.pid"
    proc = proctree.spawn(_parent_that_orphans(pid_file, creationflags="0x01000000 | 0x00000008 | 0x00000200"),
                          stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    proc.wait(timeout=30)
    gc = int(pid_file.read_text())
    try:
        assert proctree.kill_tree(proc) is True and _wait_dead(gc)
    finally:
        proctree.release(proc)


@windows_only
def test_closing_the_job_kills_survivors(tmp_path):
    """Kill-on-close: if URI drops the job without an explicit kill (or dies), the tree dies."""
    pid_file = tmp_path / "gc.pid"
    proc = proctree.spawn(_parent_that_orphans(pid_file), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL)
    proc.wait(timeout=30)
    gc = int(pid_file.read_text())
    assert proctree.process_alive(gc)
    proctree.release(proc)
    assert _wait_dead(gc)


@windows_only
def test_spawn_fails_closed_when_the_child_cannot_be_contained(monkeypatch):
    def refuse(self, proc): raise proctree.ContainmentError("AssignProcessToJobObject failed (test)")
    monkeypatch.setattr(proctree.JobTree, "assign", refuse)
    with pytest.raises(proctree.ContainmentError):
        proctree.spawn([sys.executable, "-c", "import time; time.sleep(3600)"])


# ---- F-2: Windows-compatible liveness ---------------------------------------------------------

def test_process_alive_tracks_a_real_process(tmp_path):
    assert proctree.process_alive(os.getpid())
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    assert not proctree.process_alive(child.pid)


@posix_only
def test_process_alive_treats_a_zombie_as_dead():
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    deadline = time.monotonic() + 5
    while proctree.process_alive(child.pid) and time.monotonic() < deadline: time.sleep(0.05)
    assert not proctree.process_alive(child.pid)  # exited but not yet reaped
    child.wait()


@windows_only
def test_process_alive_never_uses_os_kill_on_windows(monkeypatch):
    """On Windows `os.kill(pid, 0)` is not a probe (WinError 87 / CTRL_C_EVENT)."""
    def forbidden(*a): raise AssertionError("os.kill used as a liveness probe")
    monkeypatch.setattr(os, "kill", forbidden)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        assert proctree.process_alive(child.pid)
    finally:
        child.kill(); child.wait()
    assert not proctree.process_alive(child.pid)


def test_qualification_driver_liveness_is_portable():
    from scripts import m38_harness_qualification as driver
    assert driver.process_alive is proctree.process_alive and driver._alive(os.getpid())
    child = subprocess.Popen([sys.executable, "-c", "pass"]); child.wait()
    assert not driver._alive(child.pid)


# ---- F-3: semantic path consent ----------------------------------------------------------------

def _nt_resolve(p: str) -> str:
    """What `Path(p).expanduser().resolve()` does on Windows for an absolute-ish path on C:."""
    return ntpath.normpath(p if ntpath.splitdrive(p)[0] else "C:" + p)


@pytest.mark.parametrize("text,granted,ok", [
    ("yes, allow access to /home/someone/e for this run", r"C:\home\someone\e", True),   # the a87e158 F-3 case
    ("yes, allow access to D:/Reports/2026 for this run", r"D:\reports\2026", True),      # separators and case
    (r"yes, allow access to d:\REPORTS\2026\ for this run.", r"D:\Reports\2026", True),   # trailing slash, period
    ('yes, allow access to "C:\\My Docs\\q3" please', r"C:\My Docs\q3", True),           # quoted, with a space
    ("yes, it's fine, allow access to D:/x for Chetan's run", r"D:\x", True),             # apostrophes elsewhere
    ("yes, allow access to D:/Reports/2026 for this run", r"D:\Reports", False),         # a child never grants the parent
    ("yes, allow access to D:/Reports for this run", r"D:\Reports\2026", False),         # nor a parent the child
    ("yes, allow access to /home/someone/e2 for this run", r"C:\home\someone\e", False),
    ("yes, allow access to reports for this run", r"C:\reports", False),                 # a bare word is not a path
])
def test_consent_compares_paths_semantically_under_windows_rules(text, granted, ok):
    assert _names_same_path(text, granted, resolve=_nt_resolve, normcase=ntpath.normcase) is ok


def test_consent_still_works_on_this_platform(tmp_path):
    d = tmp_path / "Reports" / "2026"; d.mkdir(parents=True)
    g = ElevationGrant.from_user(intake(f"yes, allow access to {d}/ for this run"), f"extra_dir:{d}", "run-1")
    assert g.elevation == f"extra_dir:{d.resolve()}"
    with pytest.raises(HarnessError):
        ElevationGrant.from_user(intake(f"yes, allow access to {d} for this run"), f"extra_dir:{d.parent}", "run-1")


@windows_only
def test_windows_posix_style_consent_is_accepted(tmp_path):
    """The exact a87e158 F-3 reproduction, on a real Windows host."""
    g = ElevationGrant.from_user(intake("yes, allow access to /home/someone/e for this run"), "extra_dir:/home/someone/e", "run-1")
    assert ntpath.normcase(g.elevation.split(":", 1)[1]).endswith(ntpath.normcase(r"\home\someone\e"))


@windows_only
def test_any_windows_drive_root_and_unc_paths_are_refused():
    for root in ("\\", "D:\\", "C:\\", "\\\\server\\share\\x"):
        with pytest.raises(HarnessError):
            ElevationGrant.from_user(intake(f"yes, allow access to {root} for this run"), f"extra_dir:{root}", "run-1")


# ---- F-4 / Codex: owner-only secret files --------------------------------------------------------

def test_write_private_is_owner_only_on_this_platform(tmp_path):
    p = tmp_path / "mcp.json"
    write_private(p, b"{}")
    assert p.read_bytes() == b"{}" and is_private(p)
    if os.name != "nt": assert p.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError): write_private(p, b"again")  # exclusive create, never overwrite


@posix_only
def test_is_private_rejects_a_group_or_world_readable_file(tmp_path):
    p = tmp_path / "f"; p.write_bytes(b"x"); p.chmod(0o644)
    assert not is_private(p)


SID = "S-1-5-21-1-2-3-1001"


@pytest.mark.parametrize("sddl,ok", [
    (owner_only_sddl(SID), True),
    ("D:P", True),                                              # no entries: nobody has access
    (f"D:(A;;FA;;;{SID})", False),                              # not protected: inheritance can add readers
    (f"D:P(A;;FA;;;{SID})(A;;FR;;;WD)", False),                  # Everyone can read
    (f"D:P(A;ID;FA;;;{SID})", False),                            # inherited entry
    (f"D:P(A;;FA;;;{SID})(A;;FA;;;BA)", False),                  # Administrators too
    ("D:NO_ACCESS_CONTROL", False),                             # NULL DACL: everyone
    ("D:AI(A;;FA;;;S-1-5-21-1-2-3-1001)", False),
])
def test_owner_only_sddl_check(sddl, ok):
    assert sddl_is_owner_only(sddl, SID) is ok


@windows_only
def test_windows_secret_file_is_not_readable_by_other_principals(tmp_path):
    """Codex (3cd3557) / a87e158 F-4: mcp.json was created 0o666 (inherited ACL) on Windows."""
    from uri_v1.execution import private_files
    p = tmp_path / "mcp.json"
    write_private(p, b"{}")
    sddl = private_files._dacl_sddl(p)
    assert sddl_is_owner_only(sddl, private_files.current_user_sid()), sddl


# ---- differential rerun: compare content, not bytes ------------------------------------------------

def test_metadata_only_change_does_not_count_as_a_causal_change(tmp_path):
    """Round 3's differential rerun compared raw .xlsx bytes, which embed the save time, so a
    hardcoded output whose two runs straddled a clock second "changed" and passed (the
    intermittent test_hardcoded_output_fails_the_differential_rerun failure). Here the
    hardcoded script changes metadata on every run (process id as the title) but never its
    content: it must FAIL, deterministically."""
    openpyxl = pytest.importorskip("openpyxl")
    vdir = tmp_path / "v"; vdir.mkdir(); tmp = tmp_path / "v.tmp"; tmp.mkdir()
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Data"; ws.append(["Amount"]); ws.append([10]); ws.append([20])
    wb.save(vdir / "input.xlsx")
    (vdir / "report.py").write_text(
        "import os\nfrom openpyxl import Workbook\n"
        "out = Workbook(); out.properties.title = str(os.getpid()); o = out.active; o.title = 'Summary'\n"
        "o.append(['Total']); o.append([30]); out.save('summary.xlsx')\n")
    subprocess.run([sys.executable, "report.py"], cwd=vdir, check=True)
    item = _differential_rerun({"script": "report.py"}, ["summary.xlsx"], vdir, tmp, None)
    assert item["status"] == "FAIL", item
