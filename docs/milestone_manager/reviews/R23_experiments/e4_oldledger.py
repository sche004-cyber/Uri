from common import *
import collections
m=Manager(T+"/work/rehearsal_copy")
p=m.projection()
print("events",p["events"],"errors",p["integrity_errors"][:2])
print("conflict types",collections.Counter(c["type"] for c in p["conflicts"]))
print("statuses",collections.Counter(x["status"] for x in p["milestones"].values()))
print("cand-changed", [c for c in p["conflicts"] if c["type"]=="CANDIDATE_CHANGED"][:2])
print("RED", [(x["id"],views.indicator(p,x)["issue"]) for x in p["milestones"].values() if views.indicator(p,x)["color"]=="RED"][:5])
