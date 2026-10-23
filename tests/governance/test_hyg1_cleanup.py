"""HYG-1: the governance conftest removes the rollback trees a test creates, keeps evidence when the test failed, and
repeated runs leave nothing behind that whole-repository collection would import."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
_spec = importlib.util.spec_from_file_location("governance_conftest", HERE / "conftest.py")
C = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(C)


def _fake_work(tmp_path):
    work = tmp_path / "work" / "c1"
    (work / "checkpoints").mkdir(parents=True)
    (work / "checkpoints" / "final-closure-20261005-phase1.zip").write_bytes(b"fixture")   # pre-existing, kept
    (work / "review5").mkdir()                                                              # not ours, kept
    return work


def _make(work):
    tree = work / "rollback_hyg1_abc"
    (tree / "uri_core").mkdir(parents=True)
    (tree / "test_c1_source_pin.py").write_text("def test_x():\n    assert True\n", encoding="utf-8")
    (work / "negative_restore_hyg1_def").mkdir()
    (work / "checkpoints" / "negative_hyg1_123.zip").write_bytes(b"zip")
    return {tree, work / "negative_restore_hyg1_def", work / "checkpoints" / "negative_hyg1_123.zip"}


def test_hyg1_a_passing_test_removes_only_what_it_created(tmp_path):
    work = _fake_work(tmp_path)
    before = C.snapshot(work)
    made = _make(work)
    assert C.snapshot(work) - before == made
    out = C.retire(C.snapshot(work) - before, failed=False, evidence_dir=tmp_path / "evidence")
    assert sorted(out["removed"]) == sorted(str(p) for p in made) and out["kept"] == []
    assert not any(p.exists() for p in made) and not (tmp_path / "evidence").exists()
    assert (work / "checkpoints" / "final-closure-20261005-phase1.zip").is_file() and (work / "review5").is_dir()


def test_hyg1_a_failed_test_keeps_the_evidence_then_removes_it(tmp_path):
    work = _fake_work(tmp_path)
    before = C.snapshot(work)
    made = _make(work)
    ev = tmp_path / "evidence"
    out = C.retire(C.snapshot(work) - before, failed=True, evidence_dir=ev)
    assert not any(p.exists() for p in made)
    assert (ev / "rollback_hyg1_abc" / "test_c1_source_pin.py").is_file()
    assert (ev / "negative_hyg1_123.zip").read_bytes() == b"zip"
    manifest = json.loads((ev / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["kept"]) == 3 and len(out["kept"]) == 3


def test_hyg1_a_real_rehearsal_made_during_a_test_is_not_taken(tmp_path):
    """P0-HYG-A: the tools' own default names (rollback_<hex>, negative_<hex>.zip) are never cleanup candidates."""
    work = _fake_work(tmp_path)
    before = C.snapshot(work)
    real = work / ("rollback_" + "0" * 32)
    (real / "uri_core").mkdir(parents=True)
    (work / "checkpoints" / "negative_operator.zip").write_bytes(b"real")
    made = _make(work)
    assert C.snapshot(work) - before == made
    C.retire(C.snapshot(work) - before, failed=False, evidence_dir=tmp_path / "evidence")
    assert real.is_dir() and (work / "checkpoints" / "negative_operator.zip").is_file()


@pytest.mark.skipif(not (ROOT / "work/c1/checkpoints/final-closure-20261005-phase1.zip").is_file(),
                    reason="frozen checkpoint fixture not installed: run scripts/fcv_install_phase1_fixtures.py (FCV-09)")
def test_hyg1_repeated_rollback_test_runs_leave_nothing_to_collect():
    before = C.snapshot()
    for _ in range(2):
        r = subprocess.run([sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
                            "tests/governance/test_fcv11_guarded_rollback.py",
                            "tests/governance/test_fcv01_rollback_amendment.py"],
                           cwd=ROOT, capture_output=True, text=True, timeout=900)
        assert r.returncode == 0, r.stdout[-2000:]
        assert C.snapshot() == before, sorted(str(p) for p in C.snapshot() - before)
