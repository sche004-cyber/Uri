from common import *
import subprocess, json
SRC=T+"/src"
home = Path(tempfile.mkdtemp())/"l"; EventStore.init(home, "h1"); Manager(home, actor="w0").create_milestone("MM-PRE","pre")
wcode = f"""
import sys, json; sys.dont_write_bytecode=True; sys.path.insert(0,r'{SRC}')
from scripts.dev_workflow.milestones.service import Manager
m = Manager(r'{home}', actor=sys.argv[1]); n=0
for i in range(150):
    m.create_milestone(f'MM-{{sys.argv[1]}}-{{i}}'.upper(), 't'); n+=1
    m.record_decision('t','d','2026-10-22','OTHER','s', supersedes=None)
print(n)
"""
rcode = f"""
import sys, json, time; sys.dont_write_bytecode=True; sys.path.insert(0,r'{SRC}')
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones import views
m = Manager(r'{home}'); n=bad=0; s=set(); t0=time.time()
while time.time()-t0 < float(sys.argv[1]):
    p=m.projection(); n+=1; views.status_lines(p, False)
    if p['integrity_errors']: bad+=1; s.add(p['integrity_errors'][0][:80])
    v=m.store.verify()
    if not v['ok']: bad+=1; s.add(str(v['errors'][:1] or v['torn'])[:80])
print(json.dumps([n,bad,sorted(s)]))
"""
ws=[subprocess.Popen([sys.executable,"-c",wcode,f"w{k}"],stdout=subprocess.PIPE,text=True) for k in range(4)]
rs=[subprocess.Popen([sys.executable,"-c",rcode,"25"],stdout=subprocess.PIPE,text=True) for k in range(4)]
wo=[w.communicate()[0].strip() for w in ws]; ro=[json.loads(r.communicate()[0]) for r in rs]
p=Manager(home).projection()
print("writers", wo, "readers [reads, alarms, samples]", ro)
print("milestones", len(p["milestones"]), "decisions", len(p["decisions"]), "events", p["events"], "errs", p["integrity_errors"], "verify", EventStore(home).verify()["ok"])
