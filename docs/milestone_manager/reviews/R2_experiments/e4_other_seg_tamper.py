from common import *
import shutil
m1 = new("h1")
m2home = Path(tempfile.mkdtemp())/"l2"; EventStore.init(m2home,"h2"); m2 = Manager(m2home, actor="impl:b")
m2.create_milestone("MM-B","t1")
shutil.copy(m2.store.segment_path, m1.store.events_dir/"h2.jsonl")
m1.create_milestone("MM-A","A")   # cache now covers h2
seg = m1.store.events_dir/"h2.jsonl"
seg.write_bytes(seg.read_bytes().replace(b'"title":"t1"', b'"title":"tX"'))  # same length edit
print("verify ok:", m1.store.verify()["ok"])
try:
    m1.create_milestone("MM-C","C"); print("WRITE ACCEPTED on broken chain")
except StoreError as e: print("refused", e.code)
print("title via projection():", m1.projection()["milestones"]["MM-B"]["title"], "integrity_errors:", m1.projection().get("integrity_errors"))
# also: truncate last line of h2 (delete newest event) -> silently accepted?
