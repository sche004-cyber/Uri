from common import *
import shutil, time, re
base=Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
EventStore.init(A,"ha"); a=Manager(A,actor="impl:a"); a.create_milestone("MM-1","x"); a.update_milestone("MM-1",candidate_commit=C1)
shutil.copytree(A,B,ignore=shutil.ignore_patterns("local",".lock")); EventStore.init_host(B,"hb"); b=Manager(B,actor="impl:b")
a.record_review("MM-1",C1,"subagent","rev:y","SUBAGENT","ACCEPT",0,0,"COMPLETED_WITH_RESULT","ok"); a.set_status("MM-1","ACCEPTED","go")
b.update_milestone("MM-1",candidate_commit=C2); shutil.copy(B/"events/hb.jsonl",A/"events/hb.jsonl")
p=a.projection(); ids={r["id"] for r in views.conflict_rows(p)}; print("ids",ids)
rx=re.compile(r"[0-9a-f]{12}\.[0-9a-f]{6}")
for args in (["status","--no-tasks"],["status","--json","--no-tasks"],["status","--a2ui","--no-tasks"],["show","MM-1"],["resume","MM-1","--no-tasks"],["ready"],["log","--limit","200"],["verify"],["rebuild"],["conflicts"],["--actor","impl:a","status-set","MM-1","DONE","--reason","x"],["--actor","impl:a","resolve-conflict","MM-1","--note","n"],["--actor","impl:a","resolve-conflict","MM-1","--note","n","--id","deadbeef0000.000000"]):
    rc,out=runcli("--home",str(A),*args); print(f"{' '.join(args)[:50]:52} rc={rc} ids={sorted(set(rx.findall(out)))}")
