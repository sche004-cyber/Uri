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


def test_folder_steps_restrict_folder_before_resetting_children(tmp_path):   # R2-01 / R1-01, on every platform
    (tmp_path / "scheduler.db").write_bytes(b"x")
    (tmp_path / "api-token").write_text("old")
    steps = S.icacls_steps(tmp_path, "me", folder=True)
    assert steps == [["icacls", str(tmp_path), "/inheritance:r", "/grant:r", "me:(OI)(CI)F"],
                     ["icacls", str(tmp_path / "api-token"), "/reset", "/T", "/Q", "/L"],
                     ["icacls", str(tmp_path / "scheduler.db"), "/reset", "/T", "/Q", "/L"]]
    assert all("/C" not in st for st in steps)                            # an un-resettable file fails the step
    assert all(st[1] != str(tmp_path) for st in steps if "/reset" in st)  # the folder itself is never reset
    assert S.icacls_steps(tmp_path, "me") == [["icacls", str(tmp_path), "/inheritance:r", "/grant:r", "me:F"]]


def test_empty_folder_has_only_the_restrict_step(tmp_path):              # R1-01: no reset step, so nothing to fail
    assert S.icacls_steps(tmp_path, "me", folder=True) == [
        ["icacls", str(tmp_path), "/inheritance:r", "/grant:r", "me:(OI)(CI)F"]]


@pytest.mark.skipif(not WIN, reason="Windows-qualified: the icacls branch")
def test_folder_acl_failure_fails_closed(tmp_path, monkeypatch):           # R1-02: a failed step re-applies the grant
    calls = []

    def run(cmd, **k):
        calls.append(cmd)
        return _Fail()
    monkeypatch.setattr(S.subprocess, "run", run)
    with pytest.raises(S.StateAclError):
        S.restrict_to_user(tmp_path, folder=True)
    assert len(calls) == 2 and all("/grant:r" in c and "/reset" not in c for c in calls)   # grant, then re-grant


def _simulated_windows(monkeypatch, fail_reset):
    """Drive the icacls branch on any platform: a fake icacls that records calls and fails `/reset` on demand."""
    monkeypatch.setattr(S, "_WINDOWS", True, raising=False)
    monkeypatch.setenv("USERNAME", "me")
    calls = []

    class _R:
        stdout = stderr = ""

        def __init__(self, rc):
            self.returncode = rc

    def run(cmd, **k):
        calls.append(list(cmd))
        return _R(5 if (fail_reset and "/reset" in cmd) else 0)
    monkeypatch.setattr(S.subprocess, "run", run)
    monkeypatch.setattr(S, "drop_foreign_entries", lambda p: calls.append(["drop", str(p)]), raising=False)
    return calls


def test_folder_is_never_reset_to_its_inherited_acl(tmp_path, monkeypatch):   # R1-01, on every platform
    state = tmp_path / "state"
    state.mkdir()
    (state / "api-token").write_text("live")
    calls = _simulated_windows(monkeypatch, fail_reset=False)
    S.restrict_to_user(state, folder=True)
    grant = ["icacls", str(state), "/inheritance:r", "/grant:r", "me:(OI)(CI)F"]
    assert calls[:2] == [grant, ["drop", str(state)]]                     # the folder is closed first, then cleared
    assert all(c[1] != str(state) for c in calls if "/reset" in c)        # and never reset afterwards
    assert ["icacls", str(state / "api-token"), "/reset", "/T", "/Q", "/L"] in calls


@pytest.mark.parametrize("nested", [False, True])
def test_planted_link_is_never_reset_and_fails_closed(tmp_path, monkeypatch, nested):   # R2-05, on every platform
    outside = tmp_path / "protected"
    outside.mkdir()
    (outside / "secret").write_text("x")
    state = tmp_path / "state"
    state.mkdir()
    (state / "scheduler.db").write_bytes(b"x")
    parent = state / "sub" if nested else state
    parent.mkdir(exist_ok=True)
    link = parent / "x"
    if WIN:
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    calls = _simulated_windows(monkeypatch, fail_reset=False)
    with pytest.raises(S.StateAclError):
        S.restrict_to_user(state, folder=True)
    grant = ["icacls", str(state), "/inheritance:r", "/grant:r", "me:(OI)(CI)F"]
    assert not [c for c in calls if "/reset" in c]                        # nothing is reset, the link least of all
    assert calls[-1] == grant                                             # the folder is left closed
    assert (outside / "secret").read_text() == "x"


@pytest.mark.skipif(not WIN, reason="Windows-qualified: a real junction and the real icacls")
def test_junction_target_acl_is_untouched(tmp_path):                     # R2-05 with real icacls
    outside = tmp_path / "protected"
    outside.mkdir()
    subprocess.run(["icacls", str(outside), "/inheritance:r", "/grant:r", "*S-1-5-32-544:(OI)(CI)F",
                    f"{os.environ['USERNAME']}:(OI)(CI)F"], check=True, capture_output=True)
    before = _aces(outside)
    state = tmp_path / "state"
    state.mkdir()
    subprocess.run(["cmd", "/c", "mklink", "/J", str(state / "x"), str(outside)], check=True, capture_output=True)
    with pytest.raises(S.StateAclError):
        S.restrict_to_user(state, folder=True)
    assert _aces(outside) == before                                       # still protected, not reset to inherited
    aces = _aces(state)
    assert len(aces) == 1 and aces[0].endswith(":(OI)(CI)(F)"), aces      # the state folder is still closed


def test_reset_steps_never_follow_links(tmp_path):                       # R2-05: /L on every child reset
    (tmp_path / "x").mkdir()
    assert all("/L" in st for st in S.icacls_steps(tmp_path, "me", folder=True) if "/reset" in st)


def test_child_reset_failure_keeps_folder_closed_and_removes_token(tmp_path, monkeypatch, capsys):   # R1-02
    state = tmp_path / "state"
    state.mkdir()
    (state / "api-token").write_text("old")
    calls = _simulated_windows(monkeypatch, fail_reset=True)
    monkeypatch.setattr(S, "build", lambda a: pytest.fail("the ACL failure must stop main before build"))
    rc = S.main(["run", "--state", str(state), "--mode", "fixture"])
    assert rc == 4
    assert "STATE_ACL_FAILED" in capsys.readouterr().out
    grant = ["icacls", str(state), "/inheritance:r", "/grant:r", "me:(OI)(CI)F"]
    resets = [i for i, c in enumerate(calls) if "/reset" in c]
    assert grant in calls and resets and calls.index(grant) < resets[0]   # folder closed before any reset
    assert calls[-1] == grant                                             # and re-applied after the failure
    assert not (state / "api-token").exists()                             # no old token left on disk


@pytest.mark.skipif(WIN, reason="POSIX flock probe; the msvcrt probe is Windows-qualified")
def test_live_instance_folder_acl_is_not_touched(tmp_path, monkeypatch, capsys):   # R1-01: lock before the ACL
    import fcntl
    state = tmp_path / "state"
    state.mkdir()
    (state / "api-token").write_text("live")
    fh = open(state / "scheduler.lock", "a+b")
    fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)               # a running instance holds the lock
    touched = []
    monkeypatch.setattr(S, "restrict_to_user", lambda p, **k: touched.append(p))
    monkeypatch.setattr(S, "build", lambda a: touched.append("build"))
    try:
        rc = S.main(["run", "--state", str(state), "--mode", "fixture"])
    finally:
        fh.close()
    assert rc == 3
    assert "SCHEDULER_ALREADY_RUNNING" in capsys.readouterr().out
    assert touched == []
    assert (state / "api-token").read_text() == "live"


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
