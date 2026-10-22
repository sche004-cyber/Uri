from common import *
import subprocess, shutil, io
def g(cwd,*a): r=subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip()[:200].replace("\n"," | ")
def cl(name):
    c = base/name; g(base,"clone","-q",str(origin),str(c)); g(c,"config","user.email","a@b"); g(c,"config","user.name","a"); return c
base = Path(tempfile.mkdtemp()); origin = base/"o.git"; g(base,"init","-q","--bare",str(origin))
c1 = cl("c1")
EventStore.init(c1/"mm","pc1", autocommit=True); Manager(c1/"mm",actor="impl:a").create_milestone("MM-A","A")
print("push1", g(c1,"push","-q","origin","HEAD:master"))
c2 = cl("c2"); EventStore.init_host(c2/"mm","pc2"); print("c2 init-host pc2 git", EventStore(c2/"mm").git_state(), "push", g(c2,"push","-q","origin","HEAD:master"))
c3 = cl("c3")
try: EventStore.init_host(c3/"mm","pc2"); print("TAKEOVER")
except StoreError as e: print("c3 pc2 refused", e.code, "| host.json left", (c3/"mm/local/host.json").exists())
EventStore.init_host(c3/"mm","pc3")
B = Manager(c2/"mm", actor="impl:b"); C = Manager(c3/"mm", actor="impl:c")
B.create_milestone("MM-B","B"); C.create_milestone("MM-C","C")
print("c2 push", g(c2,"push","-q","origin","HEAD:master"))
print("c3 pull", g(c3,"pull","-q","--no-rebase","origin","master"))
p = C.projection(); print("c3 after pull: errors", p["integrity_errors"][:2], "milestones", sorted(p["milestones"]), "verify", C.store.verify()["ok"])
print("c3 push", g(c3,"push","-q","origin","HEAD:master")); print("c1 pull", g(c1,"pull","-q","--no-rebase","origin","master"))
A = Manager(c1/"mm",actor="impl:a"); p=A.projection(); print("c1 after pull errors", p["integrity_errors"][:2], sorted(p["milestones"]), "verify", A.store.verify()["ok"])
# duplicate ids across hosts
try: A.create_milestone("MM-B","dup"); print("dup MM-B on c1 ALLOWED")
except Exception as e: print("dup MM-B refused", getattr(e,"code",e))
# failed init-host inside git, then retry same id
c4 = cl("c4"); orig = EventStore.write_anchors
def boom(self, segs): raise OSError("disk")
EventStore.write_anchors = boom
try: EventStore.init_host(c4/"mm","pc4")
except OSError as e: print("c4 failed:", e, "| host.json", (c4/"mm/local/host.json").exists(), "| seg", (c4/"mm/events/pc4.jsonl").exists(), "| .gitignore", (c4/"mm/.gitignore").exists(), "| git status", g(c4,"status","--porcelain"))
EventStore.write_anchors = orig
try: EventStore.init_host(c4/"mm","pc4"); print("c4 retry pc4 OK verify", EventStore(c4/"mm").verify()["ok"])
except StoreError as e: print("c4 retry refused", e.code)
# pre-existing .gitignore with custom content and local/ with other content: failed init-host
c5 = cl("c5"); gi_before = (c5/"mm/.gitignore").read_bytes(); (c5/"mm/local").mkdir(exist_ok=True); (c5/"mm/local/notes.txt").write_text("mine")
anch_pre = b'{"junk": 1}'; (c5/"mm/local/anchors.json").write_bytes(anch_pre)
EventStore.write_anchors = boom
try: EventStore.init_host(c5/"mm","pc5")
except OSError: pass
EventStore.write_anchors = orig
print("c5 after failed: gitignore same", (c5/"mm/.gitignore").read_bytes()==gi_before, "notes kept", (c5/"mm/local/notes.txt").exists(), "anchors restored", (c5/"mm/local/anchors.json").read_bytes()==anch_pre)
# failure AFTER anchors written but in autocommit? autocommit never raises; simulate raise in autocommit
c6 = cl("c6"); oa = EventStore.autocommit
def boomc(self, label): raise RuntimeError("git died")
EventStore.autocommit = boomc
try: EventStore.init_host(c6/"mm","pc6")
except RuntimeError as e: print("c6 autocommit raised: host.json", (c6/"mm/local/host.json").exists(), "seg", (c6/"mm/events/pc6.jsonl").exists(), "anchors", (c6/"mm/local/anchors.json").exists())
EventStore.autocommit = oa
try: print("c6 store verify", EventStore(c6/"mm").verify()["ok"], EventStore(c6/"mm").git_state())
except StoreError as e: print("c6 store", e.code)
