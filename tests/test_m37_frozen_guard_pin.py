"""M37-L3: the frozen M37 scope guard now proves the frozen M37/M38 paths intact.

Authorized frozen-test edit (User, Chetan, 2026-09-29 13:57 UTC, "Fix in M37"):
tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged also diffs
every pre-freeze M37/M38 path against the freeze commit 5bbf738, so an edit under
uri_v1/edge/ or uri_v1/execution/ (or the other M37/M38 entries) no longer passes.

This file:
- pins the guard file to its authorized content (SHA-256, line endings
  normalized so a Windows CRLF checkout hashes the same);
- proves the exemption is exactly the guard file and this pin;
- exercises the real guard on a disposable clone, never on the working
  checkout, against changed, added, deleted, renamed and committed tampering.
  Each probe checks what the tampering adds to the clone's offenders, so it
  stays meaningful on a branch whose guard already fails for its own paths.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

import pytest

import tests.test_m37_edge_resolution as m37

ROOT = Path(__file__).resolve().parents[1]
GUARD = "tests/test_m37_edge_resolution.py"
# M39 line (User, Chetan, 2026-10-01 13:10 UTC, "Update pin"): the guard file here carries both
# authorized edits, the re-frozen M37-L3 fix (b94e76f0... on the M37 line) plus the existing M39
# entry (2026-09-29 05:21 UTC), so the pin is the hash of that combined content.
GUARD_SHA256 = "fda0d60025abd5c3d6fb9f3716cf6db8982179092a04eff64b8d42c361e15686"


def _normalized_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def test_guard_file_is_pinned_to_its_authorized_content():
    assert _normalized_sha256(ROOT / GUARD) == GUARD_SHA256


def test_freeze_commit_and_exemption_are_exact():
    assert m37.FREEZE_COMMIT == "5bbf73856011fac7f8abad6970e664616a4c01ec"
    assert m37.FREEZE_EXEMPT == {GUARD, "tests/test_m37_frozen_guard_pin.py"}
    assert m37.FROZEN_M37_M38 == ("uri_v1/edge/", "uri_v1/execution/", "tests/test_m37_", "tests/test_m38_",
                                  "tests/m37_edge_support.py", "tests/m38_harness_support.py", "scripts/m37_",
                                  "scripts/m38_", "fixtures/m37_edge/", "fixtures/m38_harness/")
    # Frozen code at bd7c450 is the tree of the freeze commit (governance-only commit on top).
    assert subprocess.run(["git", "diff", "--quiet", "bd7c450", m37.FREEZE_COMMIT, "--", "uri_v1"], cwd=ROOT).returncode == 0


@pytest.fixture(scope="module")
def clone(tmp_path_factory):
    dest = tmp_path_factory.mktemp("m37_guard_clone") / "repo"
    subprocess.run(["git", "clone", "-q", "--shared", str(ROOT), str(dest)], check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    subprocess.run(["git", "checkout", "-q", "--detach", head], cwd=dest, check=True)
    return dest


def _offenders(clone, monkeypatch):
    monkeypatch.setattr(m37, "ROOT", clone)
    return set(m37.frozen_scope_offenders())


def _reset(clone):
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    subprocess.run(["git", "checkout", "-q", "--detach", head], cwd=clone, check=True)
    subprocess.run(["git", "reset", "-q", "--hard", head], cwd=clone, check=True)
    subprocess.run(["git", "clean", "-q", "-fdx", "--", "uri_v1", "tests", "scripts", "fixtures"], cwd=clone, check=True)


@pytest.fixture
def baseline(clone, monkeypatch):
    """Offenders of the untouched clone (none on the frozen line itself)."""
    _reset(clone)
    yield _offenders(clone, monkeypatch)
    _reset(clone)


# One frozen file per pre-freeze M37/M38 entry.
CHANGED = ["uri_v1/edge/resolver.py", "uri_v1/execution/verify.py", "uri_v1/execution/harness/adapters.py",
           "tests/test_m37_edge_execution.py", "tests/test_m38_harness.py", "tests/m37_edge_support.py",
           "tests/m38_harness_support.py", "scripts/m37_edge_qualification.py", "scripts/m38_harness_qualification.py"]


@pytest.mark.parametrize("relpath", CHANGED)
def test_guard_fails_for_a_changed_frozen_m37_m38_file(clone, monkeypatch, baseline, relpath):
    target = clone / relpath
    assert target.is_file(), relpath
    target.write_bytes(target.read_bytes() + b"\n# m37-l3 guard probe\n")
    assert _offenders(clone, monkeypatch) - baseline == {relpath}


@pytest.mark.parametrize("relpath", ["uri_v1/edge/_probe.py", "uri_v1/execution/planning/_probe.py",
                                     "fixtures/m37_edge/_probe.txt", "fixtures/m38_harness/_probe.txt",
                                     "scripts/m37_probe.py", "tests/test_m38_probe.py"])
def test_guard_fails_for_a_new_file_under_a_frozen_m37_m38_path(clone, monkeypatch, baseline, relpath):
    target = clone / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# probe\n")
    assert _offenders(clone, monkeypatch) - baseline == {relpath}


def test_guard_fails_for_a_deleted_frozen_file(clone, monkeypatch, baseline):
    (clone / "uri_v1/edge/repair.py").unlink()
    assert _offenders(clone, monkeypatch) - baseline == {"uri_v1/edge/repair.py"}


def test_guard_fails_for_a_committed_rename_between_frozen_paths(clone, monkeypatch, baseline):
    """A rename within the M37/M38 paths passes the M36-baseline check (both names are
    allowed there); against the freeze commit both names are reported, even once committed."""
    subprocess.run(["git", "mv", "uri_v1/edge/repair.py", "uri_v1/execution/repair.py"], cwd=clone, check=True)
    subprocess.run(["git", "-c", "user.name=probe", "-c", "user.email=probe@example.invalid", "commit", "-q",
                    "-m", "probe"], cwd=clone, check=True)
    assert _offenders(clone, monkeypatch) - baseline == {"uri_v1/edge/repair.py", "uri_v1/execution/repair.py"}


def test_the_guard_test_itself_fails_on_tampering(clone, monkeypatch, baseline):
    """End to end: the frozen test function itself raises for the tampered file (pytest
    shortens long assertion messages, so the offender is checked on the list it asserts)."""
    target = clone / "uri_v1/execution/verify.py"
    target.write_bytes(target.read_bytes() + b"\n# m37-l3 guard probe\n")
    monkeypatch.setattr(m37, "ROOT", clone)
    with pytest.raises(AssertionError):
        m37.test_m36_and_frozen_files_unchanged()
    assert "uri_v1/execution/verify.py" in m37.frozen_scope_offenders()


def test_guard_change_is_caught_by_the_pin_not_the_exemption(clone, monkeypatch, baseline):
    """The guard file is exempt from the freeze diff, so the pin is what holds it."""
    target = clone / GUARD
    target.write_bytes(target.read_bytes() + b"\n# m37-l3 guard probe\n")
    assert _offenders(clone, monkeypatch) == baseline  # exempt from the freeze diff ...
    assert _normalized_sha256(target) != GUARD_SHA256  # ... but no longer matches the pin


def test_pin_ignores_line_endings(tmp_path):
    lf = (ROOT / GUARD).read_bytes().replace(b"\r\n", b"\n")
    crlf = tmp_path / "crlf.py"
    crlf.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert _normalized_sha256(crlf) == _normalized_sha256(ROOT / GUARD) == GUARD_SHA256
