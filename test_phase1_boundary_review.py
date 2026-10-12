"""Second review: catalogue presence never becomes server capability; adapters stay client-only.

Each check runs in a fresh interpreter so an import made by another test cannot hide a leak.
"""
import json
from pathlib import Path
import subprocess
import sys
import textwrap

ROOT = Path(__file__).resolve().parent


def fresh(code):
    out = subprocess.run([sys.executable, "-c", textwrap.dedent(code)], cwd=ROOT, capture_output=True, text=True,
                         timeout=180, env={**__import__("os").environ, "URI_EXTERNAL_CREDENTIAL_SECRET": "synthetic"})
    assert out.returncode == 0, out.stderr[-3000:]
    return json.loads(out.stdout.strip().splitlines()[-1])


def test_server_dispatcher_refuses_paired_client_capability_before_loading_any_client_code():
    result = fresh("""
        import sys, json
        from uri_core.core.dispatcher import ToolDispatcher
        r = ToolDispatcher().execute_tool("external_harness_task", instruction="write x", expected_file="x.md")
        loaded = sorted(m for m in sys.modules if m.startswith(("uri_harness_adapters", "uri_core.client_runtime")))
        print(json.dumps({"status": r["status"], "message": r["message"], "loaded": loaded}))
    """)
    assert result["status"] == "error" and "never on the server runtime" in result["message"]
    assert result["loaded"] == []


def test_catalogue_entry_is_a_runtime_gap_for_the_server():
    result = fresh("""
        import json
        from uri_core.core.capability_registry import CapabilityRegistry
        d = next(c for c in CapabilityRegistry("uri_workspace/capabilities_registry.json").list_capabilities() if c.id == "external_harness_task")
        print(json.dumps({"gap": d.gap_reason, "availability": d.availability,
                          "approval": d.approval_requirement}))
    """)
    # is_executable is status-only in the shared registry; the runtime gap is what the legacy gates honour.
    assert result == {"gap": "unavailable_runtime", "availability": "unavailable_on_runtime", "approval": "user_approval_required"}


def test_neither_server_composition_loads_adapters_or_the_client_runtime_harness():
    result = fresh("""
        import sys, json
        import uri_core.app.server                                       # legacy server (shared catalogue)
        from uri_core.app.paired_server import create_app, default_composition
        default_composition()
        print(json.dumps(sorted(m for m in sys.modules if m.startswith("uri_harness_adapters"))))
    """)
    assert result == []


def test_default_paired_composition_refuses_every_harness_selection():
    result = fresh("""
        import json
        from uri_core.app.paired_server import default_composition
        from uri_core.core.paired_reasoning import ReasoningUnavailable
        policy = default_composition()["policy"]
        out = {}
        for provider in ("claude_code", "codex_cli", "antigravity"):
            try:
                policy.require({"kind": "client_external_harness", "provider": provider, "model": None})
                out[provider] = "ACCEPTED"
            except ReasoningUnavailable as exc:
                out[provider] = str(exc)
        print(json.dumps(out))
    """)
    assert set(result.values()) == {"ADAPTER_NOT_QUALIFIED"}


def test_worker_registry_has_nothing_usable_without_auth_and_qualification():
    result = fresh("""
        import json
        from uri_harness_adapters import default_registry
        rows = default_registry().discover()
        print(json.dumps({r["harness_id"]: [r["usable"], r["qualification"]] for r in rows}))
    """)
    assert all(usable is False for usable, _ in result.values())
    assert result["antigravity"][1] == "REFUSED"
    assert {q for _, q in result.values()} <= {"NATIVE_UNQUALIFIED", "REFUSED"}
