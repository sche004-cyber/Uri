"""Cut the Phase 2 candidate checkpoint (Phase 2A + Phase 2B material) OUTSIDE the tree, with a sidecar manifest.

Usage: python scripts/phase2b_checkpoint.py <out_dir>
Includes every untracked Phase 2 path (uri_supervisor, uri_supervisor_bridge, tests/phase2a, tests/phase2b,
docs/*/PHASE2A_*, docs/*/PHASE2B_*, scripts/phase2b_*) plus GIT_HEAD/GIT_STATUS. Excludes __pycache__ and ledgers.
"""
import datetime
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GLOBS = ["uri_supervisor/**/*", "uri_supervisor_bridge/**/*", "tests/phase2a/**/*", "tests/phase2b/**/*",
         "docs/plans/PHASE2A_*", "docs/architecture/PHASE2A_*", "docs/plans/PHASE2B_*", "docs/architecture/PHASE2B_*",
         "scripts/phase2b_*"]


def main(out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.date.today().strftime("%Y%m%d")
    zpath = out_dir / f"phase2b-candidate-{stamp}.zip"
    files = []
    for g in GLOBS:
        for p in sorted(ROOT.glob(g)):
            if p.is_file() and "__pycache__" not in p.parts and p.suffix not in (".pyc", ".db", ".db-wal", ".db-shm"):
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
        z.writestr("GIT_HEAD.txt", git("rev-parse", "HEAD"))
        z.writestr("GIT_STATUS.txt", git("status", "--short"))
        z.writestr("MANIFEST.json", json.dumps(manifest, indent=1, sort_keys=True))
    sha = hashlib.sha256(zpath.read_bytes()).hexdigest()
    side = {"path": str(zpath), "sha256": sha, "files": len(files), "base_commit": git("rev-parse", "--short", "HEAD").strip(),
            "head": git("rev-parse", "HEAD").strip(), "phase2a_checkpoint_sha256": "c0b82fa040a52c3e829e4951c1e89d7bffa1c0576bf362ffdfbef51e8314751c",
            "phase1_frozen_checkpoint_sha256": "31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7", "status": "CANDIDATE, NOT FROZEN"}
    (out_dir / f"phase2b-candidate-{stamp}.json").write_text(json.dumps(side, indent=1))
    print(json.dumps(side, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
