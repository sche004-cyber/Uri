from common import *
import subprocess
def g(cwd,*a): r=subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip()[:220].replace("\n"," | ")
base = Path(tempfile.mkdtemp()); origin = base/"origin.git"; g(base,"init","--bare",str(origin))
c1 = base/"c1"; g(base,"clone",str(origin),str(c1)); g(c1,"config","user.email","a@b"); g(c1,"config","user.name","a")
EventStore.init(c1/"mm","owner-pc",autocommit=True); a = Manager(c1/"mm", actor="impl:a"); a.create_milestone("MM-A","A"); g(c1,"push","origin","HEAD:master")
c2 = base/"c2"; g(base,"clone",str(origin),str(c2)); g(c2,"config","user.email","a@b"); g(c2,"config","user.name","a")
b = Manager(c2/"mm", actor="impl:b"); print("second clone host id:", b.store.host)
b.create_milestone("MM-B","B"); a.create_milestone("MM-C","C"); g(c1,"push","origin","HEAD:master")
print("pull:", g(c2,"pull","--no-rebase","origin","master"))
