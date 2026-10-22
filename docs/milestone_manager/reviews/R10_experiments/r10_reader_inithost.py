from common import *
import subprocess, shutil, io, time, collections
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
# real, un-hooked init-host in a child (no artificial delay); parent polls status as fast as possible
child = f'''
import sys; sys.path.insert(0, r"{T}/exp"); from common import *
import time; time.sleep(0.5); EventStore.init_host(r"{home}", "hb"); print("done", flush=True)
'''
p = subprocess.Popen([sys.executable, "-c", child], stdout=subprocess.PIPE, text=True)
res = collections.Counter(); ex = {}
while p.poll() is None:
    o = io.StringIO()
    try: rc = cli.run(["--home", str(home), "status"], out=o)
    except SystemExit as e: rc = e.code
    res[rc] += 1; ex.setdefault(rc, o.getvalue().replace("\n"," ")[:200])
print("child", p.communicate()[0].strip(), "status rcs", dict(res))
for k,v in ex.items(): print(" ", k, v)
o = io.StringIO(); print("final status rc", cli.run(["--home", str(home), "status"], out=o))
