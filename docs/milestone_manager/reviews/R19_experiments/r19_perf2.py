from common import *
import time, subprocess, statistics
from scripts.dev_workflow.milestones import model as M
for N in (1000, 2000, 3300):
    home = Path(tempfile.mkdtemp())/"l"; EventStore.init(home,"h1"); m = Manager(home, actor="a")
    with m.store.locked():
        for i in range(N):
            m.store.append("MILESTONE_CREATED", {"id": f"MM-{i}", "title": "t"}, actor="a")
        for i in range(N):
            m.store.append("MILESTONE_UPDATED", {"id": f"MM-{i}", "fields": {"title": "u"}}, actor="a", base={f"MM-{i}": 0})
    m.store.write_anchors(m.store.read_all())
    p = m.projection()
    hs = {c["entity"]: c for c in p["conflicts"]}
    with m.store.locked():
        for i in range(N):
            c = hs[f"MM-{i}"]
            m.store.append("CONFLICT_RESOLVED", {"entity": f"MM-{i}", "note": "n", "conflicts": [c["event"]["hash"]],
                     "seen": [[c["event"]["hash"], c["type"], M.conflict_fingerprint(c)]]}, actor="a")
    m.store.write_anchors(m.store.read_all())
    ts=[]
    for _ in range(3):
        t0=time.perf_counter(); p=m.projection(); ts.append(time.perf_counter()-t0)
    env=dict(os.environ, PYTHONPATH=T+"/src"); cl=[]
    for _ in range(3):
        t0=time.perf_counter(); rr=subprocess.run([sys.executable,"-X","utf8","-m","scripts.dev_workflow.milestones","--home",str(home),"status","--no-tasks"],capture_output=True,text=True,env=env,cwd=T+"/src"); cl.append(time.perf_counter()-t0)
    t0=time.perf_counter(); m.create_milestone("MM-NEW","n"); tw=time.perf_counter()-t0
    print(f"resolved={N} open={len(views.open_conflicts(p))} events={p['events']} rebuild_median={statistics.median(ts):.3f} cli_status_median={statistics.median(cl):.2f} write={tw:.3f}")
