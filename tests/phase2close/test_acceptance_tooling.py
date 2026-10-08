"""Closure review round 1, D1: `qualify` must never be satisfied by a shell credential; only a login stored under the
client profile may qualify a client. Values of credential variables are never read by these tests' assertions."""
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "tests")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
spec = importlib.util.spec_from_file_location("acc", ROOT / "scripts" / "phase2close_acceptance.py")
acc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acc)

FAKE = {"CODEX_API_KEY": "x", "CLAUDE_CODE_OAUTH_TOKEN": "x", "ANTHROPIC_API_KEY": "x", "OPENAI_API_KEY": "x",
        "GITHUB_TOKEN": "x", "SOME_SECRET": "x", "DB_PASSWORD": "x", "CODEX_HOME": "C:/owner/.codex", "PATH": "C:/bin"}


def test_probe_environment_removes_every_credential_and_pins_the_client_profile(tmp_path):
    env, removed = acc.probe_environment(tmp_path, dict(FAKE))
    assert removed == sorted(["ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "CODEX_API_KEY", "DB_PASSWORD", "GITHUB_TOKEN",
                              "OPENAI_API_KEY", "SOME_SECRET"])
    assert not set(removed) & set(env)
    assert env["CODEX_HOME"] == str(tmp_path / "home" / ".codex")          # the owner's CODEX_HOME is overridden
    assert env["USERPROFILE"] == env["HOME"] == str(tmp_path / "home") and env["PATH"] == "C:/bin"
    from uri_supervisor.executors import BUILTIN_SPECS
    for s in BUILTIN_SPECS.values():                                       # what an executor/probe would be given
        fwd = s.build_env(env)
        assert not {"CODEX_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"} & set(fwd)


def test_qualify_probes_under_the_sanitized_environment_and_restores_the_caller(tmp_path, monkeypatch):
    base = tmp_path / "campaign"
    client_root = base / "client"
    (client_root / "control").mkdir(parents=True)
    (base / "campaign.json").write_text(json.dumps({"base": str(base), "client_root": str(client_root), "gates": []}))
    seen = {}

    def direct_probe(provider, model, evidence):
        seen["probe"] = {k: k in os.environ for k in ("CODEX_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")}
        seen["codex_home"] = os.environ.get("CODEX_HOME")
        return {"ok": True, "status": "OK", "executable": "codex", "version": "0.0.0"}   # a token-backed success
    from uri_supervisor_bridge import qualification as q
    monkeypatch.setattr(acc, "_load_p2c", lambda: SimpleNamespace(direct_probe=direct_probe))
    def auth(provider, exe):
        seen["auth_token_visible"] = "CODEX_API_KEY" in os.environ
        return False                                  # no login stored under the client profile
    monkeypatch.setattr(q, "native_auth_probe", auth)
    monkeypatch.setenv("CODEX_API_KEY", "shell-token-must-not-reach-the-probe")
    rc = acc.qualify(SimpleNamespace(campaign=str(base), provider="codex_cli", model="m"))
    assert seen["probe"] == {"CODEX_API_KEY": False, "CLAUDE_CODE_OAUTH_TOKEN": False}
    assert seen["auth_token_visible"] is False and seen["codex_home"] == str(client_root / "home" / ".codex")
    assert rc == 2 and os.environ["CODEX_API_KEY"] == "shell-token-must-not-reach-the-probe"   # caller restored
    camp = json.loads((base / "campaign.json").read_text())
    assert camp["qualifications"][-1]["persisted"] is False and "CODEX_API_KEY" in camp["qualifications"][-1]["credential_vars_removed"]
    assert not (client_root / "control" / "supervisor" / "qualification" / "codex_cli.json").exists()
