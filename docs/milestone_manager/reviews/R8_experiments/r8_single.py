from common import *
import io
import scripts.dev_workflow.milestones.store as S
# host's first command single-event, anchors refreshed OK; second command multi-event torn after line 0
m = new(); m.create_milestone("MM-A","A")
m.record_decision("T","D","2026-10-21","REPO-RECORD","s"); m.record_decision("T2","D2","2026-10-21","REPO-RECORD","s", supersedes="LDEC-001")
L = m.store.segment_path.read_bytes().split(b"\n")[:-1]
anch = json.loads(m.store.anchors_path.read_text()); anch["h1"] = {"count": 3, "head": json.loads(L[2])["hash"]}
m.store.anchors_path.write_text(json.dumps(anch))
m.store.segment_path.write_bytes(b"\n".join(L[:-1]) + b"\n" + L[-1][:100])
o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=o); print("anchored single-first, torn 2nd batch: rc", rc, o.getvalue().replace("\n"," ")[:160])
# first single-event command with failed anchor refresh, then multi-event (gets ANCHORS_ADOPTED prepended) torn
m = new(); ia = m.store.anchors_path.read_bytes(); m.create_milestone("MM-A","A"); m.store.anchors_path.write_bytes(ia)
m.create_milestone("MM-B","B")   # becomes batch ANCHORS_ADOPTED + create
L = m.store.segment_path.read_bytes().split(b"\n")[:-1]; m.store.anchors_path.write_bytes(ia)
m.store.segment_path.write_bytes(b"\n".join(L[:-1]) + b"\n" + L[-1][:150])
o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=o); print("unanchored single-first, torn batch: rc", rc, o.getvalue().replace("\n"," ")[:200])
o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "recover", "--acknowledge-loss"], out=o); print("  with ack: rc", rc, "| open", [c["type"] for c in m.projection()["conflicts"] if not c["resolved"]])
print(m.store.anchor_warnings(m.store.read_all(), {"h1":{"count":0,"head":"0"*64}}))
