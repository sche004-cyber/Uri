import sys, subprocess, tempfile, json, time
SRC='C:/Users/cheta/AppData/Local/Temp/r6rev_b148t_ld/src'
sys.path.insert(0, SRC)
from pathlib import Path
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore
for rnd in range(5):
    home = Path(tempfile.mkdtemp(dir='C:/Users/cheta/AppData/Local/Temp/r6rev_b148t_ld'))/"l"; EventStore.init(home, "h1")
    wcode = f"""
import sys, json; sys.path.insert(0,'{SRC}')
from scripts.dev_workflow.milestones.service import Manager
m = Manager(r'{home}', actor=sys.argv[1]); fails=[]; warns=[]
for i in range(60):
    try: m.create_milestone(f'MM-{{sys.argv[1]}}-{{i}}'.upper(), 't'); warns += m.last_warnings
    except Exception as e: fails.append((i, type(e).__name__, str(e)[:80]))
print(json.dumps([fails, warns]))
"""
    rcode = f"""
import sys, json, time; sys.path.insert(0,'{SRC}')
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import StoreError
t=time.time(); bad=[]; n=0
while time.time()-t < float(sys.argv[1]):
    try:
        r = Manager(r'{home}'); p = r.projection(); n+=1
        if p['integrity_errors']: bad.append(p['integrity_errors'][0][:80])
        v = r.store.verify()
        if not v['ok']: bad.append(str(v['errors'][:1] or v['torn'])[:80])
    except Exception as e: bad.append(type(e).__name__+str(e)[:60])
print(json.dumps([n, bad[:3], len(bad)]))
"""
    rs = [subprocess.Popen([sys.executable, "-c", rcode, "6"], stdout=subprocess.PIPE, text=True) for k in range(3)]
    time.sleep(0.5)
    ws = [subprocess.Popen([sys.executable, "-c", wcode, f"w{k}"], stdout=subprocess.PIPE, text=True) for k in range(3)]
    wo = [json.loads(w.communicate()[0]) for w in ws]; ro = [json.loads(r.communicate()[0]) for r in rs]
    p = Manager(home).projection()
    al = [c for c in p["conflicts"] if c["type"] == "ANCHOR_LOSS"]
    print(rnd, "writer fails", [len(f[0]) for f in wo], "warns", sum(len(f[1]) for f in wo), [f[1][:1] for f in wo if f[1]],
          "| readers", ro, "| milestones", len(p["milestones"]), "ANCHOR_LOSS", len(al), "integrity", p["integrity_errors"], p["integrity_warnings"])
