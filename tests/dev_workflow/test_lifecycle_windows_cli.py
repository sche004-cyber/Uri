"""DEV-LIFECYCLE-2 W-1 / W-2 regressions, runnable on every platform.

W-1: gate test ids resolve to repository-relative paths with "/" (git's form), also where the OS separator is "\\".
W-2: on Windows the reviewer CLI found on PATH is an npm ``.cmd`` launcher. The identity bound at PLAN and checked
before every round is the program the launcher runs (plus the launcher itself), and that program is started directly,
never through cmd.exe. These tests switch the provider module into its Windows mode and use fixture launchers, so the
logic is checked on Linux too; the real install is exercised on the owner's PC.
"""
import json
import os
from pathlib import Path, PureWindowsPath

import pytest

from scripts.dev_workflow import lifecycle as L
from scripts.dev_workflow import lifecycle_providers as P


# ---------------------------------------------------------------- W-1

def test_w1_gate_test_id_is_a_slash_path_where_the_os_separator_is_backslash(tmp_path, monkeypatch):
    (tmp_path / "uri_ui/test").mkdir(parents=True)
    (tmp_path / "uri_ui/test/widget_test.dart").write_text("")
    real_path = L.Path

    class WinStylePath(PureWindowsPath):  # what str(Path(...)) gives on Windows: "\\" separators
        pass
    monkeypatch.setattr(L, "Path", WinStylePath)
    assert L._test_file("test/widget_test.dart::App renders", real_path(tmp_path), "uri_ui") == \
        "uri_ui/test/widget_test.dart"


# ---------------------------------------------------------------- W-2

@pytest.fixture
def win(monkeypatch, tmp_path):
    """The provider module in its Windows mode, PATH = one fixture folder."""
    monkeypatch.setattr(P, "WINDOWS", True, raising=False)  # (absent before W-2: the tests then fail on behaviour)
    monkeypatch.setenv("PATHEXT", ".COM;.EXE;.BAT;.CMD;.VBS;.JS;.PS1")
    d = tmp_path / "npm"
    d.mkdir()
    monkeypatch.setenv("PATH", str(d))
    return d


def _exe(path: Path, content: bytes = b"MZ fake program") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _native_shim(d: Path, rel: str = "prog/claude.exe") -> Path:
    """npm's launcher for a native CLI (the shape installed on the owner's PC)."""
    shim = d / "claude.cmd"
    shim.write_bytes(('@ECHO off\r\nGOTO start\r\n:find_dp0\r\nSET dp0=%~dp0\r\nEXIT /b\r\n:start\r\nSETLOCAL\r\n'
                      f'CALL :find_dp0\r\n"%dp0%{rel}"   %*\r\n').encode())
    return shim


def test_w2_native_launcher_binds_and_launches_the_program_not_the_cmd(win):
    exe = _exe(win / "prog/claude.exe")
    _native_shim(win)
    ident = P.reviewer_executable({"provider": "claude_cli"})
    assert ident["realpath"] == os.path.realpath(exe) and ident["sha256"] == P._file_sha256(str(exe))
    assert ident["launch"] == [os.path.realpath(exe)] and ident["launcher"]["realpath"].endswith("claude.cmd")
    assert not ident.get("ambiguous") and not ident.get("unlaunchable")
    argv = P.build_argv({"provider": "claude_cli", "binary": ident["path"]}, "reviewer", win, [], "sid")
    assert argv[0] == os.path.realpath(exe) and not argv[0].lower().endswith(".cmd")
    assert argv[1:6] == ["-p", "--safe-mode", "--setting-sources", "", "--strict-mcp-config"]


def test_w2_program_replaced_behind_an_unchanged_launcher_changes_the_identity(win):
    exe = _exe(win / "prog/claude.exe")
    shim = _native_shim(win)
    before = P.reviewer_executable({"provider": "claude_cli"})
    shim_bytes = shim.read_bytes()
    _exe(exe, b"MZ another program")
    assert shim.read_bytes() == shim_bytes
    after = P.reviewer_executable({"provider": "claude_cli"})
    assert after["sha256"] != before["sha256"] and after["launcher"] == before["launcher"]
    # the driver binds control_state()["reviewer_exec"] at PLAN: the change is drift (TAMPER), and run_worker refuses
    w = P.run_worker({"provider": "claude_cli", "binary": before["path"], "_anchor": before}, "reviewer", "p", win,
                     win.parent / "logs")
    assert w["status"] == "REFUSED" and w["binary_anchor_ok"] is False


def test_w2_npm_script_launcher_binds_interpreter_and_script(win):
    node = _exe(win / "node.exe", b"MZ node")
    cli = win / "node_modules/@anthropic-ai/claude-code/cli.js"
    cli.parent.mkdir(parents=True)
    cli.write_text("// cli")
    (win / "claude.cmd").write_bytes(
        b'@ECHO off\r\nSETLOCAL\r\nIF EXIST "%~dp0node.exe" (\r\n  SET "_prog=%~dp0node.exe"\r\n) ELSE (\r\n'
        b'  SET "_prog=node"\r\n)\r\n"%_prog%"  "%~dp0node_modules/@anthropic-ai/claude-code/cli.js" %*\r\n')
    ident = P.reviewer_executable({"provider": "claude_cli"})
    assert ident["launch"] == [os.path.realpath(node), os.path.realpath(cli)]
    assert ident["realpath"] == os.path.realpath(cli)
    assert ident["interpreter"] == {"realpath": os.path.realpath(node), "sha256": P._file_sha256(str(node))}


@pytest.mark.parametrize("body,reason", [
    (b'@ECHO off\r\n"%~dp0a.exe" "%~dp0b.exe" %*\r\n', "several programs"),
    (b'@ECHO off\r\n"%~dp0missing.exe" %*\r\n', "does not name one executable"),
    (b'@ECHO off\r\n"%~dp0prog/claude.exe"\r\n', "does not pass its arguments on"),
])
def test_w2_launcher_that_cannot_be_bound_is_unlaunchable(win, body, reason):
    """The launcher IS found (not a vacuous 'not found', R1-03) and is refused for its own reason."""
    _exe(win / "a.exe")
    _exe(win / "b.exe")
    _exe(win / "prog/claude.exe")
    (win / "claude.cmd").write_bytes(body)
    ident = P.reviewer_executable({"provider": "claude_cli"})
    assert ident["path"] == os.path.abspath(win / "claude.cmd") and ident["error"] != "not found"
    assert len(ident["unlaunchable"]) == 1 and reason in ident["unlaunchable"][0]
    assert "sha256" not in ident


def test_w2_ps1_only_is_not_a_reviewer_cli(win):
    """A ``.ps1`` is never a candidate, while a ``.cmd`` launcher beside it is (R1-03: the 'not found' is the
    ``.ps1`` being skipped, not the launcher lookup failing on this platform)."""
    (win / "claude.ps1").write_text("& node cli.js $args")
    assert P.reviewer_executable({"provider": "claude_cli"}) == {"name": "claude", "error": "not found"}
    exe = _exe(win / "prog/claude.exe")
    _native_shim(win)
    ident = P.reviewer_executable({"provider": "claude_cli"})
    assert ident["path"] == os.path.abspath(win / "claude.cmd") and ident["launch"] == [os.path.realpath(exe)]
    assert not ident.get("unlaunchable") and not ident.get("ambiguous")


def test_w2_npm_shims_with_comments_and_if_exist_lines_are_still_bound(win):
    """R1-02 keeps the genuine npm shapes launchable: comment and IF EXIST lines are not the launch line."""
    exe = _exe(win / "prog/claude.exe")
    (win / "claude.cmd").write_bytes(b'@ECHO off\r\nREM npm shim\r\n:: generated\r\nGOTO start\r\n:start\r\n'
                                     b'SETLOCAL\r\n"%~dp0prog/claude.exe"   %*\r\n')
    assert P.resolve_cli(str(win / "claude.cmd"))["launch"] == [os.path.realpath(exe)]


def test_w2_exe_planted_beside_the_launcher_is_ambiguous(win):
    _exe(win / "prog/claude.exe")
    _native_shim(win)
    _exe(win / "claude.exe", b"MZ planted")  # PATHEXT puts .EXE before .CMD: this one would win a plain lookup
    ident = P.reviewer_executable({"provider": "claude_cli"})
    assert ident["ambiguous"] and len(ident["ambiguous"]) == 2


def test_w2_unlaunchable_reviewer_cli_blocks_as_reviewer_exec(tmp_path, monkeypatch):
    """The driver stops with REVIEWER_EXEC (an owner matter) instead of running a launcher it cannot bind."""
    from scripts.dev_workflow.state_machine import WorkflowState as S
    from tests.dev_workflow.test_lifecycle import config, make_fixture
    repo, wt, base, remote = make_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt, milestone="W9-REAL-MILESTONE", independent=False, integration={"mode": "none"})
    cfg["reviewer"] = {"provider": "claude_cli"}
    bad = {"name": "claude", "path": "x", "unlaunchable": ["x/claude.cmd: launcher does not name one executable"]}
    monkeypatch.setattr(L, "reviewer_executable", lambda spec: bad)
    assert L.run(cfg) == S.BLOCKED
    st = json.loads((tmp_path / "state/state.json").read_text())
    assert st["blocker"]["kind"] == "REVIEWER_EXEC" and "cannot be bound" in st["blocker"]["reason"]
