import sys, os, json, subprocess, time, shutil
from pathlib import Path
d = Path(sys.argv[1]); src = d / "src"; home = d / "ex" / "home_stress"
shutil.rmtree(home, ignore_errors=True)
sys.path.insert(0, str(src))
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
EventStore.init(home, "hs")
Manager(home, actor="seed").create_milestone("MM-S", "stress")
env = dict(os.environ, PYTHONPATH=str(src), PYTHONDONTWRITEBYTECODE="1")
writer = r'''
import sys
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import StoreError
from scripts.dev_workflow.milestones.model import ValidationError
m = Manager(sys.argv[1], actor="w"+sys.argv[2])
bad = 0
for i in range(int(sys.argv[3])):
    try:
        m.record_handoff("MM-S", f"w{sys.argv[2]} {i}")
    except (StoreError, ValidationError) as e:
        bad += 1; print("ERR", e.code, str(e)[:200])
print("DONE", bad)
'''
reader = r'''
import sys, time
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore
m = Manager(sys.argv[1]); s = EventStore(sys.argv[1]); alarms = 0; n = 0
t_end = time.time() + float(sys.argv[2])
while time.time() < t_end:
    p = m.projection(); n += 1
    if p["integrity_errors"]:
        alarms += 1; print("ALARM proj", p["integrity_errors"][:2])
    v = s.verify(); n += 1
    if not v["ok"]:
        alarms += 1; print("ALARM verify", v["errors"][:2])
print("DONE reads", n, "alarms", alarms)
'''
t0 = time.time()
ws = [subprocess.Popen([sys.executable, "-c", writer, str(home), str(k), "40"], cwd=str(src), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for k in range(6)]
rs = [subprocess.Popen([sys.executable, "-c", reader, str(home), "25"], cwd=str(src), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for k in range(3)]
for p in ws + rs:
    out, _ = p.communicate(timeout=300)
    lines = out.strip().splitlines()
    errs = [l for l in lines if l.startswith(("ERR", "ALARM", "Traceback"))]
    print("rc", p.returncode, lines[-1] if lines else "", "| problems:", len(errs), errs[:3])
s = EventStore(home); v = s.verify()
print("final verify ok:", v["ok"], "events:", v["events"], "errors:", v["errors"][:3], "elapsed", round(time.time()-t0,1))
p = Manager(home).projection(); print("handoffs:", len(p["handoffs"]), "conflicts open:", sum(1 for c in p["conflicts"] if not c["resolved"]))
