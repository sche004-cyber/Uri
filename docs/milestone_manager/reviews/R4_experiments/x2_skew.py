from common import *
import shutil, datetime as dt
import scripts.dev_workflow.milestones.store as S
real = S.utc_now
def at(delta_h):
    S.utc_now = lambda: (dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=delta_h)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
base = Path(tempfile.mkdtemp())
EventStore.init(base/"h1","h1"); a = Manager(base/"h1", actor="impl:a")
EventStore.init(base/"h2","h2"); b = Manager(base/"h2", actor="impl:b")
def sync():
    shutil.copy(a.store.segment_path, b.store.events_dir/"h1.jsonl")
    if b.store.segment_path.exists(): shutil.copy(b.store.segment_path, a.store.events_dir/"h2.jsonl")
# Scenario 1: h1 clock correct; h2 clock 1 hour behind. h1 asks, h2 relays the owner's answer.
a.create_milestone("MM-X","X"); a.update_milestone("MM-X", candidate_commit=C1)
a.request_approval("MM-X","INTEGRATION","integrate?"); sync()
at(-1); b.resolve_approval("AP-1","APPROVED","yes","chat"); S.utc_now = real; sync()
for who,m in (("h1",a),("h2",b)):
    p = m.projection(); print(who, "AP-1:", p["approvals"]["AP-1"]["status"], "| open conflicts:", [(c["type"],c["entity"]) for c in p["conflicts"] if not c["resolved"]])
# Scenario 2: candidate swap reordered: h1 ACCEPTED on C1; h2 (1h behind) reopens & names C2
a.create_milestone("MM-Y","Y"); a.update_milestone("MM-Y", candidate_commit=C1)
a.record_review("MM-Y", C1, "subagent", "rev:x", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
a.set_status("MM-Y","ACCEPTED","reviewed"); sync()
at(-1); w = b.set_status("MM-Y","IN_PROGRESS","more work"); S.utc_now = real
print("h2 wrote", w[0]["kind"], w[0]["data"]["status"], "ok; h2 now sees MM-Y status:", b.projection()["milestones"]["MM-Y"]["status"], [ (h["status"],h["at"][11:19]) for h in b.projection()["milestones"]["MM-Y"]["status_history"]])
try: b.set_status("MM-Y","IN_PROGRESS","again")
except ValidationError as e: print("retry:", e.code)
sync()
for who,m in (("h1",a),("h2",b)):
    p = m.projection(); y = p["milestones"]["MM-Y"]
    print(who, "MM-Y:", y["status"], "candidate", y["candidate_commit"][:4], "| reviews on cand:", [r["id"] for r in p["reviews"].values() if r["commit"]==y["candidate_commit"]], "| indicator:", views.indicator(p,y)["word"], "| open:", [(c["type"]) for c in p["conflicts"] if not c["resolved"] and c["entity"]=="MM-Y"])
