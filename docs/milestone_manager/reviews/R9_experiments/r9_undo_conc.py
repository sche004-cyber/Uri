from common import *
import subprocess
def g(cwd,*a): r=subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip()[:300].replace("\n"," | ")
base = Path(tempfile.mkdtemp()); src = base/"src"; src.mkdir()
for a in (("init","-q"),("config","user.email","a@b"),("config","user.name","a")): g(src,*a)
EventStore.init(src/"mm","pc1", autocommit=False); Manager(src/"mm",actor="impl:a").create_milestone("MM-A","A")
g(src,"add","-A"); g(src,"commit","-qm","x")
c = base/"c"; g(base,"clone","-q",str(src),str(c)); home = c/"mm"
other = f'''
import sys; sys.path.insert(0, r"{T}/exp"); from common import *
EventStore.init_host(r"{home}", "pc2"); Manager(r"{home}", actor="impl:other").create_milestone("MM-OTHER","work done after a successful init-host")
print("other: init-host pc2 OK and MM-OTHER written", flush=True)
'''
real = EventStore.in_git; st = {"n":0}
def hooked(self):
    if st["n"] == 0:
        st["n"] = 1; print(subprocess.run([sys.executable, "-c", other], capture_output=True, text=True).stdout.strip())
    return real(self)
EventStore.in_git = hooked
try: EventStore.init_host(home, "pc2"); print("this init-host OK")
except StoreError as e: print("this init-host refused", e.code)
EventStore.in_git = real
print("after: pc2 seg exists", (home/"events/pc2.jsonl").exists(), "host.json", (home/"local/host.json").exists(), "anchors", (home/"local/anchors.json").exists())
