import sys, os, shutil; src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.model import find_secret
for mid in ["PASSWORD-RESET", "TOKEN-REFRESH", "SECRET-STORE", "TOKEN-BUDGET", "TOKEN-COUNT"]:
    h = os.path.join(base, "fpid2"); shutil.rmtree(h, ignore_errors=True); EventStore.init(h, "h1")
    m = Manager(h, actor="impl:a")
    try: m.create_milestone(mid, "t"); r = "ok"
    except Exception as e: r = str(e)[:160]
    print(mid, "|", r, "| base-like", find_secret({mid: 0}), "| data-like", find_secret({"id": mid, "title": "t"}))
