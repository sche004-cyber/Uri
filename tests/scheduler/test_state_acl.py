"""SCHED-TOKEN-ACL-1 (docs/scheduler/SCHED_TOKEN_ACL_1_PLAN.md): the scheduler's state folder and token file are
restricted to the current Windows user, and the service refuses to start when that fails."""
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from uri_scheduler import service as S  # noqa: E402

WIN = os.name == "nt"


def _aces(path: Path) -> list:
    out = subprocess.run(["icacls", str(path)], capture_output=True, text=True).stdout
    lines = [ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith("Successfully")]
    lines[0] = lines[0][len(str(path)):].strip()
    return lines


def _me() -> set:
    u = os.environ.get("USERNAME", "")
    return {os.environ.get("USERDOMAIN", "") + "\\" + u, os.environ.get("COMPUTERNAME", "") + "\\" + u}


def test_state_folder_gets_one_inheritable_user_entry(tmp_path):        # S1
    state = tmp_path / "state"
    state.mkdir()
    S.restrict_to_user(state, folder=True)
    if not WIN:
        assert stat.S_IMODE(state.stat().st_mode) == 0o700
        return
    aces = _aces(state)
    assert len(aces) == 1, aces
    assert aces[0].endswith(":(OI)(CI)(F)") and aces[0][:-len(":(OI)(CI)(F)")] in _me(), aces


def test_files_already_inside_are_reinherited(tmp_path):                 # S2
    state = tmp_path / "state"
    state.mkdir()
    old_db = state / "scheduler.db"
    old_db.write_bytes(b"x")
    old_token = state / "api-token"
    old_token.write_text("old")
    S.restrict_to_user(state, folder=True)
    if not WIN:                                                           # POSIX: the 0700 folder is what guards them (R2-02)
        assert stat.S_IMODE(state.stat().st_mode) == 0o700
        assert old_db.read_bytes() == b"x" and old_token.read_text() == "old"
        return
    for f in (old_db, old_token):
        aces = _aces(f)
        assert len(aces) == 1 and aces[0].endswith(":(I)(F)"), (f.name, aces)


def test_folder_steps_reset_explicit_entries_before_restricting(tmp_path):   # R2-01, on every platform
    steps = S.icacls_steps(tmp_path, "me", folder=True)
    assert steps == [["icacls", str(tmp_path), "/reset", "/T", "/Q"],
                     ["icacls", str(tmp_path), "/inheritance:r", "/grant:r", "me:(OI)(CI)F"]]
    assert "/C" not in steps[0]                                           # an un-resettable file fails the step
    assert S.icacls_steps(tmp_path, "me") == [["icacls", str(tmp_path), "/inheritance:r", "/grant:r", "me:F"]]


@pytest.mark.skipif(not WIN, reason="Windows-qualified: the icacls branch")
def test_folder_reset_failure_fails_closed(tmp_path, monkeypatch):         # R2-01: a failed /reset stops before the grant
    calls = []

    def run(cmd, **k):
        calls.append(cmd)
        return _Fail()
    monkeypatch.setattr(S.subprocess, "run", run)
    with pytest.raises(S.StateAclError):
        S.restrict_to_user(tmp_path, folder=True)
    assert len(calls) == 1 and "/reset" in calls[0]


@pytest.mark.skipif(not WIN, reason="Windows-qualified: explicit ACEs of other principals")
def test_foreign_explicit_entries_are_removed(tmp_path):                  # R2-01: S1 and S2 with a hostile starting ACL
    state = tmp_path / "state"
    state.mkdir()
    inside = state / "scheduler.db"
    inside.write_bytes(b"x")
    users = "*S-1-5-32-545"                                               # BUILTIN\Users
    for target, grant in ((state, users + ":(OI)(CI)R"), (inside, users + ":R")):
        subprocess.run(["icacls", str(target), "/grant", grant], check=True, capture_output=True)
    subprocess.run(["icacls", str(inside), "/inheritance:d"], check=True, capture_output=True)   # protected DACL
    S.restrict_to_user(state, folder=True)
    aces = _aces(state)
    assert len(aces) == 1 and aces[0].endswith(":(OI)(CI)(F)") and aces[0][:-len(":(OI)(CI)(F)")] in _me(), aces
    aces = _aces(inside)
    assert len(aces) == 1 and aces[0].endswith(":(I)(F)") and aces[0][:-len(":(I)(F)")] in _me(), aces


def test_token_file_is_new_each_launch_and_user_only(tmp_path):          # S3
    state = tmp_path / "state"
    state.mkdir()
    S.restrict_to_user(state, folder=True)
    tok = state / "api-token"
    S.write_token_file(tok, "first")
    S.write_token_file(tok, "second")
    assert tok.read_text(encoding="utf-8") == "second"
    if not WIN:
        assert stat.S_IMODE(tok.stat().st_mode) == 0o600
        return
    aces = _aces(tok)
    assert len(aces) == 1 and aces[0].endswith(":(F)") and "(I)" not in aces[0], aces
    assert aces[0][:-len(":(F)")] in _me(), aces


def _chmod_denied(*a, **k):
    raise PermissionError(1, "Operation not permitted")


class _Fail:
    returncode = 1
    stdout = stderr = ""


def test_token_acl_failure_leaves_no_token(tmp_path, monkeypatch):       # S4 (token step)
    if not WIN:
        monkeypatch.setattr(S.os, "chmod", _chmod_denied)                 # the real OS failure, not a StateAclError
    else:
        monkeypatch.setattr(S.subprocess, "run", lambda *a, **k: _Fail())
    tok = tmp_path / "api-token"
    with pytest.raises(S.StateAclError):
        S.write_token_file(tok, "secret")
    assert not tok.exists()


def test_service_refuses_to_start_when_folder_acl_fails(tmp_path, monkeypatch, capsys):   # S4 (folder step)
    if not WIN:
        monkeypatch.setattr(S.os, "chmod", _chmod_denied)                 # through the real restrict_to_user
    else:
        monkeypatch.setattr(S.subprocess, "run", lambda *a, **k: _Fail())
    built = []
    monkeypatch.setattr(S, "build", lambda a: built.append(a))
    rc = S.main(["run", "--state", str(tmp_path / "state"), "--mode", "fixture"])
    assert rc == 4
    assert "STATE_ACL_FAILED" in capsys.readouterr().out
    assert built == []                                                    # nothing was opened
    assert not (tmp_path / "state" / "api-token").exists()


def test_posix_chmod_oserror_becomes_state_acl_error(tmp_path, monkeypatch):   # R1-01
    if WIN:
        pytest.skip("POSIX branch: os.chmod")
    monkeypatch.setattr(S.os, "chmod", _chmod_denied)
    with pytest.raises(S.StateAclError):
        S.restrict_to_user(tmp_path, folder=True)


def test_token_write_oserror_becomes_state_acl_error(tmp_path, monkeypatch):   # R1-01 (unlink/write_bytes)
    tok = tmp_path / "api-token"
    real = Path.write_bytes

    def denied(self, data):
        real(self, data)                                                  # a file appears, then the OS refuses
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(Path, "write_bytes", denied)
    with pytest.raises(S.StateAclError):
        S.write_token_file(tok, "secret")
    assert not tok.exists()


def test_service_exits_4_when_token_acl_raises_oserror(tmp_path, monkeypatch, capsys):   # R1-01 (token step in main)
    closed = []

    class _Sched:
        startup = {}

        def start(self):
            return self

        def close(self):
            closed.append(True)
    monkeypatch.setattr(S, "build", lambda a: _Sched())
    real_restrict = S.restrict_to_user

    def restrict(path, *, folder=False):
        if folder:
            return real_restrict(path, folder=True)
        raise PermissionError(1, "Operation not permitted")          # an unwrapped OS error on the token file
    monkeypatch.setattr(S, "restrict_to_user", restrict)
    rc = S.main(["run", "--state", str(tmp_path / "state"), "--mode", "fixture"])
    assert rc == 4
    assert "STATE_ACL_FAILED" in capsys.readouterr().out
    assert closed == [True]
    assert not (tmp_path / "state" / "api-token").exists()


def test_missing_user_name_fails_closed(tmp_path, monkeypatch):
    if not WIN:
        pytest.skip("Windows-qualified only: USERNAME drives the Windows ACL entry")
    monkeypatch.delenv("USERNAME", raising=False)
    with pytest.raises(S.StateAclError):
        S.restrict_to_user(tmp_path, folder=True)
