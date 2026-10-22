from common import *
import subprocess, shutil, io
import scripts.dev_workflow.milestones.store as S
def g(cwd,*a): r=subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip()[:200].replace("\n"," | ")
base = Path(tempfile.mkdtemp()); origin = base/"o.git"; g(base,"init","-q","--bare",str(origin))
c1 = base/"c1"; g(base,"clone","-q",str(origin),str(c1))
for c in (c1,): g(c,"config","user.email","a@b"); g(c,"config","user.name","a")
EventStore.init(c1/"mm","pc1", autocommit=True); Manager(c1/"mm",actor="impl:a").create_milestone("MM-A","A")
print("push1", g(c1,"push","-q","origin","HEAD:master"))
c2 = base/"c2"; g(base,"clone","-q",str(origin),str(c2)); g(c2,"config","user.email","a@b"); g(c2,"config","user.name","a")
EventStore.init_host(c2/"mm","pc2"); print("c2 registered pc2; git", EventStore(c2/"mm").git_state(), "push", g(c2,"push","-q","origin","HEAD:master"))
c3 = base/"c3"; g(base,"clone","-q",str(origin),str(c3)); g(c3,"config","user.email","a@b"); g(c3,"config","user.name","a")
try:
    EventStore.init_host(c3/"mm","pc2"); print("TAKEOVER: c3 registered pc2 although c2 owns it")
except StoreError as e: print("c3 init-host pc2 refused", e.code)
# both write, then exchange
B = Manager(c2/"mm", actor="impl:b"); C = Manager(c3/"mm", actor="impl:c")
B.create_milestone("MM-B","B"); C.create_milestone("MM-C","C")
print("c2 push", g(c2,"push","-q","origin","HEAD:master"))
print("c3 pull", g(c3,"pull","-q","--no-rebase","origin","master"))
try: p = C.projection(); print("c3 after pull: errors", p["integrity_errors"][:2])
except Exception as e: print("c3 after pull exc", e)
# interrupted init-host retry inside git
c4 = base/"c4"; g(base,"clone","-q",str(origin),str(c4))
orig = EventStore.write_anchors
def boom(self, segs): raise OSError("disk")
EventStore.write_anchors = boom
try: EventStore.init_host(c4/"mm","pc4")
except OSError as e: print("c4 init-host failed (simulated):", e, "| host.json left", (c4/"mm/local/host.json").exists(), "| seg left", (c4/"mm/events/pc4.jsonl").exists())
EventStore.write_anchors = orig
for hid in ("pc4","pc5"):
    try: EventStore.init_host(c4/"mm",hid); print("c4 retry", hid, "OK"); break
    except StoreError as e: print("c4 retry", hid, "refused", e.code)
# non-git: copy ledger of a host that only registered; second machine takes the same id
base2 = Path(tempfile.mkdtemp()); EventStore.init(base2/"A","ha"); Manager(base2/"A",actor="impl:a").create_milestone("MM-A","A")
shutil.copytree(base2/"A", base2/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base2/"B","hb")
shutil.copytree(base2/"B", base2/"C", ignore=shutil.ignore_patterns("local"))
try: EventStore.init_host(base2/"C","hb"); print("non-git TAKEOVER of hb by C")
except StoreError as e: print("non-git C init-host hb refused", e.code)
# pre-existing anchors.json (host.json only removed) destroyed by failed init_host?
base3 = Path(tempfile.mkdtemp()); EventStore.init(base3/"A","ha"); Manager(base3/"A",actor="impl:a").create_milestone("MM-A","A")
(base3/"A/local/host.json").unlink(); print("anchors before", (base3/"A/local/anchors.json").exists())
EventStore.write_anchors = boom
try: EventStore.init_host(base3/"A","hz")
except OSError: pass
EventStore.write_anchors = orig
print("anchors after failed init_host", (base3/"A/local/anchors.json").exists())
