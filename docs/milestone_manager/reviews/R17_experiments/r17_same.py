from common import *
import shutil, time
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-X","x")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b")
mb.update_milestone("MM-X", next_action="B edit")          # U1
push1 = (B/"events/hb.jsonl").read_bytes()
mb.record_implementer("MM-X", "rev:y")                      # U2: the later reviewer is an implementer of MM-X
time.sleep(0.05)
ma=Manager(A,actor="impl:a"); ma.update_milestone("MM-X", candidate_commit=C1)
ma.record_review("MM-X", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "A review")
w = ma.set_status("MM-X","ACCEPTED","go"); H=w[0]["hash"][:12]
(A/"events/hb.jsonl").write_bytes(push1)   # sync 1: only U1
p = Manager(A).projection(); rows = views.conflict_rows(p)
print("after sync1 shown:", [(r["id"], r["type"], r["detail"]) for r in rows])
print("resolve", ma.resolve_conflict("MM-X", "reviewed: B's next_action edit is harmless", sorted({r["id"] for r in rows}))[0]["data"]["seen"])
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")  # sync 2: U2
p = Manager(A).projection()
print("H conflicts now:", [(c["type"], c.get("expected"), c.get("actual"), c["resolved"]) for c in p["conflicts"] if c["event"]["hash"].startswith(H)])
print("open after sync2:", views.conflict_rows(p))
m = p["milestones"]["MM-X"]; print("MM-X", m["status"], "implementers", m["implementers"], "basis reviewer", p["reviews"]["RV-1"]["reviewer"])
print("indicator", views.indicator(p, m)["color"], views.indicator(p, m)["issue"])
# would the guard accept now?
try: Manager(A,actor="impl:a").guard_status(p, m, "ACCEPTED"); print("guard now: ok")
except Exception as e: print("guard now refuses:", e)
print("verify", EventStore(A).verify()["ok"])
