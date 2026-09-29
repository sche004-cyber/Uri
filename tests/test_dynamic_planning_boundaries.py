"""Dynamic planning slice 1: import boundaries and the reused-file manifest (migration plan §7)."""
import ast
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLANNING = ROOT / "uri_v1" / "execution" / "planning"
FORBIDDEN = ("uri_core", "experimental", "server", "file_store", "uri_ui")

# LF-normalized sha256 of every reused file, pinned at BASE (4292528, on 21bcc63). Slice 1 must not change any of them.
REUSED = {
    "uri_v1/execution/officefile.py": "1fecc22568e3e44fde13047d064dea9d0aa3d0ed7da1207c7c4febdc4dfc40d3",
    "uri_v1/execution/workspace.py": "46b71b09be0c12b1f3b9d0583dfd9605ee540793bb81770c5e57c945e24c81a4",
    "uri_v1/execution/acceptance.py": "a37647008303b5155aefbd7d8b5e0d78e536ededbced08e00b46f0a8dd191cc1",
    "uri_v1/execution/lineage.py": "fd9a6a70429debbc4dfc99e34b2ad0f2c2f4efa985731b16a4369c000f22f82d",
    "uri_v1/execution/verify.py": "458bfe09efe066248559f9c3007807cb11f19afe3eb7866caa72c00a4423ebe3",
    "uri_v1/execution/run_record.py": "453dcf65f022a1acf642931eedadec859f85628e234cf04787790cd280280532",
    "uri_v1/memory/sources.py": "2a1344fcf97514fec9e1fa3a7f09fbf8eb2276c350eb87257db00bd0a50c4aaf",
    "uri_v1/memory/recorder.py": "3029c50a78f838b6c9cc1c70fcacaff33bcca5466a583274e7e468fb181e312b",
    "uri_v1/results/version_ledger.py": "3f0f9f9bf806df9a16d1f9392142c3fbd81482686946761933839265c3e9b5c4",
    "uri_v1/edge/report.py": "c2f9cbab690780c24faf1cb659a206a09f8e74c387d5957269abb3cd5957376b",
}


def imports(path: Path) -> set:
    found = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import): found.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = ("." * node.level) + (node.module or "")
            found.add(base); found.update(f"{base}.{a.name}" for a in node.names)
        elif isinstance(node, ast.Call) and getattr(node.func, "id", None) == "__import__":
            found.add("__import__")
    return found


def test_planning_imports_nothing_outside_its_boundary():
    for path in PLANNING.glob("*.py"):
        for name in imports(path):
            parts = name.lstrip(".").split(".")
            assert not any(p in FORBIDDEN for p in parts), (path.name, name)
            assert "__import__" != name and "importlib" not in parts, (path.name, name)


def test_oracle_is_a_separate_execution_path():
    names = imports(PLANNING / "oracle.py")
    for banned in ("runner", "bindings", "actions", "compiler"):
        assert not any(n.lstrip(".").split(".")[0] == banned or n.endswith("planning." + banned) for n in names), banned


def test_no_existing_module_imports_planning():
    allowed_prefixes = ("uri_v1/execution/planning/", "tests/test_dynamic_planning_", "scripts/dynamic_planning_qualification.py")
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(allowed_prefixes) or "/." in "/" + rel or rel.startswith(("node_modules/", "venv/", ".venv/")): continue
        try: text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError): continue
        assert "execution.planning" not in text and "execution import planning" not in text, rel


def test_reused_files_are_unchanged_since_base():
    for rel, sha in REUSED.items():
        data = (ROOT / rel).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(data).hexdigest() == sha, rel


def test_no_eval_exec_or_subprocess_in_planning():
    for path in PLANNING.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {getattr(n.func, "id", None) for n in ast.walk(tree) if isinstance(n, ast.Call)}
        assert not calls & {"eval", "exec", "compile"}, path.name
        assert "subprocess" not in imports(path) and "os" not in {i.split(".")[0] for i in imports(path)}, path.name
