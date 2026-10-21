from common import *
import shutil, io, contextlib, time
def cli_run(home, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try: rc = cli.run(["--home", str(home), *args])
        except SystemExit as e: rc = e.code
    return rc, buf.getvalue().strip()
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-X","x"); ma.create_milestone("MM-Y","y")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b")
mb.update_milestone("MM-X", next_action="B edit")          # U  (t1)
push1 = (B/"events/hb.jsonl").read_bytes()
mb.update_milestone("MM-Y", candidate_commit=C2)
mb.record_review("MM-Y", C2, "subagent", "rev:q", "SUBAGENT", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "B review")  # RV-0001 (t3)
time.sleep(0.05)
ma=Manager(A,actor="impl:a"); ma.update_milestone("MM-X", candidate_commit=C1)
ma.record_review("MM-X", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "A review")  # RV-0001 (ta)
w = ma.set_status("MM-X","ACCEPTED","go"); H = w[0]["hash"][:12]; print("H", H, "basis", w[0]["data"].get("basis"))
(A/"events/hb.jsonl").write_bytes(push1)   # sync 1 (git pull of B's first push)
p = Manager(A).projection()
rows = views.conflict_rows(p); print("after sync1:", [(r["id"], r["entity"], r["type"]) for r in rows])
for ent in sorted({r["entity"] for r in rows}):
    args=[]; [args.extend(["--id", i]) for i in sorted({r["id"] for r in rows if r["entity"]==ent})]
    print(" resolve", ent, cli_run(A, "--actor","impl:a","resolve-conflict", ent, *args, "--note","reviewed: B's edit is harmless")[0])
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")  # sync 2
p = Manager(A).projection()
print("all conflicts raised by H:", [(c["type"], c["entity"], c["resolved"], c.get("missing")) for c in p["conflicts"] if c["event"]["hash"].startswith(H)])
rows = views.conflict_rows(p); print("after sync2 displayed:", [(r["id"], r["entity"], r["type"]) for r in rows])
for ent in sorted({r["entity"] for r in rows}):
    args=[]; [args.extend(["--id", i]) for i in sorted({r["id"] for r in rows if r["entity"]==ent})]
    print(" resolve", ent, cli_run(A, "--actor","impl:a","resolve-conflict", ent, *args, "--note","both reviews kept")[0])
p = Manager(A).projection(); m = p["milestones"]["MM-X"]
print("MM-X status", m["status"], "basis", m["status_history"][-1].get("basis"), "-> RV-0001 subject", p["reviews"]["RV-1"]["subject"], p["reviews"]["RV-1"]["verdict"])
print("open", views.conflict_rows(p)); print(cli_run(A, "--no-emoji", "status", "--no-tasks")[1])
print("verify", EventStore(A).verify()["ok"])
