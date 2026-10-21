from common import *
import shutil, io
def c(home, *args):
    o = io.StringIO()
    try: rc = cli.run(["--home", str(home), *args], out=o)
    except SystemExit as e: rc = f"exit {e.code}"
    return rc, o.getvalue().replace("\n"," ")[:170]
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); home = base/"B"
print("init-host hb", c(home, "init-host", "--host-id", "hb"))
print("hb write", c(home, "--actor", "impl:b", "milestone-add", "MM-B", "--title", "B")[0], c(home, "--actor", "impl:b", "milestone-add", "MM-B2", "--title", "B2")[0])
# genuine loss of hb's applied events + host.json removed (e.g. machine re-registration)
seg = home/"events/hb.jsonl"; lines = seg.read_bytes().split(b"\n"); seg.write_bytes(b"\n".join(lines[:1]) + b"\n")
(home/"local/host.json").unlink()
print("init-host hc ->", c(home, "init-host", "--host-id", "hc"))
print("reanchor --acknowledge-loss (remedy in message) ->", c(home, "--actor", "impl:c", "reanchor", "--reason", "x", "--acknowledge-loss"))
print("init-host hb again ->", c(home, "init-host", "--host-id", "hb"))
(home/"local/anchors.json").unlink()
print("after manual anchors deletion: init-host hc ->", c(home, "init-host", "--host-id", "hc"))
m = Manager(home, actor="x"); p = m.projection()
print("milestones", sorted(p["milestones"]), "open conflicts", [x["type"] for x in p["conflicts"] if not x["resolved"]], "errors", p["integrity_errors"], "verify", m.store.verify()["ok"])
