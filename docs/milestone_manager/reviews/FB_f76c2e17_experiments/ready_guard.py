import os, shutil
from pathlib import Path
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones import views, model as M
B = Path(os.environ["MMFB"]) / "ex" / "rg"
C1, C2 = "1"*40, "2"*40
def setup(name):
    h = B / name; shutil.rmtree(h, ignore_errors=True)
    EventStore.init(h, host_id="h1")
    m = Manager(h, actor="impl:a")
    m.create_milestone("MM-A", "A"); m.set_status("MM-A", "IN_PROGRESS", "go")
    m.update_milestone("MM-A", candidate_commit=C1)
    m.record_review("MM-A", C1, "subagent", "subagent:r1", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    m.set_status("MM-A", "ACCEPTED", "accepted")
    m.create_milestone("MM-B", "B", depends_on=["MM-A"])
    return h, m
def show(tag, m):
    p = m.projection(); a = p["milestones"]["MM-A"]
    ind = views.indicator(p, a)
    print(f"{tag:55} A.status={a['status']:9} A.color={ind['color']:5} ready={views.ready(p)} unmet(B)={views.unmet_dependencies(p, p['milestones']['MM-B'])}")
    print("     issue:", (ind["issue"] or "")[:150])
h, m = setup("base"); show("baseline", m)
h, m = setup("d101"); m.record_implementer("MM-A", "subagent:r1"); show("D1-01 reviewer added as implementer", m)
h, m = setup("d101b"); m.record_implementer("MM-A", " SUBAGENT:R1 "); show("D1-01 variant case/space id", m)
h, m = setup("d101c"); Manager(h, actor="subagent:r1").record_handoff("MM-A", "handoff by reviewer"); show("D1-01 reviewer writes handoff", m)
h, m = setup("d101d"); Manager(h, actor="subagent:r1").assign("MM-A", hours=1); show("D1-01 reviewer assigns itself", m)
h, m = setup("r202"); m.record_review("MM-A", C1, "subagent", "subagent:r2", "SUBAGENT", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "no"); show("R2-02 later REJECT", m)
h, m = setup("r202c"); m.record_review("MM-A", C1, "subagent", "subagent:r2", "UNVERIFIED", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "no"); show("R2-02 REJECT unverified assurance", m)
h, m = setup("r202d"); m.record_review("MM-A", C1, "subagent", "subagent:r2", "SUBAGENT", "REJECT", 1, 1, "PENDING", "no"); show("R2-02 REJECT PENDING (should not invalidate)", m)

def two_host(name, h2_candidate, accept_on_c2=False):
    h = B / name; shutil.rmtree(h, ignore_errors=True)
    EventStore.init(h, host_id="h1")
    m = Manager(h, actor="impl:a")
    m.create_milestone("MM-A", "A"); m.set_status("MM-A", "IN_PROGRESS", "go")
    m.update_milestone("MM-A", candidate_commit=C1)
    m.create_milestone("MM-B", "B", depends_on=["MM-A"])
    h2 = B / (name + "_h2"); shutil.rmtree(h2, ignore_errors=True)
    EventStore.init(h2, host_id="h2")
    (h2/"events"/"h1.jsonl").write_bytes((h/"events"/"h1.jsonl").read_bytes())
    m2 = Manager(h2, actor="impl:b")
    m2.update_milestone("MM-A", candidate_commit=h2_candidate)
    if accept_on_c2:
        m2.record_review("MM-A", C2, "subagent", "subagent:r9", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok c2")
    m.record_review("MM-A", C1, "subagent", "subagent:r1", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    m.set_status("MM-A", "ACCEPTED", "accepted")
    (h/"events"/"h2.jsonl").write_bytes((h2/"events"/"h2.jsonl").read_bytes())
    return h, m
h, m = two_host("r302", C2); show("R3-02 merged other-host candidate C2", m)
p = m.projection(); print("   conflicts:", [(c.get("type"), c.get("entity")) for c in views.open_conflicts(p, "MM-A")])
h, m = two_host("r302b", C2, accept_on_c2=True); show("R3-02 merged C2 + accept on C2 (bound C1)", m)
p = m.projection(); cs = views.open_conflicts(p, "MM-A"); print("   conflicts:", [(c.get("type"), c.get("id")) for c in cs])

import subprocess, sys, json
def mm(*a):
    return subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", str(h), "--actor", "owner:x", *a], capture_output=True, text=True)
for ent in ("MM-A", "RV-1"):
    cl = json.loads(mm("conflicts", "--entity", ent).stdout)
    ids = sorted({c["id"] for c in cl if c["entity"] == ent})
    r = mm("resolve-conflict", ent, "--note", "reviewed", *sum((["--id", i] for i in ids), []))
    print("   resolve", ent, ids, r.returncode, r.stdout.replace(chr(10), " ")[:160])
show("R3-02 after resolving conflicts (bound C1 != cand C2)", m)
