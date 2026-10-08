"""Re-hash every file in the Phase 1 freeze inventory and compare with the live tree.

Reads work/c1/review6/checkpoint.json (the closure review's inventory of the 121 archived
files) and reports any difference. Also verifies the canonical checkpoint archive hash.
Read-only.
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "work/c1/checkpoints/final-closure-20261005-phase1.zip"
EXPECTED = "31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7"
# The closure report's own section 11 was written after archiving (documented in the report).
KNOWN_POST_ARCHIVE = {"docs/plans/PHASE1_FINAL_CLOSURE_REPORT.md"}


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    inv = json.loads((ROOT / "work/c1/review6/checkpoint.json").read_text(encoding="utf-8"))
    files = inv.get("inventory") or inv.get("files")
    rows = files.items() if isinstance(files, dict) else [(f["path"], f["sha256"]) for f in files]
    diffs, checked = [], 0
    for rel, digest in rows:
        if isinstance(digest, dict):
            digest = digest.get("sha256")
        p = ROOT / rel
        live = sha(p) if p.exists() else None
        checked += 1
        if live != digest and rel not in KNOWN_POST_ARCHIVE:
            diffs.append({"path": rel, "expected": digest, "live": live})
    archive = sha(ARCHIVE)
    out = {"checked": checked, "unexpected_differences": diffs, "archive_sha256": archive,
           "archive_matches": archive == EXPECTED}
    print(json.dumps(out, indent=2))
    return 0 if not diffs and out["archive_matches"] else 1


if __name__ == "__main__":
    sys.exit(main())
