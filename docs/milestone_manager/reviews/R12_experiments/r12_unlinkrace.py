from common import *
import subprocess, shutil, io, time, sys
def mk_pending():
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
    EventStore.init_host(home, "hb"); mb = Manager(home, actor="impl:b"); mb.create_milestone("MM-B","B"); mb.create_milestone("MM-B2","B2")
    seg = home/"events/hb.jsonl"; lines = seg.read_bytes().split(b"\n"); seg.write_bytes(b"\n".join(lines[:1]) + b"\n")
    (home/"local/host.json").unlink()
    child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
ow = EventStore._write_local
def wl(home, hid):
    r = ow(home, hid); os._exit(9)
EventStore._write_local = staticmethod(wl)
EventStore.init_host(r"{home}", "hc", acknowledge_loss=True)
'''
    subprocess.run([sys.executable, "-c", child])
    assert (home/"local/pending_loss.json").exists()
    return home
mode = sys.argv[1]
if mode == "held":
    home = mk_pending()
    f = open(home/"local/pending_loss.json", "rb")   # what a concurrent `status` reader does for an instant
    m = Manager(home, actor="impl:c")
    try:
        m.create_milestone("MM-C", "C"); print("write OK")
    except BaseException as e:
        print("write raised", type(e).__name__, str(e)[:120])
    f.close()
    p = Manager(home, actor="x").projection()
    print("MM-C written anyway:", "MM-C" in p["milestones"], "marker still:", (home/"local/pending_loss.json").exists(), "anchors own count:", json.loads((home/"local/anchors.json").read_text())["hc"]["count"], "warnings:", [w[:50] for w in p["integrity_warnings"]])
    Manager(home, actor="impl:c").create_milestone("MM-D", "D")
    evs = [e["kind"] for s in EventStore(home).read_all() for e in s.events if e["seg"]=="hc"]
    print("hc kinds after next write:", evs)
else:
    trials = int(sys.argv[2]); bad = {"writer": 0, "reader": 0}
    for t in range(trials):
        home = mk_pending()
        reader = f'''
import sys, time; sys.path.insert(0, r"{T}/exp"); from common import *
m = Manager(r"{home}", actor="x"); errs = 0; n = 0; t0 = time.time()
while time.time() - t0 < 2.0:
    try: m.projection(); n += 1
    except BaseException as e: errs += 1; print("READER", type(e).__name__, str(e)[:80], flush=True)
print("reads", n, "errs", errs)
'''
        rs = [subprocess.Popen([sys.executable, "-c", reader], stdout=subprocess.PIPE, text=True) for _ in range(4)]
        time.sleep(0.7)
        try: Manager(home, actor="impl:c").create_milestone("MM-C", "C")
        except BaseException as e: bad["writer"] += 1; print("trial", t, "WRITER", type(e).__name__, str(e)[:100])
        for r in rs:
            out = r.communicate()[0]
            if "READER" in out: bad["reader"] += 1; print("trial", t, out.strip().splitlines()[0][:120])
    print("trials", trials, bad)
