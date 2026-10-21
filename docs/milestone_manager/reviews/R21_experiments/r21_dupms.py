from common import *
import shutil, time
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-1","x"); ma.update_milestone("MM-1", candidate_commit=C1)
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb"); mb=Manager(B,actor="impl:b")
mb.create_milestone("MM-3","b version"); mb.request_approval("MM-1","INTEGRATION","b asks?")
time.sleep(0.05)
ma.create_milestone("MM-3","a version"); ma.request_approval("MM-1","INTEGRATION","a asks?")
ma.record_review("MM-1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")
p=ma.projection(); print("approvals", {k:(v["question"],v["status"]) for k,v in p["approvals"].items()}, "MM-3 title", p["milestones"]["MM-3"]["title"], "dups", [d["as"] for d in p["duplicates"]])
for ent,i in sorted({(r["entity"],r["id"]) for r in views.conflict_rows(p)}): ma.resolve_conflict(ent,"dup reviewed",[i])
ma.set_status("MM-1","ACCEPTED","go")
dupkey=[k for k in p["approvals"] if "@" in k][0]; print("resolving dup approval", dupkey)
ma.resolve_approval(dupkey,"APPROVED","yes integrate","chat"); ma.record_integration("MM-1","master",C1)
ma.set_status("MM-1","INTEGRATED","merged"); p=ma.projection(); print("MM-1", p["milestones"]["MM-1"]["status"], p["milestones"]["MM-1"]["status_history"][-1]["basis"], "open", views.conflict_rows(p))
ma.update_milestone("MM-3", candidate_commit=C2); ma.record_review("MM-3", C2, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok"); ma.set_status("MM-3","ACCEPTED","go")
print("MM-3", ma.projection()["milestones"]["MM-3"]["status"], "verify", ma.store.verify()["ok"])
shutil.copy(A/"events/ha.jsonl", B/"events/ha.jsonl"); pb=Manager(B).projection(); print("B view", pb["milestones"]["MM-1"]["status"], pb["milestones"]["MM-3"]["status"], views.conflict_rows(pb), pb["integrity_errors"])
