import sys, os, shutil, subprocess, json, time
src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
if len(sys.argv) > 3:
    from scripts.dev_workflow.milestones.service import Manager
    home, who = sys.argv[3], sys.argv[4]; errs = 0
    for i in range(40):
        try:
            m = Manager(home, actor=f"w:{who}", session="s")
            m.record_handoff("M1", f"{who} {i} token: 65536 context; api_key=${{OPENAI_API_KEY}}")
            m.projection()
        except Exception as e:
            errs += 1; print(who, i, type(e).__name__, getattr(e, "code", ""), str(e)[:150])
    print("worker", who, "errors", errs); sys.exit(0)
from scripts.dev_workflow.milestones.store import EventStore
from scripts.dev_workflow.milestones.service import Manager
home = os.path.join(base, "stress_ledger"); shutil.rmtree(home, ignore_errors=True)
EventStore.init(home, "h1"); Manager(home, actor="w:0", session="s").create_milestone("M1", "t")
env = dict(os.environ, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1")
t0 = time.time()
ps = [subprocess.Popen([sys.executable, __file__, src, base, home, str(k)], env=env, cwd=src, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True) for k in range(6)]
for p in ps: print(p.communicate()[0].strip()[-300:])
print("elapsed", round(time.time()-t0, 1))
r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "verify"], cwd=src, env=env, capture_output=True, text=True)
print("verify rc", r.returncode, r.stdout.strip().replace("\n", " ")[:300])
r = subprocess.run([sys.executable, "-m", "scripts.dev_workflow.milestones", "--home", home, "conflicts"], cwd=src, env=env, capture_output=True, text=True)
print("conflicts", r.stdout.strip()[:200])
p = Manager(home, actor="w:0", session="s").projection()
print("handoffs", len(p["handoffs"]), "integrity_errors", p["integrity_errors"])
