"""M31 boundary, preserved after C4: Core/Brain never knows or spawns development agents.

The original guard (tests/test_m31_model_brain_ux.py) is restored UNMODIFIED and scans all of
uri_core. The external-harness adapters that legitimately name providers live outside Core in
`uri_harness_adapters`; these tests prove that move did not open a back door.
"""
import ast
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def _imports(path):
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module


def test_no_core_module_imports_the_provider_adapters():
    offenders = [str(p.relative_to(ROOT)) for p in (ROOT / "uri_core").rglob("*.py")
                 if any(m.split(".")[0] == "uri_harness_adapters" for m in _imports(p))]
    assert offenders == []


def test_adapters_depend_only_on_the_neutral_client_runtime():
    allowed = {"uri_core.client_runtime.harness"}
    for path in (ROOT / "uri_harness_adapters").rglob("*.py"):
        internal = {m for m in _imports(path) if m.split(".")[0] == "uri_core"}
        assert internal <= allowed, (path.name, internal - allowed)


def test_server_composition_never_loads_adapters():
    code = ("import sys, uri_core.app.paired_server, uri_core.core.paired_coordinator, uri_core.core.intent_discovery;"
            "print('uri_harness_adapters' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip() == "False"


def test_core_default_turn_service_has_no_harness():
    from uri_core.client_runtime.harness import HarnessRegistry
    assert HarnessRegistry().discover() == []


def test_refused_product_cannot_be_qualified_or_invoked():
    import pytest
    from uri_core.client_runtime.harness import HarnessError
    from uri_harness_adapters import default_registry
    registry = default_registry(auth_probe=lambda hid: True)
    with pytest.raises(HarnessError, match="HARNESS_REFUSED"):
        registry.qualify("antigravity", "FIXTURE_ONLY", "c" * 64)
    row = next(r for r in registry.discover() if r["harness_id"] == "antigravity")
    assert row["qualification"] == "REFUSED" and row["usable"] is False
