from common import *
import subprocess, time, shutil, io
for prior_anchors in (False, True):
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
    if prior_anchors:
        EventStore.init_host(home, "hb"); (home/"local/host.json").unlink()   # machine lost only host.json
    child = f'''
import sys; sys.path.insert(0, r"{T}/exp"); from common import *
import time
while not Path(r"{home}/local/host.json").exists(): time.sleep(0.002)
m = Manager(r"{home}", actor="impl:other")
try: m.create_milestone("MM-OTHER","concurrent"); print("child wrote MM-OTHER as", m.store.host, flush=True)
except Exception as e: print("child refused", getattr(e,"code",e), flush=True)
'''
    p = subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    time.sleep(1.0)
    orig = EventStore.write_anchors
    def boom(self, segs): time.sleep(1.0); raise OSError("refresh failed")
    EventStore.write_anchors = boom
    try: EventStore.init_host(home, "hc")
    except OSError as e: print(f"[prior_anchors={prior_anchors}] init-host hc failed:", e)
    EventStore.write_anchors = orig
    print("  child:", p.communicate(timeout=60)[0].strip()[-200:])
    print("  host.json", (home/"local/host.json").exists(), "segments", sorted(x.name for x in (home/"events").glob("*.jsonl")))
    for hid in ("hc",):
        try: EventStore.init_host(home, hid); print("  retry", hid, "OK")
        except StoreError as e: print("  retry", hid, "refused", e.code, str(e)[:100])
    try:
        m = Manager(home, actor="x"); pr = m.projection(); print("  milestones", sorted(pr["milestones"]), "open", [c["type"] for c in pr["conflicts"] if not c["resolved"]], "verify", m.store.verify()["ok"])
    except StoreError as e: print("  ", e.code)
