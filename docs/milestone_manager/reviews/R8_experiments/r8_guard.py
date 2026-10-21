from common import *
def t(label, f):
    try: f(); print(label, "ALLOWED")
    except (ValidationError, StoreError) as e: print(label, "refused", e.code)
m = new(actor="impl:a"); m.create_milestone("MM-A","A"); m.update_milestone("MM-A", candidate_commit=C1)
t("self review recording:", lambda: m.record_review("MM-A", C1, "subagent", "impl:a", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "x"))
t("ACCEPTED with only self review:", lambda: m.set_status("MM-A","ACCEPTED","r"))
m.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "PENDING", "x")
t("ACCEPTED with PENDING review:", lambda: m.set_status("MM-A","ACCEPTED","r"))
m.record_review("MM-A", C2, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "x")
t("ACCEPTED with review bound to other commit:", lambda: m.set_status("MM-A","ACCEPTED","r"))
m.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 1, 1, "COMPLETED_WITH_RESULT", "x")
t("ACCEPTED with ACCEPT but blocking open:", lambda: m.set_status("MM-A","ACCEPTED","r"))
print("files in home:", sorted(str(p.relative_to(m.home)) for p in m.home.rglob("*") if p.is_file()))
