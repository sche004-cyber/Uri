from common import *
import shutil, time, io, re
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-X","x")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b"); mb.record_implementer("MM-X", "rev:y")
time.sleep(0.05)
ma.update_milestone("MM-X", candidate_commit=C1)
ma.record_review("MM-X", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "A review")
ma.set_status("MM-X","ACCEPTED","go")
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")
def cli_(*a):
    o=io.StringIO(); rc=cli.run(["--home",str(A),"--actor","impl:a","--no-emoji",*a],out=o); return rc,o.getvalue()
rc,s=cli_("status","--no-tasks"); print("STATUS rc",rc); print(s)
rc,s=cli_("conflicts","--entity","MM-X"); print("CONFLICTS --entity MM-X:", s)
# user resolves "the VERSION gap" by entity name, as the status line names VERSION
rc,s=cli_("resolve-conflict","MM-X","--note","VERSION gap reviewed"); print("REFUSAL rc",rc, s)
ids=re.findall(r"[0-9a-f]{12}\.[0-9a-f]{6}", s); print("ids printed by refusal:", ids)
rc,s=cli_("resolve-conflict","MM-X","--note","VERSION gap reviewed",*sum([["--id",i] for i in ids],[])); print("RESOLVE rc",rc)
p=Manager(A).projection()
print("BASIS_INVALID resolved:", [(c["type"], c["resolved"]) for c in p["conflicts"]])
m=p["milestones"]["MM-X"]; print("MM-X", m["status"], views.indicator(p,m)["color"], views.indicator(p,m)["issue"])
