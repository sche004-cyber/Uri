"""Regression coverage for the authorized M39 entry in the frozen M37 guard
(tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged;
User authorization, Chetan, 2026-09-29 05:21 UTC).

Proves the entry is minimal and hides nothing else:
- it names only M39 paths (no dynamic-planning or other lane's paths);
- the guard still fails for a changed frozen file, a new file in frozen scope,
  a look-alike of an M39 path, and a path-traversal name (exercised on a
  disposable clone, never on the working checkout);
- M39 code itself does no direct file I/O, so the allowlisted package cannot
  read or write arbitrary files; everything goes through frozen M36/M37;
- a request or answer naming a file outside the authorized folder never binds it.
"""
from __future__ import annotations

import ast
from pathlib import Path
import uuid

import pytest

import tests.test_m37_edge_resolution as m37
from uri_v1.office import request as req
from tests.m39_office_support import OfficeEnv, SALES, make_workbook, script as script_text

ROOT = Path(__file__).resolve().parents[1]


def _allowed(path: str) -> bool:
    """Same predicate the frozen guard applies, with only the M39 entry."""
    return (path.startswith(m37.M39_ALLOWED) or path in m37.M39_ALLOWED_FILES) and ".." not in path.split("/")


def test_entry_is_m39_only_and_tight():
    assert m37.M39_ALLOWED == ("uri_v1/office/", "fixtures/m39_office/", "tests/test_m39_")
    assert m37.M39_ALLOWED_FILES == {"tests/m39_office_support.py", "scripts/m39_office_benchmark.py",
                                     "scripts/m39_generate_benchmark.py"}
    for entry in m37.M39_ALLOWED + tuple(m37.M39_ALLOWED_FILES):
        assert "m39" in entry or entry == "uri_v1/office/", entry
        assert "planning" not in entry and "*" not in entry


@pytest.mark.parametrize("path", [
    "uri_v1/memory/recorder.py",                      # frozen M36
    "uri_v1/memory/uri_adapter/envelope.py",
    "uri_v1/memory/sources.py",
    "uri_v1/planning/slice1.py",                       # a non-M39 lane
    "uri_core/app/server.py",                          # live app
    "uri_ui/index.html",
    "uri_v1/office_extra.py",                          # look-alikes of M39 paths
    "uri_v1/officex/a.py",
    "fixtures/m39_office_evil/x.py",
    "scripts/m39_anything_else.py",
    "scripts/m39_office_benchmark.pyx",               # exact files match exactly
    "scripts/m39_office_benchmark.py.bak",
    "scripts/m39_generate_benchmark.py~",
    "tests/m39_office_support.py/evil.py",
    "tests/m39_office_support.pyc",
    "tests/m39_other_support.py",
    "uri_v1/office/../memory/recorder.py",             # traversal
    "tests/test_m33_3_r_anchors.py",
])
def test_entry_does_not_cover_other_paths(path):
    assert not _allowed(path), path


@pytest.mark.parametrize("path", [
    "uri_v1/office/flow.py", "fixtures/m39_office/benchmark/task_01/report.py",
    "tests/test_m39_flow.py", "tests/m39_office_support.py", "scripts/m39_office_benchmark.py",
    "scripts/m39_generate_benchmark.py",
])
def test_entry_covers_m39_paths(path):
    assert _allowed(path)


# The real guard is exercised on a disposable clone of this repository, never on
# the working checkout: an interrupted run can then never leave a frozen file
# modified or a probe file behind in the real tree.
@pytest.fixture(scope="module")
def clone(tmp_path_factory):
    import subprocess
    dest = tmp_path_factory.mktemp("guard_clone") / "repo"
    # core.autocrlf=false: check files out exactly as committed (LF), whatever
    # the machine's global setting; a CRLF checkout on Windows made the probes
    # fail for line endings, not content (readiness audit 2026-10-01, D9).
    subprocess.run(["git", "clone", "-q", "--shared", "-c", "core.autocrlf=false", str(ROOT), str(dest)], check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    subprocess.run(["git", "checkout", "-q", "--detach", head], cwd=dest, check=True)
    return dest


def _run_guard_on(clone, monkeypatch):
    monkeypatch.setattr(m37, "ROOT", clone)
    m37.test_m36_and_frozen_files_unchanged()


@pytest.mark.parametrize("relpath", [
    "uri_v1/memory/_m39_guard_probe.py",      # new file in frozen M36 scope
    "uri_core/_m39_guard_probe.py",           # live-app scope
    "fixtures/m39_office_probe/x.txt",        # look-alike of the M39 fixture prefix
    "scripts/m39_guard_probe.py",             # M39-looking script not on the exact list
    "scripts/m39_office_benchmark.pyx",       # longer name than an exact entry
])
def test_guard_still_fails_for_an_untracked_file_outside_the_entry(clone, monkeypatch, relpath):
    target = clone / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# probe\n")
    try:
        with pytest.raises(AssertionError) as info:
            _run_guard_on(clone, monkeypatch)
        assert relpath in str(info.value)
    finally:
        target.unlink()


def test_guard_still_fails_for_a_changed_frozen_file(clone, monkeypatch):
    target = clone / "uri_v1" / "memory" / "contracts.py"
    original = target.read_bytes()
    target.write_bytes(original + b"\n# m39 guard probe\n")
    try:
        with pytest.raises(AssertionError) as info:
            _run_guard_on(clone, monkeypatch)
        assert "uri_v1/memory/contracts.py" in str(info.value)
    finally:
        target.write_bytes(original)


# -- the allowlisted package cannot reach arbitrary files -------------------------------------------

# Unambiguous file-I/O method names, whatever the receiver.
_FILE_IO_METHODS = {"read_bytes", "read_text", "write_bytes", "write_text", "unlink", "rmdir", "rename",
                    "rmtree", "copyfile", "copytree", "symlink_to", "touch", "listdir", "scandir", "iterdir",
                    "rglob", "glob", "chmod"}
# Ambiguous names (str.replace, ast.walk, ...) count only on the os module.
_OS_FILE_IO = {"open", "replace", "remove", "walk", "rename", "makedirs", "mkdir", "unlink", "rmdir"}
_FILE_IO_MODULES = {"shutil", "subprocess", "io", "tempfile", "glob", "fileinput"}
# The one sanctioned exception: bootstrap creates URI's own private data
# directories (memory log, run store, scratch) under --data-dir, never user files.
_ALLOWED = {("bootstrap.py", "mkdir")}


def test_office_package_does_no_direct_file_io():
    """Every read/write of user files in uri_v1/office goes through frozen
    M36/M37 (SourceRegistry, read_bound, Workspace), which confine it to the
    authorized folder. The package itself opens nothing."""
    for path in (ROOT / "uri_v1" / "office").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                fn = node.func
                if isinstance(fn, ast.Name):
                    assert fn.id != "open", (path.name, node.lineno)
                elif isinstance(fn, ast.Attribute):
                    on_os = isinstance(fn.value, ast.Name) and fn.value.id == "os"
                    bad = fn.attr in _FILE_IO_METHODS or (on_os and fn.attr in _OS_FILE_IO) or fn.attr == "mkdir"
                    if bad and (path.name, fn.attr) not in _ALLOWED:
                        raise AssertionError((path.name, node.lineno, fn.attr))
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
                for mod in mods:
                    assert mod.split(".")[0] not in _FILE_IO_MODULES, (path.name, node.lineno, mod)


def _start(env, raw):
    parsed = req.parse(raw)
    if not parsed.ok:
        return None
    return env.session.start(raw, session_id="s-guard", turn_id=uuid.uuid4().hex, trace_id=uuid.uuid4().hex, parsed=parsed)


def test_a_file_outside_the_authorized_folder_is_never_bound(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    outside = tmp_path / "outside"; outside.mkdir()
    (outside / "secret.py").write_text("SECRET = 1\n")
    make_workbook(outside / "secret.xlsx", SALES)

    for raw in (f"make {outside / 'secret.py'} work with sales.xlsx",
                "make ../outside/secret.py work with sales.xlsx",
                "make secret.py work with sales.xlsx"):
        step = _start(env, raw)
        if step is None:
            continue  # refused at parse: nothing opened, nothing bound
        answer = step
        for _ in range(3):
            asks = [rb for rb in answer.roles.values() if getattr(rb, "ask", False)] if answer.kind == "CLARIFY" else []
            if not asks:
                break
            rb = asks[0]
            name = str(outside / "secret.py") if rb.ref_key == "script" else "sales.xlsx"
            answer = env.session.answer(answer.task_id, name, session_id="s-guard", turn_id=uuid.uuid4().hex,
                                        trace_id=uuid.uuid4().hex, round_id=rb.contract_id)
        assert answer.kind not in ("AWAITING_APPROVAL", "COMPLETED", "NOTHING_TO_WRITE", "ESCALATION_PROPOSAL"), (raw, answer)
        head = env.log.load().task(answer.task_id)
        known = {l.source_id for l in env.sources.scan().locators}
        for ref in head.payload["references"]:
            assert ref["source_id"] in known  # only files inside the authorized folder
    assert (outside / "secret.py").read_text() == "SECRET = 1\n"
