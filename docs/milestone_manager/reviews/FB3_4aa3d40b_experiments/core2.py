import sys, os, shutil, subprocess, json
src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
env = dict(os.environ, PYTHONPATH=src)
home = os.path.join(base, "core2"); shutil.rmtree(home, ignore_errors=True); EventStore.init(home, "h1")
m = Manager(home, actor="impl:a"); m.create_milestone("M1", "t"); m.record_handoff("M1", "one")
ap = os.path.join(home, "local", "anchors.json"); a = json.load(open(ap)); a["h1"] = {"count": 0, "head": "0"*64}; json.dump(a, open(ap, "w"))
seg = os.path.join(home, "events", "h1.jsonl"); n0 = len(open(seg, "rb").read().splitlines())
e = None
try:
    Manager(home, actor="impl:a").record_handoff("M1", "two"); print("write accepted (unexpected)")
except Exception as e0:
    e = e0
    print("first write:", getattr(e0, "code", type(e0).__name__), str(e0)[:220])
lines = open(seg, "rb").read().splitlines(); print("events before/after:", n0, len(lines), "last kind:", json.loads(lines[-1])["kind"])
cid = str(e).split("--id ")[1].split()[0] if "--id " in str(e) else None
print("id in refusal:", cid)
st = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "status", "--json"], cwd=src, env=env, capture_output=True, text=True).stdout
st2 = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "status"], cwd=src, env=env, capture_output=True, text=True).stdout
cf = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "conflicts"], cwd=src, env=env, capture_output=True, text=True).stdout
print("id in status --json:", cid in st, "| in status text:", cid in st2, "| in conflicts:", cid in cf)
j = json.loads(st); print("schema", j["schema"], "milestone keys", sorted(j["milestones"][0]) if isinstance(j["milestones"], list) else type(j["milestones"]))
Manager(home, actor="impl:a").record_handoff("M1", "three"); print("next write accepted")
r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "--actor", "o:1", "resolve-conflict", "LEDGER", "--id", cid, "--note", "reviewed"], cwd=src, env=env, capture_output=True, text=True)
print("resolve rc", r.returncode, (r.stdout + r.stderr).strip()[-120:].replace("\n", " "))
