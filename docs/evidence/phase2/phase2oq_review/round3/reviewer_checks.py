"""Read-only archive checks and synthetic gate probes for independent round 3."""
import hashlib
import importlib.util
import json
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TREE = ROOT / "uri-agent"
EV = ROOT / "evidence"
OUT = Path(__file__).parent

def digest(data):
    return hashlib.sha256(data).hexdigest()

def load(name, live=False):
    path = EV / name
    with zipfile.ZipFile(path) as z:
        m = json.loads(z.read("MANIFEST.json"))
        payload = {n for n in z.namelist() if not n.endswith("/") and n not in ("MANIFEST.json", "GIT_HEAD.txt", "GIT_STATUS.txt")}
        bad = [n for n, h in m.items() if digest(z.read(n)) != h]
        live_bad = [n for n, h in m.items() if not ((ROOT / n) if n.startswith("evidence/") else (TREE / n)).is_file() or digest(((ROOT / n) if n.startswith("evidence/") else (TREE / n)).read_bytes()) != h] if live else []
        print(name, "sha256", digest(path.read_bytes()), "entries", len(m), "payload_member_mismatch", sorted(payload ^ set(m)), "bad_payload", bad, "bad_live", live_bad)
        return m

b = load("phase2oq-candidate-20261008-b.zip")
c = load("phase2oq-candidate-20261008-c.zip", True)
for name in ("phase2close-candidate-20261008-f.zip", "phase2ops-candidate-20261008-r6.zip"):
    load(name)
frozen_path = Path(r"C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip")
with zipfile.ZipFile(frozen_path) as z:
    mismatch = [n for n in z.namelist() if not n.endswith("/") and n not in ("MANIFEST.json", "GIT_HEAD.txt", "GIT_STATUS.txt", "GIT_DIFF.patch") and (not (TREE / n).is_file() or (TREE / n).read_bytes() != z.read(n))]
    print("frozen", digest(frozen_path.read_bytes()), "members", len(z.namelist()), "tree_mismatch", mismatch)

added = sorted(set(c) - set(b))
removed = sorted(set(b) - set(c))
changed = sorted(n for n in c.keys() & b.keys() if c[n] != b[n])
print("delta_b_to_c", json.dumps({"added": added, "changed": changed, "removed": removed}))

spec = importlib.util.spec_from_file_location("chain", TREE / "scripts" / "phase2close_chain.py")
chain = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chain)
baseline = EV / "phase2ops_r6" / "phase1_full.log"
now = EV / "phase2oq" / "chain6" / "phase1_full.log"
collection = (EV / "phase2oq" / "phase1_collection_baseline.txt").read_text(encoding="utf-8").splitlines()
logged_collection = sorted(set(l.strip() for l in (EV / "phase2oq" / "chain6" / "phase1_collection.log").read_text(encoding="utf-8").splitlines() if "::" in l and not l.startswith(("RUN", "ERROR", "FAILED"))))
ok, details = chain.phase1_equivalence(now, baseline, chain.pytest_counts(now), logged_collection, collection)
print("real_equivalence", ok, json.dumps(details, sort_keys=True))
print("baseline_collection_sorted_unique", collection == sorted(set(collection)), "collection_vs_chain6", collection == logged_collection)

def emit(name, passes, skips, fails, total):
    p = OUT / name
    p.write_text("\n".join([*("PASSED " + x for x in passes), *skips, *("FAILED " + x + " - x" for x in fails), f"{len(fails)} failed, {len(passes)} passed, {total-len(passes)-len(fails)} skipped in 1s"]) + "\n", encoding="utf-8")
    return p

coll = [f"x.py::test_p{i}" for i in range(2675)] + [f"live.py::test_s{i}" for i in range(12)] + [f"f.py::test_f{i}" for i in range(11)]
fails = [f"f.py::test_f{i}" for i in range(11)]
base = emit("probe_base.log", coll[:2675], ["SKIPPED [12] live.py:10: unavailable"], fails, 2698)
cases = {}
def check(label, passes, skips, collection_now=coll, failures=fails):
    p = emit("probe_" + label + ".log", passes, skips, failures, 2698)
    cases[label] = chain.phase1_equivalence(p, base, chain.pytest_counts(p), collection_now, coll)
check("identical", coll[:2675], ["SKIPPED [12] live.py:10: unavailable"])
check("missing_replaced", coll[:2674] + ["new.py::test_new"], ["SKIPPED [12] live.py:10: unavailable"], [x for x in coll if x != "x.py::test_p2674"] + ["new.py::test_new"])
check("lost_pass_new_skip", coll[:2674] + ["live.py::test_s0"], ["SKIPPED [11] live.py:10: unavailable", "SKIPPED [1] x.py:99: new"])
check("new_failure", coll[:2674], ["SKIPPED [12] live.py:10: unavailable"], failures=fails + ["x.py::test_p2674"])
check("new_skip", coll[:2674], ["SKIPPED [12] live.py:10: unavailable", "SKIPPED [1] x.py:99: new"])
check("unproven_same_file_pass", coll[:2675] + ["live.py::test_s0"], ["SKIPPED [11] live.py:10: unavailable"])
swap_coll = [f"x.py::test_p{i}" for i in range(2674)] + ["live.py::test_pass"] + [f"live.py::test_s{i}" for i in range(12)] + fails
swap_base = emit("probe_swap_base.log", swap_coll[:2675], ["SKIPPED [12] live.py:10: unavailable"], fails, 2698)
swap_now = emit("probe_swap_now.log", swap_coll[:2674] + ["live.py::test_s0"], ["SKIPPED [12] live.py:10: unavailable"], fails, 2698)
swap_ok, swap_details = chain.phase1_equivalence(swap_now, swap_base, chain.pytest_counts(swap_now), swap_coll, swap_coll)
print("probe_lost_pass_same_skip_location", swap_ok, json.dumps(swap_details, sort_keys=True))
for label, (v, d) in cases.items():
    print("probe", label, "PASS", v, "missing", d.get("collection_missing"), "added", d.get("collection_added"), "extra_skips", d["skips_not_in_baseline"], "unmatched", d["gone_skips_without_named_pass"])
