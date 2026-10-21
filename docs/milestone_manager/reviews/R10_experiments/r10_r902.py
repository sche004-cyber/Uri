from common import *
import subprocess, shutil, time
def mk():
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); return base/"B"
for fail in (True, False):
    home = mk()
    p1 = f'''
import sys, time; sys.path.insert(0, r"{T}/exp"); from common import *
oa = EventStore.append_many
def am(self, *a, **k):
    r = oa(self, *a, **k); time.sleep(2)
    if {fail}: raise OSError("boom after append")
    return r
EventStore.append_many = am
try: EventStore.init_host(r"{home}", "pc2"); print("P1 OK")
except Exception as e: print("P1", type(e).__name__, getattr(e,"code",e))
'''
    p2 = f'''
import sys; sys.path.insert(0, r"{T}/exp"); from common import *
try: EventStore.init_host(r"{home}", "pc2"); Manager(r"{home}", actor="impl:p2").create_milestone("MM-P2","p2"); print("P2 OK + wrote MM-P2")
except Exception as e: print("P2", type(e).__name__, getattr(e,"code",e))
'''
    a = subprocess.Popen([sys.executable,"-c",p1], stdout=subprocess.PIPE, text=True); time.sleep(1.0)
    b = subprocess.Popen([sys.executable,"-c",p2], stdout=subprocess.PIPE, text=True)
    print("fail=%s" % fail, a.communicate()[0].strip(), "|", b.communicate()[0].strip())
    try:
        m = Manager(home, actor="x"); p = m.projection()
        print("   host", m.store.host, "milestones", sorted(p["milestones"]), "errors", p["integrity_errors"][:1], "warn", p["integrity_warnings"][:1], "verify", m.store.verify()["ok"])
    except StoreError as e: print("   state", e.code)
