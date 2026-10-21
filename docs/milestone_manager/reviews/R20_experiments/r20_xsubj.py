from common import *
import shutil, time, io, json
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-1","x"); ma.create_milestone("MM-2","y")
ma.update_milestone("MM-1", candidate_commit=C1)
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b"); mb.update_milestone("MM-2", candidate_commit=C2)
ma.record_review("MM-1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok"); time.sleep(0.05)
mb.record_review("MM-2", C2, "subagent", "rev:z", "SUBAGENT", "REJECT", 2, 2, "COMPLETED_WITH_RESULT", "no")
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")
def cli_(*a):
    o=io.StringIO(); rc=cli.run(["--home",str(A),"--actor","impl:a","--no-emoji",*a],out=o); return rc,o.getvalue()
print("STATUS:\n"+cli_("status","--no-tasks")[1])
rc,s=cli_("conflicts","--entity","MM-2"); rows=json.loads(s)
print("conflicts --entity MM-2 shows:", [(r["id"],r["type"],r["entity"],r["subject"],r["detail"]) for r in rows])
print("all conflicts:", [(r["id"],r["type"],r["entity"],r["subject"]) for r in json.loads(cli_("conflicts")[1])])
r=rows[0]; print("resolve", cli_("resolve-conflict", r["entity"], "--id", r["id"], "--note", "MM-2 duplicate reviewed")[0])
p=Manager(A).projection()
print("after:", [(c["type"], c["subject"], c["resolved"]) for c in p["conflicts"]])
print("MM-1 indicator:", views.indicator(p,p["milestones"]["MM-1"])["color"], views.indicator(p,p["milestones"]["MM-1"])["issue"])
ev=[e for s in Manager(A).store.read_all() for e in s.valid_events if e["kind"]=="CONFLICT_RESOLVED"][-1]
print("seen recorded:", ev["data"]["seen"])
