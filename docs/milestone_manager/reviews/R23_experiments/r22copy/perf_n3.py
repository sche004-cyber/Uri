from pathlib import Path
import json, statistics, subprocess, sys, tempfile, time
from pathlib import Path
SRC="C:/Users/cheta/AppData/Local/Temp/r23_0nhyl83y/src"; sys.path.insert(0, SRC); tempfile.tempdir="C:/Users/cheta/AppData/Local/Temp/r23_0nhyl83y/tmp"
from scripts.dev_workflow.milestones import views
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore

home = Path(tempfile.mkdtemp()) / "l"
EventStore.init(home, "perf")
m = Manager(home, actor="perf")
m.create_milestone("MM-A", "A")
with m.store.locked():
    for i in range(10_000):
        m.store.append("EVIDENCE_ADDED", {"id": f"EV-{i:016x}", "subject": "MM-A", "kind": "log", "ref": f"r{i}",
                                          "sha256": None, "commit": None, "result_class": "COMPLETED_WITH_RESULT",
                                          "summary": "perf"}, actor="perf")
m.store.write_anchors(m.store.read_all())
res = {"bytes": m.store.segment_path.stat().st_size}
for name, fn in (("rebuild", m.projection), ("status_lines", lambda: views.status_lines(m.projection())),
                 ("status_json", lambda: views.status_json(m.projection()))):
    ts = []
    for _ in range(5):
        t0 = time.perf_counter(); fn(); ts.append(time.perf_counter() - t0)
    res[name] = {"median_s": round(statistics.median(ts), 3), "max_s": round(max(ts), 3)}
for args in (["status", "--no-tasks"], ["status", "--json", "--no-tasks"]):
    ts = []
    for _ in range(3):
        t0 = time.perf_counter()
        subprocess.run([sys.executable, "-X", "utf8", "-m", "scripts.dev_workflow.milestones", "--home", str(home), *args],
                       cwd=SRC, capture_output=True, check=True)
        ts.append(time.perf_counter() - t0)
    res["cli " + " ".join(args)] = {"median_s": round(statistics.median(ts), 3), "max_s": round(max(ts), 3)}
print(json.dumps(res, indent=1))
