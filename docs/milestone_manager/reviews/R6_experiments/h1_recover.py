from common import *
import io, shutil
def torn(m, b=b'{"x'):
    with m.store.segment_path.open("ab") as f: f.write(b)
def openal(m): return [c for c in m.projection()["conflicts"] if c["type"]=="ANCHOR_LOSS" and not c["resolved"]]
def tryrec(label, m, ack=False):
    try:
        r = m.store.recover("impl:a", None, ack); print(f"{label}: recovered={r.get('recovered')} problems={r.get('anchor_problems')} AL={len(openal(m))} verify={m.store.verify()['ok']}")
    except StoreError as e: print(f"{label}: REFUSED {e.code} {str(e)[:160]}")
# a healthy torn tail
m = new(); m.create_milestone("MM-A","A"); m.create_milestone("MM-B","B"); torn(m); tryrec("a healthy torn", m)
# b first write crash (only torn bytes)
m = new(); torn(m); tryrec("b first-write torn", m)
# c init-host clone then first write torn
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); A=Manager(base/"A",actor="impl:a"); A.create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base/"B","hb")
B=Manager(base/"B",actor="impl:b"); torn(B); tryrec("c init-host first-write torn", B)
B.create_milestone("MM-B","B"); print("   after write AL", len(openal(B)), B.projection()["integrity_warnings"])
# d init-host then write then torn
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); A=Manager(base/"A",actor="impl:a"); A.create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base/"B","hb")
B=Manager(base/"B",actor="impl:b"); B.create_milestone("MM-B","B"); torn(B); tryrec("d init-host write torn", B)
# e partial multi-event batch: write full lines of first event of a batch + torn
m = new(); m.create_milestone("MM-A","A")
segbefore = m.store.segment_path.read_bytes()
m.create_milestone("MM-B","B", depends_on=["MM-A"])
# use a batch command: import register produces multi-event batch; emulate by cutting last write partially
data = m.store.segment_path.read_bytes()
print("e: lines", data.count(b"\n"))
# f: crash after append on first write before anchors refresh (anchors own count 0), then torn on 2nd write
m = new(); m.create_milestone("MM-A","A"); a=m.store.read_anchors(); a["h1"]={"count":0,"head":"0"*64}; m.store.anchors_path.write_text(json.dumps(a))
torn(m); tryrec("f first refresh lost + torn 2nd write", m)
# g crash after append on first write (no torn), next write
m = new(); m.create_milestone("MM-A","A"); a=m.store.read_anchors(); a["h1"]={"count":0,"head":"0"*64}; m.store.anchors_path.write_text(json.dumps(a))
m.create_milestone("MM-B","B"); print("g first refresh lost then write: AL", len(openal(m)))
# h: other host segment pulled with torn tail + own torn
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); A=Manager(base/"A",actor="impl:a"); A.create_milestone("MM-A","A")
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base/"B","hb")
B=Manager(base/"B",actor="impl:b"); B.create_milestone("MM-B","B")
A.create_milestone("MM-C","C"); shutil.copy(A.store.segment_path, B.store.events_dir/"ha.jsonl"); 
with (B.store.events_dir/"ha.jsonl").open("ab") as f: f.write(b'{"y')
torn(B); tryrec("h other torn + own torn", B)
# i: silent rebase via wiping local/ and init-host with new id after truncation
m = new(); m.create_milestone("MM-A","A"); m.update_milestone("MM-A", candidate_commit=C1)
m.record_review("MM-A", C1, "subagent", "rev:x", "SUBAGENT", "REJECT", 2, 2, "COMPLETED_WITH_RESULT", "bad")
lines = m.store.segment_path.read_bytes().split(b"\n")[:-1]; m.store.segment_path.write_bytes(b"\n".join(lines[:-1])+b"\n")
print("i before: verify", m.store.verify()["ok"])
shutil.rmtree(m.home/"local"); EventStore.init_host(m.home, "h2"); m2 = Manager(m.home, actor="impl:a")
p = m2.projection(); print("i after wipe+init-host: errors", p["integrity_errors"], "warnings", p["integrity_warnings"], "AL", len(openal(m2)), "RV-1 present", "RV-1" in p["reviews"])
