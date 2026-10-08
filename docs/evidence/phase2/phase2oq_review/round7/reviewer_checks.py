import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOP = HERE.parents[2]
TREE = TOP / "uri-agent"
EV = TOP / "evidence"


def sha(b):
    return hashlib.sha256(b).hexdigest()


def archive(name):
    path = EV / name
    with zipfile.ZipFile(path) as z:
        manifest = json.loads(z.read("MANIFEST.json"))
        members = set(z.namelist()) - {"MANIFEST.json", "GIT_DIFF.patch", "GIT_HEAD.txt", "GIT_STATUS.txt"}
        bad = [n for n, h in manifest.items() if n not in members or sha(z.read(n)) != h]
        tree = {n: h for n, h in manifest.items() if not n.startswith("evidence/")}
        live_bad = [n for n, h in tree.items() if not (TREE / n).is_file() or sha((TREE / n).read_bytes()) != h]
        evidence_bad = [n for n, h in manifest.items() if n.startswith("evidence/") and
                        (not (TOP / n).is_file() or sha((TOP / n).read_bytes()) != h)]
    return manifest, dict(sha256=sha(path.read_bytes()), entries=len(manifest), members=len(members),
                          member_delta=sorted(members ^ set(manifest)), bad=bad, tree_files=len(tree),
                          evidence_files=len(manifest)-len(tree), live_tree_bad=live_bad, live_evidence_bad=evidence_bad)


g, gi = archive("phase2oq-candidate-20261008-g.zip")
f, fi = archive("phase2oq-candidate-20261008-f.zip")
spec = importlib.util.spec_from_file_location("chain", TREE / "scripts/phase2close_chain.py")
ch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ch)
basepath = EV / "phase2oq"
base = json.loads((basepath / "phase1_outcome_baseline.json").read_text())
bx = basepath / "outcome_baseline/phase1_baseline.xml"
bl = basepath / "outcome_baseline/phase1_baseline.log"
nx = basepath / "chain10/phase1_full.xml"
nl = basepath / "chain10/phase1_full.log"
summary = json.loads((basepath / "chain10/chain_summary.json").read_text())
with zipfile.ZipFile(EV / "phase2close-candidate-20261008-f.zip") as z:
    accepted = z.read("scripts/phase2d_regression.py")
    ini = z.read("scripts/phase2d_pytest.ini")
frozen = Path(r"C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip")
with zipfile.ZipFile(frozen) as z:
    frozen_files = [n for n in z.namelist() if not n.endswith("/") and n not in
                    ("MANIFEST.json", "GIT_HEAD.txt", "GIT_STATUS.txt", "GIT_DIFF.patch") and not n.startswith("evidence/")]
    frozen_info = dict(sha256=sha(frozen.read_bytes()), entries=len(frozen_files),
                       live_bad=[n for n in frozen_files if not (TREE/n).is_file() or (TREE/n).read_bytes() != z.read(n)])

probes = {}
probes["actual_baseline_pins"] = ch.baseline_pins_hold()
probes["exit_gate"] = {str(code): (code == ch.PHASE1_EXPECTED_EXIT) for code in (0, 1, 2, 3, 4, 5, "TIMED_OUT")}
probes["baseline_map_equals_xml"] = ch.junit_outcomes(bx) == base["outcomes"]
probes["baseline_integrity"] = ch.junit_integrity(bx, ch.pytest_counts(bl))
probes["chain_integrity"] = ch.junit_integrity(nx, ch.pytest_counts(nl))
probes["chain_identity"] = ch.outcome_identity(ch.junit_outcomes(nx), base["outcomes"])
probes["same_failures"] = ch.failed_ids(nl) == ch.failed_ids(EV / "phase2ops_r6/phase1_full.log")
probes["runner_sha"] = base["runner_sha256"] == sha(accepted)
probes["runner_argv"] = ch.runner_argv((TREE/"scripts/phase2d_regression.py").read_text()) == ch.runner_argv(accepted.decode()) + [ch.OQ_EXTRA_IGNORE]
probes["ini"] = (TREE/"scripts/phase2d_pytest.ini").read_bytes() == ini
outcomes = base["outcomes"]
p = next(k for k, v in outcomes.items() if v == "passed")
s = next(k for k, v in outcomes.items() if v == "skipped")
mutations = {}
for name in ("missing", "added", "lost_pass", "swap", "new_failure", "new_skip"):
    m = outcomes.copy()
    if name == "missing": m.pop(p)
    if name == "added": m["review::added"] = "passed"
    if name == "lost_pass": m[p] = "skipped"
    if name == "swap": m[p], m[s] = m[s], m[p]
    if name == "new_failure": m[p] = "failed"
    if name == "new_skip": m[p] = "skipped"
    mutations[name] = ch.outcome_identity(m, outcomes)[0]
probes["outcome_mutations_accepted"] = mutations

scratch = HERE / "scratch"
scratch.mkdir(exist_ok=True)
(scratch / "outcome_baseline").mkdir(exist_ok=True)
for rel in ch.BASELINE_PINS:
    dest = scratch / rel
    dest.write_bytes((basepath / rel).read_bytes())
probes["copied_baseline_pins"] = ch.baseline_pins_hold(scratch)[0]
import xml.etree.ElementTree as ET
t = ET.parse(scratch / "outcome_baseline/phase1_baseline.xml")
cases = list(t.getroot().iter("testcase"))
pc = next(c for c in cases if not any(x.tag in ("failure", "error", "skipped") for x in c))
sc = next(c for c in cases if any(x.tag == "skipped" for x in c))
sk = next(x for x in sc if x.tag == "skipped")
sc.remove(sk)
pc.append(sk)
t.write(scratch / "outcome_baseline/phase1_baseline.xml", encoding="utf-8")
tampered = outcomes.copy()
tampered[p], tampered[s] = tampered[s], tampered[p]
probes["joint_tamper"] = dict(pins_hold=ch.baseline_pins_hold(scratch)[0],
    integrity=ch.junit_integrity(scratch / "outcome_baseline/phase1_baseline.xml", ch.pytest_counts(bl))["ok"],
    changed_ids=[p, s])
scratch_xml = scratch / "small.xml"
scratch_xml.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="a" name="s"><skipped/></testcase></testsuite></testsuites>')
probes["outcome_count_mismatch"] = ch.junit_integrity(scratch_xml, dict(passed=2, failed=0, skipped=0, errors=0))["ok"]
scratch_xml.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="a" name="p"/></testsuite></testsuites>')
probes["duplicate_id"] = ch.junit_integrity(scratch_xml, dict(passed=2, failed=0, skipped=0, errors=0))["ok"]
scope = ch.phase1_scope_check(TREE, EV / "phase2close-candidate-20261008-f.zip")
result = dict(subject=gi, previous=fi, added=sorted(set(g)-set(f)), removed=sorted(set(f)-set(g)),
    changed=sorted(k for k in g.keys() & f.keys() if g[k] != f[k]),
    head=subprocess.run(["git", "-C", str(TREE), "rev-parse", "HEAD"],capture_output=True,text=True).stdout.strip(),
    closure_sha=sha((EV/"phase2close-candidate-20261008-f.zip").read_bytes()),
    round7_sha=sha((EV/"phase2ops-candidate-20261008-r6.zip").read_bytes()), frozen=frozen_info,
    scope=scope, probes=probes, chain={k:{"PASS":v.get("PASS"),"exit":v.get("exit")} for k,v in summary["gates"].items()},
    chain_all_pass=summary["ALL_PASS"])
(HERE / "reviewer_results.json").write_text(json.dumps(result, indent=2, default=str))
print(json.dumps({k:v for k,v in result.items() if k not in ("added", "scope")},indent=2,default=str))
