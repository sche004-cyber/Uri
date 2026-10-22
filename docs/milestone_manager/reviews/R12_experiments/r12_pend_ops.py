from common import *
import subprocess, shutil
def mk_pending(point="K2"):
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
    subprocess.run([sys.executable, "-c", child]); return home
def state(home, tag):
    m = Manager(home); p = m.projection()
    print(f"  {tag}: marker={(home/'local/pending_loss.json').exists()} open={[ (c['type'], c['kind']) for c in p['conflicts'] if not c['resolved']]} verify={m.store.verify()['ok']}")
home = mk_pending()
st = EventStore(home)
try: print("reanchor (no ack):", {k: st.reanchor("impl:c", "re-base")[k] for k in ("lost","unknown_previous")})
except StoreError as e: print("reanchor refused", e.code)
state(home, "after reanchor")
Manager(home, actor="impl:c").create_milestone("MM-C","C"); state(home, "after write")
home = mk_pending()
seg = home/"events/hc.jsonl"; seg.write_bytes(b'{"v":1,"seg":"hc"')   # power loss during first append (torn tail)
st = EventStore(home)
try: r = st.recover("impl:c"); print("recover:", r.get("recovered"), r.get("anchor_problems"))
except StoreError as e: print("recover refused", e.code)
state(home, "after recover")
Manager(home, actor="impl:c").create_milestone("MM-C","C"); state(home, "after write")
