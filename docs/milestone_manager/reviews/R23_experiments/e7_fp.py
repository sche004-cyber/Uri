from common import *
import shutil, time
base=Path(tempfile.mkdtemp()); A=base/"A"
EventStore.init(A,"ha"); a=Manager(A,actor="impl:a"); a.create_milestone("MM-1","x"); a.update_milestone("MM-1",candidate_commit=C1)
mk=lambda n:(shutil.copytree(A,base/n,ignore=shutil.ignore_patterns("local",".lock")),EventStore.init_host(base/n,"h"+n.lower()),Manager(base/n,actor="impl:"+n))[2]
b=mk("B"); c=mk("C")
b.update_milestone("MM-1",candidate_commit=C2); time.sleep(0.02)
c.update_milestone("MM-1",candidate_commit=C3); time.sleep(0.02)
a.record_review("MM-1",C1,"subagent","rev:y","SUBAGENT","ACCEPT",0,0,"COMPLETED_WITH_RESULT","ok"); a.set_status("MM-1","ACCEPTED","go")
shutil.copy(b.home/"events/hb.jsonl",A/"events/hb.jsonl")
p=a.projection(); rows=views.conflict_rows(p,"MM-1"); print("after B sync:",[(r["id"],r["type"],r["detail"]) for r in rows])
for ent,i in sorted({(r["entity"],r["id"]) for r in rows}): a.resolve_conflict(ent,"saw C2 only",[i])
shutil.copy(c.home/"events/hc.jsonl",A/"events/hc.jsonl")
p=a.projection()
cc=[x for x in p["conflicts"] if x["type"]=="CANDIDATE_CHANGED"]
print("CANDIDATE_CHANGED after C sync:",[(x["candidate"][:4],x["resolved"],x.get("resolution",{}).get("note")) for x in cc])
print("open now:",[(r["type"],r["detail"]) for r in views.conflict_rows(p,"MM-1")])
print("indicator",views.indicator(p,p["milestones"]["MM-1"])["color"])
