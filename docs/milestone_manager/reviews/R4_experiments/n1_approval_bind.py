from common import *
import shutil, time
base = Path(tempfile.mkdtemp())
h1 = base/"h1"; EventStore.init(h1,"h1"); a = Manager(h1, actor="impl:a")
h2 = base/"h2"; EventStore.init(h2,"h2"); b = Manager(h2, actor="impl:b")
for ms in ("MM-X","MM-Y"):
    a.create_milestone(ms, ms); a.update_milestone(ms, candidate_commit=C1)
shutil.copy(a.store.segment_path, h2/"events"/"h1.jsonl")
# h1 (offline) asks the owner about integrating MM-Y; owner never answers
a.request_approval("MM-Y","INTEGRATION","integrate Y?")
a.add_blocker("MM-Y","OWNER","Y blocked","owner input")
time.sleep(0.02)
# h2 (offline) asks about MM-X, owner approves X; h2 resolves its blocker on X
b.request_approval("MM-X","INTEGRATION","integrate X?")
b.resolve_approval("AP-1","APPROVED","yes, integrate X","chat 2026-10-21")
b.add_blocker("MM-X","OWNER","X blocked","x"); b.resolve_blocker("BLK-1","fixed X")
# merge
shutil.copy(a.store.segment_path, h2/"events"/"h1.jsonl")
shutil.copy(b.store.segment_path, h1/"events"/"h2.jsonl")
p = a.projection()
for k,v in p["approvals"].items(): print(k, v["subject"], v["status"], (v["resolution"] or {}).get("owner_words"))
for k,v in p["blockers"].items(): print(k, v["subject"], v["status"])
print("open conflicts:", [(c["type"],c["entity"],c["subject"]) for c in p["conflicts"] if not c["resolved"]])
print("integrity:", p["integrity_errors"])
# proceed on Y without any conflict resolution
a.resolve_conflict("AP-1","merged two hosts"); a.resolve_conflict("BLK-1","merged two hosts")
a.record_review("MM-Y", C1, "subagent", "rev:z", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
a.set_status("MM-Y","ACCEPTED","r")
a.record_integration("MM-Y","refs/heads/canon",C1)
a.set_status("MM-Y","INTEGRATED","owner approved (AP-1)")
try:
    a.set_status("MM-Y","DONE","done"); 
except ValidationError as e: print("DONE refused", e.code)
p = a.projection(); y=p["milestones"]["MM-Y"]
print("MM-Y:", y["status"], y["status_history"][-1]["basis"], views.indicator(p, y)["word"])
