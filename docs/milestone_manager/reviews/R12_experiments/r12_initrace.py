from common import *
import subprocess, shutil, io, time, sys
def mk():
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
    EventStore.init_host(home, "hb"); mb = Manager(home, actor="impl:b"); mb.create_milestone("MM-B","B"); mb.create_milestone("MM-B2","B2")
    seg = home/"events/hb.jsonl"; lines = seg.read_bytes().split(b"\n"); seg.write_bytes(b"\n".join(lines[:1]) + b"\n")
    (home/"local/host.json").unlink()
    return home
trials = int(sys.argv[1]); fails = 0; results = {}
for t in range(trials):
    home = mk()
    reader = f'''
import sys, time; sys.path.insert(0, r"{T}/exp"); from common import *
t0 = time.time(); n = 0; other = 0
while time.time() - t0 < 2.5:
    try: Manager(r"{home}", actor="x").projection(); n += 1
    except StoreError as e:
        if e.code != "NO_HOST_ID": other += 1; print("READER", e.code, flush=True)
    except BaseException as e: other += 1; print("READER", type(e).__name__, str(e)[:80], flush=True)
print("reads", n)
'''
    rs = [subprocess.Popen([sys.executable, "-c", reader], stdout=subprocess.PIPE, text=True) for _ in range(4)]
    time.sleep(0.8)
    try: EventStore.init_host(home, "hc", acknowledge_loss=True); r = "ok"
    except BaseException as e: r = f"{type(e).__name__}"; fails += 1; print("trial", t, "init-host raised", type(e).__name__, str(e)[:90])
    outs = [x.communicate()[0] for x in rs]
    for o in outs:
        if "READER" in o: print("trial", t, [l for l in o.splitlines() if "READER" in l][:2])
    if r != "ok":
        st = dict(host=(home/"local/host.json").exists(), seg=(home/"events/hc.jsonl").exists(), marker=(home/"local/pending_loss.json").exists())
        print("   state after failure:", st)
        try: EventStore.init_host(home, "hc", acknowledge_loss=True); print("   retry ok")
        except BaseException as e: print("   retry", getattr(e,"code",type(e).__name__))
print("trials", trials, "init-host failures", fails)
