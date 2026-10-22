from common import *
import subprocess, sys
home = Path(tempfile.mkdtemp())/"l"; EventStore.init(home, "h1")
code = f"""
import sys, os; sys.path.insert(0, r'{T}/src')
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore
EventStore.write_anchors = lambda self, segs: os._exit(9)   # process killed between fsync and anchor refresh
Manager(r'{home}', actor='impl:a').create_milestone('MM-A','A')
"""
r = subprocess.run([sys.executable, "-c", code]); print("killed rc", r.returncode)
m = Manager(home, actor="impl:a"); p = m.projection(); print("status warnings:", p["integrity_warnings"], "errors", p["integrity_errors"])
m.create_milestone("MM-B","B"); print("retry/next write ok; warnings", m.last_warnings)
p = m.projection(); print("open:", [(c["type"], c["kind"]) for c in p["conflicts"] if not c["resolved"]])
from scripts.dev_workflow.milestones import views
print("\n".join(views.status_lines(p))[:400])
