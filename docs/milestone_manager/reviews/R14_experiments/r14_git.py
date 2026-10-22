from common import *
import subprocess, io, contextlib
def cli_run(home, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: rc = cli.run(["--home", str(home), *args])
        except SystemExit as e: rc = e.code
    return rc, buf.getvalue()
home = Path(tempfile.mkdtemp())/"L"; home.mkdir()
g = lambda *a: subprocess.run(["git", "-C", str(home), *a], capture_output=True, text=True)
g("init", "-q"); g("config", "user.name", "t"); g("config", "user.email", "t@t")
EventStore.init(home, "h1", autocommit=True)
g("add", "-A"); g("commit", "-qm", "init")
ow = EventStore.write_anchors
EventStore.write_anchors = lambda self, segs: (_ for _ in ()).throw(OSError("simulated"))
m = Manager(home, actor="impl:a"); m.create_milestone("MM-A", "A"); print("warn1", m.last_warnings)
EventStore.write_anchors = ow
print("git status after first", g("status", "--porcelain").stdout.strip())
rc, out = cli_run(home, "--actor", "impl:a", "milestone-add", "MM-B", "--title", "B"); print("refusal rc", rc, out.replace("\n"," ")[:250])
print("git log", g("log", "--oneline").stdout.strip().splitlines()); print("git status", repr(g("status", "--porcelain").stdout.strip()))
rc, out = cli_run(home, "--actor", "impl:a", "milestone-add", "MM-B", "--title", "B"); print("retry rc", rc)
# autocommit error on the refusal is reported?
home2 = Path(tempfile.mkdtemp())/"L"; home2.mkdir()
subprocess.run(["git", "-C", str(home2), "init", "-q"])
EventStore.init(home2, "h1", autocommit=True)
EventStore.write_anchors = lambda self, segs: (_ for _ in ()).throw(OSError("simulated"))
Manager(home2, actor="impl:a").create_milestone("MM-A", "A")
EventStore.write_anchors = ow
oac = EventStore.autocommit
EventStore.autocommit = lambda self, label: {"committed": False, "error": "simulated commit failure"}
rc, out = cli_run(home2, "--actor", "impl:a", "milestone-add", "MM-B", "--title", "B"); print("refusal w/ autocommit error rc", rc, "mentions error:", "simulated commit failure" in out)
rc, out = cli_run(home2, "--actor", "impl:a", "milestone-add", "MM-C", "--title", "C"); print("normal w/ autocommit error rc", rc, "mentions error:", "simulated commit failure" in out)
