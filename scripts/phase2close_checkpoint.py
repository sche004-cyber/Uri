"""Cut the Phase 2 CLOSURE candidate checkpoint (Phase 2A + 2B + 2C + 2D + UI/operations + closure material) OUTSIDE
the tree, with a sidecar manifest. Same discipline as `phase2ops_checkpoint.py`: refuses to overwrite, hashes every
file. Adds the closure globs (tests/phase2close, PHASE2CLOSE docs, phase2close scripts, the development ledger, the
handoff Dart file) and the two accepted-test files whose assertions changed for CAP-1.

Usage: python scripts/phase2close_checkpoint.py <out_dir> [<evidence_dir> ...]      (URI_CANDIDATE_SUFFIX optional)
"""
import datetime
import hashlib
import json
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOBS = ["uri_supervisor/**/*", "uri_supervisor_bridge/**/*", "tests/phase2a/**/*", "tests/phase2b/**/*", "tests/phase2c/**/*",
         "tests/phase2d/**/*", "tests/phase2ops/**/*",
         "docs/plans/PHASE2A_*", "docs/architecture/PHASE2A_*", "docs/plans/PHASE2B_*", "docs/architecture/PHASE2B_*",
         "docs/plans/PHASE2C_*", "docs/architecture/PHASE2C_*", "docs/plans/PHASE2D_*", "docs/architecture/PHASE2D_*",
         "docs/plans/PHASE2OPS_*", "docs/architecture/PHASE2OPS_*",
         "scripts/phase2b_*", "scripts/phase2c_*", "scripts/phase2d_*", "scripts/phase2ops_*",
         "scripts/run_uri_supervised_worker.py", "scripts/run_uri_phase2_server.py",
         "uri_ui/lib/services/supervised_runtime.dart", "uri_ui/lib/screens/tasks/supervised_execution_screen.dart",
         "uri_ui/test/supervised_*", "uri_ui/lib/app.dart",
         "tests/phase2close/**/*", "docs/plans/PHASE2CLOSE_*", "docs/architecture/PHASE2CLOSE_*", "scripts/phase2close_*",
         "docs/plans/URI_DEVELOPMENT_TODO.md", "uri_ui/lib/services/task_handoff.dart", "docs/plans/C6_UI_INTEGRATION_CONTRACT.md",
         "docs/plans/C7_CUTOVER_REQUIREMENTS.md"]
SKIP_SUFFIX = (".pyc", ".db", ".db-wal", ".db-shm")


def main(out_dir, *evidence_dirs):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().strftime("%Y%m%d")
    suffix = os.environ.get("URI_CANDIDATE_SUFFIX", "")
    if suffix and not suffix.replace("-", "").isalnum():
        raise SystemExit("BAD_SUFFIX")
    zpath = out_dir / f"phase2close-candidate-{stamp}{suffix}.zip"
    if zpath.exists() or zpath.with_suffix(".json").exists():
        raise SystemExit("CANDIDATE_EXISTS_REFUSING_TO_OVERWRITE: " + str(zpath))
    files = []
    for g in GLOBS:
        for p in sorted(ROOT.glob(g)):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in SKIP_SUFFIX:
                files.append(p)
    files = sorted(set(files))
    git = lambda *a: subprocess.run(["git", "-C", str(ROOT), *a], capture_output=True, text=True).stdout
    manifest = {}
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for p in files:
            rel = p.relative_to(ROOT).as_posix()
            data = p.read_bytes()
            manifest[rel] = hashlib.sha256(data).hexdigest()
            z.writestr(rel, data)
        ev_count = 0
        for evidence_dir in evidence_dirs:
            ev = Path(evidence_dir)
            for p in sorted(ev.rglob("*")):
                if p.is_file() and p.suffix not in SKIP_SUFFIX and "__pycache__" not in p.parts:
                    rel = "evidence/" + ev.name + "/" + p.relative_to(ev).as_posix()
                    data = p.read_bytes()
                    manifest[rel] = hashlib.sha256(data).hexdigest()
                    z.writestr(rel, data)
                    ev_count += 1
        z.writestr("GIT_HEAD.txt", git("rev-parse", "HEAD"))
        z.writestr("GIT_STATUS.txt", git("status", "--short"))
        z.writestr("MANIFEST.json", json.dumps(manifest, indent=1, sort_keys=True))
    sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
    side = {"path": str(zpath), "sha256": sha, "files": len(files), "evidence_files": ev_count,
            "base_commit": git("rev-parse", "--short", "HEAD").strip(), "head": git("rev-parse", "HEAD").strip(),
            "phase2ops_accepted_candidate_sha256": "9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a",
            "phase2d_accepted_candidate_sha256": "cbec537adffcd629d5b7aec907e50c8eeea6f83d8edf52e05b658deb0968688d",
            "phase2c_checkpoint_sha256": "4e8126539da1f0ede3989f6d307253b5b4267be4fe1ce4ae405d19e761840f71",
            "phase1_frozen_checkpoint_sha256": "31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7",
            "status": "PHASE 2 CLOSURE CANDIDATE, NOT FROZEN, NOT CUT OVER; opt-in per installation; human acceptance, "
                      "client-profile login, EXE-1 decision and physical power loss PENDING (owner)"}
    zpath.with_suffix(".json").write_text(json.dumps(side, indent=1))
    print(json.dumps(side, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], *sys.argv[2:])
