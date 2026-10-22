from common import *
import shutil, datetime as dt
import scripts.dev_workflow.milestones.store as S
import scripts.dev_workflow.milestones.service as SV
real = S.utc_now
def at(delta_h):
    f = lambda: (dt.datetime.now(dt.timezone.utc)+dt.timedelta(hours=delta_h)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    S.utc_now = f; SV.store_now = f
def reset(): S.utc_now = real; SV.store_now = real
base = Path(tempfile.mkdtemp())
# host "a" lags; host "b" correct. names chosen so lagging host sorts FIRST
EventStore.init(base/"B","b"); B = Manager(base/"B", actor="impl:b")
EventStore.init(base/"A","a"); A = Manager(base/"A", actor="impl:a")
def sync():
    shutil.copy(B.store.segment_path, A.store.events_dir/"b.jsonl")
    if A.store.segment_path.exists(): shutil.copy(A.store.segment_path, B.store.events_dir/"a.jsonl")
B.create_milestone("MM-X","X"); B.update_milestone("MM-X", candidate_commit=C1)
B.request_approval("MM-X","INTEGRATION","integrate?"); sync()
at(-1); A.resolve_approval("AP-1","APPROVED","yes","chat"); print("A warnings:", A.last_warnings[:1]); reset(); sync()
for who,m in (("b",B),("a",A)):
    p = m.projection()
    print(who, "AP-1:", p["approvals"]["AP-1"]["status"], "| open conflicts:", [(c["type"],c["entity"]) for c in p["conflicts"] if not c["resolved"]])
evs = [e for s in A.store.read_all() for e in s.valid_events]
from scripts.dev_workflow.milestones import model as Mo
print("fold order:", [(e["seg"],e["seq"],e["kind"],e["ts"][11:26]) for e in Mo.ordered(A.store.read_all())])
# Future clock: host b 30 days ahead writes one event; then all hosts pinned
base = Path(tempfile.mkdtemp())
EventStore.init(base/"B","b"); B = Manager(base/"B", actor="impl:b")
EventStore.init(base/"A","a"); A = Manager(base/"A", actor="impl:a")
at(24*30); B.create_milestone("MM-F","F"); reset(); sync()
A.create_milestone("MM-G","G"); print("future: A warnings:", A.last_warnings)
A.create_milestone("MM-H","H"); sync()
B.create_milestone("MM-I","I"); print("future: B (correct clock now) warnings:", B.last_warnings)
print("ts:", [(e["seg"],e["data"].get("id"),e["ts"][:19]) for e in Mo.ordered(A.store.read_all())])
# causal inversion under pinned ts: B (pinned) requests approval, A (pinned) resolves; A's seg 'a' < 'b'
B.update_milestone("MM-F", candidate_commit=C1); B.request_approval("MM-F","INTEGRATION","q?"); sync()
A.resolve_approval("AP-1","APPROVED","yes","chat"); sync()
for who,m in (("b",B),("a",A)):
    p = m.projection(); print(who, "AP-1:", p["approvals"]["AP-1"]["status"], [(c["type"],c["entity"]) for c in p["conflicts"] if not c["resolved"]])
