"""Cloud policy (AC-12) and the integrated server composition (W3, AC-9)."""
import ast
import json
import socket
from pathlib import Path

import pytest

from uri_operational_intelligence import cloud_policy as CP

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def no_network(monkeypatch):
    def refuse(*a, **k):
        raise AssertionError("NETWORK_USED")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def test_module_has_no_transport_or_credential_access():
    tree = ast.parse((ROOT / "uri_operational_intelligence/cloud_policy.py").read_text(encoding="utf-8"))
    imported = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for a in (n.names if isinstance(n, ast.Import) else [ast.alias(n.module or "")])}
    assert imported <= {"__future__", "json", "secrets", "threading", "time", "pathlib"}
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert not names & {"environ", "getenv", "keyring", "urlopen", "connect"}


def test_call_is_always_refused(no_network):
    with pytest.raises(CP.CloudPolicyError, match="CLOUD_ACTIVATION_DISABLED"):
        CP.call("anthropic", "x", prompt="hi")
    assert all(p["activation"] == "disabled" and p["credentials"] == "none" for p in CP.providers())


def test_cap_is_five_dollars_and_cannot_be_raised():
    assert CP.MONTHLY_CAP_USD == 5.00
    with pytest.raises(CP.CloudPolicyError, match="CAP_ABOVE_POLICY"):
        CP.CloudSpendPolicy(cap_usd=5.01)


def test_single_use_manual_approval(tmp_path, no_network):
    now = [1_800_000_000.0]
    p = CP.CloudSpendPolicy(tmp_path / "cloud.json", clock=lambda: now[0])
    rec = p.request("anthropic", "m", 0.40)
    with pytest.raises(CP.CloudPolicyError, match="APPROVAL_NOT_USABLE"):
        p.consume(rec["id"], "anthropic", "m", 0.40)               # not approved yet
    with pytest.raises(CP.CloudPolicyError, match="MANUAL_APPROVAL_REQUIRED"):
        p.approve(rec["id"], by_user="yes")                         # only a literal True from a UI button handler
    p.approve(rec["id"], by_user=True)
    with pytest.raises(CP.CloudPolicyError, match="APPROVAL_BINDING_MISMATCH"):
        p.consume(rec["id"], "anthropic", "other-model", 0.40)
    p.consume(rec["id"], "anthropic", "m", 0.40)
    with pytest.raises(CP.CloudPolicyError, match="APPROVAL_NOT_USABLE"):
        p.consume(rec["id"], "anthropic", "m", 0.40)               # single use
    assert p.spent() == 0.40
    reloaded = CP.CloudSpendPolicy(tmp_path / "cloud.json", clock=lambda: now[0])
    assert reloaded.spent() == 0.40
    stored = json.loads((tmp_path / "cloud.json").read_text())
    assert "prompt" not in json.dumps(stored)


def test_monthly_cap_and_expiry(tmp_path):
    now = [1_800_000_000.0]
    p = CP.CloudSpendPolicy(clock=lambda: now[0])
    a = p.request("openai", "m", 4.90)
    p.approve(a["id"], by_user=True)
    p.consume(a["id"], "openai", "m", 4.90)
    with pytest.raises(CP.CloudPolicyError, match="MONTHLY_CAP_EXCEEDED"):
        p.request("openai", "m", 0.20)
    b = p.request("openai", "m", 0.05)
    now[0] += CP.APPROVAL_TTL_S + 1
    with pytest.raises(CP.CloudPolicyError, match="APPROVAL_EXPIRED"):
        p.approve(b["id"], by_user=True)


def test_integrated_composition_offers_phase2_rows_plus_runtime_v1(tmp_path):
    pytest.importorskip("uri_supervisor_bridge.composition")
    from uri_supervisor_bridge.composition import write_policy
    from uri_operational_intelligence import brain_client as BC
    from uri_operational_intelligence.integrated_composition import integrated_server_composition, offered_rows
    cfg = {"model": {"id": "qwen-test"}, "runtime": {"port": 9, "ctx": 32768}}
    pf = write_policy(tmp_path / "control/phase2_reasoning_policy.json",
                      [("client_external_harness", "codex_cli", None)])
    comp, provider = integrated_server_composition(pf, cfg, BC.BrainClient("http://127.0.0.1:9"))
    assert offered_rows(comp) == sorted({("server_local_model", "uri-deterministic", None),
                                         ("client_external_harness", "codex_cli", None),
                                         ("server_local_model", "llamacpp-runtime-v1", "qwen-test")}, key=str)
    assert comp["qualified"] == ("remember_fact", "external_harness_task")

    class Sel:
        def __init__(self, k, p, m):
            self.kind, self.provider, self.model = k, p, m
    # Non-Brain rows get no interpreter suggestion (same as the accepted Phase 2 profile) and never call the model.
    assert comp["interpreter"]("remember x", "remember_fact", ["fact"], Sel("client_external_harness", "codex_cli", None)) == {}
    assert provider.calls == []


def test_malformed_policy_still_refuses(tmp_path):
    pytest.importorskip("uri_supervisor_bridge.composition")
    from uri_supervisor_bridge.composition import PolicyError
    from uri_operational_intelligence import brain_client as BC
    from uri_operational_intelligence.integrated_composition import integrated_server_composition
    pf = tmp_path / "p.json"
    pf.write_text('{"schema": "wrong"}')
    with pytest.raises(PolicyError):
        integrated_server_composition(pf, {"model": {"id": "q"}, "runtime": {"port": 9, "ctx": 1}},
                                      BC.BrainClient("http://127.0.0.1:9"))
