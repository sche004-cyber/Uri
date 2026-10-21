from common import *
import shutil, datetime as dt, io
import scripts.dev_workflow.milestones.store as S
real = S.utc_now
base = Path(tempfile.mkdtemp())
EventStore.init(base/"h1","h1"); a = Manager(base/"h1", actor="impl:a")
EventStore.init(base/"h2","h2"); b = Manager(base/"h2", actor="impl:b")
b.record_decision("Old","old","2026-10-21","OWNER-PROMPT","chat")
S.utc_now = lambda: (dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")  # h2 clock 1h ahead
b.record_decision("New","new","2026-10-21","OWNER-PROMPT","chat", supersedes="LDEC-001")
S.utc_now = real
lines = b.store.segment_path.read_bytes().split(b"\n")[:-1]
(a.store.events_dir/"h2.jsonl").write_bytes(b"\n".join(lines[:-1])+b"\n")   # h1 receives h2's segment missing the batch's 2nd event
print("h1 warnings:", a.projection()["integrity_warnings"], "errors:", a.projection()["integrity_errors"])
for i in range(2):
    o=io.StringIO(); rc=cli.run(["--home",str(a.home),"--actor","impl:a","recover"],out=o); print("recover rc", rc, json.loads(o.getvalue()).get("abandoned_batches"))
    print("  warnings after:", a.projection()["integrity_warnings"])
