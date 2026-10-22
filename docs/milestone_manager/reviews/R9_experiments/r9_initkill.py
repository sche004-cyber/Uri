from common import *
import subprocess, shutil, io
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
child = f'''
import sys, os; sys.path.insert(0, r"{T}/exp"); from common import *
EventStore.write_anchors = lambda self, segs: os._exit(9)
EventStore.init_host(r"{home}", "hb")
'''
print("child rc", subprocess.run([sys.executable, "-c", child]).returncode)
print("host.json", (home/"local/host.json").exists(), "seg", (home/"events/hb.jsonl").exists(), "anchors", (home/"local/anchors.json").exists())
for args in (["status"], ["verify"], ["--actor","impl:b","create-milestone","MM-B","--title","B"], ["--actor","impl:b","recover"], ["--actor","impl:b","reanchor","--reason","init-host crashed"], ["--actor","impl:b","reanchor","--reason","init-host crashed","--acknowledge-loss"], ["--actor","impl:b","create-milestone","MM-B","--title","B"]):
    o = io.StringIO()
    try: rc = cli.run(["--home", str(home), *args], out=o)
    except SystemExit as e: rc = f"exit {e.code}"
    print(args[-3:], "rc", rc, o.getvalue().replace("\n"," ")[:200])
m = Manager(home, actor="x"); print("open", [c["type"] for c in m.projection()["conflicts"] if not c["resolved"]])
