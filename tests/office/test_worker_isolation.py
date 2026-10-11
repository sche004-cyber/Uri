"""The guarded worker imports only `uri_operational_intelligence` and can never import `uri_office` (plan §4).

URI Office runs as its own local service. These tests pin that the worker sandbox was not widened for it:
  1. the worker's package list is exactly ("uri_operational_intelligence",) — read from the script source, not imported;
  2. the worker's file guard (FixtureGuard with the worker's package roots), which is what actually stops imports of
     unlisted packages (the worker's SourceFinder only declines them), refuses every `uri_office` file;
  3. no module inside `uri_operational_intelligence` imports `uri_office`.
"""
import ast
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORKER = ROOT / "scripts" / "run_uri_integrated_worker.py"


def _assigned(name):
    tree = ast.parse(WORKER.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {WORKER}")


def test_worker_package_list_is_unchanged():
    assert _assigned("WS_PACKAGES") == ("uri_operational_intelligence",)
    assert "uri_office" not in _assigned("PHASE2_PACKAGES")


def test_worker_guard_refuses_uri_office_files(tmp_path, monkeypatch):
    """Build the guard the way the worker does (FixtureGuard + the worker's package roots) and ask it about files."""
    from types import SimpleNamespace

    from uri_core.core.runtime_identity import FixtureGuard

    monkeypatch.setenv("SYSTEMROOT", os.environ.get("SYSTEMROOT", str(tmp_path / "systemroot")))
    state = tmp_path / "state"
    state.mkdir()
    guard = FixtureGuard(SimpleNamespace(data={"state_root": str(state), "source_root": str(ROOT)}))
    for pkg in _assigned("PHASE2_PACKAGES") + _assigned("WS_PACKAGES"):
        guard.read_roots.append((ROOT / pkg).resolve())
    guard.check_path(str(ROOT / "uri_operational_intelligence" / "__init__.py"))          # allowed
    for f in ("__init__.py", "service.py", "google.py", "grants.py"):
        with pytest.raises(PermissionError, match="C1_FIXTURE_PATH_DENIED"):
            guard.check_path(str(ROOT / "uri_office" / f))
    with pytest.raises(PermissionError):
        guard.check_path(str(ROOT / "uri_office"))                                       # no listing either
    assert not any((ROOT / "uri_office").resolve().is_relative_to(r) for r in guard.read_roots)


def test_oi_package_never_imports_uri_office():
    offenders = []
    for py in (ROOT / "uri_operational_intelligence").rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(n == "uri_office" or n.startswith("uri_office.") for n in names):
                offenders.append(str(py.relative_to(ROOT)))
    assert offenders == []
