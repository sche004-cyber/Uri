from common import *
m = new()
m.create_milestone("MM-A","A")
m.update_milestone("MM-A", candidate_commit=C1)
m.record_review("MM-A", C1, "subagent", "rev:x", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
m.set_status("MM-A","ACCEPTED","reviewed")
# swap candidate to an unreviewed commit
m.update_milestone("MM-A", candidate_commit=C2)
m.request_approval("MM-A","INTEGRATION","merge?")
m.resolve_approval("AP-1","APPROVED","yes merge","chat")
m.record_integration("MM-A","refs/x",C2)
m.set_status("MM-A","INTEGRATED","merged")
p=m.projection(); a=p["milestones"]["MM-A"]
print("status",a["status"],"candidate",a["candidate_commit"][:6],"reviews on C2:",[r["id"] for r in p["reviews"].values() if r["commit"]==C2])
