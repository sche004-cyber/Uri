import sys, subprocess, tempfile, time
sys.path.insert(0, "C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/7930d870-1417-469b-b31b-e46354e768c5/scratchpad/src")
from pathlib import Path
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore
home = Path(tempfile.mkdtemp())/"l"; EventStore.init(home, "h1")
w = subprocess.Popen([sys.executable, "-c", f"""
import sys; sys.path.insert(0,'C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/7930d870-1417-469b-b31b-e46354e768c5/scratchpad/src')
from scripts.dev_workflow.milestones.service import Manager
m = Manager(r'{home}', actor='w')
for i in range(300): m.create_milestone(f'MM-{{i}}', 't')
"""])
r = Manager(home); n = bad = 0; samples=set()
while w.poll() is None:
    p = r.projection(); n += 1
    if p["integrity_errors"]: bad += 1; samples.add(p["integrity_errors"][0][:90])
    v = r.store.verify()
print("reads", n, "reads with integrity_errors", bad, list(samples)[:3])
print("final:", r.projection()["integrity_errors"], r.store.verify()["ok"])
