from common import *
import io, subprocess, shutil
import scripts.dev_workflow.milestones.service as SV
def g(cwd,*a): r=subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip()[:300].replace("\n"," | ")
# R6-03: abandon fails after recover
m = new(); m.create_milestone("MM-A","A"); 
with m.store.segment_path.open("ab") as f: f.write(b'{"x')
orig = SV.Manager.abandon_batches
SV.Manager.abandon_batches = lambda self, r: (_ for _ in ()).throw(SV.StoreError("LOCK_TIMEOUT","x"))
o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=o)
SV.Manager.abandon_batches = orig
print("R6-03 abandon fail rc", rc, o.getvalue().replace("\n"," ")[:300])
# also invalid --reason (ValidationError from check_text)? 
m = new(); m.create_milestone("MM-A","A")
with m.store.segment_path.open("ab") as f: f.write(b'{"x')
o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover", "--reason", ""], out=o); print("empty reason rc", rc, o.getvalue().replace("\n"," ")[:200])
# R6-03 consistency: acknowledged recover re-base: anchors after = all segments counts?
m = new(); [m.create_milestone(f"MM-{i}","x") for i in range(3)]
lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]; m.store.segment_path.write_bytes(b"\n".join(lines[:-1])+b"\n"+b'{"v')
r = m.store.recover("impl:a", None, True); a = m.store.read_anchors(); print("ack recover anchors", {k:v["count"] for k,v in a.items()}, "seg events", len(m.store.read_all()[0].events), "verify", m.store.verify()["ok"])
# fresh git clone init-host, autocommit False (default), events committed manually
base = Path(tempfile.mkdtemp()); origin = base/"o.git"; g(base,"init","--bare",str(origin))
c1 = base/"c1"; g(base,"clone",str(origin),str(c1)); g(c1,"config","user.email","a@b"); g(c1,"config","user.name","a")
EventStore.init(c1/"mm","pc1"); a=Manager(c1/"mm",actor="impl:a"); a.create_milestone("MM-A","A")
print("add/commit", g(c1,"add","-A")[0], g(c1,"commit","-qm","x")[0], "push", g(c1,"push","origin","HEAD:master")[0])
c2 = base/"c2"; g(base,"clone",str(origin),str(c2))
try: st = EventStore.init_host(c2/"mm","pc2"); print("fresh clone (autocommit off) init-host OK; git", st.git_state(), "verify", st.verify()["ok"])
except StoreError as e: print("fresh clone init-host REFUSED", e)
# fresh clone with core.autocrlf=true explicit
c3 = base/"c3"; g(base,"-c","core.autocrlf=true","clone",str(origin),str(c3)); g(c3,"config","core.autocrlf","true")
print("c3 crlf?", b"\r\n" in (c3/"mm"/"events"/"pc1.jsonl").read_bytes())
try: st = EventStore.init_host(c3/"mm","pc3"); b=Manager(c3/"mm",actor="impl:b"); b.create_milestone("MM-C","C"); print("autocrlf clone init-host+write OK verify", b.store.verify()["ok"], b.store.git_state())
except StoreError as e: print("autocrlf clone init-host REFUSED", e)
# original host wipes local/ with a clean tree -> re-register
shutil.rmtree(c1/"mm"/"local")
try: st = EventStore.init_host(c1/"mm","pc1b"); print("clean-tree re-register OK; adopted", [e["data"] for s in st.read_all() for e in s.events if e["kind"]=="HOST_REGISTERED"])
except StoreError as e: print("clean re-register REFUSED", e)
# ledger inside parent repo, never committed (autocommit off) -> local wiped -> init-host
base = Path(tempfile.mkdtemp()); g(base,"init","-q"); EventStore.init(base/"mm","h1"); Manager(base/"mm",actor="impl:a").create_milestone("MM-A","A")
shutil.rmtree(base/"mm"/"local"); gi_before=(base/"mm"/".gitignore").exists()
try: EventStore.init_host(base/"mm","h2"); print("untracked ledger re-register OK")
except StoreError as e: print("untracked ledger re-register:", e.code, "| host.json left:", (base/"mm"/"local"/"host.json").exists(), "| local dir left:", (base/"mm"/"local").exists())
# init_host with lock held by another process -> append fails -> host.json left?
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local"))
import scripts.dev_workflow.milestones.store as S
S.LOCK_TIMEOUT_S = 0.3
import contextlib
holder = S.os_lock(base/"B"/".lock"); holder.__enter__()
try:
    EventStore.init_host.__func__ if False else None
    S.os_lock.__defaults__ = (0.3,)
    EventStore.init_host(base/"B","hb"); print("init_host under lock: OK?")
except StoreError as e: print("init_host under held lock:", e.code, "| host.json left:", (base/"B"/"local"/"host.json").exists())
holder.__exit__(None,None,None)
try:
    B = Manager(base/"B", actor="impl:b"); p = B.projection(); print("  after: integrity errors", p["integrity_errors"][:1], "| retry init-host:", end=" ")
    try: EventStore.init_host(base/"B","hb2"); print("OK")
    except StoreError as e: print(e.code)
except StoreError as e: print("  after: Manager", e.code)
