from common import *
import shutil, time
base = Path(tempfile.mkdtemp())
EventStore.init(base/"h1","h1"); a = Manager(base/"h1", actor="impl:a")
EventStore.init(base/"h2","h2"); b = Manager(base/"h2", actor="impl:b")
a.record_decision("Base","use X","2026-10-21","OWNER-PROMPT","chat")          # LDEC-001
shutil.copy(a.store.segment_path, b.store.events_dir/"h1.jsonl")
# both hosts offline record their next decision -> both allocate LDEC-002
a.record_decision("A-side","A says Y","2026-10-21","OWNER-PROMPT","chat a")      # LDEC-002 on h1
time.sleep(0.02)
b.record_decision("B-side","B replaces X with Z","2026-10-21","OWNER-PROMPT","chat b", supersedes="LDEC-001")  # LDEC-002 on h2 (batch, by_target None)
shutil.copy(a.store.segment_path, b.store.events_dir/"h1.jsonl"); shutil.copy(b.store.segment_path, a.store.events_dir/"h2.jsonl")
p = a.projection()
for k,d in p["decisions"].items(): print(k, d["title"], d["status"], "superseded_by", [s["by"] for s in d["superseded_by"]], "supersedes", d["supersedes"])
print("open:", [(c["type"],c["entity"]) for c in p["conflicts"] if not c["resolved"]])
# variant: supersede_decision (with by_target) naming the dup key: what does old.superseded_by say?
