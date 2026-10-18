"""Source-state binding for every live harness (review R2-02): which code ran.

The runtime a harness uses must be a materialized runtime whose receipt names the candidate commit, and every file the
materializer copied must still be byte-identical in the runtime AND in the candidate checkout, whose HEAD and
porcelain status are recorded too. Harnesses refuse to run when the binding is not clean.
"""
import hashlib
import json
import subprocess
from pathlib import Path

SRC = Path(r"D:\uri-dev\uri-runtime-profiles-integ")


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def bind(runtime_root) -> dict:
    rt = Path(runtime_root)
    receipt = json.loads((rt / "OI_MATERIALIZATION_RECEIPT.json").read_text())
    bad = [rel for rel, d in receipt["oi_files_copied"].items()
           if _sha(rt / rel) != d or not (SRC / rel).exists() or _sha(SRC / rel) != d]
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=SRC, text=True).strip()
    porcelain = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=no"], cwd=SRC, text=True)
    out = {"runtime_root": str(rt), "materialized_from": receipt["candidate_head"], "candidate_head_now": head,
           "candidate_tracked_changes": porcelain.splitlines(), "runtime_files_checked": len(receipt["oi_files_copied"]),
           "mismatched": bad[:20]}
    out["ok"] = not bad and receipt.get("head_is_base") is True and not porcelain.strip()
    return out


def require(runtime_root) -> dict:
    b = bind(runtime_root)
    if not b["ok"]:
        raise SystemExit("BINDING_NOT_CLEAN: " + json.dumps(b))
    return b
