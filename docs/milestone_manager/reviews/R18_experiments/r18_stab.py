from common import *
import shutil, time, subprocess
def openc(home): return [(r["id"], r["type"]) for r in views.conflict_rows(Manager(home).projection())]
# 1. legit same-host flows after acceptance
m = new(); m.create_milestone("MM-1","x"); m.update_milestone("MM-1", candidate_commit=C1)
m.record_review("MM-1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
m.set_status("MM-1","ACCEPTED","go")
m.record_implementer("MM-1","rev:y")
Manager(m.home, actor="rev:y").assign("MM-1", 1)
Manager(m.home, actor="rev:y").record_handoff("MM-1","did integration prep")
p = m.projection(); print("legit same-host after-accept: open", openc(m.home), "indicator", views.indicator(p,p["milestones"]["MM-1"])["color"])
try: m.set_status("MM-1","DONE","done"); print("DONE ok")
except Exception as e: print("DONE refused:", e)
# 2. concurrent handoff by the reviewer (no base on milestone) -> fold re-check
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-X","x")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
Manager(B,actor="rev:y").record_handoff("MM-X","rev:y implemented part")
time.sleep(0.05)
ma.update_milestone("MM-X", candidate_commit=C1)
ma.record_review("MM-X", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
ma.set_status("MM-X","ACCEPTED","go")
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")
print("concurrent handoff by reviewer: open", openc(A))
ids = sorted({i for i,_ in openc(A)})
ma.resolve_conflict("MM-X","acknowledged", ids); print("after resolve open", openc(A))
# 3. stability of resolutions across processes with different hash seeds and a git clone
code = f"""
import sys; sys.path.insert(0, r'{T}/src')
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones import views
print(len(views.conflict_rows(Manager(r'%s').projection())))
"""
for home in (A,):
    for seed in ("0","1","12345","random"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        r = subprocess.run([sys.executable,"-c",code % home], capture_output=True, text=True, env=env)
        print("seed", seed, "open:", r.stdout.strip(), r.stderr.strip()[-200:])
# 4. R17 scenario: resolve after both syncs, then re-sync in reverse file order / copy into a fresh clone
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-X","x")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b"); mb.update_milestone("MM-X", next_action="B"); mb.record_implementer("MM-X","q:z")
time.sleep(0.05)
ma.update_milestone("MM-X", candidate_commit=C1)
(A/"events/hb.jsonl").write_bytes((B/"events/hb.jsonl").read_bytes())
ids = sorted({i for i,_ in openc(A)}); ma.resolve_conflict("MM-X","ok", ids)
print("A open after resolve", openc(A))
# B pulls A, then B writes more on other entity, A pulls back
shutil.copy(A/"events/ha.jsonl", B/"events/ha.jsonl"); print("B open", openc(B))
mb.create_milestone("MM-Y","y"); shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl"); print("A open after unrelated B write", openc(A))
C = base/"C"; shutil.copytree(A, C, ignore=shutil.ignore_patterns("local")); EventStore.init_host(C,"hc"); print("fresh host C open", openc(C))
print("verify", EventStore(A).verify()["ok"], EventStore(C).verify()["ok"])
