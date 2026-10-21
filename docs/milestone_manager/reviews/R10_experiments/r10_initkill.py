from common import *
import subprocess, shutil, io
# hook: N = which call kills. points: 'wa1' first write_anchors, 'wa2' second, 'git' in_git, 'app' append_many
def run(point):
    base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
    shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
    child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
P = "{point}"; n = {{"wa":0}}
ow = EventStore.write_anchors; oi = EventStore.in_git; oa = EventStore.append_many
def wa(self, segs):
    n["wa"] += 1
    if P == "wa%d" % n["wa"]: os._exit(9)
    return ow(self, segs)
def ig(self):
    if P == "git": os._exit(9)
    return oi(self)
def am(self, *a, **k):
    r = oa(self, *a, **k)
    if P == "app": os._exit(9)
    return r
EventStore.write_anchors = wa; EventStore.in_git = ig; EventStore.append_many = am
EventStore.init_host(r"{home}", "hb")
'''
    rc = subprocess.run([sys.executable, "-c", child]).returncode
    print(f"[{point}] child rc", rc, "host.json", (home/"local/host.json").exists(), "seg", (home/"events/hb.jsonl").exists(), "anchors", (home/"local/anchors.json").exists())
    for args in (["status"], ["--actor","impl:b","milestone-add","MM-B","--title","B"], ["init-host","--host-id","hb2"]):
        o = io.StringIO()
        try: rc = cli.run(["--home", str(home), *args], out=o)
        except SystemExit as e: rc = f"exit {e.code}"
        print("   ", args[:3], "rc", rc, o.getvalue().replace("\n"," ")[:160])
    try:
        m = Manager(home, actor="x"); print("    open", [c["type"] for c in m.projection()["conflicts"] if not c["resolved"]])
    except Exception as e: print("    mgr", e)
for p in ("git","wa1","app","wa2"): run(p)
