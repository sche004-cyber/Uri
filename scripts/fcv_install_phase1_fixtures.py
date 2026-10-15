"""Copy the Phase 1 suite's untracked checkpoint fixtures into a disposable runtime, by exact hash (FCV-09).

    python scripts/fcv_install_phase1_fixtures.py <runtime-root> [--from <directory holding the fixtures>]

Each fixture listed in docs/governance/fcv_recovery/PHASE1_TEST_FIXTURES.json is copied only when its bytes have the
recorded SHA-256; an existing destination must already hold those exact bytes. Nothing else is written.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

LIST = Path(__file__).resolve().parents[1] / "docs/governance/fcv_recovery/PHASE1_TEST_FIXTURES.json"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("runtime")
    ap.add_argument("--from", dest="source", default=None)
    a = ap.parse_args(argv)
    result = {}
    for fx in json.loads(LIST.read_text(encoding="utf-8"))["fixtures"]:
        src = Path(a.source) / Path(fx["path"]).name if a.source else Path(fx["origin"])
        dest = Path(a.runtime) / fx["path"]
        if dest.exists():
            result[fx["path"]] = "PRESENT_EXACT" if sha(dest) == fx["sha256"] else "PRESENT_MISMATCH"
            continue
        if not src.is_file() or sha(src) != fx["sha256"]:
            result[fx["path"]] = "SOURCE_MISSING_OR_MISMATCH"
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)
        result[fx["path"]] = "INSTALLED" if sha(dest) == fx["sha256"] else "COPY_MISMATCH"
    print(json.dumps(result, indent=1))
    return 0 if all(v in ("INSTALLED", "PRESENT_EXACT") for v in result.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
