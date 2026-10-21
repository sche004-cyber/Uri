from common import *
import shutil, time
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-X","x")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b")
mb.update_milestone("MM-X", next_action="B edit")          # U1
push1 = (B/"events/hb.jsonl").read_bytes()
mb.record_implementer("MM-X", "rev:y")                      # U2
time.sleep(0.05)
ma=Manager(A,actor="impl:a"); ma.update_milestone("MM-X", candidate_commit=C1)
ma.record_review("MM-X", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "A review")
w = ma.set_status("MM-X","ACCEPTED","go"); H=w[0]["hash"][:12]
(A/"events/hb.jsonl").write_bytes(push1)   # sync 1: only U1
rows = views.conflict_rows(Manager(A).projection())
print("DISPLAYED to resolver:", [(r["id"], r["type"], r["detail"]) for r in rows])
ids = sorted({r["id"] for r in rows})
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")  # sync 2 (git pull) BEFORE the resolver acts
w = ma.resolve_conflict("MM-X", "reviewed what I was shown", ids)
print("seen recorded:", w[0]["data"]["seen"])
p = Manager(A).projection(); m = p["milestones"]["MM-X"]
print("open after resolve:", views.conflict_rows(p))
print("resolved BASIS_INVALID never displayed:", [(c["type"], c["missing"], c["resolved"]) for c in p["conflicts"] if c["type"]=="BASIS_INVALID"])
print("MM-X", m["status"], "implementers", m["implementers"], "basis reviewer", p["reviews"]["RV-1"]["reviewer"]["id"])
print("indicator", views.indicator(p, m)["color"], views.indicator(p, m)["issue"])
print("verify", EventStore(A).verify()["ok"])
