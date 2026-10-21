import sys, subprocess, tempfile, json, time, os
T="C:/Users/cheta/AppData/Local/Temp/r15_a55o83gr"; SRC=T+"/src"
os.environ["TEMP"]=os.environ["TMP"]=T+"/tmp"; os.environ["PYTHONDONTWRITEBYTECODE"]="1"
sys.path.insert(0, SRC)
from pathlib import Path
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore
tot_reads = tot_bad = 0
for rnd in range(5):
    home = Path(tempfile.mkdtemp(dir=T+"/tmp"))/"l"; EventStore.init(home, "h1")
    wcode = f"""
import sys, json; sys.dont_write_bytecode=True; sys.path.insert(0,r'{SRC}')
from scripts.dev_workflow.milestones.service import Manager
m = Manager(r'{home}', actor=sys.argv[1]); fails=[]; warns=[]
for i in range(60):
    try:
        mid = f'MM-{{sys.argv[1]}}-{{i}}'.upper(); m.create_milestone(mid, 't'); warns += m.last_warnings
        if i % 3 == 0: m.update_milestone(mid, title='u'); m.add_blocker(mid, 'TECHNICAL', 'r', 'n'); warns += m.last_warnings
    except Exception as e: fails.append((i, type(e).__name__, str(e)[:80]))
print(json.dumps([fails, warns]))
"""
    rcode = f"""
import sys, json, time; sys.dont_write_bytecode=True; sys.path.insert(0,r'{SRC}')
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones import views
t=time.time(); bad=[]; n=0
while time.time()-t < float(sys.argv[1]):
    try:
        r = Manager(r'{home}'); p = r.projection(); n+=1
        if p['integrity_errors']: bad.append(p['integrity_errors'][0][:80])
        if [w for w in p['integrity_warnings'] if 'torn' not in w]: pass
        views.status_json(p, None)
        v = r.store.verify()
        if v['errors']: bad.append(str(v['errors'][:1])[:80])
    except Exception as e: bad.append(type(e).__name__+str(e)[:60])
print(json.dumps([n, bad[:3], len(bad)]))
"""
    rs = [subprocess.Popen([sys.executable, "-c", rcode, "8"], stdout=subprocess.PIPE, text=True) for k in range(4)]
    time.sleep(0.5)
    ws = [subprocess.Popen([sys.executable, "-c", wcode, f"w{k}"], stdout=subprocess.PIPE, text=True) for k in range(4)]
    wo = [json.loads(w.communicate()[0]) for w in ws]; ro = [json.loads(r.communicate()[0]) for r in rs]
    p = Manager(home).projection(); v = EventStore(home).verify()
    al = [c for c in p["conflicts"] if c["type"] == "ANCHOR_LOSS"]
    tot_reads += sum(r[0] for r in ro); tot_bad += sum(r[2] for r in ro)
    print(rnd, "writer fails", [len(f[0]) for f in wo], [f[0][:1] for f in wo if f[0]], "warns", sum(len(f[1]) for f in wo),
          "| readers", ro, "| milestones", len(p["milestones"]), "events", v["events"], "verify ok", v["ok"], "ANCHOR_LOSS", len(al), "integrity", p["integrity_errors"], p["integrity_warnings"])
print("TOTAL reads", tot_reads, "false alarms", tot_bad)
