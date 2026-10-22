import sys, os, json, shutil
src, home, p0 = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones import importers
shutil.rmtree(home, ignore_errors=True)
EventStore.init(home, "h1")
m = Manager(home, actor="rev:fb2", session="s")
out = {}
for name, fn in [("decisions", importers.import_decisions), ("developmental", importers.import_register)]:
    r = fn(m, os.path.join(p0, name + ".md"), commit="e0fdb35f9aaaf14e25fc2c64cdfc87a96d89f376")
    out[name] = {k: (v if not isinstance(v, list) else v) for k, v in r.items()}
print(json.dumps(out, indent=1, default=str))
