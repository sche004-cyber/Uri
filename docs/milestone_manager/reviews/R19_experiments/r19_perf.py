from common import *
import time, subprocess
from scripts.dev_workflow.milestones import model as M
for N in (500, 1000, 2000):
    home = Path(tempfile.mkdtemp())/"l"; EventStore.init(home,"h1"); m = Manager(home, actor="a")
    with m.store.locked():
        for i in range(2*N):
            m.store.append("MILESTONE_CREATED", {"id": f"MM-{i}", "title": "t"}, actor="a")
        for i in range(2*N):
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
    t0=time.perf_counter(); p=m.projection(); tp=time.perf_counter()-t0
    t0=time.perf_counter(); sl=views.status_lines(p, False, None, None); ts=time.perf_counter()-t0
    t0=time.perf_counter(); rows=views.conflict_rows(p); tc=time.perf_counter()-t0
    r = rows[-1]
    t0=time.perf_counter(); m.resolve_conflict(r["entity"], "ok", [r["id"]]); tw=time.perf_counter()-t0
    t0=time.perf_counter(); m.create_milestone("MM-NEW", "n"); tw2=time.perf_counter()-t0
    try:
        t0=time.perf_counter(); m.resolve_conflict(rows[0]["entity"], "ok"); 
    except Exception as e: tn=time.perf_counter()-t0
    env=dict(os.environ, PYTHONPATH=T+"/src")
    t0=time.perf_counter(); rr=subprocess.run([sys.executable,"-m","scripts.dev_workflow.milestones","--home",str(home),"status"],capture_output=True,text=True,env=env,cwd=T+"/src"); tcli=time.perf_counter()-t0
    t0=time.perf_counter(); rr2=subprocess.run([sys.executable,"-m","scripts.dev_workflow.milestones","--home",str(home),"conflicts"],capture_output=True,text=True,env=env,cwd=T+"/src"); tcli2=time.perf_counter()-t0
    print(f"N_open={len(rows)} N_resolved={N} events={p['events']} projection={tp:.3f} status_lines={ts:.3f} conflicts={tc:.3f} resolve_write={tw:.3f} create_write={tw2:.3f} no_id_refusal={tn:.3f} cli_status={tcli:.2f}(rc {rr.returncode}) cli_conflicts={tcli2:.2f}(rc {rr2.returncode}) {rr.stderr[-200:]}")
