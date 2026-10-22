from common import *
import shutil, time
base = Path(tempfile.mkdtemp())
h1 = base/"h1"; EventStore.init(h1,"h1"); a = Manager(h1, actor="impl:a")
h2 = base/"h2"; EventStore.init(h2,"h2"); b = Manager(h2, actor="impl:b")
for m in (a,b): m.create_milestone("MM-A","A") if m is a else None
shutil.copy(a.store.segment_path, h2/"events"/"h1.jsonl"); b.rebuild()
a.update_milestone("MM-A", candidate_commit=C1); shutil.copy(a.store.segment_path, h2/"events"/"h1.jsonl"); b.rebuild()
# offline: both record review RV-n and decision DEC-001
a.record_review("MM-A", C1, "codex_cli", "codex", "SUBAGENT", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "HIGH found")
a.record_decision("Keep X","keep x","2026-10-21","OWNER-PROMPT","chat a")
time.sleep(0.01)
b.record_review("MM-A", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "fine")
b.record_decision("Drop X","drop x","2026-10-21","OWNER-PROMPT","chat b")
# merge (git pull) h1 segment into h2
shutil.copy(a.store.segment_path, h2/"events"/"h1.jsonl")
p = b.projection()
print("reviews:", {k:(v["verdict"],v["recorded"]["seg"]) for k,v in p["reviews"].items()})
print("decisions:", {k:(v["title"],v["recorded"]["seg"]) for k,v in p["decisions"].items()})
print("conflicts:", [(c["entity"],c["kind"]) for c in p["conflicts"] if not c["resolved"]])
for c in ("RV-1","LDEC-001"): b.resolve_conflict(c, "seen")
try:
    b.set_status("MM-A","ACCEPTED","after merge"); print("ACCEPTED set; REJECT review from h1 hidden")
except ValidationError as e: print("refused", e)
