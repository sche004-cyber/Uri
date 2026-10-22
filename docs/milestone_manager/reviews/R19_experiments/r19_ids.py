from common import *
import shutil, time, subprocess, re
base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-1","x")
ma.update_milestone("MM-1", candidate_commit=C1); ma.add_blocker("MM-1","TECHNICAL","r","n"); ma.request_approval("MM-1","INTEGRATION","ok?")
shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
mb=Manager(B,actor="impl:b")
mb.resolve_blocker("BLK-1","fixed on B"); mb.resolve_approval("AP-1","DENIED","no","chat")
mb.update_milestone("MM-1", next_action="B")
time.sleep(0.05)
ma.resolve_blocker("BLK-1","fixed on A"); ma.resolve_approval("AP-1","APPROVED","yes","chat")
ma.update_milestone("MM-1", next_action="A")
shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl"); shutil.copy(A/"events/ha.jsonl", B/"events/ha.jsonl")
def ids(home):
    p = Manager(home).projection()
    rows = views.conflict_rows(p)
    return sorted((r["id"], r["type"], r["entity"], r["subject"]) for r in rows)
ia, ib = ids(A), ids(B); print("A", ia); print("B equal", ia==ib)
p = Manager(A).projection()
sl = "\n".join(views.status_lines(p, False, None, None))
print("status ids", sorted(set(re.findall(r"--id (\S+)`", sl))))
for ent in sorted({e for _,_,e,_ in ia}):
    try: ma.resolve_conflict(ent, "x")
    except Exception as e: print("NO_ID msg", ent, str(e)[:160])
code = f"""
import sys,json; sys.path.insert(0, r'{T}/src')
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones import views
print(json.dumps(sorted(r['id'] for r in views.conflict_rows(Manager(sys.argv[1]).projection()))))
"""
outs=set()
for home in (A,B):
    for seed in ("0","1","999","random"):
        r = subprocess.run([sys.executable,"-c",code, str(home)], capture_output=True, text=True, env=dict(os.environ, PYTHONHASHSEED=seed))
        outs.add(r.stdout.strip() or r.stderr[-300:])
print("distinct id lists across hosts x seeds:", len(outs))
# fresh host via copy (git clone simulated with git below)
C = base/"C"; shutil.copytree(A, C, ignore=shutil.ignore_patterns("local")); EventStore.init_host(C,"hc")
print("C equal", ids(C)==ia)
# resolve each entity using ids from status lines, from host A
for idv in sorted(set(re.findall(r"resolve-conflict (\S+) --id (\S+)`", sl))):
    ma.resolve_conflict(idv[0], "reviewed", [idv[1]])
print("A open after", ids(A))
shutil.copy(A/"events/ha.jsonl", B/"events/ha.jsonl"); print("B open after", ids(B))
print(views.indicator(Manager(A).projection(), Manager(A).projection()["milestones"]["MM-1"])["color"])
