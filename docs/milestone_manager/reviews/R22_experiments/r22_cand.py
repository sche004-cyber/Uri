from common import *
import shutil, time, io
for order in ("B first","A first"):
    base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
    EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-1","x"); ma.update_milestone("MM-1", candidate_commit=C1)
    shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb"); mb=Manager(B,actor="impl:b")
    def a():
        ma.record_review("MM-1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok"); ma.set_status("MM-1","ACCEPTED","go")
    def b(): mb.update_milestone("MM-1", candidate_commit=C2)
    if order=="B first": b(); time.sleep(0.05); a()
    else: a(); time.sleep(0.05); b()
    shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl")
    p=ma.projection(); m=p["milestones"]["MM-1"]
    rows=views.conflict_rows(p)
    print(order, "status", m["status"], "cand", m["candidate_commit"][:4], "basis", m["status_history"][-1].get("basis"))
    print("  conflicts", [(r["type"], r["entity"], r["detail"]) for r in rows])
    for ent,i in sorted({(r["entity"],r["id"]) for r in rows}): ma.resolve_conflict(ent,"seen",[i])
    p=ma.projection(); m=p["milestones"]["MM-1"]; ind=views.indicator(p,m)
    print("  after resolve:", m["status"], m["candidate_commit"][:4], ind["color"], ind.get("issue"), "| verify", ma.store.verify()["ok"])
    print("  status line:", [l for l in views.status_lines(p, False, None, None) if "MM-1" in l])
    try: ma.set_status("MM-1","DONE","x"); print("  DONE allowed!")
    except ValidationError as e: print("  DONE refused", e.code)
