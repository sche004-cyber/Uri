from common import *
S="ghp_"+"d"*36
def setup():
    m=new(); m.create_milestone("MM-A","A"); m.update_milestone("MM-A",candidate_commit=C1)
    m.add_blocker("MM-A","TECHNICAL","r","n"); m.request_approval("MM-A","SCOPE","q?")
    m.record_decision("t","d","2026-10-22","OTHER","src")
    return m
cmds=[["milestone-add","MM-B","--title",S],["milestone-add","MM-B","--title","t","--objective",S],
["milestone-add","MM-B","--title","t","--worktree",S],["milestone-add","MM-B","--title","t","--branch",S],
["milestone-add","MM-B","--title","t","--next-action",S],["milestone-add","MM-B","--title","t","--acceptance-ref",S],
["milestone-add","MM-B","--title","t","--priority","P1 "+S[:10]],
["milestone-update","MM-A","--objective",S],["milestone-update","MM-A","--title",S],["milestone-update","MM-A","--next-action",S],
["status-set","MM-A","PAUSED","--reason",S],["dep-remove","MM-A","MM-A","--reason",S],
["assign","MM-A","--worktree",S],["release","MM-A","--reason",S],["implementer-add","MM-A",S],
["blocker-add","MM-A","--kind","OTHER","--reason",S,"--needs","n"],["blocker-add","MM-A","--kind","OTHER","--reason","r","--needs",S],
["blocker-resolve","BLK-1","--resolution",S],
["evidence-add","MM-A","--kind","log","--ref",S,"--result","COMPLETED_WITH_RESULT","--summary","s","--no-hash"],
["evidence-add","MM-A","--kind","log","--ref","r","--result","COMPLETED_WITH_RESULT","--summary",S,"--no-hash"],
["review-add","MM-A","--commit",C1,"--reviewer-kind","other","--reviewer-id",S,"--assurance","SUBAGENT","--verdict","ACCEPT","--blocking-open","0","--findings-total","0","--result","COMPLETED_WITH_RESULT","--summary","s"],
["review-add","MM-A","--commit",C1,"--reviewer-kind","other","--reviewer-id","r","--assurance","SUBAGENT","--verdict","ACCEPT","--blocking-open","0","--findings-total","0","--result","COMPLETED_WITH_RESULT","--summary",S],
["approval-request","MM-A","--kind","SCOPE","--question",S],
["approval-resolve","AP-1","APPROVED","--owner-words",S,"--source","chat"],["approval-resolve","AP-1","APPROVED","--owner-words","yes","--source",S],
["approval-resolve","AP-1","WITHDRAWN","--reason",S],
["decision-add","--title",S,"--decision","d","--date","x","--evidence-class","OTHER","--source","s"],
["decision-add","--title","t","--decision",S,"--date","x","--evidence-class","OTHER","--source","s"],
["decision-add","--title","t","--decision","d","--date",S[:39],"--evidence-class","OTHER","--source","s"],
["decision-add","--title","t","--decision","d","--date","x","--evidence-class","OTHER","--source",S],
["decision-add","--title","t","--decision","d","--date","x","--evidence-class","OTHER","--source","s","--proposal",S],
["decision-add","--title","t","--decision","d","--date","x","--evidence-class","OTHER","--source","s","--reasoning",S],
["decision-add","--title","t","--decision","d","--date","x","--evidence-class","OTHER","--source","s","--alternatives-rejected",S],
["decision-add","--title","t","--decision","d","--date","x","--evidence-class","OTHER","--source","s","--consequences",S],
["decision-add","--title","t","--decision","d","--date","x","--evidence-class","OTHER","--source","s","--related",S],
["decision-add","--title","t","--decision","d","--date","x","--evidence-class","OTHER","--source","s","--supersedes","LDEC-001","--note",S],
["decision-supersede","LDEC-001","--by","LDEC-001","--note",S],
["decision-correct","LDEC-001","--correction",S,"--evidence-class","OTHER","--source","s"],
["decision-correct","LDEC-001","--correction","c","--evidence-class","OTHER","--source",S],
["handoff","MM-A","--summary",S],["handoff","MM-A","--summary","s","--done",S],["handoff","MM-A","--summary","s","--next",S],
["handoff","MM-A","--summary","s","--files",S],
["link-lifecycle","MM-A","D:/x/"+S],["link-lifecycle","MM-A","D:/x","--config",S],
["integration-record","MM-A","--target-ref",S,"--target-commit",C1],
["resolve-conflict","MM-A","--note",S,"--id","abc"],
["recover","--reason",S],
]
bad=0
for c in cmds:
    m=setup(); b=segbytes(m.home)
    rc,out=runcli("--home",str(m.home),"--actor","impl:a",*c)
    same=segbytes(m.home)==b
    o=json.loads(out) if out.strip().startswith("{") else {}
    code=o.get("refused") or o.get("error")
    ok = rc!=0 and same and S not in "".join(x.decode() for x in segbytes(m.home).values())
    if not ok or code not in ("SECRET",): print("CHECK", c[:2], rc, code, same, out[:200].replace("\n"," "))
    bad+= not ok
print("commands", len(cmds), "not-refused", bad)
