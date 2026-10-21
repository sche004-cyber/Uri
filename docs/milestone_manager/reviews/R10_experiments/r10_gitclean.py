from common import *
import subprocess, io
def g(cwd,*a): r=subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip()[:200].replace("\n"," | ")
base = Path(tempfile.mkdtemp()); src = base/"src"; src.mkdir()
for a in (("init","-q"),("config","user.email","a@b"),("config","user.name","a")): g(src,*a)
EventStore.init(src/"mm","pc1", autocommit=True); Manager(src/"mm",actor="impl:a").create_milestone("MM-A","A")
c = base/"c"; g(base,"clone","-q",str(src),str(c)); g(c,"config","user.email","a@b"); g(c,"config","user.name","a")
EventStore.init_host(c/"mm","pc2"); Manager(c/"mm",actor="impl:b").create_milestone("MM-B","B")
print("git status", g(c,"status","--porcelain"))
for mode in ("-fdx", "-fdX"):
    print("git clean", mode, g(c,"clean",mode))
    for hid in ("pc2", "pc3" if mode=="-fdx" else "pc4"):
        try: EventStore.init_host(c/"mm", hid); print("  init-host", hid, "OK")
        except StoreError as e: print("  init-host", hid, e.code)
    m = Manager(c/"mm", actor="x"); p = m.projection(); print("  milestones", sorted(p["milestones"]), "errors", p["integrity_errors"][:1], "verify", m.store.verify()["ok"])
