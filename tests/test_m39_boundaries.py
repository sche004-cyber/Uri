"""Q-O5: boundaries and regression (M39 plan §5.5).

- `uri_v1/office` imports no `uri_core`/`uri_ui`/network client, and only the
  allowed subset of `uri_v1.*`.
- Every path changed since 5bbf738 (the M36-M38 freeze commit, code frozen at
  bd7c450, that M39 now builds on; repair round 3, re-audit R2-5) is an M39
  path. It was 610c8f8, the pre-freeze M38 audit-package commit.
- M36/M37/M38 and frozen files are byte-identical (git diff empty for them).
- `require_anchors()["ok"]` still holds (M33.3 frozen anchors unchanged).
- No workbook cell values or script source text leak into Memory beyond
  names/hashes/structure (plan §5.5 "Records scan").
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "5bbf738"  # M36-M38 freeze commit (frozen code bd7c450); was 610c8f8 before the freeze

# Never imported by uri_v1.office (plan §4.1).
BANNED = {"uri_core", "uri_ui", "requests", "httpx", "urllib3", "aiohttp", "socket"}
ALLOWED_URI_V1_TOP = {"memory", "results", "user_storage", "edge", "execution", "turn",
                     "reference_clarification", "evaluation", "office"}
# Only uri_v1.memory.contracts is imported directly from the memory package
# (mirrors tests/test_m37_edge_resolution.py's own edge/execution boundary
# check); everything else in uri_v1.memory goes through the public modules
# office/binding.py and office/flow.py already use (retrieval, uri_adapter, recorder, sources).
ALLOWED_MEMORY_SUBMODULES = {"uri_v1.memory.contracts", "uri_v1.memory.retrieval", "uri_v1.memory.recorder",
                            "uri_v1.memory.sources", "uri_v1.memory.log",
                            "uri_v1.memory.uri_adapter.envelope", "uri_v1.memory.uri_adapter.links"}


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            yield from (a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            yield node.module or ""


def test_office_import_boundaries():
    for path in (ROOT / "uri_v1" / "office").rglob("*.py"):
        for mod in _imports(path):
            top = mod.split(".")[0]
            assert top not in BANNED, (path, mod)
            if mod.startswith("uri_v1."):
                parts = mod.split(".")
                assert parts[1] in ALLOWED_URI_V1_TOP, (path, mod)
                if parts[1] == "memory" and len(parts) > 2:
                    assert mod in ALLOWED_MEMORY_SUBMODULES, (path, mod)


def test_office_never_calls_a_model_or_network_client():
    """No model/LLM call anywhere in this milestone's own logic (plan §4.1)."""
    forbidden_calls = ("openai", "anthropic", "urllib", "socket.socket", "subprocess.Popen")
    for path in (ROOT / "uri_v1" / "office").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        for token in forbidden_calls:
            assert token not in text, (path, token)


# Upstream repair commits, on the same branch, made by sessions other than this
# one (audit-driven fixes to M37/M38, not M39 edits): a path outside the M39
# allowlist is tolerated only if its *current* content is byte-identical to
# what one of these commits itself introduced -- i.e. it is legitimately at
# the repair's own version, not drifted from it by anything this package's
# code did. This is what plan §6 means by re-running Q-O5 after an
# audit-driven API change: the frozen-scope check is re-pointed at the new,
# audited version of those files instead of silently disabled.
KNOWN_UPSTREAM_REPAIRS = (
    "763d8e7",  # M37 repair: audit findings F-1..F-9 (uri_v1/edge/*, uri_v1/execution/{verify,workspace}.py)
    "b013dba",  # M38 repair: audit findings H-2/H-3/M-2..M-5 (uri_v1/execution/harness/*)
)


def _matches_some_upstream_repair(path: str) -> bool:
    working = (ROOT / path).read_bytes() if (ROOT / path).is_file() else None
    if working is None:
        return False
    for rev in KNOWN_UPSTREAM_REPAIRS:
        try:
            at_repair = subprocess.check_output(["git", "show", f"{rev}:{path}"], cwd=ROOT, stderr=subprocess.DEVNULL)
        except subprocess.CalledProcessError:
            continue
        if working == at_repair:
            return True
    return False


def test_m36_m37_m38_and_frozen_files_unchanged():
    changed = subprocess.check_output(["git", "diff", "--name-only", BASELINE, "--",
                                       "uri_v1", "uri_core", "uri_ui", "tests", "scripts", "fixtures"],
                                      cwd=ROOT, text=True).splitlines()
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--",
                                         "uri_v1", "uri_core", "uri_ui", "tests", "scripts", "fixtures"],
                                        cwd=ROOT, text=True).splitlines()
    allowed = ("uri_v1/office/", "tests/test_m39_", "tests/m39_office_support.py",
               "scripts/m39_", "fixtures/m39_office/", "docs/plans/M39_")
    offenders = [p for p in changed + untracked
                if not p.startswith(allowed) and not _matches_some_upstream_repair(p)]
    assert not offenders, offenders


def test_frozen_anchors_unchanged():
    from scripts.m33_3_r_anchors import require_anchors
    result = require_anchors()
    assert result["ok"] is True
    assert result["changed"] == []


def test_office_never_imports_a_workbook_library():
    """This package never opens a workbook itself (that stays in
    `uri_v1.execution.officefile` / `uri_v1.edge.scriptinfo`, both frozen
    M37 code it only calls); it only reads *script* bytes, for AST structure
    inspection (`acceptance_builder.py`), never workbook cell values."""
    for path in (ROOT / "uri_v1" / "office").rglob("*.py"):
        for mod in _imports(path):
            assert mod.split(".")[0] not in ("openpyxl", "pandas", "xlrd"), (path, mod)


def test_no_cell_values_or_script_text_in_telemetry_or_fixtures():
    """Dynamic records scan (plan §5.5): after the D1-D12 scenarios have run
    (tests/test_m39_flow.py), no Memory record or Edge telemetry event this
    package wrote contains a workbook cell value or the script's own source
    text -- only names, hashes and structure. Re-derives its own fixture
    scenario (D1) rather than depending on test collection order."""
    import _pytest.monkeypatch as mp
    from tests.m39_office_support import OfficeEnv, SALES, make_workbook, script as script_text
    from uri_v1.memory.contracts import plain
    from uri_v1.office import request as req

    monkeypatch = mp.MonkeyPatch()
    try:
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            env = OfficeEnv(tmp, monkeypatch, with_harness=False)
            make_workbook(env.root / "sales.xlsx", SALES)
            script_bytes = script_text(column="amount")
            env.write("report.py", script_bytes)
            parsed = req.parse("make report.py work with sales.xlsx")
            turn_id, trace_id = env.turn()
            env.session.start("make report.py work with sales.xlsx", session_id="s", turn_id=turn_id,
                              trace_id=trace_id, parsed=parsed)

            forbidden = [b"North", b"South"]  # distinctive SALES cell values (short/numeric tokens dropped: they
                                              # trivially collide with substrings of hex ids/hashes)
            index = env.log.load()
            for record in index.records.values():
                blob = repr(plain(record.payload)).encode("utf-8", "replace")
                for token in forbidden:
                    assert token not in blob, (record.record_id, token)
                assert script_bytes not in blob.decode("utf-8", "replace")
            for event in env.telemetry.events():
                blob = repr(event).encode("utf-8", "replace")
                for token in forbidden:
                    assert token not in blob, (event, token)
    finally:
        monkeypatch.undo()
