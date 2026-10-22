from common import *
import shutil, io, subprocess
# (1) crash between first append and anchor write (simulate by making write_anchors fail once)
m = new()
orig = EventStore.write_anchors
def boom(self, segs): raise OSError("simulated crash/lock")
EventStore.write_anchors = boom
m.create_milestone("MM-A","A"); print("(1) first write with anchors failing; warnings:", m.last_warnings)
EventStore.write_anchors = orig
p = m.projection(); print("    integrity after:", p["integrity_errors"])
try: m.create_milestone("MM-B","B"); print("    next write OK")
except StoreError as e: print("    next write refused:", e.code)
# (1b) same but not the first write
m = new(); m.create_milestone("MM-A","A"); EventStore.write_anchors = boom
m.create_milestone("MM-B","B"); EventStore.write_anchors = orig
print("(1b) later write anchors fail: integrity", m.projection()["integrity_errors"])
# (2) fresh init / init-host on clone / first write after merge
base = Path(tempfile.mkdtemp())
EventStore.init(base/"A","ha"); a = Manager(base/"A", actor="impl:a"); print("(2) fresh init integrity:", a.projection()["integrity_errors"])
a.create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local"))
EventStore.init_host(base/"B","hb"); b = Manager(base/"B", actor="impl:b")
print("    init-host clone integrity:", b.projection()["integrity_errors"])
b.create_milestone("MM-B","B"); a.create_milestone("MM-C","C")
shutil.copy(a.store.segment_path, b.store.events_dir/"ha.jsonl"); shutil.copy(b.store.segment_path, a.store.events_dir/"hb.jsonl")
print("    after merge both:", a.projection()["integrity_errors"], b.projection()["integrity_errors"])
a.create_milestone("MM-D","D"); b.create_milestone("MM-E","E"); print("    first writes after merge ok")
# (3) clone that includes own segment of the old host? init-host with name of existing -> refused
try: EventStore.init_host(base/"B2" if False else base/"A", "hb")
except StoreError as e: print("(3) init-host on registered:", e.code)
# (4) recover after torn tail at first event
m = new(); m.create_milestone("MM-A","A")
seg = m.store.segment_path; seg.write_bytes(seg.read_bytes()+b'{"partial')
print("(4) torn: integrity", m.projection()["integrity_errors"], "warn", m.projection()["integrity_warnings"])
print("    recover:", m.store.recover("impl:a")["recovered"], "integrity after", m.projection()["integrity_errors"])
# (4b) torn only line in a fresh ledger (first ever write torn)
m = new(); m.store.segment_path.parent.mkdir(parents=True, exist_ok=True); m.store.segment_path.write_bytes(b'{"partial')
print("(4b) torn first line integrity", m.projection()["integrity_errors"]); print("    recover", m.store.recover("impl:a")["recovered"], m.projection()["integrity_errors"])
