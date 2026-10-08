"""Phase 2D regression runner with an explicit, contamination-safe test scope.

Usage (from the Phase 2 worktree, .venv interpreter):
  python -I scripts/phase2d_regression.py phase2        # tests/phase2a tests/phase2b tests/phase2c tests/phase2d
  python -I scripts/phase2d_regression.py authority     # Phase 1 authority suites (134 baseline)
  python -I scripts/phase2d_regression.py phase1-full   # full Phase 1 repository suite, Phase 2 suites excluded
  python -I scripts/phase2d_regression.py <name> --log <file>
Every run uses scripts/phase2d_pytest.ini (norecursedirs: work/, evidence/, ...) plus explicit --ignore flags, so the
3,096-file rollback residue under work/c1 can never be collected again. Nothing under work/ or evidence/ is deleted.
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INI = ROOT / "scripts" / "phase2d_pytest.ini"
IGNORES = ["--ignore=work", "--ignore=evidence", "--ignore=uri_workspace", "--ignore=temp_evidence", "--ignore=reports",
           "--ignore=research_notes", "--ignore=graphify-out", "--ignore=uri_ui", "--ignore=.venv"]
AUTHORITY = ["test_c5_loop.py", "test_c2_uncertain_adversarial.py", "test_c5_intent_adversarial.py", "test_c4_harness.py",
             "test_phase1_fail_closed.py", "test_intent_discovery_unit.py", "test_c5_intent_discovery.py", "test_c7_rollback_boundary.py"]
PHASE2 = ["tests/phase2a", "tests/phase2b", "tests/phase2c", "tests/phase2d", "tests/phase2ops"]
KNOWN_BASELINE_FAILURES = [  # the 11 e8e3b65 failures recorded in the Phase 1 final closure report (pre-existing)
    "step3_test.py::test_drive", "step4_test.py::test_download", "test_capability_directory.py", "test_m20_feasibility_validation.py",
    "test_m20_recovery_loop.py", "test_m20_semantic_interpreter_resilience.py", "test_orchestrator_session_workflow.py",
    "test_usage_import_boundary.py", "test_workflow_restart_recovery.py"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("suite", choices=["phase2", "authority", "phase1-full", "phase2d"])
    ap.add_argument("--log", default=None)
    ap.add_argument("extra", nargs="*")
    a = ap.parse_args()
    if a.suite == "phase2":
        targets = PHASE2
    elif a.suite == "phase2d":
        targets = ["tests/phase2d"]
    elif a.suite == "authority":
        targets = AUTHORITY
    else:
        targets = ["."] + ["--ignore=" + t for t in PHASE2]
    cmd = [sys.executable, "-I", "-m", "pytest", "-c", str(INI), "--rootdir", str(ROOT), "-q", "-rfEs", *IGNORES, *targets, *a.extra]
    print("RUN", " ".join(cmd), flush=True)
    t0 = time.time()
    if a.log:
        with open(a.log, "wb") as log:
            log.write((" ".join(cmd) + "\n").encode())
            log.flush()
            r = subprocess.run(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT)
            log.write(f"\nEXIT={r.returncode} DURATION_S={round(time.time() - t0, 1)}\n".encode())
    else:
        r = subprocess.run(cmd, cwd=str(ROOT))
    print(f"EXIT={r.returncode} DURATION_S={round(time.time() - t0, 1)}")
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
