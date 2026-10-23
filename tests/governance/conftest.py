"""HYG-1: governance rollback tests clean up the trees they write under work/c1.

The FCV-01 / FCV-11 rollback tests restore the Phase 1 checkpoint into `work/c1/rollback_*` and
`work/c1/negative_restore_*`, and derive negative checkpoints as `work/c1/checkpoints/negative_*.zip`. Those trees hold
`test_*.py` files of the restored Phase 1 tree, so whole-repository collection used to import them (196 collection
errors on the AP-6 integration checkout, finding HYG-1).

After every test in this folder, the entries that test created (and only those) are removed, whether the test passed
or failed. When the test failed they are first copied into the test's own pytest `tmp_path` (`hyg1-evidence/`, with a
`manifest.json`), which pytest keeps for the last three runs, so failure evidence survives without accumulating.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / "work" / "c1"
# (sub-folder of work/c1, glob) of what the rollback tests create
PATTERNS = (("", "rollback_*"), ("", "negative_restore_*"), ("checkpoints", "negative_*.zip"))


def snapshot(work: Path = WORK) -> set[Path]:
    out = set()
    for sub, pattern in PATTERNS:
        base = work / sub if sub else work
        if base.is_dir():
            out.update(base.glob(pattern))
    return out


def retire(paths, failed: bool, evidence_dir: Path) -> dict:
    """Remove `paths`; when `failed`, copy them into `evidence_dir` first. Returns what was kept and removed."""
    kept, removed = [], []
    for p in sorted(paths):
        if failed:
            target = evidence_dir / p.name
            evidence_dir.mkdir(parents=True, exist_ok=True)
            if p.is_dir():
                shutil.copytree(p, target, dirs_exist_ok=True)
            elif p.exists():
                shutil.copy2(p, target)
            kept.append({"from": str(p), "to": str(target)})
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)
        removed.append(str(p))
    if failed and kept:
        (evidence_dir / "manifest.json").write_text(json.dumps({"kept": kept}, indent=1), encoding="utf-8")
    return {"kept": kept, "removed": removed}


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "_hyg1_" + rep.when, rep)


@pytest.fixture(autouse=True)
def _clean_rollback_work(request, tmp_path):
    before = snapshot()
    yield
    new = snapshot() - before
    if not new:
        return
    failed = any(getattr(request.node, "_hyg1_" + w, None) is not None and getattr(request.node, "_hyg1_" + w).failed
                 for w in ("setup", "call"))
    retire(new, failed, tmp_path / "hyg1-evidence")
