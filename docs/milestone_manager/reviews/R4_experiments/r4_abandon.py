from common import *
import shutil, datetime as dt, io
import scripts.dev_workflow.milestones.store as S, scripts.dev_workflow.milestones.service as SV
real = S.utc_now
base = Path(tempfile.mkdtemp())
EventStore.init(base/"B","b"); B = Manager(base/"B", actor="impl:b")
EventStore.init(base/"A","a"); A = Manager(base/"A", actor="impl:a")
B.record_decision("Old","old","2026-10-21","OWNER-PROMPT","chat")
B.record_decision("New","new","2026-10-21","OWNER-PROMPT","chat", supersedes="LDEC-001")
print("B before:", {k:v["status"] for k,v in B.projection()["decisions"].items()})
lines = B.store.segment_path.read_bytes().split(b"\n")[:-1]
(A.store.events_dir/"b.jsonl").write_bytes(b"\n".join(lines[:-1])+b"\n")   # A receives b's segment mid-sync
f = lambda: (dt.datetime.now(dt.timezone.utc)-dt.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
S.utc_now = f; SV.store_now = f   # A's clock 5 min behind
o=io.StringIO(); rc=cli.run(["--home",str(A.home),"--actor","impl:a","recover"],out=o); print("A recover rc", rc, json.loads(o.getvalue()).get("abandoned_batches"))
S.utc_now = real; SV.store_now = real
shutil.copy(B.store.segment_path, A.store.events_dir/"b.jsonl"); shutil.copy(A.store.segment_path, B.store.events_dir/"a.jsonl")
for who,m in (("B",B),("A",A)):
    p=m.projection(); print(who, "after full sync:", {k:v["status"] for k,v in p["decisions"].items()}, "warn", p["integrity_warnings"])
