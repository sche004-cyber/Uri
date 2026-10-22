from common import *
import subprocess, io
def g(cwd,*a): r=subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip()[:200].replace("\n"," | ")
base = Path(tempfile.mkdtemp()); origin = base/"origin.git"; g(base,"init","--bare",str(origin))
c1 = base/"c1"; g(base,"clone",str(origin),str(c1)); g(c1,"config","user.email","a@b"); g(c1,"config","user.name","a")
EventStore.init(c1/"mm","pc1",autocommit=True); a = Manager(c1/"mm", actor="impl:a"); a.create_milestone("MM-A","A")
print("c1 tracked:", g(c1,"ls-files")[1]); print("push", g(c1,"push","origin","HEAD:master")[0])
c2 = base/"c2"; g(base,"clone",str(origin),str(c2)); g(c2,"config","user.email","a@b"); g(c2,"config","user.name","a")
try: Manager(c2/"mm", actor="impl:b")
except StoreError as e: print("clone without init-host:", e.code)
o=io.StringIO(); rc=cli.run(["--home",str(c2/"mm"),"status","--no-tasks"],out=o); print("status on unregistered clone rc", rc, o.getvalue()[:60].strip())
try: EventStore.init_host(c2/"mm","pc1")
except StoreError as e: print("init-host pc1:", e.code)
EventStore.init_host(c2/"mm","pc2"); b = Manager(c2/"mm", actor="impl:b"); print("c2 anchors:", list(b.store.read_anchors()))
b.create_milestone("MM-B","B"); a.create_milestone("MM-C","C"); print("push a", g(c1,"push","origin","HEAD:master")[0])
print("pull b", g(c2,"pull","--no-rebase","origin","master")[0], "| push b", g(c2,"push","origin","HEAD:master")[0])
print("pull a", g(c1,"pull","--no-rebase","origin","master")[0])
for n,m in (("a",a),("b",b)):
    v = Manager(m.home).store.verify(); print(n, "verify", v["ok"], v["errors"], "events", v["events"], "git", v["git"])
pa, pb = a.projection(), b.projection()
print("same projection a/b:", M_eq := (json.dumps({k:pa[k] for k in ("milestones","conflicts")},sort_keys=True)==json.dumps({k:pb[k] for k in ("milestones","conflicts")},sort_keys=True)))
# after pull, a has not yet anchored pc2; delete pc2 newest event in c1 (as if force-pushed shorter) -> detected?
a.create_milestone("MM-D","D"); print("a anchors after write:", {k:v["count"] for k,v in a.store.read_anchors().items()})
