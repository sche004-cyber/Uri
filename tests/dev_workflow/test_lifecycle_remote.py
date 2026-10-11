"""DEV-LIFECYCLE-2 (TEST ONLY): F1, a Windows crash in process cleanup, and F3, the canonical remote found by URL.

Kept apart from test_lifecycle_platform.py so that each test here fails on the baseline for its own reason (the
os.killpg AttributeError, the remote chosen by name), not because the new containment module is missing.
"""
import json
import os
import signal
import subprocess
from pathlib import Path

import pytest

from scripts.dev_workflow import lifecycle as L
from scripts.dev_workflow import lifecycle_providers as LP

try:
    from scripts.dev_workflow import containment as C
except ImportError:          # the baseline has no containment module
    C = None


# ---------------------------------------------------------------- F1: no POSIX-only call where it does not exist

def _no_posix_kill(monkeypatch):
    monkeypatch.delattr(os, "killpg", raising=False)
    monkeypatch.delattr(signal, "SIGKILL", raising=False)


@pytest.mark.parametrize("windows", [False, True])
def test_f1_killpg_without_os_killpg_never_raises(monkeypatch, windows):
    _no_posix_kill(monkeypatch)
    calls = []
    if windows:
        if C is None:
            pytest.fail("no containment module: nothing replaces os.killpg on Windows")
        monkeypatch.setattr(C, "WINDOWS", True)
        monkeypatch.setattr(C.subprocess, "run", lambda argv, **kw: calls.append(argv))
    LP._killpg(999999)          # an exited / unknown pid
    L._killpg(999999)
    if windows:
        assert calls and calls[0][:4] == ["taskkill", "/F", "/T", "/PID"]


def test_f1_no_posix_only_call_on_the_worker_and_gate_paths():
    """Every os.killpg / os.getsid / signal.SIGKILL / start_new_session / '/proc' use is behind a platform check."""
    src = {p: Path(p).read_text(encoding="utf-8") for p in ("scripts/dev_workflow/lifecycle.py",
                                                           "scripts/dev_workflow/lifecycle_providers.py")}
    assert "os.killpg(" not in src["scripts/dev_workflow/lifecycle.py"]
    assert "start_new_session" not in src["scripts/dev_workflow/lifecycle.py"]
    prov = src["scripts/dev_workflow/lifecycle_providers.py"]
    assert "start_new_session" not in prov and "os.killpg(" not in prov
    # The remaining POSIX calls (getsid, /proc, SIGKILL in the orphan sweep) run only after enable_containment(),
    # which is True only on Linux, and sweep_orphans() returns before them on Windows.
    sweep = prov[prov.index("def sweep_orphans"):]
    assert sweep.index("containment.WINDOWS") < sweep.index("enable_containment()") < sweep.index("signal.SIGKILL")


# ---------------------------------------------------------------- F3: canonical remote by URL

def g(cwd, *a):
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "clone"
    r.mkdir()
    g(r, "init", "-q")
    return r


def _cfg(repo, url):
    return {"repo": str(repo), "canonical_url": url}


def test_f3_resolves_the_one_remote_with_the_canonical_url(repo):
    g(repo, "remote", "add", "origin", "https://github.com/sche004-cyber/uri-agent.git")
    g(repo, "remote", "add", "uri-repo", "git@github.com:sche004-cyber/Uri.git")
    assert L.canonical_remote(_cfg(repo, "https://github.com/sche004-cyber/Uri")) == ("uri-repo", None)


def test_f3_no_matching_remote_is_refused(repo):
    g(repo, "remote", "add", "origin", "https://github.com/sche004-cyber/uri-agent.git")
    name, why = L.canonical_remote(_cfg(repo, "https://github.com/sche004-cyber/Uri"))
    assert name is None and "no remote" in why
    assert L.canonical_remote({"repo": str(repo)})[0] is None


def test_f3_ambiguous_remote_is_refused(repo):
    g(repo, "remote", "add", "a", "https://github.com/sche004-cyber/Uri")
    g(repo, "remote", "add", "b", "https://GitHub.com/sche004-cyber/uri.git/")
    name, why = L.canonical_remote(_cfg(repo, "https://github.com/sche004-cyber/Uri"))
    assert name is None and "several" in why


def test_f3_insteadof_is_applied_before_comparing(repo):
    g(repo, "config", "url.https://github.com/elsewhere/Uri.insteadOf", "https://github.com/sche004-cyber/Uri")
    g(repo, "remote", "add", "uri-repo", "https://github.com/sche004-cyber/Uri")
    # the remote's NAME and configured URL look canonical, but git would fetch from elsewhere
    assert L.canonical_remote(_cfg(repo, "https://github.com/sche004-cyber/Uri"))[0] is None


def _lifecycle_fixture(tmp_path):
    from tests.dev_workflow.test_lifecycle import config, make_fixture
    return config, make_fixture(tmp_path, defect=False)


def test_f3_empty_baseline_lookup_is_blocked(tmp_path, capsys):
    config, (repo, wt, base, remote) = _lifecycle_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt)
    raw = json.loads(Path(cfg["_config_path"]).read_text())
    raw["baseline"] = {"remote_branch": "no-such-branch"}
    Path(cfg["_config_path"]).write_text(json.dumps(raw))
    assert L.main(["run", cfg["_config_path"]]) == L.EXIT[L.S.BLOCKED]
    out = json.loads(capsys.readouterr().out)
    assert out["stage"] == "BLOCKED" and out["blocker"]["kind"] == "BASELINE"
    assert not (Path(cfg["state_dir"]) / "events.jsonl").exists()      # never planned against "no baseline"


def test_f3_baseline_from_the_canonical_remote_by_url(tmp_path):
    config, (repo, wt, base, remote) = _lifecycle_fixture(tmp_path)
    g(repo, "remote", "rename", "origin", "uri-repo")
    g(repo, "remote", "add", "origin", str(tmp_path))                  # 'origin' now points elsewhere
    cfg = config(tmp_path, repo, wt, integration={"mode": "fast-forward", "target_ref": "canon", "authorized": True})
    raw = json.loads(Path(cfg["_config_path"]).read_text())
    raw["baseline"] = {"remote_branch": "canon", "expect": base}
    Path(cfg["_config_path"]).write_text(json.dumps(raw))
    cfg = L.load_config(cfg["_config_path"])
    assert L.run(cfg) == L.S.COMPLETE
    s = L.status(cfg)
    assert s["baseline"] == base and s["integration"]["remote"] == "uri-repo"
    assert g(remote, "rev-parse", "refs/heads/canon") == s["candidate"]


def test_f3_integration_remote_that_is_not_canonical_is_blocked(tmp_path):
    config, (repo, wt, base, remote) = _lifecycle_fixture(tmp_path)
    g(repo, "remote", "add", "other", str(tmp_path / "elsewhere.git"))
    cfg = config(tmp_path, repo, wt, integration={"mode": "fast-forward", "remote": "other", "target_ref": "canon",
                                                  "authorized": True})
    assert L.run(cfg) == L.S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "REMOTE" and g(remote, "rev-parse", "refs/heads/canon") == base


def test_f3_empty_integration_target_is_blocked(tmp_path):
    config, (repo, wt, base, remote) = _lifecycle_fixture(tmp_path)
    cfg = config(tmp_path, repo, wt, integration={"mode": "fast-forward", "target_ref": "no-such-target",
                                                  "authorized": True})
    assert L.run(cfg) == L.S.BLOCKED
    s = L.status(cfg)
    assert s["blocker"]["kind"] == "REMOTE" and "returned nothing" in s["blocker"]["reason"]
