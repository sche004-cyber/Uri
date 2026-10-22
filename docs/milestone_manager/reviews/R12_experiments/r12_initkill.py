from common import *
import subprocess, shutil, io
def c(home, *args):
    o = io.StringIO()
    try: rc = cli.run(["--home", str(home), *args], out=o)
    except SystemExit as e: rc = f"exit {e.code}"
    return rc, o.getvalue().replace("\n"," ")[:160]
def mk():
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
    EventStore.init_host(home, "hb"); mb = Manager(home, actor="impl:b"); mb.create_milestone("MM-B","B"); mb.create_milestone("MM-B2","B2")
    seg = home/"events/hb.jsonl"; lines = seg.read_bytes().split(b"\n"); seg.write_bytes(b"\n".join(lines[:1]) + b"\n")
    (home/"local/host.json").unlink()
    return home
def summary(home, tag):
    try:
        m = Manager(home, actor="x"); p = m.projection()
    except StoreError as e:
        print(f"    {tag}: {e.code}"); return
    evs = [e for s in m.store.read_all() for e in s.events]
    kinds = [e["kind"] for e in evs if e["kind"] in ("HOST_REGISTERED","LOSS_RECORDED","ANCHORS_ADOPTED","STORE_RECOVERED","ANCHORS_RESET")]
    hr_probs = [bool(e["data"].get("anchor_problems")) for e in evs if e["kind"]=="HOST_REGISTERED" and e["seg"]==m.store.host]
    print(f"    {tag}: host={m.store.host} kinds={kinds} own HR problems={hr_probs} open={[x['type'] for x in p['conflicts'] if not x['resolved']]} marker={(home/'local/pending_loss.json').exists()} verify={m.store.verify()['ok']} warn={[w[:60] for w in p['integrity_warnings']]}")
def run(point):
    home = mk()
    child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
from scripts.dev_workflow.milestones import store as S
P = "{point}"
ow = EventStore._write_local; oa = EventStore.append_many; owa = EventStore.write_anchors; oab = S.atomic_write_bytes
from pathlib import Path as _P
_u = _P.unlink
def unl(self, *a, **k):
    r = _u(self, *a, **k)
    if P == "K3b" and self.name == "pending_loss.json": os._exit(9)
    return r
def awb(path, data):
    r = oab(path, data)
    if P == "K0" and path.name == "pending_loss.json": os._exit(9)
    if P == "K0b" and path.name == "anchors.json": os._exit(9)
    return r
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
S.atomic_write_bytes = awb; _P.unlink = unl
EventStore._write_local = staticmethod(wl); EventStore.append_many = am; EventStore.write_anchors = wa
EventStore.init_host(r"{home}", "hc", acknowledge_loss=True)
'''
    rc = subprocess.run([sys.executable, "-c", child]).returncode
    print(f"[{point}] child rc", rc, "host.json", (home/"local/host.json").exists(), "seg hc", (home/"events/hc.jsonl").exists(), "marker", (home/"local/pending_loss.json").exists())
    print("    status rc", c(home, "status")[0])
    if not (home/"local/host.json").exists():
        print("    retry no ack ->", c(home, "init-host", "--host-id", "hc")[1][:110])
        print("    retry ack ->", c(home, "init-host", "--host-id", "hc", "--acknowledge-loss")[0])
    summary(home, "after reg")
    print("    write1 ->", c(home, "--actor", "impl:c", "milestone-add", "MM-C", "--title", "C")[0])
    print("    write2 ->", c(home, "--actor", "impl:c", "milestone-add", "MM-D", "--title", "D")[0])
    summary(home, "after writes")
for p in ("K0","K0b","K1","K2","K3","K3b","K4","none"): run(p)
