"""Operational qualification of the acceptance tooling: the client-profile Codex config is written once and never
overwritten, the login guide prints (never runs) an isolated login, and `status` keeps the four states apart."""
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("acc_oq", ROOT / "scripts" / "phase2close_acceptance.py")
acc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(acc)

from uri_supervisor_bridge import qualification as q  # noqa: E402


def _campaign(tmp_path, gates=()):
    base = tmp_path / "campaign"
    client = base / "client"
    (client / "control").mkdir(parents=True)
    (base / "campaign.json").write_text(json.dumps({"base": str(base), "client_root": str(client), "gates": list(gates)}))
    return base, client


def test_codex_client_config_is_the_owners_choice_written_once_and_never_overwritten(tmp_path):
    import pytest
    _, client = _campaign(tmp_path)
    cfg = Path(q.client_cli_homes(client)["CODEX_HOME"]) / "config.toml"
    with pytest.raises(SystemExit, match="CODEX_SANDBOX_MODE_INVALID"):
        acc.write_codex_client_config(client, None)                   # no silent default backend
    assert not cfg.exists()
    assert acc.write_codex_client_config(client, "unelevated") == "unelevated"
    assert "network NOT confined" in cfg.read_text()
    owner = '[windows]\nsandbox = "elevated"\n'
    cfg.write_text(owner)                                            # the owner changed it to the elevated backend
    assert acc.write_codex_client_config(client, "unelevated") == "elevated"
    assert cfg.read_text() == owner


def test_login_guide_prints_an_isolated_login_and_runs_nothing(tmp_path, capsys, monkeypatch):
    base, client = _campaign(tmp_path)
    exe = tmp_path / "codex.exe"
    exe.write_bytes(b"x")
    monkeypatch.setattr(q, "native_executable", lambda provider, found=None: exe)
    ran = []
    monkeypatch.setattr(acc.subprocess, "run", lambda *a, **k: ran.append(a))
    assert acc.login_guide(SimpleNamespace(campaign=str(base), provider="codex_cli")) == 0
    out = capsys.readouterr().out
    assert ran == []
    assert f'$env:CODEX_HOME = "{client / "home" / ".codex"}"' in out
    assert f'$env:USERPROFILE = "{client / "home"}"' in out
    assert f'& "{exe}" login' in out and "Remove-Item Env:CODEX_API_KEY" in out
    assert "Do not copy credential files" in out


def test_status_keeps_installed_authenticated_qualified_and_operational_apart(tmp_path, capsys, monkeypatch):
    base, client = _campaign(tmp_path, gates=[{"gate": "PA-8 native-codex-login", "result": "PASS"}])
    exe = tmp_path / "codex.exe"
    exe.write_bytes(b"x")
    monkeypatch.setattr(q, "native_executable", lambda provider, found=None: exe if provider == "codex_cli" else None)
    seen = {}

    def auth(provider, executable):
        seen[provider] = os.environ.get("CODEX_HOME")
        return True                                             # logged in inside the client profile
    monkeypatch.setattr(q, "native_auth_probe", auth)
    assert acc.status(SimpleNamespace(campaign=str(base))) == 0
    out = json.loads(capsys.readouterr().out)
    codex, claude = out["providers"]["codex_cli"], out["providers"]["claude_code"]
    assert codex["installed"] is True and codex["authenticated_client_profile"] is True
    assert codex["qualified"] is False and codex["qualification_reason"] == "NO_RECORD"   # logged in is not qualified
    assert codex["operational"] is False and codex["login_gate"] == "PASS"               # qualified is not operational
    assert claude["installed"] is False and claude["authenticated_client_profile"] is None
    assert seen["codex_cli"] == str(client / "home" / ".codex")                         # probed under the client profile


def test_pa13_chat_handoff_is_an_owner_gate():
    assert "PA-13 chat-supervised-handoff" in acc.GATES
