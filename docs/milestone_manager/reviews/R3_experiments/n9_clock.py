from common import *
import scripts.dev_workflow.milestones.store as S
m = new()
m.create_milestone("MM-A","A")
real = S.utc_now
S.utc_now = lambda: "2020-01-01T00:00:00.000000Z"   # host clock stepped backwards (e.g. NTP correction / CMOS reset)
m.update_milestone("MM-A", candidate_commit=C1)
S.utc_now = real
p = m.projection()
print("candidate after write:", p["milestones"]["MM-A"]["candidate_commit"], "| conflicts:", [(c["type"],c["entity"]) for c in p["conflicts"]], "| verify ok:", m.store.verify()["ok"])
