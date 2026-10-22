from common import *
import importlib
from scripts.dev_workflow.milestones import service as SV
def base(c=C1):
    m=new(); m.create_milestone("MM-1","x"); m.update_milestone("MM-1",candidate_commit=c); return m
def rev(m,c,rid="rev:y"): m.record_review("MM-1", c, "subagent", rid, "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
def integ(m,c):
    r=m.request_approval("MM-1","INTEGRATION","merge?"); aid=r[0]["data"]["id"]; m.resolve_approval(aid,"APPROVED","yes","chat")
    m.record_integration("MM-1","master",c); m.set_status("MM-1","INTEGRATED","merged")
def chk(tag,m):
    p=m.projection(); mm=p["milestones"]["MM-1"]; cc=[c["type"] for c in p["conflicts"]]
    ind=views.indicator(p,mm); print(f"{tag}: {mm['status']} cand={mm['candidate_commit'][:4]} bound={(mm['bound_commit'] or '-')[:4]} ind={ind['color']} conflicts={cc} verify={m.store.verify()['ok']}")
# F1 accept->integrate->done
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a"); integ(m,C1); m.set_status("MM-1","DONE","d"); chk("F1 accept-integrate-done",m)
# F2 IN_PROGRESS->new cand->re-accept
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a"); m.set_status("MM-1","IN_PROGRESS","r"); m.update_milestone("MM-1",candidate_commit=C2); rev(m,C2,"rev:z"); m.set_status("MM-1","ACCEPTED","a2"); integ(m,C2); chk("F2 reaccept new cand + integrate",m)
# F3 re-accept same commit
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a"); m.set_status("MM-1","IN_PROGRESS","r"); m.set_status("MM-1","ACCEPTED","a2"); chk("F3 reaccept same",m)
# F4 set candidate to same value while ACCEPTED
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a"); m.update_milestone("MM-1",candidate_commit=C1); m.update_milestone("MM-1",next_action="n"); chk("F4 same-cand update",m)
# F5 accept -> DONE directly
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a"); m.set_status("MM-1","DONE","d"); chk("F5 accept-done",m)
# F6 old ledger: INTEGRATED/DONE basis without commit (simulate pre-R22 guard)
orig=SV.Manager.guard_status
def old_guard(self,p,m,status):
    b=orig(self,p,m,status)
    if status in ("INTEGRATED","DONE"): b.pop("commit",None)
    return b
SV.Manager.guard_status=old_guard
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a"); integ(m,C1); m.set_status("MM-1","DONE","d")
SV.Manager.guard_status=orig; chk("F6 old-basis integrate-done",m)
SV.Manager.guard_status=old_guard
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a"); m.set_status("MM-1","IN_PROGRESS","r"); m.update_milestone("MM-1",candidate_commit=C2); rev(m,C2,"rev:z"); m.set_status("MM-1","ACCEPTED","a2"); integ(m,C2); m.set_status("MM-1","DONE","d")
SV.Manager.guard_status=orig; chk("F6b old-basis new-cand",m)
# F7 old ledger where ACCEPTED basis lacked commit too (pre-R1-ish)
def older(self,p,m,status):
    b=orig(self,p,m,status); b.pop("commit",None); return b
SV.Manager.guard_status=older
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a"); integ(m,C1); m.set_status("MM-1","DONE","d")
SV.Manager.guard_status=orig; chk("F7 no-commit anywhere",m)
# F8 PAUSED from ACCEPTED then back
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a"); m.set_status("MM-1","PAUSED","p"); m.update_milestone("MM-1",candidate_commit=C2); chk("F8 paused new cand",m)
try: m.set_status("MM-1","ACCEPTED","a"); print("  F8 accept on C2 w/o review allowed!")
except ValidationError as e: print("  F8 re-accept refused",e.code)
# F9 INTEGRATED via record on target containing (repo) - target != cand
m=base(); rev(m,C1); m.set_status("MM-1","ACCEPTED","a")
r=m.request_approval("MM-1","INTEGRATION","merge?"); m.resolve_approval("AP-1","APPROVED","yes","chat")
import subprocess
repo=Path(tempfile.mkdtemp())/"r"; repo.mkdir(); g=lambda *a: subprocess.run(["git","-C",str(repo),*a],capture_output=True,text=True)
g("init","-q"); (repo/"f").write_text("1"); g("add","f"); g("-c","user.name=x","-c","user.email=x@y","commit","-qm","a"); c1=g("rev-parse","HEAD").stdout.strip()
(repo/"f").write_text("2"); g("-c","user.name=x","-c","user.email=x@y","commit","-qam","b"); c2=g("rev-parse","HEAD").stdout.strip()
m2=base(c1); rev(m2,c1); m2.set_status("MM-1","ACCEPTED","a"); r=m2.request_approval("MM-1","INTEGRATION","merge?"); m2.resolve_approval("AP-1","APPROVED","yes","chat")
m2.record_integration("MM-1","master",c2,repo=repo); m2.set_status("MM-1","INTEGRATED","merged"); m2.set_status("MM-1","DONE","d"); chk("F9 integrate target!=cand",m2)
