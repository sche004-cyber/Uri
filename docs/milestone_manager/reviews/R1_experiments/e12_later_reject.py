from common import *
m = new()
m.create_milestone("MM-A","A"); m.update_milestone("MM-A", candidate_commit=C1)
m.record_review("MM-A", C1, "subagent", "rev:x", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
m.set_status("MM-A","ACCEPTED","reviewed")
m.record_review("MM-A", C1, "codex_cli", "codex", "SUBAGENT", "REJECT", 2, 2, "COMPLETED_WITH_RESULT", "two HIGH")
m.set_status("MM-A","DONE","closing anyway")
p = m.projection(); print("status:", p["milestones"]["MM-A"]["status"], "indicator:", views.indicator(p, p["milestones"]["MM-A"])["word"])
# case-variant reviewer id vs implementer
m2 = new(actor="impl:a"); m2.create_milestone("MM-B","B"); m2.update_milestone("MM-B", candidate_commit=C1)
m2.record_review("MM-B", C1, "session", "IMPL:A", "SESSION", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "self")
m2.set_status("MM-B","ACCEPTED","self-review with case variant"); print("self-review accepted:", m2.projection()["milestones"]["MM-B"]["status"])
