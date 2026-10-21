from common import *
import subprocess, shutil
def g(cwd,*a): r=subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip()[:300]
# (a) delete anchors + truncate newest
m = new(); m.create_milestone("MM-A","A"); m.record_decision("D","d","2026-10-21","OWNER-PROMPT","chat")
lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]
m.store.segment_path.write_bytes(b"\n".join(lines[:-1])+b"\n"); m.store.anchors_path.unlink()
print("(a) verify ok after truncation+anchor delete:", m.store.verify()["ok"])
# (b) corrupt anchors
m = new(); m.create_milestone("MM-A","A"); m.record_decision("D","d","2026-10-21","OWNER-PROMPT","chat")
lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]
m.store.segment_path.write_bytes(b"\n".join(lines[:-1])+b"\n")
m.store.anchors_path.write_text("<<<<<<< HEAD\n{}\n=======\n{}\n>>>>>>> x\n")
print("(b) verify ok with corrupt anchors + truncation:", m.store.verify()["ok"], m.store.verify()["errors"])
m.create_milestone("MM-B","B"); print("    write accepted; anchors now", m.store.read_anchors())
# (c) git multi-host with autocommit
base = Path(tempfile.mkdtemp()); origin = base/"origin.git"; g(base,"init","--bare",str(origin))
c1 = base/"c1"; g(base,"clone",str(origin),str(c1))
for c in (c1,): g(c,"config","user.email","a@b"); g(c,"config","user.name","a")
EventStore.init(c1/"mm","h1",autocommit=True); a = Manager(c1/"mm", actor="impl:a"); a.create_milestone("MM-A","A")
print("push1", g(c1,"push","origin","HEAD:master"))
c2 = base/"c2"; g(base,"clone",str(origin),str(c2)); g(c2,"config","user.email","a@b"); g(c2,"config","user.name","a")
cfg = json.loads((c2/"mm"/"mm.json").read_text()); cfg["host_id"]="h2"; (c2/"mm"/"mm.json").write_text(json.dumps(cfg))
b = Manager(c2/"mm", actor="impl:b"); b.create_milestone("MM-B","B")
a.create_milestone("MM-C","C"); print("push a", g(c1,"push","origin","HEAD:master")[0])
print("pull b", g(c2,"pull","--no-rebase","origin","master"))
print("b anchors.json head:", (c2/"mm"/"anchors.json").read_text()[:200].replace("\n"," "))
print("b verify:", Manager(c2/"mm").store.verify()["ok"], Manager(c2/"mm").store.verify()["errors"])
