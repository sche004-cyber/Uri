from common import *
import io, shutil
import scripts.dev_workflow.milestones.store as S
w = Path(tempfile.mkdtemp())
# R5-03
reg = w/"r.md"
def wr(st): reg.write_text("# Reg X\n\n## B. Capabilities\n\n| ID | Capability | Status |\n|---|---|---|\n| CAP-1 | thing | "+st+" |\n", encoding="utf-8")
m = new(); wr("RED broken"); importers.import_register(m, reg); wr("YELLOW partial"); importers.import_register(m, reg); wr("GREEN ok"); importers.import_register(m, reg)
r = m.projection()["records"]["REG-B-CAP-1"]
print("R5-03 original", r["original"]["fields"]["status"], "| revisions", [(x["previous"]["fields"]["status"], x["fields"]["status"]) for x in r["revisions"]], "| current", r["fields"]["status"])
# CLI collision exit
other = w/"o.md"; other.write_text("# Other Reg\n\n## B. Capabilities\n\n| ID | Capability | Status |\n|---|---|---|\n| CAP-1 | other | RED x |\n| CAP-2 | other2 | RED y |\n", encoding="utf-8")
o = io.StringIO(); rc = cli.run(["--home", str(m.home), "--actor", "impl:a", "import-register", str(other)], out=o); print("R5-02 CLI rc", rc, json.loads(o.getvalue()).get("collisions"), json.loads(o.getvalue()).get("recorded"))
# R5-09 BOM
bom = w/"bom.md"; bom.write_bytes(b"\xef\xbb\xbf" + reg.read_bytes()); m2 = new()
try: print("R5-09 BOM register:", importers.import_register(m2, bom)["recorded"])
except Exception as e: print("R5-09 BOM register FAIL", e)
dsrc = Path("D:/uri-dev/uri-p0-audit/decisions.md"); dbom = w/"decisions.md"; dbom.write_bytes(b"\xef\xbb\xbf"+dsrc.read_bytes())
try: rr = importers.import_decisions(new(), dbom); print("R5-09 BOM decisions:", rr["recorded"], len(rr["collisions"]))
except Exception as e: print("R5-09 BOM decisions FAIL", e)
# BOM + same register identity as non-BOM: idempotent?
m3 = new(); importers.import_register(m3, reg); print("  BOM after non-BOM same register:", {k: v for k, v in importers.import_register(m3, bom).items() if k in ("recorded","revised","unchanged","collisions")})
# R5-08
for bad in ({"h1": {"count": "3", "head": "0"*64}}, {"h1": {"count": -1, "head": "0"*64}}, {"h1": {"count": 1, "head": "abc"}}, {"h1": {"count": True, "head": "0"*64}}, {"h1": {"count": 1.0, "head": "0"*64}}):
    m = new(); m.create_milestone("MM-A","A"); m.store.anchors_path.write_text(json.dumps(bad))
    o = io.StringIO(); rc = cli.run(["--home", str(m.home), "verify"], out=o); print("R5-08", bad["h1"], "verify rc", rc)
# R5-05: other host far in future, then reanchor ack / recover
base = Path(tempfile.mkdtemp()); EventStore.init(base/"A","ha"); A=Manager(base/"A",actor="impl:a")
orig = S.utc_now; S.utc_now = lambda: "2030-01-01T00:00:00.000000Z"; A.create_milestone("MM-A","A"); S.utc_now = orig
shutil.copytree(base/"A", base/"B", ignore=shutil.ignore_patterns("local")); EventStore.init_host(base/"B","hb"); B=Manager(base/"B",actor="impl:b")
B.create_milestone("MM-B","B"); 
with B.store.segment_path.open("ab") as f: f.write(b'{"x')
rec = B.store.recover("impl:b"); B.store.reanchor("impl:b","r", acknowledge_loss=True)
evs = [json.loads(l) for l in B.store.segment_path.read_text(encoding="utf-8").splitlines()]
print("R5-05", [(e["kind"], e["ts"]) for e in evs])
p = B.projection(); print("R5-06 warnings", p["integrity_warnings"])
# R5-07
from scripts.dev_workflow.milestones import views
m = new(); m.create_milestone("MM-A","A"); p = m.projection(); views.status_json(p); print("R5-07 _cidx before", "_cidx" in p)
model.apply(p, {"v":1,"seg":"h1","seq":99,"ts":"2099","actor":"x","session":None,"kind":"ANCHORS_ADOPTED","data":{},"base":{},"prev":"","hash":"h"*64}); print("  after apply", "_cidx" in p)
