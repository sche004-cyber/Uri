"""Structural boundary: Core and the supervisor never know the bridge; the bridge never reaches into Core's intent,
session or approval machinery; the Phase 1 harness protections are reused, not weakened."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BRIDGE = ROOT / "uri_supervisor_bridge"


def _texts(pkg):
    return {str(f): f.read_text(encoding="utf-8", errors="replace") for f in (ROOT / pkg).rglob("*.py")}


def test_core_and_supervisor_never_import_the_bridge():
    for pkg in ("uri_core", "uri_harness_adapters", "uri_supervisor", "uri_ui"):
        for f, text in _texts(pkg).items():
            assert "uri_supervisor_bridge" not in text, f


def test_bridge_never_touches_intent_session_or_approval_machinery():
    forbidden = ("import uri_core.core.intent_discovery", "from uri_core.core.intent_discovery", "IntentDiscovery(", "session_with(",
                 "save_session", "approval_store", "ApprovalGate", "from uri_core.core.paired_coordinator",
                 "from uri_core.core.client_service", "ClientService(", "record_user_decision(", ".prepare(", ".settle(", ".claim(")
    for f, text in _texts("uri_supervisor_bridge").items():
        code = "\n".join(line for line in text.splitlines() if not line.strip().startswith("#"))
        for token in forbidden:
            assert token not in code, (f, token)


def test_bridge_only_consumes_frozen_verification_primitives():
    text = (BRIDGE / "authority.py").read_text(encoding="utf-8")
    assert "verify_ticket(" in text and "SignedTicket.model_validate" in text and "public_projection(" in text
    assert "Ed25519PrivateKey" not in text and ".sign(" not in text          # the bridge never signs anything


def test_bridge_runner_overrides_only_the_harness_execution_seam():
    text = (BRIDGE / "runner.py").read_text(encoding="utf-8")
    overridden = set(re.findall(r"^    def (\w+)\(", text, re.M))
    # `begin` (Phase 2C) only records the reasoning selection the approval was requested under; it calls the frozen
    # begin unchanged and alters neither the envelope nor the protocol.
    assert overridden <= {"__init__", "begin", "_validate_ticket", "_run_harness", "_runner"}, overridden
    assert "_execute" not in overridden and "_run_local" not in overridden and "_finish" not in overridden


def test_supervisor_bypass_refusal_still_a_superset_of_phase1():
    from uri_core.client_runtime.harness import FORBIDDEN_FLAGS as CORE
    from uri_supervisor.executors import FORBIDDEN_FLAGS as SUP
    assert set(CORE) <= set(SUP)


def test_not_started_prefix_matches_frozen_runtime():
    from uri_core.client_runtime.turn_runner import NOT_STARTED as CORE
    from uri_supervisor_bridge.bridge import NOT_STARTED as MINE
    assert CORE == MINE


def test_phase2a_frozen_core_tests_still_hold():
    import subprocess, sys
    r = subprocess.run([sys.executable, "-m", "pytest", str(ROOT / "tests/phase2a/test_frozen_core.py"), "-q", "-p", "no:cacheprovider"],
                       capture_output=True, text=True, cwd=str(ROOT), timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-1000:]
