from common import *
import shutil, time, re
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-X","x")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b"); mb.record_implementer("MM-X", "rev:y")      # concurrent: reviewer becomes implementer
time.sleep(0.05)
ma.update_milestone("MM-X", candidate_commit=C1)
ma.record_review("MM-X", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "A review")
ma.set_status("MM-X","ACCEPTED","go")
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")      # sync
p = Manager(A).projection()
sl = views.status_lines(p, False, None, None)
print("STATUS:"); print("\n".join(sl))
print("CONFLICTS:", [(r["id"], r["type"], r["detail"]) for r in views.conflict_rows(p)])
ent, cid = re.search(r"`resolve-conflict (\S+) --id (\S+)`", "\n".join(sl)).groups()
ma.resolve_conflict(ent, "VERSION gap reviewed (as shown by status)", [cid])
p = Manager(A).projection(); m=p["milestones"]["MM-X"]
print("after following status instruction: open", views.conflict_rows(p))
print("BASIS_INVALID resolved:", [(c["type"], c["missing"], c["resolved"]) for c in p["conflicts"] if c["type"]=="BASIS_INVALID"])
print("MM-X", m["status"], "implementers", m["implementers"], "indicator", views.indicator(p,m)["color"])
