"""Phase 2 operational qualification, EXE-1: native launch chains, the worker-only Codex home/sandbox invariant, and the
OQ-1 usability gate. Synthetic layouts unless a test says REAL."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from phase2d.conftest import ROOT, signed_record, trust_for
from uri_supervisor_bridge import qualification as q
from uri_supervisor_bridge.qualification import QualificationError

TRIPLE = q.CODEX_NATIVE_TRIPLE


def npm_layout(tmp_path, codex=True, claude=True, layout=None):
    """A synthetic npm global directory with the two launchers and their native payloads (copies of a real exe)."""
    npm = tmp_path / "npm"
    npm.mkdir()
    if codex:
        (npm / "codex.cmd").write_text("@ECHO off\r\n", encoding="utf-8")
        vendor = npm / "node_modules/@openai/codex/node_modules/@openai/codex-win32-x64/vendor" / TRIPLE
        for rel in ("bin/codex.exe", "bin/codex-code-mode-host.exe", "codex-path/rg.exe", "codex-resources/codex-command-runner.exe",
                    "codex-resources/voice/bin/x.dll"):
            (vendor / rel).parent.mkdir(parents=True, exist_ok=True)
            (vendor / rel).write_bytes(rel.encode())
        (vendor / "codex-resources/voice/notes.txt").write_text("not pinned")
        (vendor / "codex-package.json").write_text(json.dumps(layout or {"layoutVersion": 1, "version": "0.158.0", "target": TRIPLE,
                                                                         "entrypoint": "bin/codex.exe"}))
    if claude:
        (npm / "claude.cmd").write_text("@ECHO off\r\n", encoding="utf-8")
        exe = npm / "node_modules/@anthropic-ai/claude-code/bin/claude.exe"
        exe.parent.mkdir(parents=True)
        exe.write_bytes(b"claude")
    return npm


def test_native_executable_replaces_the_npm_launchers(tmp_path):
    npm = npm_layout(tmp_path)
    codex = q.native_executable("codex_cli", str(npm / "codex.cmd"))
    claude = q.native_executable("claude_code", str(npm / "claude.cmd"))
    assert codex.name == "codex.exe" and codex.parent.name == "bin" and TRIPLE in str(codex)
    assert claude.name == "claude.exe"
    plain = tmp_path / "standalone.exe"
    plain.write_bytes(b"x")
    assert q.native_executable("codex_cli", str(plain)) == plain.resolve()


def test_missing_vendor_payload_is_refused(tmp_path):
    npm = npm_layout(tmp_path, codex=True, claude=False)
    shutil.rmtree(npm / "node_modules/@openai/codex/node_modules")
    with pytest.raises(QualificationError, match="LAUNCH_CHAIN_VENDOR_MISSING"):
        q.native_executable("codex_cli", str(npm / "codex.cmd"))
    with pytest.raises(QualificationError, match="LAUNCH_CHAIN_VENDOR_MISSING"):
        q.native_executable("claude_code", str(npm / "claude.cmd"))


def test_native_codex_chain_pins_every_executable_and_resolves_nothing_by_name(tmp_path):
    npm = npm_layout(tmp_path)
    exe = q.native_executable("codex_cli", str(npm / "codex.cmd"))
    pinned, resolve = q.launch_chain_for("codex_cli", exe)
    names = sorted(Path(p).name for p in pinned)
    assert resolve == {}
    assert names == sorted(["codex-package.json", "codex.exe", "codex-code-mode-host.exe", "rg.exe", "codex-command-runner.exe", "x.dll"])
    q.check_launch_chain(pinned, resolve)
    (exe.parent.parent / "codex-resources/voice/bin/x.dll").write_bytes(b"swapped")       # payload replaced after qualification
    with pytest.raises(QualificationError, match="LAUNCH_CHAIN_HASH_MISMATCH"):
        q.check_launch_chain(pinned, resolve)


def test_unknown_or_damaged_vendor_layout_is_refused(tmp_path):
    npm = npm_layout(tmp_path, layout={"layoutVersion": 2, "entrypoint": "bin/codex.exe", "target": TRIPLE})
    exe = q.native_executable("codex_cli", str(npm / "codex.cmd"))
    with pytest.raises(QualificationError, match="LAUNCH_CHAIN_LAYOUT_UNKNOWN"):
        q.launch_chain_for("codex_cli", exe)
    # Review round 1, OQ-R1-1: a missing descriptor is a damaged layout, never a "standalone" binary with empty pins.
    (exe.parent.parent / "codex-package.json").unlink()
    with pytest.raises(QualificationError, match="LAUNCH_CHAIN_LAYOUT_UNKNOWN"):
        q.launch_chain_for("codex_cli", exe)
    loose = tmp_path / "loose" / "codex.exe"
    loose.parent.mkdir()
    loose.write_bytes(b"x")
    with pytest.raises(QualificationError, match="LAUNCH_CHAIN_LAYOUT_UNKNOWN"):
        q.launch_chain_for("codex_cli", loose)                    # any codex.exe needs the recognised layout
    under_vendor = tmp_path / "x" / "vendor" / "tool.exe"
    under_vendor.parent.mkdir(parents=True)
    under_vendor.write_bytes(b"x")
    with pytest.raises(QualificationError, match="LAUNCH_CHAIN_LAYOUT_UNKNOWN"):
        q.launch_chain_for("codex_cli", under_vendor)


def _codex_record(client, codex_home_cfg=None):
    ev = Path(client) / "ev.json"
    ev.write_text(json.dumps({"provider": "codex_cli", "ok": True, "version": "0.0.1", "model": None,
                              "executable_sha256": q._file_sha256(sys.executable)}))
    return signed_record(client, provider="codex_cli", level="NATIVE_QUALIFIED", spec_id="codex_cli", executable=sys.executable,
                         executable_args=[], version="0.0.1", models=[None], evidence_path=ev, qualified_by="test")


def test_worker_codex_home_invariant(tmp_path):
    client = tmp_path / "client"
    (client / "control").mkdir(parents=True)
    rec = _codex_record(client)
    home = q.client_cli_homes(client)["CODEX_HOME"]
    q.check_codex_client_home(rec, None, {})                    # not the worker composition: nothing checked
    with pytest.raises(QualificationError, match="CODEX_HOME_NOT_CLIENT_PROFILE"):
        q.check_codex_client_home(rec, home, {})                # absent = Codex would fall back to the owner's login
    other = tmp_path / "owner/.codex"
    other.mkdir(parents=True)
    with pytest.raises(QualificationError, match="CODEX_HOME_NOT_CLIENT_PROFILE"):
        q.check_codex_client_home(rec, home, {"CODEX_HOME": str(other)})
    with pytest.raises(QualificationError, match="CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED"):
        q.check_codex_client_home(rec, home, {"CODEX_HOME": home})
    for bad in ('[windows]\nsandbox = "danger"\n', "not toml [", 'windows = "unelevated"\n'):
        (Path(home) / "config.toml").write_text(bad)
        with pytest.raises(QualificationError, match="CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED"):
            q.check_codex_client_home(rec, home, {"CODEX_HOME": home})
    (Path(home) / "config.toml").write_text('[windows]\nsandbox = "unelevated"\n')
    # Review round 1, OQ-R1-1: a NATIVE record that does not pin a recognised vendored layout never composes in the worker.
    with pytest.raises(QualificationError, match="LAUNCH_CHAIN_LAYOUT_NOT_PINNED"):
        q.check_codex_client_home(rec, home, {"CODEX_HOME": home})
    npm = npm_layout(tmp_path, claude=False)
    exe = q.native_executable("codex_cli", str(npm / "codex.cmd"))
    ev = Path(client) / "ev-native.json"
    ev.write_text(json.dumps({"provider": "codex_cli", "ok": True, "version": "0.0.1", "model": None,
                              "executable_sha256": q._file_sha256(exe)}))
    vendored = signed_record(client, provider="codex_cli", level="NATIVE_QUALIFIED", spec_id="codex_cli", executable=exe,
                             executable_args=[], version="0.0.1", models=[None], evidence_path=ev, qualified_by="test")
    assert any(k.endswith("codex-package.json") for k in vendored["pinned_files"])
    for mode in q.CODEX_SANDBOX_MODES:
        (Path(home) / "config.toml").write_text(f'[windows]\nsandbox = "{mode}"\n')
        q.check_codex_client_home(vendored, home, {"CODEX_HOME": home + os.sep})
    stripped = dict(vendored, pinned_files={k: v for k, v in vendored["pinned_files"].items() if not k.endswith("codex-package.json")})
    with pytest.raises(QualificationError, match="LAUNCH_CHAIN_LAYOUT_NOT_PINNED"):
        q.check_codex_client_home(stripped, home, {"CODEX_HOME": home})
    claude = dict(rec, provider="claude_code", spec_id="claude_code")
    q.check_codex_client_home(claude, home, {})                 # other providers are untouched


def test_codex_home_is_rechecked_before_every_execution(tmp_path, monkeypatch):
    """compose_client(codex_home=...) composes only under the pin, and still_valid (run before each bridge execution)
    refuses once the executor environment no longer names the client profile."""
    client = tmp_path / "client"
    (client / "control").mkdir(parents=True)
    from phase2d.conftest import fixture_record
    fixture_record(client, "codex_cli", (None,))
    home = q.client_cli_homes(client)["CODEX_HOME"]
    monkeypatch.delenv("CODEX_HOME", raising=False)
    comp = q.compose_client(client, trust=trust_for(client), allow_fixture=True, codex_home=home)
    assert comp.report[0]["reason"] == "CODEX_HOME_NOT_CLIENT_PROFILE" and comp.executors == {}
    monkeypatch.setenv("CODEX_HOME", home)
    comp = q.compose_client(client, trust=trust_for(client), allow_fixture=True, codex_home=home)
    assert comp.report[0]["status"] == "QUALIFIED"              # fixture level: home pinned, sandbox not required
    assert comp.executors["codex_cli"].revalidate() is None
    monkeypatch.setenv("CODEX_HOME", str(tmp_path))
    assert comp.executors["codex_cli"].revalidate() == "CODEX_HOME_NOT_CLIENT_PROFILE"
    monkeypatch.delenv("CODEX_HOME")
    assert comp.executors["codex_cli"].revalidate() == "CODEX_HOME_NOT_CLIENT_PROFILE"


def test_oq1_proposal_carries_live_usability(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start("use the harness to write a greeting into out.txt")
    harness = turn["execution_proposal"]["harness"]
    assert harness["usable"] is True and harness["reason"] is None


def _native_codex():
    try:
        return q.native_executable("codex_cli")
    except QualificationError:
        return None


@pytest.mark.skipif(_native_codex() is None, reason="native Codex not installed")
def test_real_native_codex_in_the_real_worker_fails_closed_without_a_client_login(tmp_path):
    """REAL: server + worker processes, native codex.exe, scripted local endpoint (phases W, W2, W3 of
    scripts/phase2oq_native_worker.py). The client profile has no login: the record composes, the harness is not
    usable, Approve is refused before the server sees it; no sandbox mode / the npm launcher invalidate the record."""
    out = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/phase2oq_native_worker.py"), "--evidence", str(tmp_path / "ev"),
                          "--phases", "W,W2,W3"], capture_output=True, text=True, timeout=600, cwd=str(ROOT))
    assert out.returncode == 0, out.stderr[-2000:]
    summary = json.loads(next(line for line in out.stdout.splitlines() if line.startswith("{")))
    assert summary["probe"] == "OK" and summary["logged_in"] is False
    assert summary["W_codex_row"][0]["status"] == "QUALIFIED" and summary["W_codex_row"][0]["pinned_files"] > 1
    assert summary["W_harness"]["usable"] is False and summary["W_harness"]["auth_state"] == "NOT_AUTHENTICATED"
    assert summary["W_begin"] == {"result": "REFUSED", "code": "HARNESS_NOT_USABLE"}
    assert summary["W2"] == [["INVALIDATED", "CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED"]]
    assert summary["W3"] == [["INVALIDATED", "LAUNCH_CHAIN_RESOLUTION_CHANGED"]]


def test_oq_r1_2_legacy_turn_decide_cannot_approve_an_unusable_executor(stack, monkeypatch):
    """Review round 1, OQ-R1-2: the blocking `turn_decide approve=true` path is gated exactly like `execution_begin`: the
    approval never reaches the server, the turn is released (cancelled) and nothing is created. Declining stays open."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    from phase2b.conftest import CODEX
    from phase2d.conftest import fixture_record
    from uri_core.client_runtime.turn_runner import TurnError
    fixture_record(stack.client_root, "codex_cli", ("gpt-6-sol",))
    comp = q.compose_client(stack.client_root, trust=trust_for(stack.client_root), allow_fixture=True)
    stack.bridge.executors = comp.executors
    stack.bridge._ensure_registrations()
    turn = stack.start("use the harness to write a greeting into out.txt", reasoning=CODEX)
    assert turn["execution_proposal"]["harness"]["usable"] is False
    for cmd in ({"command": "turn_decide", "turn_id": turn["turn_id"], "approve": True},
                {"command": "turn_decide", "turn_id": turn["turn_id"], "approve": True,
                 "approval_digest": turn["approval_request"]["approval_digest"]}):
        t = stack.start("use the harness to write a greeting into out.txt", reasoning=CODEX) if cmd is not None and "approval_digest" in cmd else turn
        cmd = {**cmd, "turn_id": t["turn_id"]}
        if "approval_digest" in cmd:
            cmd["approval_digest"] = t["approval_request"]["approval_digest"]
        with pytest.raises(TurnError, match="HARNESS_NOT_USABLE"):
            stack.service.handle("turn_decide", cmd)
        rec = stack.turn_record(t["turn_id"])
        assert rec["state"] == "cancelled" and not rec.get("dispatched")
    assert stack.tasks() == 0
    declined = stack.start("use the harness to write a greeting into out.txt", reasoning=CODEX)
    out = stack.service.handle("turn_decide", {"command": "turn_decide", "turn_id": declined["turn_id"], "approve": False})
    assert out["state"] in ("cancelled", "reply") and stack.tasks() == 0
