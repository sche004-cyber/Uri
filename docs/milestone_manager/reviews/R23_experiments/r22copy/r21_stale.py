from common import *
import shutil, time, io, re, json
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-X","x")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b")
mb.update_milestone("MM-X", next_action="B edit")          # U1
push1 = (B/"events/hb.jsonl").read_bytes()
mb.record_implementer("MM-X", "rev:y")                      # U2 makes reviewer an implementer
time.sleep(0.05)
ma=Manager(A,actor="impl:a"); ma.update_milestone("MM-X", candidate_commit=C1)
ma.record_review("MM-X", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "A review")
ma.set_status("MM-X","ACCEPTED","go")
(A/"events/hb.jsonl").write_bytes(push1)   # sync 1: only U1
def cli_(*a):
    o=io.StringIO(); rc=cli.run(["--home",str(A),"--actor","impl:a","--no-emoji",*a],out=o); return rc,o.getvalue()
rc,s=cli_("conflicts","--entity","MM-X"); rows=json.loads(s)
print("DISPLAYED:", [(r["id"], r["type"], r["detail"]) for r in rows])
ids = sorted({r["id"] for r in rows})
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")  # sync 2 before resolver acts
args=sum([["--id",i] for i in ids],[])
rc,s=cli_("resolve-conflict","MM-X","--note","reviewed",*args); print("first try rc",rc,s)
new_ids=[i for i in re.findall(r"[0-9a-f]{12}\.[0-9a-f]{6}", s) if i not in ids]
print("ids leaked by refusal that were never displayed:", new_ids)
# user retries with displayed ids replaced by the leaked one(s), never running `conflicts` again
retry=[new_ids[0] if i.split(".")[0]==new_ids[0].split(".")[0] else i for i in ids] if new_ids else ids
while True:
    rc,s=cli_("resolve-conflict","MM-X","--note","reviewed",*sum([["--id",i] for i in retry],[]))
    print("retry rc",rc,s.strip()[:300])
    more=[i for i in re.findall(r"[0-9a-f]{12}\.[0-9a-f]{6}", s) if i not in retry]
    if rc==0 or not more: break
    retry=[more[0] if i.split(".")[0]==more[0].split(".")[0] else i for i in retry]
p=Manager(A).projection()
print("conflicts now:", [(c["type"], c.get("missing") or (c.get("expected"),c.get("actual")), c["resolved"]) for c in p["conflicts"]])
m=p["milestones"]["MM-X"]; print("MM-X", m["status"], views.indicator(p,m)["color"], views.indicator(p,m)["issue"])
