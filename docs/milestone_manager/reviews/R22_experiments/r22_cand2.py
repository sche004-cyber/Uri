from common import *
import shutil, time, io, json
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-1","x"); ma.update_milestone("MM-1", candidate_commit=C1)
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb"); mb=Manager(B,actor="impl:b")
ma.record_review("MM-1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok"); ma.set_status("MM-1","ACCEPTED","go")
ma.request_approval("MM-1","INTEGRATION","merge?"); ma.resolve_approval("AP-1","APPROVED","yes","chat")
ma.record_integration("MM-1","master",C1); ma.set_status("MM-1","INTEGRATED","merged")
time.sleep(0.05); mb.update_milestone("MM-1", candidate_commit=C2, next_action="continue")
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")
p=ma.projection(); rows=views.conflict_rows(p); print("conflicts", [(r["type"],r["entity"],r["recorded_by"],r["detail"]) for r in rows])
for ent,i in sorted({(r["entity"],r["id"]) for r in rows}): ma.resolve_conflict(ent,"seen",[i])
p=ma.projection(); m=p["milestones"]["MM-1"]
print("after:", m["status"], m["candidate_commit"][:4], "integration cand", m["integration"]["candidate_commit"][:4], views.indicator(p,m)["color"], views.indicator(p,m)["issue"])
o=io.StringIO(); cli.run(["--home",str(A),"status","--json","--no-tasks"],out=o); j=json.loads(o.getvalue()); print([ (x["id"],x["status"],x["indicator"]["color"],x["candidate_commit"][:4]) for x in j["milestones"]])
