from common import *
import subprocess, time, pathlib
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
import shutil; shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local"))
home = base/"B"
child = f'''
import sys; sys.path.insert(0, r"{T}/exp"); from common import *
import time
while not Path(r"{home}/local/host.json").exists(): time.sleep(0.005)
m = Manager(r"{home}", actor="impl:other")
m.create_milestone("MM-OTHER","written by concurrent command")
print("child wrote MM-OTHER ok", flush=True)
'''
orig_wa = EventStore.write_anchors; orig_unlink = pathlib.Path.unlink
state = {"n": 0}
def boom(self, segs):
    p = subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    state["p"] = p; time.sleep(1.5)   # child is now blocked on the lock
    raise OSError("anchors write failed")
def slow_unlink(self, missing_ok=False):
    if state["n"] == 0: time.sleep(2.0)   # widen the unlocked window between lock release and undo
    state["n"] += 1; return orig_unlink(self, missing_ok=missing_ok)
EventStore.write_anchors = boom; pathlib.Path.unlink = slow_unlink
try: EventStore.init_host(home, "hb")
except OSError as e: print("init-host failed:", e)
EventStore.write_anchors = orig_wa; pathlib.Path.unlink = orig_unlink
out = state["p"].communicate(timeout=60)[0]; print("child:", out.strip()[-300:])
print("seg hb exists", (home/"events/hb.jsonl").exists(), "host.json", (home/"local/host.json").exists())
EventStore.init_host(home, "hb2"); m = Manager(home, actor="impl:a"); p = m.projection()
print("after retry: milestones", sorted(p["milestones"]), "errors", p["integrity_errors"], "open conflicts", [c["type"] for c in p["conflicts"] if not c["resolved"]], "verify", m.store.verify()["ok"])
