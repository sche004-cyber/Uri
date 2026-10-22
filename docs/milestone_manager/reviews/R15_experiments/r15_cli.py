from common import *
import shutil, io, contextlib
def cli_run(home, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try: rc = cli.run(["--home", str(home), *args])
        except SystemExit as e: rc = e.code
    return rc, buf.getvalue().strip().replace("\n"," ")[:220]
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-0","base")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base/"B","hb")
ma, mb = Manager(base/"A",actor="impl:a"), Manager(base/"B",actor="impl:b")
ma.update_milestone("MM-0", title="a"); mb.update_milestone("MM-0", title="b"); mb.update_milestone("MM-0", title="b2")
shutil.copy(base/"B/events/hb.jsonl", base/"A/events/hb.jsonl")
A=base/"A"
p = Manager(A).projection(); rows = views.conflict_rows(p); print("rows", [(r["id"], r["entity"], r["type"]) for r in rows])
ids=[r["id"] for r in rows]
print("conflicts", cli_run(A, "conflicts")[0], "entity filter", cli_run(A, "conflicts", "--entity", "MM-0")[1][:80])
print("empty id", cli_run(A, "--actor","impl:a","resolve-conflict","MM-0","--id","","--note","x"))
print("short id", cli_run(A, "--actor","impl:a","resolve-conflict","MM-0","--id",ids[0][:7],"--note","x"))
print("upper 8", cli_run(A, "--actor","impl:a","resolve-conflict","MM-0","--id",ids[0][:8].upper(),"--note","x")[0])
p = Manager(A).projection(); print("open", [(c["event"]["hash"][:12]) for c in p["conflicts"] if not c["resolved"]])
print("mixed good+bad", cli_run(A, "--actor","impl:a","resolve-conflict","MM-0","--id",ids[1],"--id","deadbeef00","--note","x"))
p = Manager(A).projection(); print("open after mixed", [(c["event"]["hash"][:12]) for c in p["conflicts"] if not c["resolved"]])
print("missing value", cli_run(A, "resolve-conflict","MM-0","--note","x","--id"))
seg=A/"events/hb.jsonl"; seg.write_bytes(seg.read_bytes().replace(b'"b2"', b'"bX"'))
print("conflicts on tampered", cli_run(A, "conflicts")[0])
