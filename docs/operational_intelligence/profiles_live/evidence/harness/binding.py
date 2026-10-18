"""Source-state binding for every live harness (review R2-02): which code ran.

The runtime a harness uses must be a materialized runtime whose receipt names the candidate commit, and every file the
materializer copied must still be byte-identical in the runtime AND in the candidate checkout, whose HEAD and
porcelain status are recorded too. Harnesses refuse to run when the binding is not clean.
The binding is taken once, at the start of a run. It does not cover base or overlay files outside the receipt (none
of them changes in this milestone).
"""
import hashlib
import json
import subprocess
from pathlib import Path

SRC = Path(r"D:\uri-dev\uri-runtime-profiles-integ")
TOOLS = Path(__file__).resolve().parent
EVIDENCE_ONLY = "docs/operational_intelligence/profiles_live/"


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
    # Review R3-03: the runtime must come from the candidate HEAD, or from an ancestor whose only differences to HEAD
    # are evidence documents (an evidence-only commit on top of the tested code does not change what runs).
    since = subprocess.check_output(["git", "diff", "--name-only", receipt["candidate_head"], head], cwd=SRC,
                                    text=True).split()
    out["changed_since_materialization"] = since
    out["code_matches_head"] = all(x.startswith(EVIDENCE_ONLY) for x in since)
    # The harness scripts that ran, hashed at run time (not only the later copies in the evidence folder).
    out["harness_sha256"] = {f.name: _sha(f) for f in sorted(TOOLS.iterdir()) if f.suffix in (".py", ".sh", ".dart")}
    out["ok"] = (not bad and receipt.get("head_is_base") is True and not porcelain.strip()
                 and out["code_matches_head"])
    return out


def require(runtime_root) -> dict:
    b = bind(runtime_root)
    if not b["ok"]:
        raise SystemExit("BINDING_NOT_CLEAN: " + json.dumps(b))
    return b
