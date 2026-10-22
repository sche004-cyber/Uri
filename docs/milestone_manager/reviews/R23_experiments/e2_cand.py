from common import *
import shutil, time
def hosts():
    base=Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
    EventStore.init(A,"ha"); a=Manager(A,actor="impl:a"); a.create_milestone("MM-1","x"); a.update_milestone("MM-1",candidate_commit=C1)
    shutil.copytree(A,B,ignore=shutil.ignore_patterns("local",".lock")); EventStore.init_host(B,"hb"); b=Manager(B,actor="impl:b")
    return a,b
def accept(a, c=C1, rid="rev:y"):
    a.record_review("MM-1", c, "subagent", rid, "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok"); a.set_status("MM-1","ACCEPTED","go")
def integrate(a, c=C1):
    r=a.request_approval("MM-1","INTEGRATION","merge?"); aid=r[0]["data"]["id"]
    a.resolve_approval(aid,"APPROVED","yes","chat"); a.record_integration("MM-1","master",c); a.set_status("MM-1","INTEGRATED","merged")
def sync(a,b):
    shutil.copy(b.home/"events/hb.jsonl", a.home/"events/hb.jsonl")
def report(tag,a):
    p=a.projection(); m=p["milestones"]["MM-1"]; ind=views.indicator(p,m)
    rc,out=runcli("--home",str(a.home),"status","--json","--no-tasks"); row=[x for x in json.loads(out)["milestones"] if x["id"]=="MM-1"][0]
    cc=[(r["type"],r["detail"].get("bound","")[:4],(r["detail"].get("candidate") or "")[:4]) for r in views.conflict_rows(p) if r["entity"]=="MM-1"]
    print(f"{tag}: status={m['status']} cand={(m['candidate_commit'] or '')[:4]} bound={(m.get('bound_commit') or '')[:4]} ind={ind['color']} json={row['indicator']['color']} conflicts={cc}")
    return p
def resolve_all(a):
    p=a.projection()
    for ent,i in sorted({(r["entity"],r["id"]) for r in views.conflict_rows(p)}): a.resolve_conflict(ent,"seen",[i])
# S1 update first
a,b=hosts(); b.update_milestone("MM-1",candidate_commit=C2); time.sleep(0.02); accept(a); sync(a,b); report("S1 B-update-first",a); resolve_all(a); report("S1 after resolve",a)
try: a.set_status("MM-1","DONE","x"); print("  S1 DONE allowed!")
except ValidationError as e: print("  S1 DONE refused", e.code)
# S2 accept first
a,b=hosts(); accept(a); time.sleep(0.02); b.update_milestone("MM-1",candidate_commit=C2); sync(a,b); report("S2 A-accept-first",a); resolve_all(a); report("S2 after resolve",a)
a.update_milestone("MM-1",candidate_commit=C1); report("S2 cand back",a)
# S3 integrated
a,b=hosts(); accept(a); integrate(a); time.sleep(0.02); b.update_milestone("MM-1",candidate_commit=C2); sync(a,b); report("S3 integrated-then-B",a); resolve_all(a); report("S3 after resolve",a)
# S3b B update before integrated (but after accept on A's ts?) B updates first, then A accept+integrate
a,b=hosts(); b.update_milestone("MM-1",candidate_commit=C2); time.sleep(0.02); accept(a); integrate(a); sync(a,b); report("S3b B-first-then-integrated",a); resolve_all(a); report("S3b after resolve",a)
# S4 DONE path
a,b=hosts(); accept(a); a.set_status("MM-1","DONE","done"); time.sleep(0.02); b.update_milestone("MM-1",candidate_commit=C2); sync(a,b); report("S4 done-then-B",a); resolve_all(a); report("S4 after resolve",a)
# S4b remedy IN_PROGRESS
a.set_status("MM-1","IN_PROGRESS","rework"); report("S4b in_progress",a)
