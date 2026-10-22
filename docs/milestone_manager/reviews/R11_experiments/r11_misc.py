from common import *
import shutil, io, subprocess
def c(home, *args):
    o = io.StringIO()
    try: rc = cli.run(["--home", str(home), *args], out=o)
    except SystemExit as e: rc = f"exit {e.code}"
    return rc, o.getvalue().replace("\n"," ")[:140]
def g(cwd,*a): r=subprocess.run(["git","-C",str(cwd),*a],capture_output=True,text=True); return r.returncode, (r.stdout+r.stderr).strip()[:200].replace("\n"," | ")
# 1 corrupt host.json loop
m = new(); m.create_milestone("MM-A","A"); hp = m.store.host_path; hp.write_bytes(b"")
print("1 status:", c(m.home, "status")); print("  init-host:", c(m.home, "init-host", "--host-id", "h9"))
# 2 ack flow: blocks positive status until resolve
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
EventStore.init_host(home, "hb"); mb = Manager(home, actor="impl:b"); mb.create_milestone("MM-B","B"); mb.update_milestone("MM-B", candidate_commit=C1)
mb.record_review("MM-B", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "x")
seg = home/"events/hb.jsonl"; L = seg.read_bytes().split(b"\n"); seg.write_bytes(b"\n".join(L[:-2]) + b"\n"); (home/"local/host.json").unlink()
print("2 init-host hc:", c(home, "init-host", "--host-id", "hc")[1][:90])
print("  with ack:", c(home, "init-host", "--host-id", "hc", "--acknowledge-loss")[0])
mc = Manager(home, actor="impl:c"); mc.create_milestone("MM-C","C"); mc.update_milestone("MM-C", candidate_commit=C1)
mc.record_review("MM-C", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "x")
try: mc.set_status("MM-C","ACCEPTED","r"); print("  ACCEPTED allowed while ANCHOR_LOSS open (BAD)")
except Exception as e: print("  ACCEPTED refused", getattr(e,"code",e))
print("  status shows:", c(home, "status")[1][:120])
print("  resolve:", c(home, "--actor", "owner", "resolve-conflict", "LEDGER", "--resolution", "reviewed")[0:2])
try: mc.set_status("MM-C","ACCEPTED","r"); print("  ACCEPTED after resolve OK")
except Exception as e: print("  ACCEPTED still refused", getattr(e,"code",e))
# 3 legit: multi-host git, other host advances via pull, machine loses only host.json -> re-register
b2 = Path(tempfile.mkdtemp()); o = b2/"o.git"; g(b2,"init","-q","--bare",str(o))
c1 = b2/"c1"; g(b2,"clone","-q",str(o),str(c1)); g(c1,"config","user.email","a@b"); g(c1,"config","user.name","a")
EventStore.init(c1/"mm","p1",autocommit=True); Manager(c1/"mm",actor="impl:a").create_milestone("MM-A","A"); g(c1,"push","-q","origin","HEAD:master")
c2 = b2/"c2"; g(b2,"clone","-q",str(o),str(c2)); g(c2,"config","user.email","a@b"); g(c2,"config","user.name","a")
EventStore.init_host(c2/"mm","p2"); Manager(c2/"mm",actor="impl:b").create_milestone("MM-B","B"); g(c2,"push","-q","origin","HEAD:master")
g(c1,"pull","-q","--no-rebase","origin","master"); Manager(c1/"mm",actor="impl:a").create_milestone("MM-A2","A2"); g(c1,"push","-q","origin","HEAD:master")
g(c2,"pull","-q","--no-rebase","origin","master")
(c2/"mm/local/host.json").unlink()
print("3 re-register after losing host.json:", c(c2/"mm","init-host","--host-id","p2b")[0], "verify", EventStore(c2/"mm").verify()["ok"], "open", [x["type"] for x in Manager(c2/"mm").projection()["conflicts"] if not x["resolved"]])
# 3b fresh clone then git clean -fdx then re-register
c3 = b2/"c3"; g(b2,"clone","-q",str(o),str(c3)); print("3b fresh clone init-host:", c(c3/"mm","init-host","--host-id","p3")[0]); g(c3,"clean","-fdx"); print("  after clean -fdx p3b:", c(c3/"mm","init-host","--host-id","p3b")[0])
