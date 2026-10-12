"""C4 harness adapter tests: offline fake harness + honest native discovery. No login, no provider call."""
import json
import os
from pathlib import Path
import sys
import threading
import uuid

import pytest

from uri_core.client_runtime import harness as h
from uri_harness_adapters import (claude_invocation, codex_invocation, default_registry, parse_claude,
                                  parse_codex)
from uri_core.client_runtime.process_tree import process_alive

ROOT = Path(__file__).resolve().parent
FAKE = [sys.executable, str(ROOT / "fixtures/c4_harness/fake_harness.py")]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows job containment")


@pytest.fixture
def ws():
    d = ROOT / "work/c1" / ("c4_harness_" + uuid.uuid4().hex)
    d.mkdir(parents=True)
    return d


def capsule(ws, **kw):
    return h.Capsule(run_id=uuid.uuid4().hex, workspace=str(ws), instructions=b"do the task", **kw)


def run(ws, scenario, monkeypatch, **kw):
    monkeypatch.setenv("URI_FAKE_SCENARIO", scenario)
    for k, v in kw.items(): monkeypatch.setenv(k, str(v))
    argv, env, prompt = claude_invocation(FAKE, capsule(ws))
    proc = h.supervise(argv, cwd=ws, env=env, stdin_bytes=prompt, timeout_s=20, inactivity_s=20, log_path=ws / "log.jsonl")
    return proc, parse_claude(proc)


def test_claude_argv_is_scoped_and_never_bypasses(ws):
    argv, env, _ = claude_invocation(FAKE, capsule(ws))
    assert not h.FORBIDDEN_FLAGS.intersection(argv)
    assert "Bash" in argv[argv.index("--disallowedTools") + 1:] and "dontAsk" in argv
    assert all("//" in a for a in argv if a.startswith("Write("))
    assert "--strict-mcp-config" in argv and "--dangerously-skip-permissions" not in argv
    with pytest.raises(h.HarnessError):
        h._check(["x", "--yolo"])


def test_env_never_forwards_provider_keys(monkeypatch):
    env = h.harness_env(("CLAUDE_CODE_OAUTH_TOKEN",), {"PATH": "p", "ANTHROPIC_API_KEY": "k", "OPENAI_API_KEY": "k",
        "CLAUDE_CODE_OAUTH_TOKEN": "t", "GITHUB_TOKEN": "g", "URI_FAKE_SCENARIO": "s"})
    assert env == {"PATH": "p", "CLAUDE_CODE_OAUTH_TOKEN": "t", "URI_FAKE_SCENARIO": "s"}
    assert h.harness_env(("ANTHROPIC_API_KEY",), {"ANTHROPIC_API_KEY": "k"}) == {}


def test_native_discovery_is_honest_and_not_usable():
    rows = {r["harness_id"]: r for r in default_registry().discover()}
    for hid in ("claude_code", "codex_cli"):
        assert rows[hid]["usable"] is False and rows[hid]["qualification"] == "NATIVE_UNQUALIFIED"
        if rows[hid]["installed"]:
            assert rows[hid]["auth_state"] == "AUTH_UNVERIFIED" and rows[hid]["required_user_action"]
    assert rows["antigravity"]["usable"] is False and rows["antigravity"]["qualification"] == "REFUSED"
    with pytest.raises(h.HarnessError, match="HARNESS_NOT_USABLE"):
        default_registry().invoke("claude_code", capsule(Path("C:/")))


def test_authenticated_but_unqualified_still_unusable_and_fixture_qualification_needs_evidence():
    reg = default_registry({"claude_code": FAKE}, auth_probe=lambda hid: True)
    assert reg.discover()[0]["auth_state"] == "AUTHENTICATED" and reg.discover()[0]["usable"] is False
    with pytest.raises(h.HarnessError):
        reg.qualify("claude_code", "FIXTURE_ONLY", "nothex")
    reg.qualify("claude_code", "FIXTURE_ONLY", "a" * 64)
    row = reg.discover()[0]
    assert row["usable"] is True and row["qualification"] == "FIXTURE_ONLY"
    assert reg.invoke("claude_code", capsule(ROOT / "work"))[0][0]


def test_honest_run_produces_claim_and_artifact(ws, monkeypatch):
    proc, claim = run(ws, "honest", monkeypatch)
    assert claim["claimed_outcome"] == "completed_claimed" and claim["contained"] and (ws / "out.txt").exists()


def test_false_claim_is_only_a_claim(ws, monkeypatch):
    proc, claim = run(ws, "false_claim", monkeypatch)
    assert claim["claimed_outcome"] == "completed_claimed" and not (ws / "out.txt").exists()  # URI verifier must catch


def test_quota_exhaustion_is_classified_not_failed(ws, monkeypatch):
    _, claim = run(ws, "quota", monkeypatch)
    assert claim["claimed_outcome"] == "quota_exhausted" and claim["error_family"] == "QUOTA"


def test_timeout_kills_descendants(ws, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "hang_with_child")
    pid_file = ws / "child.pid"; monkeypatch.setenv("URI_FAKE_CHILD_PID", str(pid_file))
    argv, env, prompt = claude_invocation(FAKE, capsule(ws))
    proc = h.supervise(argv, cwd=ws, env=env, stdin_bytes=prompt, timeout_s=3, inactivity_s=3, log_path=ws / "log.jsonl")
    assert proc.timed_out and proc.contained
    claim = parse_claude(proc)
    assert claim["claimed_outcome"] == "outcome_unknown"
    assert pid_file.exists() and not process_alive(int(pid_file.read_text()))


def test_cancel_event(ws, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "hang_with_child")
    monkeypatch.setenv("URI_FAKE_CHILD_PID", str(ws / "c.pid"))
    ev = threading.Event(); threading.Timer(1.5, ev.set).start()
    argv, env, prompt = claude_invocation(FAKE, capsule(ws))
    proc = h.supervise(argv, cwd=ws, env=env, stdin_bytes=prompt, timeout_s=30, inactivity_s=30, log_path=ws / "l", cancel=ev)
    assert proc.cancelled and parse_claude(proc)["claimed_outcome"] == "outcome_unknown"


def test_codex_argv_sandboxed(ws):
    argv, env, _ = codex_invocation(["python"], capsule(ws))
    assert "workspace-write" in argv and 'approval_policy="never"' in argv and "danger-full-access" not in argv


def test_codex_shaped_success_and_quota_are_parsed(ws, monkeypatch):
    """Regression: a completed Codex turn must be a claim, not 'no result'."""
    for scenario, expect in (("honest", "completed_claimed"), ("quota", "quota_exhausted")):
        monkeypatch.setenv("URI_FAKE_SCENARIO", scenario)
        argv, env, prompt = codex_invocation(FAKE, capsule(ws))
        proc = h.supervise(argv, cwd=ws, env=env, stdin_bytes=prompt, timeout_s=20, inactivity_s=20, log_path=ws / (scenario + ".jsonl"))
        assert parse_codex(proc)["claimed_outcome"] == expect
