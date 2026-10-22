import sys, os, shutil; src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
C1 = "a"*40
for mid in ["PASSWORD-RESET", "TOKEN-REFRESH", "API-KEY-ROTATION", "SECRET-STORE", "OAUTH-TOKEN", "AUTH-V2"]:
    h = os.path.join(base, "fpid"); shutil.rmtree(h, ignore_errors=True); EventStore.init(h, "h1")
    m = Manager(h, actor="impl:a")
    steps = [("create", lambda: m.create_milestone(mid, "t")),
             ("update", lambda: m.update_milestone(mid, candidate_commit=C1)),
             ("handoff", lambda: m.record_handoff(mid, "progress")),
             ("review", lambda: m.record_review(mid, C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")),
             ("status", lambda: m.set_status(mid, "ACCEPTED", "r"))]
    res = []
    for lab, fn in steps:
        try: fn(); res.append(lab + ":ok")
        except Exception as e: res.append(f"{lab}:{getattr(e,'code',type(e).__name__)}")
    print(mid, " ".join(res))
