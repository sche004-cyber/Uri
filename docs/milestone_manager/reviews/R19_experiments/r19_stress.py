from common import *
import subprocess, json
SRC=T+"/src"
home = Path(tempfile.mkdtemp())/"l"; EventStore.init(home, "h1")
Manager(home, actor="w0").create_milestone("MM-PRE","pre")
code = f"""
import sys, json; sys.path.insert(0,r'{SRC}')
from scripts.dev_workflow.milestones.service import Manager
m = Manager(r'{home}', actor=sys.argv[1]); fails=[]
for i in range(200):
    try:
        m.create_milestone(f'MM-{{sys.argv[1]}}-{{i}}'.upper(), 't')
        if i%5==0: m.update_milestone(f'MM-{{sys.argv[1]}}-{{i}}'.upper(), expect_version=0, next_action='stale')
    except Exception as e: fails.append((i, type(e).__name__, str(e)[:80]))
print(json.dumps(fails))
"""
ws = [subprocess.Popen([sys.executable, "-c", code, f"w{k}"], stdout=subprocess.PIPE, text=True) for k in range(3)]
r = Manager(home); n = bad = vbad = 0; samples=set(); vs=set(); idbad=0
while any(w.poll() is None for w in ws):
    p = r.projection(); n += 1
    if p["integrity_errors"]: bad += 1; samples.add(p["integrity_errors"][0][:90])
    rows = views.conflict_rows(p)
    v = r.store.verify()
    if not v["ok"]: vbad += 1; vs.add(str(v["errors"][:1] or v["torn"])[:90])
fails = [json.loads(w.stdout.read()) for w in ws]
p = r.projection()
print("reads", n, "false proj alarms", bad, samples, "| false verify", vbad, vs)
print("writer exceptions", [len(f) for f in fails], {f[1] for fl in fails for f in fl})
print("milestones", len(p["milestones"]), "final errs", p["integrity_errors"], "open conflicts", len(views.open_conflicts(p)))
