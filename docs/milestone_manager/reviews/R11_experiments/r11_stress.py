import sys, subprocess, tempfile, json
SRC='C:/Users/cheta/AppData/Local/Temp/r11_0cbv209a/src'
sys.path.insert(0, SRC)
from pathlib import Path
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore
home = Path(tempfile.mkdtemp(dir='C:/Users/cheta/AppData/Local/Temp/r11_0cbv209a/tmp'))/"l"; EventStore.init(home, "h1")
Manager(home, actor="w0").create_milestone("MM-PRE","pre")
code = f"""
import sys, json; sys.path.insert(0,'{SRC}')
from scripts.dev_workflow.milestones.service import Manager
m = Manager(r'{home}', actor=sys.argv[1]); fails=[]
for i in range(200):
    try: m.create_milestone(f'MM-{{sys.argv[1]}}-{{i}}'.upper(), 't')
    except Exception as e: fails.append((i, type(e).__name__, str(e)[:80]))
print(json.dumps(fails))
"""
ws = [subprocess.Popen([sys.executable, "-c", code, f"w{k}"], stdout=subprocess.PIPE, text=True) for k in range(2)]
r = Manager(home); n = bad = vbad = 0; samples=set(); vs=set()
while any(w.poll() is None for w in ws):
    p = r.projection(); n += 1
    if p["integrity_errors"]: bad += 1; samples.add(p["integrity_errors"][0][:90])
    v = r.store.verify()
    if not v["ok"]: vbad += 1; vs.add(str(v["errors"][:1] or v["torn"])[:90])
fails = [json.loads(w.stdout.read()) for w in ws]
p = r.projection()
print("reads", n, "false proj", bad, samples, "| false verify", vbad, vs)
print("writer exceptions", [len(f) for f in fails], [f[:2] for f in fails])
print("milestones", len(p["milestones"]), "final", p["integrity_errors"])
