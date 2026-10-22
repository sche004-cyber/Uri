from common import *
import shutil, time
def run(order):
    base = Path(tempfile.mkdtemp()); A=base/"A"; B=base/"B"
    EventStore.init(A,"ha"); ma=Manager(A,actor="impl:a"); ma.create_milestone("MM-1","x"); ma.create_milestone("MM-2","y")
    ma.update_milestone("MM-1", candidate_commit=C1)
    shutil.copytree(A, B, ignore=shutil.ignore_patterns("local")); EventStore.init_host(B,"hb")
    mb=Manager(B,actor="impl:b"); mb.update_milestone("MM-2", candidate_commit=C2)
    def ra(): ma.record_review("MM-1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    def rb(): mb.record_review("MM-2", C2, "subagent", "rev:z", "SUBAGENT", "REJECT", 2, 2, "COMPLETED_WITH_RESULT", "no")
    if order=="A first": ra(); time.sleep(0.05); rb()
    else: rb(); time.sleep(0.05); ra()
    shutil.copy(B/"events/hb.jsonl", A/"events/hb.jsonl"); shutil.copy(A/"events/ha.jsonl", B/"events/ha.jsonl")
    p = ma.projection()
    print(order, "reviews", {k:(v["subject"],v["verdict"]) for k,v in p["reviews"].items()})
    rows = views.conflict_rows(p); print(" conflicts", [(r["id"],r["type"],r["entity"],r["subject"]) for r in rows])
    print(" status MM-1:", [l for l in views.status_lines(p, False, None, None) if "MM-1" in l][:1])
    print(" status MM-2:", [l for l in views.status_lines(p, False, None, None) if "MM-2" in l][:1])
    for r in rows: ma.resolve_conflict(r["entity"], "dup reviewed", [r["id"]])
    try:
        ma.set_status("MM-1","ACCEPTED","go"); p=ma.projection(); print(" ACCEPTED ok, basis", p["milestones"]["MM-1"]["status_history"][-1]["basis"])
    except Exception as e: print(" ACCEPT refused", e)
    try:
        mb2=Manager(B,actor="impl:b"); mb2.set_status("MM-2","ACCEPTED","go"); print(" MM-2 ACCEPTED?? (REJECT review)")
    except Exception as e: print(" MM-2 refused", str(e)[:120])
    print(" open after", views.conflict_rows(ma.projection()), "verify", EventStore(A).verify()["ok"])
    shutil.copy(A/"events/ha.jsonl", B/"events/ha.jsonl"); print(" B view MM-1", Manager(B).projection()["milestones"]["MM-1"]["status"], views.conflict_rows(Manager(B).projection()))
run("A first"); run("B first")
