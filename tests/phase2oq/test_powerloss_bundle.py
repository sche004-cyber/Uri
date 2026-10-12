"""PA-11 preparation: the guest bundle is self-sufficient (stdlib + its own files) and matches the tree byte for byte.
The SIMULATED run below is a plumbing check of the extracted bundle only; it qualifies nothing."""
import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("plb", ROOT / "scripts" / "phase2oq_powerloss_bundle.py")
plb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(plb)


def test_bundle_matches_the_tree_and_runs_the_harness_from_its_own_copy(tmp_path):
    m = plb.build(tmp_path / "bundle.zip")
    z = zipfile.ZipFile(tmp_path / "bundle.zip")
    names = set(z.namelist())
    assert {"scripts/phase2close_powerloss_harness.py", "tests/phase2a/helpers/fake_executor.py", "uri_supervisor/supervisor.py",
            "uri_supervisor/winproc.py", "guest/install_guest_task.ps1", "MANIFEST.json"} <= names
    manifest = json.loads(z.read("MANIFEST.json"))
    for rel, digest in manifest["files"].items():
        assert hashlib.sha256(z.read(rel)).hexdigest() == digest
        if not rel.startswith("guest/"):
            assert (ROOT / rel).read_bytes() == z.read(rel)
    assert "IAmInsideTheThrowawayVM" in z.read("guest/install_guest_task.ps1").decode()
    guest = tmp_path / "guest"
    z.extractall(guest)
    out = tmp_path / "sim"
    r = subprocess.run([sys.executable, "-I", "-B", str(guest / "scripts/phase2close_powerloss_harness.py"), "simulate",
                        "--iterations", "2", "--out", str(out), "--min-s", "1", "--max-s", "2"],
                       capture_output=True, text=True, timeout=300, cwd=str(guest))
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    summary = json.loads((out / "summary.json").read_text())
    assert summary["verdict"] == "SIMULATED_ONLY_NOT_A_QUALIFICATION" and summary["passed"] == 2
    rows = json.loads((out / "iterations.json").read_text())
    assert all(r_["os_unclean_shutdown"] is None for r_ in rows)          # a simulated guest carries no OS witness
