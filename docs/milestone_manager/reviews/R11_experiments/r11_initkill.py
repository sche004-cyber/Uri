from common import *
import subprocess, shutil, io
def c(home, *args):
    o = io.StringIO()
    try: rc = cli.run(["--home", str(home), *args], out=o)
    except SystemExit as e: rc = f"exit {e.code}"
    return rc, o.getvalue().replace("\n"," ")[:150]
def mk(loss):
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
    if loss:
        EventStore.init_host(home, "hb"); mb = Manager(home, actor="impl:b"); mb.create_milestone("MM-B","B"); mb.create_milestone("MM-B2","B2")
        seg = home/"events/hb.jsonl"; lines = seg.read_bytes().split(b"\n"); seg.write_bytes(b"\n".join(lines[:1]) + b"\n")
        (home/"local/host.json").unlink()
    return home
def run(point, loss):
    home = mk(loss)
    child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
from scripts.dev_workflow.milestones import store as S
P = "{point}"
ow = EventStore._write_local; oa = EventStore.append_many; owa = EventStore.write_anchors
def wl(home, hid):
    if P == "K1": os._exit(9)
    r = ow(home, hid)
    if P == "K2": os._exit(9)
    return r
def am(self, *a, **k):
    r = oa(self, *a, **k)
    if P == "K3": os._exit(9)
    return r
def wa(self, segs):
    r = owa(self, segs)
    if P == "K4": os._exit(9)
    return r
EventStore._write_local = staticmethod(wl); EventStore.append_many = am; EventStore.write_anchors = wa
EventStore.init_host(r"{home}", "hc", acknowledge_loss={loss})
'''
    rc = subprocess.run([sys.executable, "-c", child]).returncode
    print(f"[{point} loss={loss}] child rc", rc, "host.json", (home/"local/host.json").exists(), "seg hc", (home/"events/hc.jsonl").exists())
    print("    status", c(home, "status")[0])
    if not (home/"local/host.json").exists():
        print("    retry init-host hc (no ack) ->", c(home, "init-host", "--host-id", "hc"))
    print("    write ->", c(home, "--actor", "impl:c", "milestone-add", "MM-C", "--title", "C")[0])
    m = Manager(home, actor="x"); p = m.projection()
    print("    open", [x["type"] for x in p["conflicts"] if not x["resolved"]], "errors", p["integrity_errors"][:1], "verify", m.store.verify()["ok"])
for loss in (False, True):
    for p in ("K1","K2","K3","K4","none"): run(p, loss)
