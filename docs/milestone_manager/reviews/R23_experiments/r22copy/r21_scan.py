from common import *
import shutil, time, io, re, json
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-1","x"); ma.create_milestone("MM-2","y")
ma.update_milestone("MM-1", candidate_commit=C1)
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b"); mb.update_milestone("MM-2", candidate_commit=C2); mb.record_implementer("MM-1","rev:y")
mb.create_milestone("MM-3","dup on b")
ma.record_review("MM-1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok"); time.sleep(0.05)
mb.record_review("MM-2", C2, "subagent", "rev:z", "SUBAGENT", "REJECT", 2, 2, "COMPLETED_WITH_RESULT", "no")
ma.set_status("MM-1","ACCEPTED","go"); ma.create_milestone("MM-3","dup on a")
ma.request_approval("MM-1","OWNER_DECISION" if "OWNER_DECISION" in model.APPROVAL_KINDS else model.APPROVAL_KINDS[0],"q?")
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")
# a ledger loss: reset own anchor to count 0 => next write records ANCHORS_ADOPTED
anc=json.loads(ma.store.anchors_path.read_text()); anc["ha"]={"count":0,"head":"0"*64}; ma.store.anchors_path.write_text(json.dumps(anc))
RX=re.compile(r"[0-9a-f]{12}\.[0-9a-f]{6}")
def cli_(*a):
    o=io.StringIO(); rc=cli.run(["--home",str(A),"--actor","impl:a","--no-emoji",*a],out=o); return rc,o.getvalue()
cmds=[("status","--no-tasks"),("status","--json","--no-tasks"),("status","--a2ui","--no-tasks"),("status","--milestone","MM-1","--no-tasks"),
("show","MM-1"),("show","RV-1"),("resume","MM-1","--no-tasks"),("resume","MM-3","--no-tasks"),("ready",),("log","--limit","200"),("verify",),("verify-evidence",),("rebuild",),
("milestone-add","MM-9","--title","t"),  # records ANCHORS_ADOPTED -> LEDGER_LOSS_RECORDED
("status","--no-tasks"),("conflicts","--entity","LEDGER"),
("status-set","MM-2","ACCEPTED","--reason","x"),("status-set","MM-1","DONE","--reason","x"),
("resolve-conflict","MM-1","--note","n"),("resolve-conflict","RV-1","--note","n","--id","zzzz"),
("resolve-conflict","LEDGER","--note","n"),("recover",),("reanchor","--reason","r"),("milestone-add","MM-10","--title","t"),
("review-add","MM-1","--commit",C1,"--reviewer-kind","subagent","--reviewer-id","q","--assurance","SUBAGENT","--verdict","ACCEPT","--blocking-open","0","--findings-total","0","--result","COMPLETED_WITH_RESULT","--summary","s"),
]
for c in cmds:
    rc,s=cli_(*c); ids=set(RX.findall(s))
    print(f"{' '.join(c)[:50]:50} rc={rc} ids={sorted(ids)}")
    if c[0]=="milestone-add" and "LEDGER_LOSS" in s: print("   LOSS MSG:", json.loads(s)["message"][:400])
print("conflicts all:")
for r in json.loads(cli_("conflicts")[1]): print("  ",r["id"],r["type"],r["entity"],r["subject"],r["subjects"],r["recorded_by"],r["detail"])
