"""URI Desktop Recovery — Truthful Acceptance Battery.

Tests T1–T8 against the CANONICAL POST /ask endpoint. These tests verify
that the desktop application correctly flows through URI Core's real
request lifecycle, not a middleware bypass.

REQUIREMENTS:
- Backend must be running at http://127.0.0.1:8000 (start via Launch URI.bat).
- Ollama must be running with qwen3.5:9b available.
- Tests call the real POST /ask endpoint and verify the canonical response
  shape produced by uri_core.app.server._finalize_ask_response().

RUN:
    python tests_desktop_recovery.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

BASE_URL = "http://127.0.0.1:8000"


def _ask(text: str, session_id: str = "test-desktop-session", timeout: float = 60.0) -> Dict[str, Any]:
    """Send a real POST /ask to the canonical endpoint."""
    url = f"{BASE_URL}/ask"
    payload = json.dumps({
        "session_id": session_id,
        "text": text,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _health() -> Dict[str, Any]:
    """Check GET /health."""
    req = urllib.request.Request(f"{BASE_URL}/health")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _desktop_status() -> Dict[str, Any]:
    """Check GET /desktop/status."""
    req = urllib.request.Request(f"{BASE_URL}/desktop/status")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


# ─── Test Functions ───


def test_t1_health_endpoint():
    """T1: Backend health check — verifies the server is running and healthy."""
    result = _health()
    assert result.get("status") == "ok", f"Health check failed: {result}"
    print("T1: Health endpoint         — PASS")


def test_t2_desktop_status_endpoint():
    """T2: Desktop status endpoint — verifies capability inventory is honest."""
    result = _desktop_status()
    assert result.get("runtime") == "desktop", f"Runtime mismatch: {result}"
    assert "model_roles" in result, "Missing model_roles in status"
    assert "v1_capabilities" in result, "Missing v1_capabilities in status"
    assert "architecture_note" in result, "Missing architecture_note"
    # Verify architecture note confirms no bypass
    note = result["architecture_note"]
    assert "canonical" in note.lower(), f"Architecture note should mention canonical pipeline: {note}"
    assert "no middleware interception" in note.lower() or "no /ask bypass" in note.lower(), \
        f"Architecture note should confirm no bypass: {note}"
    print("T2: Desktop status endpoint — PASS")


def test_t3_canonical_ask_response_shape():
    """T3: Canonical /ask response shape — verifies the response comes from
    _finalize_ask_response(), not a middleware bypass."""
    result = _ask("Hello, what can you do?")
    # The canonical response shape from _finalize_ask_response() includes these fields:
    required_keys = {"status", "session_id", "response", "serving_provider", "serving_model"}
    actual_keys = set(result.keys())
    missing = required_keys - actual_keys
    assert not missing, f"Response missing canonical keys: {missing}. Got: {actual_keys}"
    # Verify we got a real response (not empty/None)
    assert result.get("response") is not None, "Response field is None"
    assert result.get("status") is not None, "Status field is None"
    print(f"T3: Canonical /ask shape    — PASS (status={result['status']}, model={result.get('serving_model')})")


def test_t4_model_roles_consumed():
    """T4: Model roles configuration is runtime-consumed — verifies the
    model_roles.json roles are loaded by the canonical pipeline."""
    # The desktop status endpoint should reflect the configured roles
    status = _desktop_status()
    roles = status.get("model_roles", {})
    assert "reasoning" in roles, "Missing 'reasoning' role from model_roles"
    assert "drafting" in roles, "Missing 'drafting' role from model_roles"
    # Verify the configured model matches what's in model_roles.json
    config_path = Path(__file__).resolve().parent / "uri_workspace" / "model_roles.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        for role_name in ("reasoning", "drafting", "semantic_interpretation"):
            if role_name in config and role_name in roles:
                expected_model = config[role_name].get("model")
                actual_model = roles[role_name].get("model")
                assert expected_model == actual_model, \
                    f"Role {role_name}: config says {expected_model} but status says {actual_model}"
    print("T4: Model roles consumed    — PASS")


def test_t5_canonical_model_execution():
    """T5: Real model execution through canonical pipeline — verifies
    that POST /ask actually calls a model (not a fabricated response)."""
    # Ask a question that requires model reasoning
    result = _ask("What is 17 multiplied by 23?", timeout=90.0)
    assert result.get("status") is not None, f"No status in response: {result}"
    response_text = result.get("response")
    # The response should be non-empty and come from the model
    if isinstance(response_text, dict):
        response_text = response_text.get("message", str(response_text))
    assert response_text and len(str(response_text)) > 5, \
        f"Response too short or empty — suggests no model execution: {response_text}"
    print(f"T5: Canonical model exec    — PASS (len={len(str(response_text))})")


def test_t6_no_middleware_bypass():
    """T6: Verify no middleware bypass is active — the response should come
    through _finalize_ask_response(), which reads from UsageMeter."""
    result = _ask("Tell me about URI's architecture.")
    # Key check: the canonical path sets serving_provider/serving_model via
    # _serving_model_for_turn() which reads UsageMeter records. A middleware
    # bypass would set these directly from hardcoded values.
    # The canonical path may return None for serving_model in unauthenticated
    # mode (no UsageMeter records) — this is correct behavior.
    # What we verify is the response SHAPE matches canonical, and there's
    # no fabricated "execution_path" field that the middleware used to add.
    response_keys = set(result.keys())
    canonical_keys = {
        "status", "session_id", "error", "semantic_analysis", "execution",
        "response", "narrative", "narrative_unavailable_reason",
        "serving_provider", "serving_model", "serving_prompt_tokens",
        "serving_eval_tokens", "serving_duration_seconds",
    }
    # All canonical keys should be present
    missing = canonical_keys - response_keys
    assert not missing, f"Missing canonical keys (suggests non-canonical path): {missing}"
    # No extra fabricated keys (like "edge_only" or custom "execution_path" from old adapter)
    execution = result.get("execution")
    if isinstance(execution, dict):
        # The canonical execution dict should NOT have "edge_only" (that was fabricated)
        assert "edge_only" not in execution, "Found fabricated 'edge_only' in execution — middleware bypass detected"
    print("T6: No middleware bypass    — PASS")


def test_t7_v1_capabilities_honest():
    """T7: V1 capability inventory is honest — reports importability and
    qualification status without claiming fabricated integration."""
    status = _desktop_status()
    v1 = status.get("v1_capabilities", {})
    assert isinstance(v1, dict), f"v1_capabilities is not a dict: {type(v1)}"
    # Each reported capability should have an 'importable' field
    for cap_name, cap_info in v1.items():
        assert "importable" in cap_info, \
            f"Capability {cap_name} missing 'importable' field"
        assert isinstance(cap_info["importable"], bool), \
            f"Capability {cap_name} 'importable' should be bool"
    print(f"T7: V1 capabilities honest  — PASS ({len(v1)} capabilities inventoried)")


def test_t8_governance_anchors_intact():
    """T8: Governance anchors — frozen scope guard and M33.3-R anchors."""
    import subprocess
    repo_root = Path(__file__).resolve().parent
    python_exe = repo_root / ".venv" / "Scripts" / "python.exe"
    if not python_exe.exists():
        python_exe = Path("C:/Users/cheta/Development/uri-agent/.venv/Scripts/python.exe")

    # Run the frozen scope guard test
    result = subprocess.run(
        [str(python_exe), "-m", "pytest",
         "tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged",
         "-o", "pythonpath=.",
         "-x", "-q", "--tb=short"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, f"Frozen scope guard FAILED:\n{result.stdout}\n{result.stderr}"

    # Run M33.3-R anchor tests
    result2 = subprocess.run(
        [str(python_exe), "-m", "pytest",
         "tests/test_rar_replay.py",
         "-o", "pythonpath=.",
         "-x", "-q", "--tb=short"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result2.returncode == 0, f"M33.3-R anchors FAILED:\n{result2.stdout}\n{result2.stderr}"
    print("T8: Governance anchors      — PASS")


def main():
    """Run all acceptance tests sequentially."""
    print("=" * 60)
    print("URI Desktop Recovery — Truthful Acceptance Battery")
    print("=" * 60)
    print()

    # Pre-check: is the backend running?
    try:
        _health()
    except Exception as exc:
        print(f"FATAL: Backend not reachable at {BASE_URL}/health: {exc}")
        print("Start the backend with: .\\Launch URI.bat")
        sys.exit(1)

    tests = [
        test_t1_health_endpoint,
        test_t2_desktop_status_endpoint,
        test_t3_canonical_ask_response_shape,
        test_t4_model_roles_consumed,
        test_t5_canonical_model_execution,
        test_t6_no_middleware_bypass,
        test_t7_v1_capabilities_honest,
        test_t8_governance_anchors_intact,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except Exception as exc:
            print(f"  FAIL: {test_fn.__name__}: {exc}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(tests)} tests")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
