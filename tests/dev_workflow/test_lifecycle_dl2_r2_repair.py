"""DEV-LIFECYCLE-2 r2 repair regressions (R1-02, R2-01), runnable on every platform.

R1-02: a Windows ``.cmd`` launcher that hands the reviewer to a command interpreter (cmd.exe, PowerShell) or a shell
script, or that passes ``%*`` only outside the line that runs the program, is not bound or launched.
R2-01: a worker or gate command whose ``communicate()`` raises OSError after a successful spawn still goes through
``containment.finish``: its job is terminated and tracked (fake kernel32).
"""
import os
import sys

import pytest

from scripts.dev_workflow import containment as C
from scripts.dev_workflow import lifecycle as L
from scripts.dev_workflow import lifecycle_providers as P
from tests.dev_workflow.test_lifecycle_platform import FakeApi, FakeProc


# ---------------------------------------------------------------- R1-02

@pytest.fixture
def win(monkeypatch, tmp_path):
    monkeypatch.setattr(P, "WINDOWS", True)
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD")
    d = tmp_path / "npm"
    d.mkdir()
    monkeypatch.setenv("PATH", str(d))
    for rel in ("cmd.exe", "powershell.exe", "pwsh.exe", "node.exe", "prog/claude.exe"):
        (d / rel).parent.mkdir(parents=True, exist_ok=True)
        (d / rel).write_bytes(b"MZ " + rel.encode())
    for rel in ("real.bat", "real.cmd", "claude.ps1"):
        (d / rel).write_text("@echo off\r\n")
    return d


@pytest.mark.parametrize("body", [
    b'@ECHO off\r\n"%~dp0cmd.exe" /c "%~dp0real.bat" %*\r\n',                 # the reviewer's probe
    b'@ECHO off\r\n"%~dp0cmd.exe" /c %*\r\n',                                # cmd.exe as the program
    b'@ECHO off\r\n"%~dp0pwsh.exe" -File "%~dp0claude.ps1" %*\r\n',            # PowerShell script
    b'@ECHO off\r\n"%~dp0powershell.exe" -NoProfile %*\r\n',                   # PowerShell reading stdin
    b'@ECHO off\r\n"%~dp0node.exe" "%~dp0real.cmd" %*\r\n',                    # a .cmd as the "script"
    b'@ECHO off\r\nREM %*\r\n"%~dp0prog/claude.exe"\r\n',                      # %* only in a comment
    b'@ECHO off\r\nSET a=%*\r\n"%~dp0prog/claude.exe"\r\n',                    # %* not on the launch line
    b'@ECHO off\r\nREM %*\r\n"%~dp0cmd.exe" /k\r\n',                         # cmd.exe, %* only in a comment
])
def test_r1_02_launcher_running_an_interpreter_or_without_launch_line_args_is_refused(win, body):
    (win / "claude.cmd").write_bytes(body)
    r = P.resolve_cli(str(win / "claude.cmd"))
    assert "error" in r and "launch" not in r
    ident = P.reviewer_executable({"provider": "claude_cli"})
    assert ident.get("path", "").endswith("claude.cmd") and ident.get("unlaunchable")
    assert P.cli_launch({"provider": "claude_cli", "binary": str(win / "claude.cmd")}, "claude") != \
        [os.path.realpath(win / "cmd.exe")]


# ---------------------------------------------------------------- R2-01

class BrokenPipeProc(FakeProc):
    returncode = None

    def communicate(self, input=None, timeout=None):
        raise OSError(22, "Invalid argument")


@pytest.fixture
def fake_windows(monkeypatch):
    api = FakeApi()
    monkeypatch.setattr(C, "WINDOWS", True)
    monkeypatch.setattr(C, "_API", api)
    monkeypatch.setattr(C, "_OPEN_JOBS", [])
    monkeypatch.setattr(C, "_TAINTED", [])
    monkeypatch.setattr(C.subprocess, "Popen", BrokenPipeProc)
    monkeypatch.setattr(C.subprocess, "run", lambda *a, **k: None)
    return api


def test_r2_01_worker_whose_communicate_fails_is_finished(fake_windows, tmp_path):
    api = fake_windows
    rec = P.run_worker({"provider": "command", "argv": [sys.executable, "-c", "pass"]}, "reviewer", "prompt", tmp_path,
                       tmp_path / "log", timeout_s=60)
    assert rec["status"] == "FAILED" and "communicate" in rec["detail"]
    assert api.jobs[1]["terminated"] is True and api.jobs[1]["active"] == 0
    assert "containment_post" in rec
    # the job was tracked by finish(): precheck re-verifies it and only then closes it
    assert C.precheck(wait_s=0.1)["contained"] is True and ("close", 1) in api.calls


def test_r2_01_worker_left_running_after_communicate_failure_fails_closed(fake_windows, tmp_path, monkeypatch):
    """If termination fails, the job stays tracked and the next precheck is not contained."""
    api = fake_windows
    api.terminate_fails = True
    rec = P.run_worker({"provider": "command", "argv": [sys.executable, "-c", "pass"]}, "reviewer", "prompt", tmp_path,
                       tmp_path / "log", timeout_s=60)
    assert rec["status"] == "FAILED" and rec["contained"] is False
    assert C._OPEN_JOBS == [1]
    assert C.precheck(wait_s=0.1)["contained"] is False


def test_r2_01_gate_command_whose_communicate_fails_is_finished(fake_windows, tmp_path):
    api = fake_windows
    rc, out, err, state = L.run_cmd(["gate"], tmp_path, 60)
    assert rc is None and state == "BLOCKED" and "communicate" in err
    assert api.jobs[1]["terminated"] is True and C._OPEN_JOBS == [1]
    assert C.precheck(wait_s=0.1)["contained"] is True
