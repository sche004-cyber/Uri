from common import *
def tryit(label, f):
    try: f(); print(label, "ALLOWED")
    except ValidationError as e: print(label, "refused", e.code)
m = new(); m.create_milestone("MM-1","x"); m.update_milestone("MM-1", candidate_commit=C1)
m.request_approval("MM-1","INTEGRATION","ok?"); m.resolve_approval("AP-1","APPROVED","yes","chat")
m.update_milestone("MM-1", candidate_commit=C2)
m.record_review("MM-1", C2, "subagent", "rev:z", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "pos")
m.set_status("MM-1","ACCEPTED","x"); m.record_integration("MM-1","master",C2)
tryit("integrated with approval bound to old commit", lambda: m.set_status("MM-1","INTEGRATED","x"))
m.record_decision("T","D","2026-10-22","OWNER-PROMPT","chat", ident="LDEC-900")
tryit("same decision id again", lambda: m.record_decision("T2","D2","2026-10-22","OWNER-PROMPT","chat", ident="LDEC-900"))
print("dec", m.projection()["decisions"]["LDEC-900"]["decision"])
