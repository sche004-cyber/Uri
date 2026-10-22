import sys, os, shutil; src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones import views
mid = "M" + "X"*63; worst = 0
h = os.path.join(base, "r2303b"); shutil.rmtree(h, ignore_errors=True); EventStore.init(h, "h1")
m = Manager(h, actor="a:1"); m.create_milestone(mid, "t")
p = m.projection(); full = views.resume_brief(p, mid, max_chars=100000)
lines = full.split("\n"); print("first lines lens", [len(l) for l in lines[:6]])
for tl in range(1, 120):
    p["milestones"][mid]["title"] = "T" * tl
    t = views.resume_brief(p, mid, max_chars=200); worst = max(worst, len(t))
print("max resume len over title lengths 1..119 at max_chars=200:", worst)
