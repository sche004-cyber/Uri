"""SCHED-TOKEN-ACL-1 (docs/scheduler/SCHED_TOKEN_ACL_1_PLAN.md), redesigned after lifecycle 1b: the state folder is
created locked to the current user, an existing one is only checked (never repaired), the token file is user-only,
and the service refuses to start (exit 4) when any of that does not hold. `secure-state` moves an old folder over."""
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
ROOT_USER = not WIN and os.geteuid() == 0


def _aces(path: Path) -> list:
    out = subprocess.run(["icacls", str(path)], capture_output=True, text=True).stdout
    lines = [ln.strip() for ln in out.splitlines() if ln.strip() and not ln.startswith("Successfully")]
    lines[0] = lines[0][len(str(path)):].strip()
    return lines


def _locked(path: Path):
    if WIN:
        sid = S._user_sid()
        owner, dacl, link = S.security_of(path)
        assert owner == sid and not link and dacl.startswith("P") and dacl.endswith(f"(A;OICI;FA;;;{sid})"), dacl
        assert len(_aces(path)) == 1, _aces(path)
    else:
        st = os.lstat(path)
        assert stat.S_IMODE(st.st_mode) == 0o700 and st.st_uid == os.geteuid()


def _run(state: Path, monkeypatch):
    built = []
    monkeypatch.setattr(S, "build", lambda a: built.append(a))
    return S.main(["run", "--state", str(state), "--mode", "fixture"]), built


# S1: a new state folder is locked to the user from the moment it exists

def test_new_state_folder_is_created_locked(tmp_path):
    state = tmp_path / "a" / "state"
    S.make_state_folder(state)
    _locked(state)
    S.make_state_folder(state)                                            # a locked folder passes the check again
    _locked(state)


def test_existing_open_folder_is_refused_not_repaired(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    if not WIN:
        os.chmod(state, 0o755)
    before = stat.S_IMODE(state.stat().st_mode)
    with pytest.raises(S.StateAclError, match="secure-state"):
        S.make_state_folder(state)
    assert stat.S_IMODE(state.stat().st_mode) == before                   # checked only, never changed


def test_state_path_that_is_a_link_is_refused(tmp_path):
    real = tmp_path / "real"
    S.make_state_folder(real)
    link = tmp_path / "state"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("cannot create a symlink here")
    with pytest.raises(S.StateAclError):
        S.make_state_folder(link)


# S2: nothing inside the folder may be a link or belong to someone else

def test_link_inside_is_refused(tmp_path):
    state = tmp_path / "state"
    S.make_state_folder(state)
    try:
        (state / "outputs").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("cannot create a symlink here")
    with pytest.raises(S.StateAclError):
        S.make_state_folder(state)


@pytest.mark.skipif(not ROOT_USER, reason="POSIX: needs root to plant a file owned by another uid")
def test_file_owned_by_another_user_is_refused(tmp_path):
    state = tmp_path / "state"
    S.make_state_folder(state)
    (state / "scheduler.db").write_bytes(b"x")
    os.chown(state / "scheduler.db", 65534, 65534)
    with pytest.raises(S.StateAclError, match="another user"):
        S.make_state_folder(state)


@pytest.mark.skipif(not WIN, reason="Windows-qualified: explicit entry of another principal")
def test_foreign_explicit_entry_inside_is_refused(tmp_path):
    state = tmp_path / "state"
    S.make_state_folder(state)
    db = state / "scheduler.db"
    db.write_bytes(b"x")
    subprocess.run(["icacls", str(db), "/grant", "*S-1-5-32-545:R"], check=True, capture_output=True)  # Users
    with pytest.raises(S.StateAclError):
        S.make_state_folder(state)


@pytest.mark.skipif(not WIN, reason="Windows-qualified: explicit entry of another principal")
def test_foreign_explicit_entry_on_folder_is_refused(tmp_path):
    state = tmp_path / "state"
    S.make_state_folder(state)
    subprocess.run(["icacls", str(state), "/grant", "*S-1-5-32-545:(OI)(CI)R"], check=True, capture_output=True)
    with pytest.raises(S.StateAclError):
        S.make_state_folder(state)


def test_secure_state_moves_an_old_folder_into_a_locked_one(tmp_path):
    state = tmp_path / "state"
    (state / "outputs").mkdir(parents=True)
    (state / "scheduler.db").write_bytes(b"db")
    (state / "outputs" / "a.txt").write_text("a")
    if not WIN:
        os.chmod(state, 0o755)
    old = S.secure_state(state)
    _locked(state)
    assert (state / "scheduler.db").read_bytes() == b"db" and (state / "outputs" / "a.txt").read_text() == "a"
    assert (old / "scheduler.db").read_bytes() == b"db"                   # the old folder is kept, not deleted
    S.make_state_folder(state)


def test_secure_state_with_a_link_inside_changes_nothing(tmp_path):
    state = tmp_path / "state"
    state.mkdir()
    try:
        (state / "outputs").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("cannot create a symlink here")
    with pytest.raises(S.StateAclError, match="links"):
        S.secure_state(state)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state"]


def test_secure_state_refuses_while_running(tmp_path, monkeypatch):
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setattr(S, "_running_instance", lambda p: True)
    with pytest.raises(S.StateAclError, match="running"):
        S.secure_state(state)
    assert state.is_dir() and len(list(tmp_path.iterdir())) == 1


def test_secure_state_command_then_run_check_passes(tmp_path, capsys):
    state = tmp_path / "state"
    state.mkdir()
    if not WIN:
        os.chmod(state, 0o777)
    assert S.main(["secure-state", "--state", str(state)]) == 0
    assert '"secured"' in capsys.readouterr().out
    _locked(state)


# S3: a new token file every launch, user-only before the token is written

def test_token_file_is_new_each_launch_and_user_only(tmp_path):
    state = tmp_path / "state"
    S.make_state_folder(state)
    tok = state / "api-token"
    S.write_token_file(tok, "first")
    S.write_token_file(tok, "second")
    assert tok.read_text(encoding="utf-8") == "second"
    if not WIN:
        assert stat.S_IMODE(tok.stat().st_mode) == 0o600
        return
    aces = _aces(tok)
    assert len(aces) == 1 and aces[0].endswith(":(F)") and "(I)" not in aces[0], aces


@pytest.mark.skipif(WIN, reason="POSIX ordering probe through os.chmod")
def test_token_is_restricted_before_it_is_written(tmp_path, monkeypatch):    # R3-02 (1b)
    tok = tmp_path / "api-token"
    seen = []
    real = os.chmod

    def chmod(path, mode):
        seen.append(Path(path).read_bytes())
        real(path, mode)
    monkeypatch.setattr(S.os, "chmod", chmod)
    S.write_token_file(tok, "secret")
    assert seen == [b""] and tok.read_text() == "secret"


# S4: any failure refuses to start with exit 4, and no token is left behind

def _denied(*a, **k):
    raise PermissionError(1, "Operation not permitted")


def test_service_refuses_to_start_on_an_open_folder(tmp_path, monkeypatch, capsys):
    state = tmp_path / "state"
    state.mkdir()
    if not WIN:
        os.chmod(state, 0o755)
    rc, built = _run(state, monkeypatch)
    assert rc == 4 and "STATE_ACL_FAILED" in capsys.readouterr().out
    assert built == []                                                    # nothing was opened
    assert not (state / "api-token").exists()


def test_service_refuses_to_start_when_the_folder_cannot_be_created(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(S.os, "mkdir", _denied)
    monkeypatch.setattr(S, "_create_locked_folder", _denied)
    rc, built = _run(tmp_path / "state", monkeypatch)
    assert rc == 4 and "STATE_ACL_FAILED" in capsys.readouterr().out and built == []
    assert not (tmp_path / "state").exists()


@pytest.mark.skipif(WIN, reason="POSIX branch: os.chmod")
def test_token_chmod_failure_leaves_no_token(tmp_path, monkeypatch):
    monkeypatch.setattr(S.os, "chmod", _denied)
    tok = tmp_path / "api-token"
    with pytest.raises(S.StateAclError):
        S.write_token_file(tok, "secret")
    assert not tok.exists()


def test_token_write_oserror_leaves_no_token(tmp_path, monkeypatch):
    tok = tmp_path / "api-token"
    real = Path.write_text

    def denied(self, *a, **k):
        real(self, "partial")
        raise PermissionError(13, "Permission denied")
    monkeypatch.setattr(Path, "write_text", denied)
    with pytest.raises(S.StateAclError):
        S.write_token_file(tok, "secret")
    assert not tok.exists()


def test_service_exits_4_when_the_token_step_fails(tmp_path, monkeypatch, capsys):
    closed = []

    class _Sched:
        startup = {}

        def start(self):
            return self

        def close(self):
            closed.append(True)
    monkeypatch.setattr(S, "build", lambda a: _Sched())
    monkeypatch.setattr(S, "write_token_file", lambda p, t: (_ for _ in ()).throw(S.StateAclError("denied")))
    rc = S.main(["run", "--state", str(tmp_path / "state"), "--mode", "fixture"])
    assert rc == 4 and "STATE_ACL_FAILED" in capsys.readouterr().out and closed == [True]
    assert not (tmp_path / "state" / "api-token").exists()


@pytest.mark.skipif(not WIN, reason="Windows-qualified: user SID lookup")
def test_missing_user_sid_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(S, "_user_sid", lambda: (_ for _ in ()).throw(S.StateAclError("no current user SID")))
    with pytest.raises(S.StateAclError):
        S.make_state_folder(tmp_path / "state")
