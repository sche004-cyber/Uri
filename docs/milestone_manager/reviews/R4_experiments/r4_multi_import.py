from common import *
import shutil
src = Path("D:/uri-dev/uri-p0-audit/decisions.md")
base = Path(tempfile.mkdtemp())
EventStore.init(base/"A","ha"); A = Manager(base/"A", actor="impl:a")
EventStore.init(base/"B","hb"); B = Manager(base/"B", actor="impl:b")
importers.import_decisions(A, src, "8e1d6324"); importers.import_decisions(B, src, "8e1d6324")
shutil.copy(A.store.segment_path, B.store.events_dir/"ha.jsonl"); shutil.copy(B.store.segment_path, A.store.events_dir/"hb.jsonl")
pa, pb = A.projection(), B.projection()
import json
strip = lambda p: json.dumps({k: p[k] for k in ("decisions","conflicts","approvals")}, sort_keys=True, default=str)
print("projections identical:", strip(pa)==strip(pb))
print("decisions", len(pa["decisions"]), "conflict types", {c["type"]:0 for c in pa["conflicts"]}.keys(), len(pa["conflicts"]))
dups = {k:v for k,v in pa["decisions"].items() if "@" in k}
bad=[]
for k,d in pa["decisions"].items():
    for s in d["superseded_by"]:
        # link must stay within same origin segment
        if ("@" in k) != ("@" in s["by"]): bad.append((k,s["by"]))
    for s in d["supersedes"]:
        if ("@" in k) != ("@" in s["id"]): bad.append((s["id"],k))
print("cross-origin links:", bad[:5], "unbound:", [c for c in pa["conflicts"] if c["type"]=="UNBOUND_REFERENCE"][:2])
# re-import on A after merge: what happens to B's duplicates?
r = importers.import_decisions(A, src, "8e1d6324"); print("re-import after merge: rec", r["recorded"], "unch", r["unchanged"], "coll", len(r["collisions"]), "sup", r["supersessions"])
