from common import *
def t(label, f):
    try: f(); print(label, "ALLOWED")
    except (ValidationError, StoreError) as e: print(label, "refused", e.code)
for rc, rev, commit in (("PENDING","rev:y",C1), ("COMPLETED_WITH_RESULT","impl:a",C1), ("COMPLETED_WITH_RESULT","rev:y",C2), ("COMPLETED_WITH_RESULT","rev:y",C1)):
    m = new(); m.create_milestone("MM-A","A"); m.update_milestone("MM-A", candidate_commit=C1)
    try: m.record_review("MM-A", commit, "subagent", rev, "SUBAGENT", "ACCEPT", 0, 0, rc, "ok")
    except (ValidationError, StoreError) as e: print("  record refused", e.code)
    t(f"accept rc={rc} reviewer={rev} commit={commit[:4]}:", lambda: m.set_status("MM-A","ACCEPTED","r"))
