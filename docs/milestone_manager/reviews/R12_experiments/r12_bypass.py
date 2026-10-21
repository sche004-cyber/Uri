from common import *
import subprocess, shutil, io
def mk():
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); ma = Manager(base/"A",actor="impl:a"); ma.create_milestone("MM-A","A")
    ma.update_milestone("MM-A", candidate_commit=C1)
    ma.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "x")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
    EventStore.init_host(home, "hb"); mb = Manager(home, actor="impl:b"); mb.create_milestone("MM-B","B"); mb.create_milestone("MM-B2","B2")
    seg = home/"events/hb.jsonl"; lines = seg.read_bytes().split(b"\n"); seg.write_bytes(b"\n".join(lines[:1]) + b"\n")
    (home/"local/host.json").unlink()
    return home
for point in ("K2", "none"):
    home = mk()
    child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
ow = EventStore._write_local
def wl(home, hid):
    r = ow(home, hid)
    if "{point}" == "K2": os._exit(9)
    return r
EventStore._write_local = staticmethod(wl)
EventStore.init_host(r"{home}", "hc", acknowledge_loss=True)
'''
    print(point, "child rc", subprocess.run([sys.executable, "-c", child]).returncode)
    m = Manager(home, actor="impl:c")
    print("  warnings:", [w[:70] for w in m.projection()["integrity_warnings"]])
    try:
        w = m.set_status("MM-A", "ACCEPTED", "first write after interrupted registration")
        print("  ACCEPTED ALLOWED; batch kinds:", [e["kind"] for e in w])
    except Exception as e:
        print("  ACCEPTED refused:", getattr(e, "code", e))
    p = m.projection()
    print("  MM-A status:", p["milestones"]["MM-A"]["status"], "open:", [c["type"] for c in p["conflicts"] if not c["resolved"]])
    print("  indicator:", views.indicator(p, p["milestones"]["MM-A"]) if hasattr(views,"indicator") else None)
