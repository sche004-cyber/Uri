from common import *
import shutil, time
base = Path(tempfile.mkdtemp()); H = {}
for h in ("h1","h2","h3"):
    EventStore.init(base/h, h); H[h] = Manager(base/h, actor=f"impl:{h}")
def share(src, dst): shutil.copy(H[src].store.segment_path, H[dst].store.events_dir/f"{src}.jsonl")
H["h1"].create_milestone("MM-A","A"); share("h1","h2"); share("h1","h3")
H["h1"].update_milestone("MM-A", title="h1 title"); time.sleep(0.02)
H["h2"].update_milestone("MM-A", title="h2 title"); time.sleep(0.02)
H["h3"].update_milestone("MM-A", next_action="h3 says: do NOT ship, regression found"); time.sleep(0.02)
share("h2","h1")
p = H["h1"].projection(); print("h1 sees open conflicts:", [(c["type"],c["event"]["seg"]) for c in p["conflicts"] if not c["resolved"]])
H["h1"].resolve_conflict("MM-A", "reviewed h2's title change")
share("h3","h1")   # h3's offline edit arrives after the resolution
p = H["h1"].projection()
print("all conflicts:", [(c["type"], c["event"]["seg"], c["resolved"]) for c in p["conflicts"]])
print("next_action:", p["milestones"]["MM-A"]["next_action"])
