"""Phase 2C hardening: an optional SHA-256 pin on the executable file. D-B3 compares resolved paths (the binary the
Phase 1 registry qualified); the pin additionally refuses a replaced file at the same path. Found while reviewing the
real path: `shutil.which("codex")` resolves to the npm shim `codex.CMD`, so path identity alone is weak."""
import hashlib
import sys
from dataclasses import replace

from phase2b.conftest import CLAUDE, fake_binding, fake_registry
from uri_supervisor_bridge.bridge import NOT_STARTED, SupervisorBridge


def _bridge(tmp_path, binding):
    return SupervisorBridge(tmp_path / "client", registry=fake_registry("claude_code"), executors={"claude_code": binding},
                            timeout_s=15, inactivity_s=4)


def test_matching_pin_runs(tmp_path, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    pin = hashlib.sha256(open(sys.executable, "rb").read()).hexdigest()
    b = _bridge(tmp_path, replace(fake_binding("claude_code"), executable_sha256=pin))
    try:
        signed, request, now = authority.issue()
        assert b.execute(authority.verify(signed, request, CLAUDE, now=now))[0] == "verified"
    finally:
        b.close()


def test_wrong_pin_refuses_before_any_task_exists(tmp_path, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    b = _bridge(tmp_path, replace(fake_binding("claude_code"), executable_sha256="0" * 64))
    try:
        signed, request, now = authority.issue()
        out = b.execute(authority.verify(signed, request, CLAUDE, now=now))
        assert out == ("failed", [], NOT_STARTED + "EXECUTOR_BINARY_HASH_MISMATCH")
        assert b.L.q1("SELECT COUNT(*) FROM task")[0] == 0
    finally:
        b.close()


def test_no_pin_keeps_phase2b_behaviour(tmp_path, authority, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    b = _bridge(tmp_path, fake_binding("claude_code"))
    try:
        signed, request, now = authority.issue()
        assert b.execute(authority.verify(signed, request, CLAUDE, now=now))[0] == "verified"
    finally:
        b.close()
