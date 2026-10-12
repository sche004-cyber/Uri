"""Read-only archive and gate checks for the independent round-2 review."""
import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = ROOT / "evidence"
TREE = ROOT / "uri-agent"
NAMES = {
    "r1": "phase2oq-candidate-20261008.zip",
    "r2": "phase2oq-candidate-20261008-b.zip",
    "f": "phase2close-candidate-20261008-f.zip",
    "r7": "phase2ops-candidate-20261008-r6.zip",
}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def archive(name):
    path = EVIDENCE / name
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("MANIFEST.json"))
        names = {x for x in z.namelist() if not x.endswith("/") and x not in
                 {"MANIFEST.json", "GIT_HEAD.txt", "GIT_STATUS.txt"}}
        assert names == set(manifest), (name, "membership", len(names), len(manifest))
        bad_payload = [x for x in manifest if sha(z.read(x)) != manifest[x]]
        bad_live = []
        for x in manifest:
            live = (EVIDENCE / x if x.startswith("evidence/") else TREE / x)
            if x.startswith("evidence/"):
                live = ROOT / x
            if name == NAMES["r2"] and (not live.is_file() or sha(live.read_bytes()) != manifest[x]):
                bad_live.append(x)
        print(name, "sha256", sha(path.read_bytes()), "entries", len(manifest), "payload_mismatch", bad_payload,
              "live_mismatch", bad_live)
        return manifest

m = {k: archive(v) for k, v in NAMES.items()}
for old in ("r1", "f", "r7"):
    a, b = m[old], m["r2"]
    added = sorted(set(b) - set(a))
    removed = sorted(set(a) - set(b))
    changed = sorted(x for x in set(a) & set(b) if a[x] != b[x])
    print("delta", old, "added", len(added), "changed", len(changed), "removed", len(removed))
    if old == "r1":
        print("r1 changed", json.dumps(changed))
        print("r1 added", json.dumps(added))
        print("r1 removed", json.dumps(removed))

# The acceptance predicate does not bind pass/skip IDs. Two hypothetical test
# result maps with the same failure IDs and counts demonstrate its blind spot.
baseline = {"failed": {f"f{i}" for i in range(11)},
            "passed": {f"p{i}" for i in range(2675)},
            "skipped": {f"s{i}" for i in range(12)}}
missing_replaced = {"failed": set(baseline["failed"]),
                    "passed": (baseline["passed"] - {"p0"}) | {"new"},
                    "skipped": set(baseline["skipped"])}
lost_pass_swap = {"failed": set(baseline["failed"]),
                  "passed": (baseline["passed"] - {"p0"}) | {"s0"},
                  "skipped": (baseline["skipped"] - {"s0"}) | {"p0"}}
def predicate(x):
    return (x["failed"] == baseline["failed"] and sum(map(len, x.values())) == 2698
            and len(x["failed"]) == 11 and len(x["passed"]) >= 2675)
print("gate predicate baseline/missing_replaced/lost_pass_swap",
      predicate(baseline), predicate(missing_replaced), predicate(lost_pass_swap))
