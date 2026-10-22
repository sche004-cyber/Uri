from common import *
import shutil, io, os
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
print("git on PATH:", shutil.which("git"))
m = Manager(base/"A", actor="impl:a"); m.create_milestone("MM-A2","A2"); print("normal write without git OK; verify", m.store.verify()["ok"], m.store.verify()["git"])
o = io.StringIO()
try: rc = cli.run(["--home", str(home), "init-host", "--host-id", "hb"], out=o); print("init-host rc", rc, o.getvalue()[:200])
except BaseException as e: print("init-host raised", type(e).__name__, str(e)[:120])
print("state: host.json", (home/"local/host.json").exists(), "anchors", (home/"local/anchors.json").exists())
