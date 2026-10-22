from common import *
import shutil
m1 = new("h1")
m2home = Path(tempfile.mkdtemp())/"l2"; EventStore.init(m2home,"h2"); m2 = Manager(m2home, actor="impl:b")
m2.create_milestone("MM-B","b")
m1.create_milestone("MM-A","A")
# h2 segment arrives (e.g. git pull, which does not take MM's lock) while m1 is inside _write
orig = m1.store.append
def append(*a, **k):
    shutil.copy(m2.store.segment_path, m1.store.events_dir/"h2.jsonl")
    return orig(*a, **k)
m1.store.append = append
m1.update_milestone("MM-A", title="A2")
m1.store.append = orig
inc = m1.projection(); full = model.fold(model.ordered(m1.store.read_all()))
print("incremental has MM-B:", "MM-B" in inc["milestones"], "| full rebuild has MM-B:", "MM-B" in full["milestones"])
m1.create_milestone("MM-C","C")
print("after another write, incremental has MM-B:", "MM-B" in m1.projection()["milestones"])
