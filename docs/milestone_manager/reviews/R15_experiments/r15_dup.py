from common import *
import shutil, io, contextlib
def cli_run(home, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: rc = cli.run(["--home", str(home), *args])
        except SystemExit as e: rc = e.code
    return rc, buf.getvalue().strip()
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); Manager(base/"A",actor="impl:a").create_milestone("MM-0","base")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base/"B","hb")
ma, mb = Manager(base/"A",actor="impl:a"), Manager(base/"B",actor="impl:b")
ma.create_milestone("MM-X","from A"); mb.create_milestone("MM-X","from B")
ma.record_decision("DA","a","2026-10-22",sorted(model.EVIDENCE_CLASSES)[0],"x", ident="LDEC-900"); mb.record_decision("DB","b","2026-10-22",sorted(model.EVIDENCE_CLASSES)[0],"x", ident="LDEC-900")
shutil.copy(base/"B/events/hb.jsonl", base/"A/events/hb.jsonl")
A = base/"A"
rc, out = cli_run(A, "conflicts"); print("conflicts rc", rc); print(out)
rc, out = cli_run(A, "--no-emoji", "status", "--no-tasks"); print("status rc", rc); print(out)
p = Manager(A).projection()
for ent in ("MM-X", "LDEC-900"):
    ids = sorted({r["id"] for r in views.conflict_rows(p) if r["entity"] == ent})
    args = []
    for i in ids: args += ["--id", i]
    rc, out = cli_run(A, "--actor", "impl:a", "resolve-conflict", ent, *args, "--note", "reviewed both")
    print("resolve", ent, ids, "rc", rc, out.replace("\n"," ")[:300])
    rc, out = cli_run(A, "--actor", "impl:a", "resolve-conflict", ent, "--note", "x")
    print("resolve no id", ent, "rc", rc, out.replace("\n"," ")[:300])
p = Manager(A).projection()
print("open after", [(c["type"], c["entity"], c["event"]["hash"][:12]) for c in p["conflicts"] if not c["resolved"]])
# can MM-X ever reach ACCEPTED?
m = Manager(A, actor="impl:a"); m.update_milestone("MM-X", candidate_commit=C1)
m.record_review("MM-X", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
try: m.set_status("MM-X","ACCEPTED","go"); print("ACCEPTED ok")
except Exception as e: print("ACCEPTED refused", getattr(e,"code",e), e)
