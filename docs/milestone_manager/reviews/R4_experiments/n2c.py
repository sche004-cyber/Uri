import sys, subprocess, tempfile, json
sys.path.insert(0, "C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/7930d870-1417-469b-b31b-e46354e768c5/scratchpad/src")
from pathlib import Path
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore
home = Path(tempfile.mkdtemp())/"l"; EventStore.init(home, "h1")
w = subprocess.Popen([sys.executable, "-c", f"""
import sys, json; sys.path.insert(0,'C:/Users/cheta/AppData/Local/Temp/claude/C--Users-cheta-Development-Uri--V1/7930d870-1417-469b-b31b-e46354e768c5/scratchpad/src')
from scripts.dev_workflow.milestones.service import Manager
m = Manager(r'{home}', actor='w'); fails=[]
for i in range(300):
    try: m.create_milestone(f'MM-{{i}}', 't')
    except Exception as e: fails.append((i, type(e).__name__))
print(json.dumps(fails))
"""], stdout=subprocess.PIPE, text=True)
r = Manager(home); n = bad = 0; samples=set()
while w.poll() is None:
    p = r.projection(); n += 1
    if p["integrity_errors"]: bad += 1; samples.add(p["integrity_errors"][0][-60:])
    r.store.verify()
fails = json.loads(w.stdout.read())
p = r.projection()
print("reads", n, "false integrity reads", bad, list(samples)[:3])
print("writer exceptions", len(fails), fails[:5])
print("milestones present for failed writes:", sum(1 for i,_ in fails if f"MM-{i}" in p["milestones"]), "/", len(fails))
print("final integrity", p["integrity_errors"], "anchors", json.loads((home/'local'/'anchors.json').read_text()))
