from common import *
import subprocess, shutil
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); ma = Manager(base/"A",actor="impl:a"); ma.create_milestone("MM-A","A")
ma.update_milestone("MM-A", candidate_commit=C1); ma.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "x")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
oa = EventStore.append_many
def am(self, *a, **k):
    r = oa(self, *a, **k); os._exit(9)
EventStore.append_many = am
EventStore.init_host(r"{home}", "hc")
'''
print("child rc", subprocess.run([sys.executable, "-c", child]).returncode)
m = Manager(home, actor="impl:c")
try: w = m.set_status("MM-A","ACCEPTED","first write"); print("ACCEPTED ALLOWED, batch", [e["kind"] for e in w])
except Exception as e: print("refused", getattr(e,"code",e))
p = m.projection(); print("status", p["milestones"]["MM-A"]["status"], "open", [(c["type"], c["kind"]) for c in p["conflicts"] if not c["resolved"]])
