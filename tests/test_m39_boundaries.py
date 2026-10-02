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


# Audit 736464a N1: the KNOWN_UPSTREAM_REPAIRS exemption (763d8e7, b013dba)
# is gone. It let a frozen M37/M38 file be rolled back to its pre-freeze
# repair-commit bytes and still pass. Since BASELINE is the freeze commit
# 5bbf738, every frozen file must match it exactly; only M39 paths and the
# hash-pinned authorized edit below may differ.


def test_m36_m37_m38_and_frozen_files_unchanged():
    changed = subprocess.check_output(["git", "diff", "--name-only", "--no-renames", BASELINE, "--",
                                       "uri_v1", "uri_core", "uri_ui", "tests", "scripts", "fixtures"],
                                      cwd=ROOT, text=True).splitlines()
    untracked = subprocess.check_output(["git", "ls-files", "--others", "--exclude-standard", "--",
                                         "uri_v1", "uri_core", "uri_ui", "tests", "scripts", "fixtures"],
                                        cwd=ROOT, text=True).splitlines()
    allowed = ("uri_v1/office/", "tests/test_m39_", "tests/m39_office_support.py",
               "scripts/m39_", "fixtures/m39_office/", "docs/plans/M39_")
    offenders = [p for p in changed + untracked
                if not p.startswith(allowed) and not _is_authorized_frozen_edit(p)
                and not _is_desktop_recovery_edit(p)]
    assert not offenders, offenders


# Frozen files edited with the User's explicit authorization, pinned to the
# exact authorized content: any further change to them is an offender again.
# - tests/test_m37_edge_resolution.py: minimal M39 allowlist entry in
#   test_m36_and_frozen_files_unchanged (Chetan, 2026-09-29 05:21 UTC).
#
# Pinned by git blob id (what `git hash-object` computes for the working file),
# not by a hash of the raw bytes: git applies the checkout's own line-ending
# conversion first, so a Windows checkout or clone with core.autocrlf=true
# (CRLF on disk, same committed content) matches, while any real content
# change does not. Was sha256 f288b194... of the LF bytes, which failed on
# such checkouts (integration readiness audit 2026-10-01, D9).
AUTHORIZED_FROZEN_EDITS = {
    # Re-pinned for the desktop recovery allowlist (Chetan, 2026-10-01 18:21/18:24 UTC):
    # was a6bb874c... / c51c46c1...; the M36 guard gains the same exact-file exemption.
    "tests/test_m37_edge_resolution.py": "f2a40db7684c5eb98a39177d44337d588b09f012",
    "tests/test_m37_frozen_guard_pin.py": "d0433c6e8ae40df2fa48fca40496932f0c9f8c6a",
    "tests/test_m36_memory_adversarial.py": "1d988355d3d2796c6c37e236544548d47e89624e",
}

# Desktop recovery / Edge-first allowlist: exact uri_core/uri_ui files pinned by blob in
# desktop_recovery_allowlist.py, whose own content is pinned here. See
# docs/plans/DESKTOP_RECOVERY_ALLOWLIST.md.
DESKTOP_ALLOWLIST_MODULE = ("desktop_recovery_allowlist.py", "0d78d54350bc91c44dbec3aa42fc622007b49b2e")


def _is_desktop_recovery_edit(path: str) -> bool:
    module, pin = DESKTOP_ALLOWLIST_MODULE
    if not (ROOT / module).is_file():
        return False
    if subprocess.check_output(["git", "hash-object", "--", module], cwd=ROOT, text=True).strip() != pin:
        return False
    from desktop_recovery_allowlist import is_desktop_recovery_edit
    return is_desktop_recovery_edit(ROOT, path)


def _is_authorized_frozen_edit(path: str) -> bool:
    expected = AUTHORIZED_FROZEN_EDITS.get(path)
    target = ROOT / path
    if expected is None or not target.is_file():
        return False
    blob = subprocess.check_output(["git", "hash-object", "--", path], cwd=ROOT, text=True).strip()
    return blob == expected


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
